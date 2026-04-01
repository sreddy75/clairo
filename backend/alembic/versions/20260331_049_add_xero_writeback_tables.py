"""Add Xero writeback job tracking tables.

Spec 049: Xero Tax Code Write-Back.
Creates xero_writeback_jobs and xero_writeback_items tables.

Revision ID: 049_add_xero_writeback_tables
Revises: cc6091fd7b14
Create Date: 2026-03-31
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "049_add_xero_writeback_tables"
down_revision = "a054rls0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- xero_writeback_jobs --
    op.create_table(
        "xero_writeback_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bas_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "triggered_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("total_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("succeeded_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("error_detail", sa.Text, nullable=True),
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
    op.create_index(
        "ix_xero_writeback_jobs_tenant_session",
        "xero_writeback_jobs",
        ["tenant_id", "session_id"],
    )
    op.create_index(
        "ix_xero_writeback_jobs_tenant_status",
        "xero_writeback_jobs",
        ["tenant_id", "status"],
        postgresql_where=sa.text("status != 'completed'"),
    )

    # -- xero_writeback_items --
    op.create_table(
        "xero_writeback_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_writeback_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("xero_document_id", sa.String(255), nullable=False),
        sa.Column("local_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "override_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "line_item_indexes",
            postgresql.ARRAY(sa.Integer),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("before_tax_types", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("after_tax_types", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("skip_reason", sa.String(50), nullable=True),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.Column("xero_http_status", sa.Integer, nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "job_id",
            "source_type",
            "xero_document_id",
            name="uq_writeback_item_job_source_doc",
        ),
    )
    op.create_index(
        "ix_xero_writeback_items_tenant_job",
        "xero_writeback_items",
        ["tenant_id", "job_id"],
    )
    op.create_index(
        "ix_xero_writeback_items_tenant_status_failed",
        "xero_writeback_items",
        ["tenant_id", "status"],
        postgresql_where=sa.text("status = 'failed'"),
    )


def downgrade() -> None:
    op.drop_index("ix_xero_writeback_items_tenant_status_failed", table_name="xero_writeback_items")
    op.drop_index("ix_xero_writeback_items_tenant_job", table_name="xero_writeback_items")
    op.drop_table("xero_writeback_items")
    op.drop_index("ix_xero_writeback_jobs_tenant_status", table_name="xero_writeback_jobs")
    op.drop_index("ix_xero_writeback_jobs_tenant_session", table_name="xero_writeback_jobs")
    op.drop_table("xero_writeback_jobs")
