"""add_tax_knowledge_models

Spec 045: Comprehensive Australian Tax Knowledge Base
- Create legislation_sections table
- Create content_cross_references table
- Create tax_domains table (with seed data)
- Create bm25_index_entries table
- Create scraper_circuit_breakers table
- Add columns to content_chunks (content_type, section_ref, cross_references,
  defined_terms_used, topic_tags, fy_applicable, court, case_citation,
  legislation_section_id, document_hash, natural_key)
- Add columns to ingestion_jobs (completed_items, failed_items, total_items,
  is_resumable, parent_job_id)

Revision ID: d4a7e1f03c92
Revises: c7e4a2f39b01
Create Date: 2026-03-05 00:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision: str = "d4a7e1f03c92"
down_revision: str | None = "c7e4a2f39b01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create tax knowledge base tables, extend existing tables, and seed domains."""

    # =========================================================================
    # 1. Create legislation_sections table
    # =========================================================================
    op.create_table(
        "legislation_sections",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("act_id", sa.String(20), nullable=False),
        sa.Column("act_name", sa.String(255), nullable=False),
        sa.Column("act_short_name", sa.String(50), nullable=False),
        sa.Column("section_ref", sa.String(50), nullable=False),
        sa.Column("part", sa.String(20), nullable=True),
        sa.Column("division", sa.String(20), nullable=True),
        sa.Column("subdivision", sa.String(20), nullable=True),
        sa.Column("heading", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("compilation_date", sa.Date(), nullable=False),
        sa.Column("compilation_number", sa.String(20), nullable=True),
        sa.Column(
            "cross_references",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "defined_terms",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "topic_tags",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "is_current",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Unique constraint
        sa.UniqueConstraint(
            "act_id",
            "section_ref",
            "compilation_date",
            name="uq_legislation_section",
        ),
    )

    # Indexes for legislation_sections
    op.create_index("ix_legislation_sections_act", "legislation_sections", ["act_id"])
    op.create_index("ix_legislation_sections_ref", "legislation_sections", ["section_ref"])
    op.create_index(
        "ix_legislation_sections_topic_tags",
        "legislation_sections",
        ["topic_tags"],
        postgresql_using="gin",
    )

    # =========================================================================
    # 2. Create content_cross_references table
    # =========================================================================
    op.create_table(
        "content_cross_references",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("content_chunks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_section_ref", sa.String(100), nullable=False),
        sa.Column(
            "target_chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("content_chunks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reference_type", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Unique constraint
        sa.UniqueConstraint(
            "source_chunk_id",
            "target_section_ref",
            "reference_type",
            name="uq_cross_ref",
        ),
    )

    # Indexes for content_cross_references
    op.create_index("ix_cross_ref_source", "content_cross_references", ["source_chunk_id"])
    op.create_index("ix_cross_ref_target", "content_cross_references", ["target_section_ref"])
    op.create_index("ix_cross_ref_target_chunk", "content_cross_references", ["target_chunk_id"])

    # =========================================================================
    # 3. Create tax_domains table
    # =========================================================================
    op.create_table(
        "tax_domains",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("slug", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "topic_tags",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "legislation_refs",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "ruling_types",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column(
            "display_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # =========================================================================
    # 4. Create bm25_index_entries table
    # =========================================================================
    op.create_table(
        "bm25_index_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("content_chunks.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("collection_name", sa.String(100), nullable=False),
        sa.Column("tokens", postgresql.JSONB(), nullable=False),
        sa.Column(
            "section_refs",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Indexes for bm25_index_entries
    op.create_index("ix_bm25_collection", "bm25_index_entries", ["collection_name"])
    op.create_index(
        "ix_bm25_section_refs",
        "bm25_index_entries",
        ["section_refs"],
        postgresql_using="gin",
    )

    # =========================================================================
    # 5. Create scraper_circuit_breakers table
    # =========================================================================
    op.create_table(
        "scraper_circuit_breakers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source_host", sa.String(255), nullable=False, unique=True),
        sa.Column(
            "state",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'closed'"),
        ),
        sa.Column(
            "failure_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "recovery_timeout_seconds",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("3600"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # =========================================================================
    # 6. Add columns to content_chunks
    # =========================================================================
    op.add_column(
        "content_chunks",
        sa.Column("content_type", sa.String(50), nullable=True),
    )
    op.add_column(
        "content_chunks",
        sa.Column("section_ref", sa.String(100), nullable=True),
    )
    op.add_column(
        "content_chunks",
        sa.Column("cross_references", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "content_chunks",
        sa.Column("defined_terms_used", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "content_chunks",
        sa.Column("topic_tags", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "content_chunks",
        sa.Column("fy_applicable", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "content_chunks",
        sa.Column("court", sa.String(20), nullable=True),
    )
    op.add_column(
        "content_chunks",
        sa.Column("case_citation", sa.String(100), nullable=True),
    )
    op.add_column(
        "content_chunks",
        sa.Column(
            "legislation_section_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("legislation_sections.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "content_chunks",
        sa.Column("document_hash", sa.String(64), nullable=True),
    )
    op.add_column(
        "content_chunks",
        sa.Column("natural_key", sa.String(200), nullable=True),
    )

    # Indexes for new content_chunks columns
    op.create_index("ix_content_chunks_section_ref", "content_chunks", ["section_ref"])
    op.create_index("ix_content_chunks_content_type", "content_chunks", ["content_type"])
    op.create_index("ix_content_chunks_document_hash", "content_chunks", ["document_hash"])
    op.create_index("ix_content_chunks_natural_key", "content_chunks", ["natural_key"])
    op.create_index(
        "ix_content_chunks_topic_tags",
        "content_chunks",
        ["topic_tags"],
        postgresql_using="gin",
    )

    # =========================================================================
    # 7. Add columns to ingestion_jobs
    # =========================================================================
    op.add_column(
        "ingestion_jobs",
        sa.Column(
            "completed_items",
            postgresql.JSONB(),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "ingestion_jobs",
        sa.Column(
            "failed_items",
            postgresql.JSONB(),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "ingestion_jobs",
        sa.Column("total_items", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ingestion_jobs",
        sa.Column(
            "is_resumable",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("TRUE"),
        ),
    )
    op.add_column(
        "ingestion_jobs",
        sa.Column(
            "parent_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingestion_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # =========================================================================
    # 8. Seed tax_domains with initial data
    # =========================================================================
    tax_domains_table = sa.table(
        "tax_domains",
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("topic_tags", postgresql.JSONB),
        sa.column("legislation_refs", postgresql.JSONB),
        sa.column("ruling_types", postgresql.JSONB),
        sa.column("icon", sa.String),
        sa.column("display_order", sa.Integer),
        sa.column("is_active", sa.Boolean),
    )

    op.bulk_insert(
        tax_domains_table,
        [
            {
                "slug": "gst",
                "name": "GST Guardian",
                "description": (
                    "GST registration, BAS reporting, input tax credits, "
                    "taxable supplies, GST-free and input taxed supplies"
                ),
                "topic_tags": [
                    "GST",
                    "BAS",
                    "input_tax_credit",
                    "taxable_supply",
                    "GST_free",
                    "input_taxed",
                ],
                "legislation_refs": [
                    "A New Tax System (Goods and Services Tax) Act 1999",
                ],
                "ruling_types": ["GSTR", "GSTD"],
                "icon": "receipt",
                "display_order": 1,
                "is_active": True,
            },
            {
                "slug": "division_7a",
                "name": "Division 7A Advisor",
                "description": (
                    "Private company loans, payments, debt forgiveness, "
                    "deemed dividends, compliant loan agreements"
                ),
                "topic_tags": [
                    "division_7a",
                    "loans",
                    "private_company",
                    "deemed_dividend",
                    "benchmark_interest",
                ],
                "legislation_refs": ["ITAA 1936 Part III Div 7A"],
                "ruling_types": ["TR", "TD", "PCG"],
                "icon": "building",
                "display_order": 2,
                "is_active": True,
            },
            {
                "slug": "cgt",
                "name": "CGT Advisor",
                "description": (
                    "Capital gains tax events, cost base, discounts, "
                    "small business concessions, rollovers"
                ),
                "topic_tags": [
                    "CGT",
                    "capital_gain",
                    "cost_base",
                    "CGT_discount",
                    "small_business_CGT",
                    "rollover",
                ],
                "legislation_refs": ["ITAA 1997 Part 3-1"],
                "ruling_types": ["TR", "TD"],
                "icon": "trending-up",
                "display_order": 3,
                "is_active": True,
            },
            {
                "slug": "smsf",
                "name": "SMSF Specialist",
                "description": (
                    "Self-managed superannuation funds, contribution caps, "
                    "pensions, investment rules, auditing"
                ),
                "topic_tags": [
                    "SMSF",
                    "superannuation",
                    "contribution_cap",
                    "pension",
                    "SMSF_audit",
                ],
                "legislation_refs": [
                    "Superannuation Industry (Supervision) Act 1993",
                    "ITAA 1997 Part 3-30",
                ],
                "ruling_types": ["TR", "TD", "SGR", "SRB"],
                "icon": "piggy-bank",
                "display_order": 4,
                "is_active": True,
            },
            {
                "slug": "fbt",
                "name": "FBT Advisor",
                "description": (
                    "Fringe benefits tax, car benefits, entertainment, "
                    "exempt benefits, FBT return preparation"
                ),
                "topic_tags": [
                    "FBT",
                    "fringe_benefit",
                    "car_benefit",
                    "entertainment",
                    "exempt_benefit",
                ],
                "legislation_refs": [
                    "Fringe Benefits Tax Assessment Act 1986",
                ],
                "ruling_types": ["TR", "TD"],
                "icon": "car",
                "display_order": 5,
                "is_active": True,
            },
            {
                "slug": "trusts",
                "name": "Trusts Advisor",
                "description": (
                    "Trust income distribution, streaming, family trusts, "
                    "trust losses, section 100A"
                ),
                "topic_tags": [
                    "trust",
                    "distribution",
                    "streaming",
                    "family_trust",
                    "trust_loss",
                    "section_100A",
                ],
                "legislation_refs": ["ITAA 1936 Part III Div 6"],
                "ruling_types": ["TR", "TD", "PCG"],
                "icon": "users",
                "display_order": 6,
                "is_active": True,
            },
            {
                "slug": "payg",
                "name": "PAYG & Payroll",
                "description": (
                    "PAYG withholding, PAYG instalments, super guarantee, "
                    "STP reporting, contractor vs employee"
                ),
                "topic_tags": [
                    "PAYG",
                    "withholding",
                    "instalment",
                    "super_guarantee",
                    "STP",
                    "contractor",
                ],
                "legislation_refs": [
                    "Taxation Administration Act 1953 Schedule 1",
                    "Superannuation Guarantee (Administration) Act 1992",
                ],
                "ruling_types": ["TR", "TD", "SGR"],
                "icon": "wallet",
                "display_order": 7,
                "is_active": True,
            },
            {
                "slug": "international",
                "name": "International Tax",
                "description": (
                    "Transfer pricing, thin capitalisation, CFCs, "
                    "foreign income, tax treaties, withholding tax"
                ),
                "topic_tags": [
                    "international",
                    "transfer_pricing",
                    "thin_cap",
                    "CFC",
                    "foreign_income",
                    "treaty",
                    "withholding",
                ],
                "legislation_refs": [
                    "ITAA 1936 Part III Div 13",
                    "ITAA 1997 Part 3-6",
                ],
                "ruling_types": ["TR", "TD"],
                "icon": "globe",
                "display_order": 8,
                "is_active": True,
            },
            {
                "slug": "deductions",
                "name": "Deductions & Expenses",
                "description": (
                    "General deductions, specific deductions, depreciation, "
                    "home office, travel, work-related expenses"
                ),
                "topic_tags": [
                    "deduction",
                    "depreciation",
                    "home_office",
                    "travel",
                    "work_related",
                    "instant_asset_writeoff",
                ],
                "legislation_refs": [
                    "ITAA 1997 Div 8",
                    "ITAA 1997 Div 40",
                ],
                "ruling_types": ["TR", "TD", "PCG"],
                "icon": "calculator",
                "display_order": 9,
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    """Remove tax knowledge base tables, columns, and seed data."""

    # =========================================================================
    # 1. Remove columns from ingestion_jobs (reverse order)
    # =========================================================================
    op.drop_column("ingestion_jobs", "parent_job_id")
    op.drop_column("ingestion_jobs", "is_resumable")
    op.drop_column("ingestion_jobs", "total_items")
    op.drop_column("ingestion_jobs", "failed_items")
    op.drop_column("ingestion_jobs", "completed_items")

    # =========================================================================
    # 2. Remove indexes and columns from content_chunks (reverse order)
    # =========================================================================
    op.drop_index("ix_content_chunks_topic_tags", table_name="content_chunks")
    op.drop_index("ix_content_chunks_natural_key", table_name="content_chunks")
    op.drop_index("ix_content_chunks_document_hash", table_name="content_chunks")
    op.drop_index("ix_content_chunks_content_type", table_name="content_chunks")
    op.drop_index("ix_content_chunks_section_ref", table_name="content_chunks")

    op.drop_column("content_chunks", "natural_key")
    op.drop_column("content_chunks", "document_hash")
    op.drop_column("content_chunks", "legislation_section_id")
    op.drop_column("content_chunks", "case_citation")
    op.drop_column("content_chunks", "court")
    op.drop_column("content_chunks", "fy_applicable")
    op.drop_column("content_chunks", "topic_tags")
    op.drop_column("content_chunks", "defined_terms_used")
    op.drop_column("content_chunks", "cross_references")
    op.drop_column("content_chunks", "section_ref")
    op.drop_column("content_chunks", "content_type")

    # =========================================================================
    # 3. Drop new tables (reverse creation order)
    # =========================================================================
    op.drop_table("scraper_circuit_breakers")

    op.drop_index("ix_bm25_section_refs", table_name="bm25_index_entries")
    op.drop_index("ix_bm25_collection", table_name="bm25_index_entries")
    op.drop_table("bm25_index_entries")

    # tax_domains (seed data removed automatically with table drop)
    op.drop_table("tax_domains")

    op.drop_index("ix_cross_ref_target_chunk", table_name="content_cross_references")
    op.drop_index("ix_cross_ref_target", table_name="content_cross_references")
    op.drop_index("ix_cross_ref_source", table_name="content_cross_references")
    op.drop_table("content_cross_references")

    op.drop_index("ix_legislation_sections_topic_tags", table_name="legislation_sections")
    op.drop_index("ix_legislation_sections_ref", table_name="legislation_sections")
    op.drop_index("ix_legislation_sections_act", table_name="legislation_sections")
    op.drop_table("legislation_sections")
