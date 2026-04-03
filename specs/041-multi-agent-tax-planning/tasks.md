# Tasks: Multi-Agent Tax Planning Pipeline

**Input**: Design documents from `/specs/041-multi-agent-tax-planning/`  
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/api.md, research.md, quickstart.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)

## Phase 0: Git Setup

- [x] T000 Create feature branch from main
  - Run: `git checkout main && git pull origin main`
  - Run: `git checkout -b feature/041-multi-agent-tax-planning`

---

## Phase 1: Setup

**Purpose**: New sub-package structure and shared infrastructure for agent pipeline

- [x] T001 Create agents sub-package directory structure at `backend/app/modules/tax_planning/agents/` with `__init__.py`, `orchestrator.py`, `profiler.py`, `scanner.py`, `modeller.py`, `advisor.py`, `reviewer.py`, `prompts.py`
- [x] T002 Create Celery task file at `backend/app/tasks/tax_planning.py` with task registration boilerplate following the pattern in `backend/app/tasks/reports.py`
- [x] T003 [P] Create frontend component stubs at `frontend/src/components/tax-planning/AnalysisProgress.tsx`, `AccountantBrief.tsx`, `ClientSummaryPreview.tsx`, `ImplementationChecklist.tsx`

---

## Phase 2: Foundational (Data Model + Repositories)

**Purpose**: Database tables, models, repositories, schemas, and exceptions that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Create Alembic migration for `tax_plan_analyses` table with all columns from `data-model.md` (id, tenant_id, tax_plan_id, version, is_current, status, client_profile JSONB, strategies_evaluated JSONB, recommended_scenarios JSONB, combined_strategy JSONB, accountant_brief Text, client_summary Text, review_result JSONB, review_passed, entities JSONB, group_structure JSONB, distribution_plan JSONB, entity_summaries JSONB, generation_time_ms, token_usage JSONB, generated_by, reviewed_by, shared_at, timestamps) at `backend/app/modules/tax_planning/migrations/`
- [x] T005 Create Alembic migration for `implementation_items` table with all columns from `data-model.md` (id, tenant_id, analysis_id FK, sort_order, title, description, strategy_ref, deadline, estimated_saving, entity_id, risk_rating, compliance_notes, client_visible, status, completed_at, completed_by, timestamps) at `backend/app/modules/tax_planning/migrations/`
- [x] T006 Add `current_analysis_id` nullable FK column to existing `tax_plans` table via migration
- [x] T007 [P] Add `TaxPlanAnalysis` SQLAlchemy model to `backend/app/modules/tax_planning/models.py` with `TenantMixin`, all JSONB columns, status enum, relationships to TaxPlan and ImplementationItem, unique constraint on (tax_plan_id, version)
- [x] T008 [P] Add `ImplementationItem` SQLAlchemy model to `backend/app/modules/tax_planning/models.py` with `TenantMixin`, FK to tax_plan_analyses, all columns from data-model.md
- [x] T009 Add `AnalysisRepository` to `backend/app/modules/tax_planning/repository.py` with methods: `create()`, `get_by_id()`, `get_current_for_plan()`, `list_versions()`, `update()`, `set_current()`
- [x] T010 [P] Add `ImplementationItemRepository` to `backend/app/modules/tax_planning/repository.py` with methods: `create_batch()`, `list_by_analysis()`, `update_status()`, `get_by_id()`
- [x] T011 Add Pydantic schemas for analysis requests/responses to `backend/app/modules/tax_planning/schemas.py`: `AnalysisGenerateResponse`, `AnalysisResponse`, `AnalysisUpdateRequest`, `ImplementationItemResponse`, `ImplementationItemUpdateRequest`
- [x] T012 [P] Add domain exceptions to `backend/app/modules/tax_planning/exceptions.py`: `AnalysisInProgressError`, `AnalysisNotFoundError`, `AnalysisNotApprovedError`, `NoFinancialsError`
- [x] T013 Run migrations and verify tables created: `cd backend && uv run alembic upgrade head`

