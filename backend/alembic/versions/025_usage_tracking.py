"""Usage tracking tables and tenant extensions.

Revision ID: 025_usage_tracking
Revises: 024_auth_clerk_id_lookup
Create Date: 2025-12-31

Spec 020: Usage Tracking & Limits
- Adds usage tracking columns to tenants table
- Creates usage_snapshots table for historical tracking
- Creates usage_alerts table for alert deduplication
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "025_usage_tracking"
down_revision: str | None = "024_auth_clerk_id_lookup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add usage tracking infrastructure."""
    # 1. Create usage_alert_type enum
    usage_alert_type = postgresql.ENUM(
        "threshold_80",
        "threshold_90",
        "limit_reached",
        name="usage_alert_type",
        create_type=True,
    )
    usage_alert_type.create(op.get_bind(), checkfirst=True)

    # 2. Add usage tracking columns to tenants table
    op.add_column(
        "tenants",
        sa.Column(
            "ai_queries_month",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="AI chat completions this billing period",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "documents_month",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Documents processed this billing period",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "usage_month_reset",
            sa.Date(),
            nullable=True,
            comment="Date when monthly counters were last reset",
        ),
    )

    # 3. Create usage_snapshots table
    op.create_table(
        "usage_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("client_count", sa.Integer(), nullable=False),
        sa.Column("ai_queries_count", sa.Integer(), nullable=False),
        sa.Column("documents_count", sa.Integer(), nullable=False),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("client_limit", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("client_count >= 0", name="ck_usage_snapshots_client_count"),
        sa.CheckConstraint("ai_queries_count >= 0", name="ck_usage_snapshots_ai_queries"),
        sa.CheckConstraint("documents_count >= 0", name="ck_usage_snapshots_documents"),
    )

    # Create indexes for usage_snapshots
    op.create_index(
        "ix_usage_snapshots_tenant_id",
        "usage_snapshots",
        ["tenant_id"],
    )
    op.create_index(
        "ix_usage_snapshots_captured_at",
        "usage_snapshots",
        ["captured_at"],
    )
    op.create_index(
        "ix_usage_snapshots_tenant_period",
        "usage_snapshots",
        ["tenant_id", "captured_at"],
    )

    # 4. Create usage_alerts table
    op.create_table(
        "usage_alerts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "alert_type",
            postgresql.ENUM(
                "threshold_80",
                "threshold_90",
                "limit_reached",
                name="usage_alert_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "billing_period",
            sa.String(7),
            nullable=False,
            comment="Format: YYYY-MM",
        ),
        sa.Column("threshold_percentage", sa.Integer(), nullable=False),
        sa.Column("client_count_at_alert", sa.Integer(), nullable=False),
        sa.Column("client_limit_at_alert", sa.Integer(), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "alert_type",
            "billing_period",
            name="uq_usage_alert_dedup",
        ),
        sa.CheckConstraint(
            "threshold_percentage IN (80, 90, 100)",
            name="ck_usage_alerts_threshold",
        ),
    )

    # Create indexes for usage_alerts
    op.create_index(
        "ix_usage_alerts_tenant_id",
        "usage_alerts",
        ["tenant_id"],
    )
    op.create_index(
        "ix_usage_alerts_dedup",
        "usage_alerts",
        ["tenant_id", "alert_type", "billing_period"],
    )


def downgrade() -> None:
    """Remove usage tracking infrastructure."""
    # Drop usage_alerts table and indexes
    op.drop_index("ix_usage_alerts_dedup", table_name="usage_alerts")
    op.drop_index("ix_usage_alerts_tenant_id", table_name="usage_alerts")
    op.drop_table("usage_alerts")

    # Drop usage_snapshots table and indexes
    op.drop_index("ix_usage_snapshots_tenant_period", table_name="usage_snapshots")
    op.drop_index("ix_usage_snapshots_captured_at", table_name="usage_snapshots")
    op.drop_index("ix_usage_snapshots_tenant_id", table_name="usage_snapshots")
    op.drop_table("usage_snapshots")

    # Remove usage tracking columns from tenants
    op.drop_column("tenants", "usage_month_reset")
    op.drop_column("tenants", "documents_month")
    op.drop_column("tenants", "ai_queries_month")

    # Drop usage_alert_type enum
    usage_alert_type = postgresql.ENUM(
        "threshold_80",
        "threshold_90",
        "limit_reached",
        name="usage_alert_type",
    )
    usage_alert_type.drop(op.get_bind(), checkfirst=True)
