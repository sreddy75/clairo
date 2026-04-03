# Feature Specification: Multi-Agent Tax Planning Pipeline

**Feature Branch**: `041-multi-agent-tax-planning`  
**Created**: 2026-04-03  
**Status**: Draft  
**Input**: Autonomous tax plan generation using multiple AI agents — profiles clients, scans strategies, models scenarios, produces dual-audience documents, quality-reviews everything.  
**Builds On**: 049-ai-tax-planning-advisory (Phase 1 MVP — already shipped)  
**Prepares For**: Phase 2 — multi-entity groups, trust distributions, Division 293, franking credits

---

## Strategic Context

Phase 1 (spec 049) shipped a reactive tool: the accountant chats with an AI agent to explore tax strategies one at a time. It works, but the accountant drives everything — they must know what to ask, iterate manually, and synthesise the output themselves.

This spec upgrades tax planning from a **reactive chat tool** to a **proactive advisory engine**. The system autonomously analyses the client's financial position, evaluates all applicable strategies, models the best combinations, and produces two ready-to-use documents: a technical brief for the accountant and a plain-language summary for the client.

The accountant's role shifts from "prompt engineer" to "reviewer and approver" — higher leverage, faster throughput, more clients served during EOFY season.

### Phase 2 Scalability

This spec explicitly designs the data model and agent architecture to extend to Phase 2 without breaking changes:

- **Multi-entity groups**: The analysis stores an `entities[]` array (Phase 1: single item)
- **Trust distributions**: The strategy scanner evaluates distribution strategies (Phase 1: skipped, Phase 2: enabled)
- **Division 293 / franking credits**: Tax calculator extensions (Phase 1: not calculated, Phase 2: new calculator inputs)
- **Client folder integration**: The profiler agent accepts document context (Phase 1: financials only, Phase 2: uploaded documents)
- **Entity restructuring**: The modeller agent handles multi-entity scenarios (Phase 1: single entity, Phase 2: cross-entity)

---

## User Scenarios & Testing

### User Story 1 — Generate Comprehensive Tax Plan (Priority: P1)

As an accountant, I want to click one button and receive a complete tax plan for my client — with ranked strategies, projected savings, and implementation steps — so I can advise multiple clients efficiently during EOFY season without manually exploring each strategy.

**Why this priority**: This is the core value proposition. It transforms a 2–3 hour manual process (research strategies, model each one, write up findings) into a 2-minute automated pipeline. During EOFY season, an accountant with 50 clients cannot spend 2 hours per client on tax planning. This tool makes comprehensive planning feasible for every client, not just the top-billing ones.

**Independent Test**: Open a client's tax plan with loaded Xero financials → click "Generate Tax Plan" → wait for pipeline to complete → see a ranked list of strategies with projected savings, risk ratings, and implementation timelines.

**Acceptance Scenarios**:

1. **Given** a tax plan with Xero financials loaded for a company client (FY 2025-26), **When** I click "Generate Tax Plan", **Then** the system begins autonomous analysis with real-time progress updates showing each stage (profiling, scanning, modelling, writing, reviewing).

2. **Given** the pipeline is running, **When** I view the progress, **Then** I see stage-by-stage status updates: "Analysing client profile...", "Evaluating 20+ tax strategies...", "Modelling top 5 strategies...", "Writing accountant brief...", "Quality review...".

3. **Given** the pipeline completes successfully, **When** I view the results, **Then** I see: client profile summary, all strategies evaluated (with applicable/not-applicable and why), top recommended strategies ranked by net benefit, combined strategy analysis showing total potential savings, and implementation timeline.

4. **Given** a small business company with $400K revenue and $260K taxable income, **When** the pipeline completes, **Then** at minimum the following strategy categories are evaluated: timing strategies (prepayments, deferrals), depreciation strategies (instant asset write-off), superannuation strategies (additional contributions), and each strategy includes a tax saving figure calculated using the real tax calculator (not AI estimates).

5. **Given** the pipeline completes, **When** I review the strategies, **Then** each strategy includes: description, estimated tax saving (from the real calculator), cash flow impact, risk rating (conservative/moderate/aggressive), compliance notes citing specific ATO provisions, and implementation deadline relative to EOFY.

---

### User Story 2 — Review Accountant Brief (Priority: P1)

As an accountant, I want to review a professional-grade tax planning brief with technical analysis, so I can verify the recommendations before presenting them to my client or including them in working papers.

