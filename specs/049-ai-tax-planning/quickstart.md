# Quickstart: AI Tax Planning & Advisory

**Branch**: `049-ai-tax-planning` | **Date**: 2026-03-31

---

## What This Feature Does

Adds a tax planning module that lets accountants estimate a client's tax position (from Xero P&L or manual entry) and use AI chat to model what-if scenarios with accurate tax calculations. Supports companies, individuals, trusts, and partnerships for FY 2025-26. Exports results as branded PDF.

---

## New Dependencies

**Backend**:
- `weasyprint` — HTML-to-PDF conversion for tax plan export
- `jinja2` — already available (FastAPI dependency), used for PDF templates

**Frontend**: No new dependencies.

---

## Database Migration

```bash
cd backend
uv run alembic revision --autogenerate -m "049: add tax planning tables"
uv run alembic upgrade head
```

Creates 4 tables: `tax_rate_configs`, `tax_plans`, `tax_scenarios`, `tax_plan_messages`. Seeds 2025-26 Australian tax rates.

---

## Where Things Live

### Backend

```
backend/app/modules/tax_planning/           # NEW module
├── __init__.py                              # NEW — module exports
├── models.py                                # NEW — TaxPlan, TaxScenario, TaxPlanMessage, TaxRateConfig
├── schemas.py                               # NEW — Pydantic request/response models
├── repository.py                            # NEW — CRUD operations
├── service.py                               # NEW — business logic, Xero data pull, orchestration
├── router.py                                # NEW — API endpoints
├── exceptions.py                            # NEW — domain exceptions
├── tax_calculator.py                        # NEW — pure-function tax calculation engine
├── agent.py                                 # NEW — TaxPlanningAgent (Claude tool-use)
├── prompts.py                               # NEW — system prompts for AI scenario modelling
└── templates/
    └── tax_plan_export.html                 # NEW — Jinja2 PDF export template

backend/app/main.py                          # MODIFY — register tax_planning router + model imports
backend/alembic/versions/
└── 20260401_049_tax_planning.py             # NEW — migration + seed data
```

### Frontend

```
frontend/src/app/(protected)/clients/[id]/
└── page.tsx                                 # MODIFY — add tax-planning tab

frontend/src/components/tax-planning/        # NEW directory
├── TaxPlanningWorkspace.tsx                 # NEW — main container (financials + chat + scenarios)
├── FinancialsPanel.tsx                      # NEW — income/expense display + manual entry form
├── TaxPositionCard.tsx                      # NEW — tax position summary display
├── ScenarioChat.tsx                         # NEW — AI chat interface with streaming
├── ScenarioCard.tsx                         # NEW — individual scenario display
├── ComparisonTable.tsx                      # NEW — side-by-side scenario comparison
└── ManualEntryForm.tsx                      # NEW — React Hook Form + Zod for manual financials

frontend/src/lib/api/tax-planning.ts         # NEW — API wrapper functions
frontend/src/types/tax-planning.ts           # NEW — TypeScript types
```

---

## Key Implementation Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| P&L data source | Reuse existing `XeroReportService` | Pipeline already fetches, transforms, and caches P&L data |
| Tax calculation | Pure functions, rates in DB | Must be deterministic (within $1 accuracy), updatable without deploy |
| AI agent pattern | Standalone agent with tool-use | Needs multi-turn conversation + deterministic tax calculation tools |
| Financials storage | JSONB on `tax_plans` | Always 1:1 with plan, no normalization benefit from separate table |
| Frontend integration | Tab in client detail page | Consistent with existing client-scoped features (BAS, Insights) |
| PDF export | Server-side weasyprint | Consistent formatting, access to tenant branding |

---

## Development Order

1. **Models + Migration** — `models.py`, Alembic migration with seed data
2. **Tax Calculator** — `tax_calculator.py` with unit tests (pure functions, easy to test)
3. **Schemas + Exceptions** — `schemas.py`, `exceptions.py`
4. **Repository** — `repository.py` (CRUD for all entities)
5. **Service + Xero Integration** — `service.py` (financials pull, calculation orchestration)
6. **Router (CRUD endpoints)** — `router.py` (plans, financials, scenarios)
7. **AI Agent** — `agent.py`, `prompts.py` (scenario modelling with tool-use)
8. **Chat endpoints** — streaming SSE in router
9. **PDF Export** — `templates/`, export endpoint
10. **Frontend: Types + API** — `types/tax-planning.ts`, `lib/api/tax-planning.ts`
11. **Frontend: Components** — workspace, financials, chat, scenarios
12. **Frontend: Tab Integration** — wire into client detail page
13. **Register module** — `main.py` router + model imports

---

## Testing Strategy

### Backend

| Test Type | Location | What to Test |
|-----------|----------|-------------|
| Unit | `tests/unit/modules/tax_planning/test_tax_calculator.py` | All tax calculations: individual brackets, company rates, LITO, Medicare, HELP. Verify within $1 of manual calculation. |
| Unit | `tests/unit/modules/tax_planning/test_service.py` | Financials transformation from Xero P&L, annualisation logic |
| Integration | `tests/integration/api/test_tax_plans.py` | Full CRUD cycle, Xero pull, manual entry, scenario creation |
| Integration | `tests/integration/api/test_tax_chat.py` | AI chat endpoint, scenario generation, message persistence |

### Frontend

| Test Type | What to Test |
|-----------|-------------|
| Component | Manual entry form validation (Zod schema) |
| Component | Tax position display with various entity types |
| E2E | Full flow: create plan → pull financials → chat → export |

---

## Verification

After implementation, verify these scenarios manually:

1. **Xero pull**: Select a client with Xero → create tax plan → see P&L figures pre-populated
2. **Manual entry**: Select a client without Xero → create tax plan → enter figures manually → see tax position
3. **Company tax**: Enter $500K revenue, $350K expenses for a company → verify 25% rate on $150K = $37,500
4. **Individual tax**: Enter $90K taxable income for individual → verify marginal rates + Medicare + LITO
5. **AI scenario**: Type "prepay $30K rent before June 30" → verify AI generates scenario with accurate tax saving
6. **Comparison**: Generate 3 scenarios → ask "compare all options" → verify comparison table
7. **Export**: Click export → verify PDF has client name, practice branding, scenarios, disclaimer
8. **Resumption**: Close browser → reopen tax plan → verify all data and chat history preserved
