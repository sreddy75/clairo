# Feature Specification: Tax Planning Modeller — Architectural Redesign

**Feature Branch**: `059-2-tax-planning-correctness-followup`
**Created**: 2026-04-18
**Status**: Draft
**Input**: Follow-up to Spec 059 (Tax Planning Calculation Correctness). Captures the modeller redesign necessitated by HANDOFF.md and the failed three-layer meta-scenario filter attempt (commits `19b51fc`, `e16a58e`, `d3c2f70`, `6997fb8`).

---

## Origin & Problem

Spec 059 landed the provenance, annualisation, and group-model-honesty work that made the tax position panel trustworthy. One symptom remained unresolved at spec close: the Scenario Modeller agent — the component that evaluates individual tax strategies and reports a combined saving — produces a materially wrong "Total Tax Saving" headline. In the live UAT run captured in HANDOFF.md, the figure shown to the accountant was exactly **double** the true arithmetic sum of the individual strategies ($22,000 reported vs $11,000 real).

Root-cause analysis (see HANDOFF.md and conversation 2026-04-18) established:

1. **The double-counting is structural, not stochastic.** The language model running the modeller reliably emits an extra "combined" / "meta" scenario at the end of its evaluation loop. The modeller then sums every scenario including the meta one, producing 2× the correct total.
2. **Three remediation layers were tried and all have structural holes.**
   - A hard cap on the evaluation-loop count fails when the LLM displaces a real strategy with a meta-call (count stays under the cap).
   - A keyword-based name filter fails when the LLM renames the meta-scenario ("Integrated Tax Minimisation Strategy").
   - A ratio threshold (`saving > 1.1 × sum_of_others`) fails because a faithful meta-scenario's saving exactly **equals** the sum of its siblings — the inequality cannot fire at the most common shape.
3. **A second, independent failure mode has now emerged.** The token budget increase intended to give the multi-round loop headroom triggers the Anthropic SDK's "streaming required for long operations" rejection, so the pipeline cannot complete at all under the current design.

Because every defensive layer treats a symptom of the same root cause — the LLM controls the evaluation loop — no further defensive layer will close the gap. The component needs an architectural redesign where the number of scenarios is **bounded by code, not inferred from LLM behaviour**.

This spec captures that redesign as a standalone, shippable unit of work. It does **not** re-open any Spec 059 story; it fixes the one Spec 059 story the team committed to handing off rather than papering over. Related stories (citation verifier bug, pre-Stage-3 rate language, duplicate-scenario upsert) are captured separately and explicitly out of scope here.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Accountant sees a correct, single-sourced Total Tax Saving figure (Priority: P1)

An accountant opens the Analysis tab of a tax plan for a client. The "Total Tax Saving" headline at the top of the page equals the exact arithmetic sum of the individual strategies' tax savings shown below it. There is no hidden "combined" strategy that duplicates and sums the individuals. The number the accountant sees is the number the accountant can defend, line by line, against the list of recommended strategies on the same screen.

**Why this priority**: This is the gating defect that makes the platform dangerous in front of a paying client. An accountant who reads a doubled tax saving out loud during a client meeting is presenting advice that the firm's professional indemnity insurance cannot justify. Until this is fixed, the tax planning feature cannot be used live.

**Independent Test**: Run an analysis against the golden-dataset fixture (N applicable strategies). Assert `combined_strategy.total_tax_saving` exactly equals the arithmetic sum of the individual scenarios' `tax_saving` fields (modulo the existing 2dp rounding tolerance). Assert no scenario's `strategy_id` is absent from the input strategy list.

**Acceptance Scenarios**:

1. **Given** a client with N applicable strategies, **When** the analysis completes, **Then** the Total Tax Saving headline equals the sum of the individual scenarios' savings to the cent.
2. **Given** the same client, **When** the accountant reads the list of recommended strategies on the Analysis tab, **Then** there is no entry whose title summarises or combines other entries.
3. **Given** an analysis persisted to the database, **When** its `recommended_scenarios` field is inspected, **Then** every scenario's `strategy_id` matches a strategy that was passed to the modeller as input — no generated, synthesised, or combined IDs appear.

---

