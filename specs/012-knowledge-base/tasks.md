# Tasks: Knowledge Base Infrastructure

**Input**: Design documents from `/specs/012-knowledge-base/`
**Prerequisites**: spec.md, plan.md, RESEARCH.md, CONTEXT-STRATEGY.md
**Branch**: `feature/012-knowledge-base`

**Last Updated**: 2025-12-30

---

## Implementation Status Summary

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 0 | Git Setup | ✅ Complete |
| Phase 1 | Setup & Dependencies | ✅ Complete |
| Phase 2 | Foundational Infrastructure | ✅ Complete |
| Phase 3 | Database Models & Schemas | ✅ Complete |
| Phase 4 | Pinecone Collection Infrastructure (US2) | ✅ Complete |
| Phase 5 | Embedding Service (US8) | ✅ Complete |
| Phase 6 | ATO Content Ingestion Pipeline (US3) | ✅ Complete |
| Phase 7 | Compliance Knowledge Retrieval (US1) | ✅ Complete |
| Phase 8 | Celery Background Tasks | ✅ Complete |
| Phase 9 | Metadata Search & Filtering (US7) | ⏳ Partial |
| Phase 10 | Legislation Ingestion (US4) | ❌ Not Started |
| Phase 11 | Business Advisory Content (US5) | ❌ Not Started |
| Phase 12 | Content Update Pipeline (US6) | ⏳ Partial |
| Phase 13 | Audit Events | ❌ Not Started |
| Phase 14 | Polish & Documentation | ⏳ Partial |
| Phase 15 | Knowledge Base Admin UI (US9) | ✅ Complete |
| Phase 16 | AI Assistant Chat UI (US10) | ✅ Complete |
| Phase 17 | Chat Conversation Persistence (US10) | ✅ Complete |
| Phase FINAL | PR & Merge | ❌ Not Started |

**Current Knowledge Base Stats:**
- `compliance_knowledge_dev`: 338 vectors
- `business_fundamentals_dev`: 15 vectors
- `financial_management_dev`: 1 vector
- Total: 354 vectors

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US10)

## User Story Mapping

| ID | Priority | Story | Status |
|----|----------|-------|--------|
| US1 | P1 | Compliance Knowledge Retrieval | ✅ Complete |
| US2 | P1 | Pinecone Collection Infrastructure | ✅ Complete |
| US3 | P1 | ATO Content Ingestion Pipeline | ✅ Complete |
| US4 | P2 | Legislation Content Ingestion | ❌ Not Started |
| US5 | P2 | Business Advisory Content Ingestion | ❌ Not Started |
| US6 | P2 | Content Update Pipeline | ⏳ Partial |
| US7 | P2 | Metadata Search and Filtering | ⏳ Partial |
| US8 | P1 | Embedding Service | ✅ Complete |
| US9 | P1 | Knowledge Base Admin UI | ✅ Complete |
| US10 | P1 | AI Assistant Chat Interface | ✅ Complete |

---

## Phase 0: Git Setup (REQUIRED) ✅ COMPLETE

- [x] T000 Feature branch created and merged work in progress

---

## Phase 1: Setup & Dependencies ✅ COMPLETE

- [x] T001 Add Python dependencies to pyproject.toml
  - Added: `pinecone = "^5.4"` (migrated from Qdrant)
  - Added: `voyageai = "^0.3"`
  - Added: `feedparser = "^6.0"`
  - Added: `beautifulsoup4 = "^4.12"`
  - Added: `lxml = "^5.2"`
  - Added: `anthropic = "^0.40"` (for AI chatbot)
  - Added: `pymupdf = "^1.26"` (for PDF parsing)

- [x] T002 Add VoyageSettings to config
  - File: `backend/app/config.py`
  - VoyageSettings with api_key, model (`voyage-3.5-lite`), batch_size

- [x] T003 Add PineconeSettings to config
  - File: `backend/app/config.py`
  - PineconeSettings with api_key, environment

- [x] T004 Add AnthropicSettings to config
  - File: `backend/app/config.py`
  - AnthropicSettings with api_key, model (`claude-sonnet-4-20250514`), max_tokens, temperature

---

## Phase 2: Foundational Infrastructure (BLOCKING) ✅ COMPLETE

### T010-T019: Pinecone Client (US2) ✅ COMPLETE

