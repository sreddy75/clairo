# Tasks: Progressive Xero Data Sync

**Input**: Design documents from `/specs/043-progressive-xero-sync/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.yaml, quickstart.md

**Tests**: Not explicitly requested — test tasks omitted. Add test phases per user story if TDD approach is desired.

**Organization**: Tasks grouped by user story. US1+US2 combined as MVP (tightly coupled P1 stories).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US7)
- Exact file paths included in all descriptions

---

## Phase 0: Git Setup (COMPLETE)

Branch `043-progressive-xero-sync` already exists and is checked out. Plan artifacts committed.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Database schema changes, new models, repositories, and schemas needed by all user stories

- [x] T001 Extend XeroSyncJob model with `sync_phase` (Integer, nullable), `parent_job_id` (UUID FK self-referential), `triggered_by` (String(20), default 'user'), and `cancelled_at` (DateTime(tz), nullable) columns in `backend/app/modules/integrations/xero/models.py`

- [x] T002 Add 6 new `last_*_sync_at` DateTime(tz) nullable columns to XeroConnection model — `last_credit_notes_sync_at`, `last_payments_sync_at`, `last_overpayments_sync_at`, `last_prepayments_sync_at`, `last_journals_sync_at`, `last_manual_journals_sync_at` in `backend/app/modules/integrations/xero/models.py`

- [x] T003 Add XeroSyncEntityProgress model (id, tenant_id, job_id FK, entity_type, status enum, records_processed/created/updated/failed, error_message, modified_since, started_at, completed_at, duration_ms, timestamps) with indexes on (job_id), (tenant_id), (job_id, entity_type) UNIQUE in `backend/app/modules/integrations/xero/models.py`

- [x] T004 Add PostSyncTask model (id, tenant_id, job_id FK, connection_id FK, task_type, status enum, sync_phase, started_at, completed_at, error_message, result_summary JSONB, timestamps) with indexes on (job_id), (connection_id, task_type), (tenant_id) in `backend/app/modules/integrations/xero/models.py`

- [x] T005 Add XeroWebhookEvent model (id, tenant_id, connection_id FK, webhook_key UNIQUE, event_type, event_category, resource_id, status enum, batch_id, processed_at, error_message, raw_payload JSONB, created_at) with indexes on (webhook_key) UNIQUE, (connection_id, status), (tenant_id), (batch_id) in `backend/app/modules/integrations/xero/models.py`

- [x] T006 Generate Alembic migration for all schema changes — new tables (xero_sync_entity_progress, post_sync_tasks, xero_webhook_events), new columns on xero_sync_jobs and xero_connections, RLS policies on all new tables in `backend/alembic/versions/`

- [x] T007 Add XeroSyncEntityProgressRepository with methods: create(), bulk_create_for_job(), update_status(), get_by_job_id(), get_by_job_and_entity() in `backend/app/modules/integrations/xero/repository.py`

- [x] T008 [P] Add PostSyncTaskRepository with methods: create(), update_status(), get_by_job_id(), get_by_connection() in `backend/app/modules/integrations/xero/repository.py`

- [x] T009 [P] Add XeroWebhookEventRepository with methods: create(), get_by_webhook_key(), get_pending_by_connection(), mark_processed(), get_pending_batch() in `backend/app/modules/integrations/xero/repository.py`

- [x] T010 Add Pydantic schemas — EntityProgressResponse, SyncStatusResponse (enhanced with phase/entities/post_sync_tasks), PostSyncTaskResponse, MultiClientSyncResponse, MultiClientSyncStatusResponse, SSE event schemas (SyncStartedEvent, EntityProgressEvent, PhaseCompleteEvent, SyncCompleteEvent, SyncFailedEvent, PostSyncProgressEvent) in `backend/app/modules/integrations/xero/schemas.py`

- [x] T011 [P] Create Redis pub/sub publisher and subscriber for sync progress events — SyncProgressPublisher (publish_sync_started, publish_entity_progress, publish_phase_complete, publish_sync_complete, publish_sync_failed, publish_post_sync_progress) and SyncProgressSubscriber (subscribe to channel, async generator yielding SSE-formatted events) in `backend/app/modules/integrations/xero/sync_progress.py`

**Checkpoint**: Schema and infrastructure ready. Run migration: `docker exec clairo-backend alembic upgrade head`

---

## Phase 2: Foundational (Per-Entity Task Architecture)

**Purpose**: Refactor monolithic `run_sync` into per-entity Celery tasks with isolated DB sessions. This is the critical refactoring that ALL user stories depend on.

**CRITICAL**: No user story work can begin until this phase is complete.

- [x] T012 Create generic `sync_entity` Celery task that accepts (job_id, entity_type, connection_id, tenant_id, modified_since, force_full) — creates its own async DB session, sets RLS context, resolves entity_type to the appropriate XeroDataService method, calls it with isolated error handling, updates XeroSyncEntityProgress record (started_at, status, record counts, completed_at, duration_ms), and publishes progress via SyncProgressPublisher in `backend/app/tasks/xero.py`

- [x] T013 Create `run_phased_sync` orchestrator Celery task using Celery chain of chords — Phase 1 chord: group(accounts, contacts, recent_invoices) + on_complete callback; Phase 2 chord: group(bank_transactions, payments, credit_notes, overpayments, prepayments) + on_complete callback; Phase 3 chord: group(journals, manual_journals, purchase_orders, repeating_invoices, tracking_categories, quotes, payroll, assets, org_profile) + on_complete callback. Each phase callback updates XeroSyncJob (sync_phase, status), creates XeroSyncEntityProgress records for next phase entities, and publishes phase_complete event via Redis pub/sub in `backend/app/tasks/xero.py`

- [x] T014 Add job initialization logic to `run_phased_sync` — on start: update job status to in_progress, create XeroSyncEntityProgress records for all Phase 1 entities (status=pending), publish sync_started event. On final completion: aggregate all entity results into job totals (records_processed/created/updated/failed), set job status to completed/failed, publish sync_complete event in `backend/app/tasks/xero.py`

**Checkpoint**: Per-entity tasks execute in parallel within phases. Verify by triggering a sync and checking xero_sync_entity_progress table for per-entity records.

---

## Phase 3: User Story 1 + User Story 2 — Non-Blocking Phased Sync (P1) — MVP

**Goal**: Sync runs in background without blocking the user. Initial sync delivers essential data in <30s, then historical data loads progressively.

**Independent Test**: Trigger a sync for a connected client → user is NOT blocked → toast notification appears → essential data visible within 30s → historical data loads in background → completion notification with summary.

### Backend

- [x] T015 [US1] Add `start_phased_sync()` method to XeroSyncService — creates parent XeroSyncJob, dispatches `run_phased_sync` Celery task. Update `initiate_sync()` to call `start_phased_sync()` instead of dispatching legacy `run_sync` in `backend/app/modules/integrations/xero/service.py`

- [x] T016 [US1] Enhance `POST /api/v1/xero/connections/{id}/sync` endpoint — accept `force_full` parameter, return enhanced SyncJobResponse with sync_phase and triggered_by fields in `backend/app/modules/integrations/xero/router.py`

- [x] T017 [US1] Add `GET /api/v1/xero/connections/{id}/sync/{job_id}/entities` endpoint — return list of EntityProgressResponse for all entity types in the job, queried from XeroSyncEntityProgress table in `backend/app/modules/integrations/xero/router.py`

- [x] T018 [US1] Enhance `GET /api/v1/xero/connections/{id}/sync/status` endpoint — return SyncStatusResponse with current phase, total_phases, per-entity progress list, aggregate record counts, and post_sync_tasks in `backend/app/modules/integrations/xero/router.py`

### Frontend

- [x] T019 [P] [US1] Update API types and functions in `frontend/src/lib/xero-sync.ts` — add SyncJobResponse (with sync_phase, triggered_by), EntityProgressResponse, SyncStatusResponse (with entities array, phase info, post_sync_tasks), add getEntityProgress(token, connectionId, jobId) and enhanced getSyncStatus() functions

- [x] T020 [P] [US1] Create SyncNotificationBadge component in `frontend/src/components/integrations/xero/SyncNotificationBadge.tsx` — bell icon badge showing count of active syncs, polls active sync count, shows toast on sync completion with summary ("Client X sync complete — 2,517 records synced"), integrates with existing notification system

- [x] T021 [US1] Refactor SyncProgressDialog to non-blocking mode in `frontend/src/components/integrations/xero/SyncProgressDialog.tsx` — closing the dialog does NOT cancel the sync, replace blocking modal with optional expandable panel, show per-entity progress from EntityProgressResponse, show phase indicator ("Phase 1 of 3: Essential Data"), add "View Details" link to full progress view

- [x] T022 [US1] Update SyncTriggerButton behavior — on sync trigger show toast confirmation ("Syncing data for Client X...") instead of opening blocking dialog, navigate user back to their workflow in `frontend/src/components/integrations/xero/SyncTriggerButton.tsx`

- [x] T023 [US1] Update SyncStatusDisplay with data freshness indicator — show "Last synced X ago" with relative time, show amber warning when data is stale (>24 hours), show green indicator when fresh (<1 hour) in `frontend/src/components/integrations/xero/SyncStatusDisplay.tsx`

- [x] T024 [US2] Add "Syncing historical data..." indicator to client dashboard sections that depend on Phase 2/3 data — show available Phase 1 data immediately, subtle loading state for sections awaiting later phases in relevant frontend client dashboard components

**Checkpoint**: Trigger sync → toast appears → user can navigate freely → per-entity progress visible in status endpoint → notification on completion. Phase 1 data available in <30s.

---

## Phase 4: User Story 4 — Incremental Sync Expansion (P2)

**Goal**: Expand If-Modified-Since from 3 entity types to 9. Subsequent syncs complete in seconds by only fetching changed records.

**Independent Test**: Full sync a client → wait → modify a record in Xero → trigger sync again → only changed entities fetched → sync completes in <10s.

- [x] T025 [US4] Wire If-Modified-Since timestamps for 6 new entity types in `backend/app/tasks/xero.py` — when building entity sync task arguments, pass `connection.last_credit_notes_sync_at`, `last_payments_sync_at`, `last_overpayments_sync_at`, `last_prepayments_sync_at`, `last_journals_sync_at`, `last_manual_journals_sync_at` as modified_since for the respective entity tasks (unless force_full=True)

- [x] T026 [US4] Update timestamp storage after successful entity sync — in each entity task's completion handler, write back the sync timestamp to the appropriate `last_*_sync_at` column on XeroConnection for all 9 IMS-supported entities (contacts, invoices, bank_transactions + 6 new) in `backend/app/tasks/xero.py`

- [x] T027 [US4] Fix date format inconsistency in XeroClient — standardize If-Modified-Since header format across all entity methods (credit_notes, payments, overpayments, prepayments, journals, manual_journals currently use ISO 8601 while contacts, invoices, bank_transactions use RFC 7231) in `backend/app/modules/integrations/xero/client.py`

- [x] T028 [US4] Update `sync_all_stale_connections` scheduler to prefer incremental sync — set `force_full=False` by default so per-entity timestamps are used, add logic to force full sync if no per-entity timestamps exist (first sync after migration) in `backend/app/tasks/scheduler.py`

**Checkpoint**: Run full sync → check last_*_sync_at columns populated for all 9 entities → run another sync → verify API calls use If-Modified-Since headers → sync completes much faster.

---

## Phase 5: User Story 3 — Multi-Client Parallel Sync (P2)

**Goal**: "Sync All Clients" action queues and processes all connected clients in parallel with Xero API rate limit management.

**Depends on**: Phase 3 (US1+US2) — requires phased sync working for individual clients.

**Independent Test**: Click "Sync All" → multiple clients sync concurrently → aggregate progress shows "12/50 clients..." → rate limits respected → individual failures don't affect other clients.

### Backend

- [x] T029 [US3] Add `start_multi_client_sync()` to XeroSyncService — fetch all active connections for tenant, skip connections with active syncs, create XeroSyncJob for each, dispatch phased sync tasks with staggered delays for rate limit safety, return MultiClientSyncResponse (batch_id, total_connections, jobs_queued, jobs_skipped) in `backend/app/modules/integrations/xero/service.py`

- [x] T030 [US3] Add `POST /api/v1/xero/sync/all` endpoint — accept force_full and sync_type params, call start_multi_client_sync(), return 202 with MultiClientSyncResponse in `backend/app/modules/integrations/xero/router.py`

- [x] T031 [US3] Add `GET /api/v1/xero/sync/all/status` endpoint — aggregate status across all jobs in the batch (total, completed, in_progress, failed, pending), include per-connection summary (connection_id, organization_name, status, records_processed), return MultiClientSyncStatusResponse in `backend/app/modules/integrations/xero/router.py`

- [x] T032 [US3] Implement global rate-limit-aware concurrency control — add configurable max_concurrent_syncs setting, use Celery task routing or Redis-based semaphore to limit parallel Xero API connections, respect per-connection rate limits (60/min) AND cross-connection daily limit (5000/day) in `backend/app/tasks/xero.py`

### Frontend

- [x] T033 [P] [US3] Create MultiClientSyncButton component in `frontend/src/components/integrations/xero/MultiClientSyncButton.tsx` — "Sync All Clients" button with confirmation dialog, shows aggregate progress bar ("Syncing 12/50 clients..."), expandable per-client status list, handles partial failures gracefully

- [x] T034 [US3] Add multi-client sync API functions (startMultiClientSync, getMultiClientSyncStatus) and types (MultiClientSyncResponse, MultiClientSyncStatusResponse) in `frontend/src/lib/xero-sync.ts`

**Checkpoint**: Click "Sync All" → multiple clients process concurrently → aggregate progress visible → rate limits never exceeded → individual client failures isolated.

---

## Phase 6: User Story 7 — Post-Sync Data Preparation (P2)

**Goal**: Automatically trigger quality scoring, BAS calculation, AI aggregation, insight generation, and trigger evaluation after each sync phase completes. Track execution and notify user.

**Independent Test**: Sync a client → after Phase 1: quality score appears on client card → after full sync: BAS periods calculated, insights generated → user notified with summary.

- [x] T035 [US7] Implement per-phase post-sync task dispatch in phase completion callbacks — Phase 1 callback: dispatch quality_score task, create PostSyncTask record (task_type='quality_score', sync_phase=1); Phase 2 callback: dispatch bas_calculation + aggregation tasks, create PostSyncTask records; Phase 3 callback: dispatch insights + triggers tasks, create PostSyncTask records in `backend/app/tasks/xero.py`

- [x] T036 [US7] Wrap existing post-sync Celery tasks (calculate_quality_score, calculate_bas_periods, compute_aggregations, generate_insights_for_connection, evaluate_data_triggers) to update their corresponding PostSyncTask record on start (status=in_progress, started_at), completion (status=completed, completed_at, result_summary), and failure (status=failed, error_message) in `backend/app/tasks/xero.py`

- [x] T037 [US7] Publish post_sync_progress events via Redis pub/sub when PostSyncTask status changes — include task_type, status, result_summary for SSE consumption in `backend/app/tasks/xero.py`

- [x] T038 [US7] Add post-sync task status to GET /sync/status response — include PostSyncTaskResponse array showing each task's type, status, and result_summary in `backend/app/modules/integrations/xero/router.py`

**Checkpoint**: Sync a client → PostSyncTask records created per phase → quality score calculated after Phase 1 → BAS + aggregation after Phase 2 → insights + triggers after Phase 3 → all tasks tracked in post_sync_tasks table.

---

## Phase 7: User Story 5 — Real-Time SSE Progress (P3)

**Goal**: Replace 2-second polling with Server-Sent Events for sub-second progress updates during sync.

**Independent Test**: Trigger a sync → open SSE stream → receive entity_progress, phase_complete, sync_complete events in real-time (<1s latency) → no page refresh needed.

### Backend

- [x] T039 [US5] Add SSE subscriber async generator to SyncProgressSubscriber — subscribe to Redis pub/sub channel for connection_id, yield SSE-formatted strings (`event: {type}\ndata: {json}\n\n`), handle connection cleanup on client disconnect, support optional job_id filtering in `backend/app/modules/integrations/xero/sync_progress.py`

- [x] T040 [US5] Add `GET /api/v1/xero/connections/{id}/sync/stream` SSE endpoint — accept optional job_id query param, authenticate request, create SyncProgressSubscriber, return StreamingResponse with media_type='text/event-stream' and appropriate headers (Cache-Control: no-cache, Connection: keep-alive) in `backend/app/modules/integrations/xero/router.py`

### Frontend

- [x] T041 [P] [US5] Create useSyncProgress hook in `frontend/src/hooks/useSyncProgress.ts` — wraps native EventSource API, connects to /sync/stream endpoint with auth token, parses SSE events into typed objects (SyncStartedEvent, EntityProgressEvent, PhaseCompleteEvent, SyncCompleteEvent, SyncFailedEvent, PostSyncProgressEvent), handles reconnection on disconnect, exposes connection status

- [x] T042 [US5] Replace polling with SSE in SyncProgressDialog — use useSyncProgress hook instead of setInterval polling, update entity progress in real-time as events arrive, fall back to polling if SSE connection fails in `frontend/src/components/integrations/xero/SyncProgressDialog.tsx`

- [x] T043 [US5] Add auto-refresh of client data on sync_complete SSE event — when sync completes, invalidate relevant TanStack Query caches (client data, invoices, contacts) so dashboard updates automatically without manual page reload in relevant frontend hooks/components

**Checkpoint**: Open browser DevTools Network tab → trigger sync → observe SSE stream with real-time events → progress updates appear instantly → data refreshes automatically on completion.

---

## Phase 8: User Story 6 — Xero Webhooks (P3)

**Goal**: Receive Xero webhook events and trigger targeted single-record syncs for near-real-time data freshness.

**Independent Test**: Configure Xero webhook → create/update invoice in Xero → webhook received → targeted sync runs → record appears in Clairo within 2 minutes.

- [x] T044 [US6] Create webhook handler with HMAC-SHA256 signature verification — verify X-Xero-Signature header against webhook signing key, handle intent-to-receive validation (respond with 200 to validation requests), reject invalid signatures with 401 in `backend/app/modules/integrations/xero/webhook_handler.py`

- [x] T045 [US6] Add `POST /api/v1/xero/webhooks` endpoint — parse webhook payload, verify signature via webhook_handler, store events as XeroWebhookEvent records, return 200 immediately (async processing), dispatch webhook processing task in `backend/app/modules/integrations/xero/router.py`

- [x] T046 [US6] Implement event deduplication and batching logic — deduplicate by webhook_key, batch events for the same connection within a 30-second window, group by entity type, create a single targeted sync per entity type per connection in `backend/app/modules/integrations/xero/webhook_handler.py`

- [x] T047 [US6] Create `process_webhook_events` Celery task — fetch pending webhook events, batch by connection + entity_type, dispatch targeted incremental sync for each batch (single entity type, modified_since from event timestamp), mark events as processed/failed in `backend/app/tasks/xero.py`

- [x] T048 [US6] Add XERO_WEBHOOK_KEY environment variable to config and update XeroSettings in `backend/app/config.py`

**Checkpoint**: Send test webhook payload → signature verified → event stored → batch processed → targeted sync runs → record updated in database.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T049 Add structured logging for sync operations — log phase transitions, entity start/complete/fail with record counts, rate limit state, multi-client batch progress across `backend/app/tasks/xero.py` and `backend/app/modules/integrations/xero/service.py`

- [x] T050 Ensure audit events emitted for sync start/complete/fail per compliance requirements — verify integration.xero.sync.started, .completed, .failed events include job_id, phase, triggered_by, record counts in `backend/app/tasks/xero.py`

- [x] T051 Deprecate legacy `run_sync` task — add deprecation warning, keep functional as fallback, update all callers to use `run_phased_sync` in `backend/app/tasks/xero.py`

- [x] T052 Fix `accounting_url` bug in XeroClient — Spec 025 methods (get_purchase_orders, get_repeating_invoices, get_tracking_categories, get_quotes) reference `self.settings.accounting_url` which doesn't exist; change to `self.settings.api_url` in `backend/app/modules/integrations/xero/client.py`

- [x] T053 Fix Spec 025 service methods that reference uninitialized `self.xero_client` — update sync_purchase_orders, sync_repeating_invoices, sync_tracking_categories, sync_quotes to use `async with XeroClient(...)` pattern consistent with other entity sync methods in `backend/app/modules/integrations/xero/service.py`

---

## Phase FINAL: PR & Merge

- [ ] T054 Run backend tests and fix any failures
  - Run: `cd backend && uv run pytest`
  - All tests must pass before PR

- [x] T055 Run backend linting and type checking
  - Run: `cd backend && uv run ruff check .`
  - Fix any issues

- [x] T056 Run frontend build and fix any errors
  - Run: `cd frontend && npm run build`
  - Fix any TypeScript or build errors

- [ ] T057 Push feature branch and create PR
  - Run: `git push origin 043-progressive-xero-sync`
  - Run: `gh pr create --title "Spec 043: Progressive Xero Data Sync" --body "..."`
  - Include summary of all phases and user stories in PR description

- [ ] T058 Address review feedback (if any)
  - Make requested changes
  - Push additional commits

- [ ] T059 Merge PR to main
  - Squash merge after approval
  - Delete feature branch after merge

- [ ] T060 Update ROADMAP.md
  - Mark spec 043 as COMPLETE
  - Update current focus to next spec

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 0 (Git) ──→ Phase 1 (Setup) ──→ Phase 2 (Foundational) ──┬──→ Phase 3 (US1+US2, P1) ──→ Phase 5 (US3, P2)
                                                                 ├──→ Phase 4 (US4, P2)
                                                                 ├──→ Phase 6 (US7, P2)
                                                                 ├──→ Phase 7 (US5, P3)
                                                                 └──→ Phase 8 (US6, P3)
                                                                          │
                                                                          ▼
                                                                 Phase 9 (Polish) ──→ Phase FINAL (PR)
```

