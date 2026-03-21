"""SQLAlchemy models for the Client Portal module.

This module defines:
- PortalInvitation: Tracks client invitations to the portal
- PortalSession: Manages authenticated client sessions
- DocumentRequestTemplate: Reusable templates for document requests
- DocumentRequest: Core entity for document requests (ClientChase)
- RequestResponse: Client's response to a document request
- PortalDocument: Documents uploaded through the portal
- RequestEvent: Event sourcing for request status changes
- BulkRequest: Tracks bulk request batches

Note: In Clairo, "client" = XeroConnection = one business = one BAS to lodge.
The portal is used by business owners of XeroConnection entities.

Spec: 030-client-portal-document-requests
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin
from app.modules.portal.enums import (
    BulkRequestStatus,
    InvitationStatus,
    RequestPriority,
    RequestStatus,
)

if TYPE_CHECKING:
    from app.modules.auth.models import Tenant, User
    from app.modules.integrations.xero.models import XeroConnection


# =============================================================================
# Portal Invitation
# =============================================================================


class PortalInvitation(Base, TimestampMixin):
    """Portal invitation sent to a client (XeroConnection).

    In Clairo, 'client' = XeroConnection = one business = one BAS to lodge.
    This invitation is sent to the business owner to access the portal.
    """

    __tablename__ = "portal_invitations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("xero_connections.id"), index=True, nullable=False
    )

    # Invitation details
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # SHA-256 hash

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(20), default=InvitationStatus.PENDING.value, nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Delivery tracking
    email_delivered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_bounced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bounce_reason: Mapped[str | None] = mapped_column(String(255))

    # Metadata
    invited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Relationships
    tenant: Mapped[Tenant] = relationship("Tenant")
    connection: Mapped[XeroConnection] = relationship("XeroConnection")
    inviter: Mapped[User] = relationship("User")

    __table_args__ = (Index("ix_portal_invitations_connection_status", "connection_id", "status"),)


# =============================================================================
# Portal Session
# =============================================================================


class PortalSession(Base, TimestampMixin):
    """Authenticated portal session for a client (XeroConnection).

    In Clairo, 'client' = XeroConnection = one business = one BAS to lodge.
    This session allows the business owner to access the portal.
    """

    __tablename__ = "portal_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("xero_connections.id"), index=True, nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False
    )

    # Token tracking (hashed for security)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    # Device information
    device_fingerprint: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    ip_address: Mapped[str | None] = mapped_column(String(45))

    # Timestamps
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Revocation
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(String(255))

    # Relationships
    connection: Mapped[XeroConnection] = relationship("XeroConnection")
    tenant: Mapped[Tenant] = relationship("Tenant")

    __table_args__ = (Index("ix_portal_sessions_active", "connection_id", "revoked", "expires_at"),)


# =============================================================================
# Document Request Template
# =============================================================================


class DocumentRequestTemplate(Base, TimestampMixin):
    """Template for document requests."""

    __tablename__ = "document_request_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), index=True
    )
    # tenant_id = None for system templates

    # Template details
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description_template: Mapped[str] = mapped_column(Text, nullable=False)
    expected_document_types: Mapped[list[str]] = mapped_column(ARRAY(String(50)), default=list)
    icon: Mapped[str | None] = mapped_column(String(50))

    # Defaults
    default_priority: Mapped[str] = mapped_column(
        String(20), default=RequestPriority.NORMAL.value, nullable=False
    )
    default_due_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)

    # Flags
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Tracking
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Relationships
    tenant: Mapped[Tenant | None] = relationship("Tenant")
    creator: Mapped[User | None] = relationship("User")

    __table_args__ = (Index("ix_templates_tenant_active", "tenant_id", "is_active"),)


# =============================================================================
# Document Request
# =============================================================================


class DocumentRequest(Base, TimestampMixin):
    """Document request sent to a client (ClientChase).

    In Clairo, 'client' = XeroConnection = one business = one BAS to lodge.
    This is the core entity for the ClientChase document request workflow.
    """

    __tablename__ = "document_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("xero_connections.id"), index=True, nullable=False
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_request_templates.id")
    )

    # Request details
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    priority: Mapped[str] = mapped_column(
        String(20), default=RequestPriority.NORMAL.value, nullable=False
    )

    # Period context (for auto-filing)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(20), default=RequestStatus.PENDING.value, index=True, nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Reminder settings
    auto_remind: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reminder_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Bulk request tracking
    bulk_request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)

    # Tracking
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    completed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    # Relationships
    tenant: Mapped[Tenant] = relationship("Tenant")
    connection: Mapped[XeroConnection] = relationship("XeroConnection")
    template: Mapped[DocumentRequestTemplate | None] = relationship("DocumentRequestTemplate")
    creator: Mapped[User] = relationship("User", foreign_keys=[created_by])
    completer: Mapped[User | None] = relationship("User", foreign_keys=[completed_by])
    responses: Mapped[list[RequestResponse]] = relationship(
        "RequestResponse", back_populates="request", cascade="all, delete-orphan"
    )
    events: Mapped[list[RequestEvent]] = relationship(
        "RequestEvent", back_populates="request", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_requests_tenant_status", "tenant_id", "status"),
        Index("ix_requests_connection_status", "connection_id", "status"),
        Index("ix_requests_due_date", "status", "due_date"),
        Index("ix_requests_bulk", "bulk_request_id"),
    )


# =============================================================================
# Request Response
# =============================================================================


class RequestResponse(Base, TimestampMixin):
    """Client response to a document request.

    Submitted by the business owner through the portal.
    """

    __tablename__ = "request_responses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_requests.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("xero_connections.id"), index=True, nullable=False
    )

    # Response content
    note: Mapped[str | None] = mapped_column(Text)

    # Submission tracking
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ip_address: Mapped[str | None] = mapped_column(String(45))

    # Relationships
    request: Mapped[DocumentRequest] = relationship("DocumentRequest", back_populates="responses")
    connection: Mapped[XeroConnection] = relationship("XeroConnection")
    documents: Mapped[list[PortalDocument]] = relationship(
        "PortalDocument", back_populates="response", cascade="all, delete-orphan"
    )


# =============================================================================
# Portal Document
# =============================================================================


class PortalDocument(Base, TimestampMixin):
    """Document uploaded through the client portal.

    Documents are stored in S3/MinIO with virus scanning.
    """

    __tablename__ = "portal_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("xero_connections.id"), index=True, nullable=False
    )
    response_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("request_responses.id"),
        index=True,
    )

    # File details
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # bytes

    # Storage
    s3_bucket: Mapped[str] = mapped_column(String(100), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)

    # Auto-filing metadata
    document_type: Mapped[str | None] = mapped_column(String(50), index=True)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)))

    # Tracking
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    uploaded_by_client: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Virus scan status
    scan_status: Mapped[str | None] = mapped_column(String(20))
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    tenant: Mapped[Tenant] = relationship("Tenant")
    connection: Mapped[XeroConnection] = relationship("XeroConnection")
    response: Mapped[RequestResponse | None] = relationship(
        "RequestResponse", back_populates="documents"
    )

    __table_args__ = (
        Index("ix_portal_docs_connection_type", "connection_id", "document_type"),
        Index("ix_portal_docs_period", "connection_id", "period_start", "period_end"),
    )


# =============================================================================
# Request Event
# =============================================================================


class RequestEvent(Base):
    """Event log for document request lifecycle."""

    __tablename__ = "request_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_requests.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Event details
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_data: Mapped[dict | None] = mapped_column(JSONB)

    # Actor information
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # User or Client ID

    # Context
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )

    # Relationships
    request: Mapped[DocumentRequest] = relationship("DocumentRequest", back_populates="events")

    __table_args__ = (Index("ix_request_events_type", "request_id", "event_type"),)


# =============================================================================
# Bulk Request
# =============================================================================


class BulkRequest(Base, TimestampMixin):
    """Bulk document request batch."""

    __tablename__ = "bulk_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False
    )

    # Batch details
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_request_templates.id")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)

    # Stats
    total_clients: Mapped[int] = mapped_column(Integer, nullable=False)
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default=BulkRequestStatus.PENDING.value, nullable=False
    )

    # Tracking
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    tenant: Mapped[Tenant] = relationship("Tenant")
    template: Mapped[DocumentRequestTemplate | None] = relationship("DocumentRequestTemplate")
    creator: Mapped[User] = relationship("User")
