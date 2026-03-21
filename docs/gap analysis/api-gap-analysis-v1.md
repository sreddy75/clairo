# Clairo API Gap Analysis v1.0

**Document Version:** 1.0
**Date:** December 2025
**Status:** Initial Analysis
**Author:** Analysis Agent

---

## Executive Summary

This document provides a comprehensive gap analysis comparing Clairo's intended features against the available Xero APIs (Practice Manager API v3.1 and Accounting API v2.0). The analysis reveals that while the APIs provide solid foundational capabilities for client management and basic financial reporting, there are **critical gaps** in data quality assessment, compliance analytics, and direct ATO integration that will require alternative approaches.

**Overall Viability Assessment:** The platform is **viable with workarounds**. Core features can be delivered, but the unique differentiators (Data Quality Engine, Compliance Analytics) will require significant internal computation rather than relying on API-provided data.

---

## 1. Feature-by-Feature Analysis

### 1.1 Multi-Client Dashboard

**Purpose:** Provide a portfolio-wide view of all clients with BAS period status, deadline tracking, and bulk operations.

#### Required Data

| Data Element | Description |
|--------------|-------------|
| Client list | All clients in the practice |
| Client details | ABN, GST registration, contact info |
| BAS job status | Current status of each client's BAS job |
| Deadline dates | Due dates for BAS lodgement |
| Staff assignments | Who is working on each client |

#### Available API Endpoints

| Endpoint | Source | Data Provided |
|----------|--------|---------------|
| `client.api/list` | Practice Manager | Full client list with UUID, Name, Email, Phone, Address, TaxNumber, GSTRegistered, GSTPeriod |
| `client.api/get/[uuid]` | Practice Manager | Detailed client information including ABN, ACN, GST settings |
| `job.api/list` | Practice Manager | All jobs with State, DueDate, ClientUUID |
| `job.api/current` | Practice Manager | Active jobs in progress |
| `job.api/client/[uuid]` | Practice Manager | All jobs for a specific client |
| `job.api/staff/[uuid]` | Practice Manager | Jobs assigned to specific staff |
| `staff.api/list` | Practice Manager | Staff member list |

#### Gap Status: **Full Access**

#### Gap Description
No significant gaps. The Practice Manager API provides comprehensive client and job data needed for the multi-client dashboard.

#### Available Fields
- `ClientDetails.UUID`, `Name`, `Email`, `Phone`, `TaxNumber` (ABN)
- `ClientDetails.GSTRegistered`, `GSTPeriod`, `PrepareGST`
- `JobDetails.State`, `DueDate`, `StartDate`, `CompletedDate`
- `JobDetails.ManagerUUID`, `PartnerUUID`

#### Impact Level: **Low**

#### Notes
- Jobs can be filtered by Type to identify BAS-specific jobs
- DueDate field enables deadline tracking
- State field (Planned, In Progress, Completed) provides status tracking

---

### 1.2 Data Quality Engine (Core Differentiator)

**Purpose:** Proactively assess BAS readiness by detecting data quality issues before BAS preparation begins.

#### Required Data

| Data Element | Description |
|--------------|-------------|
| Unreconciled bank transactions | Transactions not matched to bank feed |
| GST coding on all transactions | Tax type applied to each transaction |
| Expected vs actual GST amounts | Validation of GST calculations |
| PAYG withholding data | Employee tax withholding |
| Superannuation contributions | SG compliance data |
| Transaction completeness | Missing fields, descriptions |
| Duplicate detection | Potential duplicate entries |

#### Available API Endpoints

| Endpoint | Source | Data Provided |
|----------|--------|---------------|
| `/BankTransactions` | Accounting | Bank transactions with IsReconciled field |
| `/Invoices` | Accounting | Sales invoices with line item tax types |
| `/Invoices?where=Type=="ACCPAY"` | Accounting | Bills/purchases with tax types |
| `/TaxRates` | Accounting | Available tax rates for validation |
| `/Accounts?where=Type=="BANK"` | Accounting | Bank account list |
| `/Reports/BankSummary` | Accounting | Bank reconciliation summary |

#### Gap Status: **Partial Access**

#### Gap Description

