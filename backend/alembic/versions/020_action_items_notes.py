"""Add notes column to action_items.

Revision ID: 020_action_items_notes
Revises: 019_action_items
Create Date: 2025-12-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "020_action_items_notes"
down_revision: str | None = "019_action_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add notes column to action_items table."""
    op.add_column(
        "action_items",
        sa.Column("notes", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove notes column from action_items table."""
    op.drop_column("action_items", "notes")
