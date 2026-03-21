# Data Model: Client Portal Foundation + Document Requests

**Spec**: 030-client-portal-document-requests
**Date**: 2026-01-01

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA MODEL OVERVIEW                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐         ┌─────────────────┐                       │
│  │     Tenant      │◄────────│     Client      │                       │
│  │   (existing)    │   1:N   │   (existing)    │                       │
│  └─────────────────┘         └────────┬────────┘                       │
│                                       │                                 │
│         ┌─────────────────────────────┼─────────────────────────────┐  │
│         │                             │                             │  │
│         ▼                             ▼                             ▼  │
│  ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  │PortalInvitation │         │  PortalSession  │         │DocumentRequest  │
│  │                 │         │                 │         │                 │
│  │ - magic_link    │         │ - access_token  │         │ - title         │
│  │ - expires_at    │         │ - refresh_token │         │ - due_date      │
│  │ - status        │         │ - device_info   │         │ - status        │
│  └─────────────────┘         └─────────────────┘         └────────┬────────┘
│                                                                   │         │
│                                                                   │ 1:N     │
│                                                                   ▼         │
│  ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  │ DocumentRequest │◄────────│  RequestEvent   │         │RequestResponse  │
│  │    Template     │   N:1   │                 │         │                 │
│  │                 │         │ - event_type    │         │ - note          │
│  │ - name          │         │ - actor_id      │         │ - documents     │
│  │ - description   │         │ - created_at    │         │ - submitted_at  │
│  └─────────────────┘         └─────────────────┘         └────────┬────────┘
│                                                                   │         │
│                                                                   │ 1:N     │
│                                                                   ▼         │
│                                                          ┌─────────────────┐
│                                                          │PortalDocument   │
│                                                          │                 │
│                                                          │ - filename      │
│                                                          │ - s3_key        │
│                                                          │ - document_type │
│                                                          └─────────────────┘
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. PortalInvitation

Tracks client invitations to the portal.

```python
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from enum import Enum
from sqlalchemy import String, Text, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InvitationStatus(str, Enum):
    """Status of portal invitation."""
    PENDING = "PENDING"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class PortalInvitation(Base):
    """Portal invitation sent to a client."""
    __tablename__ = "portal_invitations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"), index=True)

    # Invitation details
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # SHA-256 hash

    # Status tracking
    status: Mapped[str] = mapped_column(String(20), default=InvitationStatus.PENDING)
    sent_at: Mapped[datetime | None] = mapped_column()
    accepted_at: Mapped[datetime | None] = mapped_column()
    expires_at: Mapped[datetime] = mapped_column()

    # Delivery tracking
    email_delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    email_bounced: Mapped[bool] = mapped_column(Boolean, default=False)
    bounce_reason: Mapped[str | None] = mapped_column(String(255))

    # Metadata
    invited_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    client = relationship("Client", back_populates="portal_invitations")
    inviter = relationship("User")

    __table_args__ = (
        Index("ix_portal_invitations_client_status", "client_id", "status"),
    )
```

---

## 2. PortalSession

Manages authenticated client sessions.

```python
class PortalSession(Base):
    """Authenticated portal session for a client."""
    __tablename__ = "portal_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)

    # Token tracking (hashed for security)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True)

    # Device information
    device_fingerprint: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    ip_address: Mapped[str | None] = mapped_column(String(45))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    last_active_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column()

    # Revocation
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column()
    revoke_reason: Mapped[str | None] = mapped_column(String(255))

    # Relationships
    client = relationship("Client", back_populates="portal_sessions")

    __table_args__ = (
        Index("ix_portal_sessions_active", "client_id", "revoked", "expires_at"),
    )
```

---

## 3. DocumentRequestTemplate

Reusable templates for document requests.

```python
class DocumentRequestTemplate(Base):
    """Template for document requests."""
    __tablename__ = "document_request_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID | None] = mapped_column(ForeignKey("tenants.id"), index=True)
    # tenant_id = None for system templates

    # Template details
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description_template: Mapped[str] = mapped_column(Text)
    expected_document_types: Mapped[list[str]] = mapped_column(ARRAY(String))
    icon: Mapped[str | None] = mapped_column(String(50))

    # Defaults
    default_priority: Mapped[str] = mapped_column(String(20), default="NORMAL")
    default_due_days: Mapped[int] = mapped_column(default=7)

    # Flags
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Tracking
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    creator = relationship("User")

    __table_args__ = (
        Index("ix_templates_tenant_active", "tenant_id", "is_active"),
    )
```

