# Data Model: Comprehensive Australian Tax Knowledge Base

**Feature**: 045-comprehensive-tax-knowledge-base
**Date**: 2026-03-05

---

## New Tables

### `legislation_sections`

Tracks ingested legislation sections for cross-referencing and section-level lookup.

```sql
CREATE TABLE legislation_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    act_id VARCHAR(20) NOT NULL,           -- e.g., "C2004A05138"
    act_name VARCHAR(255) NOT NULL,        -- e.g., "Income Tax Assessment Act 1997"
    act_short_name VARCHAR(50) NOT NULL,   -- e.g., "ITAA 1997"
    section_ref VARCHAR(50) NOT NULL,      -- e.g., "s104-10"
    part VARCHAR(20),                      -- e.g., "3-1"
    division VARCHAR(20),                  -- e.g., "104"
    subdivision VARCHAR(20),               -- e.g., "104-A"
    heading TEXT,                          -- Section heading text
    content_hash VARCHAR(64) NOT NULL,     -- SHA-256 for change detection
    compilation_date DATE NOT NULL,        -- legislation.gov.au compilation date
    compilation_number VARCHAR(20),        -- e.g., "C26222"
    cross_references JSONB DEFAULT '[]',   -- ["s104-5", "s110-25", "Div 115"]
    defined_terms JSONB DEFAULT '[]',      -- ["CGT asset", "capital proceed"]
    topic_tags JSONB DEFAULT '[]',         -- ["CGT", "disposal"]
    is_current BOOLEAN DEFAULT TRUE,       -- False if act section repealed
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_legislation_section UNIQUE (act_id, section_ref, compilation_date)
);

CREATE INDEX idx_legislation_sections_act ON legislation_sections (act_id);
CREATE INDEX idx_legislation_sections_ref ON legislation_sections (section_ref);
CREATE INDEX idx_legislation_sections_topic ON legislation_sections USING GIN (topic_tags);
```

### `content_cross_references`

Links between content chunks for graph traversal during retrieval.

```sql
CREATE TABLE content_cross_references (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_chunk_id UUID NOT NULL REFERENCES content_chunks(id) ON DELETE CASCADE,
    target_section_ref VARCHAR(100) NOT NULL, -- e.g., "s109D ITAA 1936"
    target_chunk_id UUID REFERENCES content_chunks(id) ON DELETE SET NULL, -- Resolved link
    reference_type VARCHAR(20) NOT NULL,     -- "cites", "defines", "supersedes", "amends"
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_cross_ref UNIQUE (source_chunk_id, target_section_ref, reference_type)
);

CREATE INDEX idx_cross_ref_source ON content_cross_references (source_chunk_id);
CREATE INDEX idx_cross_ref_target ON content_cross_references (target_section_ref);
CREATE INDEX idx_cross_ref_target_chunk ON content_cross_references (target_chunk_id);
```

### `tax_domains`

Specialist tax domain configuration for scoped retrieval.

```sql
CREATE TABLE tax_domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(50) NOT NULL UNIQUE,       -- e.g., "gst", "division_7a", "cgt"
    name VARCHAR(100) NOT NULL,             -- e.g., "GST Guardian"
    description TEXT NOT NULL,              -- User-facing description
    topic_tags JSONB NOT NULL DEFAULT '[]', -- ["GST", "BAS", "input_tax_credit"]
    legislation_refs JSONB DEFAULT '[]',    -- ["GST Act 1999", "ITAA 1997 Div 11"]
    ruling_types JSONB DEFAULT '[]',        -- ["GSTR", "GSTD"]
    icon VARCHAR(50),                       -- Frontend icon identifier
    display_order INT NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `bm25_index_entries`

Lightweight BM25 keyword index for hybrid search.

```sql
CREATE TABLE bm25_index_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id UUID NOT NULL REFERENCES content_chunks(id) ON DELETE CASCADE,
    collection_name VARCHAR(100) NOT NULL,
    tokens JSONB NOT NULL,                  -- Pre-tokenized text for BM25 scoring
    section_refs JSONB DEFAULT '[]',        -- Extracted section/ruling references for exact match
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_bm25_chunk UNIQUE (chunk_id)
);

