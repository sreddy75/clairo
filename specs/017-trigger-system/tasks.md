# Tasks: Trigger System (Spec 017)

**Input**: Design documents from `/specs/017-trigger-system/`
**Prerequisites**: plan.md (required), spec.md (required)
**Branch**: `feature/017-trigger-system`

---

## Implementation Status

| Phase | Status | Tasks |
|-------|--------|-------|
| Phase 0: Git Setup | ✅ Complete | T000 |
| Phase 1: Backend Model | ✅ Complete | T001-T004 |
| Phase 2: Trigger Evaluators | ✅ Complete | T005-T008 |
| Phase 3: Trigger Executor | ✅ Complete | T009-T012 |
| Phase 4: Celery Integration | ✅ Complete | T013-T016 |
| Phase 5: API Endpoints | ✅ Complete | T017-T020 |
| Phase 6: Default Triggers & Seeding | ✅ Complete | T021-T023 |
| Phase 7: Polish | ✅ Complete | T024-T026 |
| Phase 8: Admin UI | ✅ Complete | T027-T031 |
| Phase FINAL: PR & Merge | ✅ Complete | TFINAL |

**Last Updated**: 2025-12-31
**Status**: COMPLETE

---

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)

---

## Phase 0: Git Setup (REQUIRED)

**Purpose**: Create feature branch before any implementation

- [x] T000 Create feature branch from main
  - Run: `git checkout main && git pull origin main`
  - Run: `git checkout -b feature/017-trigger-system`
  - Verify: You are now on the feature branch

---

## Phase 1: Backend Model

**Purpose**: Database models and schemas for triggers

- [ ] T001 Create triggers module structure
  - Create: `backend/app/modules/triggers/__init__.py`
  - Create: `backend/app/modules/triggers/models.py`
  - Create: `backend/app/modules/triggers/schemas.py`
  - Create: `backend/app/modules/triggers/service.py`
  - Create: `backend/app/modules/triggers/router.py`

- [ ] T002 Create database migration
  - Create: `backend/alembic/versions/021_triggers.py`
  - Table: `triggers` with all fields from plan.md
  - Table: `trigger_executions` for execution history
  - Indexes: tenant_id, trigger_type, status, last_executed_at
  - RLS: Enable row level security

- [ ] T003 Implement Trigger and TriggerExecution models
  - File: `backend/app/modules/triggers/models.py`
  - Enums: `TriggerType` (data_threshold, time_scheduled, event_based)
  - Enums: `TriggerStatus` (active, disabled, error)
  - Model: `Trigger` with config JSON, target_analyzers, dedup settings
  - Model: `TriggerExecution` with results tracking

- [ ] T004 Implement Pydantic schemas
  - File: `backend/app/modules/triggers/schemas.py`
  - `TriggerCreate` - name, type, config, target_analyzers
  - `TriggerUpdate` - all optional fields
  - `TriggerResponse` - full response with execution stats
  - `TriggerExecutionResponse` - execution history record
  - `TriggerListResponse` - paginated list

**Checkpoint**: Models and schemas defined, migration ready

---

## Phase 2: Trigger Evaluators

**Purpose**: Condition evaluators for each trigger type

- [ ] T005 Create evaluators module structure
  - Create: `backend/app/modules/triggers/evaluators/__init__.py`
  - Create: `backend/app/modules/triggers/evaluators/base.py`

- [ ] T006 [P] Implement data threshold evaluator
  - Create: `backend/app/modules/triggers/evaluators/data_triggers.py`
  - Class: `DataThresholdEvaluator`
  - Methods: `evaluate(client_id, config)` → bool
  - Support metrics: revenue_ytd, ar_overdue_total, unreconciled_count
  - Support operators: gt, gte, lt, lte, eq

- [ ] T007 [P] Implement time-based evaluator
  - Create: `backend/app/modules/triggers/evaluators/time_triggers.py`
  - Class: `TimeScheduleEvaluator`
  - Methods: `should_run(trigger, now)` → bool
  - Support: cron expressions, timezone handling
  - Support: days_before_deadline for BAS reminders

- [ ] T008 [P] Implement event-based evaluator
  - Create: `backend/app/modules/triggers/evaluators/event_triggers.py`
  - Class: `EventTriggerEvaluator`
  - Methods: `matches_event(trigger, event_type, payload)` → bool
  - Support events: xero_connection_created, bas_lodged, xero_sync_complete

