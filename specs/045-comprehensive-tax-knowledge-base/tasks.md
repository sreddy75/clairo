# Tasks: Comprehensive Australian Tax Knowledge Base

**Input**: Design documents from `/specs/045-comprehensive-tax-knowledge-base/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/api.yaml, research.md, quickstart.md

**Tests**: Not explicitly requested in the feature specification. Test tasks are omitted.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `backend/` for Python/FastAPI, `frontend/` for Next.js/TypeScript

---

## Phase 0: Git Setup (REQUIRED)

**Purpose**: Create feature branch before any implementation

- [x] T000 Create feature branch from main
  - Run: `git checkout main && git pull origin main`
  - Run: `git checkout -b 045-comprehensive-tax-knowledge-base`
  - Verify: You are now on the feature branch
  - _Note: Branch already exists — skip if already on it_

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install new dependencies and create package structure

- [x] T001 Install new Python dependencies in `backend/pyproject.toml`
  - Run: `cd backend && uv add rank-bm25 sentence-transformers`
  - `rank-bm25`: BM25 keyword scoring for hybrid search
  - `sentence-transformers`: Cross-encoder re-ranking model

- [x] T002 [P] Create chunkers package structure in `backend/app/modules/knowledge/chunkers/`
  - Create `backend/app/modules/knowledge/chunkers/__init__.py` with chunker registry (maps content_type to chunker class)
  - Create `backend/app/modules/knowledge/chunkers/base.py` with `BaseStructuredChunker` abstract class defining interface: `chunk(raw_content, metadata) -> list[ChunkResult]`
  - `ChunkResult` dataclass: text, content_type, section_ref, cross_references, defined_terms_used, topic_tags, metadata

- [x] T003 [P] Create retrieval package structure in `backend/app/modules/knowledge/retrieval/`
  - Create `backend/app/modules/knowledge/retrieval/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database migration, new models, and base schemas that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Add new SQLAlchemy models in `backend/app/modules/knowledge/models.py`
  - Add `LegislationSection` model (act_id, act_name, act_short_name, section_ref, part, division, subdivision, heading, content_hash, compilation_date, compilation_number, cross_references JSONB, defined_terms JSONB, topic_tags JSONB, is_current, timestamps)
  - Add `ContentCrossReference` model (source_chunk_id FK, target_section_ref, target_chunk_id FK nullable, reference_type, created_at)
  - Add `TaxDomain` model (slug unique, name, description, topic_tags JSONB, legislation_refs JSONB, ruling_types JSONB, icon, display_order, is_active, timestamps)
  - Add `BM25IndexEntry` model (chunk_id FK unique, collection_name, tokens JSONB, section_refs JSONB, created_at)
  - Add `ScraperCircuitBreaker` model (source_host unique, state, failure_count, last_failure_at, last_success_at, opened_at, recovery_timeout_seconds, timestamps)
  - Extend existing `ContentChunk` model with new nullable columns: content_type, section_ref, cross_references JSONB, defined_terms_used JSONB, topic_tags JSONB, fy_applicable JSONB, court, case_citation, legislation_section_id FK, document_hash (SHA-256 of full source document), natural_key (idempotency key like "legislation:s109D-ITAA1936")
  - Extend existing `IngestionJob` model with: completed_items JSONB, failed_items JSONB, total_items INT, is_resumable BOOL, parent_job_id FK nullable
  - Add relationships between models as defined in data-model.md

- [x] T005 Create Alembic migration in `backend/alembic/versions/`
  - Generate migration: `cd backend && uv run alembic revision --autogenerate -m "add_tax_knowledge_models"`
  - Creates tables: `legislation_sections`, `content_cross_references`, `tax_domains`, `bm25_index_entries`, `scraper_circuit_breakers`
  - Adds columns to `content_chunks`: content_type, section_ref, cross_references, defined_terms_used, topic_tags, fy_applicable, court, case_citation, legislation_section_id, document_hash, natural_key
  - Adds columns to `ingestion_jobs`: completed_items, failed_items, total_items, is_resumable, parent_job_id
  - Creates all indexes: GIN on JSONB columns (topic_tags, section_refs), B-tree on section_ref, act_id, court, content_type, legislation_section_id, document_hash, natural_key
  - Include data migration to seed `tax_domains` with 9 initial domains from data-model.md seed data
  - Run: `uv run alembic upgrade head`

- [x] T006 Add Pydantic schemas for new models in `backend/app/modules/knowledge/schemas.py`
  - Add `TaxDomainSchema`, `TaxDomainListResponse`
  - Add `KnowledgeSearchRequest` (query, domain optional, filters optional, limit)
  - Add `SearchFilters` (entity_types, source_types, fy_applicable, exclude_superseded)
  - Add `KnowledgeSearchResponse`, `SearchResultSchema` (chunk_id, title, text, source_url, source_type, section_ref, ruling_number, effective_date, is_superseded, relevance_score, content_type)
  - Add `LegislationSectionResponse` (section_ref, act_name, act_short_name, heading, text, part, division, subdivision, compilation_date, cross_references, defined_terms, related_rulings)
  - Add `KnowledgeChatRequest` (message, conversation_id, domain, client_id)
  - Add `KnowledgeChatResponse` (message, citations, confidence, confidence_score, domain_detected, query_type, superseded_warnings, attribution)
  - Add `CitationSchema` (number, title, url, source_type, section_ref, effective_date, text_preview, score, verified)
  - Add admin schemas: `LegislationIngestRequest`, `CaseLawIngestRequest`, `IngestionJobResponse`, `FreshnessReportResponse`, `CitationAuditRequest`, `CitationAuditResponse`
  - All schemas per contracts/api.yaml

