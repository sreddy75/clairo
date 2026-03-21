"""Spec 030 - Client Portal Foundation + Document Requests

Create tables for:
- portal_invitations: Magic link invitations to clients
- portal_sessions: Authenticated portal sessions
- document_request_templates: Reusable request templates
- document_requests: Document request workflow (ClientChase)
- request_responses: Client responses to requests
- portal_documents: Documents uploaded through portal
- request_events: Event log for request lifecycle
- bulk_requests: Bulk document request batches

Revision ID: 033_spec_030
Revises: 032_spec_025
Create Date: 2026-01-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "033_spec_030"
down_revision: str | None = "032_spec_025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create portal_invitations table
    op.create_table(
        "portal_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="PENDING"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("email_delivered", sa.Boolean, nullable=False, default=False),
        sa.Column("email_bounced", sa.Boolean, nullable=False, default=False),
        sa.Column("bounce_reason", sa.String(255), nullable=True),
        sa.Column(
            "invited_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_portal_invitations_connection_status", "portal_invitations", ["connection_id", "status"]
    )

    # Create portal_sessions table
    op.create_table(
        "portal_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("refresh_token_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("device_fingerprint", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "last_active_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean, nullable=False, default=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_portal_sessions_active", "portal_sessions", ["connection_id", "revoked", "expires_at"]
    )

    # Create document_request_templates table
    op.create_table(
        "document_request_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,  # NULL for system templates
            index=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description_template", sa.Text, nullable=False),
        sa.Column("expected_document_types", postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("default_priority", sa.String(20), nullable=False, default="NORMAL"),
        sa.Column("default_due_days", sa.Integer, nullable=False, default=7),
        sa.Column("is_system", sa.Boolean, nullable=False, default=False),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_templates_tenant_active", "document_request_templates", ["tenant_id", "is_active"]
    )

    # Create bulk_requests table (needed before document_requests due to FK)
    op.create_table(
        "bulk_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_request_templates.id"),
            nullable=True,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("total_clients", sa.Integer, nullable=False),
        sa.Column("sent_count", sa.Integer, nullable=False, default=0),
        sa.Column("failed_count", sa.Integer, nullable=False, default=0),
        sa.Column("status", sa.String(20), nullable=False, default="PENDING"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # Create document_requests table
    op.create_table(
        "document_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_request_templates.id"),
            nullable=True,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, default="NORMAL"),
        sa.Column("period_start", sa.Date, nullable=True),
        sa.Column("period_end", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, default="PENDING", index=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_remind", sa.Boolean, nullable=False, default=True),
        sa.Column("reminder_count", sa.Integer, nullable=False, default=0),
        sa.Column("last_reminder_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "bulk_request_id",
            postgresql.UUID(as_uuid=True),
            index=True,
            nullable=True,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "completed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_requests_tenant_status", "document_requests", ["tenant_id", "status"])
    op.create_index(
        "ix_requests_connection_status", "document_requests", ["connection_id", "status"]
    )
    op.create_index("ix_requests_due_date", "document_requests", ["status", "due_date"])
    op.create_index("ix_requests_bulk", "document_requests", ["bulk_request_id"])

    # Create request_responses table
    op.create_table(
        "request_responses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_requests.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column(
            "submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # Create portal_documents table
    op.create_table(
        "portal_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "response_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("request_responses.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("s3_bucket", sa.String(100), nullable=False),
        sa.Column("s3_key", sa.String(500), unique=True, nullable=False),
        sa.Column("document_type", sa.String(50), nullable=True, index=True),
        sa.Column("period_start", sa.Date, nullable=True),
        sa.Column("period_end", sa.Date, nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column(
            "uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("uploaded_by_client", sa.Boolean, nullable=False, default=True),
        sa.Column("scan_status", sa.String(20), nullable=True),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_portal_docs_connection_type", "portal_documents", ["connection_id", "document_type"]
    )
    op.create_index(
        "ix_portal_docs_period", "portal_documents", ["connection_id", "period_start", "period_end"]
    )

    # Create request_events table
    op.create_table(
        "request_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_requests.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_data", postgresql.JSONB, nullable=True),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            index=True,
            nullable=False,
        ),
    )
    op.create_index("ix_request_events_type", "request_events", ["request_id", "event_type"])


def downgrade() -> None:
    # Drop tables in reverse order of creation
    op.drop_index("ix_request_events_type", table_name="request_events")
    op.drop_table("request_events")

    op.drop_index("ix_portal_docs_period", table_name="portal_documents")
    op.drop_index("ix_portal_docs_connection_type", table_name="portal_documents")
    op.drop_table("portal_documents")

    op.drop_table("request_responses")

    op.drop_index("ix_requests_bulk", table_name="document_requests")
    op.drop_index("ix_requests_due_date", table_name="document_requests")
    op.drop_index("ix_requests_connection_status", table_name="document_requests")
    op.drop_index("ix_requests_tenant_status", table_name="document_requests")
    op.drop_table("document_requests")

    op.drop_table("bulk_requests")

    op.drop_index("ix_templates_tenant_active", table_name="document_request_templates")
    op.drop_table("document_request_templates")

    op.drop_index("ix_portal_sessions_active", table_name="portal_sessions")
    op.drop_table("portal_sessions")

    op.drop_index("ix_portal_invitations_connection_status", table_name="portal_invitations")
    op.drop_table("portal_invitations")
