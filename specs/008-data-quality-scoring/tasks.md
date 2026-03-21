# Implementation Tasks: Data Quality Scoring

## Overview

This document contains the actionable task list for implementing Spec 008: Data Quality Scoring.

**Goal**: Implement automated data quality scoring across five dimensions to help accountants identify and address data issues before BAS preparation.

**Branch**: `feature/008-data-quality-scoring`
**Status**: COMPLETE

---

## Phase 1: Database Schema

### Task 1.1: Create Migration for Quality Tables
- [x] Create Alembic migration file `005_quality_scoring.py`
- [x] Add `quality_scores` table with all columns
- [x] Add `quality_issues` table with all columns
- [x] Add indexes for performance
- [x] Add RLS policies for tenant isolation
- [x] Test migration up/down

**Acceptance Criteria:**
- Migration runs without errors
- RLS policies enforce tenant isolation
- Indexes exist on connection_id, quarter, severity columns

### Task 1.2: Create SQLAlchemy Models
- [x] Create `backend/app/modules/quality/__init__.py`
- [x] Create `backend/app/modules/quality/models.py`
- [x] Define `QualityScore` model
- [x] Define `QualityIssue` model
- [x] Define `IssueSeverity` enum
- [x] Define `IssueCode` enum
- [x] Export models from `__init__.py`

**Acceptance Criteria:**
- Models match database schema
- Enums for severity and issue codes defined
- Relationships to XeroConnection defined

---

## Phase 2: Quality Calculator

### Task 2.1: Create Calculator Base Classes
- [x] Create `backend/app/modules/quality/calculator.py`
- [x] Define `DimensionCalculator` base class
- [x] Define `CalculationResult` dataclass
- [x] Define dimension weight constants

**Acceptance Criteria:**
- Base class provides consistent interface
- Weight constants match spec (20%, 30%, 20%, 15%, 15%)

### Task 2.2: Implement Freshness Calculator
- [x] Create `FreshnessCalculator` class
- [x] Check `last_full_sync_at` timestamp
- [x] Score based on recency thresholds:
  - 100%: < 24 hours
  - 75%: < 48 hours
  - 50%: < 7 days
  - 25%: < 30 days
  - 0%: > 30 days
- [x] Add unit tests

**Acceptance Criteria:**
- Correct scoring for all thresholds
- Handles NULL sync timestamp (score = 0)

### Task 2.3: Implement Reconciliation Calculator
- [x] Create `ReconciliationCalculator` class
- [x] Query bank transactions for quarter
- [x] Count reconciled vs total transactions
- [x] Calculate percentage score
- [x] Add unit tests

**Acceptance Criteria:**
- Correctly identifies reconciled transactions
- Handles zero transactions (score = 100)
- Efficient aggregate query (not N+1)

### Task 2.4: Implement Categorization Calculator
- [x] Create `CategorizationCalculator` class
- [x] Query invoices and bank transactions for quarter
- [x] Check for valid tax_type on each
- [x] Calculate percentage with valid categorization
- [x] Add unit tests

**Acceptance Criteria:**
- Identifies missing/invalid GST codes
- Handles zero records (score = 100)
- Counts both invoices and transactions

### Task 2.5: Implement Completeness Calculator
- [x] Create `CompletenessCalculator` class
- [x] Check for presence of:
  - Accounts (Chart of Accounts synced)
  - Contacts synced
  - Invoices OR transactions for quarter
- [x] Score based on data presence
- [x] Add unit tests

**Acceptance Criteria:**
- Detects missing data types
- Graceful handling of empty connections

### Task 2.6: Implement PAYG Readiness Calculator
- [x] Create `PaygReadinessCalculator` class
- [x] Check `has_payroll_access` flag
- [x] If false, return N/A (excluded from score)
- [x] If true, check for pay runs in quarter
- [x] Score: 100% if pay runs exist, 50% if employees only, 0% if nothing
- [x] Add unit tests

