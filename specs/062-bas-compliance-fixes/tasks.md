# Tasks: BAS Compliance Fixes & Data Accuracy

**Input**: Design documents from `/specs/062-bas-compliance-fixes/`
**Branch**: `062-bas-compliance-fixes` (already created)
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/api.md ✅

**Tests**: Not explicitly requested — test tasks omitted. Add unit tests per standard PR policy.

**Organization**: Tasks grouped by user story (11 stories + 1 FR-only feature). Each phase is independently testable.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 0: Git Setup

**Branch already created**: `062-bas-compliance-fixes` — no action needed. Verify you are on the correct branch before starting.

- [X] T000 Verify active branch is `062-bas-compliance-fixes` (`git branch --show-current`)

---

## Phase 1: Setup (Shared Audit Events)

**Purpose**: Register new audit event types used across multiple stories. Blocking for all audit-emitting tasks.

- [X] T001 Add 4 new audit event constants to `backend/app/modules/bas/audit_events.py`: `BAS_GST_BASIS_SET`, `BAS_GST_BASIS_CHANGED`, `BAS_GST_BASIS_CHANGED_POST_LODGEMENT`, `BAS_INSTALMENT_ENTERED`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema migration and two infrastructure risks that block multiple user stories. MUST be complete before any user story work begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Write Alembic migration `backend/alembic/versions/[hash]_bas_gst_basis_and_instalments.py` — add `gst_reporting_basis VARCHAR(10)`, `gst_basis_updated_at TIMESTAMPTZ`, `gst_basis_updated_by UUID FK` to `practice_clients`; `gst_basis_used VARCHAR(10)` to `bas_sessions`; `t1_instalment_income NUMERIC(15,2)`, `t2_instalment_rate NUMERIC(8,5)` to `bas_calculations` (all nullable)

- [X] T003 Run and verify migration: `cd backend && uv run alembic upgrade head` — confirm all 6 columns appear in the database

- [X] T004 Verify `XeroPayment` sync exists in `backend/app/modules/integrations/xero/data_service.py` — if `sync_payments()` is absent or not called from the sync pipeline, add it before proceeding to US1 (cash basis depends on `XeroPayment.payment_date`)

- [X] T005 Verify `XeroBankTransaction` has an `is_reconciled` or equivalent reconciliation status field in `backend/app/modules/integrations/xero/models.py` — document the field name for use in US11; if absent, identify the correct alternative (e.g., bank statement line status)

**Checkpoint**: Migration applied, XeroPayment sync confirmed, reconciliation field identified. User story work can begin.

---

## Phase 3: User Story 1 — Cash vs Accrual Basis Selection (Priority: P1) 🎯 MVP

**Goal**: Before any BAS figures load, the accountant selects (or confirms) the client's GST reporting basis. Figures are then fetched using the correct date filter.

**Independent Test**: Open BAS for a test client with no saved basis — basis prompt appears before any figures load. Select "Cash basis" — only invoices with a payment date in the quarter appear in G1. Reload — saved preference pre-selected, no re-prompt.

### Implementation

- [X] T006 [US1] Update `PracticeClient` model in `backend/app/modules/clients/models.py` — add `gst_reporting_basis: Mapped[str | None]`, `gst_basis_updated_at: Mapped[datetime | None]`, `gst_basis_updated_by: Mapped[uuid.UUID | None]` mapped columns

- [X] T007 [US1] Update `ClientRepository` in `backend/app/modules/clients/repository.py` — add `update_gst_basis(client_id, basis, updated_by)` method using `flush()` not `commit()`

- [X] T008 [US1] Update `ClientService` in `backend/app/modules/clients/service.py` — add `set_gst_basis(client_id, basis, actor_id)` method; emit `BAS_GST_BASIS_SET` or `BAS_GST_BASIS_CHANGED` audit event; check if any lodged `BASSession` exists for this client and emit `BAS_GST_BASIS_CHANGED_POST_LODGEMENT` if so

- [X] T009 [P] [US1] Update `PracticeClientResponse` and `PracticeClientUpdate` schemas in `backend/app/modules/clients/schemas.py` — add `gst_reporting_basis`, `gst_basis_updated_at`, `gst_basis_updated_by` fields

