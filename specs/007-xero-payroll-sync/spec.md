# Spec 007: Xero Payroll Sync

## Overview

**Goal**: Extend Xero data synchronization to include payroll data required for complete BAS lodgement, specifically PAYG withholding amounts (BAS labels W1, W2, and 4).

**Problem Statement**: Currently, Clairo syncs GST-related data (invoices, bank transactions, accounts) from Xero. However, for businesses with employees, a complete BAS requires PAYG withholding data which comes from payroll:
- **Label W1**: Total of salary, wages and other payments
- **Label W2**: Amounts withheld from salary, wages and other payments
- **Label 4**: PAYG tax withheld from payments shown at W2

Without payroll data, Clairo can only prepare partial BAS statements for businesses with employees.

**Success Criteria**:
- Payroll data synced from Xero Payroll API
- BAS summary includes PAYG withholding amounts for the quarter
- Client detail view shows payroll status and totals
- Dashboard aggregates payroll data alongside GST data

---

## Context

### BAS Requirements (ATO)

The Business Activity Statement includes:

| Section | Label | Description | Data Source |
|---------|-------|-------------|-------------|
| GST | 1A | Total sales (incl. GST) | Invoices (ACCREC) |
| GST | 1B | GST on sales | Invoices (ACCREC) |
| GST | 11 | Total purchases (incl. GST) | Invoices (ACCPAY) + Bank Transactions |
| GST | 12 | GST on purchases | Invoices (ACCPAY) + Bank Transactions |
| **PAYG** | **W1** | **Total wages paid** | **Pay Runs** |
| **PAYG** | **W2** | **Amounts withheld** | **Pay Runs** |
| **PAYG** | **4** | **PAYG tax withheld** | **Pay Runs** |
| FTC | 7A-7D | Fuel tax credits | Manual/Other |

### Xero Payroll API (AU)

Xero provides a separate Payroll API for Australian businesses:

**Base URL**: `https://api.xero.com/payroll.xro/2.0/`

**Key Endpoints**:
| Endpoint | Purpose |
|----------|---------|
| `GET /Employees` | List all employees |
| `GET /PayRuns` | List pay runs with summary |
| `GET /PayRuns/{PayRunID}` | Pay run details including payslips |
| `GET /Timesheets` | Employee timesheets |
| `GET /SuperFunds` | Superannuation fund details |
| `GET /PayItems` | Earnings rates, deduction types, etc. |
| `GET /Settings` | Payroll settings |

**Required OAuth Scopes**: `payroll.employees`, `payroll.payruns`, `payroll.settings`

### Data Model Extension

New entities required:

```
XeroEmployee
├── id (UUID, PK)
├── connection_id (FK → XeroConnection)
├── xero_employee_id (UUID, unique per connection)
├── first_name, last_name
├── email
├── status (active, terminated)
├── start_date
├── termination_date
├── ordinary_earnings_rate_id
├── tax_file_number_status
├── created_at, updated_at

XeroPayRun
├── id (UUID, PK)
├── connection_id (FK → XeroConnection)
├── xero_pay_run_id (UUID, unique per connection)
├── payroll_calendar_id
├── pay_run_status (draft, posted)
├── pay_run_period_start
├── pay_run_period_end
├── payment_date
├── total_wages (decimal) ─────────────→ W1
├── total_tax (decimal) ───────────────→ W2/4
├── total_super (decimal)
├── total_deductions (decimal)
├── total_reimbursements (decimal)
├── created_at, updated_at

XeroPayslip (optional - for detailed breakdown)
├── id (UUID, PK)
├── pay_run_id (FK → XeroPayRun)
├── employee_id (FK → XeroEmployee)
├── xero_payslip_id (UUID)
├── gross_earnings (decimal)
├── tax_amount (decimal)
├── net_pay (decimal)
├── super_amount (decimal)
├── created_at, updated_at
```

---

## Requirements

### Functional Requirements

#### FR-1: Payroll Connection Scope
- When connecting to Xero, request payroll scopes in addition to accounting scopes
- Handle cases where payroll access is denied (business has no payroll or not authorized)
- Store payroll authorization status on XeroConnection

#### FR-2: Employee Sync
- Fetch all employees from Xero Payroll API
- Store employee details including status and tax file number status
- Track active vs terminated employees
- Sync periodically alongside other data

#### FR-3: Pay Run Sync
- Fetch pay runs for the current and previous financial year
- Store summary totals for each pay run
- Calculate quarterly aggregates for BAS labels:
  - W1: Sum of `total_wages` for pay runs in quarter
  - W2/4: Sum of `total_tax` for pay runs in quarter
- Optionally sync individual payslips for detailed breakdown

