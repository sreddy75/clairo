# Research: AI Tax Planning & Advisory

**Branch**: `049-ai-tax-planning` | **Date**: 2026-03-31

---

## R1: Xero P&L Data Acquisition Strategy

**Decision**: Reuse the existing `XeroReportService.get_report()` pipeline with `report_type=PROFIT_AND_LOSS` and `period_key="2025-FY"` (Australian FY July-June). No new Xero API integration required.

**Rationale**:
- The full P&L pipeline already exists: `XeroClient.get_profit_and_loss()` → `ProfitAndLossTransformer.extract_profit_and_loss_summary()` → cached in `xero_reports` table with TTL-based freshness.
- Summary data provides all fields needed for tax estimation: `revenue`, `other_income`, `total_income`, `cost_of_sales`, `operating_expenses`, `gross_profit`, `net_profit`.
- Raw row data (`rows_data` JSONB) available for line-item breakdown if the accountant wants granularity beyond summary totals.
- Cache TTL for current-period P&L is 1 hour. The spec's "stale if >24h" requirement is already exceeded — data is fresher than required.
- Australian FY period key parsing is built in: `"2025-FY"` → `from_date=2025-07-01`, `to_date=2026-06-30`.

**Alternatives Considered**:
- **Build a separate P&L fetcher**: Rejected — duplicates existing pipeline with no benefit. The existing transformer already categorises income and expenses by type.
- **Use Balance Sheet data alongside P&L**: Deferred to Phase 2. P&L alone is sufficient for income tax estimation.

**Implementation Notes**:
- Entity chain: `XpmClient.xero_connection_id` → `XeroConnection.id` → `XeroReport.connection_id` (with `report_type=profit_and_loss`, `period_key="2025-FY"`).
- The `force_refresh` parameter on `get_report()` can trigger a fresh Xero API call when the accountant explicitly requests updated data.
- For annualisation of partial-year data: calculate months elapsed from `period_start` to today, scale summary figures proportionally. This is a new calculation, not available from existing pipeline.

---

## R2: Tax Calculation Engine Architecture

**Decision**: Build a pure-function tax calculation engine as a standalone service (`tax_calculator.py`) within the `tax_planning` module. No external tax calculation API. All Australian tax rates stored in a `tax_rate_config` table with version tracking.

**Rationale**:
- Australian tax rates change annually via legislation. Storing them in a database table (not hardcoded) allows updates without code deployment — satisfying spec requirement FR-002.
- Tax calculation for Phase 1 is deterministic: given `(entity_type, taxable_income, financial_year, payg_credits)`, the result is a fixed set of outputs. No AI/LLM needed for the calculation itself.
- The four entity types each have distinct calculation logic:
  - **Company**: 25% (small business, turnover < $50M) or 30% (standard).
  - **Individual**: 2025-26 marginal rates (0%, 16%, 30%, 37%, 45%) + Medicare Levy (2%) + LITO + optional HELP/HECS.
  - **Trust**: 47% on undistributed income (no distribution modelling in Phase 1).
  - **Partnership**: Net income at entity level, taxed in partner's hands at individual rates (simplified single-partner view).

**Alternatives Considered**:
- **Use an external tax calculation API (e.g., TaxCalc)**: Rejected — adds external dependency, cost, and latency for calculations that are straightforward to implement. Australian individual/company tax is well-defined.
- **Hardcode rates in Python constants**: Rejected — violates spec requirement that rates be updatable without code deployment.
- **Use LLM for tax calculation**: Rejected — LLMs hallucinate numbers. Tax calculation must be deterministic and verifiable to within $1 (SC-003).

**Implementation Notes**:
- 2025-26 individual tax brackets: $0-$18,200 (0%), $18,201-$45,000 (16%), $45,001-$135,000 (30%), $135,001-$190,000 (37%), $190,001+ (45%).
- LITO: $700 for income ≤ $37,500, reduces by 5c/$1 for $37,501-$45,000, then 1.5c/$1 for $45,001-$66,667.
- Medicare Levy: 2% of taxable income, with low-income thresholds ($26,000 single, phase-in $26,001-$32,500).
- HELP repayment: 2025-26 thresholds start at $54,435 (1%), max 10% at $151,201+.

---

## R3: AI Agent Architecture for Scenario Modelling

**Decision**: Build a standalone `TaxPlanningAgent` class with its own router endpoints, dedicated system prompt, and direct Claude API calls. Do NOT route through the existing `MultiPerspectiveOrchestrator`.

