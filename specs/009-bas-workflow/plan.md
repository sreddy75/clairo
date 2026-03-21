# Implementation Plan: BAS Preparation Workflow

**Branch**: `feature/009-bas-workflow` | **Date**: 2025-12-29 | **Spec**: [spec.md](./spec.md)

## Summary

Implement a BAS preparation workflow that enables accountants to prepare Business Activity Statements with automated GST calculations from Xero data, PAYG aggregation from payroll sync, variance analysis against prior periods, and exportable working papers. This builds upon Spec 008 (Data Quality Scoring) and reuses existing quarter utility functions and calculator patterns.

## Technical Context

**Language/Version**: Python 3.12+, TypeScript
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, Next.js 14, Tailwind CSS
**Storage**: PostgreSQL 16 with new BAS tables
**Testing**: pytest, pytest-asyncio, httpx
**Target Platform**: Web application (accountant dashboard)
**Performance Goals**: GST calculation < 10s for 5000 transactions
**Constraints**: Calculations must be deterministic, audit trail required
**Scale/Scope**: 50-200 clients per tenant, ~5000 transactions/quarter/client max

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Modular Monolith | ✅ Pass | New `bas` module follows existing pattern |
| Repository Pattern | ✅ Pass | BASRepository for all DB operations |
| Multi-tenancy/RLS | ✅ Pass | All tables include tenant_id, RLS enforced |
| Testing Strategy | ✅ Pass | Unit + integration tests per spec |
| Audit Logging | ✅ Pass | BAS events logged per spec requirements |
| Type Hints | ✅ Pass | All code fully typed |

## Project Structure

### Documentation (this feature)

```text
specs/009-bas-workflow/
├── spec.md              # Requirements specification ✓
├── plan.md              # This file
└── tasks.md             # Task list (next step)
```

### Source Code (repository root)

```text
backend/
├── app/
│   └── modules/
│       └── bas/                        # NEW MODULE
│           ├── __init__.py
│           ├── models.py               # BASPeriod, BASSession, BASCalculation, BASAdjustment
│           ├── schemas.py              # Pydantic schemas for API
│           ├── repository.py           # Database operations
│           ├── service.py              # Business logic
│           ├── calculator.py           # GST/PAYG calculation engine
│           ├── variance.py             # Variance analysis engine
│           ├── exporter.py             # PDF/Excel export
│           └── router.py               # API endpoints
│
├── alembic/
│   └── versions/
│       └── xxx_bas_workflow.py         # Database migration
│
└── tests/
    ├── unit/
    │   └── modules/
    │       └── bas/
    │           ├── test_calculator.py
    │           ├── test_variance.py
    │           └── test_service.py
    └── integration/
        └── api/
            └── test_bas.py

frontend/
└── src/
    ├── app/
    │   └── (protected)/
    │       └── clients/
    │           └── [id]/
    │               └── bas/
    │                   ├── page.tsx            # BAS period list
    │                   └── [sessionId]/
    │                       └── page.tsx        # BAS preparation session
    └── components/
        └── bas/
            ├── BASPeriodSelector.tsx
            ├── GSTSummary.tsx
            ├── PAYGSummary.tsx
            ├── VarianceTable.tsx
            ├── AdjustmentForm.tsx
            └── ExportButton.tsx
```

**Structure Decision**: Follows existing modular monolith pattern established by `quality` and `integrations/xero` modules.

---

## Architecture Overview

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Frontend                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Period       │  │ GST          │  │ PAYG         │  │ Variance     │ │
│  │ Selector     │  │ Summary      │  │ Summary      │  │ Table        │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                 │                 │                 │         │
│         └─────────────────┴─────────────────┴─────────────────┘         │
│                                    │                                     │
│                            API Calls (TanStack Query)                    │
└────────────────────────────────────┼────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────┐
│                              Backend                                     │
│                                    │                                     │
│  ┌─────────────────────────────────▼──────────────────────────────────┐ │
│  │                          BAS Router                                 │ │
│  │  /api/v1/clients/{id}/bas/periods                                  │ │
│  │  /api/v1/clients/{id}/bas/sessions                                 │ │
│  │  /api/v1/clients/{id}/bas/sessions/{id}/calculate                  │ │
│  │  /api/v1/clients/{id}/bas/sessions/{id}/export                     │ │
│  └─────────────────────────────────┬──────────────────────────────────┘ │
│                                    │                                     │
│  ┌─────────────────────────────────▼──────────────────────────────────┐ │
│  │                          BAS Service                                │ │
│  │  - create_session()        - approve_session()                     │ │
│  │  - calculate_gst()         - add_adjustment()                      │ │
│  │  - calculate_payg()        - export_working_papers()               │ │
│  │  - get_variance()                                                   │ │
│  └────────┬──────────────┬────────────────┬──────────────┬───────────┘ │
│           │              │                │              │             │
│  ┌────────▼───────┐ ┌────▼────┐ ┌─────────▼────────┐ ┌───▼──────────┐ │
│  │ GSTCalculator  │ │PAYGCalc │ │ VarianceAnalyzer │ │ WorkingPaper │ │
│  │                │ │         │ │                  │ │ Exporter     │ │
│  └────────┬───────┘ └────┬────┘ └─────────┬────────┘ └───┬──────────┘ │
│           │              │                │              │             │
│  ┌────────▼──────────────▼────────────────▼──────────────▼───────────┐ │
│  │                       BAS Repository                               │ │
│  └────────────────────────────────┬──────────────────────────────────┘ │
│                                   │                                     │
└───────────────────────────────────┼─────────────────────────────────────┘
                                    │
