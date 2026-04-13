"""Add is_reconciled and auto_park_reason to tax_code_suggestions.

Spec 057: BAS Transaction Grouping by Xero Reconciliation Status.
- is_reconciled: mirrors XeroBankTransaction.is_reconciled at suggestion creation time.
  NULL for invoices/credit notes; True/False for bank transactions.
- auto_park_reason: set to 'unreconciled_in_xero' when system auto-parks a suggestion;
  NULL for manually parked items and all non-auto-parked suggestions.

Revision ID: 057_reconciliation_fields
Revises: 056_suggestion_notes
Create Date: 2026-04-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "057_reconciliation_fields"
down_revision: str | None = "056_suggestion_notes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tax_code_suggestions",
        sa.Column("is_reconciled", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "tax_code_suggestions",
        sa.Column("auto_park_reason", sa.String(50), nullable=True),
    )
    op.create_index(
        "ix_tax_code_suggestions_session_reconciled",
        "tax_code_suggestions",
        ["session_id", "is_reconciled"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tax_code_suggestions_session_reconciled",
        table_name="tax_code_suggestions",
    )
    op.drop_column("tax_code_suggestions", "auto_park_reason")
    op.drop_column("tax_code_suggestions", "is_reconciled")
