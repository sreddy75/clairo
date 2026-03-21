# Requirements Document: BAS Preparation Workflow

## Introduction

This document defines the requirements for the BAS Preparation Workflow feature in Clairo. Building upon the completed Data Quality Scoring (Spec 008), this feature enables accountants to prepare Business Activity Statements (BAS) for their clients with automated GST calculations, variance analysis, and a structured preparation workflow.

BAS Preparation Workflow is the first component of Milestone M4 (BAS Workflow) and represents a critical step toward the platform's core value proposition: reducing BAS preparation time while improving accuracy.

**Key Context:**
- Data Quality Scoring complete (Spec 008) - clients have quality scores and issues identified
- Xero data available: XeroInvoice, XeroBankTransaction, XeroAccount, XeroEmployee, XeroPayRun
- Multi-tenant architecture with RLS enforced
- Australian Financial Year: July-June (Q1=Jul-Sep, Q2=Oct-Dec, Q3=Jan-Mar, Q4=Apr-Jun)
- Target: Reduce BAS prep time by >50% vs manual process

---

## Problem Statement

Accountants currently prepare BAS manually through a time-consuming process:
1. **Data gathering** - Export data from Xero, reconcile bank accounts
2. **GST calculation** - Manually sum transactions by GST code
3. **Variance analysis** - Compare to prior periods using spreadsheets
4. **Documentation** - Create working papers for audit trail
5. **Review** - Check calculations, identify anomalies
6. **Client communication** - Request missing information

This process takes 2-4 hours per client and is error-prone. Clairo automates GST calculations, flags variances, and provides a structured workflow with full audit trail, reducing prep time to under 1 hour.

---

## Requirements

### User Story 1: BAS Period Selection and Creation (Priority: P1)

As an accountant, I want to select a BAS period for a client and create a preparation session, so that I can start working on their BAS in a structured way.

**Why this priority**: This is the entry point for the entire workflow. Without period selection, no other functionality can proceed.

**Independent Test**: Can be tested by selecting a client and creating a BAS prep session, which immediately shows the session exists and is ready for work.

**Acceptance Scenarios:**

1. **Given** I am viewing a client's detail page, **When** I click "Prepare BAS", **Then** I see a period selector with available quarters.

2. **Given** I select a quarter (e.g., Q2 FY2025), **When** I click "Start Preparation", **Then** a new BAS preparation session is created with status "In Progress".

3. **Given** a BAS session already exists for the selected quarter, **When** I try to create another, **Then** I am redirected to the existing session.

4. **Given** the selected quarter has data quality score <50%, **When** I start preparation, **Then** I see a warning about data quality issues that should be resolved first.

---

### User Story 2: Automated GST Calculation (Priority: P1)

As an accountant, I want the system to automatically calculate GST figures from synced Xero data, so that I don't have to manually sum transactions.

**Why this priority**: GST calculation is the core value proposition - without accurate calculations, the platform provides no value.

**Independent Test**: Can verify by comparing system-calculated GST figures against Xero's BAS report for the same period.

**Acceptance Scenarios:**

1. **Given** a BAS session is in progress, **When** I view the GST tab, **Then** I see calculated totals for all GST fields:
   - G1 (Total sales including GST)
   - G2 (GST on sales - export sales)
   - G3 (Other GST-free sales)
   - G10 (Capital purchases)
   - G11 (Non-capital purchases)
   - 1A (GST on sales)
   - 1B (GST on purchases)

2. **Given** transactions exist in Xero with various tax types, **When** GST is calculated, **Then** each transaction is correctly categorized:
   - OUTPUT (GST on sales) → 1A
   - INPUT (GST on purchases) → 1B
   - BASEXCLUDED → excluded from GST calculation
   - EXEMPTEXPENSES → G3 (GST-free)
   - EXEMPTINCOME → G3 (GST-free)
   - CAPEX → G10 (capital)

3. **Given** transactions span multiple months, **When** I view GST breakdown, **Then** I can see monthly sub-totals within the quarter.

4. **Given** the calculation completes, **When** I refresh the page, **Then** I see the cached calculation result (not recalculating).

---

### User Story 3: PAYG Withholding Summary (Priority: P1)

