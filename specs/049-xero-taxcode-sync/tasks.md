# Tasks: Xero Tax Code Write-Back

**Input**: Design documents from `specs/049-xero-taxcode-sync/`
**Branch**: `049-xero-taxcode-sync` (already active)
**Prerequisites**: plan.md ✅ · spec.md ✅ · research.md ✅ · data-model.md ✅ · contracts/ ✅

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no cross-task dependency)
- **[Story]**: User story label (US1–US11)
- All paths from repository root

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database tables, Xero client write methods, and base model changes that MUST exist before any user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T001 Create Alembic migration `add_xero_writeback_tables` — creates `xero_writeback_jobs` and `xero_writeback_items` tables with all columns, indexes, and enums as defined in `specs/049-xero-taxcode-sync/data-model.md` in `backend/app/migrations/versions/`
- [ ] T002 Create Alembic migration `add_tax_code_override_writeback_status` — adds `writeback_status VARCHAR(20) NOT NULL DEFAULT 'pending_sync'` column to `tax_code_overrides` table in `backend/app/migrations/versions/`
- [ ] T003 Create Alembic migration `extend_classification_requests_for_sendback` — adds `parent_request_id UUID NULLABLE FK→classification_requests` and `round_number INTEGER NOT NULL DEFAULT 1` to `classification_requests`; removes old `UNIQUE(session_id)` constraint; adds `UNIQUE(session_id, round_number) WHERE parent_request_id IS NULL` partial index in `backend/app/migrations/versions/`
- [ ] T004 Create Alembic migration `add_agent_transaction_notes` — creates `agent_transaction_notes` table with all columns and indexes as in data-model.md in `backend/app/migrations/versions/`
- [ ] T005 Create Alembic migration `add_client_classification_rounds` — creates `client_classification_rounds` table with all columns and indexes as in data-model.md in `backend/app/migrations/versions/`
- [ ] T006 [P] Create `backend/app/modules/integrations/xero/writeback_models.py` — define `XeroWritebackJobStatus`, `XeroWritebackItemStatus`, `XeroWritebackSkipReason` enums; `XeroWritebackJob` and `XeroWritebackItem` SQLAlchemy models with all fields from data-model.md; include `tenant_id` RLS column, FK relationships to `XeroConnection`, `BASSession`, `PracticeUser`
- [ ] T007 [P] Add `writeback_status` field and `TaxCodeOverrideWritebackStatus` enum to `TaxCodeOverride` model in `backend/app/modules/bas/models.py`
- [ ] T008 Add `parent_request_id` (nullable UUID FK self-ref) and `round_number` (INTEGER default 1) fields to `ClassificationRequest` model in `backend/app/modules/bas/classification_models.py`; add `relationship` for parent/child requests
- [ ] T009 [P] Add Xero document write methods to `backend/app/modules/integrations/xero/client.py`: `get_invoice(access_token, xero_tenant_id, invoice_id)`, `get_bank_transaction(...)`, `get_credit_note(...)`, `update_invoice(access_token, xero_tenant_id, invoice_id, line_items)`, `update_bank_transaction(...)`, `update_credit_note(...)` — each method includes `Xero-Tenant-Id` header and rate-limit header parsing; raises `XeroRateLimitError` on 429, `XeroAuthError` on 401
- [ ] T010 [P] Add writeback-specific exceptions to `backend/app/modules/integrations/xero/exceptions.py`: `WritebackError`, `XeroDocumentNotEditableError(skip_reason: str)`, `XeroConflictError(xero_document_id: str)`, `WritebackJobNotFoundError`
- [ ] T011 Create `backend/app/modules/integrations/xero/writeback_repository.py` — `XeroWritebackRepository` class with methods: `create_job(...)`, `get_job(job_id, tenant_id)`, `list_jobs_for_session(session_id, tenant_id)`, `create_item(...)`, `get_items_for_job(job_id)`, `update_item_status(item_id, status, ...)`, `update_job_counts(job_id, ...)`, `get_failed_items(job_id)`; all methods use `flush()` not `commit()`; all queries filter by `tenant_id`
- [ ] T012 Create `backend/app/modules/integrations/xero/writeback_schemas.py` — Pydantic schemas matching `contracts/writeback.yaml`: `WritebackJobResponse`, `WritebackJobDetailResponse`, `WritebackItemResponse`; all fields typed with UUID/datetime/enum as appropriate

**Checkpoint**: Migrations runnable, models defined, Xero client has write methods, schemas defined — user story implementation can begin.

---

## Phase 3: User Story 1 — Sync Approved Tax Codes to Xero (Priority: P1) 🎯 MVP

**Goal**: Tax agent triggers "Sync to Xero" for a BAS session; system writes all approved unsynced overrides to Xero; returns job with success count.

**Independent Test**: Approve 3 TaxCodeOverride records in a BAS session → trigger `POST /bas/sessions/{id}/writeback` → poll job until completed → verify XeroWritebackItems show `status=success` and corresponding TaxCodeOverride records have `writeback_status=synced`.

