"""Auth and multi-tenancy tables with RLS.

Revision ID: 001_auth_multitenancy
Revises:
Create Date: 2025-12-28

This migration creates the foundational authentication and multi-tenancy tables:
- tenants: Accounting practices (organizations)
- users: Base identity for all user types
- practice_users: Profile for accountants/staff (Clerk auth)
- invitations: User invitations
- audit_logs: Immutable audit trail

RLS (Row-Level Security):
- Enabled on practice_users and invitations tables
- Uses PostgreSQL session variable app.current_tenant_id
- The users table is NOT tenant-scoped (shared identity)

Audit log rules:
- UPDATE and DELETE are blocked via PostgreSQL rules
- Provides tamper-evident logging
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_auth_multitenancy"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create auth and multi-tenancy tables with RLS policies."""

    # =========================================================================
    # Create PostgreSQL Enums
    # =========================================================================

    user_type_enum = postgresql.ENUM(
        "practice_user",
        "business_owner",
        name="user_type",
        create_type=True,
    )
    user_type_enum.create(op.get_bind(), checkfirst=True)

    user_role_enum = postgresql.ENUM(
        "admin",
        "accountant",
        "staff",
        name="user_role",
        create_type=True,
    )
    user_role_enum.create(op.get_bind(), checkfirst=True)

    subscription_status_enum = postgresql.ENUM(
        "trial",
        "active",
        "suspended",
        "cancelled",
        name="subscription_status",
        create_type=True,
    )
    subscription_status_enum.create(op.get_bind(), checkfirst=True)

    # =========================================================================
    # Create tenants table
    # =========================================================================

    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(50), unique=True, nullable=False),
        sa.Column(
            "settings",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "subscription_status",
            postgresql.ENUM(
                "trial",
                "active",
                "suspended",
                "cancelled",
                name="subscription_status",
                create_type=False,
            ),
            nullable=False,
            server_default="trial",
        ),
        sa.Column("mfa_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"])
    op.create_index("ix_tenants_subscription_status", "tenants", ["subscription_status"])
    op.create_index("ix_tenants_is_active", "tenants", ["is_active"])

    # =========================================================================
    # Create users table (base identity - NOT tenant-scoped)
    # =========================================================================

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column(
            "user_type",
            postgresql.ENUM(
                "practice_user",
                "business_owner",
                name="user_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_user_type", "users", ["user_type"])
    op.create_index("ix_users_is_active", "users", ["is_active"])

    # =========================================================================
    # Create practice_users table (profile - tenant-scoped with RLS)
    # =========================================================================

    op.create_table(
        "practice_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("clerk_id", sa.String(100), unique=True, nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(
                "admin",
                "accountant",
                "staff",
                name="user_role",
                create_type=False,
            ),
            nullable=False,
            server_default="accountant",
        ),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_practice_users_user_id", "practice_users", ["user_id"])
    op.create_index("ix_practice_users_tenant_id", "practice_users", ["tenant_id"])
    op.create_index("ix_practice_users_clerk_id", "practice_users", ["clerk_id"])
    op.create_index("ix_practice_users_role", "practice_users", ["role"])

    # =========================================================================
    # Create invitations table (tenant-scoped with RLS)
    # =========================================================================

    op.create_table(
        "invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "invited_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_users.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(
                "admin",
                "accountant",
                "staff",
                name="user_role",
                create_type=False,
            ),
            nullable=False,
            server_default="accountant",
        ),
        sa.Column("token", sa.String(64), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "accepted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_invitations_tenant_id", "invitations", ["tenant_id"])
    op.create_index("ix_invitations_email", "invitations", ["email"])
    op.create_index("ix_invitations_token", "invitations", ["token"])
    op.create_index("ix_invitations_expires_at", "invitations", ["expires_at"])

    # =========================================================================
    # Create audit_logs table (immutable, tenant-scoped for queries)
    # =========================================================================

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), unique=True, nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("actor_type", sa.String(50), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_email", sa.String(255), nullable=True),
        sa.Column("actor_ip", postgresql.INET, nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_category", sa.String(50), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("old_values", postgresql.JSONB, nullable=True),
        sa.Column("new_values", postgresql.JSONB, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("previous_checksum", sa.String(64), nullable=True),
    )
    op.create_index("ix_audit_logs_occurred_at", "audit_logs", ["occurred_at"])
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_event_category", "audit_logs", ["event_category"])
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])
    op.create_index("ix_audit_logs_resource_id", "audit_logs", ["resource_id"])

    # =========================================================================
    # Enable Row-Level Security
    # =========================================================================

    # Enable RLS on practice_users table
    op.execute("ALTER TABLE practice_users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE practice_users FORCE ROW LEVEL SECURITY")

    # Enable RLS on invitations table
    op.execute("ALTER TABLE invitations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invitations FORCE ROW LEVEL SECURITY")

    # =========================================================================
    # Create RLS Policies
    # =========================================================================

    # Policy for practice_users: tenant isolation
    op.execute(
        """
        CREATE POLICY tenant_isolation_practice_users ON practice_users
            FOR ALL
            USING (
                tenant_id = NULLIF(
                    current_setting('app.current_tenant_id', true),
                    ''
                )::uuid
            )
        """
    )

    # Policy for invitations: tenant isolation
    op.execute(
        """
        CREATE POLICY tenant_isolation_invitations ON invitations
            FOR ALL
            USING (
                tenant_id = NULLIF(
                    current_setting('app.current_tenant_id', true),
                    ''
                )::uuid
            )
        """
    )

    # Policy for invitations: public read by valid token
    # This allows unauthenticated users to look up invitations by token
    op.execute(
        """
        CREATE POLICY public_invitation_by_token ON invitations
            FOR SELECT
            USING (
                token IS NOT NULL
                AND accepted_at IS NULL
                AND revoked_at IS NULL
                AND expires_at > NOW()
            )
        """
    )

    # =========================================================================
    # Audit Log Immutability Rules
    # =========================================================================

    # Prevent updates to audit_logs
    op.execute(
        """
        CREATE RULE audit_no_update AS ON UPDATE TO audit_logs
            DO INSTEAD NOTHING
        """
    )

    # Prevent deletes from audit_logs
    op.execute(
        """
        CREATE RULE audit_no_delete AS ON DELETE TO audit_logs
            DO INSTEAD NOTHING
        """
    )


def downgrade() -> None:
    """Remove auth and multi-tenancy tables and RLS policies."""

    # =========================================================================
    # Remove Audit Log Rules
    # =========================================================================

    op.execute("DROP RULE IF EXISTS audit_no_delete ON audit_logs")
    op.execute("DROP RULE IF EXISTS audit_no_update ON audit_logs")

    # =========================================================================
    # Remove RLS Policies
    # =========================================================================

    op.execute("DROP POLICY IF EXISTS public_invitation_by_token ON invitations")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_invitations ON invitations")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_practice_users ON practice_users")

    # =========================================================================
    # Disable RLS
    # =========================================================================

    op.execute("ALTER TABLE invitations DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE practice_users DISABLE ROW LEVEL SECURITY")

    # =========================================================================
    # Drop Tables
    # =========================================================================

    op.drop_table("audit_logs")
    op.drop_table("invitations")
    op.drop_table("practice_users")
    op.drop_table("users")
    op.drop_table("tenants")

    # =========================================================================
    # Drop Enums
    # =========================================================================

    op.execute("DROP TYPE IF EXISTS subscription_status")
    op.execute("DROP TYPE IF EXISTS user_role")
    op.execute("DROP TYPE IF EXISTS user_type")
