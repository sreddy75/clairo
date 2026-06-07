# Tasks: BAS Compliance Round 2 — Figures Accuracy & Field Usability

**Input**: Design documents from `/specs/063-bas-compliance-xero-figures/`
**Branch**: `063-bas-compliance-xero-figures` (already checked out)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this belongs to (US1–US4)
- Exact file paths included in all descriptions

---

## Phase 1: Foundational (Prerequisite Investigation)

**Purpose**: Confirm the concrete field name and filtering logic needed before writing any fix. These block US1 and US3 implementation but not US2 or US4.

- [X] T001 Confirm the amount field name on `XeroBankTransaction` used to compute balance discrepancy — open `backend/app/modules/integrations/xero/models.py`, find `XeroBankTransaction`, record the correct column name (likely `sub_total` or `amount`) for use in T010
- [X] T002 [P] Audit `backend/app/modules/bas/calculator.py` for cash basis date filtering — identify which date field is used for sales invoices when `gst_basis='cash'` (must be `fully_paid_on_date`, not `invoice_date`); document the finding in a code comment stub at the line(s) that need fixing (actual fix in T019)
- [X] T003 [P] Audit all suggestion-count queries in `backend/app/modules/bas/repository.py` that do NOT already filter `tax_type != 'BASEXCLUDED'` — list the method names; actual fix in T030

---

## Phase 2: US2 — W1/W2 Fields Stay Editable (P2, Frontend only)

**Story goal**: Accountant can enter, save, correct, and re-save W1 and W2 within a single BAS session without a page reload.

**Independent test**: Open BAS PAYG tab for a client with no Xero payroll. Enter W1 value and blur — field stays editable. Enter W2 and blur — field stays editable. Refresh page — both values persist.

- [X] T004 [US2] Fix W1/W2 lock-out condition in `frontend/src/components/bas/BASTab.tsx` (line ~1501): change `parseFloat(calculation.w1_total_wages) > 0` to `calculation.payg_source_label !== null && calculation.payg_source_label !== undefined` so the PAYGManualEntry component is only replaced by the locked display when Xero payroll actually auto-populated the fields; also add a transient "Saved ✓" state to `PAYGManualEntry` — after `onUpdated` resolves successfully, set a `saved` boolean to `true` and render a brief confirmation label, then clear it after 2000ms via `setTimeout` (FR-004)
- [X] T005 [US2] Verify the Xero-payroll locked display still renders correctly for clients that DO have `payg_source_label` set — manually trace the condition change against the existing read-only render path in `frontend/src/components/bas/BASTab.tsx` lines ~1502–1535 and confirm no regression
- [X] T006 [P] [US2] Verify T1/T2 (PAYG Instalment) `InstalmentSection` in `frontend/src/components/bas/BASTab.tsx` is unaffected by the W1/W2 condition change — confirm `InstalmentSection` renders independently of `payg_source_label`

---

## Phase 3: US4 — BAS Excluded Not Flagged as Uncoded (P3)

**Story goal**: Zero BAS Excluded transactions appear in the uncoded count, uncoded panel, or "Request Client Input" queue.

**Independent test**: Open BAS for OreScope — 36 wage transactions (BASEXCLUDED) must not appear in uncoded panel. Trigger "Request Client Input" — those transactions must not appear in the client request.

- [X] T007 [US4] Create Alembic data-cleanup migration `backend/alembic/versions/20260429_063_dismiss_basexcluded_suggestions.py` — UPDATE `tax_code_suggestions` SET `status='dismissed'`, `dismissed_at=NOW()`, `dismissal_reason='bas_excluded_auto_cleanup'` WHERE `tax_type='BASEXCLUDED'` AND `status='pending'`; downgrade is a no-op
- [X] T008 [P] [US4] Add BASEXCLUDED guard in `backend/app/modules/bas/classification_service.py` at line ~134 after `pending = [s for s in suggestions if s.status == "pending"]`: add `pending = [s for s in pending if (s.tax_type or "").upper() != "BASEXCLUDED"]` with a comment explaining why
- [X] T009 [P] [US4] If T003 found any suggestion-count queries in `backend/app/modules/bas/repository.py` missing the BASEXCLUDED exclusion — add `AND upper(tax_type) != 'BASEXCLUDED'` to those queries (skip if T003 found all queries already correct)
- [ ] T010 [US4] Run `cd backend && uv run alembic upgrade head` to apply the T007 migration and confirm it completes without error; verify against a local DB that the affected rows are now `dismissed`

---

