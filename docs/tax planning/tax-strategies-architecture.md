# Tax Strategies Knowledge Base — Architecture & Solution Guide

**Clairo · April 2026 · Design pass before build**

Paired brief: `specs/briefs/2026-04-18-tax-strategies-knowledge-base.md`
Deliverable (shareable): `/Users/suren/Documents/Claude/Projects/Clairo/clairo-tax-strategies-architecture.docx`

---

## 1. Summary

This document specifies how Clairo will ingest, store, retrieve and cite a reauthored Australian tax strategies library (the `tax_strategies` namespace) as part of the existing knowledge module. It is designed to fit the current Pinecone + hybrid retrieval stack, the existing admin UI under `/admin/knowledge`, the current citation verification pipeline, and the tax planning module's retrieval hook. Coverage target is 415 strategies across 8 categories (mirroring the Tax Fitness blueprint). Content is written fresh from ATO primary sources and reviewed by a qualified Australian tax practitioner; no proprietary content is ingested.

This is a design-pass document. It is written to let Asaf implement without re-reading the existing code path-by-path, and to let Suren validate the approach end-to-end before any build starts.

---

## 2. Context & goals

Clairo's first live tax planning session (Zac/OreScope, 2026-04-18) surfaced several trust bugs, most severe of which were unverified citations (F1-14) and AI strategy suggestions pulled from general model knowledge rather than grounded material (F1-7, F1-12). Unni then shared the Tax Fitness strategy library (415 entries, STP-branded) as a reference for how accountants already think about strategy coverage. We have decided to reauthor an equivalent, Clairo-owned corpus covering the same topics, with the following constraints agreed with Suren:

- Tax-law facts and thresholds are preserved verbatim (they are ATO law, not STP IP).
- Category taxonomy and coverage are mirrored 1:1 (8 groups, 415 strategies, multi-tag model, 4-section shape after dropping the indicative $ figure).
- Prose wording, structure and implementation steps are written fresh from ATO primary sources. No reading-and-paraphrasing from the STP PDFs.
- Clairo-owned strategy IDs (CLR-001 … CLR-415). The STP source reference is carried internally as metadata only, never surfaced.
- Phased rollout — top ~100 highest-frequency strategies first (alpha/beta backbone), ~250 more in phase 2, long tail thereafter.
- Unni acts as the paid tax reviewer. No content is published without his sign-off.

Design goals for the retrieval system:

- **Trust**: every AI claim traceable to a specific strategy entry (and the ATO source behind it).
- **Recall**: hit-rate on plausible accountant and client-context queries ≥ 90% for top-100 coverage. Pure semantic search is not sufficient; metadata pre-filtering + hybrid retrieval + query expansion are the levers.
- **Precision**: top-5 reranked results should be the strategies a tax accountant would actually cite in the scenario.
- **Operability**: admin surfaces that follow the existing `/admin/knowledge` pattern.
- **Tenant-ready**: platform-baseline corpus today, per-tenant private overlay possible later without refactor.

---

## 3. Existing architecture — what we build on

### 3.1 Vector store and embeddings

- Single Pinecone index `clairo-knowledge` (1024 dim, cosine), configured in `backend/app/core/pinecone_service.py`.
- Embeddings: Voyage 3.5 lite (1024 dims), via `VoyageService`.
- Namespaces declared in `backend/app/modules/knowledge/collections.py` via `NAMESPACES` dict. Shared namespaces (e.g. `compliance_knowledge`) have no environment suffix; non-shared (e.g. `insight_dedup`) get `_dev` / `_prod` suffix.

### 3.2 Data model