**Checkpoint**: Database ready, models/repos/schemas available for all agents and endpoints

---

## Phase 3: User Story 1 — Generate Comprehensive Tax Plan (Priority: P1) MVP

**Goal**: Accountant clicks "Generate Tax Plan" → 5-agent pipeline runs autonomously → produces ranked strategies with real calculator numbers

**Independent Test**: Open a client's tax plan with Xero financials → click Generate → watch progress → see strategies with tax savings, risk ratings, and deadlines

### Agent Implementation

- [x] T014 [US1] Implement `ProfilerAgent.run()` in `backend/app/modules/tax_planning/agents/profiler.py` — takes financials_data + entity_type + financial_year, calls Claude with structured output prompt, returns client_profile dict (SBE eligibility, tax rate, thresholds, financials summary). Add profiler system prompt to `agents/prompts.py`
- [x] T015 [US1] Implement `StrategyScannerAgent.run()` in `backend/app/modules/tax_planning/agents/scanner.py` — takes client_profile + financials + tax_position, calls `_retrieve_tax_knowledge()` for RAG citations, calls Claude to evaluate 15+ strategy categories, returns strategies_evaluated array with applicable/not-applicable + reasons + risk + compliance refs. Add scanner system prompt to `agents/prompts.py`
- [x] T016 [US1] Implement `ScenarioModellerAgent.run()` in `backend/app/modules/tax_planning/agents/modeller.py` — takes top strategies + financials + entity_type + rate_configs, uses Claude tool-use with `CALCULATE_TAX_TOOL` (reuse from `prompts.py:52-115`), extract `_execute_tool()` logic from `agent.py:268-367` into shared utility, models each strategy + combined optimal set, returns recommended_scenarios + combined_strategy with real calculator numbers
- [x] T017 [US1] Implement `AdvisorAgent.run()` in `backend/app/modules/tax_planning/agents/advisor.py` — takes profile + scenarios + strategies + financials, calls Claude to generate accountant_brief (technical markdown) + client_summary (plain-language markdown). Add advisor system prompt to `agents/prompts.py`
- [x] T018 [US1] Implement `ReviewerAgent.run()` in `backend/app/modules/tax_planning/agents/reviewer.py` — takes all previous outputs + rate_configs, spot-checks calculator numbers by re-running `calculate_tax_position()`, verifies RAG citations exist, checks for strategy contradictions, returns review_result dict + review_passed boolean. Add reviewer system prompt to `agents/prompts.py`

### Orchestrator + Celery Task

- [x] T019 [US1] Implement `AnalysisPipelineOrchestrator` in `backend/app/modules/tax_planning/agents/orchestrator.py` — chains 5 agents sequentially (profiler → scanner → modeller → advisor → reviewer), saves results to `TaxPlanAnalysis` via `AnalysisRepository`, generates `ImplementationItem` records from recommended scenarios, reports progress after each stage
- [x] T020 [US1] Implement `run_analysis_pipeline` Celery task in `backend/app/tasks/tax_planning.py` — sync wrapper with `asyncio.run()`, fresh DB via `get_celery_db_context()`, calls orchestrator, uses `self.update_state(state="PROGRESS", meta={"stage": ..., "stage_number": ..., "total_stages": 5, "message": ...})` after each agent completes, handles concurrency guard (check `status == "generating"`)

### API Endpoints

- [x] T021 [US1] Add `POST /tax-plans/{plan_id}/analysis/generate` endpoint to `backend/app/modules/tax_planning/router.py` — validates plan has financials, checks no analysis in progress (409), dispatches Celery task, returns 202 with task_id + analysis_id
- [x] T022 [US1] Add `GET /tax-plans/{plan_id}/analysis/progress/{task_id}` SSE endpoint to `backend/app/modules/tax_planning/router.py` — polls Celery AsyncResult, streams progress events as SSE, yields complete/error events
- [x] T023 [US1] Add `GET /tax-plans/{plan_id}/analysis` endpoint to `backend/app/modules/tax_planning/router.py` — returns current analysis with all fields + implementation items