- [x] T007 Add repository methods in `backend/app/modules/knowledge/repository.py`
  - Add `get_legislation_section(section_ref, act_id=None) -> LegislationSection | None`
  - Add `upsert_legislation_section(data) -> LegislationSection`
  - Add `get_cross_references(chunk_id) -> list[ContentCrossReference]`
  - Add `create_cross_reference(data) -> ContentCrossReference`
  - Add `list_tax_domains(active_only=True) -> list[TaxDomain]`
  - Add `get_tax_domain(slug) -> TaxDomain | None`
  - Add `get_bm25_entries(collection_name) -> list[BM25IndexEntry]`
  - Add `upsert_bm25_entry(chunk_id, collection_name, tokens, section_refs) -> BM25IndexEntry`
  - Add `get_freshness_report() -> list[dict]` (aggregated last_ingested_at, chunk_count, error_count per source)
  - Add `get_chunks_by_section_ref(section_ref) -> list[ContentChunk]`
  - Add `get_chunks_by_natural_key(natural_key) -> list[ContentChunk]` — for idempotent replace
  - Add `get_chunks_by_document_hash(document_hash) -> list[ContentChunk]` — for change detection
  - Add `delete_chunks_by_natural_key(natural_key) -> int` — returns count deleted, also deletes associated BM25IndexEntry rows (cascade)
  - Add `get_circuit_breaker(source_host) -> ScraperCircuitBreaker | None`
  - Add `upsert_circuit_breaker(source_host, state, failure_count, ...) -> ScraperCircuitBreaker`
  - Add `update_job_checkpoint(job_id, completed_item, failed_item=None)` — appends to completed_items/failed_items JSONB arrays
  - Add `get_job_completed_items(job_id) -> set[str]` — returns set of already-completed source URLs for resume

- [x] T007a Implement idempotent ingestion manager in `backend/app/modules/knowledge/ingestion_manager.py`
  - `IngestionManager` class that wraps the document-level idempotency logic:
  - `should_ingest(natural_key: str, document_hash: str) -> IngestDecision` — returns SKIP (unchanged), REPLACE (changed), INSERT (new)
  - `replace_document(natural_key: str, new_chunks: list, new_vectors: list)` — atomically deletes old chunks/vectors, inserts new ones
    - Deletes old Pinecone vectors by stored IDs (looks up qdrant_point_id from ContentChunk rows)
    - Deletes old ContentChunk + BM25IndexEntry rows (cascaded)
    - Inserts new chunks, vectors, BM25 entries
  - `insert_document(natural_key: str, document_hash: str, chunks: list, vectors: list)` — inserts new document
  - Generates deterministic Pinecone vector IDs: `{source_type}:{natural_key}:{chunk_index}` (makes re-upserts safe)
  - All DB operations in a single transaction; Pinecone upserts are idempotent via deterministic IDs
  - Natural key construction:
    - Legislation: `legislation:{act_id}:{section_ref}` (e.g., `legislation:C1936A00027:s109D`)
    - Rulings: `ruling:{ruling_number}` (e.g., `ruling:TR-2024-1`)
    - Case law: `case_law:{case_citation}` (e.g., `case_law:2010-HCA-10`)
    - Other: `other:{url_hash}` (SHA-256 of source_url)

- [x] T007b Implement circuit breaker for scrapers in `backend/app/modules/knowledge/scrapers/circuit_breaker.py`
  - `ScraperCircuitBreaker` class wrapping the DB-backed circuit breaker model:
  - `check(source_host: str) -> bool` — returns True if requests are allowed (circuit closed or half-open)
  - `record_success(source_host: str)` — resets failure count, closes circuit
  - `record_failure(source_host: str)` — increments failure count, opens circuit if threshold exceeded (default: 5 consecutive failures)
  - When circuit is OPEN: raise `CircuitOpenError` with `retry_after` timestamp
  - HALF_OPEN state: allow `half_open_max_requests` (default 2) test requests after `recovery_timeout` (default 1 hour)
  - Integrate with `BaseScraper._fetch_url()` — check circuit before each request, record success/failure after

- [x] T007c Update Celery ingestion task for checkpoint/resume in `backend/app/tasks/knowledge.py`
  - Modify `_ingest_source_async()` to use `IngestionManager` for document-level idempotency instead of first-chunk-hash dedup
  - Add checkpoint tracking: after each successful document ingestion, call `repository.update_job_checkpoint(job_id, source_url)`
  - On task resume (retry): load `get_job_completed_items(job_id)` and skip already-completed URLs
  - Replace single-vector Pinecone upserts with batched upserts (batch all chunks for a document, then upsert in one call via `PineconeService.upsert_vectors()` which already batches in groups of 100)
  - Add per-document error isolation: if one document fails, continue to next, record in `failed_items`
  - Update Celery task config to pass `parent_job_id` on retry so checkpoint data is preserved across retries
  - Configure site-specific rate limits:
    - `legislation.gov.au`: 10-second request interval
    - ATO Legal Database: 2-second request interval
    - Federal Court RSS: 1-second (standard)
  - Integrate circuit breaker: check before scraping each source host, skip if circuit is open

**Checkpoint**: Foundation ready — models, migration, schemas, repository, idempotent ingestion, circuit breaker, checkpoint/resume all in place. User story implementation can begin.

---

## Phase 3: User Story 1 - Tax Research Without Client Context (Priority: P1) - MVP

