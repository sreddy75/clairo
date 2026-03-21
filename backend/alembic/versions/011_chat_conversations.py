"""Add chat conversation tables.

Revision ID: 011_chat_conversations
Revises: 010_knowledge_base
Create Date: 2025-12-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "011_chat_conversations"
down_revision: str | None = "010_knowledge_base"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create chat_conversations table
    op.create_table(
        "chat_conversations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column("title", sa.String(200), nullable=False, server_default="New Conversation"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for chat_conversations
    op.create_index(
        "ix_chat_conversations_user_id",
        "chat_conversations",
        ["user_id"],
    )
    op.create_index(
        "ix_chat_conversations_user_updated",
        "chat_conversations",
        ["user_id", "updated_at"],
    )

    # Create chat_messages table
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["chat_conversations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for chat_messages
    op.create_index(
        "ix_chat_messages_conversation_created",
        "chat_messages",
        ["conversation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_conversation_created", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_conversations_user_updated", table_name="chat_conversations")
    op.drop_index("ix_chat_conversations_user_id", table_name="chat_conversations")
    op.drop_table("chat_conversations")
