# Feature Specification: Comprehensive Australian Tax Knowledge Base

**Feature Branch**: `045-comprehensive-tax-knowledge-base`
**Created**: 2026-03-05
**Status**: Draft
**Input**: Build a comprehensive Australian tax knowledge base by ingesting publicly available ATO rulings, legislation, case law, and practitioner guidance into Clairo's existing RAG infrastructure. This replaces/leapfrogs Tax Guru's $4,500 knowledge product by combining authoritative public sources with Clairo's client-context intelligence.

## Context

Clairo's existing knowledge base (spec 012) established the RAG infrastructure: Pinecone vector store, Voyage embeddings, ATO scrapers, semantic chunking, and citation system. However, the knowledge corpus is thin -- primarily ATO RSS rulings and some web content. Competitor Tax Guru (tax-guru.ai) charges $4,500 for access to 18,000+ "expert-verified" articles across 17 tax specialisations, but this content is fundamentally repackaged public information from ATO, legislation, and case law.

All Australian tax knowledge sources are either CC BY 4.0 licensed (legislation.gov.au), explicitly free to copy/adapt (ATO copyright policy), or available under CC BY 4.0 (Open Australian Legal Corpus). The engineering challenge is not access -- it's building a sophisticated ingestion, chunking, and retrieval pipeline that handles the unique characteristics of legal content.

**Key insight**: Tax Guru provides generic research answers. Clairo can provide **client-contextual** answers grounded in the same knowledge but enriched with the client's actual Xero financial data. This is fundamentally more valuable.

**Research Document**: `research.md` -- comprehensive source analysis, legal RAG best practices, embedding benchmarks, copyright analysis.

---

## User Scenarios & Testing

### User Story 1 - Tax Research Without Client Context (Priority: P1)

An accountant asks a general tax question (e.g., "What are the Division 7A rules for loans from private companies?") via the knowledge chatbot. The system retrieves relevant legislation sections, ATO rulings, and guidance, then provides a comprehensive answer with numbered citations linking to specific sources.

**Why this priority**: This is the direct Tax Guru competitor feature. Accountants need authoritative tax research answers without necessarily selecting a client first.

**Independent Test**: Ask "What are the Div 7A rules?" and verify the response cites specific ITAA 1936 sections (s109D-109N), relevant TRs/TDs, and includes effective dates.

**Acceptance Scenarios**:

1. **Given** the knowledge base contains ITAA 1936 Division 7A sections and related ATO rulings, **When** an accountant asks "What are the Division 7A rules for loans?", **Then** the response cites specific legislation sections (s109D, s109E, s109N) with their text, relevant rulings (TR/TD), and current benchmark interest rate.

2. **Given** a query about GST registration thresholds, **When** the accountant asks "When does a business need to register for GST?", **Then** the response cites the GST Act 1999, current $75K threshold, and links to ATO guidance, with effective date noted.

3. **Given** a query mentioning a superseded ruling, **When** the system retrieves a superseded TR, **Then** the response flags it as superseded and directs to the current ruling.

4. **Given** a query the knowledge base cannot adequately answer (top retrieval score < 0.5), **When** the system generates a response, **Then** it declines with "I don't have sufficient information in my knowledge base" rather than hallucinating.

---

### User Story 2 - Client-Contextual Tax Research (Priority: P1)

An accountant selects a client and asks a tax question. The system combines knowledge base retrieval with the client's financial data to provide a contextual answer. For example: "Does this client have a Div 7A issue?" produces an answer that references both the legislation AND the client's actual loan balances from Xero.

**Why this priority**: This is Clairo's key differentiator over Tax Guru. Generic answers are a commodity; client-specific answers are the moat.

**Independent Test**: Select a client with shareholder loans visible in Xero, ask about Div 7A, and verify the response references both the legislation and the client's specific loan amounts.

**Acceptance Scenarios**:

1. **Given** a client with Xero data showing a $150K shareholder loan, **When** the accountant asks "Does this client have a Div 7A issue?", **Then** the response identifies the specific loan, cites s109D ITAA 1936, calculates the minimum yearly repayment at the current benchmark rate, and cites the source for the benchmark rate.

2. **Given** a client's P&L showing $80K revenue, **When** the accountant asks "Does this client need to register for GST?", **Then** the response notes revenue exceeds the $75K threshold, cites the GST Act, and recommends registration.

