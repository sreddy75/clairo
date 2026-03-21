# Requirements Document: Multi-Client Dashboard

## Introduction

This document defines the requirements for the Multi-Client Dashboard feature in Clairo. Building upon the completed Single Client View (Spec 005), this feature provides accountants with a centralized dashboard to view all client businesses across all Xero connections, assess BAS readiness at a glance, and efficiently prioritize their BAS preparation workload.

The Multi-Client Dashboard completes Milestone M2 (Multi-Client View) and delivers the core value proposition of Clairo: helping accountants manage BAS preparation across their entire client portfolio efficiently.

**Key Context:**
- Single Client View is complete (Spec 005) - individual client financial data accessible
- Xero Data Sync is complete (Spec 004) - all client data is synced and available
- Data exists in: XeroClient, XeroInvoice, XeroBankTransaction, XeroAccount, XeroConnection tables
- Quarter utility functions available for BAS period calculations
- Multi-tenant architecture with RLS enforced

---

## Data Model Clarification (CRITICAL)

### Client = XeroConnection = One Business = One BAS

In Clairo, the term **"Client"** refers to a **client business entity**, which is represented by a **XeroConnection**. Each XeroConnection represents one Xero organization that belongs to a business owner who is a client of the accounting practice.

```
Accounting Practice (Clairo Tenant)
    │
    ├── Client Business A  ←── XeroConnection: "ABC Pty Ltd"
    │   └── Their invoices, bank transactions, contacts → BAS #1
    │
    ├── Client Business B  ←── XeroConnection: "XYZ Trading"
    │   └── Their invoices, bank transactions, contacts → BAS #2
    │
    └── Client Business C  ←── XeroConnection: "123 Services"
        └── Their invoices, bank transactions, contacts → BAS #3
```

**Important Distinctions:**

| Term | What It Represents | BAS Relevance |
|------|-------------------|---------------|
| **XeroConnection** | A client business (Xero organization) | ONE BAS to lodge per connection |
| **XeroClient** | Contacts within a Xero org (customers/suppliers of the business) | NOT a BAS entity - just transaction counterparties |

**The dashboard shows:**
- One row per **XeroConnection** (each client business)
- Aggregated sales/purchases/GST for that entire business
- BAS status for that business's BAS lodgement

**NOT:**
- Individual contacts within a Xero organization

---

## Requirements

### Requirement 1: Dashboard Overview

**User Story:** As an accountant, I want to see a high-level summary of all my client businesses' BAS status, so that I can quickly understand my overall workload.

#### Acceptance Criteria

1. WHEN a user navigates to the dashboard THEN the system SHALL display summary cards showing:
   - Total number of client businesses (XeroConnections)
   - Number of clients with activity this quarter
   - Total GST position (Net GST across all clients)
   - Number of clients requiring attention (data quality issues or incomplete data)

2. WHEN displaying the dashboard THEN the system SHALL:
   - Default to the current BAS quarter
   - Show data aggregated from all active Xero connections
   - Update in real-time when quarter selection changes

3. WHEN displaying amounts THEN the system SHALL format as Australian currency ($ with comma separators).

---

### Requirement 2: Client Portfolio Table

**User Story:** As an accountant, I want to see all my client businesses in a sortable, filterable table, so that I can quickly find and prioritize clients for BAS preparation.

#### Acceptance Criteria

1. WHEN viewing the dashboard THEN the system SHALL display a client portfolio table with columns:
   - Organization name (linked to client detail/drill-down view)
   - Total Sales (current quarter) - sum of all ACCREC invoices
   - Total Purchases (current quarter) - sum of all ACCPAY invoices
   - GST Collected (current quarter)
   - GST Paid (current quarter)
   - Net GST (current quarter) - GST Collected minus GST Paid
   - Activity count (number of invoices + transactions)
   - BAS Status indicator (Ready, Needs Review, No Activity, Missing Data)
   - Last synced timestamp

2. WHEN viewing the client table THEN the system SHALL support:
   - Sorting by any column (default: organization name A-Z)
   - Search by organization name
   - Filter by BAS status

3. WHEN a client row is clicked THEN the system SHALL navigate to a detailed view for that business.

4. WHEN displaying the table THEN the system SHALL:
   - Show 25 rows per page by default
   - Support page size selection (10, 25, 50, 100)
   - Display total count and current page info

5. WHEN a client has no activity for the selected quarter THEN the system SHALL:
   - Display $0.00 for all financial columns
   - Show "No Activity" status indicator
   - Visually de-emphasize the row (muted colors)

---

### Requirement 3: BAS Status Indicators

**User Story:** As an accountant, I want to see visual indicators of each client business's BAS readiness, so that I can prioritize clients who need attention.

#### Acceptance Criteria

1. WHEN calculating BAS status for a client business THEN the system SHALL categorize as:
   - **Ready** (green): Has activity (invoices OR transactions), data synced within 24 hours
   - **Needs Review** (yellow): Has activity but data is stale (>24 hours since sync)
   - **No Activity** (gray): No invoices AND no transactions for the quarter
   - **Missing Data** (red): Has invoices but no bank transactions, or vice versa

