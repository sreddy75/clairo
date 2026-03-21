# Requirements Document: Data Quality Scoring

## Introduction

This document defines the requirements for the Data Quality Scoring feature in Clairo. Building upon the completed Multi-Client Dashboard (Spec 006) and Payroll Sync (Spec 007), this feature provides accountants with an automated assessment of each client's data quality and BAS readiness, enabling them to identify and address data issues before BAS preparation begins.

Data Quality Scoring completes Milestone M3 (Quality Engine) and delivers a key differentiator for Clairo: proactive identification of data problems that would otherwise delay or complicate BAS lodgement.

**Key Context:**
- Multi-Client Dashboard complete (Spec 006) - shows all clients with BAS status
- Payroll Sync complete (Spec 007) - PAYG data available (W1, W2 fields)
- Data exists in: XeroConnection, XeroInvoice, XeroBankTransaction, XeroAccount, XeroEmployee, XeroPayRun tables
- Quarter utility functions available for BAS period calculations
- Multi-tenant architecture with RLS enforced

---

## Problem Statement

Accountants currently discover data quality issues **during** BAS preparation, leading to:
- Last-minute scrambling to reconcile transactions
- Delayed lodgements due to missing information
- Client communication bottlenecks ("we need your missing invoices")
- Increased error risk when rushing to meet deadlines

Clairo solves this by **proactively scoring** data quality and surfacing issues **before** BAS preparation begins, giving accountants time to address problems.

---

## Requirements

### Requirement 1: Quality Score Calculation

**User Story:** As an accountant, I want to see a data quality score for each client business, so that I can quickly identify which clients need data cleanup before BAS preparation.

#### Acceptance Criteria

1. WHEN viewing a client business THEN the system SHALL calculate and display a quality score from 0-100%.

2. THE quality score SHALL be calculated based on the following dimensions:

   | Dimension | Weight | Description |
   |-----------|--------|-------------|
   | **Data Freshness** | 20% | How recently was data synced from Xero? |
   | **Reconciliation** | 30% | What percentage of bank transactions are reconciled? |
   | **Categorization** | 20% | What percentage of transactions have valid GST codes? |
   | **Completeness** | 15% | Are invoices, transactions, and accounts all present? |
   | **PAYG Readiness** | 15% | If payroll enabled, is PAYG data complete? |

3. WHEN calculating the Data Freshness dimension THEN the system SHALL score as:
   - 100%: Synced within 24 hours
   - 75%: Synced within 48 hours
   - 50%: Synced within 7 days
   - 25%: Synced within 30 days
   - 0%: Not synced in 30+ days

4. WHEN calculating the Reconciliation dimension THEN the system SHALL:
   - Count bank transactions in the BAS quarter
   - Calculate percentage that are reconciled (have matching invoice/payment)
   - Score = (reconciled_count / total_count) * 100

5. WHEN calculating the Categorization dimension THEN the system SHALL:
   - Count all invoices and bank transactions in the quarter
   - Check that each has a valid tax type (GST, GST Free, BAS Excluded, etc.)
   - Score = (categorized_count / total_count) * 100

6. WHEN calculating the Completeness dimension THEN the system SHALL check:
   - Has at least one synced account (Chart of Accounts)
   - Has invoices OR bank transactions for the quarter
   - Has contact records synced
   - Score based on presence of required data types

7. WHEN calculating the PAYG Readiness dimension THEN the system SHALL:
   - If `has_payroll_access = false`, score this dimension as 100% (N/A - not applicable)
   - If `has_payroll_access = true`, check for pay runs in the quarter
   - Score = 100% if pay runs exist, 50% if employees exist but no pay runs, 0% if expected but missing

8. WHEN displaying the quality score THEN the system SHALL show:
   - Overall score as percentage (0-100%)
   - Color-coded indicator (green >80%, yellow 50-80%, red <50%)
   - Breakdown by dimension (optional drill-down)

---

### Requirement 2: Quality Issues Detection

**User Story:** As an accountant, I want to see specific data quality issues for each client, so that I can take targeted action to fix them.

#### Acceptance Criteria

1. WHEN analyzing a client's data THEN the system SHALL detect and report the following issue types:

   | Issue Code | Severity | Description |
   |------------|----------|-------------|
   | `STALE_DATA` | Warning | Data not synced in 24+ hours |
   | `STALE_DATA_CRITICAL` | Critical | Data not synced in 7+ days |
   | `UNRECONCILED_TXN` | Warning | Bank transactions not reconciled |
   | `MISSING_GST_CODE` | Warning | Invoice/transaction missing GST classification |
   | `INVALID_GST_CODE` | Error | Invoice has invalid or unknown GST code |
   | `NO_INVOICES` | Info | No invoices for the quarter |
   | `NO_TRANSACTIONS` | Info | No bank transactions for the quarter |
   | `MISSING_PAYROLL` | Warning | Payroll enabled but no pay runs synced |
   | `INCOMPLETE_PAYROLL` | Warning | Employees exist but no pay runs for quarter |