### Frontend

- [x] T024 [US1] Add `generateAnalysis()`, `getAnalysisProgress()`, `getAnalysis()` API functions to `frontend/src/lib/api/tax-planning.ts`
- [x] T025 [US1] Implement `AnalysisProgress` component in `frontend/src/components/tax-planning/AnalysisProgress.tsx` — 5-step progress stepper (Profile → Scan → Model → Write → Review), polls SSE endpoint, shows current stage + message, handles completion and error states
- [x] T026 [US1] Add "Generate Tax Plan" button to `TaxPlanningWorkspace.tsx` in the Position tab (when financials loaded + no current analysis), triggers generation flow, shows AnalysisProgress while running
- [x] T027 [US1] Display analysis results in `TaxPlanningWorkspace.tsx` — add "Analysis" tab to the workflow tabs showing: client profile summary, strategies overview, recommended scenarios with savings/risk/deadline
- [x] T028 [US1] Add TypeScript types for analysis entities to `frontend/src/types/tax-planning.ts`: `TaxPlanAnalysis`, `ImplementationItem`, `AnalysisProgressEvent`

**Checkpoint**: Full pipeline generates a comprehensive tax plan from one click. Accountant sees ranked strategies with real numbers.

---

## Phase 4: User Story 2 — Review Accountant Brief (Priority: P1)

**Goal**: Accountant reviews and edits the generated technical brief with proper citations and verified numbers

**Independent Test**: View accountant brief → verify all numbers match calculator → edit a section → save changes → see status change to "reviewed"

- [x] T029 [US2] Add `PATCH /tax-plans/{plan_id}/analysis` endpoint to `backend/app/modules/tax_planning/router.py` — accepts updated accountant_brief, client_summary, status; validates status transitions
- [x] T030 [US2] Implement `AccountantBrief` component in `frontend/src/components/tax-planning/AccountantBrief.tsx` — renders accountant_brief markdown via react-markdown + remarkGfm, toggle to edit mode (textarea), save button calls PATCH endpoint, shows review_result (what passed/failed in quality check)
- [x] T031 [US2] Add accountant brief view to the "Analysis" tab in `TaxPlanningWorkspace.tsx` — shows AccountantBrief component with edit/save controls, status badge (draft/reviewed/approved)

**Checkpoint**: Accountant can review, edit, and mark the brief as reviewed

---

## Phase 5: User Story 5 — Pipeline Progress & Error Handling (Priority: P1)

**Goal**: Real-time progress feedback during pipeline execution, graceful error recovery

**Independent Test**: Trigger pipeline → see stepper advance through stages → simulate failure → see error with retry option

- [x] T032 [US5] Add retry-from-stage logic to `run_analysis_pipeline` Celery task in `backend/app/tasks/tax_planning.py` — accept optional `resume_from_stage` parameter, skip completed stages using saved partial results from the analysis record
- [x] T033 [US5] Add `POST /tax-plans/{plan_id}/analysis/retry` endpoint to `backend/app/modules/tax_planning/router.py` — dispatches Celery task with resume_from_stage, returns 202
- [x] T034 [US5] Add error state and retry button to `AnalysisProgress` component in `frontend/src/components/tax-planning/AnalysisProgress.tsx` — show which stage failed, error message, "Retry from [stage]" button

**Checkpoint**: Pipeline failures show clear error with one-click retry

---

## Phase 6: User Story 3 — Share Client Summary to Portal (Priority: P2)

**Goal**: Accountant approves the plan and shares a plain-language summary to the client portal with interactive checklist

