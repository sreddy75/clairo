# Requirements Document: Client Business View

## Introduction

This document defines the requirements for the Client Business View feature in Clairo. Building upon the completed Xero Data Sync (Spec 004), this feature enables accountants to view comprehensive financial data for their client businesses, including invoices, bank transactions, contacts, and BAS-relevant financial summaries.

**Key Context:**
- Xero Data Sync is complete (Spec 004) - connections, contacts, invoices, bank transactions, and accounts are synced
- Multi-tenant architecture with RLS enforced
- All data queries scoped by tenant_id automatically

---

## CRITICAL: Data Model Clarification

### Client = XeroConnection = One Business = One BAS

In Clairo, "client" refers to a **client business** (XeroConnection), NOT a contact within that business.

| Term | What It Represents | BAS Relevance |
|------|-------------------|---------------|
| **XeroConnection** | A client business (Xero organization) the accountant manages | ONE BAS to lodge per connection |
| **XeroClient** | Contacts (customers/suppliers) WITHIN a client business | NOT a BAS entity - these are the client's customers/suppliers |

### Example

```
Accounting Practice (Clairo Tenant)
└── XeroConnection: "ABC Pty Ltd" (CLIENT BUSINESS - ONE BAS)
    ├── XeroClient: "John Smith" (Customer OF ABC Pty Ltd)
    ├── XeroClient: "Office Supplies Co" (Supplier OF ABC Pty Ltd)
    ├── XeroInvoice: Sales invoice to John Smith
    └── XeroBankTransaction: Payment from John Smith

└── XeroConnection: "XYZ Trading" (CLIENT BUSINESS - ANOTHER BAS)
    ├── XeroClient: "Jane Doe" (Customer OF XYZ Trading)
    └── ...
```

### UX Hierarchy

```
/clients              → List of CLIENT BUSINESSES (XeroConnections)
/clients/[id]         → Detail page for ONE client business
    ├── Overview tab  → BAS status, sync status, key metrics
    ├── Contacts tab  → Customers/suppliers OF this business (XeroClients)
    ├── Invoices tab  → Sales & purchase invoices
    └── Transactions tab → Bank transactions
```

---

## Requirements

### Requirement 1: Client Business List View

**User Story:** As an accountant, I want to see a list of all my client businesses, so that I can select one to view their details.

#### Acceptance Criteria

1. WHEN a user navigates to the clients page THEN the system SHALL display a list of all XeroConnection records for the tenant.