**Goal**: Accountants can ask general tax questions and get comprehensive answers with citations from legislation, rulings, and guidance. Direct Tax Guru competitor feature.

**Independent Test**: Ask "What are the Div 7A rules?" and verify the response cites ITAA 1936 sections (s109D-109N), relevant TRs/TDs, and includes effective dates.

### Implementation for User Story 1

- [x] T008 [P] [US1] Implement ATO Legal Database scraper in `backend/app/modules/knowledge/scrapers/ato_legal_db.py`
  - Extend existing ATO scraper pattern from `scrapers/base.py`
  - Use print URL pattern: `/law/view/print?DocID={docid}&PiT=99991231235958` for clean HTML
  - Enumerate DocIDs by prefix: TXR (Tax Rulings), TXD (Tax Determinations), GST (GSTR/GSTD), CLR (Class Rulings), PRR (Product Rulings), COG (Guidelines), TPA (Practical Compliance), AID (Interpretive Decisions), PSR (Private Rulings), SRB (Super Rulings), SAV (Law Admin Practice Statements)
  - Extract ruling metadata: title, status (current/draft/withdrawn/superseded), superseded_by, related_legislation, date_of_effect
  - Parse ruling structure: Ruling section, Explanation, Examples, Date of Effect
  - Integrate with circuit breaker (check before each request, record success/failure)
  - Configure 2-second request interval for ATO Legal Database
  - Return `ScrapedContent` with natural_key set to `ruling:{ruling_number}` and document_hash of full raw HTML
  - Populate all metadata fields: ruling_number, source_type, effective_date, is_superseded, superseded_by, confidence_level="high", topic_tags (derived from ruling prefix)

- [x] T009 [P] [US1] Implement legislation scraper in `backend/app/modules/knowledge/scrapers/legislation_gov.py`
  - Fetch EPUB files from legislation.gov.au for key tax acts:
    - ITAA 1997 (C2004A05138), ITAA 1936 (C1936A00027), GST Act 1999 (C2004A00446), FBTAA 1986 (C2004A03401), TAA 1953 (C2004A00957), SIS Act 1993 (C2004A00534), SGAA 1992 (C2004A00477)
  - Parse EPUB HTML using BeautifulSoup to extract sections with TOC anchors
  - **Respect 10-second crawl delay** for legislation.gov.au (site-specific rate limit in scraper config)
  - Integrate with circuit breaker for legislation.gov.au host
  - Extract hierarchical metadata: act, part, division, subdivision, section
  - Track compilation numbers and dates for amendment detection
  - Calculate document_hash (SHA-256 of full section text) for change detection
  - Return `ScrapedContent` per section with natural_key set to `legislation:{act_id}:{section_ref}` (e.g., `legislation:C1936A00027:s109D`)
  - Populate `LegislationSection` records during ingestion with all metadata
  - Set topic_tags based on parent division/part (e.g., Division 7A sections get ["division_7a", "deemed_dividend"])

- [x] T010 [P] [US1] Implement legislation chunker in `backend/app/modules/knowledge/chunkers/legislation.py`
  - Extend `BaseStructuredChunker`
  - Chunk at section level (256-512 tokens primary boundary)
  - Split at subsection only for very long sections (>512 tokens)
  - Never split mid-paragraph
  - Prefix every chunk with section number and heading
  - Set content_type to "operative_provision", "definition", or "example" based on section analysis
  - Extract cross-references to other sections via regex (e.g., "section 109D", "Div 7A", "Part 3-1")
  - Extract defined terms used (match against known definitions list)
  - Assign topic_tags based on parent division/part

- [x] T011 [P] [US1] Implement ruling chunker in `backend/app/modules/knowledge/chunkers/ruling.py`
  - Extend `BaseStructuredChunker`
  - Keep "Ruling" section as single chunk (content_type="ruling")
  - Split "Explanation" by numbered paragraphs (content_type="explanation")
  - Keep "Examples" as individual chunks (content_type="example")
  - "Date of Effect" as single chunk
  - Preserve ruling number in every chunk's section_ref
  - Extract cross-references to legislation sections and other rulings
  - Tag with topic_tags based on ruling type prefix (GSTR -> GST, TR -> varies)

- [x] T012 [US1] Implement hybrid search in `backend/app/modules/knowledge/retrieval/hybrid_search.py`
  - Implement BM25 scoring using `rank-bm25` library
  - Load BM25 index from `bm25_index_entries` table for given collection
  - Implement Reciprocal Rank Fusion (RRF) to combine dense (Pinecone) + sparse (BM25) scores
  - Default fusion weights: 0.6 semantic / 0.4 keyword
  - Accept dynamic weight override based on query type
  - `hybrid_search(query, collection, limit=30, semantic_weight=0.6, pinecone_filter=None) -> list[ScoredChunk]`
  - **Pinecone metadata filtering**: Accept and pass filter dict to Pinecone query. Key filters:
    - `is_superseded: {"$ne": true}` — always exclude superseded content by default
    - `source_type: {"$in": [...]}` — filter by content source
    - `topic_tags: {"$in": [...]}` — domain scoping
    - `section_ref: {"$eq": "..."}` — exact section match for SECTION_LOOKUP
    - `ruling_number: {"$eq": "..."}` — exact ruling match for RULING_LOOKUP
    - `court: {"$eq": "..."}` — case law court filtering
  - BM25 side: filter `bm25_index_entries` by `section_refs` JSONB for exact-match queries before scoring
  - Integrate with existing `PineconeService.search()` / `search_multi_namespace()`

