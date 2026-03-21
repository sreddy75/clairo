# Tasks: A2UI Agent-Driven Interfaces

**Feature**: 033-a2ui-agent-driven-interfaces
**Branch**: `033-a2ui-agent-driven-interfaces`
**Total Tasks**: 80
**Estimated Phases**: 11

---

## Overview

This task list implements the A2UI Agent-Driven Interfaces feature, enabling AI agents to generate dynamic, context-aware native UIs using a declarative component protocol.

### User Stories (from spec.md)

| Story | Priority | Description |
|-------|----------|-------------|
| US1 | P1 | Dynamic Insight Presentation |
| US2 | P1 | Context-Aware Dashboard |
| US3 | P1 | Camera-First Mobile Document Capture |
| US4 | P2 | Ad-Hoc Query Visualization |
| US5 | P2 | BAS Review Exception Focus |
| US6 | P3 | End-of-Day Summary |

### Dependencies

```
Phase 1 (Setup) ─────────────────────────────────────────────┐
                                                              │
Phase 2 (Foundational: A2UI Core) ───────────────────────────┤
                                                              │
┌─────────────────────────────────────────────────────────────┤
│                                                             │
├── US1 (Insights) ────────────────────────────┐              │
│                                               │              │
├── US2 (Dashboard) ───────────────────────────┤              │
│                                               │              │
├── US3 (Mobile Capture) ──────────────────────┤              │
│                                               │              │
├── US4 (Queries) ─────────────────────────────┤              │
│                                               │              │
├── US5 (BAS Review) ──────────────────────────┤              │
│                                               │              │
└── US6 (Day Summary) ─────────────────────────┘              │
                                                              │
Phase 10 (Polish) ────────────────────────────────────────────┘
```

---

## Phase 0: Git Setup (REQUIRED)

**Purpose**: Feature branch already created by speckit.specify

- [X] T000 Verify on feature branch `033-a2ui-agent-driven-interfaces`
  - Run: `git branch --show-current`
  - Expected: `033-a2ui-agent-driven-interfaces`

---

## Phase 1: Setup (4 tasks)

**Purpose**: Install dependencies and create directory structure

- [X] T001 Create A2UI frontend directory structure at frontend/src/lib/a2ui/
- [X] T002 Create A2UI component directories at frontend/src/components/a2ui/{charts,data,layout,actions,alerts,forms,media,feedback}/
- [X] T003 [P] Create A2UI backend module at backend/app/core/a2ui/
- [X] T004 [P] Add user-agents package for device detection in backend/pyproject.toml

---

## Phase 2: Foundational - A2UI Core (12 tasks)

**Purpose**: Core A2UI infrastructure that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

### Frontend Core

- [X] T005 Create A2UI TypeScript types in frontend/src/lib/a2ui/types.ts
- [X] T006 Create component catalog registry in frontend/src/lib/a2ui/catalog.ts
- [X] T007 Create A2UI data context provider in frontend/src/lib/a2ui/context.tsx
- [X] T008 Create A2UI renderer component in frontend/src/lib/a2ui/renderer.tsx
- [X] T009 Create error fallback component in frontend/src/lib/a2ui/fallback.tsx
- [X] T010 [P] Create useA2UIRenderer hook in frontend/src/hooks/useA2UIRenderer.ts
- [X] T011 [P] Create useDeviceContext hook in frontend/src/hooks/useDeviceContext.ts
- [X] T012 Export A2UI module public API in frontend/src/lib/a2ui/index.ts

### Backend Core

- [X] T013 Create Pydantic A2UI schemas in backend/app/core/a2ui/schemas.py
- [X] T014 Create A2UI response builder in backend/app/core/a2ui/builder.py
- [X] T015 Create device context detection in backend/app/core/a2ui/device.py
- [X] T016 Export A2UI module in backend/app/core/a2ui/__init__.py

**Checkpoint**: A2UI renderer can render a basic message with alert card and action button

---

## Phase 3: User Story 1 - Dynamic Insight Presentation (Priority: P1)

**Goal**: AI agents generate insight UIs with appropriate charts, tables, and actions based on finding severity

**Independent Test**: Fetch `/api/v1/insights/{id}/ui`, pass to A2UIRenderer, verify alert cards, charts, and action buttons render based on severity

### A2UI Components for US1