- [X] T010 [US1] Update `PATCH /clients/{client_id}` and `GET /clients/{client_id}` in `backend/app/modules/clients/router.py` — accept and return `gst_reporting_basis` via the updated schemas

- [X] T011 [US1] Update `BASSession` model in `backend/app/modules/bas/models.py` — add `gst_basis_used: Mapped[str | None]` mapped column

- [X] T012 [US1] Refactor `GSTCalculator.calculate()` in `backend/app/modules/bas/calculator.py` — accept `gst_basis: Literal["cash", "accrual"]` parameter; branch `_get_invoices()`: accrual → filter by `XeroInvoice.issue_date`, cash → join `XeroPayment` and filter by `XeroPayment.payment_date`; apply same branching to `_get_credit_notes()`

- [X] T013 [US1] Update `BASService` in `backend/app/modules/bas/service.py` — read `client.gst_reporting_basis` before triggering calculation; pass basis to `GSTCalculator.calculate()`; snapshot basis into `BASSession.gst_basis_used` at calculation time; raise domain exception if basis is `None` (not yet set)

- [X] T014 [P] [US1] Update `BASSession` response schema in `backend/app/modules/bas/schemas.py` — include `gst_basis_used` field

- [ ] T015 [US1] Create `frontend/src/components/bas/GSTBasisModal.tsx` — shadcn `Dialog` component; shown when `client.gst_reporting_basis` is `null`; two options: "Cash basis" / "Accrual basis"; on confirm calls `PATCH /clients/{id}` then re-triggers BAS data fetch; on change for an already-loaded session shows warning: "Changing the basis will reload all figures. Any manual adjustments will be lost."

- [ ] T016 [US1] Update `frontend/src/components/bas/BASTab.tsx` — before fetching BAS calculation, check `client.gst_reporting_basis`; if `null` open `GSTBasisModal`; display active basis label on BAS screen header (e.g., "GST: Cash basis")

- [ ] T017 [US1] Handle post-lodgement basis change in `GSTBasisModal.tsx` — if `BASSession.lodged_at` is set, show elevated secondary warning: "This period has been lodged with the ATO. Changing the basis will require you to lodge an amended BAS." before confirming

**Checkpoint**: Accountant prompted for basis on first open, saved preference used on return. Cash basis shows payment-date-filtered invoices, accrual shows issue-date-filtered invoices.

---

## Phase 4: User Story 2 — PAYGW (Wages) Population (Priority: P2)

**Goal**: W1 and W2 fields auto-populate from Xero payroll data for the quarter. If no payroll data, a clear prompt guides manual entry.

**Independent Test**: Open BAS for a client with Xero payroll and wages paid in the quarter — W1 and W2 are pre-filled with source label "From Xero Payroll — [date range]". Open BAS for a client with no payroll data — W1/W2 blank with hint text.

### Implementation

- [X] T018 [US2] Trace why `PAYGCalculator` results are not populating `BASCalculation.w1_total_wages` / `w2_amount_withheld` in `backend/app/modules/bas/service.py` — confirm whether `PAYGCalculator.calculate()` is being called and its results written; fix the call chain if broken

- [X] T019 [US2] Ensure only **finalised** Xero pay runs populate W1/W2 — in `backend/app/modules/bas/calculator.py` or `PAYGCalculator`, filter `XeroPayRun` records by finalised status; if draft pay runs exist for the period, record their count in the response metadata

- [X] T020 [P] [US2] Update `PAYGBreakdown` schema in `backend/app/modules/bas/schemas.py` — add `source_label: str` (e.g., "From Xero Payroll — 1 Jan 2025 to 31 Mar 2025"), `has_payroll: bool`, `draft_pay_run_count: int`

- [X] T021 [US2] Update the PAYG section in `frontend/src/components/bas/BASTab.tsx` (or the PAYG sub-component) — display `source_label` beneath W1/W2 fields when `has_payroll` is true; show hint "No payroll data found — enter manually if wages were paid" when `has_payroll` is false; show note "N draft pay run(s) not included" when `draft_pay_run_count > 0`

**Checkpoint**: W1/W2 auto-populated from Xero for clients with payroll; manual entry available for all; draft pay run caveat shown when applicable.

---

## Phase 5: User Story 3 — PAYG Instalment Manual Entry (Priority: P3)

