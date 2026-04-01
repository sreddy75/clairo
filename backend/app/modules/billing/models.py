"""Billing module database models.

This module defines:
- BillingEventStatus enum
- BillingEvent model for tracking subscription and payment events
- UsageAlertType enum (Spec 020)
- UsageSnapshot model for historical usage tracking (Spec 020)
- UsageAlert model for alert deduplication (Spec 020)
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.modules.auth.models import Tenant


class BillingEventStatus(str, enum.Enum):
    """Status of a billing event."""

    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"


class BillingEvent(Base):
    """Billing event model for tracking subscription and payment events.

    Stores all Stripe webhook events for audit and idempotency.
    """

    __tablename__ = "billing_events"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    stripe_event_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    event_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    amount_cents: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="aud",
    )
    status: Mapped[BillingEventStatus] = mapped_column(
        Enum(
            BillingEventStatus,
            name="billing_event_status",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=BillingEventStatus.PROCESSED,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="billing_events")

    __table_args__ = (
        UniqueConstraint("stripe_event_id", name="uq_billing_events_stripe_event_id"),
        Index("ix_billing_events_tenant_id", "tenant_id"),
        Index("ix_billing_events_event_type", "event_type"),
        Index("ix_billing_events_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<BillingEvent(id={self.id}, type={self.event_type}, status={self.status})>"


# =============================================================================
# Usage Tracking Models (Spec 020)
# =============================================================================


class UsageAlertType(str, enum.Enum):
    """Types of usage alerts for threshold notifications.

    Spec 020: Usage Tracking & Limits
    """

    THRESHOLD_80 = "threshold_80"
    THRESHOLD_90 = "threshold_90"
    LIMIT_REACHED = "limit_reached"

    def __str__(self) -> str:
        """Return the enum value as string."""
        return self.value


class UsageSnapshot(Base):
    """Point-in-time usage snapshot for historical tracking.

    Captures tenant usage metrics daily for trend analysis and reporting.

    Spec 020: Usage Tracking & Limits
    """

    __tablename__ = "usage_snapshots"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When this snapshot was captured",
    )
    client_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of active clients at snapshot time",
    )
    ai_queries_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="AI queries in the billing period",
    )
    documents_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Documents processed in the billing period",
    )
    tier: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Subscription tier at snapshot time",
    )
    client_limit: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Client limit at snapshot time (null = unlimited)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="usage_snapshots")

    __table_args__ = (
        CheckConstraint("client_count >= 0", name="ck_usage_snapshots_client_count"),
        CheckConstraint("ai_queries_count >= 0", name="ck_usage_snapshots_ai_queries"),
        CheckConstraint("documents_count >= 0", name="ck_usage_snapshots_documents"),
        Index("ix_usage_snapshots_tenant_id", "tenant_id"),
        Index("ix_usage_snapshots_captured_at", "captured_at"),
        Index("ix_usage_snapshots_tenant_period", "tenant_id", "captured_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<UsageSnapshot(id={self.id}, tenant={self.tenant_id}, captured={self.captured_at})>"
        )


class UsageAlert(Base):
    """Record of usage alerts sent to tenants.

    Used to prevent duplicate alerts for the same threshold in the same billing period.

    Spec 020: Usage Tracking & Limits
    """

    __tablename__ = "usage_alerts"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    alert_type: Mapped[UsageAlertType] = mapped_column(
        Enum(
            UsageAlertType,
            name="usage_alert_type",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        comment="Type of alert (threshold_80, threshold_90, limit_reached)",
    )
    billing_period: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        comment="Billing period in YYYY-MM format",
    )
    threshold_percentage: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Threshold percentage (80, 90, or 100)",
    )
    client_count_at_alert: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Client count when alert was triggered",
    )
    client_limit_at_alert: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Client limit when alert was triggered",
    )
    recipient_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Email address the alert was sent to",
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When the alert email was sent",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="usage_alerts")

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "alert_type",
            "billing_period",
            name="uq_usage_alert_dedup",
        ),
        CheckConstraint(
            "threshold_percentage IN (80, 90, 100)",
            name="ck_usage_alerts_threshold",
        ),
        Index("ix_usage_alerts_tenant_id", "tenant_id"),
        Index("ix_usage_alerts_dedup", "tenant_id", "alert_type", "billing_period"),
    )

    def __repr__(self) -> str:
        return f"<UsageAlert(id={self.id}, type={self.alert_type}, period={self.billing_period})>"
