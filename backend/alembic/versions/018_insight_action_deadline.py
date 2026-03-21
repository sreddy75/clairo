"""Add action_deadline to insights.

Revision ID: 018_insight_action_deadline
Revises: 017_insights_table
Create Date: 2024-12-31
"""

import sqlalchemy as sa
from alembic import op

revision = "018_insight_action_deadline"
down_revision = "017_insights"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add action_deadline column to insights table."""
    op.add_column(
        "insights",
        sa.Column(
            "action_deadline",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Date by which action should be taken (e.g., BAS due date, super deadline)",
        ),
    )

    # Add index for queries filtering by deadline
    op.create_index(
        "idx_insights_action_deadline",
        "insights",
        ["action_deadline"],
        postgresql_where=sa.text("action_deadline IS NOT NULL"),
    )


def downgrade() -> None:
    """Remove action_deadline column."""
    op.drop_index("idx_insights_action_deadline", table_name="insights")
    op.drop_column("insights", "action_deadline")