**Goal**: A PAYG Instalment section is always visible in the BAS workflow, allowing accountants to manually enter T1 (instalment income) and T2 (instalment rate) for quarterly BAS filers.

**Independent Test**: Navigate to the PAYG tab of any client's BAS preparation. A "PAYG Instalment" section is visible with T1 and T2 fields. Enter values — total amount payable updates. Leave blank — section shows $0.00, not blank.

### Implementation

- [X] T022 [P] [US3] Update `BASCalculation` model in `backend/app/modules/bas/models.py` — add `t1_instalment_income: Mapped[Decimal | None]`, `t2_instalment_rate: Mapped[Decimal | None]` mapped columns (columns added in migration T002)

- [X] T023 [P] [US3] Update `BASCalculation` response schema in `backend/app/modules/bas/schemas.py` — add `t1_instalment_income`, `t2_instalment_rate`, computed `t_instalment_payable` (t1 × t2, or 0 if either is null)

- [X] T024 [US3] Update `BASRepository` in `backend/app/modules/bas/repository.py` — extend the calculation update method to accept and persist T1/T2 values

- [X] T025 [US3] Add `BASService.update_instalment(session_id, t1, t2, actor_id)` in `backend/app/modules/bas/service.py` — saves T1/T2, emits `BAS_INSTALMENT_ENTERED` audit event with old/new values

- [X] T026 [US3] Add `PATCH /bas/calculations/{calculation_id}/instalments` endpoint in `backend/app/modules/bas/router.py` — accepts `{ t1_instalment_income, t2_instalment_rate }`, returns updated calculation including `t_instalment_payable`

- [X] T027 [US3] Create `frontend/src/components/bas/InstalmentSection.tsx` — always-visible section within the PAYG tab; T1 label "Instalment income (T1)", T2 label "Instalment rate (T2)"; computed "Instalment payable" displayed read-only; empty fields display as $0.00 / 0%; calls `PATCH /bas/calculations/{id}/instalments` on blur; uses `formatCurrency` from `@/lib/formatters`

- [X] T028 [US3] Wire `InstalmentSection` into the PAYG tab within `frontend/src/components/bas/BASTab.tsx`

**Checkpoint**: T1/T2 fields visible for all clients; values persist; payable amount computed and displayed.

---

## Phase 6: User Story 4 — Fix "Manual Required" Label (Priority: P4)

**Goal**: All instances of "Manual Required" replaced with "Uncoded" or "Needs tax code". A two-status header shows reconciliation status and coding status as separate indicators.

**Independent Test**: Open a client with pending tax code suggestions. The badge reads "N Uncoded" not "N Manual Required". The BAS header shows two distinct indicators: reconciliation status (e.g., "All reconciled") and coding status (e.g., "57 uncoded").

### Implementation

- [X] T029 [US4] Search the entire frontend codebase for "Manual Required" (`grep -r "Manual Required" frontend/src/`) — list all occurrences and replace each with the contextually appropriate label: "Uncoded" (badge/count context) or "Needs tax code" (action/prompt context)

- [X] T030 [P] [US4] Update `backend/app/modules/bas/router.py` line ~1277 — change API endpoint summary string from "Manual Required" to "Uncoded"

- [X] T031 [US4] Update the BAS screen header in `frontend/src/components/bas/BASTab.tsx` (or the BAS summary header sub-component) — add two visually distinct status indicators: (1) Reconciliation status badge using Xero sync data (e.g., "All reconciled ✓" in green or "N unreconciled" in amber), (2) Coding status badge (e.g., "57 uncoded" in amber or "All coded ✓" in green)

**Checkpoint**: No "Manual Required" text anywhere in the UI. Two-status header visible.

---

## Phase 7: User Story 5 — Uncoded Transactions in Date Order (Priority: P5)

**Goal**: Uncoded transaction list sorted date descending (most recent first) by default. Sortable by other columns.

**Independent Test**: Load a client with uncoded transactions spanning multiple dates. List opens sorted most-recent-first. Clicking the date column header re-sorts ascending (oldest first).

### Implementation

- [X] T032 [US5] Confirm backend returns uncoded transactions `ORDER BY transaction_date DESC` (or `issue_date DESC`) in the relevant query in `backend/app/modules/bas/service.py` or `repository.py` — fix if ordering is non-deterministic

