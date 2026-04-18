# Xero API Mapping for Clairo

This document maps the Xero Practice Manager API and Xero Accounting API endpoints relevant to the Clairo platform.

---

## API Overview

Clairo will integrate with **two Xero APIs**:

1. **Xero Practice Manager API (v3.1)** - For firm-level operations (clients, jobs, staff, time tracking)
2. **Xero Accounting API** - For financial data (BAS reports, GST, transactions, bank reconciliation)

### Authentication

| Parameter | Details |
|-----------|---------|
| Auth Method | OAuth 2.0 (required for all new integrations) |
| Access Token Expiry | 30 minutes |
| Refresh Token Expiry | 60 days (rotating - single use) |
| Alternative | Custom Connection (client credentials grant) for premium apps |

### Rate Limits

| Limit Type | Value |
|------------|-------|
| API calls per minute | 60 |
| API calls per day (per org/app) | 5,000 |
| Concurrent requests per tenant | 5 |
| Rate limit error code | 429 (Too Many Requests) |

**Note:** Rate limits apply per connection. Each connected Xero organisation has its own limit pool.

---

## Practice Manager API Endpoints (v3.1)

### Clients API (`client.api`)

**Relevance to Clairo:** Core for multi-client dashboard, client health scoring, portfolio management.

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `client.api/list` | GET | List all clients with parameters | Load client portfolio for dashboard |
| `client.api/search` | GET | Search clients | Client search/filtering |
| `client.api/get/[uuid]` | GET | Get specific client details | Client detail view, data quality context |
| `client.api/add` | POST | Add new client | Future: onboard new clients |
| `client.api/update` | PUT | Update client | Update client metadata |
| `client.api/archive` | PUT | Archive client | Client offboarding workflow |
| `client.api/contacts` | GET | Get client contacts | Client communication automation |
| `client.api/contact/[uuid]` | GET | Get specific contact | Contact details for notifications |
| `client.api/contact` | POST | Add contact | Add new contact |
| `client.api/contact/[uuid]` | PUT | Update contact | Update contact details |
| `client.api/contact/[uuid]` | DELETE | Delete contact | Remove contact |
| `client.api/documents/[uuid]` | GET | Get client documents | Document management |
| `client.api/document` | POST | Add document | Store BAS worksheets |

**Key Client Fields:**
- `UUID`, `Name`, `Email`, `Phone`, `Address`
- `TaxNumber`, `BusinessNumber`, `CompanyNumber`
- `AccountManagerUUID`, `JobManagerUUID`
- `GSTRegistered`, `GSTPeriod`, `PrepareGST`, `PrepareTaxReturn`
- `BillingClientUUID`

---

### Jobs API (`job.api`)

**Relevance to Clairo:** BAS preparation workflow, job status tracking, deadline management.

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `job.api/list` | GET | List all jobs | BAS pipeline view |
| `job.api/current` | GET | Get current/active jobs | Dashboard - jobs in progress |
| `job.api/get/[job number]` | GET | Get specific job | Job detail view |
| `job.api/client/[uuid]` | GET | Get jobs by client | Client's BAS history |
| `job.api/staff/[uuid]` | GET | Get jobs by staff member | Team workload view |
| `job.api/add` | POST | Create new job | Create BAS job for period |
| `job.api/update` | PUT | Update job | Update BAS job status |
| `job.api/state` | PUT | Change job state | Update BAS workflow state |
| `job.api/delete` | POST | Delete job | Remove cancelled BAS job |
| `job.api/assign` | PUT | Assign staff to job | Team assignment |
| `job.api/applytemplate` | POST | Apply job template | Apply BAS job template |
| `job.api/tasks` | GET | Get job tasks | BAS preparation checklist |
| `job.api/task` | POST | Add task to job | Add BAS prep task |
| `job.api/task` | PUT | Update task | Update task status |
| `job.api/task/[uuid]/complete` | PUT | Mark task complete | Complete BAS step |
| `job.api/task/[uuid]/reopen` | PUT | Reopen task | Reopen for revisions |
| `job.api/reordertasks` | PUT | Reorder tasks | Customize workflow order |
| `job.api/note` | POST | Add note to job | Add BAS notes/comments |
| `job.api/documents/[job number]` | GET | Get job documents | BAS documentation |
| `job.api/document` | POST | Add document | Attach BAS worksheets |
| `job.api/costs/[job number]` | GET | Get job costs | Billing tracking |
| `job.api/cost` | POST | Add cost | Add cost entry |
| `job.api/cost` | PUT | Update cost | Update cost |

