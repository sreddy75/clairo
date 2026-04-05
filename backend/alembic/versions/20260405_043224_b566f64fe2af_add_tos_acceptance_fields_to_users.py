"""Add ToS acceptance fields to users

Revision ID: b566f64fe2af
Revises: 4e34cb2ed1bb
Create Date: 2026-04-05 04:32:24.143294+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import INET

# Revision identifiers
revision: str = 'b566f64fe2af'
down_revision: str | None = '4e34cb2ed1bb'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add ToS acceptance tracking columns to users table."""
    op.add_column('users', sa.Column(
        'tos_accepted_at',
        sa.DateTime(timezone=True),
        nullable=True,
        comment='When the user accepted the Terms of Service',
    ))
    op.add_column('users', sa.Column(
        'tos_version_accepted',
        sa.String(20),
        nullable=True,
        comment='ToS version string accepted (e.g. 1.0)',
    ))
    op.add_column('users', sa.Column(
        'tos_accepted_ip',
        INET,
        nullable=True,
        comment='IP address at time of ToS acceptance',
    ))


def downgrade() -> None:
    """Remove ToS acceptance tracking columns from users table."""
    op.drop_column('users', 'tos_accepted_ip')
    op.drop_column('users', 'tos_version_accepted')
    op.drop_column('users', 'tos_accepted_at')
