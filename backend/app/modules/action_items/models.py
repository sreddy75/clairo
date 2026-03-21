"""Action Item database models."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ActionItemStatus(str, Enum):
    """Status of an action item."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ActionItemPriority(str, Enum):
    """Priority levels for action items."""

    URGENT = "urgent"  # Do today
    HIGH = "high"  # This week
    MEDIUM = "medium"  # This month
    LOW = "low"  # When possible


class ActionItem(Base):
    """Curated action item created from insights or manually.

    Action items represent work that an accountant has decided
    needs to be done, optionally derived from AI-generated insights.
    """

    __tablename__ = "action_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)

    # Content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # Internal notes

    # Source insight (optional - can be standalone)
    source_insight_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("insights.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Client context (optional)
    client_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("xero_connections.id", ondelete="SET NULL"),
        nullable=True,
    )
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Assignment
    assigned_to_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    assigned_to_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    assigned_by_user_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Scheduling
    due_date: Mapped[date | None] = mapped_column(nullable=True)
    priority: Mapped[ActionItemPriority] = mapped_column(
        String(20),
        default=ActionItemPriority.MEDIUM,
        nullable=False,
    )

    # Status tracking
    status: Mapped[ActionItemStatus] = mapped_column(
        String(20),
        default=ActionItemStatus.PENDING,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Completion notes
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    source_insight = relationship("Insight", foreign_keys=[source_insight_id])
    client = relationship("XeroConnection", foreign_keys=[client_id])

    __table_args__ = (
        Index("idx_action_items_tenant", "tenant_id"),
        Index("idx_action_items_status", "tenant_id", "status"),
        Index("idx_action_items_assigned", "tenant_id", "assigned_to_user_id"),
        Index("idx_action_items_due_date", "tenant_id", "due_date"),
        Index("idx_action_items_client", "tenant_id", "client_id"),
        Index("idx_action_items_insight", "source_insight_id"),
    )

    def __repr__(self) -> str:
        return f"<ActionItem {self.id}: {self.title[:30]}...>"