CREATE INDEX idx_bm25_collection ON bm25_index_entries (collection_name);
CREATE INDEX idx_bm25_section_refs ON bm25_index_entries USING GIN (section_refs);
```

---

## Extended Tables

### `content_chunks` (existing — add columns)

```sql
ALTER TABLE content_chunks
    ADD COLUMN content_type VARCHAR(50),       -- "operative_provision", "definition", "example", "headnote", "reasoning", "ruling", "explanation"
    ADD COLUMN section_ref VARCHAR(100),        -- "s104-10 ITAA 1997", "TR 2024/1 para 15"
    ADD COLUMN cross_references JSONB DEFAULT '[]',  -- ["s104-5", "Div 115"]
    ADD COLUMN defined_terms_used JSONB DEFAULT '[]', -- ["CGT asset", "capital proceed"]
    ADD COLUMN topic_tags JSONB DEFAULT '[]',   -- ["CGT", "disposal", "CGT_event_A1"]
    ADD COLUMN fy_applicable JSONB DEFAULT '[]', -- ["2025", "2026"]
    ADD COLUMN court VARCHAR(20),               -- "HCA", "FCA", "FCAFC", "AATA"
    ADD COLUMN case_citation VARCHAR(100),      -- "[2010] HCA 10"
    ADD COLUMN legislation_section_id UUID REFERENCES legislation_sections(id) ON DELETE SET NULL,
    ADD COLUMN document_hash VARCHAR(64),       -- SHA-256 of FULL source document (for change detection)
    ADD COLUMN natural_key VARCHAR(200);        -- Idempotency key: "legislation:s109D-ITAA1936", "ruling:TR2024-1"

CREATE INDEX idx_chunks_content_type ON content_chunks (content_type);
CREATE INDEX idx_chunks_section_ref ON content_chunks (section_ref);
CREATE INDEX idx_chunks_topic_tags ON content_chunks USING GIN (topic_tags);
CREATE INDEX idx_chunks_court ON content_chunks (court) WHERE court IS NOT NULL;
CREATE INDEX idx_chunks_legislation_section ON content_chunks (legislation_section_id) WHERE legislation_section_id IS NOT NULL;
CREATE INDEX idx_chunks_document_hash ON content_chunks (document_hash) WHERE document_hash IS NOT NULL;
CREATE INDEX idx_chunks_natural_key ON content_chunks (natural_key) WHERE natural_key IS NOT NULL;
```

### `knowledge_sources` (existing — add source_types)

No schema change needed. Existing `source_type` enum already supports extensible values. New source types to register:
- `legislation_gov` — Federal Register of Legislation
- `ato_legal_db` — ATO Legal Database (full crawl)
- `open_legal_corpus` — HuggingFace Open Australian Legal Corpus
- `federal_court_rss` — Federal Court RSS feed
- `tpb` — Tax Practitioners Board
- `treasury` — Treasury exposure drafts

---

## SQLAlchemy Models

### LegislationSection

```python
class LegislationSection(Base):
    __tablename__ = "legislation_sections"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    act_id: Mapped[str] = mapped_column(String(20), nullable=False)
    act_name: Mapped[str] = mapped_column(String(255), nullable=False)
    act_short_name: Mapped[str] = mapped_column(String(50), nullable=False)
    section_ref: Mapped[str] = mapped_column(String(50), nullable=False)
    part: Mapped[str | None] = mapped_column(String(20))
    division: Mapped[str | None] = mapped_column(String(20))
    subdivision: Mapped[str | None] = mapped_column(String(20))
    heading: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    compilation_date: Mapped[date] = mapped_column(Date, nullable=False)
    compilation_number: Mapped[str | None] = mapped_column(String(20))
    cross_references: Mapped[list] = mapped_column(JSONB, default=list)
    defined_terms: Mapped[list] = mapped_column(JSONB, default=list)
    topic_tags: Mapped[list] = mapped_column(JSONB, default=list)
    is_current: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    chunks: Mapped[list["ContentChunk"]] = relationship(back_populates="legislation_section")

    __table_args__ = (
        UniqueConstraint("act_id", "section_ref", "compilation_date", name="uq_legislation_section"),
        Index("idx_legislation_sections_act", "act_id"),
        Index("idx_legislation_sections_ref", "section_ref"),
    )
```

### ContentCrossReference

```python
class ContentCrossReference(Base):
    __tablename__ = "content_cross_references"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_chunk_id: Mapped[UUID] = mapped_column(ForeignKey("content_chunks.id", ondelete="CASCADE"), nullable=False)
    target_section_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    target_chunk_id: Mapped[UUID | None] = mapped_column(ForeignKey("content_chunks.id", ondelete="SET NULL"))
    reference_type: Mapped[str] = mapped_column(String(20), nullable=False)  # cites, defines, supersedes, amends
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    source_chunk: Mapped["ContentChunk"] = relationship(foreign_keys=[source_chunk_id])
    target_chunk: Mapped["ContentChunk | None"] = relationship(foreign_keys=[target_chunk_id])

    __table_args__ = (
        UniqueConstraint("source_chunk_id", "target_section_ref", "reference_type", name="uq_cross_ref"),
    )