As an accountant, I want to see PAYG withholding totals from payroll data, so that I can complete the PAYG section of the BAS.

**Why this priority**: PAYG is a required field on most BAS forms and is sourced from payroll data synced in Spec 007.

**Independent Test**: Can verify by comparing W1/W2 totals against pay run summaries in Xero.

**Acceptance Scenarios:**

1. **Given** a BAS session is in progress and payroll data exists, **When** I view the PAYG tab, **Then** I see:
   - W1 (Total salary/wages)
   - W2 (Amount withheld from salary/wages)

2. **Given** multiple pay runs exist in the quarter, **When** I view PAYG details, **Then** I see each pay run listed with its contribution to W1/W2.

3. **Given** no payroll data exists (not a payroll client), **When** I view PAYG, **Then** I see "N/A - No payroll data" with W1=0, W2=0.

4. **Given** the client has payroll but no pay runs for this quarter, **When** I view PAYG, **Then** I see a warning that pay runs may be missing.

---

### User Story 4: Variance Analysis (Priority: P2)

As an accountant, I want to see how this quarter's figures compare to the previous quarter and same quarter last year, so that I can identify anomalies that need investigation.

**Why this priority**: Variance analysis catches errors and unusual patterns, but the base calculations (P1 stories) must work first.

**Independent Test**: Can verify by comparing two quarters with known differences and confirming variances are highlighted correctly.

**Acceptance Scenarios:**

1. **Given** I am viewing GST calculations, **When** prior period data exists, **Then** I see variance columns showing:
   - $ change vs prior quarter
   - % change vs prior quarter
   - $ change vs same quarter last year (if available)

2. **Given** a variance exceeds 20%, **When** viewing the comparison, **Then** it is highlighted in yellow (warning).

3. **Given** a variance exceeds 50%, **When** viewing the comparison, **Then** it is highlighted in red (requires attention).

4. **Given** I click on a highlighted variance, **When** the detail panel opens, **Then** I see contributing transactions that explain the change.

5. **Given** this is the first BAS for a new client, **When** I view variances, **Then** I see "N/A - First period" instead of variance figures.

---

### User Story 5: BAS Summary and Review (Priority: P2)

As an accountant, I want to see a complete BAS summary with all calculated fields, so that I can review before marking as ready for lodgement.

**Why this priority**: The summary is the final review step before approval, but depends on calculations being complete.

**Independent Test**: Can verify by generating a summary and checking all required BAS fields are populated.

**Acceptance Scenarios:**

1. **Given** all calculations are complete, **When** I view the Summary tab, **Then** I see:
   - All G fields (G1-G11)
   - GST payable/refundable (1A - 1B)
   - PAYG withholding (W1, W2)
   - Total amount payable/refundable

2. **Given** the calculated GST payable is positive, **When** viewing summary, **Then** it shows "GST Payable: $X,XXX".

3. **Given** the calculated GST payable is negative (refund), **When** viewing summary, **Then** it shows "GST Refund: $X,XXX".

4. **Given** I am satisfied with the figures, **When** I click "Mark Ready for Review", **Then** the BAS session status changes to "Ready for Review".

5. **Given** there are unresolved critical issues, **When** I try to mark ready, **Then** I see a blocking warning with the issues that must be resolved.

---

### User Story 6: Working Paper Export (Priority: P3)

As an accountant, I want to export BAS working papers, so that I have documentation for the client file and potential ATO audit.

**Why this priority**: Export is important for compliance but not blocking for the preparation workflow itself.

**Independent Test**: Can verify by exporting and checking the document contains all BAS figures with supporting detail.

**Acceptance Scenarios:**

1. **Given** a BAS session exists, **When** I click "Export Working Papers", **Then** I can download a PDF with:
   - Client name and ABN
   - BAS period
   - All calculated figures with breakdowns
   - Variance analysis summary
   - Preparer name and timestamp

2. **Given** I want Excel format, **When** I select "Export as Excel", **Then** I get a spreadsheet with:
   - Summary sheet with BAS figures
   - Detail sheets for GST transactions
   - Detail sheets for payroll data

3. **Given** a BAS session is marked "Ready for Review", **When** I export, **Then** the export is stamped as "Final" with audit timestamp.