- [ ] T013 [P] [US1] Create `backend/app/modules/integrations/xero/writeback_service.py` — `XeroWritebackService` with `initiate_writeback(session_id, triggered_by, tenant_id, db)`: validates session status ≥ `ready_for_review` (raises `WritebackError` if not); queries `TaxCodeOverride` records where `status=approved`, `writeback_status=pending_sync`, `session_id` matches; raises `WritebackError("no_items_to_sync")` if zero found; calls `validate_tax_types_for_org(connection, overrides)` (see T013a) before grouping; groups by `(source_type, xero_document_id)`; creates `XeroWritebackJob` (status=pending, total_count=N) and one `XeroWritebackItem` per document group; returns job after flushing
- [ ] T013a [P] [US1] Add `get_tax_rates(access_token, xero_tenant_id)` method to `backend/app/modules/integrations/xero/client.py` — calls `GET /TaxRates`, returns list of `{"TaxType": str, "Name": str, "Status": str}` dicts; add `validate_tax_types_for_org(connection, overrides, db)` helper in `writeback_service.py` that calls `get_tax_rates()`, builds a set of active `TaxType` codes, and raises `WritebackError("invalid_tax_type", tax_type=code)` for any override whose `override_tax_type` is not in that set — prevents writing unknown codes that would cause Xero 400 errors
- [ ] T014 [P] [US1] Add `group_overrides_by_document(overrides: list[TaxCodeOverride], db)` helper to `writeback_service.py` — resolves each override's `source_id` to its Xero document ID and `xero_document_id`; returns `dict[tuple[source_type, xero_document_id], list[TaxCodeOverride]]`
- [ ] T015 [US1] Create `backend/app/tasks/xero_writeback.py` — Celery task `process_writeback_job(job_id: str, tenant_id: str)` bound to queue `xero_writeback`; task is idempotent (checks `XeroWritebackItem.status != success` before processing each item); on start: sets `XeroWritebackJob.status=in_progress`, `started_at=now()`; loops through items sequentially
- [ ] T016 [US1] Implement document reconstruction in `process_writeback_job`: for each `XeroWritebackItem`, load the local Xero entity (`XeroInvoice`/`XeroBankTransaction`/`XeroCreditNote`) from DB; `deepcopy(entity.line_items)`; apply each override's `override_tax_type` to the correct line item index; record `before_tax_types` and `after_tax_types` on the item
- [ ] T017 [US1] Implement Xero write call in `process_writeback_job`: call appropriate `xero_client.update_*()` method with reconstructed `line_items`; pass `idempotencyKey=str(writeback_item.id)` header on each call (prevents Xero-side duplicate on Celery retry); pass `summarizeErrors=false` query param to receive per-field error detail; on HTTP 200: set `XeroWritebackItem.status=success`, `processed_at=now()`; update each `TaxCodeOverride.writeback_status=synced`, `is_active=false`; update local Xero entity `line_items` JSONB with the written payload; increment `XeroWritebackJob.succeeded_count`
- [ ] T018 [US1] Implement rate limit handling in `process_writeback_job`: after each item, call `XeroRateLimiter.get_wait_time(state)` — if > 0, `asyncio.sleep(wait_time)` before next item; update `RateLimitState` from response headers after each call; update `XeroConnection.rate_limit_*` fields
- [ ] T019 [US1] Implement OAuth token refresh in `process_writeback_job`: before each item, check `XeroConnection.token_expires_at` — if within 5 minutes, call `XeroClient.refresh_token()`, save new tokens; if refresh fails, mark all remaining items `failed` with `error_detail=auth_error`, set job `status=failed`, abort task
- [ ] T020 [US1] Implement job completion logic in `process_writeback_job`: after all items processed, set `completed_at=now()`, `duration_seconds`, `status` = `completed` (if failed_count=0 and skipped_count<total), `partial` (if succeeded_count>0 and failed_count>0), `failed` (if succeeded_count=0 and all failed)
- [ ] T021 [US1] Add `enqueue_writeback_task(job_id, tenant_id)` helper in `writeback_service.py` that dispatches `process_writeback_job.apply_async(args=[str(job_id), str(tenant_id)], queue="xero_writeback")`; called from `initiate_writeback()` after job creation
- [ ] T022 [US1] Add writeback endpoints to `backend/app/modules/bas/router.py`: `POST /bas/sessions/{session_id}/writeback` calls `XeroWritebackService.initiate_writeback()`, returns 202 with `WritebackJobResponse`; `GET /bas/sessions/{session_id}/writeback/jobs` returns list; `GET /bas/sessions/{session_id}/writeback/jobs/{job_id}` returns `WritebackJobDetailResponse` with items; raise 409 if job already `in_progress`; raise 400 if no items to sync; convert domain exceptions to HTTP exceptions
- [ ] T023 [US1] Add `SyncToXeroButton` component to `frontend/src/app/bas/[sessionId]/_components/SyncToXeroButton.tsx` — shows count of `approved_unsynced` overrides from BAS session data; hidden if count=0; disabled while any job is `in_progress`; on click: calls `POST /writeback`, stores returned `job_id` in component state, triggers `WritebackProgressPanel`; uses `Button` from shadcn/ui

**Checkpoint**: Tax agent can trigger sync → Celery task writes to Xero → frontend shows job created. Basic happy-path writeback functional.

---

## Phase 4: User Story 2 — Handle Non-Editable Transactions Gracefully (Priority: P1)

**Goal**: Voided, deleted, period-locked, and conflict-changed documents are detected, skipped, and reported clearly — without failing the entire sync.

**Independent Test**: Attempt writeback on a VOIDED Xero invoice → verify `XeroWritebackItem.status=skipped`, `skip_reason=voided` → verify other items in the same job still succeed.

- [ ] T024 [US2] Add pre-flight check method `check_document_editability(xero_client, connection, source_type, xero_document_id, local_entity)` to `writeback_service.py` — calls `xero_client.get_{type}()` to fetch current Xero document; if `Status in (VOIDED, DELETED)` → raise `XeroDocumentNotEditableError("voided"/"deleted")`; if `UpdatedDateUTC` differs from `local_entity.xero_updated_at` → raise `XeroConflictError`; for bank transactions, check `IsReconciled == True` (not `IsLocked` — that field does not exist on Xero bank transactions) → raise `XeroDocumentNotEditableError("reconciled")`
- [ ] T025 [US2] Integrate pre-flight check into `process_writeback_job` in `backend/app/tasks/xero_writeback.py` — call `check_document_editability()` before reconstruction; catch `XeroDocumentNotEditableError` and `XeroConflictError`; set `XeroWritebackItem.status=skipped`, `skip_reason` from exception; increment `XeroWritebackJob.skipped_count`; continue to next item
- [ ] T026 [US2] Handle error-based skip cases in `process_writeback_job` — catch HTTP 400 responses from `update_*()` calls and classify by Xero error message: "period" or "locked" → `skip_reason=period_locked`; "Cannot modify line items on an invoice that has payments" → `skip_reason=authorised_locked`; credit note applied → `skip_reason=credit_note_applied`; set `status=skipped` and increment `skipped_count` for all; continue to next item
- [ ] T027 [US2] Handle unexpected Xero errors in `process_writeback_job` — catch all other exceptions from `update_*()` calls; set `XeroWritebackItem.status=failed`, `error_detail=str(e)`, `xero_http_status` from response; increment `failed_count`; continue processing remaining items (do not abort job)
- [ ] T028 [US2] Update `WritebackResultsSummary` to display skip details in `frontend/src/app/bas/[sessionId]/_components/WritebackResultsSummary.tsx` — render amber warning section listing each skipped item with `skip_reason` mapped to human-readable label: `voided` → "Voided in Xero", `period_locked` → "Period is locked — unlock in Xero first", `conflict_changed` → "Xero data changed — re-sync from Xero first", `reconciled` → "Reconciled transaction — unreconcile in Xero first", `authorised_locked` → "Invoice has payments applied — remove payment in Xero first", `credit_note_applied` → "Credit note fully applied — reverse in Xero first"; guidance text per reason; uses `Badge` and `Card` from shadcn/ui

