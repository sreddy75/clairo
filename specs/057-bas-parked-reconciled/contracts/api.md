# API Contracts: BAS Transaction Grouping by Xero Reconciliation Status

**Branch**: `057-bas-parked-reconciled` | **Date**: 2026-04-13

---

## Modified: `TaxCodeSuggestion` Response Schema

Two new fields added to the existing `TaxCodeSuggestion` response object returned by all suggestion endpoints.

```typescript
// Additions to existing TaxCodeSuggestion type in frontend/src/lib/bas.ts
interface TaxCodeSuggestion {
  // ... all existing fields ...

  // NEW
  is_reconciled: boolean | null;   // null for invoices/credit notes
  auto_park_reason: string | null; // "unreconciled_in_xero" | null
}
```

**Endpoints returning `TaxCodeSuggestion[]` (all unchanged paths):**
- `GET /{connection_id}/bas/sessions/{session_id}/tax-code-suggestions`
- `POST .../approve`, `.../override`, `.../dismiss`, `.../unpark`

---

## New Endpoint: Refresh Reconciliation Status

### `POST /clients/{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/refresh-reconciliation`

Re-fetches Xero reconciliation status for all bank-transaction suggestions in the session and reclassifies auto-parked / newly-unreconciled suggestions accordingly.

**Auth**: Accountant JWT (Clerk), same as all BAS session endpoints.

**Request body**: None.

**Response `200 OK`**:
```json
{
  "data": {
    "reclassified_count": 3,
    "newly_reconciled": 2,
    "newly_unreconciled": 1
  }
}
```

**Response `503 Service Unavailable`** (Xero connection unavailable):
```json
{
  "error": "Xero connection unavailable",
  "code": "xero_connection_unavailable",
  "details": {}
}
```

**Response `404 Not Found`** (session not found or not accessible):
```json
{
  "error": "BAS session not found",
  "code": "session_not_found",
  "details": {}
}
```

**Side effects**:
- Updates `is_reconciled` and `status` / `auto_park_reason` on affected `TaxCodeSuggestion` rows.
- Writes `transaction.reconciliation_refreshed` audit event.

---

## Modified: `TaxCodeSuggestionSummary` Response

New field added to the existing summary endpoint.

### `GET /{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/summary`

**Response additions**:
```json
{
  "data": {
    // ... all existing fields ...
    "reconciled_count": 12,
    "reconciled_needs_review_count": 2,
    "auto_parked_count": 5
  }
}
```

| Field | Description |
|-------|-------------|
| `reconciled_count` | Total suggestions where `is_reconciled = True` |
| `reconciled_needs_review_count` | Reconciled suggestions where `status = 'pending'` (have a detected issue) |
| `auto_parked_count` | Suggestions where `auto_park_reason = 'unreconciled_in_xero'` |

---

## No New Endpoints for Auto-Park

Auto-parking happens server-side during `generate_suggestions`. There is no client-initiated "auto-park" API call — the frontend reads `auto_park_reason` on each suggestion to determine the display label.