- [X] T033 [US5] Audit `frontend/src/components/bas/TransactionList.tsx` (or equivalent component rendering uncoded transactions) — remove any frontend sort override that contradicts backend ordering; add sortable column headers (date, amount, description) using shadcn `Table` with sort state

**Checkpoint**: Uncoded transactions appear most-recent-first; column sort works.

---

## Phase 8: User Story 6 — Cent-Level Precision in Transaction Amounts (Priority: P6)

**Goal**: All transaction amounts display two decimal places throughout the BAS workflow and transaction list.

**Independent Test**: Load any client with cent-value transactions. Every amount in the transaction list and BAS form fields shows two decimal places (e.g., $1,234.56 not $1,235).

### Implementation

- [X] T034 [US6] Search frontend for currency rounding in BAS components: `grep -r "toFixed(0)\|Math\.round\|parseInt" frontend/src/components/bas/` — list all matches

- [X] T035 [US6] Replace all whole-dollar rounding in BAS components with `formatCurrency` from `@/lib/formatters` — verify `formatCurrency` outputs 2 decimal places; update the formatter if it does not

- [X] T036 [P] [US6] Verify BAS form field displays (G1, 1A, 1B, W1, W2, T1, T2 etc.) in `frontend/src/components/bas/BASTab.tsx` and sub-components all use `formatCurrency` — fix any that use raw number display or `toFixed(0)`

**Checkpoint**: All transaction amounts and BAS form fields display cents.

---

## Phase 9: User Story 7 — Quarter Context Preserved Across Tabs (Priority: P7)

**Goal**: Selected BAS quarter persists across BAS, Insights, and Dashboard tabs. Switching tabs does not lose or reset the quarter.

**Independent Test**: Select March quarter on BAS tab. Switch to Insights tab — shows March data. Switch to Dashboard — shows March data. Return to BAS tab — still shows March quarter selected.

### Implementation

- [X] T037 [US7] Create `frontend/src/stores/clientPeriodStore.ts` — Zustand slice with `{ selectedQuarter: number, selectedFyYear: number, setQuarter: (q: number, fy: number) => void }`; no localStorage persistence (resets on page refresh)

- [X] T038 [US7] Update `frontend/src/app/(protected)/clients/[id]/page.tsx` — replace local `selectedQuarter`/`selectedFyYear` state with `useClientPeriodStore`; remove prop-drilling of quarter to child tabs

- [X] T039 [US7] Update `frontend/src/components/bas/BASTab.tsx` — consume `useClientPeriodStore` instead of receiving quarter as prop; update `setQuarter` in the store when the accountant changes quarter

- [X] T040 [US7] Update the Insights tab component — consume `useClientPeriodStore`; pass `?period=Q{quarter}&fy={fyYear}` to all Insights API calls; display selected quarter label in the Insights tab header

- [X] T041 [P] [US7] Update the Dashboard tab component — consume `useClientPeriodStore`; scope any period-sensitive data to the selected quarter; label any data outside the period clearly

**Checkpoint**: Quarter selection is shared state; all three tabs reflect the same period simultaneously.

---

## Phase 10: User Story 8 — Insights Tab Accuracy & Quality (Priority: P8)

**Goal**: Fix 6 Insights sub-issues: overdue AR figure, GST registration suppression, AI language, confidence routing, deduplication, and calculation breakdown.

**Independent Test**: Open Insights for a GST-registered client with no overdue AR and one invoice 176 days past due. The overdue AR figure shows only the overdue invoice amount. No GST registration insight appears. No insight uses "I notice..." language. No insight below 70% confidence appears in Urgent. No insight appears twice. Each numeric insight has a "How was this calculated?" section.

### Implementation

- [X] T042 [US8] Fix overdue AR query in `backend/app/modules/insights/analyzers/compliance.py` — replace current query with: `XeroInvoice WHERE due_date < today AND status NOT IN ('PAID', 'VOIDED')` — sum `amount_due` on these records; do not divide total outstanding by a ratio

- [X] T043 [US8] Add GST registration suppression in `backend/app/modules/insights/analyzers/compliance.py` — before generating the GST registration insight, check `PracticeClient.gst_reporting_basis IS NOT NULL` (or a GST-registered flag on the client); if already registered, skip the insight entirely