| Data Element | Status | Details |
|--------------|--------|---------|
| Unreconciled bank transactions | **Available** | `IsReconciled` field on BankTransactions |
| GST coding anomalies | **Available** | Can compare `TaxType` on line items against expected rates |
| GST amount validation | **Available** | Can calculate expected tax and compare to `TaxAmount` |
| PAYG withholding | **Not Available** | No Payroll API access for PAYG data |
| Superannuation data | **Not Available** | No Payroll API access for super contributions |
| Missing transaction data | **Partially Available** | Can check for empty fields but no data completeness score from API |
| Duplicate detection | **Not Available** | No built-in duplicate detection; must implement client-side |

#### Critical Gaps

1. **PAYG Withholding Data**
   - **Gap:** Xero Payroll API is separate from Accounting API and requires additional OAuth scopes
   - **Impact:** Cannot validate PAYG amounts for BAS Label W1/W2
   - **Severity:** HIGH - PAYG is a core BAS component

2. **Superannuation Contributions**
   - **Gap:** Super data is in Payroll API, not Accounting API
   - **Impact:** Cannot verify SG compliance for data quality scoring
   - **Severity:** MEDIUM - Not directly on BAS but affects compliance

3. **No "BAS Readiness Score" from API**
   - **Gap:** Must calculate all quality scores internally
   - **Impact:** Requires significant processing logic
   - **Severity:** LOW - Expected; this is our differentiator

#### Impact Level: **High**

#### Notes
- Bank reconciliation status IS available via `IsReconciled` field
- GST validation is possible by querying transactions and comparing tax amounts
- All quality scoring must be computed internally based on raw transaction data
- Payroll data requires separate Xero Payroll API integration (additional OAuth scopes: `payroll.employees`, `payroll.payruns`, `payroll.settings`)

---

### 1.3 Automated Variance Analysis

**Purpose:** Compare current period BAS data against prior periods to detect significant variances.

#### Required Data

| Data Element | Description |
|--------------|-------------|
| Current period BAS figures | GST collected, GST paid, net GST |
| Prior period BAS figures | Historical comparison data |
| P&L by period | Revenue/expense variance |
| Industry benchmarks | (Future) Comparative data |

#### Available API Endpoints

| Endpoint | Source | Data Provided |
|----------|--------|---------------|
| `/Reports/ProfitAndLoss` | Accounting | P&L with date range parameters |
| `/Reports` | Accounting | List of published reports including BAS |
| `/Reports/{ReportID}` | Accounting | Specific report data |
| `/Reports/TrialBalance` | Accounting | Trial balance for period |
| `/Reports/BalanceSheet` | Accounting | Balance sheet |

#### Gap Status: **Partial Access**

#### Gap Description

| Data Element | Status | Details |
|--------------|--------|---------|
| BAS report data | **Limited** | BAS reports only available if "published" in Xero |
| P&L by period | **Available** | Date range parameters supported |
| Prior period comparison | **Manual** | Must make separate API calls for each period |
| Variance calculation | **Not Available** | No built-in variance analysis; must compute internally |

#### Critical Gaps

1. **BAS Report Access**
   - **Gap:** BAS reports must be "published" in Xero to appear in `/Reports` endpoint
   - **Impact:** Draft BAS data may not be accessible
   - **Workaround:** Calculate BAS figures from underlying transaction data

2. **No Native Period Comparison**
   - **Gap:** API doesn't provide period-over-period comparison
   - **Impact:** Must fetch multiple periods and calculate variance internally
   - **Severity:** LOW - Expected behaviour

#### Impact Level: **Medium**

#### Notes
- P&L reports accept `fromDate` and `toDate` parameters for period specification
- Multiple API calls needed for historical comparison (watch rate limits)
- BAS figures can be reconstructed from transaction data if reports unavailable

---

### 1.4 BAS Preparation Workflow

**Purpose:** Track BAS jobs through preparation stages with task management and approvals.

#### Required Data

| Data Element | Description |
|--------------|-------------|
| Job status/state | Current workflow stage |
| Task list | BAS preparation checklist |
| Task completion | Track completed steps |
| Approval workflow | Sign-off process |
| Document attachments | BAS worksheets, supporting docs |
| Audit trail | Change history |

#### Available API Endpoints

