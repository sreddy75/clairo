"""add_primary_contact_email_to_xero_connections

Revision ID: a1b2c3d4e5f6
Revises: 54ae5071be1b
Create Date: 2026-01-03 10:12:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "54ae5071be1b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add primary_contact_email column to xero_connections."""
    op.add_column(
        "xero_connections",
        sa.Column(
            "primary_contact_email",
            sa.String(255),
            nullable=True,
            comment="Primary contact email for document requests and notifications",
        ),
    )


def downgrade() -> None:
    """Remove primary_contact_email column from xero_connections."""
    op.drop_column("xero_connections", "primary_contact_email")