**Checkpoint**: Non-editable docs are silently skipped, agents see clear reasons, job doesn't fail on known bad cases.

---

## Phase 5: User Story 5 — Audit Trail for Xero Write-Backs (Priority: P1)

**Goal**: Every write attempt (success, skip, failure) is logged in the audit trail with full context for ATO compliance.

**Independent Test**: Trigger a writeback → query `audit_logs` table → verify entries exist for `xero.taxcode.writeback_initiated`, `xero.taxcode.writeback_item_success`, `xero.taxcode.writeback_completed` events with correct `resource_id`, `actor_id`, `tenant_id`.

- [ ] T029 [P] [US5] Add writeback audit event constants to `backend/app/modules/integrations/xero/audit_events.py`: `WRITEBACK_INITIATED = "xero.taxcode.writeback_initiated"`, `WRITEBACK_ITEM_SUCCESS = "xero.taxcode.writeback_item_success"`, `WRITEBACK_ITEM_SKIPPED = "xero.taxcode.writeback_item_skipped"`, `WRITEBACK_ITEM_FAILED = "xero.taxcode.writeback_item_failed"`, `WRITEBACK_COMPLETED = "xero.taxcode.writeback_completed"`, `WRITEBACK_RETRY_INITIATED = "xero.taxcode.writeback_retry_initiated"`; add classification send-back events: `ITEMS_SENT_BACK = "classification.items_sent_back"`, `CLIENT_ANSWERED_ROUND = "classification.client_answered_round"` (in BAS audit events file)
- [ ] T030 [US5] Emit `WRITEBACK_INITIATED` audit event in `writeback_service.py` `initiate_writeback()` — call `audit_event(event_type=WRITEBACK_INITIATED, resource_type="xero_writeback_job", resource_id=job.id, new_values={session_id, connection_id, user_id, count_queued})`
- [ ] T031 [US5] Emit per-item audit events in `process_writeback_job` in `backend/app/tasks/xero_writeback.py` — after each item outcome: emit `WRITEBACK_ITEM_SUCCESS` with `{xero_document_id, source_type, line_item_indexes, before_tax_types, after_tax_types, user_id}`, OR `WRITEBACK_ITEM_SKIPPED` with `{skip_reason}`, OR `WRITEBACK_ITEM_FAILED` with `{xero_http_status, error_detail}`; all include `session_id`, `tenant_id`, timestamp
- [ ] T032 [US5] Emit `WRITEBACK_COMPLETED` audit event at end of `process_writeback_job` — include `{job_id, total, succeeded, skipped, failed, duration_seconds, user_id}`
- [ ] T033 [US5] Emit `CLIENT_ANSWERED_ROUND` audit event in `classification_service.py` portal submit handler when processing a returned item response — include `{request_id, transaction_id, round_number, client_response_category}`

**Checkpoint**: Full audit trail persisted for all writeback outcomes. ATO traceability requirement met.

---

## Phase 6: User Story 6 — Client Must Describe "I Don't Know" Transactions (Priority: P1)

**Goal**: Portal clients cannot submit "I don't know" without a description; server rejects blank descriptions.

**Independent Test**: Submit a portal classification with `client_needs_help=true` and empty `client_description` → expect HTTP 400 with code `missing_idk_description`. Submit with description → expect 200.

- [ ] T034 [P] [US6] Add server-side validation to portal submit handler in `backend/app/modules/bas/classification_service.py`: in `submit_classification(request_id, responses, portal_session_id)`, iterate responses; for any where `category == "i_dont_know"`, validate `description` is non-null and non-empty; raise domain exception `ClassificationValidationError("missing_idk_description")` if not met; convert to 400 in router
- [ ] T035 [US6] Update portal `ClassificationItem` component in `frontend/src/app/portal/classify/[token]/_components/ClassificationItem.tsx` — when "I don't know" option selected: show mandatory `Textarea` with label "Please describe what you know about this transaction"; add red asterisk indicator; disable item's "done" state until textarea has non-empty value; show inline validation message "A description is required" if user attempts to proceed without filling it
- [ ] T036 [US6] Update portal "I don't know" submission in frontend `useClassificationState` hook — when category=`i_dont_know`, mark item as "unanswered" until description ≥ 1 char; prevent progress-to-next-item navigation if "I don't know" + empty description
- [ ] T037 [US6] Ensure "I don't know" description is passed correctly in `PortalSubmitRequest` payload from `frontend/src/lib/api/classification-extensions.ts` to server; update type definition to match `contracts/classification-extensions.yaml`

**Checkpoint**: No blank "I don't know" items can reach agent review. Client and server both enforce description.

---

## Phase 7: User Story 7 — Client Must Answer Every Transaction Before Submitting (Priority: P1)

**Goal**: Submit button disabled until all transactions answered; server validates completeness.

**Independent Test**: Load portal with 5 transactions, answer 4 → submit button disabled, counter shows "1 still needs your answer". Answer all 5 → submit enabled. POST with 1 unanswered → 400 `unanswered_transactions`.

- [ ] T038 [P] [US7] Add server-side all-answered validation to portal submit handler in `backend/app/modules/bas/classification_service.py`: before processing, count `ClientClassification` records in request where `classified_at IS NULL`; if count > 0, raise `ClassificationValidationError("unanswered_transactions", count=N)`; convert to 400 in router with count in `details`
- [ ] T039 [US7] Update portal submit component in `frontend/src/app/portal/classify/[token]/_components/ClassificationSubmit.tsx` — disable `Button` (shadcn) when `unansweredCount > 0`; show live counter below button: "N of M transactions answered" / "Ready to submit" when all done; counter updates reactively from `useClassificationState` as user answers items; use `cn()` for conditional button states
- [ ] T040 [US7] Track answer state per item in portal frontend — update `useClassificationState` hook to maintain `answeredIds: Set<string>` incrementally; item is "answered" when it has a non-IDK category OR `i_dont_know` + non-empty description OR `personal`; export `unansweredCount` and `answeredCount` from hook
- [ ] T041 [US7] Ensure submit button on returned-item portal sessions also gates on all-answered state — reuse same `unansweredCount` logic for round 2+ `ClassificationRequest` portal sessions