2. FOR each detected issue THEN the system SHALL record:
   - Issue code
   - Severity (Critical, Error, Warning, Info)
   - Affected entity type (invoice, transaction, employee, etc.)
   - Affected entity ID (for drill-down)
   - Suggested action to resolve
   - First detected timestamp

3. WHEN displaying issues THEN the system SHALL:
   - Group by severity (Critical first, then Error, Warning, Info)
   - Show count per category
   - Allow filtering by issue type
   - Provide suggested resolution for each issue

4. WHEN an issue is resolved (e.g., transaction is reconciled) THEN the system SHALL:
   - Automatically remove the issue on next quality check
   - Track resolution time for analytics

---

### Requirement 3: Dashboard Quality Integration

**User Story:** As an accountant, I want to see quality scores on the main dashboard, so that I can prioritize clients who need attention.

#### Acceptance Criteria

1. WHEN viewing the Multi-Client Dashboard THEN the system SHALL display:
   - Quality score badge next to each client row
   - Summary card showing count of clients by quality tier (Good, Fair, Poor)
   - Ability to filter/sort by quality score

2. WHEN displaying quality score on dashboard THEN the system SHALL show:
   - Score as percentage
   - Color-coded badge (green/yellow/red)
   - Count of critical issues (if any)

3. WHEN a user clicks on a quality score THEN the system SHALL:
   - Navigate to the client detail page
   - Open the quality tab showing issue breakdown

4. THE dashboard summary SHALL include:
   ```
   +------------------+
   | Quality Overview |
   +------------------+
   | Good (>80%): 12  |
   | Fair (50-80%): 5 |
   | Poor (<50%): 2   |
   +------------------+
   ```

---

### Requirement 4: Client Detail Quality Tab

**User Story:** As an accountant, I want to see detailed quality information for a specific client, so that I can understand and address their data issues.

#### Acceptance Criteria

1. WHEN viewing a client detail page THEN the system SHALL display a "Quality" tab showing:
   - Overall quality score (large, prominent)
   - Score breakdown by dimension
   - List of detected issues
   - Last quality check timestamp
   - Trend indicator (improving, stable, declining)

2. THE quality dimension breakdown SHALL display:
   ```
   +--------------------------------+
   | Data Freshness     | 100% ████ |
   | Reconciliation     |  75% ███░ |
   | Categorization     |  90% ████ |
   | Completeness       | 100% ████ |
   | PAYG Readiness     | N/A  ░░░░ |
   +--------------------------------+
   | Overall Score      |  87%      |
   +--------------------------------+
   ```

3. FOR each issue in the issues list THEN the system SHALL display:
   - Severity icon (color-coded)
   - Issue title and description
   - Affected count (e.g., "15 transactions")
   - Suggested action button
   - "View Details" to see specific records

4. WHEN "View Details" is clicked for an issue THEN the system SHALL:
   - Show a modal or expandable section
   - List specific affected records (invoices, transactions)
   - Provide links to view each record in Xero (external link)

5. WHEN "Dismiss Issue" is clicked THEN the system SHALL:
   - Mark the issue as dismissed for this quarter
   - Record who dismissed it and why (optional note)
   - Exclude from quality score calculation
   - Show dismissed issues in a separate "Dismissed" section

---

### Requirement 5: Quality Score API

**User Story:** As a frontend developer, I need API endpoints to fetch quality scores and issues, so that the UI can display them efficiently.

#### Acceptance Criteria

1. THE API SHALL provide a quality summary endpoint:
   ```
   GET /api/v1/clients/{id}/quality
   Query params: quarter, fy_year
   Response: {
     overall_score: decimal,
     dimensions: {
       data_freshness: { score: decimal, weight: decimal, details: string },
       reconciliation: { score: decimal, weight: decimal, details: string },
       categorization: { score: decimal, weight: decimal, details: string },
       completeness: { score: decimal, weight: decimal, details: string },
       payg_readiness: { score: decimal, weight: decimal, details: string, applicable: bool }
     },
     issue_counts: {
       critical: number,
       error: number,
       warning: number,
       info: number
     },
     last_checked_at: datetime,
     trend: string  // "improving", "stable", "declining"
   }
   ```

2. THE API SHALL provide a quality issues list endpoint:
   ```
   GET /api/v1/clients/{id}/quality/issues
   Query params: quarter, fy_year, severity, issue_type, include_dismissed
   Response: {
     issues: [{
       id: uuid,
       code: string,
       severity: string,
       title: string,
       description: string,
       affected_entity_type: string,
       affected_count: number,
       affected_ids: [uuid],
       suggested_action: string,
       first_detected_at: datetime,
       dismissed: bool,
       dismissed_by: uuid | null,
       dismissed_at: datetime | null,
       dismissed_reason: string | null
     }],
     total: number
   }
   ```

