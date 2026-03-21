# Ingestion Pipeline -- Complete Reference

## Pipeline Stages

### Stage 1: Source Discovery & Scraping

All scrapers extend `BaseScraper` (`scrapers/base.py`), which provides:

- **Rate limiting**: Token-bucket via semaphore + configurable request interval (default 1 req/s)
- **Concurrency control**: Semaphore (default 3 concurrent requests)
- **Retry logic**: Tenacity with 3 attempts, exponential backoff (1-30s)
- **HTTP client**: httpx AsyncClient with 30s timeout, 5MB max content
- **Abstract interface**: `source_type` (property), `collection_name` (property), `get_content_urls()` (AsyncIterator), `extract_content()` -> `ScrapedContent | None`

`ScrapedContent` is a dataclass with:
- `text`, `title`, `source_url`, `source_type`
- `effective_date`, `expiry_date` (optional)
- `entity_types`, `industries` (optional lists)
- `ruling_number`, `is_superseded`, `superseded_by` (optional)
- `raw_metadata` (dict for extra fields)
- `to_chunk_payload()` method for Pinecone metadata conversion

#### Scraper Implementations

| Scraper | Source | Rate | Special Behavior |
|---------|--------|------|-----------------|
| `ATORSSScraper` | ATO RSS feeds (rulings, news, legal_database) | 1 req/s | Extracts ruling numbers, classifies source types |
| `ATOWebScraper` | ATO website pages | 1 req/s | Configurable crawl depth, section-based or URL list |
| `ATOAPIScraper` | ATO public API (PDF guides) | 1 req/s | PyMuPDF for PDF extraction; predefined content IDs for BAS, GST, PAYG, FBT |
| `ATOLegalDatabaseScraper` | ATO Legal Database (rulings) | 0.5 req/s | Print-friendly URLs; discovery via What's New + DocID enumeration; detects withdrawn/superseded; ruling types: TR, GSTR, TD, PCG, CR, PR, SGR, PS LA, AID |
| `LegislationGovScraper` | legislation.gov.au | 10s crawl delay | 7 configured acts (ITAA 1997, ITAA 1936, GST Act, FBTAA, TAA 1953, SIS Act, SGAA); overrides `scrape_all()` for per-section yield; extracts cross-references, topic tags, compilation info |
| `CaseLawScraper` | Open Australian Legal Corpus (HF JSONL) + Federal Court RSS | 1 req/s | Tax-relevance keyword filtering; extracts citation, court, legislation references |
| `TPBTreasuryScraper` | TPB info products + Treasury exposure drafts | 1 req/s | Standard HTML scraping |

#### Circuit Breaker (`scrapers/circuit_breaker.py`)

DB-backed circuit breaker (`ScraperCircuitBreakerState` model):
- **States**: CLOSED (normal) -> OPEN (failing) -> HALF_OPEN (testing)
- **Failure threshold**: 5 consecutive failures to open
- **Recovery timeout**: 3600 seconds before transitioning to half-open
- **Half-open test requests**: 2 successes required to close
- **Methods**: `check(host)`, `record_success(host)`, `record_failure(host)`
- Raises `CircuitOpenError` when open

---

### Stage 2: Chunking

Two chunking paths exist:

#### General-purpose: `SemanticChunker` (`chunker.py`)

Used by the legacy `_ingest_source_async()` Celery task for ato_rss, ato_web, ato_api sources.

Configuration:
- Chunk size: 1500 characters
- Overlap: 200 characters
- Min chunk: 100 characters
- Max chunk: 3000 characters
- Split strategy: Recursive with semantic separators (paragraph breaks -> line breaks -> sentences -> words)

Methods: `chunk_text()`, `chunk_html()`, `chunk_structured_content()`

Returns list of chunks with `content_hash` (SHA-256 of chunk text).

#### Structure-aware: Chunker Registry (`chunkers/__init__.py`)

Used by Spec 045 Celery tasks. Registry maps content_type to chunker class:

```python
get_chunker("legislation")  # -> LegislationChunker
get_chunker("ruling")       # -> RulingChunker
get_chunker("case_law")     # -> CaseLawChunker
```

All extend `BaseStructuredChunker` (`chunkers/base.py`) which provides:
- Abstract `chunk(raw_content, metadata) -> list[ChunkResult]`
- `ChunkResult` dataclass: text, content_type, section_ref, cross_references, defined_terms_used, topic_tags, metadata
- Helper `_split_at_boundary()`: paragraph-aware splitting, 512 max tokens, 64 min tokens
- Common regex patterns: `SECTION_REF_PATTERN`, `RULING_REF_PATTERN`
- Cross-reference extraction: `extract_section_references()`, `extract_ruling_references()`

##### LegislationChunker (`chunkers/legislation.py`)

- Chunks at section level (256-512 tokens)
- Classifies `content_type`: `operative_provision`, `definition`, `example`
- Extracts cross-references to other sections
- Extracts defined terms from `COMMON_DEFINED_TERMS` list
- Registered as `"legislation"` chunker

##### RulingChunker (`chunkers/ruling.py`)

- Parses ruling text into structural sections: Ruling, Explanation, Examples, Date of Effect, Appendix
- Each section gets different chunking strategy
- Explanation split at numbered paragraphs
- Examples split at "Example N" headings
- Registered as `"ruling"` chunker

##### CaseLawChunker (`chunkers/case_law.py`)

- Parses case text into: headnote, reasoning, orders sections
- Reasoning split by numbered paragraphs `[1]`, `[2]`, etc.
- Every chunk prefixed with case citation and section label
- Fallback to paragraph-boundary splitting if structure not detected
- Registered as `"case_law"` chunker

---

### Stage 3: Idempotency Check (`ingestion_manager.py`)

`IngestionManager` provides document-level idempotency:

```python
decision = await manager.should_ingest(natural_key, document_hash)
# Returns: IngestDecision.SKIP | IngestDecision.REPLACE | IngestDecision.INSERT
```

Logic:
1. Look up `ContentChunk` by `natural_key`
2. If found and `document_hash` matches -> **SKIP** (content unchanged)
3. If found and `document_hash` differs -> **REPLACE** (content updated)
4. If not found -> **INSERT** (new content)

#### Natural Key Format

Built by `build_natural_key(source_type, identifier)`:
- Legislation: `legislation:{act_id}:{section_ref}`
- Ruling: `ruling:{ruling_number}`
- Case law: `case_law:{case_citation}`
- Other: `other:{sha256(url)}`

#### Deterministic Vector IDs

Format: `{source_type}:{natural_key}:{chunk_index}`

This allows predictable deletion when replacing documents -- all old vectors for a natural_key can be identified and deleted.

---

### Stage 4: Embedding (`core/voyage.py`)

`VoyageService` wraps the Voyage AI API:
- Model: `voyage-3.5-lite` (1024 dimensions)
- `embed_document(text)`: uses `input_type="document"` for content storage
- `embed_query(query)`: uses `input_type="query"` for retrieval (different embedding space)
- `embed_batch(texts)`: automatic batching by `batch_size` setting; configurable parallel vs sequential
- Retry: tenacity, 3 attempts, exponential backoff (1-10s), retries on `RateLimitError` and `ConnectionError`
- Cost estimate: `$0.02 per 1M tokens` (voyage-3.5-lite)

---

### Stage 5: Storage

#### Pinecone Upsert (`core/pinecone_service.py`)

`PineconeService.upsert_vectors()`:
- Sync Pinecone client wrapped with `asyncio.to_thread`
- Batch size: 100 vectors per API call
- Parameters: `index_name`, `ids`, `vectors`, `payloads`, `namespace`

**IngestionManager's `insert_document()`**:
1. Builds deterministic vector IDs
2. Constructs Pinecone metadata (text truncated to 30KB)
3. Batch upserts to Pinecone
4. Creates `ContentChunk` DB rows (one per chunk)
5. Creates `BM25IndexEntry` DB rows (tokenized text for keyword search)

