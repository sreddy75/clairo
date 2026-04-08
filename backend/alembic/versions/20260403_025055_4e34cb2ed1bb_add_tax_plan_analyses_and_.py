"""Add tax_plan_analyses and implementation_items tables

Revision ID: 4e34cb2ed1bb
Revises: cc6091fd7b14
Create Date: 2026-04-03 02:50:55.838024+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# Revision identifiers
revision: str = "4e34cb2ed1bb"
down_revision: str | None = "cc6091fd7b14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database to this revision."""
    # tax_plan_analyses table
    op.create_table(
        "tax_plan_analyses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tax_plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tax_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("status", sa.String(20), nullable=False, server_default="generating"),
        # Agent outputs
        sa.Column("client_profile", postgresql.JSONB(), nullable=True),
        sa.Column("strategies_evaluated", postgresql.JSONB(), nullable=True),
        sa.Column("recommended_scenarios", postgresql.JSONB(), nullable=True),
        sa.Column("combined_strategy", postgresql.JSONB(), nullable=True),
        # Documents
        sa.Column("accountant_brief", sa.Text(), nullable=True),
        sa.Column("client_summary", sa.Text(), nullable=True),
        # Quality review
        sa.Column("review_result", postgresql.JSONB(), nullable=True),
        sa.Column("review_passed", sa.Boolean(), nullable=True),
        # Phase 2 extension fields
        sa.Column("entities", postgresql.JSONB(), nullable=True),
        sa.Column("group_structure", postgresql.JSONB(), nullable=True),
        sa.Column("distribution_plan", postgresql.JSONB(), nullable=True),
        sa.Column("entity_summaries", postgresql.JSONB(), nullable=True),
        # Metadata
        sa.Column("generation_time_ms", sa.Integer(), nullable=True),
        sa.Column("token_usage", postgresql.JSONB(), nullable=True),
        sa.Column("generated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("shared_at", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tax_plan_id", "version", name="uq_tax_plan_analysis_plan_version"),
    )
    op.create_index("ix_tax_plan_analyses_plan_id", "tax_plan_analyses", ["tax_plan_id"])
    op.create_index(
        "ix_tax_plan_analyses_tenant_status", "tax_plan_analyses", ["tenant_id", "status"]
    )

    # implementation_items table
    op.create_table(
        "implementation_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tax_plan_analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("strategy_ref", sa.String(100), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("estimated_saving", sa.Numeric(12, 2), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("risk_rating", sa.String(20), nullable=True),
        sa.Column("compliance_notes", sa.Text(), nullable=True),
        sa.Column("client_visible", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by", sa.String(20), nullable=True),
        # Timestamps
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_implementation_items_analysis_id", "implementation_items", ["analysis_id"])
    op.create_index(
        "ix_implementation_items_tenant_status", "implementation_items", ["tenant_id", "status"]
    )

    # Add current_analysis_id FK to tax_plans
    op.add_column(
        "tax_plans", sa.Column("current_analysis_id", postgresql.UUID(as_uuid=True), nullable=True)
    )


def downgrade() -> None:
    """Downgrade database from this revision."""
    op.drop_column("tax_plans", "current_analysis_id")
    op.drop_index("ix_implementation_items_tenant_status", table_name="implementation_items")
    op.drop_index("ix_implementation_items_analysis_id", table_name="implementation_items")
    op.drop_table("implementation_items")
    op.drop_index("ix_tax_plan_analyses_tenant_status", table_name="tax_plan_analyses")
    op.drop_index("ix_tax_plan_analyses_plan_id", table_name="tax_plan_analyses")
    op.drop_table("tax_plan_analyses")
