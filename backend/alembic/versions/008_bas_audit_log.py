"""Add BAS audit log table for compliance tracking.

Revision ID: 008_bas_audit_log
Revises: 007_fix_bas_user_fks
Create Date: 2025-12-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008_bas_audit_log"
down_revision: str | None = "007_fix_bas_user_fks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create bas_audit_log table
    op.create_table(
        "bas_audit_log",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        # Event details
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("event_description", sa.Text(), nullable=False),
        # Status tracking
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=True),
        # User tracking
        sa.Column("performed_by", sa.UUID(), nullable=True),  # NULL for system actions
        sa.Column("performed_by_name", sa.String(length=255), nullable=True),
        sa.Column("is_system_action", sa.Boolean(), nullable=False, server_default="false"),
        # Additional context
        sa.Column("event_metadata", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["bas_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["performed_by"],
            ["practice_users.id"],
            name="fk_bas_audit_log_performed_by_practice_users",
            ondelete="SET NULL",
        ),
    )

    # Create indexes for efficient querying
    op.create_index("idx_bas_audit_log_tenant", "bas_audit_log", ["tenant_id"])
    op.create_index("idx_bas_audit_log_session", "bas_audit_log", ["session_id"])
    op.create_index("idx_bas_audit_log_event_type", "bas_audit_log", ["event_type"])
    op.create_index("idx_bas_audit_log_created_at", "bas_audit_log", ["created_at"])

    # Enable RLS
    op.execute("ALTER TABLE bas_audit_log ENABLE ROW LEVEL SECURITY")

    # Create RLS policy
    op.execute("""
        CREATE POLICY bas_audit_log_tenant_isolation ON bas_audit_log
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)

    # Add auto_created flag to bas_sessions
    op.add_column(
        "bas_sessions",
        sa.Column("auto_created", sa.Boolean(), nullable=False, server_default="false"),
    )

    # Add reviewed_by and reviewed_at to track accountant review
    op.add_column(
        "bas_sessions",
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
    )
    op.add_column(
        "bas_sessions",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Add FK for reviewed_by
    op.create_foreign_key(
        "fk_bas_sessions_reviewed_by_practice_users",
        "bas_sessions",
        "practice_users",
        ["reviewed_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Drop FK and columns from bas_sessions
    op.drop_constraint(
        "fk_bas_sessions_reviewed_by_practice_users", "bas_sessions", type_="foreignkey"
    )
    op.drop_column("bas_sessions", "reviewed_at")
    op.drop_column("bas_sessions", "reviewed_by")
    op.drop_column("bas_sessions", "auto_created")

    # Drop RLS policy
    op.execute("DROP POLICY IF EXISTS bas_audit_log_tenant_isolation ON bas_audit_log")

    # Drop indexes
    op.drop_index("idx_bas_audit_log_created_at", table_name="bas_audit_log")
    op.drop_index("idx_bas_audit_log_event_type", table_name="bas_audit_log")
    op.drop_index("idx_bas_audit_log_session", table_name="bas_audit_log")
    op.drop_index("idx_bas_audit_log_tenant", table_name="bas_audit_log")

    # Drop table
    op.drop_table("bas_audit_log")
