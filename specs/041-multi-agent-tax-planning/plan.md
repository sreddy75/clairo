# Implementation Plan: Multi-Agent Tax Planning Pipeline

**Branch**: `041-multi-agent-tax-planning` | **Date**: 2026-04-03 | **Spec**: [spec.md](spec.md)

## Summary

Build a 5-agent autonomous tax planning pipeline that profiles clients, scans 15+ strategies, models optimal combinations with real tax calculator numbers, produces dual-audience documents (accountant brief + client summary), and quality-reviews everything. Runs as a Celery background job with SSE progress. Accountant reviews/approves, then shares to client portal with interactive implementation checklist.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend)  
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Celery, Anthropic SDK (Claude Sonnet), Pydantic v2, React 18 + shadcn/ui  
**Storage**: PostgreSQL 16 (2 new tables: `tax_plan_analyses`, `implementation_items`)  
**Testing**: pytest with pytest-asyncio  
**Target Platform**: Web (Railway deployment)  
**Performance Goals**: Full pipeline completes in < 60 seconds  
**Constraints**: All tax figures from real calculator (never hallucinated), human-in-the-loop approval  
**Scale/Scope**: ~50 clients per practice per EOFY season

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Modular monolith structure | PASS | New code in `modules/tax_planning/agents/` sub-package |
| Repository pattern | PASS | New `AnalysisRepository`, `ImplementationItemRepository` |
| Multi-tenancy (tenant_id + RLS) | PASS | All new tables include `tenant_id` |
| Audit events | PASS | analysis.generated, analysis.reviewed, analysis.shared, implementation.updated |
| Human-in-the-loop AI | PASS | Accountant must review and approve before sharing |
| Domain exceptions (not HTTPException) | PASS | New domain exceptions in tax_planning/exceptions.py |
| Module boundaries | PASS | Agents call tax calculator directly (same module), RAG via knowledge service interface |
| Test coverage | TRACKED | Unit tests for each agent, integration tests for pipeline + endpoints |

## Project Structure

### Source Code

```
backend/app/
├── modules/tax_planning/
│   ├── agents/                    # NEW — multi-agent pipeline
│   │   ├── __init__.py
│   │   ├── orchestrator.py        # Pipeline coordinator
│   │   ├── profiler.py            # Agent 1: entity profiling
│   │   ├── scanner.py             # Agent 2: strategy scanning + RAG
│   │   ├── modeller.py            # Agent 3: tool-use scenario modelling
│   │   ├── advisor.py             # Agent 4: document generation
│   │   ├── reviewer.py            # Agent 5: quality verification
│   │   └── prompts.py             # Per-agent system prompts
│   ├── models.py                  # + TaxPlanAnalysis, ImplementationItem
│   ├── schemas.py                 # + analysis schemas
│   ├── repository.py              # + AnalysisRepository
│   ├── service.py                 # + analysis service methods
│   ├── router.py                  # + /analysis/* endpoints
│   └── exceptions.py              # + AnalysisInProgressError, etc.
├── tasks/
│   └── tax_planning.py            # NEW — Celery task
└── core/
    └── (no changes)

frontend/src/
├── components/tax-planning/
│   ├── AnalysisProgress.tsx       # NEW — pipeline progress stepper
│   ├── AccountantBrief.tsx        # NEW — markdown renderer + editor
│   ├── ClientSummaryPreview.tsx   # NEW — portal preview
│   ├── ImplementationChecklist.tsx # NEW — action items
│   └── TaxPlanningWorkspace.tsx   # MODIFIED — add Generate button + results
├── app/(protected)/clients/[id]/
│   └── page.tsx                   # MODIFIED — analysis results in Tax Planning tab
├── app/portal/
│   └── tax-plan/page.tsx          # NEW — client portal view
├── lib/api/
│   └── tax-planning.ts            # + analysis API functions
└── types/
    └── tax-planning.ts            # + analysis type definitions
```

## Key Reuse Points

| Component | Location | Reuse |
|-----------|----------|-------|
| `calculate_tax_position()` | `tax_calculator.py:335` | Modeller agent calls via Claude tool-use |
| `CALCULATE_TAX_TOOL` | `prompts.py:52-115` | Shared tool definition |
| `_execute_tool()` | `agent.py:268-367` | Extract to `agents/modeller.py` for reuse |
| `_retrieve_tax_knowledge()` | `service.py:601-681` | Scanner agent uses for compliance citations |
| `_load_rate_configs()` | `service.py:532-542` | Shared across agents needing tax rates |
| Celery task pattern | `tasks/reports.py:63-104` | Sync wrapper + asyncio.run() + fresh DB session |
| Progress reporting | `tasks/knowledge.py:323-331` | `update_state(state="PROGRESS", meta={...})` |
| Portal data sharing | `portal/classification_router.py` | Auth via magic link, query by connection_id |
| SSE streaming | `agents/router.py:142+` | Poll Celery state, stream as SSE events |

## Implementation Phases

### Phase A: Data Model + Infrastructure (Foundation)