---

## 4. DocumentRequest

Core entity for document requests (ClientChase).

```python
class RequestStatus(str, Enum):
    """Status of a document request."""
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    VIEWED = "VIEWED"
    RESPONDED = "RESPONDED"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"


class RequestPriority(str, Enum):
    """Priority level for requests."""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class DocumentRequest(Base):
    """Document request sent to a client."""
    __tablename__ = "document_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    template_id: Mapped[UUID | None] = mapped_column(ForeignKey("document_request_templates.id"))

    # Request details
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text)
    due_date: Mapped[date | None] = mapped_column()
    priority: Mapped[str] = mapped_column(String(20), default=RequestPriority.NORMAL)

    # Period context (for auto-filing)
    period_start: Mapped[date | None] = mapped_column()
    period_end: Mapped[date | None] = mapped_column()

    # Status tracking
    status: Mapped[str] = mapped_column(String(20), default=RequestStatus.PENDING, index=True)
    sent_at: Mapped[datetime | None] = mapped_column()
    viewed_at: Mapped[datetime | None] = mapped_column()
    responded_at: Mapped[datetime | None] = mapped_column()
    completed_at: Mapped[datetime | None] = mapped_column()

    # Reminder settings
    auto_remind: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_count: Mapped[int] = mapped_column(default=0)
    last_reminder_at: Mapped[datetime | None] = mapped_column()

    # Bulk request tracking
    bulk_request_id: Mapped[UUID | None] = mapped_column(index=True)

    # Tracking
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    completed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    client = relationship("Client", back_populates="document_requests")
    template = relationship("DocumentRequestTemplate")
    creator = relationship("User", foreign_keys=[created_by])
    completer = relationship("User", foreign_keys=[completed_by])
    responses = relationship("RequestResponse", back_populates="request")
    events = relationship("RequestEvent", back_populates="request")

    __table_args__ = (
        Index("ix_requests_tenant_status", "tenant_id", "status"),
        Index("ix_requests_client_status", "client_id", "status"),
        Index("ix_requests_due_date", "status", "due_date"),
        Index("ix_requests_bulk", "bulk_request_id"),
    )
```

---

## 5. RequestResponse

Client's response to a document request.

```python
class RequestResponse(Base):
    """Client response to a document request."""
    __tablename__ = "request_responses"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_requests.id", ondelete="CASCADE"),
        index=True,
    )
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"), index=True)

    # Response content
    note: Mapped[str | None] = mapped_column(Text)

    # Submission tracking
    submitted_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    ip_address: Mapped[str | None] = mapped_column(String(45))

    # Relationships
    request = relationship("DocumentRequest", back_populates="responses")
    documents = relationship("PortalDocument", back_populates="response")
```

---

## 6. PortalDocument

Documents uploaded through the portal.

```python
class PortalDocument(Base):
    """Document uploaded through the client portal."""
    __tablename__ = "portal_documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    response_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("request_responses.id"),
        index=True,
    )

    # File details
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column()  # bytes

    # Storage
    s3_bucket: Mapped[str] = mapped_column(String(100))
    s3_key: Mapped[str] = mapped_column(String(500), unique=True)

    # Auto-filing metadata
    document_type: Mapped[str | None] = mapped_column(String(50), index=True)
    period_start: Mapped[date | None] = mapped_column()
    period_end: Mapped[date | None] = mapped_column()
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    # Tracking
    uploaded_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    uploaded_by_client: Mapped[bool] = mapped_column(Boolean, default=True)

    # Virus scan status
    scan_status: Mapped[str | None] = mapped_column(String(20))  # PENDING, CLEAN, INFECTED
    scanned_at: Mapped[datetime | None] = mapped_column()

    # Relationships
    tenant = relationship("Tenant")
    client = relationship("Client", back_populates="portal_documents")
    response = relationship("RequestResponse", back_populates="documents")

    __table_args__ = (
        Index("ix_portal_docs_client_type", "client_id", "document_type"),
        Index("ix_portal_docs_period", "client_id", "period_start", "period_end"),
    )
```

---

## 7. RequestEvent

