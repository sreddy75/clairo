# Implementation Plan: Tax Planning Intelligence Improvements

**Branch**: `046-tax-planning-intelligence` | **Date**: 2026-04-06 | **Spec**: [spec.md](spec.md)

## Summary

Enrich the tax planning module with 6 improvements from beta tester feedback: fix bank balance display, add revenue forecasting, pull prior year comparisons, add multi-year trends, ground AI strategies in actual financial data, and incorporate payroll intelligence. All changes modify existing files — no new tables, columns, or migrations.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Anthropic SDK (Claude Sonnet)
**Storage**: PostgreSQL 16 — existing `financials_data` JSONB field on TaxPlan model
**Testing**: pytest + pytest-asyncio
**Constraints**: No schema changes, backward-compatible with existing tax plans

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Modular monolith | PASS | All changes within tax_planning module + prompts |
| Repository pattern | PASS | Uses existing plan_repo, Xero report service |
| Multi-tenancy | PASS | All queries scoped by tenant_id |
| Audit logging | PASS | New Xero data pulls logged via existing integration audit |
| No cross-module DB queries | PASS | Payroll data queried via Xero models within tax_planning service |

## Key Files to Modify

### Backend (4 files)

| File | Changes |
|------|---------|
| `backend/app/modules/tax_planning/service.py` | Fix bank balance null handling, add prior year P&L pull, add forecasting logic, add payroll query |
| `backend/app/modules/tax_planning/prompts.py` | Extend `format_financial_context()` with projection, prior year, payroll, strategy context |
| `backend/app/modules/tax_planning/agents/prompts.py` | Update scanner prompt to include actual financial constraints for strategy sizing |
| `backend/app/modules/tax_planning/agents/scanner.py` | Pass enriched financial context to scanner agent |

### Frontend (2 files)

| File | Changes |
|------|---------|
| `frontend/src/components/tax-planning/FinancialsPanel.tsx` | Add projection display, prior year comparison, payroll summary sections |
| `frontend/src/types/tax-planning.ts` | Extend financial data types for new fields |

## Implementation Phases

### Phase 1: Bank Balance Fix (US1) — Quick Win

**service.py:223**: When `bank_balances` is empty list, set `total_bank_balance = None` instead of `sum([]) = 0`.

```python
# BEFORE
total_bank_balance = sum(a["closing_balance"] for a in bank_balances)

# AFTER
total_bank_balance = sum(a["closing_balance"] for a in bank_balances) if bank_balances else None
```

Frontend already handles `null` correctly (hides section). No frontend changes needed.

### Phase 2: Revenue Forecasting (US2)

**service.py**: After `_transform_xero_to_financials()`, calculate months elapsed and project.

1. Calculate `months_elapsed` from FY start to reconciliation date
2. If `months_elapsed >= 3`, compute monthly averages for revenue, expenses, net profit
3. Project to 12 months: `projected_X = monthly_avg_X * 12`
4. Store in `financials_data`: `projection` dict with `projected_revenue`, `projected_expenses`, `projected_net_profit`, `months_data_available`, `is_annualised: True`
5. Update `months_data_available` to actual months (not hardcoded 12)

**prompts.py**: Add projection section to AI context: "--- Full Year Projection --- Projected Revenue: $X (based on N months YTD)"

**FinancialsPanel.tsx**: Show "Projected Full Year" card below YTD actuals when projection exists. Badge with "Projected" label.

### Phase 3: Prior Year Comparison (US3)

**service.py**: After current P&L pull, make second `get_report()` call with prior FY period key and same `to_date_override` (same months).

```python
# Current FY: "2025-FY" with to_date "2026-03-15"
# Prior YTD: "2024-FY" with to_date "2025-03-15" (same month/day, year-1)
prior_fy_key = f"{int(plan.financial_year[:4]) - 1}-FY"
prior_to_date = effective_to.replace(str(fy_year), str(fy_year - 1))  # shift 1 year back
```

Store as `financials_data["prior_year_ytd"]` with same structure as current income/expenses.

**prompts.py**: Add "--- Same Period Last Year ---" section with revenue, expenses, and % change.

**FinancialsPanel.tsx**: Show comparison table: Current vs Prior with change arrows and percentages.

### Phase 4: Multi-Year Trends (US4)

**service.py**: Pull full FY P&L for FY-1 and FY-2 (no to_date_override = full year).

```python
# FY-1 full year
prior1 = await report_service.get_report(connection_id, "profit_and_loss", f"{fy_year - 1}-FY")
# FY-2 full year
prior2 = await report_service.get_report(connection_id, "profit_and_loss", f"{fy_year - 2}-FY")
```

Store as `financials_data["prior_years"]` = `[{year, revenue, expenses, net_profit}, ...]`

**prompts.py**: Add "--- Multi-Year Trends ---" section showing 3-year trend.

**FinancialsPanel.tsx**: Show trend mini-table: FY-2 → FY-1 → Current (projected).

### Phase 5: Data-Informed Strategy Sizing (US5)

**prompts.py / agents/prompts.py**: Enrich the scanner agent's system prompt with a "Strategy Constraints" section:

```
--- Strategy Constraints ---
Available Cash: $X (from bank balance)
Monthly Operating Expenses: $X (from P&L)
Cash Buffer Required: ~3 months operating expenses
Maximum Available for Strategies: $X (cash - 3mo buffer)
Existing Asset Purchases YTD: $X (from P&L equipment/depreciation lines)
```

This gives the AI realistic bounds for strategy amounts. No code logic change — just richer context.

### Phase 6: Payroll Intelligence (US6)

**service.py**: After bank balance fetch, if `connection.has_payroll_access`:
1. Query `XeroPayRun` table for this connection's pay runs in the current FY
2. Query `XeroEmployee` table for active employees
3. Aggregate: employee_count, total_wages_ytd, total_super_ytd, total_tax_withheld_ytd
4. Store as `financials_data["payroll_summary"]`

**prompts.py**: Add "--- Payroll Data ---" section with employee count, wages, super, and note about owner/director employees.

**FinancialsPanel.tsx**: Show payroll summary card when data exists.

## Complexity Tracking

No constitution violations. All data stored in existing `financials_data` JSONB.
