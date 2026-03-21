# Tasks: Xero Reports API Integration

**Input**: Design documents from `/specs/023-xero-reports-api/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Integration tests only for key user journeys (no TDD requested)

**Organization**: Tasks grouped by user story for independent implementation and testing

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US7)
- All paths are absolute from repository root

---

## User Stories Summary

| Story | Priority | Title | Backend | Frontend |
|-------|----------|-------|---------|----------|
| US1 | P1 | View Profit & Loss Summary | ✓ | ✓ |
| US2 | P1 | View Balance Sheet Snapshot | ✓ | ✓ |
| US3 | P1 | View Aged Receivables Report | ✓ | ✓ |
| US4 | P2 | View Aged Payables Report | ✓ | ✓ |
| US5 | P2 | View Trial Balance | ✓ | ✓ |
| US6 | P2 | AI Enhanced Financial Analysis | ✓ | - |
| US7 | P3 | Bank Summary View | ✓ | ✓ |

---

## Phase 0: Git Setup (REQUIRED)

**Purpose**: Create feature branch before any implementation

- [X] T000 Create feature branch from main
  - Run: `git checkout main && git pull origin main`
  - Run: `git checkout -b feature/023-xero-reports-api`
  - Verify: You are now on the feature branch

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Database schema, enums, base models

- [X] T001 Add XeroReportType enum in backend/app/modules/integrations/xero/models.py
  - Enum values: PROFIT_AND_LOSS, BALANCE_SHEET, AGED_RECEIVABLES, AGED_PAYABLES, TRIAL_BALANCE, BANK_SUMMARY, BUDGET_SUMMARY

- [X] T002 Add XeroReportSyncStatus enum in backend/app/modules/integrations/xero/models.py
  - Enum values: PENDING, IN_PROGRESS, COMPLETED, FAILED, SKIPPED

- [X] T003 Add XeroReport model in backend/app/modules/integrations/xero/models.py
  - Fields: id, tenant_id, connection_id, report_type, period_key, period_start, period_end, as_of_date
  - JSONB fields: rows_data, summary_data, report_titles, parameters
  - Metadata: xero_report_id, report_name, xero_updated_at, fetched_at, cache_expires_at, is_current_period
  - Constraint: unique(connection_id, report_type, period_key)

- [X] T004 Add XeroReportSyncJob model in backend/app/modules/integrations/xero/models.py
  - Fields: id, tenant_id, connection_id, report_type, status
  - Timing: started_at, completed_at, duration_ms
  - Results: rows_fetched, report_id, error_code, error_message, retry_count, next_retry_at
  - Context: triggered_by, user_id

- [X] T005 Create Alembic migration for xero_reports and xero_report_sync_jobs tables
  - Run: `cd backend && uv run alembic revision --autogenerate -m "Add Xero Reports tables"`
  - Apply: `uv run alembic upgrade head`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Repository, base service, schemas - MUST complete before user stories

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Add XeroReportRepository in backend/app/modules/integrations/xero/repository.py
  - Methods: get_by_id, get_cached_report, get_reports_by_connection, upsert_report
  - Include: cache expiry checking, period key validation

- [X] T007 [P] Add report schemas in backend/app/modules/integrations/xero/schemas.py
  - ReportListResponse, ReportSummary, ReportResponse, ReportRow, ReportCell
  - ReportPendingResponse, RefreshReportRequest, SyncJobResponse, RateLimitResponse

- [X] T008 [P] Add report transformer base in backend/app/modules/integrations/xero/transformers.py
  - XeroReportTransformer class with extract_summary() method
  - parse_xero_date() helper for Xero date format

- [X] T009 Add XeroReportService skeleton in backend/app/modules/integrations/xero/service.py
  - Methods: get_report, list_report_statuses, refresh_report, sync_all_reports
  - Dependencies: XeroReportRepository, XeroClient, XeroConnectionService

- [X] T010 Add report list endpoint in backend/app/modules/integrations/xero/router.py
  - GET /connections/{connection_id}/reports - list available reports with sync status

- [X] T011 [P] Create frontend API client in frontend/src/lib/xero-reports.ts
  - Functions: listReports, getReport, refreshReport

- [X] T012 [P] Create ReportSelector component in frontend/src/components/integrations/xero/ReportSelector.tsx
  - Display available report types with sync status
  - Period selector (FY, Quarter, Month, Custom)

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - View Profit & Loss Summary (P1) 🎯 MVP

**Goal**: Fetch and display P&L report from Xero with period selection

**Independent Test**: Navigate to client → Financial Reports → P&L → displays revenue, expenses, net profit

### Implementation for User Story 1

- [X] T013 [US1] Add get_profit_and_loss method in backend/app/modules/integrations/xero/client.py
  - Parameters: access_token, tenant_id, from_date, to_date, periods, timeframe, standard_layout
  - CRITICAL: Include undocumented `date` parameter for per-period amounts
  - Return: tuple[dict, RateLimitState]

- [X] T014 [US1] Add ProfitAndLossSummary schema in backend/app/modules/integrations/xero/schemas.py
  - Fields: revenue, other_income, total_income, cost_of_sales, gross_profit
  - Fields: operating_expenses, total_expenses, operating_profit, net_profit
  - Calculated: gross_margin_pct, net_margin_pct, expense_ratio_pct

- [X] T015 [US1] Add P&L transformer in backend/app/modules/integrations/xero/transformers.py
  - Method: extract_profit_and_loss_summary(rows_data) -> ProfitAndLossSummary
  - Parse row structure: Header, Section (Revenue, Expenses), SummaryRow

- [X] T016 [US1] Implement get_report for P&L in XeroReportService
  - Check cache, fetch from Xero if stale, transform, save
  - Cache TTL: 1 hour for current period, indefinite for historical

- [X] T017 [US1] Add GET /clients/{client_id}/reports/profit-and-loss endpoint in router.py
  - Query params: period (YYYY-FY, YYYY-QN, YYYY-MM), periods, timeframe
  - Return: ReportResponse with summary and rows

- [X] T018 [US1] Add POST /clients/{client_id}/reports/profit-and-loss/refresh endpoint
  - Throttle: max 1 refresh per 5 minutes
  - Return: ReportResponse or RateLimitResponse (429)

- [X] T019 [US1] Create ProfitLossReport component in frontend/src/components/integrations/xero/ProfitLossReport.tsx
  - Display: Revenue section, Expenses section, Net Profit summary
  - Period selector integration
  - Refresh button with loading state
  - Empty state for no data

- [X] T020 [US1] Create reports page in frontend/src/app/(protected)/clients/[id]/reports/page.tsx
  - Tab-based navigation for report types
  - Default to P&L report
  - Report selector sidebar

- [X] T021 [US1] Add audit event logging for P&L
  - Events: report.sync.started, report.sync.completed, report.sync.failed, report.viewed

**Checkpoint**: P&L report fully functional - can view, refresh, see empty states

---

## Phase 4: User Story 2 - View Balance Sheet Snapshot (P1)

**Goal**: Fetch and display Balance Sheet as of a specific date

**Independent Test**: Navigate to client → Financial Reports → Balance Sheet → displays assets, liabilities, equity

### Implementation for User Story 2

- [X] T022 [US2] Add get_balance_sheet method in backend/app/modules/integrations/xero/client.py
  - Parameters: access_token, tenant_id, as_of_date, periods, timeframe
  - Return: tuple[dict, RateLimitState]

- [X] T023 [US2] Add BalanceSheetSummary schema in backend/app/modules/integrations/xero/schemas.py
  - Fields: current_assets, non_current_assets, total_assets
  - Fields: current_liabilities, non_current_liabilities, total_liabilities, total_equity
  - Calculated: current_ratio, quick_ratio, debt_to_equity

- [X] T024 [US2] Add Balance Sheet transformer in backend/app/modules/integrations/xero/transformers.py
  - Method: extract_balance_sheet_summary(rows_data) -> BalanceSheetSummary
  - Parse sections: Assets (Current, Non-Current), Liabilities, Equity

- [X] T025 [US2] Implement get_report for Balance Sheet in XeroReportService
  - Use as_of_date for period_key (YYYY-MM-DD format)

- [X] T026 [US2] Add GET /clients/{client_id}/reports/balance-sheet endpoint
  - Query params: as_of_date (default: today)
  - Return: ReportResponse

- [X] T027 [US2] Add POST /clients/{client_id}/reports/balance-sheet/refresh endpoint

- [X] T028 [US2] Create BalanceSheetReport component in frontend/src/components/reports/BalanceSheetReport.tsx
  - Display: Assets section (current/non-current), Liabilities section, Equity section
  - Date picker for historical snapshots
  - Ratio summary cards (current ratio, debt/equity)

- [X] T029 [US2] Add Balance Sheet tab to reports page

**Checkpoint**: Balance Sheet fully functional alongside P&L

---

## Phase 5: User Story 3 - View Aged Receivables Report (P1)

**Goal**: Show debtors with aging buckets for collection risk visibility

**Independent Test**: View Aged Receivables → see contacts with amounts in aging buckets (Current, 30, 60, 90+ days)

### Implementation for User Story 3

- [X] T030 [US3] Add get_aged_receivables method in backend/app/modules/integrations/xero/client.py
  - Parameters: access_token, tenant_id, as_of_date
  - Return: tuple[dict, RateLimitState]

- [X] T031 [US3] Add AgedReceivablesSummary schema in backend/app/modules/integrations/xero/schemas.py
  - Fields: current, overdue_1_30, overdue_31_60, overdue_61_90, overdue_90_plus, total
  - Calculated: overdue_total, overdue_pct, avg_debtor_days
  - high_risk_contacts: list[dict] (over 90 days with amount > $5,000)

- [X] T032 [US3] Add Aged Receivables transformer in backend/app/modules/integrations/xero/transformers.py
  - Method: extract_aged_receivables_summary(rows_data) -> AgedReceivablesSummary
  - Parse contact rows with aging bucket cells
  - Identify high-risk contacts

- [X] T033 [US3] Implement get_report for Aged Receivables in XeroReportService
  - Cache TTL: 4 hours (point-in-time, changes less frequently)

- [X] T034 [US3] Add GET /clients/{client_id}/reports/aged-receivables endpoint
  - Query params: as_of_date
  - Return: ReportResponse with contact-level detail

- [X] T035 [US3] Add POST /clients/{client_id}/reports/aged-receivables/refresh endpoint

- [X] T036 [US3] Create AgedReceivablesReport component in frontend/src/components/reports/AgedReceivablesReport.tsx
  - Display: Summary totals by aging bucket
  - Table: Contact, Current, 1-30, 31-60, 61-90, 90+, Total
  - Highlight: High-risk debtors (90+ days, > $5,000)
  - Click on debtor → show invoices (if available)

- [X] T037 [US3] Add Aged Receivables tab to reports page

**Checkpoint**: Aged Receivables functional with high-risk debtor highlighting

---

## Phase 6: User Story 4 - View Aged Payables Report (P2)

**Goal**: Show creditors with aging buckets for cash flow planning

**Independent Test**: View Aged Payables → see suppliers with amounts in aging buckets

### Implementation for User Story 4

- [X] T038 [US4] Add get_aged_payables method in backend/app/modules/integrations/xero/client.py
  - Parameters: access_token, tenant_id, as_of_date
  - Return: tuple[dict, RateLimitState]

- [X] T039 [US4] Add AgedPayablesSummary schema in backend/app/modules/integrations/xero/schemas.py
  - Fields: current, overdue_1_30, overdue_31_60, overdue_61_90, overdue_90_plus, total
  - Calculated: overdue_total, overdue_pct, avg_creditor_days

- [X] T040 [US4] Add Aged Payables transformer in backend/app/modules/integrations/xero/transformers.py
  - Method: extract_aged_payables_summary(rows_data) -> AgedPayablesSummary

- [X] T041 [US4] Implement get_report for Aged Payables in XeroReportService

- [X] T042 [US4] Add GET and POST endpoints for aged-payables in router.py

- [X] T043 [US4] Create AgedPayablesReport component in frontend/src/components/reports/AgedPayablesReport.tsx
  - Display: Summary totals by aging bucket
  - Table: Supplier, Current, 1-30, 31-60, 61-90, 90+, Total

- [X] T044 [US4] Add Aged Payables tab to reports page

**Checkpoint**: Aged Payables functional

---

## Phase 7: User Story 5 - View Trial Balance (P2)

**Goal**: Show all accounts with debit/credit balances for reconciliation

**Independent Test**: View Trial Balance → see all accounts with balances that sum to zero

### Implementation for User Story 5

- [X] T045 [US5] Add get_trial_balance method in backend/app/modules/integrations/xero/client.py
  - Parameters: access_token, tenant_id, as_of_date, payments_only
  - Return: tuple[dict, RateLimitState]

- [X] T046 [US5] Add TrialBalanceSummary schema in backend/app/modules/integrations/xero/schemas.py
  - Fields: total_debits, total_credits, is_balanced
  - Account rows: account_code, account_name, debit, credit

- [X] T047 [US5] Add Trial Balance transformer in backend/app/modules/integrations/xero/transformers.py
  - Method: extract_trial_balance_summary(rows_data) -> TrialBalanceSummary

- [X] T048 [US5] Implement get_report for Trial Balance in XeroReportService

- [X] T049 [US5] Add GET and POST endpoints for trial-balance in router.py

- [X] T050 [US5] Create TrialBalanceReport component in frontend/src/components/reports/TrialBalanceReport.tsx
  - Display: Account table with Code, Name, Debit, Credit columns
  - Footer: Total debits, Total credits, Balance check

- [X] T051 [US5] Add Trial Balance tab to reports page

**Checkpoint**: Trial Balance functional

---

## Phase 8: User Story 6 - AI Enhanced Financial Analysis (P2)

**Goal**: Enhance AI agent context with report data for deeper insights

**Independent Test**: AI chat responses include insights referencing P&L trends, liquidity ratios, collection risk

### Implementation for User Story 6

- [X] T052 [US6] Create report context builder in backend/app/modules/knowledge/context_builder.py
  - Method: get_client_report_context(connection_id: UUID) -> dict
  - Include: P&L summary, Balance Sheet ratios, Aged Receivables high-risk

- [X] T053 [US6] Update Financial Health agent prompt in backend/app/modules/agents/prompts.py
  - Updated Strategy perspective description with ratio analysis instructions
  - Added P&L metrics: gross margin, net margin, operating efficiency
  - Added Balance Sheet metrics: current ratio, debt-to-equity, liquidity

- [X] T054 [US6] Update Collection Risk agent prompt in backend/app/modules/agents/prompts.py
  - Updated Insight perspective description with aged receivables analysis
  - Added instructions for identifying high-risk debtors
  - Added cash flow impact and supplier risk analysis

- [X] T055 [US6] Add report summary to client chat context in backend/app/modules/knowledge/context_builder.py
  - Added report context to Strategy and Insight perspectives via _get_perspective_context
  - Updated format_perspective_context_for_prompt to format report data for prompts

- [X] T056 [US6] Add unit tests for AI context enrichment in backend/tests/unit/modules/knowledge/test_context_builder.py
  - Test: get_client_report_context returns correct report data
  - Test: format_perspective_context_for_prompt includes P&L, Balance Sheet, and Aged Receivables

**Checkpoint**: AI agents use report data for insights

---

## Phase 9: User Story 7 - Bank Summary View (P3)

**Goal**: Show cash positions across all bank accounts

**Independent Test**: View Bank Summary → see all bank accounts with opening balance, receipts, payments, closing balance

### Implementation for User Story 7

- [X] T057 [US7] Add get_bank_summary method in backend/app/modules/integrations/xero/client.py
  - Parameters: access_token, tenant_id, from_date, to_date
  - Return: tuple[dict, RateLimitState]

- [X] T058 [US7] Add BankSummarySummary schema in backend/app/modules/integrations/xero/schemas.py
  - Fields per account: account_name, opening_balance, receipts, payments, closing_balance
  - Totals: total_opening, total_receipts, total_payments, total_closing

- [X] T059 [US7] Add Bank Summary transformer in backend/app/modules/integrations/xero/transformers.py

- [X] T060 [US7] Implement get_report for Bank Summary in XeroReportService

- [X] T061 [US7] Add GET and POST endpoints for bank-summary in router.py

- [X] T062 [US7] Create BankSummaryReport component in frontend/src/components/reports/BankSummaryReport.tsx
  - Display: Account table with Opening, Receipts, Payments, Closing columns
  - Footer: Totals row

- [X] T063 [US7] Add Bank Summary tab to reports page

**Checkpoint**: Bank Summary functional

---

## Phase 10: Background Sync & Nightly Jobs

**Purpose**: Celery tasks for automatic report syncing

- [X] T064 Create sync_reports_for_connection Celery task in backend/app/tasks/reports.py
  - Sync all 7 report types for a single connection
  - Handle rate limiting, errors, retries
  - Log sync job status

- [X] T065 Create nightly_report_sync Celery task in backend/app/tasks/reports.py
  - Query all active XeroConnections
  - Queue sync_reports_for_connection for each
  - Stagger to respect rate limits (10 clients/minute)

- [X] T066 Add Celery Beat schedule for nightly sync in backend/app/celery_config.py
  - Schedule: 2:00 AM AEST daily
  - Task: nightly_report_sync

- [X] T067 Add POST /clients/{client_id}/reports/sync endpoint in router.py
  - Trigger full sync for a client
  - Return: SyncJobResponse with job_id

- [X] T068 Add GET /clients/{client_id}/reports/sync/{job_id} endpoint
  - Check sync job status
  - Return: SyncJobResponse

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T069 [P] Add Budget Summary support (optional report)
  - Add get_budget_summary to client.py
  - Add schema and transformer
  - Handle "Budget not configured" gracefully

- [ ] T070 [P] Add multi-currency support
  - Display base currency in report headers
  - Handle currency formatting in frontend

- [ ] T071 Add error handling for Xero connection expiry
  - Detect token expiry during sync
  - Queue reconnection notification
  - Show "Reconnect required" in UI

- [ ] T072 [P] Add report export functionality
  - Endpoint: GET /clients/{id}/reports/{type}/export?format=csv
  - Audit event: report.exported

- [X] T073 Run linting and type checking
  - Run: `cd backend && uv run ruff check .`
  - Run: `cd backend && uv run mypy app/`
  - Run: `cd frontend && npm run lint`

- [ ] T074 Manual testing with Xero demo company
  - Test all 7 report types
  - Verify caching behavior
  - Test refresh throttling

---

## Phase FINAL: PR & Merge (REQUIRED)

**Purpose**: Create pull request and merge to main

- [ ] TFINAL-1 Ensure all tests pass
  - Run: `cd backend && uv run pytest`
  - Run: `cd frontend && npm run build`

- [ ] TFINAL-2 Push feature branch and create PR
  - Run: `git push -u origin feature/023-xero-reports-api`
  - Run: `gh pr create --title "Spec 023: Xero Reports API Integration" --body "..."`

- [ ] TFINAL-3 Address review feedback (if any)

- [ ] TFINAL-4 Merge PR to main
  - Squash merge after approval
  - Delete feature branch after merge

- [ ] TFINAL-5 Update ROADMAP.md
  - Mark Spec 023 as COMPLETE
  - Update current focus to next spec

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 0: Git Setup
    ↓
Phase 1: Setup (enums, models, migration)
    ↓
Phase 2: Foundational (repository, service skeleton, schemas)
    ↓
Phase 3-9: User Stories (can run in parallel after Phase 2)
    ↓
Phase 10: Background Sync
    ↓
Phase 11: Polish
    ↓
Phase FINAL: PR & Merge
```

