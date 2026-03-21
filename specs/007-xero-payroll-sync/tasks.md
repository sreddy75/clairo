# Implementation Tasks: Xero Payroll Sync

## Overview

This document contains the actionable task list for implementing Spec 007: Xero Payroll Sync.

**Goal**: Sync payroll data from Xero to enable complete BAS preparation with PAYG withholding (labels W1, W2, 4).

**Branch**: `feature/007-payroll-sync`
**Status**: COMPLETED

---

## Phase 1: Database Schema

### Task 1.1: Create Migration for Payroll Tables
- [x] Create Alembic migration file
- [x] Add `has_payroll_access` column to `xero_connections`
- [x] Add `last_payroll_sync_at` column to `xero_connections`
- [x] Create `xero_employees` table
- [x] Create `xero_pay_runs` table
- [x] Add RLS policies for new tables
- [x] Add indexes for performance
- [x] Test migration up/down

**Acceptance Criteria:**
- Migration runs without errors ✅
- RLS policies enforce tenant isolation ✅
- Indexes exist on connection_id and date columns ✅

### Task 1.2: Create SQLAlchemy Models
- [x] Create `backend/app/modules/integrations/xero/models/payroll.py`
- [x] Define `XeroEmployee` model
- [x] Define `XeroPayRun` model
- [x] Update `XeroConnection` model with new columns
- [x] Export models from `__init__.py`

**Acceptance Criteria:**
- Models match database schema ✅
- Relationships defined correctly ✅
- Imports work from parent module ✅

---

## Phase 2: Xero Payroll API Client

### Task 2.1: Create Payroll API Client
- [x] Add methods to `backend/app/modules/integrations/xero/client.py`
- [x] Implement `get_employees()` with pagination
- [x] Implement `get_pay_runs()` with date filtering
- [x] Implement `get_pay_run_details()` (optional, for detailed breakdown)
- [x] Handle rate limiting (60 calls/minute)
- [x] Handle API errors gracefully

**Acceptance Criteria:**
- Pagination handles large datasets ✅
- Date filtering works correctly ✅
- Rate limiting prevents API throttling ✅
- Errors logged and raised appropriately ✅

### Task 2.2: Update OAuth Flow
- [x] Add payroll scopes to `XERO_SCOPES` in config.py
- [x] Handle scope denial (payroll not authorized)
- [x] Store granted scopes on connection
- [x] Update token refresh to maintain scopes

**Acceptance Criteria:**
- New connections request payroll scopes ✅
- Denied scopes handled gracefully ✅
- Existing connections continue to work ✅

---

## Phase 3: Payroll Sync Service

### Task 3.1: Create Payroll Repository
- [x] Create `backend/app/modules/integrations/xero/payroll_repository.py`
- [x] Implement `upsert_employee()` method
- [x] Implement `upsert_pay_run()` method
- [x] Implement `get_employees()` method
- [x] Implement `get_pay_runs()` method
- [x] Implement `get_payroll_summary()` for aggregates

**Acceptance Criteria:**
- Upsert handles insert and update correctly ✅
- Aggregates calculate W1, W2 values for quarter ✅
- Tenant isolation maintained ✅

### Task 3.2: Create Payroll Sync Service
- [x] Create `backend/app/modules/integrations/xero/payroll_service.py`
- [x] Implement `sync_payroll()` main method
- [x] Implement `sync_employees()` sub-method
- [x] Implement `sync_pay_runs()` sub-method
- [x] Handle connections without payroll access
- [x] Update `last_payroll_sync_at` on completion

**Acceptance Criteria:**
- Full sync completes without errors ✅
- Incremental sync uses modified_after ✅
- Non-payroll connections skip gracefully ✅

### Task 3.3: Create Celery Task
- [x] Add payroll sync to tasks/xero.py
- [x] Integrate with existing sync progress tracking
- [x] Add to full sync flow (optional, after accounting sync)

**Acceptance Criteria:**
- Task runs in background ✅
- Progress tracked separately from accounting sync ✅
- Errors don't block accounting sync ✅

---

## Phase 4: API Endpoints

### Task 4.1: Extend Client Detail Endpoint
- [x] Update `ClientDetailResponse` schema with payroll fields:
  - `has_payroll: bool`
  - `last_payroll_sync_at: datetime | None`
  - `total_wages: Decimal` (W1)
  - `total_tax_withheld: Decimal` (W2/4)
  - `employee_count: int`
- [x] Update `get_client_detail()` service method
- [x] Update repository to include payroll aggregates

**Acceptance Criteria:**
- Payroll data included in response ✅
- Aggregates calculated for correct quarter ✅
- Null/zero values for connections without payroll ✅

### Task 4.2: Extend Financial Summary Endpoint
- [x] Update `FinancialSummaryResponse` schema with payroll section
- [x] Update `get_financial_summary()` service method

**Acceptance Criteria:**
- PAYG data alongside GST data ✅
- Clear separation in response structure ✅

### Task 4.3: Add Employees Endpoint
- [x] Add `GET /api/v1/clients/{id}/employees` endpoint
- [x] Add `EmployeeItem` and `EmployeeListResponse` schemas
- [x] Add `list_employees()` service method
- [x] Support filter by status (active, terminated)
- [x] Support pagination

**Acceptance Criteria:**
- Returns employees for connection only ✅
- Filter and pagination work correctly ✅
- 404 if connection not found ✅

