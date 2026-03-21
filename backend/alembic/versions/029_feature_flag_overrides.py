"""Add feature_flag_overrides table for admin dashboard.

Revision ID: 029_feature_flag_overrides
Revises: 028_oauth_client_fields
Create Date: 2026-01-01

Spec 022: Admin Dashboard (Internal)
- Add feature_flag_overrides table for per-tenant feature flag overrides
- Allows admins to enable/disable features for specific tenants
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision: str = "029_feature_flag_overrides"
down_revision: str | None = "028_oauth_client_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create feature_flag_overrides table."""
    op.create_table(
        "feature_flag_overrides",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Tenant this override applies to",
        ),
        sa.Column(
            "feature_key",
            sa.String(50),
            nullable=False,
            comment="Feature identifier (e.g., 'client_portal', 'api_access')",
        ),
        sa.Column(
            "override_value",
            sa.Boolean(),
            nullable=True,
            comment="True=enabled, False=disabled, None=use tier default",
        ),
        sa.Column(
            "reason",
            sa.String(500),
            nullable=False,
            comment="Required reason for the override",
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Admin who created this override",
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Admin who last updated this override",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When override was created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When override was last updated",
        ),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_feature_flag_overrides_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["practice_users.id"],
            name="fk_feature_flag_overrides_created_by",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["practice_users.id"],
            name="fk_feature_flag_overrides_updated_by",
            ondelete="SET NULL",
        ),
        # Unique constraint: one override per feature per tenant
        sa.UniqueConstraint(
            "tenant_id",
            "feature_key",
            name="uq_feature_flag_override_tenant_feature",
        ),
        # Check constraint: feature_key must be valid
        sa.CheckConstraint(
            "feature_key IN ('ai_insights', 'client_portal', 'custom_triggers', "
            "'api_access', 'knowledge_base', 'magic_zone')",
            name="ck_feature_flag_override_valid_key",
        ),
    )

    # Create indexes
    op.create_index(
        "ix_feature_flag_overrides_tenant_id",
        "feature_flag_overrides",
        ["tenant_id"],
    )
    op.create_index(
        "ix_feature_flag_overrides_feature_key",
        "feature_flag_overrides",
        ["feature_key"],
    )
    op.create_index(
        "ix_feature_flag_overrides_tenant_feature",
        "feature_flag_overrides",
        ["tenant_id", "feature_key"],
    )


def downgrade() -> None:
    """Drop feature_flag_overrides table."""
    op.drop_index(
        "ix_feature_flag_overrides_tenant_feature",
        table_name="feature_flag_overrides",
    )
    op.drop_index(
        "ix_feature_flag_overrides_feature_key",
        table_name="feature_flag_overrides",
    )
    op.drop_index(
        "ix_feature_flag_overrides_tenant_id",
        table_name="feature_flag_overrides",
    )
    op.drop_table("feature_flag_overrides")
