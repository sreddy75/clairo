"""progressive_sync_tables

Spec 043: Progressive Xero Data Sync
- Add phase tracking columns to xero_sync_jobs
- Add 6 new last_*_sync_at columns to xero_connections
- Create xero_sync_entity_progress table
- Create post_sync_tasks table
- Create xero_webhook_events table
- Add RLS policies to all new tables

Revision ID: b12cfec71461
Revises: 57ba9e4d45c4
Create Date: 2026-02-14 21:32:51.587833+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision: str = "b12cfec71461"
down_revision: str | None = "57ba9e4d45c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database to this revision."""

    # =========================================================================
    # 1. Create enum types
    # =========================================================================
    entity_progress_status = postgresql.ENUM(
        "pending",
        "in_progress",
        "completed",
        "failed",
        "skipped",
        name="xero_sync_entity_progress_status",
        create_type=False,
    )
    entity_progress_status.create(op.get_bind(), checkfirst=True)

    post_sync_task_status = postgresql.ENUM(
        "pending",
        "in_progress",
        "completed",
        "failed",
        name="post_sync_task_status",
        create_type=False,
    )
    post_sync_task_status.create(op.get_bind(), checkfirst=True)

    webhook_event_status = postgresql.ENUM(
        "pending",
        "processing",
        "completed",
        "failed",
        name="xero_webhook_event_status",
        create_type=False,
    )
    webhook_event_status.create(op.get_bind(), checkfirst=True)

    # =========================================================================
    # 2. Extend xero_sync_jobs with phase tracking columns
    # =========================================================================
    op.add_column(
        "xero_sync_jobs",
        sa.Column(
            "sync_phase",
            sa.Integer(),
            nullable=True,
            comment="Current sync phase (1, 2, or 3). Null for legacy full syncs.",
        ),
    )
    op.add_column(
        "xero_sync_jobs",
        sa.Column(
            "parent_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_sync_jobs.id", ondelete="CASCADE"),
            nullable=True,
            comment="Links phase jobs to a parent orchestration job",
        ),
    )
    op.add_column(
        "xero_sync_jobs",
        sa.Column(
            "triggered_by",
            sa.String(20),
            nullable=False,
            server_default="user",
            comment="What triggered this sync: user, schedule, webhook, system",
        ),
    )
    op.add_column(
        "xero_sync_jobs",
        sa.Column(
            "cancelled_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the job was cancelled",
        ),
    )

    # =========================================================================
    # 3. Extend xero_connections with 6 new last_*_sync_at columns
    # =========================================================================
    for entity in [
        "credit_notes",
        "payments",
        "overpayments",
        "prepayments",
        "journals",
        "manual_journals",
    ]:
        op.add_column(
            "xero_connections",
            sa.Column(
                f"last_{entity}_sync_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment=f"Last successful {entity.replace('_', ' ')} sync timestamp",
            ),
        )

    # =========================================================================
    # 4. Create xero_sync_entity_progress table
    # =========================================================================
    op.create_table(
        "xero_sync_entity_progress",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_sync_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column(
            "status",
            entity_progress_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("records_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("modified_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
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
            "job_id", "entity_type", name="uq_xero_sync_entity_progress_job_entity"
        ),
    )
    op.create_index(
        "ix_xero_sync_entity_progress_tenant",
        "xero_sync_entity_progress",
        ["tenant_id"],
    )
    op.create_index(
        "ix_xero_sync_entity_progress_job",
        "xero_sync_entity_progress",
        ["job_id"],
    )

    # =========================================================================
    # 5. Create post_sync_tasks table
    # =========================================================================
    op.create_table(
        "post_sync_tasks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_sync_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column(
            "status",
            post_sync_task_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("sync_phase", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result_summary", postgresql.JSONB(), nullable=True),
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
    op.create_index("ix_post_sync_tasks_job", "post_sync_tasks", ["job_id"])
    op.create_index("ix_post_sync_tasks_tenant", "post_sync_tasks", ["tenant_id"])
    op.create_index(
        "ix_post_sync_tasks_connection_type",
        "post_sync_tasks",
        ["connection_id", "task_type"],
    )

    # =========================================================================
    # 6. Create xero_webhook_events table
    # =========================================================================
    op.create_table(
        "xero_webhook_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
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
        sa.Column("webhook_key", sa.String(255), nullable=False, unique=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("event_category", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(50), nullable=False),
        sa.Column(
            "status",
            webhook_event_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_xero_webhook_events_connection_status",
        "xero_webhook_events",
        ["connection_id", "status"],
    )
    op.create_index(
        "ix_xero_webhook_events_tenant",
        "xero_webhook_events",
        ["tenant_id"],
    )
    op.create_index(
        "ix_xero_webhook_events_batch",
        "xero_webhook_events",
        ["batch_id"],
    )

    # =========================================================================
    # 7. RLS policies on new tables
    # =========================================================================
    for table in [
        "xero_sync_entity_progress",
        "post_sync_tasks",
        "xero_webhook_events",
    ]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
        """)


def downgrade() -> None:
    """Downgrade database from this revision."""

    # Drop RLS policies
    for table in [
        "xero_webhook_events",
        "post_sync_tasks",
        "xero_sync_entity_progress",
    ]:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    # Drop tables
    op.drop_table("xero_webhook_events")
    op.drop_table("post_sync_tasks")
    op.drop_table("xero_sync_entity_progress")

    # Remove columns from xero_connections
    for entity in [
        "manual_journals",
        "journals",
        "prepayments",
        "overpayments",
        "payments",
        "credit_notes",
    ]:
        op.drop_column("xero_connections", f"last_{entity}_sync_at")

    # Remove columns from xero_sync_jobs
    op.drop_column("xero_sync_jobs", "cancelled_at")
    op.drop_column("xero_sync_jobs", "triggered_by")
    op.drop_column("xero_sync_jobs", "parent_job_id")
    op.drop_column("xero_sync_jobs", "sync_phase")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS xero_webhook_event_status")
    op.execute("DROP TYPE IF EXISTS post_sync_task_status")
    op.execute("DROP TYPE IF EXISTS xero_sync_entity_progress_status")