## Phase 4: US3 — Unreconciled Warning Fires on Recalculate (P2)

**Story goal**: Warning modal appears on every Recalculate where unreconciled_count > 0 or balance_discrepancy > 0; "Proceed anyway" is sticky for the session.

**Independent test**: Open BAS for Awning Scape (116 unreconciled, $9,100 discrepancy). Click Recalculate — warning modal appears with count and dollar amount before figures load. Click "Proceed anyway" — calculation runs, inline banner visible. Click Recalculate again — modal does NOT reappear; calculation runs directly.

- [X] T011 [US3] Extend `backend/app/modules/bas/repository.py` — `get_reconciliation_status` (line 1454): add `func.sum(XeroBankTransaction.{field_from_T001}).filter(~XeroBankTransaction.is_reconciled).label("balance_discrepancy")` to the existing COUNT query; return `balance_discrepancy` as `Decimal` (absolute value, default 0 if null) in the result dict
- [X] T012 [US3] Update `backend/app/modules/bas/service.py` — `get_reconciliation_status` (line ~1712): ensure the new `balance_discrepancy` key from the repository dict is included in the returned response dict (the existing `{**counts, "as_of": ...}` pattern should pass it through automatically — verify and add explicit fallback `counts.get("balance_discrepancy", Decimal("0"))` if needed)
- [X] T013 [P] [US3] Update `frontend/src/lib/bas.ts` — add `balance_discrepancy: number` to the `ReconciliationStatus` interface so TypeScript is aware of the new field
- [X] T014 [P] [US3] Update `frontend/src/components/bas/UnreconciledWarning.tsx` — add `balanceDiscrepancy: number` prop; display it in the dialog body: if `balanceDiscrepancy >= 1` show "$X,XXX balance discrepancy"; if `0 < balanceDiscrepancy < 1` show the amount plus "This may be a rounding difference"; if `balanceDiscrepancy === 0` show count-only message (existing behaviour); keep existing `AlertDialog` structure
- [X] T015 [US3] Update `frontend/src/components/bas/BASTab.tsx` — modify `handleCalculate` (line 465) to add a reconciliation pre-check:
  - If `reconciliationStatus` is null at Recalculate time, fetch it inline via `getReconciliationStatus(token, connectionId, selectedSession.start_date, selectedSession.end_date)` and store in state before continuing
  - Wrap the inline fetch in a try/catch — if it throws, set a non-blocking inline notice (e.g. a small `<p>` below the Recalculate button: "Reconciliation status unavailable") and proceed to `triggerBASCalculation` anyway (FR-009)
  - If `!proceededWithUnreconciled` AND (`reconciliationStatus.unreconciled_count > 0` OR `reconciliationStatus.balance_discrepancy > 0`): emit audit event `bas.reconciliation.warning_shown` (see T032), call `setShowUnreconciledWarning(true)` and `return` early
  - Otherwise proceed to `triggerBASCalculation` as before
  - In the "Proceed anyway" handler: emit audit event `bas.reconciliation.proceed_anyway` (see T032) before calling `setProceededWithUnreconciled(true)` and `handleCalculate()`
- [X] T016 [P] [US3] Pass `balanceDiscrepancy={reconciliationStatus?.balance_discrepancy ?? 0}` prop into `<UnreconciledWarning>` at the render site in `frontend/src/components/bas/BASTab.tsx` (line ~858)
- [X] T017 [US3] Verify the session-selection `useEffect` (line ~404) is unchanged — reconciliation status is still pre-fetched on session select so it's available immediately when Recalculate is clicked; confirm the inline-fetch in T015 is only a fallback for the race-condition case

---

## Phase 5: US1 — BAS Figures Match Xero Activity Statement (P1)

**Story goal**: Clairo's GST figures match Xero's activity statement within $0.01 for G1, G10, G11, 1A, 1B; cross-check panel shows inline error when Xero is unreachable.

**Independent test**: Run Clairo BAS for Heart of Love Q3 FY26 (cash basis). Compare G1, G10, G11, 1A, 1B against the Xero activity statement PDF line by line — all within $0.01. Simulate Xero offline — cross-check panel shows "Could not connect to Xero" inline message with Refresh button.

