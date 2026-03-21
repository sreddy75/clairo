"""Trigger database models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TriggerType(str, Enum):
    """Type of trigger."""

    DATA_THRESHOLD = "data_threshold"  # Fires when metric crosses threshold
    TIME_SCHEDULED = "time_scheduled"  # Fires on cron schedule
    EVENT_BASED = "event_based"  # Fires on business event


class TriggerStatus(str, Enum):
    """Status of a trigger."""

    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"  # Auto-disabled after repeated failures


class Trigger(Base):
    """Trigger configuration for proactive insight generation.

    Triggers define when and how insights should be automatically
    generated based on data changes, schedules, or business events.
    """

    __tablename__ = "triggers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)

    # Identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[TriggerType] = mapped_column(String(50), nullable=False)

    # Configuration (type-specific)
    # DATA_THRESHOLD: {"metric": "revenue_ytd", "operator": "gte", "threshold": 75000}
    # TIME_SCHEDULED: {"cron": "0 6 * * *", "timezone": "Australia/Sydney"}
    # EVENT_BASED: {"event": "xero_sync_complete", "conditions": {...}}
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Target analyzers to run when triggered
    target_analyzers: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)),
        nullable=False,
        default=list,
    )

    # Deduplication settings
    dedup_window_hours: Mapped[int] = mapped_column(
        nullable=False,
        default=168,  # 7 days
    )

    # Status tracking
    status: Mapped[TriggerStatus] = mapped_column(
        String(20),
        default=TriggerStatus.ACTIVE,
        nullable=False,
    )
    last_executed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(nullable=False, default=0)

    # Whether this is a system default trigger
    is_system_default: Mapped[bool] = mapped_column(nullable=False, default=False)

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_triggers_tenant", "tenant_id"),
        Index("idx_triggers_type", "tenant_id", "trigger_type"),
        Index("idx_triggers_status", "tenant_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Trigger {self.id}: {self.name} ({self.trigger_type})>"


class TriggerExecution(Base):
    """Record of a trigger execution.

    Tracks when triggers fire, what they generated, and any errors.
    Used for monitoring and debugging trigger behavior.
    """

    __tablename__ = "trigger_executions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    trigger_id: Mapped[UUID] = mapped_column(
        ForeignKey("triggers.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)

    # Execution timing
    started_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)

    # Execution status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="running",
    )  # running, success, failed, partial

    # Results
    clients_evaluated: Mapped[int] = mapped_column(nullable=False, default=0)
    insights_created: Mapped[int] = mapped_column(nullable=False, default=0)
    insights_deduplicated: Mapped[int] = mapped_column(nullable=False, default=0)

    # Client IDs that were processed (for dedup tracking)
    client_ids: Mapped[list[str]] = mapped_column(
        ARRAY(String(36)),
        nullable=False,
        default=list,
    )

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("idx_trigger_executions_trigger", "trigger_id"),
        Index("idx_trigger_executions_tenant", "tenant_id"),
        Index("idx_trigger_executions_started", "trigger_id", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<TriggerExecution {self.id}: trigger={self.trigger_id} status={self.status}>"