### User Story Dependencies

| Story | Depends On | Can Start After |
|-------|-----------|-----------------|
| US1+US2 (P1) | Phase 2 | Foundational complete |
| US4 (P2) | Phase 2 | Foundational complete (parallel with US1+US2) |
| US3 (P2) | Phase 3 | US1+US2 complete (needs working phased sync) |
| US7 (P2) | Phase 2 | Foundational complete (parallel with US1+US2) |
| US5 (P3) | Phase 2 | Foundational complete (parallel with US1+US2) |
| US6 (P3) | Phase 1 | Setup complete (independent of other stories) |

### Within Each User Story

- Models/repos before services
- Services before endpoints
- Backend before frontend (for same endpoint)
- Core implementation before integration

### Parallel Opportunities

After Phase 2 completes, these can run in parallel:
- **Stream A**: Phase 3 (US1+US2) → Phase 5 (US3)
- **Stream B**: Phase 4 (US4)
- **Stream C**: Phase 6 (US7)
- **Stream D**: Phase 7 (US5)
- **Stream E**: Phase 8 (US6)

Within each phase, tasks marked [P] can run in parallel.

---

## Parallel Examples

### Phase 1 — Parallel model creation:
```
Task T007: Add XeroSyncEntityProgressRepository     ──┐
Task T008: [P] Add PostSyncTaskRepository            ──┼── parallel (different sections of repository.py)
Task T009: [P] Add XeroWebhookEventRepository        ──┘
Task T011: [P] Create sync_progress.py               ──── parallel (new file, no deps)
```

