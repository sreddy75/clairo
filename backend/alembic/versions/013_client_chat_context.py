"""Add client context fields to chat tables.

Revision ID: 013_client_chat_context
Revises: 012_client_ai_aggregations
Create Date: 2025-12-30

Adds:
- chat_conversations.client_id: Optional FK to xero_clients
- chat_messages.metadata: JSONB for client context metadata
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "013_client_chat_context"
down_revision = "012_client_ai_aggregations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add client_id to chat_conversations
    op.add_column(
        "chat_conversations",
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    # Add FK constraint
    op.create_foreign_key(
        "fk_chat_conversations_client_id",
        "chat_conversations",
        "xero_clients",
        ["client_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add index for client lookups
    op.create_index(
        "ix_chat_conversations_client_id",
        "chat_conversations",
        ["client_id"],
    )

    # Add metadata column to chat_messages
    op.add_column(
        "chat_messages",
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # Remove metadata from chat_messages
    op.drop_column("chat_messages", "metadata")

    # Remove client_id from chat_conversations
    op.drop_index("ix_chat_conversations_client_id", "chat_conversations")
    op.drop_constraint(
        "fk_chat_conversations_client_id",
        "chat_conversations",
        type_="foreignkey",
    )
    op.drop_column("chat_conversations", "client_id")