**Rationale**:
- The existing orchestrator is designed for general-purpose accounting queries with perspective detection. Tax planning requires a fundamentally different interaction model: multi-turn conversation with persistent financial context, structured scenario output, and deterministic tax recalculation after each scenario.
- Tax planning needs **tool-use**: the AI must call the tax calculation engine to produce accurate numbers, not generate numbers from the LLM (which would hallucinate). The current orchestrator does not use tool-use — it's a single-turn prompt-only system.
- The standalone agent pattern already exists (`QueryVisualizationAgent`, `DaySummaryAgent`) and is the established way to build domain-specific agents in Clairo.
- Conversation history must persist per tax plan (not per generic chat session), requiring a dedicated message store.

**Alternatives Considered**:
- **Add a `TAX_PLANNING` perspective to the orchestrator**: Rejected — the orchestrator is single-turn, no tool-use, and not designed for multi-turn conversational scenarios. Would require too much refactoring.
- **Use `options_format=True` strategy mode**: Rejected — this still produces LLM-generated numbers without deterministic tax calculation. Tax figures must be computed, not generated.
- **Use LangChain/LangGraph tools pattern**: Rejected — the existing tool definitions in `agents/tools/` are not wired into the orchestrator. Building our own tool-use with the Anthropic SDK directly is simpler and more predictable.

**Implementation Notes**:
- Use `anthropic.AsyncAnthropic` (not sync) for non-blocking LLM calls.
- Model: `claude-sonnet-4-20250514` (consistent with agent framework settings).
- System prompt includes: client financial context, current tax position, Australian tax rules, available strategies, compliance warnings.
- Tool-use: expose `calculate_tax_position` tool to the LLM so it can compute accurate before/after numbers for each scenario.
- Streaming via SSE for real-time response delivery (follow existing `agentChatStream` pattern).
- Max response tokens: 4000 (consistent with agent settings).

---

## R4: Data Model — Tax Plan Lifecycle

**Decision**: Single `tax_plans` table with status tracking, one-to-many `tax_scenarios`, one-to-many `tax_plan_messages` for conversation history. Financials stored as JSONB within the tax plan (not a separate table) since there's exactly one financial snapshot per plan.

**Rationale**:
- Spec mandates one plan per client per FY (FR-008): unique constraint on `(xpm_client_id, financial_year)`.
- Financials are always 1:1 with the plan — a separate table adds join overhead with no normalization benefit.
- Scenarios are 1:N — each AI-generated scenario is a distinct record with its own impact calculations, risk rating, and compliance notes.
- Conversation messages are 1:N — preserving full chat history enables context-aware follow-ups and plan resumption.

**Alternatives Considered**:
- **Separate `tax_plan_financials` table**: Rejected — always 1:1 with plan, no independent lifecycle. JSONB column on `tax_plans` is simpler.
- **Reuse `chat_conversations`/`chat_messages` from agents module**: Rejected — tax plan conversations have a different lifecycle (tied to plan, not to a generic chat session) and need additional fields (scenario references).
- **Store scenarios as JSONB array on tax plan**: Rejected — scenarios need independent CRUD, status tracking, and references from conversation messages.

**Implementation Notes**:
- `tax_plans.financials_data` (JSONB): stores `{source, income: {revenue, other_income, ...}, expenses: {cost_of_sales, operating_expenses, ...}, credits: {payg_instalments, payg_withholding}, adjustments: [...]}`.
- `tax_plans.tax_position` (JSONB): stores the calculated base tax position `{taxable_income, tax_payable, credits_total, net_position, calculation_details: {...}}`.
- `tax_scenarios.impact_data` (JSONB): stores `{taxable_income_change, tax_payable_change, net_benefit, cash_flow_impact}`.
- Status flow: `draft` → `in_progress` → `finalised`.

---

## R5: Frontend Integration — Client Detail Tab vs. Separate Page

**Decision**: Add "Tax Planning" as a primary tab in the client detail page (`LedgerCardsHeader`), rendering the full tax planning interface inline. Deep-linking via `?tab=tax-planning`.

**Rationale**:
- Tax planning is a client-scoped activity — the accountant is always working in the context of a specific client. A separate route would break the client-detail navigation flow.
- The existing tab system supports deep-linking via URL search params. Adding `tax-planning` to `primaryTabs` gives it top-level visibility alongside Overview, BAS, and Insights.
- The tax planning interface is complex (financials + chat + scenarios) but fits within the existing tab content area pattern — other tabs like BAS and Insights already have comparable complexity.

**Alternatives Considered**:
- **Separate route `/clients/[id]/tax-planning/`**: Rejected — breaks the single-page client experience. Other comparable features (BAS, Insights) are tabs, not separate routes.
- **Modal/drawer overlay**: Rejected — tax planning is a full working session, not a quick action. Needs full screen real estate.

**Implementation Notes**:
- Add `'tax-planning'` to `Tab` union type in `LedgerCardsHeader.tsx`.
- Add to `primaryTabs` array (top-level, alongside Overview, BAS, Insights).
- Add to `validTabs` whitelist in `page.tsx`.
- Tax planning tab content is a self-contained component (`TaxPlanningWorkspace`) that manages its own state.

