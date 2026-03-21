"""SQLAlchemy models for client AI context aggregations.

These models store pre-computed financial summaries for efficient
context injection into AI chat queries. Data is computed during
Xero sync and retrieved at query time.

Models:
- ClientAIProfile: Tier 1 profile data (always included in context)
- ClientExpenseSummary: Expense aggregations by category/period
- ClientARAgingSummary: Accounts receivable aging buckets
- ClientAPAgingSummary: Accounts payable aging buckets
- ClientGSTSummary: GST/BAS period summaries
- ClientMonthlyTrend: Monthly financial metrics
- ClientComplianceSummary: Payroll/super/contractor data

All models are tenant-scoped with RLS enforcement.
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.auth.models import Tenant
    from app.modules.integrations.xero.models import XeroConnection


# =============================================================================
# Enums
# =============================================================================


class PeriodType(str, enum.Enum):
    """Period type for aggregation summaries."""

    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"

    def __str__(self) -> str:
        return self.value


class QueryIntent(str, enum.Enum):
    """Detected query intent for context selection."""

    TAX_DEDUCTIONS = "tax_deductions"
    CASH_FLOW = "cash_flow"
    GST_BAS = "gst_bas"
    COMPLIANCE = "compliance"
    GENERAL = "general"

    def __str__(self) -> str:
        return self.value


class RevenueBracket(str, enum.Enum):
    """Revenue bracket for client profiling."""

    MICRO = "micro"  # < $75K (below GST threshold)
    SMALL = "small"  # $75K - $500K
    MEDIUM = "medium"  # $500K - $2M
    LARGE = "large"  # $2M - $10M
    ENTERPRISE = "enterprise"  # > $10M

    def __str__(self) -> str:
        return self.value


# =============================================================================
# Models
# =============================================================================


class ClientAIProfile(Base, TimestampMixin):
    """Client AI profile for Tier 1 context.

    This model stores the essential client profile data that is always
    included in AI context (Tier 1). Contains business metadata used
    for intent-based filtering and context relevance.

    Note: "Client" here refers to the Xero organization (XeroConnection),
    not individual contacts (XeroClient). Aggregations are keyed by connection_id.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection (organization).
        client_id: Legacy FK to Xero client (nullable, deprecated).
        entity_type: Business entity type (sole_trader, company, trust, etc.).
        industry_code: ANZSIC industry code.
        gst_registered: Whether the client is GST registered.
        revenue_bracket: Estimated revenue bracket.
        employee_count: Number of employees.
        computed_at: When the profile was last computed.
    """

    __tablename__ = "client_ai_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Tenant association (RLS enforced)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Organization linkage (primary key for aggregations)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Legacy client linkage (deprecated - kept for backwards compatibility)
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Profile data
    entity_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Business entity type: sole_trader, company, trust, partnership",
    )
    industry_code: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="ANZSIC industry code",
    )
    gst_registered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Whether GST registered (inferred from transactions)",
    )
    revenue_bracket: Mapped[RevenueBracket | None] = mapped_column(
        Enum(
            RevenueBracket,
            name="revenue_bracket",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=True,
        comment="Estimated annual revenue bracket",
    )
    employee_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Number of active employees from payroll",
    )

    # Computation tracking
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When the profile was last computed",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        UniqueConstraint("connection_id", name="uq_client_ai_profile_connection"),
        Index("ix_client_ai_profiles_tenant", "tenant_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ClientAIProfile(connection_id={self.connection_id}, bracket={self.revenue_bracket})>"
        )


class ClientExpenseSummary(Base, TimestampMixin):
    """Client expense summary for Tier 2 context (TAX intent).

    Stores aggregated expense data by account code and category
    for a given period. Used for tax deduction queries.

    Note: Keyed by connection_id (organization), not client_id (contact).

    Attributes:
        id: Unique identifier.
        tenant_id: Foreign key to tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection (organization).
        period_type: Type of period (month, quarter, year).
        period_start: Start date of the period.
        period_end: End date of the period.
        by_account_code: Expenses grouped by account code (JSONB).
        by_category: Expenses grouped by category (JSONB).
        total_expenses: Total expenses for the period.
        total_gst: Total GST on expenses.
        transaction_count: Number of transactions.
        computed_at: When the summary was computed.
    """

    __tablename__ = "client_expense_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Period definition
    period_type: Mapped[PeriodType] = mapped_column(
        Enum(
            PeriodType,
            name="period_type",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    # Aggregated data
    by_account_code: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment='Expenses by account code: {"400": {"amount": 1000, "gst": 100, "count": 5}}',
    )
    by_category: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment='Expenses by category: {"office": 500, "travel": 300}',
    )
    total_expenses: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    total_gst: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    transaction_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "period_type",
            "period_start",
            name="uq_expense_summary_connection_period",
        ),
        Index("ix_client_expense_summaries_tenant", "tenant_id"),
        Index(
            "ix_expense_summaries_connection_period",
            "connection_id",
            "period_start",
        ),
    )

    def __repr__(self) -> str:
        return f"<ClientExpenseSummary(connection_id={self.connection_id}, period={self.period_start})>"


class ClientARAgingSummary(Base, TimestampMixin):
    """Client accounts receivable aging for Tier 2 context (CASH_FLOW intent).

    Stores AR aging buckets and top debtors list.
    Note: Keyed by connection_id (organization).

    Attributes:
        id: Unique identifier.
        tenant_id: Foreign key to tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection (organization).
        as_of_date: Date the aging was calculated.
        current_amount: Amounts not yet due.
        days_31_60: Amounts 31-60 days overdue.
        days_61_90: Amounts 61-90 days overdue.
        over_90_days: Amounts over 90 days overdue.
        total_outstanding: Total AR outstanding.
        top_debtors: List of top debtors (JSONB).
        computed_at: When the summary was computed.
    """

    __tablename__ = "client_ar_aging_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Aging buckets
    current_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
        comment="Not yet due",
    )
    days_31_60: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    days_61_90: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    over_90_days: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    total_outstanding: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    # Top debtors
    top_debtors: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        comment='Top 5 debtors: [{"name": "ABC Co", "amount": 5000, "days_overdue": 45}]',
    )

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "as_of_date",
            name="uq_ar_aging_connection_date",
        ),
        Index("ix_client_ar_aging_tenant", "tenant_id"),
        Index("ix_ar_aging_connection_date", "connection_id", "as_of_date"),
    )

    def __repr__(self) -> str:
        return f"<ClientARAgingSummary(connection_id={self.connection_id}, total={self.total_outstanding})>"


class ClientAPAgingSummary(Base, TimestampMixin):
    """Client accounts payable aging for Tier 2 context (CASH_FLOW intent).

    Stores AP aging buckets and top creditors list.
    Note: Keyed by connection_id (organization).

    Attributes:
        id: Unique identifier.
        tenant_id: Foreign key to tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection (organization).
        as_of_date: Date the aging was calculated.
        current_amount: Amounts not yet due.
        days_31_60: Amounts 31-60 days overdue.
        days_61_90: Amounts 61-90 days overdue.
        over_90_days: Amounts over 90 days overdue.
        total_outstanding: Total AP outstanding.
        top_creditors: List of top creditors (JSONB).
        computed_at: When the summary was computed.
    """

    __tablename__ = "client_ap_aging_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Aging buckets
    current_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
        comment="Not yet due",
    )
    days_31_60: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    days_61_90: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    over_90_days: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    total_outstanding: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    # Top creditors
    top_creditors: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        comment='Top 5 creditors: [{"name": "XYZ Ltd", "amount": 3000, "days_overdue": 30}]',
    )

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "as_of_date",
            name="uq_ap_aging_connection_date",
        ),
        Index("ix_client_ap_aging_tenant", "tenant_id"),
        Index("ix_ap_aging_connection_date", "connection_id", "as_of_date"),
    )

    def __repr__(self) -> str:
        return f"<ClientAPAgingSummary(connection_id={self.connection_id}, total={self.total_outstanding})>"


class ClientGSTSummary(Base, TimestampMixin):
    """Client GST summary for Tier 2 context (GST_BAS intent).

    Stores BAS-relevant GST figures for a period.
    Note: Keyed by connection_id (organization).

    Attributes:
        id: Unique identifier.
        tenant_id: Foreign key to tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection (organization).
        period_type: Type of period (month, quarter).
        period_start: Start date of the period.
        period_end: End date of the period.
        gst_on_sales_1a: GST collected on sales (BAS 1A).
        gst_on_purchases_1b: GST paid on purchases (BAS 1B).
        net_gst: Net GST position (1A - 1B).
        total_sales: Total sales amount.
        total_purchases: Total purchases amount.
        adjustments: Any GST adjustments (JSONB).
        computed_at: When the summary was computed.
    """

    __tablename__ = "client_gst_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Period definition
    period_type: Mapped[PeriodType] = mapped_column(
        Enum(
            PeriodType,
            name="period_type",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    # GST figures
    gst_on_sales_1a: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
        comment="GST collected on sales (BAS 1A)",
    )
    gst_on_purchases_1b: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
        comment="GST paid on purchases (BAS 1B)",
    )
    net_gst: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
        comment="Net GST position (1A - 1B)",
    )
    total_sales: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    total_purchases: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    # Adjustments
    adjustments: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="GST adjustments: {credit_amendments: 100, debit_amendments: -50}",
    )

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "period_type",
            "period_start",
            name="uq_gst_summary_connection_period",
        ),
        Index("ix_client_gst_summaries_tenant", "tenant_id"),
        Index(
            "ix_gst_summaries_connection_period",
            "connection_id",
            "period_start",
        ),
    )

    def __repr__(self) -> str:
        return f"<ClientGSTSummary(connection_id={self.connection_id}, net_gst={self.net_gst})>"


class ClientMonthlyTrend(Base, TimestampMixin):
    """Client monthly financial trends for Tier 2 context.

    Stores monthly financial metrics for trend analysis.
    Note: Keyed by connection_id (organization).

    Attributes:
        id: Unique identifier.
        tenant_id: Foreign key to tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection (organization).
        year: Year of the month.
        month: Month (1-12).
        revenue: Total revenue for the month.
        expenses: Total expenses for the month.
        gross_profit: Revenue minus cost of goods.
        net_cashflow: Net cash movement.
        computed_at: When the summary was computed.
    """

    __tablename__ = "client_monthly_trends"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Period
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)

    # Financial metrics
    revenue: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    expenses: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    gross_profit: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
        comment="Revenue minus cost of goods sold",
    )
    net_cashflow: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
        comment="Net cash movement for the month",
    )

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "year",
            "month",
            name="uq_monthly_trend_connection_period",
        ),
        Index("ix_client_monthly_trends_tenant", "tenant_id"),
        Index(
            "ix_monthly_trends_connection_year_month",
            "connection_id",
            "year",
            "month",
        ),
    )

    def __repr__(self) -> str:
        return f"<ClientMonthlyTrend(connection_id={self.connection_id}, {self.year}-{self.month:02d})>"


class ClientComplianceSummary(Base, TimestampMixin):
    """Client compliance summary for Tier 2 context (COMPLIANCE intent).

    Stores payroll, super, and contractor payment summaries.
    Note: Keyed by connection_id (organization).

    Attributes:
        id: Unique identifier.
        tenant_id: Foreign key to tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection (organization).
        period_type: Type of period (quarter, year).
        period_start: Start date of the period.
        period_end: End date of the period.
        total_wages: Total wages paid.
        total_payg_withheld: Total PAYG tax withheld.
        total_super: Total superannuation.
        employee_count: Number of employees paid.
        contractor_payments: Total contractor payments.
        contractor_count: Number of contractors paid.
        computed_at: When the summary was computed.
    """

    __tablename__ = "client_compliance_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Period definition
    period_type: Mapped[PeriodType] = mapped_column(
        Enum(
            PeriodType,
            name="period_type",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    # Payroll totals
    total_wages: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
        comment="Total wages paid (BAS W1)",
    )
    total_payg_withheld: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
        comment="Total PAYG tax withheld (BAS W2/4)",
    )
    total_super: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
        comment="Total superannuation",
    )
    employee_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Number of employees paid in period",
    )

    # Contractor payments
    contractor_payments: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
        comment="Total payments to contractors",
    )
    contractor_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Number of contractors paid",
    )

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "period_type",
            "period_start",
            name="uq_compliance_summary_connection_period",
        ),
        Index("ix_client_compliance_summaries_tenant", "tenant_id"),
        Index(
            "ix_compliance_summaries_connection_period",
            "connection_id",
            "period_start",
        ),
    )

    def __repr__(self) -> str:
        return f"<ClientComplianceSummary(connection_id={self.connection_id}, wages={self.total_wages})>"