- [X] T018 [US1] In `backend/app/modules/bas/calculator.py` — document the investigation finding from T002 with a TODO comment at the affected filtering block (e.g., `# BUG 063: invoices were filtered by invoice_date on cash basis — must use fully_paid_on_date`)
- [X] T019 [US1] Fix cash basis date filtering in `backend/app/modules/bas/calculator.py` — change the invoice/bill date filter from `invoice_date` to `fully_paid_on_date` (for invoices) and `payment_date` (for bills) when `gst_basis='cash'`; bank transactions are already filtered by `transaction_date` which represents the payment date; add an inline comment explaining the ATO cash basis rule
- [X] T020 [US1] Add retry wrapper in `backend/app/modules/bas/tax_code_service.py` — `get_xero_bas_crosscheck` (line ~948): wrap the `client.get_bas_report(...)` call in a `for attempt in range(3)` loop; on `XeroRateLimitError` re-raise immediately (never retry); on any other exception sleep `1.5 ** attempt` seconds and retry; after all 3 attempts fail, return the existing error-payload dict with `xero_error` set to a descriptive message
- [X] T021 [P] [US1] Import `asyncio` at the top of `backend/app/modules/bas/tax_code_service.py` if not already present (needed for `asyncio.sleep` in retry loop); also import `XeroRateLimitError` from `backend/app/modules/integrations/xero/client.py` if not already imported
- [X] T022 [P] [US1] Update `frontend/src/components/bas/XeroBASCrossCheck.tsx` — if the response has `xero_error` set (non-null/non-empty string), display a shadcn `Alert` (variant `destructive` or amber warning) with text "Could not connect to Xero — cross-check unavailable. Try refreshing or check the Xero connection." Do not render empty/zero figure rows when in error state; keep the existing Refresh button visible
- [ ] T023 [US1] Run the BAS cross-check for Heart of Love Q3 FY26 locally (or against staging) after T019 — compare Clairo figures against the Xero activity statement and confirm all fields match within $0.01; document the comparison result in a comment in `backend/app/modules/bas/calculator.py` near the fixed line
- [X] T024 [US1] Extend `get_xero_bas_crosscheck` in `backend/app/modules/bas/tax_code_service.py` to parse G1 (Total Sales/GST-free), G10 (Capital Purchases), and G11 (Non-capital Purchases) from the Xero BAS report rows — add them to both `clairo_figures` (pulled from `BASCalculation`) and the Xero figures dict; update `XeroBASCrossCheckDifference` schema in `backend/app/modules/bas/schemas.py` if needed
- [X] T025 [P] [US1] Update `frontend/src/components/bas/XeroBASCrossCheck.tsx` — render G1, G10, G11 rows in the side-by-side comparison table alongside the existing 1A/1B rows; highlight discrepant fields with the same visual treatment currently used for 1A/1B

---

## Phase 6: Audit Events (Cross-Cutting)

**Purpose**: Emit the 3 new audit events defined in the spec. These touch backend service and frontend handler code — implement after the story tasks they instrument are complete.

- [X] T032 [US3] In `backend/app/modules/bas/audit_events.py` — add event constants `BAS_RECONCILIATION_WARNING_SHOWN`, `BAS_RECONCILIATION_PROCEED_ANYWAY`; in `backend/app/modules/bas/service.py` or via the frontend's API call, ensure `bas.reconciliation.warning_shown` is emitted (actor, session_id, unreconciled_count, balance_discrepancy, period dates) and `bas.reconciliation.proceed_anyway` is emitted (actor, session_id, unreconciled_count, balance_discrepancy) — follow the existing `audit_event()` pattern from `app.core.audit`
- [X] T033 [P] [US1] In `backend/app/modules/bas/tax_code_service.py` — `get_xero_bas_crosscheck`: after computing `differences`, if any fields differ emit `bas.figures.cross_check_discrepancy` (session_id, discrepant field names, Clairo values, Xero values, basis_used) using the existing audit event pattern; add the event constant to `backend/app/modules/bas/audit_events.py`

---

## Phase 7: Tests (Constitution Compliance)

**Purpose**: Add integration and unit tests required by the project constitution (80% service coverage, 100% endpoint coverage).

- [X] T034 [US3] Add integration test in `backend/tests/integration/api/test_bas_worksheet.py` — assert that `GET /api/v1/clients/{client_id}/reconciliation-status` response includes `balance_discrepancy` as a numeric field; test with a fixture that has known unreconciled transactions with non-zero amounts; test that `balance_discrepancy = 0` when all transactions are reconciled
- [X] T035 [P] [US1] Add unit tests in `backend/tests/unit/modules/bas/test_tax_code_service.py` for the retry wrapper in `get_xero_bas_crosscheck`:
  - Test that a transient error (5xx) on first attempt triggers a retry and succeeds on second attempt
  - Test that after 3 consecutive failures the method returns a dict with `xero_error` set (not raises)
  - Test that a `XeroRateLimitError` is re-raised immediately without retry

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Regression verification, lint/typecheck, and final validation across all fixes.

