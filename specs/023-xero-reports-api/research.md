# Research: Xero Reports API Integration

**Feature**: 023-xero-reports-api
**Date**: 2026-01-01
**Status**: Complete

---

## Research Tasks

### 1. Xero Reports API Endpoints

**Decision**: Use Xero Accounting API v2.0 Reports endpoints

**Available Endpoints**:

| Report Type | Endpoint | Purpose |
|-------------|----------|---------|
| Profit & Loss | `GET /Reports/ProfitAndLoss` | Revenue, expenses, net profit |
| Balance Sheet | `GET /Reports/BalanceSheet` | Assets, liabilities, equity |
| Aged Receivables | `GET /Reports/AgedReceivablesByContact` | Debtor aging buckets |
| Aged Payables | `GET /Reports/AgedPayablesByContact` | Creditor aging buckets |
| Trial Balance | `GET /Reports/TrialBalance` | Account balances for reconciliation |
| Bank Summary | `GET /Reports/BankSummary` | Cash position across accounts |
| Budget Summary | `GET /Reports/BudgetSummary` | Budget vs actual variance |

**Base URL**: `https://api.xero.com/api.xro/2.0`

**Rationale**: These are the standard Xero Accounting API endpoints used by all major integrations. They provide pre-calculated financial data that Xero already computes, avoiding the need to recalculate from raw transactions.

**Alternatives Considered**:
- Xero Finance API (includes Cash Flow) - Only available for non-US organizations, not needed for initial release
- Xero Reports 2.0 (custom reports) - More flexible but complex; standard reports sufficient for MVP

---

### 2. API Parameters by Report Type

#### Profit & Loss (`GET /Reports/ProfitAndLoss`)

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `fromDate` | date | Start date (YYYY-MM-DD) | Start of current month |
| `toDate` | date | End date (YYYY-MM-DD) | Today |
| `periods` | int | Number of comparison periods | 1 |
| `timeframe` | string | `MONTH`, `QUARTER`, `YEAR` | `MONTH` |
| `trackingCategoryID` | UUID | Filter by tracking category | None |
| `trackingCategoryID2` | UUID | Second tracking filter | None |
| `trackingOptionID` | UUID | Specific tracking option | None |
| `trackingOptionID2` | UUID | Second tracking option | None |
| `standardLayout` | bool | Use standard chart of accounts layout | `true` |
| `paymentsOnly` | bool | Cash basis (vs accrual) | `false` |
| `date` | date | **CRITICAL**: Undocumented parameter needed for per-period amounts | Same as `fromDate` |

**Example**:
```
GET /Reports/ProfitAndLoss?date=2025-07-01&fromDate=2025-07-01&toDate=2025-12-31&timeframe=MONTH&periods=6&standardLayout=true
```

**Important Note**: The `date` parameter is undocumented but critical for getting amounts by account and period. Without it, results are cumulative.

#### Balance Sheet (`GET /Reports/BalanceSheet`)

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `date` | date | Report as-of date | Today |
| `periods` | int | Number of comparison periods | 1 |
| `timeframe` | string | `MONTH`, `QUARTER`, `YEAR` | `MONTH` |
| `trackingCategoryID` | UUID | Filter by tracking category | None |
| `trackingOptionID` | UUID | Specific tracking option | None |
| `standardLayout` | bool | Use standard chart of accounts layout | `true` |
| `paymentsOnly` | bool | Cash basis (vs accrual) | `false` |

**Example**:
```
GET /Reports/BalanceSheet?date=2025-12-31&periods=2&timeframe=MONTH&standardLayout=true
```

#### Aged Receivables (`GET /Reports/AgedReceivablesByContact`)

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `date` | date | Aged as-of date | Today |
| `fromDate` | date | Filter: invoices from | None |
| `toDate` | date | Filter: invoices to | None |

**Example**:
```
GET /Reports/AgedReceivablesByContact?date=2025-12-31
```

**Response includes**: Contact details with amounts in aging buckets (Current, 1-30, 31-60, 61-90, 90+)

#### Aged Payables (`GET /Reports/AgedPayablesByContact`)

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `date` | date | Aged as-of date | Today |
| `fromDate` | date | Filter: bills from | None |
| `toDate` | date | Filter: bills to | None |

**Example**:
```
GET /Reports/AgedPayablesByContact?date=2025-12-31
```

#### Trial Balance (`GET /Reports/TrialBalance`)

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `date` | date | Report as-of date | End of current month |
| `paymentsOnly` | bool | Cash basis | `false` |

