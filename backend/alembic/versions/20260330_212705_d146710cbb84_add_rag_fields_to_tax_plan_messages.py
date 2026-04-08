"""add RAG fields to tax_plan_messages

Revision ID: d146710cbb84
Revises: a161d4be08ea
Create Date: 2026-03-30 21:27:05.642626+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision: str = "d146710cbb84"
down_revision: str | None = "a161d4be08ea"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add source_chunks_used and citation_verification to tax_plan_messages."""
    op.add_column(
        "tax_plan_messages",
        sa.Column("source_chunks_used", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "tax_plan_messages",
        sa.Column("citation_verification", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    """Remove RAG fields from tax_plan_messages."""
    op.drop_column("tax_plan_messages", "citation_verification")
    op.drop_column("tax_plan_messages", "source_chunks_used")
