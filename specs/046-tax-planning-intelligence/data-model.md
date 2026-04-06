# Data Model: Tax Planning Intelligence Improvements

**Date**: 2026-04-06

## No Schema Changes Required

All new data stored in the existing `financials_data` JSONB field on the `TaxPlan` model.

## Enriched financials_data Structure

### Current fields (unchanged)
```
income: { revenue, other_income, total_income, breakdown }
expenses: { cost_of_sales, operating_expenses, total_expenses, breakdown }
credits: { payg_instalments, payg_withholding, franking_credits }
adjustments: []
turnover: number
months_data_available: number  ← currently hardcoded to 12
is_annualised: boolean         ← currently hardcoded to false
bank_balances: [{ account_name, closing_balance }]
total_bank_balance: number | null  ← FIX: null when no data (was 0)
last_reconciliation_date: string | null
period_coverage: string
unreconciled_summary: { ... }
```

### New fields

```
projection: {                          ← US2: Revenue forecasting
  projected_revenue: number
  projected_expenses: number
  projected_net_profit: number
  monthly_avg_revenue: number
  monthly_avg_expenses: number
  months_used: number                  ← actual months of data
  projection_method: "linear_average"
} | null

prior_year_ytd: {                      ← US3: Same period comparison
  revenue: number
  other_income: number
  total_income: number
  cost_of_sales: number
  operating_expenses: number
  total_expenses: number
  net_profit: number
  period_coverage: string              ← e.g. "1 Jul 2024 – 15 Mar 2025"
  changes: {                           ← computed % changes
    revenue_pct: number
    expenses_pct: number
    profit_pct: number
  }
} | null

prior_years: [                         ← US4: Multi-year trends
  {
    financial_year: string             ← e.g. "2025"
    revenue: number
    expenses: number
    net_profit: number
  }
] | null

strategy_context: {                    ← US5: Strategy sizing
  available_cash: number | null
  monthly_operating_expenses: number
  cash_buffer_3mo: number
  max_strategy_budget: number | null
  existing_asset_spend: number         ← from P&L line items
  existing_prepaid_expenses: number    ← from P&L line items
} | null

payroll_summary: {                     ← US6: Payroll intelligence
  employee_count: number
  total_wages_ytd: number
  total_super_ytd: number
  total_tax_withheld_ytd: number
  has_owners: boolean                  ← true if any employee has director/owner title
  employees: [
    { name, job_title, status }
  ]
} | null
```
