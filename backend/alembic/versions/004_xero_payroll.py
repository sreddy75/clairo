"""Add Xero payroll tables for PAYG withholding data.

Revision ID: 004_xero_payroll
Revises: 003_xero_sync
Create Date: 2025-12-29

This migration adds:
- Payroll tracking columns to xero_connections table
- xero_employees table for synced Xero employees
- xero_pay_runs table for synced pay runs
- RLS policies for all new tables

Required for complete BAS lodgement with PAYG withholding (labels W1, W2, 4).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004_xero_payroll"
down_revision: str | None = "003_xero_sync"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add payroll columns and create payroll entity tables."""

    # =========================================================================
    # Add payroll tracking columns to xero_connections
    # =========================================================================

    op.add_column(
        "xero_connections",
        sa.Column(
            "has_payroll_access",
            sa.Boolean,
            nullable=False,
            server_default="false",
            comment="Whether payroll scopes were granted",
        ),
    )
    op.add_column(
        "xero_connections",
        sa.Column(
            "last_payroll_sync_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last successful payroll sync timestamp",
        ),
    )
    op.add_column(
        "xero_connections",
        sa.Column(
            "last_employees_sync_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last successful employees sync timestamp",
        ),
    )

    # =========================================================================
    # Create PostgreSQL Enums for payroll entities
    # =========================================================================

    xero_employee_status_enum = postgresql.ENUM(
        "active",
        "terminated",
        name="xero_employee_status",
        create_type=True,
    )
    xero_employee_status_enum.create(op.get_bind(), checkfirst=True)

    xero_pay_run_status_enum = postgresql.ENUM(
        "draft",
        "posted",
        name="xero_pay_run_status",
        create_type=True,
    )
    xero_pay_run_status_enum.create(op.get_bind(), checkfirst=True)

    # =========================================================================
    # Create xero_employees table
    # =========================================================================

    op.create_table(
        "xero_employees",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("xero_employee_id", sa.String(50), nullable=False, index=True),
        sa.Column("first_name", sa.String(255), nullable=True),
        sa.Column("last_name", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active",
                "terminated",
                name="xero_employee_status",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("termination_date", sa.Date, nullable=True),
        sa.Column("job_title", sa.String(255), nullable=True),
        sa.Column("xero_updated_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "connection_id",
            "xero_employee_id",
            name="uq_xero_employee_connection_employee",
        ),
    )

    op.create_index(
        "ix_xero_employees_tenant_status",
        "xero_employees",
        ["tenant_id", "status"],
    )

    # =========================================================================
    # Create xero_pay_runs table
    # =========================================================================

    op.create_table(
        "xero_pay_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("xero_pay_run_id", sa.String(50), nullable=False, index=True),
        sa.Column("payroll_calendar_id", sa.String(50), nullable=True),
        sa.Column(
            "pay_run_status",
            postgresql.ENUM(
                "draft",
                "posted",
                name="xero_pay_run_status",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("payment_date", sa.Date, nullable=False),
        # Financial totals for BAS
        sa.Column(
            "total_wages",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0.00",
            comment="Total wages paid (BAS W1)",
        ),
        sa.Column(
            "total_tax",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0.00",
            comment="Total PAYG tax withheld (BAS W2/4)",
        ),
        sa.Column(
            "total_super",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0.00",
            comment="Total superannuation",
        ),
        sa.Column(
            "total_deductions",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "total_reimbursements",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "total_net_pay",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column("employee_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("xero_updated_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "connection_id",
            "xero_pay_run_id",
            name="uq_xero_pay_run_connection_payrun",
        ),
    )

    op.create_index(
        "ix_xero_pay_runs_tenant_payment_date",
        "xero_pay_runs",
        ["tenant_id", "payment_date"],
    )
    op.create_index(
        "ix_xero_pay_runs_connection_period",
        "xero_pay_runs",
        ["connection_id", "period_start", "period_end"],
    )

    # =========================================================================
    # Enable RLS on all new tables
    # =========================================================================

    for table_name in ["xero_employees", "xero_pay_runs"]:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{table_name} ON {table_name}
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
            """
        )

    # =========================================================================
    # Create updated_at triggers for all new tables
    # =========================================================================

    for table_name in ["xero_employees", "xero_pay_runs"]:
        op.execute(
            f"""
            CREATE TRIGGER {table_name}_updated_at
            BEFORE UPDATE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
            """
        )


def downgrade() -> None:
    """Drop payroll columns and entity tables."""

    # Drop triggers
    for table_name in ["xero_employees", "xero_pay_runs"]:
        op.execute(f"DROP TRIGGER IF EXISTS {table_name}_updated_at ON {table_name}")

    # Drop RLS policies
    for table_name in ["xero_employees", "xero_pay_runs"]:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table_name} ON {table_name}")

    # Drop tables
    op.drop_table("xero_pay_runs")
    op.drop_table("xero_employees")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS xero_pay_run_status")
    op.execute("DROP TYPE IF EXISTS xero_employee_status")

    # Drop columns from xero_connections
    op.drop_column("xero_connections", "last_employees_sync_at")
    op.drop_column("xero_connections", "last_payroll_sync_at")
    op.drop_column("xero_connections", "has_payroll_access")