- [x] T013 [US1] Implement cross-encoder re-ranker in `backend/app/modules/knowledge/retrieval/reranker.py`
  - Load `cross-encoder/ms-marco-MiniLM-L-6-v2` model via sentence-transformers
  - `rerank(query, candidates: list[ScoredChunk], top_k=10) -> list[ScoredChunk]`
  - Takes top 30 candidates from hybrid search, re-ranks, returns top 10
  - Cache model in memory (singleton pattern) to avoid reload per request
  - Target latency: <100ms for 30 candidates

- [x] T014 [US1] Implement query router in `backend/app/modules/knowledge/retrieval/query_router.py`
  - Classify incoming queries into types: SECTION_LOOKUP, RULING_LOOKUP, CONCEPTUAL, PROCEDURAL, SCENARIO, CASE_LAW
  - SECTION_LOOKUP: regex for section/division patterns (e.g., "s109D", "section 104-10", "Div 7A")
  - RULING_LOOKUP: regex for TR/GSTR/TD/PCG/GSTD patterns
  - CASE_LAW: keywords like "court", "case", "tribunal", "decision"
  - PROCEDURAL: action verbs + process terms ("how to", "steps to", "register for")
  - SCENARIO: factual patterns ("my client has", "a company with", "if a business")
  - CONCEPTUAL: default fallback for generic questions
  - **Query router drives both fusion weights AND Pinecone metadata filters**:
  - Return `QueryClassification(query_type, confidence, pinecone_filter, fusion_weights, extracted_refs)`
  - Each type maps to specific retrieval strategy:
    - SECTION_LOOKUP: fusion (0.2/0.8), filter `{section_ref: {$eq: extracted_ref}, is_superseded: {$ne: true}}`
    - RULING_LOOKUP: fusion (0.2/0.8), filter `{ruling_number: {$eq: extracted_ref}, is_superseded: {$ne: true}}`
    - CONCEPTUAL: fusion (0.7/0.3), filter `{is_superseded: {$ne: true}}`, plus topic_tags if domain detected
    - PROCEDURAL: fusion (0.5/0.5), filter `{source_type: {$in: ["ato_guide", "ato_ruling"]}, is_superseded: {$ne: true}}`
    - SCENARIO: fusion (0.6/0.4), filter `{is_superseded: {$ne: true}}`
    - CASE_LAW: fusion (0.5/0.5), filter `{source_type: {$eq: "case_law"}}`
  - Extract section/ruling references from query text via regex and include in `extracted_refs` for downstream use

- [x] T015 [US1] Implement query expander in `backend/app/modules/knowledge/retrieval/query_expander.py`
  - LLM-assisted expansion for CONCEPTUAL and SCENARIO queries
  - Use Claude to generate 2-3 query variants that include relevant section numbers, legal terms, and synonyms
  - Legal synonym table: GST <-> Goods and Services Tax <-> GST Act 1999, Div 7A <-> Division 7A <-> deemed dividend, etc.
  - `expand_query(query, query_type) -> list[str]` returning original + expanded queries
  - Merge results from all query variants using RRF
  - Skip expansion for SECTION_LOOKUP and RULING_LOOKUP (already precise)

- [x] T016 [US1] Wire up enhanced search in knowledge service `backend/app/modules/knowledge/service.py`
  - Add `search_knowledge(request: KnowledgeSearchRequest) -> KnowledgeSearchResponse`
  - Pipeline: query_router -> query_expander (if needed) -> hybrid_search -> reranker -> format results
  - Apply filters from request (entity_types, source_types, fy_applicable, exclude_superseded)
  - Return results with query_type, domain_detected, total_results

- [x] T017 [US1] Add search and domain API endpoints in `backend/app/modules/knowledge/router.py`
  - `GET /api/v1/knowledge/domains` — list active tax domains from repository
  - `GET /api/v1/knowledge/domains/{slug}` — get single domain details
  - `POST /api/v1/knowledge/search` — invoke search pipeline, return KnowledgeSearchResponse
  - All endpoints require authentication (existing auth middleware)

- [x] T018 [US1] Add ingestion Celery tasks in `backend/app/tasks/knowledge.py`
  - Add `ingest_ato_legal_database()` task — runs ATO Legal DB scraper, chunks with ruling chunker, embeds, stores
  - Add `ingest_legislation(acts: list[str] | None)` task — runs legislation scraper for specified acts (or all configured), chunks with legislation chunker, embeds, stores, creates LegislationSection records
  - **Both tasks use `IngestionManager` for document-level idempotency** (from T007a):
    - Compute natural_key and document_hash per scraped document
    - Call `should_ingest()` — SKIP if unchanged, REPLACE if changed, INSERT if new
    - Use deterministic Pinecone vector IDs (`{source_type}:{natural_key}:{chunk_index}`)
    - Track checkpoint per document via `update_job_checkpoint()`
  - Both tasks: populate BM25IndexEntry for each chunk (tokenize text, extract section_refs as normalised tokens)
  - Both tasks: create ContentCrossReference entries for detected cross-references
  - Both tasks: store full Pinecone metadata per vector (content_type, section_ref, topic_tags, ruling_number, is_superseded, effective_date, confidence_level, document_hash — per spec 1.5.3)
  - Both tasks: use batched Pinecone upserts (all chunks for a document in one call)
  - Update existing ingestion infrastructure to use new structured chunkers for matching content types

- [x] T019 [US1] Add admin ingestion endpoints in `backend/app/modules/knowledge/router.py`
  - `POST /api/v1/admin/knowledge/ingest/legislation` — accepts LegislationIngestRequest, dispatches Celery task, returns IngestionJobResponse with 202
  - Wire up admin auth check (existing admin middleware)