**Checkpoint**: Portal submit is fully gated. No partial submissions reach the server.

---

## Phase 8: User Story 9 — Agent Sends "I Don't Know" Items Back to Client With Guidance (Priority: P1)

**Goal**: Agent can select unresolved "I don't know" items, add a comment, and send them back to the client as a new request with a new magic link.

**Independent Test**: Client submits "I don't know" for transaction A → agent adds comment "Please confirm this was for your vehicle" → agent triggers send-back → verify new `ClassificationRequest` created (round_number=2, parent_request_id=original) → verify `AgentTransactionNote` record with `is_send_back_comment=true` → verify email sent with new magic link → client opens new portal session, sees original response + agent comment.

- [ ] T042 [P] [US9] Add `AgentTransactionNote` and `ClientClassificationRound` models to `backend/app/modules/bas/classification_models.py` — all fields from data-model.md; `AgentTransactionNote` FK to `ClassificationRequest`, `PracticeUser`; `ClientClassificationRound` FK to `BASSession`, `ClassificationRequest`; include `tenant_id` on both
- [ ] T043 [P] [US9] Create Alembic migrations for agent_transaction_notes and client_classification_rounds (if not already included in T004/T005 — verify and consolidate if needed)
- [ ] T044 [P] [US9] Add send-back schemas to `backend/app/modules/bas/classification_schemas.py`: `AgentNoteCreate`, `AgentNoteResponse`, `SendBackRequest`, `SendBackResponse`, `ClassificationRoundResponse` matching `contracts/classification-extensions.yaml`
- [ ] T045 [US9] Implement `send_items_back(request_id, items_with_comments, triggered_by, tenant_id, db)` in `backend/app/modules/bas/classification_service.py`: validate each `classification_id` has `client_needs_help=true`; validate agent_comment non-empty for each item; create new `ClassificationRequest` (parent_request_id=source_request.id, round_number=source.round_number+1); copy `ClientClassification` records for returned items into new request (reset `classified_at`, keep denormalized context); create `AgentTransactionNote` per item (is_send_back_comment=true); create `ClientClassificationRound` per item (round_number, agent_comment, request_id); generate new magic link (7-day expiry); send email via Resend with new link; emit `ITEMS_SENT_BACK` audit event; return new request
- [ ] T046 [US9] Implement `get_classification_thread(session_id, source_type, source_id, line_item_index, tenant_id, db)` in `classification_service.py` — queries `ClientClassificationRound` ordered by round_number; returns ordered list of rounds with agent comments and client responses
- [ ] T047 [US9] Add classification extension endpoints to `backend/app/modules/bas/router.py`: `POST /bas/sessions/{id}/classification-requests/{req_id}/send-back` calls `send_items_back()`; `GET /bas/sessions/{id}/classification-requests/{req_id}/notes` lists `AgentTransactionNote`; `POST /bas/sessions/{id}/classification-requests/{req_id}/notes` creates `AgentTransactionNote`; `GET /bas/sessions/{id}/transactions/{type}/{doc_id}/{idx}/rounds` calls `get_classification_thread()`; convert domain exceptions to HTTP
- [ ] T048 [US9] Add classification repository methods to `backend/app/modules/bas/classification_repository.py`: `get_idk_items_for_request(request_id, tenant_id)`, `create_agent_note(...)`, `list_notes_for_request(request_id, tenant_id)`, `create_classification_round(...)`, `list_rounds_for_transaction(...)`; all filter by `tenant_id`, use `flush()`
- [ ] T049 [US9] Create `SendBackModal` component in `frontend/src/app/bas/[sessionId]/review/_components/SendBackModal.tsx` — multi-item dialog (shadcn `Dialog`); lists all IDK items with checkbox selection; each selected item shows required `Textarea` for agent comment; submit disabled until all selected items have non-empty comment; on submit: calls `POST /send-back`; shows confirmation with `client_email` and expiry
- [ ] T050 [US9] Update agent review screen to show "Send Back to Client" button when IDK items exist — add `Send Back` button in `frontend/src/app/bas/[sessionId]/review/_components/IdontkKnowItemsSection.tsx` (create if not exists); shows count of IDK items; opens `SendBackModal` on click; add in-app indicator (amber `Badge`) on overridden items that received a late client response
- [ ] T051 [US9] Update portal classify page to display thread history for returned items in `frontend/src/app/portal/classify/[token]/page.tsx` — for round 2+ requests, fetch rounds via API; render conversation thread above response field: client's original IDK response (in muted style) → agent comment (in highlighted callout "Your accountant says:") → new response field; uses `Card` from shadcn/ui
- [ ] T052 [US9] Emit `CLIENT_ANSWERED_ROUND` audit event (T033) in portal submit handler when processing round 2+ responses — verify `round_number > 1` and emit with `{request_id, round_number, client_response_category}` context

**Checkpoint**: Full multi-round send-back loop functional. Agent can send IDK items back; client receives email with new link; thread history visible on both sides.

---

## Phase 9: User Story 3 — Sync Progress and Status Visibility (Priority: P2)

**Goal**: Tax agent sees real-time progress during sync; post-sync summary persists on BAS session screen.

**Independent Test**: Trigger sync with 10+ items → poll job endpoint → verify `succeeded_count` + `skipped_count` + `failed_count` increments as items are processed (before `completed_at` is set) → verify full results visible after navigation away and return.