**Acceptance Criteria:**
- Returns NULL/N/A when payroll not applicable
- Correctly checks for pay runs in quarter

### Task 2.7: Create Score Aggregator
- [x] Create `QualityScoreAggregator` class
- [x] Accept all dimension results
- [x] Calculate weighted overall score
- [x] Handle N/A dimensions (redistribute weight)
- [x] Add unit tests

**Acceptance Criteria:**
- Weighted calculation matches spec
- PAYG weight redistributed when not applicable

---

## Phase 3: Issue Detector

### Task 3.1: Create Issue Detector
- [x] Create `backend/app/modules/quality/issue_detector.py`
- [x] Define `IssueDetector` class
- [x] Define issue detection methods for each issue type
- [x] Return list of detected `QualityIssue` objects

**Acceptance Criteria:**
- Detects all issue types from spec
- Includes affected entity IDs

### Task 3.2: Implement Data Freshness Issues
- [x] Detect `STALE_DATA` (>24h since sync)
- [x] Detect `STALE_DATA_CRITICAL` (>7d since sync)
- [x] Add unit tests

### Task 3.3: Implement Reconciliation Issues
- [x] Detect `UNRECONCILED_TXN` with count and IDs
- [x] Include suggested action text
- [x] Add unit tests

### Task 3.4: Implement Categorization Issues
- [x] Detect `MISSING_GST_CODE` for invoices/transactions
- [x] Detect `INVALID_GST_CODE` for unknown tax types
- [x] Add unit tests

### Task 3.5: Implement Completeness Issues
- [x] Detect `NO_INVOICES` for quarter
- [x] Detect `NO_TRANSACTIONS` for quarter
- [x] Add unit tests

### Task 3.6: Implement PAYG Issues
- [x] Detect `MISSING_PAYROLL` when payroll enabled but no data
- [x] Detect `INCOMPLETE_PAYROLL` when employees but no pay runs
- [x] Add unit tests

---

## Phase 4: Repository & Service

### Task 4.1: Create Quality Repository
- [x] Create `backend/app/modules/quality/repository.py`
- [x] Implement `get_score()` method
- [x] Implement `upsert_score()` method
- [x] Implement `get_issues()` method
- [x] Implement `upsert_issues()` method
- [x] Implement `dismiss_issue()` method
- [x] Implement `get_portfolio_quality()` for dashboard

**Acceptance Criteria:**
- Upsert handles insert and update correctly
- Tenant isolation maintained
- Efficient queries with proper indexes

### Task 4.2: Create Quality Service
- [x] Create `backend/app/modules/quality/service.py`
- [x] Implement `calculate_quality()` main method
- [x] Implement `get_quality_summary()` method
- [x] Implement `get_issues()` method
- [x] Implement `dismiss_issue()` method
- [x] Implement `get_portfolio_summary()` for dashboard

**Acceptance Criteria:**
- Calculation uses all calculators
- Results saved to database
- Audit events logged

### Task 4.3: Create Pydantic Schemas
- [x] Create `backend/app/modules/quality/schemas.py`
- [x] Define `QualityScoreResponse` schema
- [x] Define `QualityDimensionResponse` schema
- [x] Define `QualityIssueResponse` schema
- [x] Define `QualityIssuesListResponse` schema
- [x] Define `DismissIssueRequest` schema
- [x] Define `RecalculateResponse` schema

**Acceptance Criteria:**
- All API responses have Pydantic schemas
- Proper validation on request schemas

---

## Phase 5: API Endpoints

### Task 5.1: Create Quality Router
- [x] Create `backend/app/modules/quality/router.py`
- [x] Add `GET /clients/{id}/quality` endpoint
- [x] Add `GET /clients/{id}/quality/issues` endpoint
- [x] Add `POST /clients/{id}/quality/recalculate` endpoint
- [x] Add `POST /clients/{id}/quality/issues/{issue_id}/dismiss` endpoint
- [x] Register router in `main.py`

