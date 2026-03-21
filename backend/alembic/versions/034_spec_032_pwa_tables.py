"""Add PWA tables for push subscriptions and WebAuthn

Revision ID: 034_pwa_tables
Revises: 033_spec_030_client_portal
Create Date: 2026-01-03

Spec: 032-pwa-mobile-document-capture
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "034_pwa_tables"
down_revision = "033_spec_030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Push subscriptions table
    op.create_table(
        "push_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.Text, nullable=False),
        sa.Column("p256dh_key", sa.String(255), nullable=False),
        sa.Column("auth_key", sa.String(255), nullable=False),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("device_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_unique_constraint(
        "uq_push_subscriptions_endpoint", "push_subscriptions", ["endpoint"]
    )
    op.create_index("ix_push_subscriptions_client_id", "push_subscriptions", ["client_id"])
    op.create_index("ix_push_subscriptions_tenant_id", "push_subscriptions", ["tenant_id"])
    op.create_index(
        "ix_push_subscriptions_tenant_client",
        "push_subscriptions",
        ["tenant_id", "client_id"],
    )

    # WebAuthn credentials table
    op.create_table(
        "webauthn_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("credential_id", sa.LargeBinary, nullable=False, unique=True),
        sa.Column("public_key", sa.LargeBinary, nullable=False),
        sa.Column("sign_count", sa.Integer, default=0, nullable=False),
        sa.Column("device_name", sa.String(255), nullable=True),
        sa.Column("aaguid", sa.LargeBinary, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_webauthn_credentials_client_id", "webauthn_credentials", ["client_id"])
    op.create_index("ix_webauthn_credentials_tenant_id", "webauthn_credentials", ["tenant_id"])
    op.create_index(
        "ix_webauthn_credentials_credential_id",
        "webauthn_credentials",
        ["credential_id"],
    )
    op.create_index(
        "ix_webauthn_credentials_tenant_client",
        "webauthn_credentials",
        ["tenant_id", "client_id"],
    )

    # Push notification logs table
    op.create_table(
        "push_notification_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "subscription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("push_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("data", postgresql.JSONB, default={}),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fcm_message_id", sa.String(255), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )

    op.create_index(
        "ix_push_notification_logs_subscription_id",
        "push_notification_logs",
        ["subscription_id"],
    )
    op.create_index("ix_push_notification_logs_sent_at", "push_notification_logs", ["sent_at"])
    op.create_index(
        "ix_push_notification_logs_type_sent",
        "push_notification_logs",
        ["notification_type", "sent_at"],
    )

    # PWA installation events table
    op.create_table(
        "pwa_installation_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("platform", sa.String(50), nullable=True),
        sa.Column("metadata", postgresql.JSONB, default={}),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("ix_pwa_events_client_id", "pwa_installation_events", ["client_id"])
    op.create_index("ix_pwa_events_tenant_id", "pwa_installation_events", ["tenant_id"])
    op.create_index(
        "ix_pwa_events_tenant_type",
        "pwa_installation_events",
        ["tenant_id", "event_type"],
    )
    op.create_index("ix_pwa_events_created_at", "pwa_installation_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("pwa_installation_events")
    op.drop_table("push_notification_logs")
    op.drop_table("webauthn_credentials")
    op.drop_table("push_subscriptions")
