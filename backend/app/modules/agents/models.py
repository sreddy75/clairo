"""Database models for agent audit logging."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class AgentQuery(Base, TimestampMixin):
    """Audit log for agent queries.

    Stores metadata about each query processed by the multi-perspective
    orchestrator. Does NOT store query content for privacy.
    """

    __tablename__ = "agent_queries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("practice_users.id"))

    # Client context (optional - for client-specific queries)
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("xero_connections.id"), nullable=True
    )

    # Query analysis (NOT the actual query text)
    query_hash: Mapped[str] = mapped_column(String(64))  # SHA-256 for deduplication
    perspectives_used: Mapped[list[str]] = mapped_column(ARRAY(String(50)))

    # Results
    confidence: Mapped[float] = mapped_column(Float)
    escalation_required: Mapped[bool] = mapped_column(Boolean, default=False)
    escalation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Performance metrics
    processing_time_ms: Mapped[int | None] = mapped_column(nullable=True)
    token_usage: Mapped[int | None] = mapped_column(nullable=True)

    # Additional query metadata (named to avoid conflict with SQLAlchemy Base.metadata)
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_agent_queries_tenant_created", "tenant_id", "created_at"),
        Index("ix_agent_queries_user_created", "user_id", "created_at"),
        # RLS policy will be added via migration
    )


class AgentEscalation(Base, TimestampMixin):
    """Records for queries that required human escalation."""

    __tablename__ = "agent_escalations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_queries.id"), index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), index=True
    )

    # Escalation details
    reason: Mapped[str] = mapped_column(String(255))
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, resolved, dismissed

    # The original query (stored here for escalation review, unlike audit table)
    query_text: Mapped[str] = mapped_column(Text)
    perspectives_used: Mapped[list[str]] = mapped_column(ARRAY(String(50)))

    # Agent's partial analysis (for context when reviewing)
    partial_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Resolution
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("practice_users.id"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Feedback for improvement
    accountant_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_useful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    __table_args__ = (
        Index("ix_agent_escalations_tenant_status", "tenant_id", "status"),
        Index("ix_agent_escalations_pending", "status", "created_at"),
    )