| Endpoint | Source | Data Provided |
|----------|--------|---------------|
| `job.api/list`, `job.api/get` | Practice Manager | Job details with State |
| `job.api/state` | Practice Manager | Change job state |
| `job.api/tasks` | Practice Manager | Task list for job |
| `job.api/task` (POST/PUT) | Practice Manager | Create/update tasks |
| `job.api/task/[uuid]/complete` | Practice Manager | Mark task complete |
| `job.api/task/[uuid]/reopen` | Practice Manager | Reopen task |
| `job.api/note` | Practice Manager | Add notes to job |
| `job.api/documents/[job number]` | Practice Manager | Get job documents |
| `job.api/document` (POST) | Practice Manager | Attach documents |
| `job.api/applytemplate` | Practice Manager | Apply job template |

#### Gap Status: **Partial Access**

#### Gap Description

| Data Element | Status | Details |
|--------------|--------|---------|
| Job state tracking | **Available** | State field: Planned, In Progress, Completed |
| Task management | **Available** | Full CRUD on tasks |
| Task completion tracking | **Available** | Complete/reopen endpoints |
| Document management | **Available** | Attach/retrieve documents |
| Approval workflow | **Limited** | No native approval/sign-off workflow |
| Audit trail | **Not Available** | No change history in API |
| Custom workflow states | **Limited** | Pre-defined states only |

#### Critical Gaps

1. **No Native Approval Workflow**
   - **Gap:** No built-in approval/rejection mechanism
   - **Impact:** Must build approval logic in Clairo
   - **Workaround:** Use custom fields or job notes to track approvals

2. **Limited Workflow States**
   - **Gap:** Only Planned, In Progress, Completed states
   - **Impact:** Cannot track granular BAS stages (e.g., "Review", "Pending Approval", "Ready to Lodge")
   - **Workaround:** Use tasks to represent workflow stages

3. **No Audit Trail**
   - **Gap:** API doesn't expose change history
   - **Impact:** Must maintain audit log in Clairo
   - **Severity:** MEDIUM - Required for compliance

#### Impact Level: **Medium**

#### Notes
- Custom fields API (`customfield.api`) can store Clairo-specific workflow data
- Job notes can be used for comments and basic approval tracking
- Consider maintaining parallel workflow state in Clairo database

---

### 1.5 Compliance Analytics

**Purpose:** Portfolio-wide compliance health dashboard with risk scoring and recommended actions.

#### Required Data

| Data Element | Description |
|--------------|-------------|
| Lodgement history | Past BAS lodgement dates |
| Due date compliance | On-time vs late |
| Penalty exposure | Outstanding penalties |
| ATO audit indicators | Risk factors |
| Historical data quality | Trend analysis |

#### Available API Endpoints

| Endpoint | Source | Data Provided |
|----------|--------|---------------|
| `job.api/client/[uuid]` | Practice Manager | Historical jobs for client |
| `job.api/list` | Practice Manager | All jobs with DueDate, CompletedDate |
| None | - | ATO data not available |

#### Gap Status: **No Access**

#### Gap Description

| Data Element | Status | Details |
|--------------|--------|---------|
| Lodgement history | **Inferred** | Can track completed BAS jobs, not actual ATO lodgement |
| Due date compliance | **Available** | Compare DueDate to CompletedDate |
| Penalty exposure | **Not Available** | No ATO data in Xero API |
| ATO audit probability | **Not Available** | No ATO data; must calculate from internal models |
| ATO notices | **Not Available** | ATO correspondence not in API |

#### Critical Gaps

1. **No ATO Integration**
   - **Gap:** Xero API does not provide ATO lodgement status or penalty data
   - **Impact:** Cannot show actual lodgement confirmation or penalty amounts
   - **Severity:** HIGH - Core feature limitation

2. **Audit Probability Cannot Be Calculated from API Data**
   - **Gap:** No access to ATO risk factors
   - **Impact:** Must use heuristic models based on data patterns
   - **Workaround:** Build internal risk scoring based on data quality, industry, and turnover

#### Impact Level: **Critical**

#### Notes
- Compliance scoring must be entirely internally modelled
- Consider integration with ATO directly (Phase 3) for real data
- Can calculate basic risk scores from:
  - Historical late lodgements (DueDate vs CompletedDate)
  - Data quality trends (internal scoring)
  - Industry and revenue patterns (from Organisation data)

---

### 1.6 Client Communication

**Purpose:** Automated deadline reminders, data requests, and status updates.

#### Required Data

| Data Element | Description |
|--------------|-------------|
| Client contact info | Email, phone, address |
| Multiple contacts | Primary, secondary contacts |
| Communication history | Past messages |
| Communication preferences | Preferred contact method |

#### Available API Endpoints

