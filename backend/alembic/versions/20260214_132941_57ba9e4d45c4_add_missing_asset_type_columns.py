"""add_missing_asset_type_columns

Revision ID: 57ba9e4d45c4
Revises: fix_journal_source_enum
Create Date: 2026-02-14 13:29:41.016270+00:00

Aligns xero_asset_types table with the SQLAlchemy model (Spec 025).
The original migration created book/tax split columns, but the model
was updated to use unified depreciation columns. This migration adds
the missing columns so the sync doesn't fail.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# Revision identifiers
revision: str = "57ba9e4d45c4"
down_revision: str | None = "fix_journal_source_enum"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add missing columns to xero_asset_types that the model expects."""
    # Add new columns that the model defines but the table is missing
    op.add_column(
        "xero_asset_types",
        sa.Column(
            "fixed_asset_account_id",
            sa.String(50),
            nullable=True,
            comment="Balance sheet account ID",
        ),
    )
    op.add_column(
        "xero_asset_types",
        sa.Column(
            "depreciation_expense_account_id",
            sa.String(50),
            nullable=True,
            comment="P&L depreciation expense account ID",
        ),
    )
    op.add_column(
        "xero_asset_types",
        sa.Column(
            "accumulated_depreciation_account_id",
            sa.String(50),
            nullable=True,
            comment="Accumulated depreciation account ID",
        ),
    )
    op.add_column(
        "xero_asset_types",
        sa.Column(
            "depreciation_method", sa.String(50), nullable=True, comment="Depreciation method"
        ),
    )
    op.add_column(
        "xero_asset_types",
        sa.Column(
            "averaging_method",
            sa.String(20),
            nullable=True,
            comment="Averaging method (FullMonth or ActualDays)",
        ),
    )
    op.add_column(
        "xero_asset_types",
        sa.Column(
            "depreciation_rate",
            sa.Numeric(10, 4),
            nullable=True,
            comment="Annual depreciation rate (%)",
        ),
    )
    op.add_column(
        "xero_asset_types",
        sa.Column(
            "effective_life_years", sa.Integer(), nullable=True, comment="Effective life in years"
        ),
    )
    op.add_column(
        "xero_asset_types",
        sa.Column(
            "calculation_method",
            sa.String(20),
            nullable=True,
            server_default="Rate",
            comment="How depreciation is calculated (Rate/Life)",
        ),
    )
    op.add_column(
        "xero_asset_types",
        sa.Column(
            "locks",
            sa.Integer(),
            nullable=True,
            server_default="0",
            comment="Number of locked periods",
        ),
    )

    # Migrate data from old columns to new columns where possible
    op.execute("""
        UPDATE xero_asset_types SET
            depreciation_method = COALESCE(book_depreciation_method, tax_depreciation_method),
            averaging_method = COALESCE(book_averaging_method, tax_averaging_method),
            depreciation_rate = COALESCE(book_depreciation_rate, tax_depreciation_rate),
            effective_life_years = COALESCE(book_effective_life_years, tax_effective_life_years),
            locks = COALESCE(asset_count, 0)
    """)

    # Drop old columns that the model no longer uses
    op.drop_column("xero_asset_types", "book_depreciation_method")
    op.drop_column("xero_asset_types", "book_depreciation_rate")
    op.drop_column("xero_asset_types", "book_effective_life_years")
    op.drop_column("xero_asset_types", "book_averaging_method")
    op.drop_column("xero_asset_types", "tax_depreciation_method")
    op.drop_column("xero_asset_types", "tax_depreciation_rate")
    op.drop_column("xero_asset_types", "tax_effective_life_years")
    op.drop_column("xero_asset_types", "tax_averaging_method")
    op.drop_column("xero_asset_types", "asset_count")
    op.drop_column("xero_asset_types", "locked_for_accounting_period")


def downgrade() -> None:
    """Reverse: restore old columns, drop new ones."""
    # Restore old columns
    op.add_column("xero_asset_types", sa.Column("book_depreciation_method", sa.String(30)))
    op.add_column("xero_asset_types", sa.Column("book_depreciation_rate", sa.Numeric(10, 4)))
    op.add_column("xero_asset_types", sa.Column("book_effective_life_years", sa.Integer()))
    op.add_column("xero_asset_types", sa.Column("book_averaging_method", sa.String(30)))
    op.add_column("xero_asset_types", sa.Column("tax_depreciation_method", sa.String(30)))
    op.add_column("xero_asset_types", sa.Column("tax_depreciation_rate", sa.Numeric(10, 4)))
    op.add_column("xero_asset_types", sa.Column("tax_effective_life_years", sa.Integer()))
    op.add_column("xero_asset_types", sa.Column("tax_averaging_method", sa.String(30)))
    op.add_column("xero_asset_types", sa.Column("asset_count", sa.Integer()))
    op.add_column("xero_asset_types", sa.Column("locked_for_accounting_period", sa.Date()))

    # Migrate data back
    op.execute("""
        UPDATE xero_asset_types SET
            book_depreciation_method = depreciation_method,
            book_averaging_method = averaging_method,
            book_depreciation_rate = depreciation_rate,
            book_effective_life_years = effective_life_years,
            asset_count = locks
    """)

    # Drop new columns
    op.drop_column("xero_asset_types", "fixed_asset_account_id")
    op.drop_column("xero_asset_types", "depreciation_expense_account_id")
    op.drop_column("xero_asset_types", "accumulated_depreciation_account_id")
    op.drop_column("xero_asset_types", "depreciation_method")
    op.drop_column("xero_asset_types", "averaging_method")
    op.drop_column("xero_asset_types", "depreciation_rate")
    op.drop_column("xero_asset_types", "effective_life_years")
    op.drop_column("xero_asset_types", "calculation_method")
    op.drop_column("xero_asset_types", "locks")
