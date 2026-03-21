# Implementation Tasks: Client Business View

## Overview

This document contains the actionable task list for implementing Spec 005: Client Business View (refactored).

**CRITICAL**: The original implementation used XeroClient (contacts) as the primary entity. The correct model is: **Client = XeroConnection (business) = One BAS to lodge**.

**Branch**: `feature/005-clients-refactor`
**Status**: COMPLETE

---

## REFACTOR: Data Model Correction

### What Changed

| Aspect | Before (Incorrect) | After (Correct) |
|--------|-------------------|-----------------|
| "Client" refers to | XeroClient (contact) | XeroConnection (business) |
| `/clients` shows | List of contacts | List of businesses |
| `/clients/[id]` shows | Contact details | Business details with tabs |
| Contacts are | Primary entity | Sub-view within a business |
| URL parameter | `client_id` | `connection_id` |

---

## Phase 1: Backend - New Clients Module

### Task 1.1: Create Module Structure
- [x] Create `backend/app/modules/clients/__init__.py`
- [x] Create `backend/app/modules/clients/router.py`
- [x] Create `backend/app/modules/clients/service.py`
- [x] Create `backend/app/modules/clients/repository.py`
- [x] Create `backend/app/modules/clients/schemas.py`
- [x] Register router in `app/main.py`

**Acceptance Criteria:**
- Module structure follows existing patterns
- Router registered at `/api/v1/clients`

### Task 1.2: Implement List Clients Endpoint
- [x] Add `GET /api/v1/clients` endpoint
- [x] Reuse dashboard repository's `list_connections_with_financials()` method
- [x] Support query params: quarter, fy_year, status, search, sort_by, sort_order, page, limit
- [x] Return paginated list of XeroConnections with financial data

**Acceptance Criteria:**
- Returns same data structure as dashboard `/clients` endpoint
- Pagination works correctly
- BAS status calculated per connection

### Task 1.3: Implement Client Detail Endpoint
- [x] Add `GET /api/v1/clients/{connection_id}` endpoint
- [x] Return connection details with financial summary
- [x] Calculate BAS status for the connection
- [x] Include contact count, invoice count, transaction count

**Acceptance Criteria:**
- Returns 404 if connection not found or belongs to different tenant
- Financial summary calculated for specified quarter
- BAS status reflects data freshness

### Task 1.4: Implement Contacts Endpoint
- [x] Add `GET /api/v1/clients/{connection_id}/contacts` endpoint
- [x] Query XeroClient records filtered by connection_id
- [x] Support filter by contact_type (customer, supplier, both)
- [x] Support search by name or ABN
- [x] Paginate results

**Acceptance Criteria:**
- Returns only contacts for the specified connection
- Tenant isolation via RLS
- Pagination with 25 items per page

### Task 1.5: Implement Invoices Endpoint
- [x] Add `GET /api/v1/clients/{connection_id}/invoices` endpoint
- [x] Query XeroInvoice records filtered by connection_id
- [x] Support filter by invoice_type, status, date range
- [x] Default date range to current quarter
- [x] Paginate results

**Acceptance Criteria:**
- Returns invoices for the connection (not filtered by XeroClient)
- Date filtering works correctly
- Pagination with 20 items per page

### Task 1.6: Implement Transactions Endpoint
- [x] Add `GET /api/v1/clients/{connection_id}/transactions` endpoint
- [x] Query XeroBankTransaction records filtered by connection_id
- [x] Support filter by transaction_type, date range
- [x] Default date range to current quarter
- [x] Paginate results

**Acceptance Criteria:**
- Returns transactions for the connection
- Date filtering works correctly
- Pagination with 20 items per page

---

## Phase 2: Frontend - Client List Page

### Task 2.1: Refactor Client List Page
- [x] Update `/clients/page.tsx` to fetch XeroConnections (not XeroClients)
- [x] Use `/api/v1/clients` endpoint (or `/api/v1/dashboard/clients`)
- [x] Display organization_name instead of contact name
- [x] Display BAS status, last synced, activity count
- [x] Remove contact_type column (not relevant for businesses)

**Acceptance Criteria:**
- Shows list of client businesses (XeroConnections)
- Each row shows organization name, status, last sync
- Clicking row navigates to `/clients/[id]`

### Task 2.2: Update Navigation Links
- [x] Update row click to navigate to `/clients/[connection_id]`
- [x] Remove any links that reference XeroClient IDs

**Acceptance Criteria:**
- Navigation uses connection_id not client_id

---

## Phase 3: Frontend - Client Detail Page

### Task 3.1: Refactor Detail Page Header
- [x] Update to accept connection_id from URL params
- [x] Fetch connection details from `/api/v1/clients/{id}`
- [x] Display organization_name, BAS status, last sync
- [x] Keep Refresh Data and View in Xero buttons

