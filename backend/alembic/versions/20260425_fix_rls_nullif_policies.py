"""Fix RLS policies to use NULLIF for safe empty-string handling

Several tables have RLS policies using:
    current_setting('app.current_tenant_id', true)::uuid
This fails with an error when app.current_tenant_id is '' (empty string).
The correct pattern is:
    NULLIF(current_setting('app.current_tenant_id', true), '')::uuid

This migration drops and recreates the broken policies on all affected tables.

Revision ID: 062_fix_rls_nullif
Revises: 062_bas_gst_basis
Create Date: 2026-04-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "062_fix_rls_nullif"
down_revision: str | None = "062_bas_gst_basis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables whose policies were created with the broken pattern (no NULLIF)
AFFECTED_TABLES = [
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
    "document_request_templates",
    # From 005_quality_scoring.py
    "quality_scores",
    "quality_issues",
    # From 008_bas_audit_log.py
    "bas_audit_log",
    # From 006_bas_workflow.py (bas_periods uses NULLIF already, but sessions/calculations may not)
    "bas_sessions",
    "bas_calculations",
    "bas_adjustments",
    # From 016_agent_audit_tables.py
    "agent_queries",
    "agent_escalations",
]

SAFE_POLICY = """
CREATE POLICY {table}_tenant_isolation ON {table}
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
"""

BROKEN_POLICY = """
CREATE POLICY {table}_tenant_isolation ON {table}
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
"""


def upgrade() -> None:
    """Replace broken RLS policies with safe NULLIF versions."""
    for table in AFFECTED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(SAFE_POLICY.format(table=table))


def downgrade() -> None:
    """Restore original (broken) RLS policies."""
    for table in AFFECTED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(BROKEN_POLICY.format(table=table))
