# Clairo API Gap Analysis v2.0

**Document Version:** 2.0
**Date:** December 2025
**Status:** Comprehensive Analysis (Revised)
**Author:** Analysis Agent
**Previous Version:** v1.0 (December 2025)
**Changes:** Addresses all issues (R1-R18) from Review Agent assessment

---

## Executive Summary

This document provides a comprehensive gap analysis comparing Clairo's intended features against the available Xero APIs (Practice Manager API v3.1, Accounting API v2.0, and Payroll AU API), with a preliminary assessment of MYOB API capabilities. This revision addresses all 18 issues identified in the v1.0 review, adds critical missing sections, and provides detailed analysis for all three product phases.

**Key Findings:**
- Core MVP features are viable with available APIs
- Webhooks are severely limited (Contacts/Invoices only) - requires polling strategy **[R3]**
- BAS reports require "published" status in Xero - confirmed via research **[R8]**
- MYOB integration is feasible but requires dedicated development effort **[R5]**
- Xero Practice Manager is a separate product from Xero accounting - market penetration risk exists **[R12]**
- Rate limits are manageable with proper caching but require careful planning at scale **[R7]**
- Offline capability requires significant local data caching architecture **[R4]**

**Overall Viability Assessment:** The platform is **viable with workarounds**. Core features can be delivered, but require:
1. Robust polling strategy (no webhook support for most data)
2. Local caching for offline capability
3. Internal computation for all scoring/analytics
4. Separate integration effort for MYOB

---

## Table of Contents