- [x] T020 [US1] Extend knowledge chatbot for tax research in `backend/app/modules/knowledge/chatbot.py`
  - Update retrieval to use new hybrid search pipeline instead of direct Pinecone-only search
  - Add grounding enforcement system prompt for tax research mode (answer ONLY from context, decline if insufficient)
  - Add confidence scoring to responses: `0.4 * top_score + 0.3 * mean_top5 + 0.3 * citation_verified_rate`
  - Add superseded content warnings when retrieved chunks have is_superseded=True
  - Add required attribution text for legislation sources
  - Return enhanced response matching KnowledgeChatResponse schema

**Checkpoint**: User Story 1 complete — general tax research with hybrid search, re-ranking, query routing, and structured ingestion pipeline. Accountants can ask tax questions and get cited answers.

---

## Phase 4: User Story 4 - Legislation Section Lookup (Priority: P1)

**Goal**: Accountants can query specific legislation sections by reference and get exact text with contextual information.

**Independent Test**: Ask "What does s104-10 ITAA 1997 say?" and verify the response returns exact section text, identifies it as CGT Event A1, and notes related sections.

### Implementation for User Story 4

- [x] T021 [US4] Add legislation section lookup endpoint in `backend/app/modules/knowledge/router.py`
  - `GET /api/v1/knowledge/legislation/{section_ref}` — look up section by reference (e.g., s109D-ITAA1936)
  - Parse section_ref to extract section number and act identifier
  - Query `legislation_sections` table for match
  - If found: return full section text (from associated ContentChunk), cross-references, defined_terms, related rulings (query chunks with matching ruling references)
  - If not found: 404

- [x] T022 [US4] Add legislation lookup service method in `backend/app/modules/knowledge/service.py`
  - `get_legislation_section(section_ref: str) -> LegislationSectionResponse`
  - Parse flexible section references: "s109D", "s109D ITAA 1936", "s109D-ITAA1936", "section 109D"
  - Resolve to LegislationSection record and associated content chunks
  - Gather cross-referenced sections and related rulings
  - Return structured response with full text, hierarchy (part/division/subdivision), and related content

- [x] T023 [US4] Integrate section lookup with query router in `backend/app/modules/knowledge/retrieval/query_router.py`
  - When query_router detects SECTION_LOOKUP type, switch to keyword-heavy fusion (0.2 semantic / 0.8 keyword)
  - Attempt direct section lookup first via repository before falling back to hybrid search
  - If direct match found, prioritize that result at top of search results

**Checkpoint**: User Story 4 complete — direct legislation section lookup with cross-references and related rulings.

---

## Phase 5: User Story 6 - Citation Verification & Trust (Priority: P1)

**Goal**: Every AI-generated answer includes verifiable citations that actually exist in the knowledge base. No fabricated references.

**Independent Test**: Ask 10 different tax questions and verify every citation in every response corresponds to an actual document in the knowledge base.

### Implementation for User Story 6

- [x] T024 [US6] Implement citation verifier in `backend/app/modules/knowledge/retrieval/citation_verifier.py`
  - `verify_citations(response_text: str, retrieved_chunks: list[ContentChunk]) -> CitationVerificationResult`
  - Extract all section/ruling references from LLM response via regex (s109D, TR 2024/1, GSTR 2000/1, etc.)
  - Cross-reference each citation against chunks in retrieved context
  - For each citation: mark as `verified=True` if found in context, `verified=False` if not
  - Ungrounded citations: flag with disclaimer text or remove from response
  - Return `CitationVerificationResult(citations: list[Citation], ungrounded_count: int, verification_rate: float)`
  - Calculate confidence score: `0.4 * top_score + 0.3 * mean_top5 + 0.3 * citation_verified_rate`

- [x] T025 [US6] Integrate citation verification into chatbot pipeline in `backend/app/modules/knowledge/chatbot.py`
  - After LLM generates response, run citation_verifier before returning to user
  - Attach verified citations to response (CitationSchema with verified boolean)
  - Set confidence tier: High (>0.7), Medium (0.5-0.7), Low (<0.5)
  - Low confidence: override response with decline message
  - Add superseded_warnings array for any cited content that is superseded
  - Ensure every response includes confidence level and attribution text

- [x] T026 [US6] Add citation audit admin endpoint in `backend/app/modules/knowledge/router.py`
  - `POST /api/v1/admin/knowledge/verify-citations` — accepts CitationAuditRequest (sample_size)
  - Fetches recent knowledge chat responses from DB
  - Runs citation verification on each response
  - Returns CitationAuditResponse (total_audited, citations_checked, citations_verified, citations_ungrounded, verification_rate, ungrounded_examples)

**Checkpoint**: User Story 6 complete — all citations verified post-generation, confidence scoring active, admin can audit citation accuracy.

---

## Phase 6: User Story 2 - Client-Contextual Tax Research (Priority: P1)

**Goal**: Accountants select a client and get tax answers enriched with the client's actual financial data from Xero.

**Independent Test**: Select a client with shareholder loans in Xero, ask about Div 7A, verify response references both legislation AND client's specific loan amounts.

**Depends on**: US1 (search pipeline), US6 (citation verification)

### Implementation for User Story 2

