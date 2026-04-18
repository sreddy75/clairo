"""Tax planning calculation correctness.

Spec 059: Adds strategy_category, requires_group_model, source_tags columns to
tax_scenarios; enforces case-insensitive trimmed title uniqueness per plan.

Revision ID: 059_tax_planning_correctness
Revises: perf_indexes_20260416
Create Date: 2026-04-18
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "059_tax_planning_correctness"
down_revision: str | None = "perf_indexes_20260416"
branch_labels = None
depends_on = None


STRATEGY_CATEGORY_VALUES = (
    "prepayment",
    "capex_deduction",
    "super_contribution",
    "director_salary",
    "trust_distribution",
    "dividend_timing",
    "spouse_contribution",
    "multi_entity_restructure",
    "other",
)


def upgrade() -> None:
    # 1. Strategy category enum type
    strategy_category_enum = postgresql.ENUM(
        *STRATEGY_CATEGORY_VALUES,
        name="strategy_category_enum",
    )
    strategy_category_enum.create(op.get_bind(), checkfirst=True)

    # 2. New columns on tax_scenarios
    op.add_column(
        "tax_scenarios",
        sa.Column(
            "strategy_category",
            postgresql.ENUM(
                *STRATEGY_CATEGORY_VALUES,
                name="strategy_category_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="other",
        ),
    )
    op.add_column(
        "tax_scenarios",
        sa.Column(
            "requires_group_model",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "tax_scenarios",
        sa.Column(
            "source_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    # 3. Disambiguate any pre-existing duplicate titles before enforcing the index.
    #    Keeps the earliest row unchanged; suffixes the later duplicates with their id.
    op.execute(
        """
        UPDATE tax_scenarios
        SET title = title || ' (duplicate ' || id::text || ')'
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY tax_plan_id, LOWER(TRIM(title))
                           ORDER BY created_at, id
                       ) AS rn
                FROM tax_scenarios
            ) t
            WHERE t.rn > 1
        )
        """
    )

    # 4. Partial unique index enforcing case-insensitive trimmed title per plan.
    op.create_index(
        "ix_tax_scenarios_plan_normalized_title",
        "tax_scenarios",
        ["tax_plan_id", sa.text("LOWER(TRIM(title))")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_tax_scenarios_plan_normalized_title", "tax_scenarios")
    op.drop_column("tax_scenarios", "source_tags")
    op.drop_column("tax_scenarios", "requires_group_model")
    op.drop_column("tax_scenarios", "strategy_category")
    op.execute("DROP TYPE IF EXISTS strategy_category_enum")
