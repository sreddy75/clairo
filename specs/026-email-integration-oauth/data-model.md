# Data Model: Email Integration & OAuth

**Feature**: 026-email-integration-oauth
**Date**: 2026-01-01

---

## Entity Overview

| Entity | Description | Source |
|--------|-------------|--------|
| EmailConnection | OAuth connection with encrypted tokens | User action |
| EmailSyncJob | Sync job tracking | System |
| RawEmail | Stored email with metadata | Gmail/Microsoft API |
| EmailAttachment | Attachment metadata and storage reference | Gmail/Microsoft API |

---

## Enums

### EmailProvider

```python
class EmailProvider(str, enum.Enum):
    """Email provider for OAuth connection."""
    GMAIL = "GMAIL"
    OUTLOOK = "OUTLOOK"
    FORWARDING = "FORWARDING"
```

### ConnectionStatus

```python
class ConnectionStatus(str, enum.Enum):
    """Email connection status."""
    PENDING = "PENDING"      # OAuth initiated, awaiting callback
    ACTIVE = "ACTIVE"        # Connected and syncing
    EXPIRED = "EXPIRED"      # Token refresh failed
    REVOKED = "REVOKED"      # User revoked access
    DISCONNECTED = "DISCONNECTED"  # User disconnected
```

### SyncJobStatus

```python
class SyncJobStatus(str, enum.Enum):
    """Email sync job status."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
```

### SyncJobType

```python
class SyncJobType(str, enum.Enum):
    """Type of sync job."""
    INITIAL_BACKFILL = "INITIAL_BACKFILL"
    INCREMENTAL = "INCREMENTAL"
```

---

## Entity Definitions

### EmailConnection

OAuth connection for email access.

```python
class EmailConnection(TenantBase):
    """OAuth email connection with encrypted tokens."""
    __tablename__ = "email_connections"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)

    # Provider info
    provider: Mapped[EmailProvider] = mapped_column(nullable=False)
    email_address: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))

    # OAuth tokens (encrypted)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Sync state
    sync_cursor: Mapped[str | None] = mapped_column(String(500))  # historyId or deltaToken
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_email_count: Mapped[int] = mapped_column(default=0)

    # Status
    status: Mapped[ConnectionStatus] = mapped_column(default=ConnectionStatus.PENDING)
    status_reason: Mapped[str | None] = mapped_column(String(500))

    # Forwarding-specific (for FORWARDING provider)
    forwarding_address: Mapped[str | None] = mapped_column(String(255))

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(onupdate=func.now())

    # Relationships
    sync_jobs: Mapped[list["EmailSyncJob"]] = relationship(back_populates="connection")
    emails: Mapped[list["RawEmail"]] = relationship(back_populates="connection")
```

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | UUID | No | Primary key |
| tenant_id | UUID | No | FK to tenants |
| provider | Enum | No | GMAIL, OUTLOOK, or FORWARDING |
| email_address | String(255) | No | Connected email address |
| display_name | String(255) | Yes | User's display name |
| access_token_encrypted | Text | No | AES-256 encrypted access token |
| refresh_token_encrypted | Text | Yes | AES-256 encrypted refresh token |
| token_expires_at | DateTime | No | When access token expires |
| sync_cursor | String(500) | Yes | historyId (Gmail) or deltaToken (Microsoft) |
| last_sync_at | DateTime | Yes | Last successful sync time |
| status | Enum | No | Connection status |
| forwarding_address | String(255) | Yes | For FORWARDING provider |

---

### EmailSyncJob

Tracks sync job execution.

