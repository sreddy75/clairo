# Tasks: Bulk Client Import via Multi-Org Xero OAuth

**Input**: Design documents from `/specs/035-bulk-client-import/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/api.yaml

**Tests**: Tests are included as specified in the feature specification (unit, integration, and contract tests).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Phase 0: Git Setup (REQUIRED)

**Purpose**: Create feature branch before any implementation

- [x] T000 Create feature branch from main
  - Run: `git checkout main && git pull origin main`
  - Run: `git checkout -b feature/035-bulk-client-import`
  - Verify: You are now on the feature branch
  - _This ensures all work is isolated and can be reviewed via PR_

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Database models, migrations, and shared schemas needed by all user stories

- [x] T001 Add `is_bulk_import` column to XeroOAuthState model in `backend/app/modules/integrations/xero/models.py`
  - Add `is_bulk_import = Column(Boolean, default=False, server_default="false", nullable=False)` to the `XeroOAuthState` class
  - This column distinguishes bulk import flows from single-org flows in the OAuth state

- [x] T002 Create BulkImportOrganization model in `backend/app/modules/onboarding/models.py`
  - Add the `BulkImportOrganization` SQLAlchemy model with all fields from data-model.md:
    - `id` (UUID PK), `tenant_id` (FK tenants.id), `bulk_import_job_id` (FK bulk_import_jobs.id)
    - `xero_tenant_id` (String 50), `organization_name` (String 255), `status` (String 20, default "pending")
    - `connection_id` (FK xero_connections.id, nullable), `connection_type` (String 20, default "client")
    - `assigned_user_id` (FK practice_users.id, nullable), `already_connected` (Boolean, default False)
    - `selected_for_import` (Boolean, default True), `match_status` (String 20, nullable)
    - `matched_client_name` (String 255, nullable), `error_message` (Text, nullable)
    - `sync_started_at` (DateTime tz, nullable), `sync_completed_at` (DateTime tz, nullable)
    - `created_at`, `updated_at` (DateTime tz)
  - Add indexes: `ix_bulk_import_orgs_job`, `ix_bulk_import_orgs_tenant`, `ix_bulk_import_orgs_xero_tenant`
  - Add relationship: `bulk_import_job` → BulkImportJob, `connection` → XeroConnection

- [x] T003 Create Alembic migration for bulk import schema changes in `backend/app/alembic/versions/`
  - Generate migration: `uv run alembic revision --autogenerate -m "add_bulk_import_organizations"`
  - Migration must:
    - Add `is_bulk_import` column to `xero_oauth_states` table (Boolean, default False)
    - Create `bulk_import_organizations` table with all columns and indexes
  - Verify: `uv run alembic upgrade head` runs without errors

- [x] T004 Create BulkImportOrganizationRepository in `backend/app/modules/onboarding/repository.py`
  - Follow existing repository pattern in the codebase
  - Methods:
    - `create(data: dict) -> BulkImportOrganization`
    - `get_by_job_id(job_id: UUID) -> list[BulkImportOrganization]`
    - `get_by_id(id: UUID) -> BulkImportOrganization | None`
    - `update_status(id: UUID, status: str, **kwargs) -> BulkImportOrganization`
    - `bulk_create(items: list[dict]) -> list[BulkImportOrganization]`
    - `get_failed_by_job_id(job_id: UUID) -> list[BulkImportOrganization]`
  - All queries must include `tenant_id` filter for RLS

- [x] T005 [P] Create bulk import Pydantic schemas in `backend/app/modules/integrations/xero/schemas.py`
  - Add schemas matching contracts/api.yaml:
    - `BulkImportInitiateRequest` (redirect_uri: str)
    - `BulkImportInitiateResponse` (auth_url: str, state: str)
    - `ImportOrganization` (xero_tenant_id, organization_name, already_connected, existing_connection_id, match_status, matched_client_name)
    - `BulkImportCallbackResponse` (auth_event_id, organizations list, already_connected_count, new_count, plan_limit, current_client_count, available_slots)
    - `ImportOrgSelection` (xero_tenant_id, selected, connection_type, assigned_user_id)
    - `BulkImportConfirmRequest` (auth_event_id, organizations list)
    - `BulkImportJobResponse` (job_id, status, total_organizations, imported_count, failed_count, skipped_count, progress_percent, created_at)
    - `BulkImportJobDetailResponse` (extends BulkImportJobResponse + organizations list, started_at, completed_at)
    - `BulkImportOrgStatus` (xero_tenant_id, organization_name, status, connection_id, connection_type, assigned_user_id, error_message, sync_started_at, sync_completed_at)
    - `BulkImportJobListResponse` (jobs list, total, limit, offset)

**Checkpoint**: Database schema ready, models and schemas in place. User story implementation can begin.

---

## Phase 2: User Story 1 - Bulk Connect Xero Client Organizations (Priority: P1) - MVP

**Goal**: Enable an accountant to authorize multiple Xero organizations in a single OAuth flow and create connections for all of them.

**Independent Test**: Accountant clicks "Import Clients from Xero", completes Xero OAuth selecting multiple orgs, all selected orgs appear as new connections.

**Implements**: FR-001, FR-002, FR-003, FR-006, FR-007, FR-012, FR-013, FR-017, FR-018

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T006 [P] [US1] Unit test for BulkImportService.handle_bulk_callback() in `backend/tests/unit/modules/integrations/xero/test_bulk_import_service.py`
  - Test: Processes all authorized organizations from Xero connections response
  - Test: Identifies new vs already-connected organizations using auth_event_id
  - Test: Returns correct counts (new_count, already_connected_count)
  - Test: Respects uncertified app limit (25 orgs)
  - Test: Returns plan limit and available slots

- [x] T007 [P] [US1] Unit test for BulkImportService.confirm_bulk_import() in `backend/tests/unit/modules/integrations/xero/test_bulk_import_service.py`
  - Test: Creates XeroConnection records for selected orgs with shared tokens
  - Test: Creates BulkImportJob with source_type="xero_bulk_oauth"
  - Test: Creates BulkImportOrganization records for each org
  - Test: Skips already-connected orgs
  - Test: Enforces subscription tier client limit (rejects if exceeds)
  - Test: Prevents concurrent bulk imports for same tenant (409 conflict)

- [x] T008 [P] [US1] Integration test for bulk import endpoints in `backend/tests/integration/api/test_bulk_import.py`
  - Test: POST /bulk-import/initiate returns auth_url and state with is_bulk_import=true
  - Test: GET /bulk-import/callback processes code+state, returns org list
  - Test: POST /bulk-import/confirm creates connections and returns job
  - Test: 409 when bulk import already in progress
  - Test: 400 when selection exceeds plan limit
  - Test: **Backward compatibility (FR-013)** — existing single-org OAuth flow (POST /connect, GET /callback without is_bulk_import) still works unchanged after bulk import code is added

### Implementation for User Story 1

- [x] T009 [US1] Implement BulkImportService.initiate_bulk_import() in `backend/app/modules/integrations/xero/service.py`
  - Create a new `BulkImportService` class (or add methods to existing service)
  - `initiate_bulk_import(tenant_id, user_id, redirect_uri)`:
    - Check no existing in-progress bulk import for tenant (FR-017)
    - Create XeroOAuthState with `is_bulk_import=True`
    - Generate Xero OAuth authorization URL (same as existing flow)
    - Return auth_url and state token
  - Audit event: `integration.xero.bulk_import.start`

- [x] T010 [US1] Implement BulkImportService.handle_bulk_callback() in `backend/app/modules/integrations/xero/service.py`
  - `handle_bulk_callback(code, state)`:
    - Validate state token, verify `is_bulk_import=True`
    - Exchange code for access/refresh tokens (existing pattern)
    - Call Xero GET /connections to fetch all authorized orgs
    - Filter to orgs from current auth_event_id (FR-002)
    - Cross-reference with existing XeroConnections for tenant (FR-012)
    - Check subscription tier limit via BillingService (FR-006)
    - Check uncertified app limit of 25 (FR-007)
    - Return BulkImportCallbackResponse with org list, counts, limits
  - Audit event: `integration.xero.oauth.multi_org`
  - Depends on: T009

- [x] T011 [US1] Implement BulkImportService.confirm_bulk_import() in `backend/app/modules/integrations/xero/service.py`
  - `confirm_bulk_import(tenant_id, user_id, auth_event_id, organizations)`:
    - Validate selected org count against available plan slots
    - For each selected org: create XeroConnection with shared encrypted tokens, auth_event_id
    - Create BulkImportJob (source_type="xero_bulk_oauth")
    - Create BulkImportOrganization records via `BulkImportOrganizationRepository.bulk_create()` (T004) — do NOT import the onboarding model directly; access through the repository to respect module boundaries (Constitution Section I)
    - Mark already-connected orgs as "skipped" with already_connected=true
    - Mark deselected orgs as "skipped" with selected_for_import=false
    - Queue Celery task for bulk sync (T020)
    - Return BulkImportJobResponse
  - Audit events: `integration.xero.connection.created` (per org)
  - Depends on: T010

- [x] T012 [US1] Add bulk import router endpoints in `backend/app/modules/integrations/xero/router.py`
  - POST `/api/v1/integrations/xero/bulk-import/initiate` → calls initiate_bulk_import()
  - GET `/api/v1/integrations/xero/bulk-import/callback` → calls handle_bulk_callback()
  - POST `/api/v1/integrations/xero/bulk-import/confirm` → calls confirm_bulk_import()
  - All endpoints require Clerk auth (existing pattern)
  - HTTPException mapping for domain exceptions (409 for concurrent import, 400 for validation)
  - Depends on: T009, T010, T011

- [x] T013 [P] [US1] Create frontend API client for bulk import in `frontend/src/lib/api/bulk-import.ts`
  - Functions:
    - `initiateBulkImport(redirectUri: string): Promise<BulkImportInitiateResponse>`
    - `handleBulkCallback(code: string, state: string): Promise<BulkImportCallbackResponse>`
    - `confirmBulkImport(request: BulkImportConfirmRequest): Promise<BulkImportJobResponse>`
    - `getBulkImportStatus(jobId: string): Promise<BulkImportJobDetailResponse>`
    - `retryFailedOrgs(jobId: string): Promise<BulkImportJobResponse>`
    - `listBulkImportJobs(limit?: number, offset?: number): Promise<BulkImportJobListResponse>`
  - Use existing API client pattern (auth headers, error handling)

- [x] T014 [P] [US1] Create TypeScript types for bulk import in `frontend/src/types/bulk-import.ts`
  - Export interfaces matching contracts/api.yaml schemas:
    - `BulkImportInitiateResponse`, `ImportOrganization`, `BulkImportCallbackResponse`
    - `ImportOrgSelection`, `BulkImportConfirmRequest`
    - `BulkImportJobResponse`, `BulkImportJobDetailResponse`, `BulkImportOrgStatus`
    - `BulkImportJobListResponse`

- [x] T015 [US1] Add "Import Clients from Xero" button to `frontend/src/app/(protected)/clients/page.tsx`
  - Add button in the page header area (next to existing actions)
  - On click: call `initiateBulkImport()` with redirect URI, then redirect to Xero OAuth URL
  - Follow existing button/action patterns on the clients page
  - Depends on: T013, T014

**Checkpoint**: User Story 1 complete. Accountant can bulk-authorize orgs via OAuth and create connections. The configuration screen and progress dashboard are not yet built (US2/US3).

---

## Phase 3: User Story 2 - Configure Imported Clients Before Sync (Priority: P2)

**Goal**: Post-OAuth configuration screen where the accountant can select orgs, assign team members, and set connection types before sync begins.

**Independent Test**: After bulk OAuth, the configuration screen shows all orgs with checkboxes, team member dropdowns, and connection type selectors. Submitting triggers import with selected options.

**Implements**: FR-004, FR-005

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T016 [P] [US2] Integration test for configuration screen data flow in `backend/tests/integration/api/test_bulk_import.py`
  - Test: Callback response includes all fields needed for config screen (org name, already_connected, match_status)
  - Test: Confirm request with mixed selected/deselected orgs creates correct records
  - Test: Confirm request with team member assignments persists assigned_user_id

### Implementation for User Story 2

- [x] T017 [US2] Create bulk import configuration page at `frontend/src/app/(protected)/clients/import/page.tsx`
  - Reads `auth_event_id` from URL query params (set by OAuth callback redirect)
  - Calls `handleBulkCallback()` or reads cached callback data
  - Renders table/list of organizations with:
    - Checkbox per org (default: selected, greyed out for already_connected)
    - Organization name
    - Connection type dropdown (practice/client, default: client)
    - Team member assignment dropdown (populated from practice users)
    - "Already Connected" badge for existing connections
  - Shows plan limit warning if applicable (available_slots < new_count)
  - Disables excess checkboxes if plan limit would be exceeded
  - "Import Selected" button submits BulkImportConfirmRequest
  - On success: redirect to `/clients/import/progress/{jobId}`
  - Loading and error states
  - Depends on: T013, T014, T015

**Checkpoint**: User Stories 1 and 2 complete. Full OAuth → Configure → Import flow works end-to-end.

---

## Phase 4: User Story 3 - Monitor Bulk Sync Progress (Priority: P3)

**Goal**: Real-time progress dashboard showing overall completion, per-org status, and retry capability.

**Independent Test**: After confirming import, the progress page shows real-time status updates polling every 2 seconds, with per-org details and retry for failures.

**Implements**: FR-008, FR-009, FR-010, FR-011

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T018 [P] [US3] Unit test for bulk sync orchestrator in `backend/tests/unit/modules/integrations/xero/test_bulk_import_service.py`
  - Test: Orchestrator dispatches syncs with max 10 concurrent
  - Test: Updates BulkImportOrganization status through lifecycle (pending → importing → syncing → completed)
  - Test: Handles sync failure and sets error_message
  - Test: Updates BulkImportJob progress_percent correctly
  - Test: Job status transitions (PENDING → IN_PROGRESS → COMPLETED/PARTIAL_FAILURE/FAILED)

- [x] T019 [P] [US3] Integration test for job status and retry endpoints in `backend/tests/integration/api/test_bulk_import.py`
  - Test: GET /bulk-import/{job_id} returns per-org details with status
  - Test: POST /bulk-import/{job_id}/retry re-queues failed orgs
  - Test: GET /bulk-import/jobs returns paginated list
  - Test: 404 for non-existent job_id
  - Test: 400 when no failed orgs to retry

### Implementation for User Story 3

- [x] T020 [US3] Implement run_bulk_xero_import Celery task in `backend/app/tasks/xero.py`
  - New task `run_bulk_xero_import(job_id: UUID)`:
    - Fetch BulkImportJob and associated BulkImportOrganization records
    - Update job status to IN_PROGRESS
    - For each org with status "pending" + selected_for_import=True:
      - Update org status to "importing" → create connection if needed → "syncing"
      - Dispatch existing `run_sync` task for the connection
      - Limit to max 10 concurrent syncs (use semaphore or queue)
      - Check Redis app-wide rate limit counter before dispatching
      - On sync complete: update org status to "completed", increment job.imported_count
      - On sync fail: update org status to "failed", set error_message, increment job.failed_count
    - After all orgs processed: update job status (COMPLETED / PARTIAL_FAILURE / FAILED)
    - Update job.progress_percent after each org completes
  - Audit events: `integration.xero.bulk_sync.start`, `integration.xero.bulk_sync.fail`

- [x] T021 [US3] Implement Redis-based app-wide rate limit counter in `backend/app/modules/integrations/xero/service.py`
  - Add to BulkImportService (or rate limiter module):
    - `check_app_rate_limit() -> bool`: Read Redis counter for current minute window
    - `update_app_rate_limit(remaining: int)`: Update counter from Xero `X-AppMinLimit-Remaining` header
  - Redis key: `xero:app_rate_limit:{minute_window}` with 60s TTL
  - Threshold: pause dispatch when remaining < 500 (of 10,000/min)
  - Depends on: T020

- [x] T022 [US3] Add job status and retry endpoints in `backend/app/modules/integrations/xero/router.py`
  - GET `/api/v1/integrations/xero/bulk-import/{job_id}` → returns BulkImportJobDetailResponse
  - POST `/api/v1/integrations/xero/bulk-import/{job_id}/retry` → re-queues failed orgs
  - GET `/api/v1/integrations/xero/bulk-import/jobs` → returns paginated list
  - Service methods:
    - `get_bulk_import_status(job_id, tenant_id)` → fetches job + org records
    - `retry_failed_orgs(job_id, tenant_id)` → resets failed orgs to pending, re-dispatches task
    - `list_bulk_import_jobs(tenant_id, limit, offset)` → paginated query
  - Depends on: T020

- [x] T023 [US3] Create bulk import progress page at `frontend/src/app/(protected)/clients/import/progress/[jobId]/page.tsx`
  - Read `jobId` from URL params
  - Poll `getBulkImportStatus(jobId)` every 2 seconds using TanStack Query refetchInterval
  - Display:
    - Overall progress bar with "X of Y complete" text
    - Per-organization table with: name, status badge (pending/syncing/completed/failed), error message (expandable), sync timestamps
    - Estimated time remaining (based on average sync duration of completed orgs)
    - "Retry Failed" button (visible when failed_count > 0)
    - "View Clients" link when job is completed
  - Stop polling when job status is COMPLETED, PARTIAL_FAILURE, or FAILED
  - Depends on: T013, T014

**Checkpoint**: User Stories 1, 2, and 3 complete. Full end-to-end flow: OAuth → Configure → Import → Monitor Progress.

---

## Phase 5: User Story 4 - Auto-Match Imported Orgs to Existing Clients (Priority: P4)

**Goal**: Automatically match imported Xero organizations to existing client records by name, reducing manual linking effort.

**Independent Test**: Import orgs that match existing client names → matched orgs show "Matched" label on configuration screen and link automatically.

**Implements**: FR-014, FR-015

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T024 [P] [US4] Unit test for auto-matching logic in `backend/tests/unit/modules/integrations/xero/test_bulk_import_service.py`
  - Test: Exact name match (case-insensitive, normalized) returns "matched"
  - Test: Fuzzy match with Jaccard similarity > 0.8 returns "suggested"
  - Test: No match returns "unmatched"
  - Test: Normalization strips "Pty Ltd", "Pty", "Ltd", leading/trailing whitespace
  - Test: Multiple orgs with matches are all identified correctly

### Implementation for User Story 4

- [x] T025 [US4] Implement auto-matching service in `backend/app/modules/integrations/xero/service.py`
  - Add to BulkImportService:
    - `match_orgs_to_clients(tenant_id, organizations) -> list[ImportOrganization]`:
      - Fetch existing client records for tenant
      - For each org, run two-pass matching (research decision R6):
        1. **Exact match**: Normalize both names (lowercase, strip "pty ltd", "pty", "ltd", whitespace) and compare
        2. **Fuzzy match**: Jaccard similarity on word tokens with threshold 0.8
      - Set `match_status` to "matched", "suggested", or "unmatched"
      - Set `matched_client_name` for matched/suggested results
  - Called during `handle_bulk_callback()` to populate match info on the callback response
  - Depends on: T010

- [x] T026 [US4] Update configuration screen with match indicators in `frontend/src/app/(protected)/clients/import/page.tsx`
  - Show match status badges per org:
    - "Matched" (green) — auto-linked, accountant can override
    - "Suggested Match: [client name]" (yellow) — accountant confirms or rejects
    - "Unmatched" (grey) — no existing client found
  - For "suggested" matches: show confirm/reject inline controls
  - For "unmatched" orgs: show dropdown to manually link to existing client (optional)
  - Depends on: T017, T025

**Checkpoint**: All 4 user stories complete. Full feature is functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T027 [P] Add audit logging for all 6 audit events defined in spec
  - Verify all events are emitted in service methods:
    - `integration.xero.bulk_import.start` (T009)
    - `integration.xero.oauth.multi_org` (T010)
    - `integration.xero.connection.created` (T011)
    - `integration.xero.bulk_import.complete` (T020)
    - `integration.xero.bulk_sync.start` (T020)
    - `integration.xero.bulk_sync.fail` (T020)
  - Ensure all events include required data per spec audit table
  - **Verify FR-016 job metadata completeness**: Confirm BulkImportJob records capture all required metadata fields — initiating user ID, creation timestamp, total org count, imported/failed/skipped counts, and per-organization results (imported_clients and failed_clients JSONB arrays). Add a unit test asserting all metadata fields are populated after a completed bulk import

- [x] T028 [P] Contract test for Xero bulk connections API in `backend/tests/contract/adapters/test_xero_bulk_connections.py`
  - Test: GET /connections response shape (tenantId, tenantName, authEventId)
  - Test: Token exchange response with access_token and refresh_token
  - Test: X-AppMinLimit-Remaining header present in responses
  - Use VCR cassettes or mock fixtures matching real Xero API responses

- [x] T029 [P] Error handling and edge cases
  - Handle 0 organizations returned from Xero (show helpful message)
  - Handle cancelled OAuth flow (graceful redirect)
  - Handle token expiry during bulk sync (auto-refresh)
  - Handle concurrent import guard (409 response with clear message)
  - Handle same-name organizations (display Xero tenant ID for disambiguation)

- [x] T030 Run quickstart.md validation
  - Follow all steps in `specs/035-bulk-client-import/quickstart.md`
  - Verify the 5 test scenarios in the quickstart work as expected

---

## Phase FINAL: PR & Merge (REQUIRED)

**Purpose**: Create pull request and merge to main

- [x] TFINAL-1 Ensure all tests pass
  - Run: `cd backend && uv run pytest tests/unit/modules/integrations/xero/test_bulk_import_service.py tests/integration/api/test_bulk_import.py tests/contract/adapters/test_xero_bulk_connections.py -v`
  - All tests must pass before PR

- [x] TFINAL-2 Run linting and type checking
  - Run: `cd backend && uv run ruff check .`
  - Run: `cd frontend && npm run lint`
  - Fix any issues

- [ ] TFINAL-3 Push feature branch and create PR
  - Run: `git push -u origin feature/035-bulk-client-import`
  - Run: `gh pr create --title "Spec 035: Bulk Client Import via Multi-Org Xero OAuth" --body "..."`
  - PR description should include:
    - Summary of changes (6 new API endpoints, new BulkImportOrganization table, 3 new frontend pages)
    - Link to spec: `specs/035-bulk-client-import/spec.md`
    - Test coverage summary
    - Manual testing steps from quickstart.md

- [ ] TFINAL-4 Address review feedback (if any)
  - Make requested changes
  - Push additional commits

- [ ] TFINAL-5 Merge PR to main
  - Squash merge after approval
  - Delete feature branch after merge

- [ ] TFINAL-6 Update ROADMAP.md
  - Mark spec 035 as COMPLETE
  - Update current focus to next spec

---

## Dependencies & Execution Order

### Phase Dependencies

- **Git Setup (Phase 0)**: MUST be done first — creates feature branch
- **Setup (Phase 1)**: Depends on Phase 0 — models, migrations, schemas, repository
- **User Story 1 (Phase 2)**: Depends on Phase 1 — core OAuth flow + connections
- **User Story 2 (Phase 3)**: Depends on Phase 2 (T013, T014, T015) — configuration screen
- **User Story 3 (Phase 4)**: Depends on Phase 2 (T011 for confirm flow) — progress + sync orchestration
- **User Story 4 (Phase 5)**: Depends on Phase 2 (T010 for callback) + Phase 3 (T017 for config screen)
- **Polish (Phase 6)**: Can start after Phase 2, finish after all stories
- **PR & Merge (Phase FINAL)**: After all desired phases complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 1 — No dependencies on other stories
- **User Story 2 (P2)**: Depends on US1 backend (callback + confirm endpoints) — Adds configuration UI
- **User Story 3 (P3)**: Depends on US1 backend (confirm endpoint) — Adds sync orchestration + progress UI
- **User Story 4 (P4)**: Depends on US1 backend (callback) + US2 frontend (config screen) — Adds matching logic + UI indicators

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services
- Services before endpoints/routes
- Backend before frontend (frontend depends on API)
- Core implementation before integration

### Parallel Opportunities

- T005 (schemas) can run in parallel with T001 (model change) and T002 (new model)
- T006, T007, T008 (US1 tests) can all run in parallel
- T013, T014 (frontend API client + types) can run in parallel with backend US1 work
- T018, T019 (US3 tests) can run in parallel
- T024 (US4 tests) can run in parallel with US3 implementation
- T027, T028, T029 (polish tasks) can all run in parallel

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (models, migration, schemas, repository)
2. Complete Phase 2: US1 (bulk OAuth + connection creation)
3. **STOP and VALIDATE**: Test bulk OAuth flow end-to-end
4. Accountants can bulk-connect orgs, even without config screen or progress dashboard

### Incremental Delivery

1. Phase 1 (Setup) → Foundation ready
2. Phase 2 (US1: Bulk Connect) → MVP: bulk OAuth works → Deploy/Demo
3. Phase 3 (US2: Config Screen) → Better UX: select/configure before import → Deploy/Demo
4. Phase 4 (US3: Progress Dashboard) → Visibility: real-time sync monitoring → Deploy/Demo
5. Phase 5 (US4: Auto-Match) → Optimization: reduces manual linking work → Deploy/Demo
6. Each story adds value without breaking previous stories

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- The existing single-org OAuth flow (FR-013) must remain untouched throughout