**Why this priority**: The accountant must trust the output before sharing it. The brief is the accountant's working paper — it needs to be technically sound, properly referenced, and defensible if the ATO queries the advice.

**Independent Test**: After pipeline completion, view the "Accountant Brief" tab → see a structured document with executive summary, per-strategy analysis, combined impact, risk assessment, and compliance notes with ATO provision references.

**Acceptance Scenarios**:

1. **Given** a completed analysis, **When** I view the accountant brief, **Then** I see a structured document with: executive summary (total potential savings, recommended approach), per-strategy detailed analysis, combined strategy impact, implementation timeline, risk assessment, and compliance documentation requirements.

2. **Given** the accountant brief includes strategy recommendations, **When** I check the numbers, **Then** every tax saving figure matches what the real tax calculator produces (no AI-hallucinated numbers).

3. **Given** the accountant brief cites ATO provisions, **When** I verify the citations, **Then** each citation references a real ATO ruling, legislation section, or tax determination that exists in the knowledge base.

4. **Given** I disagree with a recommendation, **When** I edit the brief, **Then** my changes are saved and reflected in the approved version (the AI output is a starting point, not final).

---

### User Story 3 — Share Client Summary to Portal (Priority: P2)

As an accountant, I want to approve the tax plan and share a client-friendly summary to the client portal, so my client can see what's recommended, understand the savings, and track implementation progress.

**Why this priority**: This closes the loop between accountant analysis and client action. Without it, the accountant still needs to rewrite everything in an email. The portal summary turns the plan into an interactive checklist the client can act on.

**Independent Test**: After approving a tax plan → click "Share with Client" → client logs into portal → sees tax plan summary with savings estimate, recommended actions as a checklist, and ability to ask questions.

**Acceptance Scenarios**:

1. **Given** an approved tax plan, **When** I click "Share with Client", **Then** the client summary appears in the client's portal under a "Tax Planning" section with the practice's branding.

2. **Given** the client views their tax plan, **Then** they see: estimated total savings, each recommended action in plain language (no jargon), a deadline for each action, and a checkbox to mark actions as completed.

3. **Given** the client marks an action as completed, **When** the accountant views the tax plan, **Then** they see the updated implementation status with which actions the client has taken.

4. **Given** the client has a question about a recommendation, **When** they click "Ask a Question", **Then** the question is routed to the accountant as a notification with the relevant tax plan context.

---

### User Story 4 — Re-generate After Data Changes (Priority: P2)

As an accountant, I want to re-run the analysis when the client's financials change (e.g., after a new Xero sync or manual adjustments), so the recommendations stay current as the year progresses.

**Why this priority**: Tax planning is iterative — financials change as the year progresses. A March analysis may need updating in May when Q3 actuals come in.

**Independent Test**: Update financials (Xero refresh or manual edit) → click "Re-generate" → new analysis runs with updated numbers → changes from previous version are highlighted.

**Acceptance Scenarios**:

1. **Given** a previously generated tax plan analysis, **When** I refresh Xero data and click "Re-generate", **Then** the system runs a fresh analysis using the updated financials and preserves the previous version for comparison.

2. **Given** a re-generated analysis, **When** I compare to the previous version, **Then** I can see what changed: which strategies are new/removed, how savings estimates changed, and whether risk ratings shifted.

---

### User Story 5 — Pipeline Progress and Error Handling (Priority: P1)

As an accountant, I want to see real-time progress as the analysis runs and graceful handling if something goes wrong, so I'm not left staring at a spinner wondering what's happening.

**Why this priority**: The pipeline takes 30-60 seconds. Without progress feedback, users will assume it's broken and navigate away.

**Independent Test**: Click "Generate Tax Plan" → see a progress stepper showing which agent is running → if an agent fails, see a clear message about what happened with an option to retry.

**Acceptance Scenarios**:

1. **Given** I click "Generate Tax Plan", **When** the pipeline starts, **Then** I see a progress stepper with stages: Profile → Scan Strategies → Model Scenarios → Write Documents → Review, with the current stage highlighted and a brief status message.

2. **Given** the strategy scanner is running, **When** I view the progress, **Then** I see how many strategies have been evaluated (e.g., "Evaluating strategy 15 of 22...").

3. **Given** an agent fails mid-pipeline (e.g., Xero token expired during modelling), **When** the error occurs, **Then** I see a clear error message identifying which stage failed, with a "Retry" button that resumes from the failed stage (not from scratch).

4. **Given** the pipeline completes with warnings (e.g., some citations could not be verified), **When** I view results, **Then** the quality review section clearly lists what passed and what needs manual attention.

