# Implementation Plan: Client Business View

## Overview

This document outlines the technical implementation plan for Spec 005: Client Business View (refactored). The feature enables accountants to view comprehensive financial data for their client businesses (XeroConnections), including contacts, invoices, bank transactions, and BAS-relevant financial summaries.

**CRITICAL DATA MODEL**: Client = XeroConnection = One Business = One BAS

---

## REFACTOR: Data Model Correction

### What Changed

| Aspect | Before (Incorrect) | After (Correct) |
|--------|-------------------|-----------------|
| "Client" refers to | XeroClient (contact) | XeroConnection (business) |
| `/clients` shows | List of contacts | List of businesses |
| `/clients/[id]` shows | Contact details | Business details with tabs |
| Contacts are | Primary entity | Sub-view within a business |
| URL parameter | `client_id` (XeroClient.id) | `connection_id` (XeroConnection.id) |

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                        │
│  ┌─────────────────┐  ┌─────────────────────────────────────┐  │
│  │ /clients        │  │ /clients/[connectionId]             │  │
│  │ List businesses │  │ Business detail with tabs:          │  │
│  │ (XeroConnections│  │ - Overview (summary cards)          │  │
│  │  for tenant)    │  │ - Contacts (XeroClients)            │  │
│  └────────┬────────┘  │ - Invoices (filtered by connection) │  │
│           │           │ - Transactions (by connection)      │  │
│           └───────────┴──────────────┬──────────────────────┘  │
│                                      │                          │
│                    ┌─────────────────▼─────────────────┐       │
│                    │       API Client Layer            │       │
│                    └─────────────────┬─────────────────┘       │
└──────────────────────────────────────┼──────────────────────────┘
                                       │ HTTP
┌──────────────────────────────────────▼──────────────────────────┐
│                        Backend (FastAPI)                         │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Clients Module (NEW)                      ││
│  │  GET /api/v1/clients                   # List connections    ││
│  │  GET /api/v1/clients/{id}              # Connection detail   ││
│  │  GET /api/v1/clients/{id}/contacts     # Contacts for conn   ││
│  │  GET /api/v1/clients/{id}/invoices     # Invoices for conn   ││
│  │  GET /api/v1/clients/{id}/transactions # Txns for conn       ││
│  │  GET /api/v1/clients/{id}/summary      # Financial summary   ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Note: Reuses existing Dashboard repository for financial calcs │
└──────────────────────────────────────────────────────────────────┘
```

---

## Implementation Strategy

### Option A: Create New `/api/v1/clients` Module (RECOMMENDED)

Create a dedicated `clients` module that focuses on the client business view:

**Pros:**
- Clean separation from dashboard (which is aggregate view)
- Clear URL structure (`/api/v1/clients/{connection_id}`)
- Easier to extend for future client-specific features
- Follows existing module pattern

**Cons:**
- Some code overlap with dashboard repository

### Option B: Extend Dashboard Module

Add client detail endpoints to the existing dashboard module.

**Pros:**
- Reuses existing code
- Single source of truth for client data

**Cons:**
- Mixes aggregate (dashboard) and detail (client) concerns
- Dashboard module becomes too large

**Decision: Option A** - Create new clients module with clean separation.

---

## Project Structure

### New Backend Module

```
backend/app/modules/clients/
├── __init__.py
├── router.py           # API endpoints
├── service.py          # Business logic
├── repository.py       # Data access (can import from dashboard)
└── schemas.py          # Request/Response models
```

### Frontend Pages (Refactored)

```
frontend/src/app/(protected)/clients/
├── page.tsx            # Client list (shows XeroConnections)
└── [id]/
    └── page.tsx        # Client detail with tabs
```

---

## API Endpoints Design

### GET /api/v1/clients

List all client businesses (XeroConnections) for the tenant.

```python
@router.get("/", response_model=ClientListResponse)
async def list_clients(
    quarter: int | None = None,
    fy_year: int | None = None,
    status: str | None = None,  # BAS status filter
    search: str | None = None,
    sort_by: str = "organization_name",
    sort_order: str = "asc",
    page: int = 1,
    limit: int = 25,
)
```

**Response:** Same as dashboard `/clients` endpoint (already refactored in Spec 006).

### GET /api/v1/clients/{connection_id}

Get detail for a single client business.

```python
@router.get("/{connection_id}", response_model=ClientDetailResponse)
async def get_client_detail(
    connection_id: UUID,
    quarter: int | None = None,
    fy_year: int | None = None,
)
```

**Response:**
```python
class ClientDetailResponse(BaseModel):
    id: UUID
    organization_name: str
    xero_tenant_id: str
    status: str
    last_full_sync_at: datetime | None
    bas_status: str

    # Financial summary for quarter
    total_sales: Decimal
    total_purchases: Decimal
    gst_collected: Decimal
    gst_paid: Decimal
    net_gst: Decimal
    invoice_count: int
    transaction_count: int
    contact_count: int

    quarter_label: str
    quarter: int
    fy_year: int