**Acceptance Criteria:**
- All endpoints return correct status codes
- Authentication required (Clerk tokens)
- RLS enforced

### Task 5.2: Add Integration Tests for Quality API
- [x] Create `backend/tests/integration/api/test_quality_endpoints.py`
- [x] Test GET quality returns correct score
- [x] Test GET issues returns issues list
- [x] Test POST recalculate triggers calculation
- [x] Test POST dismiss marks issue dismissed
- [x] Test RLS blocks cross-tenant access

**Acceptance Criteria:**
- All endpoints tested
- Error cases covered

---

## Phase 6: Celery Integration

### Task 6.1: Create Quality Celery Task
- [x] Create `backend/app/tasks/quality.py`
- [x] Implement `calculate_quality_score` task
- [x] Accept connection_id and trigger_reason
- [x] Call QualityService.calculate_quality()
- [x] Handle errors gracefully
- [x] Calculate for multiple quarters (last 6 quarters)

**Acceptance Criteria:**
- Task runs in background
- Errors logged, don't crash worker
- Multiple quarters calculated automatically

### Task 6.2: Integrate with Sync Task
- [x] Update `backend/app/tasks/xero.py`
- [x] After sync completes, trigger quality calculation
- [x] Pass trigger_reason="sync"
- [x] Quality calc is async, doesn't block sync response

**Acceptance Criteria:**
- Quality calculated after each sync
- Sync response not delayed by quality calc

---

## Phase 7: Dashboard Integration

### Task 7.1: Update Dashboard Summary Schema
- [x] Update `DashboardSummaryResponse` in `clients/schemas.py`
- [x] Add `quality` field with:
  - `avg_score: Decimal`
  - `good_count: int` (>80%)
  - `fair_count: int` (50-80%)
  - `poor_count: int` (<50%)
  - `total_critical_issues: int`

**Acceptance Criteria:**
- Schema includes quality aggregates
- Fields properly typed

### Task 7.2: Update Dashboard Service
- [x] Update `get_dashboard_summary()` in `clients/service.py`
- [x] Query quality scores for all connections
- [x] Calculate aggregates (avg, counts by tier)
- [x] Include in response

**Acceptance Criteria:**
- Quality data in dashboard summary
- Efficient aggregate query

### Task 7.3: Update Dashboard Clients Schema
- [x] Update `DashboardClientItem` schema
- [x] Add `quality_score: Decimal | None`
- [x] Add `critical_issues: int`

### Task 7.4: Update Dashboard Clients Query
- [x] Update `get_dashboard_clients()` query
- [x] LEFT JOIN quality_scores table
- [x] Include quality score in response

**Acceptance Criteria:**
- Each client row includes quality score
- Handles connections with no score (NULL)

---

## Phase 8: Client Detail Integration

### Task 8.1: Update Client Detail Response
- [x] Update `ClientDetailResponse` schema
- [x] Add `quality_score: Decimal | None`
- [x] Add `quality_issues_count: int`

### Task 8.2: Update Client Detail Service
- [x] Update `get_client_detail()` method
- [x] Fetch quality score for connection
- [x] Include in response

**Acceptance Criteria:**
- Quality data in client detail response
- Handles missing score gracefully

---

## Phase 9: Frontend - Quality Components

### Task 9.1: Create QualityBadge Component
- [x] Create `frontend/src/components/quality/QualityBadge.tsx`
- [x] Accept score prop (0-100)
- [x] Display color-coded badge:
  - Green: >80%
  - Yellow: 50-80%
  - Red: <50%
- [x] Show percentage text

**Acceptance Criteria:**
- Correct colors for thresholds
- Accessible (not color-only)

### Task 9.2: Create QualityScoreCard Component
- [x] Create `frontend/src/components/quality/QualityScoreCard.tsx`
- [x] Large score display with color
- [x] Show last calculated timestamp
- [x] Show dimension breakdown
- [x] Circular progress indicator

