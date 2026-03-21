"""fix_progressive_sync_rls_policies

Fix RLS policies on xero_sync_entity_progress, post_sync_tasks, and
xero_webhook_events tables to use missing_ok=true in current_setting().

The original migration (b12cfec71461) used:
    current_setting('app.current_tenant_id')::uuid
which raises an error if the GUC variable is not set.

All other tables in the codebase use:
    NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
which returns NULL (no rows) when the setting is missing.

Revision ID: a3f9c8d21e74
Revises: b12cfec71461
Create Date: 2026-02-21 00:00:00.000000+00:00
"""

from collections.abc import Sequence

from alembic import op

# Revision identifiers
revision: str = "a3f9c8d21e74"
down_revision: str | None = "b12cfec71461"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables that need RLS policy fixes
TABLES = [
    "xero_sync_entity_progress",
    "post_sync_tasks",
    "xero_webhook_events",
]


def upgrade() -> None:
    """Replace RLS policies with missing_ok=true variant."""
    for table in TABLES:
        # Drop the broken policy
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        # Recreate with missing_ok=true and NULLIF for safe UUID cast
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (
                tenant_id = NULLIF(
                    current_setting('app.current_tenant_id', true), ''
                )::uuid
            )
            """
        )


def downgrade() -> None:
    """Revert to the original (strict) RLS policies."""
    for table in TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (
                tenant_id = current_setting('app.current_tenant_id')::uuid
            )
            """
        )
