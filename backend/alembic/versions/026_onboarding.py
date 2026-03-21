"""Onboarding flow tables.

Revision ID: 026_onboarding
Revises: 025_usage_tracking
Create Date: 2025-12-31

Spec 021: Onboarding Flow
- Creates onboarding_progress table for tracking tenant progress
- Creates bulk_import_jobs table for client import jobs
- Creates email_drips table for onboarding email tracking
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "026_onboarding"
down_revision: str | None = "025_usage_tracking"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create onboarding tables."""
    # Create onboarding_status enum
    op.execute("""
        CREATE TYPE onboarding_status AS ENUM (
            'started',
            'tier_selected',
            'payment_setup',
            'xero_connected',
            'clients_imported',
            'tour_completed',
            'completed',
            'skipped_xero'
        )
    """)

    # Create bulk_import_job_status enum
    op.execute("""
        CREATE TYPE bulk_import_job_status AS ENUM (
            'pending',
            'in_progress',
            'completed',
            'partial_failure',
            'failed',
            'cancelled'
        )
    """)

    # Create onboarding_progress table
    op.create_table(
        "onboarding_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            comment="Foreign key to tenant (1:1 relationship)",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "started",
                "tier_selected",
                "payment_setup",
                "xero_connected",
                "clients_imported",
                "tour_completed",
                "completed",
                "skipped_xero",
                name="onboarding_status",
                create_type=False,
            ),
            nullable=False,
            server_default="started",
            comment="Current onboarding state",
        ),
        sa.Column(
            "current_step",
            sa.String(50),
            nullable=False,
            server_default="tier_selection",
            comment="Current step identifier for UI routing",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="When onboarding began",
        ),
        sa.Column(
            "tier_selected_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When tier was chosen",
        ),
        sa.Column(
            "payment_setup_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When Stripe checkout completed",
        ),
        sa.Column(
            "xero_connected_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When Xero OAuth completed",
        ),
        sa.Column(
            "clients_imported_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When first client imported",
        ),
        sa.Column(
            "tour_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When product tour finished",
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When all steps done",
        ),
        sa.Column(
            "checklist_dismissed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When user dismissed checklist",
        ),
        sa.Column(
            "xero_skipped",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether user skipped Xero connection",
        ),
        sa.Column(
            "tour_skipped",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether user skipped product tour",
        ),
        sa.Column(
            "extra_data",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Additional tracking data",
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
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_onboarding_progress_tenant_id",
        "onboarding_progress",
        ["tenant_id"],
        unique=True,
    )
    op.create_index(
        "ix_onboarding_progress_status",
        "onboarding_progress",
        ["status"],
    )

    # Create bulk_import_jobs table
    op.create_table(
        "bulk_import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            comment="Foreign key to tenant",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "in_progress",
                "completed",
                "partial_failure",
                "failed",
                "cancelled",
                name="bulk_import_job_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
            comment="Current job status",
        ),
        sa.Column(
            "source_type",
            sa.String(20),
            nullable=False,
            comment="Source: 'xpm' or 'xero_accounting'",
        ),
        sa.Column(
            "total_clients",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Total clients to import",
        ),
        sa.Column(
            "imported_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Successfully imported count",
        ),
        sa.Column(
            "failed_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Failed import count",
        ),
        sa.Column(
            "progress_percent",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Current progress (0-100)",
        ),
        sa.Column(
            "client_ids",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="List of XPM/Xero client IDs to import",
        ),
        sa.Column(
            "imported_clients",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="List of imported client details",
        ),
        sa.Column(
            "failed_clients",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="List of failed clients with errors",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Job start time",
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Job completion time",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
            comment="Overall error if job failed",
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
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_bulk_import_jobs_tenant_id",
        "bulk_import_jobs",
        ["tenant_id"],
    )
    op.create_index(
        "ix_bulk_import_jobs_status",
        "bulk_import_jobs",
        ["status"],
    )

    # Create email_drips table
    op.create_table(
        "email_drips",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            comment="Foreign key to tenant",
        ),
        sa.Column(
            "email_type",
            sa.String(50),
            nullable=False,
            comment="Email template identifier",
        ),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="When email was sent",
        ),
        sa.Column(
            "recipient_email",
            sa.String(255),
            nullable=False,
            comment="Recipient email address",
        ),
        sa.Column(
            "extra_data",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Additional context",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "email_type",
            name="uq_email_drip_tenant_type",
        ),
    )
    op.create_index(
        "ix_email_drips_tenant_id",
        "email_drips",
        ["tenant_id"],
    )
    op.create_index(
        "ix_email_drips_email_type",
        "email_drips",
        ["email_type"],
    )


def downgrade() -> None:
    """Drop onboarding tables."""
    # Drop tables in reverse order
    op.drop_index("ix_email_drips_email_type", table_name="email_drips")
    op.drop_index("ix_email_drips_tenant_id", table_name="email_drips")
    op.drop_table("email_drips")

    op.drop_index("ix_bulk_import_jobs_status", table_name="bulk_import_jobs")
    op.drop_index("ix_bulk_import_jobs_tenant_id", table_name="bulk_import_jobs")
    op.drop_table("bulk_import_jobs")

    op.drop_index("ix_onboarding_progress_status", table_name="onboarding_progress")
    op.drop_index("ix_onboarding_progress_tenant_id", table_name="onboarding_progress")
    op.drop_table("onboarding_progress")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS bulk_import_job_status")
    op.execute("DROP TYPE IF EXISTS onboarding_status")