3. **Given** a client with fixed assets, **When** the accountant asks "What can we write off this year?", **Then** the response identifies qualifying assets from Xero data, cites the instant asset write-off threshold from current legislation, and calculates the total deduction.

---

### User Story 3 - Specialist Tax Modules (Priority: P2)

The knowledge chatbot routes queries to specialist knowledge domains based on topic detection. The system presents itself with specialist expertise areas (e.g., GST, SMSF, CGT, Division 7A, FBT, Trusts) that accountants can browse or that are automatically selected based on query analysis.

**Why this priority**: Tax Guru's 17 specialist "Gurus" is a compelling UX pattern that makes AI capabilities discoverable. Clairo should match this with specialist routing backed by domain-partitioned knowledge.

**Independent Test**: Ask a CGT-specific question and verify the response draws primarily from CGT-related legislation (ITAA 1997 Part 3-1) and CGT-specific rulings.

**Acceptance Scenarios**:

1. **Given** the knowledge base is populated with domain-tagged content, **When** an accountant asks a GST question, **Then** the retrieval prioritises content tagged with `topic_tags` containing "GST" and searches the `compliance_knowledge` namespace with appropriate filters.

2. **Given** the system has specialist domains configured, **When** the accountant browses the chat interface, **Then** they can see available specialist areas (GST, CGT, SMSF, FBT, Div 7A, Trusts, Super, Payroll, International Tax) and optionally select one to focus the conversation.

3. **Given** a specialist domain is selected, **When** the accountant asks a question, **Then** retrieval is scoped to that domain's legislation, rulings, and guidance, producing more precise answers.

---

### User Story 4 - Legislation Section Lookup (Priority: P1)

An accountant queries a specific legislation section (e.g., "What does section 109D say?") and receives the exact text of that section with contextual information (parent division, related sections, definitions of terms used).

**Why this priority**: Direct section lookup is the most common use case for tax professionals. The system must handle exact reference queries, not just conceptual questions.

**Independent Test**: Ask "What does s104-10 ITAA 1997 say?" and verify the response returns the exact section text, identifies it as CGT Event A1, and notes related sections.

**Acceptance Scenarios**:

1. **Given** legislation sections are indexed with section-level metadata, **When** an accountant asks "What does section 109D say?", **Then** the system performs keyword-heavy retrieval, finds the exact section, and returns its full text with the act reference and effective date.

2. **Given** a section uses defined terms, **When** the section is retrieved, **Then** key defined terms are either explained inline or available via a definitions panel.

3. **Given** a section cross-references other sections, **When** the section is returned, **Then** cross-referenced sections are listed and optionally retrievable.

---

### User Story 5 - Knowledge Base Freshness & Monitoring (Priority: P2)

The system automatically monitors ATO RSS feeds and the Federal Register of Legislation for new or updated rulings and legislation amendments. New content is ingested within 24 hours of publication. Superseded rulings are automatically detected and marked.

**Why this priority**: Tax law changes frequently. Stale knowledge is worse than no knowledge -- it can lead to incorrect advice.

**Independent Test**: Verify that a ruling published this week appears in the knowledge base within 24 hours, and that a superseded ruling is marked appropriately.

**Acceptance Scenarios**:

1. **Given** the ATO publishes a new TR at 2:00 PM AEDT on Wednesday, **When** the scheduled ingestion job runs, **Then** the ruling is chunked, embedded, and searchable within 24 hours.

2. **Given** the ATO supersedes TR 2024/X with TR 2026/Y, **When** the ingestion job processes TR 2026/Y, **Then** TR 2024/X is marked as `is_superseded=True` with `superseded_by="TR 2026/Y"`.

3. **Given** a legislation amendment is published on legislation.gov.au, **When** the weekly legislation sync runs, **Then** affected sections are re-ingested with updated `compilation_date` and `content_hash`.

4. **Given** the admin dashboard, **When** an admin views knowledge base status, **Then** they see last ingestion time per source, total chunks per namespace, and any ingestion errors.

---

### User Story 6 - Citation Verification & Trust (Priority: P1)

Every AI-generated tax research answer includes verifiable citations. Citations reference specific legislation sections, ruling numbers, or case citations that exist in the knowledge base. The system never fabricates references.

