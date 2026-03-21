# Tasks: Voice Feedback Portal

**Input**: Design documents from `/specs/048-voice-feedback-portal/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/feedback-api.yaml

**Tests**: Not explicitly requested — test tasks omitted. Manual verification via quickstart.md.

**Organization**: Tasks grouped by user story. US1 and US2 are combined into a single phase since they form one indivisible user flow (voice capture → AI conversation → brief).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 0: Git Setup

**Purpose**: Feature branch already created by `/speckit.specify`

- [x] T000 Verify on feature branch `048-voice-feedback-portal`
  - Run: `git branch --show-current` → should show `048-voice-feedback-portal`
  - If not: `git checkout 048-voice-feedback-portal`

---

## Phase 1: Setup

**Purpose**: Install dependencies and create module skeleton

- [x] T001 Install backend dependency: `cd backend && uv add openai` (Whisper transcription API)
- [x] T002 Install frontend dependencies: `cd frontend && npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities`
- [x] T003 Add `OPENAI_API_KEY` to backend config in `backend/app/config.py` — add a new `openai` settings section with `api_key: SecretStr` field, following the existing `anthropic` config pattern
- [x] T004 Create feedback module directory: `backend/app/modules/feedback/` with empty `__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Data layer, schemas, repository, and frontend plumbing that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 [P] Create enums in `backend/app/modules/feedback/enums.py` — define `SubmissionType`, `SubmissionStatus`, `MessageRole`, `ContentType`, `Severity` enums (all inheriting from `str, Enum`) per data-model.md
- [x] T006 [P] Create exceptions in `backend/app/modules/feedback/exceptions.py` — define `FeedbackError(DomainError)` base, `SubmissionNotFoundError(FeedbackError)` with 404, `ConversationCompleteError(FeedbackError)` with 400, `InvalidAudioError(FeedbackError)` with 400, following `backend/app/modules/portal/exceptions.py` pattern
- [x] T007 Create models in `backend/app/modules/feedback/models.py` — implement `FeedbackSubmission` (using `BaseModel` + `TenantMixin` from `app.database`), `FeedbackMessage`, `FeedbackComment` with all fields, indexes, relationships, and cascade deletes per data-model.md. Import enums from `enums.py`. Add composite indexes: `(tenant_id, status)`, `(tenant_id, submitter_id)`, `(tenant_id, type)` on submissions; `(submission_id, created_at)` on messages; `(submission_id)` on comments
- [x] T008 Create Alembic migration: `cd backend && uv run alembic revision --autogenerate -m "add feedback tables"` — verify the generated migration creates `feedback_submissions`, `feedback_messages`, `feedback_comments` tables with correct columns and indexes, then run `uv run alembic upgrade head`
- [x] T009 [P] Create schemas in `backend/app/modules/feedback/schemas.py` — define `SubmissionCreate`, `SubmissionResponse` (with `from_model()` classmethod and computed `has_brief` field), `SubmissionDetailResponse`, `SubmissionListResponse` (with `items`, `total`, `limit`, `offset`), `MessageResponse`, `ConversationResponse`, `ConversationTurnResponse`, `VoiceConversationTurnResponse`, `CommentCreate`, `CommentResponse`, `FeedbackStats`, `StatusUpdate`, `BriefConfirmRequest` per contracts/feedback-api.yaml. All response schemas must have `model_config = {"from_attributes": True}`
- [x] T010 [P] Create repository in `backend/app/modules/feedback/repository.py` — implement `FeedbackRepository` with methods: `create_submission()`, `get_submission()` (with tenant check), `list_submissions()` (with status/type/submitter filters, pagination, returns `tuple[list, int]`), `update_submission()`, `update_status()`, `get_stats()` (counts by status and type), `create_message()`, `list_messages()` (ordered by created_at), `create_comment()`, `list_comments()`. All methods take `tenant_id` parameter. Use `flush()` not `commit()`. Follow `backend/app/modules/portal/repository.py` pattern
- [x] T011 [P] Create TypeScript types in `frontend/src/types/feedback.ts` — define interfaces matching API schemas: `FeedbackSubmission`, `SubmissionDetail`, `SubmissionListResponse`, `FeedbackMessage`, `ConversationTurnResponse`, `VoiceConversationTurnResponse`, `FeedbackComment`, `FeedbackStats`, `SubmissionType`, `SubmissionStatus`, `Severity` (as union types)
- [x] T012 [P] Create API client in `frontend/src/lib/api/feedback.ts` — implement functions using `apiClient` pattern from `frontend/src/lib/api-client.ts`: `createSubmission(token, type, audioFile)` (FormData), `listSubmissions(token, params)`, `getSubmission(token, id)`, `updateStatus(token, id, status)`, `getConversation(token, id)`, `sendMessage(token, id, content, contentType)`, `sendVoiceMessage(token, id, audioFile)` (FormData), `confirmBrief(token, id, revisions?)`, `exportBrief(token, id)`, `getStats(token)`, `listComments(token, id)`, `addComment(token, id, content)`. All functions return typed responses
- [x] T013 Add "Feedback" navigation item in `frontend/src/app/(protected)/layout.tsx` — add to the `navigation` array with `{ name: 'Feedback', href: '/feedback', icon: MessageSquareText }` (import `MessageSquareText` from `lucide-react`). Place it after "Notifications" in the nav order