- [x] T027 [US2] Extend client chatbot with knowledge grounding in `backend/app/modules/knowledge/client_chatbot.py`
  - Accept optional `client_id` in chat request
  - When client_id provided: fetch client's financial context from Xero data (existing client service)
  - Combine knowledge base retrieval results with client financial context in LLM prompt
  - System prompt instructs LLM to reference both legislation/rulings AND client's specific financial data
  - Example: "Based on s109D ITAA 1936, the $150K shareholder loan shown in [Client]'s balance sheet would be treated as a deemed dividend..."
  - Use same citation verification pipeline from US6

- [x] T028 [US2] Add client_id parameter support to knowledge chat endpoint in `backend/app/modules/knowledge/router.py`
  - Extend `POST /api/v1/knowledge/chat` to accept optional `client_id` from KnowledgeChatRequest
  - When client_id provided: validate client exists and belongs to tenant, then route to client_chatbot
  - When client_id not provided: route to standard knowledge chatbot (US1 flow)

**Checkpoint**: User Story 2 complete — client-contextual answers combining knowledge base with Xero financial data. Clairo's key differentiator over Tax Guru.

---

## Phase 7: User Story 3 - Specialist Tax Modules (Priority: P2)

**Goal**: Knowledge chatbot routes queries to specialist domains. Accountants can browse and select specialist areas like GST, SMSF, CGT, Division 7A, FBT, Trusts.

**Independent Test**: Ask a CGT-specific question and verify the response draws primarily from CGT-related legislation (ITAA 1997 Part 3-1) and CGT-specific rulings.

**Depends on**: US1 (search pipeline)

### Implementation for User Story 3

- [x] T029 [US3] Implement domain configuration module in `backend/app/modules/knowledge/domains.py`
  - Load specialist domain config from `tax_domains` table (via repository)
  - `get_domain_filters(slug: str) -> DomainFilters` — returns topic_tags, legislation_refs, ruling_types for scoped retrieval
  - `detect_domain(query: str) -> str | None` — auto-detect domain from query content using keyword matching against domain topic_tags
  - Cache domain config in memory with TTL

- [x] T030 [US3] Integrate domain scoping into search pipeline in `backend/app/modules/knowledge/service.py`
  - When domain is specified in search/chat request: apply domain's topic_tags as filter on retrieval
  - When domain is auto-detected: apply same scoping, return domain_detected in response
  - Domain scoping adds Pinecone metadata filter on topic_tags + BM25 filtered to matching chunks
  - Extend hybrid_search to accept optional domain_filters parameter

- [x] T031 [P] [US3] Create domain selector frontend component in `frontend/src/components/knowledge/domain-selector.tsx`
  - Fetch domains from `GET /api/v1/knowledge/domains`
  - Display as clickable chips/cards with icon, name, and description
  - Selected domain passed to chat/search requests as `domain` parameter
  - "All Topics" option to clear domain filter
  - Responsive grid layout

- [x] T032 [P] [US3] Create confidence badge frontend component in `frontend/src/components/knowledge/confidence-badge.tsx`
  - Display confidence tier (High/Medium/Low) with color coding (green/amber/red)
  - Show confidence score on hover
  - Render alongside each knowledge chat response

- [x] T033 [P] [US3] Create enhanced citation panel frontend component in `frontend/src/components/knowledge/enhanced-citation-panel.tsx`
  - Display numbered citations with source type icon, title, section_ref, effective_date
  - Clickable citations expand to show text_preview and source_url link
  - Verified badge (checkmark) for verified citations
  - Warning indicator for unverified citations

- [x] T034 [P] [US3] Create supersession banner frontend component in `frontend/src/components/knowledge/supersession-banner.tsx`
  - Yellow warning banner displayed when response references superseded content
  - Text: "Note: Some referenced content has been superseded. [Details]"
  - Expandable to show which specific rulings/sections are superseded and their replacements

- [x] T035 [US3] Integrate new components into knowledge chat UI in `frontend/src/app/(dashboard)/knowledge/`
  - Add domain-selector above chat input
  - Add confidence-badge to each assistant message
  - Replace existing citation display with enhanced-citation-panel
  - Add supersession-banner when superseded_warnings present in response
  - Wire up domain parameter in chat API calls

**Checkpoint**: User Story 3 complete — specialist domains browsable and selectable, domain-scoped retrieval, polished citation and confidence UI.

---

## Phase 8: User Story 5 - Knowledge Base Freshness & Monitoring (Priority: P2)

**Goal**: Automatic monitoring of ATO RSS feeds and legislation for new/updated content. Superseded rulings auto-detected. Admin dashboard shows freshness status.

**Independent Test**: Verify a ruling published this week appears in knowledge base within 24 hours, and that superseded rulings are marked.

**Depends on**: US1 (ingestion pipeline)

### Implementation for User Story 5

- [x] T036 [P] [US5] Implement case law scraper in `backend/app/modules/knowledge/scrapers/case_law.py`
  - Download Open Australian Legal Corpus from HuggingFace (JSONL, one-time bulk load)
  - Filter for tax-relevant cases using keyword/NLP classification (keywords: "tax", "GST", "income tax", "deduction", "capital gain", "ATO", "Commissioner of Taxation")
  - Parse Federal Court RSS feed for ongoing new tax judgments
  - Return `ScrapedContent` with natural_key set to `case_law:{case_citation}` and document_hash of full text
  - Return structured results with case metadata: citation, court (HCA/FCA/FCAFC/AATA), date, legislation_considered
  - Set topic_tags based on legislation_considered (cases referencing GST Act tagged with "GST", etc.)

- [x] T037 [P] [US5] Implement case law chunker in `backend/app/modules/knowledge/chunkers/case_law.py`
  - Extend `BaseStructuredChunker`
  - Chunk headnote as single high-priority chunk (content_type="headnote")
  - Chunk reasoning by issue/numbered paragraph (content_type="reasoning")
  - Chunk orders as single chunk (content_type="orders")
  - Set court and case_citation metadata on all chunks
  - Extract legislation references from reasoning sections

