# Quickstart: Voice Feedback Portal

**Feature**: 048-voice-feedback-portal
**Date**: 2026-03-16

## Prerequisites

- Backend running (`cd backend && uv run uvicorn app.main:app --reload`)
- Frontend running (`cd frontend && npm run dev`)
- PostgreSQL running with latest migrations
- MinIO running (for audio file storage)
- Environment variables set:
  - `OPENAI_API_KEY` — for Whisper transcription API
  - `ANTHROPIC_API_KEY` — already configured for Claude
  - MinIO credentials — already configured in existing settings

## New Dependencies

### Backend
```bash
cd backend && uv add openai  # For Whisper transcription API
```

Note: `anthropic` and `boto3`/`aioboto3` (MinIO) are already in the project.

### Frontend
```bash
cd frontend && npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities
```

## Database Migration

```bash
cd backend && uv run alembic revision --autogenerate -m "add feedback tables"
cd backend && uv run alembic upgrade head
```

Creates 3 tables:
- `feedback_submissions` — main submission entity
- `feedback_messages` — AI conversation messages
- `feedback_comments` — internal team notes

## Key Files to Create

### Backend (in order)

1. `backend/app/modules/feedback/enums.py` — SubmissionType, SubmissionStatus, MessageRole, ContentType, Severity
2. `backend/app/modules/feedback/models.py` — FeedbackSubmission, FeedbackMessage, FeedbackComment (use BaseModel + TenantMixin)
3. `backend/app/modules/feedback/exceptions.py` — FeedbackError, SubmissionNotFoundError, ConversationCompleteError
4. `backend/app/modules/feedback/schemas.py` — Create/Update/Response schemas with `from_model()` classmethods
5. `backend/app/modules/feedback/repository.py` — CRUD operations with tenant isolation, flush() not commit()
6. `backend/app/modules/feedback/prompts.py` — PM hat and Engineer hat system prompts, brief generation prompt
7. `backend/app/modules/feedback/transcription.py` — Whisper API wrapper (upload file → get transcript)
8. `backend/app/modules/feedback/service.py` — Business logic: create submission, transcribe, conversation turns, brief generation
9. `backend/app/modules/feedback/router.py` — FastAPI routes per contracts/feedback-api.yaml
10. `backend/app/modules/feedback/__init__.py` — Public exports
11. Register router in `backend/app/main.py` → `register_routes()`

### Frontend (in order)

1. `frontend/src/types/feedback.ts` — TypeScript types matching API schemas
2. `frontend/src/lib/api/feedback.ts` — API client functions (follow apiClient pattern)
3. `frontend/src/components/feedback/AudioRecorder.tsx` — MediaRecorder + waveform visualisation
4. `frontend/src/components/feedback/ConversationChat.tsx` — AI conversation UI (text input + voice button)
5. `frontend/src/components/feedback/BriefPreview.tsx` — Review generated brief before confirming
6. `frontend/src/components/feedback/FeedbackCard.tsx` — Card component for kanban/list view
7. `frontend/src/components/feedback/KanbanBoard.tsx` — Drag-and-drop board with dnd-kit
8. `frontend/src/components/feedback/SubmissionDetail.tsx` — Dialog showing full submission detail
9. `frontend/src/app/(protected)/feedback/new/page.tsx` — New submission flow
10. `frontend/src/app/(protected)/feedback/page.tsx` — Main page (kanban + list toggle)
11. Add nav item in `frontend/src/app/(protected)/layout.tsx`

## Testing

### Backend
```bash
cd backend && uv run pytest tests/unit/modules/feedback/ -v
cd backend && uv run pytest tests/integration/api/test_feedback.py -v
```

### Frontend
```bash
cd frontend && npm run lint
cd frontend && npx tsc --noEmit
```

## Verification

1. Navigate to `/feedback` in the app — should see empty kanban board
2. Click "New Submission" → select "Feature Request"
3. Record a 30-second voice memo describing a feature idea
4. Verify transcription appears within 30 seconds
5. Interact with the AI agent — answer 2-3 follow-up questions
6. Verify structured brief is generated with all required fields
7. Confirm the brief — submission should appear on the kanban as "New"
8. Drag the card to "In Review" — verify status updates
9. Click the card — verify detail dialog shows brief, transcript, and conversation
10. Add a team comment — verify it appears in the detail view
11. Click "Export for Spec" — verify markdown output contains the structured brief