**Checkpoint**: Data layer, API client, and navigation are ready. User story implementation can begin.

---

## Phase 3: User Story 1+2 — Voice Submission + AI Conversation (Priority: P1) MVP

**Goal**: A user can record/upload a voice memo, have a structured AI conversation in either Feature Request or Bug/Enhancement mode, review a generated brief, and confirm the submission.

**Independent Test**: Record a voice memo, complete the AI conversation with 2-3 follow-up exchanges, verify the generated brief contains all required fields, confirm submission appears with status "New".

### Backend

- [x] T014 [P] [US1] Create transcription service in `backend/app/modules/feedback/transcription.py` — implement `TranscriptionService` class with method `transcribe(audio_file: UploadFile) -> tuple[str, int]` that: validates file extension (mp3, m4a, wav, webm) and size (max 25MB), uploads to OpenAI Whisper API using the `openai` package (`client.audio.transcriptions.create(model="whisper-1", file=file)`), returns `(transcript_text, duration_seconds)`. Raise `InvalidAudioError` for invalid files. Get API key from settings via `get_settings().openai.api_key.get_secret_value()`
- [x] T015 [P] [US1] Create AI prompts in `backend/app/modules/feedback/prompts.py` — define three prompt constants: (1) `PM_HAT_SYSTEM_PROMPT` — instructs Claude to act as a product manager collecting feature request info (user story, current behaviour, desired behaviour, domain context, frequency, impact); includes the brief JSON template fields; instructs to ask follow-up questions until all fields are populated. (2) `ENGINEER_HAT_SYSTEM_PROMPT` — instructs Claude to act as a BA/engineer collecting bug/enhancement info (observed behaviour, expected behaviour, business rule, severity, reproduction context); includes the brief JSON template. (3) `BRIEF_GENERATION_PROMPT` — instructs Claude to produce a structured JSON brief from the full conversation, conforming to the mode-specific schema from research.md Decision 7. All prompts should instruct the agent to respond conversationally (not in JSON) during the Q&A phase, and only output JSON when explicitly asked to generate the final brief
- [x] T016 [US1] Create feedback service in `backend/app/modules/feedback/service.py` — implement `FeedbackService(session: AsyncSession)` that internally creates `FeedbackRepository(session)` and `TranscriptionService()`. Methods: (1) `create_submission(tenant_id, submitter_id, submitter_name, type, audio_file)` — uploads audio to MinIO at key `feedback/{tenant_id}/{submission_id}/audio.{ext}`, transcribes via Whisper, creates submission record with status "draft", stores system prompt as first message, sends transcript as second message (role=user, content_type=transcript), calls Claude for initial response, stores assistant response as third message, returns submission. (2) `send_message(submission_id, tenant_id, content, content_type)` — validates conversation not complete, stores user message, builds messages array from all stored messages, calls Claude API with system prompt + message history, stores assistant response, checks if brief is ready (Claude will signal this), returns `ConversationTurnResponse`. (3) `send_voice_message(submission_id, tenant_id, audio_file)` — transcribes audio, then calls `send_message()` with content_type=transcript. (4) `confirm_brief(submission_id, tenant_id, revisions)` — if revisions provided, sends revision instructions to Claude and regenerates brief; otherwise takes the latest brief from the conversation, validates JSON structure via Pydantic, renders brief_markdown, updates submission with brief_data, brief_markdown, title (from brief), severity (from brief if bug mode), status="new", conversation_complete=True. (5) `get_conversation(submission_id, tenant_id)` — returns ordered messages. Use `anthropic.Anthropic` client following pattern from `backend/app/modules/agents/orchestrator.py`. Raise domain exceptions, never HTTPException
- [x] T017 [US1] Create router endpoints for submission flow in `backend/app/modules/feedback/router.py` — implement FastAPI router with `prefix="/api/v1/feedback"`, `tags=["feedback"]`. Use `Annotated` dependency injection pattern from `backend/app/modules/action_items/router.py`. Endpoints: (1) `POST /` — accepts `UploadFile` + `Form(type)`, creates submission via service, returns 201 `SubmissionResponse`. (2) `GET /{submission_id}/conversation` — returns `ConversationResponse`. (3) `POST /{submission_id}/conversation/message` — accepts JSON body with content + content_type, returns `ConversationTurnResponse`. (4) `POST /{submission_id}/conversation/voice` — accepts `UploadFile`, returns `VoiceConversationTurnResponse`. (5) `POST /{submission_id}/confirm` — accepts optional revisions, returns `SubmissionResponse`. Add audit events for `feedback.created`. Catch domain exceptions — the global handler in main.py handles conversion to HTTP responses automatically
- [x] T018 [US1] Register feedback router in `backend/app/main.py` — add import and `app.include_router(feedback_router, tags=["feedback"])` in `register_routes()` function, following the existing module registration pattern with try/except
- [x] T019 [US1] Update module exports in `backend/app/modules/feedback/__init__.py` — export router, models, enums, schemas, service with `__all__`

