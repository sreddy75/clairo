# Tasks: BAS Workflow Tracker — Practice Management Layer

**Input**: Design documents from `/specs/058-bas-workflow-tracker/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US5)
- Exact file paths included in all descriptions

---

## Phase 0: Git Setup

- [x] T000 Verify on feature branch `058-bas-workflow-tracker`
  - Run: `git branch --show-current` → should output `058-bas-workflow-tracker`
  - If not: `git checkout 058-bas-workflow-tracker`

---

## Phase 1: Setup

**Purpose**: New models, migration, and foundational schemas

- [x] T001 Create `PracticeClient` SQLAlchemy model in `backend/app/modules/clients/models.py`
  - Fields: id (UUID PK), tenant_id (FK tenants), name (VARCHAR 255), abn (VARCHAR 11 nullable), accounting_software (VARCHAR 20, default 'unknown'), xero_connection_id (FK xero_connections nullable UNIQUE), assigned_user_id (FK practice_users nullable), notes (TEXT nullable), notes_updated_at (TIMESTAMPTZ nullable), notes_updated_by (FK practice_users nullable), manual_status (VARCHAR 20 nullable), created_at, updated_at
  - Include `AuditableMixin` per constitution
  - RLS policy: `tenant_id = current_setting('app.current_tenant_id')::uuid`
  - Indexes: tenant_id, assigned_user_id, xero_connection_id (unique partial), (tenant_id, accounting_software), (tenant_id, name)
  - FK on assigned_user_id → ON DELETE SET NULL (orphan becomes unassigned)
  - Add `AccountingSoftwareType` enum: xero, quickbooks, myob, email, other, unknown
  - Add `ManualBASStatus` enum: not_started, in_progress, completed, lodged

- [x] T002 [P] Create `ClientQuarterExclusion` SQLAlchemy model in `backend/app/modules/clients/models.py`
  - Fields: id (UUID PK), tenant_id (FK tenants), client_id (FK practice_clients), quarter (SMALLINT 1-4), fy_year (VARCHAR 7), reason (VARCHAR 30 nullable), reason_detail (TEXT nullable), excluded_by (FK practice_users), excluded_at (TIMESTAMPTZ), reversed_at (TIMESTAMPTZ nullable), reversed_by (FK practice_users nullable)
  - Unique partial index: (client_id, quarter, fy_year) WHERE reversed_at IS NULL
  - Index: (tenant_id, quarter, fy_year)
  - Add `ExclusionReason` enum: dormant, lodged_externally, gst_cancelled, left_practice, other

- [x] T003 [P] Create `ClientNoteHistory` SQLAlchemy model in `backend/app/modules/clients/models.py`
  - Fields: id (UUID PK), tenant_id (FK tenants), client_id (FK practice_clients), note_text (TEXT), edited_by (FK practice_users), edited_at (TIMESTAMPTZ)
  - Index: (client_id, edited_at DESC)
  - Immutable: add no-update/no-delete rules (same pattern as audit_logs)

- [x] T004 [P] Add `display_name` column (VARCHAR 100, nullable) to `PracticeUser` model in `backend/app/modules/auth/models.py`
  - Add `display_name` field to model class
  - Add `display_name` to `PracticeUserResponse` schema in `backend/app/modules/auth/schemas.py`

- [x] T005 Create Alembic migration for new tables and column in `backend/app/alembic/versions/`
  - Run: `cd backend && uv run alembic revision --autogenerate -m "add practice_clients, exclusions, note_history tables"`
  - Review generated migration — ensure RLS policies, partial unique indexes, and check constraints are correct
  - Add immutability rules (no-update, no-delete) for `client_note_history`
  - Run: `cd backend && uv run alembic upgrade head`

- [x] T006 Create backfill migration in `backend/app/alembic/versions/`
  - Run: `cd backend && uv run alembic revision -m "backfill practice_clients from xero_connections"`
  - INSERT INTO practice_clients from xero_connections WHERE status IN ('active', 'needs_reauth')
  - UPDATE practice_clients SET assigned_user_id from bulk_import_organizations where available (match via xero_tenant_id)
  - Run: `cd backend && uv run alembic upgrade head`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Repository, service, and schema foundations that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T007 Create Pydantic schemas for PracticeClient in `backend/app/modules/clients/schemas.py`
  - `PracticeClientCreate` (name, abn, accounting_software, assigned_user_id, notes)
  - `PracticeClientUpdate` (name, abn, assigned_user_id — all optional)
  - `PracticeClientResponse` (full response with assigned_user_name, notes_updated_by_name, etc.)
  - `PracticeClientAssignRequest` (assigned_user_id: UUID | None)
  - `PracticeClientBulkAssignRequest` (client_ids: list[UUID], assigned_user_id: UUID | None)
  - `PracticeClientNotesUpdate` (notes: str, max 5000 chars)
  - `ManualStatusUpdate` (manual_status: ManualBASStatus)

- [x] T008 [P] Create Pydantic schemas for exclusions in `backend/app/modules/clients/schemas.py`
  - `ClientExclusionCreate` (quarter: int 1-4, fy_year: str, reason: ExclusionReason | None, reason_detail: str | None)
  - `ClientExclusionResponse` (full response with excluded_by_name)
  - `ClientExclusionReversedResponse` (reversed_at, reversed_by_name)

- [x] T009 Create `PracticeClientRepository` in `backend/app/modules/clients/repository.py`
  - `create(data: PracticeClientCreate) -> PracticeClient` — insert new client
  - `get_by_id(client_id: UUID, tenant_id: UUID) -> PracticeClient | None`
  - `get_by_xero_connection_id(connection_id: UUID) -> PracticeClient | None`
  - `update(client_id: UUID, data: PracticeClientUpdate) -> PracticeClient`
  - `update_assignment(client_id: UUID, assigned_user_id: UUID | None) -> PracticeClient`
  - `bulk_update_assignment(client_ids: list[UUID], assigned_user_id: UUID | None, tenant_id: UUID) -> int`
  - `update_notes(client_id: UUID, notes: str, updated_by: UUID) -> PracticeClient`
  - `update_manual_status(client_id: UUID, status: str) -> PracticeClient`
  - All methods must include `tenant_id` in WHERE clauses
  - Use `flush()` not `commit()` per constitution

- [x] T010 [P] Create `ClientExclusionRepository` in `backend/app/modules/clients/repository.py`
  - `create_exclusion(data: dict) -> ClientQuarterExclusion`
  - `get_active_exclusion(client_id: UUID, quarter: int, fy_year: str) -> ClientQuarterExclusion | None`
  - `reverse_exclusion(exclusion_id: UUID, reversed_by: UUID) -> ClientQuarterExclusion`
  - `list_exclusions_for_quarter(tenant_id: UUID, quarter: int, fy_year: str) -> list[ClientQuarterExclusion]`
  - `get_excluded_client_ids(tenant_id: UUID, quarter: int, fy_year: str) -> set[UUID]`

- [x] T011 [P] Create `ClientNoteHistoryRepository` in `backend/app/modules/clients/repository.py`
  - `create_history_entry(client_id: UUID, tenant_id: UUID, note_text: str, edited_by: UUID)`
  - `get_history(client_id: UUID, tenant_id: UUID) -> list[ClientNoteHistory]` — ordered by edited_at DESC

- [x] T012 Refactor `DashboardRepository.list_connections_with_financials` in `backend/app/modules/dashboard/repository.py`
  - Change driving table from `xero_connections` to `practice_clients`
  - LEFT JOIN `xero_connections` ON `practice_clients.xero_connection_id = xero_connections.id`
  - Invoice/transaction subqueries join on `xero_connections.id` (only when connection exists)
  - Add unreconciled transaction count subquery: COUNT `xero_bank_transactions` WHERE `is_reconciled = false` AND `transaction_date` between quarter bounds, grouped by `connection_id`
  - Add new query params: `assigned_user_id` (UUID | None), `show_excluded` (bool), `software` (str | None)
  - LEFT JOIN `client_quarter_exclusions` for the selected quarter (WHERE reversed_at IS NULL)
  - Default filter: WHERE exclusion IS NULL (active clients only)
  - When `show_excluded=true`: WHERE exclusion IS NOT NULL
  - When `assigned_user_id` provided: WHERE `practice_clients.assigned_user_id = ?`
  - Return new fields per row: `assigned_user_id`, `assigned_user_name` (join practice_users), `accounting_software`, `has_xero_connection`, `notes` (first 100 chars as preview), `unreconciled_count`, `exclusion` (if showing excluded), `manual_status`
  - Update BAS status derivation: add check — if `unreconciled_count > 5` AND would be READY, set to NEEDS_REVIEW
  - For non-Xero clients (xero_connection_id IS NULL): use `manual_status` as display status instead of auto-derived

- [x] T013 Refactor `DashboardRepository.get_status_counts` in `backend/app/modules/dashboard/repository.py`
  - Rewrite to use SQL COUNT/GROUP BY instead of fetching 1000 rows
  - Query from `practice_clients` LEFT JOIN xero_connections, LEFT JOIN exclusions
  - Exclude excluded clients from counts
  - Include `assigned_user_id` filter param
  - Return `excluded_count` as additional field

- [x] T014 Refactor `DashboardRepository.get_aggregated_summary` in `backend/app/modules/dashboard/repository.py`
  - Query from `practice_clients` instead of `xero_connections`
  - Exclude excluded clients from aggregates
  - Add `excluded_count` to response
  - Add `team_members` breakdown: list of {id, name, client_count} grouped by assigned_user_id
  - Include `assigned_user_id` filter param

- [x] T015 Update `DashboardSummaryResponse` schema in `backend/app/modules/dashboard/schemas.py`
  - Add `excluded_count: int`
  - Add `team_members: list[TeamMemberSummary]` where TeamMemberSummary = {id: UUID | None, name: str, client_count: int}

- [x] T016 Update `ClientPortfolioItem` schema in `backend/app/modules/dashboard/schemas.py`
  - Add `assigned_user_id: UUID | None`
  - Add `assigned_user_name: str | None`
  - Add `accounting_software: str`
  - Add `has_xero_connection: bool`
  - Add `notes_preview: str | None` (first 100 chars of notes)
  - Add `unreconciled_count: int`
  - Add `exclusion: ClientExclusionBrief | None`
  - Add `manual_status: str | None`

- [x] T017 Update `DashboardService.get_client_portfolio` in `backend/app/modules/dashboard/service.py`
  - Pass through new filter params: `assigned_user_id`, `show_excluded`, `software`
  - Map new fields from repository results to updated `ClientPortfolioItem` schema

- [x] T018 Update `DashboardService.get_summary` in `backend/app/modules/dashboard/service.py`
  - Pass through `assigned_user_id` filter
  - Map new fields (excluded_count, team_members) to updated `DashboardSummaryResponse`

- [x] T019 Update dashboard router query params in `backend/app/modules/dashboard/router.py`
  - `GET /dashboard/summary`: add `assigned_user_id: UUID | None = None` query param
  - `GET /dashboard/clients`: add `assigned_user_id: UUID | None = None`, `show_excluded: bool = False`, `software: str | None = None` query params

- [x] T020 Run backend validation
  - Run: `cd backend && uv run ruff check . && uv run pytest -x`
  - Ensure all existing tests pass with refactored dashboard queries
  - Fix any type errors or missing fields

**Checkpoint**: Foundation ready — all models exist, migration applied, dashboard queries refactored. User story work can now begin.

---

## Phase 3: User Story 1 — Team Assignment (Priority: P1) MVP

**Goal**: Accountants can assign clients to team members and filter the dashboard by "My Clients"

**Independent Test**: Assign team members to clients via API, verify dashboard shows assignee column and "My Clients" filter works

### Implementation

- [x] T021 [US1] Create `PracticeClientService` with assignment methods in `backend/app/modules/clients/service.py`
  - `assign_client(client_id, assigned_user_id, current_user) -> PracticeClientResponse` — validate user exists in tenant, call repository, emit `client.assigned` audit event
  - `bulk_assign_clients(client_ids, assigned_user_id, current_user) -> BulkAssignResponse` — validate all clients belong to tenant, call repository, emit audit events per client
  - Import `PracticeClientRepository` — never import models directly from other modules

- [x] T022 [US1] Add assignment endpoints to `backend/app/modules/clients/router.py`
  - `PATCH /clients/{client_id}/assign` — single client assignment
  - `POST /clients/bulk-assign` — bulk assignment (1-100 client_ids)
  - Both require Permission.INTEGRATION_WRITE
  - Raise domain exceptions in service, convert to HTTPException in router

- [ ] T023 [US1] Fix bulk import to propagate assigned_user_id in `backend/app/modules/integrations/xero/bulk_import_service.py`
  - In `confirm_bulk_import()` after XeroConnection creation (around line 463): also create PracticeClient record with `xero_connection_id` set and `assigned_user_id` from the org selection
  - In `_run_bulk_import_async` Celery task: verify PracticeClient exists after sync completion
  - For any new XeroConnection created outside bulk import: add a hook/signal to create a corresponding PracticeClient

- [x] T024 [US1] Add team member filter to dashboard in `frontend/src/app/(protected)/dashboard/page.tsx`
  - Add state: `selectedAssignee: string | null` (UUID or 'me' or null for all)
  - Fetch team members via `listTenantUsers()` on mount
  - Render a dropdown/select above the status filter tabs: "All Clients", "My Clients", team member names
  - Default to "My Clients" for non-admin roles (check user role from Clerk)
  - Pass `assigned_user_id` param to `fetchClients` and `fetchSummary` API calls

- [x] T025 [US1] Add "Assigned To" column to dashboard client table in `frontend/src/app/(protected)/dashboard/page.tsx`
  - Add column between "Client" and "Net GST" columns
  - Display `assigned_user_name` or "Unassigned" badge
  - Make it an inline dropdown (shadcn Select) that triggers PATCH /clients/{id}/assign on change
  - Hidden below `md` breakpoint for responsive design

- [ ] T026 [US1] Add bulk selection and assignment to dashboard in `frontend/src/app/(protected)/dashboard/page.tsx`
  - Add checkboxes to each row + "select all" header checkbox
  - When 1+ rows selected, show a floating action bar with: "Assign to [dropdown]" button
  - On confirm: call POST /clients/bulk-assign, then refresh client list
  - Clear selection after successful assignment

- [x] T027 [US1] Add "Unassigned" filter option to status tabs in `frontend/src/app/(protected)/dashboard/page.tsx`
  - Extend team member dropdown with an "Unassigned" option that filters to clients where `assigned_user_id` is null

**Checkpoint**: Team assignment is fully functional — clients can be assigned, dashboard shows assignees, "My Clients" filter works, bulk assignment works.

---

## Phase 4: User Story 2 — Client Exclusion per Quarter (Priority: P1)

**Goal**: Accountants can mark clients as "not required" for a specific quarter, hiding them from the active dashboard

**Independent Test**: Exclude a client for a quarter via API, verify it disappears from default dashboard and summary totals

### Implementation

- [x] T028 [US2] Create exclusion service methods in `backend/app/modules/clients/service.py`
  - `exclude_client(client_id, quarter, fy_year, reason, reason_detail, current_user) -> ClientExclusionResponse` — check not already excluded, create exclusion, emit `client.exclusion.created` audit event
  - `reverse_exclusion(exclusion_id, current_user) -> ClientExclusionReversedResponse` — set reversed_at/reversed_by, emit `client.exclusion.reversed` audit event

- [x] T029 [US2] Add exclusion endpoints to `backend/app/modules/clients/router.py`
  - `POST /clients/{client_id}/exclusions` — exclude for quarter
  - `DELETE /clients/{client_id}/exclusions/{exclusion_id}` — reverse exclusion
  - Require Permission.INTEGRATION_WRITE
  - Return 409 if already excluded for that quarter

- [ ] T030 [US2] Add "Excluded" filter tab to dashboard in `frontend/src/app/(protected)/dashboard/page.tsx`
  - Add to `STATUS_TABS`: `{ value: 'excluded', label: 'Excluded' }`
  - When selected, pass `show_excluded=true` to API call
  - Show exclusion reason and who excluded in each row
  - Show count from `summary.excluded_count`

- [ ] T031 [US2] Add exclude/include actions to dashboard client rows in `frontend/src/app/(protected)/dashboard/page.tsx`
  - Add a context menu or action button per row
  - For active clients: "Exclude from this quarter" → opens a small dialog with reason dropdown (dormant, lodged externally, GST cancelled, left practice, other) and optional detail text → calls POST /clients/{id}/exclusions
  - For excluded clients (when viewing excluded tab): "Include in this quarter" button → calls DELETE /clients/{id}/exclusions/{exclusion_id}
  - Refresh client list and summary after action

- [ ] T032 [US2] Verify summary cards exclude excluded clients in `frontend/src/app/(protected)/dashboard/page.tsx`
  - Confirm that `summary.status_counts` and `summary.total_clients` / `summary.active_clients` reflect only non-excluded clients
  - Display `excluded_count` somewhere visible (e.g., a subtle "40 excluded" label near the stat cards)

**Checkpoint**: Client exclusion works — clients can be excluded per quarter, they disappear from the default view, summary totals are accurate, exclusions are reversible.

---

## Phase 5: User Story 3 — Persistent Client Notes (Priority: P2)

**Goal**: Team members see persistent client instructions when opening a BAS session

**Independent Test**: Add a note to a client, open a BAS session for that client in a different quarter, verify the note appears prominently

### Implementation

- [x] T033 [US3] Create notes service methods in `backend/app/modules/clients/service.py`
  - `update_notes(client_id, notes, current_user) -> PracticeClientResponse` — save to client record, create history entry, emit `client.notes.updated` audit event
  - `get_note_history(client_id, current_user) -> list[NoteHistoryEntry]` — ordered by edited_at DESC

- [x] T034 [US3] Add notes endpoints to `backend/app/modules/clients/router.py`
  - `PATCH /clients/{client_id}/notes` — update persistent notes
  - `GET /clients/{client_id}/notes/history` — get note change history

- [ ] T035 [US3] Add notes editor to client detail page in `frontend/src/app/(protected)/clients/[id]/page.tsx`
  - Add a "Client Notes" section — prominent, above the tab content area
  - Show existing notes with "last edited by [name] on [date]" metadata
  - Editable textarea (shadcn Textarea) with save button
  - Save calls PATCH /clients/{id}/notes
  - Collapsible "History" link that expands to show previous versions from GET /clients/{id}/notes/history

- [ ] T036 [US3] Add persistent notes banner to BASTab in `frontend/src/components/bas/BASTab.tsx`
  - Fetch the PracticeClient notes when BASTab mounts (need a new API call or pass from parent)
  - If notes exist: render an info banner at the top of the BAS tab (before the workflow progress bar), styled as a light blue/amber callout with a "Standing Instructions" label
  - Show the full note text, "Last updated by [name] on [date]"
  - Include a subtle "Edit" link that navigates to the client detail page notes section
  - Keep existing `internal_notes` (session-specific) as a separate section lower in the tab — label it "Quarter Notes"

**Checkpoint**: Persistent notes work — notes carry across quarters, displayed prominently in BAS sessions, history is auditable.

---

## Phase 6: User Story 4 — Non-Xero Client Visibility (Priority: P2)

**Goal**: All clients (including QuickBooks, MYOB, email-based) appear in the dashboard

**Independent Test**: Create a non-Xero client via API, verify it appears on the dashboard with appropriate indicators

### Implementation

- [x] T037 [US4] Create manual client service method in `backend/app/modules/clients/service.py`
  - `create_manual_client(data: PracticeClientCreate, current_user) -> PracticeClientResponse` — validate accounting_software is not 'xero' (Xero clients are created via import), create PracticeClient, emit `client.created_manual` audit event

- [x] T038 [US4] Create manual status update method in `backend/app/modules/clients/service.py`
  - `update_manual_status(client_id, status, current_user) -> PracticeClientResponse` — reject if client has xero_connection_id (auto-derived status), update manual_status field

- [x] T039 [US4] Add manual client endpoints to `backend/app/modules/clients/router.py`
  - `POST /clients/manual` — create non-Xero client
  - `PATCH /clients/{client_id}/manual-status` — update BAS status for non-Xero clients

- [ ] T040 [US4] Add "Add Client" button and form to dashboard in `frontend/src/app/(protected)/dashboard/page.tsx`
  - Add a "+" or "Add Client" button near the page header
  - Opens a shadcn Dialog/Sheet with form fields: name (required), ABN (optional, 11-digit validation), accounting software dropdown (QuickBooks, MYOB, email-based, other), team member assignment dropdown (optional), notes (optional textarea)
  - On submit: call POST /clients/manual, then refresh client list
  - Show success toast on creation

- [ ] T041 [US4] Add accounting software indicators to dashboard table in `frontend/src/app/(protected)/dashboard/page.tsx`
  - For non-Xero clients: show a small badge/icon indicating software type (e.g., "QB", "MYOB", "Email") next to the client name
  - For Xero clients: show connected icon (already implied by existing behavior)
  - For non-Xero clients: show `manual_status` in the status column instead of auto-derived BAS status
  - Add a "Software" filter option or integrate with existing filters

- [ ] T042 [US4] Add manual status progression to non-Xero client detail in `frontend/src/app/(protected)/clients/[id]/page.tsx`
  - When viewing a non-Xero client (no xero_connection_id), show a simplified status progression UI
  - Status steps: Not Started → In Progress → Completed → Lodged
  - Each step clickable to advance/set status via PATCH /clients/{id}/manual-status
  - Hide Xero-specific tabs (BAS calculations, sync, etc.) for non-Xero clients

**Checkpoint**: Non-Xero clients visible — manual clients can be created, appear on dashboard, have appropriate status indicators.

---

## Phase 7: User Story 5 — Smarter Readiness Signals (Priority: P2)

**Goal**: Dashboard accurately reflects readiness by considering unreconciled transactions

**Independent Test**: Verify a client with >5 unreconciled transactions shows as "Needs Review" not "Ready"

### Implementation

- [x] T043 [US5] Verify unreconciled count is included in dashboard query (already done in T012)
  - Confirm `unreconciled_count` is returned in `ClientPortfolioItem` response
  - Confirm BAS status derivation checks: if `unreconciled_count > 5` AND status would be READY → set to NEEDS_REVIEW
  - Write a unit test: given a client with invoices + transactions + fresh sync + 10 unreconciled → status is NEEDS_REVIEW
  - Write a unit test: given a client with invoices + transactions + fresh sync + 3 unreconciled → status is READY

- [ ] T044 [US5] Add unreconciled count column to dashboard table in `frontend/src/app/(protected)/dashboard/page.tsx`
  - Add "Unrec." column between "Quality" and "Status" columns
  - Show count as a number; highlight in amber/red when >5
  - Hidden below `lg` breakpoint

- [ ] T045 [US5] Add unreconciled attention cards in `frontend/src/components/insights/InsightsWidget.tsx`
  - When dashboard data includes clients with high unreconciled counts (>5), surface them as attention items
  - Format: "[Client Name] has [N] unreconciled transactions"
  - Link to client detail page

**Checkpoint**: Readiness signals improved — unreconciled count visible, clients with many unreconciled transactions flagged correctly.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T046 [P] Emit audit events for all mutation endpoints in `backend/app/modules/clients/service.py`
  - Verify all 6 audit event types from spec are emitted: client.assigned, client.exclusion.created, client.exclusion.reversed, client.notes.updated, client.created_manual, client.merged
  - Use `audit_event()` from `app.core.audit` with full context (old_values, new_values)

- [ ] T047 [P] Handle team member removal edge case in `backend/app/modules/auth/service.py`
  - When a PracticeUser is deactivated/removed: update all `practice_clients` with that `assigned_user_id` to NULL (SET NULL FK handles this at DB level, but add notification logic)
  - Notify practice admins of orphaned client assignments

- [ ] T048 [P] Ensure new XeroConnections auto-create PracticeClient records
  - In the Xero OAuth callback (where new XeroConnection is created outside bulk import): also create a corresponding PracticeClient with `accounting_software = 'xero'`
  - Check: `backend/app/modules/integrations/xero/service.py` or relevant OAuth handler

- [ ] T049 Run full validation
  - Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest -x`
  - Run: `cd frontend && npm run lint && npx tsc --noEmit`
  - Start dev server: `cd frontend && npm run dev` — manually test dashboard with new features
  - Verify: 280 clients load in <2s, team filter responds in <500ms