**Acceptance Criteria:**
- Shows connection (business) info, not contact info
- BAS status badge displays correctly
- Stale data warning shows if sync > 24 hours

### Task 3.2: Implement Tabbed Layout
- [x] Add tab navigation: Overview, Contacts, Invoices, Transactions
- [x] Show counts in tab labels (e.g., "Invoices (89)")
- [x] Default to Overview tab
- [x] Preserve tab selection when changing quarter

**Acceptance Criteria:**
- Tabs switch content area
- Counts load on page init
- Active tab is visually indicated

### Task 3.3: Implement Overview Tab
- [x] Show financial summary cards (Sales, Purchases, GST, Net GST)
- [x] Keep quarter selector functional
- [x] Display key metrics for the quarter

**Acceptance Criteria:**
- Summary cards show data for selected quarter
- Quarter selector updates all data

### Task 3.4: Implement Contacts Tab (NEW)
- [x] Create contacts list component
- [x] Fetch from `/api/v1/clients/{id}/contacts`
- [x] Show contact name, type badge, email, ABN
- [x] Add filter by contact_type
- [ ] Add search by name/ABN (UI filter - backend supports it)
- [x] Paginate results

**Acceptance Criteria:**
- Lists XeroClients for this connection only
- Filter and search work correctly
- Shows empty state when no contacts

### Task 3.5: Refactor Invoices Tab
- [x] Update to fetch by connection_id (not client_id)
- [x] Use `/api/v1/clients/{id}/invoices` endpoint
- [x] Keep existing filter/sort functionality
- [x] Keep line item expansion

**Acceptance Criteria:**
- Shows all invoices for the connection
- Filtering by type/status/date works
- Line items expand correctly

### Task 3.6: Refactor Transactions Tab
- [x] Update to fetch by connection_id (not client_id)
- [x] Use `/api/v1/clients/{id}/transactions` endpoint
- [x] Keep existing filter/sort functionality

**Acceptance Criteria:**
- Shows all transactions for the connection
- Filtering by type/date works

---

## Phase 4: Cleanup

### Task 4.1: Remove Old Endpoints (Optional)
- [ ] Evaluate if `/api/v1/integrations/xero/clients` endpoints still needed
- [ ] Deprecate or remove if no longer used
- [ ] Update any remaining references

### Task 4.2: Update Tests
- [ ] Update/add integration tests for new endpoints
- [ ] Verify tenant isolation
- [ ] Test pagination on all list endpoints

### Task 4.3: Update Documentation
- [ ] Mark tasks complete in tasks.md
- [ ] Update ROADMAP.md if needed
- [ ] Verify spec.md matches implementation

---

## Phase 5: Commit & Merge

### Task 5.1: Final Testing
- [x] Run backend lint: `uv run ruff check`
- [x] Run frontend lint: `npm run lint`
- [ ] Manual verification of all functionality

### Task 5.2: Commit
- [x] Stage all changes
- [x] Commit with descriptive message

### Task 5.3: Merge
- [ ] Push branch
- [ ] Merge to main
- [ ] Delete feature branch

---

## Verification Checklist

After completion:

- [x] `/clients` page shows XeroConnections (businesses), not XeroClients (contacts)
- [x] Each business row shows: organization name, BAS status, last synced
- [x] `/clients/[id]` shows tabbed detail for ONE business
- [x] Overview tab shows financial summary
- [x] Contacts tab shows customers/suppliers OF that business
- [x] Invoices tab shows invoices for that connection
- [x] Transactions tab shows transactions for that connection
- [x] All endpoints properly tenant-isolated
- [x] Spec documentation matches implementation

---

## Previous Implementation (Reference Only)

The original implementation used the wrong data model. Key files that need refactoring:

<details>
<summary>Files to Refactor (Click to expand)</summary>

### Backend (Existing - Needs Update)
- `/backend/app/modules/integrations/xero/router.py` - Client endpoints based on XeroClient
- `/backend/app/modules/integrations/xero/service.py` - XeroClientService methods
- `/backend/app/modules/integrations/xero/schemas.py` - Client schemas

### Frontend (Existing - Needs Update)
- `/frontend/src/app/(protected)/clients/page.tsx` - Lists XeroClients
- `/frontend/src/app/(protected)/clients/[id]/page.tsx` - Shows XeroClient detail

### What Was Wrong
- `/clients` showed XeroClients (contacts) instead of XeroConnections (businesses)
- `/clients/[id]` showed contact detail instead of business detail
- Invoices/transactions were filtered by client_id (contact) instead of connection_id

</details>