### Frontend

- [x] T020 [P] [US1] Create AudioRecorder component in `frontend/src/components/feedback/AudioRecorder.tsx` — implement a recording widget using native `MediaRecorder` API: (1) "Record" button that requests microphone via `navigator.mediaDevices.getUserMedia({audio: true})`. (2) During recording: show elapsed time counter, animated waveform visualisation using `AudioContext` + `AnalyserNode` + canvas, "Stop" button. (3) After recording: show playback controls (play/pause, duration), "Re-record" and "Use this recording" buttons. (4) Also include a "Upload file instead" link that opens a file picker accepting `.mp3,.m4a,.wav,.webm` (max 25MB). (5) Export the audio as a `File` object for upload. (6) Handle browser incompatibility: if `navigator.mediaDevices` is unavailable, show only the upload option with an explanatory message. Use shadcn `Button`, `Card`. Use `cn()` for conditional classes
- [x] T021 [P] [US1] Create ConversationChat component in `frontend/src/components/feedback/ConversationChat.tsx` — implement a chat-style conversation UI: (1) Message list showing user and assistant messages with role indicators, timestamps via `formatRelativeTime`. Transcript messages show a microphone icon badge. (2) Input area at bottom with text input (shadcn `Textarea` with auto-resize) and send button. (3) "Record follow-up" button next to the text input that opens a mini audio recorder (reuse AudioRecorder in compact mode), transcribes via `sendVoiceMessage` API, and displays the transcript. (4) Loading state while waiting for AI response (typing indicator). (5) When `brief_ready` is true in the response, display the `BriefPreview` component. (6) Auto-scroll to bottom on new messages via `messagesEndRef`. Use shadcn `Card`, `Button`, `Badge`, `ScrollArea`
- [x] T022 [P] [US1] Create BriefPreview component in `frontend/src/components/feedback/BriefPreview.tsx` — display the AI-generated brief for review: (1) Render `brief_markdown` in a styled card with appropriate headings. (2) Two action buttons: "Confirm" (calls `confirmBrief` API with no revisions) and "Request Changes" (opens a text input for revision instructions, calls `confirmBrief` with revisions string). (3) Loading state while confirmation is processing. (4) On successful confirmation, show success message and redirect to `/feedback`. Use shadcn `Card`, `Button`, `Textarea`
- [x] T023 [US1] Create new submission page in `frontend/src/app/(protected)/feedback/new/page.tsx` — implement the full submission flow as a multi-step page: (1) Step 1: Mode selection — two large cards "Feature Request" and "Bug / Enhancement" with icons and descriptions. (2) Step 2: Audio capture — render `AudioRecorder` component. On completion, call `createSubmission` API with the audio file and selected type. Show loading state during transcription ("Transcribing your recording..."). (3) Step 3: AI conversation — render `ConversationChat` component with the submission ID. The initial AI message from the API response is already loaded. (4) Step 3 includes BriefPreview inline when the brief is ready. (5) After confirmation, redirect to `/feedback`. Use `useAuth()` for token, `useRouter()` for navigation. Page title: "New Feedback". Back button to `/feedback`

