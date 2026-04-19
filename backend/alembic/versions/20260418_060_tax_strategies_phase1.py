"""Tax strategies KB Phase 1 infrastructure.

Spec 060: Creates the tax_strategies and tax_strategy_authoring_jobs tables
and adds three nullable columns on content_chunks (tax_strategy_id FK,
chunk_section, context_header). All additions are purely additive — no
existing column renamed, no backfill required. See
specs/060-tax-strategies-kb/data-model.md.

Revision ID: 060_tax_strategies_phase1
Revises: 059_1_as_at_date
Create Date: 2026-04-18
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "060_tax_strategies_phase1"
down_revision: str | None = "059_1_as_at_date"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # 1. tax_strategies parent table
    # -----------------------------------------------------------------
    op.create_table(
        "tax_strategies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("strategy_id", sa.String(16), nullable=False),
        sa.Column("source_ref", sa.String(32), nullable=True),
        sa.Column(
            "tenant_id",
            sa.String(64),
            nullable=False,
            server_default="platform",
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "categories",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("implementation_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("explanation_text", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "entity_types",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("income_band_min", sa.Integer(), nullable=True),
        sa.Column("income_band_max", sa.Integer(), nullable=True),
        sa.Column("turnover_band_min", sa.Integer(), nullable=True),
        sa.Column("turnover_band_max", sa.Integer(), nullable=True),
        sa.Column("age_min", sa.Integer(), nullable=True),
        sa.Column("age_max", sa.Integer(), nullable=True),
        sa.Column(
            "industry_triggers",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "financial_impact_type",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "keywords",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "ato_sources",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "case_refs",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="stub",
        ),
        sa.Column("fy_applicable_from", sa.Date(), nullable=True),
        sa.Column("fy_applicable_to", sa.Date(), nullable=True),
        sa.Column(
            "last_reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("reviewer_clerk_user_id", sa.String(120), nullable=True),
        sa.Column("reviewer_display_name", sa.String(200), nullable=True),
        sa.Column("superseded_by_strategy_id", sa.String(16), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Partial unique index: only one live row per CLR-id; older versions stay
    op.create_index(
        "uq_tax_strategies_strategy_id_live",
        "tax_strategies",
        ["strategy_id"],
        unique=True,
        postgresql_where=sa.text("superseded_by_strategy_id IS NULL"),
    )
    op.create_index(
        "ix_tax_strategies_strategy_id",
        "tax_strategies",
        ["strategy_id"],
    )
    op.create_index(
        "ix_tax_strategies_source_ref",
        "tax_strategies",
        ["source_ref"],
    )
    op.create_index(
        "ix_tax_strategies_tenant_id",
        "tax_strategies",
        ["tenant_id"],
    )
    op.create_index(
        "ix_tax_strategies_status",
        "tax_strategies",
        ["status"],
    )
    op.create_index(
        "ix_tax_strategies_tenant_status",
        "tax_strategies",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_tax_strategies_categories",
        "tax_strategies",
        ["categories"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_tax_strategies_entity_types",
        "tax_strategies",
        ["entity_types"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_tax_strategies_industry_triggers",
        "tax_strategies",
        ["industry_triggers"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_tax_strategies_keywords",
        "tax_strategies",
        ["keywords"],
        postgresql_using="gin",
    )

    # -----------------------------------------------------------------
    # 2. tax_strategy_authoring_jobs
    # -----------------------------------------------------------------
    op.create_table(
        "tax_strategy_authoring_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("strategy_id", sa.String(16), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "input_payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("output_payload", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.String(120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_tax_strategy_authoring_jobs_strategy_id",
        "tax_strategy_authoring_jobs",
        ["strategy_id"],
    )
    op.create_index(
        "ix_tax_strategy_authoring_jobs_stage",
        "tax_strategy_authoring_jobs",
        ["stage"],
    )
    op.create_index(
        "ix_tax_strategy_authoring_jobs_status",
        "tax_strategy_authoring_jobs",
        ["status"],
    )
    op.create_index(
        "ix_tax_strategy_authoring_jobs_strategy_stage_created",
        "tax_strategy_authoring_jobs",
        ["strategy_id", "stage", "created_at"],
    )
    op.create_index(
        "ix_tax_strategy_authoring_jobs_stage_status",
        "tax_strategy_authoring_jobs",
        ["stage", "status"],
    )

    # -----------------------------------------------------------------
    # 3. content_chunks extensions — three nullable columns
    # -----------------------------------------------------------------
    op.add_column(
        "content_chunks",
        sa.Column(
            "tax_strategy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tax_strategies.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "content_chunks",
        sa.Column("chunk_section", sa.String(32), nullable=True),
    )
    op.add_column(
        "content_chunks",
        sa.Column("context_header", sa.String(300), nullable=True),
    )
    op.create_index(
        "ix_content_chunks_tax_strategy_id",
        "content_chunks",
        ["tax_strategy_id"],
    )


def downgrade() -> None:
    # Reverse order — drop content_chunks extensions first, then child table,
    # then parent table.
    op.drop_index("ix_content_chunks_tax_strategy_id", table_name="content_chunks")
    op.drop_column("content_chunks", "context_header")
    op.drop_column("content_chunks", "chunk_section")
    op.drop_column("content_chunks", "tax_strategy_id")

    op.drop_index(
        "ix_tax_strategy_authoring_jobs_stage_status",
        table_name="tax_strategy_authoring_jobs",
    )
    op.drop_index(
        "ix_tax_strategy_authoring_jobs_strategy_stage_created",
        table_name="tax_strategy_authoring_jobs",
    )
    op.drop_index(
        "ix_tax_strategy_authoring_jobs_status",
        table_name="tax_strategy_authoring_jobs",
    )
    op.drop_index(
        "ix_tax_strategy_authoring_jobs_stage",
        table_name="tax_strategy_authoring_jobs",
    )
    op.drop_index(
        "ix_tax_strategy_authoring_jobs_strategy_id",
        table_name="tax_strategy_authoring_jobs",
    )
    op.drop_table("tax_strategy_authoring_jobs")

    op.drop_index("ix_tax_strategies_keywords", table_name="tax_strategies")
    op.drop_index("ix_tax_strategies_industry_triggers", table_name="tax_strategies")
    op.drop_index("ix_tax_strategies_entity_types", table_name="tax_strategies")
    op.drop_index("ix_tax_strategies_categories", table_name="tax_strategies")
    op.drop_index("ix_tax_strategies_tenant_status", table_name="tax_strategies")
    op.drop_index("ix_tax_strategies_status", table_name="tax_strategies")
    op.drop_index("ix_tax_strategies_tenant_id", table_name="tax_strategies")
    op.drop_index("ix_tax_strategies_source_ref", table_name="tax_strategies")
    op.drop_index("ix_tax_strategies_strategy_id", table_name="tax_strategies")
    op.drop_index(
        "uq_tax_strategies_strategy_id_live",
        table_name="tax_strategies",
    )
    op.drop_table("tax_strategies")
