# Tasks: Tax Planning Intelligence Improvements

**Input**: Design documents from `/specs/046-tax-planning-intelligence/`

**Organization**: Tasks grouped by user story. All backend changes in 2 main files, frontend in 2 files.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 0: Git Setup

- [ ] T000 Verify on feature branch `046-tax-planning-intelligence`

---

## Phase 1: Setup

- [ ] T001 Extend TypeScript types at `frontend/src/types/tax-planning.ts` — add optional fields: `projection`, `prior_year_ytd`, `prior_years`, `strategy_context`, `payroll_summary` matching data-model.md

---

## Phase 2: User Story 1 — Bank Balance Fix (Priority: P1)

**Goal**: Show actual bank balance or "not available" — never misleading $0

- [ ] T002 [US1] Fix bank balance null handling in `backend/app/modules/tax_planning/service.py` line 223 — change `total_bank_balance = sum(...)` to return `None` when `bank_balances` is empty
- [ ] T003 [US1] Update `frontend/src/components/tax-planning/FinancialsPanel.tsx` — when `total_bank_balance` is null, show "Bank data not available" message instead of hiding the section entirely

**Checkpoint**: Bank balance shows correctly or shows "not available"

---

## Phase 3: User Story 2 — Revenue Forecasting (Priority: P1)

**Goal**: Project full-year figures from YTD data

- [ ] T004 [US2] Add forecasting logic in `backend/app/modules/tax_planning/service.py` — after `_transform_xero_to_financials()`, calculate months_elapsed from FY start to recon date. If ≥3 months, compute monthly averages and project to 12 months. Store as `financials_data["projection"]`. Update `months_data_available` and `is_annualised`
- [ ] T005 [US2] Add projection context to AI prompt in `backend/app/modules/tax_planning/prompts.py` — in `format_financial_context()`, add "--- Full Year Projection ---" section showing projected revenue, expenses, net profit when projection data exists
- [ ] T006 [US2] Add projection display in `frontend/src/components/tax-planning/FinancialsPanel.tsx` — show "Projected Full Year" card with projected figures and "Projected" badge when projection data exists

**Checkpoint**: Mid-year plans show YTD actuals + projected full year

---

## Phase 4: User Story 3 — Prior Year Comparison (Priority: P2)

**Goal**: Same-period-last-year side-by-side with growth rates

- [ ] T007 [US3] Pull prior year YTD P&L in `backend/app/modules/tax_planning/service.py` — after current P&L pull, call `get_report()` with prior FY period key and same to_date shifted back 1 year. Transform and store as `financials_data["prior_year_ytd"]` with change percentages
- [ ] T008 [US3] Add prior year context to AI prompt in `backend/app/modules/tax_planning/prompts.py` — add "--- Same Period Last Year ---" section with revenue/expense/profit comparisons and % changes
- [ ] T009 [US3] Add comparison display in `frontend/src/components/tax-planning/FinancialsPanel.tsx` — show current vs prior year table with change arrows and percentages

**Checkpoint**: Prior year comparison visible with growth/decline indicators

---

## Phase 5: User Story 4 — Multi-Year Trends (Priority: P2)

**Goal**: FY-1 and FY-2 full-year summaries for trend analysis

- [ ] T010 [US4] Pull full-year P&L for FY-1 and FY-2 in `backend/app/modules/tax_planning/service.py` — two additional `get_report()` calls with full FY period keys (no to_date_override). Store summaries as `financials_data["prior_years"]`
- [ ] T011 [US4] Add multi-year context to AI prompt in `backend/app/modules/tax_planning/prompts.py` — add "--- Multi-Year Trends ---" section showing 3-year revenue/expense/profit trend
- [ ] T012 [US4] Add trend display in `frontend/src/components/tax-planning/FinancialsPanel.tsx` — show mini trend table: FY-2 → FY-1 → Current

**Checkpoint**: Multi-year trends visible in financials panel and AI context

---

## Phase 6: User Story 5 — Strategy Sizing (Priority: P2)

**Goal**: AI strategies grounded in actual financial position

- [ ] T013 [US5] Build strategy context in `backend/app/modules/tax_planning/service.py` — after bank and P&L data, compute: available_cash, monthly_operating_expenses, cash_buffer_3mo, max_strategy_budget, existing_asset_spend (from P&L expense breakdown). Store as `financials_data["strategy_context"]`
- [ ] T014 [US5] Update scanner agent prompt in `backend/app/modules/tax_planning/agents/prompts.py` — add "Strategy Constraints" section with available cash, monthly burn, max budget. Instruct AI to not exceed available cash without justification
- [ ] T015 [US5] Pass strategy context to scanner agent in `backend/app/modules/tax_planning/agents/scanner.py` — include `strategy_context` in the user prompt alongside existing financial data

**Checkpoint**: AI strategies reference actual cash and spending patterns

---

## Phase 7: User Story 6 — Payroll Intelligence (Priority: P3)

**Goal**: Employee wages and super factored into tax planning

- [ ] T016 [US6] Query payroll data in `backend/app/modules/tax_planning/service.py` — if `connection.has_payroll_access`, query XeroPayRun (aggregate wages, super, tax withheld for current FY) and XeroEmployee (active count, names, titles). Store as `financials_data["payroll_summary"]`
- [ ] T017 [US6] Add payroll context to AI prompt in `backend/app/modules/tax_planning/prompts.py` — add "--- Payroll Data ---" section with employee count, wages, super, and note about owners/directors
- [ ] T018 [US6] Add payroll display in `frontend/src/components/tax-planning/FinancialsPanel.tsx` — show payroll summary card when data exists

**Checkpoint**: Payroll data visible and AI references super/wage strategies

---

## Phase 8: Polish

- [ ] T019 [P] Run backend lint — `cd backend && uv run ruff check app/modules/tax_planning/`
- [ ] T020 [P] Run frontend type-check — `cd frontend && npx tsc --noEmit`
- [ ] T021 Rebuild backend container — `docker compose up -d --build backend`

---

## Phase FINAL: Commit & Merge

- [ ] T022 Commit all changes, merge to main, push

---

## Dependencies

- T002-T003 (US1): Independent, no dependencies
- T004-T006 (US2): Independent
- T007-T009 (US3): Independent
- T010-T012 (US4): Independent (but similar pattern to US3)
- T013-T015 (US5): Depends on US1 (bank balance data for strategy context)
- T016-T018 (US6): Independent

US1-US4 can all run in parallel. US5 benefits from US1 being done first (bank balance). US6 is fully independent.

## Notes

- 22 tasks total, all backend-focused
- Core changes in 2 backend files (service.py, prompts.py) + 2 frontend files (FinancialsPanel.tsx, tax-planning.ts)
- No database migrations
- All new data is nullable — backward-compatible with existing tax plans
