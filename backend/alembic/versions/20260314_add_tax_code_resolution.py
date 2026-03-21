"""Add tax code resolution tables.

Spec 046: AI Tax Code Resolution for BAS Preparation.
Creates tax_code_suggestions and tax_code_overrides tables.

Revision ID: 046_tax_code_resolution
Revises: d4a7e1f03c92
Create Date: 2026-03-14
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "046_tax_code_resolution"
down_revision = "d4a7e1f03c92"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums
    source_type_enum = postgresql.ENUM(
        "invoice",
        "bank_transaction",
        "credit_note",
        name="tax_code_suggestion_source_type",
        create_type=False,
    )
    source_type_enum.create(op.get_bind(), checkfirst=True)

    status_enum = postgresql.ENUM(
        "pending",
        "approved",
        "rejected",
        "overridden",
        "dismissed",
        name="tax_code_suggestion_status",
        create_type=False,
    )
    status_enum.create(op.get_bind(), checkfirst=True)

    tier_enum = postgresql.ENUM(
        "account_default",
        "client_history",
        "tenant_history",
        "llm_classification",
        "manual",
        name="confidence_tier",
        create_type=False,
    )
    tier_enum.create(op.get_bind(), checkfirst=True)

    # Create tax_code_suggestions table
    op.create_table(
        "tax_code_suggestions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bas_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_type",
            source_type_enum,
            nullable=False,
        ),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_item_index", sa.Integer(), nullable=False),
        sa.Column("line_item_id", sa.String(50), nullable=True),
        sa.Column("original_tax_type", sa.String(50), nullable=False),
        sa.Column("suggested_tax_type", sa.String(50), nullable=True),
        sa.Column("applied_tax_type", sa.String(50), nullable=True),
        sa.Column("confidence_score", sa.Numeric(3, 2), nullable=True),
        sa.Column("confidence_tier", tier_enum, nullable=True),
        sa.Column("suggestion_basis", sa.Text(), nullable=True),
        sa.Column(
            "status",
            status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "resolved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissal_reason", sa.Text(), nullable=True),
        # Denormalized context
        sa.Column("account_code", sa.String(10), nullable=True),
        sa.Column("account_name", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("line_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("tax_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        # Constraints
        sa.UniqueConstraint(
            "session_id",
            "source_type",
            "source_id",
            "line_item_index",
            name="uq_tax_code_suggestion_session_source_line",
        ),
    )
    op.create_index("ix_tax_code_suggestions_tenant_id", "tax_code_suggestions", ["tenant_id"])
    op.create_index("ix_tax_code_suggestions_session_id", "tax_code_suggestions", ["session_id"])
    op.create_index(
        "ix_tax_code_suggestions_source", "tax_code_suggestions", ["source_type", "source_id"]
    )
    op.create_index("ix_tax_code_suggestions_status", "tax_code_suggestions", ["status"])

    # Create tax_code_overrides table
    op.create_table(
        "tax_code_overrides",
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
        sa.Column(
            "source_type",
            source_type_enum,
            nullable=False,
        ),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_item_index", sa.Integer(), nullable=False),
        sa.Column("original_tax_type", sa.String(50), nullable=False),
        sa.Column("override_tax_type", sa.String(50), nullable=False),
        sa.Column(
            "applied_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_users.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "suggestion_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tax_code_suggestions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("conflict_detected", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("xero_new_tax_type", sa.String(50), nullable=True),
        sa.Column("conflict_resolved_at", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_tax_code_overrides_tenant_id", "tax_code_overrides", ["tenant_id"])
    op.create_index("ix_tax_code_overrides_connection_id", "tax_code_overrides", ["connection_id"])
    # Partial unique index: only one active override per line item
    op.create_index(
        "uq_tax_code_override_active",
        "tax_code_overrides",
        ["connection_id", "source_type", "source_id", "line_item_index"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_tax_code_override_active", table_name="tax_code_overrides")
    op.drop_index("ix_tax_code_overrides_connection_id", table_name="tax_code_overrides")
    op.drop_index("ix_tax_code_overrides_tenant_id", table_name="tax_code_overrides")
    op.drop_table("tax_code_overrides")

    op.drop_index("ix_tax_code_suggestions_status", table_name="tax_code_suggestions")
    op.drop_index("ix_tax_code_suggestions_source", table_name="tax_code_suggestions")
    op.drop_index("ix_tax_code_suggestions_session_id", table_name="tax_code_suggestions")
    op.drop_index("ix_tax_code_suggestions_tenant_id", table_name="tax_code_suggestions")
    op.drop_table("tax_code_suggestions")

    # Drop enums
    sa.Enum(name="confidence_tier").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="tax_code_suggestion_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="tax_code_suggestion_source_type").drop(op.get_bind(), checkfirst=True)
