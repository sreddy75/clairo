"""Create action_items table.

Revision ID: 019_action_items
Revises: 018_insight_action_deadline
Create Date: 2025-12-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "019_action_items"
down_revision: str | None = "018_insight_action_deadline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create action_items table."""
    op.create_table(
        "action_items",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        # Content
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Source
        sa.Column("source_insight_id", sa.UUID(), nullable=True),
        # Client context
        sa.Column("client_id", sa.UUID(), nullable=True),
        sa.Column("client_name", sa.String(255), nullable=True),
        # Assignment
        sa.Column("assigned_to_user_id", sa.String(255), nullable=True),
        sa.Column("assigned_to_name", sa.String(255), nullable=True),
        sa.Column("assigned_by_user_id", sa.String(255), nullable=False),
        # Scheduling
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        # Status tracking
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        # Completion
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_insight_id"], ["insights.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["client_id"], ["xero_connections.id"], ondelete="SET NULL"),
        # Check constraints
        sa.CheckConstraint(
            "priority IN ('urgent', 'high', 'medium', 'low')",
            name="action_items_priority_check",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'cancelled')",
            name="action_items_status_check",
        ),
    )

    # Create indexes
    op.create_index("idx_action_items_tenant", "action_items", ["tenant_id"])
    op.create_index("idx_action_items_status", "action_items", ["tenant_id", "status"])
    op.create_index(
        "idx_action_items_assigned", "action_items", ["tenant_id", "assigned_to_user_id"]
    )
    op.create_index("idx_action_items_due_date", "action_items", ["tenant_id", "due_date"])
    op.create_index("idx_action_items_client", "action_items", ["tenant_id", "client_id"])
    op.create_index("idx_action_items_insight", "action_items", ["source_insight_id"])


def downgrade() -> None:
    """Drop action_items table."""
    op.drop_index("idx_action_items_insight", table_name="action_items")
    op.drop_index("idx_action_items_client", table_name="action_items")
    op.drop_index("idx_action_items_due_date", table_name="action_items")
    op.drop_index("idx_action_items_assigned", table_name="action_items")
    op.drop_index("idx_action_items_status", table_name="action_items")
    op.drop_index("idx_action_items_tenant", table_name="action_items")
    op.drop_table("action_items")