---

### User Story 7: Adjustment Recording (Priority: P3)

As an accountant, I want to record manual adjustments to calculated figures, so that I can account for items not in Xero data.

**Why this priority**: Adjustments are occasional edge cases; the automated calculation handles 90%+ of scenarios.

**Independent Test**: Can verify by adding an adjustment and confirming the total reflects the change.

**Acceptance Scenarios:**

1. **Given** I need to adjust a GST figure, **When** I click "Add Adjustment" on any line, **Then** I can enter:
   - Adjustment amount (positive or negative)
   - Reason/description
   - Supporting reference (optional)

2. **Given** an adjustment is recorded, **When** I view the line item, **Then** I see both calculated and adjusted totals.

3. **Given** adjustments exist, **When** I export working papers, **Then** adjustments are clearly listed with reasons.

4. **Given** I want to remove an adjustment, **When** I delete it, **Then** the original calculated figure is restored.

---

### Edge Cases

- **What happens when Xero data is stale?** Show warning banner with "Last synced X hours ago" and prompt to sync before finalizing.
- **What happens when there are no transactions for a quarter?** Show empty BAS with all zeros; allow to proceed (valid scenario for dormant companies).
- **What happens when GST codes are missing?** Show uncategorized transactions requiring manual review before calculations are final.
- **What happens when the calculation takes too long?** Background task with progress indicator; timeout at 60 seconds with error message.
- **What happens when prior period data doesn't exist?** Variance analysis shows "N/A" for comparisons.
- **What happens when a user tries to edit a finalized BAS?** Block edits; require "Reopen" action which creates audit trail entry.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST calculate GST amounts from synced Xero invoices and bank transactions for the selected BAS period.

- **FR-002**: System MUST correctly categorize transactions by tax type (OUTPUT, INPUT, BASEXCLUDED, EXEMPTEXPENSES, EXEMPTINCOME, CAPEX, etc.).

- **FR-003**: System MUST aggregate PAYG withholding (W1, W2) from synced pay run data.

- **FR-004**: System MUST allow only one BAS session per client per quarter (prevent duplicates).

- **FR-005**: System MUST track BAS session status through lifecycle: Draft → In Progress → Ready for Review → Approved → Lodged.

- **FR-006**: System MUST calculate variances against prior quarter and same quarter last year when data exists.

- **FR-007**: System MUST highlight significant variances (>20% warning, >50% critical).

- **FR-008**: System MUST allow manual adjustments with required reason for each adjustment.

- **FR-009**: System MUST export working papers in PDF and Excel formats.

- **FR-010**: System MUST log all BAS-related actions in audit trail.

- **FR-011**: System MUST prevent marking "Ready for Review" if critical data quality issues exist.

- **FR-012**: System MUST support both quarterly and monthly BAS periods (monthly for larger businesses).

### Key Entities

- **BASPeriod**: Represents a BAS quarter (Q1-Q4) or month for a client. Links to XeroConnection, has period dates and lodgement deadline.

- **BASSession**: A preparation session for a specific BAS period. Tracks status, preparer, timestamps, and aggregated calculations.

- **BASCalculation**: Cached GST/PAYG calculation results for a session. Contains G-fields, W-fields, and metadata.

- **BASAdjustment**: Manual adjustment to a calculated field. Contains amount, reason, and who made the adjustment.

- **BASVariance**: Pre-calculated variance data comparing periods. Contains absolute and percentage changes.

---

## Auditing & Compliance Checklist

### Audit Events Required

- [x] **Data Access Events**: BAS figures are sensitive financial compliance data
- [x] **Data Modification Events**: BAS sessions, adjustments, status changes
- [ ] **Authentication Events**: No auth changes in this feature
- [ ] **Integration Events**: Reads from synced data, no new integrations
- [x] **Compliance Events**: BAS preparation is a compliance workflow

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| `bas.session.created` | New BAS session | Client ID, period, preparer | 10 years | None |
| `bas.session.status_changed` | Status transition | Before/after status, actor | 10 years | None |
| `bas.calculation.performed` | GST calculation run | Calculation summary, duration | 7 years | None |
| `bas.adjustment.created` | Manual adjustment added | Amount, reason, actor | 10 years | None |
| `bas.adjustment.deleted` | Adjustment removed | Adjustment details, actor | 10 years | None |
| `bas.export.generated` | Working paper export | Export format, actor | 5 years | None |
| `bas.session.approved` | Marked approved | All figures, approver | 10 years | None |