**Independent Test**: Approve analysis → share to portal → login as client → see summary + checklist → mark item complete → accountant sees update

- [x] T035 [US3] Add `POST /tax-plans/{plan_id}/analysis/approve` endpoint to `backend/app/modules/tax_planning/router.py` — sets status to "approved", records reviewed_by
- [x] T036 [US3] Add `POST /tax-plans/{plan_id}/analysis/share` endpoint to `backend/app/modules/tax_planning/router.py` — validates status is "approved", sets status to "shared", records shared_at
- [x] T037 [US3] Add `PATCH /tax-plans/{plan_id}/analysis/items/{item_id}` endpoint to `backend/app/modules/tax_planning/router.py` — update implementation item status (pending/in_progress/completed/skipped), records completed_at and completed_by
- [x] T038 [US3] Implement `ClientSummaryPreview` component in `frontend/src/components/tax-planning/ClientSummaryPreview.tsx` — renders client_summary markdown, shows what client will see
- [x] T039 [US3] Implement `ImplementationChecklist` component in `frontend/src/components/tax-planning/ImplementationChecklist.tsx` — list of items with checkboxes, deadlines, estimated savings, risk badges, status tracking
- [x] T040 [US3] Add approve/share workflow buttons to Analysis tab in `TaxPlanningWorkspace.tsx` — "Approve" button (sets status), "Share with Client" button (sets shared), preview of client summary before sharing
- [x] T041 [US3] Add `GET /client-portal/tax-plan` portal endpoint to `backend/app/modules/portal/router.py` — authenticates via magic link, returns shared analysis summary + implementation items for the client's connection_id
- [x] T042 [US3] Add `PATCH /client-portal/tax-plan/items/{item_id}` portal endpoint to `backend/app/modules/portal/router.py` — allows client to mark items as completed
- [x] T043 [US3] Add `POST /client-portal/tax-plan/question` portal endpoint to `backend/app/modules/portal/router.py` — creates a notification to the accountant with the question text + plan context
- [x] T044 [US3] Create portal tax plan page at `frontend/src/app/portal/tax-plan/page.tsx` — client view with client_summary markdown, implementation checklist, "Ask a Question" form
- [x] T045 [US3] Add portal API functions to `frontend/src/lib/api/portal.ts` or similar: `getPortalTaxPlan()`, `updatePortalItem()`, `askPortalQuestion()`

**Checkpoint**: Full accountant→client sharing workflow with interactive checklist on both sides

---

## Phase 7: User Story 4 — Re-generate After Data Changes (Priority: P2)

**Goal**: Re-run analysis with updated financials, preserving previous versions for comparison

**Independent Test**: Update Xero financials → click Re-generate → new analysis with version 2 → compare changes from version 1

- [x] T046 [US4] Add `POST /tax-plans/{plan_id}/analysis/regenerate` endpoint to `backend/app/modules/tax_planning/router.py` — creates new version (increments version, sets is_current=true on new, false on old), dispatches Celery task
- [x] T047 [US4] Add `regenerateAnalysis()` API function to `frontend/src/lib/api/tax-planning.ts`
- [x] T048 [US4] Add version selector and diff view to Analysis tab in `TaxPlanningWorkspace.tsx` — dropdown to select previous versions, highlight what changed (new/removed strategies, changed savings amounts)

**Checkpoint**: Iterative tax planning works — re-generate after data changes, compare versions

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T049 [P] Add audit events for analysis lifecycle: `analysis.generated`, `analysis.reviewed`, `analysis.shared`, `implementation.updated` in `backend/app/modules/tax_planning/service.py`
- [x] T050 [P] Add notification to accountant when client marks implementation item complete or asks a question in `backend/app/modules/notifications/`
- [x] T051 [P] Add PDF export of accountant brief — reuse existing weasyprint pattern from `backend/app/modules/tax_planning/` PDF export
- [x] T052 Lint and format all new code: `cd backend && uv run ruff check . && uv run ruff format .` and `cd frontend && npm run lint`
- [x] T053 Run full verification checklist from `quickstart.md`