- [x] T010 [US2] Create Pinecone client wrapper
  - File: `backend/app/core/pinecone_service.py`
  - `PineconeService` class with async operations
  - Health check, create/delete index, upsert/search vectors

- [x] T011 [US2] Add namespace support
  - Environment-aware namespaces: `{collection}_{env}` (e.g., `compliance_knowledge_dev`)
  - Functions: `get_namespace_with_env()`, `get_base_namespace()`

- [x] T012 [US2] Add multi-namespace search
  - `search_multi_namespace()` - Search across multiple namespaces in parallel

- [x] T013 [P] [US2] Create Pinecone dependency injection
  - File: `backend/app/core/dependencies.py`
  - `get_pinecone_service()` dependency

### T020-T029: Embedding Service (US8) ✅ COMPLETE

- [x] T020 [US8] Create Voyage embedding service
  - File: `backend/app/core/voyage.py`
  - `VoyageService` class
  - Model: `voyage-3.5-lite`, Dimension: 1024

- [x] T021 [US8] Add embed methods
  - `embed_text()` - Single document embedding
  - `embed_query()` - Query embedding (different input_type)
  - `embed_batch()` - Batch embedding with auto-batching

- [x] T022 [P] [US8] Create Voyage dependency injection
  - File: `backend/app/core/dependencies.py`
  - `get_voyage_service()` dependency

### T030-T039: Collection Management (US2) ✅ COMPLETE

- [x] T030 [US2] Create knowledge module
  - File: `backend/app/modules/knowledge/__init__.py`

- [x] T031 [US2] Define namespace schemas
  - File: `backend/app/modules/knowledge/collections.py`
  - 6 namespaces defined: compliance_knowledge, strategic_advisory, industry_knowledge, business_fundamentals, financial_management, people_operations
  - Single Pinecone index: `clairo-knowledge`
  - Vector dimension: 1024 (voyage-3.5-lite)

- [x] T032 [US2] Create collection manager
  - `CollectionManager` class
  - `initialize_all()`, `reset_collection()`, `get_all_stats()`

---

## Phase 3: Database Models & Schemas ✅ COMPLETE

### T040-T049: SQLAlchemy Models ✅ COMPLETE

- [x] T040 Create KnowledgeSource model
  - File: `backend/app/modules/knowledge/models.py`
  - Fields: id, name, source_type, base_url, collection_name, scrape_config (JSONB), is_active, last_scraped_at

- [x] T041 Create ContentChunk model
  - File: `backend/app/modules/knowledge/models.py`
  - Fields: id, source_id, qdrant_point_id, collection_name, content_hash, source_url, title, etc.

- [x] T042 Create IngestionJob model
  - File: `backend/app/modules/knowledge/models.py`
  - Fields: id, source_id, status, items_processed, items_added, items_skipped, items_failed, errors (JSONB)

- [x] T043 Create Alembic migration
  - Migration created and applied

### T050-T059: Pydantic Schemas ✅ COMPLETE

- [x] T050 Create knowledge source schemas
  - File: `backend/app/modules/knowledge/schemas.py`

- [x] T051 Create content chunk schemas

- [x] T052 Create ingestion job schemas

- [x] T053 Create search schemas

- [x] T054 Create chat schemas
  - `ChatRequest`, `ChatResponse`, `CitationResponse`

---

## Phase 4: Pinecone Collection Infrastructure (US2) ✅ COMPLETE

- [x] T060 [US2] Create knowledge repository
  - File: `backend/app/modules/knowledge/repository.py`
  - `KnowledgeSourceRepository`, `ContentChunkRepository`, `IngestionJobRepository`

- [x] T061 [US2] Create collection initialization endpoint
  - `POST /api/v1/admin/knowledge/collections/initialize`

- [x] T062 [US2] Create collection list endpoint
  - `GET /api/v1/admin/knowledge/collections`

- [x] T063 [US2] Create collection delete endpoint
  - `DELETE /api/v1/admin/knowledge/collections/{name}`

---

## Phase 5: Embedding Service (US8) ✅ COMPLETE

- [x] T070 [US8] Embedding integrated in search pipeline
- [x] T071 [US8] Test endpoint available via search

---

## Phase 6: ATO Content Ingestion Pipeline (US3) ✅ COMPLETE

### T080-T089: Content Scrapers ✅ COMPLETE

- [x] T080 [US3] Create base scraper interface
  - File: `backend/app/modules/knowledge/scrapers/base.py`
  - `BaseScraper` abstract class with rate limiting, retry logic
  - Browser-like headers to avoid 403 blocks

