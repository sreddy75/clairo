"""Add Xero Reports tables.

Spec 023: Xero Reports API Integration

This migration creates tables for:
- xero_reports: Cached report data from Xero
- xero_report_sync_jobs: Audit trail for sync operations

Revision ID: 030_xero_reports
Revises: 029_feature_flag_overrides
Create Date: 2026-01-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "030_xero_reports"
down_revision: str | None = "029_feature_flag_overrides"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create enum types first (set create_type=False to prevent double creation)
    xeroreporttype = postgresql.ENUM(
        "profit_and_loss",
        "balance_sheet",
        "aged_receivables_by_contact",
        "aged_payables_by_contact",
        "trial_balance",
        "bank_summary",
        "budget_summary",
        name="xeroreporttype",
        create_type=False,
    )
    xeroreporttype.create(op.get_bind(), checkfirst=True)

    xeroreportsyncstatus = postgresql.ENUM(
        "pending",
        "in_progress",
        "completed",
        "failed",
        "skipped",
        name="xeroreportsyncstatus",
        create_type=False,
    )
    xeroreportsyncstatus.create(op.get_bind(), checkfirst=True)

    # Create xero_reports table
    op.create_table(
        "xero_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "report_type",
            xeroreporttype,
            nullable=False,
        ),
        sa.Column(
            "period_key",
            sa.String(50),
            nullable=False,
            comment="Period identifier: '2025-FY', '2025-Q4', '2025-12', '2025-12-31'",
        ),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column(
            "as_of_date",
            sa.Date(),
            nullable=True,
            comment="For point-in-time reports (Balance Sheet, Aged)",
        ),
        sa.Column("xero_report_id", sa.String(255), nullable=True),
        sa.Column("report_name", sa.String(255), nullable=False),
        sa.Column(
            "report_titles",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "xero_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When Xero last updated this report",
        ),
        sa.Column(
            "rows_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
            comment="Full Rows array from Xero response",
        ),
        sa.Column(
            "summary_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
            comment="Extracted key metrics: revenue, net_profit, current_ratio, etc.",
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "cache_expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When this cached data should be considered stale",
        ),
        sa.Column(
            "is_current_period",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="True if period includes today (affects cache TTL)",
        ),
        sa.Column(
            "parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
            comment="Query params used: timeframe, periods, standardLayout, etc.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_xero_reports_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["xero_connections.id"],
            name="fk_xero_reports_connection",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "connection_id",
            "report_type",
            "period_key",
            name="uq_xero_reports_connection_type_period",
        ),
    )

    # Create indexes for xero_reports
    op.create_index(
        "ix_xero_reports_tenant_id",
        "xero_reports",
        ["tenant_id"],
    )
    op.create_index(
        "ix_xero_reports_connection_id",
        "xero_reports",
        ["connection_id"],
    )
    op.create_index(
        "ix_xero_reports_tenant_type",
        "xero_reports",
        ["tenant_id", "report_type"],
    )
    op.create_index(
        "ix_xero_reports_cache_expires",
        "xero_reports",
        ["cache_expires_at"],
    )

    # Create xero_report_sync_jobs table
    op.create_table(
        "xero_report_sync_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "report_type",
            xeroreporttype,
            nullable=False,
        ),
        sa.Column(
            "status",
            xeroreportsyncstatus,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "duration_ms",
            sa.Integer(),
            nullable=True,
            comment="Total sync duration in milliseconds",
        ),
        sa.Column(
            "rows_fetched",
            sa.Integer(),
            nullable=True,
            comment="Number of rows in fetched report",
        ),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Resulting report record if successful",
        ),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "triggered_by",
            sa.String(50),
            nullable=False,
            server_default="'scheduled'",
            comment="'scheduled', 'on_demand', 'retry'",
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="User who triggered on-demand sync",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_xero_report_sync_jobs_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["xero_connections.id"],
            name="fk_xero_report_sync_jobs_connection",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["xero_reports.id"],
            name="fk_xero_report_sync_jobs_report",
            ondelete="SET NULL",
        ),
    )

    # Create indexes for xero_report_sync_jobs
    op.create_index(
        "ix_xero_report_sync_jobs_tenant_id",
        "xero_report_sync_jobs",
        ["tenant_id"],
    )
    op.create_index(
        "ix_xero_report_sync_jobs_connection_id",
        "xero_report_sync_jobs",
        ["connection_id"],
    )
    op.create_index(
        "ix_xero_report_sync_jobs_status",
        "xero_report_sync_jobs",
        ["status", "next_retry_at"],
    )


def downgrade() -> None:
    # Drop tables
    op.drop_table("xero_report_sync_jobs")
    op.drop_table("xero_reports")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS xeroreportsyncstatus")
    op.execute("DROP TYPE IF EXISTS xeroreporttype")