### Compliance Considerations

- **ATO Requirements**: BAS records must be retained for 5 years minimum; recommend 10 years for full audit protection.
- **Data Retention**: All BAS calculations, adjustments, and status changes must be retained with full history.
- **Access Logging**: Only authorized tenant users should access BAS data; all access must be logged.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: BAS preparation time reduced by >50% compared to manual process (target: <1 hour per client)
- **SC-002**: GST calculations match Xero's BAS report within 0.1% accuracy
- **SC-003**: Variance analysis catches 90%+ of significant period-over-period changes
- **SC-004**: 95%+ of BAS sessions can be completed without manual adjustments
- **SC-005**: Working paper exports meet ATO documentation requirements

---

## Non-Functional Requirements

### Performance

1. GST calculation SHALL complete within 10 seconds for clients with up to 5,000 transactions per quarter.

2. BAS summary page SHALL load within 3 seconds for any client.

3. Export generation SHALL complete within 30 seconds for PDF, 15 seconds for Excel.

### Accuracy

1. GST calculations SHALL be deterministic - same data produces identical results.

2. Rounding SHALL follow ATO guidelines (round to nearest dollar for BAS fields).

3. Tax type mapping SHALL handle all Xero tax codes correctly.

### Security

1. BAS data SHALL be tenant-isolated via RLS.

2. BAS sessions SHALL only be accessible by tenant members.

3. All BAS actions SHALL be logged in audit trail.

### Availability

1. BAS calculation tasks SHALL retry on failure (max 3 retries).

2. Calculation results SHALL be cached to prevent repeated computation.

---

## Out of Scope

The following items are explicitly out of scope for this specification:

1. **ATO Lodgement** - Submitting BAS to ATO (Spec 010-012)
2. **Review/Approval Workflow** - Multi-user approval process (Spec 010)
3. **Client Portal View** - Business owner viewing BAS (Layer 2)
4. **AI-Powered Suggestions** - Smart recommendations for issues (Layer 3)
5. **Batch BAS Preparation** - Preparing multiple clients at once (future enhancement)
6. **Installment Activity Statement (IAS)** - Monthly PAYG instalments (future)
7. **FBT Calculations** - Fringe Benefits Tax (out of BAS scope)

---

## Dependencies

| Dependency | Description | Status |
|------------|-------------|--------|
| Spec 008: Data Quality Scoring | Quality scores for BAS readiness checks | COMPLETE |
| Spec 007: Xero Payroll Sync | PAYG data for W1/W2 fields | COMPLETE |
| Spec 004: Xero Data Sync | Invoice/transaction data for GST | COMPLETE |
| XeroInvoice model | Invoice data with tax types | Available |
| XeroBankTransaction model | Transaction data with tax types | Available |
| XeroPayRun model | Pay run data for PAYG | Available |
| XeroAccount model | Chart of accounts for categorization | Available |

---

## Data Model Additions

### BASPeriod Table

```sql
CREATE TABLE bas_periods (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    connection_id UUID NOT NULL REFERENCES xero_connections(id),

    -- Period identification
    period_type VARCHAR(10) NOT NULL,  -- 'quarterly' or 'monthly'
    quarter INTEGER,                    -- 1-4 for quarterly, NULL for monthly
    month INTEGER,                      -- 1-12 for monthly, NULL for quarterly
    fy_year INTEGER NOT NULL,          -- Financial year (e.g., 2025)

    -- Period dates
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    due_date DATE NOT NULL,            -- ATO lodgement deadline

    -- Unique constraint
    UNIQUE(connection_id, fy_year, quarter),
    UNIQUE(connection_id, fy_year, month)
);
```

### BASSession Table

