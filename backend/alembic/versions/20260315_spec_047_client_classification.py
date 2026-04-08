"""Add client transaction classification tables.

Spec 047: Client Transaction Classification.
Two new tables for accountant-initiated client classification requests
and per-transaction client classifications with audit trail.

Revision ID: 047_client_classification
Revises: 046_enum_to_varchar
Create Date: 2026-03-15
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "047_client_classification"
down_revision = "046_enum_to_varchar"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- classification_requests --
    op.create_table(
        "classification_requests",
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
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bas_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "invitation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("portal_invitations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "requested_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("client_email", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("transaction_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("classified_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("session_id", name="uq_classification_request_session"),
    )
    op.create_index(
        "ix_classification_request_connection_status",
        "classification_requests",
        ["connection_id", "status"],
    )

    # -- client_classifications --
    op.create_table(
        "client_classifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("classification_requests.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # Transaction reference
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_item_index", sa.Integer, nullable=False),
        # Denormalized transaction context
        sa.Column("transaction_date", sa.Date, nullable=True),
        sa.Column("line_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("account_code", sa.String(10), nullable=True),
        # Client input
        sa.Column("client_category", sa.String(50), nullable=True),
        sa.Column("client_description", sa.Text, nullable=True),
        sa.Column("client_is_personal", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("client_needs_help", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "classified_by_session",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("portal_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # AI mapping
        sa.Column("ai_suggested_tax_type", sa.String(50), nullable=True),
        sa.Column("ai_confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("ai_mapped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "suggestion_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tax_code_suggestions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Accountant review
        sa.Column("accountant_action", sa.String(20), nullable=True),
        sa.Column(
            "accountant_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("accountant_tax_type", sa.String(50), nullable=True),
        sa.Column("accountant_reason", sa.Text, nullable=True),
        sa.Column("accountant_acted_at", sa.DateTime(timezone=True), nullable=True),
        # Receipt / invoice
        sa.Column("receipt_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("receipt_flag_source", sa.String(20), nullable=True),
        sa.Column("receipt_flag_reason", sa.String(255), nullable=True),
        sa.Column(
            "receipt_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("portal_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "request_id",
            "source_type",
            "source_id",
            "line_item_index",
            name="uq_client_classification_request_source_line",
        ),
    )


def downgrade() -> None:
    op.drop_table("client_classifications")
    op.drop_index(
        "ix_classification_request_connection_status", table_name="classification_requests"
    )
    op.drop_table("classification_requests")