**Checkpoint**: At this point, users can record voice feedback, have an AI conversation, and save structured briefs. This is the MVP.

---

## Phase 4: User Story 3 — Kanban Board (Priority: P2)

**Goal**: Team members can view all submissions on a kanban board with drag-and-drop to update status.

**Independent Test**: Create 3+ submissions, verify they appear as cards on the board, drag a card between columns, verify status persists on refresh.

### Backend

- [x] T024 [US3] Add list, detail, status update, and stats endpoints to `backend/app/modules/feedback/router.py` — add: (1) `GET /` — calls `service.list_submissions()` with query params (status, type, mine_only, limit, offset), returns `SubmissionListResponse`. Non-admin users forced to `mine_only=True`. (2) `GET /{submission_id}` — returns `SubmissionDetailResponse` including message_count and comment_count. (3) `PATCH /{submission_id}/status` — requires admin role, validates status transition, calls `service.update_status()`, emits `feedback.status_change` audit event, returns `SubmissionResponse`. (4) `GET /stats` — returns `FeedbackStats` with counts by status and type. Add role checking using existing `get_current_practice_user` dependency

### Frontend

- [x] T025 [P] [US3] Create FeedbackCard component in `frontend/src/components/feedback/FeedbackCard.tsx` — render a compact card for kanban display: title (or "Untitled" if draft), type badge (coral for feature request, blue for bug), severity badge (if set, using status colour semantics), submitter name, relative time via `formatRelativeTime`, and conversation status indicator (draft/complete). Card is clickable (onClick prop). Use shadcn `Card`, `Badge`. Use `cn()` for conditional styles. Card must accept `dnd-kit` sortable props for drag-and-drop
- [x] T026 [US3] Create KanbanBoard component in `frontend/src/components/feedback/KanbanBoard.tsx` — implement a 5-column kanban board using `@dnd-kit/core` and `@dnd-kit/sortable`: columns are New, In Review, Planned, In Progress, Done (exclude Draft — drafts are not shown on the board). Each column shows a count badge in the header. Cards are `SortableItem` wrappers around `FeedbackCard`. On `DragEnd`, if the card moved to a different column, call `updateStatus` API and optimistically update local state. Show empty state per column ("No submissions"). Column headers use status colour coding (green for Done, amber for In Review/Planned, coral for New). Use shadcn components, `cn()` for classes
- [x] T027 [US3] Create main feedback page in `frontend/src/app/(protected)/feedback/page.tsx` — implement the primary feedback page: (1) Page header with title "Feedback" and "New Submission" button (links to `/feedback/new`). (2) Stats bar showing total count and counts by status. (3) KanbanBoard component populated from `listSubmissions` API call. (4) Data fetching via `useAuth()` + `useCallback` + `useEffect` pattern (following clients page pattern). (5) Refresh on card status change (optimistic update in kanban, refetch stats). (6) Page title: "Feedback", subtitle: "Voice-powered feedback from your team"