1. [Phase 1 Feature Analysis](#1-phase-1-feature-analysis-mvp)
2. [Phase 2 Feature Analysis](#2-phase-2-feature-analysis-intelligence)
3. [Phase 3 Feature Analysis](#3-phase-3-feature-analysis-platform)
4. [Critical Gaps Summary](#4-critical-gaps-summary)
5. [Data Not Available via API](#5-data-not-available-via-api)
6. [Workaround Proposals](#6-workaround-proposals)
7. [Webhook Analysis](#7-webhook-analysis) **[R3]**
8. [Rate Limit Calculations](#8-rate-limit-calculations) **[R7]**
9. [Multi-Tenancy Considerations](#9-multi-tenancy-considerations) **[R6]**
10. [Offline Mode Requirements](#10-offline-mode-requirements) **[R4]**
11. [Xero App Partner Certification](#11-xero-app-partner-certification) **[R9]**
12. [MYOB Integration Assessment](#12-myob-integration-assessment) **[R5]**
13. [Risk Assessment](#13-risk-assessment)
14. [Clarification Answers](#14-clarification-answers)
15. [Appendices](#appendices)

---

## 1. Phase 1 Feature Analysis (MVP)

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
| `clientgroup.api/list` | Practice Manager | Client groups for portfolio segmentation **[R16]** |

#### Gap Status: **Full Access**

#### Available Fields
- `ClientDetails.UUID`, `Name`, `Email`, `Phone`, `TaxNumber` (ABN)
- `ClientDetails.GSTRegistered`, `GSTPeriod`, `PrepareGST`
- `JobDetails.State`, `DueDate`, `StartDate`, `CompletedDate`
- `JobDetails.ManagerUUID`, `PartnerUUID`

#### Important Clarifications **[R6 partial]**

1. **Job DueDate vs ATO BAS Due Date**: The `DueDate` field in Practice Manager represents the internal job deadline set by the firm. This may differ from the actual ATO BAS lodgement deadline. Clairo must maintain a separate ATO lodgement calendar with official dates (28th of following month for monthly, 28th of second month for quarterly).

2. **Bulk Operations via Client Groups** **[R16]**: The `clientgroup.api` endpoint enables portfolio segmentation for batch operations. Clients can be grouped (e.g., "Monthly BAS", "Quarterly BAS") and operations can target entire groups.

#### Impact Level: **Low**

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
| Trend data | Recurring issues by client |

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
| PAYG withholding | **Requires Payroll API** | Separate OAuth scopes; see section 1.2.1 |
| Superannuation data | **Requires Payroll API** | Separate OAuth scopes; see section 1.2.1 |
| Missing transaction data | **Partially Available** | Can check for empty fields but no data completeness score from API |
| Duplicate detection | **Not Available** | No built-in duplicate detection; must implement client-side |
| Trend analysis (recurring issues) | **Available** | Can query historical periods and analyse patterns internally |

#### 1.2.1 Payroll API Integration **[R11 - Updated]**

**Critical Market Reality:**

The Xero Payroll API requires separate OAuth scopes and is only available to Xero subscribers who have Xero Payroll enabled. Important considerations:

| Factor | Implication |
|--------|-------------|
| **Market Segmentation** | Many Australian SMEs use external payroll systems (MYOB Payroll, KeyPay, Deputy, standalone systems) rather than Xero Payroll |
| **Xero Payroll Adoption** | Not all Xero accounting subscribers have Xero Payroll - it's a separate paid product |
| **Development Effort** | Integration requires 3-4 weeks (revised from 2-3 weeks) due to additional complexity |
| **Scope Requirement** | Requires: `payroll.employees`, `payroll.payruns`, `payroll.settings`, `payroll.timesheets` |

**Recommended Approach:**

1. **Phase 1 MVP**: Skip payroll validation; focus on GST and bank reconciliation quality
2. **Phase 1b**: Add Xero Payroll integration for clients with Xero Payroll
3. **Universal**: Provide manual PAYG import option for clients using external payroll systems
4. **Communication**: Clearly indicate in UI when payroll data is unavailable and why

#### Impact Level: **High**

---

### 1.3 Automated Variance Analysis

**Purpose:** Compare current period BAS data against prior periods to detect significant variances.

#### Required Data

| Data Element | Description |
|--------------|-------------|
| Current period BAS figures | GST collected, GST paid, net GST |
| Prior period BAS figures | Historical comparison data |
| P&L by period | Revenue/expense variance |

#### Available API Endpoints

| Endpoint | Source | Data Provided |
|----------|--------|---------------|
| `/Reports/ProfitAndLoss` | Accounting | P&L with date range parameters |
| `/Reports` | Accounting | List of published reports including BAS |
| `/Reports/{ReportID}` | Accounting | Specific report data |
| `/Reports/TrialBalance` | Accounting | Trial balance for period |
| `/Reports/BalanceSheet` | Accounting | Balance sheet |

#### Gap Status: **Partial Access**

#### BAS Report Access Clarification **[R8 - Verified]**

**Research Confirmed:** BAS/Activity Statement reports must be **published** in Xero before they appear in the `/Reports` API endpoint.

**Mechanism:**
1. User navigates to Adviser > Activity Statement in Xero
2. User clicks "Publish" button on draft report
3. Published report then appears in `GET /Reports` response
4. Use returned `ReportID` to fetch full report data via `GET /Reports/{ReportID}`

**Draft BAS Data Not Available:** Draft Activity Statements cannot be accessed via API. This is a confirmed limitation.

**Workaround:** Calculate BAS figures from underlying transaction data:
- GST Collected: Sum of `TaxAmount` where `TaxType` is OUTPUT on sales invoices
- GST Paid: Sum of `TaxAmount` where `TaxType` is INPUT on purchase invoices/bills
- Net GST: Calculate difference internally
- This approach is actually more reliable than depending on published reports

#### Impact Level: **Medium**

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

#### Job Template Capabilities **[R15 - Expanded]**

The `job.api/applytemplate` endpoint enables standardised BAS workflows:

**Available Template Features:**
- Pre-defined task sequences for BAS preparation
- Standard task names and descriptions
- Task ordering (reorderable via `job.api/reordertasks`)
- Template application creates all tasks at once

**BAS Workflow Standardisation Strategy:**
1. Create job templates in XPM for each BAS type (Monthly, Quarterly, Annual)
2. Templates include standard tasks: Data Quality Check, Reconciliation Review, GST Calculation, PAYG Verification, Manager Review, Partner Approval, Lodgement
3. Apply template via API when creating new BAS jobs
4. Track completion status per task

**Limitation:** Templates are managed in XPM directly - API can apply but not create/modify templates.

#### Gap Status: **Partial Access**

#### Critical Gaps

| Gap | Severity | Workaround |
|-----|----------|------------|
| No native approval/sign-off workflow | MEDIUM | Use task-based approval (create "Approval" task) |
| Limited workflow states (Planned, In Progress, Completed) | MEDIUM | Use tasks to represent granular stages |
| No audit trail from API | MEDIUM | Maintain event log in Clairo for changes |
| Cannot create/modify job templates via API | LOW | Manage templates in XPM; apply via API |

#### Impact Level: **Medium**

---

### 1.5 Exportable Worksheets and Reports **[R14 - Added]**

**Purpose:** Generate PDF and Excel exports of BAS worksheets and reports.

#### API Capability Assessment

**Finding:** Xero APIs do not provide pre-formatted PDF/Excel exports of BAS worksheets. The Reports API returns structured data (JSON) not rendered documents.

| Export Need | API Support | Clairo Requirement |
|-------------|-------------|---------------------|
| BAS Worksheet PDF | Not Available | Generate internally using PDF library |
| BAS Data Export (Excel) | Data Available | Export transaction data to Excel format |
| Client Reports | Data Available | Generate reports from API data |
| Variance Reports | Not Available | Calculate and render internally |

**Implementation Approach:**
1. Fetch required data via API (transactions, reports, job details)
2. Generate worksheets using server-side PDF library (e.g., Puppeteer, PDFKit)
3. Use Excel generation library for spreadsheet exports (e.g., ExcelJS, xlsx)
4. Store generated documents via `job.api/document`

#### Impact Level: **Low** (expected to generate internally)

---

### 1.6 Multi-Ledger Support

**Purpose:** Abstracted data layer supporting Xero (primary) and MYOB (Phase 1b).

#### Xero Integration Status: **Full Support**

See all sections above for detailed Xero API analysis.

#### MYOB Integration Status **[R5]**: See Section 12 (MYOB Integration Assessment)

---

## 2. Phase 2 Feature Analysis (Intelligence)

### 2.1 Compliance Analytics

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

#### Gap Status: **Limited Access**

#### Gap Description

| Data Element | Status | Details |
|--------------|--------|---------|
| Lodgement history | **Inferred Only** | Can track completed BAS jobs, not actual ATO lodgement |
| Due date compliance | **Available** | Compare `DueDate` to `CompletedDate` on jobs |
| Penalty exposure | **Not Available** | ATO data not in Xero API |
| ATO audit probability | **Not Available** | Must calculate from internal models |
| ATO notices | **Not Available** | ATO correspondence not in API |

#### Risk Scoring Approach

Since ATO data is not available, Clairo must build internal risk models:

| Risk Factor | Data Source | Calculation |
|-------------|-------------|-------------|
| Late lodgement history | Job DueDate vs CompletedDate | % of late completions over 12 months |
| Data quality score | Clairo internal | Average readiness score trend |
| Industry risk profile | Organisation data | Map industry to ATO audit rates |
| Revenue threshold | P&L reports | Higher revenue = higher scrutiny |
| Variance volatility | Historical BAS figures | Large variances trigger attention |

**Important Caveat:** These are proxy indicators, not actual ATO risk data. Communicate clearly to users that these are "estimated risk indicators" based on data patterns.

#### Impact Level: **Critical**

---

### 2.2 Client Communication

**Purpose:** Automated deadline reminders, data requests, and status updates.

#### Available API Endpoints

| Endpoint | Source | Data Provided |
|----------|--------|---------------|
| `client.api/contacts` | Practice Manager | All contacts for client |
| `client.api/contact/[uuid]` | Practice Manager | Specific contact details |
| `client.api/contact` (POST) | Practice Manager | Add new contact |
| `job.api/note` | Practice Manager | Add notes to job |

#### Gap Status: **Partial Access**

| Capability | Status | Details |
|------------|--------|---------|
| Contact information | **Available** | Full contact details for communications |
| Multiple contacts per client | **Available** | Full contact list per client |
| Communication history | **Not Available** | Must maintain in Clairo |
| Email sending | **Not Available** | Integrate with SendGrid/SES/etc. |
| Template library | **Internal** | Manage templates in Clairo |

#### Template Library **[Partial R1]**

The "Template library for common scenarios" mentioned in Phase 2 requirements is an internal Clairo feature, not dependent on Xero API. This should include:
- Deadline reminder templates
- Missing information request templates
- BAS completion notification templates
- Overdue payment reminders

**Implementation:** Store templates in Clairo database; merge with client/job data at send time.

#### Impact Level: **Medium**

---

### 2.3 Advisory Foundations **[R1 - New Section]**

**Purpose:** Cash flow patterns and alerts, GST recovery opportunities, basic what-if scenario tools.

#### 2.3.1 Cash Flow Patterns and Alerts

**Required Data:**
- Bank transaction history
- Invoice payment patterns
- Bill payment patterns
- Historical cash positions

**Available API Endpoints:**

| Endpoint | Data Provided | Relevance |
|----------|---------------|-----------|
| `/BankTransactions` | All bank transactions | Cash flow history |
| `/Invoices` | Sales invoices with dates | Receivables timing |
| `/Invoices?where=Type=="ACCPAY"` | Purchase invoices | Payables timing |
| `/Reports/BankSummary` | Bank balances | Current position |
| `/Reports/AgedReceivables` | Overdue receivables | Cash at risk |
| `/Reports/AgedPayables` | Overdue payables | Cash requirements |

**Gap Assessment:**

| Feature | API Support | Implementation |
|---------|-------------|----------------|
| Historical cash flow | **Available** | Query transactions, calculate net flow |
| Cash flow forecasting | **Partial** | Use invoice due dates + historical patterns |
| Alert triggers | **Available** | Define thresholds, compare against current data |
| Trend visualisation | **Available** | Aggregate historical data for charts |

**Implementation Approach:**
1. Sync bank transactions daily (watch rate limits - see Section 8)
2. Calculate rolling cash flow metrics (7-day, 30-day, 90-day)
3. Compare current patterns to historical averages
4. Trigger alerts when deviations exceed thresholds
5. Present as advisory insights during BAS review

**Impact Level:** Medium (data available; requires computation)

#### 2.3.2 GST Recovery Opportunities

**Purpose:** Identify unclaimed GST input credits, GST coding errors, and missed deductions.

**Required Data:**
- All purchase transactions with tax types
- Chart of accounts (expense categories)
- Tax rates and their applicability

**Available API Endpoints:**

| Endpoint | Data Provided | Relevance |
|----------|---------------|-----------|
| `/Invoices?where=Type=="ACCPAY"` | Purchase invoices with line items | GST on purchases |
| `/BankTransactions` | Bank transactions with tax types | Coded GST |
| `/TaxRates` | Available tax rates | Validation reference |
| `/Accounts` | Chart of accounts | Category analysis |

**GST Recovery Detection Logic:**

| Opportunity Type | Detection Method |
|------------------|------------------|
| Uncoded purchases | Transactions with no TaxType or "NONE" on expense accounts |
| Incorrect tax rate | Expenses coded as OUTPUT instead of INPUT |
| Capital purchases | Large expenses not coded as CAPEXINPUT |
| Motor vehicle GST | Partial claim eligibility based on business use |
| Home office GST | For sole traders - often miscoded |

**Gap Assessment:**

| Feature | API Support | Notes |
|---------|-------------|-------|
| Transaction analysis | **Available** | Query all transactions with tax types |
| Category-based rules | **Available** | Map accounts to expected tax treatment |
| Historical comparison | **Available** | Compare periods for anomalies |
| Suggested corrections | **Clairo Logic** | Rules engine identifies issues |

**Implementation:** Build rules engine that analyses transactions and flags potential GST recovery opportunities based on:
- Account type vs tax type mismatches
- Industry-standard deduction patterns
- Historical client patterns

**Impact Level:** Medium (core advisory value)

#### 2.3.3 What-If Scenario Tools

**Purpose:** Basic scenario modelling for "what if" business decisions.

**Data Required:**
- Current financial position (P&L, Balance Sheet)
- Historical trends
- Scenario parameters (user input)

**Available API Endpoints:**

| Endpoint | Data Provided | Relevance |
|----------|---------------|-----------|
| `/Reports/ProfitAndLoss` | P&L with date parameters | Baseline financials |
| `/Reports/BalanceSheet` | Balance sheet | Current position |
| `/Invoices` | Revenue trends | Growth projections |
| `/Organisation` | Business settings | Tax rates, GST status |

**Gap Assessment:**

What-if tools are primarily **computational, not API-dependent**. The API provides baseline data; scenarios are calculated internally.

| Scenario Type | API Data Needed | Computation |
|---------------|-----------------|-------------|
| Revenue change impact | Current P&L | Apply % change to revenue line |
| GST impact modelling | Current GST figures | Recalculate at different rates |
| Expense scenario | Current expenses | Adjust categories, recalculate |
| Hiring impact (Phase 3) | Payroll data | Model salary, super, PAYG |

**Implementation:**
1. Fetch current financial data as baseline
2. User inputs scenario parameters
3. Calculate projected figures internally
4. Display comparison (current vs scenario)

**Impact Level:** Low (internal computation)

---

### 2.4 Time Tracking Feature **[R10 - New Section]**

**Purpose:** Track time spent on BAS preparation for efficiency metrics and billing.

#### Available API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `time.api/list` | GET | List all time entries |
| `time.api/job/[job number]` | GET | Time entries for specific job |
| `time.api/staff/[uuid]` | GET | Time entries for staff member |
| `time.api/add` | POST | Create time entry |
| `time.api/update` | PUT | Update time entry |
| `time.api/delete/[uuid]` | DELETE | Delete time entry |

#### Key Time Entry Fields
- `UUID`, `ID`, `JobID`, `StaffMemberUUID`, `TaskUUID`
- `Date`, `Minutes`, `Note`
- `Billable`, `Start`, `End`

#### Gap Status: **Full Access**

#### Clairo Use Cases

| Use Case | Implementation |
|----------|----------------|
| BAS efficiency metrics | Aggregate time per BAS job, compare across clients |
| Staff productivity | Time per staff member on BAS work |
| Billing accuracy | Capture time for invoicing |
| Process improvement | Identify time-consuming BAS clients |
| Benchmark comparisons | Average time per BAS type (monthly vs quarterly) |

**Value for Practice:** Helps answer "How long does BAS really take for each client?" enabling better pricing and resource allocation.

#### Impact Level: **Low** (Full API support)

---

## 3. Phase 3 Feature Analysis (Platform)

### 3.1 White-Label Client Portal **[R2 - New Section]**

**Purpose:** Firm-branded interface for business owners to review BAS drafts, view dashboards, and communicate.

#### 3.1.1 Required Data for Client Portal

| Portal Feature | Data Requirements | API Source |
|----------------|-------------------|------------|
| BAS draft review | BAS figures, supporting details | Calculated from transactions (see 1.3) |
| Financial dashboards | P&L summary, cash position, receivables | `/Reports/*` endpoints |
| Q&A threads | Comments, questions, responses | `job.api/note` (limited) |
| Document access | BAS worksheets, reports | `job.api/documents` |
| Approval workflow | Draft status, sign-off mechanism | Clairo internal + job state |

#### 3.1.2 API Capability Assessment

| Feature | API Support | Gap Analysis |
|---------|-------------|--------------|
| BAS figures for review | **Available** | Calculate from transaction data |
| P&L dashboard | **Available** | `/Reports/ProfitAndLoss` with parameters |
| Balance sheet | **Available** | `/Reports/BalanceSheet` |
| Cash flow summary | **Available** | `/Reports/BankSummary` |
| Aged receivables | **Available** | `/Reports/AgedReceivables` |
| Q&A/comments | **Limited** | Job notes are internal (not client-visible in XPM) |
| Document storage | **Available** | `job.api/document` for attachments |
| Client authentication | **Not Available** | Clairo must implement separately |

#### 3.1.3 Critical Gap: Q&A Thread Implementation

**Issue:** The `job.api/note` endpoint creates notes that are visible only within Practice Manager - they are internal notes, not client-facing communications.

**Workaround:** Build Q&A system entirely within Clairo:
1. Store threads in Clairo database
2. Link threads to job/client via UUIDs
3. Implement notification system (email)
4. Optionally sync key communications to XPM as notes for practitioner reference

#### 3.1.4 Data Exposure Considerations

| Data Type | Client Visibility | Implementation Notes |
|-----------|-------------------|---------------------|
| BAS figures | Show summary only | Hide calculation details |
| Transaction list | Optional (firm choice) | Configurable exposure |
| Data quality issues | Filtered view | Show "items needing attention" not raw issues |
| Accountant notes | Never expose | Internal workflow only |
| Documents | Firm controlled | Explicit publish to portal |

#### Impact Level: **Medium** (data available; portal is Clairo feature)

---

### 3.2 Direct ATO Integration

**Purpose:** DSP certification for direct BAS lodgement and ATO notice ingestion.

#### Gap Status: **Completely Separate from Xero**

This is not a Xero API feature. Direct ATO integration requires:

| Requirement | Description | Timeline |
|-------------|-------------|----------|
| DSP Certification | Digital Service Provider application to ATO | 12-18 months **[R13 - corrected from 6-12]** |
| SBR Implementation | Standard Business Reporting protocol | Included in DSP process |
| Security Assessment | ATO security standards compliance | Part of certification |
| Conformance Testing | Technical testing with ATO | 2-3 months |
| Ongoing Obligations | Annual attestation, breach reporting | Continuous |

#### Alternative Strategies

1. **Partner with Existing DSP** (Recommended for faster time-to-market)
   - LodgeiT: Tier 1 DSP, API available
   - GovReports: Established player
   - Reduces risk and development effort

2. **Direct DSP Certification** (Long-term independence)
   - 12-18 month timeline
   - Significant compliance overhead
   - Higher control over experience

#### Impact Level: **Critical** (for Phase 3)

---

### 3.3 Advanced Advisory **[R1 partial - Hiring Impact, Quarterly Planning, Benchmarking]**

**Purpose:** Hiring impact modelling, quarterly planning tools, industry benchmarking.

#### 3.3.1 Hiring Impact Modelling

**Data Requirements:**
- Payroll data (if Xero Payroll): `payroll.*` scopes
- Salary benchmarks: External data source
- Super guarantee rates: ATO published rates
- PAYG withholding tables: ATO tax tables

**Gap Assessment:**
- Payroll API provides existing employee data
- New hire modelling is computational (user inputs salary, Clairo calculates impacts)
- External data needed for salary benchmarks

**Impact Level:** Medium

#### 3.3.2 Quarterly Planning Tools

**Implementation:** Primarily computational, using historical data from API:
- Fetch 4+ quarters of P&L data
- Calculate trends and seasonality
- Generate projections
- Allow user adjustments

**Gap Assessment:** API data sufficient; computation is internal.

**Impact Level:** Low

#### 3.3.3 Industry Benchmarking

**Data Requirements:**
- Client industry classification: `/Organisation` (industry codes)
- Benchmark data: **Not available from Xero**

**Gap:** Industry benchmark data must come from external sources:
- ATO benchmarks (publicly available)
- Industry associations
- Third-party data providers

**Impact Level:** Medium (requires external data integration)

---

## 4. Critical Gaps Summary

| Gap | Feature Affected | Severity | Phase | Blocker? |
|-----|------------------|----------|-------|----------|
| **No Payroll API in standard scope** | Data Quality Engine | Critical | 1 | Partial - PAYG/super validation blocked |
| **No ATO integration** | Compliance Analytics | Critical | 2, 3 | Yes - for actual lodgement/penalty data |
| **BAS reports must be published** | Variance Analysis | High | 1 | No - calculate from transactions |
| **No webhooks for Practice Manager** | Real-time updates | High | 1, 2 | No - requires polling |
| **Webhooks limited to Contacts/Invoices** | Real-time sync | High | 1, 2 | No - requires hybrid approach |
| **No native approval workflow** | BAS Workflow | Medium | 1 | No - build in Clairo |
| **No audit trail from API** | BAS Workflow | Medium | 1 | No - maintain internally |
| **No client-facing Q&A** | Client Portal | Medium | 3 | No - build in Clairo |
| **DSP certification required** | ATO Integration | Critical | 3 | Yes - for Phase 3 |
| **XPM separate from Xero Accounting** | Market Access | High | 1 | See R12 analysis |

---

## 5. Data Not Available via API

### Completely Unavailable

| Data Type | Reason | Impact | Workaround |
|-----------|--------|--------|------------|
| **PAYG withholding amounts** | Payroll API separate | Cannot validate W1/W2 labels | Add Payroll API or manual import |
| **Superannuation contributions** | Payroll API separate | Cannot verify SG compliance | Add Payroll API or manual import |
| **ATO lodgement confirmation** | ATO system | Cannot confirm actual lodgement | DSP partnership or manual tracking |
| **ATO penalties/interest** | ATO system | Cannot show actual exposure | Risk modelling only |
| **ATO audit status** | ATO system | Cannot show audit flags | Heuristic risk indicators |
| **ATO correspondence** | ATO system | Cannot ingest notices | Manual upload or DSP |
| **Change/audit history** | Not exposed in API | Cannot see Xero changes | Track Clairo changes only |
| **Industry benchmarks** | External data | Cannot compare to industry | Integrate ATO benchmarks |
| **Draft BAS reports** | Must be published | Cannot access until published | Calculate from transactions |

### Requires Additional API Access

| Data Type | API Required | OAuth Scopes Needed |
|-----------|--------------|---------------------|
| Payroll data | Xero Payroll AU API | `payroll.employees`, `payroll.payruns`, `payroll.settings` |
| Leave balances | Xero Payroll AU API | `payroll.employees.read` |
| Employee tax declarations | Xero Payroll AU API | `payroll.employees.read` |
| Practice Manager data | XPM API | `practice_manager` **[R17]** |

---

## 6. Workaround Proposals

### 6.1 PAYG/Super Data Gap

**Problem:** Cannot access payroll data for PAYG withholding and super validation.

**Workarounds:**

| Option | Description | Effort | Coverage |
|--------|-------------|--------|----------|
| **1. Xero Payroll API** | Request additional OAuth scopes | 3-4 weeks | Xero Payroll users only |
| **2. Manual Import** | Upload PAYG summary from external payroll | 1 week | Universal |
| **3. Skip Initially** | Focus on GST quality; add payroll later | 0 weeks | Limited value |

**Recommendation:**
- Option 1 for clients using Xero Payroll
- Option 2 for clients using external payroll (KeyPay, Deputy, standalone)
- Clearly communicate in UI which payroll system is connected

**Market Reality Note** **[R11]:** Many SMEs use external payroll systems. Clairo should not assume Xero Payroll availability.

### 6.2 Real-Time Data Gap (No Webhooks)

**Problem:** No webhook support for Practice Manager; limited webhooks for Accounting API.

**Workaround:** See Section 7 (Webhook Analysis) for detailed polling strategy.

### 6.3 Approval Workflow Gap

**Problem:** No native approval mechanism in Practice Manager API.

**Workaround - Task-Based Approval:**

```
1. Create "Manager Approval" task on BAS job
2. Create "Partner Sign-off" task on BAS job
3. Task completion = approval granted
4. Store approval metadata in Clairo:
   - Approver ID (from staff completing task)
   - Timestamp (from task completion time)
   - Comments (task notes)
5. Sync status to Xero job state when all approvals complete
```

**Benefits:**
- Uses existing API (no custom fields needed)
- Visible in XPM for practitioners
- Clear audit trail

### 6.4 Audit Trail Gap

**Problem:** No change history available from API.

**Workaround - Event Sourcing:**

```
1. Log all Clairo-originated changes:
   - User ID, timestamp, action, before/after values
2. Immutable event log stored in Clairo database
3. Generate audit reports from event log
4. Acknowledge limitation: Direct Xero changes not tracked
```

**Mitigation:** Periodic data snapshots to detect changes made outside Clairo.

### 6.5 BAS Report Data Gap

**Problem:** BAS reports only available if published.

**Workaround - Calculate from Transactions:**

| BAS Label | Calculation |
|-----------|-------------|
| 1A: GST on sales | Sum TaxAmount where TaxType = OUTPUT |
| 1B: GST on purchases | Sum TaxAmount where TaxType = INPUT |
| GST payable/refundable | 1A - 1B |

**Benefits:**
- Always available (doesn't depend on publishing)
- More current than published report
- Can calculate for any date range

### 6.6 Client Portal Q&A Gap

**Problem:** Job notes are internal, not client-facing.

**Workaround:** Build Q&A system in Clairo:
1. Store threads linked to job UUID
2. Email notifications for new messages
3. Client authentication separate from Xero
4. Optional: Sync summaries to XPM notes for practitioner reference

---

## 7. Webhook Analysis **[R3]**

### 7.1 Research Findings

Based on web research (December 2025):

| API | Webhook Support | Events Available |
|-----|-----------------|------------------|
| **Xero Accounting API** | Limited | Contacts, Invoices only |
| **Xero Practice Manager API** | **None** | No webhook support |
| **Xero Payroll API** | None | No webhook support |

**Key Quote:** Xero has acknowledged that limited webhook coverage "is a big gap" and they are "exploring options to expand our range of webhooks." (Xero Developer Ideas, 2025)

### 7.2 Webhook Technical Requirements

When webhooks are available (Contacts/Invoices):

| Requirement | Details |
|-------------|---------|
| Response time | Must respond within 5 seconds with HTTP 200 |
| Validation | HMAC-SHA256 signature verification required |
| Reliability | Xero retries failed deliveries |
| Processing | Process asynchronously after acknowledging receipt |

### 7.3 Impact on Clairo Architecture

| Data Type | Sync Strategy | Frequency |
|-----------|---------------|-----------|
| Contacts | Webhook + polling fallback | Real-time + hourly backup |
| Invoices | Webhook + polling fallback | Real-time + hourly backup |
| Bank transactions | Polling only | Every 15-30 minutes |
| Jobs | Polling only | Every 15 minutes |
| Client list | Polling only | Every 30 minutes |
| Reports | Polling only | Every hour |
| Time entries | Polling only | Every 30 minutes |

### 7.4 Recommended Polling Strategy

**Tier 1 - High Priority (every 15 minutes):**
- Active jobs (`job.api/current`)
- Bank transactions for clients in BAS prep

**Tier 2 - Standard (every 30 minutes):**
- Client list (`client.api/list`)
- Time entries (`time.api/list`)
- Job updates for non-active jobs

**Tier 3 - Low Priority (every 60 minutes):**
- Reports
- Organisation settings
- Staff list

**User-Triggered Refresh:**
- Allow manual refresh from dashboard
- Queue refresh when user opens client detail view

### 7.5 Implications for Data Freshness

| Scenario | Expected Latency | Acceptable? |
|----------|------------------|-------------|
| New client added | 30 minutes | Yes (infrequent) |
| Bank transaction reconciled | 15-30 minutes | Acceptable |
| Job status changed | 15 minutes | Yes |
| Invoice created | Real-time (webhook) | Excellent |
| BAS published | 60 minutes | Yes (user-triggered refresh available) |

**Recommendation:** Design UI to show "Last synced: X minutes ago" and provide manual refresh button.

---

## 8. Rate Limit Calculations **[R7]**

### 8.1 Xero Rate Limits

| Limit Type | Value | Scope |
|------------|-------|-------|
| Per minute | 60 calls | Per app per tenant |
| Per day | 5,000 calls | Per app per tenant |
| Concurrent | 5 calls | Per tenant |

**Important:** Each connected Xero organisation has its own limit pool. A Clairo firm with 100 clients has 100 separate rate limit pools.

### 8.2 Usage Scenarios

#### Scenario 1: Initial Client Onboarding (per client)

| API Call | Purpose | Count |
|----------|---------|-------|
| `client.api/get` | Client details | 1 |
| `/Organisation` | Org settings | 1 |
| `/BankTransactions` | Full transaction history (paginated) | 5-20 |
| `/Invoices` | Invoice history (paginated) | 5-20 |
| `/Accounts` | Chart of accounts | 1 |
| `/TaxRates` | Tax rates | 1 |
| `/Reports/ProfitAndLoss` | Historical P&L (4 periods) | 4 |
| `/Reports/BalanceSheet` | Current balance | 1 |
| `job.api/client/[uuid]` | Historical jobs | 1 |

**Estimated Total:** 20-50 calls per client onboarding

**Rate Limit Impact:**
- 60/minute limit: Can onboard ~1-2 clients per minute
- 5,000/day limit: Can onboard ~100-200 clients per day

**Recommendation:** Queue onboarding, spread over time.

#### Scenario 2: Daily Sync for 50-Client Practice

| API Call | Purpose | Per Client | Total (50 clients) |
|----------|---------|------------|-------------------|
| `/BankTransactions?ModifiedAfter` | New transactions | 1-2 | 50-100 |
| `/Invoices?ModifiedAfter` | New invoices | 1-2 | 50-100 |
| `job.api/client/[uuid]` | Job updates | 1 | 50 |

**Estimated Daily Total:** 150-250 calls across all clients

**Rate Limit Impact:** Well within 5,000/day per org. Each org only sees ~3-5 calls.

**Recommendation:** Safe for daily sync.

#### Scenario 3: Dashboard Refresh During BAS Crunch Period **[R18]**

Assume: 50 clients, 10 practitioners, peak usage

| Action | API Calls | Concurrent Risk |
|--------|-----------|-----------------|
| Dashboard load | 5 calls (aggregated data) | Medium |
| Client detail view | 10 calls | Low |
| Refresh all clients | 50 x 5 = 250 calls | HIGH |
| 10 users simultaneously | 10 x 5 = 50 concurrent | EXCEEDS LIMIT |

**Concurrency Issue:** 5 concurrent call limit per tenant means only 5 practitioners can make API calls simultaneously to the same Xero org.

**Mitigation:**
1. **Aggressive Caching:** Cache data locally; serve from cache
2. **Queue API Requests:** Serialize calls per tenant
3. **Background Sync:** Pre-fetch data before peak usage
4. **Rate Limiting in Clairo:** Implement internal rate limiter

#### Scenario 4: Scaling to 200 Clients

| Metric | Calculation | Result |
|--------|-------------|--------|
| Daily sync calls | 200 x 5 = 1,000 | Within limits |
| Dashboard refresh | 200 x 3 = 600 calls | Spread over time |
| Peak concurrent (worst case) | 20 users x 5 = 100 | Queue required |

**Recommendation:** Implement request queue per tenant; prioritize active BAS clients.

### 8.3 Certified App Rate Limits **[R9]**

Xero App Partners do NOT receive higher rate limits (contrary to common assumption). Benefits are:
- Unlimited client connections (vs 25 for uncertified)
- App Store listing
- Xero ecosystem credibility

Rate limits remain 60/min, 5,000/day regardless of certification status.

### 8.4 Token Refresh at Scale **[Addressing technical consideration]**

**Challenge:** 200 clients = 200 OAuth token pairs (access + refresh tokens)

| Token | Expiry | Strategy |
|-------|--------|----------|
| Access token | 30 minutes | Refresh before expiry |
| Refresh token | 60 days, **rotating** | Single use - must store new token |

**Token Management Strategy:**

1. **Proactive Refresh:** Refresh access tokens 5 minutes before expiry
2. **Secure Storage:** Encrypted token storage in database
3. **Rotation Handling:** Always save new refresh token after use
4. **Error Handling:** Detect revoked access; notify practitioner
5. **Batch Processing:** Stagger token refreshes to avoid API bursts

---

## 9. Multi-Tenancy Considerations **[R6]**

### 9.1 Data Isolation Model

**Clairo Multi-Tenant Architecture:**

```
┌─────────────────────────────────────────────────────┐
│                    Clairo Platform                  │
├─────────────────────────────────────────────────────┤
│  Firm A (Tenant 1)    │    Firm B (Tenant 2)        │
│  ┌─────────────────┐  │    ┌─────────────────┐      │
│  │ Client 1        │  │    │ Client X        │      │
│  │ Client 2        │  │    │ Client Y        │      │
│  │ Client 3        │  │    │ Client Z        │      │
│  └─────────────────┘  │    └─────────────────┘      │
├─────────────────────────────────────────────────────┤
│  Database: Tenant ID on all records                  │
│  API: OAuth connections per tenant+client            │
└─────────────────────────────────────────────────────┘
```

### 9.2 Xero API Tenant Boundaries

| Entity | Tenant Scope | Notes |
|--------|--------------|-------|
| Xero Organisation | Connected to specific Clairo firm | OAuth connection per org per firm |
| Practice Manager | XPM instance = one firm | Firm's entire client list |
| Accounting API | Per Xero org | Separate connection per client org |

**Key Distinction:**
- **XPM API:** Returns ALL clients for the connected practice
- **Accounting API:** Per-organisation connection required

### 9.3 Data Segregation Requirements

| Requirement | Implementation |
|-------------|----------------|
| Firm A cannot see Firm B's clients | Tenant ID filter on all queries |
| Firm A cannot see Firm B's XPM data | Separate OAuth connections |
| Client data belongs to firm's tenant | Foreign key constraints |
| User access scoped to tenant | Role-based access control |

### 9.4 Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Cross-tenant data leakage | Critical | Tenant ID on all records; query-level enforcement |
| OAuth token confusion | High | Token storage keyed by tenant + org UUID |
| Cached data exposure | High | Tenant-scoped cache keys |
| API response confusion | Medium | Validate org UUID matches expected |

### 9.5 Practice Manager Client Visibility

**Important:** When Clairo connects to a firm's XPM instance, it can see ALL clients in that practice. This is the intended behavior for a practice management tool.

**Implication:** If two Clairo firms somehow connect to the same XPM instance (unlikely but possible in edge cases), they would see the same client list.

**Safeguard:** Clairo should verify that the connected XPM instance matches the expected practice/tenant.

---

## 10. Offline Mode Requirements **[R4]**

### 10.1 Requirement Analysis

From overview.md: *"Offline-capable: Support for regional Australia connectivity issues"*

This is listed as a **design principle**, suggesting it's a core requirement rather than a nice-to-have.

### 10.2 Offline Capability Tiers

| Tier | Description | Complexity |
|------|-------------|------------|
| **View Only** | Display cached data when offline | Low |
| **Partial Edit** | Limited edits (notes, internal status) | Medium |
| **Full Offline** | Complete BAS prep workflow offline | High |

### 10.3 Data Caching Requirements

**For View Only Tier:**

| Data Type | Cache Strategy | Freshness |
|-----------|----------------|-----------|
| Client list | Full cache | Sync when online |
| Job list | Full cache | Sync when online |
| Transaction summary | Aggregated cache | Per-period snapshot |
| Data quality scores | Calculated cache | Recalculate on sync |
| P&L/Balance Sheet | Period snapshots | Per-period cache |

**Storage Estimate (per client):**
- Client details: ~5 KB
- Job history (12 months): ~50 KB
- Transaction summary: ~100 KB
- Reports (4 quarters): ~200 KB
- **Total per client:** ~355 KB
- **50 clients:** ~18 MB
- **200 clients:** ~71 MB

### 10.4 Offline-Capable Features

| Feature | Offline Support | Notes |
|---------|-----------------|-------|
| View dashboard | YES | From cached data |
| View client details | YES | From cached data |
| View job status | YES | From cached data |
| View data quality scores | YES | Pre-calculated |
| Add notes to job | PARTIAL | Queue for sync |
| Update task status | PARTIAL | Queue for sync |
| Calculate variance | YES | From cached transactions |
| Run reports | YES | From cached data |
| Create new job | NO | Requires API |
| Sync new data | NO | Requires connectivity |

### 10.5 Technical Implementation

**Architecture Components:**

```
┌─────────────────────────────────────────┐
│           Clairo Web App               │
├─────────────────────────────────────────┤
│  Service Worker (caching, sync queue)   │
├─────────────────────────────────────────┤
│  IndexedDB (local data store)           │
├─────────────────────────────────────────┤
│  Sync Manager (background sync)         │
└─────────────────────────────────────────┘
```

**Key Technologies:**
- **Service Worker:** Intercept network requests, serve from cache
- **IndexedDB:** Client-side storage for structured data
- **Background Sync API:** Queue changes when offline, sync when online

### 10.6 Conflict Resolution

**Scenario:** User makes changes offline; same data changed in Xero.

| Conflict Type | Resolution Strategy |
|---------------|---------------------|
| Job status changed | Last-write-wins (warn user) |
| Task completed | Accept both (non-conflicting) |
| Notes added | Merge (append both) |
| Transaction data | Xero is source of truth (discard local) |

**Recommendation:** Clairo changes (notes, tasks, status) can conflict; Xero data is always source of truth for financial data.

### 10.7 MVP Recommendation

**For Phase 1:** Implement **View Only** offline tier
- Cache essential data (clients, jobs, scores)
- Provide clear "offline mode" indicator
- Disable sync-dependent features when offline
- Queue note/task changes for later sync

**Phase 2:** Expand to **Partial Edit** as usage patterns emerge

---

## 11. Xero App Partner Certification **[R9]**

### 11.1 Research Findings

Based on Xero Developer documentation (December 2025):

| Aspect | Details |
|--------|---------|
| Program | Xero App Partner Program |
| Benefits | Unlimited connections, App Store listing, ecosystem credibility |
| Rate Limits | **No change** (still 60/min, 5,000/day) |
| Timeline | 2-4 weeks for certification process |
| Requirements | Pass certification checkpoints |

### 11.2 Certification Checkpoints

| Checkpoint | Description | Clairo Impact |
|------------|-------------|----------------|
| Sign up with Xero | Developer account | Done |
| Xero App Store | App listing requirements | Marketing materials needed |
| Connection | OAuth implementation | Standard OAuth2 flow |
| Branding and Naming | No Xero trademark misuse | Review app name/branding |
| Scopes | Request only needed scopes | Minimize scope requests |
| Error Handling | Graceful error handling | Required anyway |
| Data Integrity | Proper data handling | Required anyway |
| Account and Payment Mapping | Financial data mapping | For accounting apps |
| Taxes | Correct tax handling | Critical for BAS |

### 11.3 2025-2026 Changes

**New Tiered Model (effective March 2026):**

| Tier | Connections | Benefits |
|------|-------------|----------|
| Starter | Small scale | Basic access |
| Core | Growing scale | Standard benefits |
| Plus | Larger scale | Enhanced benefits |
| Advanced | Enterprise scale | Premium support |
| Enterprise | Unlimited scale | Full benefits |

**Key Policy Changes:**
- Prohibition on using API data to train AI/ML models
- Apps must not use bots/browser extensions to simulate user actions
- Updated commercial terms consolidating existing agreements

### 11.4 Exemption for Practice Tools

**Good News:** "Bespoke Integrations for Accountants and Bookkeepers built for your own practice or a single client" are excluded from the new pricing model.

**Implication:** If Clairo is positioned as a practice tool (not a multi-practice SaaS), pricing exemptions may apply. However, Clairo's SaaS model likely requires standard certification.

### 11.5 Certification Timeline Recommendation

| Phase | Milestone | Timeline |
|-------|-----------|----------|
| Pre-launch | Develop with demo company | Month 1-4 |
| Design partners | Use uncertified (25 connection limit) | Month 4-6 |
| Apply for certification | Submit application | Month 6 |
| Certification process | Pass checkpoints | Month 6-7 |
| Certified launch | App Store listing | Month 7+ |

**Note:** The 25-connection limit during design partner phase is actually sufficient for 5-10 design partners with 2-3 clients each for testing.

---

## 12. MYOB Integration Assessment **[R5]**

### 12.1 MYOB API Overview

**Research Findings (December 2025):**

| Aspect | Details |
|--------|---------|
| API Type | REST API with JSON format |
| Authentication | OAuth 2.0 (updated March 2025) |
| Products | AccountRight, MYOB Essentials, MYOB Business |
| Documentation | developer.myob.com |
| Rate Limits | Not explicitly documented (more lenient than Xero) |

### 12.2 Key API Changes (2025)

| Change | Date | Impact |
|--------|------|--------|
| New OAuth requirements | March 2025 | Old "CompanyFile" scope deprecated |
| `/accountright` endpoint deprecated | March 2025 | New auth flow required |
| Administrator-only access | March 2025 | Only admins can authorize |
| JournalTransaction API improvements | August 2025 | Better performance |

### 12.3 MYOB API Capabilities Comparison

| Capability | Xero | MYOB | Notes |
|------------|------|------|-------|
| Client management | XPM API | No equivalent | MYOB lacks practice manager |
| Transaction data | Accounting API | AccountRight API | Similar capabilities |
| BAS data | Reports endpoint | BAS Provision data | Different structure |
| Invoices | Full CRUD | Full CRUD | Comparable |
| Bank transactions | Full access | Full access | Comparable |
| GST codes | TaxRates API | TaxCodes API | Mapping required |
| Payroll | Separate API | Integrated | MYOB Payroll in same product |

### 12.4 Key Differences from Xero

| Aspect | Xero Approach | MYOB Approach |
|--------|---------------|---------------|
| Practice management | XPM (separate product) | None (use external PM tools) |
| Multi-client access | Via XPM connection | Individual file connections |
| BAS preparation | Published reports | GST report data |
| Company files | Cloud-hosted | Local or cloud hosted |
| OAuth flow | Standard OAuth 2.0 | OAuth 2.0 (updated 2025) |

### 12.5 Integration Strategy for Phase 1b

**Challenge:** MYOB lacks a practice management equivalent to XPM. Clairo must handle client/job management internally for MYOB clients.

**Proposed Architecture:**

```
┌─────────────────────────────────────────┐
│            Clairo Platform             │
├─────────────────────────────────────────┤
│  Unified Data Layer (abstraction)       │
├───────────────┬─────────────────────────┤
│  Xero Adapter │     MYOB Adapter        │
│  ┌──────────┐ │     ┌──────────────┐    │
│  │XPM API   │ │     │Internal PM   │    │
│  │Accounting│ │     │AccountRight  │    │
│  └──────────┘ │     └──────────────┘    │
└───────────────┴─────────────────────────┘
```

**MYOB Adapter Requirements:**

| Component | Xero Source | MYOB Equivalent |
|-----------|-------------|-----------------|
| Client list | `client.api/list` | Clairo internal database |
| Job tracking | `job.api/*` | Clairo internal database |
| Transactions | `/BankTransactions` | `/GeneralLedger/TransactionJournal` |
| Invoices | `/Invoices` | `/Sale/Invoice` |
| GST data | `/TaxRates` | `/GeneralLedger/TaxCode` |
| Reports | `/Reports/*` | `/Report/*` |

### 12.6 Development Effort Estimate

| Component | Effort | Priority |
|-----------|--------|----------|
| MYOB OAuth implementation | 1 week | High |
| Transaction data adapter | 2 weeks | High |
| Invoice/Bill adapter | 1 week | High |
| GST validation logic | 1 week | High |
| Report generation | 1 week | Medium |
| Internal client/job management | 2 weeks | High |
| Testing and integration | 2 weeks | High |
| **Total** | **10 weeks** | Phase 1b |

### 12.7 Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| API changes (March 2025 style) | Medium | High | Monitor MYOB developer updates |
| Company file access complexity | Medium | Medium | Clear onboarding flow |
| Lack of practice management | High | Medium | Build internal equivalent |
| User adoption friction | Medium | Medium | Seamless onboarding UX |

### 12.8 Recommendation

**Phase 1b Scope:**
1. Focus on MYOB AccountRight (most common for BAS-focused practices)
2. Build internal client/job management for MYOB clients
3. Implement core data quality features (bank rec, GST validation)
4. Defer advanced features until Xero implementation stable

**Timeline:** Start MYOB development after Xero MVP validated (Month 4-6)

---

## 13. Risk Assessment

### 13.1 Overall Viability: **Viable with Significant Internal Development**

The Xero APIs provide foundational data access but key differentiators must be built internally.

### 13.2 Risk Matrix (Updated)

| Risk | Probability | Impact | Mitigation | Issue Ref |
|------|-------------|--------|------------|-----------|
| **Payroll data inaccessible** | Medium | High | Payroll API + manual import option | R11 |
| **BAS reports incomplete** | Medium | Medium | Calculate from transactions | R8 |
| **Rate limiting impacts sync** | Medium | Medium | Caching, queuing, prioritization | R7 |
| **ATO integration timeline** | High | High | DSP partnership; defer to Phase 3 | - |
| **API changes by Xero** | Low | High | Abstract data layer; monitor changes | - |
| **XPM market penetration** | Medium | High | See R12 analysis below | R12 |
| **Webhook limitations** | High | Medium | Polling strategy implemented | R3 |
| **Offline connectivity issues** | Medium | Medium | Local caching; offline mode | R4 |
| **MYOB integration complexity** | Medium | Medium | Dedicated adapter development | R5 |
| **Multi-tenant data leakage** | Low | Critical | Tenant ID enforcement; access controls | R6 |

### 13.3 XPM Market Penetration Risk **[R12]**

**Issue:** Xero Practice Manager (XPM) is a separate product from Xero accounting. Not all Xero accounting users have XPM.

**Market Analysis:**

| User Segment | Xero Accounting | XPM | Clairo Impact |
|--------------|-----------------|-----|----------------|
| Accountant practices (20+ clients) | Yes | Often | Primary target - OK |
| Small bookkeepers (5-20 clients) | Yes | Sometimes | May need non-XPM mode |
| Business owners | Yes | No | Not target market |

**Risk Level:** Medium - Primary target (practices 20-200 clients) likely has XPM

**Mitigation Strategies:**

1. **Validate in design partner selection:** Confirm XPM usage before onboarding
2. **Non-XPM mode (future):** Allow manual client/job management if XPM unavailable
3. **Market research:** Survey target market on XPM adoption rates
4. **Messaging:** Position Clairo as complementary to XPM, not dependent

**Fallback:** If XPM adoption is lower than expected, build internal client/job management (similar to MYOB approach).

### 13.4 Development Effort Impact (Revised)

| Feature | Original | Revised | Reason |
|---------|----------|---------|--------|
| Data Quality Engine | Medium | High | All scoring internal; payroll complexity |
| Variance Analysis | Low | Medium | Multi-call, internal calculation |
| Compliance Analytics | Medium | High | Entirely modelled internally |
| BAS Workflow | Low | Medium | Custom workflow engine needed |
| Client Communication | Low | Medium | External email integration |
| Offline Mode | Not estimated | Medium | Local caching architecture |
| Webhook Handling | Not estimated | Medium | Polling infrastructure |
| MYOB Integration | Medium | High | 10 weeks dedicated effort |
| ATO Integration | High | Critical | DSP certification (12-18 months) |

### 13.5 Go/No-Go Assessment (Updated)

| Criterion | Assessment |
|-----------|------------|
| Core value proposition deliverable? | **Yes** - Data Quality Engine is computable |
| Unique differentiator viable? | **Yes** - Internal models provide differentiation |
| Technical feasibility confirmed? | **Yes** - APIs sufficient for source data |
| Development timeline realistic? | **Review Required** - More internal logic than anticipated |
| Offline capability feasible? | **Yes** - Standard PWA techniques |
| MYOB integration viable? | **Yes** - Separate development track |
| Phase 3 (ATO) feasibility? | **Uncertain** - DSP certification major undertaking |
| XPM market risk acceptable? | **Yes with mitigation** - Target market likely has XPM |

---

## 14. Clarification Answers

### Xero API Questions

**Q1: Does Xero Practice Manager support webhooks?**
**A:** No. XPM has no webhook support. Xero acknowledged this is a "big gap" and is exploring expansion. Polling is required for all XPM data.

**Q2: What exactly triggers a BAS report to be "published"?**
**A:** User manually clicks "Publish" on the draft Activity Statement in Xero (Adviser > Activity Statement). This is a manual action, not automatic. Once published, the report appears in the `/Reports` API endpoint.

**Q3: Can Practice Manager custom fields store structured data (JSON)?**
**A:** The API documentation suggests custom fields are primitive values (text, number, date). For structured data, store JSON as text and parse in Clairo, or use Clairo's own database.

**Q4: What happens when a Xero org is disconnected?**
**A:** API calls will fail with 401/403 errors. Clairo should detect this (e.g., during polling) and notify the practitioner. Recommend checking token validity before each sync batch.

**Q5: Is there an API to access ATO lodgement dates calendar?**
**A:** No. Clairo must maintain ATO due date calendar internally. ATO publishes these dates on their website; consider scraping or manual maintenance.

### Clairo Requirements Clarification

**Q6: What is the target data freshness for the dashboard?**
**A:** Recommend 15-30 minute freshness as default (achievable with polling). Real-time is not feasible without webhooks for most data. Provide manual refresh option.

**Q7: Is MYOB Integration truly Phase 1b or can it slip to Phase 2?**
**A:** Based on overview.md, MYOB is explicitly Phase 1b. Recommend: Validate Xero MVP (Phase 1) first, then begin MYOB development. If Xero validation takes longer, MYOB may slip.

**Q8: What percentage of target customers have Xero Payroll vs external payroll?**
**A:** Unknown - requires market research. Estimate: 40-60% of SMEs using Xero may have external payroll (KeyPay, Deputy, standalone). Recommendation: Support both via Payroll API + manual import.

**Q9: Is offline mode a "nice to have" or hard requirement for MVP?**
**A:** Listed as a design principle in overview.md, suggesting core requirement. Recommend: Implement View-Only offline for MVP; expand later based on usage.

**Q10: What is the expected maximum client portfolio size to support?**
**A:** overview.md suggests 20-200 clients as primary target. Rate limit calculations show 200 clients is manageable with proper caching.

### Competitive/Market Questions

**Q11: Do competitors (LodgeiT, GovReports) use Xero webhooks?**
**A:** Research inconclusive. Given webhook limitations, competitors likely use polling. Recommendation: Implement efficient polling; monitor for webhook expansion.

**Q12: What Xero App Store tier are we targeting?**
**A:** With new tier model (March 2026), likely start at Core tier and grow. Focus on certification checkpoints; tier placement follows from connection count.

---

## Appendices

### Appendix A: API Endpoint Reference

#### Practice Manager API v3.1

| Category | Endpoints Used | Gap Status |
|----------|----------------|------------|
| Clients | `client.api/list`, `get`, `contacts` | Full |
| Client Groups | `clientgroup.api/list`, `get` | Full **[R16]** |
| Jobs | `job.api/list`, `current`, `state`, `tasks` | Full |
| Staff | `staff.api/list`, `get` | Full |
| Time | `time.api/list`, `job/[id]` | Full **[R10]** |
| Custom Fields | `customfield.api/*` | Full |
| Documents | `client.api/documents`, `job.api/documents` | Full |

#### Accounting API v2.0

| Category | Endpoints Used | Gap Status |
|----------|----------------|------------|
| Reports | `/Reports`, `/Reports/ProfitAndLoss` | Partial (BAS must be published) |
| Bank Transactions | `/BankTransactions` | Full |
| Invoices | `/Invoices` | Full |
| Tax Rates | `/TaxRates` | Full |
| Organisation | `/Organisation` | Full |
| Accounts | `/Accounts` | Full |

#### Not Available

| API | Status |
|-----|--------|
| Xero Payroll AU API | Separate OAuth scopes required |
| ATO SBR/API | Not Xero; direct ATO integration |
| Practice Manager Webhooks | Not available |

### Appendix B: OAuth Scope Requirements **[R17 - Updated]**

#### Minimum Scopes (MVP)

```
offline_access
openid
profile
email
accounting.transactions.read
accounting.reports.read
accounting.settings.read
accounting.contacts.read
practice_manager                   # [R17 - Added]
```

#### Additional Scopes for Full Feature Set

```
accounting.transactions            # For write operations
accounting.settings                # For write operations
accounting.contacts                # For write operations
payroll.employees.read             # For payroll integration
payroll.payruns.read               # For payroll integration
payroll.settings.read              # For payroll integration
```

### Appendix C: Feature Coverage Matrix (Updated) **[From Review]**

| Feature (from overview.md) | Analyzed? | Adequate Depth? | Issue Addressed |
|---------------------------|-----------|-----------------|-----------------|
| Multi-Client Dashboard | Yes | Yes | - |
| Deadline tracking with ATO dates | Yes | Yes | R1 (clarified) |
| Bulk status updates | Yes | Yes | R16 |
| Data Quality Engine | Yes | Yes | - |
| Issue detection (reconciliation, GST, PAYG) | Yes | Yes | R11 |
| Trend analysis (recurring issues) | Yes | Yes | R1 |
| BAS Preparation Workflow | Yes | Yes | - |
| Automated variance analysis | Yes | Yes | R8 |
| Approval workflow with audit trail | Yes | Yes | - |
| Exportable worksheets (PDF, Excel) | Yes | Yes | R14 |
| Multi-Ledger Support (Xero) | Yes | Yes | - |
| Multi-Ledger Support (MYOB) | Yes | Yes | R5 |
| Abstracted data layer | Yes | Yes | R5 |
| Compliance Analytics | Yes | Yes | - |
| Penalty risk scoring | Yes | Yes | - |
| ATO audit probability | Yes | Yes | - |
| Client Communication | Yes | Yes | - |
| Template library | Yes | Yes | R1 |
| Advisory Foundations | Yes | Yes | R1 |
| White-Label Client Portal | Yes | Yes | R2 |
| Direct ATO Integration | Yes | Yes | R13 |
| Advanced Advisory | Yes | Yes | R1 |
| Offline capability | Yes | Yes | R4 |

### Appendix D: Issue Resolution Tracker

| Issue ID | Status | Section | Notes |
|----------|--------|---------|-------|
| R1 | Resolved | 2.3, 3.3 | Advisory Foundations added |
| R2 | Resolved | 3.1 | White-Label Portal added |
| R3 | Resolved | 7 | Webhook Analysis added |
| R4 | Resolved | 10 | Offline Mode added |
| R5 | Resolved | 12 | MYOB Assessment added |
| R6 | Resolved | 9 | Multi-Tenancy added |
| R7 | Resolved | 8 | Rate Limit Calculations added |
| R8 | Resolved | 1.3 | BAS Report behavior verified |
| R9 | Resolved | 11 | App Partner Certification added |
| R10 | Resolved | 2.4 | Time Tracking added |
| R11 | Resolved | 1.2.1, 6.1 | Payroll complexity updated |
| R12 | Resolved | 13.3 | XPM market risk added |
| R13 | Resolved | 3.2, Document | Date consistency fixed (12-18 months) |
| R14 | Resolved | 1.5 | Export functionality added |
| R15 | Resolved | 1.4 | Job template analysis expanded |
| R16 | Resolved | 1.1 | Client groups noted |
| R17 | Resolved | Appendix B | practice_manager scope added |
| R18 | Resolved | 8.2 | Concurrent request limits analyzed |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | December 2025 | Analysis Agent | Initial gap analysis |
| 2.0 | December 2025 | Analysis Agent | Comprehensive revision addressing all review issues (R1-R18) |

---

## Sources

- [Xero Practice Manager API Overview](https://developer.xero.com/documentation/api/practice-manager/overview-practice-manager)
- [Xero API Webhooks](https://developer.xero.com/documentation/guides/webhooks/overview/)
- [Xero Rate Limits](https://developer.xero.com/documentation/best-practices/api-call-efficiencies/rate-limits/)
- [Xero App Partner FAQs](https://developer.xero.com/documentation/xero-app-store/app-partner-guides/faqs/)
- [Xero Certification Checkpoints](https://developer.xero.com/documentation/xero-app-store/app-partner-guides/certification-checkpoints/)
- [Xero Accounting API Reports](https://developer.xero.com/documentation/api/accounting/reports)
- [MYOB Developer Portal](https://developer.myob.com/api/myob-business-api/)
- [MYOB OAuth 2.0 Guide (2025)](https://apisupport.myob.com/hc/en-us/articles/13065472856719-MYOB-OAuth2-0-Authentication-Guide-Post-March-2025)
- [Xero Developer Ideas - Webhooks](https://xero.uservoice.com/forums/5528-accounting-api/suggestions/40184635-provide-more-webhooks)

---

*This analysis is based on Xero and MYOB API documentation as of December 2025, web research conducted December 2025, and the Clairo feature requirements defined in overview.md.*
