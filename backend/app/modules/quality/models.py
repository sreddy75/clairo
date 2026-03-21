"""SQLAlchemy models for quality scoring."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.modules.auth.models import User
    from app.modules.integrations.xero.models import XeroConnection


class IssueSeverity(str, Enum):
    """Severity levels for quality issues."""

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IssueCode(str, Enum):
    """Issue codes for detected quality problems."""

    # Data freshness
    STALE_DATA = "STALE_DATA"
    STALE_DATA_CRITICAL = "STALE_DATA_CRITICAL"

    # Reconciliation
    UNRECONCILED_TXN = "UNRECONCILED_TXN"

    # Categorization
    MISSING_GST_CODE = "MISSING_GST_CODE"
    INVALID_GST_CODE = "INVALID_GST_CODE"

    # Completeness
    NO_INVOICES = "NO_INVOICES"
    NO_TRANSACTIONS = "NO_TRANSACTIONS"

    # PAYG
    MISSING_PAYROLL = "MISSING_PAYROLL"
    INCOMPLETE_PAYROLL = "INCOMPLETE_PAYROLL"


class QualityScore(Base):
    """Quality score for a connection's data for a specific quarter."""

    __tablename__ = "quality_scores"
    __table_args__ = (
        UniqueConstraint(
            "connection_id", "quarter", "fy_year", name="uq_quality_scores_connection_quarter"
        ),
        CheckConstraint("quarter >= 1 AND quarter <= 4", name="ck_quality_scores_quarter_range"),
        CheckConstraint("fy_year >= 2020", name="ck_quality_scores_fy_year_min"),
        CheckConstraint(
            "overall_score >= 0 AND overall_score <= 100", name="ck_quality_scores_overall_range"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("xero_connections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    fy_year: Mapped[int] = mapped_column(Integer, nullable=False)

    # Overall weighted score
    overall_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    # Individual dimension scores (0-100)
    freshness_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    reconciliation_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    categorization_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    completeness_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    payg_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )  # NULL if not applicable

    # Calculation metadata
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    calculation_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trigger_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    connection: Mapped["XeroConnection"] = relationship(
        "XeroConnection", back_populates="quality_scores"
    )

    def __repr__(self) -> str:
        return f"<QualityScore {self.connection_id} Q{self.quarter} FY{self.fy_year}: {self.overall_score}%>"


class QualityIssue(Base):
    """A detected quality issue for a connection."""

    __tablename__ = "quality_issues"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('critical', 'error', 'warning', 'info')",
            name="ck_quality_issues_severity",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("xero_connections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    fy_year: Mapped[int] = mapped_column(Integer, nullable=False)

    # Issue identification
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Affected entities
    affected_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    affected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    affected_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    suggested_action: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Lifecycle
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Dismissal
    dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    dismissed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    connection: Mapped["XeroConnection"] = relationship(
        "XeroConnection", back_populates="quality_issues"
    )
    dismissed_by_user: Mapped["User | None"] = relationship("User")

    @property
    def severity_enum(self) -> IssueSeverity:
        """Get severity as enum."""
        return IssueSeverity(self.severity)

    @property
    def code_enum(self) -> IssueCode:
        """Get code as enum."""
        return IssueCode(self.code)

    def __repr__(self) -> str:
        return f"<QualityIssue {self.code} ({self.severity}) for {self.connection_id}>"
