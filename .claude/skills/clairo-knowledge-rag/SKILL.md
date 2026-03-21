---
name: clairo-knowledge-rag
description: >
  Complete recipe for Clairo's knowledge/RAG module: ingestion pipeline, retrieval pipeline, scraper patterns, and Pinecone configuration.
  Use when implementing features that touch knowledge ingestion, document retrieval, search, RAG, chatbot, or AI-powered compliance queries.
  Use during /speckit.plan or /speckit.implement for knowledge module tasks.
  Do NOT use for non-knowledge features like billing, auth, or client management.
---

# Clairo Knowledge/RAG Module

This skill gives Claude Code instant context on the knowledge/RAG module so it does not need to re-read 40+ files every time a RAG-related feature is worked on. Covers ingestion (URL -> scrape -> chunk -> embed -> upsert) and retrieval (query -> route -> expand -> search -> fuse -> rerank -> cite).

---

## Module Map -- Quick Reference

| Layer | File(s) | Key Class / Function | One-liner |
|-------|---------|---------------------|-----------|
| **Models** | `knowledge/models.py` | `KnowledgeSource`, `ContentChunk`, `IngestionJob`, `LegislationSection`, `ContentCrossReference`, `TaxDomain`, `BM25IndexEntry`, `ScraperCircuitBreakerState`, `ChatConversation`, `ChatMessage` | All DB models; `ContentChunk.qdrant_point_id` is the Pinecone vector ID (legacy name) |
| **Schemas** | `knowledge/schemas.py` | `ChunkPayload`, `KnowledgeSearchRequest`, `SearchResponse`, `ChatRequest`, `ManualContentUpload`, `CollectionInfo`, `EnhancedCitationSchema` | Pydantic request/response schemas |
| **Repository** | `knowledge/repository.py` | `KnowledgeSourceRepository`, `ContentChunkRepository`, `IngestionJobRepository`, `LegislationSectionRepository`, `BM25IndexRepository`, `CircuitBreakerRepository` | All DB access; repository pattern |
| **Service** | `knowledge/service.py` | `KnowledgeService.search_knowledge()` | Main search orchestrator: classify -> domain scope -> expand -> hybrid search -> RRF -> rerank -> format |
| **Router** | `knowledge/router.py` | FastAPI endpoints | All API routes (~83KB); collection CRUD, source CRUD, ingestion, search, chatbot, admin |
| **Chatbot** | `knowledge/chatbot.py` | `KnowledgeChatbot` | Two paths: original (`retrieve_context`) and enhanced (`retrieve_context_enhanced` + `chat_enhanced`) |
| **Client Chat** | `knowledge/client_chatbot.py` | `ClientContextChatbot` | Combines client financial data (Xero) with RAG for grounded answers |
| **Collections** | `knowledge/collections.py` | `CollectionManager`, `INDEX_NAME`, `NAMESPACE_CONFIGS` | Pinecone index config, 7 namespaces, env-suffix logic |
| **Domains** | `knowledge/domains.py` | `DomainManager` | DB-backed domain config with 5-min TTL cache |
| **Ingestion Mgr** | `knowledge/ingestion_manager.py` | `IngestionManager` | Idempotent doc ingestion: `should_ingest()` -> `insert_document()` / `replace_document()` |
| **Chunker (general)** | `knowledge/chunker.py` | `SemanticChunker` | 1500 char chunks, 200 overlap, recursive split |
| **Chunker (legislation)** | `knowledge/chunkers/legislation.py` | `LegislationChunker` | Section-level chunks (256-512 tokens), classifies content_type |
| **Chunker (ruling)** | `knowledge/chunkers/ruling.py` | `RulingChunker` | Structural sections: Ruling, Explanation, Examples, Date of Effect |
| **Chunker (case law)** | `knowledge/chunkers/case_law.py` | `CaseLawChunker` | Sections: headnote, reasoning, orders; fallback to paragraph split |
| **Chunker registry** | `knowledge/chunkers/__init__.py` | `get_chunker()`, `register_chunker()` | Maps content_type string -> chunker class |
| **Query Router** | `knowledge/retrieval/query_router.py` | `QueryRouter.classify()` | Pure regex classification, 6 query types, fusion weights + Pinecone filters per type |
| **Query Expander** | `knowledge/retrieval/query_expander.py` | `QueryExpander.expand()` | Synonym table + LLM expansion (claude-haiku-4-5, 5s timeout, 256 tokens) |
| **Hybrid Search** | `knowledge/retrieval/hybrid_search.py` | `HybridSearchEngine.hybrid_search()` | BM25 + Pinecone semantic -> RRF fusion (k=60) |
| **Reranker** | `knowledge/retrieval/reranker.py` | `CrossEncoderReranker.rerank()` | cross-encoder/ms-marco-MiniLM-L-6-v2, sigmoid-normalized, lazy-loaded |
| **Citation Verifier** | `knowledge/retrieval/citation_verifier.py` | `CitationVerifier.verify()` | Post-generation check: numbered citations, section refs, ruling refs |
| **ScoredChunk** | `knowledge/retrieval/__init__.py` | `ScoredChunk` | Common interchange dataclass: chunk_id, score, text, payload |
| **Intent Detector** | `knowledge/intent_detector.py` | `QueryIntentDetector` | Financial query classification for client-context chat (NOT for Pinecone) |
| **Doc Processor** | `knowledge/document_processor.py` | `DocumentProcessor` | PDF/DOCX/TXT text extraction for manual uploads |
| **Context Builder** | `knowledge/context_builder.py` | `ContextBuilderService` | Builds client financial context from Xero data (Tier 1/2/3) |
| **Token Budget** | `knowledge/token_budget.py` | `TokenBudgetManager` | 4 tiers: profile 500, summaries 4000, details 2000, RAG 2000 (12500 total) |
| **Scrapers** | `knowledge/scrapers/base.py` | `BaseScraper` | ABC with rate limiting (1 req/s), semaphore (3 concurrent), tenacity retries (3x) |
| **ATO RSS** | `knowledge/scrapers/ato_rss.py` | `ATORSSScraper` | RSS feeds (rulings, news, legal_database) |
| **ATO Web** | `knowledge/scrapers/ato_web.py` | `ATOWebScraper` | ATO website crawl with configurable depth |
| **ATO API** | `knowledge/scrapers/ato_api.py` | `ATOAPIScraper` | PDF guides (BAS, GST, PAYG, FBT) via ATO public API |
| **ATO Legal DB** | `knowledge/scrapers/ato_legal_db.py` | `ATOLegalDatabaseScraper` | Rulings (TR, GSTR, TD, PCG, etc.); print-friendly URLs; 0.5 req/s |
| **Legislation** | `knowledge/scrapers/legislation_gov.py` | `LegislationGovScraper` | 7 tax acts; 10s crawl delay; per-section ScrapedContent |
| **Case Law** | `knowledge/scrapers/case_law.py` | `CaseLawScraper` | Open Australian Legal Corpus (HF JSONL) + Federal Court RSS |
| **TPB/Treasury** | `knowledge/scrapers/tpb_treasury.py` | `TPBTreasuryScraper` | TPB info products + Treasury exposure drafts |
| **Circuit Breaker** | `knowledge/scrapers/circuit_breaker.py` | `ScraperCircuitBreaker` | DB-backed: 5 failure threshold, 3600s recovery, 2 half-open tests |
| **Celery Tasks** | `tasks/knowledge.py` | `ingest_source`, `ingest_all_sources`, `ingest_ato_legal_database`, `ingest_legislation`, `ingest_case_law` | Async-in-sync Celery tasks with checkpoint/resume |
| **Pinecone Service** | `core/pinecone_service.py` | `PineconeService` | Async wrapper around sync Pinecone client; batch upsert (100); `search_multi_namespace` |
| **Voyage Service** | `core/voyage.py` | `VoyageService` | Voyage 3.5 lite embeddings; `embed_query()` vs `embed_document()`; batch with retry |
| **Aggregation** | `knowledge/aggregation_models.py`, `aggregation_repository.py`, `aggregation_service.py` | `AggregationRepository`, various summary models | Client financial summaries for context builder |

