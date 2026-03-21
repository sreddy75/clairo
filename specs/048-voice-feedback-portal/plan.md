# Implementation Plan: Voice Feedback Portal

**Branch**: `048-voice-feedback-portal` | **Date**: 2026-03-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/048-voice-feedback-portal/spec.md`

## Summary

Build a voice-powered feedback portal where SME advisors (and eventually all platform users) can submit product feedback via voice memos or in-browser recording. An AI agent (Claude) conducts a structured clarification conversation in one of two modes (Feature Request / Bug & Enhancement), producing a detailed brief stored in the database. A lightweight kanban board with drag-and-drop provides team visibility and prioritisation. The feature adds a new `feedback` backend module following the modular monolith pattern and a new `/feedback` frontend route in the protected layout.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, anthropic SDK, OpenAI Whisper API (transcription), React 18 + shadcn/ui
**Storage**: PostgreSQL 16 (3 new tables: `feedback_submissions`, `feedback_messages`, `feedback_comments`), MinIO (audio file storage)
**Testing**: pytest + pytest-asyncio (backend), manual + Playwright (frontend)
**Target Platform**: Web (desktop primary, mobile secondary)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Transcription < 30s for recordings under 3 min, AI conversation responses < 5s
**Constraints**: Audio files max 25MB, recordings max 5 minutes, tenant-isolated data
**Scale/Scope**: Initially 2-3 SME advisors, designed to scale to all platform users (~500+ practices)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Modular monolith structure | PASS | New `feedback` module follows standard module pattern |
| Repository pattern | PASS | Dedicated `FeedbackRepository` with `flush()` not `commit()` |
| Multi-tenancy (`tenant_id` on all tables) | PASS | All 3 tables include `tenant_id` with FK |
| Domain exceptions (not HTTPException in services) | PASS | `FeedbackError` hierarchy extends `DomainError` |
| Audit events for data modifications | PASS | `feedback.created`, `feedback.status_change`, `feedback.comment_added`, `feedback.exported` |
| Testing strategy (unit + integration) | PASS | Service unit tests, API integration tests, audit event verification |
| API design (RESTful, versioned) | PASS | `/api/v1/feedback/*` with standard CRUD + action endpoints |
| Frontend: shadcn/ui components only | PASS | Uses Card, Table, Dialog, Button, Badge, Tabs — no raw HTML |
| Frontend: shared formatters and cn() | PASS | Uses `formatRelativeTime`, `formatDate`, `cn()` from shared libs |
| Frontend: status colour semantics | PASS | Green=done, amber=in review/planned, coral=new, neutral=draft |
| No cross-module direct DB queries | PASS | Feedback module is self-contained, no cross-module dependencies |
| Human-in-the-loop for AI outputs | PASS | User reviews and confirms AI-generated brief before saving |

## Project Structure

### Documentation (this feature)

```text
specs/048-voice-feedback-portal/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── feedback-api.yaml
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   └── modules/
│       └── feedback/
│           ├── __init__.py
│           ├── models.py          # FeedbackSubmission, FeedbackMessage, FeedbackComment
│           ├── enums.py           # SubmissionType, SubmissionStatus, MessageRole
│           ├── schemas.py         # Create/Update/Response schemas
│           ├── repository.py      # DB access (flush, not commit)
│           ├── service.py         # Business logic + Claude conversation
│           ├── router.py          # API endpoints
│           ├── exceptions.py      # FeedbackError hierarchy
│           ├── prompts.py         # PM hat and Engineer hat system prompts
│           └── transcription.py   # Whisper API integration
└── tests/
    ├── unit/modules/feedback/
    │   ├── test_service.py
    │   └── test_prompts.py
    └── integration/api/
        └── test_feedback.py

frontend/
└── src/
    ├── app/(protected)/feedback/
    │   ├── page.tsx               # Main feedback page (kanban + list view)
    │   └── new/
    │       └── page.tsx           # New submission flow (record/upload → conversation → brief)
    ├── components/feedback/
    │   ├── KanbanBoard.tsx        # Drag-and-drop kanban
    │   ├── FeedbackCard.tsx       # Individual submission card
    │   ├── SubmissionDetail.tsx   # Detail dialog (brief + transcript + conversation)
    │   ├── AudioRecorder.tsx      # In-browser recording with waveform
    │   ├── ConversationChat.tsx   # AI clarification conversation UI
    │   └── BriefPreview.tsx       # Review brief before confirming
    ├── lib/api/
    │   └── feedback.ts            # API client functions
    └── types/
        └── feedback.ts            # TypeScript types
```

**Structure Decision**: Standard web application structure following existing Clairo patterns. New `feedback` module in backend, new `/feedback` route in frontend protected layout. No new infrastructure services required — uses existing MinIO for file storage, existing Anthropic SDK for Claude, and adds OpenAI Whisper API for transcription.

## Complexity Tracking

No constitution violations. No complexity justifications needed.