**Why this priority**: Tax Guru's key marketing pitch is "no hallucinations, expert-verified." Clairo must match or exceed this with architectural guarantees, not manual curation.

**Independent Test**: Ask 10 different tax questions and verify that every citation in every response corresponds to an actual document in the knowledge base.

**Acceptance Scenarios**:

1. **Given** the LLM generates a response citing "s109D ITAA 1936", **When** post-generation verification runs, **Then** the system confirms s109D was in the retrieved context and the citation is valid.

2. **Given** the LLM generates a response citing a ruling number, **When** post-generation verification runs, **Then** the system confirms the ruling exists in the knowledge base with matching content.

3. **Given** the LLM attempts to cite a section NOT in the retrieved context, **When** post-generation verification runs, **Then** the ungrounded citation is flagged or removed, and a disclaimer is added.

4. **Given** any response with citations, **When** the accountant clicks a citation, **Then** they see the source document title, URL, relevant text excerpt, effective date, and confidence score.

---

## Technical Design

### Phase 1: Content Ingestion Pipeline (P0)

#### 1.1 New Scrapers

**Legislation Scraper** (`scrapers/legislation_gov.py`):
- Fetch EPUB files from legislation.gov.au via predictable URL patterns
- Parse EPUB HTML (BeautifulSoup) to extract sections with TOC anchors
- Fallback: ATO Legal Database section-level URLs for granular access
- Respect 10-second crawl delay for legislation.gov.au
- Store with hierarchical metadata (act, part, division, subdivision, section)
- Track compilation numbers for amendment detection

**Case Law Ingester** (`scrapers/case_law.py`):
- Download Open Australian Legal Corpus from HuggingFace (JSONL, one-time)
- Filter for tax-relevant cases (keyword/NLP classification)
- Parse Federal Court RSS for ongoing updates
- Chunk by semantic section (headnote, facts, reasoning, orders)
- Store with case metadata (citation, court, date, legislation considered)

**Enhanced ATO Scraper** (`scrapers/ato_legal_db.py`):
- Extend existing ATO scrapers to cover all 12 content categories
- Use print URL pattern: `/law/view/print?DocID={docid}&PiT=99991231235958`
- Enumerate DocIDs by prefix pattern (TXR, TXD, GST, CLR, PRR, COG, TPA, AID, PSR, SRB, SAV)
- Parse ruling structure (Ruling section, Explanation, Examples, Date of Effect)
- Extract ruling status, supersession info, related legislation

**TPB/Treasury Scraper** (`scrapers/tpb_treasury.py`):
- Scrape TPB information products (HTML pages)
- Download Treasury exposure drafts (PDF processing via existing document_processor)

#### 1.2 Structure-Aware Chunker

Extend existing `chunker.py` with content-type-specific chunking:

```python
class LegislationChunker:
    """Chunks legislation along natural hierarchical boundaries."""
    # Primary boundary: section level (256-512 tokens)
    # Split at subsection only for very long sections
    # Never split mid-paragraph
    # Prefix every chunk with section number and heading

class RulingChunker:
    """Chunks ATO rulings by structural sections."""
    # Keep "Ruling" section as single chunk
    # Split "Explanations" by numbered paragraph
    # Preserve ruling number in every chunk

class CaseLawChunker:
    """Chunks court decisions by semantic section."""
    # Headnote as single high-priority chunk
    # Reasoning by issue/numbered paragraph
    # Orders as single chunk
```

#### 1.3 Metadata Enrichment

During ingestion, automatically extract and tag:
- Cross-references to other sections/rulings (regex extraction)
- Defined terms used (match against definitions index)
- Topic classification (rule-based + LLM-assisted for ambiguous content)
- Entity type applicability (company, trust, sole trader, partnership)
- Financial year applicability
- Ruling lifecycle status (draft, current, withdrawn, superseded)

#### 1.4 Content Freshness Pipeline

```
Scheduled Jobs (Celery Beat):
├── ATO RSS Monitor (6x daily) → detect new rulings → trigger ingestion
├── ATO Legal DB Delta Crawl (weekly) → detect updated/new documents
├── Legislation.gov.au Sync (monthly) → detect amended acts
├── Federal Court RSS (daily) → ingest new tax judgments
└── Supersession Check (weekly) → mark superseded rulings
```