- [x] T081 [US3] Implement ATO RSS scraper
  - File: `backend/app/modules/knowledge/scrapers/ato_rss.py`
  - Parses ATO legal database RSS feeds

- [x] T082 [US3] Implement ATO website scraper
  - File: `backend/app/modules/knowledge/scrapers/ato_web.py`
  - Scrapes HTML content from ATO website pages

- [x] T083 [US3] Implement ATO API scraper (PDF)
  - File: `backend/app/modules/knowledge/scrapers/ato_api.py`
  - Fetches PDF guides from ATO public API
  - Parses PDFs using PyMuPDF
  - Content IDs: bas_guide, gst_guide, payg_withholding, fbt_guide, due_dates, starting_business

### T090-T099: Semantic Chunker ✅ COMPLETE

- [x] T090 [US3] Create semantic chunker
  - File: `backend/app/modules/knowledge/chunker.py`
  - `SemanticChunker` class

- [x] T091 [US3] Heading-based chunking implemented
  - Target size: ~800 tokens with 50-token overlap

- [x] T092 [US3] Content hash deduplication
  - Prevents duplicate ingestion of unchanged content

### T100-T109: Ingestion Pipeline ✅ COMPLETE

- [x] T100 [US3] Ingestion implemented in Celery task
  - File: `backend/app/tasks/knowledge.py`

- [x] T101 [US3] Hash-based deduplication working

- [x] T102 [US3] Metadata extraction implemented

- [x] T103 [US3] Source management endpoints
  - `POST /api/v1/admin/knowledge/sources`
  - `GET /api/v1/admin/knowledge/sources`
  - `PUT /api/v1/admin/knowledge/sources/{id}`
  - `DELETE /api/v1/admin/knowledge/sources/{id}`
  - `POST /api/v1/admin/knowledge/sources/{id}/ingest`

- [x] T104 [US3] Job tracking endpoints
  - `GET /api/v1/admin/knowledge/jobs`
  - `GET /api/v1/admin/knowledge/jobs/{id}`
  - `DELETE /api/v1/admin/knowledge/jobs/{id}`

---

## Phase 7: Compliance Knowledge Retrieval (US1) ✅ COMPLETE

- [x] T110 [US1] Multi-namespace search implemented
  - `search_multi_namespace()` in PineconeService

- [x] T111 [US1] Search endpoint created
  - `POST /api/v1/admin/knowledge/search/test`

- [x] T112 [US1] Result formatting implemented

---

## Phase 8: Celery Background Tasks ✅ COMPLETE

- [x] T120 Create knowledge Celery tasks
  - File: `backend/app/tasks/knowledge.py`
  - `ingest_source` task with retry logic
  - `ingest_all_sources` task for batch ingestion

- [x] T121 Ingestion endpoints use Celery
  - Returns job_id immediately, client polls status

---

## Phase 9: Metadata Search & Filtering (US7) ⏳ PARTIAL

- [x] T130 [US7] Basic filtering by namespace/collection
- [ ] T131 [US7] Entity type filtering (sole_trader, company, trust, etc.)
- [ ] T132 [US7] Industry filtering
- [ ] T133 [US7] Date range filtering (effective_after)
- [ ] T134 [US7] Superseded content filtering

---

## Phase 10: Legislation Ingestion (US4) ❌ NOT STARTED

- [ ] T140 [US4] Implement AustLII scraper
- [ ] T141 [US4] Implement legislation chunker
- [ ] T142 [US4] Configure legislation sources (ITAA, GST Act, Super Guarantee Act)

---

## Phase 11: Business Advisory Content (US5) ❌ NOT STARTED

- [ ] T150 [US5] Implement Business.gov.au scraper
- [ ] T151 [US5] Implement Fair Work scraper
- [ ] T152 [US5] Configure advisory sources

---

## Phase 12: Content Update Pipeline (US6) ⏳ PARTIAL

- [x] T160 [US6] Content change detection via hash comparison
- [ ] T161 [US6] Update processing (re-embed changed content)
- [ ] T162 [US6] Superseded content checker task
- [ ] T163 [US6] Scheduled RSS check task (daily)

---

## Phase 13: Audit Events ❌ NOT STARTED

- [ ] T170 Create knowledge audit events
- [ ] T171 Add audit logging to service

---

