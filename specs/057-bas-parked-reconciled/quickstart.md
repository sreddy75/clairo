# Developer Quickstart: BAS Transaction Grouping by Xero Reconciliation Status

**Branch**: `057-bas-parked-reconciled`

---

## What This Feature Does

When tax code suggestions are generated for a BAS session, unreconciled Xero bank transactions are automatically placed in the "Parked" state. Reconciled transactions are grouped in a new collapsible "Reconciled" accordion section in the BAS UI. Accountants can manually refresh reconciliation status from Xero at any time.

---

## Key Files to Touch

### Backend

| File | Change |
|------|--------|
| `backend/app/modules/bas/models.py` | Add `is_reconciled` + `auto_park_reason` to `TaxCodeSuggestion` |
| `backend/app/modules/bas/schemas.py` | Add fields to `TaxCodeSuggestionResponse` + `TaxCodeSuggestionSummary` |
| `backend/app/modules/bas/repository.py` | Add `apply_reconciliation_refresh()`, `get_bank_transaction_source_ids()`, extend `list_suggestions()` and `get_suggestion_summary()` |
| `backend/app/modules/bas/service.py` | Extend `generate_suggestions()` to join `XeroBankTransaction` and auto-park; add `refresh_reconciliation_status()` service method |
| `backend/app/modules/bas/router.py` | Add `POST .../refresh-reconciliation` endpoint |
| `backend/app/modules/bas/exceptions.py` | Add `XeroConnectionUnavailableError` if not already present |
| `backend/app/alembic/versions/20260413_add_reconciliation_fields_to_suggestions.py` | Migration: two new nullable columns + index |

### Frontend

| File | Change |
|------|--------|
| `frontend/src/lib/bas.ts` | Add `is_reconciled`, `auto_park_reason` to `TaxCodeSuggestion` type; add `reconciled_count`, `reconciled_needs_review_count`, `auto_parked_count` to `TaxCodeSuggestionSummary`; add `refreshReconciliationStatus()` API function |
| `frontend/src/components/bas/TaxCodeResolutionPanel.tsx` | Add `reconciled` bucket; add "Reconciled" `AccordionItem`; extend "Parked" section to show auto-park label; add "Refresh reconciliation status" button |
| `frontend/src/components/bas/TaxCodeSuggestionCard.tsx` | Show "Unreconciled in Xero" badge when `auto_park_reason === 'unreconciled_in_xero'` |

---

## Running After Changes

```sh
# Backend — run migration
cd backend && uv run alembic upgrade head

# Backend — run tests
cd backend && uv run pytest -k "suggestion or reconcil"

# Backend — lint
cd backend && uv run ruff check . && uv run ruff format .

# Frontend — typecheck
cd frontend && npx tsc --noEmit

# Frontend — lint
cd frontend && npm run lint
```

---

## Critical Constraints

1. **Auto-park only on first generation**: `bulk_create_suggestions` uses `ON CONFLICT DO NOTHING` — existing rows are never overwritten. Auto-park logic runs only when inserting new suggestion rows.
2. **Never re-park an acted-on suggestion**: `apply_reconciliation_refresh()` checks `auto_park_reason IS NOT NULL` before clearing to `pending`. Manually parked (`auto_park_reason IS NULL`) and approved/overridden rows are never touched by refresh.
3. **Non-bank transactions**: `is_reconciled = None` for invoices and credit notes. The Reconciled section only shows suggestions with `is_reconciled = True`.
4. **Cross-module join pattern**: `service.py` in `bas` module may query `XeroBankTransaction` only via the `integrations/xero` public service interface, not by importing models directly.
5. **`tenant_id` on all queries**: Both the reconciliation status query and the suggestion update must include `tenant_id` for RLS compliance.

---

## Auto-Park Logic Summary (generate_suggestions)

```python
# In generate_suggestions() — after building TaxCodeSuggestion objects for bank transactions
# but before calling bulk_create_suggestions():

xero_ids = [s.source_id for s in suggestions if s.source_type == "bank_transaction"]
reconciled_map = await xero_service.get_reconciliation_status_map(connection_id, xero_ids)

for s in suggestions:
    if s.source_type == "bank_transaction":
        s.is_reconciled = reconciled_map.get(str(s.source_id), False)
        if not s.is_reconciled:
            s.status = "dismissed"
            s.auto_park_reason = "unreconciled_in_xero"
```

---

## Frontend Bucket Change (TaxCodeResolutionPanel)

Current 5 buckets → New 6 buckets:

| Bucket | Condition (before) | Condition (after) |
|--------|-------------------|-------------------|
| `highConfidence` | pending, score ≥ 0.9 | pending, `is_reconciled != true`, score ≥ 0.9 |
| `needsReview` | pending, score 0.7–0.9 | pending, `is_reconciled != true`, score 0.7–0.9 |
| `manual` | pending, score < 0.7 or null | pending, `is_reconciled != true`, score < 0.7 or null |
| `parked` | dismissed or rejected | dismissed or rejected (unchanged — `auto_park_reason` only affects display label) |
| `resolved` | approved or overridden | approved or overridden, `is_reconciled != true` |
| **`reconciled`** | *(new)* | `is_reconciled === true` (all statuses) |

The `reconciled` bucket catches **all** suggestions where `is_reconciled === true`, regardless of status. This means a reconciled suggestion that has been approved still appears in the Reconciled section, not in the Resolved section. This intentional — "reconciled in Xero" is the primary grouping signal.
