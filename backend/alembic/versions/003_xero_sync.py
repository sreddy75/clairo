"""Add Xero sync tracking columns and sync entity tables.

Revision ID: 003_xero_sync
Revises: 002_xero_oauth
Create Date: 2025-12-28

This migration adds:
- Sync tracking columns to xero_connections table
- xero_sync_jobs table for tracking sync job execution
- xero_clients table for synced Xero contacts
- xero_invoices table for synced invoices
- xero_bank_transactions table for synced bank transactions
- xero_accounts table for synced chart of accounts
- RLS policies for all new tables
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003_xero_sync"
down_revision: str | None = "002_xero_oauth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add sync columns and create sync entity tables."""

    # =========================================================================
    # Add sync tracking columns to xero_connections
    # =========================================================================

    op.add_column(
        "xero_connections",
        sa.Column(
            "last_contacts_sync_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last successful contacts sync timestamp",
        ),
    )
    op.add_column(
        "xero_connections",
        sa.Column(
            "last_invoices_sync_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last successful invoices sync timestamp",
        ),
    )
    op.add_column(
        "xero_connections",
        sa.Column(
            "last_transactions_sync_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last successful bank transactions sync timestamp",
        ),
    )
    op.add_column(
        "xero_connections",
        sa.Column(
            "last_accounts_sync_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last successful accounts sync timestamp",
        ),
    )
    op.add_column(
        "xero_connections",
        sa.Column(
            "last_full_sync_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last successful full sync timestamp",
        ),
    )
    op.add_column(
        "xero_connections",
        sa.Column(
            "sync_in_progress",
            sa.Boolean,
            nullable=False,
            server_default="false",
            comment="Whether a sync is currently in progress",
        ),
    )

    # =========================================================================
    # Create PostgreSQL Enums for sync entities
    # =========================================================================

    xero_sync_type_enum = postgresql.ENUM(
        "contacts",
        "invoices",
        "bank_transactions",
        "accounts",
        "full",
        name="xero_sync_type",
        create_type=True,
    )
    xero_sync_type_enum.create(op.get_bind(), checkfirst=True)

    xero_sync_status_enum = postgresql.ENUM(
        "pending",
        "in_progress",
        "completed",
        "failed",
        "cancelled",
        name="xero_sync_status",
        create_type=True,
    )
    xero_sync_status_enum.create(op.get_bind(), checkfirst=True)

    xero_contact_type_enum = postgresql.ENUM(
        "customer",
        "supplier",
        "both",
        name="xero_contact_type",
        create_type=True,
    )
    xero_contact_type_enum.create(op.get_bind(), checkfirst=True)

    xero_invoice_type_enum = postgresql.ENUM(
        "accrec",
        "accpay",
        name="xero_invoice_type",
        create_type=True,
    )
    xero_invoice_type_enum.create(op.get_bind(), checkfirst=True)

    xero_invoice_status_enum = postgresql.ENUM(
        "draft",
        "submitted",
        "authorised",
        "paid",
        "voided",
        "deleted",
        name="xero_invoice_status",
        create_type=True,
    )
    xero_invoice_status_enum.create(op.get_bind(), checkfirst=True)

    xero_bank_transaction_type_enum = postgresql.ENUM(
        "receive",
        "spend",
        "receive_overpayment",
        "spend_overpayment",
        "receive_prepayment",
        "spend_prepayment",
        name="xero_bank_transaction_type",
        create_type=True,
    )
    xero_bank_transaction_type_enum.create(op.get_bind(), checkfirst=True)

    xero_account_class_enum = postgresql.ENUM(
        "asset",
        "equity",
        "expense",
        "liability",
        "revenue",
        name="xero_account_class",
        create_type=True,
    )
    xero_account_class_enum.create(op.get_bind(), checkfirst=True)

    # =========================================================================
    # Create xero_sync_jobs table
    # =========================================================================

    op.create_table(
        "xero_sync_jobs",
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
        sa.Column(
            "sync_type",
            postgresql.ENUM(
                "contacts",
                "invoices",
                "bank_transactions",
                "accounts",
                "full",
                name="xero_sync_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "in_progress",
                "completed",
                "failed",
                "cancelled",
                name="xero_sync_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
            index=True,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_processed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_created", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("progress_details", postgresql.JSONB, nullable=True),
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
    )

    op.create_index(
        "ix_xero_sync_jobs_connection_status",
        "xero_sync_jobs",
        ["connection_id", "status"],
    )

    # =========================================================================
    # Create xero_clients table
    # =========================================================================

    op.create_table(
        "xero_clients",
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
        sa.Column("xero_contact_id", sa.String(50), nullable=False, index=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("contact_number", sa.String(50), nullable=True),
        sa.Column("abn", sa.String(11), nullable=True, comment="Validated 11-digit ABN"),
        sa.Column(
            "contact_type",
            postgresql.ENUM(
                "customer",
                "supplier",
                "both",
                name="xero_contact_type",
                create_type=False,
            ),
            nullable=False,
            server_default="customer",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("addresses", postgresql.JSONB, nullable=True),
        sa.Column("phones", postgresql.JSONB, nullable=True),
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
            "xero_contact_id",
            name="uq_xero_client_connection_contact",
        ),
    )

    op.create_index(
        "ix_xero_clients_tenant_name",
        "xero_clients",
        ["tenant_id", "name"],
    )

    # =========================================================================
    # Create xero_invoices table
    # =========================================================================

    op.create_table(
        "xero_invoices",
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
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_clients.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("xero_invoice_id", sa.String(50), nullable=False, index=True),
        sa.Column(
            "xero_contact_id",
            sa.String(50),
            nullable=True,
            comment="Stored for reference even if client not synced",
        ),
        sa.Column("invoice_number", sa.String(255), nullable=True),
        sa.Column(
            "invoice_type",
            postgresql.ENUM(
                "accrec",
                "accpay",
                name="xero_invoice_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft",
                "submitted",
                "authorised",
                "paid",
                "voided",
                "deleted",
                name="xero_invoice_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("issue_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "subtotal",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "tax_amount",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "total_amount",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column("currency", sa.String(3), nullable=False, server_default="AUD"),
        sa.Column(
            "line_items",
            postgresql.JSONB,
            nullable=True,
            comment="Line items with account_code, tax_type, amounts",
        ),
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
            "xero_invoice_id",
            name="uq_xero_invoice_connection_invoice",
        ),
    )

    op.create_index(
        "ix_xero_invoices_tenant_date",
        "xero_invoices",
        ["tenant_id", "issue_date"],
    )
    op.create_index(
        "ix_xero_invoices_tenant_type",
        "xero_invoices",
        ["tenant_id", "invoice_type"],
    )

    # =========================================================================
    # Create xero_bank_transactions table
    # =========================================================================

    op.create_table(
        "xero_bank_transactions",
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
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_clients.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("xero_transaction_id", sa.String(50), nullable=False, index=True),
        sa.Column("xero_contact_id", sa.String(50), nullable=True),
        sa.Column("xero_bank_account_id", sa.String(50), nullable=True),
        sa.Column(
            "transaction_type",
            postgresql.ENUM(
                "receive",
                "spend",
                "receive_overpayment",
                "spend_overpayment",
                "receive_prepayment",
                "spend_prepayment",
                name="xero_bank_transaction_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column(
            "subtotal",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "tax_amount",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "total_amount",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column("line_items", postgresql.JSONB, nullable=True),
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
            "xero_transaction_id",
            name="uq_xero_transaction_connection_txn",
        ),
    )

    op.create_index(
        "ix_xero_transactions_tenant_date",
        "xero_bank_transactions",
        ["tenant_id", "transaction_date"],
    )

    # =========================================================================
    # Create xero_accounts table
    # =========================================================================

    op.create_table(
        "xero_accounts",
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
        sa.Column("xero_account_id", sa.String(50), nullable=False, index=True),
        sa.Column("account_code", sa.String(10), nullable=True),
        sa.Column("account_name", sa.String(255), nullable=False),
        sa.Column("account_type", sa.String(50), nullable=False),
        sa.Column(
            "account_class",
            postgresql.ENUM(
                "asset",
                "equity",
                "expense",
                "liability",
                "revenue",
                name="xero_account_class",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("default_tax_type", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "reporting_code",
            sa.String(50),
            nullable=True,
            comment="BAS reporting code for mapping",
        ),
        sa.Column(
            "is_bas_relevant",
            sa.Boolean,
            nullable=False,
            server_default="false",
            comment="True if relevant to BAS calculations",
        ),
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
            "xero_account_id",
            name="uq_xero_account_connection_account",
        ),
    )

    op.create_index(
        "ix_xero_accounts_tenant_code",
        "xero_accounts",
        ["tenant_id", "account_code"],
    )

    # =========================================================================
    # Enable RLS on all new tables
    # =========================================================================

    for table_name in [
        "xero_sync_jobs",
        "xero_clients",
        "xero_invoices",
        "xero_bank_transactions",
        "xero_accounts",
    ]:
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

    for table_name in [
        "xero_sync_jobs",
        "xero_clients",
        "xero_invoices",
        "xero_bank_transactions",
        "xero_accounts",
    ]:
        op.execute(
            f"""
            CREATE TRIGGER {table_name}_updated_at
            BEFORE UPDATE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
            """
        )


def downgrade() -> None:
    """Drop sync columns and entity tables."""

    # Drop triggers
    for table_name in [
        "xero_sync_jobs",
        "xero_clients",
        "xero_invoices",
        "xero_bank_transactions",
        "xero_accounts",
    ]:
        op.execute(f"DROP TRIGGER IF EXISTS {table_name}_updated_at ON {table_name}")

    # Drop RLS policies
    for table_name in [
        "xero_sync_jobs",
        "xero_clients",
        "xero_invoices",
        "xero_bank_transactions",
        "xero_accounts",
    ]:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table_name} ON {table_name}")

    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table("xero_accounts")
    op.drop_table("xero_bank_transactions")
    op.drop_table("xero_invoices")
    op.drop_table("xero_clients")
    op.drop_table("xero_sync_jobs")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS xero_account_class")
    op.execute("DROP TYPE IF EXISTS xero_bank_transaction_type")
    op.execute("DROP TYPE IF EXISTS xero_invoice_status")
    op.execute("DROP TYPE IF EXISTS xero_invoice_type")
    op.execute("DROP TYPE IF EXISTS xero_contact_type")
    op.execute("DROP TYPE IF EXISTS xero_sync_status")
    op.execute("DROP TYPE IF EXISTS xero_sync_type")

    # Drop columns from xero_connections
    op.drop_column("xero_connections", "sync_in_progress")
    op.drop_column("xero_connections", "last_full_sync_at")
    op.drop_column("xero_connections", "last_accounts_sync_at")
    op.drop_column("xero_connections", "last_transactions_sync_at")
    op.drop_column("xero_connections", "last_invoices_sync_at")
    op.drop_column("xero_connections", "last_contacts_sync_at")