```

### TaxDomain

```python
class TaxDomain(Base):
    __tablename__ = "tax_domains"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    topic_tags: Mapped[list] = mapped_column(JSONB, default=list)
    legislation_refs: Mapped[list] = mapped_column(JSONB, default=list)
    ruling_types: Mapped[list] = mapped_column(JSONB, default=list)
    icon: Mapped[str | None] = mapped_column(String(50))
    display_order: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
```

### BM25IndexEntry

```python
class BM25IndexEntry(Base):
    __tablename__ = "bm25_index_entries"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    chunk_id: Mapped[UUID] = mapped_column(ForeignKey("content_chunks.id", ondelete="CASCADE"), unique=True, nullable=False)
    collection_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens: Mapped[list] = mapped_column(JSONB, nullable=False)
    section_refs: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    chunk: Mapped["ContentChunk"] = relationship()
```

---

## Entity Relationship Diagram

```
┌─────────────────────┐     ┌─────────────────────────┐
│  KnowledgeSource    │────→│     IngestionJob         │
│  (existing)         │     │     (existing)           │
└─────────┬───────────┘     └─────────────────────────┘
          │ 1:N
          ▼
┌─────────────────────┐     ┌─────────────────────────┐
│   ContentChunk      │────→│  BM25IndexEntry          │
│   (extended)        │     │  (NEW - 1:1)             │
│                     │     └─────────────────────────┘
│  + content_type     │
│  + section_ref      │     ┌─────────────────────────┐
│  + cross_references │────→│ ContentCrossReference    │
│  + topic_tags       │     │ (NEW - 1:N from source)  │
│  + court            │     │                          │
│  + case_citation    │     │  source_chunk_id ──→ CC  │
│  + legislation_     │     │  target_section_ref      │
│    section_id       │     │  target_chunk_id ──→ CC  │
└─────────┬───────────┘     └─────────────────────────┘
          │ N:1
          ▼
