"""Change aggregation tables to use connection_id instead of client_id.

Revision ID: 015_aggregation_connection_id
Revises: 014_fix_client_fk
Create Date: 2025-12-30

All aggregation tables now key by connection_id (XeroConnection/organization)
instead of client_id (XeroClient/contact). Financial data belongs to the
organization, not individual contacts.

Tables affected:
- client_ai_profiles: Make client_id nullable, add unique constraint on connection_id
- client_expense_summaries: Replace client_id with connection_id
- client_ar_aging_summaries: Replace client_id with connection_id
- client_ap_aging_summaries: Replace client_id with connection_id
- client_gst_summaries: Replace client_id with connection_id
- client_monthly_trends: Replace client_id with connection_id
- client_compliance_summaries: Replace client_id with connection_id
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "015_aggregation_connection_id"
down_revision = "014_fix_client_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # ClientAIProfile - already has connection_id, just update constraints
    # =========================================================================

    # Drop old unique constraint on client_id
    op.drop_constraint("uq_client_ai_profile_client", "client_ai_profiles", type_="unique")

    # Drop old index on connection_id (will recreate with constraint)
    op.drop_index("ix_client_ai_profiles_connection", "client_ai_profiles")

    # Make client_id nullable
    op.alter_column("client_ai_profiles", "client_id", nullable=True)

    # Change FK on client_id to SET NULL instead of CASCADE
    op.drop_constraint(
        "fk_client_ai_profiles_client_id_xero_clients", "client_ai_profiles", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_client_ai_profiles_client_id_xero_clients",
        "client_ai_profiles",
        "xero_clients",
        ["client_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add unique constraint on connection_id
    op.create_unique_constraint(
        "uq_client_ai_profile_connection", "client_ai_profiles", ["connection_id"]
    )

    # =========================================================================
    # ClientExpenseSummary - add connection_id, drop client_id
    # =========================================================================

    # Add connection_id column
    op.add_column(
        "client_expense_summaries",
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,  # Temporarily nullable for migration
        ),
    )

    # Populate connection_id from client_id via join (if any data exists)
    op.execute("""
        UPDATE client_expense_summaries ces
        SET connection_id = xc.connection_id
        FROM xero_clients xc
        WHERE ces.client_id = xc.id
    """)

    # Drop old constraints and indexes
    op.drop_constraint(
        "uq_client_expense_summary_period", "client_expense_summaries", type_="unique"
    )
    op.drop_index("ix_client_expense_summaries_client_period", "client_expense_summaries")

    # Drop client_id FK and column
    op.drop_constraint(
        "fk_client_expense_summaries_client_id_xero_clients",
        "client_expense_summaries",
        type_="foreignkey",
    )
    op.drop_column("client_expense_summaries", "client_id")

    # Make connection_id NOT NULL and add FK
    op.alter_column("client_expense_summaries", "connection_id", nullable=False)
    op.create_foreign_key(
        "client_expense_summaries_connection_id_fkey",
        "client_expense_summaries",
        "xero_connections",
        ["connection_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Add new constraints
    op.create_unique_constraint(
        "uq_expense_summary_connection_period",
        "client_expense_summaries",
        ["connection_id", "period_type", "period_start"],
    )
    op.create_index(
        "ix_expense_summaries_connection_period",
        "client_expense_summaries",
        ["connection_id", "period_start"],
    )

    # =========================================================================
    # ClientARAgingSummary - add connection_id, drop client_id
    # =========================================================================

    op.add_column(
        "client_ar_aging_summaries",
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.execute("""
        UPDATE client_ar_aging_summaries cars
        SET connection_id = xc.connection_id
        FROM xero_clients xc
        WHERE cars.client_id = xc.id
    """)

    op.drop_constraint("uq_client_ar_aging_date", "client_ar_aging_summaries", type_="unique")
    op.drop_index("ix_client_ar_aging_client_date", "client_ar_aging_summaries")
    op.drop_constraint(
        "fk_client_ar_aging_summaries_client_id_xero_clients",
        "client_ar_aging_summaries",
        type_="foreignkey",
    )
    op.drop_column("client_ar_aging_summaries", "client_id")

    op.alter_column("client_ar_aging_summaries", "connection_id", nullable=False)
    op.create_foreign_key(
        "client_ar_aging_summaries_connection_id_fkey",
        "client_ar_aging_summaries",
        "xero_connections",
        ["connection_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_unique_constraint(
        "uq_ar_aging_connection_date",
        "client_ar_aging_summaries",
        ["connection_id", "as_of_date"],
    )
    op.create_index(
        "ix_ar_aging_connection_date",
        "client_ar_aging_summaries",
        ["connection_id", "as_of_date"],
    )

    # =========================================================================
    # ClientAPAgingSummary - add connection_id, drop client_id
    # =========================================================================

    op.add_column(
        "client_ap_aging_summaries",
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.execute("""
        UPDATE client_ap_aging_summaries caps
        SET connection_id = xc.connection_id
        FROM xero_clients xc
        WHERE caps.client_id = xc.id
    """)

    op.drop_constraint("uq_client_ap_aging_date", "client_ap_aging_summaries", type_="unique")
    op.drop_index("ix_client_ap_aging_client_date", "client_ap_aging_summaries")
    op.drop_constraint(
        "fk_client_ap_aging_summaries_client_id_xero_clients",
        "client_ap_aging_summaries",
        type_="foreignkey",
    )
    op.drop_column("client_ap_aging_summaries", "client_id")

    op.alter_column("client_ap_aging_summaries", "connection_id", nullable=False)
    op.create_foreign_key(
        "client_ap_aging_summaries_connection_id_fkey",
        "client_ap_aging_summaries",
        "xero_connections",
        ["connection_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_unique_constraint(
        "uq_ap_aging_connection_date",
        "client_ap_aging_summaries",
        ["connection_id", "as_of_date"],
    )
    op.create_index(
        "ix_ap_aging_connection_date",
        "client_ap_aging_summaries",
        ["connection_id", "as_of_date"],
    )

    # =========================================================================
    # ClientGSTSummary - add connection_id, drop client_id
    # =========================================================================

    op.add_column(
        "client_gst_summaries",
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.execute("""
        UPDATE client_gst_summaries cgs
        SET connection_id = xc.connection_id
        FROM xero_clients xc
        WHERE cgs.client_id = xc.id
    """)

    op.drop_constraint("uq_client_gst_summary_period", "client_gst_summaries", type_="unique")
    op.drop_index("ix_client_gst_summaries_client_period", "client_gst_summaries")
    op.drop_constraint(
        "fk_client_gst_summaries_client_id_xero_clients", "client_gst_summaries", type_="foreignkey"
    )
    op.drop_column("client_gst_summaries", "client_id")

    op.alter_column("client_gst_summaries", "connection_id", nullable=False)
    op.create_foreign_key(
        "client_gst_summaries_connection_id_fkey",
        "client_gst_summaries",
        "xero_connections",
        ["connection_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_unique_constraint(
        "uq_gst_summary_connection_period",
        "client_gst_summaries",
        ["connection_id", "period_type", "period_start"],
    )
    op.create_index(
        "ix_gst_summaries_connection_period",
        "client_gst_summaries",
        ["connection_id", "period_start"],
    )

    # =========================================================================
    # ClientMonthlyTrend - add connection_id, drop client_id
    # =========================================================================

    op.add_column(
        "client_monthly_trends",
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.execute("""
        UPDATE client_monthly_trends cmt
        SET connection_id = xc.connection_id
        FROM xero_clients xc
        WHERE cmt.client_id = xc.id
    """)

    op.drop_constraint("uq_client_monthly_trend_period", "client_monthly_trends", type_="unique")
    op.drop_index("ix_client_monthly_trends_client_year_month", "client_monthly_trends")
    op.drop_constraint(
        "fk_client_monthly_trends_client_id_xero_clients",
        "client_monthly_trends",
        type_="foreignkey",
    )
    op.drop_column("client_monthly_trends", "client_id")

    op.alter_column("client_monthly_trends", "connection_id", nullable=False)
    op.create_foreign_key(
        "client_monthly_trends_connection_id_fkey",
        "client_monthly_trends",
        "xero_connections",
        ["connection_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_unique_constraint(
        "uq_monthly_trend_connection_period",
        "client_monthly_trends",
        ["connection_id", "year", "month"],
    )
    op.create_index(
        "ix_monthly_trends_connection_year_month",
        "client_monthly_trends",
        ["connection_id", "year", "month"],
    )

    # =========================================================================
    # ClientComplianceSummary - add connection_id, drop client_id
    # =========================================================================

    op.add_column(
        "client_compliance_summaries",
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.execute("""
        UPDATE client_compliance_summaries ccs
        SET connection_id = xc.connection_id
        FROM xero_clients xc
        WHERE ccs.client_id = xc.id
    """)

    op.drop_constraint(
        "uq_client_compliance_summary_period", "client_compliance_summaries", type_="unique"
    )
    op.drop_index("ix_client_compliance_summaries_client_period", "client_compliance_summaries")
    op.drop_constraint(
        "fk_client_compliance_summaries_client_id_xero_clients",
        "client_compliance_summaries",
        type_="foreignkey",
    )
    op.drop_column("client_compliance_summaries", "client_id")

    op.alter_column("client_compliance_summaries", "connection_id", nullable=False)
    op.create_foreign_key(
        "client_compliance_summaries_connection_id_fkey",
        "client_compliance_summaries",
        "xero_connections",
        ["connection_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_unique_constraint(
        "uq_compliance_summary_connection_period",
        "client_compliance_summaries",
        ["connection_id", "period_type", "period_start"],
    )
    op.create_index(
        "ix_compliance_summaries_connection_period",
        "client_compliance_summaries",
        ["connection_id", "period_start"],
    )


def downgrade() -> None:
    # This is a one-way migration - downgrade would require
    # re-mapping connection_id back to client_id which may not be possible
    # if there are multiple clients per connection.
    raise NotImplementedError(
        "Downgrade not supported - this migration changes the data model "
        "from client-based to connection-based aggregations."
    )