2. FOR each BAS status THEN the system SHALL display:
   - Color-coded badge/indicator
   - Tooltip explaining the status
   - Icon in addition to color (accessibility)

3. WHEN filtering by BAS status THEN the system SHALL:
   - Support multi-select filtering (e.g., show Ready AND Needs Review)
   - Update table and summary cards to reflect filtered data
   - Show count of clients in each status category

---

### Requirement 4: Quarter Navigation

**User Story:** As an accountant, I want to switch between BAS quarters, so that I can review historical data or prepare for upcoming periods.

#### Acceptance Criteria

1. WHEN viewing the dashboard THEN the system SHALL display a BAS quarter selector prominently.

2. WHEN the quarter selector is displayed THEN the system SHALL:
   - Default to the current quarter
   - Show 4 previous quarters
   - Show the next quarter if within 1 month of quarter end
   - Display quarters in "Q# FY##" format (e.g., "Q2 FY25")

3. WHEN a user selects a different quarter THEN the system SHALL:
   - Update all summary cards for the new quarter
   - Update all client financial data in the table
   - Recalculate all BAS status indicators
   - Preserve search and filter selections
   - Update URL to include quarter parameter (for sharing/bookmarking)

4. WHEN displaying quarter boundaries THEN the system SHALL show:
   - Quarter start date
   - Quarter end date
   - Days remaining (for current/future quarters)

---

### Requirement 5: Quick Actions

**User Story:** As an accountant, I want quick access to common actions, so that I can efficiently manage my client portfolio.

#### Acceptance Criteria

1. WHEN viewing the dashboard THEN the system SHALL display quick action buttons:
   - Refresh (re-fetch dashboard data)
   - Export to CSV (export current view data)

2. WHEN a user clicks "Export to CSV" THEN the system SHALL:
   - Export current filtered/sorted view
   - Include all visible columns
   - Name file with quarter (e.g., "bas-clients-q2-fy25.csv")

---

### Requirement 6: Dashboard API Endpoints

**User Story:** As a frontend developer, I need API endpoints to fetch aggregated dashboard data, so that the UI can display it efficiently.

#### Acceptance Criteria

1. WHEN the frontend requests dashboard summary THEN the API SHALL provide:
   ```
   GET /api/v1/dashboard/summary
   Query params: quarter, fy_year
   Response: {
     total_clients: number,        // Count of XeroConnections
     active_clients: number,       // Connections with activity
     total_sales: decimal,         // Sum of all ACCREC invoices
     total_purchases: decimal,     // Sum of all ACCPAY invoices
     gst_collected: decimal,
     gst_paid: decimal,
     net_gst: decimal,
     status_counts: {
       ready: number,
       needs_review: number,
       no_activity: number,
       missing_data: number
     },
     quarter_label: string,        // e.g., "Q2 FY25"
     quarter: number,
     fy_year: number,
     last_sync_at: datetime
   }
   ```

2. WHEN the frontend requests client portfolio list THEN the API SHALL provide:
   ```
   GET /api/v1/dashboard/clients
   Query params: quarter, fy_year, status, search, sort_by, sort_order, page, limit
   Response: {
     clients: [{
       id: uuid,                   // XeroConnection ID
       organization_name: string,
       total_sales: decimal,
       total_purchases: decimal,
       gst_collected: decimal,
       gst_paid: decimal,
       net_gst: decimal,
       invoice_count: number,
       transaction_count: number,
       activity_count: number,
       bas_status: string,
       last_synced_at: datetime
     }],
     total: number,
     page: number,
     limit: number
   }
   ```

3. ALL dashboard API endpoints SHALL:
   - Require authentication
   - Enforce tenant isolation via RLS
   - Use efficient aggregate queries (no N+1)
   - Log audit events for data access

---

### Requirement 7: Real-time Updates

**User Story:** As an accountant, I want the dashboard to reflect the latest data, so that I'm always working with current information.

#### Acceptance Criteria

1. WHEN viewing the dashboard THEN the system SHALL:
   - Show "Last updated: X minutes ago" indicator
   - Provide manual refresh button
   - Auto-refresh every 5 minutes while tab is active

2. WHEN data is stale (>1 hour since refresh) THEN the system SHALL:
   - Display a prominent warning
   - Suggest refreshing data
   - Show when last sync occurred

---

### Requirement 8: Responsive Design

**User Story:** As an accountant, I want to access the dashboard on different devices, so that I can monitor my clients flexibly.

#### Acceptance Criteria

1. WHEN viewing on desktop (>1024px) THEN the system SHALL display:
   - Summary cards in a horizontal row
   - Full client table with all columns
   - All quick actions visible

2. WHEN viewing on tablet (768px-1024px) THEN the system SHALL:
   - Stack summary cards in 2x2 grid
   - Show condensed table columns (name, net GST, status)
   - Quick actions in dropdown menu

3. WHEN viewing on mobile (<768px) THEN the system SHALL:
   - Stack summary cards vertically
   - Show card-based client list instead of table
   - Floating action button for quick actions

---

