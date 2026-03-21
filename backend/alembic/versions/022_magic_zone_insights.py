"""Add Magic Zone insight fields.

Revision ID: 022_magic_zone_insights
Revises: 021_triggers
Create Date: 2025-12-31

These fields support the Magic Zone Analyzer feature which routes
high-value insights through the Multi-Agent Orchestrator for
cross-pillar analysis with OPTIONS format.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "022_magic_zone_insights"
down_revision: str | None = "021_triggers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add Magic Zone fields to insights table."""
    # Add generation_type column - tracks how the insight was generated
    op.add_column(
        "insights",
        sa.Column(
            "generation_type",
            sa.String(50),
            nullable=False,
            server_default="rule_based",
            comment="How insight was generated: rule_based, ai_single, or magic_zone",
        ),
    )

    # Add agents_used column - tracks which agents contributed (for magic_zone)
    op.add_column(
        "insights",
        sa.Column(
            "agents_used",
            JSONB(),
            nullable=True,
            comment="List of agent names that contributed to this insight",
        ),
    )

    # Add options_count column - number of options presented (for magic_zone)
    op.add_column(
        "insights",
        sa.Column(
            "options_count",
            sa.Integer(),
            nullable=True,
            comment="Number of OPTIONS presented in the insight detail",
        ),
    )

    # Create index for filtering by generation_type
    op.create_index(
        "idx_insights_generation_type",
        "insights",
        ["generation_type"],
    )


def downgrade() -> None:
    """Remove Magic Zone fields from insights table."""
    op.drop_index("idx_insights_generation_type", table_name="insights")
    op.drop_column("insights", "options_count")
    op.drop_column("insights", "agents_used")
    op.drop_column("insights", "generation_type")