---

## R6: PDF Export Strategy

**Decision**: Server-side PDF generation using `weasyprint` (Python library). Template rendered as HTML with Jinja2, converted to PDF.

**Rationale**:
- PDF export needs consistent formatting regardless of browser/OS — server-side generation ensures this.
- `weasyprint` is a mature, well-supported HTML-to-PDF converter that handles CSS well. No headless browser required.
- Jinja2 templates allow branding customisation (practice name, logo from tenant settings) without code changes.
- The export endpoint returns the PDF directly as a file download — no intermediate storage needed for Phase 1.

**Alternatives Considered**:
- **Client-side PDF (jsPDF, react-pdf)**: Rejected — inconsistent rendering, limited CSS support, can't access tenant branding server-side.
- **Headless Chrome (Puppeteer)**: Rejected — heavy dependency, overkill for a structured document.
- **LaTeX**: Rejected — steep learning curve for template customisation, unnecessary complexity.
- **Third-party PDF API (e.g., PDFShift)**: Rejected — adds external dependency and cost.

**Implementation Notes**:
- New dependency: `weasyprint` (add to `pyproject.toml`).
- Template location: `backend/app/modules/tax_planning/templates/tax_plan_export.html`.
- Endpoint: `GET /api/v1/tax-plans/{id}/export` returns `application/pdf`.
- Template includes: practice name/branding, client name, FY, current tax position, scenarios comparison table, recommended strategy, disclaimer.

---

## R7: Tax Rate Configuration Storage

**Decision**: Store tax rates in a `tax_rate_configs` table with `financial_year` as the primary key, rates stored as JSONB. Seed 2025-26 rates via Alembic data migration.

**Rationale**:
- Spec explicitly requires rates not be hardcoded (edge case: "tax rates stored as configuration data, not hardcoded").
- A database table allows admin updates without redeployment.
- JSONB storage provides flexibility for the different rate structures across entity types (marginal brackets for individuals, flat rates for companies, LITO thresholds, HELP thresholds, Medicare thresholds).
- Financial year as key ensures historical rate preservation — past plans always reference the rates they were calculated with.

**Alternatives Considered**:
- **Python constants file**: Rejected — requires code deployment to update rates.
- **Environment variables**: Rejected — too complex for structured rate tables with brackets and thresholds.
- **External config service**: Rejected — unnecessary complexity for a single configuration domain.
- **JSON file in repo**: Rejected — still requires deployment to update.

**Implementation Notes**:
- Table: `tax_rate_configs` with `financial_year` (string, e.g., "2025-26"), `entity_type` (nullable — shared rates like Medicare apply to all), `rates_data` (JSONB), `effective_from` (date).
- Unique constraint on `(financial_year, entity_type)`.
- JSONB structure varies by entity type:
  - Individual: `{brackets: [{min, max, rate}], medicare_levy: {rate, low_threshold, phase_in_threshold}, lito: {max_offset, ...}, help: {thresholds: [{min, rate}]}}`
  - Company: `{small_business_rate, standard_rate, small_business_turnover_threshold}`
  - Trust: `{undistributed_rate}`
- Seed data in Alembic migration for 2025-26.

---

## R8: Conversation Persistence and Context Window Management

**Decision**: Store conversation messages in a dedicated `tax_plan_messages` table. Inject the last N messages (up to context token limit) into the system prompt for each AI call. Do not use the existing `chat_conversations`/`chat_messages` tables.

**Rationale**:
- Tax plan conversations are tied to a specific plan lifecycle, not a generic chat session. When a plan is replaced (FR-008: new plan replaces old), its conversation history should be replaced too.
- The AI needs financial context + conversation history + scenario history in every call. Managing the context window requires prioritising: financial data first, recent messages, then older messages.
- A dedicated table allows tax-plan-specific fields (e.g., `scenario_id` reference for messages that triggered scenario generation).

**Alternatives Considered**:
- **Reuse `chat_conversations`/`chat_messages`**: Rejected — different lifecycle management, missing plan-specific fields.
- **Store messages as JSONB array on tax plan**: Rejected — unbounded growth, hard to query individual messages, no pagination.
- **Use Anthropic's conversation API (stateful)**: Not available — the Anthropic SDK is stateless; we manage conversation state ourselves.

**Implementation Notes**:
- `tax_plan_messages` table: `id`, `tax_plan_id` (FK), `tenant_id`, `role` (user/assistant), `content` (text), `scenario_ids` (array of UUIDs — scenarios referenced in this message), `token_count` (int), `created_at`.
- Context injection: sum `token_count` from newest to oldest, stop when approaching `max_context_tokens` (12000). Always include the system prompt + financial context first.
- Scenario summaries are injected into the system prompt so the AI knows what's already been modelled.
