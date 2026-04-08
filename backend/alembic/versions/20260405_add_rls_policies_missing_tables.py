"""Add RLS policies to 16 tenant-scoped tables

Tables created after Feb 2026 were missing Row-Level Security policies.
This migration adds the standard tenant isolation policy to all of them.

Revision ID: a054rls0001
Revises: b566f64fe2af
Create Date: 2026-04-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a054rls0001"
down_revision: str | None = "b566f64fe2af"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Standard tables: tenant_id NOT NULL
STANDARD_TABLES = [
    "portal_invitations",
    "portal_sessions",
    "bulk_requests",
    "document_requests",
    "portal_documents",
    "tax_code_suggestions",
    "tax_code_overrides",
    "classification_requests",
    "client_classifications",
    "feedback_submissions",
    "tax_plans",
    "tax_scenarios",
    "tax_plan_messages",
    "tax_plan_analyses",
    "implementation_items",
]

# RLS policy pattern with FORCE (applies even to table owners/superusers)
ENABLE_RLS = "ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"
FORCE_RLS = "ALTER TABLE {table} FORCE ROW LEVEL SECURITY"
CREATE_POLICY = """
CREATE POLICY {table}_tenant_isolation ON {table}
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
"""
DROP_POLICY = "DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}"
NO_FORCE_RLS = "ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"
DISABLE_RLS = "ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"


def upgrade() -> None:
    """Add RLS policies to all tenant-scoped tables missing them."""
    # Standard tables
    for table in STANDARD_TABLES:
        op.execute(ENABLE_RLS.format(table=table))
        op.execute(FORCE_RLS.format(table=table))
        op.execute(CREATE_POLICY.format(table=table))

    # Special case: document_request_templates has nullable tenant_id
    # Tenant-owned templates are isolated; system templates (tenant_id IS NULL) visible to all
    op.execute(ENABLE_RLS.format(table="document_request_templates"))
    op.execute(FORCE_RLS.format(table="document_request_templates"))
    op.execute(CREATE_POLICY.format(table="document_request_templates"))
    op.execute("""
        CREATE POLICY document_request_templates_system_read ON document_request_templates
            FOR SELECT
            USING (tenant_id IS NULL)
    """)


def downgrade() -> None:
    """Remove RLS policies from all tables."""
    for table in STANDARD_TABLES:
        op.execute(DROP_POLICY.format(table=table))
        op.execute(NO_FORCE_RLS.format(table=table))
        op.execute(DISABLE_RLS.format(table=table))

    op.execute(
        "DROP POLICY IF EXISTS document_request_templates_system_read ON document_request_templates"
    )
    op.execute(DROP_POLICY.format(table="document_request_templates"))
    op.execute(NO_FORCE_RLS.format(table="document_request_templates"))
    op.execute(DISABLE_RLS.format(table="document_request_templates"))
