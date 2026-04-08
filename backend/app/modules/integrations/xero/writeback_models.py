"""SQLAlchemy models for Xero tax code write-back.

Spec 049: Xero Tax Code Write-Back.
Defines XeroWritebackJob and XeroWritebackItem models for tracking
write-back operations that push approved tax code changes from Clairo to Xero.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.auth.models import PracticeUser
    from app.modules.bas.models import BASSession
    from app.modules.integrations.xero.models import XeroConnection


# =============================================================================
# Enums
# =============================================================================


class XeroWritebackJobStatus(str, enum.Enum):
    """Status of a Xero write-back job."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"

    def __str__(self) -> str:
        return self.value


class XeroWritebackItemStatus(str, enum.Enum):
    """Status of a single write-back item (one Xero document)."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"

    def __str__(self) -> str:
        return self.value


class XeroWritebackSkipReason(str, enum.Enum):
    """Reason a write-back item was skipped without error."""

    VOIDED = "voided"
    DELETED = "deleted"
    PERIOD_LOCKED = "period_locked"
    RECONCILED = "reconciled"
    AUTHORISED_LOCKED = "authorised_locked"
    CONFLICT_CHANGED = "conflict_changed"
    CREDIT_NOTE_APPLIED = "credit_note_applied"
    INVALID_TAX_TYPE = "invalid_tax_type"

    def __str__(self) -> str:
        return self.value


# =============================================================================
# Models
# =============================================================================


class XeroWritebackJob(Base, TimestampMixin):
    """Represents one "Sync to Xero" invocation triggered by a tax agent.

    Each job tracks the overall outcome of writing multiple approved
    TaxCodeOverride records back to Xero documents.
    """

    __tablename__ = "xero_writeback_jobs"

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
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bas_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=XeroWritebackJobStatus.PENDING.value,
        server_default=XeroWritebackJobStatus.PENDING.value,
    )

    # Counts
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    succeeded_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    skipped_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    failed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Error detail for top-level failures (e.g. auth failure)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    connection: Mapped["XeroConnection"] = relationship(
        foreign_keys=[connection_id],
        lazy="selectin",
    )
    session: Mapped["BASSession"] = relationship(
        foreign_keys=[session_id],
        lazy="selectin",
    )
    triggered_by_user: Mapped["PracticeUser | None"] = relationship(
        foreign_keys=[triggered_by],
        lazy="selectin",
    )
    items: Mapped[list["XeroWritebackItem"]] = relationship(
        back_populates="job",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_xero_writeback_jobs_tenant_session", "tenant_id", "session_id"),
        Index(
            "ix_xero_writeback_jobs_tenant_status",
            "tenant_id",
            "status",
            postgresql_where=~(String(20) == "completed"),  # type: ignore[operator]
        ),
    )

    def __repr__(self) -> str:
        return f"<XeroWritebackJob {self.id} status={self.status} session={self.session_id}>"


class XeroWritebackItem(Base, TimestampMixin):
    """One Xero document to be updated within a write-back job.

    Groups all TaxCodeOverride changes targeting the same Xero document
    into a single API call (to avoid multiple round-trips per document).
    """

    __tablename__ = "xero_writeback_items"

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
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_writeback_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Xero document reference
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    xero_document_id: Mapped[str] = mapped_column(String(255), nullable=False)
    local_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Override IDs and line item changes (arrays)
    override_ids: Mapped[list[Any]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        default=list,
        server_default="{}",
    )
    line_item_indexes: Mapped[list[int]] = mapped_column(
        ARRAY(Integer),
        nullable=False,
        default=list,
        server_default="{}",
    )

    # Before/after snapshot for audit trail
    before_tax_types: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    after_tax_types: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=XeroWritebackItemStatus.PENDING.value,
        server_default=XeroWritebackItemStatus.PENDING.value,
    )
    skip_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    xero_http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    job: Mapped["XeroWritebackJob"] = relationship(
        back_populates="items",
    )

    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "source_type",
            "xero_document_id",
            name="uq_writeback_item_job_source_doc",
        ),
        Index("ix_xero_writeback_items_tenant_job", "tenant_id", "job_id"),
        Index(
            "ix_xero_writeback_items_tenant_status_failed",
            "tenant_id",
            "status",
            postgresql_where=~(String(20) == "failed"),  # type: ignore[operator]
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<XeroWritebackItem {self.id} job={self.job_id}"
            f" doc={self.xero_document_id} status={self.status}>"
        )