- [X] T044 [US8] Audit `AIAnalyzer` prompt in `backend/app/modules/insights/analyzers/` — ensure the system prompt for insight card generation explicitly requires third-person declarative language (e.g., "Revenue declined 12%") and prohibits first-person chat language; add post-processing: strip any generated insight text beginning with "I " or "It appears"

- [X] T045 [US8] Add confidence threshold routing in `backend/app/modules/insights/generator.py` — after all analyzers run, apply: `if insight.confidence_score < 0.70: insight.priority = InsightPriority.MEDIUM` before persisting; add `URGENT_CONFIDENCE_THRESHOLD = 0.70` constant at module level

- [X] T046 [US8] Add deduplication step in `backend/app/modules/insights/generator.py` — after collecting all insights from all analyzers, group by `(insight_type, period)`; keep the highest-confidence instance per group; discard others

- [X] T047 [US8] Ensure each insight with a numeric figure stores its source data points in its `metadata` JSONB field in `backend/app/modules/insights/models.py` and the relevant analyzers — verify the schema supports a `calculation_breakdown: list[{label, value}]` structure in metadata

- [X] T048 [P] [US8] Add "How was this calculated?" expandable section to the Insights card component in `frontend/src/components/insights/` — render `metadata.calculation_breakdown` as a list of label/value rows inside a shadcn `Collapsible`; show only when `calculation_breakdown` is present and non-empty

**Checkpoint**: Overdue AR figure matches Xero, no irrelevant GST insight, no AI chat language, all Urgent insights ≥70% confidence, no duplicates, breakdown available on numeric insights.

---

## Phase 11: User Story 9 — Request Client Input Label & Ordering Fixes (Priority: P9)

**Goal**: Transactions sent to clients via Request Client Input use plain-language labels ("Needs tax code") and are sorted date descending.

**Independent Test**: Trigger a Request Client Input for a client with uncoded transactions. The email received by the client shows "Needs tax code" (not "Manual Required"), and transactions are listed most-recent-first.

### Implementation

- [X] T049 [US9] Update `classification_service.py` in `backend/app/modules/bas/classification_service.py` — in `create_request()`, sort `unresolved_suggestions` by `transaction_date DESC` before building the email payload

- [X] T050 [US9] Update `transaction_classification_request()` template in `backend/app/modules/portal/notifications/templates.py` — replace "Manual Required" with "Needs tax code" (plain language for non-accountants); verify no other "Manual Required" text in the template

**Checkpoint**: Client email shows correct label and date-ordered transactions.

---

## Phase 12: User Story 10 — Load Error with Working Refresh (Priority: P10)

**Goal**: When BAS data fails to load, the error state is descriptive and the Retry button re-triggers the data fetch.

**Independent Test**: With Xero disconnected, open BAS for any client. An error state appears with a description and Retry button. Click Retry — another fetch attempt is made. If still failing, error message updates.

### Implementation

- [X] T051 [US10] Locate the error state render in `frontend/src/components/bas/BASTab.tsx` — find the Retry/Refresh button and its `onClick` handler; confirm it is wired (not a no-op or missing handler)

- [X] T052 [US10] Wire the Retry button to re-trigger the BAS data fetch — use the React Query `refetch()` function from the BAS session query, or re-call `triggerBASCalculation`; ensure the button shows a loading state during retry

- [X] T053 [P] [US10] Update the error message content in the BAS error state component — replace generic "Something went wrong" with a descriptive message (e.g., "Unable to load BAS data — Xero may be unavailable.") and a suggested next step (e.g., "Check the Xero connection in Settings, then try again.")

**Checkpoint**: Retry button is functional; error message is descriptive; loading state shown during retry.

---

## Phase 13: User Story 11 — Unreconciled Data Warning (Priority: P11)

**Goal**: When Xero data includes unreconciled transactions for the selected period, a blocking warning appears before BAS figures are shown. Accountant must explicitly choose "Proceed anyway" or "Go back".

**Independent Test**: Open BAS for a client with unreconciled Xero transactions. Blocking warning appears before any figures. "Go back" returns to client overview. "Proceed anyway" shows figures with a persistent amber banner. Open BAS for a fully-reconciled client — no warning.

### Implementation