---

## Pinecone Configuration

| Setting | Value |
|---------|-------|
| Index name | `clairo-knowledge` |
| Dimensions | 1024 |
| Metric | cosine |
| Embedding model | `voyage-3.5-lite` (Voyage AI) |
| Serverless spec | AWS us-east-1 |

### Namespaces (7 total)

| Namespace | Env-suffixed? | Content |
|-----------|--------------|---------|
| `compliance_knowledge` | No (shared) | Tax legislation, rulings, case law, ATO guides -- **primary namespace** |
| `strategic_advisory` | No (shared) | Advisory content |
| `industry_knowledge` | No (shared) | Industry-specific |
| `business_fundamentals` | No (shared) | General business |
| `financial_management` | No (shared) | Financial management |
| `people_operations` | No (shared) | HR/people |
| `insight_dedup` | Yes (`_dev`/`_staging`/`_prod`) | Insight deduplication vectors |

**NOTE**: All legal content (legislation, rulings, case law) goes into `compliance_knowledge`. The `get_namespace_with_env()` function adds `_dev`/`_staging`/`_prod` suffix only for `insight_dedup`.

### Pinecone Metadata Fields (per vector)

Standard: `text`, `source_url`, `title`, `source_type`, `source_id`, `chunk_index`, `_collection`

