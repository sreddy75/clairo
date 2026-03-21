# Feature Specification: Xero Reports API Integration

**Feature Branch**: `023-xero-reports-api`
**Created**: 2026-01-01
**Status**: Draft
**Phase**: E (Data Intelligence)

## Overview

Integrate Xero Reports API to fetch pre-calculated financial reports (P&L, Balance Sheet, Aged Receivables/Payables, Trial Balance, Bank Summary, Budget Summary). This data enhances AI agent analysis by providing accurate, Xero-calculated financial metrics rather than requiring Clairo to recalculate from raw transactions.

**Why This Matters**:
- Gap analysis revealed we're fetching only ~20% of available Xero data
- Reports API provides pre-calculated financials (no calculation errors)
- Enables deeper AI insights: liquidity analysis, trend detection, collection risk
- Foundation for Specs 024 (Credit Notes/Payments) and 025 (Fixed Assets)

---

## User Scenarios & Testing

### User Story 1 - View Profit & Loss Summary (Priority: P1)

As an accountant reviewing a client, I want to see the P&L summary from Xero so that I can quickly understand revenue, expenses, and profitability without manually calculating from transactions.

**Why this priority**: P&L is the most frequently requested financial report. Accountants need this for every client review and BAS preparation.

**Independent Test**: Navigate to any client → Financial Reports section → P&L report displays with revenue, expenses, net profit for selected period.

**Acceptance Scenarios**:

1. **Given** a client with Xero connection, **When** I navigate to Financial Reports and select P&L, **Then** I see revenue, cost of sales, gross profit, expenses, and net profit for the current financial year.

2. **Given** a P&L report is displayed, **When** I select a different period (monthly, quarterly, YTD), **Then** the report updates to show figures for that period with comparison to prior period.

3. **Given** a client with no Xero data for the period, **When** I view P&L, **Then** I see an empty state with message "No data for this period".

---

### User Story 2 - View Balance Sheet Snapshot (Priority: P1)

As an accountant, I want to view the Balance Sheet snapshot from Xero so that I can assess the client's financial position (assets, liabilities, equity) at any point in time.

**Why this priority**: Balance Sheet is essential for understanding financial health, liquidity ratios, and solvency. Required for proper client advisory.

**Independent Test**: Navigate to client → Financial Reports → Balance Sheet → displays assets, liabilities, equity with proper categorization.

**Acceptance Scenarios**:

1. **Given** a client with Xero connection, **When** I view Balance Sheet, **Then** I see Current Assets, Non-Current Assets, Current Liabilities, Non-Current Liabilities, and Equity sections with line items and totals.

2. **Given** a Balance Sheet is displayed, **When** I select a historical date, **Then** the report shows the financial position as of that date.

3. **Given** multiple asset/liability accounts, **When** viewing Balance Sheet, **Then** accounts are grouped by type matching Xero's chart of accounts structure.

---

### User Story 3 - View Aged Receivables Report (Priority: P1)

As an accountant, I want to see the Aged Receivables report so that I can identify which debtors are overdue and by how much, enabling proactive collection advice.

**Why this priority**: Collection risk directly impacts cash flow. Identifying overdue debtors early prevents bad debts and enables timely follow-up.

**Independent Test**: View Aged Receivables → see contacts with amounts in aging buckets (Current, 30 days, 60 days, 90+ days).

**Acceptance Scenarios**:

1. **Given** a client with outstanding invoices, **When** I view Aged Receivables, **Then** I see each debtor with amounts in Current, 1-30 days, 31-60 days, 61-90 days, and 90+ days columns.

2. **Given** the Aged Receivables report, **When** I click on a debtor, **Then** I can see the individual invoices making up their balance.

3. **Given** aged receivables data, **When** AI Insights runs, **Then** debtors over 90 days with amounts > $5,000 trigger collection risk insights.

---

### User Story 4 - View Aged Payables Report (Priority: P2)

As an accountant, I want to see the Aged Payables report so that I can understand payment obligations and advise on cash flow planning.

