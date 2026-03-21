"""Add insights table for proactive intelligence.

Revision ID: 017_insights
Revises: 016_agent_audit_tables
Create Date: 2025-12-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "017_insights"
down_revision: str | None = "016_agent_audit_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create insights table
    op.create_table(
        "insights",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=True),
        # Classification
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("insight_type", sa.String(100), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        # Content
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        # Actions
        sa.Column(
            "suggested_actions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("related_url", sa.String(500), nullable=True),
        # Lifecycle
        sa.Column("status", sa.String(50), nullable=False, server_default="new"),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actioned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        # Audit
        sa.Column("generation_source", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column(
            "data_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
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
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_insights_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["xero_connections.id"],
            name="fk_insights_client",
            ondelete="CASCADE",
        ),
    )

    # Create indexes
    op.create_index(
        "idx_insights_tenant_status",
        "insights",
        ["tenant_id", "status"],
    )
    op.create_index(
        "idx_insights_tenant_priority",
        "insights",
        ["tenant_id", "priority"],
    )
    op.create_index(
        "idx_insights_client",
        "insights",
        ["client_id"],
        postgresql_where=sa.text("client_id IS NOT NULL"),
    )
    op.create_index(
        "idx_insights_generated",
        "insights",
        ["generated_at"],
    )
    op.create_index(
        "idx_insights_type_client",
        "insights",
        ["insight_type", "client_id"],
    )

    # Enable RLS
    op.execute("ALTER TABLE insights ENABLE ROW LEVEL SECURITY")

    # Create RLS policy for tenant isolation
    op.execute(
        """
        CREATE POLICY insights_tenant_isolation ON insights
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )

    # Grant permissions (only if clairo role exists - for local dev)
    # Railway manages permissions automatically, so this is skipped in production
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'clairo') THEN
                GRANT ALL ON insights TO clairo;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # Drop RLS policy
    op.execute("DROP POLICY IF EXISTS insights_tenant_isolation ON insights")

    # Disable RLS
    op.execute("ALTER TABLE insights DISABLE ROW LEVEL SECURITY")

    # Drop indexes
    op.drop_index("idx_insights_type_client", table_name="insights")
    op.drop_index("idx_insights_generated", table_name="insights")
    op.drop_index("idx_insights_client", table_name="insights")
    op.drop_index("idx_insights_tenant_priority", table_name="insights")
    op.drop_index("idx_insights_tenant_status", table_name="insights")

    # Drop table
    op.drop_table("insights")