Spec 045 additions: `content_type`, `section_ref`, `ruling_number`, `topic_tags`, `court`, `case_citation`, `document_hash`, `natural_key`, `is_superseded`, `superseded_by`, `effective_date`, `confidence_level`

**30KB text truncation limit** enforced by IngestionManager.

---

## Ingestion Pipeline Overview

```
[Source URL]
  |
  v
[Scraper] -- BaseScraper ABC with rate limiting + retries + circuit breaker
  |          7 scraper implementations (ato_rss, ato_web, ato_api, ato_legal_db,
  |          legislation_gov, case_law, tpb_treasury)
  |
  v
[ScrapedContent] -- dataclass with to_chunk_payload()
  |
  v
[Chunker] -- SemanticChunker (general) or structure-aware chunker via registry:
  |           "legislation" -> LegislationChunker (section-level, 256-512 tokens)
  |           "ruling"      -> RulingChunker (structural sections)
  |           "case_law"    -> CaseLawChunker (headnote/reasoning/orders)
  |
  v
[IngestionManager.should_ingest()] -- SKIP / REPLACE / INSERT
  |  Uses natural_key + document_hash for idempotency
  |
  v
[VoyageService.embed_batch()] -- voyage-3.5-lite, batch mode, sequential for rate limits
  |
  v
[IngestionManager.insert_document() / replace_document()]
  |  - Deterministic vector IDs: {source_type}:{natural_key}:{chunk_index}
  |  - Batch Pinecone upsert
  |  - Creates ContentChunk DB rows
  |  - Creates BM25IndexEntry rows (tokenized text)
  |  - Creates ContentCrossReference rows
  |
  v
[IngestionJob checkpoint updated] -- supports resume on retry
```

See `references/ingestion-pipeline.md` for complete details.

---

## Retrieval Pipeline Overview

