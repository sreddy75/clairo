"""Quality scoring tables.

Revision ID: 005_quality_scoring
Revises: 004_xero_payroll
Create Date: 2025-12-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005_quality_scoring"
down_revision: str | None = "004_xero_payroll"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create quality_scores table
    op.create_table(
        "quality_scores",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("connection_id", sa.UUID(), nullable=False),
        sa.Column("quarter", sa.Integer(), nullable=False),
        sa.Column("fy_year", sa.Integer(), nullable=False),
        # Overall weighted score
        sa.Column("overall_score", sa.Numeric(precision=5, scale=2), nullable=False),
        # Individual dimension scores (0-100)
        sa.Column("freshness_score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("reconciliation_score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("categorization_score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("completeness_score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column(
            "payg_score", sa.Numeric(precision=5, scale=2), nullable=True
        ),  # NULL if not applicable
        # Calculation metadata
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("calculation_duration_ms", sa.Integer(), nullable=True),
        sa.Column("trigger_reason", sa.String(length=50), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["xero_connections.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "connection_id", "quarter", "fy_year", name="uq_quality_scores_connection_quarter"
        ),
        sa.CheckConstraint("quarter >= 1 AND quarter <= 4", name="ck_quality_scores_quarter_range"),
        sa.CheckConstraint("fy_year >= 2020", name="ck_quality_scores_fy_year_min"),
        sa.CheckConstraint(
            "overall_score >= 0 AND overall_score <= 100", name="ck_quality_scores_overall_range"
        ),
    )

    # Create quality_issues table
    op.create_table(
        "quality_issues",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("connection_id", sa.UUID(), nullable=False),
        sa.Column("quarter", sa.Integer(), nullable=False),
        sa.Column("fy_year", sa.Integer(), nullable=False),
        # Issue identification
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Affected entities
        sa.Column("affected_entity_type", sa.String(length=50), nullable=True),
        sa.Column("affected_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "affected_ids", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("suggested_action", sa.Text(), nullable=True),
        # Lifecycle
        sa.Column(
            "first_detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        # Dismissal
        sa.Column("dismissed", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("dismissed_by", sa.UUID(), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_reason", sa.Text(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["xero_connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dismissed_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "severity IN ('critical', 'error', 'warning', 'info')",
            name="ck_quality_issues_severity",
        ),
    )

    # Create indexes for quality_scores
    op.create_index("idx_quality_scores_tenant", "quality_scores", ["tenant_id"])
    op.create_index("idx_quality_scores_connection", "quality_scores", ["connection_id"])
    op.create_index("idx_quality_scores_quarter", "quality_scores", ["quarter", "fy_year"])

    # Create indexes for quality_issues
    op.create_index("idx_quality_issues_tenant", "quality_issues", ["tenant_id"])
    op.create_index("idx_quality_issues_connection", "quality_issues", ["connection_id"])
    op.create_index("idx_quality_issues_quarter", "quality_issues", ["quarter", "fy_year"])
    op.create_index("idx_quality_issues_severity", "quality_issues", ["severity"])
    op.create_index("idx_quality_issues_dismissed", "quality_issues", ["dismissed"])
    op.create_index("idx_quality_issues_code", "quality_issues", ["code"])

    # Enable RLS on quality_scores
    op.execute("ALTER TABLE quality_scores ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY quality_scores_tenant_isolation ON quality_scores
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )

    # Enable RLS on quality_issues
    op.execute("ALTER TABLE quality_issues ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY quality_issues_tenant_isolation ON quality_issues
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )


def downgrade() -> None:
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS quality_issues_tenant_isolation ON quality_issues")
    op.execute("DROP POLICY IF EXISTS quality_scores_tenant_isolation ON quality_scores")

    # Drop indexes for quality_issues
    op.drop_index("idx_quality_issues_code", table_name="quality_issues")
    op.drop_index("idx_quality_issues_dismissed", table_name="quality_issues")
    op.drop_index("idx_quality_issues_severity", table_name="quality_issues")
    op.drop_index("idx_quality_issues_quarter", table_name="quality_issues")
    op.drop_index("idx_quality_issues_connection", table_name="quality_issues")
    op.drop_index("idx_quality_issues_tenant", table_name="quality_issues")

    # Drop indexes for quality_scores
    op.drop_index("idx_quality_scores_quarter", table_name="quality_scores")
    op.drop_index("idx_quality_scores_connection", table_name="quality_scores")
    op.drop_index("idx_quality_scores_tenant", table_name="quality_scores")

    # Drop tables
    op.drop_table("quality_issues")
    op.drop_table("quality_scores")
