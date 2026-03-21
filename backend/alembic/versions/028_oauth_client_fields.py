"""Add client-specific OAuth fields to xero_oauth_states.

Revision ID: 028_oauth_client_fields
Revises: 027_xpm_client_auth
Create Date: 2026-01-01

Phase 6b.3: Individual Client Authorization
- Add xpm_client_id to xero_oauth_states for client-specific OAuth
- Add connection_type to xero_oauth_states to indicate practice vs client OAuth
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision: str = "028_oauth_client_fields"
down_revision: str | None = "027_xpm_client_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database to this revision."""
    # Add xpm_client_id column to xero_oauth_states
    op.add_column(
        "xero_oauth_states",
        sa.Column(
            "xpm_client_id",
            sa.UUID(),
            sa.ForeignKey("xpm_clients.id", ondelete="SET NULL"),
            nullable=True,
            comment="XPM client this OAuth is for (null for practice OAuth)",
        ),
    )

    # Add connection_type column to xero_oauth_states
    # Note: xero_connection_type enum was created in migration 027
    op.add_column(
        "xero_oauth_states",
        sa.Column(
            "connection_type",
            postgresql.ENUM(
                "practice",
                "client",
                name="xero_connection_type",
                create_type=False,
            ),
            nullable=False,
            server_default="practice",
            comment="Whether this OAuth is for practice or client Xero org",
        ),
    )

    # Create indexes
    op.create_index(
        "ix_xero_oauth_states_xpm_client_id",
        "xero_oauth_states",
        ["xpm_client_id"],
    )
    op.create_index(
        "ix_xero_oauth_states_connection_type",
        "xero_oauth_states",
        ["connection_type"],
    )


def downgrade() -> None:
    """Downgrade database from this revision."""
    # Drop indexes
    op.drop_index("ix_xero_oauth_states_connection_type", table_name="xero_oauth_states")
    op.drop_index("ix_xero_oauth_states_xpm_client_id", table_name="xero_oauth_states")

    # Drop columns
    op.drop_column("xero_oauth_states", "connection_type")
    op.drop_column("xero_oauth_states", "xpm_client_id")
