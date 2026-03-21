"""Add agent queries and escalations tables for Spec 014.

Revision ID: 016_agent_audit_tables
Revises: 015_aggregation_connection_id
Create Date: 2025-12-30

Adds audit tables for the multi-perspective agent system:
- agent_queries: Audit log for all agent queries (without query content for privacy)
- agent_escalations: Tracks queries that require human review
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "016_agent_audit_tables"
down_revision = "015_aggregation_connection_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # agent_queries - Audit log for agent queries
    # =========================================================================
    op.create_table(
        "agent_queries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "correlation_id",
            postgresql.UUID(as_uuid=True),
            unique=True,
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
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Client context (optional)
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Query analysis (NOT the actual query content)
        sa.Column("query_hash", sa.String(64), nullable=False),
        sa.Column("perspectives_used", postgresql.ARRAY(sa.String(50)), nullable=False),
        # Results
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("escalation_required", sa.Boolean, default=False, nullable=False),
        sa.Column("escalation_reason", sa.String(255), nullable=True),
        # Performance metrics
        sa.Column("processing_time_ms", sa.Integer, nullable=True),
        sa.Column("token_usage", sa.Integer, nullable=True),
        # Additional query metadata (named to avoid conflict with SQLAlchemy Base.metadata)
        sa.Column("extra_data", postgresql.JSONB, nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # Additional indexes for agent_queries
    op.create_index(
        "ix_agent_queries_tenant_created",
        "agent_queries",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_agent_queries_user_created",
        "agent_queries",
        ["user_id", "created_at"],
    )

    # =========================================================================
    # agent_escalations - Queries requiring human review
    # =========================================================================
    op.create_table(
        "agent_escalations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "query_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_queries.id", ondelete="CASCADE"),
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
        # Escalation details
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("status", sa.String(20), default="pending", nullable=False),
        # Store query for review (unlike audit table)
        sa.Column("query_text", sa.Text, nullable=False),
        sa.Column("perspectives_used", postgresql.ARRAY(sa.String(50)), nullable=False),
        sa.Column("partial_response", sa.Text, nullable=True),
        # Resolution
        sa.Column(
            "resolved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        # Feedback
        sa.Column("accountant_response", sa.Text, nullable=True),
        sa.Column("feedback_useful", sa.Boolean, nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # Additional indexes for agent_escalations
    op.create_index(
        "ix_agent_escalations_tenant_status",
        "agent_escalations",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_agent_escalations_pending",
        "agent_escalations",
        ["status", "created_at"],
    )

    # =========================================================================
    # RLS Policies
    # =========================================================================

    # Enable RLS on agent_queries
    op.execute("ALTER TABLE agent_queries ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY agent_queries_tenant_isolation ON agent_queries
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)

    # Enable RLS on agent_escalations
    op.execute("ALTER TABLE agent_escalations ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY agent_escalations_tenant_isolation ON agent_escalations
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)


def downgrade() -> None:
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS agent_escalations_tenant_isolation ON agent_escalations")
    op.execute("DROP POLICY IF EXISTS agent_queries_tenant_isolation ON agent_queries")

    # Drop tables
    op.drop_table("agent_escalations")
    op.drop_table("agent_queries")
