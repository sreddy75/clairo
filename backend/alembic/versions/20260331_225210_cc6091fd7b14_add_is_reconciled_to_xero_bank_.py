"""add is_reconciled to xero_bank_transactions

Revision ID: cc6091fd7b14
Revises: d146710cbb84
Create Date: 2026-03-31 22:52:10.775061+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# Revision identifiers
revision: str = 'cc6091fd7b14'
down_revision: str | None = 'd146710cbb84'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database to this revision."""
    op.add_column(
        "xero_bank_transactions",
        sa.Column("is_reconciled", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index(
        "ix_xero_transactions_reconciled_date",
        "xero_bank_transactions",
        ["xero_bank_account_id", "is_reconciled", "transaction_date"],
    )


def downgrade() -> None:
    """Downgrade database from this revision."""
    op.drop_index("ix_xero_transactions_reconciled_date", table_name="xero_bank_transactions")
    op.drop_column("xero_bank_transactions", "is_reconciled")
