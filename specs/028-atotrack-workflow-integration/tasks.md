# Implementation Tasks: ATOtrack Workflow Integration

**Feature**: 028-atotrack-workflow-integration
**Branch**: `028-atotrack-workflow-integration`
**Total Tasks**: 68
**Estimated Phases**: 10

---

## Overview

This task list implements ATOtrack workflow integration - automatic task creation, insight generation, deadline notifications, AI response drafting, and practice management sync.

### User Stories (from spec.md)

| Story | Priority | Description |
|-------|----------|-------------|
| US1 | P1 | Automatic Task Creation |
| US2 | P1 | Automatic Insight Generation |
| US3 | P1 | Deadline Notifications |
| US4 | P1 | ATOtrack Dashboard |
| US5 | P2 | AI Response Drafting |
| US6 | P1 | Mark as Resolved |
| US7 | P3 | Practice Management Integration |

### Dependencies

```
US1 (Tasks) ──┐
              ├──► US6 (Resolve) ──► US4 (Dashboard)
US2 (Insights)┘
                                          │
US3 (Notifications) ──────────────────────┘

US5 (Drafting) - Independent, P2
US7 (PM Integration) - Independent, P3
```

---

## Phase 1: Setup (4 tasks)

**Goal**: Create ATOtrack submodule structure

- [ ] T001 Create atotrack submodule directory in backend/app/modules/email/atotrack/
- [ ] T002 Create atotrack __init__.py with module exports in backend/app/modules/email/atotrack/__init__.py
- [ ] T003 Create atotrack dependencies.py for dependency injection in backend/app/modules/email/atotrack/dependencies.py
- [ ] T004 Create test directories for atotrack in backend/tests/unit/modules/email/atotrack/ and backend/tests/integration/api/

---

## Phase 2: Foundational - Shared Components (6 tasks)

**Goal**: Build shared infrastructure for workflow operations

- [ ] T005 Create enums.py with TaskPriority, ResponseDraftType, ResponseDraftStatus, NotificationType in backend/app/modules/email/atotrack/enums.py
- [ ] T006 Create exceptions.py with CorrespondenceNotFoundError, TaskAlreadyExistsError, DraftGenerationError in backend/app/modules/email/atotrack/exceptions.py
- [ ] T007 [P] Extend ATOCorrespondence model with task_id, insight_id, resolved_at, resolved_by fields in backend/app/modules/email/ato_parsing/models.py
- [ ] T008 [P] Create Alembic migration for correspondence extensions in backend/alembic/versions/
- [ ] T009 Create base schemas for workflow operations in backend/app/modules/email/atotrack/schemas.py
- [ ] T010 Register atotrack router in main.py under /api/v1/atotrack prefix in backend/app/main.py

---

## Phase 3: User Story 1 - Automatic Task Creation (9 tasks)

**Goal**: Auto-create tasks from parsed ATO correspondence
**Independent Test**: Parse audit notice → verify task created with 28-day deadline

### Task Rules Engine

- [ ] T011 [US1] Create TaskRule dataclass and TASK_RULES mapping in backend/app/modules/email/atotrack/task_rules.py
- [ ] T012 [US1] Implement get_task_rule() for notice type lookup in backend/app/modules/email/atotrack/task_rules.py
- [ ] T013 [US1] Implement calculate_due_date() with fallback to defaults in backend/app/modules/email/atotrack/task_rules.py
- [ ] T014 [US1] Implement format_task_title() with placeholder substitution in backend/app/modules/email/atotrack/task_rules.py
- [ ] T015 [P] [US1] Write unit tests for task rules in backend/tests/unit/modules/email/atotrack/test_task_rules.py

### Task Creation Service

- [ ] T016 [US1] Create ATOtrackService class with task creation method in backend/app/modules/email/atotrack/service.py
- [ ] T017 [US1] Implement _create_task_if_needed() checking for duplicates in backend/app/modules/email/atotrack/service.py
- [ ] T018 [US1] Add audit logging for task creation events in backend/app/modules/email/atotrack/service.py
- [ ] T019 [US1] Write integration test for task auto-creation in backend/tests/integration/api/test_atotrack.py

---

## Phase 4: User Story 2 - Automatic Insight Generation (8 tasks)

**Goal**: Generate insights from high-priority correspondence
**Independent Test**: Parse penalty notice → verify insight appears with HIGH severity

### Insight Rules Engine

- [ ] T020 [US2] Create InsightRule dataclass and INSIGHT_RULES mapping in backend/app/modules/email/atotrack/insight_rules.py
- [ ] T021 [US2] Implement get_insight_rule() for notice type lookup in backend/app/modules/email/atotrack/insight_rules.py
- [ ] T022 [US2] Implement calculate_severity() with amount-based escalation in backend/app/modules/email/atotrack/insight_rules.py
- [ ] T023 [P] [US2] Write unit tests for insight rules in backend/tests/unit/modules/email/atotrack/test_insight_rules.py

