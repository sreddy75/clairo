# Quickstart: Multi-Agent Tax Planning Pipeline

**Feature**: 041-multi-agent-tax-planning

## Prerequisites

- Existing tax plan with financials loaded (Xero or manual)
- Docker services running: `docker-compose up -d`
- Backend dev server or Docker container
- Frontend dev server on port 3000

## Development Setup

```bash
# Ensure all services are running
docker-compose up -d

# Run migrations (after adding new tables)
cd backend && uv run alembic upgrade head

# Start backend (if not using Docker)
cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Start frontend
cd frontend && npm run dev
```

## Module Structure

```
backend/app/modules/tax_planning/
├── models.py            # + TaxPlanAnalysis, ImplementationItem
├── schemas.py           # + analysis request/response schemas
├── repository.py        # + AnalysisRepository, ImplementationItemRepository
├── service.py           # + analysis orchestration methods
├── router.py            # + /analysis/* endpoints
├── agents/              # NEW — multi-agent pipeline
│   ├── __init__.py
│   ├── orchestrator.py  # Pipeline coordinator (Celery task entry)
│   ├── profiler.py      # Agent 1: Client profiling
│   ├── scanner.py       # Agent 2: Strategy scanning
│   ├── modeller.py      # Agent 3: Scenario modelling (uses calculator)
│   ├── advisor.py       # Agent 4: Document generation
│   ├── reviewer.py      # Agent 5: Quality review
│   └── prompts.py       # System prompts for each agent
├── tax_calculator.py    # Existing — reused by modeller agent
├── agent.py             # Existing chat agent — kept for interactive chat
└── prompts.py           # Existing — CALCULATE_TAX_TOOL reused

backend/app/tasks/
└── tax_planning.py      # NEW — Celery task for pipeline execution

frontend/src/components/tax-planning/
├── TaxPlanningWorkspace.tsx  # + "Generate Tax Plan" button, results tabs
├── AnalysisProgress.tsx      # NEW — real-time pipeline progress stepper
├── AccountantBrief.tsx       # NEW — markdown renderer + editor for brief
├── ClientSummaryPreview.tsx  # NEW — preview of what client will see
└── ImplementationChecklist.tsx # NEW — action items with status tracking

frontend/src/app/(protected)/clients/[id]/
└── page.tsx             # Tax Planning tab gets new "Generate" workflow

frontend/src/app/portal/
└── tax-plan/page.tsx    # NEW — client portal view of shared plan
```

## Key Patterns

### Agent Pattern
Each agent is a class with a single `run()` method:
```python
class ProfilerAgent:
    async def run(self, financials: dict, entity_type: str, ...) -> dict:
        # 1. Build prompt with financial context
        # 2. Call Claude
        # 3. Parse structured output
        # 4. Return profile dict
```

### Tax Calculator via Tool-Use
The Modeller agent uses Claude tool-use (same as existing chat agent):
```python
# Claude calls calculate_tax_position tool
# Agent executes locally, returns real numbers
# Claude sees exact before/after and writes analysis
```

### Celery Pipeline Task
```python
@celery_app.task(bind=True)
def run_analysis_pipeline(self, plan_id, tenant_id):
    # 1. Profile → update_state(PROGRESS, stage="profiling")
    # 2. Scan → update_state(PROGRESS, stage="scanning")
    # 3. Model → update_state(PROGRESS, stage="modelling")
    # 4. Write → update_state(PROGRESS, stage="writing")
    # 5. Review → update_state(PROGRESS, stage="reviewing")
    # 6. Save results → return analysis_id
```

## Testing

```bash
# Run all tax planning tests
cd backend && uv run pytest tests/ -k "tax_plan" -v

# Lint
cd backend && uv run ruff check . && cd ../frontend && npm run lint

# Typecheck
cd frontend && npx tsc --noEmit
```

## Verification Checklist

1. [ ] Create a tax plan with Xero financials loaded
2. [ ] Click "Generate Tax Plan" → see progress stepper
3. [ ] Pipeline completes → view accountant brief with real calculator numbers
4. [ ] Edit the brief → save changes
5. [ ] Approve → share to client portal
6. [ ] Login as client → see summary + checklist
7. [ ] Mark a checklist item complete → accountant sees update