- Postgres model `ContentChunk` in `app/modules/knowledge/models.py` is the authoritative record of each chunk, with rich metadata (content_type, section_ref, cross_references, defined_terms_used, topic_tags, fy_applicable, entity_types, industries, natural_key, document_hash, is_superseded).
- Field `qdrant_point_id` on ContentChunk is the Pinecone vector ID (migration artefact — don't rename).
- Related tables: `KnowledgeSource`, `IngestionJob`, `LegislationSection`, `ContentCrossReference`, `TaxDomain`, `BM25IndexEntry`.

### 3.3 Retrieval pipeline

- Entry point: `KnowledgeService.search_knowledge()` in `app/modules/knowledge/service.py` (lines 90–267).
- Query classification via `QueryRouter.classify()` in `retrieval/query_router.py` — returns QueryType (SECTION_LOOKUP / RULING_LOOKUP / CONCEPTUAL / PROCEDURAL / SCENARIO / CASE_LAW), fusion weights, pinecone filter.
- Hybrid: `HybridSearchEngine.hybrid_search()` in `retrieval/hybrid_search.py` — semantic over Pinecone + BM25 (in-memory, hydrated from `BM25IndexEntry`) + RRF fusion.
- Query expansion: `QueryExpander.expand_query()` in `retrieval/query_expander.py` — skipped for SECTION/RULING lookups; expands CONCEPTUAL/SCENARIO into synonyms + related concepts.
- Cross-encoder rerank: `retrieval/reranker.py` with `ms-marco-MiniLM-L-6-v2` on top 30 candidates → top 10.
- Domain scoping: `DomainManager` maps auto-detected domain slug (e.g. `division_7a`, `cgt`, `smsf`) to DB-backed filter sets.

### 3.4 Citations

- `ChatMessage.citations` stores `[{number, title, url, source_type, score}]`. `CitationVerifier` (retrieval/citation_verifier.py) extracts `[Source: ...]` patterns, matches against retrieved chunks by section ref or body text.
- Tax planning builds a verification summary via `TaxPlanningService._build_citation_verification()` (service.py 1283–1349) — counts + per-citation status.
- Frontend renders via `CitationBadge` (frontend/src/components/tax-planning/CitationBadge.tsx) — green/amber/red badge reflecting overall verification.

### 3.5 Admin UI

- Root: `/frontend/src/app/(protected)/admin/knowledge/page.tsx` — Clerk super_admin gate, tab layout.
- Existing tabs: Ingestion, Collections, Search Test, Sources, Jobs. Components in `admin/knowledge/components/`.
- Hooks: `use-sources.ts`, `use-collections.ts`, `use-jobs.ts`, `use-search-test.ts`.
- shadcn/ui patterns: Table for lists, Dialog/Sheet for forms, Badge for status, Alert for feedback.

### 3.6 Tax planning hook point

`TaxPlanningService._retrieve_tax_knowledge()` (service.py 1201–1281) currently calls `KnowledgeService.search_knowledge()` with an entity_type-derived filter and `exclude_superseded=True`. Limit is 8, top 5 returned. This is where tax_strategies retrieval plugs in.

---

## 4. Proposed design — additive, minimally invasive

The design adds one new Pinecone namespace, one new module (tax_strategies) for parent documents and authoring pipeline, a set of nullable columns on ContentChunk for strategy-specific metadata, and one new admin tab. It reuses the hybrid retrieval stack, the Celery-based ingestion pattern, the citation verifier, and the CitationBadge component. No existing table schema is broken; no existing retrieval call signature changes without a default that preserves current behaviour.

High-level additions:

- **Namespace**: `tax_strategies` (shared=true) in NAMESPACES dict.
- **Parent document**: new module `backend/app/modules/tax_strategies/` with model TaxStrategy. ContentChunk rows for the strategy point back via new FK `tax_strategy_id`.
- **Chunking**: two child chunks per strategy (implementation + explanation) with contextual headers and keyword tails; full parent returned to LLM.
- **Retrieval**: KnowledgeSearchRequest extended with optional `namespaces: list[str]` and structured eligibility filters. Tax planning call passes `namespaces=["compliance_knowledge", "tax_strategies"]`.
- **Citations**: `[CLR-241: Change PSI to PSB]` markup convention; CitationVerifier extended; CitationBadge extended with per-citation clickable chips.
- **Admin UI**: new "Strategies" tab in `/admin/knowledge` with list, detail/edit view, authoring-pipeline dashboard.
- **Content pipeline**: new Celery tasks for each authoring stage, new table `tax_strategy_authoring_jobs` modelled on `IngestionJob`.

---

## 5. Data model

### 5.1 New table: `tax_strategies`

Parent document record. One row per strategy; ~415 rows at full coverage. Holds the authoritative prose returned to the LLM intact; ContentChunk rows are child chunks for vector retrieval.

```python
class TaxStrategy(Base):
    __tablename__ = "tax_strategies"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    strategy_id: Mapped[str] = mapped_column(String(16), unique=True, index=True)
        # Clairo-owned identifier, e.g. 'CLR-241'. Surfaced to users.
    source_ref: Mapped[str | None] = mapped_column(String(32), index=True)
        # Internal mapping only, e.g. 'STP-241'. NEVER surfaced.
    tenant_id: Mapped[str] = mapped_column(String(64), default="platform", index=True)
        # 'platform' for baseline; tenant UUID for private overlays.

    name: Mapped[str] = mapped_column(String(200))
    categories: Mapped[list[str]] = mapped_column(ARRAY(String))
        # Multi-tag: Business, Recommendations, Employees, ATO_obligations,
        # Rental_properties, Investors_retirees, Business_structures, SMSF.

    implementation_text: Mapped[str] = mapped_column(Text)
    explanation_text: Mapped[str] = mapped_column(Text)

    # Structured eligibility metadata (enrichment pass + reviewer confirmed)
    entity_types: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    income_band_min: Mapped[int | None] = mapped_column(Integer)
    income_band_max: Mapped[int | None] = mapped_column(Integer)
    turnover_band_min: Mapped[int | None] = mapped_column(Integer)
    turnover_band_max: Mapped[int | None] = mapped_column(Integer)
    age_min: Mapped[int | None] = mapped_column(Integer)
    age_max: Mapped[int | None] = mapped_column(Integer)
    industry_triggers: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    financial_impact_type: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
        # deduction_expansion | tax_deferral | income_split | cgt_reduction |
        # fbt_reduction | asset_protection | succession | retirement
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
        # Aliases, abbreviations, shorthand. Used in BM25 AND appended to chunk text.

    ato_sources: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
        # e.g. ['ITAA 1997 Div 87', 'TR 2001/8']
    case_refs: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    # Lifecycle
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="stub", index=True)
        # stub | researching | drafted | enriched | in_review | approved
        # | published | superseded | archived
    fy_applicable_from: Mapped[date | None]
    fy_applicable_to: Mapped[date | None]
    last_reviewed_at: Mapped[datetime | None]
    reviewer: Mapped[str | None] = mapped_column(String(120))
    superseded_by_strategy_id: Mapped[str | None] = mapped_column(String(16))

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_tax_strategies_categories", categories, postgresql_using="gin"),
        Index("ix_tax_strategies_entity_types", entity_types, postgresql_using="gin"),
        Index("ix_tax_strategies_industry_triggers", industry_triggers, postgresql_using="gin"),
        Index("ix_tax_strategies_keywords", keywords, postgresql_using="gin"),
        Index("ix_tax_strategies_tenant_status", tenant_id, status),
    )
```

### 5.2 ContentChunk extensions

ContentChunk already carries most required fields. Additions:

```python
# Added to ContentChunk (models.py)
tax_strategy_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("tax_strategies.id", ondelete="CASCADE"), index=True
)
chunk_section: Mapped[str | None] = mapped_column(String(32))
    # 'implementation' | 'explanation' | 'header'
context_header: Mapped[str | None] = mapped_column(String(300))
    # The contextual prefix prepended to chunk text.
```

Existing fields reused: `content_type` (= "tax_strategy"), `collection_name` (= "tax_strategies"), `entity_types` (from parent), `topic_tags` (from parent categories), `is_superseded` (mirrors TaxStrategy.status == superseded), `fy_applicable`, `natural_key` (= strategy_id).

### 5.3 Authoring pipeline job table

```python
class TaxStrategyAuthoringJob(Base):
    __tablename__ = "tax_strategy_authoring_jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    strategy_id: Mapped[str] = mapped_column(String(16), index=True)
    stage: Mapped[str] = mapped_column(String(32), index=True)
        # research | draft | enrich | chunk_and_embed
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    input_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_payload: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=func.now())
```

---

## 6. Namespace and collection configuration

Add to `NAMESPACES` in `backend/app/modules/knowledge/collections.py`:

```python
"tax_strategies": {
    "description": (
        "Clairo-authored Australian tax planning strategies. "
        "415 entries across 8 categories. Platform-baseline; private "
        "overlays filtered via metadata tenant_id."
    ),
    "shared": True,  # same across dev/staging/prod
    "filterable_fields": [
        "tenant_id", "strategy_id", "categories", "chunk_section",
        "entity_types", "industry_triggers",
        "income_band_min", "income_band_max",
        "turnover_band_min", "turnover_band_max",
        "age_min", "age_max",
        "financial_impact_type",
        "fy_applicable_from", "fy_applicable_to",
        "is_superseded",
    ],
},
```

Initialisation runs via the existing `POST /initialize` endpoint on the knowledge router.

---

## 7. Chunking strategy

The single biggest retrieval-quality lever for this corpus is contextual chunking. Naive chunking of a strategy's prose loses the strategy name and category context when only the "Implementation advice" list embeds; the embedding then looks like a generic numbered list and retrieval quality collapses. The design below addresses that.

### 7.1 Parent-child model

- Parent document = TaxStrategy row in Postgres. Always returned to the LLM in full when any of its chunks match. Never directly embedded.
- Child chunks = two per strategy: one for implementation_text, one for explanation_text. Each embedded and stored in Pinecone + ContentChunk.
- Total vectors: 415 strategies × 2 = ~830 vectors at full coverage.

### 7.2 Contextual headers (the key move)

Every child chunk text begins with a context header that includes strategy id, name, category, and section label. The header is generated at chunk time, stored in `ContentChunk.context_header`, and embedded as part of the chunk text.

Example — the implementation chunk for CLR-241 (PSI → PSB):

```
[CLR-241: Change PSI to PSB — Category: Business]
Implementation advice:
1. Advertise the business to the general public through websites,
   newspapers, or online sites.
2. Ensure at least two unrelated clients, with the largest client
   accounting for less than 80% of the PSI.

Keywords: PSI, PSB, personal services income, personal services
business, 80% rule, unrelated clients test, results test, Div 87.
```

Effects:

- **Semantic** retrieval matches queries that name the strategy ("PSI to PSB"), because the name is in the embedding input.
- **BM25** retrieval matches shorthand ("Div 87", "80% rule") because keywords are in the chunk body.
- **Cross-encoder rerank** re-scores against the full chunk text including the header.

### 7.3 Chunk size and splitting

- Target 200–500 tokens per chunk. Typical strategy sections fall in this range. Use existing `BaseStructuredChunker._split_at_boundary()` for overflow cases.
- Context header does not count against the chunk budget — it is a prepended prefix. Every split piece carries the same header.
- New chunker class: `StrategyChunker(BaseStructuredChunker)` in `backend/app/modules/knowledge/chunkers/strategy.py`, following the pattern of existing `RulingChunker` and `LegislationChunker`.

### 7.4 Keyword enrichment tail

The last line of each chunk is a `Keywords:` line populated from `TaxStrategy.keywords` — aliases, abbreviations, and common shorthand ("Div 7A", "catch-up super", "IAWO", "bucket co"). Guarantees BM25 catches them even when the canonical text uses formal wording.

---

## 8. Metadata schema on Pinecone vectors

Metadata is the difference between "semantic search is hit-and-miss" and "reliable retrieval." Two layers:

### 8.1 Identity metadata (required on every chunk)

```python
{
  "chunk_id":          str,     # ContentChunk UUID
  "tax_strategy_id":   str,     # TaxStrategy UUID (used to fetch parent)
  "strategy_id":       str,     # 'CLR-241'
  "name":              str,     # 'Change PSI to PSB'
  "categories":        list,    # ['Business']
  "chunk_section":     str,     # 'implementation' | 'explanation'
  "tenant_id":         str,     # 'platform' or tenant UUID
  "_collection":       str,     # 'tax_strategies'
  "version":           int,
  "is_superseded":     bool,
  "fy_applicable_from": str | None,
  "fy_applicable_to":   str | None,
  "text":              str,     # Chunk text with header + keyword tail
}
```

### 8.2 Structured eligibility metadata (enables pre-filtering)

```python
{
  "entity_types":          list,   # ['individual','sole_trader']
  "income_band_min":       int | None,
  "income_band_max":       int | None,
  "turnover_band_min":     int | None,
  "turnover_band_max":     int | None,
  "age_min":               int | None,
  "age_max":               int | None,
  "industry_triggers":     list,
  "financial_impact_type": list,
  "ato_sources":           list,
  "case_refs":             list,
  "keywords":              list,
}
```

All eligibility fields are optional; absent = broadly applicable along that axis. The enrichment LLM pass populates these; Unni reviews and confirms during sign-off.

---

## 9. Retrieval pipeline enhancements

No existing retrieval class signatures change with breaking semantics. Four additive changes.

### 9.1 Multi-namespace search in KnowledgeSearchRequest

```python
# app/modules/knowledge/schemas.py
class KnowledgeSearchRequest(BaseModel):
    query: str
    filters: KnowledgeSearchFilters | None = None
    limit: int = 10
    namespaces: list[str] | None = None   # NEW: default preserves current behaviour
```

KnowledgeService.search_knowledge(...) passes `namespaces` through to `HybridSearchEngine.hybrid_search(namespaces=[...])` which already supports multi-namespace via `PineconeService.search_multi_namespace()`.

Tax planning call becomes:

```python
request = KnowledgeSearchRequest(
    query=query,
    filters=KnowledgeSearchFilters(
        entity_types=entity_filter or None,
        exclude_superseded=True,
        # NEW structured filters from client context:
        income_band=client.estimated_income,
        turnover_band=client.estimated_turnover,
        age=client.age,
        industry_codes=client.industry_codes,
    ),
    namespaces=["compliance_knowledge", "tax_strategies"],
    limit=12,  # dedupe by parent strategy will collapse
)
```

### 9.2 Structured eligibility pre-filtering

The filter reduces the candidate set before semantic ranking. Built from client context:

```python
pinecone_filter = {
    "$and": [
        {"tenant_id": {"$in": ["platform", tenant_uuid]}},
        {"is_superseded": {"$ne": True}},
        {"entity_types": {"$in": ["individual", "sole_trader"]}},
        # Income band inclusion: strategy applies if client income falls
        # between income_band_min and income_band_max (NULLs = unbounded)
        {"$or": [
            {"income_band_min": {"$exists": False}},
            {"income_band_min": {"$lte": client_income}},
        ]},
        {"$or": [
            {"income_band_max": {"$exists": False}},
            {"income_band_max": {"$gte": client_income}},
        ]},
        # (similar for turnover, age, industry)
    ]
}
```

A query that would otherwise retrieve "SMSF pension start" for a 28-year-old employee is filtered out at Pinecone level.

### 9.3 Query expansion for tax strategies

QueryExpander already expands CONCEPTUAL/SCENARIO queries. Extend expansion prompt to include tax-strategy synonyms and accountant shorthand.

Example:

```
Original: "what can I do to reduce Angela's tax"
Expanded variants:
  - salary optimisation strategies for high-income individual
  - concessional super contributions
  - personal services income rules
  - income splitting between spouses
  - deductible investment loans

Each variant retrieves 30 candidates; union via RRF; rerank top 30.
```

Expansion is LLM-driven (Claude Sonnet); cached at the query layer with a 60-minute TTL keyed on normalised query text. Skip if QueryType is SECTION_LOOKUP or RULING_LOOKUP.

### 9.4 Two-pass retrieval: chunk → parent

```python
async def retrieve_strategies(query, client_context) -> list[TaxStrategyHit]:
    chunks = await hybrid_search_engine.hybrid_search(
        query=query, collection="tax_strategies",
        pinecone_filter=build_filter(client_context),
        namespaces=["compliance_knowledge", "tax_strategies"],
        limit=30,
    )
    # Dedupe: for each tax_strategy_id, keep the chunk with the highest score
    by_parent: dict[str, ScoredChunk] = {}
    for c in chunks:
        sid = c.payload.get("tax_strategy_id")
        if not sid:
            continue  # compliance_knowledge chunks pass through unchanged
        if sid not in by_parent or c.score > by_parent[sid].score:
            by_parent[sid] = c
    parent_candidates = [
        await repo.fetch_parent(sid) for sid in by_parent
    ]
    # Rerank against full parent text
    reranked = cross_encoder.rerank(
        query, parent_candidates, top_k=8,
    )
    return reranked
```

### 9.5 Citation-ready result shape

Each reranked parent is returned to the LLM wrapped in an envelope that makes citation attribution unambiguous:

```xml
<strategy id="CLR-241" name="Change PSI to PSB"
          categories="Business"
          ato_sources="ITAA 1997 Div 87, TR 2001/8"
          case_refs="">
  <implementation>
    1. Advertise the business to the general public ...
    2. Ensure at least two unrelated clients ...
  </implementation>
  <explanation>
    Personal services income (PSI) is mainly from an individual's ...
    To change PSI into PSB, one of the following two tests must be passed:
    1. Results test - These three conditions must be met for at least 75% ...
  </explanation>
</strategy>
```

System prompt instructs: *"When drawing on a `<strategy>` element, cite inline as `[CLR-XXX: Name]`. Include ATO source in parentheses for any threshold or test. Never assert a figure or rule that is not present in the provided strategies."*

---

## 10. Content authoring pipeline

Runs in Celery, tracked per strategy via `TaxStrategyAuthoringJob` rows, surfaced in admin UI as a kanban board.

### 10.1 Stage machine

- **stub** — TaxStrategy row with name, category, source_ref. Bulk-seeded from Tax Fitness index xlsx.
- **researching** — research Celery task fetches ATO primary sources; stores in `job.output_payload.ato_sources`.
- **drafted** — Claude Opus drafts implementation_text and explanation_text from ATO sources + scope prompt.
- **enriched** — second LLM pass extracts structured eligibility metadata.
- **in_review** — Unni opens admin detail view, accepts / edits / rejects.
- **approved** — final task chunks, embeds, upserts to Pinecone + writes ContentChunk rows.
- **published** — live in retrieval.
- **superseded** — re-drafts create a new version; old vectors soft-deleted via `fy_applicable_to`.

### 10.2 Celery tasks

```python
# backend/app/tasks/tax_strategy_authoring.py

@celery_app.task(name="tax_strategies.research", bind=True, queue="tax_strategies")
def research_strategy(self, strategy_id: str) -> None: ...

@celery_app.task(name="tax_strategies.draft", bind=True, queue="tax_strategies")
def draft_strategy(self, strategy_id: str) -> None: ...

@celery_app.task(name="tax_strategies.enrich", bind=True, queue="tax_strategies")
def enrich_strategy(self, strategy_id: str) -> None: ...

@celery_app.task(name="tax_strategies.publish", bind=True, queue="tax_strategies")
def publish_strategy(self, strategy_id: str) -> None:
    # 1. Generate context header for each section
    # 2. Chunk via StrategyChunker
    # 3. Embed via VoyageService
    # 4. Upsert to Pinecone namespace 'tax_strategies'
    # 5. Write ContentChunk rows (tax_strategy_id FK, chunk_section set)
    # 6. Populate BM25IndexEntry rows
    # 7. Set TaxStrategy.status = 'published'
```

Each task writes a `TaxStrategyAuthoringJob` row; failures retry with exponential backoff up to 3 attempts before marking failed.

### 10.3 LLM drafting prompt — the quality floor

```
System:
  You are writing a single-page tax planning strategy for Australian
  accountants. The strategy must be factually correct against provided
  ATO primary sources, practically actionable, and legally precise on
  thresholds and tests. Do not invent content not supported by sources.
  Format:
    (1) Implementation advice: 4–8 numbered, imperative steps.
    (2) Strategy explanation: 250–500 words. Preserve every threshold,
        percentage, test, date verbatim from the sources.
  Do not include: an indicative dollar figure, STP branding, ChangeGPS
  branding, or generic marketing language.

User:
  Strategy: {name}
  Category: {categories}
  ATO primary sources: {fetched_ato_content}
  Coverage target (blueprint scope, not for wording):
    {tax_fitness_topic_scope}
  Write the Implementation advice and Strategy explanation.
```

The blueprint scope is given as topic coverage, not content to paraphrase — this is the line that keeps the reauthoring clean. The LLM works from ATO primary sources; the blueprint only tells it which topic to cover.

### 10.4 Reviewer workflow (Unni)

- Admin strategy list filtered to `status = in_review`. Queue ordered by priority band (top-100 first).
- Detail view shows drafted implementation + explanation, structured eligibility fields, ATO sources pulled in research. Inline Edit on every field.
- Actions: Accept & publish (primary CTA), Edit (stays in_review, re-save), Reject (back to drafted with reviewer_notes; triggers re-draft with feedback injected into prompt).
- Diff view between successive drafts (JSON-patch style), rendered as rich diff in the detail pane.
- Batch-accept disabled: Unni must accept each strategy individually (feature, not bug — it's his signature of approval).

### 10.5 Versioning, updates, supersession

- Minor changes (typos, formatting) → update in place.
- Substantive changes → new version (version += 1, new row, mark old as `superseded_by`).
- Publishing new version runs full chunk → embed → upsert cycle. Old Pinecone vectors soft-deleted by setting `fy_applicable_to = today` and filtering `is_superseded = true` at query time.
- Annual review cycle: scheduled task flags strategies whose ATO source `document_hash` changed for reviewer attention.

---

## 11. Citation handling

### 11.1 Markup convention

Inline citation markup: `[CLR-241: Change PSI to PSB]`. Single convention across all AI surfaces (tax planning chat, scenario analysis, pre-meeting brief). The LLM emits it; the frontend intercepts it; the backend verifier matches it.

ATO source citations remain in their existing format (e.g. `(ITAA 1997 s 87-15)`) and are emitted as parenthetical supplements to the primary `[CLR-XXX]` citation for any claim about a threshold or test.

### 11.2 Backend citation verification

Extend `CitationVerifier` to recognise the CLR-XXX pattern:

```python
# app/modules/knowledge/retrieval/citation_verifier.py

CLR_PATTERN = re.compile(r"\[CLR-(\d{3,5}):\s*([^\]]+)\]")

def extract_strategy_citations(text: str) -> list[StrategyCitation]:
    return [
        StrategyCitation(
            strategy_id=f"CLR-{m.group(1)}",
            name=m.group(2).strip(),
        )
        for m in CLR_PATTERN.finditer(text)
    ]

# Verification: each extracted citation matched against retrieved
# strategies served to the LLM. Match criteria (in order):
#   1. Exact strategy_id match                    → verified
#   2. strategy_id match but name drift > 30%     → partially_verified
#   3. No strategy_id match                       → unverified
```

The returned verification summary extends `_build_citation_verification()` to include `strategy_citations` as a list alongside section-ref and ruling-number arrays. Overall status collapses to verified / partially_verified / unverified as today.

### 11.3 Frontend rendering

Two additions to CitationBadge.tsx and one new component:

- **StrategyChip (new)** — renders a `[CLR-241: Change PSI to PSB]` inline reference as a small clickable badge. Green if verified, amber if partially, red if unverified. Click opens a Sheet (shadcn) showing full strategy content, ATO sources, case refs, and a link to the admin detail view if user is super_admin.
- **Message-level CitationBadge** — existing component. Extended to show secondary count: "3 strategies cited (all verified)" alongside section-ref/ruling count.
- **useStrategyHydration hook (new)** — given an array of strategy_ids from a chat message's citations, fetches full TaxStrategy records via `GET /tax-strategies?ids=` and caches them. Used by StrategyChip to populate the Sheet without the chat message embedding the full content.

### 11.4 Markdown renderer integration

In the existing chat message renderer, add a regex-based tokenizer that converts any CLR-XXX match in the assistant message into a `<StrategyChip/>` React node before markdown rendering.

---

## 12. Admin UI extensions

All work lives under `/frontend/src/app/(protected)/admin/knowledge/` and follows the existing tabs + components + hooks pattern. No new admin route — the tab becomes one more entry in the existing knowledge admin tabset.

### 12.1 New tab: "Strategies"

New component: `components/strategies-tab.tsx`. Structure mirrors `sources-tab.tsx`. Contents:

- **Top bar** — filter by status, category, tenant (platform / private overlay), search box.
- **Counters** — summary of strategy counts per status ("Published 97 / In review 12 / Drafted 31 / Stub 275") — immediate situational awareness.
- **Table** — columns: Strategy ID (CLR-XXX), Name, Categories (pills), Status (Badge), Last reviewed, Reviewer, Version. Row click → detail Sheet.
- **Actions bar** — Seed from Index (one-time), Bulk research, Bulk publish.

### 12.2 Strategy detail view (Sheet)

- Read/edit strategy name, categories, implementation_text (markdown editor), explanation_text (markdown editor).
- Structured eligibility fields as form controls — entity_types (multi-select), income_band slider, turnover_band slider, age range, industry_triggers (multi-select), financial_impact_type (multi-select), keywords (tag input), ato_sources (array input), case_refs (array input).
- Version history panel with diff view.
- Authoring jobs log (TaxStrategyAuthoringJob rows).
- Action bar — Save, Submit for review, Approve & publish, Reject to draft, Archive.

### 12.3 Authoring pipeline dashboard

New sub-tab: "Pipeline". Kanban-style view with columns stub / researching / drafted / enriched / in_review / approved / published. Cards in in_review highlighted and counted prominently — Unni's queue.

Backed by `GET /admin/tax-strategies/pipeline-stats` returning counts per status.

### 12.4 Collections tab integration

Existing Collections tab reads from `CollectionManager.get_all_stats()`. Once the `tax_strategies` namespace is initialised, it appears automatically alongside compliance_knowledge etc. — no explicit work.

### 12.5 Search Test tab integration

Extend namespace selector to accept multi-select. For tax_strategies searches, result card adds strategy_id, categories, chunk_section, and an "Open strategy" link.

### 12.6 Admin API additions

```
# Under existing /admin/knowledge router

POST   /tax-strategies                 # create stub
GET    /tax-strategies                 # list with filters
GET    /tax-strategies/{strategy_id}   # full detail + chunks + jobs
PATCH  /tax-strategies/{strategy_id}   # update fields
POST   /tax-strategies/{strategy_id}/research   # trigger research task
POST   /tax-strategies/{strategy_id}/draft      # trigger draft task
POST   /tax-strategies/{strategy_id}/enrich     # trigger enrich task
POST   /tax-strategies/{strategy_id}/submit     # drafted|enriched → in_review
POST   /tax-strategies/{strategy_id}/approve    # in_review → approved → publish
POST   /tax-strategies/{strategy_id}/reject     # with reviewer_notes
POST   /tax-strategies/{strategy_id}/supersede  # create new version
POST   /tax-strategies/seed-from-index          # one-time: parse index xlsx
GET    /tax-strategies/pipeline-stats           # counts per status

# Client-facing (non-admin):
GET    /tax-strategies/{strategy_id}/public     # read-only for citation hydration
```

---

## 13. Integration with tax planning module

The tax planning module's `_retrieve_tax_knowledge()` is the single integration point. Changes there are narrow:

- Pass `namespaces=["compliance_knowledge", "tax_strategies"]` by default.
- Populate KnowledgeSearchFilters with income_band, turnover_band, age, industry_codes sourced from the client's Xero connection + profile. Structured metadata pre-filter earns its value here.
- Return tax_strategies results wrapped in the `<strategy>` envelope (§9.5).
- System prompt updated to instruct `[CLR-XXX]` citation format and "do not assert a figure not present in the provided strategies."

All scenario-generation, explore-strategies, and chat-answer surfaces in tax planning now receive grounded strategies automatically.

---

## 14. Multi-tenant considerations

All platform-baseline strategies are written with `tenant_id="platform"` on both TaxStrategy rows and Pinecone vector metadata. Retrieval always uses a filter of the form:

```
tenant_id ∈ {"platform", <current_tenant_uuid>}
```

Today no tenant has a private overlay, so this evaluates to `tenant_id == "platform"` and behaves as expected. When Path A (Unni's private overlay) ships:

- TaxStrategy rows with `tenant_id=<unni_tenant_uuid>` added via same admin UI.
- Retrieval union returns both platform and private strategies; ranking treats them equally.
- Citation chip surfaces "Your firm's strategy" vs "Clairo platform strategy" as a small label when `tenant_id != "platform"`.

No schema changes required to enable Path A — it's purely a content-layer overlay once the rest of this design ships.

---

## 15. Phased rollout

### Phase 1 — infrastructure (weeks 1–2)

- DB migrations: TaxStrategy, TaxStrategyAuthoringJob, ContentChunk extensions.
- Namespace addition + initialization.
- Celery tasks scaffolded (research / draft / enrich / publish), working end-to-end on a single test strategy.
- Admin UI Strategies tab shell + strategy detail Sheet (read-only first).
- CitationVerifier CLR pattern extension + StrategyChip frontend component.
- Seed-from-Tax-Fitness-index endpoint + 415 stub rows.
- **Exit criterion**: Asaf can click "Research" on a stub, see the job complete, edit drafted content in admin Sheet, click "Publish", and retrieve it via Search Test tab with a `[CLR-XXX: ...]` chip rendering in Clairo chat.

### Phase 2 — alpha content (weeks 3–8)

- Identify top ~100 highest-frequency strategies (concessional super / IAWO / PSI / negative gearing / bucket company / CGT small-business backbone plus common FBT, trust distribution, SMSF basics).
- Research + draft + enrich all 100 via pipeline in batches of 20. LLM-assisted drafting; each through Unni's review queue.
- Unni's paid review arrangement in place. Target: 20 approved per week over 5 weeks.
- Retrieval tuning against gold-set of 30 accountant queries (built with Unni) — measure recall @ top-5.
- **Exit criterion**: 100 strategies published, recall ≥ 90% on gold-set, alpha ready for another live session.

### Phase 3 — beta expansion (weeks 9–16)

- Research + draft + enrich next ~250 strategies. Review throughput target: 30–40 per week.
- Structured eligibility metadata accuracy review (10-strategy sample per week).
- Per-tenant overlay UI (Path A) stood up in admin for Unni's and Vik's tenants.
- **Exit criterion**: ~350 strategies live, beta cohort onboarded, per-tenant overlay validated.

### Phase 4 — long tail + maintenance (Q3+)

- Remaining ~65 strategies published.
- Annual ATO-source-change review task scheduled.
- New-strategy intake workflow for tenants requesting coverage gaps.

---

## 16. Open questions and risks

- **Unni's review capacity** — 20 approvals/week alongside practice work is ambitious. Risk: bottleneck delays alpha. Mitigation: explicit weekly review windows under paid advisory; batch LLM drafts; side-by-side review tooling.
- **LLM draft quality floor** — if >30% of drafts rejected, review becomes rewrite and velocity collapses. Mitigation: seed 5–10 exemplar strategies Unni writes himself as few-shot examples; monitor rejection rate weekly; prompt tuning.
- **Structured metadata accuracy** — eligibility filters only work if enrichment pass is right. Mitigation: default NULL (broadly applicable) when ambiguous; calibration sample reviewed by Unni; A/B vs unfiltered baseline for first 50 strategies.
- **Gold-set construction** — need labelled test set (query → correct strategies). Mitigation: Unni provides 30–50 real client queries from practice history (paid time); labels populated during review.
- **Budget-change volatility** — rates change and strategies must stay current. Mitigation: every strategy carries `fy_applicable_from/to` and `ato_sources`; scheduled task refetches ATO content and flags strategies whose source `document_hash` changed; annual FY-start review cycle.
- **Rights boundary** — reauthoring from public ATO sources, not copying STP content. If STP index xlsx considered proprietary even as a coverage list, seed step carries exposure. Mitigation: derive coverage from our own reading of AU tax structure (by category); treat Tax Fitness only as completeness sanity-check, not source list.

---

## 17. Appendix — worked example: CLR-241 (PSI → PSB)

### 17.1 TaxStrategy row (Postgres)

```json
{
  "id": "<uuid>",
  "strategy_id": "CLR-241",
  "source_ref": "STP-241",
  "tenant_id": "platform",
  "name": "Change PSI to PSB",
  "categories": ["Business"],
  "implementation_text": "1. Advertise the business ...\n2. Ensure at least ...",
  "explanation_text": "Personal services income (PSI) is mainly from ...",
  "entity_types": ["individual", "sole_trader"],
  "income_band_min": 50000,
  "income_band_max": null,
  "turnover_band_min": null,
  "turnover_band_max": null,
  "age_min": null, "age_max": null,
  "industry_triggers": ["contracting", "consulting", "IT_services", "medical_locum"],
  "financial_impact_type": ["deduction_expansion"],
  "keywords": ["PSI", "PSB", "personal services income",
               "personal services business", "80% rule",
               "unrelated clients test", "results test",
               "employment test", "business premises test"],
  "ato_sources": ["ITAA 1997 Div 87", "TR 2001/8", "TR 2022/3"],
  "case_refs": [],
  "version": 1,
  "status": "published",
  "fy_applicable_from": "2024-07-01",
  "fy_applicable_to": null,
  "last_reviewed_at": "2026-05-14T10:22:00Z",
  "reviewer": "Unni Subramaniam"
}
```

### 17.2 Child chunks in Pinecone (2 rows)

```
# Vector 1: implementation
id:       "tax_strategy:CLR-241:implementation:v1"
values:   [<1024 floats>]   # Voyage 3.5 lite embedding
metadata: {
  "chunk_id": "<uuid>",
  "tax_strategy_id": "<parent_uuid>",
  "strategy_id": "CLR-241",
  "name": "Change PSI to PSB",
  "categories": ["Business"],
  "chunk_section": "implementation",
  "tenant_id": "platform",
  "version": 1,
  "is_superseded": false,
  "fy_applicable_from": "2024-07-01",
  "fy_applicable_to": null,
  "entity_types": ["individual", "sole_trader"],
  "income_band_min": 50000,
  "turnover_band_max": null,
  "industry_triggers": ["contracting", "consulting", "IT_services",
                        "medical_locum"],
  "financial_impact_type": ["deduction_expansion"],
  "ato_sources": ["ITAA 1997 Div 87", "TR 2001/8", "TR 2022/3"],
  "keywords": ["PSI","PSB","80% rule","unrelated clients test", ...],
  "text": "[CLR-241: Change PSI to PSB — Category: Business]\n
            Implementation advice:\n
            1. Advertise the business ...\n
            2. Ensure at least two unrelated clients ...\n
            \n
            Keywords: PSI, PSB, personal services income, ..."
}

# Vector 2: explanation  (same metadata shape, chunk_section='explanation')
```

### 17.3 Example retrieval query

```
Query: "Can Zac split some income to his wife if he's contracting?"

Classification  → SCENARIO (confidence 0.88), domain detected: psi
Expansion       → [
                    "income splitting between spouses for contractor",
                    "personal services income rules contractor",
                    "employ spouse PSB tests",
                    "Division 87 PSI distribution",
                  ]
Filter          → {
                    tenant_id in [platform, <uuid>],
                    entity_types contains any of [individual, sole_trader],
                    industry_triggers overlap [contracting, consulting],
                    is_superseded != true,
                  }
Hybrid search   → 30 chunks per query variant across both namespaces
Dedupe parent   → 12 distinct strategies
Cross-encoder   → top 8:
                    CLR-241 (Change PSI to PSB)                score 0.92
                    CLR-140 (Change PSI into business income)  score 0.89
                    CLR-023 (Employ spouse in business)        score 0.83
                    CLR-089 (Income splitting via partnership) score 0.75
                    ...
Envelope        → Top 4–5 returned to LLM wrapped in <strategy> tags.
```

### 17.4 Example LLM response with citations

User message: "Can Zac split some income to his wife if he's contracting?"

Assistant response (excerpt):

```
Before recommending any income splitting, Zac's situation needs to pass
the Personal Services Income rules. If his contracting work is mainly a
reward for his personal skills, the PSI rules in [CLR-241: Change PSI to
PSB] apply — and under those rules, the only deductions allowed against
PSI are the ones an employee would be entitled to, which means paying
his wife a salary generally wouldn't be deductible.

There are two paths forward:

1. If Zac passes the Results Test (paid for a specific result, provides
   his own tools, liable for fixing mistakes) for at least 75% of the
   income, or passes the 80% rule plus one of the unrelated-clients /
   employment / business-premises tests, his contracting becomes a
   Personal Services Business. That unlocks the strategies in
   [CLR-241: Change PSI to PSB] including employing his wife in the
   business (ITAA 1997 Div 87).

2. If he can't move to PSB status, income splitting is effectively
   blocked by Div 87 and we should focus on other levers instead.
```

Frontend: each `[CLR-XXX]` becomes a green StrategyChip, clickable to expand. CitationBadge at the bottom reads "2 strategies cited (all verified) — 3 ATO sources referenced."

---

## 18. What to validate before build

1. Walk this doc end-to-end with Asaf; confirm ContentChunk extensions and new module fit without breaking existing migrations.
2. Confirm Unni's paid-reviewer arrangement (rate, weekly hours, review cadence) so Phase 2 is operational from day one.
3. Build one strategy end-to-end (CLR-012 Concessional super is a good candidate — mid-complexity, high-frequency) as a vertical-slice proof before scaling to 100.

If those three land, the design is ready to ship. Exit criteria for each phase and the overall definition of done are specified in §19.

---

## 19. Validation & exit criteria

This section defines the definition of done at three layers: automated tests that must pass in CI on every PR, evaluation tests that measure quality on a regular cadence, and acceptance tests that require Unni's sign-off before a phase is considered complete. All three layers must land for the KB implementation to be considered validated.

Asaf writes the automated tests (§19.1) as part of Phase 1 infrastructure — they can run against empty data while content lands, because assertions are testable on schema and pipeline shape before any strategies are published.

### 19.1 Automated tests (CI gates, ship-blocking)

Live in the backend + frontend test suites; run on every PR.

**Unit — backend**

- `CitationVerifier.extract_strategy_citations()` correctly parses `[CLR-241: Change PSI to PSB]` patterns, with/without whitespace, across multi-line responses.
- `CitationVerifier.verify_strategy_citations()` returns `verified` for exact strategy_id match, `partially_verified` for strategy_id match with name drift > 30%, `unverified` otherwise.
- `StrategyChunker` produces exactly 2 chunks per strategy (implementation + explanation) for typical input; splits cleanly at paragraph boundary when `explanation_text` exceeds 500 tokens.
- Every chunk's `context_header` field conforms to `[CLR-XXX: Name — Category: Y]` format.
- Every chunk body ends with a `Keywords: <comma-separated>` line.

**Integration — backend**

- Publishing a TaxStrategy via `tax_strategies.publish` Celery task produces: 1 TaxStrategy row with status=published, 2 ContentChunk rows with `tax_strategy_id` FK set, 2 BM25IndexEntry rows, 2 Pinecone vectors with full metadata payload.
- `KnowledgeSearchRequest(namespaces=["compliance_knowledge", "tax_strategies"])` returns hits from both namespaces when present; defaults to current behaviour when `namespaces` is None.
- Structured eligibility pre-filter correctly excludes strategies outside client bands — table-driven test: 5 client profiles × 10 strategies with varied eligibility metadata, expected inclusion/exclusion for each pair.
- Retrieval dedupes chunks by `tax_strategy_id` before cross-encoder rerank; no strategy_id appears twice in top-8.
- Returned LLM context envelope conforms to the `<strategy id="CLR-XXX" ...>` schema.
- `[CLR-241]` in an assistant message when CLR-241 was in the retrieved set verifies as `verified`; a hallucinated `[CLR-999: ...]` verifies as `unverified`.
- `tenant_id` filter correctly unions platform baseline with tenant overlay; private-tenant strategies do not leak across tenants.

**Frontend**

- `StrategyChip` renders green/amber/red per verification status; click opens Sheet; Sheet populates via `useStrategyHydration`.
- Chat message renderer converts `[CLR-XXX: Name]` tokens into `<StrategyChip/>` React nodes before markdown render.
- Admin Strategies tab list paginates and filters by status / category / tenant correctly.
- Admin strategy detail Sheet persists field edits via PATCH; optimistic update reverts on server error.

### 19.2 Evaluation tests (benchmarks, regression-gated)

Quality measurements that run on a cadence — at least weekly during Phase 2, monthly thereafter — and alert if any metric regresses below threshold for two consecutive runs.

- **Recall@5 ≥ 90%** on Unni's 30–50 query gold-set. Gold-set built during Phase 2 kickoff; each query has 1–3 labelled "correct" strategies.
- **Top-1 precision ≥ 60%** on the same gold-set.
- **PSI sensitivity**: any synthetic client profile with industry code in {contracting, consulting, IT_services, medical_locum} AND income concentration > 80% returns CLR-241 in top-3.
- **PSI specificity**: any non-PSI profile (entity=company, or salary-earner with no contracting income) does not return CLR-241 in top-5.
- **Shadow test**: 10 real historical tax planning sessions from Unni's practice; retrieve strategies against the client profile at time of session; Unni labels each result "would I have cited this?" — false-negative rate ≤ 15%.
- **Metadata filter lift**: A/B compare filtered vs unfiltered retrieval on gold-set. Filtered version must have strictly higher recall@5 (proves the filter is helping, not hurting).

### 19.3 Acceptance tests (UAT — Unni, release-blocking per phase)

Qualitative tests Unni performs before a phase is signed off.

**Phase 1 exit**

- One complete strategy (CLR-012 Concessional super, suggested vertical slice) moves end-to-end: stub → researching → drafted → enriched → in_review → approved → published.
- Admin UI Strategies tab is navigable; detail Sheet is editable; publishing from in_review produces a retrievable strategy.
- Tax planning chat shows a green `StrategyChip` for CLR-012 when asked "should my employee salary-sacrifice to super?"

**Phase 2 exit (100 strategies published — alpha-ready)**

- Three test-client profiles exercised (sole trader $60k employee-like, contractor $180k 90%-concentration, SMSF member age 68). Retrieval returns materially different top-5 for each; Unni confirms each top-5 is profile-appropriate.
- Pre-meeting brief run against the contractor profile surfaces a PSI flag pointing to CLR-241 automatically, without the accountant asking.
- 20-question stress test in tax planning chat: zero responses return the F1-14 "Sources could not be verified" badge.
- Same strategy cited in chat and the Scenarios tab row shows consistent implementation steps and ATO source.
- Second live client session (equivalent to Zac's) runs end-to-end with Unni signing off that every AI strategy claim is traceable to a library entry.

**Phase 3 exit (~350 strategies — beta-ready)**

- Beta cohort (10 customers) onboarded; each runs at least one tax planning session; aggregate unverified-citation rate < 2%.
- Per-tenant overlay stood up for Unni's and Vik's tenants; retrieval union works; private strategies do not leak.

### 19.4 Performance criteria

- Retrieval latency p95 ≤ 800ms end-to-end for tax planning chat (query embedding + hybrid retrieval + dedupe + cross-encoder rerank + parent fetch).
- Publishing a strategy (chunk + embed + upsert) completes in ≤ 30s p95.
- Admin Strategies tab list loads ≤ 500ms for 500 rows.

### 19.5 Definition of done

The tax_strategies knowledge base is considered implemented and validated when:

1. All automated tests in §19.1 pass in CI on main.
2. All evaluation metrics in §19.2 meet their thresholds on the gold-set.
3. Phase-2 acceptance tests in §19.3 are signed off by Unni.
4. Performance criteria in §19.4 are met under production-like load.
5. The Zac-equivalent second live client session runs cleanly.
