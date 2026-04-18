"""SQLAlchemy models for the Tax Planning module.

Entities:
    - TaxRateConfig: Australian tax rates stored as configuration data
    - TaxPlan: Tax planning session per client per financial year
    - TaxScenario: What-if scenario within a tax plan
    - TaxPlanMessage: AI chat conversation message
    - TaxPlanAnalysis: Multi-agent pipeline output for a tax plan
    - ImplementationItem: Actionable checklist item within an analysis
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseModel, TenantMixin
from app.modules.tax_planning.strategy_category import StrategyCategory

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EntityType(str, enum.Enum):
    """Supported entity types for tax planning."""

    COMPANY = "company"
    INDIVIDUAL = "individual"
    TRUST = "trust"
    PARTNERSHIP = "partnership"


class TaxPlanStatus(str, enum.Enum):
    """Lifecycle status of a tax plan."""

    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    FINALISED = "finalised"


class DataSource(str, enum.Enum):
    """Source of financial data for a tax plan."""

    XERO = "xero"
    MANUAL = "manual"
    XERO_WITH_ADJUSTMENTS = "xero_with_adjustments"


class RiskRating(str, enum.Enum):
    """Risk level of a tax scenario strategy."""

    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TaxRateConfig(BaseModel):
    """Australian tax rates, thresholds, and offsets.

    One record per financial year per rate type. Stored as configuration data
    so rates can be updated without code deployment.
    """

    __tablename__ = "tax_rate_configs"
    __table_args__ = (
        UniqueConstraint(
            "financial_year",
            "rate_type",
            name="uq_tax_rate_config_year_type",
        ),
        Index("ix_tax_rate_configs_financial_year", "financial_year"),
    )

    financial_year: Mapped[str] = mapped_column(String(10), nullable=False)
    rate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    rates_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class TaxPlan(BaseModel, TenantMixin):
    """A tax planning session for a specific client and financial year.

    One plan per client per FY (enforced by unique constraint).
    Contains base financials (from Xero or manual entry), calculated tax
    position, and status tracking.
    """

    __tablename__ = "tax_plans"
    __table_args__ = (
        UniqueConstraint(
            "xero_connection_id",
            "financial_year",
            name="uq_tax_plan_connection_fy",
        ),
        Index("ix_tax_plans_tenant_status", "tenant_id", "status"),
        Index("ix_tax_plans_xero_connection_id", "xero_connection_id"),
    )

    xero_connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id"),
        nullable=False,
    )
    financial_year: Mapped[str] = mapped_column(String(10), nullable=False)
    entity_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        server_default="draft",
    )
    data_source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    financials_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tax_position: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    xero_report_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Spec 059.1 — user-selectable "as at" anchor for projections. When set,
    # annualisation + P&L to_date + bank balances + unreconciled summary +
    # payroll all use this date instead of the Xero reconciliation date.
    # Null = fall back to `effective_date = recon_date or today` (pre-059.1
    # behaviour). BAS quarter ends (31 Mar, 30 Jun, 30 Sep, 31 Dec) are the
    # typical useful values.
    as_at_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Relationships
    scenarios: Mapped[list["TaxScenario"]] = relationship(
        back_populates="tax_plan",
        cascade="all, delete-orphan",
        order_by="TaxScenario.sort_order",
        lazy="selectin",
    )
    messages: Mapped[list["TaxPlanMessage"]] = relationship(
        back_populates="tax_plan",
        cascade="all, delete-orphan",
        order_by="TaxPlanMessage.created_at",
        lazy="noload",
    )
    analyses: Mapped[list["TaxPlanAnalysis"]] = relationship(
        back_populates="tax_plan",
        cascade="all, delete-orphan",
        lazy="noload",
    )


class TaxScenario(BaseModel, TenantMixin):
    """A modelled what-if scenario within a tax plan.

    Generated by the AI agent. Each scenario shows the impact of a specific
    strategy on the client's tax position.
    """

    __tablename__ = "tax_scenarios"
    __table_args__ = (
        Index("ix_tax_scenarios_tax_plan_id", "tax_plan_id"),
        # Spec 059 FR-030: enforce case-insensitive trimmed title uniqueness per plan.
        # Functional index — not representable via UniqueConstraint on ORM columns.
        Index(
            "ix_tax_scenarios_plan_normalized_title",
            "tax_plan_id",
            text("LOWER(TRIM(title))"),
            unique=True,
        ),
    )

    # Override updated_at — updated during upsert refinements (spec 059 FR-031)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    tax_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    assumptions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    impact_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    risk_rating: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    compliance_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cash_flow_impact: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Spec 059 FR-017: Strategy category and multi-entity honesty flag.
    # Enum type is created by migration 059_tax_planning_correctness; SQLAlchemy
    # must NOT re-create it on model import (create_type=False).
    strategy_category: Mapped[StrategyCategory] = mapped_column(
        SQLEnum(
            StrategyCategory,
            name="strategy_category_enum",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            create_type=False,
        ),
        nullable=False,
        default=StrategyCategory.OTHER,
        server_default=StrategyCategory.OTHER.value,
    )
    requires_group_model: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    # Spec 059 FR-011: Provenance tags keyed by JSON Pointer (RFC 6901) into
    # impact_data and assumptions. Values: "confirmed" | "derived" | "estimated".
    source_tags: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    # Relationships
    tax_plan: Mapped["TaxPlan"] = relationship(back_populates="scenarios")


class TaxPlanMessage(BaseModel, TenantMixin):
    """Conversation message for a tax plan's AI chat session.

    Preserves full history for context-aware follow-ups and plan resumption.
    """

    __tablename__ = "tax_plan_messages"
    __table_args__ = (
        Index(
            "ix_tax_plan_messages_plan_id_created",
            "tax_plan_id",
            "created_at",
        ),
    )

    # Override updated_at — messages are immutable once created
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    tax_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    scenario_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        default=list,
        server_default="{}",
    )
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    # RAG context — which knowledge chunks informed this response
    source_chunks_used: Mapped[list[dict] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Citation verification result for this response
    citation_verification: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    tax_plan: Mapped["TaxPlan"] = relationship(back_populates="messages")


# ---------------------------------------------------------------------------
# Analysis Pipeline Models (Spec 041)
# ---------------------------------------------------------------------------


class AnalysisStatus(str, enum.Enum):
    """Lifecycle status of a tax plan analysis."""

    GENERATING = "generating"
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    SHARED = "shared"


class ImplementationStatus(str, enum.Enum):
    """Status of an implementation checklist item."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class TaxPlanAnalysis(BaseModel, TenantMixin):
    """Stored output of the multi-agent tax planning pipeline.

    One analysis per generation run, versioned for re-generation support.
    Contains all agent outputs: client profile, strategies evaluated,
    recommended scenarios, accountant brief, client summary, and review.
    """

    __tablename__ = "tax_plan_analyses"
    __table_args__ = (
        UniqueConstraint(
            "tax_plan_id",
            "version",
            name="uq_tax_plan_analysis_plan_version",
        ),
        Index("ix_tax_plan_analyses_plan_id", "tax_plan_id"),
        Index("ix_tax_plan_analyses_tenant_status", "tenant_id", "status"),
    )

    tax_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AnalysisStatus.GENERATING.value,
        server_default="generating",
    )

    # Agent outputs
    client_profile: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    strategies_evaluated: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    recommended_scenarios: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    combined_strategy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Documents
    accountant_brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Quality review
    review_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    review_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Phase 2 extension fields (nullable, populated later)
    entities: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    group_structure: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    distribution_plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    entity_summaries: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Metadata
    generation_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    shared_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    tax_plan: Mapped["TaxPlan"] = relationship(
        foreign_keys=[tax_plan_id],
        back_populates="analyses",
    )
    items: Mapped[list["ImplementationItem"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        order_by="ImplementationItem.sort_order",
        lazy="selectin",
    )


class ImplementationItem(BaseModel, TenantMixin):
    """Individual action item within a tax plan analysis.

    Tracks implementation progress across accountant and client portal views.
    """

    __tablename__ = "implementation_items"
    __table_args__ = (
        Index("ix_implementation_items_analysis_id", "analysis_id"),
        Index("ix_implementation_items_tenant_status", "tenant_id", "status"),
    )

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_plan_analyses.id", ondelete="CASCADE"),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    estimated_saving: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    risk_rating: Mapped[str | None] = mapped_column(String(20), nullable=True)
    compliance_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_visible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ImplementationStatus.PENDING.value,
        server_default="pending",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_by: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Relationships
    analysis: Mapped["TaxPlanAnalysis"] = relationship(back_populates="items")