```
[User Query]
  |
  v
[QueryRouter.classify()] -- pure regex, 6 types with fusion weights + Pinecone filters
  |  SECTION_LOOKUP:  0.2 semantic / 0.8 keyword, filter by section_ref
  |  RULING_LOOKUP:   0.2 / 0.8, filter by ruling_number
  |  CASE_LAW:        0.5 / 0.5, filter by source_type=case_law
  |  PROCEDURAL:      0.5 / 0.5, filter source_type in [ato_guide, ato_ruling]
  |  SCENARIO:        0.6 / 0.4, exclude superseded
  |  CONCEPTUAL:      0.7 / 0.3, exclude superseded
  |
  v
[DomainManager.get_domain_filters()] -- DB-backed with 5-min TTL cache
  |  Replaces hardcoded topic_tags with domain-specific filters
  |
  v
[QueryExpander.expand()] -- synonym table + LLM (claude-haiku-4-5, 5s timeout)
  |  Only for CONCEPTUAL/PROCEDURAL/SCENARIO/CASE_LAW
  |  Returns list of query variants
  |
  v
[HybridSearchEngine.hybrid_search()] -- per variant
  |  1. Embed query via Voyage (input_type="query")
  |  2. Pinecone semantic search (limit*2 candidates)
  |  3. BM25 keyword search from DB-backed token index
  |  4. RRF fusion: final = sw * rrf_semantic + (1-sw) * rrf_bm25, k=60
  |  5. Enrich BM25-only results with DB + Pinecone metadata
  |
  v
[Merge variants via RRF] -- deduplicate by chunk_id
  |
  v
[CrossEncoderReranker.rerank()] -- ms-marco-MiniLM-L-6-v2, sigmoid normalization
  |  ~80MB model, lazy-loaded, thread-safe cache
  |  Graceful fallback if model fails
  |
  v
[Format results] -- build citations, detect superseded, compute confidence
  |  Confidence = 0.4 * top_score + 0.3 * mean_top5 + 0.3 * citation_verified_rate
  |  Low confidence (< 0.5): declines to answer
  |
  v
[CitationVerifier.verify()] -- post-generation verification
  |  Checks [N] citations, section refs, ruling refs against retrieved chunks
  |
  v
[Response] -- message, citations, confidence, superseded_warnings, attribution
```

See `references/retrieval-pipeline.md` for complete details.

---

## Pre-change Checklist

Before making changes to the knowledge/RAG module, verify:

- [ ] Which pipeline am I touching -- ingestion, retrieval, or both?
- [ ] Does the change affect Pinecone metadata? If so, update: `ChunkPayload` schema, `IngestionManager.insert_document()`, `_build_pinecone_metadata()` in relevant Celery task, and any Pinecone filter logic in `QueryRouter`
- [ ] Does the change add a new source type? If so: add scraper (extend `BaseScraper`), register chunker if structure-aware, add to `_SPEC045_SOURCES` in `tasks/knowledge.py`, add Celery task
- [ ] Does the change affect search quality? Test with: section lookup ("s 8-1 ITAA 1997"), ruling lookup ("TR 2024/1"), conceptual ("What is GST?"), scenario ("client has...")
- [ ] Does the change affect DB models? Create Alembic migration, check `qdrant_point_id` naming
- [ ] Does the change touch the chatbot? Two code paths exist: original (`retrieve_context`) and enhanced (`retrieve_context_enhanced`) -- update both or confirm which

---

## Post-change Checklist

- [ ] Pinecone metadata changes: existing vectors are NOT retroactively updated; consider re-ingestion
- [ ] New metadata filters: verify Pinecone index supports the field (only metadata stored at upsert time is filterable)
- [ ] BM25 index: new chunks must have `BM25IndexEntry` rows or they are invisible to keyword search
- [ ] Cross-references: if adding new cross-ref extraction, update both the chunker and the Celery task's xref creation loop
- [ ] Circuit breaker: if adding a new external source, ensure `record_success()` / `record_failure()` calls bracket the scraping loop
- [ ] Run `uv run pytest` for backend tests

---

## Known Gotchas & Issues

See `references/known-issues.md` for the complete list. Critical items:

