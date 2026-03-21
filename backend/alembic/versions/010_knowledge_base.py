"""Knowledge base infrastructure tables.

Revision ID: 010_knowledge_base
Revises: 009_add_lodgement_fields
Create Date: 2025-12-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "010_knowledge_base"
down_revision: str | None = "009_add_lodgement_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # =========================================================================
    # Create knowledge_sources table
    # =========================================================================
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        # Source identification
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        # Configuration
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("collection_name", sa.String(length=100), nullable=False),
        sa.Column(
            "scrape_config",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # Status
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_knowledge_sources_name"),
    )

    # Create indexes for knowledge_sources
    op.create_index("idx_knowledge_sources_collection", "knowledge_sources", ["collection_name"])
    op.create_index("idx_knowledge_sources_source_type", "knowledge_sources", ["source_type"])
    op.create_index("idx_knowledge_sources_active", "knowledge_sources", ["is_active"])

    # =========================================================================
    # Create content_chunks table
    # =========================================================================
    op.create_table(
        "content_chunks",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        # Qdrant linkage
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("qdrant_point_id", sa.String(length=100), nullable=False),
        sa.Column("collection_name", sa.String(length=100), nullable=False),
        # Deduplication
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        # Content metadata
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        # Temporal metadata
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        # Classification metadata (arrays)
        sa.Column(
            "entity_types",
            postgresql.ARRAY(sa.String(50)),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column(
            "industries",
            postgresql.ARRAY(sa.String(100)),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        # Ruling-specific
        sa.Column("ruling_number", sa.String(length=50), nullable=True),
        # Status
        sa.Column("is_superseded", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("superseded_by", sa.String(length=50), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("qdrant_point_id", name="uq_content_chunks_qdrant_point"),
    )

    # Create indexes for content_chunks
    op.create_index("idx_content_chunks_qdrant_point", "content_chunks", ["qdrant_point_id"])
    op.create_index("idx_content_chunks_collection", "content_chunks", ["collection_name"])
    op.create_index("idx_content_chunks_content_hash", "content_chunks", ["content_hash"])
    op.create_index(
        "idx_content_chunks_source_collection",
        "content_chunks",
        ["source_id", "collection_name"],
    )
    op.create_index("idx_content_chunks_effective_date", "content_chunks", ["effective_date"])
    op.create_index("idx_content_chunks_ruling_number", "content_chunks", ["ruling_number"])
    op.create_index("idx_content_chunks_superseded", "content_chunks", ["is_superseded"])

    # =========================================================================
    # Create ingestion_jobs table
    # =========================================================================
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        # Job identification
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        # Timing
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        # Statistics
        sa.Column("items_processed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("items_added", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("items_updated", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("items_skipped", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("items_failed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default=sa.text("0")),
        # Error tracking
        sa.Column(
            "errors",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        # Trigger info
        sa.Column(
            "triggered_by",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'manual'"),
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_ingestion_jobs_status",
        ),
    )

    # Create indexes for ingestion_jobs
    op.create_index("idx_ingestion_jobs_status", "ingestion_jobs", ["status"])
    op.create_index(
        "idx_ingestion_jobs_source_status",
        "ingestion_jobs",
        ["source_id", "status"],
    )
    op.create_index("idx_ingestion_jobs_created_at", "ingestion_jobs", ["created_at"])


def downgrade() -> None:
    # Drop indexes for ingestion_jobs
    op.drop_index("idx_ingestion_jobs_created_at", table_name="ingestion_jobs")
    op.drop_index("idx_ingestion_jobs_source_status", table_name="ingestion_jobs")
    op.drop_index("idx_ingestion_jobs_status", table_name="ingestion_jobs")

    # Drop indexes for content_chunks
    op.drop_index("idx_content_chunks_superseded", table_name="content_chunks")
    op.drop_index("idx_content_chunks_ruling_number", table_name="content_chunks")
    op.drop_index("idx_content_chunks_effective_date", table_name="content_chunks")
    op.drop_index("idx_content_chunks_source_collection", table_name="content_chunks")
    op.drop_index("idx_content_chunks_content_hash", table_name="content_chunks")
    op.drop_index("idx_content_chunks_collection", table_name="content_chunks")
    op.drop_index("idx_content_chunks_qdrant_point", table_name="content_chunks")

    # Drop indexes for knowledge_sources
    op.drop_index("idx_knowledge_sources_active", table_name="knowledge_sources")
    op.drop_index("idx_knowledge_sources_source_type", table_name="knowledge_sources")
    op.drop_index("idx_knowledge_sources_collection", table_name="knowledge_sources")

    # Drop tables
    op.drop_table("ingestion_jobs")
    op.drop_table("content_chunks")
    op.drop_table("knowledge_sources")