---

## Phase FINAL: PR & Merge

- [ ] T050 Ensure all tests pass
  - Run: `cd backend && uv run pytest -x`
  - Run: `cd frontend && npx tsc --noEmit && npm run lint`

- [ ] T051 Push feature branch and create PR
  - Run: `git push -u origin 058-bas-workflow-tracker`
  - Run: `gh pr create --title "Spec 058: BAS Workflow Tracker — Practice Management Layer" --body "..."`
  - Include summary: 3 new tables, 9 API endpoints, dashboard refactored for unified client view

- [ ] T052 Address review feedback (if any)

- [ ] T053 Merge PR to main
  - Squash merge after approval
  - Delete feature branch after merge

- [ ] T054 Update ROADMAP.md
  - Mark spec 058 as COMPLETE
  - Update current focus to next spec

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 0 (Git Setup)**: Already done
- **Phase 1 (Setup)**: Models + migrations — BLOCKS everything
- **Phase 2 (Foundational)**: Repository + dashboard refactor — BLOCKS all user stories
- **Phase 3-7 (User Stories)**: All depend on Phase 2 completion
- **Phase 8 (Polish)**: Depends on all desired user stories
- **Phase FINAL (PR)**: Depends on Phase 8

### User Story Dependencies

- **US1 (Team Assignment)**: Can start after Phase 2 — no dependency on other stories
- **US2 (Client Exclusion)**: Can start after Phase 2 — no dependency on other stories
- **US3 (Persistent Notes)**: Can start after Phase 2 — no dependency on other stories
- **US4 (Non-Xero Visibility)**: Can start after Phase 2 — no dependency on other stories
- **US5 (Readiness Signals)**: Backend work done in Phase 2 (T012) — frontend can start after Phase 2