```

### GET /api/v1/clients/{connection_id}/contacts

List contacts (customers/suppliers) for a client business.

```python
@router.get("/{connection_id}/contacts", response_model=ContactListResponse)
async def list_client_contacts(
    connection_id: UUID,
    contact_type: str | None = None,  # customer, supplier, both
    search: str | None = None,
    page: int = 1,
    limit: int = 25,
)
```

### GET /api/v1/clients/{connection_id}/invoices

List invoices for a client business.

```python
@router.get("/{connection_id}/invoices", response_model=InvoiceListResponse)
async def list_client_invoices(
    connection_id: UUID,
    invoice_type: str | None = None,  # accrec, accpay
    status: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    limit: int = 20,
)
```

### GET /api/v1/clients/{connection_id}/transactions

List bank transactions for a client business.

```python
@router.get("/{connection_id}/transactions", response_model=TransactionListResponse)
async def list_client_transactions(
    connection_id: UUID,
    transaction_type: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    limit: int = 20,
)
```

---

## Frontend Component Design

### Client List Page (`/clients/page.tsx`)

This page can largely **reuse the dashboard** table since it shows the same data:
- List of XeroConnections with financial summaries
- Clicking a row navigates to `/clients/[id]`

**Key difference from dashboard:**
- Dashboard is read-only overview
- Clients page is entry point to detailed management

### Client Detail Page (`/clients/[id]/page.tsx`)

```
┌────────────────────────────────────────────────────────────────┐
│  ← Back to Clients                                              │
├────────────────────────────────────────────────────────────────┤
│  Demo Company (AU)                              Q2 FY26 ▼      │
│  ● Ready  |  Last synced: 29/12/2025           [Refresh] [Xero]│
├────────────────────────────────────────────────────────────────┤
│  [Overview] [Contacts (42)] [Invoices (89)] [Transactions (127)]│
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ Sales    │ │ Purchases│ │ Net GST  │ │ Activity │          │
│  │ $58,703  │ │ $22,230  │ │ $3,400   │ │ 127      │          │
│  │ GST:$5,337│ │ GST:$1,937│ │ Payable  │ │ items    │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│                                                                 │
│  [Tab content based on selection]                               │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### Tab Components

1. **Overview Tab**: Summary cards (can reuse existing summary cards from current client detail)
2. **Contacts Tab**: New - list of XeroClients with contact_type filter
3. **Invoices Tab**: Existing - move from current implementation
4. **Transactions Tab**: Existing - move from current implementation

---

## Migration Strategy

### Backend

1. **Create new `/api/v1/clients` module** with correct data model
2. **Keep existing `/api/v1/integrations/xero/clients` temporarily** for backwards compatibility
3. **Update frontend to use new endpoints**
4. **Deprecate old endpoints**

### Frontend

1. **Refactor `/clients/page.tsx`** to list XeroConnections instead of XeroClients
2. **Refactor `/clients/[id]/page.tsx`** to:
   - Accept connection_id instead of client_id
   - Add tabs for Overview, Contacts, Invoices, Transactions
   - Move existing invoice/transaction components into tabs
3. **Add new Contacts tab** to show XeroClients for the connection

---

## Code Reuse

### From Dashboard Module (Spec 006)

The dashboard repository already has methods for aggregating by XeroConnection:
- `get_aggregated_summary()` - Can be adapted for single connection
- `list_connections_with_financials()` - Already returns correct data

### From Existing Clients Implementation

The current implementation has useful components that need minor refactoring:
- Invoice list component (change client_id to connection_id)
- Transaction list component (change client_id to connection_id)
- Financial summary cards
- Quarter selector

---

## Implementation Phases

### Phase 1: Backend Module Setup
- Create `/api/v1/clients` module structure
- Implement list clients endpoint (reuse dashboard logic)
- Implement client detail endpoint

### Phase 2: Backend Contacts/Invoices/Transactions
- Implement contacts endpoint (filter XeroClients by connection_id)
- Implement invoices endpoint (filter by connection_id)
- Implement transactions endpoint (filter by connection_id)

### Phase 3: Frontend Client List
- Refactor `/clients/page.tsx` to show XeroConnections
- Link to new detail page

### Phase 4: Frontend Client Detail with Tabs
- Create tabbed layout
- Move existing components into tabs
- Add new Contacts tab

### Phase 5: Testing & Cleanup
- Update tests
- Remove old endpoints
- Update documentation

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking existing functionality | Feature branch, phased migration |
| Data model confusion | Clear documentation in code comments |
| Performance with large contact lists | Pagination on all endpoints |
| Missing data during migration | Keep old endpoints until new ones verified |

---

## Success Criteria

- [ ] `/clients` page shows XeroConnections (client businesses)
- [ ] `/clients/[id]` shows tabbed detail view for one business
- [ ] Contacts tab shows XeroClients for that connection
- [ ] Invoices/Transactions tabs work with connection_id
- [ ] All endpoints properly tenant-isolated
- [ ] Spec documentation matches implementation
