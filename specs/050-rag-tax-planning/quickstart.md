# Quickstart: RAG-Grounded Tax Planning

**Feature**: 050-rag-tax-planning
**Date**: 2026-03-31

## Prerequisites

- Docker services running (`docker-compose up -d`)
- Backend running with these env vars set:
  - `ANTHROPIC_API_KEY` — for Claude API calls
  - `VOYAGE_API_KEY` — for embedding (Voyage 3.5 lite)
  - `PINECONE_API_KEY` — for vector storage
  - `TOKEN_ENCRYPTION_KEY` — for Xero token decryption
- Frontend running (`cd frontend && npm run dev`)
- At least one Xero-connected client with a tax plan

## Step 1: Run Database Migration

```bash
cd backend && uv run alembic upgrade head
```

This adds `source_chunks_used` and `citation_verification` columns to `tax_plan_messages`.

## Step 2: Populate Knowledge Base

### Option A: Via Admin UI
1. Navigate to http://localhost:3000/admin → Knowledge Base
2. Go to Sources tab → Create new source for each:
   - **ATO Tax Planning Topics**: Type=`ato_web`, Collection=`compliance_knowledge`
   - **ATO Rulings (TR/TD)**: Type=`ato_legal_db`, Collection=`compliance_knowledge`
   - **ATO PCGs**: Type=`ato_legal_db`, Collection=`compliance_knowledge`
3. Go to Ingestion tab → Trigger ingestion for each source
4. Monitor progress in Jobs tab

### Option B: Via Celery Tasks
```bash
# Trigger from backend container
docker exec clairo-backend python -c "
from app.tasks.knowledge import ingest_source
ingest_source.delay('ato_legal_db')
"
```

## Step 3: Verify Knowledge Base Content

1. Go to Admin → Knowledge Base → Search Test tab
2. Try queries:
   - "prepaid expenses deduction 12 month rule"
   - "instant asset write-off threshold 2025-26"
   - "Division 7A private company loans"
   - "small business CGT concessions"
3. Verify results return relevant ATO content with source attribution

## Step 4: Test Tax Planning with Citations

1. Navigate to a client → Tax Planning tab
2. Create or open a tax plan with financials loaded
3. Ask: "What are the best strategies to reduce tax?"
4. Verify response includes:
   - Inline citations like "[Source: TR 98/1]" or "[Source: s82KZM ITAA 1936]"
   - A "Sources" section at the bottom
   - A verification badge (green "Sources verified" or amber warning)

## Architecture Overview

```
Frontend (ScenarioChat.tsx)
  ↓ POST /api/v1/tax-plans/{id}/chat/stream
Backend (TaxPlanningService)
  ↓ 1. Classify query (QueryRouter)
  ↓ 2. Retrieve chunks (KnowledgeService → Pinecone)
  ↓ 3. Build prompt with reference material
  ↓ 4. Stream response (TaxPlanningAgent → Claude)
  ↓ 5. Verify citations (CitationVerifier)
  ↓ 6. Save message with RAG metadata
  ↓ SSE events: thinking → content → scenario → verification → done
Frontend renders Markdown + verification badge
```

## Key Files Modified

| File | Change |
|------|--------|
| `backend/app/modules/tax_planning/service.py` | Add RAG retrieval before agent call |
| `backend/app/modules/tax_planning/agent.py` | Accept `reference_material` parameter |
| `backend/app/modules/tax_planning/prompts.py` | Update system prompt with citation instructions |
| `backend/app/modules/tax_planning/models.py` | Add `source_chunks_used`, `citation_verification` to TaxPlanMessage |
| `backend/app/modules/tax_planning/schemas.py` | Add new fields to message response schema |
| `frontend/src/components/tax-planning/ScenarioChat.tsx` | Handle `verification` SSE event, show badge |

## Testing

```bash
# Run tax planning tests
cd backend && uv run pytest tests/ -k "tax_planning" -v

# Run knowledge retrieval tests
cd backend && uv run pytest tests/ -k "knowledge" -v

# Lint
cd backend && uv run ruff check .
cd frontend && npm run lint && npx tsc --noEmit
```