- [X] T054 [US11] Implement `BASRepository.get_reconciliation_status(connection_id, start_date, end_date)` in `backend/app/modules/bas/repository.py` — using the reconciliation field identified in T005, return `{ unreconciled_count: int, total_transactions: int }` for the given period (must include `tenant_id` filter)

- [X] T055 [US11] Add `BASService.get_reconciliation_status(client_id, start_date, end_date)` in `backend/app/modules/bas/service.py` — wraps repository call; returns status plus `as_of: datetime` (current time)

- [X] T056 [US11] Add `GET /bas/clients/{client_id}/reconciliation-status` endpoint in `backend/app/modules/bas/router.py` — query params: `start_date`, `end_date`; response: `{ unreconciled_count, total_transactions, as_of }`

- [X] T057 [US11] Create `frontend/src/components/bas/UnreconciledWarning.tsx` — shadcn `AlertDialog`; shown when `unreconciled_count > 0`; title: "Xero data is not fully reconciled"; description: "Xero transactions for this period are not fully reconciled — BAS figures may be incomplete or inaccurate."; two buttons: "Go back and reconcile first" (navigates to client overview) and "Proceed anyway" (closes dialog, loads figures)

- [X] T058 [US11] Update `frontend/src/components/bas/BASTab.tsx` — before fetching BAS figures, call `GET /bas/clients/{client_id}/reconciliation-status`; if `unreconciled_count > 0`, render `UnreconciledWarning` instead of loading figures; if accountant proceeds, show persistent shadcn `Alert` banner: "Warning: based on unreconciled data as at [date]"

**Checkpoint**: Blocking dialog shown for unreconciled clients; "Go back" and "Proceed" both work; persistent banner shown when proceeding.

---

## Phase 14: FR-021 — Insights in BAS Lodgement Email

**Goal**: Accountant can optionally include an Insights summary in the BAS lodgement confirmation email sent to the client. Accountant chooses whether to include it, per lodgement.

**Independent Test**: In the Lodgement modal, toggle "Include Insights summary". Lodge the BAS. The confirmation email received by the client includes a "This Quarter in Numbers" section listing top insights. Without the toggle, email has no insights section.

### Implementation

- [X] T059 [FR21] Add insights summary generation method to `backend/app/modules/insights/` — a function that fetches top 5 insights for a given period (priority DESC, confidence DESC) and formats them as a plain-text/HTML summary suitable for email inclusion

- [X] T060 [FR21] Update `lodgement_service.py` in `backend/app/modules/bas/lodgement_service.py` — add `include_insights: bool = False` and `insights_format: str = "inline"` parameters to `record_lodgement()`; if `include_insights`, fetch and format the insights summary

- [X] T061 [FR21] Update `lodgement_confirmation()` template in `backend/app/modules/notifications/templates.py` — add optional `insights_section: str | None` parameter; if provided, render a "This Quarter in Numbers" section in the email body before the closing

- [X] T062 [FR21] Update `send_lodgement_confirmation()` in `backend/app/modules/notifications/email_service.py` — accept and pass through `insights_section`

- [X] T063 [FR21] Update the lodge endpoint in `backend/app/modules/bas/router.py` — accept `{ include_insights: bool, insights_format: str }` in the lodge request body; pass to `record_lodgement()`

- [X] T064 [FR21] Update `frontend/src/components/bas/LodgementModal.tsx` — add shadcn `Switch` toggle "Include Insights summary in client email" (default off); if toggled on, show a preview of the top insights for the period (fetched from existing Insights API); pass `include_insights: true` to the lodge API call

**Checkpoint**: Toggle present in lodgement modal; insights section appears in email when toggled on; no insights section when toggled off.

---

## Phase 15: Polish & Cross-Cutting

- [X] T065 [P] Run full backend validation: `cd backend && uv run ruff check . && uv run pytest` — fix any lint errors or broken tests introduced by this feature
- [X] T066 [P] Run full frontend validation: `cd frontend && npm run lint && npx tsc --noEmit` — fix any type errors or lint warnings
- [X] T067 Verify no "Manual Required" text remains anywhere in the codebase: `grep -r "Manual Required" frontend/src/ backend/app/` — zero results expected
- [ ] T068 Verify cent precision: manually spot-check 5 transaction amounts across BAS workflow and transaction list for 2 decimal places
- [ ] T069 Verify quarter context: manual test — BAS tab → Insights tab → Dashboard tab → BAS tab; confirm quarter label consistent across all tabs
- [X] T070 Update `CLAUDE.md` `## Active Technologies` section to add the 062 spec entry