```python
class EmailSyncJob(TenantBase):
    """Email sync job tracking."""
    __tablename__ = "email_sync_jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    connection_id: Mapped[UUID] = mapped_column(ForeignKey("email_connections.id"), index=True)

    # Job details
    job_type: Mapped[SyncJobType] = mapped_column(nullable=False)
    status: Mapped[SyncJobStatus] = mapped_column(default=SyncJobStatus.PENDING)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Results
    emails_found: Mapped[int] = mapped_column(default=0)
    emails_synced: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    # Cursor state
    start_cursor: Mapped[str | None] = mapped_column(String(500))
    end_cursor: Mapped[str | None] = mapped_column(String(500))

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    connection: Mapped["EmailConnection"] = relationship(back_populates="sync_jobs")
```

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | UUID | No | Primary key |
| connection_id | UUID | No | FK to email_connections |
| job_type | Enum | No | INITIAL_BACKFILL or INCREMENTAL |
| status | Enum | No | Job status |
| started_at | DateTime | Yes | When job started |
| completed_at | DateTime | Yes | When job finished |
| emails_found | Integer | No | Total emails matching filter |
| emails_synced | Integer | No | Emails successfully synced |
| error_message | Text | Yes | Error details if failed |

---

### RawEmail

Stored email with full content.

```python
class RawEmail(TenantBase):
    """Raw email stored from provider."""
    __tablename__ = "raw_emails"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    connection_id: Mapped[UUID] = mapped_column(ForeignKey("email_connections.id"), index=True)

    # Provider reference
    provider_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    thread_id: Mapped[str | None] = mapped_column(String(255))

    # Email metadata
    from_address: Mapped[str] = mapped_column(String(255), nullable=False)
    from_name: Mapped[str | None] = mapped_column(String(255))
    to_addresses: Mapped[list] = mapped_column(JSONB, default=list)
    cc_addresses: Mapped[list] = mapped_column(JSONB, default=list)
    subject: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Content
    body_text: Mapped[str | None] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(String(500))

    # Headers (for parsing)
    headers: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Status
    is_read: Mapped[bool] = mapped_column(default=False)
    is_processed: Mapped[bool] = mapped_column(default=False)  # Parsed by Spec 027

    # Metadata
    synced_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    connection: Mapped["EmailConnection"] = relationship(back_populates="emails")
    attachments: Mapped[list["EmailAttachment"]] = relationship(back_populates="email")

    # Unique constraint
    __table_args__ = (
        UniqueConstraint('connection_id', 'provider_message_id', name='uq_email_provider_message'),
    )
```

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | UUID | No | Primary key |
| connection_id | UUID | No | FK to email_connections |
| provider_message_id | String(255) | No | Gmail/Microsoft message ID |
| thread_id | String(255) | Yes | Email thread ID |
| from_address | String(255) | No | Sender email |
| from_name | String(255) | Yes | Sender display name |
| to_addresses | JSONB | No | List of recipients |
| subject | Text | Yes | Email subject |
| received_at | DateTime | No | When email was received |
| body_text | Text | Yes | Plain text body |
| body_html | Text | Yes | HTML body |
| headers | JSONB | No | All email headers |
| is_read | Boolean | No | Viewed in Clairo |
| is_processed | Boolean | No | Parsed by Spec 027 |

---

### EmailAttachment

Attachment metadata.

```python
class EmailAttachment(TenantBase):
    """Email attachment metadata."""
    __tablename__ = "email_attachments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    email_id: Mapped[UUID] = mapped_column(ForeignKey("raw_emails.id"), index=True)

    # Provider reference
    provider_attachment_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Attachment details
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(default=0)

    # Storage
    storage_key: Mapped[str | None] = mapped_column(String(500))  # S3/MinIO key
    is_downloaded: Mapped[bool] = mapped_column(default=False)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    email: Mapped["RawEmail"] = relationship(back_populates="attachments")
```

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | UUID | No | Primary key |
| email_id | UUID | No | FK to raw_emails |
| provider_attachment_id | String(255) | No | Provider's attachment ID |
| filename | String(255) | No | Attachment filename |
| content_type | String(100) | Yes | MIME type |
| size_bytes | Integer | No | File size |
| storage_key | String(500) | Yes | S3/MinIO object key |
| is_downloaded | Boolean | No | Whether content is stored |

---

## Database Indexes