### Within Each User Story

- Backend service before router endpoints
- Router endpoints before frontend API integration
- Core functionality before polish

### Parallel Opportunities

- T001, T002, T003, T004 can all run in parallel (different model files)
- T007, T008 can run in parallel (different schema sections)
- T009, T010, T011 can run in parallel (different repository classes)
- After Phase 2: US1 through US5 can all proceed in parallel (different files)
- T046, T047, T048 can run in parallel (polish tasks)

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup (T001-T006)
2. Complete Phase 2: Foundational (T007-T020)
3. Complete Phase 3: US1 — Team Assignment (T021-T027)
4. Complete Phase 4: US2 — Client Exclusion (T028-T032)
5. **STOP and VALIDATE**: Test assignment + exclusion independently
6. This covers the two P1 stories and delivers the core "replace the Excel" value

### Full Delivery

7. Phase 5: US3 — Persistent Notes (T033-T036)
8. Phase 6: US4 — Non-Xero Visibility (T037-T042)
9. Phase 7: US5 — Readiness Signals (T043-T045)
10. Phase 8: Polish (T046-T049)
11. Phase FINAL: PR & Merge (T050-T054)

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Commit after each task or logical group
- The dashboard refactor (T012-T014) is the highest-risk task — test thoroughly
- Total: 55 tasks (T000-T054)