- [X] T017 [P] [US1] Create AlertCard component in frontend/src/components/a2ui/alerts/AlertCard.tsx
- [X] T018 [P] [US1] Create LineChart component in frontend/src/components/a2ui/charts/LineChart.tsx
- [X] T019 [P] [US1] Create BarChart component in frontend/src/components/a2ui/charts/BarChart.tsx
- [X] T020 [P] [US1] Create StatCard component in frontend/src/components/a2ui/data/StatCard.tsx
- [X] T021 [P] [US1] Create ActionButton component in frontend/src/components/a2ui/actions/ActionButton.tsx
- [X] T022 [P] [US1] Create Accordion component in frontend/src/components/a2ui/layout/Accordion.tsx
- [X] T023 [US1] Register US1 components in catalog at frontend/src/lib/a2ui/catalog.ts

### Backend for US1

- [X] T024 [US1] Create insight A2UI generator in backend/app/modules/insights/a2ui_generator.py
- [X] T025 [US1] Add GET /insights/{id}/ui endpoint in backend/app/modules/insights/router.py

### Integration for US1

- [X] T026 [US1] Integrate A2UIRenderer in insight detail page at frontend/src/app/(protected)/insights/[id]/page.tsx

**Checkpoint**: Viewing an insight shows dynamic UI with severity-appropriate components

---

## Phase 4: User Story 2 - Context-Aware Dashboard (Priority: P1)

**Goal**: Dashboard adapts layout based on time of day, urgency, and workload

**Independent Test**: Fetch `/api/v1/dashboard/ui` at different times, verify layout changes (Monday 9am vs Friday 4pm)

### A2UI Components for US2

- [X] T027 [P] [US2] Create UrgencyBanner component in frontend/src/components/a2ui/alerts/UrgencyBanner.tsx
- [X] T028 [P] [US2] Create Badge component in frontend/src/components/a2ui/alerts/Badge.tsx
- [X] T029 [P] [US2] Create Card component in frontend/src/components/a2ui/layout/Card.tsx
- [X] T030 [P] [US2] Create Timeline component in frontend/src/components/a2ui/layout/Timeline.tsx
- [X] T031 [US2] Register US2 components in catalog at frontend/src/lib/a2ui/catalog.ts

### Backend for US2

- [X] T032 [US2] Create dashboard personalization agent in backend/app/modules/dashboard/a2ui_generator.py
- [X] T033 [US2] Add GET /dashboard/ui endpoint in backend/app/modules/dashboard/router.py

### Integration for US2

- [X] T034 [US2] Integrate A2UIRenderer in dashboard page at frontend/src/app/(protected)/dashboard/page.tsx

**Checkpoint**: Dashboard shows personalized layout based on time and context

---

## Phase 5: User Story 3 - Camera-First Mobile Document Capture (Priority: P1)

**Goal**: Mobile devices show camera capture as primary action, desktop shows file upload

**Independent Test**: Access `/api/v1/portal/requests/{id}/ui` from mobile User-Agent, verify cameraCapture is primary

### A2UI Components for US3

- [X] T035 [P] [US3] Create CameraCapture component in frontend/src/components/a2ui/media/CameraCapture.tsx
- [X] T036 [P] [US3] Create FileUpload component in frontend/src/components/a2ui/media/FileUpload.tsx
- [X] T037 [P] [US3] Create Progress component in frontend/src/components/a2ui/feedback/Progress.tsx
- [X] T038 [US3] Register US3 components in catalog at frontend/src/lib/a2ui/catalog.ts

### Backend for US3

- [ ] T039 [US3] Create document request A2UI generator in backend/app/modules/portal/requests/a2ui_generator.py
  - **BLOCKED**: Requires portal module (Phase E: Business Owner Portal - NOT STARTED)
- [ ] T040 [US3] Add GET /portal/requests/{id}/ui endpoint in backend/app/modules/portal/requests/router.py
  - **BLOCKED**: Requires portal module (Phase E: Business Owner Portal - NOT STARTED)

### Integration for US3

- [ ] T041 [US3] Integrate A2UIRenderer in portal request page at frontend/src/app/portal/requests/[id]/page.tsx
  - **BLOCKED**: Requires portal module (Phase E: Business Owner Portal - NOT STARTED)

**Checkpoint**: Mobile shows camera-first UI, desktop shows file picker

---

## Phase 6: User Story 4 - Ad-Hoc Query Visualization (Priority: P2)

**Goal**: Natural language queries return visual answers with charts, tables, and filters

**Independent Test**: POST to `/api/v1/queries/ui` with "which clients are at risk?", verify data table with filters renders

### A2UI Components for US4