---

## Phase FINAL: PR & Merge

- [ ] T071 Ensure all validation commands pass: `cd backend && uv run ruff check . && uv run pytest && cd ../frontend && npm run lint && npx tsc --noEmit`

- [ ] T072 Push branch and create PR: `git push -u origin 062-bas-compliance-fixes && gh pr create --title "feat(062): BAS compliance fixes — cash/accrual basis, PAYGW, insights quality" --body "Fixes 11 bugs and gaps in BAS preparation workflow. Most critical: adds cash vs accrual GST basis selection to prevent materially incorrect BAS lodgements."`

- [ ] T073 Update `specs/ROADMAP.md` — mark spec 062 as COMPLETE after merge

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 0** (Git): Verify branch — first
- **Phase 1** (Audit events): Can start immediately — no blocking deps
- **Phase 2** (Foundational): BLOCKS all user story phases — complete T002–T005 first
- **Phases 3–14** (User Stories): All depend on Phase 2 completion
- **Phase 15** (Polish): After all desired stories complete
- **Phase FINAL**: After Polish

### User Story Dependencies

All user stories are independent of each other after Phase 2 completes. Suggested parallel groupings:

| Group | Stories | Why Together |
|-------|---------|-------------|
| Group 1 | US1 (T006–T017) | Compliance-critical, highest priority |
| Group 2 | US2 + US3 (T018–T028) | Both PAYG-related, share PAYG tab in frontend |
| Group 3 | US4 + US5 + US6 (T029–T036) | All frontend label/display fixes, same components |
| Group 4 | US7 (T037–T041) | Zustand store creation — do before US8 which also uses quarter context |
| Group 5 | US8 (T042–T048) | Backend Insights fixes — independent |
| Group 6 | US9 + US10 + US11 (T049–T058) | Backend + frontend reliability fixes |
| Group 7 | FR-021 (T059–T064) | Lodgement email feature — independent |

### Within Each User Story

1. Backend model → repository → service → router
2. Frontend store/component creation → wiring into parent

---

## Parallel Opportunities

```bash
# Phase 2 — run in parallel after migration:
T004  Verify XeroPayment sync
T005  Verify is_reconciled field

# US1 — run in parallel:
T009  Update client schemas
T014  Update BAS session schema

# US3 — run in parallel:
T022  Update BASCalculation model
T023  Update BASCalculation schema

# US8 — run in parallel after generator fixes (T045, T046):
T047  Ensure metadata breakdown stored in analyzers
T048  Add frontend "How was this calculated?" section

# Phase 15 — run in parallel:
T065  Backend validation
T066  Frontend validation
```

---

## Implementation Strategy

### MVP (User Story 1 only — P1 compliance fix)

1. Phase 0 → Phase 1 → Phase 2 (migration + risk verification)
2. Phase 3 (US1: Cash vs Accrual) — T006–T017
3. **STOP and VALIDATE**: Basis prompt works, cash/accrual figures are correct
4. Ship as emergency hotfix if needed — this alone prevents materially wrong BAS lodgements

### Full Delivery (All stories)

Complete phases in order of priority (P1 → P11 → FR-021), validating each phase before proceeding. The largest individual phases are US1 (12 tasks) and US8 (7 tasks) — plan accordingly.

### Total Task Count: 74 tasks (T000–T073)

| Phase | Tasks | Stories |
|-------|-------|---------|
| Phase 0–2 | T000–T005 | Setup + Foundation |
| Phase 3 | T006–T017 | US1: Cash/Accrual (12 tasks) |
| Phase 4 | T018–T021 | US2: PAYGW (4 tasks) |
| Phase 5 | T022–T028 | US3: Instalment T1/T2 (7 tasks) |
| Phase 6 | T029–T031 | US4: Label Fix (3 tasks) |
| Phase 7 | T032–T033 | US5: Sort Order (2 tasks) |
| Phase 8 | T034–T036 | US6: Cent Precision (3 tasks) |
| Phase 9 | T037–T041 | US7: Quarter Context (5 tasks) |
| Phase 10 | T042–T048 | US8: Insights Quality (7 tasks) |
| Phase 11 | T049–T050 | US9: Client Input (2 tasks) |
| Phase 12 | T051–T053 | US10: Retry Button (3 tasks) |
| Phase 13 | T054–T058 | US11: Unreconciled Warning (5 tasks) |
| Phase 14 | T059–T064 | FR-021: Insights Email (6 tasks) |
| Phase 15 + FINAL | T065–T073 | Polish + PR (9 tasks) |