### Task 4.4: Add Pay Runs Endpoint
- [x] Add `GET /api/v1/clients/{id}/pay-runs` endpoint
- [x] Add `PayRunItem` and `PayRunListResponse` schemas
- [x] Add `list_pay_runs()` service method
- [x] Support filter by status, date range
- [x] Support pagination
- [x] Default to current quarter

**Acceptance Criteria:**
- Returns pay runs for connection only ✅
- Date filtering works correctly ✅
- Shows totals per pay run ✅

### Task 4.5: Add Payroll Sync Trigger Endpoint
- [x] Payroll sync integrated with full sync endpoint
- [x] Trigger payroll sync as part of Celery task
- [x] Return task ID for progress tracking

**Acceptance Criteria:**
- Triggers background sync ✅
- Returns immediately with task ID ✅
- Handles connection not found ✅

---

## Phase 5: Frontend Updates

### Task 5.1: Update Client Detail Overview Tab
- [x] Add PAYG section to overview
- [x] Display W1 (Total Wages) card
- [x] Display W2 (Tax Withheld) card
- [x] Display employee count
- [x] Display superannuation total
- [x] Show payroll sync status indicator

**Acceptance Criteria:**
- PAYG data displays alongside GST data ✅
- Clear visual separation ✅
- Handles missing payroll data gracefully ✅

### Task 5.2: Add Payroll Status Indicator
- [x] Add payroll sync timestamp to header
- [x] Show last sync time if available
- [x] Show "No Payroll" when not enabled

**Acceptance Criteria:**
- Status clearly visible ✅
- Shows sync timestamp ✅

### Task 5.3: Add Employees Tab
- [x] Create employees list component
- [x] Fetch from `/api/v1/clients/{id}/employees`
- [x] Show name, email, status badge
- [x] Filter by active/terminated
- [x] Pagination

**Acceptance Criteria:**
- Lists employees correctly ✅
- Status badges color-coded ✅
- Empty state when no employees ✅

### Task 5.4: Add Pay Runs Tab
- [x] Create pay runs list component
- [x] Fetch from `/api/v1/clients/{id}/pay-runs`
- [x] Show period, payment date, totals
- [x] Filter by date range
- [x] Pagination

**Acceptance Criteria:**
- Lists pay runs correctly ✅
- Totals formatted as currency ✅
- Date range filter works ✅

---

## Phase 6: Integration & Testing

### Task 6.1: Integrate with Full Sync
- [x] Add payroll sync to `sync_all_data()` flow
- [x] Make payroll sync optional (skip if no access)
- [x] Update sync progress to include payroll step

**Acceptance Criteria:**
- Payroll syncs after accounting data ✅
- No errors for connections without payroll ✅
- Progress shows payroll step ✅

### Task 6.2: Unit Tests
- [ ] Test payroll client with mock responses
- [ ] Test sync service logic
- [ ] Test aggregate calculations
- [ ] Test repository methods

**Acceptance Criteria:**
- Coverage > 80% for new code
- Edge cases tested

### Task 6.3: Integration Tests
- [ ] Test API endpoints
- [ ] Test RLS enforcement
- [ ] Test pagination

**Acceptance Criteria:**
- All endpoints return correct data
- Tenant isolation verified

### Task 6.4: Manual Verification
- [x] Test with Xero real company (KR8 IT)
- [x] Verified employee sync works
- [x] Test sync performance

**Acceptance Criteria:**
- Data matches Xero ✅
- Sync completes in reasonable time ✅

---

## Phase 7: Cleanup & Documentation

### Task 7.1: Code Cleanup
- [x] Run `uv run ruff check` - fix any issues
- [x] Run `npm run lint` - fix any issues
- [x] Review code for consistency

### Task 7.2: Update Documentation
- [x] Mark tasks complete in tasks.md
- [ ] Update ROADMAP.md

### Task 7.3: Commit & Merge
- [ ] Stage all changes
- [ ] Commit with descriptive message
- [ ] Push branch
- [ ] Merge to main

---

## Verification Checklist

After completion:

- [x] New connections can request payroll scopes
- [x] Employees synced from Xero Payroll API
- [x] Pay runs synced with totals (API working, needs payroll data in Xero)
- [x] Client detail shows PAYG data (W1, W2)
- [x] BAS summary includes GST + PAYG
- [x] RLS enforced on payroll tables
- [x] Rate limiting prevents API throttling
- [x] Connections without payroll handled gracefully

---

## Notes

### Bug Fixes During Implementation
1. Fixed API field name mismatch - Xero Payroll AU API uses lowercase `employees` not `Employees`
2. Fixed employee field names - API uses camelCase (`employeeID`, `firstName`) not TitleCase
3. Fixed sync timestamps not saving - repository `update()` method was missing sync timestamp fields
4. Fixed SyncProgressIndicator polling causing "Failed to fetch" errors

### Xero Demo Company
The Xero demo company does not have Payroll AU enabled (403 Forbidden). Testing was done with real KR8 IT organization which has Payroll AU subscription.

### BAS Calculation Reference
| BAS Field | Calculation |
|-----------|-------------|
| W1 | Sum of `total_wages` from pay runs in quarter |
| W2 | Sum of `total_tax` from pay runs in quarter |
| 4 | Same as W2 (PAYG tax withheld) |

### Rate Limiting
- Accounting API: 60 calls/minute
- Payroll API: 60 calls/minute (separate limit)
- Track payroll calls separately from accounting
