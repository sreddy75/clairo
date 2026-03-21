"""fix_xero_schema_drift

Fix schema drift between SQLAlchemy models and database for tables
created in migration 032_spec_025_fixed_assets_enhanced_analysis:

1. Add missing expected_arrival_date column to xero_purchase_orders
2. Add missing xero_updated_at column to xero_purchase_orders
3. Rename constraint on xero_purchase_orders to match model name
4. Rename constraint on xero_repeating_invoices to match model name

Revision ID: c7e4a2f39b01
Revises: a3f9c8d21e74
Create Date: 2026-02-22 00:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers
revision: str = "c7e4a2f39b01"
down_revision: str | None = "a3f9c8d21e74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table: str, column: str) -> bool:
    """Check if a column exists on a table."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.scalar() is not None


def _constraint_exists(constraint_name: str) -> bool:
    """Check if a constraint exists."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM information_schema.table_constraints WHERE constraint_name = :name"),
        {"name": constraint_name},
    )
    return result.scalar() is not None


def upgrade() -> None:
    """Fix schema drift for xero_purchase_orders and xero_repeating_invoices."""
    # 1. Add missing expected_arrival_date column (if not already present)
    if not _column_exists("xero_purchase_orders", "expected_arrival_date"):
        op.add_column(
            "xero_purchase_orders",
            sa.Column(
                "expected_arrival_date",
                sa.Date(),
                nullable=True,
                comment="Expected arrival date from Xero",
            ),
        )

    # 2. Add missing xero_updated_at column (if not already present)
    if not _column_exists("xero_purchase_orders", "xero_updated_at"):
        op.add_column(
            "xero_purchase_orders",
            sa.Column(
                "xero_updated_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )

    # 3. Rename unique constraint on xero_purchase_orders (if old name exists)
    if _constraint_exists("uq_xero_purchase_orders_connection_xero_id"):
        op.execute(
            "ALTER TABLE xero_purchase_orders "
            'RENAME CONSTRAINT "uq_xero_purchase_orders_connection_xero_id" '
            'TO "uq_xero_purchase_order_connection_po"'
        )

    # 4. Rename unique constraint on xero_repeating_invoices (if old name exists)
    if _constraint_exists("uq_xero_repeating_invoices_connection_xero_id"):
        op.execute(
            "ALTER TABLE xero_repeating_invoices "
            'RENAME CONSTRAINT "uq_xero_repeating_invoices_connection_xero_id" '
            'TO "uq_xero_repeating_invoice_connection_ri"'
        )


def downgrade() -> None:
    """Reverse schema drift fixes."""
    # Reverse constraint renames
    op.execute(
        "ALTER TABLE xero_repeating_invoices "
        'RENAME CONSTRAINT "uq_xero_repeating_invoice_connection_ri" '
        'TO "uq_xero_repeating_invoices_connection_xero_id"'
    )
    op.execute(
        "ALTER TABLE xero_purchase_orders "
        'RENAME CONSTRAINT "uq_xero_purchase_order_connection_po" '
        'TO "uq_xero_purchase_orders_connection_xero_id"'
    )

    # Remove added columns
    op.drop_column("xero_purchase_orders", "xero_updated_at")
    op.drop_column("xero_purchase_orders", "expected_arrival_date")
