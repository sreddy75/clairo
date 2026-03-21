# Retrieval Pipeline -- Complete Reference

## Entry Points

There are three main retrieval entry points:

1. **`KnowledgeService.search_knowledge()`** (`service.py`) -- The main search API, used by the `/search` endpoint
2. **`KnowledgeChatbot.chat_enhanced()`** (`chatbot.py`) -- Enhanced chatbot with full pipeline, used by the Tax Guru chatbot
3. **`ClientContextChatbot.chat_with_knowledge()`** (`client_chatbot.py`) -- Client-context chatbot combining RAG with Xero financial data

All three use the same underlying retrieval components but differ in how they compose them.

---

## Stage 1: Query Classification (`retrieval/query_router.py`)

`QueryRouter.classify(query, domain=None) -> QueryClassification`

Pure regex-based classification with no LLM calls. Six query types in priority order:

| Query Type | Detection Pattern | Semantic Weight | Keyword Weight | Pinecone Filter |
|-----------|------------------|-----------------|----------------|-----------------|
| `SECTION_LOOKUP` | `s 8-1`, `section 8-1`, `div 40` | 0.2 | 0.8 | `section_ref = {extracted_ref}` |
| `RULING_LOOKUP` | `TR 2024/1`, `GSTR 2000/1`, `TD 2024/1` | 0.2 | 0.8 | `ruling_number = {extracted_number}` |
| `CASE_LAW` | `case`, `court`, `held that`, `plaintiff`, `defendant` | 0.5 | 0.5 | `source_type = case_law` |
| `PROCEDURAL` | `how to`, `steps`, `process`, `lodge`, `due date` | 0.5 | 0.5 | `source_type in [ato_guide, ato_ruling]` |
| `SCENARIO` | `what if`, `client has`, `suppose`, `example` | 0.6 | 0.4 | `is_superseded != true` |
| `CONCEPTUAL` | Default (fallback) | 0.7 | 0.3 | `is_superseded != true` |

`QueryClassification` dataclass returned:
- `query_type`: The classified type
- `semantic_weight`: Float 0-1
- `keyword_weight`: Float 0-1
- `pinecone_filter`: Dict for Pinecone metadata filtering
- `extracted_refs`: List of extracted section/ruling references
- `domain_detected`: Optional domain slug
- `topic_tags`: List of topic tags (may be overridden by DomainManager)

### Domain Detection

The router also detects tax domains via keyword/regex matching:
- Uses `_DOMAIN_PATTERNS` and `_DOMAIN_ALIAS_PATTERNS` dictionaries
- Maps to domain slugs: `gst`, `income_tax`, `fbt`, `superannuation`, `payg`, `capital_gains`, etc.
- Adds `topic_tags` filter based on `DOMAIN_TOPIC_TAGS` mapping

---

## Stage 2: Domain Scoping (`domains.py`)

`DomainManager` replaces the router's hardcoded topic_tags with DB-backed domain filters:

```python
filters = await domain_manager.get_domain_filters(slug)
# Returns DomainFilters(topic_tags, legislation_refs, ruling_types)
```

- Loads domain config from `tax_domains` DB table
- 5-minute TTL cache to avoid repeated DB queries
- `detect_domain(query)`: sync regex-based detection, reuses patterns from query_router
- `_DOMAIN_PATTERNS` and `_DOMAIN_ALIAS_PATTERNS` are imported from `query_router.py`

In `KnowledgeService.search_knowledge()`:
1. Router classifies query (may set hardcoded topic_tags)
2. Service strips hardcoded topic_tags via `_strip_topic_tags_filter()`
3. Service loads domain filters from DB via DomainManager
4. Merges domain filters into Pinecone filter via `_merge_pinecone_filters()`

---

## Stage 3: Query Expansion (`retrieval/query_expander.py`)

`QueryExpander.expand(query, query_type) -> list[str]`

Two-stage expansion, only for CONCEPTUAL/PROCEDURAL/SCENARIO/CASE_LAW query types:

### Stage 3a: Synonym Expansion

Uses `LEGAL_SYNONYM_TABLE` (hardcoded dict):
- Maps common terms to legal equivalents, e.g., `"tax break"` -> `"tax deduction"`, `"car"` -> `"motor vehicle"`
- Performs case-insensitive substring matching
- Returns modified query with synonyms injected

### Stage 3b: LLM Expansion

- Model: `claude-haiku-4-5-20251001`
- Timeout: 5 seconds
- Max tokens: 256
- Prompt asks for 2-3 alternative phrasings
- Response parsed to extract individual query variants
- Graceful fallback: if LLM fails (timeout, error), returns only synonym-expanded original query