**Why this priority**: Understanding payables helps with cash flow forecasting and supplier relationship management, but is secondary to receivables for most accountants.

**Independent Test**: View Aged Payables → see suppliers with amounts in aging buckets.

**Acceptance Scenarios**:

1. **Given** a client with outstanding bills, **When** I view Aged Payables, **Then** I see each creditor with amounts in Current, 1-30 days, 31-60 days, 61-90 days, and 90+ days columns.

2. **Given** aged payables data, **When** AI analyzes cash flow, **Then** it factors in upcoming payment obligations for accurate forecasting.

---

### User Story 5 - View Trial Balance (Priority: P2)

As an accountant preparing BAS reconciliation, I want to view the Trial Balance so that I can verify account balances match Xero's general ledger.

**Why this priority**: Trial Balance is essential for reconciliation but typically only needed during BAS prep or EOFY, not daily viewing.

**Independent Test**: View Trial Balance → see all accounts with debit/credit balances that sum to zero.

**Acceptance Scenarios**:

1. **Given** a client with Xero connection, **When** I view Trial Balance for a period, **Then** I see all accounts with YTD movements, debit and credit columns, and a balanced total.

2. **Given** Trial Balance data, **When** comparing to BAS figures, **Then** GST account balances can be validated against BAS worksheet totals.

---

### User Story 6 - AI Enhanced Financial Analysis (Priority: P2)

As an accountant, I want AI agents to use report data for deeper insights so that I receive more accurate and actionable advice about client financial health.

**Why this priority**: This is the key value-add - making AI smarter with better data. Builds on the foundation of having reports available.

**Independent Test**: After report sync, AI chat responses include insights referencing P&L trends, liquidity ratios, collection risk based on real report data.

**Acceptance Scenarios**:

1. **Given** P&L data is synced, **When** Financial Health agent runs, **Then** it calculates and reports gross margin, expense ratios, and profit trends.

2. **Given** Balance Sheet data is synced, **When** Financial Health agent runs, **Then** it calculates current ratio, quick ratio, and debt-to-equity metrics.

3. **Given** Aged Receivables data, **When** Collection Risk agent runs, **Then** it identifies high-risk debtors and suggests follow-up actions.

4. **Given** Budget Summary data (if available), **When** Budget Variance agent runs, **Then** it highlights categories exceeding budget thresholds.

---

### User Story 7 - Bank Summary View (Priority: P3)

As an accountant, I want to see the Bank Summary report so that I can quickly view cash positions across all bank accounts.

**Why this priority**: Useful for cash flow overview but lower priority as bank feeds already show individual account balances.

**Independent Test**: View Bank Summary → see all bank accounts with opening balance, receipts, payments, closing balance.

**Acceptance Scenarios**:

1. **Given** a client with bank accounts in Xero, **When** I view Bank Summary, **Then** I see each account with opening balance, total receipts, total payments, and closing balance for the period.

---

### Edge Cases

- What happens when Xero rate limits are exceeded during report sync?
  → Queue and retry with exponential backoff, continue with other clients

- How does system handle reports for clients with no transactions?
  → Display empty report with informative message, don't show as error

- What happens when a report type isn't available (e.g., no budget configured)?
  → Gracefully indicate "Budget not configured in Xero" rather than error

- How are multi-currency clients handled in reports?
  → Display in base currency as returned by Xero, note currency in report header

- What if Xero connection expires mid-sync?
  → Mark sync as partial, queue reconnection notification, use last successful data

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST sync Profit and Loss report from Xero for configurable periods (monthly, quarterly, YTD, custom)
- **FR-002**: System MUST sync Balance Sheet report from Xero as of configurable dates
- **FR-003**: System MUST sync Aged Receivables by Contact report with aging buckets
- **FR-004**: System MUST sync Aged Payables by Contact report with aging buckets
- **FR-005**: System MUST sync Trial Balance report for period reconciliation
- **FR-006**: System MUST sync Bank Summary report for cash position overview
- **FR-007**: System SHOULD sync Budget Summary report when budget is configured in Xero
- **FR-008**: System MUST cache reports with configurable TTL (default: 24 hours for historical, 1 hour for current period)
- **FR-009**: System MUST handle Xero rate limits (60 requests/minute) with queuing and backoff
- **FR-010**: System MUST provide on-demand report refresh for current period data
- **FR-011**: Reports MUST be accessible via API for AI agent consumption
- **FR-012**: System MUST track report sync status per client (last sync, sync errors)