2. FOR each client business in the list THEN the system SHALL display:
   - Organization name (from Xero)
   - Connection status (active/inactive)
   - BAS status indicator (ready, needs review, no activity, missing data)
   - Last synced timestamp (from connection's last_full_sync_at)
   - Activity count (invoices + transactions for current quarter)

3. WHEN viewing the client list THEN the system SHALL support:
   - Sorting by organization name (default: A-Z)
   - Sorting by BAS status
   - Filtering by BAS status
   - Search by organization name

4. WHEN a client list has more than 25 clients THEN the system SHALL paginate results with 25 items per page.

5. WHEN a user clicks on a client business row THEN the system SHALL navigate to the client detail view.

---

### Requirement 2: Client Business Detail Header

**User Story:** As an accountant, I want to see a client business's key information at a glance, so that I can quickly understand the business and its BAS status.

#### Acceptance Criteria

1. WHEN viewing a client detail page THEN the system SHALL display a header section containing:
   - Organization name (prominent display)
   - BAS status badge (Ready, Needs Review, No Activity, Missing Data)
   - Connection status badge (Active/Inactive)
   - Last synced timestamp
   - Xero tenant ID (for reference)

2. WHEN client data is stale (last sync > 24 hours ago) THEN the system SHALL display a visual indicator warning.

3. WHEN viewing the client header THEN the system SHALL display quick action buttons:
   - Refresh Data (trigger sync for this connection)
   - View in Xero (external link to Xero organization)

---

### Requirement 3: Client Business Overview Tab

**User Story:** As an accountant, I want to see a financial overview for a client business, so that I can quickly assess their BAS readiness.

#### Acceptance Criteria

1. WHEN viewing the Overview tab THEN the system SHALL display financial summary cards for the selected BAS quarter showing:
   - Total Sales (sum of ACCREC invoices)
   - Total Purchases (sum of ACCPAY invoices)
   - GST Collected (sum of tax_amount from ACCREC invoices)
   - GST Paid (sum of tax_amount from ACCPAY invoices)
   - Net GST Position (GST Collected - GST Paid)
   - Invoice Count
   - Transaction Count

2. WHEN calculating financial summaries THEN the system SHALL:
   - Only include invoices with status: AUTHORISED or PAID
   - Use the issue_date to determine BAS quarter membership
   - Default to the current BAS quarter (based on today's date)

3. WHEN a user selects a different quarter THEN the system SHALL recalculate all summary values for that quarter.

4. WHEN displaying amounts THEN the system SHALL format as Australian currency ($ with comma separators).

5. WHEN the net GST position is negative (refund due) THEN the system SHALL display it with appropriate visual styling.

---

### Requirement 4: Contacts Tab (Customers/Suppliers)

**User Story:** As an accountant, I want to view a client business's contacts (their customers and suppliers), so that I can understand who they transact with.

#### Acceptance Criteria

1. WHEN viewing the Contacts tab THEN the system SHALL display a list of XeroClient records for this connection.

2. FOR each contact in the list THEN the system SHALL display:
   - Contact name
   - Contact type badge (Customer, Supplier, or Both)
   - Email (if available)
   - ABN (if available)
   - Active/Inactive status indicator

3. WHEN viewing contacts THEN the system SHALL support:
   - Filtering by contact type (Customer, Supplier, Both, All)
   - Search by contact name or ABN
   - Pagination with 25 items per page

4. WHEN a user clicks on a contact row THEN the system MAY expand to show additional details (addresses, phones).

---

### Requirement 5: Invoices Tab

**User Story:** As an accountant, I want to view a client business's invoices, so that I can review their sales and purchase activity.

#### Acceptance Criteria

1. WHEN viewing the Invoices tab THEN the system SHALL display invoices for this connection.

2. FOR each invoice in the list THEN the system SHALL display:
   - Invoice number
   - Invoice type icon/badge (Sales or Purchase)
   - Contact name (the customer/supplier on the invoice)
   - Issue date
   - Due date
   - Status badge (Draft, Submitted, Authorised, Paid, Voided)
   - Subtotal amount
   - Tax amount
   - Total amount

3. WHEN viewing invoices THEN the system SHALL support:
   - Filtering by invoice type (Sales/Purchases or All)
   - Filtering by status
   - Filtering by date range (defaults to current quarter)
   - Sorting by date (default: newest first)
   - Pagination with 20 items per page

4. WHEN a user clicks on an invoice row THEN the system SHALL expand to show line item details including:
   - Description
   - Quantity
   - Unit amount
   - Account code
   - Tax type
   - Line amount

---

### Requirement 6: Bank Transactions Tab

**User Story:** As an accountant, I want to view a client business's bank transactions, so that I can review their cash flow activity.

#### Acceptance Criteria

1. WHEN viewing the Transactions tab THEN the system SHALL display bank transactions for this connection.

2. FOR each bank transaction THEN the system SHALL display:
   - Transaction date
   - Transaction type badge (Receive, Spend, etc.)
   - Contact name (if linked)
   - Reference (if available)
   - Status
   - Total amount (styled as positive/negative based on type)
   - Tax amount

3. WHEN viewing bank transactions THEN the system SHALL support:
   - Filtering by transaction type (Receive/Spend or All)
   - Filtering by date range (defaults to current quarter)
   - Sorting by date (default: newest first)
   - Pagination with 20 items per page

4. WHEN a client business has no bank transactions THEN the system SHALL display an informative empty state.

---

### Requirement 7: BAS Quarter Selector

**User Story:** As an accountant, I want to select different BAS quarters, so that I can review historical data or prepare for upcoming periods.

#### Acceptance Criteria

1. WHEN viewing client financial data THEN the system SHALL display a BAS quarter selector.

2. WHEN selecting a BAS quarter THEN the system SHALL use Australian financial year quarters:
   - Q1: July - September
   - Q2: October - December
   - Q3: January - March
   - Q4: April - June

3. WHEN the quarter selector is displayed THEN the system SHALL:
   - Default to the current quarter
   - Show at least 4 previous quarters
   - Show the next quarter if within 1 month of quarter end

4. WHEN a user selects a different quarter THEN the system SHALL:
   - Update all financial summary cards
   - Filter invoices and transactions to that quarter
   - Preserve the selection when navigating between tabs

5. WHEN displaying a quarter THEN the system SHALL format as "Q# FY##" (e.g., "Q2 FY25" for Oct-Dec 2024).

---

### Requirement 8: API Endpoints

**User Story:** As a frontend developer, I need API endpoints to fetch client business data, so that the UI can display it.

#### Acceptance Criteria

1. WHEN the frontend requests client business list THEN the API SHALL provide:
   ```
   GET /api/v1/clients
   Query params: page, limit, search, status, sort_by, sort_order
   Response: { clients: [...], total, page, limit }
   ```

2. WHEN the frontend requests client business details THEN the API SHALL provide:
   ```
   GET /api/v1/clients/{connection_id}
   Response: { client: {...}, summary: {...} }
   ```

3. WHEN the frontend requests client contacts THEN the API SHALL provide:
   ```
   GET /api/v1/clients/{connection_id}/contacts
   Query params: page, limit, contact_type, search
   Response: { contacts: [...], total, page, limit }
   ```

4. WHEN the frontend requests client invoices THEN the API SHALL provide:
   ```
   GET /api/v1/clients/{connection_id}/invoices
   Query params: page, limit, invoice_type, status, from_date, to_date, sort_by, sort_order
   Response: { invoices: [...], total, page, limit }
   ```

5. WHEN the frontend requests client bank transactions THEN the API SHALL provide:
   ```
   GET /api/v1/clients/{connection_id}/transactions
   Query params: page, limit, transaction_type, from_date, to_date, sort_by, sort_order
   Response: { transactions: [...], total, page, limit }
   ```

6. WHEN the frontend requests client financial summary THEN the API SHALL provide:
   ```
   GET /api/v1/clients/{connection_id}/summary
   Query params: quarter, fy_year (optional, defaults to current)
   Response: {
     quarter: "Q2 FY25",
     total_sales, total_purchases,
     gst_collected, gst_paid, net_gst,
     invoice_count, transaction_count
   }
   ```

7. ALL API endpoints SHALL:
   - Require authentication
   - Enforce tenant isolation via RLS
   - Return 404 if connection not found or belongs to different tenant
   - Log audit events for data access

---

### Requirement 9: Responsive Design

**User Story:** As an accountant, I want to access client data on different devices, so that I can work flexibly.

#### Acceptance Criteria

1. WHEN viewing on desktop (>1024px) THEN the system SHALL display:
   - Full client list with all columns
   - Side-by-side layout for summary cards
   - Expanded invoice/transaction tables

2. WHEN viewing on tablet (768px-1024px) THEN the system SHALL:
   - Stack summary cards in 2-column grid
   - Show condensed table columns
   - Maintain full navigation

3. WHEN viewing on mobile (<768px) THEN the system SHALL:
   - Stack all summary cards vertically
   - Show card-based list views instead of tables
   - Provide slide-out detail panels

---

### Requirement 10: Empty States and Loading

**User Story:** As a user, I want clear feedback about data availability, so that I understand the current state.

#### Acceptance Criteria

1. WHEN client data is loading THEN the system SHALL display skeleton loaders matching the content layout.

2. WHEN a client business has no contacts THEN the system SHALL display:
   - "No contacts found" message
   - Explanation that contacts are synced from Xero

3. WHEN a client business has no invoices THEN the system SHALL display:
   - "No invoices found" message
   - Suggestion to sync data if last sync is old
   - Link to Xero to add invoices

4. WHEN a client business has no bank transactions THEN the system SHALL display:
   - "No bank transactions found" message
   - Explanation that only reconciled transactions appear

5. WHEN financial summary is zero THEN the system SHALL display $0.00 (not blank).

6. WHEN an API error occurs THEN the system SHALL:
   - Display a user-friendly error message
   - Provide a retry option
   - Log the error for debugging

---

## Non-Functional Requirements

### Performance

1. Client list page SHALL load within 500ms (P95) for up to 100 client businesses.

2. Client detail page SHALL load within 300ms (P95) including summary calculations.

3. Invoice and transaction lists SHALL use cursor-based pagination for efficient loading.

4. Financial summary calculations SHALL be optimized with appropriate database indexes.

### Security

1. ALL endpoints SHALL validate that the requesting user's tenant owns the connection.

2. Client data access SHALL generate audit events for compliance.

3. External links (View in Xero) SHALL use `rel="noopener noreferrer"`.

### Accessibility

1. ALL interactive elements SHALL be keyboard navigable.

2. Color-coded indicators SHALL have non-color alternatives (icons, text).

3. Financial amounts SHALL use proper ARIA attributes for screen readers.

---

## Out of Scope

The following items are explicitly out of scope for this specification:

1. **Multi-client comparison** - Viewing multiple clients side-by-side (Dashboard handles aggregate view)
2. **Data quality scoring** - Quality indicators and issues (future spec)
3. **BAS calculation** - Actual BAS form calculation (future spec)
4. **Client creation/editing** - All client data comes from Xero sync
5. **Invoice PDF viewing** - Viewing original invoice documents
6. **Bank reconciliation** - Only viewing synced transactions, not reconciling

---

## Dependencies

| Dependency | Description | Status |
|------------|-------------|--------|
| Spec 004: Xero Data Sync | Synced connection, contact, invoice, transaction data | COMPLETE |
| Spec 006: Dashboard | Multi-client overview (uses same data model) | COMPLETE |
| XeroConnection model | Connection data storage, last_full_sync_at | Available |
| XeroClient model | Contact data storage (customers/suppliers) | Available |
| XeroInvoice model | Invoice data storage | Available |
| XeroBankTransaction model | Transaction data storage | Available |

---

## BAS Quarter Reference

For clarity, Australian BAS quarters in the financial year:

| Quarter | Months | Example FY25 |
|---------|--------|--------------|
| Q1 | Jul-Sep | Jul 2024 - Sep 2024 |
| Q2 | Oct-Dec | Oct 2024 - Dec 2024 |
| Q3 | Jan-Mar | Jan 2025 - Mar 2025 |
| Q4 | Apr-Jun | Apr 2025 - Jun 2025 |

---

## Glossary

| Term | Definition |
|------|------------|
| **Client Business** | A business the accountant manages (XeroConnection) |
| **Contact** | A customer or supplier within a client business (XeroClient) |
| **ACCREC** | Accounts Receivable - Sales invoice |
| **ACCPAY** | Accounts Payable - Purchase invoice |
| **BAS Quarter** | 3-month period for Business Activity Statement |
| **GST** | Goods and Services Tax (10% in Australia) |
| **Net GST** | GST Collected minus GST Paid |
| **FY** | Financial Year (July-June in Australia) |
