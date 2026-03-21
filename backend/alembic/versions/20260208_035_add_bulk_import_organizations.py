"""add_bulk_import_organizations

Revision ID: 035_bulk_import_orgs
Revises: 688ec7c374ee
Create Date: 2026-02-08

Adds:
- is_bulk_import column to xero_oauth_states table
- bulk_import_organizations table for per-org tracking in bulk imports
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# Revision identifiers
revision: str = "035_bulk_import_orgs"
down_revision: str | None = "688ec7c374ee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database to this revision."""
    # Add is_bulk_import column to xero_oauth_states
    op.add_column(
        "xero_oauth_states",
        sa.Column(
            "is_bulk_import",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="True for bulk import flows (multi-org OAuth)",
        ),
    )

    # Create bulk_import_organizations table
    op.create_table(
        "bulk_import_organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            comment="Foreign key to tenant (RLS enforced)",
        ),
        sa.Column(
            "bulk_import_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bulk_import_jobs.id", ondelete="CASCADE"),
            nullable=False,
            comment="Parent bulk import job",
        ),
        sa.Column(
            "xero_tenant_id",
            sa.String(50),
            nullable=False,
            comment="Xero organization identifier",
        ),
        sa.Column(
            "organization_name",
            sa.String(255),
            nullable=False,
            comment="Xero organization display name",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="Status: pending, importing, syncing, completed, failed, skipped",
        ),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id", ondelete="SET NULL"),
            nullable=True,
            comment="Created XeroConnection (set after import)",
        ),
        sa.Column(
            "connection_type",
            sa.String(20),
            nullable=False,
            server_default="client",
            comment="Connection type: practice or client",
        ),
        sa.Column(
            "assigned_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_users.id", ondelete="SET NULL"),
            nullable=True,
            comment="Assigned team member",
        ),
        sa.Column(
            "already_connected",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="True if org was already connected",
        ),
        sa.Column(
            "selected_for_import",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="User's selection on config screen",
        ),
        sa.Column(
            "match_status",
            sa.String(20),
            nullable=True,
            comment="Auto-match result: matched, suggested, unmatched",
        ),
        sa.Column(
            "matched_client_name",
            sa.String(255),
            nullable=True,
            comment="Name of matched existing client",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
            comment="Error details if failed",
        ),
        sa.Column(
            "sync_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When sync was dispatched",
        ),
        sa.Column(
            "sync_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When sync finished",
        ),
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
        ),
    )

    # Create indexes
    op.create_index(
        "ix_bulk_import_orgs_job",
        "bulk_import_organizations",
        ["bulk_import_job_id"],
    )
    op.create_index(
        "ix_bulk_import_orgs_tenant",
        "bulk_import_organizations",
        ["tenant_id"],
    )
    op.create_index(
        "ix_bulk_import_orgs_xero_tenant",
        "bulk_import_organizations",
        ["xero_tenant_id"],
    )


def downgrade() -> None:
    """Downgrade database from this revision."""
    op.drop_index("ix_bulk_import_orgs_xero_tenant", "bulk_import_organizations")
    op.drop_index("ix_bulk_import_orgs_tenant", "bulk_import_organizations")
    op.drop_index("ix_bulk_import_orgs_job", "bulk_import_organizations")
    op.drop_table("bulk_import_organizations")
    op.drop_column("xero_oauth_states", "is_bulk_import")
