# Feature Specification: AI Tax Planning & Advisory

**Feature Branch**: `049-ai-tax-planning-advisory`
**Created**: 2026-03-29
**Status**: Draft (Team Alignment)
**Phase**: NEW — Fast-Track GTM (Pre-Phase E.5)
**Input**: Unni's tax planning proposal + strategic analysis

---

## Clarifications

### Session 2026-03-29

- Q: Which entity types does Phase 1 support for tax estimation? → A: Company, Individual/Sole Trader, Trust, and Partnership (basic calculations, no trust distribution modelling)
- Q: Can an accountant create multiple tax plans for the same client in the same FY? → A: No — one plan per client per FY. Creating a new plan replaces the previous one.
- Q: Does Phase 1 support only the current FY or also prior years? → A: Current FY only (2025–26). Prior year support deferred.
- Q: What level of detail does the manual entry form capture? → A: Hybrid — summary totals by tax-relevant category as the primary view, with optional line-item breakdown per category for accountants who want more granularity.
- Q: Should there be AI scenario usage limits per plan or tenant? → A: No limits for Phase 1 MVP. Monitor costs manually during trial period.

---

## Strategic Context

### Why Tax Planning, Why Now

BAS compliance is a cost centre — practices do it because they must. Tax planning is a **revenue generator** — it's advisory work billed at premium rates. The sales conversation changes from "replace your current process" to "this tool pays for itself."

**EOFY window**: April–June is when every accountant runs tax planning conversations with clients. We don't need to convince them of a workflow change — we accelerate work they're already doing. This is the lowest-friction trial path to our first 10 paying customers.

**Xero integration = unfair advantage**: Every accountant currently types numbers from Xero into a spreadsheet manually. We already have the Xero connection. Pulling the P&L directly eliminates the most tedious step in tax planning.

**GTM flywheel**: Acquire customers with advisory (immediate value) → expand into compliance (recurring volume). This is a better entry point than leading with BAS.

### Phased Delivery

| Phase | Scope | Timeline | Goal |
|-------|-------|----------|------|
| **Phase 1 (MVP)** | Single-entity tax estimator + AI scenarios | 2 weeks | Usable for EOFY season, 5–10 practice trials |
| **Phase 2** | Multi-entity groups, trust distributions, full Unni spec | 4–6 weeks after MVP | Convert trials to paying subscribers |

**This spec covers Phase 1 (MVP) only.** Phase 2 will be a separate spec after Phase 1 validation.

### Disruption Level

Low (fully additive — new module, no changes to existing modules)

---

## User Scenarios & Testing

### User Story 1 — Pull Client Financials from Xero (Priority: P1)

As an accountant, I want to pull a client's Profit & Loss from Xero into the tax planning tool so I don't have to manually type figures into a spreadsheet.

**Why this priority**: This is the single biggest time-saver. Every tax planning session starts with "get the numbers" — today that's 15–30 minutes of manual data entry per client. Automating this is what makes the tool immediately valuable.

**Independent Test**: Select a client → pull P&L → see revenue, expenses, and net profit pre-populated and ready for tax estimation.

**Acceptance Scenarios**:

1. **Given** a client with a connected Xero organisation, **When** I start a new tax plan, **Then** the system pulls the current-year P&L and pre-fills gross income, cost of sales, and operating expenses.

2. **Given** a Xero P&L with multiple income streams (trading income, interest, dividends), **When** the data is pulled, **Then** each income type is categorised separately for tax calculation purposes.

3. **Given** a client whose Xero data was last synced more than 24 hours ago, **When** I start a tax plan, **Then** the system triggers a fresh sync before populating figures, with a loading indicator.

4. **Given** a client with no Xero connection, **When** I start a tax plan, **Then** the system presents a manual entry form with all required fields, with a prompt to connect Xero.

---

### User Story 2 — Estimate Tax Position (Priority: P1)

As an accountant, I want to see an estimated tax position for my client based on their current financials so I can advise them on where they stand before EOFY.

**Why this priority**: This is the core output — the thing the accountant walks into a client meeting with. Without it, the tool is just a data viewer.