### Insight Creation Service

- [ ] T024 [US2] Implement _create_insight_if_needed() in ATOtrackService in backend/app/modules/email/atotrack/service.py
- [ ] T025 [US2] Add insight action_url linking to correspondence detail in backend/app/modules/email/atotrack/service.py
- [ ] T026 [US2] Add audit logging for insight creation events in backend/app/modules/email/atotrack/service.py
- [ ] T027 [US2] Write integration test for insight auto-creation in backend/tests/integration/api/test_atotrack.py

---

## Phase 5: User Story 3 - Deadline Notifications (7 tasks)

**Goal**: Schedule notifications for approaching deadlines
**Independent Test**: Create correspondence due in 3 days → verify notification sent

### Notification Rules

- [ ] T028 [US3] Create NotificationSchedule dataclass and NOTIFICATION_SCHEDULE in backend/app/modules/email/atotrack/notification_rules.py
- [ ] T029 [US3] Implement calculate_notification_dates() for due date in backend/app/modules/email/atotrack/notification_rules.py
- [ ] T030 [P] [US3] Write unit tests for notification scheduling in backend/tests/unit/modules/email/atotrack/test_notification_rules.py

### Notification Scheduling

- [ ] T031 [US3] Implement _schedule_notifications() in ATOtrackService in backend/app/modules/email/atotrack/service.py
- [ ] T032 [US3] Create email templates for deadline reminders in backend/app/modules/notifications/templates/atotrack/
- [ ] T033 [US3] Add snooze_notifications endpoint in router in backend/app/modules/email/atotrack/router.py
- [ ] T034 [US3] Write integration test for notification scheduling in backend/tests/integration/api/test_atotrack.py

---

## Phase 6: User Story 6 - Mark as Resolved (7 tasks)

**Goal**: Resolve correspondence with cascading updates
**Independent Test**: Mark resolved → verify task completed, insight dismissed, notifications cancelled

### Resolution Flow

- [ ] T035 [US6] Implement resolve_correspondence() in ATOtrackService in backend/app/modules/email/atotrack/service.py
- [ ] T036 [US6] Add task completion logic when resolving in backend/app/modules/email/atotrack/service.py
- [ ] T037 [US6] Add insight dismissal logic when resolving in backend/app/modules/email/atotrack/service.py
- [ ] T038 [US6] Add notification cancellation when resolving in backend/app/modules/email/atotrack/service.py
- [ ] T039 [US6] Create POST /correspondence/{id}/resolve endpoint in backend/app/modules/email/atotrack/router.py
- [ ] T040 [US6] Create POST /correspondence/{id}/reopen endpoint in backend/app/modules/email/atotrack/router.py
- [ ] T041 [US6] Write integration tests for resolve flow in backend/tests/integration/api/test_atotrack.py

---

## Phase 7: User Story 4 - ATOtrack Dashboard (10 tasks)

**Goal**: Dedicated dashboard with summary cards and action items
**Independent Test**: Open ATOtrack → see overdue, due soon, handled, triage counts

### Dashboard Service

- [ ] T042 [US4] Create ATOtrackDashboard service class in backend/app/modules/email/atotrack/dashboard.py
- [ ] T043 [US4] Implement _get_summary_counts() for dashboard cards in backend/app/modules/email/atotrack/dashboard.py
- [ ] T044 [US4] Implement _get_requires_attention() sorted by urgency in backend/app/modules/email/atotrack/dashboard.py
- [ ] T045 [US4] Implement _get_recent_resolved() for recent items in backend/app/modules/email/atotrack/dashboard.py
- [ ] T046 [P] [US4] Add Redis caching for dashboard data (5 min TTL) in backend/app/modules/email/atotrack/dashboard.py

### Dashboard API

- [ ] T047 [US4] Create GET /atotrack/dashboard endpoint in backend/app/modules/email/atotrack/router.py
- [ ] T048 [US4] Create GET /atotrack/correspondence endpoint with filters in backend/app/modules/email/atotrack/router.py
- [ ] T049 [US4] Create GET /atotrack/correspondence/{id} endpoint in backend/app/modules/email/atotrack/router.py
- [ ] T050 [US4] Create GET /atotrack/stats endpoint for analytics in backend/app/modules/email/atotrack/router.py
- [ ] T051 [US4] Write integration tests for dashboard endpoints in backend/tests/integration/api/test_atotrack.py

---

## Phase 8: User Story 5 - AI Response Drafting (9 tasks)

**Goal**: Generate AI response drafts using Claude + RAG
**Independent Test**: Click "Draft Response" on audit notice → AI-generated response appears

