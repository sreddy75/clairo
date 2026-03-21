"""add_recipient_email_to_document_requests

Revision ID: 54ae5071be1b
Revises: 033_spec_030
Create Date: 2026-01-03 09:50:59.877522+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers
revision: str = "54ae5071be1b"
down_revision: str | None = "034_pwa_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database to this revision."""
    # Add recipient_email column with a server default for existing rows
    op.add_column("document_requests", sa.Column("recipient_email", sa.String(255), nullable=True))

    # Update existing rows with a placeholder email
    op.execute(
        "UPDATE document_requests SET recipient_email = 'unknown@example.com' WHERE recipient_email IS NULL"
    )

    # Make the column non-nullable
    op.alter_column("document_requests", "recipient_email", nullable=False)


def downgrade() -> None:
    """Downgrade database from this revision."""
    op.drop_column("document_requests", "recipient_email")
