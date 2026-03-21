"""Add notifications table for in-app notifications.

Revision ID: 035_notifications
Revises: 034_pwa_tables
Create Date: 2026-01-04

Spec 011: Interim Lodgement - In-app deadline notifications
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "035_notifications"
down_revision = "034_pwa_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create notifications table."""
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            comment="Foreign key to tenant",
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_users.id", ondelete="CASCADE"),
            nullable=False,
            comment="User who receives the notification",
        ),
        sa.Column(
            "notification_type",
            sa.String(50),
            nullable=False,
            comment="Type: deadline_approaching, review_requested, etc.",
        ),
        sa.Column(
            "title",
            sa.String(255),
            nullable=False,
            comment="Notification title",
        ),
        sa.Column(
            "message",
            sa.Text,
            nullable=True,
            comment="Optional detailed message",
        ),
        sa.Column(
            "entity_type",
            sa.String(50),
            nullable=True,
            comment="Related entity type: client, bas_period, etc.",
        ),
        sa.Column(
            "entity_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Related entity ID for navigation",
        ),
        sa.Column(
            "entity_context",
            postgresql.JSONB,
            nullable=True,
            comment="Additional context for UI navigation",
        ),
        sa.Column(
            "triggered_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_users.id", ondelete="SET NULL"),
            nullable=True,
            comment="User who triggered the notification (optional)",
        ),
        sa.Column(
            "is_read",
            sa.Boolean,
            nullable=False,
            default=False,
            server_default="false",
            comment="Whether notification has been read",
        ),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the notification was read",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="When notification was created",
        ),
    )

    # Create indexes
    op.create_index(
        "ix_notifications_tenant_id",
        "notifications",
        ["tenant_id"],
    )
    op.create_index(
        "ix_notifications_user_id",
        "notifications",
        ["user_id"],
    )
    op.create_index(
        "ix_notifications_user_unread",
        "notifications",
        ["user_id", "is_read"],
        postgresql_where=sa.text("is_read = false"),
    )
    op.create_index(
        "ix_notifications_created_at",
        "notifications",
        ["created_at"],
    )
    op.create_index(
        "ix_notifications_type",
        "notifications",
        ["notification_type"],
    )


def downgrade() -> None:
    """Drop notifications table."""
    op.drop_index("ix_notifications_type", table_name="notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_index("ix_notifications_tenant_id", table_name="notifications")
    op.drop_table("notifications")