- [ ] T053 [P] [US3] Create `WritebackProgressPanel` component in `frontend/src/app/bas/[sessionId]/_components/WritebackProgressPanel.tsx` — shows when job `status=in_progress`; polls `GET /writeback/jobs/{job_id}` every 2 seconds using `useQuery` with `refetchInterval`; displays: `Progress` component showing `(succeeded+skipped+failed) / total`; text counter "X of Y items written"; item-by-item list using shadcn `Badge` for status (green=synced, amber=skipped, red=failed); stops polling when `status` transitions out of `in_progress`
- [ ] T054 [US3] Create `WritebackResultsSummary` component in `frontend/src/app/bas/[sessionId]/_components/WritebackResultsSummary.tsx` — shows when job `status` is `completed`, `partial`, or `failed`; renders summary stats (total synced ✅, skipped ⚠️, failed ❌, duration); each skipped/failed item expandable with `skip_reason`/`error_detail`; persists across navigation (fetched from `GET /writeback/jobs` on session page load)
- [ ] T055 [US3] Integrate progress panel and results summary into BAS session screen — add to `frontend/src/app/bas/[sessionId]/page.tsx` (or its parent layout): fetch latest writeback job for session on page load; show `WritebackProgressPanel` if `in_progress`; show `WritebackResultsSummary` if terminal state; show `SyncToXeroButton` when session has unsynced approved overrides; pass `job_id` between components via React state
- [ ] T056 [US3] Add `approved_unsynced_count` to BAS session response schema — in `backend/app/modules/bas/schemas.py`, add field to the session detail response; compute via query: count `TaxCodeOverride` where `status=approved` and `writeback_status=pending_sync` for session

**Checkpoint**: Real-time progress visible during sync. Results summary persists. Tax agent never needs to contact support to understand what happened.

---

## Phase 10: User Story 4 — Partial Retry for Failed Items (Priority: P2)

**Goal**: Tax agent can retry only previously failed items, leaving already-successful items untouched.

**Independent Test**: Create job where 2 of 5 items failed → call `POST /writeback/jobs/{job_id}/retry` → verify new job created with only 2 items → verify original 3 success items have `writeback_status=synced` unchanged.

- [ ] T057 [P] [US4] Implement `retry_failed_items(job_id, triggered_by, tenant_id, db)` in `backend/app/modules/integrations/xero/writeback_service.py` — load job; raise `WritebackError("no_failed_items")` if `failed_count=0`; raise 409 if another job `in_progress` for same session; get `XeroWritebackItem` records with `status=failed`; create new `XeroWritebackJob` with same session/connection; create new `XeroWritebackItem` per failed doc from original; mark original items' `TaxCodeOverride` records as `writeback_status=pending_sync` (reset); enqueue `process_writeback_job` task; emit `WRITEBACK_RETRY_INITIATED` audit event; return new job
- [ ] T058 [US4] Add `POST /bas/sessions/{id}/writeback/jobs/{job_id}/retry` endpoint to `backend/app/modules/bas/router.py` — calls `retry_failed_items()`; returns 202 `WritebackJobResponse`; 400 if no failed items; 409 if in-progress conflict
- [ ] T059 [US4] Add "Retry Failed Items" button to `WritebackResultsSummary` in `frontend/src/app/bas/[sessionId]/_components/WritebackResultsSummary.tsx` — visible only when `failed_count > 0`; calls `POST /retry`; on success: replaces current summary with new `WritebackProgressPanel` for new job; button text "Retry N failed items"
- [ ] T060 [US4] Verify idempotency guard in `process_writeback_job` covers retry scenario — when processing items from a retry job, items from the *original* job that had `status=success` are excluded because their `TaxCodeOverride.writeback_status=synced` (not `pending_sync`); add explicit log statement confirming skip

**Checkpoint**: Failed items can be retried precisely. Successful items never double-written.

---

## Phase 11: User Story 8 — Agent Adds a Note When Sending Classification Request (Priority: P2)

**Goal**: Tax agent can add a per-transaction note (not just global message) when creating a classification request; client sees it on the portal.

**Independent Test**: Agent creates classification request with per-transaction note on item A → client opens portal → verify note appears next to item A as "Your accountant says: [note]" → items without notes show no note section.

- [ ] T061 [P] [US8] Add per-transaction note creation to classification request creation flow in `backend/app/modules/bas/classification_service.py` `create_request()` method — accept optional `notes: list[AgentNoteCreate]` in request schema; create `AgentTransactionNote` records with `is_send_back_comment=false` for each; associate with newly created `ClassificationRequest`
- [ ] T062 [US8] Add `AgentNoteField` component to classification request builder in `frontend/src/app/bas/[sessionId]/_components/AgentNoteField.tsx` — optional `Textarea` below each transaction in the send-list; placeholder "Add a note for your client (optional)"; character limit 1000; state managed in parent `useCreateClassificationRequest` hook; included in `POST /classification-requests` payload as `notes[]`
- [ ] T063 [US8] Fetch and display per-transaction agent notes on portal in `frontend/src/app/portal/classify/[token]/_components/ClassificationItem.tsx` — for each transaction, check for `AgentTransactionNote` with `is_send_back_comment=false`; if exists, render amber callout card: "Your accountant says: [note_text]" using `Card` from shadcn/ui above the response options; if no note, render nothing (no empty card)
- [ ] T064 [US8] Ensure notes API is called in portal token validation — include `AgentTransactionNote` records in portal session payload (via `GET /portal/classify/{token}/session`); add `notes` array to each `ClientClassification` item in the portal response schema

**Checkpoint**: Agents can add contextual notes. Clients see targeted guidance. Empty-note sections not rendered.

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Integration tests, edge cases, and validation of end-to-end scenarios.