**Key Job Fields:**
- `UUID`, `ID`, `Name`, `Description`
- `StartDate`, `DueDate`, `CompletedDate`
- `State` (e.g., Planned, In Progress, Completed)
- `Type` (e.g., BAS, Tax Return)
- `ClientUUID`, `ManagerUUID`, `PartnerUUID`
- `Budget`

---

### Staff API (`staff.api`)

**Relevance to Clairo:** Team management, workload distribution, assignments.

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `staff.api/list` | GET | List all staff | Team dashboard |
| `staff.api/get/[uuid]` | GET | Get staff member | Staff profile |
| `staff.api/add` | POST | Add staff member | Onboard team member |
| `staff.api/update` | PUT | Update staff | Update staff details |
| `staff.api/delete` | POST | Delete staff | Remove staff |
| `staff.api/enable` | POST | Enable staff | Activate staff account |
| `staff.api/disable` | POST | Disable staff | Deactivate staff |

**Key Staff Fields:**
- `UUID`, `Name`, `Email`, `Phone`, `Mobile`
- `Address`, `PayrollCode`

---

### Time API (`time.api`)

**Relevance to Clairo:** Track time spent on BAS preparation, efficiency metrics.

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `time.api/list` | GET | List time entries | Time tracking reports |
| `time.api/get/[uuid]` | GET | Get time entry | Entry details |
| `time.api/job/[job number]` | GET | Time entries for job | BAS job time tracking |
| `time.api/staff/[uuid]` | GET | Time entries for staff | Staff productivity |
| `time.api/add` | POST | Add time entry | Log BAS work time |
| `time.api/update` | PUT | Update time entry | Correct time entries |
| `time.api/delete/[uuid]` | DELETE | Delete time entry | Remove entry |

**Key Time Fields:**
- `UUID`, `ID`, `JobID`, `StaffMemberUUID`, `TaskUUID`
- `Date`, `Minutes`, `Note`
- `Billable`, `Start`, `End`

---

### Tasks API (`task.api`)

**Relevance to Clairo:** Task templates, workflow standardization.

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `task.api/list` | GET | List all task templates | BAS workflow templates |
| `task.api/get/[uuid]` | GET | Get task template | Template details |

**Key Task Fields:**
- `UUID`, `Name`, `Description`

---

### Invoices API (`invoice.api`)

**Relevance to Clairo:** Billing for BAS services, revenue tracking.

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `invoice.api/list` | GET | List invoices | Revenue reporting |
| `invoice.api/current` | GET | Current invoices | Outstanding invoices |
| `invoice.api/draft` | GET | Draft invoices | Pending billing |
| `invoice.api/get/[invoice number]` | GET | Get invoice | Invoice details |
| `invoice.api/job/[job number]` | GET | Invoices for job | BAS job billing |
| `invoice.api/payments/[invoice number]` | GET | Invoice payments | Payment tracking |

**Key Invoice Fields:**
- `UUID`, `ID`, `Type`, `Status`
- `Date`, `DueDate`
- `Amount`, `AmountTax`, `AmountIncludingTax`
- `AmountOutstanding`, `AmountPaid`
- `ClientUUID`, `ContactUUID`

---

### Quotes API (`quote.api`)

**Relevance to Clairo:** BAS service quoting (future feature).

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `quote.api/list` | GET | List quotes | Proposal tracking |
| `quote.api/current` | GET | Current quotes | Active proposals |
| `quote.api/draft` | GET | Draft quotes | Draft proposals |
| `quote.api/get/[quote number]` | GET | Get quote | Quote details |

---

### Custom Fields API (`customfield.api`)

**Relevance to Clairo:** Store Clairo-specific data in XPM (data quality scores, etc.).

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `customfield.api/definition` | GET | Get custom field definitions | Discover available fields |
| `customfield.api/get/[uuid]` | GET | Get custom field value | Read Clairo scores |
| `customfield.api/customfield` | GET | Get custom field | Field details |
| `customfield.api/customfield` | PUT | Set custom field value | Store data quality scores |
| `customfield.api/add` | POST | Add custom field definition | Create Clairo fields |
| `customfield.api/update` | PUT | Update definition | Modify field schema |
| `customfield.api/delete` | POST | Delete definition | Remove field |

---

### Categories API (`category.api`)

**Relevance to Clairo:** Categorize jobs/tasks for reporting.

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `category.api/list` | GET | List categories | Job/task categorization |