**Example**:
```
GET /Reports/TrialBalance?date=2025-12-31
```

#### Bank Summary (`GET /Reports/BankSummary`)

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `fromDate` | date | Period start | Start of current month |
| `toDate` | date | Period end | Today |

**Example**:
```
GET /Reports/BankSummary?fromDate=2025-12-01&toDate=2025-12-31
```

#### Budget Summary (`GET /Reports/BudgetSummary`)

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `date` | date | Budget as-of date | Today |
| `periods` | int | Number of periods | 12 |
| `timeframe` | int | 1=months, 2=quarters | 1 |

**Example**:
```
GET /Reports/BudgetSummary?date=2025-12-31&periods=12&timeframe=1
```

**Note**: Returns empty if no budget configured in Xero.

---

### 3. Rate Limiting Strategy

**Decision**: Implement staggered batch sync with rate limit awareness

**Xero Rate Limits**:
| Limit Type | Value |
|------------|-------|
| Per Minute | 60 requests |
| Per Day | 5,000 requests |
| Concurrent | 5 requests |

**Strategy**:
1. **Nightly Batch**: Sync all reports during off-peak hours (2-5 AM AEST)
2. **Stagger Clients**: Process 10 clients per minute (7 reports × 10 = 70 requests, stay under 60 by spreading)
3. **Priority Queue**: P&L and Balance Sheet first, then Aged reports, then others
4. **Rate Limit Tracking**: Use existing `XeroRateLimiter` from `rate_limiter.py`
5. **Backoff**: Exponential backoff on 429 responses (existing pattern)

**Calculation for 100 clients**:
- Reports per client: 7
- Total requests: 700
- At 50 req/min (safe margin): 14 minutes
- With token refresh overhead: ~20 minutes
- Target: <30 minutes ✅

**Rationale**: Existing rate limiter infrastructure handles this well. Just need to integrate report calls into the existing sync flow.

**Alternatives Considered**:
- Dedicated rate limit pool for reports - Rejected; overly complex, existing limiter works
- Real-time fetch only - Rejected; would exceed rate limits during peak usage

---

### 4. Response Structure Analysis

**Decision**: Store as JSONB with normalized metadata

**Common Response Structure** (all reports):
```json
{
  "Reports": [{
    "ReportID": "uuid",
    "ReportName": "Profit and Loss",
    "ReportType": "ProfitAndLoss",
    "ReportTitles": ["Title", "Date Range", "Basis"],
    "ReportDate": "2025-12-31",
    "UpdatedDateUTC": "/Date(1735689600000)/",
    "Fields": [],
    "Rows": [
      {
        "RowType": "Header",
        "Cells": [{"Value": "Account"}, {"Value": "Dec 2025"}]
      },
      {
        "RowType": "Section",
        "Title": "Revenue",
        "Rows": [
          {
            "RowType": "Row",
            "Cells": [
              {"Value": "Sales", "Attributes": [{"Id": "account", "Value": "uuid"}]},
              {"Value": "125000.00"}
            ]
          }
        ]
      },
      {
        "RowType": "SummaryRow",
        "Cells": [{"Value": "Total Revenue"}, {"Value": "125000.00"}]
      }
    ]
  }]
}
```

**Row Types**:
- `Header` - Column headers
- `Section` - Category group (e.g., "Revenue", "Expenses")
- `Row` - Individual line item
- `SummaryRow` - Totals

**Storage Approach**:
1. **xero_reports table**: Metadata (id, client_id, type, period, fetched_at, etc.)
2. **JSONB column**: Raw `Rows` array for flexibility
3. **Extracted fields**: Key totals for quick queries (revenue, net_profit, etc.)

**Rationale**: Reports have different structures per type. JSONB handles evolution gracefully while extracted fields enable efficient queries.

---

### 5. Caching Strategy

**Decision**: TTL-based caching with on-demand refresh

| Report Type | Historical Cache | Current Period Cache | Refresh Throttle |
|-------------|------------------|---------------------|------------------|
| Profit & Loss | Indefinite | 1 hour | 5 min |
| Balance Sheet | Indefinite | 1 hour | 5 min |
| Aged Receivables | N/A | 4 hours | 5 min |
| Aged Payables | N/A | 4 hours | 5 min |
| Trial Balance | Indefinite | 1 hour | 5 min |
| Bank Summary | Indefinite | 4 hours | 5 min |
| Budget Summary | Indefinite | 24 hours | 15 min |