- [ ] T065 [P] Write contract tests for Xero write-back adapter in `backend/tests/contract/adapters/test_xero_writeback_adapter.py` — test `update_invoice`, `update_bank_transaction`, `update_credit_note` against mocked Xero API responses; test 429 → `XeroRateLimitError`, 401 → `XeroAuthError`, 400 "period locked" → correct exception
- [ ] T066 [P] Write integration tests for writeback API in `backend/tests/integration/api/test_writeback.py` — test: trigger with no approved overrides → 400; trigger with valid overrides → 202 job created; get job before task runs → status=pending; retry with no failures → 400; retry with failures → 202 new job; all require `tenant_id` in queries (verify cross-tenant isolation)
- [ ] T067 [P] Write integration tests for classification extensions in `backend/tests/integration/api/test_classification_extensions.py` — test: add note to request; send back IDK items; verify new request has correct `parent_request_id` and `round_number=2`; test IDK with empty description → 400; test submit with unanswered items → 400
- [ ] T068 Write unit tests for document reconstruction in `backend/tests/unit/modules/integrations/xero/test_writeback_document_reconstruction.py` — test: single override applied to 50-item invoice leaves 49 items unchanged; multiple overrides on same invoice all applied in one payload; override for index 0, 1, and 2 of bank transaction; edge case: line_items JSONB is empty list
- [ ] T069 Write E2E test for full writeback journey in `backend/tests/e2e/test_xero_writeback_journey.py` — seed: 1 tenant, BAS session, 3 approved overrides; trigger writeback; poll until complete; assert overrides `writeback_status=synced`; assert audit events present; assert local Xero entities updated
- [ ] T070 Validate `approved_unsynced_count` on BAS session detail — run `uv run pytest` and `cd frontend && npm run lint && npx tsc --noEmit` to verify no regressions; fix any type errors in generated schemas
- [ ] T071 Register `xero_writeback` Celery queue in `backend/app/tasks/celery_app.py` — add `"xero_writeback"` to task routes config; verify worker can be started with `-Q xero_writeback` flag
- [ ] T072 Update `specs/ROADMAP.md` — mark spec `049-xero-taxcode-sync` as `✅ Completed` (or current status); update "Recent Changes" section in `CLAUDE.md` to reflect new tables and modules added

---

---

## Phase 15: User Story 10 — View and Assign Tax Codes per Line Item on Split Bank Transactions (Priority: P1)

**Goal**: Tax agent sees individual line items for multi-split bank transactions in the resolution panel and can override each independently.

**Independent Test**: Seed a `XeroBankTransaction` with 3 line items in `line_items` JSONB and 3 corresponding `TaxCodeSuggestion` records (index 0, 1, 2). Load `TaxCodeResolutionPanel` → verify the 3 suggestions are grouped under a single collapsible transaction row (not 3 separate flat rows). Override index 1 only → trigger sync → verify only line item 1's `TaxType` changed in the Xero mock payload; items 0 and 2 unchanged.

- [X] T089 Create Alembic migration `add_tax_code_override_split_columns` — adds `line_amount NUMERIC(15,2) NULLABLE`, `line_description TEXT NULLABLE`, `line_account_code VARCHAR(50) NULLABLE`, `is_new_split BOOLEAN NOT NULL DEFAULT FALSE` to `tax_code_overrides` table in `backend/app/migrations/versions/`
- [X] T090 [P] Update `TaxCodeOverride` SQLAlchemy model in `backend/app/modules/bas/models.py` — add the four new mapped columns with correct types and defaults; update `__repr__` if present
- [X] T091 [P] Update `TaxCodeOverrideSchema` and add `TaxCodeOverrideWithSplitSchema` in `backend/app/modules/bas/schemas.py` — include `line_amount`, `line_description`, `line_account_code`, `is_new_split` fields (all optional); add `SplitCreateRequest` and `SplitUpdateRequest` schemas matching `contracts/splits.yaml`; add `SplitValidationError` response schema
- [X] T092 [P] [US10] Add split repository methods to `backend/app/modules/bas/repository.py`: `get_overrides_for_transaction(source_id, tenant_id, db)` — returns all active `TaxCodeOverride` records for a given `source_id` ordered by `line_item_index`; `get_transaction_total(source_id, tenant_id, db)` — fetches `XeroBankTransaction.total_amount`; all queries filter by `tenant_id`, use `flush()` not `commit()`
- [X] T093 [US10] Implement split service methods in `backend/app/modules/bas/tax_code_service.py`: `_validate_split_balance(source_id, tenant_id, db)` — sums `line_amount` for all active overrides on `source_id` where `line_amount IS NOT NULL`; raises `SplitAmountMismatchError(expected, actual)` if sum ≠ transaction total; `create_split_override(session_id, source_id, line_item_index, override_tax_type, line_amount, line_description, line_account_code, applied_by, tenant_id, db)` — validates `source_type=bank_transaction`; validates `override_tax_type` against `VALID_TAX_TYPES`; creates `TaxCodeOverride` with `is_new_split=True`, `suggestion_id=None`; calls `_validate_split_balance` after insert; `update_split_override(override_id, tenant_id, db, **fields)` — updates non-null fields; re-validates balance; `delete_split_override(override_id, tenant_id, db)` — sets `is_active=False`; re-validates balance; add `SplitAmountMismatchError` to `backend/app/modules/bas/exceptions.py` and map to 422 in router
- [X] T094 [US10] Add split endpoints to `backend/app/modules/bas/router.py`: `GET /sessions/{session_id}/bank-transactions/{source_id}/splits` → `get_overrides_for_transaction()`; `POST /sessions/{session_id}/bank-transactions/{source_id}/splits` → `create_split_override()` returns 201; `PATCH /sessions/{session_id}/bank-transactions/{source_id}/splits/{override_id}` → `update_split_override()`; `DELETE /sessions/{session_id}/bank-transactions/{source_id}/splits/{override_id}` → `delete_split_override()` returns 204; convert `SplitAmountMismatchError` to HTTP 422 with `{"detail": "split_amount_mismatch", "expected_total": ..., "actual_total": ...}`
- [X] T095 [P] [US10] Add split API functions to `frontend/src/lib/bas.ts`: `listTransactionSplits(sessionId, sourceId, token)`, `createSplit(sessionId, sourceId, body, token)`, `updateSplit(sessionId, sourceId, overrideId, body, token)`, `deleteSplit(sessionId, sourceId, overrideId, token)` — all use `apiClient.post/patch/delete` with `Authorization: Bearer {token}` header; add `TaxCodeOverrideWithSplit` TypeScript type with all split fields
- [X] T096 [US10] Refactor `TaxCodeResolutionPanel` in `frontend/src/components/bas/TaxCodeResolutionPanel.tsx` to group suggestions by `source_id` — compute `transactionGroups: Map<string, TaxCodeSuggestion[]>` from the suggestion array; for each group: if single entry with no pending splits → render existing `TaxCodeSuggestionCard` unchanged; if multiple entries OR group has associated splits → render new `TransactionLineItemGroup` component; pass `xeroSyncBadgeFor` into group component; preserve existing confidence-tier accordion structure (group parent row goes into the tier of its highest-priority line item)
- [X] T097 [US10] Create `TransactionLineItemGroup` component in `frontend/src/components/bas/TransactionLineItemGroup.tsx` — collapsible parent row (shadcn `Collapsible`) showing: transaction date, total amount, contact name, aggregate Xero status badge (computed from child rows: all synced → "Xero ✓"; any syncing → "Syncing…"; any failed → "Xero ✗ (N)"; any pending split → "Pending split" amber badge); child rows render `TaxCodeSuggestionCard` per line item with `line_item_index` label ("Line 1", "Line 2", …); expanded by default if any child is pending or unresolved

