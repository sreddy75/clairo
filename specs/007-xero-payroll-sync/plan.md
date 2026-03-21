# Implementation Plan: Xero Payroll Sync

## Overview

This plan outlines the implementation approach for syncing payroll data from Xero to enable complete BAS preparation with PAYG withholding information.

**Branch**: `feature/007-payroll-sync`
**Estimated Complexity**: Medium-High
**Dependencies**: Spec 004 (Xero Data Sync) - COMPLETE

---

## Research Summary

### Xero Payroll API Analysis

The Xero Payroll API (AU) is separate from the Accounting API:

| Aspect | Details |
|--------|---------|
| Base URL | `https://api.xero.com/payroll.xro/2.0/` |
| Authentication | Same OAuth2 as Accounting API |
| Required Scopes | `payroll.employees`, `payroll.payruns`, `payroll.settings` |
| Rate Limit | 60 calls/minute (separate from accounting) |
| Pagination | Uses `page` parameter, 100 items per page |
| Modified After | Supports `ModifiedAfter` for incremental sync |

### Key Endpoints

```
GET /Employees
- Returns: EmployeeID, FirstName, LastName, Status, Email, StartDate, etc.
- Pagination: Yes
- Modified After: Yes

GET /PayRuns
- Returns: PayRunID, PayRunStatus, PayRunPeriodStartDate, PayRunPeriodEndDate, PaymentDate
- Includes: Wages, Deductions, Tax, Super summaries
- Pagination: Yes
- Where Clause: PayRunStatus=='POSTED', PaymentDate>=DateTime(2024,01,01)

GET /PayRuns/{PayRunID}
- Returns: Full pay run details including payslips
- Use for: Detailed breakdown (optional)
```

### Data Requirements for BAS

| BAS Label | Description | Xero Source |
|-----------|-------------|-------------|
| W1 | Total salary, wages, other payments | PayRun → sum of Wages |
| W2 | Amounts withheld from payments | PayRun → sum of Tax |
| 4 | PAYG tax withheld | Same as W2 (total tax withheld) |

**Note**: W2 and Label 4 are typically the same value (PAYG withheld).

---

## Implementation Phases

### Phase 1: Database Schema

Create new tables and extend existing ones.

**Files to Create/Modify**:
- `backend/alembic/versions/xxx_add_payroll_tables.py` - Migration

**Schema**:
```sql
-- Extend xero_connections
ALTER TABLE xero_connections ADD COLUMN has_payroll_access BOOLEAN DEFAULT FALSE;
ALTER TABLE xero_connections ADD COLUMN last_payroll_sync_at TIMESTAMPTZ;

-- Create xero_employees
CREATE TABLE xero_employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    connection_id UUID NOT NULL,
    xero_employee_id UUID NOT NULL,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    email VARCHAR(255),
    status VARCHAR(50),
    start_date DATE,
    termination_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(connection_id, xero_employee_id)
);

-- Create xero_pay_runs
CREATE TABLE xero_pay_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    connection_id UUID NOT NULL,
    xero_pay_run_id UUID NOT NULL,
    pay_run_status VARCHAR(50),
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
```

**RLS Policies**: Same pattern as existing Xero tables.

---

### Phase 2: SQLAlchemy Models

Create model classes for new tables.

**Files to Create**:
- `backend/app/modules/integrations/xero/models/payroll.py`

**Models**:
```python
class XeroEmployee(Base):
    __tablename__ = "xero_employees"

    id: Mapped[UUID]
    tenant_id: Mapped[UUID]
    connection_id: Mapped[UUID]
    xero_employee_id: Mapped[UUID]
    first_name: Mapped[str | None]
    last_name: Mapped[str | None]
    email: Mapped[str | None]
    status: Mapped[str | None]
    start_date: Mapped[date | None]
    termination_date: Mapped[date | None]

class XeroPayRun(Base):
    __tablename__ = "xero_pay_runs"

    id: Mapped[UUID]
    tenant_id: Mapped[UUID]
    connection_id: Mapped[UUID]
    xero_pay_run_id: Mapped[UUID]
    pay_run_status: Mapped[str | None]
    period_start: Mapped[date]
    period_end: Mapped[date]
    payment_date: Mapped[date]
    total_wages: Mapped[Decimal]
    total_tax: Mapped[Decimal]
    total_super: Mapped[Decimal]
    total_deductions: Mapped[Decimal]
    total_reimbursements: Mapped[Decimal]
```

**Update Existing**:
- `backend/app/modules/integrations/xero/models/connection.py` - Add new columns

---

### Phase 3: Xero Payroll API Client

Create client for payroll API calls.

**Files to Create**:
- `backend/app/modules/integrations/xero/payroll_client.py`

**Implementation**:
```python
class XeroPayrollClient:
    BASE_URL = "https://api.xero.com/payroll.xro/2.0"

    async def get_employees(
        self,
        access_token: str,
        xero_tenant_id: str,
        modified_after: datetime | None = None
    ) -> list[dict]:
        """Fetch employees with pagination."""

    async def get_pay_runs(
        self,
        access_token: str,
        xero_tenant_id: str,
        from_date: date,
        to_date: date,
        status: str = "POSTED"
    ) -> list[dict]:
        """Fetch posted pay runs within date range."""

    async def get_pay_run_details(
        self,
        access_token: str,
        xero_tenant_id: str,
        pay_run_id: str
    ) -> dict:
        """Fetch detailed pay run with payslips."""
```

