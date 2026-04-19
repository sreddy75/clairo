"""SQLAlchemy models for the tax_strategies module (Spec 060).

Schema per specs/060-tax-strategies-kb/data-model.md.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    ARRAY,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TaxStrategy(Base):
    """Authoritative parent record for a single tax planning strategy.

    One row per strategy per version per tenant scope. Chunks (ContentChunk
    rows) point back via tax_strategy_id.

    Lifecycle states (status column):
        stub → researching → drafted → enriched → in_review
             → approved → published → superseded | archived

    Centralised state-transition validation lives in
    TaxStrategyService._transition_status — NO other code path mutates status.
    """

    __tablename__ = "tax_strategies"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    strategy_id: Mapped[str] = mapped_column(String(16), index=True)
    source_ref: Mapped[str | None] = mapped_column(String(32), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="platform", index=True)

    name: Mapped[str] = mapped_column(String(200))
    categories: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    implementation_text: Mapped[str] = mapped_column(Text, default="")
    explanation_text: Mapped[str] = mapped_column(Text, default="")

    # Structured eligibility metadata
    entity_types: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    income_band_min: Mapped[int | None] = mapped_column(Integer)
    income_band_max: Mapped[int | None] = mapped_column(Integer)
    turnover_band_min: Mapped[int | None] = mapped_column(Integer)
    turnover_band_max: Mapped[int | None] = mapped_column(Integer)
    age_min: Mapped[int | None] = mapped_column(Integer)
    age_max: Mapped[int | None] = mapped_column(Integer)
    industry_triggers: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    financial_impact_type: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    ato_sources: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    case_refs: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    # Lifecycle
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="stub", index=True)
    fy_applicable_from: Mapped[date | None] = mapped_column(Date)
    fy_applicable_to: Mapped[date | None] = mapped_column(Date)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewer_clerk_user_id: Mapped[str | None] = mapped_column(String(120))
    reviewer_display_name: Mapped[str | None] = mapped_column(String(200))
    superseded_by_strategy_id: Mapped[str | None] = mapped_column(String(16))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index(
            "uq_tax_strategies_strategy_id_live",
            "strategy_id",
            unique=True,
            postgresql_where="superseded_by_strategy_id IS NULL",
        ),
        Index("ix_tax_strategies_categories", "categories", postgresql_using="gin"),
        Index("ix_tax_strategies_entity_types", "entity_types", postgresql_using="gin"),
        Index(
            "ix_tax_strategies_industry_triggers",
            "industry_triggers",
            postgresql_using="gin",
        ),
        Index("ix_tax_strategies_keywords", "keywords", postgresql_using="gin"),
        Index("ix_tax_strategies_tenant_status", "tenant_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<TaxStrategy {self.strategy_id} v{self.version} status={self.status}>"


class TaxStrategyAuthoringJob(Base):
    """Per-stage pipeline execution tracker.

    A strategy may have multiple rows per (strategy_id, stage) — retries; the
    newest row (by created_at) is the current one. Populates the admin
    pipeline dashboard and per-strategy job history.

    stage ∈ {research, draft, enrich, publish}
    status ∈ {pending, running, succeeded, failed}
    """

    __tablename__ = "tax_strategy_authoring_jobs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    strategy_id: Mapped[str] = mapped_column(String(16), index=True)
    stage: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_payload: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_tax_strategy_authoring_jobs_strategy_stage_created",
            "strategy_id",
            "stage",
            "created_at",
        ),
        Index("ix_tax_strategy_authoring_jobs_stage_status", "stage", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<TaxStrategyAuthoringJob {self.strategy_id} "
            f"stage={self.stage} status={self.status}>"
        )
