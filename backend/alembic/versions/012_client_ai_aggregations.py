"""Create client AI context aggregation tables.

Revision ID: 012_client_ai_aggregations
Revises: 011_chat_conversations
Create Date: 2025-12-30

Tables:
- client_ai_profiles: Tier 1 profile data (always included in context)
- client_expense_summaries: Expense aggregations by category/period
- client_ar_aging_summaries: Accounts receivable aging buckets
- client_ap_aging_summaries: Accounts payable aging buckets
- client_gst_summaries: GST/BAS period summaries
- client_monthly_trends: Monthly financial metrics
- client_compliance_summaries: Payroll/super/contractor data

All tables have RLS policies for tenant isolation.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "012_client_ai_aggregations"
down_revision = "011_chat_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums
    period_type_enum = postgresql.ENUM(
        "month",
        "quarter",
        "year",
        name="period_type",
        create_type=False,
    )
    period_type_enum.create(op.get_bind(), checkfirst=True)

    revenue_bracket_enum = postgresql.ENUM(
        "micro",
        "small",
        "medium",
        "large",
        "enterprise",
        name="revenue_bracket",
        create_type=False,
    )
    revenue_bracket_enum.create(op.get_bind(), checkfirst=True)

    # 1. client_ai_profiles
    op.create_table(
        "client_ai_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("industry_code", sa.String(10), nullable=True),
        sa.Column("gst_registered", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("revenue_bracket", revenue_bracket_enum, nullable=True),
        sa.Column("employee_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name="pk_client_ai_profiles"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["xero_clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["xero_connections.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("client_id", name="uq_client_ai_profile_client"),
    )
    op.create_index("ix_client_ai_profiles_tenant", "client_ai_profiles", ["tenant_id"])
    op.create_index("ix_client_ai_profiles_connection", "client_ai_profiles", ["connection_id"])
    op.create_index("ix_client_ai_profiles_client_id", "client_ai_profiles", ["client_id"])

    # 2. client_expense_summaries
    op.create_table(
        "client_expense_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_type", period_type_enum, nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("by_account_code", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("by_category", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("total_expenses", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("total_gst", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("transaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name="pk_client_expense_summaries"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["xero_clients.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "client_id", "period_type", "period_start", name="uq_client_expense_summary_period"
        ),
    )
    op.create_index("ix_client_expense_summaries_tenant", "client_expense_summaries", ["tenant_id"])
    op.create_index(
        "ix_client_expense_summaries_client_period",
        "client_expense_summaries",
        ["client_id", "period_start"],
    )

    # 3. client_ar_aging_summaries
    op.create_table(
        "client_ar_aging_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("current_amount", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("days_31_60", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("days_61_90", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("over_90_days", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("total_outstanding", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("top_debtors", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name="pk_client_ar_aging_summaries"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["xero_clients.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("client_id", "as_of_date", name="uq_client_ar_aging_date"),
    )
    op.create_index("ix_client_ar_aging_tenant", "client_ar_aging_summaries", ["tenant_id"])
    op.create_index(
        "ix_client_ar_aging_client_date", "client_ar_aging_summaries", ["client_id", "as_of_date"]
    )

    # 4. client_ap_aging_summaries
    op.create_table(
        "client_ap_aging_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("current_amount", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("days_31_60", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("days_61_90", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("over_90_days", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("total_outstanding", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("top_creditors", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name="pk_client_ap_aging_summaries"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["xero_clients.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("client_id", "as_of_date", name="uq_client_ap_aging_date"),
    )
    op.create_index("ix_client_ap_aging_tenant", "client_ap_aging_summaries", ["tenant_id"])
    op.create_index(
        "ix_client_ap_aging_client_date", "client_ap_aging_summaries", ["client_id", "as_of_date"]
    )

    # 5. client_gst_summaries
    op.create_table(
        "client_gst_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_type", period_type_enum, nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("gst_on_sales_1a", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("gst_on_purchases_1b", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("net_gst", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("total_sales", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("total_purchases", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("adjustments", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name="pk_client_gst_summaries"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["xero_clients.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "client_id", "period_type", "period_start", name="uq_client_gst_summary_period"
        ),
    )
    op.create_index("ix_client_gst_summaries_tenant", "client_gst_summaries", ["tenant_id"])
    op.create_index(
        "ix_client_gst_summaries_client_period",
        "client_gst_summaries",
        ["client_id", "period_start"],
    )

    # 6. client_monthly_trends
    op.create_table(
        "client_monthly_trends",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("revenue", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("expenses", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("gross_profit", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("net_cashflow", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name="pk_client_monthly_trends"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["xero_clients.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("client_id", "year", "month", name="uq_client_monthly_trend_period"),
    )
    op.create_index("ix_client_monthly_trends_tenant", "client_monthly_trends", ["tenant_id"])
    op.create_index(
        "ix_client_monthly_trends_client_year_month",
        "client_monthly_trends",
        ["client_id", "year", "month"],
    )

    # 7. client_compliance_summaries
    op.create_table(
        "client_compliance_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_type", period_type_enum, nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("total_wages", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("total_payg_withheld", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("total_super", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("employee_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("contractor_payments", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("contractor_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name="pk_client_compliance_summaries"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["xero_clients.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "client_id", "period_type", "period_start", name="uq_client_compliance_summary_period"
        ),
    )
    op.create_index(
        "ix_client_compliance_summaries_tenant", "client_compliance_summaries", ["tenant_id"]
    )
    op.create_index(
        "ix_client_compliance_summaries_client_period",
        "client_compliance_summaries",
        ["client_id", "period_start"],
    )

    # Add RLS policies for all tables
    tables = [
        "client_ai_profiles",
        "client_expense_summaries",
        "client_ar_aging_summaries",
        "client_ap_aging_summaries",
        "client_gst_summaries",
        "client_monthly_trends",
        "client_compliance_summaries",
    ]

    for table in tables:
        # Enable RLS
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

        # Create policy for tenant isolation
        op.execute(f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (tenant_id::text = current_setting('app.current_tenant_id', true))
            WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true))
        """)


def downgrade() -> None:
    # Drop tables in reverse order
    tables = [
        "client_compliance_summaries",
        "client_monthly_trends",
        "client_gst_summaries",
        "client_ap_aging_summaries",
        "client_ar_aging_summaries",
        "client_expense_summaries",
        "client_ai_profiles",
    ]

    for table in tables:
        # Drop RLS policy first
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.drop_table(table)

    # Drop enums
    op.execute("DROP TYPE IF EXISTS period_type")
    op.execute("DROP TYPE IF EXISTS revenue_bracket")