**Independent Test**: After financials are loaded, see a calculated tax estimate showing taxable income, tax payable, PAYG credits, and net position.

**Acceptance Scenarios**:

1. **Given** a company client with $500K revenue and $350K expenses, **When** I view the tax estimate, **Then** I see: taxable income ($150K), company tax at 25% ($37,500), any PAYG instalments already paid, and net tax payable/refundable.

2. **Given** an individual client (sole trader), **When** I view the tax estimate, **Then** I see: taxable income, marginal tax rates applied correctly (2025–26 rates), Medicare Levy (2%), PAYG withholding credits, HELP/HECS repayment (if applicable), and net position.

3. **Given** a small business entity (turnover < $50M), **When** calculating company tax, **Then** the system applies the 25% small business rate, not the 30% standard rate.

4. **Given** an individual with taxable income of $45,000, **When** calculating tax, **Then** the system correctly applies: 0% on first $18,200, 16% on $18,201–$45,000, Medicare Levy of 2%, and Low Income Tax Offset (LITO).

---

### User Story 3 — AI Scenario Modelling via Chat (Priority: P1)

As an accountant, I want to describe a client's situation in natural language and get the AI to model tax scenarios so I can quickly evaluate strategies without building spreadsheet tabs.

**Why this priority**: This is the differentiator. "Client has $80K cash, $30K ATO debt, wants to buy a $60K vehicle" → AI models multiple options with actual numbers. This is the demo moment that makes every accountant think of three clients they'd use it for.

**Independent Test**: Type a scenario description → AI generates 2–3 strategy options with projected tax impact, comparison table, and a recommendation.

**Acceptance Scenarios**:

1. **Given** a tax plan with loaded financials, **When** I type "client wants to prepay 6 months of rent ($30K) before June 30", **Then** the AI models: current tax position vs. position with prepayment, shows tax saving, and notes the prepayment rules (must be < 12 months, paid before EOFY).

2. **Given** a scenario request, **When** the AI generates options, **Then** each option shows: description, taxable income impact, estimated tax saving, cash flow impact, and any compliance notes or risks.

3. **Given** a company client, **When** I type "what if we pay a $50K bonus to the director before June 30", **Then** the AI models: company tax saving from the deduction, personal tax impact on the director (including marginal rate change), and net group position.

4. **Given** a scenario that involves a compliance risk, **When** the AI generates the option, **Then** it includes a clearly labelled warning (e.g., "Part IVA risk: ATO may challenge if sole purpose is tax reduction") with a reference to the relevant ruling or provision.

5. **Given** multiple scenarios modelled in a session, **When** I ask "compare all options", **Then** the AI produces a summary table ranking scenarios by net tax benefit, cash flow impact, and risk level.

---

### User Story 4 — Export Tax Plan Summary (Priority: P2)

As an accountant, I want to export a summary of the tax plan and scenarios so I can share it with my client or include it in my working papers.

**Why this priority**: Accountants need a deliverable to take into client meetings. Without export, the tool is useful but not workflow-complete.

**Independent Test**: After modelling scenarios, click export → receive a formatted PDF or document showing the client's tax position, scenarios compared, and recommended strategy.

**Acceptance Scenarios**:

1. **Given** a completed tax plan with 3 scenarios, **When** I click export, **Then** I receive a PDF showing: client name, financial year, current tax position, each scenario with impact, comparison table, and recommended strategy.

2. **Given** an exported document, **When** a client reads it, **Then** the language is client-friendly (not accounting jargon), amounts are clearly formatted, and there is a disclaimer stating this is an estimate and not formal tax advice.

3. **Given** a tax plan, **When** I export, **Then** the document includes the accountant's practice name and branding (from tenant settings).

---

### User Story 5 — Save and Resume Tax Plans (Priority: P2)

As an accountant, I want to save a tax plan and come back to it later so I can work on it across multiple sessions or update it as new information comes in.

**Why this priority**: Tax planning is iterative — accountants revisit plans as clients provide more information or as the year progresses.