┌───────────────────────────────────┼─────────────────────────────────────┐
│                             PostgreSQL                                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐        │
│  │ bas_periods│  │bas_sessions│  │bas_calcs   │  │bas_adjust  │        │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘        │
│                                                                         │
│  (Read from existing tables)                                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐        │
│  │xero_invoices│ │xero_bank_  │  │xero_pay_   │  │quality_    │        │
│  │            │  │transactions│  │runs        │  │scores      │        │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Model

### BASPeriod

Represents a BAS reporting period for a client. Periods are created on-demand when a user starts preparation.

```python
class BASPeriod(Base, TimestampMixin):
    __tablename__ = "bas_periods"

    id: Mapped[UUID]                    # PK
    tenant_id: Mapped[UUID]             # FK tenants, RLS enforced
    connection_id: Mapped[UUID]         # FK xero_connections

    # Period identification
    period_type: Mapped[str]            # 'quarterly' | 'monthly'
    quarter: Mapped[int | None]         # 1-4 for quarterly
    month: Mapped[int | None]           # 1-12 for monthly
    fy_year: Mapped[int]                # Financial year (e.g., 2025)

    # Period dates
    start_date: Mapped[date]
    end_date: Mapped[date]
    due_date: Mapped[date]              # ATO lodgement deadline

    # Unique: (connection_id, fy_year, quarter) or (connection_id, fy_year, month)
```

### BASSession

A preparation session tracks the workflow state for a specific period.

```python
class BASSessionStatus(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    LODGED = "lodged"

class BASSession(Base, TimestampMixin):
    __tablename__ = "bas_sessions"

    id: Mapped[UUID]                    # PK
    tenant_id: Mapped[UUID]             # FK tenants
    period_id: Mapped[UUID]             # FK bas_periods, UNIQUE

    status: Mapped[BASSessionStatus]    # Workflow state
    created_by: Mapped[UUID]            # FK users
    last_modified_by: Mapped[UUID | None]
    approved_by: Mapped[UUID | None]
    approved_at: Mapped[datetime | None]

    # Calculation timestamps
    gst_calculated_at: Mapped[datetime | None]
    payg_calculated_at: Mapped[datetime | None]

    internal_notes: Mapped[str | None]
```

### BASCalculation

Cached calculation results. One per session.

```python
class BASCalculation(Base, TimestampMixin):
    __tablename__ = "bas_calculations"

    id: Mapped[UUID]                    # PK
    tenant_id: Mapped[UUID]             # FK tenants
    session_id: Mapped[UUID]            # FK bas_sessions, UNIQUE

    # G-fields (GST)
    g1_total_sales: Mapped[Decimal]     # Total sales incl GST
    g2_export_sales: Mapped[Decimal]    # Export sales (GST-free)
    g3_gst_free_sales: Mapped[Decimal]  # Other GST-free
    g10_capital_purchases: Mapped[Decimal]
    g11_non_capital_purchases: Mapped[Decimal]

    # Calculated GST fields
    field_1a_gst_on_sales: Mapped[Decimal]
    field_1b_gst_on_purchases: Mapped[Decimal]

    # PAYG fields
    w1_total_wages: Mapped[Decimal]
    w2_amount_withheld: Mapped[Decimal]

    # Summary
    gst_payable: Mapped[Decimal]        # 1A - 1B
    total_payable: Mapped[Decimal]      # GST payable + W2

    # Metadata
    calculated_at: Mapped[datetime]
    calculation_duration_ms: Mapped[int]
    transaction_count: Mapped[int]
    invoice_count: Mapped[int]
    pay_run_count: Mapped[int]
```

