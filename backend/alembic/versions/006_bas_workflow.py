"""BAS preparation workflow tables.

Revision ID: 006_bas_workflow
Revises: 005_quality_scoring
Create Date: 2025-12-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006_bas_workflow"
down_revision: str | None = "005_quality_scoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create bas_session_status enum (if not exists to handle partial migrations)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE bas_session_status AS ENUM (
                'draft',
                'in_progress',
                'ready_for_review',
                'approved',
                'lodged'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create bas_periods table
    op.create_table(
        "bas_periods",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("connection_id", sa.UUID(), nullable=False),
        # Period identification
        sa.Column("period_type", sa.String(length=10), nullable=False, server_default="quarterly"),
        sa.Column("quarter", sa.Integer(), nullable=True),
        sa.Column("month", sa.Integer(), nullable=True),
        sa.Column("fy_year", sa.Integer(), nullable=False),
        # Period dates
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
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
            "connection_id", "fy_year", "quarter", name="uq_bas_period_connection_quarter"
        ),
        sa.CheckConstraint(
            "quarter IS NULL OR (quarter >= 1 AND quarter <= 4)",
            name="ck_bas_period_quarter_range",
        ),
        sa.CheckConstraint(
            "month IS NULL OR (month >= 1 AND month <= 12)",
            name="ck_bas_period_month_range",
        ),
        sa.CheckConstraint(
            "(quarter IS NOT NULL AND month IS NULL) OR (quarter IS NULL AND month IS NOT NULL)",
            name="ck_bas_period_quarter_xor_month",
        ),
    )

    # Create bas_sessions table
    op.create_table(
        "bas_sessions",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("period_id", sa.UUID(), nullable=False),
        # Status tracking
        sa.Column(
            "status",
            sa.VARCHAR(20),
            nullable=False,
            server_default="draft",
        ),
        # User tracking
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("last_modified_by", sa.UUID(), nullable=True),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        # Calculation timestamps
        sa.Column("gst_calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payg_calculated_at", sa.DateTime(timezone=True), nullable=True),
        # Notes
        sa.Column("internal_notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["period_id"], ["bas_periods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["last_modified_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("period_id", name="uq_bas_session_period"),
    )

    # Create bas_calculations table
    op.create_table(
        "bas_calculations",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        # GST G-fields
        sa.Column(
            "g1_total_sales", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"
        ),
        sa.Column(
            "g2_export_sales", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"
        ),
        sa.Column(
            "g3_gst_free_sales",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "g10_capital_purchases",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "g11_non_capital_purchases",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0",
        ),
        # GST calculated fields
        sa.Column(
            "field_1a_gst_on_sales",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "field_1b_gst_on_purchases",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0",
        ),
        # PAYG fields
        sa.Column(
            "w1_total_wages", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"
        ),
        sa.Column(
            "w2_amount_withheld",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0",
        ),
        # Summary fields
        sa.Column(
            "gst_payable", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"
        ),
        sa.Column(
            "total_payable", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"
        ),
        # Calculation metadata
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("calculation_duration_ms", sa.Integer(), nullable=True),
        sa.Column("transaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invoice_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pay_run_count", sa.Integer(), nullable=False, server_default="0"),
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
        sa.ForeignKeyConstraint(["session_id"], ["bas_sessions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", name="uq_bas_calculation_session"),
    )

    # Create bas_adjustments table
    op.create_table(
        "bas_adjustments",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        # Adjustment details
        sa.Column("field_name", sa.String(length=50), nullable=False),
        sa.Column("adjustment_amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=True),
        # User tracking
        sa.Column("created_by", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(["session_id"], ["bas_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "field_name IN ('g1_total_sales', 'g2_export_sales', 'g3_gst_free_sales', "
            "'g10_capital_purchases', 'g11_non_capital_purchases', 'field_1a_gst_on_sales', "
            "'field_1b_gst_on_purchases', 'w1_total_wages', 'w2_amount_withheld')",
            name="ck_bas_adjustment_field_name",
        ),
    )

    # Create indexes
    op.create_index("idx_bas_periods_tenant", "bas_periods", ["tenant_id"])
    op.create_index("idx_bas_periods_connection", "bas_periods", ["connection_id"])
    op.create_index("idx_bas_sessions_tenant", "bas_sessions", ["tenant_id"])
    op.create_index("idx_bas_sessions_period", "bas_sessions", ["period_id"])
    op.create_index("idx_bas_sessions_status", "bas_sessions", ["status"])
    op.create_index("idx_bas_calculations_tenant", "bas_calculations", ["tenant_id"])
    op.create_index("idx_bas_calculations_session", "bas_calculations", ["session_id"])
    op.create_index("idx_bas_adjustments_tenant", "bas_adjustments", ["tenant_id"])
    op.create_index("idx_bas_adjustments_session", "bas_adjustments", ["session_id"])

    # Enable RLS on all tables
    op.execute("ALTER TABLE bas_periods ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE bas_sessions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE bas_calculations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE bas_adjustments ENABLE ROW LEVEL SECURITY")

    # Create RLS policies for bas_periods
    op.execute("""
        CREATE POLICY bas_periods_tenant_isolation ON bas_periods
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)

    # Create RLS policies for bas_sessions
    op.execute("""
        CREATE POLICY bas_sessions_tenant_isolation ON bas_sessions
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)

    # Create RLS policies for bas_calculations
    op.execute("""
        CREATE POLICY bas_calculations_tenant_isolation ON bas_calculations
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)

    # Create RLS policies for bas_adjustments
    op.execute("""
        CREATE POLICY bas_adjustments_tenant_isolation ON bas_adjustments
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)


def downgrade() -> None:
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS bas_adjustments_tenant_isolation ON bas_adjustments")
    op.execute("DROP POLICY IF EXISTS bas_calculations_tenant_isolation ON bas_calculations")
    op.execute("DROP POLICY IF EXISTS bas_sessions_tenant_isolation ON bas_sessions")
    op.execute("DROP POLICY IF EXISTS bas_periods_tenant_isolation ON bas_periods")

    # Drop indexes
    op.drop_index("idx_bas_adjustments_session", table_name="bas_adjustments")
    op.drop_index("idx_bas_adjustments_tenant", table_name="bas_adjustments")
    op.drop_index("idx_bas_calculations_session", table_name="bas_calculations")
    op.drop_index("idx_bas_calculations_tenant", table_name="bas_calculations")
    op.drop_index("idx_bas_sessions_status", table_name="bas_sessions")
    op.drop_index("idx_bas_sessions_period", table_name="bas_sessions")
    op.drop_index("idx_bas_sessions_tenant", table_name="bas_sessions")
    op.drop_index("idx_bas_periods_connection", table_name="bas_periods")
    op.drop_index("idx_bas_periods_tenant", table_name="bas_periods")

    # Drop tables in reverse order
    op.drop_table("bas_adjustments")
    op.drop_table("bas_calculations")
    op.drop_table("bas_sessions")
    op.drop_table("bas_periods")

    # Drop enum
    op.execute("DROP TYPE IF EXISTS bas_session_status")