**Acceptance Criteria:**
- Prominent score display
- Formatted timestamp

### Task 9.3: Create QualityDimensionBreakdown Component
- [x] Integrated into QualityScoreCard component
- [x] Progress bar for each dimension
- [x] Show weight and score
- [x] Handle N/A for PAYG

**Acceptance Criteria:**
- All 5 dimensions displayed
- N/A shown when PAYG not applicable

### Task 9.4: Create QualityIssuesList Component
- [x] Create `frontend/src/components/quality/QualityIssuesList.tsx`
- [x] List issues grouped by severity
- [x] Show severity icon/color
- [x] Dismiss button with confirmation
- [x] View details expandable section

**Acceptance Criteria:**
- Issues sorted by severity
- Dismiss action works
- Affected entities shown

---

## Phase 10: Frontend - Quality Tab

### Task 10.1: Add Quality Tab to Client Detail
- [x] Update `frontend/src/app/(protected)/clients/[id]/page.tsx`
- [x] Add "Quality" tab
- [x] Fetch quality data on tab activation
- [x] Display QualityScoreCard
- [x] Display QualityIssuesList
- [x] Add "Understanding Quality Scores" explanation section

**Acceptance Criteria:**
- Quality tab accessible
- Data loads on tab click
- Loading state shown

### Task 10.2: Add Recalculate Button
- [x] Add "Recalculate" button in Quality tab
- [x] Call POST /quality/recalculate
- [x] Show loading state during recalculation
- [x] Refresh data after completion

**Acceptance Criteria:**
- Button triggers recalculation
- UI updates with new score

### Task 10.3: Quarter-Specific Quality Scores
- [x] Pass selected quarter/fy_year to quality API
- [x] Quality scores vary by quarter
- [x] Recalculate respects selected quarter

**Acceptance Criteria:**
- Quality scores are quarter-specific
- Different quarters show different scores

---

## Phase 11: Dashboard Quality Display

### Task 11.1: Add Quality Badge to Dashboard Table
- [x] Update dashboard table component
- [x] Add Quality column with QualityBadge
- [x] Handle null scores (show "-" or "Not calculated")

**Acceptance Criteria:**
- Quality visible in dashboard table
- Sortable by quality score

### Task 11.2: Add Quality Summary Card
- [x] Add quality summary card to dashboard
- [x] Show Good/Fair/Poor counts
- [x] Show total critical issues
- [x] Color-coded sections

**Acceptance Criteria:**
- Quality overview visible on dashboard
- Counts match actual data

### Task 11.3: Consolidate Dashboard Cards
- [x] Remove redundant Data Quality Overview section
- [x] Consolidate into 4 action-focused cards:
  - Portfolio Health (avg quality, client count)
  - Ready to Lodge (green, quality ≥80%)
  - Needs Attention (yellow/red, combined)
  - No Activity (gray, no transactions)
- [x] Make cards clickable to filter table

**Acceptance Criteria:**
- No redundant information
- Actionable, concise dashboard

---

## Phase 12: Testing & Validation

### Task 12.1: Unit Tests
- [x] Calculator tests with edge cases
- [x] Issue detector tests
- [x] Service method tests

**Acceptance Criteria:**
- Coverage > 80% for quality module
- Edge cases covered

### Task 12.2: Integration Tests
- [x] All API endpoints tested
- [x] RLS enforcement verified
- [x] Celery task integration tested

**Acceptance Criteria:**
- All endpoints return expected data
- Cross-tenant access blocked

### Task 12.3: Manual Verification
- [x] Test with real Xero data (KR8 IT)
- [x] Verify scores match data reality
- [x] Test issue detection accuracy
- [x] Test dismiss workflow

**Acceptance Criteria:**
- Scores make sense for real data
- No false positives on critical issues

---

## Phase 13: Cleanup & Documentation

### Task 13.1: Code Cleanup
- [x] Run `uv run ruff check` - fix any issues
- [x] Run `npm run lint` - fix any issues
- [x] Review code for consistency