1. **`qdrant_point_id` naming**: Field is named after Qdrant (pre-Pinecone migration). Stores the Pinecone vector ID. Do NOT rename without a migration.
2. **`delete_by_source()` orphans Pinecone vectors**: DB rows are deleted but Pinecone vectors are NOT. Must manually clean Pinecone.
3. **Original chatbot path uses ZERO metadata filters**: `KnowledgeChatbot.retrieve_context()` does pure similarity search with only a 0.3 score threshold. The enhanced path (`retrieve_context_enhanced()`) uses the full pipeline.
4. **Single-vector Pinecone upserts in legacy task**: `_ingest_source_async()` in `tasks/knowledge.py` upserts one vector at a time. Spec 045 tasks use `IngestionManager` which batches correctly.
5. **Router manual upload calling convention bug**: Passes dict list instead of separate params.
6. **Text truncation**: IngestionManager truncates text to 30KB for Pinecone metadata limit. Very long documents lose tail content in metadata `text` field.

---

## External Service Integration

| Service | Wrapper | Key Details |
|---------|---------|-------------|
| **Pinecone** | `core/pinecone_service.py` | Sync client wrapped with `asyncio.to_thread`; batch upsert (100 per batch); `search_multi_namespace` for parallel NS search |
| **Voyage AI** | `core/voyage.py` | Model: `voyage-3.5-lite` (1024 dims); `embed_query()` uses `input_type="query"`, `embed_document()` uses `input_type="document"`; batch with configurable parallelism; tenacity retry (3x exponential) |
| **Anthropic (Claude)** | via `anthropic` SDK | Used in: `QueryExpander` (haiku, 5s timeout), `KnowledgeChatbot.chat_enhanced()` (configurable model), `ClientContextChatbot.chat_with_knowledge()` |
| **HuggingFace** | direct download | `CaseLawScraper` downloads JSONL from Open Australian Legal Corpus |

---

## Key File Paths (all relative to `backend/app/`)

```
modules/knowledge/
  models.py              # DB models
  schemas.py             # Pydantic schemas
  repository.py          # All repositories
  service.py             # Search orchestrator
  router.py              # API endpoints
  chatbot.py             # Knowledge chatbot (original + enhanced)
  client_chatbot.py      # Client-context chatbot
  collections.py         # Pinecone config
  domains.py             # Domain manager
  ingestion_manager.py   # Idempotent ingestion
  chunker.py             # General-purpose SemanticChunker
  intent_detector.py     # Financial query intent (client chat only)
  document_processor.py  # PDF/DOCX/TXT extraction
  context_builder.py     # Client financial context from Xero
  token_budget.py        # Token budget management
  chunkers/
    __init__.py          # Chunker registry
    base.py              # BaseStructuredChunker ABC
    legislation.py       # LegislationChunker
    ruling.py            # RulingChunker
    case_law.py          # CaseLawChunker
  retrieval/
    __init__.py          # ScoredChunk dataclass
    hybrid_search.py     # BM25 + semantic fusion
    query_router.py      # Regex classification
    query_expander.py    # Synonym + LLM expansion
    reranker.py          # Cross-encoder reranking
    citation_verifier.py # Post-generation verification
  scrapers/
    base.py              # BaseScraper ABC
    ato_rss.py           # ATO RSS feeds
    ato_web.py           # ATO website crawler
    ato_api.py           # ATO PDF API
    ato_legal_db.py      # ATO Legal Database
    legislation_gov.py   # legislation.gov.au
    case_law.py          # Legal corpus + Fed Court RSS
    tpb_treasury.py      # TPB + Treasury
    circuit_breaker.py   # DB-backed circuit breaker
  aggregation_models.py  # Client financial summary models
  aggregation_repository.py
  aggregation_service.py
tasks/
  knowledge.py           # Celery ingestion tasks
core/
  pinecone_service.py    # Pinecone wrapper
  voyage.py              # Voyage embedding wrapper
```