### User Story 2 — Analysis runs complete end-to-end without streaming errors (Priority: P1)

An accountant clicks "Re-generate Analysis" on the Analysis tab. The orchestrator runs all five pipeline agents and returns a complete, persisted analysis record in a single synchronous request cycle. The run does not fail partway through with an infrastructure-layer "streaming required" error that leaves the analysis in a `failed` state with zero modelled scenarios.

**Why this priority**: As of the current main branch, no analysis run can complete. Every click on "Re-generate Analysis" fails because the modeller's request pattern has crossed the external provider's synchronous-request threshold. This is a total outage of the feature, not a degradation.

**Independent Test**: Trigger an analysis against the golden-dataset fixture. Assert the returned status is `succeeded`, not `failed`, and that the error message does not contain "Streaming is required". Assert the modeller's contribution to total pipeline latency is within the previous per-agent budget.

**Acceptance Scenarios**:

1. **Given** a plan with up to 8 applicable strategies, **When** the orchestrator invokes the modeller, **Then** the language-model request completes in a single round without raising a streaming-requirement error.
2. **Given** a completed analysis, **When** the frontend polls the analysis endpoint, **Then** the returned status is `succeeded` and the `recommended_scenarios` field is populated.

---

### User Story 3 — Scenario count is bounded by the input strategy list (Priority: P2)

When the modeller runs, the number of scenarios it returns cannot exceed the number of strategies it was given. Every returned scenario traces back to exactly one of those input strategies by ID. There is no mechanism by which the modeller can invent a scenario that does not correspond to one of the input strategies.

**Why this priority**: This is the structural property that guarantees Story 1 and makes future regressions impossible. Without it, every future change to the modeller or its prompts risks re-introducing the meta-scenario class of bug. With it, the class of bug cannot exist regardless of what the language model returns.

**Independent Test**: Unit test: stub the language-model client to return a response that includes an entry whose `strategy_id` is not in the input strategy list. Assert that entry is dropped from `recommended_scenarios`. Stub returns duplicates of the same `strategy_id`: assert deduplication. Stub returns more entries than input strategies: assert truncation.

**Acceptance Scenarios**:

1. **Given** M applicable strategies passed to the modeller, **When** the modeller returns, **Then** `len(recommended_scenarios) ≤ M`.
2. **Given** a language-model response containing an unknown `strategy_id`, **When** the modeller processes it, **Then** the corresponding entry is silently dropped and a diagnostic log line is emitted.
3. **Given** a language-model response containing duplicate `strategy_id`s, **When** the modeller processes it, **Then** only the first occurrence is retained.

---

### User Story 4 — Reviewer no longer raises false-positives on combined-total mismatch (Priority: P2)

When the reviewer agent checks a completed analysis for quality issues, it does not flag a delta between the "combined strategy" total and the individual-scenario sum, because that delta is zero by construction. The Analysis tab does not render "Needs Review" status driven by the now-impossible double-counting discrepancy.

**Why this priority**: Every UAT run today lands on "Needs Review" with the same three-point complaint about combined-strategy arithmetic. Accountants have to click through a warning banner on every plan. With the modeller redesigned, the reviewer's complaint vanishes without any change to the reviewer itself.

**Independent Test**: Run the full pipeline against the golden-dataset fixture. Assert the reviewer's output does not contain findings matching the patterns "combined strategy" + "inconsistency", "double-counting", or "total tax saving" + "mismatch". Assert the rendered Analysis tab status is not `Needs Review` for reasons attributable to combined-total arithmetic.

**Acceptance Scenarios**:

1. **Given** a freshly run analysis, **When** the reviewer agent completes, **Then** its findings do not include a combined-total discrepancy.
2. **Given** the analysis renders in the UI, **When** the accountant views the Analysis tab, **Then** there is no "Needs Review" banner caused by combined-strategy arithmetic inconsistency.

---

### Edge Cases