**Checkpoint**: Kanban board is functional. Team can view, drag, and manage submissions.

---

## Phase 5: User Story 4 — List View & Filtering (Priority: P2)

**Goal**: Alternative list view with filtering by type, status, and date. Submitters see only their own, admins see all.

**Independent Test**: Toggle to list view, apply type and status filters, verify correct results. Log in as non-admin, verify only own submissions visible.

- [x] T028 [US4] Create SubmissionDetail dialog in `frontend/src/components/feedback/SubmissionDetail.tsx` — implement a wide shadcn `Dialog` (max-w-4xl) that shows full submission details: (1) Header with title, type badge, status badge, severity badge, submitter, and timestamps. (2) Brief section — render `brief_markdown` (or "Brief not yet generated" for drafts). (3) Transcript section — collapsible, shows original audio transcript. (4) Conversation section — collapsible, shows full message history with role indicators. (5) Metadata sidebar (on desktop) with submission ID, created date, last updated, audio duration. Follow the `InsightDetailPanel` two-column Dialog pattern from `frontend/src/components/insights/InsightDetailPanel.tsx`
- [x] T029 [US4] Add list view toggle and filters to `frontend/src/app/(protected)/feedback/page.tsx` — extend the main page: (1) Add a view toggle (Kanban / List) using shadcn `Tabs` or icon buttons. (2) List view renders a shadcn `Table` with columns: Title, Type, Status, Severity, Submitter, Created, Updated. Follow the table pattern from `frontend/src/app/(protected)/clients/page.tsx`. (3) Add filter controls above the table/kanban: type dropdown (All / Feature Request / Bug & Enhancement), status dropdown (All / individual statuses). (4) "My Submissions" toggle for admin users (non-admins always see only their own). (5) Clicking a row/card opens `SubmissionDetail` dialog. (6) Pagination in footer using existing offset/limit pattern. (7) Empty states for both views

**Checkpoint**: Full list view with filtering and detail dialog working alongside the kanban.

---

## Phase 6: User Story 5 — Team Notes & Comments (Priority: P3)

**Goal**: Team members can add internal comments to any submission, visible in the detail view.

**Independent Test**: Open a submission detail, add a comment, verify it appears with author and timestamp. Verify non-admin users cannot add comments.

- [x] T030 [US5] Add comment endpoints to `backend/app/modules/feedback/router.py` — add: (1) `GET /{submission_id}/comments` — requires admin role, returns list of `CommentResponse` ordered by created_at. (2) `POST /{submission_id}/comments` — requires admin role, accepts `CommentCreate` body, creates comment via service, emits `feedback.comment_added` audit event, returns 201 `CommentResponse`
- [x] T031 [US5] Add comments section to `frontend/src/components/feedback/SubmissionDetail.tsx` — extend the detail dialog: (1) "Team Notes" section at the bottom (only visible to admin users). (2) List existing comments with author name, timestamp (`formatRelativeTime`), and content. (3) "Add Note" text input with submit button. (4) On submit, call `addComment` API and optimistically add to list. (5) Show comment count in header. Use shadcn `Textarea`, `Button`, `Separator`