### BASAdjustment

Manual adjustments to calculated fields.

```python
class BASAdjustment(Base, TimestampMixin):
    __tablename__ = "bas_adjustments"

    id: Mapped[UUID]                    # PK
    tenant_id: Mapped[UUID]             # FK tenants
    session_id: Mapped[UUID]            # FK bas_sessions

    field_name: Mapped[str]             # e.g., 'g1_total_sales', 'field_1a'
    adjustment_amount: Mapped[Decimal]
    reason: Mapped[str]                 # Required
    reference: Mapped[str | None]       # Optional

    created_by: Mapped[UUID]            # FK users
```

---

## GST Calculation Logic

### Tax Type Mapping

Xero stores tax types in line items. Map to BAS fields:

| Xero Tax Type | BAS Impact | Notes |
|--------------|------------|-------|
| `OUTPUT` | 1A (GST on sales) | 10% GST collected |
| `OUTPUT2` | 1A | 10% GST collected |
| `INPUT` | 1B (GST on purchases) | 10% GST credits |
| `INPUT2` | 1B | 10% GST credits |
| `BASEXCLUDED` | Excluded | Not reported |
| `EXEMPTEXPENSES` | G3 | GST-free purchases |
| `EXEMPTINCOME` | G3 | GST-free sales |
| `EXEMPTEXPORT` | G2 | Export sales |
| `CAPEXINPUT` | G10 + 1B | Capital purchases |
| `NONE` | Excluded | No tax |
| `ZERORATEDINPUT` | G11 (no GST) | Zero-rated |
| `ZERORATEDOUTPUT` | G1 (no GST) | Zero-rated |

### Calculation Algorithm

```python
class GSTCalculator:
    """Calculates GST fields from Xero invoices and bank transactions."""

    async def calculate(
        self,
        connection_id: UUID,
        start_date: date,
        end_date: date,
    ) -> GSTResult:
        # 1. Query all invoices in date range
        invoices = await self._get_invoices(connection_id, start_date, end_date)

        # 2. Query all bank transactions in date range
        transactions = await self._get_transactions(connection_id, start_date, end_date)

        # 3. Extract line items and sum by tax type
        totals = defaultdict(Decimal)
        gst_totals = defaultdict(Decimal)

        for item in self._extract_line_items(invoices, transactions):
            tax_type = item.get("tax_type", "NONE")
            amount = Decimal(str(item.get("line_amount", 0)))
            tax_amount = Decimal(str(item.get("tax_amount", 0)))

            # Map to BAS categories
            if tax_type in ("OUTPUT", "OUTPUT2"):
                totals["g1"] += amount + tax_amount
                gst_totals["1a"] += tax_amount
            elif tax_type in ("INPUT", "INPUT2"):
                totals["g11"] += amount
                gst_totals["1b"] += tax_amount
            elif tax_type == "CAPEXINPUT":
                totals["g10"] += amount
                gst_totals["1b"] += tax_amount
            elif tax_type in ("EXEMPTINCOME", "ZERORATEDOUTPUT"):
                totals["g3"] += amount
            elif tax_type == "EXEMPTEXPORT":
                totals["g2"] += amount
            # BASEXCLUDED and NONE are skipped

        # 4. Return structured result
        return GSTResult(
            g1_total_sales=totals["g1"],
            g2_export_sales=totals["g2"],
            g3_gst_free_sales=totals["g3"],
            g10_capital_purchases=totals["g10"],
            g11_non_capital_purchases=totals["g11"],
            field_1a_gst_on_sales=gst_totals["1a"],
            field_1b_gst_on_purchases=gst_totals["1b"],
            gst_payable=gst_totals["1a"] - gst_totals["1b"],
        )
```

### PAYG Calculation

```python
class PAYGCalculator:
    """Aggregates PAYG withholding from pay runs."""

    async def calculate(
        self,
        connection_id: UUID,
        start_date: date,
        end_date: date,
    ) -> PAYGResult:
        # Query pay runs in date range (by payment_date)
        pay_runs = await self._get_pay_runs(connection_id, start_date, end_date)

        # Aggregate totals
        w1_total = sum(pr.total_wages for pr in pay_runs)
        w2_total = sum(pr.total_tax for pr in pay_runs)

        return PAYGResult(
            w1_total_wages=w1_total,
            w2_amount_withheld=w2_total,
            pay_run_count=len(pay_runs),
        )
```

---

## Variance Analysis

### Comparison Logic