```sql
-- Connection lookups
CREATE INDEX idx_email_connections_tenant ON email_connections(tenant_id);
CREATE INDEX idx_email_connections_status ON email_connections(status);
CREATE INDEX idx_email_connections_expires ON email_connections(token_expires_at);

-- Sync job lookups
CREATE INDEX idx_email_sync_jobs_connection ON email_sync_jobs(connection_id);
CREATE INDEX idx_email_sync_jobs_status ON email_sync_jobs(status);

-- Email lookups
CREATE INDEX idx_raw_emails_connection ON raw_emails(connection_id);
CREATE INDEX idx_raw_emails_received ON raw_emails(received_at DESC);
CREATE INDEX idx_raw_emails_from ON raw_emails(from_address);
CREATE INDEX idx_raw_emails_processed ON raw_emails(is_processed) WHERE NOT is_processed;

-- Attachment lookups
CREATE INDEX idx_email_attachments_email ON email_attachments(email_id);
```

---

## Migration Template

```python
"""Add email integration tables.

Revision ID: xxx
Create Date: 2026-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

def upgrade() -> None:
    # Email connections
    op.create_table(
        "email_connections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("email_address", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255)),
        sa.Column("access_token_encrypted", sa.Text, nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sync_cursor", sa.String(500)),
        sa.Column("last_sync_at", sa.DateTime(timezone=True)),
        sa.Column("last_sync_email_count", sa.Integer, default=0),
        sa.Column("status", sa.String(20), nullable=False, default="PENDING"),
        sa.Column("status_reason", sa.String(500)),
        sa.Column("forwarding_address", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Email sync jobs
    op.create_table(
        "email_sync_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("connection_id", UUID(as_uuid=True), sa.ForeignKey("email_connections.id"), nullable=False),
        sa.Column("job_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="PENDING"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("emails_found", sa.Integer, default=0),
        sa.Column("emails_synced", sa.Integer, default=0),
        sa.Column("error_message", sa.Text),
        sa.Column("start_cursor", sa.String(500)),
        sa.Column("end_cursor", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Raw emails
    op.create_table(
        "raw_emails",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("connection_id", UUID(as_uuid=True), sa.ForeignKey("email_connections.id"), nullable=False),
        sa.Column("provider_message_id", sa.String(255), nullable=False),
        sa.Column("thread_id", sa.String(255)),
        sa.Column("from_address", sa.String(255), nullable=False),
        sa.Column("from_name", sa.String(255)),
        sa.Column("to_addresses", JSONB, default=[]),
        sa.Column("cc_addresses", JSONB, default=[]),
        sa.Column("subject", sa.Text),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("body_text", sa.Text),
        sa.Column("body_html", sa.Text),
        sa.Column("snippet", sa.String(500)),
        sa.Column("headers", JSONB, default={}),
        sa.Column("is_read", sa.Boolean, default=False),
        sa.Column("is_processed", sa.Boolean, default=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('connection_id', 'provider_message_id', name='uq_email_provider_message'),
    )

    # Email attachments
    op.create_table(
        "email_attachments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email_id", UUID(as_uuid=True), sa.ForeignKey("raw_emails.id"), nullable=False),
        sa.Column("provider_attachment_id", sa.String(255), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100)),
        sa.Column("size_bytes", sa.Integer, default=0),
        sa.Column("storage_key", sa.String(500)),
        sa.Column("is_downloaded", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create indexes
    op.create_index("idx_email_connections_tenant", "email_connections", ["tenant_id"])
    op.create_index("idx_email_connections_status", "email_connections", ["status"])
    op.create_index("idx_email_connections_expires", "email_connections", ["token_expires_at"])
    op.create_index("idx_email_sync_jobs_connection", "email_sync_jobs", ["connection_id"])
    op.create_index("idx_raw_emails_connection", "raw_emails", ["connection_id"])
    op.create_index("idx_raw_emails_received", "raw_emails", ["received_at"])
    op.create_index("idx_raw_emails_from", "raw_emails", ["from_address"])
    op.create_index("idx_email_attachments_email", "email_attachments", ["email_id"])


def downgrade() -> None:
    op.drop_table("email_attachments")
    op.drop_table("raw_emails")
    op.drop_table("email_sync_jobs")
    op.drop_table("email_connections")
```

---

*End of Data Model Document*
