# Data Model: Xero Reports API

**Feature**: 023-xero-reports-api
**Date**: 2026-01-01

---

## Entity Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ENTITY RELATIONSHIPS                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  XeroConnection (existing)                                              │
│       │                                                                 │
│       │ 1:N                                                             │
│       ▼                                                                 │
│  XeroReport                                                             │
│       │                                                                 │
│       │ 1:N                                                             │
│       ▼                                                                 │
│  XeroReportSyncJob (tracks sync history)                                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Enums

### XeroReportType

```python
class XeroReportType(str, enum.Enum):
    """Types of reports available from Xero Reports API."""

    PROFIT_AND_LOSS = "profit_and_loss"
    BALANCE_SHEET = "balance_sheet"
    AGED_RECEIVABLES = "aged_receivables_by_contact"
    AGED_PAYABLES = "aged_payables_by_contact"
    TRIAL_BALANCE = "trial_balance"
    BANK_SUMMARY = "bank_summary"
    BUDGET_SUMMARY = "budget_summary"
```

### XeroReportSyncStatus

```python
class XeroReportSyncStatus(str, enum.Enum):
    """Status of a report sync operation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"  # e.g., budget not configured
```

---

## Entities

### XeroReport

**Purpose**: Stores fetched report data with flexible JSONB storage for varying report structures.

```python
class XeroReport(Base, TimestampMixin):
    """Cached Xero report data.

    Reports are fetched from Xero and cached locally for:
    - Fast retrieval without API calls
    - AI agent context enrichment
    - Historical trend analysis
    - ATO compliance (7-year retention)

    Each report is uniquely identified by:
    - connection_id (which client)
    - report_type (P&L, Balance Sheet, etc.)
    - period_key (e.g., "2025-FY", "2025-12", "2025-12-31")
    """

    __tablename__ = "xero_reports"

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Multi-tenancy
    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    connection_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Report identification
    report_type: Mapped[XeroReportType] = mapped_column(
        SQLAlchemyEnum(XeroReportType),
        nullable=False,
    )

    # Period identification (composite with report_type for uniqueness)
    period_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Period identifier: '2025-FY', '2025-Q4', '2025-12', '2025-12-31'",
    )
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    as_of_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="For point-in-time reports (Balance Sheet, Aged)",
    )

    # Report metadata from Xero
    xero_report_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    report_name: Mapped[str] = mapped_column(String(255), nullable=False)
    report_titles: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    xero_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When Xero last updated this report",
    )

    # Raw report data (flexible structure)
    rows_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Full Rows array from Xero response",
    )

    # Extracted summary fields (for quick queries)
    summary_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Extracted key metrics: revenue, net_profit, current_ratio, etc.",
    )

    # Sync metadata
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    cache_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When this cached data should be considered stale",
    )
    is_current_period: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="True if period includes today (affects cache TTL)",
    )

    # Report parameters used (for cache key matching)
    parameters: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Query params used: timeframe, periods, standardLayout, etc.",
    )

    # Constraints
    __table_args__ = (
        # Unique report per connection/type/period
        UniqueConstraint(
            "connection_id",
            "report_type",
            "period_key",
            name="uq_xero_reports_connection_type_period",
        ),
        # Index for common queries
        Index(
            "ix_xero_reports_tenant_type",
            "tenant_id",
            "report_type",
        ),
        Index(
            "ix_xero_reports_cache_expires",
            "cache_expires_at",
        ),
    )

    # Relationships
    connection: Mapped["XeroConnection"] = relationship(
        "XeroConnection",
        back_populates="reports",
    )
```

**Key Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `report_type` | Enum | Type of report (P&L, Balance Sheet, etc.) |
| `period_key` | String | Human-readable period identifier |
| `rows_data` | JSONB | Full report structure from Xero |
| `summary_data` | JSONB | Extracted key metrics for quick access |
| `cache_expires_at` | DateTime | When to consider data stale |
| `is_current_period` | Boolean | Affects cache TTL behavior |

---

### XeroReportSyncJob

**Purpose**: Tracks report sync operations for audit trail and retry logic.