**Checkpoint**: Multi-line bank transactions show grouped in the resolution panel with per-line-item override capability. Single-line transactions unchanged.

---

## Phase 16: User Story 11 — Create and Edit Splits on Bank Transactions (Priority: P2)

**Goal**: Tax agent can split a single-line bank transaction into multiple line items with different amounts and tax codes; syncing writes the full new split structure to Xero.

**Independent Test**: Create a single-line `XeroBankTransaction` (total $1,200). In `TransactionLineItemGroup`, click "Add Split" → enter $800/G11 and $400/BASEXCLUDED → verify balance indicator shows $1,200 = $1,200 ✅ → trigger sync → verify Xero mock receives `LineItems` array with 2 entries: `{LineAmount: 800, TaxType: "G11"}` and `{LineAmount: 400, TaxType: "BASEXCLUDED"}`.

- [X] T098 [P] [US11] Extend `apply_overrides_to_line_items` in `backend/app/modules/integrations/xero/writeback_service.py` — add two-mode handling: (1) `is_new_split=False` (existing behaviour): patch `TaxType`; additionally set `LineAmount`, `Description`, `AccountCode` from override if non-null; (2) `is_new_split=True`: after all override-mode patches, insert new line item entries at the specified indexes ordered by `line_item_index`; each new entry has `TaxType`, `LineAmount`, and optionally `Description`/`AccountCode`; omit `TaxAmount` from new entries; add `validate_balance: bool = False` and `expected_total: Decimal | None = None` parameters — when True, after reconstruction assert `sum(item.get("LineAmount", 0) for item in result) == expected_total`; raise `ValueError("split_amount_mismatch")` if not balanced
- [X] T099 [US11] Update `process_writeback_job` in `backend/app/tasks/xero_writeback.py` — detect if any overrides for a document have `is_new_split=True`; if so, call `apply_overrides_to_line_items(..., validate_balance=True, expected_total=local_entity.total_amount)`; catch `ValueError("split_amount_mismatch")` and skip document with `skip_reason="split_amount_mismatch"`; update `XeroWritebackSkipReason` enum to include `SPLIT_AMOUNT_MISMATCH = "split_amount_mismatch"` in `writeback_models.py`
- [X] T100 [P] [US11] Create `SplitCreationForm` component in `frontend/src/components/bas/SplitCreationForm.tsx` — inline form (no modal) that appears below a transaction's line items when "Add Split" is clicked; renders existing line items read-only (with their current amounts and tax codes); renders editable rows for each agent-defined split: `Input` for `LineAmount` (numeric, required), `Select` for tax code (populated from org tax types), optional `Input` for description; "Add another split" button adds a new editable row; "Remove" button on each agent-defined row (disabled if only one agent-defined row remains); displays `SplitBalanceIndicator`; "Save splits" button disabled if unbalanced; on save: calls `createSplit()` / `updateSplit()` / `deleteSplit()` for each changed row; uses shadcn `Input`, `Select`, `Button`, `Label`
- [X] T101 [P] [US11] Create `SplitBalanceIndicator` component in `frontend/src/components/bas/SplitBalanceIndicator.tsx` — shows running total of all split amounts vs. transaction total; green checkmark + "Balanced ($1,200.00)" when equal; red warning + "Unbalanced — $1,050.00 of $1,200.00 assigned ($150.00 remaining)" when not equal; uses CSS variable tokens (no hardcoded hex); re-renders on every amount field change
- [X] T102 [US11] Integrate `SplitCreationForm` into `TransactionLineItemGroup` in `frontend/src/components/bas/TransactionLineItemGroup.tsx` — add "Add Split" `Button` (outline variant) at bottom of child rows; only shown for `source_type=bank_transaction` single-line transactions or those with existing agent splits; toggles `SplitCreationForm` open/closed; on form save: refetch splits via `listTransactionSplits()` and re-render child rows; unsaved agent splits show amber "Pending" `Badge` next to line item index label
- [X] T103 [US11] Add "Pending split" aggregate status to `TransactionLineItemGroup` parent row — when any child override has `is_new_split=True` and `writeback_status=pending_sync`, the parent row aggregate badge shows amber "Pending split" (distinct from "Syncing…" which is for active job); once synced, badge transitions to "Xero ✓" consistent with other line items
- [X] T104 [P] [US11] Write unit tests for extended `apply_overrides_to_line_items` in `backend/tests/unit/tasks/test_xero_writeback.py` — add test class `TestApplyOverridesWithSplits`: test new-split insertion at index 1 of single-line transaction; test mixed (override index 0 + new split index 1); test balance validation passes when sum == total; test `ValueError` raised when sum ≠ total; test new split entry does not include TaxAmount key; test optional fields (description, account_code) populated correctly

**Checkpoint**: Tax agent can create splits on single-line transactions. Split structure written to Xero correctly. Balance enforced client-side and server-side.

---

## Dependencies (Story Completion Order)

```
Phase 2 (Foundational)
  └── US1 (Core writeback)
        ├── US2 (Non-editable handling) — adds pre-flight layer to US1 task
        ├── US5 (Audit trail) — adds audit_event() calls throughout
        └── US3 (Progress visibility) — frontend layer over US1 data
              └── US4 (Retry) — new endpoint + service method, uses job data

Phase 2 (Foundational) + Phase 6-7 (portal validation)
  └── US6 (IDK description) — server + portal change, independent of writeback
  └── US7 (All-questions gate) — server + portal change, independent of writeback
        └── US9 (Send-back) — builds on IDK concept; adds round model + send-back service
              └── US8 (Agent notes) — reuses AgentTransactionNote model from US9

T089-T091 (split columns migration + model) — prerequisite for US10 and US11
  └── US10 (View line items) — T076-T081: split API + frontend grouping
        └── US11 (Create/edit splits) — T098-T104: two-mode writeback + split UI
```