**Independent Test**: Create a tax plan → close the application → reopen → resume from where I left off with all data and scenarios preserved.

**Acceptance Scenarios**:

1. **Given** a tax plan in progress, **When** I navigate away and return later, **Then** all financials, scenarios, and AI conversation history are preserved.

2. **Given** a saved tax plan, **When** the client's Xero data has changed since I last worked on it, **Then** the system highlights what changed and offers to refresh the base figures.

3. **Given** multiple clients, **When** I view my tax plans list, **Then** I see all plans with client name, last updated date, financial year, and status (draft, in progress, finalised).

---

### Edge Cases

- What happens when Xero P&L categories don't map cleanly to tax return line items? → System uses best-effort mapping with flagged items for accountant review.
- How does the system handle mid-year tax plans where only partial-year data exists? → System annualises based on available months and clearly labels the estimate as projected.
- What if the AI suggests a strategy that is technically legal but aggressive? → AI always includes a risk rating (conservative / moderate / aggressive) and flags Part IVA or relevant anti-avoidance provisions.
- What happens when tax rates change mid-session (e.g., new legislation)? → Tax rates are stored as configuration data, not hardcoded. Updates are applied to new calculations immediately.
- How does the system handle clients with both business and personal income? → Phase 1 handles single-entity only. For individuals with both employment and business income, both are included in the same tax estimate.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST pull Profit & Loss data from Xero for the selected client for the current financial year (2025–26), categorising income and expenses by tax-relevant types. Prior year support is out of scope for Phase 1.
- **FR-002**: System MUST calculate estimated tax position for Australian companies (25% / 30% rate), individuals (2025–26 marginal rates including Medicare Levy), trusts (flat 47% rate on undistributed income, no distribution modelling in Phase 1), and partnerships (net income calculated at entity level, taxed in partners' hands at individual rates — simplified single-partner view in Phase 1).
- **FR-003**: System MUST apply Low Income Tax Offset (LITO) for individuals with taxable income under $66,667.
- **FR-004**: System MUST accept natural language scenario descriptions and generate modelled tax outcomes using the AI agent framework.
- **FR-005**: System MUST display before/after comparison for each scenario showing taxable income change, tax payable change, and net benefit.
- **FR-006**: System MUST include compliance notes and risk flags on scenarios that engage anti-avoidance provisions or have ATO audit risk.
- **FR-007**: System MUST support manual entry of financials for clients without Xero connections. The entry form presents summary totals by tax-relevant category (gross income, cost of sales, operating expenses, other income, PAYG credits) with optional line-item breakdown per category.
- **FR-008**: System MUST persist exactly one tax plan per client per financial year (unique constraint on client + FY) with full conversation history. Starting a new plan for the same client/FY replaces the existing one (with confirmation prompt).
- **FR-009**: System MUST export tax plan summaries as formatted PDF documents.
- **FR-010**: System MUST include PAYG instalment credits and withholding credits in the tax position calculation.
- **FR-011**: System MUST support HELP/HECS repayment calculation for individual clients.
- **FR-012**: System MUST apply the correct company tax rate based on entity type and aggregated turnover (small business entity test).
- **FR-013**: System MUST clearly label all outputs as estimates with appropriate disclaimers (not formal tax advice).
- **FR-014**: System MUST respect multi-tenancy — tax plans are scoped to `tenant_id` and visible only to the creating practice.

### Key Entities

- **TaxPlan**: A tax planning session for a specific client and financial year. One plan per client per FY (unique on client_id + financial_year). Contains base financials, entity type (company, individual, trust, partnership), and status.
- **TaxPlanFinancials**: The financial data underpinning a tax plan — either pulled from Xero or manually entered. Includes income by type, expenses by category, existing tax credits.
- **TaxScenario**: A modelled what-if scenario within a tax plan. Contains description, assumptions, calculated impact, risk rating, and compliance notes.
- **TaxPlanConversation**: The AI chat history for a tax plan session, enabling context-aware follow-up questions and scenario refinement.
- **TaxRateConfig**: Australian tax rates, thresholds, and offsets stored as configuration data (not hardcoded). Includes individual rates, company rates, trust tax rate (47% on undistributed income), Medicare Levy, LITO, HELP repayment thresholds.

---

## Auditing & Compliance Checklist

### Audit Events Required

- [ ] **Authentication Events**: Standard — user must be authenticated accountant within tenant.
- [x] **Data Access Events**: YES — reading client financial data from Xero for tax planning purposes.
- [x] **Data Modification Events**: YES — creating/updating tax plans, scenarios, and financial estimates.
- [x] **Integration Events**: YES — pulling P&L data from Xero API.
- [ ] **Compliance Events**: No direct ATO lodgement — this is advisory tooling, not lodgement.

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| taxplan.created | New tax plan initiated | Client ID, FY, entity type, data source (Xero/manual) | 7 years | None |
| taxplan.financials.loaded | Xero P&L pulled or manual entry saved | Income totals, expense totals, source | 7 years | Mask specific amounts in logs |
| taxplan.scenario.created | AI generates a scenario | Scenario description, projected figures, risk rating | 7 years | None |
| taxplan.exported | Tax plan exported as PDF | Export format, recipient info if emailed | 7 years | None |
| integration.xero.pnl_pulled | Xero API call for P&L | Client Xero org ID, date range, response status | 5 years | None |

### Compliance Considerations

- **ATO Requirements**: Tax plans are advisory working papers. No lodgement trail required, but practices may need to demonstrate basis for advice under TPB obligations.
- **Data Retention**: 7 years standard for client working papers under Tax Agent Services Regulations.
- **Access Logging**: All access to tax plans logged per tenant. Plans visible only to authenticated users within the tenant.
- **Disclaimers**: All outputs clearly labelled as estimates. System does not provide tax advice — it provides information and calculations for the accountant's professional judgement.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: Accountant can go from "select client" to "see tax position" in under 2 minutes (vs. 15–30 minutes with spreadsheet).
- **SC-002**: AI scenario modelling produces a valid, numerically accurate tax comparison within 15 seconds of the prompt.
- **SC-003**: Tax calculations match manual spreadsheet results to within $1 for standard company and individual scenarios (verified against Unni's existing spreadsheet tool).
- **SC-004**: 5 practices trial the tool during April–June 2026 EOFY season.
- **SC-005**: At least 3 of 5 trial practices use it on 5+ clients (indicating real workflow adoption, not curiosity).
- **SC-006**: Exported tax plan summary is rated "client-ready" by Unni without manual edits in 80%+ of cases.

---

## Phase 2 Preview (Separate Spec)

The following capabilities are explicitly **out of scope** for Phase 1 but planned for Phase 2 based on Unni's full specification:

- **Multi-entity group view**: Family trust → individuals/company with per-entity and consolidated group tax positions
- **Trust distribution modelling**: Streaming vs. non-streaming income, beneficiary allocation optimisation
- **Division 293 calculations**: Additional 15% on super for high-income individuals (>$250K)
- **Franking credit modelling**: Imputation credit tracking and refund eligibility
- **Quarterly instalment optimisation**: PAYG instalment variation modelling to improve cash flow
- **Client folder integration**: Google Drive/OneDrive linked folders for AI analysis of historical documents
- **Advanced entity structuring**: Scenario modelling for restructuring (e.g., incorporating a sole trader, establishing a trust)

---

## Architecture Notes (For Engineering Discussion)

> These are implementation hints for the planning phase, not part of the business spec.

- New module: `backend/app/modules/tax_planning/` following standard module structure
- Reuses existing Xero integration (`modules/integrations/xero/`) — specifically the P&L endpoint already available via `list-profit-and-loss`
- AI scenarios powered by existing agent framework (`modules/agents/`) — new `TaxPlanningAgent` specialist
- Tax rate configuration: new `tax_rate_config` table or JSON config — must be updatable without code deployment
- Frontend: new route `app/(dashboard)/clients/[clientId]/tax-planning/` with chat interface component
- Leverages existing knowledge base for ATO rulings and tax provisions (Pillar 2: Compliance RAG)