### Response Drafter

- [ ] T052 [US5] Create PROMPTS templates for each ResponseDraftType in backend/app/modules/email/atotrack/response_drafter.py
- [ ] T053 [US5] Implement ResponseDrafter class with Claude API in backend/app/modules/email/atotrack/response_drafter.py
- [ ] T054 [US5] Implement _build_rag_query() for relevant context in backend/app/modules/email/atotrack/response_drafter.py
- [ ] T055 [US5] Create ResponseDraft model with generation metadata in backend/app/modules/email/atotrack/models.py
- [ ] T056 [P] [US5] Create Alembic migration for response_drafts table in backend/alembic/versions/

### Drafting API

- [ ] T057 [US5] Create POST /correspondence/{id}/draft endpoint in backend/app/modules/email/atotrack/router.py
- [ ] T058 [US5] Create GET /drafts/{id} endpoint for draft retrieval in backend/app/modules/email/atotrack/router.py
- [ ] T059 [US5] Create GET /drafts/templates endpoint for template list in backend/app/modules/email/atotrack/router.py
- [ ] T060 [US5] Write integration tests for response drafting in backend/tests/integration/api/test_atotrack.py

---

## Phase 9: User Story 7 - Practice Management Integration (6 tasks)

**Goal**: Sync tasks to Karbon and XPM
**Independent Test**: Configure Karbon → ATO task created → appears in Karbon

### PM Clients

- [ ] T061 [US7] Create KarbonClient class with task CRUD in backend/app/modules/email/atotrack/integrations/karbon.py
- [ ] T062 [US7] Create XPMClient class with job CRUD in backend/app/modules/email/atotrack/integrations/xpm.py
- [ ] T063 [US7] Create PMIntegration model for credentials storage in backend/app/modules/email/atotrack/models.py
- [ ] T064 [US7] Create Celery task for async PM sync in backend/app/tasks/pm_sync.py

### PM API

- [ ] T065 [US7] Create POST /integrations/karbon connect endpoint in backend/app/modules/email/atotrack/router.py
- [ ] T066 [US7] Create POST /integrations/xpm connect endpoint in backend/app/modules/email/atotrack/router.py

---

## Phase 10: Polish & Cross-Cutting (2 tasks)

**Goal**: Settings, documentation, final validation

- [ ] T067 Create GET/PATCH /atotrack/settings endpoints in backend/app/modules/email/atotrack/router.py
- [ ] T068 Add API documentation to contracts/atotrack-api.yaml and update quickstart.md

---

## Parallel Execution Guide

### Maximum Parallelism by Phase

| Phase | Parallel Groups |
|-------|-----------------|
| Phase 1 | T001 → T002, T003, T004 |
| Phase 2 | T005, T006, (T007+T008), T009, T010 |
| Phase 3 | T011-T014 → T015, T016-T18 → T19 |
| Phase 4 | T020-T22 → T23, T24-T26 → T27 |
| Phase 5 | T028-T29 → T30, T31-T33 → T34 |
| Phase 6 | T035-T40 → T41 |
| Phase 7 | T042-T45 → T46, T47-T50 → T51 |
| Phase 8 | T052-T54, (T055+T56), T57-T59 → T60 |
| Phase 9 | (T061+T62), T63, T64 → T65+T66 |
| Phase 10 | T067, T68 |

### Independent Work Streams

```
Stream A (Core Workflow): Phase 3 → Phase 4 → Phase 6 → Phase 7
Stream B (Notifications): Phase 5 (can run parallel with Stream A after Phase 2)
Stream C (AI Drafting): Phase 8 (independent after Phase 2)
Stream D (PM Integration): Phase 9 (independent after Phase 2)
```

---

## MVP Scope

**Minimum Viable Product**: User Stories 1, 2, 6, 4 (Phases 1-4, 6-7)

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | T001-T004 | Setup |
| 2 | T005-T010 | Foundational |
| 3 | T011-T019 | Auto Task Creation |
| 4 | T020-T027 | Auto Insight Generation |
| 6 | T035-T041 | Resolve Flow |
| 7 | T042-T051 | Dashboard |

**MVP Task Count**: 41 tasks

**Post-MVP**:
- Phase 5: Notifications (T028-T034)
- Phase 8: AI Drafting (T052-T060)
- Phase 9: PM Integration (T061-T066)
- Phase 10: Polish (T067-T068)

---

## Validation Checklist

- [ ] All 68 tasks follow checklist format
- [ ] Each user story phase is independently testable
- [ ] Dependencies are correctly sequenced
- [ ] Parallel opportunities identified
- [ ] MVP scope defined (41 tasks)
- [ ] File paths specified for all implementation tasks