### Phase 3 — Parallel frontend work:
```
Task T019: [P] Update xero-sync.ts types             ──┐
Task T020: [P] Create SyncNotificationBadge           ──┼── parallel (different files)
```

### After Phase 2 — Parallel user stories:
```
Stream A: T015→T016→T017→T018→T019→T020→T021→T022→T023→T024  (US1+US2)
Stream B: T025→T026→T027→T028                                  (US4)
Stream C: T035→T036→T037→T038                                  (US7)
Stream D: T039→T040→T041→T042→T043                             (US5)
Stream E: T044→T045→T046→T047→T048                             (US6)
```

---

## Implementation Strategy

### MVP First (Phase 3: US1 + US2 Only)

1. Complete Phase 1: Setup (models, migration, repos, schemas)
2. Complete Phase 2: Foundational (per-entity tasks, phased orchestrator)
3. Complete Phase 3: US1+US2 (non-blocking phased sync)
4. **STOP and VALIDATE**: Trigger sync → user not blocked → essential data in <30s → completion notification
5. Deploy/demo — this alone eliminates the biggest pain point

### Incremental Delivery

1. Setup + Foundational → Infrastructure ready
2. US1+US2 → Non-blocking phased sync → **Deploy (MVP!)**
3. US4 → Incremental sync → Deploy (syncs now take seconds)
4. US3 → Multi-client sync → Deploy (practice-wide sync)
5. US7 → Post-sync pipeline → Deploy (automated data preparation)
6. US5 → Real-time SSE → Deploy (enhanced UX)
7. US6 → Webhooks → Deploy (near-real-time freshness)
8. Polish + PR → Complete