### Requirement 9: Empty States and Loading

**User Story:** As a user, I want clear feedback about data availability, so that I understand the current state.

#### Acceptance Criteria

1. WHEN dashboard data is loading THEN the system SHALL display skeleton loaders matching the layout.

2. WHEN no Xero connections exist THEN the system SHALL display:
   - "No connections" empty state
   - Call-to-action to connect Xero
   - Brief explanation of the feature

3. WHEN no activity exists for the selected quarter THEN the system SHALL display:
   - "No activity" message for the quarter
   - Suggestion to check previous quarters
   - Option to view all quarters

4. WHEN an API error occurs THEN the system SHALL:
   - Display user-friendly error message
   - Provide retry option
   - Log error for debugging

---

## Non-Functional Requirements

### Performance

1. Dashboard page SHALL load within 800ms (P95) for up to 100 client businesses.

2. Summary calculations SHALL use efficient aggregate queries.

3. API responses SHALL be gzip compressed.

### Security

1. ALL endpoints SHALL validate that the requesting user's tenant owns the connections.

2. Dashboard data access SHALL generate audit events for compliance.

3. Export functionality SHALL log audit events including export format and row count.

### Accessibility

1. ALL interactive elements SHALL be keyboard navigable.

2. Data tables SHALL use proper ARIA table roles and headers.

3. Status indicators SHALL have both color and icon/text alternatives.

4. Financial amounts SHALL use proper ARIA attributes for screen readers.

---

## Out of Scope

The following items are explicitly out of scope for this specification:

1. **Data quality scoring** - Quality metrics and issues (Spec 007)
2. **BAS calculation** - Actual BAS form generation (Spec 008)
3. **Client creation/editing** - All client data comes from Xero sync
4. **Bulk BAS operations** - Preparing multiple BAS simultaneously
5. **Team collaboration** - Assigning clients to team members
6. **Custom dashboard layouts** - User-defined widget arrangement
7. **Alerts/notifications** - Automated alerts for status changes (future spec)
8. **Drill-down to individual contacts** - XeroClients within a business (not relevant to BAS overview)

---

## Dependencies

| Dependency | Description | Status |
|------------|-------------|--------|
| Spec 005: Single Client View | Individual client data views | COMPLETE |
| Spec 004: Xero Data Sync | Synced client, invoice, transaction data | COMPLETE |
| XeroConnection model | Connection metadata, sync timestamps | Available |
| XeroInvoice model | Invoice data storage | Available |
| XeroBankTransaction model | Transaction data storage | Available |
| Quarter utility functions | BAS period calculations | Available |

---

## BAS Status Definitions (Per Client Business/Connection)

| Status | Criteria | Visual |
|--------|----------|--------|
| **Ready** | Has activity (invoices OR transactions), data synced within 24h | Green badge, checkmark icon |
| **Needs Review** | Has activity, but sync is stale (>24h) | Yellow badge, clock icon |
| **No Activity** | No invoices AND no transactions for quarter | Gray badge, minus icon |
| **Missing Data** | Has invoices but no transactions, or vice versa | Red badge, warning icon |

---

## User Interface Mockup (Text-based)

```
+------------------------------------------------------------------+
|  BAS Dashboard                        Q2 FY25 v  [Refresh] [Export]
+------------------------------------------------------------------+
|                                                                    |
|  +------------+  +------------+  +------------+  +------------+   |
|  | 5 Clients  |  | 4 Active   |  | $45,500    |  | 1 Needs    |   |
|  | Total      |  | This Qtr   |  | Net GST    |  | Review     |   |
|  +------------+  +------------+  +------------+  +------------+   |
|                                                                    |
|  Search: [_______________]  Status: [All v]                        |
|                                                                    |
|  +----------------------------------------------------------------+
|  | Organization     | Sales    | Purchases | GST Net | Activity |Status|
|  +----------------------------------------------------------------+
|  | ABC Pty Ltd      | $125,000 | $80,000   | $4,500  | 47       |Ready |
|  | XYZ Trading      | $89,000  | $45,000   | $4,400  | 32       |Ready |
|  | 123 Services     | $67,000  | $52,000   | $1,500  | 28       |Review|
|  | Smith & Co       | $0       | $0        | $0      | 0        |NoAct |
|  | Demo Company     | $45,000  | $0        | $4,500  | 15       |Missing|
|  +----------------------------------------------------------------+
|  Showing 1-5 of 5 clients             < 1 >     Per page: [25 v]   |
+------------------------------------------------------------------+
```

---

## Glossary

| Term | Definition |
|------|------------|
| **BAS** | Business Activity Statement |
| **Client** | A client business entity, represented by one XeroConnection |
| **Net GST** | GST Collected minus GST Paid (positive = owe ATO) |
| **Active Client** | Client with at least one invoice or transaction in quarter |
| **BAS Status** | Readiness indicator for BAS preparation |
| **XeroConnection** | A linked Xero organization representing one client business |
| **XeroClient** | Contacts (customers/suppliers) within a Xero organization - NOT a BAS entity |
| **Portfolio** | All client businesses across all connections for a tenant |
