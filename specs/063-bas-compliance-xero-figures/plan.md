# Implementation Plan: BAS Compliance Round 2 — Figures Accuracy & Field Usability

**Branch**: `063-bas-compliance-xero-figures` | **Date**: 2026-04-29 | **Spec**: [spec.md](./spec.md)

## Summary

Four confirmed BAS workflow bugs are fixed in priority order: (1) Xero cash-basis figures mismatch root-caused and fixed in the GST calculator, cross-check retry hardened; (2) W1/W2 fields unlocked via a one-line frontend condition fix; (3) unreconciled warning wired into `handleCalculate` with balance-discrepancy added to the API response; (4) stale BASEXCLUDED TaxCodeSuggestion records cleaned up and classification guards added. No new tables or columns. One data cleanup migration.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend)  
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 async, Pydantic v2, React 18, TanStack Query, httpx (Xero HTTP calls)  
**Storage**: PostgreSQL 16 — no schema changes; one data migration (UPDATE only)  
**Testing**: pytest + pytest-asyncio (backend), existing integration test suite  
**Target Platform**: Web application — backend FastAPI, frontend Next.js App Router  
**Performance Goals**: Reconciliation pre-check must add < 300ms to the Recalculate flow  
**Constraints**: Must not regress T1/T2 instalment field behaviour; must not regress existing cross-check panel when Xero is reachable  
**Scale/Scope**: All tenants with BAS clients — particularly affects any practice with payroll clients (OreScope-type) or cash-basis GST clients (Heart of Love)

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Repository pattern for all DB access | PASS | All query changes are in `BASRepository` |
| No cross-module DB queries | PASS | No new cross-module access |
| `tenant_id` on all repository queries | PASS | All existing queries already include it; no new queries introduced |
| Domain exceptions in service layer, HTTPException only in router | PASS | No new exception paths change this |
| `flush()` not `commit()` in repositories | PASS | Data migration uses raw SQL via Alembic, not ORM |
| Audit logging for data modification | PASS | W1/W2 saves already emit `bas.payg.manual_updated`; reconciliation warning emits `bas.reconciliation.proceed_anyway` |
| Multi-tenancy isolation | PASS | Reconciliation query already includes `tenant_id`; cleanup migration is tenant-scoped |
| No `HTTPException` in service layer | PASS | |
| shadcn/ui components only (frontend) | PASS | No new components; `UnreconciledWarning` uses `AlertDialog` already |
| CSS variable tokens only | PASS | |

## Project Structure

### Documentation (this feature)

```text
specs/063-bas-compliance-xero-figures/
├── plan.md              ← this file
├── research.md          ← Phase 0 (complete)
├── data-model.md        ← Phase 1 (complete)
├── contracts/
│   └── reconciliation-status.md   ← updated response shape
└── tasks.md             ← Phase 2 output (/speckit.tasks)
```

### Source Code (affected files only)

```text
backend/app/modules/bas/
├── repository.py          # get_reconciliation_status — add balance_discrepancy SUM
├── service.py             # get_reconciliation_status — pass through balance_discrepancy
├── tax_code_service.py    # get_xero_bas_crosscheck — add retry wrapper around get_bas_report
├── calculator.py          # cash basis date filtering — investigate & fix
├── classification_service.py  # send_to_client — add BASEXCLUDED guard on pending list

backend/alembic/versions/
└── 20260429_063_dismiss_basexcluded_suggestions.py  # data cleanup migration

frontend/src/
├── components/bas/
│   ├── BASTab.tsx              # handleCalculate pre-check; W1/W2 condition fix
│   └── UnreconciledWarning.tsx # add balance_discrepancy display + rounding note
│   └── XeroBASCrossCheck.tsx   # surface xero_error inline instead of silent empty
└── lib/bas.ts                  # ReconciliationStatus type — add balance_discrepancy field
```

---

## Implementation Phases

### Fix 1 — W1/W2 Field Lock-out (Frontend only, lowest risk)

**File**: `frontend/src/components/bas/BASTab.tsx`

**Change**: One condition in the PAYG tab render (around line 1501):

```tsx
// BEFORE (buggy): treats any non-zero W1 as "Xero payroll data present"
{parseFloat(calculation.w1_total_wages) > 0 ? (
  // locked read-only display
) : (
  <PAYGManualEntry ... />
)}

// AFTER: uses the correct discriminator field
{calculation.payg_source_label !== null && calculation.payg_source_label !== undefined ? (
  // locked read-only display — only shown when Xero payroll actually populated it
) : (
  <PAYGManualEntry ... />
)}
```

**Acceptance**: Enter W1, blur — tab remains in manual-entry mode. Enter W2, blur — both values persist. Xero payroll clients still show the locked "From Xero Payroll" display correctly.