---

### Client Groups API (`clientgroup.api`)

**Relevance to Clairo:** Group clients for batch operations.

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `clientgroup.api/list` | GET | List client groups | Portfolio segmentation |
| `clientgroup.api/get/[uuid]` | GET | Get group details | Group management |

---

## Xero Accounting API Endpoints

### Reports API

**Relevance to Clairo:** Core for BAS data, GST reports, financial analysis.

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `/Reports` | GET | List published reports | Discover BAS/GST reports |
| `/Reports/{ReportID}` | GET | Get specific report | Retrieve BAS report data |
| `/Reports/TrialBalance` | GET | Trial Balance | Financial health check |
| `/Reports/ProfitAndLoss` | GET | P&L Report | Variance analysis |
| `/Reports/BalanceSheet` | GET | Balance Sheet | Financial position |
| `/Reports/BankSummary` | GET | Bank Summary | Reconciliation status |
| `/Reports/AgedPayables` | GET | Aged Payables | Outstanding bills |
| `/Reports/AgedReceivables` | GET | Aged Receivables | Outstanding invoices |

**BAS Report Access:**
1. Call `GET /Reports` to list published reports
2. Find BAS report in response by type
3. Use `ReportID` to retrieve full report data

---

### Tax Rates API

**Relevance to Clairo:** GST coding validation, tax rate verification.

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `/TaxRates` | GET | List tax rates | GST code validation |
| `/TaxRates` | POST | Create tax rate | Future: custom rates |
| `/TaxRates` | PUT | Update tax rate | Future: rate updates |

**Australian Tax Types:**
- INPUT, OUTPUT (Standard GST)
- INPUTTAXED, EXEMPTOUTPUT (GST-free)
- CAPEXINPUT, CAPEXOUTPUT (Capital)
- GSTONIMPORTS (Imported goods)

---

### Bank Transactions API

**Relevance to Clairo:** Reconciliation status, data quality scoring.

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `/BankTransactions` | GET | List transactions | Reconciliation analysis |
| `/BankTransactions/{ID}` | GET | Get transaction | Transaction details |

---

### Invoices API (Accounting)

**Relevance to Clairo:** Sales data, GST on sales.

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `/Invoices` | GET | List invoices | Sales analysis |
| `/Invoices/{ID}` | GET | Get invoice | Invoice details |

---

### Bills (Accounts Payable)

**Relevance to Clairo:** Purchase data, GST on purchases.

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `/Invoices?where=Type=="ACCPAY"` | GET | List bills | Purchase analysis |

---

### Bank Accounts

**Relevance to Clairo:** Bank feed status, reconciliation tracking.

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `/Accounts?where=Type=="BANK"` | GET | List bank accounts | Bank account status |

---

### Organisation

**Relevance to Clairo:** Client org settings, GST registration status.

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `/Organisation` | GET | Get org details | GST registration, BAS period settings |

---

### Fixed Assets API (Spec 025)

**Relevance to Clairo:** Fixed asset management, depreciation tracking, instant write-off detection.

**Required OAuth Scope:** `assets` (in addition to standard `accounting.*` scopes)

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `/Assets` | GET | List all assets | Fixed assets register |
| `/Assets/{AssetId}` | GET | Get specific asset | Asset detail view |
| `/AssetTypes` | GET | List asset types | Categorization, depreciation settings |

**Key Asset Fields:**
- `assetId`, `assetName`, `assetNumber`
- `purchaseDate`, `purchasePrice`, `disposalDate`, `disposalPrice`
- `bookValue`, `accountingBookValue`
- `assetStatus` (Draft, Registered, Disposed)
- `depreciationMethod` (StraightLine, DiminishingValue)
- `depreciationRate`, `effectiveLifeYears`
- `warrantyExpiryDate`

---

### Purchase Orders API (Spec 025)

**Relevance to Clairo:** Cash flow forecasting, outstanding commitments.

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `/PurchaseOrders` | GET | List purchase orders | Outstanding POs for cash flow |
| `/PurchaseOrders/{PurchaseOrderID}` | GET | Get specific PO | PO detail view |

**Key PurchaseOrder Fields:**
- `purchaseOrderID`, `purchaseOrderNumber`
- `contact`, `date`, `deliveryDate`, `expectedArrivalDate`
- `status` (Draft, Submitted, Authorised, Billed, Deleted)
- `subtotal`, `totalTax`, `total`
- `currencyCode`, `lineItems`

