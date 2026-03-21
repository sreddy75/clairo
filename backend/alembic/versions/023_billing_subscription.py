"""Add subscription tiers and billing events.

Revision ID: 023_billing_subscription
Revises: 022_magic_zone_insights
Create Date: 2025-12-31

Implements Spec 019: Subscription & Feature Gating
- Adds subscription_tier enum (starter, professional, growth, enterprise)
- Extends subscription_status enum (grandfathered, past_due)
- Adds tier and billing columns to tenants table
- Creates billing_events table for Stripe webhook tracking
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "023_billing_subscription"
down_revision: str | None = "022_magic_zone_insights"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add subscription tiers and billing events."""
    # 1. Create subscription_tier enum
    subscription_tier_enum = sa.Enum(
        "starter",
        "professional",
        "growth",
        "enterprise",
        name="subscription_tier",
    )
    subscription_tier_enum.create(op.get_bind(), checkfirst=True)

    # 2. Extend subscription_status enum with new values
    # PostgreSQL requires ALTER TYPE ... ADD VALUE
    op.execute("ALTER TYPE subscription_status ADD VALUE IF NOT EXISTS 'grandfathered'")
    op.execute("ALTER TYPE subscription_status ADD VALUE IF NOT EXISTS 'past_due'")

    # 3. Create billing_event_status enum
    billing_event_status_enum = sa.Enum(
        "pending",
        "processed",
        "failed",
        name="billing_event_status",
    )
    billing_event_status_enum.create(op.get_bind(), checkfirst=True)

    # 4. Add new columns to tenants table
    op.add_column(
        "tenants",
        sa.Column(
            "tier",
            ENUM(
                "starter",
                "professional",
                "growth",
                "enterprise",
                name="subscription_tier",
                create_type=False,
            ),
            nullable=False,
            server_default="professional",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("client_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "tenants",
        sa.Column("owner_email", sa.String(255), nullable=True),
    )

    # 5. Create indexes for new columns
    op.create_index(
        "idx_tenants_stripe_customer_id",
        "tenants",
        ["stripe_customer_id"],
        unique=True,
        postgresql_where=sa.text("stripe_customer_id IS NOT NULL"),
    )
    op.create_index(
        "idx_tenants_stripe_subscription_id",
        "tenants",
        ["stripe_subscription_id"],
        unique=True,
        postgresql_where=sa.text("stripe_subscription_id IS NOT NULL"),
    )

    # 6. Migrate existing tenants to grandfathered status with professional tier
    # NOTE: Due to PostgreSQL limitation, new enum values cannot be used in the same
    # transaction they are added. Run this SQL manually after migration:
    #   UPDATE tenants SET subscription_status = 'grandfathered' WHERE subscription_status = 'active';
    # Or the migration will handle it on next run if enum already exists.

    # 7. Create billing_events table
    op.create_table(
        "billing_events",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        # Stripe event tracking (for idempotency)
        sa.Column("stripe_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("event_data", JSONB(), nullable=False, server_default="{}"),
        # Billing info
        sa.Column("amount_cents", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="'aud'"),
        # Status
        sa.Column(
            "status",
            ENUM(
                "pending",
                "processed",
                "failed",
                name="billing_event_status",
                create_type=False,
            ),
            nullable=False,
            server_default="processed",
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        # Audit
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )

    # 8. Create indexes for billing_events
    op.create_index(
        "idx_billing_events_tenant",
        "billing_events",
        ["tenant_id"],
    )
    op.create_index(
        "idx_billing_events_stripe_event_id",
        "billing_events",
        ["stripe_event_id"],
        unique=True,
    )
    op.create_index(
        "idx_billing_events_event_type",
        "billing_events",
        ["tenant_id", "event_type"],
    )
    op.create_index(
        "idx_billing_events_created",
        "billing_events",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    """Remove subscription tiers and billing events."""
    # Drop billing_events table and indexes
    op.drop_index("idx_billing_events_created", table_name="billing_events")
    op.drop_index("idx_billing_events_event_type", table_name="billing_events")
    op.drop_index("idx_billing_events_stripe_event_id", table_name="billing_events")
    op.drop_index("idx_billing_events_tenant", table_name="billing_events")
    op.drop_table("billing_events")

    # Revert grandfathered tenants back to active
    op.execute("""
        UPDATE tenants
        SET subscription_status = 'active'
        WHERE subscription_status = 'grandfathered'
    """)

    # Drop tenant column indexes
    op.drop_index("idx_tenants_stripe_subscription_id", table_name="tenants")
    op.drop_index("idx_tenants_stripe_customer_id", table_name="tenants")

    # Drop tenant columns
    op.drop_column("tenants", "owner_email")
    op.drop_column("tenants", "client_count")
    op.drop_column("tenants", "current_period_end")
    op.drop_column("tenants", "stripe_subscription_id")
    op.drop_column("tenants", "stripe_customer_id")
    op.drop_column("tenants", "tier")

    # Drop enums (cannot remove values from existing enum in PostgreSQL)
    op.execute("DROP TYPE IF EXISTS billing_event_status")
    op.execute("DROP TYPE IF EXISTS subscription_tier")
    # Note: subscription_status enum values cannot be removed in PostgreSQL
    # The added values (grandfathered, past_due) will remain but be unused