**Regression risk**: Low. Only affects clients without Xero payroll (`payg_source_label === null`).

---

### Fix 2 — Unreconciled Warning on Recalculate

#### 2a — Backend: Add balance_discrepancy to reconciliation response

**File**: `backend/app/modules/bas/repository.py` — `get_reconciliation_status` (line 1454)

Add `SUM(sub_total) FILTER (WHERE NOT is_reconciled)` to the existing COUNT query. Return as `"balance_discrepancy"` (Decimal, absolute value).

Verify the column name on `XeroBankTransaction` — likely `sub_total` or `amount`. Confirm during implementation.

**File**: `backend/app/modules/bas/service.py` — `get_reconciliation_status` (line 1712)

Add `balance_discrepancy` to the returned dict (already passes `**counts` — just ensure the new field is included).

#### 2b — Frontend: Wire reconciliation pre-check into handleCalculate

**File**: `frontend/src/components/bas/BASTab.tsx`

Modify `handleCalculate` to:
1. Check if reconciliation status is already fetched (it is, from session-selection `useEffect`).
2. If `!proceededWithUnreconciled` AND (`reconciliationStatus.unreconciled_count > 0` OR `reconciliationStatus.balance_discrepancy > 0`):
   - Set `showUnreconciledWarning = true`
   - Return early (do not call `triggerBASCalculation`)
3. If already `proceededWithUnreconciled`: proceed directly.

The "Proceed anyway" handler already sets `proceededWithUnreconciled = true` and calls `handleCalculate()` — this re-entry will now pass the pre-check and calculate.