### Parallel Team Strategy

With multiple developers after Phase 2:
- **Dev A**: US1+US2 (P1) → US3 (P2, depends on US1+US2)
- **Dev B**: US4 (P2) + US7 (P2)
- **Dev C**: US5 (P3) + US6 (P3)

---

## Summary

| Metric | Value |
|--------|-------|
| Total tasks | 60 |
| Phase 1 (Setup) | 11 tasks |
| Phase 2 (Foundational) | 3 tasks |
| Phase 3 (US1+US2, P1 MVP) | 10 tasks |
| Phase 4 (US4, P2) | 4 tasks |
| Phase 5 (US3, P2) | 6 tasks |
| Phase 6 (US7, P2) | 4 tasks |
| Phase 7 (US5, P3) | 5 tasks |
| Phase 8 (US6, P3) | 5 tasks |
| Phase 9 (Polish) | 5 tasks |
| Phase FINAL (PR) | 7 tasks |
| Parallel opportunities | 5 independent streams after Phase 2 |
| MVP scope | Phases 1-3 (24 tasks) |

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Each user story is independently testable after its phase completes
- Commit after each task or logical group
- Stop at any checkpoint to validate independently
- The phased sync orchestrator (T013) is the most complex single task — consider breaking into sub-steps during implementation
- T052 and T053 fix pre-existing bugs discovered during research — not new feature work but important for correctness
