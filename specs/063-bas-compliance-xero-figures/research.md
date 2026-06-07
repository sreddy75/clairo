# Research: BAS Compliance Round 2

**Branch**: `063-bas-compliance-xero-figures`  
**Date**: 2026-04-29

## Bug 1 — W1/W2 Field Lock-out

### Finding
Root cause is a single condition in `frontend/src/components/bas/BASTab.tsx` line ~1501:

```tsx
{parseFloat(calculation.w1_total_wages) > 0 ? (
  // read-only "From Xero Payroll" display ← incorrectly shows after manual save
) : (
  <PAYGManualEntry ... />   // editable manual fields
)}
```

The intent was "show the locked display if Xero payroll auto-populated the field." The bug is using `w1 > 0` as the proxy — but a manually saved W1 also makes `w1_total_wages > 0`, switching the tab to the locked display.

### Decision
Replace the condition with `calculation.payg_source_label !== null`. `payg_source_label` is already present on `BASCalculation` (backend sets it to a non-null string like `"From Xero Payroll — Q3 FY26"` when payroll data is auto-populated; null for manual entry). This is a one-line frontend fix.

### No backend changes needed for this bug.

---

## Bug 2 — Unreconciled Warning Not Firing on Recalculate

### Finding
The reconciliation check runs in a `useEffect` keyed on `[selectedSession?.id]` — it fires on session selection, not on Recalculate. The `handleCalculate` function in `BASTab.tsx` (line 465) calls `triggerBASCalculation` directly with no reconciliation pre-check.

Additionally, the reconciliation API (`/clients/{client_id}/reconciliation-status`) currently returns only `unreconciled_count` and `total_transactions` — it does **not** return `balance_discrepancy`. The spec requires showing the discrepancy amount, so the repository query must be extended to SUM the unreconciled transaction amounts.

### Decision
1. **Frontend**: Add reconciliation pre-check inside `handleCalculate`. If `!proceededWithUnreconciled` and status has `unreconciled_count > 0` or `balance_discrepancy > 0`, show the warning modal and abort the calculation. If already proceeded, skip the modal and calculate directly.
2. **Backend**: Extend `BASRepository.get_reconciliation_status` to also `SUM(sub_total)` (or equivalent amount field) for unreconciled rows and return `balance_discrepancy`. Update `BASService.get_reconciliation_status` to pass it through. No schema change needed — this is a query-only addition.
3. **Frontend**: Update `ReconciliationStatus` type to include `balance_discrepancy: number`. Update the `UnreconciledWarning` component to show it, with the "may be rounding" note when < $1.

### Relevant files
- `frontend/src/components/bas/BASTab.tsx` — `handleCalculate` (line 465), reconciliation `useEffect` (line 404)
- `frontend/src/components/bas/UnreconciledWarning.tsx` — add discrepancy display
- `backend/app/modules/bas/repository.py` — `get_reconciliation_status` (line 1454)
- `backend/app/modules/bas/service.py` — `get_reconciliation_status` (line 1665)
- `backend/app/modules/bas/router.py` — reconciliation endpoint (line 2306)

---

## Bug 3 — BAS Figures Don't Match Xero (Cash Basis)

### Finding
The cross-check infrastructure already exists:
- `XeroClient.get_bas_report` in `backend/app/modules/integrations/xero/client.py` line 2053 — calls `GET /Reports/BAS`
- `TaxCodeService.get_xero_bas_crosscheck` in `tax_code_service.py` line 881 — fetches from Xero, compares against Clairo calculation
- Router endpoint `/bas/sessions/{session_id}/xero-crosscheck` — wired up
- `XeroBASCrossCheck.tsx` — frontend panel exists

**Retry logic**: `get_bas_report` makes a raw `httpx` call with no retry. If the call fails (5xx, network timeout), it propagates as an exception and the cross-check returns an error payload to the frontend. The spec requires 2 retries for transient errors.

**Root cause of Heart of Love discrepancy**: The cash basis filter in `GSTCalculator.calculate()` uses `payment_date` filtering for bank transactions. However, invoices (sales) may be filtered by `invoice_date` even when cash basis is selected, depending on whether the `gst_basis` parameter is correctly propagated from the session into the calculator call. This needs investigation during implementation — the fix is to ensure the calculator's date filter switches on `payment_date` (bank txn) / `fully_paid_on_date` (invoice) when `gst_basis = 'cash'`.

### Decision
1. **Backend**: Wrap `get_bas_report` call in `get_xero_bas_crosscheck` with 2 retries for transient failures (non-429, non-401 errors). Existing rate-limiter (429 handling) already applies — do not retry 429s.
2. **Backend**: Investigate and fix cash basis date filtering in `GSTCalculator` — verify `payment_date` is used for invoices and bank transactions when `gst_basis = 'cash'`.
3. **Frontend**: Ensure the error payload from a failed cross-check (`xero_error` field already in response) is surfaced as a visible inline message rather than silent empty state.

### Relevant files
- `backend/app/modules/bas/tax_code_service.py` — `get_xero_bas_crosscheck` (line 881), retry wrapper to add around line 948
- `backend/app/modules/integrations/xero/client.py` — `get_bas_report` (line 2053)
- `backend/app/modules/bas/calculator.py` — cash basis date filtering (needs investigation)
- `frontend/src/components/bas/XeroBASCrossCheck.tsx` — error state display

---

## Bug 4 — BAS Excluded Treated as Uncoded

### Finding
`TaxCodeService.detect_and_generate` (line 77-79) already filters BASEXCLUDED from the excluded items list **before creating suggestions**. So new suggestion generation is correct.

The issue is **pre-existing TaxCodeSuggestion records** created before this filter was in place. Those suggestions exist in `pending` status and are picked up by:
1. The suggestion count shown in the uncoded panel UI
2. `ClassificationService.send_to_client` (line 134) which pulls all `pending` suggestions and passes them to the client

Fix requires:
1. **Backend**: Add a data migration / one-time cleanup to set status = `dismissed` on existing TaxCodeSuggestion records where `tax_type = 'BASEXCLUDED'`.
2. **Backend**: Add a guard in `ClassificationService.send_to_client` to filter out any suggestion where `tax_type = 'BASEXCLUDED'` before building the client request, as a belt-and-suspenders defence.
3. **Backend**: Verify the uncoded count returned by the session summary does not include BASEXCLUDED suggestions — add `AND tax_type != 'BASEXCLUDED'` to any count query that doesn't already have it.

### Relevant files
- `backend/app/modules/bas/classification_service.py` — `send_to_client` (line 134)
- `backend/app/modules/bas/tax_code_service.py` — `detect_and_generate` (already correct, line 77)
- `backend/app/modules/bas/repository.py` — any suggestion count queries
- Alembic migration — one-time cleanup of existing BASEXCLUDED suggestions

---

## Summary of Changes

| Area | Backend | Frontend | DB Migration |
|------|---------|----------|--------------|
| W1/W2 lock-out | None | `BASTab.tsx` — 1-line condition fix | None |
| Unreconciled warning trigger | `repository.py`, `service.py` — add balance_discrepancy | `BASTab.tsx` — pre-check in handleCalculate; `UnreconciledWarning.tsx` | None |
| Cash basis / Xero figures | `tax_code_service.py` — retry wrapper; `calculator.py` — basis fix | `XeroBASCrossCheck.tsx` — error state | None |
| BAS Excluded | `classification_service.py` — guard; `repository.py` — count guard | None | Yes — dismiss stale BASEXCLUDED suggestions |

**No new tables. No new columns. One data cleanup migration.**