### Task 13.2: Update Documentation
- [x] Mark tasks complete in tasks.md
- [x] Update spec.md with scheduler automation

### Task 13.3: Commit & Merge
- [ ] Stage all changes
- [ ] Commit with descriptive message
- [ ] Push branch
- [ ] Merge to main

---

## Phase 14: Automated Scheduling (NEW)

### Task 14.1: Configure Celery Beat
- [x] Create `backend/app/tasks/celery_app.py` beat_schedule
- [x] Add crontab schedule for daily sync (2am UTC)
- [x] Configure task queue options

**Acceptance Criteria:**
- Beat schedule configured correctly
- Runs at 2am UTC daily (12pm/1pm AEST)

### Task 14.2: Create Scheduler Tasks
- [x] Create `backend/app/tasks/scheduler.py`
- [x] Implement `sync_all_stale_connections` task:
  - Find connections not synced in 24+ hours
  - Create sync job for each
  - Trigger sync task
- [x] Implement `sync_connection_if_stale` task:
  - Check single connection staleness
  - Trigger sync if needed

**Acceptance Criteria:**
- Stale connections detected correctly
- Sync jobs created properly
- Quality calculated after each sync

### Task 14.3: Multi-Quarter Quality Calculation
- [x] Update `calculate_quality_score` task
- [x] Calculate for 6 quarters (not just current + previous)
- [x] Handle errors per-quarter gracefully

**Acceptance Criteria:**
- All 6 quarters have quality scores
- Historical quarters calculated on sync

### Task 14.4: Enable Celery Beat Service
- [x] Uncomment celery-beat service in docker-compose.yml
- [x] Add all required environment variables
- [x] Register scheduler tasks in `__init__.py`
- [x] Verify tasks are registered with worker

**Acceptance Criteria:**
- Celery Beat container running
- Tasks registered and scheduled
- Logs show scheduled execution

---

## Verification Checklist

After completion:

- [x] Quality scores calculated for all connections
- [x] Five dimensions correctly weighted
- [x] Issues detected and displayed
- [x] Dashboard shows quality scores
- [x] Client detail has Quality tab
- [x] Recalculate button works
- [x] Issue dismiss workflow works
- [x] RLS enforced on quality tables
- [x] Celery task triggers after sync
- [x] Daily scheduled sync for stale connections
- [x] Quality calculated for 6 quarters automatically

---

## Pending Tasks

- [ ] **Task 13.3**: Commit & merge changes to main branch

---

## Notes

### Quality Score Weights

| Dimension | Weight |
|-----------|--------|
| Data Freshness | 20% |
| Reconciliation | 30% |
| Categorization | 20% |
| Completeness | 15% |
| PAYG Readiness | 15% |

### Issue Severity Levels

| Severity | Color | Priority |
|----------|-------|----------|
| Critical | Red | Address immediately |
| Error | Orange | Address before BAS |
| Warning | Yellow | Review when time permits |
| Info | Blue | Informational only |

### Issue Codes

| Code | Severity | Description |
|------|----------|-------------|
| STALE_DATA | Warning | >24h since sync |
| STALE_DATA_CRITICAL | Critical | >7d since sync |
| UNRECONCILED_TXN | Warning | Unreconciled bank transactions |
| MISSING_GST_CODE | Warning | Missing GST classification |
| INVALID_GST_CODE | Error | Invalid/unknown GST code |
| NO_INVOICES | Info | No invoices for quarter |
| NO_TRANSACTIONS | Info | No transactions for quarter |
| MISSING_PAYROLL | Warning | Payroll enabled, no data |
| INCOMPLETE_PAYROLL | Warning | Employees but no pay runs |

### Scheduler Configuration

| Setting | Value |
|---------|-------|
| Daily sync time | 2:00 AM UTC (12pm/1pm AEST) |
| Stale threshold | 24 hours |
| Quarters calculated | 6 (current + 5 previous) |