### Phase 1.5: Ingestion Reliability & Data Organisation (P0)

This section addresses critical infrastructure concerns discovered during analysis of the existing ingestion pipeline.

#### 1.5.1 Idempotent Ingestion (Fix Existing Gaps)

**Current problem**: Dedup checks only the first chunk's content hash. If a document's first 1500 chars are unchanged but later content is modified, the update is silently skipped. If the first chunk changes, all chunks are re-inserted as new rows — old chunks and Pinecone vectors become orphans with no cleanup.

**Solution — Document-Level Idempotency**:

```
For each source document:
  1. Compute SHA-256 of ENTIRE raw content (before chunking)
  2. Look up by natural key:
     - Legislation: (act_id, section_ref, compilation_date)
     - Rulings: (ruling_number)
     - Case law: (case_citation)
     - Other: (source_url)
  3. If exists AND content_hash unchanged → SKIP (true idempotency)
  4. If exists AND content_hash changed → REPLACE:
     a. Delete old Pinecone vectors by stored IDs
     b. Delete old ContentChunk rows
     c. Delete old BM25IndexEntry rows
     d. Re-chunk, re-embed, re-insert (new vectors, new rows)
  5. If not exists → INSERT (new document)
```

**Deterministic Vector IDs**: Instead of random UUID4s for Pinecone vector IDs, derive them from content identity:
- Format: `{source_type}:{natural_key}:{chunk_index}`
- Example: `legislation:s109D-ITAA1936:0`, `ruling:TR2024-1:3`
- This makes Pinecone upserts naturally idempotent — re-upserting the same ID overwrites the old vector.

**ContentChunk tracking**: Add `document_hash` column (hash of full source document, not individual chunk) alongside existing `content_hash` (hash of individual chunk text). The `document_hash` is what we compare for change detection.

#### 1.5.2 Resilient Scraping

**Circuit Breaker**: Per-source circuit breaker to avoid hammering failing sites:
```python
class ScraperCircuitBreaker:
    """Trips after N consecutive failures per source host."""
    failure_threshold: int = 5         # Trip after 5 consecutive failures
    recovery_timeout: int = 3600       # Wait 1 hour before retrying
    half_open_max_requests: int = 2    # Test with 2 requests before fully opening
```

**Site-Specific Rate Limits**: Configure per scraper, not global:
- `legislation.gov.au`: 10-second delay (required by robots.txt)
- ATO Legal Database: 2-second delay (polite crawling)
- Federal Court RSS: standard (RSS feed, no rate limit concern)
- HuggingFace dataset: no rate limit (one-time download)

**Checkpoint/Resume for Large Ingestion Jobs**:
```
Each ingestion job tracks:
  - job_id: UUID
  - total_items: int (known upfront or incremented)
  - completed_items: list[str]  # source_urls or doc_ids successfully ingested
  - failed_items: list[{url, error, attempt_count}]
  - status: pending | running | paused | completed | failed

On retry/resume:
  - Skip items already in completed_items
  - Re-attempt items in failed_items (up to max_retries per item)
  - New items discovered since last run are added
```

**Atomic Per-Document Ingestion**: Each document's ingestion is an atomic unit:
1. Chunk the document
2. Embed all chunks
3. Upsert all vectors to Pinecone
4. Insert all ContentChunk rows + BM25IndexEntry rows in a single DB transaction
5. If any step fails, none persist (Pinecone upserts are idempotent via deterministic IDs, so partial upserts are safe to retry)

**Stale Content Grace Period**: If a source is temporarily unreachable:
- Keep existing content in the knowledge base
- Set `last_verified_at` timestamp on the source
- Flag as "stale" only after configurable period (7 days for rulings, 30 days for legislation)
- Never auto-delete content due to scraping failures

#### 1.5.3 Pinecone Metadata Strategy

**Problem**: The existing chatbot retrieval uses zero metadata filters — it's pure similarity search. For legal content, this means a GST question might return income tax results, superseded rulings appear alongside current ones, and section lookups produce conceptual matches instead of exact matches.

**Solution — Metadata fields stored per Pinecone vector**:

| Field | Type | Purpose | Filtered By |
|-------|------|---------|-------------|
| `text` | string | Chunk text for display | — |
| `source_type` | string | "legislation", "ato_ruling", "case_law", etc. | Query router (CASE_LAW type) |
| `content_type` | string | "operative_provision", "definition", "ruling", "headnote", "reasoning" | Query router (definition lookups) |
| `section_ref` | string | "s109D ITAA 1936", "TR 2024/1 para 15" | SECTION_LOOKUP queries, exact match |
| `ruling_number` | string | "TR 2024/1", "GSTR 2000/1" | RULING_LOOKUP queries, exact match |
| `topic_tags` | list[string] | ["GST", "BAS", "input_tax_credit"] | Domain scoping, specialist modules |
| `entity_types` | list[string] | ["company", "trust"] | Entity-type filtering |
| `is_superseded` | boolean | Whether content has been superseded | Always filter out by default |
| `effective_date` | string | ISO date | FY-applicable filtering |
| `court` | string | "HCA", "FCA", "FCAFC", "AATA" | Case law filtering |
| `case_citation` | string | "[2010] HCA 10" | Case law exact match |
| `confidence_level` | string | "high", "medium", "low" | Boost high-confidence results |
| `_collection` | string | Base namespace name | Internal routing |
| `document_hash` | string | Full document hash for dedup | Internal |

**Namespace Strategy**: All legal content (legislation, rulings, case law) goes into the existing `compliance_knowledge` namespace. No new namespaces. Metadata filters handle the differentiation. This keeps the retrieval pipeline simple — one namespace to search for all tax knowledge, with filters narrowing results.

**Filter Application by Query Type**:

```
SECTION_LOOKUP:
  - Filter: section_ref exact match (try first)
  - Fallback: hybrid search with section_ref in BM25 query
  - Always: is_superseded != true

RULING_LOOKUP:
  - Filter: ruling_number exact match
  - Always: is_superseded != true

CONCEPTUAL (e.g., "What are Div 7A rules?"):
  - Filter: topic_tags $in detected_tags (if domain detected)
  - Filter: is_superseded != true
  - No source_type filter (return legislation + rulings + guidance)

CASE_LAW:
  - Filter: source_type = "case_law"
  - Optional: court filter if specified

DOMAIN-SCOPED (e.g., user selected GST Guardian):
  - Filter: topic_tags $in domain.topic_tags
  - Filter: is_superseded != true
```

#### 1.5.4 BM25 Index Strategy

The BM25 index (`bm25_index_entries` table) serves two purposes:
1. **Keyword scoring** for hybrid search (combined with semantic via RRF)
2. **Exact-match retrieval** for section/ruling references

**Tokenization**: Pre-tokenize chunk text during ingestion. Store tokens as JSONB array. Include:
- Lowercased words
- Section references preserved as atomic tokens (e.g., "s109d" not split into "s" + "109" + "d")
- Ruling numbers preserved (e.g., "tr2024/1" as single token)
- Legal stop words removed (standard stop words minus legal terms like "shall", "must", "may")

**Section Reference Extraction**: Parse and store normalised section/ruling references in `section_refs` JSONB field. This enables direct lookup without full BM25 scoring:
```
"s109D" → normalise to "s109d-itaa1936"
"TR 2024/1" → normalise to "tr-2024-1"
"Division 7A" → normalise to "div-7a-itaa1936"
```

### Phase 2: Enhanced Retrieval (P0)

#### 2.1 Hybrid Search

Add BM25 scoring alongside vector search:
- Option A: Pinecone sparse vectors (if available in current plan)
- Option B: Separate BM25 index using `rank-bm25` Python library
- Reciprocal Rank Fusion (RRF) to combine dense + sparse scores
- Default fusion: 0.6 semantic / 0.4 keyword
- Dynamic adjustment based on query type (section lookup = 0.2/0.8)

#### 2.2 Cross-Encoder Re-ranking

Post-retrieval re-ranking pipeline:
- Initial retrieval: top 30 candidates from hybrid search
- Re-rank with `cross-encoder/ms-marco-MiniLM-L-6-v2`
- Return top 10 for context assembly
- Expected improvement: 15-25% retrieval precision

#### 2.3 Legal Query Router

Extend `intent_detector.py` with legal query classification:

| Query Type | Detection | Retrieval Strategy |
|-----------|-----------|-------------------|
| `SECTION_LOOKUP` | Regex: section/division patterns | Keyword-heavy (0.2/0.8) |
| `RULING_LOOKUP` | Regex: TR/GSTR/TD/PCG patterns | Keyword on ruling_number |
| `CONCEPTUAL` | No specific references | Semantic-heavy (0.7/0.3) + expansion |
| `PROCEDURAL` | Action verbs + process terms | Standard hybrid; filter to guides |
| `SCENARIO` | Factual client scenario | Semantic + expansion; multi-source |
| `CASE_LAW` | Court/case/tribunal terms | Filter to case law chunks |

#### 2.4 Query Expansion

LLM-assisted expansion for conceptual/scenario queries:
- Expand tax concepts to include section numbers, related terms
- Legal synonym table (GST <-> Goods and Services Tax <-> GST Act 1999)
- Multi-query retrieval for complex scenarios (2-3 variant queries, merge results)

#### 2.5 Definitions Auto-Injection

When retrieved chunks use defined terms:
- Match against definitions index (standalone definition chunks)
- Inject top 2-3 most relevant definitions into context
- Budget-aware: definitions consume token allocation from Tier 1

### Phase 3: Hallucination Prevention (P0)

#### 3.1 Grounding Enforcement

System prompt for tax research mode:
```
Answer ONLY based on the provided knowledge base context.
If the context does not contain sufficient information, say
"I don't have enough information in my knowledge base to answer
this with confidence. Please consult the relevant legislation
directly or contact the ATO."
Do NOT use your training data to supplement answers about
specific legal provisions, thresholds, or rates.
```

#### 3.2 Post-Generation Citation Verification

After LLM generates response:
1. Extract all section/ruling references via regex
2. Cross-reference against chunks in retrieved context
3. For each citation: verify the referenced document exists in context
4. Ungrounded citations: remove or flag with disclaimer
5. Assign confidence score: `0.4 * top_score + 0.3 * mean_top5 + 0.3 * citation_verified_rate`

#### 3.3 Response Confidence Tiers

| Confidence | Behaviour |
|-----------|-----------|
| High (> 0.7) | Answer with citations, standard disclaimer |
| Medium (0.5-0.7) | Answer with caveats: "Based on available information..." |
| Low (< 0.5) | Decline: "I don't have sufficient information..." |
| Superseded content | Always flag: "Note: This ruling has been superseded by..." |

### Phase 4: Specialist Domains (P2)

#### 4.1 Domain Configuration

Define specialist tax domains with scoped retrieval:

```python
TAX_DOMAINS = {
    "gst": {
        "name": "GST Guardian",
        "description": "GST registration, BAS reporting, input tax credits",
        "topic_tags": ["GST", "BAS", "input_tax_credit", "taxable_supply"],
        "legislation": ["GST Act 1999"],
        "ruling_types": ["GSTR", "GSTD"],
    },
    "division_7a": {
        "name": "Division 7A Advisor",
        "description": "Private company loans, payments, forgiven debts",
        "topic_tags": ["division_7a", "loans", "private_company", "deemed_dividend"],
        "legislation": ["ITAA 1936 Part III Div 7A"],
        "ruling_types": ["TR", "TD", "PCG"],
    },
    # ... CGT, SMSF, FBT, Trusts, Super, Payroll, International
}
```

#### 4.2 Specialist Chat UX

- Chat interface shows available specialist domains as selectable chips/cards
- Auto-detection: system identifies domain from query and shows "Routing to GST Guardian"
- Scoped retrieval: when domain selected, filter retrieval to domain's tags + legislation
- Domain-specific system prompts for deeper expertise

### Phase 5: Embedding Model Evaluation (P3)