**Rate Limiting**: Use existing rate limiter but track payroll calls separately.

---

### Phase 4: Payroll Sync Service

Create sync service for payroll data.

**Files to Create**:
- `backend/app/modules/integrations/xero/payroll_service.py`
- `backend/app/modules/integrations/xero/payroll_repository.py`

**Implementation**:
```python
class XeroPayrollService:
    async def sync_payroll(
        self,
        connection: XeroConnection
    ) -> SyncResult:
        """Full payroll sync for a connection."""

    async def sync_employees(
        self,
        connection: XeroConnection,
        access_token: str
    ) -> int:
        """Sync employees, return count."""

    async def sync_pay_runs(
        self,
        connection: XeroConnection,
        access_token: str,
        from_date: date,
        to_date: date
    ) -> int:
        """Sync pay runs, return count."""
```

**Celery Task**:
```python
@shared_task
def sync_payroll_task(connection_id: str) -> dict:
    """Background task for payroll sync."""
```

---

### Phase 5: OAuth Scope Extension

Update OAuth flow to request payroll scopes.

**Files to Modify**:
- `backend/app/modules/integrations/xero/oauth.py`

**Changes**:
- Add payroll scopes to scope list
- Handle scope denial gracefully
- Store granted scopes on connection

**Scopes to Add**:
```python
PAYROLL_SCOPES = [
    "payroll.employees",
    "payroll.payruns",
    "payroll.settings",
    "payroll.timesheets.read"  # Optional
]
```

---

### Phase 6: API Endpoints

Extend existing endpoints and add new ones.

**Files to Modify**:
- `backend/app/modules/clients/router.py`
- `backend/app/modules/clients/service.py`
- `backend/app/modules/clients/schemas.py`
- `backend/app/modules/clients/repository.py`

**Files to Create**:
- None (extend existing clients module)

**Endpoint Changes**:

```
GET /api/v1/clients/{id}
- Add: has_payroll, last_payroll_sync_at, total_wages, total_tax_withheld, employee_count

GET /api/v1/clients/{id}/summary
- Add: payroll section with aggregates

GET /api/v1/clients/{id}/employees (NEW)
- List employees for connection
- Filter: status
- Pagination

GET /api/v1/clients/{id}/pay-runs (NEW)
- List pay runs for connection
- Filter: date range, status
- Pagination

POST /api/v1/integrations/xero/{connection_id}/sync/payroll (NEW)
- Trigger payroll sync
- Return task ID
```

---

### Phase 7: Frontend Updates

Update client detail page with payroll data.

**Files to Modify**:
- `frontend/src/app/(protected)/clients/[id]/page.tsx`

**Changes**:

1. **Overview Tab**: Add PAYG section with W1, W2 values
2. **Status Indicators**: Show payroll sync status
3. **Optional**: Add Employees and Pay Runs tabs

**Component Structure**:
```
ClientDetailPage
├── Header (with payroll status indicator)
├── Tabs
│   ├── Overview (enhanced with PAYG cards)
│   ├── Contacts
│   ├── Invoices
│   ├── Transactions
│   ├── Employees (optional - Phase 7b)
│   └── Pay Runs (optional - Phase 7b)
```

---

### Phase 8: Integration with Sync Flow

Integrate payroll sync with existing sync infrastructure.

**Files to Modify**:
- `backend/app/modules/integrations/xero/service.py`
- `backend/app/tasks/xero_sync.py`

**Changes**:
- Add payroll sync to full sync flow
- Make payroll sync optional (skip if no access)
- Track payroll sync progress separately
- Update sync status to include payroll

---

## Testing Strategy

### Unit Tests
- Payroll client mock responses
- Sync service logic
- Aggregate calculations

### Integration Tests
- API endpoint responses
- Database operations
- RLS enforcement

### E2E Tests
- Full sync with Xero demo company
- Verify BAS calculations match Xero

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Payroll API not enabled for connection | Check scopes, handle gracefully, show "No payroll" status |
| Rate limiting different from accounting | Separate rate limit tracking for payroll |
| Large employee/payrun counts | Pagination, incremental sync |
| Sensitive PII data | RLS, consider field encryption for TFN status |

---

## Success Metrics

1. Payroll data synced within 2 minutes
2. BAS PAYG fields populated correctly
3. No rate limit errors
4. Clean handling of connections without payroll

---

## File Summary

### New Files
| File | Purpose |
|------|---------|
| `alembic/versions/xxx_add_payroll_tables.py` | Database migration |
| `modules/integrations/xero/models/payroll.py` | SQLAlchemy models |
| `modules/integrations/xero/payroll_client.py` | Xero API client |
| `modules/integrations/xero/payroll_service.py` | Sync business logic |
| `modules/integrations/xero/payroll_repository.py` | Database operations |

### Modified Files
| File | Changes |
|------|---------|
| `modules/integrations/xero/models/connection.py` | Add payroll columns |
| `modules/integrations/xero/oauth.py` | Add payroll scopes |
| `modules/integrations/xero/service.py` | Integrate payroll sync |
| `modules/clients/router.py` | Add payroll endpoints |
| `modules/clients/service.py` | Add payroll logic |
| `modules/clients/schemas.py` | Add payroll fields |
| `modules/clients/repository.py` | Add payroll queries |
| `frontend/.../clients/[id]/page.tsx` | Add PAYG display |
