# API Contract Changes — Tax Planning Calculation Correctness

**Feature**: `059-tax-planning-calculation-correctness`
**Date**: 2026-04-18

Minimal surface changes: one new PATCH endpoint, shape additions on three existing responses, one new response field on plan creation. Fully backward-compatible for non-updated clients (new fields appear but existing ones unchanged).

---

## 1. `POST /api/v1/tax-plans` — **Modified response**

Plan creation now reports payroll sync status so the frontend can render the "payroll still syncing" banner when the 15s synchronous window times out.

### Response (added field)

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "client_id": "uuid",
  "entity_type": "company",
  "financial_year": "2025-26",
  "tax_position": { "...": "..." },
  "financials_data": { "...": "..." },
  "scenarios": [],
  "created_at": "2026-04-18T...",

  // NEW (FR-006)
  "payroll_sync_status": "ready" | "pending" | "unavailable" | "not_required"
}
```

### Semantics

| Value | Meaning |
|-------|---------|
| `ready` | Payroll data is fresh and included in `financials_data.payroll_summary`. |
| `pending` | Sync exceeded the 15s synchronous window; background sync in flight; frontend should poll. |
| `unavailable` | Connection has no payroll access, or sync failed; frontend displays actionable banner. |
| `not_required` | Client has no Xero connection (manual-entry path). |

### Frontend polling

When `payroll_sync_status="pending"`, the frontend polls `GET /api/v1/tax-plans/{id}` every 3s (back off to 10s after 30s wall clock; cap at 2 minutes). The server's response includes the updated `payroll_sync_status` and, once ready, the recomputed `tax_position` and `financials_data`.

---

## 2. `GET /api/v1/tax-plans/{plan_id}/analysis` — **Modified response**

Analysis response now returns confirmed financials alongside AI-derived output, so the UI can show source-of-truth next to AI commentary (FR-013).

### Response (added fields)

```json
{
  "client_profile": { "...": "existing" },
  "strategies_evaluated": [ "...": "existing" ],
  "recommended_scenarios": [ "...": "existing (but each scenario now includes strategy_category, requires_group_model, source_tags)" ],
  "combined_strategy": { "...": "existing" },
  "accountant_brief": "markdown...",
  "client_summary": "markdown...",
  "review_result": { "...": "existing" },
  "implementation_items": [ "...": "existing" ],

  // NEW
  "financials_data": {
    "income": { "...": "..." },
    "expenses": { "...": "..." },
    "credits": { "...": "..." },
    "payroll_summary": { "...": "..." },
    "projection_metadata": {
      "applied": true,
      "rule": "linear",
      "months_elapsed": 6,
      "months_projected": 6,
      "ytd_snapshot": { "...": "..." },
      "applied_at": "2026-04-18T...",
      "reason": null
    }
  }
}
```

---

## 3. `GET /api/v1/tax-plans/{plan_id}/scenarios` (and embedded scenarios on plan / analysis responses) — **Modified response**

Every scenario response adds three new fields from the data model.

### Response (added fields per scenario)

```json
{
  "id": "uuid",
  "title": "Prepay rent",
  "description": "...",
  "impact_data": { "...": "existing shape" },
  "assumptions": [
    { "label": "Prepay $25,000 of rent", "amount": 25000, "baseline_ref": null }
  ],

  // NEW
  "strategy_category": "prepayment",
  "requires_group_model": false,
  "source_tags": {
    "impact_data.modified_expenses.operating_expenses": "estimated",
    "assumptions.0.amount": "estimated"
  }
}
```

---

## 4. `PATCH /api/v1/tax-plans/{plan_id}/scenarios/{scenario_id}/assumptions/{field_path}` — **NEW endpoint (FR-015)**

Allows the accountant to confirm (or replace) an AI-generated *estimated* figure from the UI's inline-edit-to-confirm component.

### Path parameters

- `plan_id` — UUID of the tax plan.
- `scenario_id` — UUID of the scenario.
- `field_path` — URL-encoded JSON Pointer (RFC 6901) into the scenario's `impact_data` or `assumptions` blob. Example: `assumptions.0.amount` or `impact_data.modified_expenses.operating_expenses`.

### Request body

```json
{
  "value": 25000
}
```

`value` may be a number (for amount fields) or string (for labels). If the field is a number, the server accepts int, float, or numeric string (parsed to Decimal).

### Response

```json
{
  "scenario_id": "uuid",
  "field_path": "assumptions.0.amount",
  "old_value": 25000,
  "new_value": 25000,
  "old_provenance": "estimated",
  "new_provenance": "confirmed"
}
```

### Status codes

- `200 OK` — confirmation persisted.
- `400 Bad Request` — `field_path` does not resolve to a numeric leaf, or `value` is malformed.
- `404 Not Found` — plan or scenario not found for the tenant.
- `409 Conflict` — field was already confirmed (returned for idempotency visibility; PATCH with identical value is treated as 200).

### Audit

Emits `tax_planning.scenario.provenance_confirmed` event with `old_value`, `new_value`, `old_provenance`, `new_provenance`.

---

## 5. Message / chat responses — **Modified citation verification**

Every chat response that includes citation verification now can report `status="low_confidence"` and includes `matched_by` detail for every verified citation.

### Response (modified `citation_verification` block)

```json
{
  "citation_verification": {
    "status": "verified" | "partially_verified" | "unverified" | "no_citations" | "low_confidence",
    "verified_count": 3,
    "total_citations": 3,
    "confidence_score": 0.82,
    "citations": [
      {
        "identifier": "TR 98/1",
        "verified": true,
        "matched_by": "ruling_number"
      },
      {
        "identifier": "s25-10 ITAA 1997",
        "verified": true,
        "matched_by": "body_text"   // NEW: fallback match against chunk body
      }
    ]
  }
}
```

### Streaming fix

The streaming event sequence changes so the verification event is sent **before** the `done` event — not after. Existing clients that handle `verification` events unchanged; the fix eliminates the race where live messages rendered without the badge.

---

## 6. Analysis review surfaces — **Modified review_result**

The review result carries per-field delta information when verification fails.

### Response (modified `review_result` block)

```json
{
  "review_result": {
    "numbers_verified": false,
    "disagreements": [                // NEW
      {
        "scenario_id": "uuid",
        "field_path": "impact_data.before.tax_payable",
        "expected": 37500.00,
        "got": 36500.00,
        "delta": 1000.00
      }
    ],
    "review_notes": "...existing..."
  }
}
```

When `numbers_verified=true`, `disagreements` is an empty array.

---

## Backward compatibility

- All new fields are additive. Existing clients that ignore unknown fields keep working.
- `status="low_confidence"` is a new enum value. The existing frontend already falls through to `"no_citations"` rendering for unknown values, so pre-deploy frontends don't crash — they just show the wrong badge until the frontend ships.
- `PATCH /assumptions/{field_path}` is a new endpoint. No existing route modified.
- The streaming-event ordering change (verification before `done`) is semantically safe for any client that handles events by type rather than position.

---

## Out of this contract (noted)

- **Bulk confirm endpoint** — explicitly excluded from this spec (see spec FR-015, "MUST NOT offer a bulk 'confirm all' action").
- **Group tax model endpoints** — next spec.
- **Streaming SSE for payroll sync completion** — opted for polling per research.md R3.

---

**Status**: API contract complete. See `quickstart.md` for developer setup and verification steps.