**IngestionManager's `replace_document()`**:
1. Deletes old Pinecone vectors by old vector IDs
2. Deletes old `ContentChunk` DB rows by `natural_key`
3. Calls `insert_document()` with new content

#### PostgreSQL Records

Each chunk creates:
- `ContentChunk` row: id, source_id, qdrant_point_id (= Pinecone vector ID), collection_name, content_hash, source_url, title, source_type, natural_key, document_hash, content_type, section_ref, topic_tags, etc.
- `BM25IndexEntry` row: chunk_id, collection_name, tokens (list), section_refs (list)
- `ContentCrossReference` rows (one per cross-reference in chunk)
- `LegislationSection` row (legislation only): act_id, section_ref, heading, part/division/subdivision, compilation info

---

### Stage 6: Job Tracking & Checkpointing

`IngestionJob` model tracks:
- `status`: pending -> running -> completed / failed
- `items_processed`, `items_added`, `items_updated`, `items_skipped`, `items_failed`
- `tokens_used`, `errors` (JSONB, max 20 stored)
- `is_resumable`: enables checkpoint/resume
- `parent_job_id`: links retry jobs to original
- `checkpoint_data`: JSONB with completed_items set

`IngestionJobRepository` methods:
- `start_job(id)`: sets status=running, started_at
- `complete_job(id, stats)`: sets status=completed, completed_at
- `fail_job(id, errors)`: sets status=failed
- `update_job_checkpoint(id, completed_item)`: adds item to checkpoint_data.completed_items
- `get_job_completed_items(id)`: returns set of completed item keys for resume

---

## Celery Task Catalog

All tasks in `tasks/knowledge.py`:

| Task | Name | Time Limit | Purpose |
|------|------|-----------|---------|
| `ingest_source` | `app.tasks.knowledge.ingest_source` | 1 hour | Legacy: ingest from ato_rss, ato_web, ato_api using SemanticChunker |
| `ingest_all_sources` | `app.tasks.knowledge.ingest_all_sources` | 2 hours | Triggers individual `ingest_source` tasks for all active sources |
| `ingest_ato_legal_database` | `app.tasks.knowledge.ingest_ato_legal_database` | 2 hours | Spec 045: ATO rulings with RulingChunker + IngestionManager |
| `ingest_legislation` | `app.tasks.knowledge.ingest_legislation` | 2 hours | Spec 045: legislation.gov.au with LegislationChunker + IngestionManager |
| `ingest_case_law` | `app.tasks.knowledge.ingest_case_law` | 2 hours | Spec 045: case law with CaseLawChunker + IngestionManager |

Common task settings (Spec 045):
- `max_retries=2`, `default_retry_delay=300`
- `autoretry_for=(ConnectionError, TimeoutError)`, `retry_backoff=True`
- `soft_time_limit` set ~200s before `time_limit`
- `dev_mode` parameter: limits items (5-10) and uses smallest sources

All Spec 045 tasks follow the same pattern:
1. Get-or-create `KnowledgeSource` record via `_get_or_create_source()`
2. Create `IngestionJob` record
3. Load completed items from parent job (if resuming)
4. Initialize: PineconeService, VoyageService, ScraperCircuitBreaker, IngestionManager
5. Loop over scraper output: circuit breaker check -> idempotency check -> chunk -> embed -> insert/replace -> checkpoint
6. Complete job with stats

### Async-in-Sync Pattern

Celery tasks are synchronous but the implementation is async. Each task:
1. Creates a new `asyncio` event loop
2. Runs `loop.run_until_complete(_run())`
3. Closes the loop in a `finally` block

DB sessions come from `get_celery_db_context()` (async context manager).

---

## Manual Upload Path

`DocumentProcessor` (`document_processor.py`) extracts text from uploaded files:
- PDF: PyMuPDF (`fitz`)
- DOCX: python-docx
- TXT: direct read

The extracted text is then chunked with `SemanticChunker` and embedded/stored via the standard pipeline.

**Known bug**: The router's manual upload endpoint passes a dict list instead of separate params to the service layer.
