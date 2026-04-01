"""Add agent_transaction_notes table.

Spec 049: Xero Tax Code Write-Back.
Per-transaction notes added by tax agents when creating or sending back
classification requests.

Revision ID: 049_add_agent_transaction_notes
Revises: 049_cls_multiround
Create Date: 2026-03-31
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "049_add_agent_transaction_notes"
down_revision = "049_cls_multiround"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_transaction_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("classification_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_item_index", sa.Integer, nullable=False),
        sa.Column("note_text", sa.Text, nullable=False),
        sa.Column(
            "is_send_back_comment",
            sa.Boolean,
            nullable=False,
            server_default="false",
            comment="False = initial context note; True = guidance on send-back",
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
    )
    op.create_index(
        "ix_agent_transaction_notes_tenant_request",
        "agent_transaction_notes",
        ["tenant_id", "request_id"],
    )
    op.create_index(
        "ix_agent_transaction_notes_request_source",
        "agent_transaction_notes",
        ["request_id", "source_type", "source_id", "line_item_index"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_transaction_notes_request_source", table_name="agent_transaction_notes")
    op.drop_index("ix_agent_transaction_notes_tenant_request", table_name="agent_transaction_notes")
    op.drop_table("agent_transaction_notes")
