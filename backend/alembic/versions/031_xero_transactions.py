"""Add credit notes, payments, journals tables (Spec 024)

Revision ID: 031_credit_notes_payments_journals
Revises: 030_xero_reports
Create Date: 2026-01-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision: str = "031_xero_transactions"
down_revision: str | None = "030_xero_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create credit notes, payments, and journals tables for Spec 024."""

    # Create enum types
    op.execute("""
        CREATE TYPE xero_credit_note_type AS ENUM ('accpaycredit', 'accreccredit');
    """)
    op.execute("""
        CREATE TYPE xero_credit_note_status AS ENUM ('draft', 'submitted', 'authorised', 'paid', 'voided');
    """)
    op.execute("""
        CREATE TYPE xero_payment_type AS ENUM (
            'accrecpayment', 'accpaypayment', 'arcreditpayment', 'apcreditpayment',
            'arprepaymentpayment', 'apprepaymentpayment', 'aroverpaymentpayment', 'apoverpaymentpayment'
        );
    """)
    op.execute("""
        CREATE TYPE xero_payment_status AS ENUM ('authorised', 'deleted');
    """)
    op.execute("""
        CREATE TYPE xero_overpayment_status AS ENUM ('authorised', 'paid', 'voided');
    """)
    op.execute("""
        CREATE TYPE xero_prepayment_status AS ENUM ('authorised', 'paid', 'voided');
    """)
    op.execute("""
        CREATE TYPE xero_journal_source_type AS ENUM (
            'accrec', 'accpay', 'cashrec', 'cashpaid', 'accpaycredit', 'accreccredit', 'transfer', 'manjournal'
        );
    """)
    op.execute("""
        CREATE TYPE xero_manual_journal_status AS ENUM ('draft', 'posted', 'deleted', 'voided');
    """)

    # Create xero_credit_notes table
    op.create_table(
        "xero_credit_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("xero_credit_note_id", sa.String(50), nullable=False),
        sa.Column("credit_note_number", sa.String(255), nullable=True),
        sa.Column(
            "credit_note_type",
            postgresql.ENUM(
                "accpaycredit", "accreccredit", name="xero_credit_note_type", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("xero_contact_id", sa.String(50), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft",
                "submitted",
                "authorised",
                "paid",
                "voided",
                name="xero_credit_note_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("issue_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("line_amount_types", sa.String(50), nullable=True),
        sa.Column("subtotal", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("tax_amount", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("total_amount", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("remaining_credit", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="AUD"),
        sa.Column("currency_rate", sa.Numeric(15, 6), nullable=False, server_default="1.0"),
        sa.Column("line_items", postgresql.JSONB, nullable=True),
        sa.Column("xero_updated_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "connection_id", "xero_credit_note_id", name="uq_xero_credit_note_connection_cn"
        ),
    )
    op.create_index("ix_xero_credit_notes_tenant_id", "xero_credit_notes", ["tenant_id"])
    op.create_index("ix_xero_credit_notes_connection_id", "xero_credit_notes", ["connection_id"])
    op.create_index(
        "ix_xero_credit_notes_xero_credit_note_id", "xero_credit_notes", ["xero_credit_note_id"]
    )
    op.create_index(
        "ix_xero_credit_notes_tenant_date", "xero_credit_notes", ["tenant_id", "issue_date"]
    )
    op.create_index(
        "ix_xero_credit_notes_tenant_type", "xero_credit_notes", ["tenant_id", "credit_note_type"]
    )
    op.create_index(
        "ix_xero_credit_notes_tenant_status", "xero_credit_notes", ["tenant_id", "status"]
    )

    # Create xero_credit_note_allocations table
    op.create_table(
        "xero_credit_note_allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "credit_note_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_credit_notes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("xero_allocation_id", sa.String(50), nullable=True),
        sa.Column("xero_invoice_id", sa.String(50), nullable=False),
        sa.Column("invoice_number", sa.String(255), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("allocation_date", sa.DateTime(timezone=True), nullable=False),
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
    )
    op.create_index("ix_xero_cn_alloc_tenant_id", "xero_credit_note_allocations", ["tenant_id"])
    op.create_index(
        "ix_xero_cn_alloc_credit_note", "xero_credit_note_allocations", ["credit_note_id"]
    )
    op.create_index("ix_xero_cn_alloc_invoice", "xero_credit_note_allocations", ["xero_invoice_id"])

    # Create xero_payments table
    op.create_table(
        "xero_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("xero_payment_id", sa.String(50), nullable=False),
        sa.Column(
            "payment_type",
            postgresql.ENUM(
                "accrecpayment",
                "accpaypayment",
                "arcreditpayment",
                "apcreditpayment",
                "arprepaymentpayment",
                "apprepaymentpayment",
                "aroverpaymentpayment",
                "apoverpaymentpayment",
                name="xero_payment_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM("authorised", "deleted", name="xero_payment_status", create_type=False),
            nullable=False,
        ),
        sa.Column("payment_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("currency_rate", sa.Numeric(15, 6), nullable=False, server_default="1.0"),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("is_reconciled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("xero_invoice_id", sa.String(50), nullable=True),
        sa.Column("xero_credit_note_id", sa.String(50), nullable=True),
        sa.Column("xero_account_id", sa.String(50), nullable=True),
        sa.Column("account_code", sa.String(10), nullable=True),
        sa.Column("xero_updated_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "connection_id", "xero_payment_id", name="uq_xero_payment_connection_payment"
        ),
    )
    op.create_index("ix_xero_payments_tenant_id", "xero_payments", ["tenant_id"])
    op.create_index("ix_xero_payments_connection_id", "xero_payments", ["connection_id"])
    op.create_index("ix_xero_payments_xero_payment_id", "xero_payments", ["xero_payment_id"])
    op.create_index("ix_xero_payments_tenant_date", "xero_payments", ["tenant_id", "payment_date"])
    op.create_index("ix_xero_payments_tenant_type", "xero_payments", ["tenant_id", "payment_type"])
    op.create_index("ix_xero_payments_invoice", "xero_payments", ["xero_invoice_id"])
    op.create_index("ix_xero_payments_credit_note", "xero_payments", ["xero_credit_note_id"])

    # Create xero_overpayments table
    op.create_table(
        "xero_overpayments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("xero_overpayment_id", sa.String(50), nullable=False),
        sa.Column("overpayment_type", sa.String(50), nullable=False),
        sa.Column("xero_contact_id", sa.String(50), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "authorised", "paid", "voided", name="xero_overpayment_status", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("overpayment_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subtotal", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("tax_amount", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("total_amount", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("remaining_credit", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="AUD"),
        sa.Column("line_items", postgresql.JSONB, nullable=True),
        sa.Column("xero_updated_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "connection_id", "xero_overpayment_id", name="uq_xero_overpayment_connection_op"
        ),
    )
    op.create_index("ix_xero_overpayments_tenant_id", "xero_overpayments", ["tenant_id"])
    op.create_index("ix_xero_overpayments_connection_id", "xero_overpayments", ["connection_id"])
    op.create_index(
        "ix_xero_overpayments_xero_overpayment_id", "xero_overpayments", ["xero_overpayment_id"]
    )
    op.create_index(
        "ix_xero_overpayments_tenant_date", "xero_overpayments", ["tenant_id", "overpayment_date"]
    )

    # Create xero_prepayments table
    op.create_table(
        "xero_prepayments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("xero_prepayment_id", sa.String(50), nullable=False),
        sa.Column("prepayment_type", sa.String(50), nullable=False),
        sa.Column("xero_contact_id", sa.String(50), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "authorised", "paid", "voided", name="xero_prepayment_status", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("prepayment_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subtotal", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("tax_amount", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("total_amount", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("remaining_credit", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="AUD"),
        sa.Column("line_items", postgresql.JSONB, nullable=True),
        sa.Column("xero_updated_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "connection_id", "xero_prepayment_id", name="uq_xero_prepayment_connection_pp"
        ),
    )
    op.create_index("ix_xero_prepayments_tenant_id", "xero_prepayments", ["tenant_id"])
    op.create_index("ix_xero_prepayments_connection_id", "xero_prepayments", ["connection_id"])
    op.create_index(
        "ix_xero_prepayments_xero_prepayment_id", "xero_prepayments", ["xero_prepayment_id"]
    )
    op.create_index(
        "ix_xero_prepayments_tenant_date", "xero_prepayments", ["tenant_id", "prepayment_date"]
    )

    # Create xero_journals table
    op.create_table(
        "xero_journals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("xero_journal_id", sa.String(50), nullable=False),
        sa.Column("journal_number", sa.Integer, nullable=False),
        sa.Column("journal_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_id", sa.String(50), nullable=True),
        sa.Column(
            "source_type",
            postgresql.ENUM(
                "accrec",
                "accpay",
                "cashrec",
                "cashpaid",
                "accpaycredit",
                "accreccredit",
                "transfer",
                "manjournal",
                name="xero_journal_source_type",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("journal_lines", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("xero_created_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "connection_id", "xero_journal_id", name="uq_xero_journal_connection_journal"
        ),
    )
    op.create_index("ix_xero_journals_tenant_id", "xero_journals", ["tenant_id"])
    op.create_index("ix_xero_journals_connection_id", "xero_journals", ["connection_id"])
    op.create_index("ix_xero_journals_xero_journal_id", "xero_journals", ["xero_journal_id"])
    op.create_index("ix_xero_journals_tenant_date", "xero_journals", ["tenant_id", "journal_date"])
    op.create_index("ix_xero_journals_source", "xero_journals", ["source_id", "source_type"])
    op.create_index("ix_xero_journals_number", "xero_journals", ["connection_id", "journal_number"])

    # Create xero_manual_journals table
    op.create_table(
        "xero_manual_journals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("xero_manual_journal_id", sa.String(50), nullable=False),
        sa.Column("narration", sa.Text, nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft",
                "posted",
                "deleted",
                "voided",
                name="xero_manual_journal_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("journal_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("line_amount_types", sa.String(50), nullable=True),
        sa.Column("show_on_cash_basis", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("journal_lines", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("xero_updated_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "connection_id", "xero_manual_journal_id", name="uq_xero_manual_journal_connection_mj"
        ),
    )
    op.create_index("ix_xero_manual_journals_tenant_id", "xero_manual_journals", ["tenant_id"])
    op.create_index(
        "ix_xero_manual_journals_connection_id", "xero_manual_journals", ["connection_id"]
    )
    op.create_index(
        "ix_xero_manual_journals_xero_manual_journal_id",
        "xero_manual_journals",
        ["xero_manual_journal_id"],
    )
    op.create_index(
        "ix_xero_manual_journals_tenant_date", "xero_manual_journals", ["tenant_id", "journal_date"]
    )
    op.create_index(
        "ix_xero_manual_journals_tenant_status", "xero_manual_journals", ["tenant_id", "status"]
    )


def downgrade() -> None:
    """Drop credit notes, payments, and journals tables."""
    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table("xero_manual_journals")
    op.drop_table("xero_journals")
    op.drop_table("xero_prepayments")
    op.drop_table("xero_overpayments")
    op.drop_table("xero_payments")
    op.drop_table("xero_credit_note_allocations")
    op.drop_table("xero_credit_notes")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS xero_manual_journal_status;")
    op.execute("DROP TYPE IF EXISTS xero_journal_source_type;")
    op.execute("DROP TYPE IF EXISTS xero_prepayment_status;")
    op.execute("DROP TYPE IF EXISTS xero_overpayment_status;")
    op.execute("DROP TYPE IF EXISTS xero_payment_status;")
    op.execute("DROP TYPE IF EXISTS xero_payment_type;")
    op.execute("DROP TYPE IF EXISTS xero_credit_note_status;")
    op.execute("DROP TYPE IF EXISTS xero_credit_note_type;")