| Endpoint | Source | Data Provided |
|----------|--------|---------------|
| `client.api/contacts` | Practice Manager | All contacts for client |
| `client.api/contact/[uuid]` | Practice Manager | Specific contact details |
| `client.api/contact` (POST) | Practice Manager | Add new contact |
| `job.api/note` | Practice Manager | Add notes (not client-visible) |

#### Gap Status: **Partial Access**

#### Gap Description

| Data Element | Status | Details |
|--------------|--------|---------|
| Contact information | **Available** | Email, Phone, Address for contacts |
| Multiple contacts | **Available** | Full contact list per client |
| Communication history | **Not Available** | No email/message history in API |
| Communication preferences | **Not Available** | No preference settings |
| Send communications | **Not Available** | Cannot send emails via API |

#### Critical Gaps

1. **No Communication History**
   - **Gap:** API doesn't track sent communications
   - **Impact:** Must maintain communication log in Clairo
   - **Severity:** MEDIUM

2. **No Email Sending Capability**
   - **Gap:** API is read/write for data, not for actions like sending emails
   - **Impact:** Must integrate with email service (SendGrid, etc.)
   - **Severity:** MEDIUM - Expected

#### Impact Level: **Medium**

#### Notes
- Contact data is fully available for external communication
- Clairo must maintain its own communication history
- Integration with email service provider required for actual sending

---

### 1.7 Direct ATO Integration (Phase 3)

**Purpose:** DSP certification for direct BAS lodgement and ATO notice ingestion.

#### Required Data

| Data Element | Description |
|--------------|-------------|
| DSP certification | Digital Service Provider status |
| SBR channel access | Standard Business Reporting |
| ATO API access | Direct lodgement capability |
| ATO notice data | Ingest ATO correspondence |

#### Available API Endpoints

**None available from Xero** - This is direct ATO integration, not Xero.

#### Gap Status: **No Access**

#### Gap Description

| Data Element | Status | Details |
|--------------|--------|---------|
| DSP certification | **Not Xero** | Must apply directly to ATO |
| SBR implementation | **Not Xero** | Separate protocol/API |
| Direct lodgement | **Not Xero** | ATO Business Portal API |
| ATO notices | **Not Xero** | ATO API for notices |

#### Critical Gaps

1. **Entirely Separate Integration**
   - **Gap:** ATO integration is completely independent of Xero
   - **Impact:** Requires DSP certification process (6-12 months)
   - **Severity:** HIGH for Phase 3

#### DSP Certification Requirements

1. **Application Process**
   - Apply via ATO Developer Portal
   - Demonstrate compliance with ATO security standards
   - Pass security assessment

2. **Technical Requirements**
   - Implement SBR (Standard Business Reporting) protocol
   - Message Authentication Codes (MAC)
   - AUSkey / myGovID authentication
   - Conformance testing

3. **Ongoing Obligations**
   - Annual security attestation
   - Maintain technical compliance
   - Report data breaches

#### Impact Level: **Critical** (for Phase 3)

#### Notes
- LodgeiT is a Tier 1 DSP - could explore partnership
- DSP certification is a significant undertaking
- Consider Phase 3 timeline of 18-24 months for DSP status
- Alternative: Integrate with existing DSP (LodgeiT, GovReports) as lodgement layer

---

## 2. Critical Gaps Summary

| Gap | Feature Affected | Severity | Blocker? |
|-----|------------------|----------|----------|
| **No Payroll API in standard scope** | Data Quality Engine | Critical | Partial - PAYG/super validation blocked |
| **No ATO integration** | Compliance Analytics | Critical | Yes - for penalty/audit data |
| **BAS reports must be published** | Variance Analysis | High | No - can calculate from transactions |
| **No native approval workflow** | BAS Workflow | Medium | No - build in Clairo |
| **No audit trail from API** | BAS Workflow | Medium | No - maintain internally |
| **No communication history** | Client Communication | Medium | No - maintain internally |
| **DSP certification required** | ATO Integration | Critical | Yes - for Phase 3 |

---

## 3. Data Not Available via API

### Completely Unavailable