Benchmark current Voyage 3.5 lite against:
- **Kanon 2 Embedder** (Australian-made, #1 on MLEB, 86.03% NDCG@10)
- **Voyage 3 Large** (85.71% NDCG@10)

Create test set of 100 Australian tax QA pairs. Measure retrieval precision at k=5 and k=10. If Kanon 2 shows >5% improvement, migrate embeddings.

---

## Data Model Changes

### New Models

```python
class LegislationSection(Base):
    """Tracks ingested legislation sections for cross-referencing."""
    id: UUID
    act_id: str           # e.g., "C2004A05138"
    act_name: str         # e.g., "ITAA 1997"
    section_ref: str      # e.g., "s104-10"
    part: str | None
    division: str | None
    subdivision: str | None
    heading: str | None
    content_hash: str     # SHA-256 for change detection
    compilation_date: date
    chunk_ids: list[UUID] # Links to ContentChunk records
    cross_references: list[str]  # ["s104-5", "s110-25"]
    defined_terms: list[str]     # ["CGT asset", "capital proceed"]
    created_at: datetime
    updated_at: datetime

class TaxDomain(Base):
    """Specialist tax domain configuration."""
    id: UUID
    slug: str             # e.g., "gst", "division_7a"
    name: str             # e.g., "GST Guardian"
    description: str
    topic_tags: list[str]
    legislation_refs: list[str]
    ruling_types: list[str]
    icon: str | None
    display_order: int
    is_active: bool
```

### Extended ContentChunk Metadata

Add to existing `ContentChunk` model:

```python
# New columns
content_type: str | None    # "operative_provision", "definition", "example", "headnote", "reasoning"
section_ref: str | None     # "s104-10 ITAA 1997"
cross_references: list[str] # JSONB: ["s104-5", "Div 115"]
defined_terms_used: list[str]  # JSONB: ["CGT asset"]
topic_tags: list[str]       # JSONB: ["CGT", "disposal"]
fy_applicable: list[str]    # JSONB: ["2025", "2026"]
court: str | None           # For case law: "HCA", "FCA", "FCAFC"
case_citation: str | None   # "[2010] HCA 10"
```

### Cross-Reference Table

```python
class ContentCrossReference(Base):
    """Links between content chunks for graph traversal."""
    id: UUID
    source_chunk_id: UUID   # FK -> ContentChunk
    target_section_ref: str # e.g., "s109D ITAA 1936"
    target_chunk_id: UUID | None  # FK -> ContentChunk (resolved)
    reference_type: str     # "cites", "defines", "supersedes", "amends"
    created_at: datetime
```

---

## API Changes

### New Endpoints

```
# Specialist domains
GET  /api/v1/knowledge/domains           → List active tax domains
GET  /api/v1/knowledge/domains/{slug}    → Get domain details

# Enhanced search
POST /api/v1/knowledge/search            → Search with hybrid retrieval
  body: { query, domain?, filters?, limit? }

# Legislation lookup
GET  /api/v1/knowledge/legislation/{section_ref}  → Get specific section
  e.g., /legislation/s109D-ITAA1936

# Admin: ingestion management
POST /api/v1/admin/knowledge/ingest/legislation   → Trigger legislation sync
POST /api/v1/admin/knowledge/ingest/case-law      → Trigger case law ingestion
GET  /api/v1/admin/knowledge/freshness             → Content freshness report
POST /api/v1/admin/knowledge/verify-citations      → Run citation audit
```

### Modified Endpoints

```
# Existing chat endpoints gain domain scoping
POST /api/v1/knowledge/chat
  body: { ...existing, domain?: string }

POST /api/v1/queries/chat
  body: { ...existing, domain?: string }
```

---

## Frontend Changes

### Knowledge Chat Enhancements

- **Domain selector**: Horizontal chip bar above chat input showing specialist domains (GST, CGT, SMSF, Div 7A, FBT, etc.)
- **Auto-routing indicator**: "Searching GST legislation and rulings..." during retrieval
- **Enhanced citations panel**: Click citation to see source text, legislation section, effective date, URL
- **Confidence indicator**: Subtle confidence badge on responses (high/medium/low)
- **Supersession warnings**: Yellow banner when response references superseded content

### Admin Knowledge Dashboard

- **Source status table**: Each source (ATO, legislation, case law) with last sync, chunk count, error count
- **Freshness indicators**: Green/yellow/red based on time since last successful sync
- **Ingestion log**: Recent jobs with success/failure details
- **Coverage metrics**: Chunks per domain, per content type
- **Citation audit results**: % of citations verified in recent responses

---

## Dependencies

| Dependency | Purpose | Status |
|-----------|---------|--------|
| Spec 012 (Knowledge Base) | Core RAG infrastructure | COMPLETE |
| Spec 044 (Evidence Traceability) | Citation system, data snapshots | Phase 1 COMPLETE |
| Pinecone | Vector store | In production |
| Voyage API | Embeddings | In production |
| Celery + Redis | Background ingestion jobs | In production |
| BeautifulSoup | HTML/EPUB parsing | Already installed |
| rank-bm25 | BM25 scoring (new dependency) | NEW |
| sentence-transformers | Cross-encoder re-ranking (new dependency) | NEW |

---

## Phased Delivery

| Phase | Scope | Priority | Effort | Dependencies |
|-------|-------|----------|--------|-------------|
| 1 | ATO Legal Database full crawl (all ruling types) | P0 | 1 week | Spec 012 |
| 2 | Legislation ingestion (key tax acts via EPUB + ATO section URLs) | P0 | 1 week | Phase 1 |
| 3 | Hybrid search + cross-encoder re-ranking | P0 | 3-4 days | Phase 1 |
| 4 | Legal query router + query expansion | P0 | 2-3 days | Phase 3 |
| 5 | Citation verification + confidence scoring | P0 | 2-3 days | Phase 3 |
| 6 | Case law ingestion (Open Australian Legal Corpus + Federal Court RSS) | P1 | 3-4 days | Phase 1 |
| 7 | Specialist domains (config, routing, frontend) | P2 | 3-4 days | Phase 4 |
| 8 | Content freshness pipeline (scheduled jobs, RSS monitoring) | P1 | 2-3 days | Phase 1 |
| 9 | Definitions index + auto-injection | P2 | 2 days | Phase 2 |
| 10 | Embedding model evaluation (Kanon 2 benchmark) | P3 | 2 days | Phase 1 |

**Total estimated effort**: ~5-6 weeks

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Knowledge base coverage | >80,000 chunks across all sources | Pinecone vector count |
| Retrieval precision @5 | >85% (vs current ~70% est.) | Manual evaluation on 100 QA pairs |
| Citation accuracy | >95% verified citations | Post-generation verification audit |
| Hallucination rate | <5% | Manual review of 100 random responses |
| Query latency (p95) | <2 seconds (retrieval + generation) | Application metrics |
| Content freshness | <24 hours for new ATO rulings | Time delta: ATO publish → searchable |
| Domain coverage | 9+ specialist domains | Configuration count |
| Accountant satisfaction | >4/5 trust rating | In-app feedback on responses |

---

## Competitive Impact

| Capability | Tax Guru | Clairo (After This Spec) |
|-----------|----------|--------------------------|
| Knowledge breadth | 18,000 articles (curated) | ~80,000+ chunks (legislation + rulings + cases) |
| Specialist domains | 17 "Gurus" | 9+ specialist domains |
| Source authority | Expert-verified rewrites | Primary sources (ATO, legislation, courts) |
| Client context | None | Full Xero financial data integration |
| Citation quality | Links to articles | Links to specific legislation sections + rulings |
| Freshness | "500+ weekly updates" | <24 hour automated ingestion |
| Hallucination prevention | Manual curation | Architectural (retrieval-grounded + verification) |
| Price | $4,500/18 months | Included in $99-$599/mo subscription |

---

## Attribution Requirements

All responses using knowledge base content must include appropriate attribution:

- **ATO content**: No specific attribution required (free to copy/adapt), but must not imply ATO endorsement
- **Legislation**: "Based on content from the Federal Register of Legislation at [date]. For the latest information please go to https://www.legislation.gov.au"
- **Court judgments**: Reproduce in unaltered form with attribution to the court
- **Open Australian Legal Corpus**: CC BY 4.0 attribution to dataset

Attribution can be displayed in a collapsible "Sources" footer on each response.

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| ATO changes URL patterns | Ingestion breaks | Monitor ingestion errors, alert on >10% failure rate, fallback to sitemap crawl |
| Legislation.gov.au rate limiting | Slow ingestion | Respect 10s crawl delay, cache EPUBs, incremental updates only |
| Stale content causes incorrect advice | Professional liability | Freshness pipeline, compilation date on every response, "as at [date]" disclaimers |
| Hallucination despite grounding | Trust erosion | Citation verification, confidence scoring, decline for low-confidence queries |
| Embedding model switch cost | Re-embedding entire corpus | Only switch if benchmark shows >5% improvement; budget ~$8 for re-embedding |
| AAT/ART case law gap | Incomplete case coverage | Seek direct ART permission; use JADE free tier for individual cases; mark gap transparently |