---

### Repeating Invoices API (Spec 025)

**Relevance to Clairo:** Recurring revenue/expense forecasting.

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `/RepeatingInvoices` | GET | List repeating invoices | Recurring revenue/expense analysis |
| `/RepeatingInvoices/{RepeatingInvoiceID}` | GET | Get specific template | Template detail |

**Key RepeatingInvoice Fields:**
- `repeatingInvoiceID`, `type` (ACCPAY, ACCREC)
- `contact`, `status` (Draft, Authorised, Deleted)
- `schedule` (unit, numberOfUnits, dueDate, startDate, endDate, nextScheduledDate)
- `subtotal`, `totalTax`, `total`
- `lineItems`

---

### Tracking Categories API (Spec 025)

**Relevance to Clairo:** Project/department profitability analysis.

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `/TrackingCategories` | GET | List tracking categories | Department/project breakdown |
| `/TrackingCategories/{TrackingCategoryID}` | GET | Get specific category | Category detail with options |

**Key TrackingCategory Fields:**
- `trackingCategoryID`, `name`, `status`
- `options` (array of tracking options)

---

### Quotes API (Spec 025)

**Relevance to Clairo:** Revenue pipeline analysis, quote conversion tracking.

| Endpoint | Method | Description | Clairo Use Case |
|----------|--------|-------------|------------------|
| `/Quotes` | GET | List quotes | Revenue pipeline view |
| `/Quotes/{QuoteID}` | GET | Get specific quote | Quote detail |

**Key Quote Fields:**
- `quoteID`, `quoteNumber`, `reference`
- `contact`, `date`, `expiryDate`
- `status` (Draft, Sent, Accepted, Declined, Invoiced)
- `subtotal`, `totalTax`, `total`
- `lineItems`, `terms`

---

## Data Model Summary

### Client Entity (from Practice Manager)

```
ClientDetails {
  UUID: string
  Name: string
  FirstName: string
  LastName: string
  Email: string
  Phone: string
  Address: string
  City: string
  Region: string
  PostCode: string
  Country: string
  TaxNumber: string         // ABN
  CompanyNumber: string     // ACN
  BusinessNumber: string
  AccountManagerUUID: string
  JobManagerUUID: string
  BillingClientUUID: string
  GSTRegistered: boolean
  GSTPeriod: string         // Monthly, Quarterly
  PrepareGST: boolean
  PrepareTaxReturn: boolean
  BankBSB: string
  BankAccountNumber: string
}
```

### Job Entity (from Practice Manager)

```
JobDetails {
  UUID: string
  ID: string
  Name: string              // e.g., "BAS Q2 2025"
  Description: string
  DateCreatedUtc: datetime
  StartDate: date
  DueDate: date             // BAS deadline
  CompletedDate: date
  Budget: decimal
  State: string             // Planned, In Progress, Completed
  Type: string              // BAS, Tax Return, etc.
  ClientUUID: string
  ManagerUUID: string
  PartnerUUID: string
}
```

### Time Entry (from Practice Manager)

```
Time {
  UUID: string
  ID: string
  JobID: string
  StaffMemberUUID: string
  TaskUUID: string
  Date: date
  Minutes: integer
  Note: string
  Billable: boolean
  Start: datetime
  End: datetime
}
```

---

## Clairo Feature to API Mapping

| Clairo Feature | Primary API | Key Endpoints |
|-----------------|-------------|---------------|
| **Multi-Client Dashboard** | Practice Manager | `client.api/list`, `job.api/list`, `job.api/current` |
| **Client Data Quality Scoring** | Accounting | `/BankTransactions`, `/Invoices`, `/Reports` |
| **BAS Pipeline View** | Practice Manager | `job.api/list`, `job.api/client/[uuid]` |
| **Deadline Tracking** | Practice Manager | `job.api/list` (filter by DueDate) |
| **Team Workload** | Practice Manager | `job.api/staff/[uuid]`, `time.api/staff/[uuid]` |
| **Variance Analysis** | Accounting | `/Reports/ProfitAndLoss`, `/Reports` (BAS) |
| **GST Validation** | Accounting | `/TaxRates`, `/Invoices`, `/BankTransactions` |
| **Reconciliation Status** | Accounting | `/BankTransactions`, `/Accounts` |
| **Time Tracking** | Practice Manager | `time.api/*` |
| **Client Communication** | Practice Manager | `client.api/contacts`, `job.api/note` |
| **Document Management** | Practice Manager | `client.api/documents`, `job.api/documents` |
| **Billing/Invoicing** | Practice Manager | `invoice.api/*` |
| **Fixed Assets Register** | Accounting | `/Assets`, `/AssetTypes` |
| **Instant Write-Off Detection** | Accounting | `/Assets` (filter by purchasePrice) |
| **Depreciation Analysis** | Accounting | `/Assets` (depreciationMethod, bookValue) |
| **Purchase Orders** | Accounting | `/PurchaseOrders` |
| **Repeating Invoices** | Accounting | `/RepeatingInvoices` |
| **Tracking Categories** | Accounting | `/TrackingCategories` |
| **Quote Pipeline** | Accounting | `/Quotes` |