- [x] T038 [P] [US5] Implement TPB/Treasury scraper in `backend/app/modules/knowledge/scrapers/tpb_treasury.py`
  - Scrape TPB information products (HTML pages)
  - Download Treasury exposure drafts (PDF via existing document processor if available)
  - Return structured results for standard chunking pipeline

- [x] T039 [US5] Add case law and TPB/Treasury ingestion Celery tasks in `backend/app/tasks/knowledge.py`
  - Add `ingest_case_law(source: str, filter_tax_only: bool)` task — runs case law scraper, chunks, embeds, stores
  - Add `ingest_tpb_treasury()` task — runs TPB/Treasury scraper, chunks, embeds, stores
  - Both tasks use `IngestionManager` for document-level idempotency (natural_key: `case_law:{citation}` or `tpb:{url_hash}`)
  - Both tasks populate BM25IndexEntry and ContentCrossReference entries
  - Both tasks store full Pinecone metadata (source_type, content_type, court, case_citation, topic_tags, is_superseded)

- [x] T040 [US5] Add case law admin ingestion endpoint in `backend/app/modules/knowledge/router.py`
  - `POST /api/v1/admin/knowledge/ingest/case-law` — accepts CaseLawIngestRequest (source, filter_tax_only), dispatches Celery task, returns 202

- [x] T041 [US5] Implement content freshness monitoring in `backend/app/tasks/knowledge.py`
  - Add Celery Beat scheduled tasks:
    - `monitor_ato_rss` (every 4 hours) — check ATO RSS for new rulings, trigger ingestion
    - `delta_crawl_ato_legal_db` (weekly) — detect updated/new documents via `IngestionManager.should_ingest()` (document_hash comparison)
    - `sync_legislation` (monthly) — detect amended acts via compilation number change, re-ingest changed sections (REPLACE semantics)
    - `monitor_federal_court_rss` (daily) — ingest new tax judgments
    - `check_supersessions` (weekly) — detect and mark superseded rulings (set is_superseded=True, superseded_by field on both DB and Pinecone metadata)
  - All scheduled tasks: check circuit breaker before hitting external sites, skip if circuit is open
  - Each job logs to existing ingestion_jobs table with checkpoint/resume support
  - **Stale content grace period**: if a source is temporarily unreachable, keep existing content. Only flag as "stale" after 7 days (rulings), 30 days (legislation). Never auto-delete due to scraping failures.

- [x] T042 [US5] Add freshness report admin endpoint in `backend/app/modules/knowledge/router.py`
  - `GET /api/v1/admin/knowledge/freshness` — calls repository.get_freshness_report()
  - Returns FreshnessReportResponse: sources array (source_type, source_name, last_ingested_at, chunk_count, error_count, freshness_status), total_chunks, last_updated
  - freshness_status: "fresh" (<24h for RSS, <7d for crawl, <30d for legislation), "stale", "error", "never_ingested"

**Checkpoint**: User Story 5 complete — all content sources ingesting, automated freshness monitoring, admin can view freshness status.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T043 [P] Add BM25 index backfill task in `backend/app/tasks/knowledge.py`
  - One-time task to populate BM25IndexEntry for all existing content_chunks that don't have an entry
  - Tokenize chunk text, extract section_refs, insert BM25IndexEntry records

- [x] T044 [P] Add attribution text to all responses in `backend/app/modules/knowledge/chatbot.py`
  - Legislation sources: "Based on content from the Federal Register of Legislation at [date]. For the latest information on Australian Government legislation please go to https://www.legislation.gov.au"
  - ATO content: no specific attribution but must not imply ATO endorsement
  - Add "This is general information, not professional advice" disclaimer to all responses

- [x] T045 Update knowledge module `__init__.py` exports and ensure all new modules are importable
  - Verify all new scrapers, chunkers, and retrieval modules are properly imported
  - Verify new router endpoints are registered in the FastAPI app

- [x] T046 Run full integration validation
  - Run: `cd backend && uv run alembic upgrade head` — verify migration applies cleanly
  - Run: `cd backend && uv run pytest tests/ -k "knowledge" -v` — verify all existing knowledge tests pass
  - Verify domain seeding: query `tax_domains` table, confirm 9 domains present
  - Verify new endpoints respond: GET /api/v1/knowledge/domains, POST /api/v1/knowledge/search

---

## Phase FINAL: PR & Merge (REQUIRED)

**Purpose**: Create pull request and merge to main

- [ ] TFINAL-1 Ensure all tests pass
  - Run: `cd backend && uv run pytest tests/ -k "knowledge" -v`
  - All tests must pass before PR

- [ ] TFINAL-2 Run linting and type checking
  - Run: `cd backend && uv run ruff check .`
  - Fix any issues

- [ ] TFINAL-3 Push feature branch and create PR
  - Run: `git push -u origin 045-comprehensive-tax-knowledge-base`
  - Run: `gh pr create --title "Spec 045: Comprehensive Australian Tax Knowledge Base" --body "Implements comprehensive tax knowledge base with hybrid search, structured chunking for legislation/rulings/case law, cross-encoder re-ranking, citation verification, specialist domains, and content freshness monitoring. Replaces Tax Guru capability."`
  - Include summary of changes in PR description

- [ ] TFINAL-4 Address review feedback (if any)
  - Make requested changes
  - Push additional commits