```sql
CREATE TABLE bas_sessions (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    period_id UUID NOT NULL REFERENCES bas_periods(id),

    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    -- draft, in_progress, ready_for_review, approved, lodged

    -- Preparer information
    created_by UUID NOT NULL REFERENCES users(id),
    last_modified_by UUID REFERENCES users(id),
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,

    -- Calculation cache
    gst_calculated_at TIMESTAMPTZ,
    payg_calculated_at TIMESTAMPTZ,

    -- Notes
    internal_notes TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Only one session per period
    UNIQUE(period_id)
);
```

### BASCalculation Table

```sql
CREATE TABLE bas_calculations (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    session_id UUID NOT NULL REFERENCES bas_sessions(id),

    -- G-fields (GST)
    g1_total_sales NUMERIC(15,2) NOT NULL DEFAULT 0,
    g2_export_sales NUMERIC(15,2) NOT NULL DEFAULT 0,
    g3_gst_free_sales NUMERIC(15,2) NOT NULL DEFAULT 0,
    g10_capital_purchases NUMERIC(15,2) NOT NULL DEFAULT 0,
    g11_non_capital_purchases NUMERIC(15,2) NOT NULL DEFAULT 0,

    -- Calculated GST fields
    field_1a_gst_on_sales NUMERIC(15,2) NOT NULL DEFAULT 0,
    field_1b_gst_on_purchases NUMERIC(15,2) NOT NULL DEFAULT 0,

    -- PAYG fields
    w1_total_wages NUMERIC(15,2) NOT NULL DEFAULT 0,
    w2_amount_withheld NUMERIC(15,2) NOT NULL DEFAULT 0,

    -- Summary
    gst_payable NUMERIC(15,2) NOT NULL DEFAULT 0,  -- 1A - 1B
    total_payable NUMERIC(15,2) NOT NULL DEFAULT 0,  -- GST + W2

    -- Calculation metadata
    calculated_at TIMESTAMPTZ NOT NULL,
    calculation_duration_ms INTEGER,
    transaction_count INTEGER,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(session_id)
);
```

### BASAdjustment Table

```sql
CREATE TABLE bas_adjustments (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    session_id UUID NOT NULL REFERENCES bas_sessions(id),

    -- Adjustment details
    field_name VARCHAR(50) NOT NULL,  -- e.g., 'g1_total_sales', 'field_1a'
    adjustment_amount NUMERIC(15,2) NOT NULL,
    reason TEXT NOT NULL,
    reference VARCHAR(255),  -- Optional reference

    -- Actor
    created_by UUID NOT NULL REFERENCES users(id),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## BAS Fields Reference

### GST Fields (Goods and Services Tax)

| Field | Name | Description |
|-------|------|-------------|
| G1 | Total sales | All sales including GST |
| G2 | Export sales | GST-free exports |
| G3 | GST-free sales | Other GST-free supplies |
| G10 | Capital purchases | Purchases of capital items |
| G11 | Non-capital purchases | Other purchases |
| 1A | GST on sales | GST collected from customers |
| 1B | GST on purchases | GST paid to suppliers |

### PAYG Fields (Pay As You Go Withholding)

| Field | Name | Description |
|-------|------|-------------|
| W1 | Total salary/wages | Gross payments to employees |
| W2 | Withholding | Tax withheld from employees |

### Status Lifecycle

```
Draft → In Progress → Ready for Review → Approved → Lodged
  │         │              │                │          │
  │         │              │                │          └── BAS submitted to ATO
  │         │              │                └── Manager approved
  │         │              └── Preparer finished
  │         └── Calculations started
  └── Session created
```

---

## Glossary

| Term | Definition |
|------|------------|
| **BAS** | Business Activity Statement - quarterly (or monthly) tax report to ATO |
| **GST** | Goods and Services Tax - 10% consumption tax in Australia |
| **PAYG** | Pay As You Go - tax withholding from employee wages |
| **1A** | GST collected on sales (liability to ATO) |
| **1B** | GST paid on purchases (credit from ATO) |
| **G-fields** | GST breakdown fields (G1-G11) on the BAS form |
| **W-fields** | PAYG withholding fields (W1-W5) on the BAS form |
| **FY Year** | Financial year (July-June in Australia) |
| **Quarter** | Q1=Jul-Sep, Q2=Oct-Dec, Q3=Jan-Mar, Q4=Apr-Jun |