---

## Implementation Considerations

### API Version Strategy
- Use **Practice Manager API v3.1** (uses UUIDs, more consistent)
- Use **Accounting API v2.0** (latest stable)

### Rate Limit Management
1. Implement request queuing
2. Use exponential backoff on 429 errors
3. Respect `Retry-After` header
4. Cache frequently accessed data (clients, staff)
5. Use pagination for large datasets

### Data Sync Strategy
1. **Initial Sync**: Full data pull on first connection
2. **Incremental Sync**: Use `ModifiedAfter` parameter where available
3. **Polling Interval**: Every 15-30 minutes for active data
4. **Webhooks**: Check if Xero offers webhooks for real-time updates

### Error Handling
- Handle OAuth token refresh (30-min expiry)
- Implement retry logic for transient failures
- Log all API interactions for debugging
- Handle rate limit gracefully with user feedback

---

## Sources

- [Xero Practice Manager API Overview](https://developer.xero.com/documentation/api/practice-manager/overview-practice-manager)
- [Practice Manager 3.1 Jobs](https://developer.xero.com/documentation/api/practice-manager-3-1/jobs)
- [Practice Manager 3.1 Tasks](https://developer.xero.com/documentation/api/practice-manager-3-1/tasks)
- [Practice Manager Clients](https://developer.xero.com/documentation/api/practice-manager/clients)
- [Practice Manager Staff](https://developer.xero.com/documentation/api/practice-manager/staff)
- [Practice Manager Time](https://developer.xero.com/documentation/api/practice-manager-3-1/time)
- [Practice Manager Invoices](https://developer.xero.com/documentation/api/practice-manager-3-1/invoices)
- [Practice Manager Custom Fields](https://developer.xero.com/documentation/api/practice-manager-3-1/custom-fields)
- [Xero OAuth 2.0 Limits](https://developer.xero.com/documentation/guides/oauth2/limits/)
- [Xero Accounting API Reports](https://developer.xero.com/documentation/api/accounting/reports)
- [Xero Accounting API Tax Rates](https://developer.xero.com/documentation/api/accounting/taxrates)
- [SyncHub XPM Data Model](https://www.synchub.io/connectors/xeropracticemanager/datamodel)
- [Xero OpenAPI Repository](https://github.com/XeroAPI/Xero-OpenAPI)

---

## Tax Planning — On-Demand Payroll Sync (Spec 059)

Tax plan creation triggers an on-demand payroll sync so `credits.payg_withholding`
and `payroll_summary.total_super_ytd` reflect the most recent Xero pay runs.
Implementation notes:

- `TaxPlanningService.pull_xero_financials` wraps
  `XeroPayrollService.sync_payroll(connection_id)` in
  `asyncio.wait_for(..., timeout=15.0)`.
- On successful sync: `payroll_status="ready"`, summary is populated from
  DB-persisted `XeroPayRun` / `XeroEmployee`, and `credits.payg_withholding`
  is wired from `payroll_summary.total_tax_withheld_ytd` (FR-007).
- On timeout: plan is returned with `payroll_sync_status="pending"`; the
  Celery task `app.tasks.xero.sync_xero_payroll` is enqueued and, on
  completion, calls `recompute_tax_position` for any tax plan created
  against the same connection in the last 2 hours.
- When `XeroConnection.has_payroll_access` is False: `payroll_sync_status=
  "unavailable"` — the UI renders an actionable "reconnect with payroll
  scope" banner rather than silently falling back to $0.

See `specs/059-tax-planning-calculation-correctness/spec.md` §US3 for the
rationale and user-facing behaviour.

---

*Document created: December 2024*
*Last updated: April 2026 (Spec 059 — tax planning calculation correctness)*
