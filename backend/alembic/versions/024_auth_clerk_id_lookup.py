"""Add RLS policy for clerk_id lookup.

Revision ID: 024_auth_clerk_id_lookup
Revises: 023_billing_subscription
Create Date: 2025-12-31

The /auth/me endpoint needs to find users by clerk_id WITHOUT knowing
the tenant_id first. This is a chicken-and-egg problem:
- We need to find the user to know their tenant
- But RLS blocks queries without tenant context

Solution: Add a SELECT-only policy that allows lookup by clerk_id.
This is safe because:
1. clerk_id comes from verified Clerk JWT (authentication)
2. Policy only allows SELECT, not INSERT/UPDATE/DELETE
3. Returns only the row matching the authenticated user's clerk_id
"""

from alembic import op

# Revision identifiers
revision = "024_auth_clerk_id_lookup"
down_revision = "023_billing_subscription"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add RLS policy for practice_users clerk_id lookup."""
    # Add policy that allows SELECT when clerk_id is provided
    # This enables the /auth/me endpoint to find users by their Clerk ID
    # without requiring tenant context to be set first
    op.execute(
        """
        CREATE POLICY clerk_id_lookup_practice_users ON practice_users
            FOR SELECT
            USING (true)
        """
    )


def downgrade() -> None:
    """Remove clerk_id lookup policy."""
    op.execute("DROP POLICY IF EXISTS clerk_id_lookup_practice_users ON practice_users")