**Important**: If `reconciliationStatus` is null at the time of Recalculate (e.g., the session-selection fetch hasn't completed), fetch it inline before the pre-check. This prevents a race condition where the user clicks Recalculate faster than the initial status fetch.

#### 2c — Frontend: Update UnreconciledWarning to show balance_discrepancy

**File**: `frontend/src/components/bas/UnreconciledWarning.tsx`

Add `balanceDiscrepancy: number` prop. Display alongside unreconciled count:

- If `balanceDiscrepancy > 0 && balanceDiscrepancy < 1`: show discrepancy + "This may be a rounding difference"  
- If `balanceDiscrepancy >= 1`: show discrepancy with standard warning message
- If `balanceDiscrepancy === 0` and `unreconciledCount > 0`: show count-only message (current behaviour)

**File**: `frontend/src/lib/bas.ts` — update `ReconciliationStatus` interface to add `balance_discrepancy: number`.

---

### Fix 3 — Xero Cross-check Retry & Cash Basis Root Cause

#### 3a — Backend: Add retry wrapper to get_xero_bas_crosscheck

**File**: `backend/app/modules/bas/tax_code_service.py` — `get_xero_bas_crosscheck` (line 948)

Wrap the `client.get_bas_report(...)` call with a retry loop:

```python
max_attempts = 3
last_exc = None
for attempt in range(max_attempts):
    try:
        data, _rate_limit = await client.get_bas_report(
            access_token=access_token,
            tenant_id=connection.xero_tenant_id,
        )
        break
    except XeroRateLimitError:
        raise  # never retry rate limits
    except Exception as exc:
        last_exc = exc
        if attempt < max_attempts - 1:
            await asyncio.sleep(1.5 ** attempt)  # 0s, 1.5s backoff
else:
    # All attempts failed — return error payload
    return {
        "xero_report_found": None,
        "xero_figures": None,
        "clairo_figures": clairo_figures,
        "differences": None,
        "period_label": period_label,
        "fetched_at": now,
        "xero_error": f"Could not connect to Xero after {max_attempts} attempts: {last_exc}",
    }
```

#### 3b — Frontend: Surface xero_error in XeroBASCrossCheck panel

**File**: `frontend/src/components/bas/XeroBASCrossCheck.tsx`

If response has `xero_error` set (non-null), display an inline alert:
> "Could not connect to Xero — cross-check unavailable. Try refreshing or check the Xero connection."

Do not show empty/zero figures when the error is present. The "Refresh" button should still be available to retry.

#### 3c — Backend: Investigate and fix cash basis date filtering in GSTCalculator

**File**: `backend/app/modules/bas/calculator.py`

Investigation target: when `gst_basis = 'cash'`, the calculator must filter:
- **Bank transactions**: by `payment_date` (already likely correct — these are cash by nature)
- **Sales invoices**: by `fully_paid_on_date` (not `invoice_date`) — this is the most likely source of the discrepancy
- **Purchase bills**: by `payment_date` on the bill (not `bill_date`)

The fix must be verified by running Clairo's calculation for Heart of Love Q3 FY26 against the Xero-downloaded activity statement. Document the root cause and the field change made in a code comment.

---

### Fix 4 — BAS Excluded Filtering

#### 4a — Data migration: dismiss stale BASEXCLUDED suggestions

**File**: `backend/alembic/versions/20260429_063_dismiss_basexcluded_suggestions.py`

```python
def upgrade():
    op.execute("""
        UPDATE tax_code_suggestions
        SET
            status = 'dismissed',
            dismissed_at = NOW(),
            dismissal_reason = 'bas_excluded_auto_cleanup'
        WHERE
            tax_type = 'BASEXCLUDED'
            AND status = 'pending'
    """)

def downgrade():
    pass  # irreversible — do not restore dismissed suggestions
```

#### 4b — Backend: Guard in classification_service.send_to_client

**File**: `backend/app/modules/bas/classification_service.py` — line ~134

After `pending = [s for s in suggestions if s.status == "pending"]`, add:

```python
# Belt-and-suspenders: BASEXCLUDED is intentionally coded — never send to client
pending = [s for s in pending if (s.tax_type or "").upper() != "BASEXCLUDED"]
```

#### 4c — Backend: Verify uncoded count does not include BASEXCLUDED

Audit all places in `BASRepository` that count pending suggestions and confirm `tax_type != 'BASEXCLUDED'` is in the filter. If any count query is missing it, add the filter.

---

## Test Plan

### Unit Tests (backend)

| Test | File | What to verify |
|------|------|---------------|
| `test_reconciliation_balance_discrepancy` | `tests/unit/modules/bas/test_reconciliation.py` | Repository returns correct `balance_discrepancy` for period with unreconciled txns |
| `test_reconciliation_zero_discrepancy` | same | Returns `balance_discrepancy = 0` when all reconciled |
| `test_send_to_client_excludes_basexcluded` | `tests/unit/modules/bas/test_classification_service.py` | Pending suggestions with `tax_type = BASEXCLUDED` are not included in request |
| `test_crosscheck_retry_on_transient_error` | `tests/unit/modules/bas/test_tax_code_service.py` | `get_xero_bas_crosscheck` retries twice then returns `xero_error` payload |
| `test_crosscheck_no_retry_on_rate_limit` | same | 429 errors are not retried |

### Integration Tests (backend)

| Test | File | What to verify |
|------|------|---------------|
| `test_reconciliation_status_includes_discrepancy` | `tests/integration/api/test_bas_worksheet.py` | GET reconciliation-status response includes `balance_discrepancy` field |
| `test_cash_basis_filters_by_payment_date` | `tests/integration/api/test_bas_worksheet.py` | Calculator includes only payment-date-filtered invoices for cash basis |

### Manual Acceptance Tests

| Test | Steps | Expected |
|------|-------|----------|
| W1/W2 stay editable | Open PAYG tab (no Xero payroll), enter W1, blur, enter W2, blur | Both fields remain editable; values persist on refresh |
| W1/W2 Xero payroll correct | Client with Xero payroll data | "From Xero Payroll" locked display still appears |
| Unreconciled warning on Recalculate | Client with unreconciled txns; click Recalculate | Warning modal appears before figures are shown |
| Proceed-sticky behaviour | Click "Proceed anyway", then Recalculate again | Modal does NOT reappear; inline banner remains |
| Balance discrepancy < $1 rounding note | Client with $0.05 discrepancy | Warning shows amount + "may be a rounding difference" |
| Heart of Love figures match Xero | Q3 FY26, cash basis | G1, G10, G11, 1A, 1B match Xero activity statement ≤ $0.01 |
| Cross-check error state | Simulate Xero offline | Inline "Could not connect to Xero" message, Refresh button visible |
| OreScope uncoded count | Open uncoded panel | 36 wage transactions absent; count shows 0 for those |
| OreScope Request Client Input | Trigger send to client | BAS Excluded wage transactions not in client request |

---

## Risk Register

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Cash basis fix changes figures for other clients | Medium | Run cross-check for multiple clients before merge; compare before/after |
| Reconciliation pre-check in handleCalculate creates a race condition (status not yet fetched) | Low | Fetch inline if `reconciliationStatus` is null at Recalculate time |
| Data migration dismisses valid pending suggestions | Low | Migration scoped to `tax_type = 'BASEXCLUDED'` only — not all pending |
| `sub_total` column name wrong on XeroBankTransaction | Low | Verify column name in models.py before writing query |
| Retry adds latency to cross-check panel | Low | Transient failures are rare; 1.5s backoff only on failure path |

---

## Artefacts Produced

| Artefact | Path |
|---------|------|
| Research | `specs/063-bas-compliance-xero-figures/research.md` |
| Data model | `specs/063-bas-compliance-xero-figures/data-model.md` |
| API contract update | `specs/063-bas-compliance-xero-figures/contracts/reconciliation-status.md` |
| This plan | `specs/063-bas-compliance-xero-figures/plan.md` |