1. Alembic migration: `tax_plan_analyses` + `implementation_items` tables
2. SQLAlchemy models: `TaxPlanAnalysis`, `ImplementationItem` with relationships
3. Repositories: `AnalysisRepository`, `ImplementationItemRepository`
4. Pydantic schemas: request/response models for analysis endpoints
5. Domain exceptions: `AnalysisInProgressError`, `AnalysisNotFoundError`, `AnalysisNotApprovedError`

### Phase B: Agent Pipeline (Core Logic)

1. **Profiler Agent** (`agents/profiler.py`)
   - Input: financials_data, entity_type, financial_year
   - Claude call: structured output extraction (entity classification, SBE eligibility, thresholds)
   - Output: client_profile dict
   - Test: mock Claude, verify profile structure for company/individual/trust

2. **Strategy Scanner** (`agents/scanner.py`)
   - Input: client_profile, financials, tax_position, knowledge_chunks (from RAG)
   - Claude call: evaluate each strategy category against profile
   - RAG: calls `_retrieve_tax_knowledge()` for compliance citations
   - Output: strategies_evaluated array
   - Test: verify 15+ categories evaluated, applicable/not-applicable with reasons

3. **Scenario Modeller** (`agents/modeller.py`)
   - Input: top strategies, financials, entity_type, rate_configs
   - Claude call with `CALCULATE_TAX_TOOL`: tool-use loop (same pattern as existing agent)
   - Reuses `_execute_tool()` logic for before/after calculation
   - Also models combined strategies
   - Output: recommended_scenarios + combined_strategy
   - Test: verify all numbers match calculator, combined strategy is valid

4. **Advisor Agent** (`agents/advisor.py`)
   - Input: profile, scenarios, strategies, financials
   - Claude call: generate two markdown documents
   - Output: accountant_brief (technical) + client_summary (plain language)
   - Test: verify both documents contain required sections, no jargon in client summary

5. **Reviewer Agent** (`agents/reviewer.py`)
   - Input: all previous agent outputs, rate_configs
   - Verification: re-run calculator for spot checks, verify citations exist in RAG, check for contradictions
   - Output: review_result dict + review_passed boolean
   - Test: inject bad numbers, verify reviewer catches them

6. **Orchestrator** (`agents/orchestrator.py`)
   - Chains agents sequentially
   - Reports progress after each stage
   - Handles partial failures (e.g., reviewer finds issues but profiler/scanner worked fine)
   - Saves results to DB via AnalysisRepository

### Phase C: Celery Task + API Endpoints

1. Celery task (`tasks/tax_planning.py`): `run_analysis_pipeline`
   - Sync wrapper with `asyncio.run()`
   - Fresh DB session via `get_celery_db_context()`
   - `update_state(state="PROGRESS", meta={stage, stage_number, ...})`
   - Concurrency guard: check `status == "generating"` before starting

2. API endpoints (`router.py` additions):
   - `POST /analysis/generate` → dispatches Celery task
   - `GET /analysis/progress/{task_id}` → SSE polling Celery state
   - `GET /analysis` → returns current analysis
   - `PATCH /analysis` → edit brief/summary
   - `POST /analysis/approve` → set status to approved
   - `POST /analysis/share` → set status to shared, populate shared_at
   - `POST /analysis/regenerate` → new version, dispatches task
   - `PATCH /analysis/items/{item_id}` → update implementation item

3. Portal endpoint (`portal/router.py` addition):
   - `GET /client-portal/tax-plan` → shared summary + items
   - `POST /client-portal/tax-plan/question` → route question to accountant
   - `PATCH /client-portal/tax-plan/items/{item_id}` → mark item complete

### Phase D: Frontend

1. **AnalysisProgress** component: stepper UI showing 5 stages, polls SSE endpoint
2. **AccountantBrief** component: markdown renderer (react-markdown) + edit mode (textarea)
3. **ClientSummaryPreview** component: preview of portal view
4. **ImplementationChecklist** component: action items with checkboxes, deadlines, savings
5. **TaxPlanningWorkspace** update: "Generate Tax Plan" button in the workflow tabs, new "Analysis" tab
6. **Portal tax-plan page**: client view with summary + checklist + ask question form
7. **API functions**: `generateAnalysis`, `getAnalysisProgress`, `getAnalysis`, `approveAnalysis`, `shareAnalysis`, etc.

### Phase E: Integration + Polish

1. Audit events for analysis lifecycle
2. Notification to accountant when client marks items complete or asks questions
3. PDF export of the accountant brief (reuse existing weasyprint pattern)
4. End-to-end testing with real Xero data

## Verification

1. Create a tax plan with Xero financials → click "Generate Tax Plan"
2. Watch progress stepper through all 5 stages
3. Review accountant brief — verify all numbers match calculator
4. Edit the brief, approve, share to portal
5. Login as client — see summary + checklist
6. Mark a checklist item complete → accountant sees update
7. Re-generate after Xero refresh → compare versions
8. `cd backend && uv run ruff check . && uv run pytest`
9. `cd frontend && npm run lint && npx tsc --noEmit`