┌─────────────────────┐     ┌─────────────────────────┐
│ LegislationSection  │     │     TaxDomain            │
│ (NEW)               │     │     (NEW)                │
│                     │     │                          │
│  act_id, act_name   │     │  slug, name              │
│  section_ref        │     │  topic_tags              │
│  part/div/subdiv    │     │  legislation_refs        │
│  cross_references   │     │  ruling_types            │
│  defined_terms      │     │  display_order           │
│  compilation_date   │     │  is_active               │
└─────────────────────┘     └─────────────────────────┘
```

---

## Seed Data: Tax Domains

```python
INITIAL_TAX_DOMAINS = [
    {
        "slug": "gst",
        "name": "GST Guardian",
        "description": "GST registration, BAS reporting, input tax credits, taxable supplies, GST-free and input taxed supplies",
        "topic_tags": ["GST", "BAS", "input_tax_credit", "taxable_supply", "GST_free", "input_taxed"],
        "legislation_refs": ["A New Tax System (Goods and Services Tax) Act 1999"],
        "ruling_types": ["GSTR", "GSTD"],
        "icon": "receipt",
        "display_order": 1,
    },
    {
        "slug": "division_7a",
        "name": "Division 7A Advisor",
        "description": "Private company loans, payments, debt forgiveness, deemed dividends, compliant loan agreements",
        "topic_tags": ["division_7a", "loans", "private_company", "deemed_dividend", "benchmark_interest"],
        "legislation_refs": ["ITAA 1936 Part III Div 7A"],
        "ruling_types": ["TR", "TD", "PCG"],
        "icon": "building",
        "display_order": 2,
    },
    {
        "slug": "cgt",
        "name": "CGT Advisor",
        "description": "Capital gains tax events, cost base, discounts, small business concessions, rollovers",
        "topic_tags": ["CGT", "capital_gain", "cost_base", "CGT_discount", "small_business_CGT", "rollover"],
        "legislation_refs": ["ITAA 1997 Part 3-1"],
        "ruling_types": ["TR", "TD"],
        "icon": "trending-up",
        "display_order": 3,
    },
    {
        "slug": "smsf",
        "name": "SMSF Specialist",
        "description": "Self-managed superannuation funds, contribution caps, pensions, investment rules, auditing",
        "topic_tags": ["SMSF", "superannuation", "contribution_cap", "pension", "SMSF_audit"],
        "legislation_refs": ["Superannuation Industry (Supervision) Act 1993", "ITAA 1997 Part 3-30"],
        "ruling_types": ["TR", "TD", "SGR", "SRB"],
        "icon": "piggy-bank",
        "display_order": 4,
    },
    {
        "slug": "fbt",
        "name": "FBT Advisor",
        "description": "Fringe benefits tax, car benefits, entertainment, exempt benefits, FBT return preparation",
        "topic_tags": ["FBT", "fringe_benefit", "car_benefit", "entertainment", "exempt_benefit"],
        "legislation_refs": ["Fringe Benefits Tax Assessment Act 1986"],
        "ruling_types": ["TR", "TD"],
        "icon": "car",
        "display_order": 5,
    },
    {
        "slug": "trusts",
        "name": "Trusts Advisor",
        "description": "Trust income distribution, streaming, family trusts, trust losses, section 100A",
        "topic_tags": ["trust", "distribution", "streaming", "family_trust", "trust_loss", "section_100A"],
        "legislation_refs": ["ITAA 1936 Part III Div 6"],
        "ruling_types": ["TR", "TD", "PCG"],
        "icon": "users",
        "display_order": 6,
    },
    {
        "slug": "payg",
        "name": "PAYG & Payroll",
        "description": "PAYG withholding, PAYG instalments, super guarantee, STP reporting, contractor vs employee",
        "topic_tags": ["PAYG", "withholding", "instalment", "super_guarantee", "STP", "contractor"],
        "legislation_refs": ["Taxation Administration Act 1953 Schedule 1", "Superannuation Guarantee (Administration) Act 1992"],
        "ruling_types": ["TR", "TD", "SGR"],
        "icon": "wallet",
        "display_order": 7,
    },
    {
        "slug": "international",
        "name": "International Tax",
        "description": "Transfer pricing, thin capitalisation, CFCs, foreign income, tax treaties, withholding tax",
        "topic_tags": ["international", "transfer_pricing", "thin_cap", "CFC", "foreign_income", "treaty", "withholding"],
        "legislation_refs": ["ITAA 1936 Part III Div 13", "ITAA 1997 Part 3-6"],
        "ruling_types": ["TR", "TD"],
        "icon": "globe",
        "display_order": 8,
    },
    {
        "slug": "deductions",
        "name": "Deductions & Expenses",
        "description": "General deductions, specific deductions, depreciation, home office, travel, work-related expenses",
        "topic_tags": ["deduction", "depreciation", "home_office", "travel", "work_related", "instant_asset_writeoff"],
        "legislation_refs": ["ITAA 1997 Div 8", "ITAA 1997 Div 40"],
        "ruling_types": ["TR", "TD", "PCG"],
        "icon": "calculator",
        "display_order": 9,
    },
]
```

---

### `ingestion_jobs` (existing — add columns for checkpoint/resume)

```sql
ALTER TABLE ingestion_jobs
    ADD COLUMN completed_items JSONB DEFAULT '[]',    -- List of source_urls/doc_ids successfully ingested
    ADD COLUMN failed_items JSONB DEFAULT '[]',       -- [{url, error, attempt_count}]
    ADD COLUMN total_items INT,                       -- Total expected items (known upfront or updated)
    ADD COLUMN is_resumable BOOLEAN DEFAULT TRUE,     -- Whether this job supports checkpoint/resume
    ADD COLUMN parent_job_id UUID REFERENCES ingestion_jobs(id) ON DELETE SET NULL; -- Links retries to original job
```

### `scraper_circuit_breakers` (new — track per-source health)

```sql
CREATE TABLE scraper_circuit_breakers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_host VARCHAR(255) NOT NULL UNIQUE,     -- e.g., "www.legislation.gov.au"
    state VARCHAR(20) NOT NULL DEFAULT 'closed',  -- "closed" (healthy), "open" (tripped), "half_open" (testing)
    failure_count INT NOT NULL DEFAULT 0,
    last_failure_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    opened_at TIMESTAMPTZ,                        -- When circuit tripped
    recovery_timeout_seconds INT NOT NULL DEFAULT 3600,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Migration Notes

- All new tables have no tenant_id — knowledge base content is system-level (public domain content shared across all tenants)
- Extended ContentChunk columns are all nullable — backward compatible with existing data
- New columns `document_hash` and `natural_key` on ContentChunk enable document-level idempotency (replaces first-chunk-only dedup)
- Extended IngestionJob columns enable checkpoint/resume for large ingestion runs
- BM25IndexEntry is populated lazily during next ingestion cycle or via backfill task
- TaxDomain seed data inserted via data migration
- LegislationSection populated during first legislation ingestion run
