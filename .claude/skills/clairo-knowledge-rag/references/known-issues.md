# Known Issues & Gotchas -- Complete Reference

## Critical Issues

### 1. `qdrant_point_id` Legacy Naming

**Location**: `models.py` -- `ContentChunk.qdrant_point_id`
**Impact**: Confusing naming throughout the codebase
**Details**: The field was named when the project used Qdrant. After migrating to Pinecone, the field still stores the Pinecone vector ID but retains the old name. It is referenced in `repository.py`, `tasks/knowledge.py`, `ingestion_manager.py`, and `chatbot.py`.
**Mitigation**: Do NOT rename without an Alembic migration. The field is used as a foreign key to locate Pinecone vectors.

### 2. `delete_by_source()` Orphans Pinecone Vectors

**Location**: `repository.py` -- `ContentChunkRepository.delete_by_source()`
**Impact**: Pinecone vectors remain after DB rows are deleted
**Details**: The repository method deletes `ContentChunk` rows from PostgreSQL but does NOT delete the corresponding vectors from Pinecone. This creates orphan vectors that consume Pinecone storage and may return stale results in searches.
**Workaround**: When deleting sources, manually call `PineconeService.delete_vectors()` with the `qdrant_point_id` values before deleting DB rows. The `IngestionManager.replace_document()` method handles this correctly for individual documents.

### 3. Original Chatbot Path Uses ZERO Metadata Filters

**Location**: `chatbot.py` -- `KnowledgeChatbot.retrieve_context()`
**Impact**: Poor retrieval precision for the original chatbot
**Details**: The original `retrieve_context()` method calls `PineconeService.search_multi_namespace()` with no metadata filters. It searches ALL namespaces with pure cosine similarity and a 0.3 score threshold. This means irrelevant content from non-compliance namespaces can appear in results.
**Status**: The enhanced path (`retrieve_context_enhanced()`) uses the full pipeline with filters. However, some code paths (e.g., `ClientContextChatbot.chat_with_client_context()`) still use the original path.

### 4. Legacy Ingestion Task: Single-Vector Pinecone Upserts

**Location**: `tasks/knowledge.py` -- `_ingest_source_async()`
**Impact**: Slow ingestion for ato_rss, ato_web, ato_api sources
**Details**: The legacy `ingest_source` task upserts one vector at a time in a loop. Pinecone recommends batch upserts of 100 vectors. The Spec 045 tasks use `IngestionManager` which delegates to `PineconeService.upsert_vectors()` with proper batching.
**Fix**: Refactor `_ingest_source_async()` to use `IngestionManager` instead of direct Pinecone calls.

### 5. Legacy Dedup Checks Only First Chunk's Content Hash

**Location**: `tasks/knowledge.py` -- `_ingest_source_async()`, line ~213
**Impact**: Multi-chunk documents may not be properly deduplicated
**Details**: The legacy task checks `chunk_repo.get_by_hash(chunks[0].content_hash)` to detect duplicates. If only the first chunk matches but other chunks have changed, the entire document is skipped. The Spec 045 `IngestionManager` uses `document_hash` (hash of full document) and `natural_key` for proper document-level dedup.

### 6. Router Manual Upload Calling Convention Bug

**Location**: `router.py` -- manual upload endpoint
**Impact**: May cause runtime errors on manual upload
**Details**: The manual upload route passes a list of dicts to the service layer instead of separate parameters as the service method expects.

---

## Design Limitations

### 7. No Retroactive Metadata Updates

**Impact**: Existing Pinecone vectors do not get new metadata fields
**Details**: When new metadata fields are added (e.g., Spec 045 added `content_type`, `section_ref`, `topic_tags`), existing vectors in Pinecone are NOT updated. Only newly ingested or replaced documents get the new fields. This means metadata filters may miss old content.
**Workaround**: Re-ingest all content to populate new metadata fields on existing vectors.

### 8. BM25 Index Coverage Gap

**Impact**: Chunks without `BM25IndexEntry` rows are invisible to keyword search
**Details**: The BM25 index is built per-chunk as a DB table. If a chunk was ingested before the BM25 index was added (or if the BM25 entry creation fails), that chunk will not appear in keyword search results. It will still appear in semantic (Pinecone) search.
**Workaround**: Run a backfill script to create `BM25IndexEntry` rows for existing chunks.

### 9. Text Truncation at 30KB

**Location**: `ingestion_manager.py`
**Impact**: Very long documents lose tail content in Pinecone `text` metadata
**Details**: Pinecone has a metadata size limit. The `IngestionManager` truncates the `text` field to 30KB (30,000 characters). The full text is still available in the chunk's original source, but the Pinecone metadata (used for reranking and display) will be incomplete.
**Note**: This mainly affects case law (long judgments) and some lengthy rulings.

### 10. BM25 Index Lazy Loading

**Location**: `retrieval/hybrid_search.py`
**Impact**: First search after startup may be slow; index cached per engine instance
**Details**: The BM25 index is built from DB rows on first use and cached on the `HybridSearchEngine` instance. If the instance is recreated (e.g., per-request in some configurations), the index is rebuilt each time. Also, newly ingested content won't appear in the BM25 index until the engine instance is recreated.