- [X] T042 [P] [US4] Create DataTable component in frontend/src/components/a2ui/data/DataTable.tsx
- [X] T043 [P] [US4] Create FilterBar component in frontend/src/components/a2ui/forms/FilterBar.tsx
- [X] T044 [P] [US4] Create ScatterChart component in frontend/src/components/a2ui/charts/ScatterChart.tsx
- [X] T045 [P] [US4] Create ExportButton component in frontend/src/components/a2ui/actions/ExportButton.tsx
- [X] T046 [P] [US4] Create QueryResult component in frontend/src/components/a2ui/data/QueryResult.tsx
- [X] T047 [US4] Register US4 components in catalog at frontend/src/lib/a2ui/catalog.ts

### Backend for US4

- [ ] T048 [US4] Create query visualization agent in backend/app/modules/agents/query_agent.py
- [ ] T049 [US4] Add POST /queries/ui endpoint in backend/app/modules/queries/router.py

### Integration for US4

- [ ] T050 [US4] Create query interface page at frontend/src/app/(protected)/queries/page.tsx

**Checkpoint**: Natural language query returns appropriate visualization

---

## Phase 7: User Story 5 - BAS Review Exception Focus (Priority: P2)

**Goal**: BAS review shows only anomalies expanded, normal fields collapsed

**Independent Test**: Fetch `/api/v1/bas/{id}/review/ui` for BAS with known anomaly, verify only anomaly expanded

### A2UI Components for US5

- [X] T051 [P] [US5] Create ComparisonTable component in frontend/src/components/a2ui/data/ComparisonTable.tsx
- [X] T052 [P] [US5] Create ApprovalBar component in frontend/src/components/a2ui/actions/ApprovalBar.tsx
- [X] T053 [US5] Register US5 components in catalog at frontend/src/lib/a2ui/catalog.ts

### Backend for US5

- [ ] T054 [US5] Create BAS review A2UI generator in backend/app/modules/bas/a2ui_generator.py
- [ ] T055 [US5] Add GET /bas/{id}/review/ui endpoint in backend/app/modules/bas/router.py

### Integration for US5

- [ ] T056 [US5] Integrate A2UIRenderer in BAS review page at frontend/src/app/(protected)/bas/[id]/review/page.tsx

**Checkpoint**: BAS review shows anomalies expanded, normal fields collapsed

---

## Phase 8: User Story 6 - End-of-Day Summary (Priority: P3)

**Goal**: Generate personalized day summary with completed work, pending items, and tomorrow's priorities

**Independent Test**: Fetch `/api/v1/day-summary/ui`, verify completed work list, pending items, and time estimates render

### A2UI Components for US6

- [X] T057 [P] [US6] Create Tabs component in frontend/src/components/a2ui/layout/Tabs.tsx
- [X] T058 [P] [US6] Create PieChart component in frontend/src/components/a2ui/charts/PieChart.tsx
- [X] T059 [US6] Register US6 components in catalog at frontend/src/lib/a2ui/catalog.ts

### Backend for US6

- [ ] T060 [US6] Create day summary agent in backend/app/modules/agents/summary_agent.py
- [ ] T061 [US6] Add GET /day-summary/ui endpoint in backend/app/modules/productivity/router.py

### Integration for US6

- [ ] T062 [US6] Create day summary modal component at frontend/src/components/productivity/DaySummaryModal.tsx

**Checkpoint**: Day summary shows completed work, pending items, and time estimates

---

## Phase 9: Remaining Components (6 tasks)

**Purpose**: Complete the 30-component catalog

- [X] T063 [P] Create remaining form components (TextInput, SelectField, Checkbox, DateRangePicker) in frontend/src/components/a2ui/forms/
- [X] T064 [P] Create remaining feedback components (Skeleton, Tooltip, Dialog) in frontend/src/components/a2ui/feedback/
- [X] T065 [P] Create Avatar component in frontend/src/components/a2ui/media/Avatar.tsx
- [X] T066 Register all remaining components in catalog at frontend/src/lib/a2ui/catalog.ts
- [X] T067 Create streaming support in frontend/src/lib/a2ui/streaming.ts
- [X] T068 Create useA2UIStream hook in frontend/src/hooks/useA2UIStream.ts

**Checkpoint**: All 30 components available in catalog, streaming supported

---

## Phase 10: LLM-Driven A2UI Integration (6 tasks)

**Purpose**: Enable LLM to dynamically decide what UI components to generate