**Checkpoint**: Team comments functional within submission detail view.

---

## Phase 7: User Story 6 — Brief Export for Speckit (Priority: P3)

**Goal**: Team members can export a confirmed brief as a markdown document formatted for speckit input.

**Independent Test**: Open a confirmed submission, click "Export for Spec", verify the downloaded/copied markdown contains all brief fields in a clean format.

- [x] T032 [US6] Add export endpoint to `backend/app/modules/feedback/router.py` — add `GET /{submission_id}/export` that returns `brief_markdown` as `text/markdown` content type with `Content-Disposition: attachment; filename="feedback-{submission_id}-brief.md"`. Return 400 if brief not yet generated. Emit `feedback.exported` audit event
- [x] T033 [US6] Add export button to `frontend/src/components/feedback/SubmissionDetail.tsx` — add an "Export for Spec" button (with Download icon from lucide-react) in the detail dialog header/footer. Only visible when `has_brief` is true. On click, call `exportBrief` API and either: (a) trigger a file download of the markdown, or (b) copy to clipboard with a toast notification "Brief copied to clipboard". Include both options as a dropdown: "Download as .md" and "Copy to clipboard"

**Checkpoint**: Briefs can be exported for speckit workflow integration.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final cleanup and validation

- [x] T034 Add feedback status config to `frontend/src/lib/constants/status.ts` — add feedback-specific status configurations: `new` (coral dot, "New"), `in_review` (amber dot, "In Review"), `planned` (amber dot, "Planned"), `in_progress` (blue dot, "In Progress"), `done` (green dot, "Done"), `draft` (stone dot, "Draft"). Add submission type configs: `feature_request` (coral badge), `bug_enhancement` (blue badge). Add severity configs: `low` (stone), `medium` (amber), `high` (orange), `critical` (red)
- [x] T035 Run backend linting and formatting: `cd backend && uv run ruff check app/modules/feedback/ && uv run ruff format app/modules/feedback/`
- [x] T036 Run frontend type checking and linting: `cd frontend && npx tsc --noEmit && npm run lint`
- [x] T037 Run quickstart.md verification — follow all 11 steps in `specs/048-voice-feedback-portal/quickstart.md` to validate the full end-to-end flow

---

## Phase FINAL: PR & Merge

- [x] T038 Ensure all backend tests pass: `cd backend && uv run pytest` (601 passed, pre-existing failures only — no regressions from feedback module)
- [x] T039 Run full validation: `cd backend && uv run ruff check . && cd ../frontend && npm run lint && npx tsc --noEmit` (all feedback module code passes — 0 TS errors, 0 lint errors in new code)
- [ ] T040 Push feature branch and create PR
  - Run: `git push -u origin 048-voice-feedback-portal`
  - Run: `gh pr create --title "Spec 048: Voice Feedback Portal" --body "..."`
  - Include summary: new feedback module, 3 tables, 12 API endpoints, kanban board, voice recording + AI conversation
- [ ] T041 Address review feedback (if any)
- [ ] T042 Merge PR to main — squash merge after approval, delete feature branch
- [ ] T043 Update `specs/ROADMAP.md` — mark spec 048 as COMPLETE

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 0 (Git)**: Already done
- **Phase 1 (Setup)**: Dependencies + config — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — creates all shared data layer + frontend plumbing
- **Phase 3 (US1+US2)**: Depends on Phase 2 — the MVP. Voice capture, AI conversation, brief generation
- **Phase 4 (US3)**: Depends on Phase 2 + Phase 3 (needs submissions to exist for the kanban to display)
- **Phase 5 (US4)**: Depends on Phase 4 (extends the main page with list view + detail dialog)
- **Phase 6 (US5)**: Depends on Phase 5 (adds comments to the detail dialog)
- **Phase 7 (US6)**: Depends on Phase 5 (adds export button to the detail dialog)
- **Phase 8 (Polish)**: After all desired story phases
- **Phase FINAL**: After Phase 8