Compare current period against:
1. **Prior Quarter** - e.g., Q2 FY2025 vs Q1 FY2025
2. **Same Quarter Last Year** - e.g., Q2 FY2025 vs Q2 FY2024

```python
class VarianceAnalyzer:
    """Analyzes variances between BAS periods."""

    async def analyze(
        self,
        current_session: BASSession,
    ) -> VarianceResult:
        # Get prior quarter
        prior_quarter_session = await self._get_prior_quarter(current_session)
        prior_year_session = await self._get_same_quarter_prior_year(current_session)

        variances = []

        for field in BAS_FIELDS:
            current_value = getattr(current_session.calculation, field)

            # Prior quarter variance
            if prior_quarter_session:
                prior_value = getattr(prior_quarter_session.calculation, field)
                variance = self._calculate_variance(current_value, prior_value)
                variances.append(FieldVariance(
                    field=field,
                    comparison="prior_quarter",
                    current=current_value,
                    prior=prior_value,
                    absolute_change=variance.absolute,
                    percent_change=variance.percent,
                    severity=self._get_severity(variance.percent),
                ))

            # Same quarter last year
            if prior_year_session:
                # Similar logic...
                pass

        return VarianceResult(variances=variances)

    def _get_severity(self, percent_change: Decimal) -> str:
        """Determine variance severity."""
        abs_change = abs(percent_change)
        if abs_change >= 50:
            return "critical"  # Red
        elif abs_change >= 20:
            return "warning"   # Yellow
        return "normal"        # No highlight
```

---

## API Endpoints

### Periods

```
GET  /api/v1/clients/{connection_id}/bas/periods
     → List available BAS periods for the client

POST /api/v1/clients/{connection_id}/bas/periods
     → Create a new BAS period (if not exists)
```

### Sessions

```
GET  /api/v1/clients/{connection_id}/bas/sessions
     → List all BAS sessions for client

POST /api/v1/clients/{connection_id}/bas/sessions
     Body: { period_id: UUID }
     → Create a new BAS preparation session

GET  /api/v1/clients/{connection_id}/bas/sessions/{session_id}
     → Get session details with calculations

PATCH /api/v1/clients/{connection_id}/bas/sessions/{session_id}
     Body: { status: string, internal_notes: string }
     → Update session status/notes
```

### Calculations

```
POST /api/v1/clients/{connection_id}/bas/sessions/{session_id}/calculate
     → Trigger GST + PAYG calculation

GET  /api/v1/clients/{connection_id}/bas/sessions/{session_id}/variance
     → Get variance analysis
```

### Adjustments

```
GET  /api/v1/clients/{connection_id}/bas/sessions/{session_id}/adjustments
     → List adjustments

POST /api/v1/clients/{connection_id}/bas/sessions/{session_id}/adjustments
     Body: { field_name: string, adjustment_amount: decimal, reason: string }
     → Add adjustment

DELETE /api/v1/clients/{connection_id}/bas/sessions/{session_id}/adjustments/{id}
     → Remove adjustment
```

### Export

```
GET  /api/v1/clients/{connection_id}/bas/sessions/{session_id}/export
     Query: format=pdf|excel
     → Download working papers
```

---

## Frontend Components

### Page Structure

```
/clients/[id]/bas
├── page.tsx                    # Period list / session overview
│   ├── BASPeriodSelector       # Quarter/month picker
│   ├── SessionList             # Previous sessions
│   └── StartPreparationButton  # Create new session
│
└── [sessionId]/page.tsx        # Preparation session
    ├── Header                  # Session status, actions
    ├── Tabs
    │   ├── GST Tab
    │   │   ├── GSTSummary      # G-fields, 1A, 1B totals
    │   │   ├── GSTBreakdown    # Monthly breakdown
    │   │   └── AdjustmentList  # Adjustments for GST fields
    │   ├── PAYG Tab
    │   │   ├── PAYGSummary     # W1, W2 totals
    │   │   └── PayRunList      # Contributing pay runs
    │   ├── Variance Tab
    │   │   └── VarianceTable   # Prior period comparisons
    │   └── Summary Tab
    │       ├── BASSummary      # All fields in BAS format
    │       ├── TotalPayable    # Net amount
    │       └── ApprovalButton  # Mark ready for review
    └── ExportMenu              # PDF/Excel export
```

### Key Components