- **Language model returns zero modifications**: Analysis completes with an empty `recommended_scenarios` list; the UI shows "0 Strategies Modelled" without error; the analysis status is `succeeded`, not `failed`. Accountant retains the option to re-run.
- **Language model returns modifications for only some input strategies**: The modeller returns a scenario per returned modification. Strategies the LLM declined to model are simply absent from the recommended list — no placeholder, no pseudo-scenario.
- **Language model returns a modification whose `strategy_id` matches an input but whose content is nonsensical**: The modification passes ID validation; the calculator still runs on it and produces a scenario with whatever `tax_saving` the numbers yield. This class of error is out of scope for this spec — it is the kind of quality signal the reviewer is intended to catch on substance, not on arithmetic.
- **Language model returns a malformed response that fails schema validation at the provider level**: The modeller propagates the provider error; the orchestrator marks the analysis `failed` with a diagnostic message. Accountant can retry. This preserves the current failure semantics for API-layer errors.
- **A group-model strategy is included**: Same behaviour as today — the scenario is returned with `tax_saving = 0` and is excluded from the combined total via the existing `requires_group_model` gate. Untouched by this spec.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The modeller MUST return a list of scenarios whose `strategy_id` values form a subset of the input strategy IDs. Any returned entry whose `strategy_id` does not match an input strategy MUST be dropped before the scenarios are persisted or returned to the orchestrator.
- **FR-002**: The modeller MUST deduplicate returned entries by `strategy_id`, retaining only the first occurrence of each.
- **FR-003**: The modeller MUST NOT return more scenarios than the number of input strategies.
- **FR-004**: `combined_strategy.total_tax_saving` MUST equal the arithmetic sum of the individual scenarios' `tax_saving` fields (over scenarios with `requires_group_model = False` and `tax_saving > 0`), within the existing 2dp rounding tolerance.
- **FR-005**: The number of scenarios in `recommended_scenarios` MUST be bounded by code, not by the behaviour or stop condition of the language model.
- **FR-006**: The modeller MUST complete its language-model interaction in a single synchronous request round trip; it MUST NOT run a multi-round loop whose termination depends on the language model's stop signal.
- **FR-007**: The modeller's language-model request MUST stay within the provider's synchronous-response threshold; the pipeline MUST NOT fail with a "streaming required" error under normal inputs (up to 8 applicable strategies).
- **FR-008**: The three legacy defensive filters (hard call cap, keyword-based name strip, ratio threshold `>1.1×`) MUST be removed from the modeller along with the dead internal re-filter inside the combined-strategy builder, since the redesigned flow makes them unreachable.
- **FR-009**: The modeller MUST emit a diagnostic log entry when it drops an unknown-strategy-id entry, when it deduplicates a duplicate-strategy-id entry, and when the language model returns zero valid modifications — so a post-hoc reviewer can see what the model attempted.
- **FR-010**: All existing per-scenario provenance behaviour from Spec 059 (source tags, `requires_group_model` flag, strategy-category coercion, risk-rating coercion) MUST be preserved unchanged — this spec replaces the control flow, not the per-scenario computation.

### Non-Functional Requirements

- **NFR-001**: The redesign MUST NOT regress any existing Spec 059 functional requirement (annualisation, provenance tagging, group-model exclusion, reviewer number verification, etc.).
- **NFR-002**: The redesign MUST NOT require database schema changes.
- **NFR-003**: The redesign MUST NOT require frontend changes; all consumer contracts (`combined_strategy.total_tax_saving`, `recommended_scenarios[*]`, `strategy_count`) remain stable.
- **NFR-004**: The redesign MUST NOT change the reviewer, advisor, scanner, or profiler agents.

### Key Entities

- **Scenario modification (LLM output)**: A structured description of one proposed change to a client's financials — associated to an input strategy by `strategy_id`, carrying proposed income/expense/turnover modifiers, assumptions, category, risk rating, and compliance notes. Produced by the modeller's language-model step. Never persisted in raw form — always transformed through the tax calculator into a scenario record.
- **Scenario (persisted)**: Unchanged from Spec 059 — carries `impact.before`, `impact.after`, `impact.change.tax_saving`, `cash_flow_impact`, `source_tags`, `requires_group_model`, `strategy_category`, `risk_rating`, and `strategy_id`. Output of the calculator step.
- **Combined strategy summary (persisted)**: Unchanged from Spec 059 — carries `total_tax_saving`, `net_cash_benefit`, `total_cash_outlay`, `strategy_count`, `excluded_count`, `recommended_combination`. Derived deterministically from the scenarios list.

