"""Spec 025 - Fixed Assets & Enhanced Analysis

Create tables for:
- xero_asset_types
- xero_assets
- xero_purchase_orders
- xero_repeating_invoices
- xero_tracking_categories
- xero_tracking_options
- xero_quotes

Revision ID: 032_spec_025
Revises: 031_xero_transactions
Create Date: 2026-01-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "032_spec_025"
down_revision: str | None = "031_xero_transactions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create xero_asset_types table
    op.create_table(
        "xero_asset_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
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
        sa.Column("xero_asset_type_id", sa.String(50), nullable=False),
        sa.Column("asset_type_name", sa.String(255), nullable=False),
        sa.Column("book_depreciation_method", sa.String(30), nullable=True),
        sa.Column("book_depreciation_rate", sa.Numeric(10, 4), nullable=True),
        sa.Column("book_effective_life_years", sa.Integer, nullable=True),
        sa.Column("book_averaging_method", sa.String(30), nullable=True),
        sa.Column("tax_depreciation_method", sa.String(30), nullable=True),
        sa.Column("tax_depreciation_rate", sa.Numeric(10, 4), nullable=True),
        sa.Column("tax_effective_life_years", sa.Integer, nullable=True),
        sa.Column("tax_averaging_method", sa.String(30), nullable=True),
        sa.Column("locked_for_accounting_period", sa.Date, nullable=True),
        sa.Column("asset_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "connection_id", "xero_asset_type_id", name="uq_xero_asset_types_connection_xero_id"
        ),
    )
    op.create_index(
        "ix_xero_asset_types_tenant_name", "xero_asset_types", ["tenant_id", "asset_type_name"]
    )
    op.create_index(
        "ix_xero_asset_types_xero_asset_type_id", "xero_asset_types", ["xero_asset_type_id"]
    )

    # Create xero_assets table
    op.create_table(
        "xero_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
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
        sa.Column("xero_asset_id", sa.String(50), nullable=False),
        sa.Column(
            "asset_type_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_asset_types.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("asset_name", sa.String(255), nullable=False),
        sa.Column("asset_number", sa.String(50), nullable=True),
        sa.Column("purchase_date", sa.Date, nullable=False),
        sa.Column("purchase_price", sa.Numeric(15, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("book_value", sa.Numeric(15, 2), nullable=False),
        sa.Column("serial_number", sa.String(100), nullable=True),
        sa.Column("warranty_expiry", sa.Date, nullable=True),
        # Book depreciation
        sa.Column("book_depreciation_method", sa.String(30), nullable=True),
        sa.Column("book_depreciation_rate", sa.Numeric(10, 4), nullable=True),
        sa.Column("book_effective_life_years", sa.Integer, nullable=True),
        sa.Column("book_current_capital_gain", sa.Numeric(15, 2), nullable=True),
        sa.Column("book_current_gain_loss", sa.Numeric(15, 2), nullable=True),
        sa.Column("book_depreciation_start_date", sa.Date, nullable=True),
        sa.Column("book_cost_limit", sa.Numeric(15, 2), nullable=True),
        sa.Column("book_residual_value", sa.Numeric(15, 2), nullable=True),
        sa.Column("book_prior_accum_depreciation", sa.Numeric(15, 2), nullable=True),
        sa.Column("book_current_accum_depreciation", sa.Numeric(15, 2), nullable=True),
        # Tax depreciation
        sa.Column("tax_depreciation_method", sa.String(30), nullable=True),
        sa.Column("tax_depreciation_rate", sa.Numeric(10, 4), nullable=True),
        sa.Column("tax_effective_life_years", sa.Integer, nullable=True),
        sa.Column("tax_current_capital_gain", sa.Numeric(15, 2), nullable=True),
        sa.Column("tax_current_gain_loss", sa.Numeric(15, 2), nullable=True),
        sa.Column("tax_depreciation_start_date", sa.Date, nullable=True),
        sa.Column("tax_cost_limit", sa.Numeric(15, 2), nullable=True),
        sa.Column("tax_residual_value", sa.Numeric(15, 2), nullable=True),
        sa.Column("tax_prior_accum_depreciation", sa.Numeric(15, 2), nullable=True),
        sa.Column("tax_current_accum_depreciation", sa.Numeric(15, 2), nullable=True),
        # Disposal
        sa.Column("disposal_date", sa.Date, nullable=True),
        sa.Column("disposal_price", sa.Numeric(15, 2), nullable=True),
        # Is billed flag
        sa.Column("is_billed", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "connection_id", "xero_asset_id", name="uq_xero_assets_connection_xero_id"
        ),
    )
    op.create_index("ix_xero_assets_xero_asset_id", "xero_assets", ["xero_asset_id"])
    op.create_index("ix_xero_assets_tenant_status", "xero_assets", ["tenant_id", "status"])
    op.create_index(
        "ix_xero_assets_tenant_purchase_date", "xero_assets", ["tenant_id", "purchase_date"]
    )
    op.create_index("ix_xero_assets_asset_type_id", "xero_assets", ["asset_type_id"])

    # Create xero_purchase_orders table
    op.create_table(
        "xero_purchase_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
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
        sa.Column("xero_purchase_order_id", sa.String(50), nullable=False),
        sa.Column("purchase_order_number", sa.String(50), nullable=True),
        sa.Column("contact_id", sa.String(50), nullable=True),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("delivery_date", sa.Date, nullable=True),
        sa.Column("delivery_address", sa.Text, nullable=True),
        sa.Column("attention_to", sa.String(255), nullable=True),
        sa.Column("telephone", sa.String(50), nullable=True),
        sa.Column("delivery_instructions", sa.Text, nullable=True),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("currency_code", sa.String(3), default="AUD"),
        sa.Column("currency_rate", sa.Numeric(15, 6), default=1.0),
        sa.Column("sub_total", sa.Numeric(15, 2), nullable=False),
        sa.Column("total_tax", sa.Numeric(15, 2), nullable=False),
        sa.Column("total", sa.Numeric(15, 2), nullable=False),
        sa.Column("line_items", postgresql.JSONB, default=[]),
        sa.Column("sent_to_contact", sa.Boolean, default=False),
        sa.Column("branding_theme_id", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "connection_id",
            "xero_purchase_order_id",
            name="uq_xero_purchase_orders_connection_xero_id",
        ),
    )
    op.create_index(
        "ix_xero_purchase_orders_xero_po_id", "xero_purchase_orders", ["xero_purchase_order_id"]
    )
    op.create_index(
        "ix_xero_purchase_orders_tenant_status", "xero_purchase_orders", ["tenant_id", "status"]
    )
    op.create_index(
        "ix_xero_purchase_orders_tenant_date", "xero_purchase_orders", ["tenant_id", "date"]
    )
    op.create_index(
        "ix_xero_purchase_orders_po_number", "xero_purchase_orders", ["purchase_order_number"]
    )

    # Create xero_repeating_invoices table
    op.create_table(
        "xero_repeating_invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
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
        sa.Column("xero_repeating_invoice_id", sa.String(50), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),  # ACCREC or ACCPAY
        sa.Column("contact_id", sa.String(50), nullable=True),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("schedule_unit", sa.String(20), nullable=False),
        sa.Column("schedule_period", sa.Integer, nullable=False),
        sa.Column("schedule_due_date", sa.Integer, nullable=True),
        sa.Column("schedule_due_date_type", sa.String(30), nullable=True),
        sa.Column("schedule_start_date", sa.Date, nullable=True),
        sa.Column("schedule_next_scheduled_date", sa.Date, nullable=True),
        sa.Column("schedule_end_date", sa.Date, nullable=True),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("branding_theme_id", sa.String(50), nullable=True),
        sa.Column("currency_code", sa.String(3), default="AUD"),
        sa.Column("sub_total", sa.Numeric(15, 2), nullable=False),
        sa.Column("total_tax", sa.Numeric(15, 2), nullable=False),
        sa.Column("total", sa.Numeric(15, 2), nullable=False),
        sa.Column("line_items", postgresql.JSONB, default=[]),
        sa.Column("has_attachments", sa.Boolean, default=False),
        sa.Column("approved_for_sending", sa.Boolean, default=False),
        sa.Column("send_copy", sa.Boolean, default=False),
        sa.Column("mark_as_sent", sa.Boolean, default=False),
        sa.Column("include_pdf", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "connection_id",
            "xero_repeating_invoice_id",
            name="uq_xero_repeating_invoices_connection_xero_id",
        ),
    )
    op.create_index(
        "ix_xero_repeating_invoices_xero_ri_id",
        "xero_repeating_invoices",
        ["xero_repeating_invoice_id"],
    )
    op.create_index(
        "ix_xero_repeating_invoices_tenant_status",
        "xero_repeating_invoices",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_xero_repeating_invoices_tenant_type", "xero_repeating_invoices", ["tenant_id", "type"]
    )
    op.create_index(
        "ix_xero_repeating_invoices_next_date",
        "xero_repeating_invoices",
        ["schedule_next_scheduled_date"],
    )

    # Create xero_tracking_categories table
    op.create_table(
        "xero_tracking_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
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
        sa.Column("xero_tracking_category_id", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "connection_id",
            "xero_tracking_category_id",
            name="uq_xero_tracking_categories_connection_xero_id",
        ),
    )
    op.create_index(
        "ix_xero_tracking_categories_xero_tc_id",
        "xero_tracking_categories",
        ["xero_tracking_category_id"],
    )
    op.create_index(
        "ix_xero_tracking_categories_tenant_name", "xero_tracking_categories", ["tenant_id", "name"]
    )

    # Create xero_tracking_options table
    op.create_table(
        "xero_tracking_options",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "tracking_category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_tracking_categories.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("xero_tracking_option_id", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "tracking_category_id",
            "xero_tracking_option_id",
            name="uq_xero_tracking_options_category_xero_id",
        ),
    )
    op.create_index(
        "ix_xero_tracking_options_xero_to_id", "xero_tracking_options", ["xero_tracking_option_id"]
    )
    op.create_index(
        "ix_xero_tracking_options_tenant_name", "xero_tracking_options", ["tenant_id", "name"]
    )

    # Create xero_quotes table
    op.create_table(
        "xero_quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
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
        sa.Column("xero_quote_id", sa.String(50), nullable=False),
        sa.Column("quote_number", sa.String(50), nullable=True),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("contact_id", sa.String(50), nullable=True),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("expiry_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("currency_code", sa.String(3), default="AUD"),
        sa.Column("currency_rate", sa.Numeric(15, 6), default=1.0),
        sa.Column("sub_total", sa.Numeric(15, 2), nullable=False),
        sa.Column("total_tax", sa.Numeric(15, 2), nullable=False),
        sa.Column("total", sa.Numeric(15, 2), nullable=False),
        sa.Column("total_discount", sa.Numeric(15, 2), nullable=True),
        sa.Column("line_items", postgresql.JSONB, default=[]),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("terms", sa.Text, nullable=True),
        sa.Column("branding_theme_id", sa.String(50), nullable=True),
        sa.Column("line_amount_types", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "connection_id", "xero_quote_id", name="uq_xero_quotes_connection_xero_id"
        ),
    )
    op.create_index("ix_xero_quotes_xero_quote_id", "xero_quotes", ["xero_quote_id"])
    op.create_index("ix_xero_quotes_tenant_status", "xero_quotes", ["tenant_id", "status"])
    op.create_index("ix_xero_quotes_tenant_date", "xero_quotes", ["tenant_id", "date"])
    op.create_index("ix_xero_quotes_tenant_expiry", "xero_quotes", ["tenant_id", "expiry_date"])
    op.create_index("ix_xero_quotes_quote_number", "xero_quotes", ["quote_number"])


def downgrade() -> None:
    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table("xero_quotes")
    op.drop_table("xero_tracking_options")
    op.drop_table("xero_tracking_categories")
    op.drop_table("xero_repeating_invoices")
    op.drop_table("xero_purchase_orders")
    op.drop_table("xero_assets")
    op.drop_table("xero_asset_types")