---

### Edge Cases

- What happens if the client has no Xero data (manual entry only)? → Pipeline runs on manual financials with reduced profiling accuracy; a warning notes that some eligibility checks may be incomplete.
- What happens if the knowledge base has no relevant ATO rulings for a strategy? → Strategy is still evaluated using the agent's training knowledge, but marked as "no RAG citation available — verify independently".
- What happens if the tax calculator produces unexpected results (e.g., negative tax)? → Reviewer agent flags this for accountant review with a note explaining the anomaly.
- What happens during Phase 2 with multi-entity groups? → The data model supports `entities[]` array and `group_structure` from day one. Phase 1 stores a single entity. Phase 2 adds entities without schema changes.
- What happens if the accountant modifies the brief after approval and the client has already seen the summary? → The portal shows the latest approved version. Changes to the brief after sharing trigger a notification to the accountant asking if they want to update the client's view.
- What happens if two accountants in the same practice generate a plan for the same client simultaneously? → The system prevents concurrent generation for the same plan with a clear "Analysis already in progress" message.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST run an autonomous multi-stage analysis pipeline triggered by a single user action ("Generate Tax Plan"), executing sequentially: client profiling, strategy scanning, scenario modelling, document generation, and quality review.
- **FR-002**: System MUST profile the client entity by analysing their financials to determine: entity type classification, small business entity eligibility, applicable tax rate, HELP/HECS status, and relevant threshold positions.
- **FR-003**: System MUST evaluate a minimum of 15 distinct tax strategy categories against the client's profile, including: timing strategies (prepayments, deferrals), depreciation strategies (instant asset write-off, pooling), superannuation strategies (concessional contributions, catch-up), and structure-related strategies.
- **FR-004**: System MUST calculate tax impact for each recommended strategy using the existing real tax calculator (not AI-generated estimates), producing exact before/after tax positions.
- **FR-005**: System MUST analyse strategy combinations to identify the optimal set of strategies that can be implemented together, including any interactions (e.g., two strategies that compound vs. conflict).
- **FR-006**: System MUST produce an "Accountant Brief" document containing: executive summary with total potential savings, per-strategy technical analysis with ATO provision references, combined strategy impact, implementation timeline with EOFY deadlines, and risk assessment.
- **FR-007**: System MUST produce a "Client Summary" document containing: estimated savings in plain language, recommended actions as numbered steps with deadlines, and no accounting jargon or legislation references.
- **FR-008**: System MUST verify the quality of the generated output, confirming: all tax figures match calculator results, cited ATO provisions exist in the knowledge base, strategies do not contradict each other, and implementation deadlines are correct.
- **FR-009**: System MUST display real-time progress as the pipeline runs, showing which stage is active and providing brief status messages.
- **FR-010**: System MUST persist the complete analysis results (profile, strategies, scenarios, documents, review) as a structured record linked to the tax plan.
- **FR-011**: System MUST allow the accountant to edit the generated brief and client summary before approving.
- **FR-012**: System MUST support sharing the approved client summary to the client portal, where the client can view recommendations, track implementation progress via checkboxes, and ask questions.
- **FR-013**: System MUST support re-generation of the analysis when financials change, preserving the previous version for comparison.
- **FR-014**: System MUST prevent concurrent pipeline execution for the same tax plan.
- **FR-015**: System MUST include risk ratings (conservative, moderate, aggressive) on each strategy with explanations referencing specific anti-avoidance provisions where applicable.
- **FR-016**: System MUST scope all analysis data to `tenant_id`, ensuring tax plan analyses are visible only to the creating practice.
- **FR-017**: System MUST run the pipeline asynchronously (background job) so the user interface remains responsive during the 30-60 second execution.

### Phase 2 Extension Points (Designed Now, Implemented Later)

- **FR-P2-001**: Data model MUST support multiple entities per analysis (`entities[]` array) for multi-entity group views.
- **FR-P2-002**: Data model MUST support group structure definition (trust → beneficiaries) and distribution plans.
- **FR-P2-003**: Strategy scanner MUST be extensible to evaluate trust distribution strategies (streaming vs. non-streaming income, beneficiary allocation optimisation).
- **FR-P2-004**: Tax calculator interface MUST be extensible to include Division 293 calculations, franking credit modelling, and PAYG instalment variation.
- **FR-P2-005**: Client summary MUST be extensible to per-beneficiary views (each beneficiary sees their own summary from the family group plan).
- **FR-P2-006**: Profiler agent MUST be extensible to accept uploaded documents (from Google Drive/OneDrive client folders) as additional context.