**Checkpoint**: All three evaluator types implemented and testable

---

## Phase 3: Trigger Executor

**Purpose**: Core execution engine that runs triggers and creates insights

- [ ] T009 Implement TriggerExecutor class
  - Create: `backend/app/modules/triggers/executor.py`
  - Class: `TriggerExecutor`
  - Method: `execute(trigger, client_ids)` → TriggerExecution
  - Integrate with existing `InsightGenerator`

- [ ] T010 Implement three-layer deduplication logic
  - File: `backend/app/modules/triggers/executor.py`
  - Layer 1: `_similar_insight_exists(client_id, category, hours=24)` - Cross-trigger dedup
  - Layer 2: Existing InsightGenerator dedup (7-day content-based)
  - Layer 3: `_trigger_recently_fired(trigger, client_id)` - Per-trigger throttle
  - Check order: Layer 3 → Layer 1 → Layer 2 (most specific to least)
  - Return early if any layer blocks to save DB queries

- [ ] T011 Implement execution recording
  - File: `backend/app/modules/triggers/executor.py`
  - Create TriggerExecution record on start
  - Update with results (clients_evaluated, insights_created, etc.)
  - Track partial failures

- [ ] T012 Implement error handling and auto-disable
  - File: `backend/app/modules/triggers/executor.py`
  - Increment consecutive_failures on error
  - Auto-disable trigger after 3 consecutive failures
  - Log errors with full context

**Checkpoint**: Executor can run triggers and create insights

---

## Phase 4: Celery Integration

**Purpose**: Background task integration for trigger execution

- [ ] T013 Create trigger Celery tasks
  - Create: `backend/app/tasks/trigger_tasks.py`
  - Task: `evaluate_data_triggers(tenant_id, client_id)`
  - Task: `execute_scheduled_trigger(trigger_id)`
  - Task: `handle_business_event(event_type, payload)`
  - Task: `run_time_triggers()` - for Celery Beat

- [ ] T014 Integrate with Xero sync task
  - Update: `backend/app/tasks/xero_tasks.py`
  - Call `evaluate_data_triggers.delay()` after sync completes
  - Pass tenant_id and client_id (connection_id)

- [ ] T015 Configure Celery Beat schedule
  - Update: `backend/app/core/celery_config.py` (or equivalent)
  - Add daily trigger check at 6am Sydney time
  - Add BAS deadline check at 9am Sydney time

- [ ] T016 Implement event bus integration
  - Update: `backend/app/modules/bas/service.py` (lodgement)
  - Emit event when BAS is lodged
  - Call `handle_business_event.delay()` with event payload

**Checkpoint**: Triggers fire automatically via Celery

---

## Phase 5: API Endpoints

**Purpose**: REST API for trigger management

- [ ] T017 Implement TriggerService
  - File: `backend/app/modules/triggers/service.py`
  - `create()` - create custom trigger
  - `get_by_id()` - get trigger with stats
  - `list()` - list triggers with filters
  - `update()` - update trigger config
  - `delete()` - delete trigger
  - `enable()` / `disable()` - toggle status
  - `get_executions()` - get execution history

- [ ] T018 Implement router endpoints
  - File: `backend/app/modules/triggers/router.py`
  - `GET /api/v1/triggers` - list triggers
  - `POST /api/v1/triggers` - create trigger
  - `GET /api/v1/triggers/{id}` - get trigger
  - `PATCH /api/v1/triggers/{id}` - update trigger
  - `DELETE /api/v1/triggers/{id}` - delete trigger

- [ ] T019 Implement trigger action endpoints
  - File: `backend/app/modules/triggers/router.py`
  - `POST /api/v1/triggers/{id}/enable` - enable
  - `POST /api/v1/triggers/{id}/disable` - disable
  - `POST /api/v1/triggers/{id}/test` - dry run test

- [ ] T020 Register router in main app
  - File: `backend/app/main.py`
  - Import and include triggers router

**Checkpoint**: API endpoints working, can manage triggers via REST

---

## Phase 6: Default Triggers & Seeding

**Purpose**: Create default triggers for new tenants

- [ ] T021 Define default trigger configurations
  - File: `backend/app/modules/triggers/defaults.py`
  - Define DEFAULT_TRIGGERS list from plan.md
  - Include all 7 default triggers (3 data, 2 time, 2 event)

