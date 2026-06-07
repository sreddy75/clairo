"""backfill practice_clients from xero_connections

Revision ID: b0169fe3036c
Revises: 9ea16a7e81fb
Create Date: 2026-04-15 12:41:43.269309+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# Revision identifiers
revision: str = "b0169fe3036c"
down_revision: str | None = "9ea16a7e81fb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Backfill practice_clients from existing xero_connections."""
    # Create a PracticeClient for every active/needs_reauth XeroConnection
    # that doesn't already have one
    op.execute(
        sa.text("""
        INSERT INTO practice_clients (id, tenant_id, name, accounting_software, xero_connection_id, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            xc.tenant_id,
            xc.organization_name,
            'xero',
            xc.id,
            xc.created_at,
            now()
        FROM xero_connections xc
        WHERE xc.status IN ('active', 'needs_reauth')
          AND NOT EXISTS (
            SELECT 1 FROM practice_clients pc WHERE pc.xero_connection_id = xc.id
          )
    """)
    )

    # Backfill assigned_user_id from bulk_import_organizations where available
    op.execute(
        sa.text("""
        UPDATE practice_clients pc
        SET assigned_user_id = bio.assigned_user_id
        FROM bulk_import_organizations bio
        JOIN xero_connections xc ON xc.xero_tenant_id = bio.xero_tenant_id
        WHERE xc.id = pc.xero_connection_id
          AND bio.assigned_user_id IS NOT NULL
          AND pc.assigned_user_id IS NULL
    """)
    )


def downgrade() -> None:
    """Remove backfilled practice_clients."""
    op.execute(
        sa.text("""
        DELETE FROM practice_clients
        WHERE xero_connection_id IS NOT NULL
    """)
    )