3. THE API SHALL provide an issue dismiss endpoint:
   ```
   POST /api/v1/clients/{id}/quality/issues/{issue_id}/dismiss
   Body: { reason: string }
   Response: { success: bool }
   ```

4. THE API SHALL provide a quality recalculate endpoint:
   ```
   POST /api/v1/clients/{id}/quality/recalculate
   Response: {
     overall_score: decimal,
     issues_found: number,
     calculated_at: datetime
   }
   ```

5. ALL quality API endpoints SHALL:
   - Require authentication
   - Enforce tenant isolation via RLS
   - Generate audit events for quality data access
   - Default to current quarter if not specified

---

### Requirement 6: Automatic Quality Checks

**User Story:** As an accountant, I want quality scores to be automatically updated when data changes, so that I always see the latest status.

#### Acceptance Criteria

1. WHEN a Xero sync completes THEN the system SHALL:
   - Trigger a quality recalculation for the affected client
   - Run as a Celery background task (non-blocking)
   - Update the quality score and issues in the database

2. WHEN a user manually refreshes quality THEN the system SHALL:
   - Recalculate immediately
   - Show progress indicator during calculation
   - Update UI with new results

3. THE system SHALL track quality history by storing:
   - Score snapshots at each calculation
   - Allow trend analysis (improving, stable, declining)
   - Retention: Keep 12 months of quality history

4. QUALITY calculations SHALL be performant:
   - Complete within 5 seconds for typical client
   - Use efficient aggregate queries
   - Cache results until next sync or recalculation

---

### Requirement 7: Bulk Quality Overview

**User Story:** As an accountant, I want to see quality status across all clients at once, so that I can identify patterns and systemic issues.

#### Acceptance Criteria

1. THE dashboard API SHALL include quality data:
   ```
   GET /api/v1/dashboard/clients
   Response includes:
     quality_score: decimal,
     critical_issues: number
   ```

2. THE dashboard summary API SHALL include quality aggregates:
   ```
   GET /api/v1/dashboard/summary
   Response includes:
     quality: {
       avg_score: decimal,
       good_count: number,    // score > 80%
       fair_count: number,    // score 50-80%
       poor_count: number,    // score < 50%
       total_critical_issues: number
     }
   ```

3. WHEN exporting dashboard to CSV THEN the export SHALL include:
   - Quality score column
   - Critical issues count column

---

### Requirement 8: Automated Scheduling

**User Story:** As an accountant, I want the system to automatically keep data fresh and quality scores calculated, so that I don't have to manually trigger syncs for each client.

#### Acceptance Criteria

1. THE system SHALL run a scheduled task daily (at 2:00 AM UTC / 12-1pm AEST) that:
   - Identifies all active Xero connections not synced in 24+ hours
   - Creates a sync job for each stale connection
   - Triggers the sync task for each job
   - Quality scores are automatically calculated after each sync

2. THE scheduler SHALL implement:
   - `sync_all_stale_connections` task for daily batch processing
   - `sync_connection_if_stale` task for on-demand single connection checks
   - Skip connections that already have a sync in progress
   - Log all sync triggers for audit purposes

3. WHEN a sync completes (manual or scheduled) THEN the system SHALL:
   - Calculate quality scores for the last 6 quarters automatically
   - This ensures historical quarters have up-to-date scores
   - Handle per-quarter calculation failures gracefully (log and continue)

4. THE scheduler configuration SHALL be:
   ```
   Schedule: Daily at 2:00 AM UTC (crontab)
   Stale threshold: 24 hours since last_full_sync_at
   Quarters calculated: 6 (current + 5 previous)
   Task queue: clairo-default
   ```

5. THE Celery Beat service SHALL be configured in docker-compose.yml:
   - Runs as a separate container (`clairo-celery-beat`)
   - Persists schedule state
   - Has access to same environment variables as worker

---

## Non-Functional Requirements

### Performance

1. Quality score calculation SHALL complete within 5 seconds for a client with 1000 transactions.

2. Dashboard quality aggregates SHALL be pre-calculated, not computed on every request.

3. Quality recalculation after sync SHALL not block the sync completion response.

### Accuracy

1. Quality scores SHALL be deterministic - same data produces same score.

2. Issue detection SHALL have zero false positives for critical issues.

3. Reconciliation status SHALL accurately reflect Xero's reconciliation state.

### Security

1. Quality data SHALL be tenant-isolated via RLS.

2. Issue dismissal SHALL be audit logged with actor and reason.

3. Quality calculation triggers SHALL be authenticated.

### Auditability

1. ALL quality score changes SHALL be logged with timestamp and trigger reason.