| Data Type | Reason | Impact |
|-----------|--------|--------|
| **PAYG withholding amounts** | Payroll API separate, additional scopes needed | Cannot validate W1/W2 labels |
| **Superannuation contributions** | Payroll API separate | Cannot verify SG compliance |
| **ATO lodgement confirmation** | ATO system, not Xero | Cannot confirm actual lodgement |
| **ATO penalties/interest** | ATO system | Cannot show actual penalty exposure |
| **ATO audit status** | ATO system | Cannot show audit flags |
| **ATO correspondence** | ATO system | Cannot ingest notices |
| **Historical lodgement dates** | ATO system | Only job completion dates available |
| **Change/audit history** | Not exposed in API | Must track internally |
| **Email communication logs** | Not in Xero | Must integrate email service |

### Requires Additional API Access

| Data Type | API Required | OAuth Scopes Needed |
|-----------|--------------|---------------------|
| Payroll data | Xero Payroll AU API | `payroll.employees`, `payroll.payruns`, `payroll.settings` |
| Leave balances | Xero Payroll AU API | `payroll.employees.read` |
| Employee tax declarations | Xero Payroll AU API | `payroll.employees.read` |

---

## 4. Workaround Proposals

### 4.1 PAYG/Super Data Gap

**Problem:** Cannot access payroll data for PAYG withholding and super validation.

**Workarounds:**

1. **Add Xero Payroll API Integration**
   - Request additional OAuth scopes for Payroll API
   - Estimated effort: 2-3 weeks development
   - Consideration: Not all Xero users have Payroll enabled

2. **Manual Import Option**
   - Allow accountants to upload PAYG summary from payroll system
   - Parse and validate against BAS figures
   - Lower tech effort but adds user friction

3. **Skip Payroll Validation Initially**
   - Focus on GST and transaction quality
   - Add payroll validation in Phase 2
   - Clearly communicate limitation to users

**Recommendation:** Option 1 (Payroll API) for firms using Xero Payroll; Option 2 as fallback for others.

### 4.2 ATO Compliance Data Gap

**Problem:** No access to actual ATO lodgement status, penalties, or audit data.

**Workarounds:**

1. **Build Predictive Risk Models**
   - Use internal data quality scores
   - Track historical on-time completion
   - Industry risk profiling
   - Create "estimated risk score" based on heuristics

2. **Partner with Existing DSP**
   - Integrate with LodgeiT or similar for lodgement
   - May provide lodgement confirmation data
   - Reduces Phase 3 scope

3. **Manual Status Tracking**
   - Accountants manually update ATO status in Clairo
   - Less automated but accurate
   - Audit trail maintained

**Recommendation:** Option 1 for MVP (risk modelling), Option 2 for Phase 3 (DSP partnership).

### 4.3 Approval Workflow Gap

**Problem:** No native approval mechanism in Practice Manager API.

**Workarounds:**

1. **Custom Fields for Status**
   - Use `customfield.api` to store approval status
   - Values: "Pending", "Approved", "Rejected"
   - Store approver and timestamp

2. **Internal Workflow Engine**
   - Build full workflow in Clairo
   - Sync status to Xero job notes for visibility
   - More flexible but adds complexity

3. **Task-Based Workflow**
   - Create approval as a task
   - "Approval" task completion = approved
   - Leverages existing API

**Recommendation:** Option 3 (task-based) for MVP simplicity, Option 2 for full platform.

### 4.4 Audit Trail Gap

**Problem:** No change history available from API.

**Workarounds:**

1. **Event Sourcing in Clairo**
   - Log all changes made through Clairo
   - Immutable event log
   - Cannot capture changes made directly in Xero

2. **Periodic Snapshot Comparison**
   - Store snapshots of data at intervals
   - Compare to detect changes
   - Resource intensive but comprehensive

**Recommendation:** Option 1 (event sourcing) for Clairo-originated changes; accept that direct Xero changes won't be tracked.

### 4.5 BAS Report Data Gap

**Problem:** BAS reports only available if published; may be incomplete or missing.

**Workarounds:**

1. **Calculate BAS from Transactions**
   - Query all transactions for period
   - Sum by tax type to calculate GST
   - Cross-reference with BAS labels

2. **Use Transaction Summary Reports**
   - `/Reports/TrialBalance` for account balances
   - `/Reports/ProfitAndLoss` for revenue/expense
   - Reconstruct BAS figures

**Recommendation:** Option 1 - calculate from source transactions for accuracy and completeness.

---

## 5. Risk Assessment

### Overall Viability: **Viable with Significant Internal Development**

The Xero APIs provide foundational data access but the key differentiators of Clairo (Data Quality Engine, Compliance Analytics) must be built as internal computation engines rather than relying on pre-calculated API data.

### Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Payroll data inaccessible** | Medium | High | Add Payroll API integration; manual import fallback |
| **BAS reports incomplete** | Medium | Medium | Calculate from transactions instead |
| **Rate limiting impacts real-time scoring** | Medium | Medium | Aggressive caching; background sync |
| **ATO integration timeline** | High | High | Partner with existing DSP; defer to Phase 3 |
| **API changes by Xero** | Low | High | Abstract data layer; version monitoring |
| **Complex OAuth management** | Medium | Medium | Use battle-tested OAuth libraries |

### Development Effort Impact

| Feature | Original Estimate | Revised Estimate | Reason |
|---------|-------------------|------------------|--------|
| Data Quality Engine | Medium | High | All scoring logic internal |
| Variance Analysis | Low | Medium | Multi-call, internal calculation |
| Compliance Analytics | Medium | High | Entirely modelled internally |
| BAS Workflow | Low | Medium | Custom workflow engine |
| Client Communication | Low | Medium | External email integration |
| ATO Integration | High | Critical | DSP certification path |

### Go/No-Go Assessment

| Criterion | Assessment |
|-----------|------------|
| Core value proposition deliverable? | **Yes** - Data Quality Engine is computable |
| Unique differentiator viable? | **Yes** - Internal models provide differentiation |
| Technical feasibility confirmed? | **Yes** - APIs sufficient for source data |
| Development timeline realistic? | **Needs Review** - More internal logic than anticipated |
| Phase 3 (ATO) feasibility? | **Uncertain** - DSP certification is major undertaking |

### Recommendations

1. **Proceed with MVP Development**
   - Multi-Client Dashboard: Fully supported
   - Data Quality Engine: Build internal scoring (defer payroll to Phase 1b)
   - BAS Workflow: Task-based workflow initially

2. **Add Xero Payroll API in Phase 1b**
   - Required for complete PAYG/super validation
   - Adds 2-3 weeks to integration timeline

3. **Evaluate DSP Partnership for Phase 3**
   - Direct DSP certification is 12-18 months
   - Partnership with LodgeiT could accelerate
   - Reduces risk and development effort

4. **Build Robust Caching Layer**
   - Rate limits (60/min, 5000/day) require smart caching
   - Background sync for data freshness
   - User-initiated refresh for immediate needs

5. **Accept Audit Trail Limitations**
   - Track Clairo-originated changes
   - Communicate that direct Xero changes not tracked
   - Consider this in compliance messaging

---

## Appendix A: API Endpoint Reference

### Practice Manager API v3.1

| Category | Endpoints Used | Gap Status |
|----------|----------------|------------|
| Clients | `client.api/list`, `get`, `contacts` | Full |
| Jobs | `job.api/list`, `current`, `state`, `tasks` | Full |
| Staff | `staff.api/list`, `get` | Full |
| Time | `time.api/list`, `job/[id]` | Full |
| Custom Fields | `customfield.api/*` | Full |
| Documents | `client.api/documents`, `job.api/documents` | Full |

### Accounting API v2.0

| Category | Endpoints Used | Gap Status |
|----------|----------------|------------|
| Reports | `/Reports`, `/Reports/ProfitAndLoss` | Partial (BAS must be published) |
| Bank Transactions | `/BankTransactions` | Full |
| Invoices | `/Invoices` | Full |
| Tax Rates | `/TaxRates` | Full |
| Organisation | `/Organisation` | Full |
| Accounts | `/Accounts` | Full |

### Not Available

| API | Status |
|-----|--------|
| Xero Payroll AU API | Separate OAuth scopes required |
| ATO SBR/API | Not Xero; direct ATO integration |

---

## Appendix B: OAuth Scope Requirements

### Current Assumed Scopes

```
offline_access
openid
profile
email
accounting.transactions
accounting.transactions.read
accounting.reports.read
accounting.settings
accounting.settings.read
accounting.contacts
accounting.contacts.read
```

### Additional Scopes for Full Feature Set

```
payroll.employees
payroll.employees.read
payroll.payruns
payroll.payruns.read
payroll.settings
payroll.settings.read
```

### Practice Manager Scopes

```
practice_manager
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | December 2025 | Analysis Agent | Initial gap analysis |

---

*This analysis is based on Xero API documentation as of December 2024 and the Clairo feature requirements defined in overview.md and solution-design.md.*