```python
class XeroReportSyncJob(Base, TimestampMixin):
    """Tracks individual report sync operations.

    Used for:
    - Audit trail of all sync attempts
    - Retry logic for failed syncs
    - Performance monitoring (duration, error rates)
    """

    __tablename__ = "xero_report_sync_jobs"

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Multi-tenancy
    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    connection_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Job details
    report_type: Mapped[XeroReportType] = mapped_column(
        SQLAlchemyEnum(XeroReportType),
        nullable=False,
    )
    status: Mapped[XeroReportSyncStatus] = mapped_column(
        SQLAlchemyEnum(XeroReportSyncStatus),
        nullable=False,
        default=XeroReportSyncStatus.PENDING,
    )

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Total sync duration in milliseconds",
    )

    # Results
    rows_fetched: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of rows in fetched report",
    )
    report_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_reports.id", ondelete="SET NULL"),
        nullable=True,
        comment="Resulting report record if successful",
    )

    # Error handling
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Request context
    triggered_by: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="scheduled",
        comment="'scheduled', 'on_demand', 'retry'",
    )
    user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="User who triggered on-demand sync",
    )

    # Constraints
    __table_args__ = (
        Index(
            "ix_xero_report_sync_jobs_status",
            "status",
            "next_retry_at",
        ),
    )
```

---

## Summary Data Schemas

### ProfitAndLossSummary

```python
class ProfitAndLossSummary(BaseModel):
    """Extracted P&L summary for quick access and AI context."""

    period_start: date
    period_end: date

    # Revenue
    revenue: Decimal
    other_income: Decimal = Decimal("0")
    total_income: Decimal

    # Cost of Sales
    cost_of_sales: Decimal = Decimal("0")
    gross_profit: Decimal

    # Expenses
    operating_expenses: Decimal
    total_expenses: Decimal

    # Profit
    operating_profit: Decimal
    net_profit: Decimal

    # Ratios (calculated)
    gross_margin_pct: float | None = None
    net_margin_pct: float | None = None
    expense_ratio_pct: float | None = None
```

### BalanceSheetSummary

```python
class BalanceSheetSummary(BaseModel):
    """Extracted Balance Sheet summary."""

    as_of_date: date

    # Assets
    current_assets: Decimal
    non_current_assets: Decimal
    total_assets: Decimal

    # Liabilities
    current_liabilities: Decimal
    non_current_liabilities: Decimal
    total_liabilities: Decimal

    # Equity
    total_equity: Decimal

    # Ratios (calculated)
    current_ratio: float | None = None
    quick_ratio: float | None = None
    debt_to_equity: float | None = None
```

### AgedReceivablesSummary

```python
class AgedReceivablesSummary(BaseModel):
    """Extracted Aged Receivables summary."""

    as_of_date: date

    # Totals by aging bucket
    current: Decimal
    overdue_1_30: Decimal
    overdue_31_60: Decimal
    overdue_61_90: Decimal
    overdue_90_plus: Decimal
    total: Decimal

    # Risk metrics
    overdue_total: Decimal
    overdue_pct: float
    avg_debtor_days: float | None = None

    # High risk contacts (over 90 days with significant amounts)
    high_risk_contacts: list[dict] = []
```

### AgedPayablesSummary

```python
class AgedPayablesSummary(BaseModel):
    """Extracted Aged Payables summary."""

    as_of_date: date

    # Totals by aging bucket
    current: Decimal
    overdue_1_30: Decimal
    overdue_31_60: Decimal
    overdue_61_90: Decimal
    overdue_90_plus: Decimal
    total: Decimal

    # Payment metrics
    overdue_total: Decimal
    overdue_pct: float
    avg_creditor_days: float | None = None
```

---

## Migration

### Alembic Migration

