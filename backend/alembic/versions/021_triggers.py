"""Create triggers and trigger_executions tables.

Revision ID: 021_triggers
Revises: 020_action_items_notes
Create Date: 2025-12-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

# revision identifiers, used by Alembic.
revision: str = "021_triggers"
down_revision: str | None = "020_action_items_notes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create triggers and trigger_executions tables."""
    # Create triggers table
    op.create_table(
        "triggers",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        # Identification
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("trigger_type", sa.String(50), nullable=False),
        # Configuration
        sa.Column("config", JSONB(), nullable=False, server_default="{}"),
        sa.Column("target_analyzers", ARRAY(sa.String(100)), nullable=False, server_default="{}"),
        # Deduplication
        sa.Column("dedup_window_hours", sa.Integer(), nullable=False, server_default="168"),
        # Status
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        # System default flag
        sa.Column("is_system_default", sa.Boolean(), nullable=False, server_default="false"),
        # Audit
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        # Check constraints
        sa.CheckConstraint(
            "trigger_type IN ('data_threshold', 'time_scheduled', 'event_based')",
            name="triggers_type_check",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'disabled', 'error')",
            name="triggers_status_check",
        ),
    )

    # Create indexes for triggers
    op.create_index("idx_triggers_tenant", "triggers", ["tenant_id"])
    op.create_index("idx_triggers_type", "triggers", ["tenant_id", "trigger_type"])
    op.create_index("idx_triggers_status", "triggers", ["tenant_id", "status"])

    # Create trigger_executions table
    op.create_table(
        "trigger_executions",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("trigger_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        # Execution timing
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        # Status
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        # Results
        sa.Column("clients_evaluated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("insights_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("insights_deduplicated", sa.Integer(), nullable=False, server_default="0"),
        # Client IDs processed
        sa.Column("client_ids", ARRAY(sa.String(36)), nullable=False, server_default="{}"),
        # Error tracking
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_details", JSONB(), nullable=True),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(["trigger_id"], ["triggers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        # Check constraints
        sa.CheckConstraint(
            "status IN ('running', 'success', 'failed', 'partial')",
            name="trigger_executions_status_check",
        ),
    )

    # Create indexes for trigger_executions
    op.create_index("idx_trigger_executions_trigger", "trigger_executions", ["trigger_id"])
    op.create_index("idx_trigger_executions_tenant", "trigger_executions", ["tenant_id"])
    op.create_index(
        "idx_trigger_executions_started", "trigger_executions", ["trigger_id", "started_at"]
    )


def downgrade() -> None:
    """Drop triggers and trigger_executions tables."""
    # Drop trigger_executions first (has FK to triggers)
    op.drop_index("idx_trigger_executions_started", table_name="trigger_executions")
    op.drop_index("idx_trigger_executions_tenant", table_name="trigger_executions")
    op.drop_index("idx_trigger_executions_trigger", table_name="trigger_executions")
    op.drop_table("trigger_executions")

    # Drop triggers
    op.drop_index("idx_triggers_status", table_name="triggers")
    op.drop_index("idx_triggers_type", table_name="triggers")
    op.drop_index("idx_triggers_tenant", table_name="triggers")
    op.drop_table("triggers")
