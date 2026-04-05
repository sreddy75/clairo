# Implementation Plan: AI Discovery Agent

**Branch**: `051-ai-discovery-agent` | **Date**: 2026-04-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/051-ai-discovery-agent/spec.md`

## Summary

Build an AI-powered discovery agent that interviews accountants about their workflows through guided natural language conversations. The agent captures structured requirements, artifacts (sample files, templates), and pain points via dynamic UI components rendered inline in chat. Supports multi-session continuity, cross-accountant aggregation, and an admin insights dashboard. Leverages existing A2UI system for generative UI, portal magic link pattern for passwordless auth, and chat streaming infrastructure for the conversation.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, Anthropic SDK (Claude Sonnet), Voyage 3.5 lite (embeddings), Resend (email), React 18 + shadcn/ui, existing A2UI system
**Storage**: PostgreSQL 16 (9 new tables, pgvector for workflow embeddings), MinIO (artifact file storage)
**Testing**: pytest + pytest-asyncio (backend), ESLint + tsc (frontend)
**Target Platform**: Web — accountant-facing chat at `/discover`, admin dashboard at `/admin/discovery`
**Project Type**: Web (backend + frontend)
**Performance Goals**: Chat response streaming < 2s to first token, auth flow < 3 minutes end-to-end
**Constraints**: Discovery contacts are NOT Clerk users — separate lightweight auth. Workflows are global (not tenant-scoped).
**Scale/Scope**: <50 contacts near-term, <100 workflows, <1000 sessions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Modular monolith structure | PASS | New `discovery` module follows standard module pattern |
| Repository pattern | PASS | All DB access via repository classes |
| Multi-tenancy | PASS WITH NOTE | Discovery contacts are **intentionally** outside tenant boundary. Workflows are global. Admin access filtered by `invited_by_tenant_id`. |
| Tech stack compliance | PASS | Python 3.12, FastAPI, SQLAlchemy 2.0, Anthropic SDK, React 18, shadcn/ui |
| Audit events | PASS | 6 audit event types defined in spec |
| Testing strategy | PASS | Unit + integration tests planned |
| API design standards | PASS | RESTful routes, Pydantic schemas, OpenAPI auto-generated |
| Human-in-the-loop | PASS | Accept/modify/reject on all AI extractions |
| No financial advice | PASS | This feature does not touch financial data or compliance |

**Re-check after Phase 1**: Multi-tenancy note justified — discovery exists to gather cross-practice insights. Tenant isolation would defeat the purpose of aggregation.

## Project Structure

### Documentation (this feature)

```text
specs/051-ai-discovery-agent/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 research output
├── data-model.md        # Phase 1 data model (8 entities)
├── quickstart.md        # Developer quickstart
├── contracts/
│   └── api.md           # API endpoint contracts
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
backend/app/modules/discovery/
├── __init__.py
├── models.py
├── schemas.py
├── repository.py
├── service.py
├── router.py
├── admin_router.py
├── exceptions.py
├── auth/
│   ├── __init__.py
│   ├── service.py
│   ├── dependencies.py
│   └── router.py
├── agent/
│   ├── __init__.py
│   ├── agent.py
│   ├── prompts.py
│   ├── skills.py
│   └── a2ui.py
└── audit_events.py

frontend/src/
├── app/discover/                    # Public: contact-facing chat
│   ├── page.tsx
│   ├── verify/page.tsx
│   └── chat/page.tsx
├── app/(protected)/admin/discovery/ # Admin: insights dashboard
│   ├── page.tsx
│   ├── contacts/[id]/page.tsx
│   ├── workflows/page.tsx
│   └── workflows/[id]/page.tsx
├── components/discovery/
│   ├── DiscoveryChat.tsx
│   └── CoverageMatrix.tsx
├── components/a2ui/discovery/
│   ├── WorkflowBuilder.tsx
│   ├── PainRanker.tsx
│   └── SegmentEstimator.tsx
└── lib/api/discovery.ts
```

**Structure Decision**: Follows the existing modular monolith pattern. New `discovery` module with auth sub-package (adapted from portal pattern) and agent sub-package (adapted from tax planning/agents pattern). Frontend has two entry points: public `/discover` for contacts and protected `/admin/discovery` for admin.

## Key Reuse Opportunities

| Existing Component | Reuse For | Location |
|---|---|---|
| Portal MagicLinkService | Passwordless auth (token gen, hash, JWT, sessions) | `portal/auth/magic_link.py` |
| Portal token storage | Frontend auth token management | `lib/api/portal.ts:208-243` |
| Chat SSE streaming | Conversation streaming endpoint | `tax_planning/router.py:244-290` |
| A2UI system | Dynamic components in chat (file upload, custom types) | `core/a2ui/`, `lib/a2ui/` |
| A2UIRenderer | Frontend rendering of agent-generated UI | `lib/a2ui/renderer.tsx` |
| A2UI fileUpload component | File collection during interviews | `components/a2ui/media/FileUpload.tsx` |
| File processor | Attachment handling and MinIO storage | `core/file_processor.py` |
| Anthropic SDK patterns | Agent implementation | `tax_planning/agent.py` |
| Resend email | Invitation and verification emails | `portal/auth/magic_link.py:563` |
| Voyage embeddings | Workflow semantic similarity | `knowledge/service.py` (embedding calls) |

## Implementation Phases

### Phase 1: Foundation (Models, Auth, Basic Chat)
- SQLAlchemy models + Alembic migration for all 9 tables
- Discovery auth service (adapted from MagicLinkService)
- Contact invitation flow (admin endpoint + email)
- Login/verify pages at `/discover`
- Basic chat endpoint with SSE streaming
- Discovery agent with `conversation_guide` skill
- Message persistence

### Phase 2: Generative UI + Extraction
- Register new A2UI component types (WorkflowBuilder, PainRanker, SegmentEstimator)
- Implement React components for each
- Wire A2UI into discovery chat stream
- `extraction` skill — structured data extraction with accept/modify/reject
- `artifact_analysis` skill — file structure preview
- File upload via A2UI in chat

### Phase 3: Multi-Session Continuity
- Discovery state JSONB management
- `state_updater` skill — update state after confirmed extractions
- Session diff computation
- `session_summariser` skill — generate summaries
- Agent greeting with context from prior sessions

### Phase 4: Admin Dashboard + Aggregation
- Contact list with completeness scores
- Contact detail view (sessions, workflows, artifacts)
- Workflow type view with cross-accountant aggregation
- Coverage matrix
- Workflow semantic matching via Voyage embeddings
- Contradiction detection

## Complexity Tracking

No constitution violations requiring justification. The multi-tenancy exception (discovery contacts outside tenant boundary) is inherent to the feature's purpose and documented in the constitution check.
