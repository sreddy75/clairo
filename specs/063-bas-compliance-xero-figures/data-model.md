# Data Model: BAS Compliance Round 2

**Branch**: `063-bas-compliance-xero-figures`  
**Date**: 2026-04-29

## No New Tables or Columns

This spec requires no schema additions. All changes are to existing query logic, frontend state, and one data cleanup migration.

---

## Modified Query: ReconciliationStatus

**File**: `backend/app/modules/bas/repository.py` — `get_reconciliation_status`

Current response shape:
```python
{
    "total_transactions": int,
    "unreconciled_count": int,
}
```

Extended response shape (this spec):
```python
{
    "total_transactions": int,
    "unreconciled_count": int,
    "balance_discrepancy": Decimal,   # SUM of sub_total for unreconciled rows; 0 if all reconciled
}
```

The `balance_discrepancy` is computed by adding `SUM(sub_total) FILTER (WHERE NOT is_reconciled)` to the existing COUNT query on `XeroBankTransaction`. No new column — the `sub_total` field already exists on that model.

### Updated Frontend Type

`frontend/src/lib/bas.ts` — `ReconciliationStatus`:
```typescript
export interface ReconciliationStatus {
  unreconciled_count: number;
  total_transactions: number;
  balance_discrepancy: number;   // new
  as_of: string | null;
}
```

---

## Frontend State: `proceededWithUnreconciled`

Already exists in `BASTab.tsx`. No changes to shape.

Behaviour change: this flag is now checked in `handleCalculate` (pre-check) rather than only being set reactively from the session-selection `useEffect`.

---

## Data Cleanup Migration

**Purpose**: Dismiss existing `TaxCodeSuggestion` records where `tax_type = 'BASEXCLUDED'` (created before the filter was added in 062).

**Approach**: Alembic data migration (not a schema migration — no column changes). Sets `status = 'dismissed'` and `dismissal_reason = 'bas_excluded_auto_cleanup'` on all matching rows.

```sql
-- Migration: dismiss stale BASEXCLUDED suggestions
UPDATE tax_code_suggestions
SET
    status = 'dismissed',
    dismissed_at = NOW(),
    dismissal_reason = 'bas_excluded_auto_cleanup'
WHERE
    tax_type = 'BASEXCLUDED'
    AND status = 'pending';
```

This is idempotent — re-running has no effect on already-dismissed rows.

---

## BASCalculation: No Changes

`payg_source_label` is already present on `BASCalculation`. The W1/W2 fix is purely frontend — no backend changes required.

---

## XeroBASCrossCheckResponse: No Changes

The `xero_error` field already exists in the response schema. The fix is to surface it correctly in the frontend rather than swallowing it silently.

```python
class XeroBASCrossCheckResponse(BaseModel):
    xero_report_found: bool | None
    xero_figures: dict | None
    clairo_figures: dict | None
    differences: dict[str, XeroBASCrossCheckDifference] | None
    period_label: str
    fetched_at: datetime
    xero_error: str | None   # already exists — surfaced to UI in this spec
```