#### FR-4: BAS Summary Enhancement
- Extend financial summary to include PAYG withholding:
  - `total_wages` (W1)
  - `total_tax_withheld` (W2/4)
- Show payroll status indicator (has payroll, no payroll, payroll not synced)
- Display PAYG data alongside GST data in client detail view

#### FR-5: Dashboard Enhancement
- Add PAYG columns to dashboard (optional, as secondary data)
- Show businesses with payroll vs without
- Flag businesses missing payroll sync where expected

#### FR-6: Rate Limit Handling
- Xero Payroll API has separate rate limits (60 calls/minute)
- Implement appropriate throttling
- Use efficient batch fetching where possible

### Non-Functional Requirements

#### NFR-1: Data Privacy
- Payroll data is sensitive PII (names, TFN status, salaries)
- Ensure RLS applies to all payroll tables
- Log access to payroll endpoints
- Consider field-level encryption for sensitive data

#### NFR-2: Sync Efficiency
- Only sync pay runs from relevant period (current FY + 1 quarter back)
- Skip payroll sync for connections without payroll enabled
- Track last sync timestamp separately for payroll

#### NFR-3: Backward Compatibility
- Existing connections without payroll scope should continue to work
- Add ability to request additional scopes for existing connections

---

## Technical Design

### Database Schema

```sql
-- Track if connection has payroll access
ALTER TABLE xero_connections ADD COLUMN has_payroll_access BOOLEAN DEFAULT FALSE;
ALTER TABLE xero_connections ADD COLUMN last_payroll_sync_at TIMESTAMPTZ;

-- Employees table
CREATE TABLE xero_employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    connection_id UUID NOT NULL REFERENCES xero_connections(id) ON DELETE CASCADE,
    xero_employee_id UUID NOT NULL,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    email VARCHAR(255),
    status VARCHAR(50), -- 'active', 'terminated'
    start_date DATE,
    termination_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(connection_id, xero_employee_id)
);

-- Pay runs table
CREATE TABLE xero_pay_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    connection_id UUID NOT NULL REFERENCES xero_connections(id) ON DELETE CASCADE,
    xero_pay_run_id UUID NOT NULL,
    pay_run_status VARCHAR(50), -- 'draft', 'posted'
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    payment_date DATE NOT NULL,
    total_wages DECIMAL(15, 2) DEFAULT 0,
    total_tax DECIMAL(15, 2) DEFAULT 0,
    total_super DECIMAL(15, 2) DEFAULT 0,
    total_deductions DECIMAL(15, 2) DEFAULT 0,
    total_reimbursements DECIMAL(15, 2) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(connection_id, xero_pay_run_id)
);

-- RLS Policies
ALTER TABLE xero_employees ENABLE ROW LEVEL SECURITY;
ALTER TABLE xero_pay_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_employees ON xero_employees
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

CREATE POLICY tenant_isolation_pay_runs ON xero_pay_runs
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Indexes for performance
CREATE INDEX idx_xero_employees_connection ON xero_employees(connection_id);
CREATE INDEX idx_xero_pay_runs_connection ON xero_pay_runs(connection_id);
CREATE INDEX idx_xero_pay_runs_period ON xero_pay_runs(connection_id, period_start, period_end);
```

### API Endpoints

#### Existing Endpoints (Enhanced)

```
GET /api/v1/clients/{id}
Response adds:
{
  ...existing fields...
  "has_payroll": true,
  "last_payroll_sync_at": "2025-01-15T10:00:00Z",
  "total_wages": 125000.00,    // W1 for quarter
  "total_tax_withheld": 35000.00,  // W2/4 for quarter
  "employee_count": 5
}

GET /api/v1/clients/{id}/summary
Response adds:
{
  ...existing fields...
  "payroll": {
    "has_payroll": true,
    "total_wages": 125000.00,
    "total_tax_withheld": 35000.00,
    "total_super": 12500.00,
    "pay_run_count": 3
  }
}
```

#### New Endpoints

```
GET /api/v1/clients/{id}/employees
- List employees for a connection
- Filter: status (active, terminated)
- Pagination: page, limit

GET /api/v1/clients/{id}/pay-runs
- List pay runs for a connection
- Filter: status (draft, posted), date range
- Default: current quarter
- Pagination: page, limit

POST /api/v1/integrations/xero/{connection_id}/sync/payroll
- Trigger payroll data sync
- Returns task ID for progress tracking
```

### Sync Logic