- [X] T036 Run `cd backend && uv run ruff check . && uv run ruff format .` — fix any lint or formatting issues introduced by T007–T035
- [X] T037 Run `cd frontend && npx tsc --noEmit` — fix any TypeScript errors (especially `balance_discrepancy` on `ReconciliationStatus` and new G1/G10/G11 fields on cross-check types)
- [X] T038 Run `cd frontend && npm run lint` — fix any ESLint errors
- [X] T039 Run `cd backend && uv run pytest -k "bas"` — confirm no regressions in the BAS test suite after calculator, repository, and service changes
- [X] T040 [P] Run `cd backend && uv run pytest -k "reconcil or crosscheck or tax_code_service"` — confirm new tests from T034/T035 pass alongside existing tests
- [ ] T041 [P] Manual regression: open BAS for a client with Xero payroll data — confirm W1/W2 locked "From Xero Payroll" display still shows correctly and Saved ✓ indicator works for manual entry (regression from T004)
- [ ] T042 [P] Manual regression: open BAS for a client with T1/T2 PAYG instalment data — confirm `InstalmentSection` still renders and saves correctly (regression from T004)
- [ ] T043 Manual regression: trigger the Xero cross-check for any healthy client — confirm G1/G10/G11/1A/1B all display correctly and the comparison panel loads (regression from T020, T024, T025)

---

## Dependency Graph

```
T001 ──────────────────────────────────────────► T011 ► T012 ► T015 ► T016
T002 ──────────────────────────────────────────► T018 ► T019 ► T023
T003 ──────────────────────────────────────────► T009

T004 ► T005
T004 ► T006 (independent verify)

T007 ► T010
T008 (parallel with T007)
T009 (parallel with T007/T008, depends on T003)

T011 ► T012 ► T013 (parallel)
                ► T014 (parallel)
                ► T015 ► T016
                ► T017 (verify)
T015 ► T032 (audit event emission wired into handleCalculate)

T018 ► T019 ► T023 ► T024 ► T025
T021 → T020 (parallel with T019)
T022 (parallel with T020)
T024 ► T033 (cross-check discrepancy audit event)

T032 + T033 (parallel, different event types)
T034 + T035 (parallel, different test files)

T036–T043: all run after all story, audit, and test tasks complete
```

## Parallel Execution Opportunities

**Within US2 (safe to run in parallel after T004)**:
- T005 and T006 can run simultaneously

**Within US4 (safe to run in parallel)**:
- T007 and T008 and T009 can all run simultaneously (different files)

**Within US3 (after T011/T012 backend work)**:
- T013, T014, T016, T017 can all run in parallel (different files)

**Within US1 (after T019)**:
- T020/T021/T022 can run in parallel
- T023 requires T019 and T020 complete (tests the whole thing)
- T024 (G1/G10/G11 backend) and T025 (frontend display) are sequential; T025 can start once T024 schema is defined

**Phases 6–7 (audit events + tests)**:
- T032 and T033 can run in parallel (different audit events, different files)
- T034 and T035 can run in parallel (different test files)

**Cross-story parallelism**:
- US2 (T004–T006) can run entirely in parallel with US4 (T007–T010) — completely different files
- US4 can run in parallel with the foundational investigation tasks (T001–T003)

## Implementation Strategy

**Suggested order for lowest-risk delivery**:

1. **Start**: T001 + T002 + T003 in parallel (investigation, no code changes)
2. **Quick win**: T004 → T005 → T006 (W1/W2 fix, 15 minutes, zero backend risk)
3. **Data fix**: T007 + T008 + T009 in parallel → T010 (BAS Excluded, migration)
4. **Backend first**: T011 → T012 (add balance_discrepancy to API)
5. **Frontend wiring**: T013 + T014 + T016 + T017 in parallel → T015 (unreconciled warning)
6. **Riskiest last**: T018 → T019 → T023 → T024 → T025 (cash basis fix + G1/G10/G11 cross-check)
   With T021 → T020 + T022 in parallel (cross-check retry + error UI)
7. **Audit + tests**: T032 + T033 in parallel → T034 + T035 in parallel
8. **Polish**: T036 → T037 + T038 + T039 in parallel → T040 + T041 + T042 in parallel → T043

**MVP scope** (unblock the accountant soonest): T004 alone (W1/W2 fix) is shippable independently — it fixes the most disruptive daily workflow blocker with zero backend risk.