## Phase 14: Polish & Documentation ⏳ PARTIAL

- [x] T180 Docstrings on public methods
- [ ] T181 Full linting pass
- [ ] T182 Verify success criteria

---

## Phase 15: Knowledge Base Admin UI (US9) ✅ COMPLETE

- [x] T190 [US9] Create TypeScript types
  - File: `frontend/src/types/knowledge.ts`

- [x] T191 [US9] Create API client
  - File: `frontend/src/lib/api/knowledge.ts`

- [x] T200 [US9] Create admin knowledge page
  - File: `frontend/src/app/(protected)/admin/knowledge/page.tsx`
  - Tabbed layout: Collections, Sources, Jobs

- [x] T201 [US9] Collections tab with stats

- [x] T210 [US9] Sources management tab
  - CRUD operations, trigger ingestion

- [x] T220 [US9] Jobs monitoring tab
  - Status badges, polling for running jobs

- [x] T230 [US9] Search test interface (in Sources tab)

---

## Phase 16: AI Assistant Chat Interface (US10) ✅ COMPLETE

**Added after initial spec - provides user-facing chat interface**

- [x] T250 [US10] Create AI Chatbot service
  - File: `backend/app/modules/knowledge/chatbot.py`
  - `KnowledgeChatbot` class with RAG pipeline
  - Streaming response support
  - Numbered citations with source metadata

- [x] T251 [US10] Create chat API endpoints
  - File: `backend/app/modules/knowledge/router.py`
  - `POST /api/v1/admin/knowledge/chat` - Non-streaming
  - `POST /api/v1/admin/knowledge/chat/stream` - SSE streaming

- [x] T252 [US10] Create frontend chat types
  - File: `frontend/src/types/knowledge.ts`
  - `ChatMessage`, `Citation`, `ChatStreamEvent`

- [x] T253 [US10] Create frontend chat API
  - File: `frontend/src/lib/api/knowledge.ts`
  - `chatStream()` - Streaming chat with SSE

- [x] T254 [US10] Create AI Assistant page
  - File: `frontend/src/app/(protected)/assistant/page.tsx`
  - Chat interface with message history
  - Streaming response with typing indicator
  - Clickable citations with source links
  - Markdown rendering for responses
  - Empty state with example questions

---

## Phase 17: Chat Conversation Persistence (US10) ✅ COMPLETE

**Enhanced chat with conversation history storage and context-aware RAG**

### Backend - Database & Models

- [x] T260 [US10] Create ChatConversation model
  - File: `backend/app/modules/knowledge/models.py`
  - Fields: id, user_id, title, created_at, updated_at
  - Relationship to ChatMessage

- [x] T261 [US10] Create ChatMessage model
  - File: `backend/app/modules/knowledge/models.py`
  - Fields: id, conversation_id, role, content, citations (JSONB), created_at

- [x] T262 [US10] Create Alembic migration
  - File: `backend/alembic/versions/011_chat_conversations.py`
  - Tables: chat_conversations, chat_messages
  - Indexes for user lookup and message ordering

### Backend - Repository & API

- [x] T263 [US10] Create ChatConversationRepository
  - File: `backend/app/modules/knowledge/repository.py`
  - Methods: create, get_by_id, get_by_user, update_title, delete, touch

- [x] T264 [US10] Create ChatMessageRepository
  - File: `backend/app/modules/knowledge/repository.py`
  - Methods: create, get_by_conversation, get_recent, count_by_conversation

- [x] T265 [US10] Create conversation management endpoints
  - `GET /api/v1/admin/knowledge/conversations` - List user conversations
  - `POST /api/v1/admin/knowledge/conversations` - Create conversation
  - `GET /api/v1/admin/knowledge/conversations/{id}` - Get with messages
  - `PATCH /api/v1/admin/knowledge/conversations/{id}` - Update title
  - `DELETE /api/v1/admin/knowledge/conversations/{id}` - Delete conversation

- [x] T266 [US10] Create persistent chat stream endpoint
  - `POST /api/v1/admin/knowledge/chat/persistent/stream`
  - Creates/continues conversations
  - Saves user and assistant messages to database
  - Returns conversation_id in done event

### Backend - RAG Improvements

- [x] T267 [US10] Implement context-aware RAG retrieval
  - File: `backend/app/modules/knowledge/chatbot.py`
  - `_build_retrieval_query()` expands query with conversation context
  - Follow-up questions retrieve relevant documents