---

## Phase FINAL: PR & Merge

- [x] T054 Ensure all tests pass: `cd backend && uv run pytest`
- [x] T055 Run linting and type checking: `cd backend && uv run ruff check .` and `cd frontend && npx tsc --noEmit`
- [x] T056 Push feature branch and create PR: `git push -u origin feature/041-multi-agent-tax-planning` and `gh pr create --title "Spec 041: Multi-Agent Tax Planning Pipeline"`
- [x] T057 Address review feedback
- [x] T058 Merge PR to main (squash merge)
- [x] T059 Update ROADMAP.md — mark spec 041 as COMPLETE

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 0 (Git)**: Must be first
- **Phase 1 (Setup)**: After Phase 0
- **Phase 2 (Foundational)**: After Phase 1 — BLOCKS all user stories
- **Phase 3 (US1 — Generate)**: After Phase 2 — MVP
- **Phase 4 (US2 — Review Brief)**: After Phase 3 (needs generated analysis)
- **Phase 5 (US5 — Progress/Errors)**: Can parallel with Phase 4 (enhances pipeline from Phase 3)
- **Phase 6 (US3 — Portal Sharing)**: After Phase 4 (needs approved analysis)
- **Phase 7 (US4 — Re-generate)**: After Phase 3 (needs existing analysis to compare)
- **Phase 8 (Polish)**: After all desired user stories
- **Phase FINAL**: After Phase 8

### User Story Dependencies

- **US1 (Generate)**: Independent — foundational for all others
- **US2 (Review Brief)**: Depends on US1 (needs generated analysis)
- **US5 (Progress)**: Enhances US1 — can be parallel with US2
- **US3 (Portal Sharing)**: Depends on US2 (needs approved analysis)
- **US4 (Re-generate)**: Depends on US1 (needs existing analysis)

### Parallel Opportunities

Within Phase 2 (Foundational):
```
T007 (TaxPlanAnalysis model) ‖ T008 (ImplementationItem model) ‖ T012 (exceptions)
```

Within Phase 3 (US1 Agents):
```
T014 (profiler) ‖ T015 (scanner) ‖ T016 (modeller) ‖ T017 (advisor) ‖ T018 (reviewer)
— all agent implementations are independent files, can be developed in parallel
— T019 (orchestrator) depends on all 5 agents
```

Within Phase 3 (US1 Frontend):
```
T024 (API functions) ‖ T25 (AnalysisProgress) ‖ T028 (types)
— T026-T027 depend on T024 + T025
```

---

## Implementation Strategy

### MVP First (Phases 0–3: US1 Only)

1. Setup + Foundational → database and infrastructure ready
2. Build 5 agents + orchestrator + Celery task
3. Add generate/progress/results endpoints
4. Frontend: Generate button + progress stepper + results view
5. **STOP and VALIDATE**: Generate a tax plan for KR8 IT with real Xero data
6. Demo to Unni — does this match what an accountant would produce manually?

### Incremental Delivery

1. MVP (US1) → one-click comprehensive tax plan generation
2. + US2 → accountant reviews and edits the brief
3. + US5 → better progress UX with retry on failure
4. + US3 → share to client portal with checklist
5. + US4 → re-generate when financials change
6. Each increment is independently valuable and demoable

---

## Notes

- All agents call Claude Sonnet via Anthropic SDK — same model as existing chat agent
- Tax calculator numbers are NEVER AI-generated — always from `calculate_tax_position()`
- RAG citations come from the existing Pinecone `clairo-knowledge` index
- The existing chat agent (`agent.py`) is preserved for interactive chat — the pipeline is a separate workflow
- Phase 2 extension points (entities[], group_structure, etc.) are nullable JSONB columns — no extra cost in Phase 1