Event sourcing for request status changes.

```python
class RequestEventType(str, Enum):
    """Types of request events."""
    CREATED = "CREATED"
    SENT = "SENT"
    VIEWED = "VIEWED"
    RESPONDED = "RESPONDED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REMINDER_SENT = "REMINDER_SENT"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_REMOVED = "DOCUMENT_REMOVED"


class ActorType(str, Enum):
    """Type of actor for event."""
    SYSTEM = "SYSTEM"
    ACCOUNTANT = "ACCOUNTANT"
    CLIENT = "CLIENT"


class RequestEvent(Base):
    """Event log for document request lifecycle."""
    __tablename__ = "request_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_requests.id", ondelete="CASCADE"),
        index=True,
    )

    # Event details
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_data: Mapped[dict | None] = mapped_column(JSONB)

    # Actor information
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column()  # User or Client ID

    # Context
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    # Relationships
    request = relationship("DocumentRequest", back_populates="events")

    __table_args__ = (
        Index("ix_request_events_type", "request_id", "event_type"),
    )
```

---

## 8. BulkRequest

Tracks bulk request batches.

```python
class BulkRequestStatus(str, Enum):
    """Status of bulk request batch."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class BulkRequest(Base):
    """Bulk document request batch."""
    __tablename__ = "bulk_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)

    # Batch details
    template_id: Mapped[UUID | None] = mapped_column(ForeignKey("document_request_templates.id"))
    title: Mapped[str] = mapped_column(String(200))
    due_date: Mapped[date | None] = mapped_column()

    # Stats
    total_clients: Mapped[int] = mapped_column()
    sent_count: Mapped[int] = mapped_column(default=0)
    failed_count: Mapped[int] = mapped_column(default=0)

    # Status
    status: Mapped[str] = mapped_column(String(20), default=BulkRequestStatus.PENDING)

    # Tracking
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column()

    # Relationships
    tenant = relationship("Tenant")
    template = relationship("DocumentRequestTemplate")
    creator = relationship("User")
```

---

## Indexes Summary

| Table | Index | Columns | Purpose |
|-------|-------|---------|---------|
| portal_invitations | ix_portal_invitations_client_status | client_id, status | Find active invitations |
| portal_sessions | ix_portal_sessions_active | client_id, revoked, expires_at | Active session lookup |
| document_request_templates | ix_templates_tenant_active | tenant_id, is_active | Template selection |
| document_requests | ix_requests_tenant_status | tenant_id, status | Dashboard queries |
| document_requests | ix_requests_client_status | client_id, status | Client portal |
| document_requests | ix_requests_due_date | status, due_date | Reminder job |
| document_requests | ix_requests_bulk | bulk_request_id | Bulk tracking |
| portal_documents | ix_portal_docs_client_type | client_id, document_type | Auto-filing |
| portal_documents | ix_portal_docs_period | client_id, period_start, period_end | Period queries |
| request_events | ix_request_events_type | request_id, event_type | Event queries |

---

## Migration Notes

```python
# Alembic migration
def upgrade():
    # 1. Create portal tables
    op.create_table("portal_invitations", ...)
    op.create_table("portal_sessions", ...)
    op.create_table("document_request_templates", ...)
    op.create_table("document_requests", ...)
    op.create_table("request_responses", ...)
    op.create_table("portal_documents", ...)
    op.create_table("request_events", ...)
    op.create_table("bulk_requests", ...)

    # 2. Add foreign keys to existing clients table
    op.add_column("clients", Column("portal_enabled", Boolean, default=False))
    op.add_column("clients", Column("portal_invited_at", DateTime))
    op.add_column("clients", Column("portal_last_login_at", DateTime))

    # 3. Create system templates
    op.execute("""
        INSERT INTO document_request_templates (id, name, description_template, ...)
        VALUES
            (gen_random_uuid(), 'Bank Statements', 'Please upload...', ...),
            (gen_random_uuid(), 'BAS Source Documents', 'Please provide...', ...),
            ...
    """)

    # 4. Add RLS policies
    op.execute("""
        ALTER TABLE document_requests ENABLE ROW LEVEL SECURITY;
        CREATE POLICY tenant_isolation ON document_requests
            FOR ALL USING (tenant_id = current_setting('app.current_tenant')::uuid);
    """)
```