- [x] T268 [US10] Streamline system prompt
  - Direct, professional tone for accountant audience
  - No fluff or apologies when no RAG results
  - LLM answers from training when no vectors match

### Frontend - Conversation UI

- [x] T269 [US10] Add conversation types
  - File: `frontend/src/types/knowledge.ts`
  - `Conversation`, `ConversationListItem`, `ConversationMessage`
  - `ChatRequestWithConversation`

- [x] T270 [US10] Add conversation API functions
  - File: `frontend/src/lib/api/knowledge.ts`
  - `chatStreamPersistent()` - Persistent streaming chat
  - `getConversations()`, `getConversation()`, `createConversation()`
  - `updateConversation()`, `deleteConversation()`

- [x] T271 [US10] Add conversation sidebar
  - File: `frontend/src/app/(protected)/assistant/page.tsx`
  - Collapsible sidebar with conversation list
  - Load past conversations
  - Delete conversations with confirmation
  - New conversation button

- [x] T272 [US10] Implement conversation persistence
  - Auto-create conversation on first message
  - Track conversation_id across messages
  - Refresh conversation list after new conversation

---

## Phase FINAL: PR & Merge ❌ NOT STARTED

- [ ] TFINAL-1 Ensure all tests pass
- [ ] TFINAL-2 Run full linting
- [ ] TFINAL-3 Create PR
- [ ] TFINAL-4 Address review feedback
- [ ] TFINAL-5 Merge to main
- [ ] TFINAL-6 Update ROADMAP.md

---

## Seed Script & Deployment

A seed script has been created for fresh deployments:

**File**: `backend/scripts/seed_knowledge_sources.py`

**Default Sources (10 total):**
1. ATO BAS Complete Guide (ato_api)
2. ATO GST Complete Guide (ato_api)
3. ATO PAYG Withholding Guide (ato_api)
4. ATO FBT Guide (ato_api)
5. ATO Due Dates Reference (ato_api)
6. ATO Starting a Business Guide (ato_api)
7. ATO BAS Due Dates (ato_web)
8. ATO GST Registration (ato_web)
9. ATO Small Business Deductions (ato_web)
10. ATO Super for Employers (ato_web)

**Usage:**
```bash
# Create sources only
docker exec clairo-backend python scripts/seed_knowledge_sources.py

# Create sources and trigger ingestion
docker exec clairo-backend python scripts/seed_knowledge_sources.py --ingest
```

---

## Environment Isolation

Pinecone namespaces are environment-aware to prevent dev/staging/prod data mixing:

| Environment | Namespace Format |
|-------------|------------------|
| development | `{collection}_dev` |
| staging | `{collection}_staging` |
| production | `{collection}_prod` |

Set via `ENVIRONMENT` env variable (defaults to "development").

---

## Key Files Reference

### Backend

| File | Description |
|------|-------------|
| `app/core/pinecone_service.py` | Pinecone client wrapper |
| `app/core/voyage.py` | Voyage embedding service |
| `app/modules/knowledge/collections.py` | Namespace configuration |
| `app/modules/knowledge/models.py` | SQLAlchemy models |
| `app/modules/knowledge/repository.py` | Database repositories |
| `app/modules/knowledge/router.py` | API endpoints |
| `app/modules/knowledge/chatbot.py` | AI chatbot with RAG |
| `app/modules/knowledge/chunker.py` | Semantic text chunking |
| `app/modules/knowledge/scrapers/` | Content scrapers |
| `app/tasks/knowledge.py` | Celery background tasks |
| `scripts/seed_knowledge_sources.py` | Deployment seed script |

### Frontend

| File | Description |
|------|-------------|
| `src/types/knowledge.ts` | TypeScript types |
| `src/lib/api/knowledge.ts` | API client functions |
| `src/app/(protected)/admin/knowledge/page.tsx` | Admin UI |
| `src/app/(protected)/assistant/page.tsx` | AI Assistant chat |

---

## Notes

- Migrated from Qdrant to Pinecone Serverless for cost efficiency
- Single Pinecone index (`clairo-knowledge`) with multiple namespaces
- Voyage-3.5-lite embeddings produce 1024-dimension vectors
- Content deduplication via content hash prevents re-embedding unchanged content
- ATO API returns PDFs (not JSON) - PyMuPDF used for parsing
- Some ATO web pages return 403 - handled gracefully with logging
