# Tasks: AI Tax Planning & Advisory

**Input**: Design documents from `/specs/049-ai-tax-planning/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1, US2, US3, US4, US5)
- Include exact file paths in descriptions

---

## Phase 0: Git Setup

**Purpose**: Verify feature branch

- [x] T000 Verify on branch `049-ai-tax-planning`
  - Run: `git branch --show-current`
  - Expected: `049-ai-tax-planning`
  - If not: `git checkout 049-ai-tax-planning` or `git checkout -b 049-ai-tax-planning`

---

## Phase 1: Setup

**Purpose**: Module directory structure and dependencies

- [x] T001 Create `backend/app/modules/tax_planning/` directory with `__init__.py`
  - Create module docstring describing purpose and exports
  - Create `templates/` subdirectory for PDF export

- [x] T002 [P] Add `weasyprint` dependency in `backend/pyproject.toml`
  - Add `weasyprint` to project dependencies
  - Run: `cd backend && uv lock && uv sync`

- [x] T003 [P] Create test directory structure
  - Create `backend/tests/unit/modules/tax_planning/` with `__init__.py`
  - Create `backend/tests/integration/api/` if not exists

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Models, migration, tax calculator, schemas, exceptions, repository — MUST complete before user story work

### Models & Migration

- [x] T004 Create SQLAlchemy models in `backend/app/modules/tax_planning/models.py`
  - `EntityType` enum: company, individual, trust, partnership
  - `TaxPlanStatus` enum: draft, in_progress, finalised
  - `DataSource` enum: xero, manual, xero_with_adjustments
  - `RiskRating` enum: conservative, moderate, aggressive
  - `TaxRateConfig` model: id, financial_year, rate_type, rates_data (JSONB), effective_from, notes, timestamps
  - `TaxPlan` model: id, tenant_id (FK tenants), xpm_client_id (FK xpm_clients), xero_connection_id (FK xero_connections, nullable), financial_year, entity_type, status, data_source, financials_data (JSONB), tax_position (JSONB, nullable), notes, xero_report_fetched_at, timestamps
  - `TaxScenario` model: id, tenant_id, tax_plan_id (FK tax_plans CASCADE), title, description, assumptions (JSONB), impact_data (JSONB), risk_rating, compliance_notes, cash_flow_impact (Decimal), sort_order, created_at
  - `TaxPlanMessage` model: id, tenant_id, tax_plan_id (FK tax_plans CASCADE), role, content, scenario_ids (ARRAY UUID), token_count, metadata (JSONB), created_at
  - All models inherit `BaseModel` + `TenantMixin`
  - Add unique constraint `uq_tax_plan_client_fy` on (xpm_client_id, financial_year)
  - Add unique constraint `uq_tax_rate_config_year_type` on (financial_year, rate_type)
  - Add all indexes per data-model.md: ix_tax_plans_tenant_id, ix_tax_plans_tenant_status, ix_tax_plans_xpm_client_id, ix_tax_scenarios_tax_plan_id, ix_tax_scenarios_tenant_id, ix_tax_plan_messages_plan_id_created, ix_tax_plan_messages_tenant_id, ix_tax_rate_configs_financial_year
  - Verify: models import without error

- [x] T005 Create Alembic migration with seed data in `backend/alembic/versions/`
  - Run: `cd backend && uv run alembic revision --autogenerate -m "049: add tax planning tables"`
  - Verify migration creates all 4 tables with correct columns, constraints, and indexes
  - Add seed data for 2025-26 tax rates in the `upgrade()` function:
    - `individual` rate_type: 2025-26 marginal brackets per data-model.md
    - `company` rate_type: small_business_rate 0.25, standard_rate 0.30, threshold 50M
    - `trust` rate_type: undistributed_rate 0.47
    - `medicare` rate_type: rate 0.02, thresholds per data-model.md
    - `lito` rate_type: max_offset 700, thresholds per data-model.md
    - `help` rate_type: 18 repayment thresholds per data-model.md
  - Run: `cd backend && uv run alembic upgrade head`
  - Verify: tables exist in database

- [x] T006 Register models in `backend/app/main.py`
  - Add model imports (noqa: F401) alongside existing module model imports
  - `from app.modules.tax_planning.models import TaxPlan, TaxScenario, TaxPlanMessage, TaxRateConfig`
  - Verify: no circular import errors

### Tax Calculator

- [x] T007 Implement tax calculation engine in `backend/app/modules/tax_planning/tax_calculator.py`
  - Pure functions — no DB access, no side effects. Accept rate config dicts as parameters.
  - `calculate_company_tax(taxable_income: Decimal, turnover: Decimal, rates: dict) -> TaxCalculationResult`
    - Apply 25% if turnover < threshold (small business), else 30%
  - `calculate_individual_tax(taxable_income: Decimal, rates: dict, medicare_rates: dict, lito_rates: dict, help_rates: dict | None = None) -> TaxCalculationResult`
    - Apply marginal brackets
    - Calculate Medicare Levy (2%, with low-income threshold phase-in)
    - Calculate LITO offset ($700, reducing above $37,500)
    - Calculate HELP repayment if help_rates provided
  - `calculate_trust_tax(taxable_income: Decimal, rates: dict) -> TaxCalculationResult`
    - Apply 47% on undistributed income
  - `calculate_partnership_tax(net_income: Decimal, individual_rates: dict, medicare_rates: dict, lito_rates: dict) -> TaxCalculationResult`
    - Calculate at individual rates for single-partner simplified view
  - `calculate_tax_position(entity_type: str, financials_data: dict, rate_configs: dict, has_help_debt: bool = False) -> dict`
    - Main entry point: derives taxable_income from financials, dispatches to entity-specific calculator, applies credits, returns full tax_position JSONB structure
  - `TaxCalculationResult` dataclass: taxable_income, gross_tax, offsets (dict), medicare_levy, help_repayment, total_tax_payable, effective_rate_pct, calculation_method
  - Verify: all functions are pure (no imports from repository/service/database)

- [x] T008 Write unit tests for tax calculator in `backend/tests/unit/modules/tax_planning/test_tax_calculator.py`
  - Test company tax: $500K revenue, $350K expenses → $150K taxable → $37,500 at 25%
  - Test company tax: standard rate (turnover > $50M) → 30%
  - Test individual marginal rates: $45,000 taxable → $0 on first $18,200 + 16% on $18,201-$45,000 = $4,288
  - Test individual: $90,000 taxable → correct marginal calculation across 3 brackets
  - Test individual: $200,000 taxable → all 5 brackets applied correctly
  - Test LITO: $37,500 income → full $700 offset
  - Test LITO: $50,000 income → reduced offset
  - Test LITO: $70,000 income → $0 offset (above $66,667)
  - Test Medicare Levy: standard 2% on $50,000 = $1,000
  - Test Medicare Levy: low-income exemption ($24,000 → $0)
  - Test Medicare Levy: phase-in ($30,000 → partial levy)
  - Test HELP repayment: $60,000 income → 1% = $600
  - Test HELP repayment: below threshold → $0
  - Test trust: $100,000 undistributed → $47,000
  - Test partnership: single partner at individual rates
  - Test credits: PAYG instalments reduce net position
  - Test edge: $0 income → $0 tax
  - Test edge: negative income → $0 tax (loss, no tax payable)
  - Accuracy requirement: all results within $1 of manual calculation (SC-003)
  - Run: `cd backend && uv run pytest tests/unit/modules/tax_planning/test_tax_calculator.py -v`

### Schemas & Exceptions

- [x] T009 [P] Create domain exceptions in `backend/app/modules/tax_planning/exceptions.py`
  - All inherit from `DomainError` (from `app.core.exceptions`)
  - `TaxPlanNotFoundError(DomainError)` — 404
  - `TaxPlanExistsError(DomainError)` — 409, includes existing_plan_id in details
  - `TaxScenarioNotFoundError(DomainError)` — 404
  - `InvalidEntityTypeError(DomainError)` — 400
  - `NoXeroConnectionError(DomainError)` — 400
  - `TaxRateConfigNotFoundError(DomainError)` — 404, for missing rate config
  - `XeroPullError(DomainError)` — 502, wraps Xero API failures
  - `TaxPlanExportError(DomainError)` — 400, e.g. no tax position calculated

- [x] T010 [P] Create Pydantic schemas in `backend/app/modules/tax_planning/schemas.py`
  - Request schemas:
    - `TaxPlanCreate`: xpm_client_id (UUID), financial_year (str, pattern `^\d{4}-\d{2}$`), entity_type (EntityType enum), data_source (DataSource enum), replace_existing (bool, default False)
    - `TaxPlanUpdate`: status (optional), notes (optional), entity_type (optional)
    - `FinancialsInput`: income (dict with revenue, other_income, breakdown), expenses (dict with cost_of_sales, operating_expenses, breakdown), credits (dict with payg_instalments, payg_withholding, franking_credits), adjustments (list), turnover (Decimal), has_help_debt (bool, default False)
    - `XeroPullRequest`: force_refresh (bool, default False)
    - `ChatMessageRequest`: message (str, min_length=1, max_length=2000)
  - Response schemas:
    - `TaxPlanResponse`: all fields from model + client_name (str), scenario_count (int), message_count (int)
    - `TaxPlanListItem`: id, xpm_client_id, client_name, financial_year, entity_type, status, data_source, scenario_count, net_position (optional Decimal), updated_at
    - `TaxPlanListResponse`: items (list[TaxPlanListItem]), total (int), page (int), page_size (int)
    - `TaxScenarioResponse`: all fields from model
    - `TaxScenarioListResponse`: items (list[TaxScenarioResponse]), total (int)
    - `TaxPlanMessageResponse`: id, role, content, scenario_ids, created_at
    - `MessageListResponse`: items, total, page, page_size
    - `FinancialsPullResponse`: financials_data (dict), tax_position (dict), data_freshness (dict)
    - `ChatResponse`: message (TaxPlanMessageResponse), scenarios_created (list), updated_tax_position (optional dict)
    - `TaxRateConfigResponse`: id, rate_type, rates_data, effective_from
    - `TaxRatesResponse`: financial_year (str), rates (list[TaxRateConfigResponse])
  - All response schemas use `ConfigDict(from_attributes=True)`

### Repository

- [x] T011 Implement repository in `backend/app/modules/tax_planning/repository.py`
  - `TaxPlanRepository`:
    - `create(data: dict) -> TaxPlan` — flush, refresh, return
    - `get_by_id(plan_id: UUID, tenant_id: UUID) -> TaxPlan | None`
    - `get_by_client_fy(xpm_client_id: UUID, financial_year: str, tenant_id: UUID) -> TaxPlan | None`
    - `list_by_tenant(tenant_id: UUID, status: str | None, financial_year: str | None, search: str | None, page: int, page_size: int) -> tuple[list[TaxPlan], int]`
    - `update(plan: TaxPlan, data: dict) -> TaxPlan`
    - `delete(plan: TaxPlan) -> None`
  - `TaxScenarioRepository`:
    - `create(data: dict) -> TaxScenario`
    - `get_by_id(scenario_id: UUID, tenant_id: UUID) -> TaxScenario | None`
    - `list_by_plan(tax_plan_id: UUID, tenant_id: UUID) -> list[TaxScenario]`
    - `delete(scenario: TaxScenario) -> None`
    - `get_next_sort_order(tax_plan_id: UUID) -> int`
  - `TaxPlanMessageRepository`:
    - `create(data: dict) -> TaxPlanMessage`
    - `list_by_plan(tax_plan_id: UUID, tenant_id: UUID, page: int, page_size: int) -> tuple[list[TaxPlanMessage], int]`
    - `get_recent_messages(tax_plan_id: UUID, max_tokens: int) -> list[TaxPlanMessage]` — newest first, cumulative token_count up to max_tokens
  - `TaxRateConfigRepository`:
    - `get_rates_for_year(financial_year: str) -> list[TaxRateConfig]`
    - `get_rate(financial_year: str, rate_type: str) -> TaxRateConfig | None`
  - All methods accept `AsyncSession` as first arg, use `flush()` not `commit()`, scope to `tenant_id` where applicable

### Module Registration

- [x] T012 Register router in `backend/app/main.py`
  - Import: `from app.modules.tax_planning.router import router as tax_planning_router`
  - Add: `app.include_router(tax_planning_router, prefix="/api/v1")`
  - Place alongside existing router registrations
  - Note: router.py doesn't exist yet — create a minimal stub with `router = APIRouter(prefix="/tax-plans", tags=["Tax Planning"])`

**Checkpoint**: Foundation ready — all models, migration, calculator, schemas, repository, and module registration complete. User story implementation can begin.

---

## Phase 3: User Story 1+2 — Load Financials & Estimate Tax Position (P1) -- MVP

**Goal**: Accountant selects a client, creates a tax plan, pulls P&L from Xero (or enters manually), and sees the estimated tax position with correct calculations for all entity types.

**Independent Test**: Select client → create plan → pull Xero P&L or enter manually → see taxable income, tax payable, PAYG credits, and net position displayed correctly.

### Backend

- [x] T013 [US1] Implement service layer in `backend/app/modules/tax_planning/service.py`
  - `TaxPlanningService.__init__(self, session: AsyncSession)`
  - `create_plan(tenant_id, data: TaxPlanCreate) -> TaxPlan`
    - Check for existing plan via `repo.get_by_client_fy()` — raise `TaxPlanExistsError` if exists and `replace_existing=False`
    - If `replace_existing=True`, delete existing plan first
    - If `data_source=xero`, verify client has xero_connection_id — raise `NoXeroConnectionError` if not
    - Look up xero_connection_id from `XpmClient` model
    - Create plan with `status=draft`
  - `pull_xero_financials(plan_id: UUID, tenant_id: UUID, force_refresh: bool) -> dict`
    - Load plan, verify has xero_connection_id
    - Call `XeroReportService.get_report(connection_id, report_type="profit_and_loss", period_key="2025-FY", force_refresh=force_refresh)`
    - Transform P&L summary_data to financials_data JSONB format (map revenue, other_income, cost_of_sales, operating_expenses from Xero summary; extract line-item breakdown from rows_data)
    - Calculate months_data_available from period dates
    - If partial year, set `is_annualised=False` (annualisation deferred)
    - Save financials_data on plan, update xero_report_fetched_at
    - Call `_calculate_and_save_position(plan)` to compute tax position
    - Return financials_data + tax_position + data_freshness info
  - `save_manual_financials(plan_id: UUID, tenant_id: UUID, data: FinancialsInput) -> dict`
    - Validate and structure financials_data from input
    - Save on plan, set data_source to `manual` or `xero_with_adjustments`
    - Call `_calculate_and_save_position(plan)`
    - Return financials_data + tax_position
  - `_calculate_and_save_position(plan: TaxPlan) -> dict`
    - Load tax rate configs for plan's financial_year via `TaxRateConfigRepository`
    - Call `calculate_tax_position()` from tax_calculator with financials and rates
    - Save tax_position JSONB on plan
    - If plan status is `draft`, transition to `in_progress`
    - Return tax_position dict
  - `get_plan(plan_id: UUID, tenant_id: UUID) -> TaxPlan` — raise `TaxPlanNotFoundError` if not found
  - `list_plans(tenant_id, status, financial_year, search, page, page_size) -> tuple[list, int]`
  - `update_plan(plan_id, tenant_id, data: TaxPlanUpdate) -> TaxPlan`
  - `delete_plan(plan_id, tenant_id) -> None`
  - Import `XeroReportService` from `app.modules.integrations.xero.service` (service layer, respects module boundaries)
  - Import `XpmClient` lookup via clients module service or direct model query (within service layer)

- [x] T014 [US1] Implement router endpoints in `backend/app/modules/tax_planning/router.py`
  - Replace the minimal stub from T012 with full implementation
  - Dependencies: `DbSession` (async session), `CurrentUser` (auth), tenant_id extraction
  - `POST /tax-plans` → `service.create_plan()` → 201 response
  - `GET /tax-plans` → `service.list_plans()` → paginated list with query params (status, financial_year, search, page, page_size)
  - `GET /tax-plans/{plan_id}` → `service.get_plan()` → full detail with scenarios list
  - `PATCH /tax-plans/{plan_id}` → `service.update_plan()` → updated plan
  - `DELETE /tax-plans/{plan_id}` → `service.delete_plan()` → 204
  - `POST /tax-plans/{plan_id}/financials/pull-xero` → `service.pull_xero_financials()` → financials + tax position + freshness
  - `PUT /tax-plans/{plan_id}/financials` → `service.save_manual_financials()` → financials + tax position
  - `GET /tax-rates/{financial_year}` → load rate configs → rates response
  - Exception handling: catch domain exceptions, convert to HTTPException with correct status codes
  - All endpoints require authentication and extract tenant_id from current user

### Frontend

- [x] T015 [P] [US1] Create TypeScript types in `frontend/src/types/tax-planning.ts`
  - `EntityType` = 'company' | 'individual' | 'trust' | 'partnership'
  - `TaxPlanStatus` = 'draft' | 'in_progress' | 'finalised'
  - `DataSource` = 'xero' | 'manual' | 'xero_with_adjustments'
  - `RiskRating` = 'conservative' | 'moderate' | 'aggressive'
  - `TaxPlan` interface matching TaxPlanResponse
  - `TaxPlanListItem` interface matching list response item
  - `TaxScenario` interface matching TaxScenarioResponse
  - `TaxPlanMessage` interface matching message response
  - `FinancialsData`, `TaxPosition`, `ImpactData` interfaces matching JSONB schemas from data-model.md
  - `TaxPlanCreateRequest`, `FinancialsInput`, `ChatMessageRequest` request types
  - `FinancialsPullResponse`, `ChatResponse`, `TaxRatesResponse` response types

- [x] T016 [P] [US1] Create API wrapper in `frontend/src/lib/api/tax-planning.ts`
  - Follow existing pattern from `frontend/src/lib/api/insights.ts`: export async functions taking `token: string`, use `apiClient.post/get/put/patch/delete` + `apiClient.handleResponse<T>`
  - `createTaxPlan(token, data: TaxPlanCreateRequest): Promise<TaxPlan>`
  - `getTaxPlan(token, planId: string): Promise<TaxPlan>`
  - `listTaxPlans(token, params): Promise<TaxPlanListResponse>`
  - `updateTaxPlan(token, planId, data): Promise<TaxPlan>`
  - `deleteTaxPlan(token, planId): Promise<void>`
  - `pullXeroFinancials(token, planId, forceRefresh): Promise<FinancialsPullResponse>`
  - `saveManualFinancials(token, planId, data: FinancialsInput): Promise<FinancialsPullResponse>`
  - `getTaxRates(token, financialYear): Promise<TaxRatesResponse>`
  - Placeholder stubs for chat/scenario/export endpoints (implemented in later phases)

- [x] T017 [US1] Create ManualEntryForm component in `frontend/src/components/tax-planning/ManualEntryForm.tsx`
  - Use React Hook Form + Zod for validation (follow pattern from `components/requests/RequestForm.tsx`)
  - Zod schema validates: income fields (revenue, other_income ≥ 0), expense fields (cost_of_sales, operating_expenses ≥ 0), credits (payg_instalments, payg_withholding ≥ 0), turnover (≥ 0)
  - Summary totals view as primary: gross income, cost of sales, operating expenses, other income, PAYG credits
  - Optional line-item breakdown per category (collapsible sections per FR-007)
  - Add/remove adjustment rows (description, amount, type: add_back/deduction)
  - Submit calls `saveManualFinancials` API
  - Loading state while saving
  - Use shadcn/ui: Form, FormField, Input, Button, Card, Accordion (for breakdown sections)
  - Use `formatCurrency` from `@/lib/formatters` for amount display
  - Prompt to connect Xero if client has no connection (per acceptance scenario 4)

- [x] T018 [US1] Create FinancialsPanel component in `frontend/src/components/tax-planning/FinancialsPanel.tsx`
  - Displays financials_data in a structured card layout
  - Income section: revenue, other_income, total_income with optional breakdown
  - Expenses section: cost_of_sales, operating_expenses, total_expenses with optional breakdown
  - Credits section: PAYG instalments, PAYG withholding, franking credits
  - Adjustments section: list of add-backs/deductions
  - Data freshness indicator: "Last synced X minutes ago" or "Manually entered"
  - "Refresh from Xero" button (if data_source is xero) calls `pullXeroFinancials(force_refresh=true)`
  - "Edit" button switches to ManualEntryForm
  - Use shadcn/ui: Card, CardHeader, CardContent, Badge, Button
  - Use `formatCurrency` from `@/lib/formatters`
  - Use `cn()` from `@/lib/utils` for conditional classes

- [x] T019 [US2] Create TaxPositionCard component in `frontend/src/components/tax-planning/TaxPositionCard.tsx`
  - Displays tax_position data as a summary card
  - Shows: taxable income, gross tax, offsets (LITO if applicable), Medicare Levy (if individual), HELP repayment (if applicable), total tax payable, credits applied (PAYG instalments, withholding), **net position** (prominent — tax payable or refundable)
  - Net position styling: green if refundable, red/amber if payable
  - Effective tax rate percentage
  - Calculation method label (e.g., "Company — Small Business 25%", "Individual — Marginal Rates")
  - Disclaimer text: "This is an estimate only. Not formal tax advice." (FR-013)
  - Entity-type-aware display: show different fields based on entity_type (e.g., LITO only for individuals, Medicare only for individuals)
  - Use shadcn/ui: Card, CardHeader, CardContent, Badge
  - Use `formatCurrency`, `formatPercentage` from `@/lib/formatters`

- [x] T020 [US1] Create TaxPlanningWorkspace component in `frontend/src/components/tax-planning/TaxPlanningWorkspace.tsx`
  - Main container that orchestrates the tax planning UI for a single client
  - Props: `clientId: string`, `clientName: string`, `xeroConnectionId: string | null`
  - State: `plan: TaxPlan | null`, `loading: boolean`, `error: string | null`
  - On mount: check if a plan exists for this client + current FY ("2025-26") via `listTaxPlans` filtered by client
  - If plan exists: load it. If not: show "Start Tax Plan" button with entity type selector
  - Create plan flow: select entity type → call `createTaxPlan` → if Xero connected, auto-pull financials → show results
  - Replace plan flow: if plan exists, show confirmation dialog before `createTaxPlan(replace_existing=true)`
  - Layout: two-column on desktop — left column (FinancialsPanel + TaxPositionCard), right column (ScenarioChat placeholder + scenarios list)
  - Use `useAuth().getToken()` from `@clerk/nextjs` for auth tokens
  - Use shadcn/ui components throughout

- [x] T021 [US1] Integrate tax planning tab into client detail page
  - Modify `frontend/src/components/client-detail/LedgerCardsHeader.tsx`:
    - Add `'tax-planning'` to the `Tab` union type
    - Add entry to `primaryTabs` array with label "Tax Planning"
  - Modify `frontend/src/app/(protected)/clients/[id]/page.tsx`:
    - Add `'tax-planning'` to `validTabs` array
    - Add conditional render block: `{activeTab === 'tax-planning' && <TaxPlanningWorkspace clientId={...} clientName={...} xeroConnectionId={...} />}`
    - Import `TaxPlanningWorkspace` component
    - Pass client's xero_connection_id from the loaded client data

**Checkpoint**: US1+US2 complete. Accountant can create a tax plan, pull financials from Xero or enter manually, and see accurate tax position for all 4 entity types.

---

## Phase 4: User Story 3 — AI Scenario Modelling via Chat (P1)

**Goal**: Accountant describes a scenario in natural language, AI models 2-3 strategy options with accurate tax calculations, compliance notes, and risk ratings.

**Independent Test**: With a loaded tax plan, type "client wants to prepay $30K rent before June 30" → AI generates scenarios with before/after numbers, risk rating, and compliance notes.

### Backend

- [x] T022 [US3] Create system prompts in `backend/app/modules/tax_planning/prompts.py`
  - `TAX_PLANNING_SYSTEM_PROMPT`: You are a tax planning specialist for Australian taxation. Context includes client's current financial position, entity type, and tax rates. Model 2-3 strategy options for each scenario. Each option must include: title, description, assumptions, impact on taxable income, compliance notes with ATO ruling references, risk rating (conservative/moderate/aggressive), cash flow impact. Always flag Part IVA (anti-avoidance) risk where applicable. All outputs are estimates, not formal tax advice.
  - `TOOL_DESCRIPTIONS`: JSON schema descriptions for the `calculate_tax_position` tool that Claude will call
  - `format_financial_context(financials_data, tax_position, entity_type)` helper to render financial context into the system prompt
  - `format_scenario_history(scenarios: list[TaxScenario])` helper to summarise existing scenarios for context injection

- [x] T023 [US3] Implement TaxPlanningAgent in `backend/app/modules/tax_planning/agent.py`
  - `TaxPlanningAgent.__init__(self, api_key: str, model: str = "claude-sonnet-4-20250514")`
  - Use `anthropic.AsyncAnthropic` client (async, per research R3)
  - `async def process_message(self, message: str, plan: TaxPlan, conversation_history: list[dict], rate_configs: dict) -> AgentResponse`
    - Build system prompt with financial context, scenario history, and rate configs
    - Build messages array: system prompt + conversation history (up to token limit) + new user message
    - Define tool: `calculate_tax_position` — accepts entity_type, modified financials, and returns deterministic tax calculation
    - Call `client.messages.create()` with tools, max_tokens=4000
    - Handle tool_use blocks: when Claude calls `calculate_tax_position`, execute the tax calculator with the provided inputs, return result to Claude
    - Loop until Claude produces a final text response (handle multiple tool calls)
    - Parse response: extract scenario data (title, description, assumptions, impact_data, risk_rating, compliance_notes, cash_flow_impact)
    - Return `AgentResponse(content=str, scenarios=list[dict], token_usage=dict)`
  - `async def process_message_streaming(self, message, plan, conversation_history, rate_configs) -> AsyncGenerator`
    - Same as `process_message` but yields SSE events during streaming
    - Yield `thinking` events during tool processing
    - Yield `content` events for text chunks
    - Yield `scenario` events when scenario data is extracted
    - Yield `done` event at end
  - `AgentResponse` dataclass: content (str), scenarios (list[dict]), token_usage (dict)

- [x] T024 [US3] Add chat and scenario methods to service in `backend/app/modules/tax_planning/service.py`
  - `async def send_chat_message(self, plan_id: UUID, tenant_id: UUID, message: str) -> ChatResponse`
    - Load plan with financials and tax_position (raise if no financials loaded)
    - Load conversation history via `message_repo.get_recent_messages(max_tokens=8000)`
    - Load rate configs for plan's financial_year
    - Save user message to `tax_plan_messages`
    - Call `TaxPlanningAgent.process_message()`
    - For each scenario in response: create `TaxScenario` record via scenario_repo
    - Save assistant message with scenario_ids
    - Return ChatResponse with message + scenarios_created
  - `async def send_chat_message_streaming(self, plan_id, tenant_id, message) -> AsyncGenerator`
    - Same flow but uses `agent.process_message_streaming()`
    - Yields SSE events for the router to stream
    - Saves message and scenarios after streaming completes
  - `async def list_scenarios(self, plan_id, tenant_id) -> list[TaxScenario]`
  - `async def delete_scenario(self, plan_id, tenant_id, scenario_id) -> None`
  - `async def list_messages(self, plan_id, tenant_id, page, page_size) -> tuple[list, int]`

- [x] T025 [US3] Add chat and scenario router endpoints in `backend/app/modules/tax_planning/router.py`
  - `POST /tax-plans/{plan_id}/chat` → `service.send_chat_message()` → ChatResponse
  - `POST /tax-plans/{plan_id}/chat/stream` → `service.send_chat_message_streaming()` → `StreamingResponse(media_type="text/event-stream")`
    - SSE format: `data: {json}\n\n` per event
    - Event types: thinking, content, scenario, done, error
    - Follow existing pattern from `backend/app/modules/agents/router.py` streaming endpoint
  - `GET /tax-plans/{plan_id}/messages` → `service.list_messages()` → paginated list
  - `GET /tax-plans/{plan_id}/scenarios` → `service.list_scenarios()` → scenario list
  - `DELETE /tax-plans/{plan_id}/scenarios/{scenario_id}` → `service.delete_scenario()` → 204

### Frontend

- [x] T026 [P] [US3] Create ScenarioCard component in `frontend/src/components/tax-planning/ScenarioCard.tsx`
  - Displays a single scenario with: title, description, risk rating badge (conservative=green, moderate=amber, aggressive=red), assumptions list, before/after/change impact data, compliance notes, cash flow impact
  - Expandable/collapsible detail section (assumptions + compliance notes)
  - Delete button with confirmation
  - Use `formatCurrency` from `@/lib/formatters`
  - Use shadcn/ui: Card, Badge, Button, Collapsible, Alert (for compliance warnings)

- [x] T027 [P] [US3] Create ComparisonTable component in `frontend/src/components/tax-planning/ComparisonTable.tsx`
  - Side-by-side comparison of all scenarios for a plan
  - Columns: Scenario title, Taxable Income Change, Tax Saving, Cash Flow Impact, Risk Rating, Net Benefit
  - Sorted by net benefit (highest first)
  - Highlight best option with a subtle indicator
  - Use shadcn/ui: Table, TableHeader, TableBody, TableRow, TableCell, Badge
  - Use `formatCurrency` from `@/lib/formatters`

- [x] T028 [US3] Create ScenarioChat component in `frontend/src/components/tax-planning/ScenarioChat.tsx`
  - Chat interface following pattern from `frontend/src/components/feedback/ConversationChat.tsx`
  - Message display: user messages right-aligned (primary bg), assistant messages left-aligned (muted bg)
  - Auto-scroll to newest message via `messagesEndRef`
  - Auto-resize textarea for input
  - Enter to send, Shift+Enter for newline
  - Streaming SSE support: follow pattern from `frontend/src/lib/api/agents.ts` `agentChatStream()`
    - Read `text/event-stream` via `ReadableStream` reader
    - Handle event types: thinking (show indicator), content (append to message), scenario (add to scenarios list), done (finalize), error (show error)
  - Loading/thinking indicator during AI processing
  - When AI creates scenarios: emit event to parent to refresh scenarios list
  - "Compare all options" button when 2+ scenarios exist → scrolls to ComparisonTable
  - Add streaming API function to `frontend/src/lib/api/tax-planning.ts`:
    - `chatStream(token, planId, message): AsyncGenerator<ChatStreamEvent>`
    - `sendChatMessage(token, planId, message): Promise<ChatResponse>`
    - `listMessages(token, planId, page?, pageSize?): Promise<MessageListResponse>`
    - `listScenarios(token, planId): Promise<TaxScenarioListResponse>`
    - `deleteScenario(token, planId, scenarioId): Promise<void>`

- [x] T029 [US3] Wire ScenarioChat, ScenarioCard, and ComparisonTable into TaxPlanningWorkspace
  - Update `frontend/src/components/tax-planning/TaxPlanningWorkspace.tsx`:
  - Right column layout: ScenarioChat at top, scenario cards below, ComparisonTable at bottom (shown when 2+ scenarios)
  - State management: scenarios list, messages list, loading states
  - On scenario created (from chat): add to scenarios list, refresh scenario display
  - On scenario deleted: remove from list
  - Pass plan financials and tax position context to ScenarioChat for display context
  - Load existing messages and scenarios on mount (for plan resumption)

**Checkpoint**: US3 complete. Full AI scenario modelling working — accountant types scenarios in chat, AI generates strategy options with accurate tax calculations, scenarios displayed with comparison table.

---

## Phase 5: User Story 4 — Export Tax Plan Summary (P2)

**Goal**: Accountant exports a formatted PDF showing client's tax position, scenarios compared, and recommended strategy with practice branding and disclaimer.

**Independent Test**: After modelling scenarios, click export → receive a PDF with client name, FY, tax position, scenarios table, and disclaimer.

- [x] T030 [US4] Create Jinja2 PDF template in `backend/app/modules/tax_planning/templates/tax_plan_export.html`
  - HTML template with embedded CSS (weasyprint compatible)
  - Header: practice name (from tenant settings), date, "Tax Planning Summary" title
  - Client section: client name, ABN (if available), financial year, entity type
  - Tax Position section: taxable income, tax payable, credits, net position, effective rate
  - Scenarios section: comparison table (if include_scenarios=true) with all scenario details
  - Each scenario: title, description, impact data, risk rating, compliance notes
  - Conversation section (if include_conversation=true): formatted chat history
  - Footer: disclaimer "This document is an estimate prepared for discussion purposes only. It does not constitute formal tax advice. Please consult your tax professional for specific advice." (FR-013)
  - Footer: practice name, generated date, "Prepared with Clairo"
  - Clean, professional styling: use system fonts, clear headings, table borders, adequate spacing
  - Client-friendly language (not accounting jargon per acceptance scenario 2)

- [x] T031 [US4] Implement PDF export in service in `backend/app/modules/tax_planning/service.py`
  - `async def export_plan_pdf(self, plan_id: UUID, tenant_id: UUID, include_scenarios: bool = True, include_conversation: bool = False) -> bytes`
    - Load plan with financials, tax_position (raise `TaxPlanExportError` if no tax_position)
    - Load scenarios if include_scenarios
    - Load messages if include_conversation
    - Load tenant settings for practice name/branding
    - Render Jinja2 template with context
    - Convert HTML to PDF via `weasyprint.HTML(string=html).write_pdf()`
    - Return PDF bytes

- [x] T032 [US4] Add export endpoint in `backend/app/modules/tax_planning/router.py`
  - `GET /tax-plans/{plan_id}/export` with query params: include_scenarios (bool, default true), include_conversation (bool, default false)
  - Return `Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=\"tax-plan-{client_name_slug}-{fy}.pdf\""})`
  - Handle errors: 400 if no tax position calculated

- [x] T033 [US4] Add export button to TaxPlanningWorkspace in `frontend/src/components/tax-planning/TaxPlanningWorkspace.tsx`
  - Add "Export PDF" button in the workspace header (next to plan status/title)
  - Only enabled when plan has a calculated tax_position
  - On click: call `GET /tax-plans/{planId}/export` and trigger browser download
  - Add export API function to `frontend/src/lib/api/tax-planning.ts`:
    - `exportPlanPdf(token, planId, includeScenarios?, includeConversation?): Promise<Blob>`
  - Loading state while PDF generates
  - Use shadcn/ui: Button with download icon

**Checkpoint**: US4 complete. Accountant can export tax plan as a branded PDF document.

---

## Phase 6: User Story 5 — Save and Resume Tax Plans (P2)

**Goal**: Accountant can navigate away, come back later, and resume a tax plan with all data preserved. Plans list shows all plans with status and last updated.

**Independent Test**: Create a tax plan → navigate away → return → plan is loaded with all data and chat history preserved. Changed Xero data is highlighted.

- [x] T034 [US5] Add Xero change detection to service in `backend/app/modules/tax_planning/service.py`
  - `async def check_xero_changes(self, plan_id: UUID, tenant_id: UUID) -> dict | None`
    - Load plan, check if data_source is xero and xero_connection_id is set
    - Fetch current P&L summary from Xero cache (without force refresh)
    - Compare current summary values with stored financials_data
    - Return dict of changed fields (field_name: {old, new}) or None if no changes
    - Used by frontend to show "Xero data has changed since you last worked on this plan"

- [x] T035 [US5] Add plan list and status management to TaxPlanningWorkspace in `frontend/src/components/tax-planning/TaxPlanningWorkspace.tsx`
  - On mount, if plan exists for client+FY:
    - Load full plan with scenarios and messages
    - Check for Xero changes via `check_xero_changes` (if data_source is xero)
    - If changes detected: show banner "Xero data has changed since {last_fetched}. Refresh?" with accept/dismiss
    - Accept: call `pullXeroFinancials(force_refresh=true)` to update
  - Status badge on plan header: Draft (gray), In Progress (blue), Finalised (green)
  - "Finalise" button to mark plan as complete (PATCH status=finalised)
  - "Reopen" button on finalised plans (PATCH status=in_progress)
  - Add `checkXeroChanges(token, planId): Promise<XeroChanges | null>` to `frontend/src/lib/api/tax-planning.ts`

**Checkpoint**: US5 complete. Full save/resume working with Xero change detection.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Audit events, disclaimers, error handling, final integration

- [x] T036 [P] Add audit events to service layer in `backend/app/modules/tax_planning/service.py`
  - Emit audit events per spec auditing checklist:
    - `taxplan.created` — on plan creation (client ID, FY, entity type, data source)
    - `taxplan.financials.loaded` — on Xero pull or manual save (income totals, expense totals, source)
    - `taxplan.scenario.created` — on scenario creation (description, projected figures, risk rating)
    - `taxplan.exported` — on PDF export (format, timestamp)
    - `integration.xero.pnl_pulled` — on Xero API call (client Xero org ID, date range, status)
  - Use `await audit_event()` from `app.core.audit` or event bus per constitution

- [x] T037 [P] Ensure disclaimers on all AI outputs
  - Backend: append disclaimer text to all assistant messages in `agent.py`
  - Frontend: TaxPositionCard already has disclaimer (T019)
  - Frontend: ScenarioCard shows compliance notes
  - Frontend: ComparisonTable footer includes disclaimer
  - PDF template already includes disclaimer (T030)
  - Verify FR-013 compliance across all output surfaces

- [x] T038 [P] Run linting and type checking
  - Run: `cd backend && uv run ruff check . && uv run ruff format .`
  - Run: `cd frontend && npm run lint && npx tsc --noEmit`
  - Fix any issues

- [x] T039 Run full validation
  - Run: `cd backend && uv run pytest`
  - Run quickstart.md verification scenarios manually:
    1. Company tax: $500K revenue, $350K expenses → verify $37,500 tax
    2. Individual tax: $90K taxable → verify marginal rates + Medicare + LITO
    3. AI scenario: "prepay $30K rent" → verify scenario with accurate numbers
    4. Export: verify PDF has practice branding, scenarios, disclaimer
    5. Resume: close and reopen plan → verify persistence

---

## Phase FINAL: PR & Merge

- [ ] TFINAL-1 Ensure all tests pass
  - Run: `cd backend && uv run ruff check . && uv run pytest && cd ../frontend && npm run lint && npx tsc --noEmit`

- [ ] TFINAL-2 Push branch and create PR
  - Run: `git push -u origin 049-ai-tax-planning`
  - Run: `gh pr create --title "Spec 049: AI Tax Planning & Advisory" --body "..."`
  - PR body: summary of changes, new tables, new module, user stories delivered

- [ ] TFINAL-3 Address review feedback (if any)

- [ ] TFINAL-4 Merge PR to main
  - Squash merge after approval
  - Delete feature branch after merge

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 0 (Git)**: First
- **Phase 1 (Setup)**: After Phase 0
- **Phase 2 (Foundational)**: After Phase 1 — BLOCKS all user stories
- **Phase 3 (US1+US2)**: After Phase 2 — MVP deliverable
- **Phase 4 (US3)**: After Phase 3 (needs financials loaded to model scenarios)
- **Phase 5 (US4)**: After Phase 3 (needs tax position for export), can parallel with Phase 4
- **Phase 6 (US5)**: After Phase 3, can parallel with Phase 4 and 5
- **Phase 7 (Polish)**: After all user stories complete
- **Phase FINAL**: After Phase 7

### User Story Dependencies

- **US1+US2 (P1)**: No dependencies on other stories — can start after foundational
- **US3 (P1)**: Depends on US1+US2 (needs loaded financials + tax position for scenario context)
- **US4 (P2)**: Depends on US1+US2 (needs tax position for PDF). Can parallel with US3.
- **US5 (P2)**: Depends on US1+US2 (needs plan CRUD). Can parallel with US3 and US4.

### Parallel Opportunities

Within Phase 2:
- T009 (exceptions) and T010 (schemas) can run in parallel
- T007 (tax calculator) can start as soon as T004 (models) provides enum types

Within Phase 3 (US1+US2):
- T015 (types) and T016 (API wrapper) can run in parallel with backend tasks
- T017 (ManualEntryForm) and T018 (FinancialsPanel) and T019 (TaxPositionCard) can run in parallel

Within Phase 4 (US3):
- T026 (ScenarioCard) and T027 (ComparisonTable) can run in parallel

Phases 4, 5, 6 can run in parallel after Phase 3 completes (if multiple developers).

---

## Parallel Example: Phase 3 Frontend

```
# These can all run in parallel (different files, no dependencies):
T015: Create TypeScript types in frontend/src/types/tax-planning.ts
T016: Create API wrapper in frontend/src/lib/api/tax-planning.ts

