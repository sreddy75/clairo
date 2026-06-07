"""Add composite performance indexes for BAS calculator queries

Revision ID: perf_indexes_20260416
Revises: b0169fe3036c
Create Date: 2026-04-16 00:00:00.000000+00:00

Adds composite indexes on (connection_id, date) columns for the four Xero
tables queried by the GST/PAYG calculator. These queries filter by
connection_id + date range on every BAS calculation and were previously
relying only on tenant_id-based indexes, causing full scans per connection.

Also adds a (session_id, status) index on tax_code_suggestions to speed
up the suggestion summary query that groups by status per session.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# Revision identifiers
revision: str = "perf_indexes_20260416"
down_revision: str | None = "b0169fe3036c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add composite indexes for BAS calculator date-range queries."""
    # xero_invoices: calculator queries WHERE connection_id = ? AND issue_date BETWEEN ? AND ?
    op.create_index(
        "ix_xero_invoices_conn_date",
        "xero_invoices",
        ["connection_id", "issue_date"],
    )

    # xero_bank_transactions: calculator queries WHERE connection_id = ? AND transaction_date BETWEEN ? AND ?
    op.create_index(
        "ix_xero_bank_transactions_conn_date",
        "xero_bank_transactions",
        ["connection_id", "transaction_date"],
    )

    # xero_credit_notes: calculator queries WHERE connection_id = ? AND issue_date BETWEEN ? AND ?
    op.create_index(
        "ix_xero_credit_notes_conn_date",
        "xero_credit_notes",
        ["connection_id", "issue_date"],
    )

    # xero_pay_runs: calculator queries WHERE connection_id = ? AND payment_date BETWEEN ? AND ?
    # (existing ix_xero_pay_runs_connection_period covers period_start/period_end, not payment_date)
    op.create_index(
        "ix_xero_pay_runs_conn_payment_date",
        "xero_pay_runs",
        ["connection_id", "payment_date"],
    )

    # tax_code_suggestions: suggestion summary query groups by (session_id, status)
    op.create_index(
        "ix_tax_code_suggestions_session_status",
        "tax_code_suggestions",
        ["session_id", "status"],
    )


def downgrade() -> None:
    """Remove performance indexes."""
    op.drop_index("ix_tax_code_suggestions_session_status", table_name="tax_code_suggestions")
    op.drop_index("ix_xero_pay_runs_conn_payment_date", table_name="xero_pay_runs")
    op.drop_index("ix_xero_credit_notes_conn_date", table_name="xero_credit_notes")
    op.drop_index("ix_xero_bank_transactions_conn_date", table_name="xero_bank_transactions")
    op.drop_index("ix_xero_invoices_conn_date", table_name="xero_invoices")