- [X] T069 Create A2UI LLM schema prompt in backend/app/modules/agents/a2ui_llm.py
- [X] T070 Create A2UI JSON parser for LLM output in backend/app/modules/agents/a2ui_llm.py
- [X] T071 Create A2UI builder from LLM spec in backend/app/modules/agents/a2ui_llm.py
- [X] T072 Integrate A2UI schema into orchestrator system prompt in backend/app/modules/agents/orchestrator.py
- [X] T073 Update orchestrator to parse LLM A2UI output in backend/app/modules/agents/orchestrator.py
- [X] T074 Add A2UI message to streaming response events in backend/app/modules/agents/orchestrator.py

**Checkpoint**: LLM dynamically generates A2UI components based on its response content

---

## Phase 11: Polish & Cross-Cutting Concerns (6 tasks)

**Purpose**: Accessibility, performance, documentation

- [X] T075 Add ARIA roles and keyboard navigation to all A2UI components (shadcn/ui components include ARIA by default)
- [X] T076 [P] Add lazy loading for chart components in frontend/src/lib/a2ui/catalog.ts
- [X] T077 [P] Add audit logging for A2UI actions in backend/app/core/a2ui/audit.py
- [X] T078 Add A2UI render performance logging in frontend/src/lib/a2ui/renderer.tsx
- [X] T079 Run quickstart.md validation - 31 components in catalog, all core infrastructure complete
- [X] T080 Update component documentation in specs/033-a2ui-agent-driven-interfaces/

---

## Phase FINAL: PR & Merge (REQUIRED)

- [X] TFINAL-1 Ensure all linting passes
  - A2UI components: All pass (3 acceptable warnings in non-A2UI code)
  - Backend A2UI: All pass

- [ ] TFINAL-2 Verify all user stories independently testable
  - Test each `/ui` endpoint returns valid A2UI
  - Verify A2UIRenderer displays correctly

- [ ] TFINAL-3 Push feature branch and create PR
  - Run: `git push -u origin 033-a2ui-agent-driven-interfaces`
  - Run: `gh pr create --title "Spec 033: A2UI Agent-Driven Interfaces" --body "..."`

- [ ] TFINAL-4 Address review feedback (if any)

- [ ] TFINAL-5 Merge PR to main

- [ ] TFINAL-6 Update ROADMAP.md - mark Spec 033 as COMPLETE

---

## Parallel Execution Guide

### Phase 2: Foundational (Maximum Parallelism)

```
Parallel Group A (Frontend Types/Context):
  T005 (types.ts) + T006 (catalog.ts) + T007 (context.tsx)

Parallel Group B (Frontend Renderer - after A):
  T008 (renderer.tsx) + T009 (fallback.tsx)

Parallel Group C (Hooks - after A):
  T010 (useA2UIRenderer) + T011 (useDeviceContext)

Parallel Group D (Backend - independent):
  T013 (schemas.py) + T014 (builder.py) + T015 (device.py)
```

### User Story Phases (After Phase 2)

All user stories can be implemented in parallel if staffed:
- Developer A: US1 (Insights) - T017-T026
- Developer B: US2 (Dashboard) - T027-T034
- Developer C: US3 (Mobile Capture) - T035-T041

---

## Implementation Strategy

### MVP First (P1 Stories Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: US1 - Dynamic Insight Presentation
4. **STOP and VALIDATE**: Insights render with appropriate UIs
5. Complete Phase 4: US2 - Context-Aware Dashboard
6. Complete Phase 5: US3 - Camera-First Mobile
7. **MVP COMPLETE**: Core A2UI functionality working

### Incremental Delivery

| Increment | Stories | Value Delivered |
|-----------|---------|-----------------|
| MVP | US1, US2, US3 | Core A2UI rendering, personalized dashboards, mobile capture |
| Enhancement 1 | US4 | Ad-hoc queries with visualizations |
| Enhancement 2 | US5 | BAS review exception focus |
| Enhancement 3 | US6 | Day summary and productivity |

---

## Task Summary

| Phase | Task Count | Focus |
|-------|------------|-------|
| Setup | 4 | Directory structure |
| Foundational | 12 | A2UI core infrastructure |
| US1 (P1) | 10 | Insight presentation |
| US2 (P1) | 8 | Dashboard personalization |
| US3 (P1) | 7 | Mobile document capture |
| US4 (P2) | 9 | Query visualization |
| US5 (P2) | 6 | BAS review |
| US6 (P3) | 6 | Day summary |
| Remaining | 6 | Complete catalog |
| Polish | 6 | Quality & docs |
| **Total** | **74** | |

---

## Notes

- [P] tasks can run in parallel (different files, no dependencies)
- [Story] label maps task to specific user story
- Each user story is independently testable after completion
- All A2UI components map to shadcn/ui native components
- No database tables required - A2UI is presentation only
- Backend changes are minimal - additive `/ui` endpoints only