### Key Entities

- **XeroReport**: Represents a fetched report instance (type, period, client, data, sync metadata)
- **XeroReportRow**: Individual line item in a report (account, values, section)
- **XeroReportCell**: Cell value in a report row (period, value, type)

### Non-Functional Requirements

- **NFR-001**: Report sync for 100 clients MUST complete within 30 minutes
- **NFR-002**: Report data queries MUST respond in <500ms
- **NFR-003**: Report data MUST be stored for 7 years (ATO compliance)

---

## Auditing & Compliance Checklist

### Audit Events Required

- [ ] **Authentication Events**: No - uses existing Xero OAuth flow
- [x] **Data Access Events**: Yes - reading financial reports is sensitive data access
- [x] **Data Modification Events**: Yes - storing synced report data
- [x] **Integration Events**: Yes - Xero API calls for report fetching
- [ ] **Compliance Events**: No - reports don't directly affect BAS lodgement

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| `report.sync.started` | Report sync begins | client_id, report_type, period | 5 years | None |
| `report.sync.completed` | Report sync succeeds | client_id, report_type, row_count, duration_ms | 5 years | None |
| `report.sync.failed` | Report sync fails | client_id, report_type, error_code, error_message | 5 years | None |
| `report.viewed` | User views report | user_id, client_id, report_type, period | 5 years | None |
| `report.exported` | User exports report | user_id, client_id, report_type, format | 5 years | None |

### Compliance Considerations

- **ATO Requirements**: Report data must be retained for 7 years as supporting documentation
- **Data Retention**: Reports should be versioned (keep historical syncs for audit trail)
- **Access Logging**: All report views logged for compliance (who viewed what, when)

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of clients with Xero connection have P&L and Balance Sheet synced within 24 hours of connection
- **SC-002**: Aged Receivables/Payables data feeds into AI insights for collection risk (>80% of applicable clients)
- **SC-003**: Report sync completes without errors for >99% of clients per day
- **SC-004**: AI agent financial insights accuracy improves by >30% (measured by user feedback ratings)
- **SC-005**: Report view latency <1 second for any report type and period

---

## Technical Notes (for Plan phase)

### Xero Reports API Endpoints

```
GET /Reports/ProfitAndLoss
GET /Reports/BalanceSheet
GET /Reports/AgedReceivablesByContact
GET /Reports/AgedPayablesByContact
GET /Reports/TrialBalance
GET /Reports/BankSummary
GET /Reports/BudgetSummary
```

### Key Parameters

- `fromDate`, `toDate` - Period range
- `periods` - Number of comparison periods
- `timeframe` - MONTH, QUARTER, YEAR
- `trackingCategoryID` - Filter by tracking category (department/project)

### Rate Limiting Strategy

- Xero allows 60 requests/minute
- Report endpoints are relatively expensive (count as 1 request each)
- Batch sync during off-peak hours (night)
- Priority: P&L and Balance Sheet first, then Aged Reports, then others

### Caching Strategy

- Historical periods: Cache indefinitely (data doesn't change)
- Current period: Cache for 1 hour, refresh on demand
- Store in PostgreSQL with JSONB for flexible report structure

---

## Dependencies

- **Spec 003 (Xero OAuth)**: Required - need valid Xero connection ✓
- **Spec 004 (Xero Data Sync)**: Required - sync infrastructure exists ✓
- **Spec 014 (Multi-Agent Framework)**: Required for AI enhancement ✓
- **Phase D**: Required - subscription/gating in place ✓