2. Issue dismissals SHALL include actor, reason, and timestamp.

3. Quality data exports SHALL generate audit events.

---

## Auditing & Compliance Checklist

### Audit Events Required

- [x] **Data Access Events**: Quality scores and issues are sensitive compliance data
- [x] **Data Modification Events**: Issue dismissals modify quality state
- [ ] **Authentication Events**: No auth changes in this feature
- [ ] **Integration Events**: Quality reads from synced data but doesn't sync
- [ ] **Compliance Events**: Quality affects BAS readiness status

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| `quality.score.calculated` | Score recalculation | Before/after scores, trigger reason | 7 years | None |
| `quality.issue.dismissed` | Issue dismissal | Issue ID, dismisser, reason | 7 years | None |
| `quality.data.exported` | Quality data export | Export format, row count | 5 years | None |

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: Quality score calculation completes within 5 seconds for 95% of clients
- **SC-002**: 80% of critical issues are resolved before BAS preparation begins
- **SC-003**: Accountants can identify "poor quality" clients in under 10 seconds from dashboard
- **SC-004**: Zero false-positive critical issues reported by users

---

## Out of Scope

The following items are explicitly out of scope for this specification:

1. **Automated issue resolution** - System won't fix issues, only report them
2. **Client notifications** - Notifying business owners of issues (future spec)
3. **Quality thresholds per client** - Custom thresholds (uses standard thresholds)
4. **Historical quality trends dashboard** - Trend visualization (future enhancement)
5. **Machine learning for issue prediction** - AI-based predictions (Layer 3-4)
6. **Integration with Xero to fix issues** - Two-way sync to fix problems

---

## Dependencies

| Dependency | Description | Status |
|------------|-------------|--------|
| Spec 006: Multi-Client Dashboard | Dashboard to display quality scores | COMPLETE |
| Spec 007: Xero Payroll Sync | PAYG data for payroll quality dimension | COMPLETE |
| XeroInvoice model | Invoice data for categorization checks | Available |
| XeroBankTransaction model | Transaction data for reconciliation checks | Available |
| XeroConnection model | Sync timestamps for freshness checks | Available |
| XeroPayRun model | Pay run data for PAYG checks | Available |

---

## Data Model Additions

### QualityScore Table

```sql
CREATE TABLE quality_scores (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    connection_id UUID NOT NULL REFERENCES xero_connections(id),
    quarter INTEGER NOT NULL,
    fy_year INTEGER NOT NULL,

    -- Overall score
    overall_score DECIMAL(5,2) NOT NULL,

    -- Dimension scores
    freshness_score DECIMAL(5,2) NOT NULL,
    reconciliation_score DECIMAL(5,2) NOT NULL,
    categorization_score DECIMAL(5,2) NOT NULL,
    completeness_score DECIMAL(5,2) NOT NULL,
    payg_score DECIMAL(5,2),  -- NULL if not applicable

    -- Metadata
    calculated_at TIMESTAMPTZ NOT NULL,
    calculation_duration_ms INTEGER,

    -- Unique constraint
    UNIQUE(connection_id, quarter, fy_year)
);
```

### QualityIssue Table

```sql
CREATE TABLE quality_issues (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    connection_id UUID NOT NULL REFERENCES xero_connections(id),
    quarter INTEGER NOT NULL,
    fy_year INTEGER NOT NULL,

    -- Issue details
    code VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,  -- critical, error, warning, info
    title VARCHAR(255) NOT NULL,
    description TEXT,
    affected_entity_type VARCHAR(50),
    affected_count INTEGER DEFAULT 0,
    affected_ids JSONB,  -- Array of UUIDs
    suggested_action TEXT,

    -- Lifecycle
    first_detected_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    resolved_at TIMESTAMPTZ,

    -- Dismissal
    dismissed BOOLEAN DEFAULT FALSE,
    dismissed_by UUID REFERENCES users(id),
    dismissed_at TIMESTAMPTZ,
    dismissed_reason TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Quality Tier Definitions

| Tier | Score Range | Color | Meaning |
|------|-------------|-------|---------|
| **Good** | 80-100% | Green | Data is clean, ready for BAS prep |
| **Fair** | 50-79% | Yellow | Some issues need attention |
| **Poor** | 0-49% | Red | Significant data quality problems |

---

## Glossary

| Term | Definition |
|------|------------|
| **Quality Score** | 0-100% rating of client data quality for BAS readiness |
| **Quality Dimension** | One of five scoring categories (freshness, reconciliation, etc.) |
| **Quality Issue** | A specific detected problem in client data |
| **Reconciled** | Bank transaction matched to invoice/payment in Xero |
| **Categorized** | Transaction has valid GST/tax type assigned |
| **PAYG Readiness** | Completeness of payroll data for PAYG withholding |
| **Issue Dismissal** | User action to ignore an issue for the current quarter |
