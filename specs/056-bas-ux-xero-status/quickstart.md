# Quickstart: 056-bas-ux-xero-status

## Prerequisites

- Backend running (`cd backend && uv run uvicorn app.main:app --reload`)
- Frontend running (`cd frontend && npm run dev`)
- PostgreSQL with existing BAS data (at least one session with tax code suggestions)
- Xero connection active for at least one client (needed for cross-check and note sync testing)

## Development Order

### 1. Database migration (backend)

```bash
cd backend
# Create migration for new columns on tax_code_suggestions
uv run alembic revision --autogenerate -m "056_add_suggestion_notes_columns"
uv run alembic upgrade head
```

New columns (3 total): `note_text`, `note_updated_by`, `note_updated_at`. No `note_xero_sync_status` column — Xero note sync is fire-and-forget.

### 2. Backend: Remove Reject (P1)

Files to modify:
- `backend/app/modules/bas/tax_code_service.py` — `reject_suggestion()` internally calls `dismiss_suggestion()`
- `backend/app/modules/bas/router.py` — mark reject endpoint as deprecated, add unpark endpoint
- `backend/app/modules/bas/schemas.py` — update `TaxCodeSuggestionResponse` to include note fields, add unpark schema

### 3. Backend: Note CRUD (P1)

Files to modify:
- `backend/app/modules/bas/models.py` — add note columns to `TaxCodeSuggestion`
- `backend/app/modules/bas/schemas.py` — add `SuggestionNoteRequest`, `SuggestionNoteResponse`
- `backend/app/modules/bas/repository.py` — add `update_suggestion_note()`
- `backend/app/modules/bas/tax_code_service.py` — add `save_note()`, `delete_note()`
- `backend/app/modules/bas/router.py` — add `PUT/DELETE /note`

### 4. Backend: Xero History & Notes sync (P2)

Files to modify:
- `backend/app/modules/integrations/xero/client.py` — add `add_history_note()` method
- `backend/app/modules/bas/tax_code_service.py` — call Xero sync (fire-and-forget) in `save_note()` when enabled

### 5. Backend: Xero BAS cross-check (P2)

Files to modify:
- `backend/app/modules/integrations/xero/client.py` — add `get_bas_report()` method
- `backend/app/modules/bas/service.py` or new `bas_crosscheck_service.py` — parse BAS labels, compare with calculation
- `backend/app/modules/bas/router.py` — add `GET /xero-crosscheck` endpoint

### 6. Frontend: Remove Reject + Add Notes (P1)

Files to modify:
- `frontend/src/components/bas/TaxCodeSuggestionCard.tsx` — remove Reject button, add "Park it" button and note icon
- `frontend/src/components/bas/TaxCodeResolutionPanel.tsx` — remove handleReject, add handlePark/handleNote, add "Parked" section with Approve and "Back to Manual" actions
- `frontend/src/components/bas/TransactionLineItemGroup.tsx` — remove onReject prop
- `frontend/src/lib/bas.ts` — remove `rejectSuggestion()`, add note/unpark API functions, update `TaxCodeSuggestion` type
- `frontend/src/components/bas/SuggestionNoteEditor.tsx` — NEW: popover note editor

### 7. Frontend: Xero BAS cross-check panel (P2)

Files to create/modify:
- `frontend/src/components/bas/XeroBASCrossCheck.tsx` — NEW: cross-check info panel
- `frontend/src/components/bas/BASTab.tsx` — add cross-check fetch to `fetchSessionDetail()`
- `frontend/src/lib/bas.ts` — add `getXeroBASCrossCheck()` function and types

## Validation

```bash
# Backend
cd backend && uv run ruff check . && uv run pytest
# Frontend
cd frontend && npm run lint && npx tsc --noEmit
```

## Key Test Scenarios

1. Open BAS session → verify no Reject button visible, "Park it" button present
2. View old "rejected" suggestion → displays as "Parked"
3. Click note icon → popover appears → type note → save → reload → note persists
4. "Park it" on a suggestion → note field serves as reason, item moves to "Parked" section
5. In "Parked" section → click "Approve" → suggestion is approved with AI-suggested tax code
6. In "Parked" section → click "Back to Manual" → suggestion returns to pending/manual review
7. Save note with "Sync to Xero" → verify note is dispatched to Xero (fire-and-forget, check logs — no persistent sync status)
8. Open BAS tab → cross-check panel shows Xero figures vs Clairo figures
9. Xero connection expired → cross-check panel shows "Could not fetch" gracefully