### User Story Dependencies

| Story | Depends On | Can Parallel With |
|-------|------------|-------------------|
| US1 (P&L) | Phase 2 | US2, US3 |
| US2 (Balance Sheet) | Phase 2 | US1, US3 |
| US3 (Aged Receivables) | Phase 2 | US1, US2 |
| US4 (Aged Payables) | Phase 2 | US5, US7 |
| US5 (Trial Balance) | Phase 2 | US4, US7 |
| US6 (AI Enhancement) | US1, US2, US3 | - |
| US7 (Bank Summary) | Phase 2 | US4, US5 |

### Parallel Opportunities

**Within Phase 2**:
- T007 (schemas) and T008 (transformers) can run in parallel
- T011 (frontend API) and T012 (ReportSelector) can run in parallel

**User Stories**:
- US1, US2, US3 (all P1) can be implemented in parallel
- US4, US5, US7 (P2/P3) can be implemented in parallel
- US6 depends on US1-US3 being complete

---

## Parallel Example: Phase 3-5 (P1 Stories)

```bash
# Launch all P1 client methods together:
Task: "Add get_profit_and_loss method in client.py"
Task: "Add get_balance_sheet method in client.py"
Task: "Add get_aged_receivables method in client.py"

# Launch all P1 schemas together:
Task: "Add ProfitAndLossSummary schema"
Task: "Add BalanceSheetSummary schema"
Task: "Add AgedReceivablesSummary schema"

# Launch all P1 transformers together:
Task: "Add P&L transformer"
Task: "Add Balance Sheet transformer"
Task: "Add Aged Receivables transformer"
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 0: Git Setup
2. Complete Phase 1: Setup (models, migration)
3. Complete Phase 2: Foundational (repository, service, schemas)
4. Complete Phase 3: US1 - P&L
5. **STOP and VALIDATE**: Test P&L independently
6. Deploy/demo if ready

### P1 Completion (US1-US3)

1. After MVP validation, add US2 (Balance Sheet)
2. Add US3 (Aged Receivables)
3. Each story adds value independently
4. All P1 stories = core financial visibility

### Full Feature

1. Add P2 stories (US4, US5, US6)
2. Add P3 story (US7)
3. Add background sync (Phase 10)
4. Polish and ship

---

## Summary

| Metric | Value |
|--------|-------|
| Total Tasks | 79 |
| Phase 1 (Setup) | 5 tasks |
| Phase 2 (Foundational) | 7 tasks |
| US1 (P&L) | 9 tasks |
| US2 (Balance Sheet) | 8 tasks |
| US3 (Aged Receivables) | 8 tasks |
| US4 (Aged Payables) | 7 tasks |
| US5 (Trial Balance) | 7 tasks |
| US6 (AI Enhancement) | 5 tasks |
| US7 (Bank Summary) | 7 tasks |
| Background Sync | 5 tasks |
| Polish | 6 tasks |
| Final | 5 tasks |

**MVP Scope**: Phase 0-3 (T000-T021) = 22 tasks for P&L functionality

**Parallel Opportunities**:
- 12 tasks marked [P] for parallel execution
- US1/US2/US3 can run fully in parallel after Phase 2
- US4/US5/US7 can run fully in parallel

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Each user story independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
