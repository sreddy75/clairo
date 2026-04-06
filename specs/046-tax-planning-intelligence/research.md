# Research: Tax Planning Intelligence Improvements

**Date**: 2026-04-06

## R1: Bank Balance $0 Bug

**Decision**: Set `total_bank_balance = None` when `bank_balances` is an empty array.

**Rationale**: `sum([]) = 0` in Python, which is misleading when there's no bank data. Setting to `None` means the frontend hides the section (existing `!= null` check at FinancialsPanel.tsx:171). When bank accounts exist but are genuinely $0, the array will have entries with `closing_balance: 0`, so sum will correctly be 0 and display.

**One-line fix**: `total_bank_balance = sum(a["closing_balance"] for a in bank_balances) if bank_balances else None`

## R2: Revenue Forecasting Approach

**Decision**: Simple linear projection — monthly average × 12.

**Rationale**: For beta, a simple average is sufficient. Seasonal adjustment, trend-weighted, or ML-based forecasting adds complexity without proportional value for ~10 beta users. The projection is clearly labelled as an estimate.

**Calculation**:
1. `months_elapsed` = months between FY start (1 July) and reconciliation date
2. If `months_elapsed >= 3`: `monthly_avg_revenue = total_revenue / months_elapsed`
3. `projected_revenue = monthly_avg_revenue * 12`
4. Same for expenses and net profit

**Minimum threshold**: 3 months to avoid wild extrapolation from thin data.

## R3: Prior Year P&L Pull

**Decision**: Use existing `get_report()` with prior FY period key and shifted `to_date_override`.

**Rationale**: The Xero report service already supports arbitrary period keys (e.g., `'2024-FY'`). To get the same-period comparison, we use the same `to_date_override` shifted back by one year (e.g., `2026-03-15` → `2025-03-15`).

**Implementation**: One additional `get_report()` call in `pull_xero_financials()`. The transform reuses `_transform_xero_to_financials()`.

**Error handling**: If prior year data doesn't exist (new Xero connection), catch the error and set `prior_year_ytd = None`. No user-visible error.

## R4: Multi-Year Full FY Pull

**Decision**: Pull FY-1 and FY-2 full-year P&L as separate report calls.

**Rationale**: Two additional `get_report()` calls, no `to_date_override` (full year). Store summary only (revenue, expenses, net_profit) — not full line-item breakdown to keep JSONB size manageable.

**Error handling**: Each prior year fetched independently. If FY-2 doesn't exist but FY-1 does, show only FY-1.

## R5: Strategy Sizing Context

**Decision**: Add a "Strategy Constraints" section to the scanner agent prompt, not custom logic.

**Rationale**: The AI already generates strategies. The problem is it lacks financial constraints. By adding cash available, monthly burn rate, and existing spending patterns to the prompt, the AI can self-constrain its recommendations. This is much simpler than building custom strategy sizing logic.

**Data to include**:
- Available cash (bank balance)
- Monthly operating expenses (total_expenses / months_elapsed)
- Cash buffer (3 months operating expenses)
- Max available for strategies (cash - buffer)
- Existing equipment/asset spend from P&L line items (grep for "equipment", "depreciation", "asset", "computer" in expense breakdown)

## R6: Payroll Data Integration

**Decision**: Query existing `XeroPayRun` and `XeroEmployee` tables directly in the tax planning service.

**Rationale**: The models and synced data already exist. No new Xero API calls needed — just query the local database tables that were populated during Xero sync.

**Query approach**:
```python
# Check if connection has payroll access
connection = await self.session.get(XeroConnection, plan.xero_connection_id)
if connection and connection.has_payroll_access:
    # Query pay runs for current FY
    pay_runs = await self.session.execute(
        select(XeroPayRun).where(
            XeroPayRun.connection_id == connection.id,
            XeroPayRun.period_start >= fy_start,
        )
    )
    # Query active employees
    employees = await self.session.execute(
        select(XeroEmployee).where(
            XeroEmployee.connection_id == connection.id,
            XeroEmployee.status == 'active',
        )
    )
```

**Note**: This is a cross-module query (tax_planning → xero models). The constitution says use service layer, but since we're querying read-only data in the same database session, direct model access is pragmatic for beta. Can refactor to service method later.
