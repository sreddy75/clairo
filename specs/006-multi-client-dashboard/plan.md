# Implementation Plan: Multi-Client Dashboard

**Branch**: `feature/006-dashboard-refactor` | **Date**: 2025-12-29 | **Spec**: [spec.md](./spec.md)

## Summary

Implement a comprehensive dashboard for accountants to view all client businesses (XeroConnections) with BAS readiness indicators, financial summaries, and portfolio management capabilities. Each row in the dashboard represents one client business (one Xero organization), which corresponds to one BAS that needs to be lodged.

**CRITICAL DATA MODEL**: Client = XeroConnection = One Business = One BAS

## Technical Context

**Language/Version**: Python 3.12+ (Backend), TypeScript/React (Frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Next.js 14, Tailwind CSS
**Storage**: PostgreSQL 16 with existing Xero tables
**Testing**: pytest with pytest-asyncio (backend), React Testing Library (frontend)
**Target Platform**: Web application (desktop-first, responsive)
**Performance Goals**: Dashboard load <800ms P95 for 100 client businesses
**Constraints**: Must aggregate by XeroConnection, RLS tenant isolation
**Scale/Scope**: Up to 100 client businesses (connections) per tenant

## Constitution Check

*GATE: Must pass before implementation*

| Requirement | Status | Notes |
|-------------|--------|-------|
| Modular Monolith Architecture | ✓ | Dashboard module under `modules/dashboard/` |
| Repository Pattern | ✓ | DashboardRepository for aggregations |
| Multi-Tenancy (RLS) | ✓ | All queries scoped by tenant_id |
| Type Hints Everywhere | ✓ | Full typing with Pydantic schemas |
| Unit Tests 80% | ✓ | Service layer tests required |
| Integration Tests 100% | ✓ | All API endpoints tested |
| Audit Logging | ✓ | Data access events logged |
| API Design Standards | ✓ | RESTful endpoints under `/api/v1/dashboard/` |

## Project Structure

### Documentation (this feature)

```text
specs/006-multi-client-dashboard/
├── spec.md              # Requirements document (updated)
├── plan.md              # This file (updated)
└── tasks.md             # Task list (to be updated)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── modules/
│   │   └── dashboard/           # Dashboard module
│   │       ├── __init__.py
│   │       ├── router.py        # API endpoints
│   │       ├── service.py       # Business logic
│   │       ├── schemas.py       # Request/Response models
│   │       └── repository.py    # Data access (aggregations by connection)
│   │
│   └── modules/integrations/xero/
│       └── models.py            # XeroConnection, XeroInvoice, XeroBankTransaction
│
├── tests/
│   ├── unit/modules/dashboard/
│   │   ├── test_service.py
│   │   └── test_repository.py
│   └── integration/api/
│       └── test_dashboard_endpoints.py

frontend/
├── src/
│   └── app/
│       └── (protected)/
│           └── dashboard/       # Dashboard page
│               └── page.tsx
```

---

## Architecture Design

### Data Model (CRITICAL)

```
┌─────────────────────────────────────────────────────────────────┐
│               Accounting Practice (Clairo Tenant)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  XeroConnection A          XeroConnection B       XeroConnection C
│  "ABC Pty Ltd"             "XYZ Trading"          "123 Services"
│  ────────────────          ────────────────       ────────────────
│  → BAS #1                  → BAS #2               → BAS #3
│                                                                  │
│  ┌───────────────┐         ┌───────────────┐     ┌───────────────┐
│  │ XeroInvoices  │         │ XeroInvoices  │     │ XeroInvoices  │
│  │ XeroTxns      │         │ XeroTxns      │     │ XeroTxns      │
│  │ XeroClients*  │         │ XeroClients*  │     │ XeroClients*  │
│  └───────────────┘         └───────────────┘     └───────────────┘
│                                                                  │
│  * XeroClients are contacts WITHIN a business, not BAS entities  │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Dashboard Page  │  │ Summary Cards   │  │ Client Table    │ │
│  │ /dashboard      │  │ Component       │  │ (by Connection) │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
│           │                    │                    │           │
│           └────────────────────┼────────────────────┘           │
│                                │                                │
│                    ┌───────────▼───────────┐                   │
│                    │   API Client Layer    │                   │
│                    │   (apiClient calls)   │                   │
│                    └───────────┬───────────┘                   │
└────────────────────────────────┼────────────────────────────────┘
                                 │ HTTP
┌────────────────────────────────▼────────────────────────────────┐
│                        Backend (FastAPI)                         │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Dashboard Router                          ││
│  │  GET /summary              GET /clients                      ││
│  └────────────────────────┬────────────────────────────────────┘│
│                           │                                      │
│  ┌────────────────────────▼────────────────────────────────────┐│
│  │                  Dashboard Service                           ││
│  │  - get_summary()         # Aggregate all connections         ││
│  │  - get_client_portfolio() # List connections with financials ││
│  │  - calculate_bas_status() # Per connection                   ││
│  └────────────────────────┬────────────────────────────────────┘│
│                           │                                      │
│  ┌────────────────────────▼────────────────────────────────────┐│
│  │                Dashboard Repository                          ││
│  │  - get_aggregated_summary() # Aggregate by tenant            ││
│  │  - list_connections_with_financials() # Per connection       ││
│  │  - get_status_counts()   # Count by BAS status               ││
│  └────────────────────────┬────────────────────────────────────┘│
│                           │                                      │
└───────────────────────────┼─────────────────────────────────────┘
                            │
               ┌────────────▼────────────┐
               │    PostgreSQL + RLS     │
               │  xero_connections       │  ← One row = one client business
               │  xero_invoices          │  ← Aggregated per connection
               │  xero_bank_transactions │  ← Aggregated per connection
               └─────────────────────────┘
```

### BAS Status Calculation Logic (Per Connection)

```python
def calculate_bas_status(connection_id: UUID, quarter_start: date, quarter_end: date) -> BASStatus:
    """
    Determine BAS readiness status for a client business (XeroConnection).

    Status Logic:
    1. READY: Has activity AND data synced within 24 hours
    2. NEEDS_REVIEW: Has activity BUT sync is stale (>24h)
    3. NO_ACTIVITY: No invoices AND no transactions for quarter
    4. MISSING_DATA: Has invoices but no transactions, or vice versa
    """
    invoice_count = get_invoice_count_for_connection(connection_id, quarter_start, quarter_end)
    transaction_count = get_transaction_count_for_connection(connection_id, quarter_start, quarter_end)
    last_sync = connection.last_full_sync_at

    has_invoices = invoice_count > 0
    has_transactions = transaction_count > 0
    is_fresh = last_sync and last_sync > datetime.now(UTC) - timedelta(hours=24)

    if not has_invoices and not has_transactions:
        return BASStatus.NO_ACTIVITY

    if has_invoices != has_transactions:  # XOR - one but not both
        return BASStatus.MISSING_DATA

    if is_fresh:
        return BASStatus.READY
    else:
        return BASStatus.NEEDS_REVIEW
```

### Database Query Strategy

For efficient dashboard loading, we aggregate by XeroConnection:

```sql
-- Summary aggregation query (aggregate by connection for the tenant)
SELECT
    COUNT(DISTINCT conn.id) as total_clients,
    COUNT(DISTINCT CASE
        WHEN inv.id IS NOT NULL OR txn.id IS NOT NULL
        THEN conn.id
    END) as active_clients,
    COALESCE(SUM(CASE WHEN inv.invoice_type = 'accrec' THEN inv.total_amount END), 0) as total_sales,
    COALESCE(SUM(CASE WHEN inv.invoice_type = 'accpay' THEN inv.total_amount END), 0) as total_purchases,
    COALESCE(SUM(CASE WHEN inv.invoice_type = 'accrec' THEN inv.tax_amount END), 0) as gst_collected,
    COALESCE(SUM(CASE WHEN inv.invoice_type = 'accpay' THEN inv.tax_amount END), 0) as gst_paid
FROM xero_connections conn
LEFT JOIN xero_invoices inv ON conn.id = inv.connection_id
    AND inv.issue_date BETWEEN :quarter_start AND :quarter_end
    AND inv.status IN ('authorised', 'paid')
LEFT JOIN xero_bank_transactions txn ON conn.id = txn.connection_id
    AND txn.transaction_date BETWEEN :quarter_start AND :quarter_end
WHERE conn.tenant_id = :tenant_id
    AND conn.status = 'active';
```

```sql
-- Client list query (one row per connection)
SELECT
    conn.id,
    conn.organization_name,
    conn.last_full_sync_at,
    COALESCE(SUM(CASE WHEN inv.invoice_type = 'accrec' THEN inv.total_amount END), 0) as total_sales,
    COALESCE(SUM(CASE WHEN inv.invoice_type = 'accpay' THEN inv.total_amount END), 0) as total_purchases,
    COALESCE(SUM(CASE WHEN inv.invoice_type = 'accrec' THEN inv.tax_amount END), 0) as gst_collected,
    COALESCE(SUM(CASE WHEN inv.invoice_type = 'accpay' THEN inv.tax_amount END), 0) as gst_paid,
    COUNT(DISTINCT inv.id) as invoice_count,
    COUNT(DISTINCT txn.id) as transaction_count
FROM xero_connections conn
LEFT JOIN xero_invoices inv ON conn.id = inv.connection_id
    AND inv.issue_date BETWEEN :quarter_start AND :quarter_end
    AND inv.status IN ('authorised', 'paid')
LEFT JOIN xero_bank_transactions txn ON conn.id = txn.connection_id
    AND txn.transaction_date BETWEEN :quarter_start AND :quarter_end
WHERE conn.tenant_id = :tenant_id
    AND conn.status = 'active'
GROUP BY conn.id, conn.organization_name, conn.last_full_sync_at
ORDER BY conn.organization_name;
```

---

## API Endpoints Design

### GET /api/v1/dashboard/summary

Returns aggregated dashboard metrics across all client businesses.

**Query Parameters:**
- `quarter` (int, optional): 1-4, default current
- `fy_year` (int, optional): e.g., 2025, default current

**Response Schema:**
```python
class DashboardSummaryResponse(BaseModel):
    total_clients: int           # Count of XeroConnections
    active_clients: int          # Connections with activity this quarter
    total_sales: Decimal
    total_purchases: Decimal
    gst_collected: Decimal
    gst_paid: Decimal
    net_gst: Decimal
    status_counts: StatusCounts
    quarter_label: str           # e.g., "Q2 FY25"
    quarter: int
    fy_year: int
    last_sync_at: datetime | None

class StatusCounts(BaseModel):
    ready: int
    needs_review: int
    no_activity: int
    missing_data: int
```

### GET /api/v1/dashboard/clients

Returns paginated list of client businesses with financial data.

**Query Parameters:**
- `quarter`, `fy_year` (as above)
- `status` (str, optional): ready|needs_review|no_activity|missing_data
- `search` (str, optional): Search by organization name
- `sort_by` (str): organization_name|total_sales|total_purchases|net_gst|activity_count
- `sort_order` (str): asc|desc
- `page` (int): Default 1
- `limit` (int): Default 25, max 100

**Response Schema:**
```python
class ClientPortfolioItem(BaseModel):
    id: UUID                     # XeroConnection ID
    organization_name: str
    total_sales: Decimal
    total_purchases: Decimal
    gst_collected: Decimal
    gst_paid: Decimal
    net_gst: Decimal
    invoice_count: int
    transaction_count: int
    activity_count: int
    bas_status: str
    last_synced_at: datetime | None

class ClientPortfolioResponse(BaseModel):
    clients: list[ClientPortfolioItem]
    total: int
    page: int
    limit: int
```

---

## Frontend Component Design

### Page Structure

```
/dashboard (page.tsx)
├── DashboardHeader
│   ├── PageTitle
│   ├── QuarterSelector
│   └── QuickActions (Refresh, Export)
│
├── SummaryCards
│   ├── TotalClientsCard        # Count of client businesses
│   ├── ActiveClientsCard       # With activity this quarter
│   ├── NetGSTCard              # Total GST position
│   └── NeedsReviewCard         # Clients needing attention
│
├── FilterBar
│   ├── SearchInput             # Search by org name
│   └── StatusFilter            # Filter by BAS status
│
└── ClientPortfolioTable
    ├── TableHeader (sortable columns)
    │   - Organization Name
    │   - Total Sales
    │   - Total Purchases
    │   - Net GST
    │   - Activity Count
    │   - BAS Status
    │   - Last Synced
    ├── TableBody (one row per connection)
    └── Pagination
```

### State Management

```typescript
// Dashboard page state
const [quarter, setQuarter] = useState<QuarterInfo>(getCurrentQuarter());
const [statusFilter, setStatusFilter] = useState<string | null>(null);
const [search, setSearch] = useState('');
const [sortBy, setSortBy] = useState('organization_name');
const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
const [page, setPage] = useState(1);

// Data fetching
const [summary, setSummary] = useState<DashboardSummary | null>(null);
const [clients, setClients] = useState<ClientPortfolioItem[]>([]);
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);
```

---

## Implementation Phases

### Phase 1: Backend Repository Refactor
- Update DashboardRepository to aggregate by XeroConnection
- Remove XeroClient-based aggregation
- Update SQL queries to join from xero_connections

### Phase 2: Backend Schemas/Service Update
- Update Pydantic schemas (remove contact_type, add organization_name)
- Update DashboardService to work with connections
- Update BAS status calculation for connections

### Phase 3: Backend API Update
- Update router parameters (remove connection_id filter, remove contact_type)
- Update response models
- Test endpoints

### Phase 4: Frontend Dashboard Update
- Update page to show organization_name instead of client name
- Remove contact type column and filter
- Update export functionality

### Phase 5: Testing & Cleanup
- Update unit tests
- Update integration tests
- Update tasks.md with completion status

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking existing functionality | Feature branch, thorough testing |
| Slow aggregate queries | Efficient SQL with proper indexes on connection_id |
| Confusion about data model | Clear documentation in spec.md |
| Empty state (no connections) | Handle gracefully with CTA to connect Xero |

---

## Dependencies on Existing Code

| Component | Location | Usage |
|-----------|----------|-------|
| Quarter utilities | `backend/app/modules/integrations/xero/utils.py` | BAS period calculations |
| XeroConnection model | `backend/app/modules/integrations/xero/models.py` | Connection data, last_full_sync_at |
| XeroInvoice model | Same | Invoice aggregations by connection |
| XeroBankTransaction model | Same | Transaction aggregations by connection |
| Auth dependencies | `backend/app/modules/auth/` | User/tenant context |
| API client | `frontend/src/lib/api.ts` | HTTP requests |

---

## Complexity Tracking

No constitution violations identified. This is a refactor to correct the data model understanding.

## Key Changes from Previous Implementation

| Aspect | Before (Incorrect) | After (Correct) |
|--------|-------------------|-----------------|
| "Client" refers to | XeroClient (contact) | XeroConnection (business) |
| Dashboard rows | One per contact | One per Xero org |
| Contact type filter | Included | Removed (not relevant) |
| Aggregation key | client_id | connection_id |
| BAS status | Per contact | Per business |
