"""SQLAlchemy models for notifications.

Spec 011: Interim Lodgement - In-app deadline notifications
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NotificationType(str, enum.Enum):
    """Types of in-app notifications."""

    # BAS Deadline notifications
    DEADLINE_APPROACHING = "deadline_approaching"
    DEADLINE_TOMORROW = "deadline_tomorrow"
    DEADLINE_TODAY = "deadline_today"
    DEADLINE_OVERDUE = "deadline_overdue"

    # Review notifications
    REVIEW_REQUESTED = "review_requested"
    REVIEW_OVERDUE = "review_overdue"

    # General
    INFO = "info"
    WARNING = "warning"
    SUCCESS = "success"

    def __str__(self) -> str:
        return self.value


class Notification(Base):
    """In-app notification for users.

    Stores notifications that are displayed in the UI notification center.
    """

    __tablename__ = "notifications"

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

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    notification_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Optional link to the related entity
    entity_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Additional context for UI navigation
    entity_context: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # User who triggered the notification (optional)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Read status
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Timestamps (only created_at, no updated_at in this table)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user = relationship(
        "PracticeUser",
        back_populates="notifications",
        foreign_keys="Notification.user_id",
    )

    def __repr__(self) -> str:
        return f"<Notification {self.id} type={self.notification_type}>"