**Parallel opportunities per story**:
- US1: T013 + T014 (service helpers) can run parallel to T006 (models) and T009 (client)
- US2: T024 (pre-flight logic) runs parallel to T025 (task integration) being written
- US5: T029 (constants) runs parallel to T030-T032 (emit calls)
- US6: T034 (server validation) runs parallel to T035-T036 (frontend)
- US7: T038 (server validation) runs parallel to T039-T040 (frontend)
- US9: T042 (models) + T044 (schemas) run parallel; T045 + T046 + T048 can start after T042
- US10: T090 + T091 (model + schema) run parallel to T092 (repo); T095 + T097 (frontend) can start once API is designed
- US11: T098 (backend writeback extension) + T100 + T101 (UI components) all parallel once T089-T091 complete

---

## Implementation Strategy

**MVP Scope (Phase 2 + US1 + US5 minimal)**:
- Complete Phase 2 (foundational) + T015-T022 (Celery task + BAS router) + T023 (button)
- Add T029-T032 for audit trail (compliance requirement, must be P1)
- Delivers: functional "Sync to Xero" with audit trail — the core P1 feature

**MVP excludes** (safe to defer to second pass):
- US3 progress panel (polling endpoint works; frontend can be simple)
- US4 retry UI (retry endpoint works; button can be added)
- US8 agent notes (non-blocking, US9 models serve as prerequisite)

**Recommended implementation order**:
1. Phase 2 (all foundational tasks) — single PR
2. US1 + US2 + US5 — single PR (core writeback with audit)
3. US6 + US7 — single PR (portal validation)
4. US9 + US8 — single PR (send-back loop)
5. US3 + US4 — single PR (polish + progress UI)
6. Phase 12 (tests + polish) — single PR

---

## Summary

| Metric | Value |
|--------|-------|
| Total tasks | 105 (T001–T104 + T013a) |
| Phase 2 (Foundational) | 12 tasks |
| US1 (Sync to Xero) | 12 tasks (incl. T013a: tax rate validation) |
| US2 (Non-editable) | 5 tasks |
| US5 (Audit trail) | 5 tasks |
| US6 (IDK description) | 4 tasks |
| US7 (All-questions gate) | 4 tasks |
| US9 (Send-back loop) | 11 tasks |
| US3 (Progress visibility) | 4 tasks |
| US4 (Retry) | 4 tasks |
| US8 (Agent notes) | 4 tasks |
| Phase 12 (Polish) | 8 tasks |
| US10 (View line items per split) | 9 tasks (T089–T097) |
| US11 (Create/edit splits) | 7 tasks (T098–T104) |
| Parallelizable tasks [P] | 26 tasks |
| New files | 14 backend + 9 frontend |
| Modified files | 8 backend + 4 frontend |
| DB migrations | 5 |

---

## Phase 13: Reliability Fixes (2026-04-06) ✅ COMPLETE

**Goal**: Fix four UX and reliability issues discovered during implementation: stale tax type list in override dropdown, unclear Apply & Recalculate purpose, sync progress disconnected from table, and override lifecycle bug preventing sync without a prior Apply & Recalculate.

- [x] T074 [P] Add `GET /api/v1/clients/{connection_id}/xero/tax-rates` endpoint to `backend/app/modules/bas/router.py` — fetches active Xero tax rates for the connected org via `xero_client.get_tax_rates()`; returns `{tax_types: [{tax_type, name}]}` filtered to `status=ACTIVE`; falls back to empty list on error
- [x] T075 [P] Add `fetchOrgTaxTypes(token, connectionId)` to `frontend/src/lib/bas.ts` — calls the new endpoint, returns org-specific tax type list; used by `TaxCodeSuggestionCard`
- [x] T076 [P] Update `TaxCodeSuggestionCard` override dropdown to fetch org-specific tax types on first open — replaces `VALID_TAX_TYPES` hardcoded list with fetched org list; falls back to `VALID_TAX_TYPES` if fetch fails; shows "Loading…" placeholder during fetch
- [x] T077 [P] Add tooltip and context-sensitive text to "Apply & Recalculate" button in `TaxCodeBulkActions` — tooltip clarifies this updates BAS figures (G1–G11) for ATO lodgement, not a prerequisite for Xero sync; when all resolved and recalculation pending, shows "All resolved — recalculate BAS figures before lodgement"
- [x] T078 Fix `approve_suggestion()` in `tax_code_service.py` to create `TaxCodeOverride(writeback_status=pending_sync)` immediately after updating suggestion status — uses `get_active_override()` guard to prevent duplicates
- [x] T079 Fix `override_suggestion()` in `tax_code_service.py` to create `TaxCodeOverride(writeback_status=pending_sync)` immediately after deactivating the old override — decouples override creation from `apply_and_recalculate`
- [x] T080 Fix `bulk_approve_suggestions()` in `tax_code_service.py` to create `TaxCodeOverride` records immediately for each approved suggestion — same `get_active_override()` guard pattern
- [x] T081 Remove `WritebackProgressPanel` and `WritebackResultsSummary` blocks from `TaxCodeResolutionPanel` accordion content — move polling logic inline as a `useEffect`; per-row "Syncing…" amber badge shown in `xeroSyncBadgeFor` during active job; compact retry one-liner below table when `failed_count > 0`
- [x] T082 Fix `selectedSession` staleness in `BASTab` — useEffect that populates `selectedSession` from `sessions` now re-syncs on every `sessions` update (removed `!selectedSession` guard); ensures `approved_unsynced_count` is fresh after background `fetchSessions()` calls
- [x] T083 Fix Sync button permanently hidden by completed job — removed `!completedWritebackJob` condition; button now shows whenever `approvedUnsyncedCount > 0` and no active job
- [x] T084 Switch `TaxCodeResolutionPanel` accordion to controlled state — `useState(['high', 'review', 'manual', 'resolved'])` replaces uncontrolled `defaultValue`; `useEffect` auto-opens `'resolved'` when sync state changes; Resolved section always visible
- [x] T085 Prevent full-page flicker on background session refresh — `fetchSessions()` in `BASTab` only sets `isLoading(true)` on initial load (`hasLoadedSessionsRef`); subsequent calls are silent background refreshes that keep `TaxCodeResolutionPanel` mounted
