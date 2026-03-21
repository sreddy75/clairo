"""Xero OAuth connection tables with RLS.

Revision ID: 002_xero_oauth
Revises: 001_auth_multitenancy
Create Date: 2025-12-28

This migration creates tables for Xero OAuth integration:
- xero_connections: Stores Xero organization connections per tenant
- xero_oauth_states: Temporary OAuth state storage during authorization

RLS (Row-Level Security):
- Enabled on xero_connections table
- Uses PostgreSQL session variable app.current_tenant_id
- xero_oauth_states is NOT RLS-protected (lookup by state token)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002_xero_oauth"
down_revision: str | None = "001_auth_multitenancy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create Xero OAuth tables with RLS policies."""

    # =========================================================================
    # Create PostgreSQL Enum
    # =========================================================================

    xero_connection_status_enum = postgresql.ENUM(
        "active",
        "needs_reauth",
        "disconnected",
        name="xero_connection_status",
        create_type=True,
    )
    xero_connection_status_enum.create(op.get_bind(), checkfirst=True)

    # =========================================================================
    # Create xero_connections table
    # =========================================================================

    op.create_table(
        "xero_connections",
        # Primary key
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Tenant association (RLS enforced)
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # Xero organization identity
        sa.Column("xero_tenant_id", sa.String(50), nullable=False, index=True),
        sa.Column("organization_name", sa.String(255), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active",
                "needs_reauth",
                "disconnected",
                name="xero_connection_status",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
            index=True,
        ),
        # OAuth tokens (encrypted at application level)
        sa.Column("access_token", sa.Text, nullable=False),
        sa.Column("refresh_token", sa.Text, nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("scopes", postgresql.ARRAY(sa.Text), nullable=False),
        # Rate limiting
        sa.Column(
            "rate_limit_daily_remaining",
            sa.Integer,
            nullable=False,
            server_default="5000",
        ),
        sa.Column(
            "rate_limit_minute_remaining",
            sa.Integer,
            nullable=False,
            server_default="60",
        ),
        sa.Column("rate_limit_reset_at", sa.DateTime(timezone=True), nullable=True),
        # Connection audit
        sa.Column(
            "connected_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "connected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # Constraints
        sa.UniqueConstraint("tenant_id", "xero_tenant_id", name="uq_xero_connection_tenant_org"),
    )

    # Create indexes for common queries
    op.create_index(
        "idx_xero_connections_active",
        "xero_connections",
        ["status"],
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "idx_xero_connections_token_expires",
        "xero_connections",
        ["token_expires_at"],
        postgresql_where=sa.text("status = 'active'"),
    )

    # =========================================================================
    # Create xero_oauth_states table (temporary, not RLS protected)
    # =========================================================================

    op.create_table(
        "xero_oauth_states",
        # Primary key
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Context (for validation after state lookup)
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # OAuth state
        sa.Column("state", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("code_verifier", sa.String(128), nullable=False),
        sa.Column("redirect_uri", sa.Text, nullable=False),
        # Lifecycle
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )

    # =========================================================================
    # Enable RLS on xero_connections
    # =========================================================================

    op.execute("ALTER TABLE xero_connections ENABLE ROW LEVEL SECURITY")

    # Policy for tenant isolation
    op.execute(
        """
        CREATE POLICY tenant_isolation_xero_connections ON xero_connections
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        """
    )

    # =========================================================================
    # Create updated_at trigger for xero_connections
    # =========================================================================

    # Create trigger function if it doesn't exist (may already exist from auth migration)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        """
    )

    op.execute(
        """
        CREATE TRIGGER xero_connections_updated_at
        BEFORE UPDATE ON xero_connections
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
        """
    )


def downgrade() -> None:
    """Drop Xero OAuth tables."""

    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS xero_connections_updated_at ON xero_connections")

    # Drop RLS policy
    op.execute("DROP POLICY IF EXISTS tenant_isolation_xero_connections ON xero_connections")

    # Drop tables
    op.drop_table("xero_oauth_states")
    op.drop_table("xero_connections")

    # Drop enum
    op.execute("DROP TYPE IF EXISTS xero_connection_status")