```python
async def sync_payroll(connection_id: UUID):
    """Sync payroll data from Xero."""

    # 1. Check if connection has payroll scope
    connection = await get_connection(connection_id)
    if not connection.has_payroll_access:
        return {"status": "skipped", "reason": "no_payroll_access"}

    # 2. Get access token
    token = await get_valid_token(connection)

    # 3. Sync employees
    employees = await fetch_xero_employees(token)
    await upsert_employees(connection_id, employees)

    # 4. Sync pay runs (current FY + 1 quarter back)
    pay_runs = await fetch_xero_pay_runs(
        token,
        from_date=get_sync_start_date(),
        to_date=datetime.now()
    )
    await upsert_pay_runs(connection_id, pay_runs)

    # 5. Update sync timestamp
    await update_payroll_sync_timestamp(connection_id)

    return {"status": "complete", "employees": len(employees), "pay_runs": len(pay_runs)}
```

---

## UI Changes

### Client Detail Page

**Overview Tab** - Add PAYG section:
```
┌─────────────────────────────────────────────────────────────┐
│ Q2 FY25 Financial Summary                                   │
├─────────────────────────────────────────────────────────────┤
│ GST                           │ PAYG Withholding            │
│ ┌───────────┬───────────────┐ │ ┌───────────┬─────────────┐ │
│ │ Sales     │ $150,000.00   │ │ │ Wages (W1)│ $125,000.00 │ │
│ │ GST (1B)  │ $15,000.00    │ │ │ Tax (W2)  │ $35,000.00  │ │
│ │ Purchases │ $80,000.00    │ │ │ Super     │ $12,500.00  │ │
│ │ GST (11)  │ $8,000.00     │ │ │ Employees │ 5           │ │
│ │ Net GST   │ $7,000.00     │ │ └───────────┴─────────────┘ │
│ └───────────┴───────────────┘ │                             │
└─────────────────────────────────────────────────────────────┘
```

**New Tab** - Employees (optional):
- List employees with status badges
- Show start date, termination date
- Link to Xero for full details

**New Tab** - Pay Runs (optional):
- List pay runs with totals
- Filter by date range, status
- Expandable to show pay run breakdown

### Dashboard

Add optional columns:
- "Has Payroll" indicator
- "PAYG Status" (synced, not synced, N/A)

---

## Implementation Phases

### Phase 1: Database & Models (Backend)
1. Create Alembic migration for new tables
2. Create SQLAlchemy models
3. Add RLS policies
4. Update XeroConnection model

### Phase 2: Xero Payroll API Client
1. Create payroll API client module
2. Implement authentication with payroll scopes
3. Implement employee fetch
4. Implement pay run fetch
5. Handle rate limiting

### Phase 3: Sync Service
1. Create payroll sync service
2. Implement employee upsert logic
3. Implement pay run upsert logic
4. Add Celery task for background sync
5. Integrate with existing sync flow

### Phase 4: API Endpoints
1. Enhance existing client detail endpoint
2. Add employees list endpoint
3. Add pay runs list endpoint
4. Add payroll sync trigger endpoint

### Phase 5: Frontend
1. Update client detail overview with PAYG data
2. Add employees tab (optional)
3. Add pay runs tab (optional)
4. Update dashboard with payroll indicators

### Phase 6: Testing & Validation
1. Unit tests for sync logic
2. Integration tests for API
3. E2E test with Xero demo company
4. Verify BAS calculations

---

## Open Questions

1. **Payslip Detail**: Do we need individual payslip data, or is pay run summary sufficient for BAS?
   - *Recommendation*: Start with pay run summaries only; add payslips if detailed breakdown needed

2. **Scope Request**: Should we request payroll scopes for all new connections, or make it optional?
   - *Recommendation*: Request by default, handle denial gracefully

3. **Historical Data**: How far back should we sync pay runs?
   - *Recommendation*: Current FY + previous FY (for comparison)

4. **Sensitive Data**: Should we encrypt PII fields (names, TFN status)?
   - *Recommendation*: TFN status yes, names can be plain text with RLS

---

## Dependencies

- **Spec 004** (Xero Data Sync): Reuses sync infrastructure, token management, rate limiting
- **Spec 006** (Dashboard): Dashboard will display payroll status

## Blocked By

- None (Spec 006 is complete)

---

## Acceptance Criteria

1. [ ] New connections can authorize payroll access
2. [ ] Employees synced from Xero Payroll API
3. [ ] Pay runs synced with quarterly aggregates
4. [ ] Client detail shows PAYG withholding data (W1, W2/4)
5. [ ] BAS summary includes all required fields for GST + PAYG
6. [ ] RLS enforced on all payroll tables
7. [ ] Rate limiting prevents API throttling
8. [ ] Sync works for connections with and without payroll

---

## References

- [Xero Payroll API (AU)](https://developer.xero.com/documentation/api/payrollau/overview)
- [BAS Form Requirements](https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/activity-statements/business-activity-statements-bas)
- [PAYG Withholding](https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/payg-withholding)