```python
"""Add Xero Reports tables.

Revision ID: 023_xero_reports
Create Date: 2026-01-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "023_xero_reports"
down_revision = "022_admin_dashboard"  # Previous migration


def upgrade() -> None:
    # Create xero_report_type enum
    op.execute("""
        CREATE TYPE xeroreporttype AS ENUM (
            'profit_and_loss',
            'balance_sheet',
            'aged_receivables_by_contact',
            'aged_payables_by_contact',
            'trial_balance',
            'bank_summary',
            'budget_summary'
        )
    """)

    # Create xero_report_sync_status enum
    op.execute("""
        CREATE TYPE xeroreportsyncstatus AS ENUM (
            'pending',
            'in_progress',
            'completed',
            'failed',
            'skipped'
        )
    """)

    # Create xero_reports table
    op.create_table(
        "xero_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", UUID(as_uuid=True), nullable=False),
        sa.Column("report_type", sa.Enum("xeroreporttype", create_type=False), nullable=False),
        sa.Column("period_key", sa.String(50), nullable=False),
        sa.Column("period_start", sa.Date, nullable=True),
        sa.Column("period_end", sa.Date, nullable=True),
        sa.Column("as_of_date", sa.Date, nullable=True),
        sa.Column("xero_report_id", sa.String(255), nullable=True),
        sa.Column("report_name", sa.String(255), nullable=False),
        sa.Column("report_titles", JSONB, nullable=False, server_default="[]"),
        sa.Column("xero_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_data", JSONB, nullable=False, server_default="{}"),
        sa.Column("summary_data", JSONB, nullable=False, server_default="{}"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cache_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_current_period", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("parameters", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["xero_connections.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("connection_id", "report_type", "period_key", name="uq_xero_reports_connection_type_period"),
    )

    op.create_index("ix_xero_reports_tenant_id", "xero_reports", ["tenant_id"])
    op.create_index("ix_xero_reports_connection_id", "xero_reports", ["connection_id"])
    op.create_index("ix_xero_reports_tenant_type", "xero_reports", ["tenant_id", "report_type"])
    op.create_index("ix_xero_reports_cache_expires", "xero_reports", ["cache_expires_at"])

    # Create xero_report_sync_jobs table
    op.create_table(
        "xero_report_sync_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", UUID(as_uuid=True), nullable=False),
        sa.Column("report_type", sa.Enum("xeroreporttype", create_type=False), nullable=False),
        sa.Column("status", sa.Enum("xeroreportsyncstatus", create_type=False), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("rows_fetched", sa.Integer, nullable=True),
        sa.Column("report_id", UUID(as_uuid=True), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("triggered_by", sa.String(50), nullable=False, server_default="'scheduled'"),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["xero_connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["xero_reports.id"], ondelete="SET NULL"),
    )

    op.create_index("ix_xero_report_sync_jobs_tenant_id", "xero_report_sync_jobs", ["tenant_id"])
    op.create_index("ix_xero_report_sync_jobs_connection_id", "xero_report_sync_jobs", ["connection_id"])
    op.create_index("ix_xero_report_sync_jobs_status", "xero_report_sync_jobs", ["status", "next_retry_at"])


def downgrade() -> None:
    op.drop_table("xero_report_sync_jobs")
    op.drop_table("xero_reports")
    op.execute("DROP TYPE xeroreportsyncstatus")
    op.execute("DROP TYPE xeroreporttype")
```

---

## Validation Rules

### XeroReport

| Field | Rule |
|-------|------|
| `period_key` | Required, max 50 chars, pattern: `YYYY-FY`, `YYYY-QN`, `YYYY-MM`, `YYYY-MM-DD` |
| `report_type` | Required, must be valid enum value |
| `rows_data` | Required, must be valid JSON object |
| `cache_expires_at` | Required, must be > `fetched_at` |

### Period Key Format

```python
def validate_period_key(period_key: str, report_type: XeroReportType) -> bool:
    """Validate period key format based on report type."""
    patterns = {
        XeroReportType.PROFIT_AND_LOSS: [
            r"^\d{4}-FY$",        # 2025-FY
            r"^\d{4}-Q[1-4]$",    # 2025-Q4
            r"^\d{4}-\d{2}$",     # 2025-12
        ],
        XeroReportType.BALANCE_SHEET: [
            r"^\d{4}-\d{2}-\d{2}$",  # 2025-12-31 (point in time)
        ],
        XeroReportType.AGED_RECEIVABLES: [
            r"^\d{4}-\d{2}-\d{2}$",  # 2025-12-31
        ],
        XeroReportType.AGED_PAYABLES: [
            r"^\d{4}-\d{2}-\d{2}$",
        ],
        XeroReportType.TRIAL_BALANCE: [
            r"^\d{4}-FY$",
            r"^\d{4}-\d{2}$",
        ],
        XeroReportType.BANK_SUMMARY: [
            r"^\d{4}-\d{2}$",
        ],
        XeroReportType.BUDGET_SUMMARY: [
            r"^\d{4}-FY$",
        ],
    }

    valid_patterns = patterns.get(report_type, [])
    return any(re.match(p, period_key) for p in valid_patterns)
```

---

## State Transitions

### XeroReportSyncJob Status

```
PENDING ──────────► IN_PROGRESS ──────────► COMPLETED
    │                    │
    │                    │
    │                    ▼
    │               FAILED ──────► (retry) ──────► PENDING
    │                    │
    │                    ▼
    └──────────────► SKIPPED (e.g., no budget configured)
```

**Transition Rules**:
- `PENDING` → `IN_PROGRESS`: When sync starts
- `IN_PROGRESS` → `COMPLETED`: Successful fetch and save
- `IN_PROGRESS` → `FAILED`: Error during fetch
- `FAILED` → `PENDING`: When retry is scheduled (max 3 retries)
- `PENDING` → `SKIPPED`: When report type not applicable (e.g., no budget)