### Key Entities

- **TaxPlanAnalysis**: The stored output of the complete multi-agent pipeline. Linked to a TaxPlan. Contains: client profile, all strategies evaluated, recommended scenarios with calculator numbers, accountant brief, client summary, implementation checklist, quality review results, and lifecycle status (generating → draft → reviewed → approved → shared).
- **AnalysisVersion**: Supports re-generation by versioning each analysis run. The latest approved version is the active one.
- **ImplementationItem**: Individual action items within the tax plan with deadlines, assigned entity, completion status, and client visibility flag. Tracks progress across accountant and client portal views.

---

## Auditing & Compliance Checklist

### Audit Events Required

- [ ] **Authentication Events**: Standard — user must be authenticated accountant within tenant.
- [x] **Data Access Events**: YES — AI agents access client financial data and ATO knowledge base.
- [x] **Data Modification Events**: YES — creating/updating tax plan analyses, approving plans, sharing to client portal.
- [x] **Integration Events**: YES — pulling financial data from Xero during analysis, knowledge base retrieval.
- [ ] **Compliance Events**: No direct ATO lodgement — this is advisory tooling.

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| analysis.generated | Pipeline completes | Plan ID, entity type, strategies count, total savings, generation time, token usage | 7 years | Mask specific financial amounts in logs |
| analysis.reviewed | Accountant approves/edits | Plan ID, reviewer user ID, changes made, approval status | 7 years | None |
| analysis.shared | Shared to client portal | Plan ID, client portal user, share timestamp | 7 years | None |
| analysis.regenerated | Re-run after data change | Plan ID, version number, financial changes summary | 7 years | Mask amounts |
| implementation.updated | Client marks action complete | Plan ID, item ID, completion status, updated by | 7 years | None |

### Compliance Considerations

- **ATO Requirements**: Tax plan analyses are advisory working papers. Practices may need to demonstrate basis for advice under Tax Practitioner Board obligations. The stored analysis provides a complete audit trail of what was recommended and why.
- **Data Retention**: 7 years standard for client working papers under Tax Agent Services Regulations.
- **Access Logging**: All access to tax plan analyses logged per tenant. Analyses visible only to authenticated users within the tenant. Client portal access limited to the specific client's approved summary.
- **Disclaimers**: All outputs clearly labelled as estimates and not formal tax advice. System does not provide tax advice — it provides information and calculations for the accountant's professional judgement.
- **AI Transparency**: The analysis records which AI agents produced each section, what knowledge base sources were used, and whether the quality review passed — supporting the accountant's obligation to verify AI-assisted advice.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: Accountant can generate a comprehensive tax plan (profile + strategies + scenarios + documents) for a client in under 2 minutes, compared to 2-3 hours of manual research and spreadsheet modelling.
- **SC-002**: The generated analysis evaluates at least 15 distinct strategy categories per client, ensuring no common strategy is missed.
- **SC-003**: All tax saving figures in the generated output match the real tax calculator to within $1, verified by the quality review agent.
- **SC-004**: The quality review agent identifies 95%+ of citation errors, number mismatches, and strategy conflicts before the accountant sees the output.
- **SC-005**: 80%+ of generated accountant briefs are rated "usable with minor edits" by trial accountants (not requiring significant rewriting).
- **SC-006**: 80%+ of generated client summaries are rated "client-ready" by trial accountants (understandable by non-accountants without jargon).
- **SC-007**: Client portal implementation checklist achieves 60%+ client engagement (client views and interacts with at least one checklist item).
- **SC-008**: During EOFY season, a practice using the tool completes tax planning for 3x more clients compared to their manual baseline.

---

## Assumptions

- The existing Phase 1 tax planning infrastructure (Xero P&L pull, tax calculator, rate configs, chat agent, scenario storage) is stable and reusable as the foundation.
- The existing RAG knowledge base contains sufficient ATO rulings and provisions to support strategy compliance citations.
- The pipeline execution time of 30-60 seconds is acceptable for a background job with real-time progress updates.
- Phase 1 of this spec focuses on single-entity analysis. Multi-entity group analysis (Phase 2) will use the same data model with additional fields populated.
- The accountant is the approver — the system never shares recommendations directly with the client without accountant review.
- Client portal access is read-only for the tax plan summary (clients cannot modify strategies, only mark actions as complete and ask questions).
