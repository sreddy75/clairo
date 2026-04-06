# Quickstart: Tax Planning Intelligence Improvements

**Date**: 2026-04-06

## Verification Steps

### US1: Bank Balance Fix
1. Open a tax plan for a client with bank accounts in Xero
2. Pull financials
3. Verify bank balance shows actual amounts (not $0)
4. For a client without bank data, verify "Bank data not available" message

### US2: Revenue Forecasting
1. Open a tax plan for a client mid-financial-year (e.g., 9 months of data)
2. Pull financials
3. Verify "Projected Full Year" section appears with projected revenue, expenses, net profit
4. Verify projected figures are labelled as estimates
5. Verify tax position uses projected full-year income

### US3: Prior Year Comparison
1. Open a tax plan for a client with 2+ years of Xero data
2. Pull financials
3. Verify prior year YTD figures appear alongside current year
4. Verify growth/decline percentages are shown
5. For a new client (no prior year), verify comparison section is hidden

### US4: Multi-Year Trends
1. Open a tax plan for a client with 3+ years of Xero data
2. Pull financials
3. Verify FY-1 and FY-2 full-year summaries appear
4. Verify trend data (revenue, expenses, profit) across years

### US5: Strategy Sizing
1. Generate an AI analysis for a client with bank balance data
2. Review strategy recommendations
3. Verify suggested amounts reference actual cash available
4. Verify no strategy exceeds available cash without explanation

### US6: Payroll Intelligence
1. Open a tax plan for a client with payroll in Xero
2. Pull financials
3. Verify payroll summary shows: employee count, wages YTD, super YTD
4. Generate AI analysis — verify super contribution strategies appear
5. For a client without payroll access, verify section is omitted cleanly
