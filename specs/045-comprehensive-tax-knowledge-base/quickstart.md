# Quickstart: Comprehensive Australian Tax Knowledge Base

**Feature**: 045-comprehensive-tax-knowledge-base
**Prerequisites**: Spec 012 (Knowledge Base) complete, Pinecone + Voyage configured

---

## 1. Install New Dependencies

```bash
cd backend
uv add rank-bm25 sentence-transformers
```

- `rank-bm25`: BM25 keyword scoring for hybrid search
- `sentence-transformers`: Cross-encoder re-ranking model

## 2. Run Database Migration

```bash
cd backend
uv run alembic upgrade head
```

This creates:
- `legislation_sections` — tracks ingested legislation
- `content_cross_references` — section-to-section links
- `tax_domains` — specialist domain configuration (seeded with 9 domains)
- `bm25_index_entries` — keyword index for hybrid search
- Extended columns on `content_chunks` (content_type, section_ref, topic_tags, etc.)

## 3. Verify Existing Infrastructure

```bash
# Ensure Pinecone is configured
echo $PINECONE_API_KEY  # Should be set
echo $VOYAGE_API_KEY    # Should be set
echo $ANTHROPIC_API_KEY # Should be set

# Verify existing knowledge namespaces
python -c "
from app.modules.knowledge.collections import get_all_collections
print(get_all_collections())
"
```

## 4. Trigger Initial Ingestion

### Phase 1: ATO Legal Database (Critical)

```bash
# Ingest all ATO ruling types via admin API
curl -X POST http://localhost:8000/api/v1/admin/knowledge/ingest/legislation \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'

# Or via Celery task directly
python -c "
from app.tasks.knowledge import ingest_ato_legal_database
ingest_ato_legal_database.delay()
"
```

### Phase 2: Legislation

```bash
# Ingest key tax acts
curl -X POST http://localhost:8000/api/v1/admin/knowledge/ingest/legislation \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"acts": ["C2004A05138", "C1936A00027", "C2004A00446"]}'
```

### Phase 3: Case Law

```bash
# Ingest from Open Australian Legal Corpus + Federal Court RSS
curl -X POST http://localhost:8000/api/v1/admin/knowledge/ingest/case-law \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source": "both", "filter_tax_only": true}'
```

## 5. Verify Ingestion

```bash
# Check freshness report
curl http://localhost:8000/api/v1/admin/knowledge/freshness \
  -H "Authorization: Bearer $TOKEN" | jq .

# Expected: sources with chunk counts > 0, freshness_status = "fresh"
```

## 6. Test Search

```bash
# Hybrid search test
curl -X POST http://localhost:8000/api/v1/knowledge/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the Division 7A rules?", "limit": 5}' | jq .

# Legislation section lookup
curl http://localhost:8000/api/v1/knowledge/legislation/s109D-ITAA1936 \
  -H "Authorization: Bearer $TOKEN" | jq .

# Domain-scoped chat
curl -X POST http://localhost:8000/api/v1/knowledge/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "When does a business need to register for GST?", "domain": "gst"}' | jq .
```

## 7. Run Tests

```bash
cd backend

# Unit tests for new components
uv run pytest tests/unit/modules/knowledge/test_legislation_chunker.py -v
uv run pytest tests/unit/modules/knowledge/test_ruling_chunker.py -v
uv run pytest tests/unit/modules/knowledge/test_hybrid_search.py -v
uv run pytest tests/unit/modules/knowledge/test_query_router.py -v
uv run pytest tests/unit/modules/knowledge/test_citation_verifier.py -v

# Integration tests
uv run pytest tests/integration/api/knowledge/ -v

# All knowledge tests
uv run pytest tests/ -k "knowledge" -v
```

## 8. Frontend Development

```bash
cd frontend
npm run dev
```

New components to work with:
- `components/knowledge/domain-selector.tsx` — specialist domain chips
- `components/knowledge/confidence-badge.tsx` — response confidence indicator
- `components/knowledge/enhanced-citation-panel.tsx` — clickable citations
- `components/knowledge/supersession-banner.tsx` — superseded content warning

## Key Files

| File | Purpose |
|------|---------|
| `knowledge/scrapers/ato_legal_db.py` | ATO Legal Database full crawler |
| `knowledge/scrapers/legislation_gov.py` | legislation.gov.au EPUB parser |
| `knowledge/scrapers/case_law.py` | Open Legal Corpus + Federal Court |
| `knowledge/chunkers/legislation.py` | Structure-aware legislation chunker |
| `knowledge/chunkers/ruling.py` | ATO ruling chunker |
| `knowledge/chunkers/case_law.py` | Case law chunker |
| `knowledge/retrieval/hybrid_search.py` | BM25 + semantic fusion |
| `knowledge/retrieval/reranker.py` | Cross-encoder re-ranking |
| `knowledge/retrieval/query_router.py` | Legal query classification |
| `knowledge/retrieval/query_expander.py` | LLM-assisted expansion |
| `knowledge/retrieval/citation_verifier.py` | Post-generation check |
| `knowledge/domains.py` | Specialist domain config |
| `knowledge/models.py` | SQLAlchemy models (extended) |

## Environment Variables

No new environment variables required. Uses existing:
- `PINECONE_API_KEY` / `PINECONE_INDEX_HOST`
- `VOYAGE_API_KEY`
- `ANTHROPIC_API_KEY`
- `REDIS_URL` (Celery)
- `POSTGRES_*` (database)

## Attribution

All responses using legislation content must include:
> "Based on content from the Federal Register of Legislation at [date]. For the latest information on Australian Government legislation please go to https://www.legislation.gov.au"

ATO content requires no specific attribution but must not imply ATO endorsement.
