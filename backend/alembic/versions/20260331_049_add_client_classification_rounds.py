"""Add client_classification_rounds table.

Spec 049: Xero Tax Code Write-Back.
Tracks the per-transaction conversation thread across multiple rounds of send-back
classification requests.

Revision ID: 049_cls_rounds
Revises: 049_add_agent_transaction_notes
Create Date: 2026-03-31
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "049_cls_rounds"
down_revision = "049_add_agent_transaction_notes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_classification_rounds",
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
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_item_index", sa.Integer, nullable=False),
        sa.Column("round_number", sa.Integer, nullable=False),
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("classification_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_comment", sa.Text, nullable=True),
        sa.Column("client_response_category", sa.String(100), nullable=True),
        sa.Column("client_response_description", sa.Text, nullable=True),
        sa.Column(
            "client_needs_help",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
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
        "ix_client_classification_rounds_tenant_session_source",
        "client_classification_rounds",
        ["tenant_id", "session_id", "source_type", "source_id", "line_item_index"],
    )
    op.create_index(
        "ix_client_classification_rounds_tenant_request",
        "client_classification_rounds",
        ["tenant_id", "request_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_client_classification_rounds_tenant_request",
        table_name="client_classification_rounds",
    )
    op.drop_index(
        "ix_client_classification_rounds_tenant_session_source",
        table_name="client_classification_rounds",
    )
    op.drop_table("client_classification_rounds")
