# API Contracts: AI Tax Code Resolution

**Branch**: `046-ai-tax-code-resolution` | **Date**: 2026-03-14

All endpoints are under the existing BAS router prefix: `/api/v1/clients/{connection_id}/bas/sessions/{session_id}/`

## Endpoints

### GET /tax-code-suggestions

List all tax code suggestions for a BAS session.

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | all | Filter: `pending`, `approved`, `rejected`, `overridden`, `dismissed` |
| `confidence_tier` | string | all | Filter: `account_default`, `client_history`, `tenant_history`, `llm_classification` |
| `min_confidence` | float | 0.0 | Minimum confidence score |

**Response 200**:
```json
{
  "suggestions": [
    {
      "id": "uuid",
      "source_type": "invoice",
      "source_id": "uuid",
      "line_item_index": 0,
      "line_item_id": "xero-line-item-id",
      "original_tax_type": "NONE",
      "suggested_tax_type": "OUTPUT",
      "applied_tax_type": null,
      "confidence_score": 0.95,
      "confidence_tier": "account_default",
      "suggestion_basis": "Account 200 (Sales) has default tax type OUTPUT",
      "status": "pending",
      "resolved_by": null,
      "resolved_at": null,
      "account_code": "200",
      "account_name": "Sales",
      "description": "Consulting services",
      "line_amount": 1000.00,
      "tax_amount": 0.00,
      "contact_name": "Acme Corp",
      "transaction_date": "2026-01-15"
    }
  ],
  "summary": {
    "total": 23,
    "pending": 15,
    "approved": 5,
    "rejected": 1,
    "overridden": 1,
    "dismissed": 1,
    "total_excluded_amount": 14280.00,
    "total_resolved_amount": 5200.00,
    "high_confidence_count": 12,
    "medium_confidence_count": 6,
    "low_confidence_count": 5
  }
}
```

---

### POST /tax-code-suggestions/generate

Trigger suggestion generation for the session. Idempotent — re-running preserves existing resolved suggestions.

**Request Body**: None (all context derived from session)

**Response 200**:
```json
{
  "generated": 23,
  "skipped_already_resolved": 5,
  "breakdown": {
    "account_default": 12,
    "client_history": 5,
    "tenant_history": 3,
    "llm_classification": 2,
    "no_suggestion": 1
  }
}
```

**Response 409**: Session not in editable state

---

### POST /tax-code-suggestions/{suggestion_id}/approve

Approve a single suggestion. Applies the suggested tax code.

**Request Body**:
```json
{
  "notes": "optional approval notes"
}
```

**Response 200**:
```json
{
  "id": "uuid",
  "status": "approved",
  "applied_tax_type": "OUTPUT",
  "resolved_by": "user-uuid",
  "resolved_at": "2026-03-14T10:30:00Z"
}
```

**Response 404**: Suggestion not found
**Response 409**: Suggestion already resolved or session not editable

---

### POST /tax-code-suggestions/{suggestion_id}/reject

Reject a suggestion. Transaction remains excluded from BAS.

**Request Body**:
```json
{
  "reason": "optional rejection reason"
}
```

**Response 200**: Same shape as approve with `status: "rejected"`

---

### POST /tax-code-suggestions/{suggestion_id}/override

Override a suggestion with a different tax code.

**Request Body**:
```json
{
  "tax_type": "INPUT",
  "reason": "optional override reason"
}
```

**Validation**: `tax_type` must be a key in `TAX_TYPE_MAPPING` and not map to `excluded`.

**Response 200**: Same shape as approve with `status: "overridden"`, `applied_tax_type: "INPUT"`
**Response 422**: Invalid tax type

---

### POST /tax-code-suggestions/{suggestion_id}/dismiss

Dismiss a transaction — confirm it should remain excluded from BAS.

**Request Body**:
```json
{
  "reason": "This is a personal expense, correctly excluded"
}
```

**Response 200**: Same shape as approve with `status: "dismissed"`

---

### POST /tax-code-suggestions/bulk-approve

Approve all pending suggestions at or above a confidence threshold.

**Request Body**:
```json
{
  "min_confidence": 0.90,
  "confidence_tier": "account_default"
}
```

At least one of `min_confidence` or `confidence_tier` is required.

**Response 200**:
```json
{
  "approved_count": 12,
  "suggestion_ids": ["uuid1", "uuid2", "..."]
}
```

---

### POST /tax-code-suggestions/recalculate

Apply all approved/overridden suggestions and recalculate BAS.

**Request Body**: None

**Response 200**:
```json
{
  "applied_count": 8,
  "recalculation": {
    "g1_total_sales_before": 45000.00,
    "g1_total_sales_after": 52000.00,
    "field_1a_before": 4500.00,
    "field_1a_after": 5200.00,
    "g11_before": 22000.00,
    "g11_after": 25500.00,
    "field_1b_before": 2200.00,
    "field_1b_after": 2550.00,
    "net_gst_before": 2300.00,
    "net_gst_after": 2650.00
  }
}
```

**Response 409**: No approved suggestions to apply, or session not editable

---

### GET /tax-code-suggestions/summary

Quick summary for the exclusion banner (lightweight, no pagination).

**Response 200**:
```json
{
  "excluded_count": 23,
  "excluded_amount": 14280.00,
  "resolved_count": 8,
  "unresolved_count": 15,
  "has_suggestions": true,
  "high_confidence_pending": 10,
  "can_bulk_approve": true,
  "blocks_approval": true
}
```

---

### GET /tax-code-suggestions/conflicts

List re-sync conflicts (overrides where Xero data changed).

**Response 200**:
```json
{
  "conflicts": [
    {
      "override_id": "uuid",
      "source_type": "invoice",
      "source_id": "uuid",
      "line_item_index": 0,
      "override_tax_type": "OUTPUT",
      "xero_new_tax_type": "INPUT",
      "description": "Consulting services",
      "line_amount": 1000.00,
      "account_code": "200",
      "detected_at": "2026-03-14T10:00:00Z"
    }
  ],
  "total": 1
}
```

---

### POST /tax-code-suggestions/conflicts/{override_id}/resolve

Resolve a re-sync conflict.

**Request Body**:
```json
{
  "resolution": "keep_override",
  "reason": "optional"
}
```

`resolution` must be one of: `keep_override` (keep local), `accept_xero` (use Xero's new value).

**Response 200**:
```json
{
  "override_id": "uuid",
  "resolution": "keep_override",
  "applied_tax_type": "OUTPUT"
}
```

## Shared Types

### Valid Tax Types (for override dropdown)

The dropdown should present only non-excluded types from `TAX_TYPE_MAPPING`:

```
OUTPUT, OUTPUT2, OUTPUTSALES,
INPUT, INPUT2, INPUT3, INPUTTAXED,
CAPEXINPUT, CAPEXINPUT2,
EXEMPTOUTPUT, EXEMPTINCOME,
EXEMPTEXPENSES,
EXEMPTEXPORT, GSTONEXPORTS,
ZERORATEDINPUT, ZERORATEDOUTPUT
```

An endpoint is not needed — this is a static list derived from `TAX_TYPE_MAPPING`.