Returns list of query strings (original + variants).

---

## Stage 4: Hybrid Search (`retrieval/hybrid_search.py`)

`HybridSearchEngine.hybrid_search(query, collection, limit=30, semantic_weight=0.6, pinecone_filter=None) -> list[ScoredChunk]`

### Step 4a: Semantic Search (Pinecone)

1. Embed query via `VoyageService.embed_query()` (input_type="query")
2. Search Pinecone with `limit * 2` candidates (to have enough after filtering)
3. Apply `pinecone_filter` if provided
4. Returns scored results with metadata

### Step 4b: Keyword Search (BM25)

1. BM25 index built lazily from `BM25IndexEntry` DB rows, filtered by collection_name
2. Cached per engine instance (not per request)
3. Tokenizes query, scores against index
4. Returns top results

### Step 4c: Reciprocal Rank Fusion (RRF)

Merges semantic and BM25 results using RRF formula:

```
rrf_score(doc) = 1 / (k + rank)   where k = 60

final_score = semantic_weight * rrf_semantic + (1 - semantic_weight) * rrf_bm25
```

- Documents appearing in both lists get combined scores
- Documents appearing in only one list get score from that list only
- Deduplication by chunk_id

### Step 4d: BM25-Only Result Enrichment

Results that appear only in BM25 (not in Pinecone semantic results) need metadata enrichment:
1. Look up `ContentChunk` in DB by chunk_id
2. Fetch vector metadata from Pinecone via `fetch_vectors()`
3. Merge metadata into the ScoredChunk payload
4. Skip results where enrichment fails (empty chunks filtered out)

---

## Stage 5: Multi-Variant Merging

When QueryExpander returns multiple query variants:
1. Each variant runs through hybrid search independently
2. Results are merged via another round of RRF
3. Deduplication by chunk_id (keep highest score)

---

## Stage 6: Cross-Encoder Reranking (`retrieval/reranker.py`)

`CrossEncoderReranker.rerank(query, candidates, top_k=10) -> list[ScoredChunk]`

- Model: `cross-encoder/ms-marco-MiniLM-L-6-v2` (~80MB)
- Lazy-loaded on first use, thread-safe cache at module level
- Scores `(query, candidate_text)` pairs jointly
- Raw logit scores normalized via sigmoid: `1 / (1 + exp(-score))` (clamped to avoid overflow)
- Returns top_k results sorted by cross-encoder score
- **Graceful fallback**: if model fails to load or scoring fails, returns candidates unchanged

Text extraction: prefers `candidate.text`, falls back to `candidate.payload["text"]`.

---

## Stage 7: Result Formatting

### Citation Building

Citations are built from the top reranked results. Each citation includes:
- `number`: Sequential index [1], [2], etc.
- `title`: Document title
- `url`: Source URL
- `source_type`: e.g., "legislation", "ato_ruling", "case_law"
- `effective_date`: When the source was effective
- `text_preview`: Truncated chunk text
- `score`: Reranker score
- `section_ref`: Section reference if available
- `ruling_number`: Ruling number if available

**Citation deduplication** (`service.py`): Citations are deduplicated by URL, keeping the highest-scored instance. RRF scores are rescaled so the best remaining score maps to the original best.

### Superseded Content Warnings

`KnowledgeChatbot.get_superseded_warnings(chunks)`:
- Checks each chunk for `is_superseded` metadata
- Returns list of warning strings with superseded_by reference

### Attribution Text

`KnowledgeChatbot.get_attribution_text(has_legislation)`:
- If results include legislation: includes legislation.gov.au attribution
- Standard attribution about ATO guidelines

---

## Stage 8: Confidence Scoring

`KnowledgeChatbot.compute_confidence(top_score, mean_top5, citation_verified_rate) -> tuple[str, float]`

Formula:
```
confidence_score = 0.4 * top_score + 0.3 * mean_top5 + 0.3 * citation_verified_rate
```

Thresholds:
- `>= 0.7`: "high"
- `>= 0.5`: "medium"
- `>= 0.3`: "low"
- `< 0.3`: "very_low"

**Low confidence behavior** (score < 0.5): The chatbot declines to answer and suggests the user consult the ATO website directly.

---

## Stage 9: Citation Verification (`retrieval/citation_verifier.py`)

`CitationVerifier.verify(response_text, retrieved_chunks) -> VerificationResult`

Post-generation verification that checks the LLM's response against retrieved chunks:

1. **Extract numbered citations**: Regex finds `[1]`, `[2]`, etc. in response text
2. **Extract section references**: Finds `s 8-1`, `section 40-880`, etc.
3. **Extract ruling references**: Finds `TR 2024/1`, `GSTR 2000/1`, etc.

For each extracted reference:
- Checks if it matches a retrieved chunk's `section_ref`, `ruling_number`, or text content
- Marks as verified or unverified

Returns:
- `verified_count`: Number of citations that match retrieved chunks
- `total_count`: Total citations found in response
- `unverified_citations`: List of citations that could not be verified
- `verification_rate`: `verified_count / total_count`

---

## Pipeline Composition by Entry Point

### `KnowledgeService.search_knowledge()` (API search)

```
classify(query) -> domain_scope(filter) -> expand(query) ->
for each variant:
  hybrid_search(variant, filter) ->
merge_variants(RRF) -> rerank(top_k) -> format_results -> deduplicate_citations
```

### `KnowledgeChatbot.chat_enhanced()` (Tax Guru)

```
classify(query) -> domain_scope(filter) -> expand(query) ->
for each variant:
  hybrid_search(variant, filter) ->
merge_variants(RRF) -> rerank(top_k) ->
build_prompt(system + sources + query) -> LLM generate ->
compute_confidence -> citation_verify -> superseded_warnings -> attribution
```

### `KnowledgeChatbot.retrieve_context()` (Original -- NO enhanced pipeline)

```
embed_query(query) -> pinecone.search_multi_namespace(all_namespaces) ->
filter by score_threshold(0.3) -> return top results
```

**WARNING**: This path uses ZERO metadata filters. Pure similarity search only.

### `ClientContextChatbot.chat_with_knowledge()` (Client context)

```
build_client_context(Xero data) ->
retrieve_context_enhanced(query, domain) ->  # Uses full pipeline
build_combined_prompt(CLIENT DATA + SOURCES + QUESTION) ->
LLM generate(KNOWLEDGE_GROUNDED_CLIENT_PROMPT) ->
compute_confidence -> superseded_warnings -> attribution
```

---

## Token Budget (Client Chat)

`TokenBudgetManager` (`token_budget.py`) manages context window allocation:

| Tier | Budget | Content |
|------|--------|---------|
| Tier 1: Profile | 500 tokens | Client name, org details |
| Tier 2: Summaries | 4000 tokens | Financial summaries (intent-specific) |
| Tier 3: Details | 2000 tokens | Raw transaction details (on-demand) |
| RAG Context | 2000 tokens | Knowledge base results |
| **Total** | **12500 tokens** | |

Token estimation: `chars / 4` approximation.

---

## Intent Detection (Client Chat Only)

`QueryIntentDetector` (`intent_detector.py`) classifies financial queries for client-context chat:

| Intent | Keywords | Financial Data Included |
|--------|----------|----------------------|
| `TAX_DEDUCTIONS` | deduction, claim, expense, depreciation | Expense summaries, asset register |
| `CASH_FLOW` | cash flow, liquidity, receivable, payable | AR/AP aging, bank balances |
| `GST_BAS` | GST, BAS, activity statement | GST summaries, BAS history |
| `COMPLIANCE` | compliance, lodgement, deadline, penalty | Compliance summaries, due dates |
| `GENERAL` | Default | All available summaries |

**IMPORTANT**: This detector affects which financial summaries are included in the prompt. It does NOT affect Pinecone queries or the knowledge retrieval pipeline.

---

## Key Configuration Constants

| Constant | Location | Value | Purpose |
|----------|----------|-------|---------|
| `_DEFAULT_COLLECTION` | `service.py` | `"compliance_knowledge"` | Default namespace for search |
| `INDEX_NAME` | `collections.py` | `"clairo-knowledge"` | Pinecone index name |
| `VECTOR_DIMENSION` | `collections.py` | `1024` | Voyage 3.5 lite dimensions |
| `_DEFAULT_MODEL_NAME` | `reranker.py` | `"cross-encoder/ms-marco-MiniLM-L-6-v2"` | Reranker model |
| RRF k parameter | `hybrid_search.py` | `60` | RRF smoothing constant |
| Score threshold | `chatbot.py` | `0.3` | Min score for original path |
| Confidence decline | `chatbot.py` | `0.5` | Score below which chatbot declines |
| Expander timeout | `query_expander.py` | `5s` | LLM expansion timeout |
| Expander model | `query_expander.py` | `claude-haiku-4-5-20251001` | LLM for query expansion |
| Expander max_tokens | `query_expander.py` | `256` | Max response tokens |