### 11. Cross-Encoder Model Cold Start

**Location**: `retrieval/reranker.py`
**Impact**: First reranking request takes several seconds
**Details**: The cross-encoder model (~80MB) is lazy-loaded on first use. The first request that triggers reranking will experience a delay of several seconds while the model downloads/loads. Subsequent requests use the cached model.
**Note**: The model is cached at module level (`_MODEL_CACHE`) with thread-safe double-checked locking.

---

## Architectural Gotchas

### 12. Two Chatbot Code Paths

**Location**: `chatbot.py` -- `retrieve_context()` vs `retrieve_context_enhanced()`
**Impact**: Easy to forget to update both paths
**Details**: The original path (`retrieve_context`) and the enhanced Spec 045 path (`retrieve_context_enhanced`) coexist. Similarly, `chat()` and `chat_enhanced()` are separate methods. When modifying retrieval behavior, you must decide which path(s) to update.
**Usage mapping**:
- `chat_enhanced()` / `retrieve_context_enhanced()`: Used by Tax Guru and `KnowledgeService.search_knowledge()`
- `retrieve_context()`: Used by `ClientContextChatbot.chat_with_client_context()` (NOT `chat_with_knowledge()` which uses enhanced)
- `chat()`: Legacy, may still be referenced by some routes

### 13. Namespace vs Collection Naming Confusion

**Impact**: Easy to confuse "collection" (logical name) with "namespace" (Pinecone namespace)
**Details**:
- `collection_name` in code refers to the logical collection (e.g., `"compliance_knowledge"`)
- Pinecone namespaces may have env suffixes (e.g., `"compliance_knowledge_dev"`)
- `get_namespace_with_env()` converts collection name to Pinecone namespace
- Most namespaces are NOT env-suffixed (shared across environments) -- only `insight_dedup` is
- The `_collection` metadata field on Pinecone vectors stores the base collection name (without env suffix)

### 14. Query Router Runs Synchronously

**Location**: `retrieval/query_router.py`
**Impact**: No issue currently, but limits future async patterns
**Details**: `QueryRouter.classify()` is a sync method using only regex. If future classification needs async operations (e.g., LLM-based classification), the method signature would need to change.

### 15. Domain Manager Regex Reuse

**Location**: `domains.py` imports `_DOMAIN_PATTERNS` and `_DOMAIN_ALIAS_PATTERNS` from `query_router.py`
**Impact**: Tight coupling between DomainManager and QueryRouter
**Details**: If the domain detection patterns change, both files are affected. The DomainManager's `detect_domain()` is a sync method that mirrors the router's domain detection logic.

### 16. Celery Async-in-Sync Pattern

**Location**: `tasks/knowledge.py`
**Impact**: Each Celery task creates and destroys an event loop
**Details**: Celery workers are synchronous, but all DB and API operations are async. Each task creates `asyncio.new_event_loop()`, runs the async implementation, and closes the loop. This works but means there is no shared event loop across tasks. DB sessions come from `get_celery_db_context()`.

### 17. Aggregation Layer is Client-Chat Only

**Location**: `aggregation_models.py`, `aggregation_repository.py`, `aggregation_service.py`, `context_builder.py`
**Impact**: These files are NOT part of the knowledge retrieval pipeline
**Details**: The aggregation layer provides client financial summaries (GST, expenses, AR/AP aging, compliance) from Xero data. It is used exclusively by `ClientContextChatbot` and `ContextBuilderService` for injecting client data into prompts. Do not confuse with RAG knowledge retrieval.

### 18. Intent Detector Scope

**Location**: `intent_detector.py`
**Impact**: Only affects client-context chat financial data selection
**Details**: `QueryIntentDetector` classifies the user's query into financial intent categories (TAX_DEDUCTIONS, CASH_FLOW, GST_BAS, COMPLIANCE, GENERAL). This determines which Xero financial summaries to include in the prompt. It does NOT affect:
- Pinecone search queries
- Metadata filters
- Knowledge retrieval pipeline
- Tax Guru chatbot

---

## Performance Considerations

### 19. Embedding Cost

- Voyage 3.5 lite: ~$0.02 per 1M tokens
- Each search query: 1 embedding call per query variant
- Each ingestion: 1 batch embedding call per document (all chunks)
- Query expansion can multiply query count by 2-4x

### 20. Pinecone Search Latency

- Single namespace search: ~50-100ms
- Multi-namespace search: parallelized, ~100-200ms total
- Search with metadata filters: may be slightly slower than unfiltered

### 21. Reranker Latency

- Cross-encoder scoring 30 candidates: <100ms after model is loaded
- First request (cold start): several seconds for model download/load

### 22. Circuit Breaker Recovery

- Once open (5 failures), the circuit breaker blocks ALL requests to that host for 3600 seconds (1 hour)
- During half-open state, only 2 test requests are allowed
- If either test request fails, the circuit reopens for another hour
- This is per-host, not per-endpoint
