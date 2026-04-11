# Tasks: BAS UX Polish & Xero Status Sync

**Input**: Design documents from `/specs/056-bas-ux-xero-status/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Database Migration)

**Purpose**: Add note columns to `tax_code_suggestions` table — required before any story implementation.

- [x] T001 Create Alembic migration adding `note_text` (TEXT), `note_updated_by` (UUID FK → practice_users.id), `note_updated_at` (TIMESTAMPTZ) columns to `tax_code_suggestions` table. Include data migration copying existing `dismissal_reason` values to `note_text` for dismissed suggestions. Add partial index `ix_tax_code_suggestions_has_note` on `(session_id) WHERE note_text IS NOT NULL`. File: `backend/alembic/versions/YYYYMMDD_056_add_suggestion_notes_columns.py`

- [x] T002 Run migration and verify columns exist: `cd backend && uv run alembic upgrade head`

---

## Phase 2: Foundational (Backend Model & Schema Updates)

**Purpose**: Update the TaxCodeSuggestion model and schemas — all stories depend on these.

- [x] T003 [P] Add `note_text`, `note_updated_by`, `note_updated_at` mapped columns to `TaxCodeSuggestion` model. Add `note_updated_by_user` relationship to `PracticeUser`. File: `backend/app/modules/bas/models.py`

- [x] T004 [P] Update `TaxCodeSuggestionResponse` schema to include `note_text`, `note_updated_by`, `note_updated_by_name`, `note_updated_at` fields. Add `SuggestionNoteRequest` (note_text: str max 2000, sync_to_xero: bool = False) and `SuggestionNoteResponse` schemas. File: `backend/app/modules/bas/schemas.py`

- [x] T005 [P] Update `TaxCodeSuggestion` frontend TypeScript interface to include `note_text`, `note_updated_by`, `note_updated_by_name`, `note_updated_at` fields. Map both `rejected` and `dismissed` status to display as "Dismissed" in any status rendering logic. File: `frontend/src/lib/bas.ts`

---

## Phase 3: User Story 1 — Remove Reject Action (P1)

**Goal**: Remove the "Reject" button from all suggestion UIs. The `/reject` API endpoint stays but maps to dismiss internally. Old `rejected` records display as "Dismissed."

**Independent Test**: Open any BAS session with suggestions → only Approve, Override, Dismiss buttons visible. Call `/reject` API → suggestion status becomes `dismissed`.

- [x] T006 [US1] Modify `reject_suggestion()` in TaxCodeService to internally call `dismiss_suggestion()` logic: set `status = "dismissed"` (not "rejected"), write `reason` to `note_text` instead of `dismissal_reason`, create audit event with type `tax_code_transaction_dismissed`. Keep method name for backward compat. File: `backend/app/modules/bas/tax_code_service.py`

- [x] T007 [US1] Remove `onReject` prop from `TaxCodeSuggestionCard` component. Remove the "Reject" `<Button>` and its `handleAction('reject', ...)` call. Remove `isLoading === 'reject'` state. Update status display: map `suggestion.status === 'rejected'` to show "Dismissed" with the same Ban icon and `bg-muted/30` styling as `dismissed`. File: `frontend/src/components/bas/TaxCodeSuggestionCard.tsx`

- [x] T008 [P] [US1] Remove `onReject` prop from `TransactionLineItemGroup` component props interface and all pass-throughs to `TaxCodeSuggestionCard`. File: `frontend/src/components/bas/TransactionLineItemGroup.tsx`

- [x] T009 [US1] In `TaxCodeResolutionPanel`: remove `import { rejectSuggestion }` from `@/lib/bas`, remove `handleReject` function, remove `onReject={handleReject}` from all `SuggestionTable` instances, remove `onReject` from `SuggestionTable` props interface and destructuring. File: `frontend/src/components/bas/TaxCodeResolutionPanel.tsx`

- [x] T010 [US1] Remove or deprecate the `rejectSuggestion()` export function from the frontend API layer (delete the function body, or keep but mark with `@deprecated` comment). File: `frontend/src/lib/bas.ts`

- [x] T011 [US1] Run linting and type checks to verify no broken references: `cd frontend && npm run lint && npx tsc --noEmit`

---

## Phase 4: User Story 2 — Per-Transaction Notes (P1)

**Goal**: Accountants can add, view, and edit a free-text note on each suggestion via an inline popover. Notes replace `dismissal_reason` for new dismissals. Audit trail captures note CRUD.

**Independent Test**: Open BAS session → click note icon on any suggestion → type note → save → reload page → note persists with visual indicator.

- [x] T012 [US2] Add `update_suggestion_note()` and `delete_suggestion_note()` repository methods to update `note_text`, `note_updated_by`, `note_updated_at` on a TaxCodeSuggestion. Use `flush()` not `commit()`. File: `backend/app/modules/bas/repository.py`

- [x] T013 [US2] Add `save_note()` and `delete_note()` methods to TaxCodeService. `save_note()`: validate note_text length (1–2000 chars), update suggestion via repo, create audit event (`suggestion.note_created` or `suggestion.note_updated` with old/new text). `delete_note()`: set note_text/note_updated_by/note_updated_at to NULL, create audit event. Update `dismiss_suggestion()` to write reason to `note_text` instead of `dismissal_reason`. File: `backend/app/modules/bas/tax_code_service.py`

- [x] T014 [US2] Add three new router endpoints: `PUT /{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/{suggestion_id}/note` (save/update note), `DELETE .../note` (remove note). Wire to TaxCodeService methods. Use existing `verify_connection_access` pattern. File: `backend/app/modules/bas/router.py`

- [x] T015 [P] [US2] Add `saveNote()` and `deleteNote()` frontend API functions following existing pattern (token, connectionId, sessionId, suggestionId params). Add `SuggestionNoteRequest` and `SuggestionNoteResponse` TypeScript interfaces. File: `frontend/src/lib/bas.ts`

- [x] T016 [US2] Create `SuggestionNoteEditor` component: a shadcn/ui `Popover` triggered by a `MessageSquare` icon button on each suggestion row. Contains a `Textarea` (max 2000 chars with character counter), Save/Cancel buttons. On save, calls `saveNote()` API and refreshes suggestion data. Show filled icon when `note_text` is non-null. File: `frontend/src/components/bas/SuggestionNoteEditor.tsx`

- [x] T017 [US2] Integrate `SuggestionNoteEditor` into `TaxCodeSuggestionCard`: add note icon button in the actions area (visible for all statuses), pass suggestion data and save/refresh callbacks. Show `note_text` preview on hover via `Tooltip` when note exists. File: `frontend/src/components/bas/TaxCodeSuggestionCard.tsx`

- [x] T018 [US2] Run backend tests and lint: `cd backend && uv run ruff check . && uv run pytest -k "suggestion"`

---

## Phase 5: User Story 3 — Sync Notes to Xero (P2)

**Goal**: Optional "Sync to Xero" toggle when saving a note. Pushes note to Xero's History & Notes API on a fire-and-forget basis (no persistent status tracking, no retry).

**Depends on**: US2 (notes must exist)

**Independent Test**: Save note with "Sync to Xero" enabled → note is dispatched to Xero's History & Notes for the transaction (verify via Xero UI or logs).

- [x] T019 [US3] Add `add_history_note()` method to XeroClient: `PUT /{entity_type}/{entity_id}/History` with `{"HistoryRecords": [{"Details": "..."}]}` body. Support entity types: `BankTransactions`, `Invoices`, `CreditNotes`. Map `source_type` enum values to Xero entity type paths. Truncate `Details` to 447 chars + "..." if over 450. Return `(response_data, rate_limit)`. File: `backend/app/modules/integrations/xero/client.py`

- [x] T020 [US3] Extend `save_note()` in TaxCodeService: when `sync_to_xero=True`, call Xero sync fire-and-forget via the Xero integration service (get connection, get access token, call `add_history_note()`). Log success or failure but do not persist sync status. Create `suggestion.note_xero_synced` audit event. File: `backend/app/modules/bas/tax_code_service.py`

- [x] T021 [P] [US3] Extend `SuggestionNoteEditor` popover: add "Sync to Xero" checkbox (visible only when Xero connection is active and `source_type` is `bank_transaction`, `invoice`, or `credit_note`). No sync status display needed (fire-and-forget). Pass `connectionId` prop to determine Xero availability. File: `frontend/src/components/bas/SuggestionNoteEditor.tsx`

---

## Phase 6: User Story 4 — Xero BAS Cross-Check (P2)

**Goal**: When BAS session detail loads, fetch BAS report from Xero for the matching period and show a comparison panel with key figures (1A, 1B, net GST).

**Independent of**: US1, US2, US3 (can be built in parallel)

**Independent Test**: Open BAS tab for a client with Xero BAS data → cross-check panel shows Xero vs Clairo figures with amber highlights on differences >$1.

- [x] T024 [US4] Add `get_bas_report()` method to XeroClient following the existing report pattern: `GET /Reports/BAS` with period date params. Return raw report JSON + rate_limit. File: `backend/app/modules/integrations/xero/client.py`

- [x] T025 [US4] Add `get_xero_bas_crosscheck()` service method: fetch BAS report from Xero for the session's period, parse BAS label rows to extract 1A/1B/net GST amounts, load Clairo's calculation for the session, compute differences and flag material (>$1) discrepancies. Return structured response per `xero-crosscheck-api.md` contract. Handle Xero errors gracefully (return `xero_report_found: null` with `xero_error` message). File: `backend/app/modules/bas/tax_code_service.py` (or new `backend/app/modules/bas/crosscheck_service.py`)

- [x] T026 [US4] Add `GET /{connection_id}/bas/sessions/{session_id}/xero-crosscheck` router endpoint. Add `XeroBASCrossCheckResponse` schema with `xero_report_found`, `xero_figures`, `clairo_figures`, `differences`, `period_label`, `fetched_at`, `xero_error` fields. Create `bas.xero_crosscheck` audit event on each fetch. File: `backend/app/modules/bas/router.py` and `backend/app/modules/bas/schemas.py`

- [x] T027 [P] [US4] Add `getXeroBASCrossCheck()` frontend API function and `XeroBASCrossCheck` TypeScript interface. File: `frontend/src/lib/bas.ts`

- [x] T028 [US4] Create `XeroBASCrossCheck` component: compact info panel using shadcn `Card` with `CardHeader`/`CardContent`. Shows "Xero BAS data found" or "No BAS report found" message. When found, renders a small table comparing 1A, 1B, net GST between Xero and Clairo. Highlights cells with >$1 difference using amber background. Shows dismiss X button that hides panel (sessionStorage-based). Shows subtle error message if Xero fetch failed. File: `frontend/src/components/bas/XeroBASCrossCheck.tsx`

- [x] T029 [US4] Integrate cross-check into BASTab: in `fetchSessionDetail()`, add `getXeroBASCrossCheck()` to the second wave of `Promise.allSettled` calls (alongside suggestion summary and writeback jobs). Store result in new `xeroCrossCheck` state. Render `<XeroBASCrossCheck>` component above the session detail content when data is available. File: `frontend/src/components/bas/BASTab.tsx`

---

## Phase 7: Polish & Cross-Cutting

**Purpose**: Final validation, lint fixes, and cleanup.

- [x] T030 Run full backend validation: `cd backend && uv run ruff check . && uv run ruff format . && uv run pytest`

- [x] T031 Run full frontend validation: `cd frontend && npm run lint && npx tsc --noEmit`

- [x] T032 Manual smoke test: open a BAS session with suggestions, verify (a) no Reject button, (b) old rejected suggestions show as "Dismissed", (c) can add/edit/delete notes, (d) Xero sync toggle dispatches fire-and-forget sync, (e) cross-check panel loads on BAS tab

---

## Dependencies

```
Phase 1 (Migration) → Phase 2 (Model/Schema)
Phase 2 → Phase 3 (US1: Remove Reject) — no other deps
Phase 2 → Phase 4 (US2: Notes) — no other deps
Phase 4 (US2) → Phase 5 (US3: Xero Note Sync) — US3 depends on US2
Phase 2 → Phase 6 (US4: Cross-Check) — independent of US1/US2/US3
All phases → Phase 7 (Polish)
```

## Parallel Execution Opportunities

**Within Phase 2**: T003, T004, T005 can all run in parallel (different files).

**Phase 3 + Phase 6**: US1 (Remove Reject) and US4 (Cross-Check) are fully independent and can be built in parallel after Phase 2.

**Within Phase 4**: T015 (frontend API functions) can run in parallel with T012-T014 (backend).

**Within Phase 6**: T027 (frontend API function) can run in parallel with T024-T026 (backend).

## Implementation Strategy

**MVP**: Phase 1 + Phase 2 + Phase 3 (US1) + Phase 4 (US2) = Remove Reject + Notes. This delivers the two P1 stories with immediate user value.

**Increment 2**: Phase 5 (US3) + Phase 6 (US4) = Xero integration features. These are P2 and can ship together or independently.

## Summary

| Metric | Value |
|--------|-------|
| Total tasks | 29 |
| US1 (Remove Reject) | 6 tasks (T006–T011) |
| US2 (Notes) | 7 tasks (T012–T018) |
| US3 (Xero Note Sync) | 3 tasks (T019–T021) |
| US4 (Cross-Check) | 6 tasks (T024–T029) |
| Setup/Foundation/Polish | 7 tasks (T001–T005, T030–T032) |
| Parallelizable tasks | 9 (marked [P]) |