- [ ] TFINAL-5 Merge PR to main
  - Squash merge after approval
  - Delete feature branch after merge

- [ ] TFINAL-6 Update ROADMAP.md
  - Mark spec 045 as COMPLETE
  - Update current focus to next spec

---

## Dependencies & Execution Order

### Phase Dependencies

- **Git Setup (Phase 0)**: MUST be done first — already complete (branch exists)
- **Setup (Phase 1)**: Install deps, create package structure
- **Foundational (Phase 2)**: Models, migration, schemas, repository, IngestionManager, circuit breaker, checkpoint/resume — BLOCKS all user stories
- **US1 (Phase 3)**: Core search pipeline — BLOCKS US2, US4, US6
- **US4 (Phase 4)**: Legislation lookup — can start after US1 T012-T014 (hybrid search + reranker + router)
- **US6 (Phase 5)**: Citation verification — can start after US1 T020 (chatbot integration)
- **US2 (Phase 6)**: Client-contextual — depends on US1 + US6
- **US3 (Phase 7)**: Specialist domains — depends on US1 (backend), frontend components are parallel
- **US5 (Phase 8)**: Freshness monitoring — depends on US1 (ingestion pipeline)
- **Polish (Phase 9)**: After all user stories
- **PR (Phase FINAL)**: After Polish

### User Story Dependencies

- **US1 (P1)**: Foundation only — no story dependencies. MVP story.
- **US4 (P1)**: Depends on US1 hybrid search + query router
- **US6 (P1)**: Depends on US1 chatbot pipeline
- **US2 (P1)**: Depends on US1 + US6 (needs search + citation verification)
- **US3 (P2)**: Depends on US1 (backend scoping); frontend components are independent
- **US5 (P2)**: Depends on US1 (ingestion infrastructure); new scrapers are independent

### Within Each User Story

- Scrapers/chunkers can be built in parallel (different files)
- Retrieval components have sequential dependencies: hybrid_search -> reranker -> query_router -> query_expander
- Service integration depends on all retrieval components
- API endpoints depend on service methods
- Frontend depends on API endpoints

### Parallel Opportunities

- T002, T003: Package structure creation (parallel)
- T008, T009, T010, T011: Scrapers and chunkers (all parallel, different files)
- T031, T032, T033, T034: Frontend components (all parallel, different files)
- T036, T037, T038: Case law + TPB scrapers and chunkers (all parallel)
- T043, T044: Polish tasks (parallel)

---

## Parallel Example: User Story 1

```bash
# Launch all scrapers and chunkers in parallel:
Task T008: "ATO Legal Database scraper in backend/app/modules/knowledge/scrapers/ato_legal_db.py"
Task T009: "Legislation scraper in backend/app/modules/knowledge/scrapers/legislation_gov.py"
Task T010: "Legislation chunker in backend/app/modules/knowledge/chunkers/legislation.py"
Task T011: "Ruling chunker in backend/app/modules/knowledge/chunkers/ruling.py"

# Then sequentially build retrieval pipeline:
Task T012: "Hybrid search" (depends on nothing in this story)
Task T013: "Re-ranker" (depends on nothing in this story)
Task T014: "Query router" (depends on T012 for fusion weight config)
Task T015: "Query expander" (depends on T014 for query type)

# Then wire up:
Task T016: "Service integration" (depends on T012-T015)
Task T017: "API endpoints" (depends on T016)
Task T018: "Celery tasks" (depends on T008-T011)
Task T019: "Admin endpoints" (depends on T018)
Task T020: "Chatbot integration" (depends on T016)
```

---

## Parallel Example: User Story 3 (Frontend)

```bash
# All frontend components can be built in parallel:
Task T031: "Domain selector in frontend/src/components/knowledge/domain-selector.tsx"
Task T032: "Confidence badge in frontend/src/components/knowledge/confidence-badge.tsx"
Task T033: "Enhanced citation panel in frontend/src/components/knowledge/enhanced-citation-panel.tsx"
Task T034: "Supersession banner in frontend/src/components/knowledge/supersession-banner.tsx"

# Then integrate:
Task T035: "Wire components into knowledge chat UI" (depends on T031-T034)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (deps + package structure)
2. Complete Phase 2: Foundational (models, migration, schemas, repository)
3. Complete Phase 3: User Story 1 (scrapers, chunkers, hybrid search, re-ranking, query routing, chatbot)
4. **STOP and VALIDATE**: Run initial ingestion, test search quality
5. Deploy/demo: accountants can ask tax questions and get cited answers

### Incremental Delivery

1. Setup + Foundational -> Foundation ready
2. Add US1 -> Test -> Deploy (MVP! Tax research works)
3. Add US4 -> Test -> Deploy (Section lookup works)
4. Add US6 -> Test -> Deploy (Citations verified)
5. Add US2 -> Test -> Deploy (Client context works - Clairo's moat)
6. Add US3 -> Test -> Deploy (Specialist domains + polished UI)
7. Add US5 -> Test -> Deploy (Freshness monitoring active)

### Suggested MVP Scope

**MVP = Phase 0 + Phase 1 + Phase 2 + Phase 3 (User Story 1)**

This gives accountants the core Tax Guru competitor: ask a tax question, get an answer with citations from legislation and ATO rulings. Everything else builds on top incrementally.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Total tasks: 50 (T000-T046 including T007a/b/c + 6 TFINAL tasks)
- New foundational tasks T007a (IngestionManager), T007b (CircuitBreaker), T007c (checkpoint/resume) are critical path
- Estimated per plan.md: ~5-6 weeks total
