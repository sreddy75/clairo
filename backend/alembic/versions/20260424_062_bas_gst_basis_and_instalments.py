"""BAS GST basis preference and PAYG instalment fields.

Spec 062: Adds GST reporting basis preference to practice_clients,
GST basis snapshot to bas_sessions, and PAYG instalment T1/T2 fields
to bas_calculations. All additions are nullable — zero downtime rollout.

Revision ID: 062_bas_gst_basis_and_instalments
Revises: 060_tax_strategies_phase1
Create Date: 2026-04-24
"""

import sqlalchemy as sa
from alembic import op

revision: str = "062_bas_gst_basis"
down_revision: str | None = "060_tax_strategies_phase1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ----------------------------------------------------------------
    # 1. practice_clients — GST reporting basis preference
    # ----------------------------------------------------------------
    op.add_column(
        "practice_clients",
        sa.Column(
            "gst_reporting_basis",
            sa.String(10),
            nullable=True,
            comment="'cash' or 'accrual'; NULL = not yet set",
        ),
    )
    op.add_column(
        "practice_clients",
        sa.Column(
            "gst_basis_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the GST basis was last changed",
        ),
    )
    op.add_column(
        "practice_clients",
        sa.Column(
            "gst_basis_updated_by",
            sa.dialects.postgresql.UUID(as_uuid=True) if hasattr(sa, "dialects") else sa.String(36),
            nullable=True,
            comment="FK to practice_users — who last changed the basis",
        ),
    )

    # Add CHECK constraint to validate basis values
    op.create_check_constraint(
        "ck_practice_clients_gst_basis",
        "practice_clients",
        "gst_reporting_basis IS NULL OR gst_reporting_basis IN ('cash', 'accrual')",
    )

    # Add FK for gst_basis_updated_by → practice_users
    op.create_foreign_key(
        "fk_practice_clients_gst_basis_updated_by",
        "practice_clients",
        "practice_users",
        ["gst_basis_updated_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # ----------------------------------------------------------------
    # 2. bas_sessions — snapshot of basis used at calculation time
    # ----------------------------------------------------------------
    op.add_column(
        "bas_sessions",
        sa.Column(
            "gst_basis_used",
            sa.String(10),
            nullable=True,
            comment="Snapshot of GST basis at calculation time; immutable after lodgement",
        ),
    )

    op.create_check_constraint(
        "ck_bas_sessions_gst_basis_used",
        "bas_sessions",
        "gst_basis_used IS NULL OR gst_basis_used IN ('cash', 'accrual')",
    )

    # ----------------------------------------------------------------
    # 3. bas_calculations — PAYG instalment T1/T2 (manual entry)
    # ----------------------------------------------------------------
    op.add_column(
        "bas_calculations",
        sa.Column(
            "t1_instalment_income",
            sa.Numeric(15, 2),
            nullable=True,
            comment="PAYG instalment income (T1) — manual entry",
        ),
    )
    op.add_column(
        "bas_calculations",
        sa.Column(
            "t2_instalment_rate",
            sa.Numeric(8, 5),
            nullable=True,
            comment="PAYG instalment rate (T2) — manual entry (e.g. 0.04 = 4%)",
        ),
    )


def downgrade() -> None:
    # bas_calculations
    op.drop_column("bas_calculations", "t2_instalment_rate")
    op.drop_column("bas_calculations", "t1_instalment_income")

    # bas_sessions
    op.drop_constraint("ck_bas_sessions_gst_basis_used", "bas_sessions", type_="check")
    op.drop_column("bas_sessions", "gst_basis_used")

    # practice_clients
    op.drop_constraint(
        "fk_practice_clients_gst_basis_updated_by", "practice_clients", type_="foreignkey"
    )
    op.drop_constraint("ck_practice_clients_gst_basis", "practice_clients", type_="check")
    op.drop_column("practice_clients", "gst_basis_updated_by")
    op.drop_column("practice_clients", "gst_basis_updated_at")
    op.drop_column("practice_clients", "gst_reporting_basis")
