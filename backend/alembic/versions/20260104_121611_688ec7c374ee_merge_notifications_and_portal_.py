"""merge_notifications_and_portal_migrations

Revision ID: 688ec7c374ee
Revises: 035_notifications, a1b2c3d4e5f6
Create Date: 2026-01-04 12:16:11.784066+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# Revision identifiers
revision: str = "688ec7c374ee"
down_revision: str | None = ("035_notifications", "a1b2c3d4e5f6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database to this revision."""
    pass


def downgrade() -> None:
    """Downgrade database from this revision."""
    pass
