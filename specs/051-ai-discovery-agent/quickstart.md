# Quickstart: AI Discovery Agent

**Branch**: `051-ai-discovery-agent` | **Date**: 2026-04-04

## Prerequisites

- Docker Compose running (PostgreSQL, Redis, MinIO)
- Backend: `cd backend && uv sync`
- Frontend: `cd frontend && npm install`
- Environment variables: Anthropic API key, Resend API key, Voyage API key

## New Module Location

```
backend/app/modules/discovery/
├── __init__.py
├── models.py           # 8 models (Contact, AuthSession, ChatSession, Message, State, Workflow, Contribution, Extraction, Artifact)
├── schemas.py          # Pydantic request/response schemas
├── repository.py       # Repository classes per model
├── service.py          # DiscoveryService (orchestrates all operations)
├── router.py           # Contact-facing routes (/api/v1/discovery/*)
├── admin_router.py     # Admin routes (/api/v1/admin/discovery/*)
├── exceptions.py       # Module exceptions
├── auth/
│   ├── __init__.py
│   ├── service.py      # DiscoveryAuthService (adapted from MagicLinkService)
│   ├── dependencies.py # CurrentDiscoveryContact dependency
│   └── router.py       # Auth routes (verify, refresh, request-code)
├── agent/
│   ├── __init__.py
│   ├── agent.py        # Discovery agent (Anthropic SDK)
│   ├── prompts.py      # System prompts for each skill
│   ├── skills.py       # Skill definitions (extraction, analysis, state update)
│   └── a2ui.py         # Discovery-specific A2UI component generation
└── audit_events.py     # Audit event type constants

frontend/src/
├── app/
│   └── discover/
│       ├── page.tsx         # Login/landing page
│       ├── verify/page.tsx  # Token verification
│       └── chat/page.tsx    # Chat interface with A2UI rendering
├── app/(protected)/admin/discovery/
│   ├── page.tsx             # Contacts list dashboard
│   ├── contacts/[id]/page.tsx  # Contact detail
│   ├── workflows/page.tsx   # Workflow aggregation dashboard
│   └── workflows/[id]/page.tsx # Workflow detail
├── components/discovery/
│   ├── DiscoveryChat.tsx    # Chat component (based on ScenarioChat pattern)
│   └── CoverageMatrix.tsx   # Topic x Contact coverage grid
├── components/a2ui/discovery/
│   ├── WorkflowBuilder.tsx  # New A2UI component: process steps
│   ├── PainRanker.tsx       # New A2UI component: drag-rank
│   └── SegmentEstimator.tsx # New A2UI component: volume inputs
└── lib/api/discovery.ts     # API client + SSE consumer
```

## Database Migration

```bash
cd backend && uv run alembic revision --autogenerate -m "Add discovery module tables"
cd backend && uv run alembic upgrade head
```

Creates 9 tables: `discovery_contacts`, `discovery_auth_sessions`, `discovery_chat_sessions`, `discovery_messages`, `discovery_state`, `discovery_workflows`, `discovery_contributions`, `discovery_extractions`, `discovery_artifacts`.

Requires pgvector extension for `discovery_workflows.embedding` column.

## Key Development Steps

1. **Models + Migration** — Create all SQLAlchemy models, run migration
2. **Auth flow** — Adapt portal magic link for discovery contacts, build login/verify pages
3. **Chat infrastructure** — SSE streaming endpoint, message persistence, discovery agent with conversation_guide skill
4. **A2UI integration** — Register new component types, wire into chat stream, implement action feedback loop
5. **Discovery state** — JSONB state management, extraction skill, session diffs
6. **Admin dashboard** — Contact list, workflow aggregation, coverage matrix
7. **Cross-interview** — Workflow embedding, semantic matching, contradiction detection

## Running

```bash
# Backend
cd backend && uv run uvicorn app.main:app --reload

# Frontend
cd frontend && npm run dev

# Test the flow
# 1. Login as admin, invite a contact
# 2. Open /discover in incognito, enter the contact's email
# 3. Verify with the token from the invitation email
# 4. Start chatting — the discovery agent guides the conversation
```

## Testing

```bash
# Unit tests
cd backend && uv run pytest tests/unit/modules/discovery/ -v

# Integration tests
cd backend && uv run pytest tests/integration/api/test_discovery.py -v

# Frontend
cd frontend && npm run lint && npx tsc --noEmit
```