---

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [ ] **Authentication Events**: No.
- [ ] **Data Access Events**: No — this is an internal agent behaviour change with no additional data-access surface.
- [ ] **Data Modification Events**: No new modification events. Existing `TaxPlanAnalysis` row update during the orchestrator run is untouched.
- [ ] **Integration Events**: No external integration changes (same Anthropic API, same calculator).
- [ ] **Compliance Events**: No BAS or ATO compliance surface is affected. This is a calculation-correctness change within the advisory (non-lodgement) domain.

### Compliance Considerations

- **ATO Requirements**: None new. The platform does not lodge based on tax planning output; tax planning is decision-support for registered agents.
- **Data Retention**: Unchanged.
- **Access Logging**: Diagnostic log lines (FR-009) are for engineering observability, not tenant-visible audit. Standard app-log retention applies.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the golden-dataset fixture, the Total Tax Saving headline is within $1 of the arithmetic sum of the individual scenarios shown on the same page, for every run across 10 consecutive executions — no regressions to the double-counting class of defect.
- **SC-002**: 100% of end-to-end analysis runs complete with status `succeeded` on valid input within the per-agent latency budget (no "streaming required" failures) across the post-ship UAT week.
- **SC-003**: 0% of analyses rendered to the Analysis tab display "Needs Review" status for reasons attributable to combined-total arithmetic, across the post-ship UAT week.
- **SC-004**: The three legacy filter layers (hard cap, keyword filter, ratio threshold) are removed from the codebase; a static check (grep) confirms the absence of `_META_KEYWORDS`, `max_tool_calls`, and the `1.1 *` structural predicate in the modeller module.
- **SC-005**: Unit test coverage added for the three new structural guarantees (unknown-id drop, duplicate-id dedupe, truncation-at-input-count) — all three tests pass in CI.
- **SC-006**: Against a live UAT run with the golden dataset, the accountant can read the Total Tax Saving headline and reconcile it line-by-line to the per-strategy savings below without discrepancy — validated in the next UAT session.

---

## Dependencies & Assumptions

**Dependencies**:

- Spec 059 must be landed (it is) — this spec replaces the modeller's control flow, which was introduced and amended under Spec 059.
- The existing tax calculator (`calculate_tax_position`) is treated as a stable, trusted primitive. No changes to it in this spec.

**Assumptions**:

- Anthropic's forced-tool-choice mechanism remains available and behaviourally stable for the duration of the implementation (no SDK or API change is anticipated).
- The input strategy list passed to the modeller is already deduplicated upstream (by the scanner) — the modeller's dedupe is a defence-in-depth measure against LLM-introduced duplicates, not an upstream correctness fix.
- A single-round structured-output request with a modifications list for up to 8 strategies fits comfortably within the provider's synchronous-response latency threshold. If this assumption proves false in live testing, the spec still succeeds (streaming can be added as a transparent transport change) — but the assumption is documented as the expected path.

---

## Out of Scope

- Citation verifier semantic-threshold bug (Spec 059 Story 6)
- Pre-Stage-3 rate language removal (Spec 059 Story 7)
- Duplicate scenario title upsert logic across chat turns (Spec 059 Story 8)
- Multi-entity group tax model (separate spec, not yet drafted)
- ~~Any change to the advisor, reviewer, scanner, or profiler agents~~ **Amended 2026-04-18**: the advisor agent was found during live-run verification to hit the same "Streaming is required" Anthropic threshold as the (now-fixed) modeller, because commit `e16a58e` raised its `MAX_TOKENS` to 64k. Story 2 demands end-to-end pipeline completion, so the advisor is promoted into scope for a transport-only change: the single `messages.create()` call becomes `messages.stream() + get_final_message()`. No prompt, output shape, or behavioural change. Reviewer, scanner, and profiler remain untouched.
- Any change to the tax calculator (`tax_calculator.py`)
- Any change to database schema
- Any frontend change
- Any change to the legacy single-agent `TaxPlanningAgent` (chat flow) — its tool-use loop is not implicated in this defect
