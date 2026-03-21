"""add_unknown_to_journal_source_type

Revision ID: fix_journal_source_enum
Revises: 035_bulk_import_orgs
Create Date: 2026-02-09

Adds 'unknown' value to xero_journal_source_type enum so unrecognized
journal source types from the Xero API can be stored as a fallback.
"""

from collections.abc import Sequence

from alembic import op


# Revision identifiers
revision: str = "fix_journal_source_enum"
down_revision: str | None = "035_bulk_import_orgs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add 'unknown' value to xero_journal_source_type enum."""
    op.execute("ALTER TYPE xero_journal_source_type ADD VALUE IF NOT EXISTS 'unknown'")


def downgrade() -> None:
    """Cannot remove enum values in PostgreSQL; no-op."""
    pass