**Historical Definition**:
- For period reports (P&L): Any period ending before current month
- For snapshot reports (Balance Sheet): Any date before yesterday

**Rationale**:
- Historical data doesn't change (Xero doesn't allow backdating)
- Current period changes frequently with new transactions
- Budget rarely changes, longest TTL
- Throttle prevents abuse of on-demand refresh

**Alternatives Considered**:
- Webhook-based invalidation - Rejected; Xero doesn't provide report webhooks
- No caching (always fresh) - Rejected; would exceed rate limits
- Longer TTL for current period - Rejected; accountants expect recent data

---

### 6. Error Handling

**Decision**: Graceful degradation with clear user feedback

**Error Scenarios**:

| Scenario | Response | User Message |
|----------|----------|--------------|
| Connection expired | Queue reconnection, show stale data | "Data may be outdated. Reconnect Xero to refresh." |
| Rate limit exceeded | Queue for later sync | "Report is being prepared. Check back in a few minutes." |
| Report not available | Return empty with flag | "Budget not configured in Xero" (for Budget Summary) |
| Xero API error | Log, retry later | "Unable to fetch report. We'll retry automatically." |
| No data for period | Return empty report | "No transactions found for this period." |

**Audit Events**:
- `report.sync.started` - Begin sync
- `report.sync.completed` - Success with row count
- `report.sync.failed` - Failure with error code
- `report.viewed` - User access

**Rationale**: ATO compliance requires audit trail. Graceful degradation ensures users can continue working even if sync fails.

---

### 7. AI Agent Integration

**Decision**: Add report summaries to client context

**Context Enhancement**:
```python
# agents/context.py
def get_client_financial_context(client_id: UUID) -> dict:
    """Enhanced context with report data."""
    return {
        # Existing
        "invoices": [...],
        "transactions": [...],
        "accounts": [...],

        # NEW: Report summaries
        "profit_and_loss": {
            "period": "2025-07-01 to 2025-12-31",
            "revenue": 245000,
            "cost_of_sales": 98000,
            "gross_profit": 147000,
            "gross_margin_pct": 60.0,
            "expenses": 112000,
            "net_profit": 35000,
            "net_margin_pct": 14.3
        },
        "balance_sheet": {
            "as_of": "2025-12-31",
            "current_assets": 180000,
            "current_liabilities": 85000,
            "current_ratio": 2.12,
            "total_assets": 320000,
            "total_liabilities": 140000,
            "equity": 180000
        },
        "aged_receivables": {
            "as_of": "2025-12-31",
            "total": 68500,
            "current": 45000,
            "overdue_30": 12000,
            "overdue_60": 3000,
            "overdue_90_plus": 8500,
            "high_risk_debtors": [
                {"contact": "ABC Corp", "amount": 8500, "days_overdue": 95}
            ]
        }
    }
```

**Agent Capabilities Enabled**:
- **Financial Health Agent**: Calculate accurate ratios from pre-calculated data
- **Trend Analysis Agent**: Compare periods using Xero's calculations
- **Collection Risk Agent**: Identify high-risk debtors from aged receivables
- **Budget Variance Agent**: Highlight overspend from budget summary

**Rationale**: Agents currently must calculate these metrics from raw data (error-prone). Using Xero's calculations ensures accuracy and reduces compute.

---

## Summary of Decisions

| Area | Decision |
|------|----------|
| API Version | Xero Accounting API v2.0 |
| Reports to Sync | 7 types (P&L, Balance Sheet, Aged AR/AP, Trial Balance, Bank Summary, Budget) |
| Storage | JSONB in PostgreSQL with extracted summary fields |
| Caching | TTL-based (1-24 hours depending on type) |
| Sync Schedule | Nightly batch + on-demand refresh |
| Rate Limiting | Use existing `XeroRateLimiter`, stagger clients |
| Error Handling | Graceful degradation, audit logging |
| AI Integration | Add report summaries to client context |

---

## Sources

- [Xero Developer - Accounting API Reports](https://developer.xero.com/documentation/api/accounting/reports)
- [Xero API Directory - GetKnit](https://www.getknit.dev/blog/xero-api-directory)
- [Xero Community - P&L API Parameters](https://community.xero.com/developer/discussion/135690020)
- [SyncHub - Building Charts with Xero Reporting API](https://blog.synchub.io/articles/building-meaningful-charts-using-xeros-reporting-api)