### User Story Dependencies

- **US1+US2 (P1)**: Independent — can start after Phase 2
- **US3 (P2)**: Needs US1+US2 complete (kanban needs submissions to display)
- **US4 (P2)**: Needs US3 complete (extends the main page)
- **US5 (P3)**: Needs US4 complete (adds to detail dialog)
- **US6 (P3)**: Needs US4 complete (adds to detail dialog) — can run **in parallel with US5**

### Parallel Opportunities

- **Phase 2**: T005, T006 in parallel; T009, T010, T011, T012, T013 in parallel (after T007/T008)
- **Phase 3**: T014, T015 in parallel; T020, T021, T022 in parallel (frontend components)
- **Phase 6 + 7**: US5 and US6 can be worked on simultaneously (different endpoints, different UI areas)

---

## Parallel Example: Phase 2 (Foundational)

```
# Round 1 — No dependencies, all different files:
T005: Create enums in backend/app/modules/feedback/enums.py
T006: Create exceptions in backend/app/modules/feedback/exceptions.py

# Round 2 — Depends on T005 (enums):
T007: Create models in backend/app/modules/feedback/models.py

# Round 3 — Depends on T007 (models):
T008: Create Alembic migration

# Round 4 — Depends on T007 (models), all different files:
T009: Create schemas in backend/app/modules/feedback/schemas.py
T010: Create repository in backend/app/modules/feedback/repository.py
T011: Create TypeScript types in frontend/src/types/feedback.ts
T012: Create API client in frontend/src/lib/api/feedback.ts
T013: Add nav item in frontend/src/app/(protected)/layout.tsx
```

## Parallel Example: Phase 3 (US1+US2 MVP)

```
# Round 1 — Backend services, no mutual dependencies:
T014: Create transcription service in backend/.../transcription.py
T015: Create AI prompts in backend/.../prompts.py

# Round 2 — Depends on T014, T015:
T016: Create feedback service in backend/.../service.py

# Round 3 — Depends on T016:
T017: Create router endpoints in backend/.../router.py
T018: Register router in backend/app/main.py
T019: Update module __init__.py

# Round 4 — Frontend components, no mutual dependencies (can start during Round 1-3):
T020: Create AudioRecorder component
T021: Create ConversationChat component
T022: Create BriefPreview component

# Round 5 — Depends on T020, T021, T022 + backend ready:
T023: Create new submission page
```

---

## Implementation Strategy

### MVP First (Phase 1-3 Only)

1. Complete Phase 1: Setup (install deps, config)
2. Complete Phase 2: Foundational (models, schemas, repo, types, API client)
3. Complete Phase 3: US1+US2 (voice capture → AI conversation → brief)
4. **STOP and VALIDATE**: Test with a real voice memo. Can you record, have a conversation, and get a useful brief?
5. If yes, the core value is proven

### Incremental Delivery

1. **Phase 1-3** → MVP: Record voice → AI conversation → structured brief (13 tasks)
2. **Phase 4** → Add kanban board for team visibility (+3 tasks)
3. **Phase 5** → Add list view, filters, detail dialog (+2 tasks)
4. **Phase 6** → Add team comments (+2 tasks)
5. **Phase 7** → Add speckit export (+2 tasks)
6. **Phase 8** → Polish and validate (+4 tasks)
7. Each phase adds value without breaking previous phases

---

## Notes

- Total tasks: 44 (T000-T043)
- MVP tasks (Phase 0-3): 24 tasks
- Per-story counts: US1+US2: 10 tasks, US3: 4 tasks, US4: 2 tasks, US5: 2 tasks, US6: 2 tasks
- Setup/Foundation: 14 tasks, Polish/PR: 10 tasks
- Parallel opportunities: 5 rounds in Phase 2, 5 rounds in Phase 3
- Suggested MVP scope: Phase 1-3 only (voice capture + AI conversation + brief generation)