- [ ] T022 Implement trigger seeding service
  - File: `backend/app/modules/triggers/service.py`
  - Method: `seed_defaults(tenant_id)` - create defaults for tenant
  - Check for existing triggers to avoid duplicates
  - Called when new tenant is created

- [ ] T023 Add seed triggers to tenant creation flow
  - Update tenant creation to call seed_defaults
  - Or create Alembic data migration for existing tenants

**Checkpoint**: New tenants get default triggers automatically

---

## Phase 7: Polish

**Purpose**: Error handling, logging, documentation

- [ ] T024 Add audit logging for trigger operations
  - Log trigger.executed events
  - Log trigger.failed events
  - Log trigger.disabled/enabled events
  - Include tenant_id, trigger_id, execution details

- [ ] T025 Add comprehensive error handling
  - Graceful handling of missing client data
  - Skip inactive/disconnected clients with warning
  - Retry logic for transient failures

- [ ] T026 Run lint and fix issues
  - Backend: `uv run ruff check .`
  - Backend: `uv run mypy .`

**Checkpoint**: Production-ready with proper logging

---

## Phase 8: Admin UI

**Purpose**: Frontend UI for trigger management

- [x] T027 Create TriggerFormModal component
  - Create: `frontend/src/components/triggers/TriggerFormModal.tsx`
  - Dynamic config fields based on trigger type
  - Data threshold: metric, operator, threshold inputs
  - Time scheduled: cron expression, timezone, days before deadline
  - Event-based: event type selection
  - Target analyzer multi-select
  - Deduplication window selector

- [x] T028 Add preset templates
  - 6 preset templates for common use cases
  - Cash Crisis Alert, Large Payables Warning
  - GST Registration Alert, BAS Deadline Reminder
  - Monthly Health Check, New Client Onboarding
  - One-click apply to pre-fill form

- [x] T029 Update triggers admin page
  - Add "Create Trigger" button in header
  - Add edit button (pencil icon) on each trigger
  - Add delete button (trash) for custom triggers
  - System defaults cannot be deleted

- [x] T030 Fix API route ordering
  - Move `/executions` endpoint before `/{trigger_id}`
  - Prevents "executions" being parsed as UUID

- [x] T031 Fix datetime timezone issues
  - Update executor.py: use `datetime.now(UTC)` instead of `utcnow()`
  - Update service.py: fix timezone-aware comparisons
  - Prevents "offset-naive and offset-aware datetime" errors

**Checkpoint**: Full CRUD UI for triggers, accountants can create custom triggers

---

## Phase FINAL: PR & Merge (REQUIRED)

- [x] TFINAL-1 Run all tests and linting
  - Backend: `uv run ruff check .`
  - Backend: `uv run pytest`

- [x] TFINAL-2 Commit all changes
  - Meaningful commit message
  - Reference spec 017

- [x] TFINAL-3 Merge to main
  - `git checkout main && git pull origin main`
  - `git merge feature/017-trigger-system --no-ff`

- [x] TFINAL-4 Push to remote
  - `git push origin main`

- [x] TFINAL-5 Update ROADMAP.md
  - Mark Spec 017 as COMPLETE
  - Update current focus to Spec 018

---

## Dependencies

```
Phase 0 (Git) → Phase 1 (Model) → Phase 2 (Evaluators) → Phase 3 (Executor)
                                                              ↓
                                              Phase 4 (Celery Integration)
                                                              ↓
                                              Phase 5 (API Endpoints)
                                                              ↓
                                              Phase 6 (Default Triggers)
                                                              ↓
                                              Phase 7 (Polish)
                                                              ↓
                                              Phase 8 (Admin UI)
                                                              ↓
                                              Phase FINAL (Merge)
```

---

## Notes

- Trigger system builds on existing InsightGenerator from Spec 016
- Data triggers hook into Xero sync completion
- Time triggers use Celery Beat scheduler
- Event triggers integrate via event bus pattern
- All triggers respect deduplication to prevent insight spam
- Default triggers seeded for all tenants
- Admin UI allows accountants to create custom triggers with:
  - 6 preset templates for common patterns
  - Full config options per trigger type
  - Edit/delete for custom triggers (system defaults protected)
