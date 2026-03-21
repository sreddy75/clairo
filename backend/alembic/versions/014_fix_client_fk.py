"""Fix chat_conversations client_id FK to reference xero_connections.

Revision ID: 014_fix_client_fk
Revises: 013_client_chat_context
Create Date: 2025-12-30

The client_id should reference XeroConnection (client businesses like "KR8 IT")
not XeroClient (contacts/vendors within a business).
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "014_fix_client_fk"
down_revision = "013_client_chat_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old FK constraint to xero_clients
    op.drop_constraint(
        "fk_chat_conversations_client_id",
        "chat_conversations",
        type_="foreignkey",
    )

    # Create new FK constraint to xero_connections
    op.create_foreign_key(
        "fk_chat_conversations_client_id",
        "chat_conversations",
        "xero_connections",
        ["client_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Drop FK to xero_connections
    op.drop_constraint(
        "fk_chat_conversations_client_id",
        "chat_conversations",
        type_="foreignkey",
    )

    # Restore FK to xero_clients
    op.create_foreign_key(
        "fk_chat_conversations_client_id",
        "chat_conversations",
        "xero_clients",
        ["client_id"],
        ["id"],
        ondelete="SET NULL",
    )