# Then these can run in parallel (different components):
T017: ManualEntryForm component
T018: FinancialsPanel component
T019: TaxPositionCard component

# Then sequential (depends on above):
T020: TaxPlanningWorkspace (composes above components)
T021: Tab integration (depends on workspace)
```

---

## Implementation Strategy

### MVP First (Phase 3: US1+US2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (models, migration, calculator, schemas, repo)
3. Complete Phase 3: US1+US2 — Load Financials & Estimate Tax Position
4. **STOP and VALIDATE**: Accountant can create plan → pull Xero → see tax position
5. This alone is valuable for EOFY season — the "15 minutes to 2 minutes" time saving

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1+US2 → Tax position estimator works → **MVP Demo** (5-10 practice trials can start)
3. US3 → AI scenario chat → **Full demo moment** ("describe scenario → get tax impact")
4. US4 → PDF export → **Workflow-complete** (accountant has deliverable for client meeting)
5. US5 → Save/resume → **Production-ready** (iterative workflow supported)

---

## Notes

- [P] tasks = different files, no dependencies on other in-progress tasks
- [Story] label maps task to user story for traceability
- Tax calculator unit tests (T008) are critical — verify accuracy to within $1 before proceeding
- AI agent (T023) requires ANTHROPIC_API_KEY in environment
- weasyprint may require system-level dependencies (Cairo, Pango) — check quickstart.md
- Commit after each task or logical group