---

## Phase 16 — Post-Trial Bug Fixes (2026-04-26)

Trial by Unni Ashok (Ashok Business Consulting Group) found 13 issues. All fixed in the `062-bas-compliance-fixes` branch.

- [X] BF-001 Fix Bug 1: BASEXCLUDED transactions wrongly flagged as uncoded
  - `backend/app/modules/bas/tax_code_service.py`: filter out `tax_type == "BASEXCLUDED"` before generating suggestions
- [X] BF-002 Fix FR-006: W1/W2 manual entry — "enter manually" hint with no input fields
  - `frontend/src/components/bas/BASTab.tsx`: added `PAYGManualEntry` inline component; new `updatePAYGManual` in `frontend/src/lib/bas.ts`; `backend/app/modules/bas/router.py`: added `PATCH /calculations/{id}/payg-manual` endpoint; `backend/app/modules/bas/service.py` + `repository.py`: added `update_payg_manual` method
- [X] BF-003 Fix Bug 3: Quarter defaults to current (Q4) instead of lodgement-relevant (Q3)
  - `backend/app/modules/clients/service.py`: lodgement-window logic — if today is within 28 days of prev-quarter end, default to that quarter
- [X] BF-004 Fix Bug 4: Misleading "Could not fetch BAS data from Xero" error message
  - `frontend/src/components/bas/XeroBASCrossCheck.tsx`: changed error text to "Live Xero cross-check unavailable — BAS figures are from the last Xero sync."
- [X] BF-005 Fix FR-007: T1/T2 instalment values not persisting after blur
  - `backend/app/modules/bas/router.py` line ~1126: `get_calculation_by_id(calculation_id)` missing `tenant_id` argument — fixed to `get_calculation_by_id(calculation_id, user.tenant_id)`
- [X] BF-006 Fix FR-008 / FR-022 / FR-009: Label "pending"/"unresolved" should read "uncoded"
  - `frontend/src/components/bas/TaxCodeBulkActions.tsx`: "pending" → "uncoded"
  - `frontend/src/components/bas/ClassificationRequestButton.tsx`: "unresolved" → "uncoded"
- [X] BF-007 Fix FR-010: Currency amounts rounding to whole dollars
  - `frontend/src/lib/formatters.ts`: `formatCurrency` default `fractionDigits` changed from 0 → 2
- [X] BF-008 Fix FR-013: GST registration insight appearing for already-registered clients
  - `backend/app/modules/insights/analyzers/compliance.py`: added secondary guard checking `PracticeClient.gst_reporting_basis`
- [X] BF-009 Fix FR-015/FR-016: Duplicate and contradictory insights (voided invoices × 5, employee count contradiction)
  - `backend/app/modules/insights/generator.py`: added `_MAX_AI_INSIGHTS = 5` cap; added "void" and "employee" to `_TOPIC_KEYWORDS`; title-based topic filtering for AI insights
- [X] BF-010 Fix FR-017: "How was this calculated?" breakdown not expanding
  - `frontend/src/components/insights/InsightDetailPanel.tsx`: added `useEffect` to reset `showBreakdown` on `insight.id` change; added `scrollIntoView` on expand; changed breakdown container from `bg-muted/50` to `bg-card` for better visibility
- [X] BF-011 Fix FR-020: Reconciliation status 404 — endpoint uses `client_id` but frontend sends connection UUID
  - `backend/app/modules/bas/service.py` `get_reconciliation_status`: added fallback lookup by `PracticeClient.xero_connection_id`
- [X] BF-012 Fix Bug 5: Insights "No financial activity in past 90 days" false positive
  - `backend/app/modules/insights/analyzers/ai_analyzer.py`: added `transactions_90d_note` to context when bank transactions are empty but invoices/trends present; updated system prompt and user prompt to prohibit "no activity" insights when other data sources show revenue