```tsx
// GSTSummary.tsx
interface GSTSummaryProps {
  calculation: BASCalculation;
  adjustments: BASAdjustment[];
  onAddAdjustment: (field: string) => void;
}

// Shows G-fields and 1A/1B with adjustments applied
export function GSTSummary({ calculation, adjustments, onAddAdjustment }: GSTSummaryProps) {
  const adjustedValues = applyAdjustments(calculation, adjustments);

  return (
    <div className="space-y-4">
      <FieldRow label="G1 - Total sales" value={adjustedValues.g1} />
      <FieldRow label="G2 - Export sales" value={adjustedValues.g2} />
      {/* ... more fields */}
      <Divider />
      <FieldRow label="1A - GST on sales" value={adjustedValues.field_1a} highlight />
      <FieldRow label="1B - GST on purchases" value={adjustedValues.field_1b} highlight />
      <FieldRow
        label="GST Payable/Refund"
        value={adjustedValues.gst_payable}
        variant={adjustedValues.gst_payable >= 0 ? "payable" : "refund"}
      />
    </div>
  );
}
```

---

## Audit Events

| Event Type | Trigger | Data Captured |
|------------|---------|---------------|
| `bas.session.created` | New session | period_id, created_by |
| `bas.session.status_changed` | Status update | before_status, after_status, actor |
| `bas.calculation.performed` | Calculate triggered | duration_ms, transaction_count, invoice_count |
| `bas.adjustment.created` | Adjustment added | field, amount, reason, actor |
| `bas.adjustment.deleted` | Adjustment removed | adjustment details, actor |
| `bas.export.generated` | Export downloaded | format, actor |
| `bas.session.approved` | Marked approved | all_figures, approver |

---

## Testing Strategy

### Unit Tests

1. **GSTCalculator** - Test tax type mapping, edge cases
2. **PAYGCalculator** - Test aggregation logic
3. **VarianceAnalyzer** - Test variance calculations, severity thresholds
4. **Service methods** - Test business logic

### Integration Tests

1. **API endpoints** - All CRUD operations
2. **Calculation flow** - End-to-end calculation
3. **Status transitions** - Workflow state machine
4. **Audit logging** - Events are generated

### Test Data

Create factory for:
- BAS periods (various quarters)
- Sessions (various states)
- Invoices with different tax types
- Pay runs with PAYG data

---

## Implementation Phases

### Phase 1: Database & Models (Backend)
- Migration for new tables
- SQLAlchemy models
- Repository with basic CRUD

### Phase 2: GST Calculation Engine
- GSTCalculator class
- Tax type mapping
- Unit tests for calculation

### Phase 3: PAYG Aggregation
- PAYGCalculator class
- Pay run aggregation
- Unit tests

### Phase 4: BAS Service & API
- Service layer orchestration
- API endpoints (periods, sessions, calculate)
- Integration tests

### Phase 5: Variance Analysis
- VarianceAnalyzer class
- Prior period lookups
- Variance API endpoint

### Phase 6: Adjustments
- Adjustment model/API
- Apply adjustments to totals
- Audit logging

### Phase 7: Export
- PDF generation (working papers)
- Excel export
- Export API endpoint

### Phase 8: Frontend - Period Selection
- BAS period list page
- Period selector component
- Create session flow

### Phase 9: Frontend - Preparation Session
- Session detail page
- GST/PAYG tabs
- Calculation trigger

### Phase 10: Frontend - Variance & Summary
- Variance tab
- Summary tab
- Approval workflow

### Phase 11: Frontend - Export & Polish
- Export buttons
- Loading states
- Error handling

### Phase 12: E2E Testing & Documentation
- E2E test scenarios
- API documentation
- Update ROADMAP

---

## Dependencies

| Dependency | Purpose | Status |
|------------|---------|--------|
| Spec 008: Data Quality | Quality checks before BAS | ✅ Complete |
| Spec 007: Payroll Sync | PAYG data (W1, W2) | ✅ Complete |
| Spec 004: Data Sync | Invoice/transaction data | ✅ Complete |
| XeroInvoice model | Tax type in line_items | ✅ Available |
| XeroPayRun model | total_wages, total_tax | ✅ Available |
| Quarter utilities | get_quarter_dates, get_current_quarter | ✅ Available (quality module) |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tax type mapping incomplete | Wrong GST calculations | Test with diverse Xero data, iterate on mapping |
| Large transaction volumes slow | Poor UX | Background task for calculation, caching |
| Line items JSONB parsing | Complex queries | Extract to dedicated function, comprehensive tests |
| PDF generation complexity | Delayed delivery | Use simple template first, enhance later |
| Variance false positives | User confusion | Make thresholds configurable per client |

---

## Success Metrics

- BAS prep time < 1 hour (vs 2-4 hours manual)
- GST accuracy within 0.1% of Xero BAS report
- 95% of sessions complete without adjustments
- Working papers meet ATO requirements
