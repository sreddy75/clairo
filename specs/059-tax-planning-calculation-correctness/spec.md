# Feature Specification: Tax Planning — Calculation Correctness

**Feature Branch**: `059-tax-planning-calculation-correctness`
**Created**: 2026-04-18
**Status**: Draft
**Input**: Brief `specs/briefs/2026-04-18-tax-planning-calculation-correctness.md` (synthesised from Unni's alpha-session feedback, Zac & Angela Phillpott / OreScope Surveying, April 2026)

---

## Clarifications

### Session 2026-04-18

- Q: When fewer than 12 months of data are loaded, which annualisation rule should project YTD income/expenses to a full FY? → A: Linear (`monthly_avg × 12`) — simple, explainable, no prior-year dependency; accountant can override via manual-entry if a different baseline is needed.
- Q: When the reviewer reports `numbers_verified=false`, what happens to the analysis output in the UI? → A: Warn prominently but don't block — render as normal with a top-of-page banner and per-scenario badge identifying the specific failing field and delta; accountant decides whether to use the result.
- Q: How is a scenario detected as "inherently multi-entity" (requiring the group model)? → A: Strategy-category enum — scanner/modeller tag every scenario with a `strategy_category` from a closed set; a code-level mapping declares which categories require the group model. Authoritative, auditable, does not rely on LLM judgment at flag-time.
- Q: How does the accountant confirm an *estimated* figure in the UI? → A: Inline edit with prefill — the AI's value is shown as a prefilled input the accountant can accept verbatim (enter/blur), tweak, or clear. Preserves agency and avoids rubber-stamping while keeping friction proportional to trust.
- Q: What is the timeout behaviour for the on-demand payroll sync at plan creation? → A: Synchronous with 15s timeout — if the sync finishes within 15 seconds use fresh data; otherwise continue plan creation, kick sync to background, and surface a "payroll still syncing" banner until the data arrives. Protects live-session UX while still preferring fresh data when available.

---

## Origin & Problem

On the first live tax-planning session run in front of a real paying client (Zac Phillpott and Angela Phillpott of OreScope Surveying), Clairo produced multiple materially wrong numbers against the accountant's side-by-side ChangeGPS reference. The accountant (Unni, SME) characterised the failure cleanly: *"My tolerance for numeric errors in front of a paying client is zero, and it should be."*

Investigation revealed this is **not nine independent bugs** but a single correctness failure: Clairo has no ground-truth contract between input data, the calculation engine, the AI agents, and the UI. Symptoms include:

- Tax payable calculated on year-to-date actuals while the LLM is simultaneously shown a projected full-year figure (contradictory numbers in the same prompt).
- "Net Benefit" reported as the company tax saving of a scenario — ignoring the offsetting tax paid by individual beneficiaries who receive the distributed income. One scenario reported ~$44,250 benefit when the true group-level net was ~$4,100.
- Scenario tabs containing AI-estimated figures (e.g. "$25,000 prepaid expenses") that were never confirmed by the accountant and carried no visible provenance.
- Super-YTD and PAYGW-YTD showing $0 because payroll data is not triggered on tax-plan creation, PAYG Withholding is never propagated into the tax-credits line, and both failure modes log silently.
- Source-citation badges showing "Sources could not be verified" because the verifier is a brittle substring match compounded by a dict-key typo that collapses confidence scoring to near-zero and swaps legitimate AI responses for a canned decline message.
- Pre-Stage-3 tax-rate language (32.5%, $120k threshold) embedded in an agent system prompt fed verbatim to the language model.
- Duplicate scenarios accumulating across chat turns with no deduplication.
- The "reviewer" agent that is meant to catch all of the above re-runs the same calculation path as the modeller on the same inputs, so it rubber-stamps every error.

Because of these findings, no further live-client sessions can run until the calculation path is trustworthy end-to-end. This spec is the **correctness audit**: restore ground truth, add the test coverage that should have caught these bugs in the first place, and expose provenance so the accountant can trust every number they read out loud.

Multi-entity ("group") tax modelling — which is the deeper architectural fix for the Net-Benefit symptom — is **explicitly split out** into a separate spec. This spec only adds a minimum honesty flag so multi-entity strategies cannot silently mislead before that work lands.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Accountant trusts the headline numbers in front of a client (Priority: P1)

An accountant opens a tax plan for a client mid-financial-year and reads the Tax Position panel aloud during a strategy meeting. Every figure on screen (taxable income, tax payable, credits applied, net position) is calculated on a projected full-financial-year basis, not on year-to-date actuals, so the numbers reflect what the client will actually owe. The accountant can explain how each figure was derived without having to cross-check against a spreadsheet.

**Why this priority**: Without this, no further live sessions are possible. Every downstream feature depends on the Position panel being arithmetically correct. This is the "can we run the next alpha session?" gate.

**Independent Test**: Load the golden-dataset fixture (Zac Phillpott's sanitised inputs), render the Tax Position panel, and assert every field matches the ChangeGPS-equivalent output within $1.

**Acceptance Scenarios**:

1. **Given** a client with 6 months of Xero data loaded and no manual override, **When** the accountant opens the Tax Position panel, **Then** taxable income is annualised from year-to-date figures using the declared projection rule and tax payable is calculated on the annualised figure.
2. **Given** the same client, **When** the accountant inspects the numbers fed to the AI chat, **Then** the chat sees exactly one set of numbers (annualised), not YTD and projected side-by-side.
3. **Given** a client with 12+ months of data loaded, **When** the tax position is computed, **Then** no annualisation occurs and the original figures are used unchanged.
4. **Given** an accountant who prefers to manually override financials, **When** they enter figures via the manual-entry form, **Then** the figures are treated as full-year and the system flags them as user-confirmed.

---

### User Story 2 — Every figure on screen shows where it came from (Priority: P1)

When an accountant opens the Analysis tab or a scenario card, every numeric field is visibly tagged as one of: *confirmed* (entered or explicitly approved by the accountant), *derived* (transformed from a confirmed figure by a deterministic rule), or *estimated* (AI-generated, pending confirmation). Estimated figures display a distinct visual treatment and cannot be presented to a client without being confirmed first.

**Why this priority**: The "$25k prepaid expenses" pattern — AI-invented assumptions presented as ground truth — is the single biggest liability risk in the current UI. Provenance tagging makes the AI's guesses visible, not hidden.

**Independent Test**: Run the multi-agent analysis on the golden-dataset fixture; inspect each rendered figure in the Analysis tab and verify it carries a provenance tag and that "estimated" figures render with the distinct treatment.

**Acceptance Scenarios**:

1. **Given** a scenario with an AI-generated assumption ("Prepay $25,000 of rent"), **When** the scenario renders in the Analysis tab, **Then** the $25,000 figure is visibly marked *estimated* with an explanatory tooltip.
2. **Given** a scenario where the modifier is derived from a confirmed figure, **When** the scenario renders, **Then** the derived figure is marked *derived* and its confirmed baseline is referenceable.
3. **Given** the accountant reviews an estimated figure and accepts it, **When** they confirm, **Then** the figure flips to *confirmed* and is persisted as such.
4. **Given** a client-facing export is generated, **When** any figure in the export is still *estimated*, **Then** the export fails or warns rather than hiding the distinction.

---

### User Story 3 — Payroll data flows into the tax position automatically (Priority: P1)

When an accountant creates a tax plan for a client whose Xero connection has payroll access, the plan automatically reflects the year-to-date superannuation and PAYG Withholding from payroll activity. PAYG Withholding already remitted is correctly applied as a tax credit, so the "before" tax baseline for every scenario is realistic rather than inflated. If payroll data is unavailable (no payroll access, not yet synced, or sync failure), the accountant sees an explicit, actionable message — not a silent $0.

**Why this priority**: Every scenario's "tax saving" is computed against the before-baseline. A silently-zeroed PAYGW credit inflates the baseline and therefore inflates every scenario's apparent saving. This is a correctness lever, not a cosmetic fix.

**Independent Test**: Seed a Xero connection with payroll access and representative `XeroPayRun` fixtures; create a tax plan; assert `credits.payg_withholding` equals the sum of payroll tax withheld YTD and that Super YTD / PAYGW YTD display the expected non-zero values. Then force `has_payroll_access=False` and assert the UI shows an explicit banner, not $0.

**Acceptance Scenarios**:

1. **Given** a Xero connection with payroll access and synced pay runs, **When** a tax plan is created, **Then** the plan's `credits.payg_withholding` reflects the YTD tax withheld and Super YTD / PAYGW YTD render non-zero values.
2. **Given** a Xero connection without payroll access, **When** a tax plan is created, **Then** the accountant sees a banner stating "Payroll data unavailable — reconnect with payroll scope" and the super/PAYGW fields display that state rather than $0.
3. **Given** a tax plan created before payroll has been synced, **When** the plan is opened, **Then** payroll sync is triggered on demand or the plan clearly indicates data is pending.
4. **Given** an accountant uses the manual-entry form to adjust one financial figure, **When** they save, **Then** payroll data, bank balances, strategy context, and prior-year context previously loaded from Xero are preserved — not wiped.

---

### User Story 4 — Multi-entity strategies do not silently mislead (Priority: P1)

When the AI surfaces a strategy whose effect depends on moving income between entities (director salary, trust distribution, dividend timing, spouse contribution), the strategy is flagged as requiring the group tax model (not yet available), is not presented as a recommendation with a single-entity net-benefit number, and clearly explains to the accountant why the figure cannot be given precisely until the group model ships.

**Why this priority**: The underlying architectural fix (multi-entity modelling) is a separate spec that will take weeks. In the meantime, surfacing single-entity numbers for inherently multi-entity strategies is the original F1-13 bug. This honesty flag is the minimum change that prevents the same mistake being repeated in live sessions before the architectural fix lands.

**Independent Test**: Trigger the scenario explorer with a prompt that suggests trust distribution or director salary; verify the resulting scenario is flagged `requires_group_model` and displays the explanatory disabled state rather than a misleading single-entity saving.

**Acceptance Scenarios**:

1. **Given** the AI generates a scenario that shifts income between entities, **When** the scenario is rendered, **Then** it is flagged `requires_group_model` and displayed with a disabled state plus explanation.
2. **Given** a single-entity strategy (e.g. prepaid expenses on a Pty Ltd), **When** the scenario is rendered, **Then** it is displayed with its entity-level tax saving as today, and no group-model flag is applied.
3. **Given** a flagged scenario, **When** the accountant views the Analysis tab export, **Then** the flagged scenario is excluded from the combined total or marked as "blocked pending group model".

---

### User Story 5 — The reviewer agent catches errors, not rubber-stamps them (Priority: P1)

When the multi-agent analysis pipeline runs, the reviewer agent verifies every scenario's numbers against an independently-derived ground truth (re-computed from raw confirmed inputs), not against the same cached baseline the modeller used. If any scenario diverges from the independent ground truth beyond a $1 tolerance, the review fails loudly with a specific explanation — and the analysis does not ship to the UI as "verified".

**Why this priority**: Every other correctness fix in this spec could be undermined by a reviewer that always says "all good". The reviewer is the final line of defence; making it actually verify is a prerequisite for trusting the pipeline at all.

**Independent Test**: Inject a deliberately wrong modeller output into the pipeline (e.g. a scenario whose `before.tax_payable` is off by $1000) and assert the reviewer reports `numbers_verified=false` with a specific field and delta.

**Acceptance Scenarios**:

1. **Given** a pipeline run where the modeller's baseline is correct, **When** the reviewer runs, **Then** verification passes.
2. **Given** a pipeline run with an injected modeller error, **When** the reviewer runs, **Then** verification fails with a specific field name and delta.
3. **Given** a verified pipeline result, **When** the UI renders the Analysis tab, **Then** a "verified" signal is visible; an unverified result is visibly flagged.

---

### User Story 6 — Source citations verify reliably (Priority: P2)

When the AI produces a response with citations to tax rulings or legislation, the citation-verification layer correctly identifies legitimate citations that reference retrieved knowledge-base content — including by section paraphrase, by document title, or by cross-reference to chunk body text — rather than flagging them as unverifiable. The confidence score that controls whether a response is delivered or replaced with a decline message is computed correctly (bug: dict-key typo).

**Why this priority**: Unverified citation badges destroy trust even when the underlying answer is correct. The dict-key typo means the current system is replacing legitimate answers with "I cannot answer" far too often. P2 rather than P1 because it affects perceived quality more than arithmetic correctness — but a fast hotfix is part of this spec.

**Independent Test**: Seed the knowledge base with known chunks; prompt the agent with a question whose answer should cite those chunks; assert the verifier marks the citations `verified` and the `confidence_score` is above the decline threshold.

**Acceptance Scenarios**:

1. **Given** an AI response that cites a section of a ruling whose body text is in a retrieved chunk (but the chunk's `section_ref` is the parent division), **When** verification runs, **Then** the citation is marked verified via chunk-text fallback.
2. **Given** retrieved chunks with legitimate relevance scores, **When** the confidence score is computed, **Then** the computation uses the chunks' actual relevance-score field, not a non-existent key.
3. **Given** the decline threshold is not breached, **When** the response is returned to the UI, **Then** the user sees the actual AI response, not the canned decline message.
4. **Given** a response with a hallucinated citation that has no corresponding chunk, **When** verification runs, **Then** the citation is correctly flagged unverified (the verifier must not become permissive to the point of missing real hallucinations).

---

### User Story 7 — No pre-Stage-3 rate language leaks to the language model (Priority: P2)

Every prompt string fed to Claude reflects the current Stage-3 Australian personal income-tax rates and thresholds. No pre-Stage-3 language (19%, 32.5%, $120,000 threshold) appears in any prompt module, example, or grounding block. Test-factory fixtures use Stage-3-aligned rates. A CI-gate test enforces absence of pre-Stage-3 strings.

**Why this priority**: The calculation engine itself is clean (DB seed is correct). This story is about preventing LLM narrative drift. The impact is in wording of AI explanations, not in numeric outputs — hence P2, but enforcement is cheap.

**Independent Test**: Run a repo-wide scan over prompt modules; assert no occurrence of `"32.5"`, `"19%"`, or `"$120,000"`. Independently render a strategy-explanation response and assert it references current-FY thresholds.

**Acceptance Scenarios**:

1. **Given** any prompt module in the tax-planning or agents modules, **When** scanned for pre-Stage-3 rate strings, **Then** none are present.
2. **Given** the tax-planning system prompt, **When** inspected, **Then** it contains an explicit Stage-3 rate grounding block.
3. **Given** a test run, **When** the prompt-scan contract test executes, **Then** it fails on any occurrence of pre-Stage-3 strings.

---

### User Story 8 — Duplicate scenarios do not accumulate (Priority: P2)

When an accountant asks the AI to refine a strategy across multiple chat turns, Clairo does not accumulate visually-identical scenarios. Either the existing scenario is updated, or the new scenario is presented with a distinguishing title, not as a silent duplicate.

**Why this priority**: Visible quality issue that embarrasses in front of a client but does not produce wrong numbers. P2.

**Independent Test**: Issue two chat prompts to the AI that both produce a scenario with the same normalised title; assert only one scenario row exists in the persisted state, or both have clearly distinct titles.

**Acceptance Scenarios**:

1. **Given** a scenario "Prepay rent" already exists, **When** the accountant asks for "Prepaid rent strategy", **Then** either the existing scenario is refined or the new one has a clearly distinct title — no silent duplicate row.
2. **Given** the AI emits two tool calls with identical strategy inputs in a single turn, **When** scenarios are persisted, **Then** only one row lands.

---

### Edge Cases

- **Xero data contains months outside the financial year**: Annualisation must only consider months within the active FY; pay runs and P&L lines straddling the FY boundary must be correctly attributed.
- **Manual financials with no Xero connection**: Annualisation does not apply; accountant is responsible for entering full-year figures; system marks them confirmed.
- **Payroll data unavailable mid-session**: If `has_payroll_access` flips to `False` after plan creation (token revoked), the tax plan must detect stale payroll state and warn rather than silently recalculating with empty data.
- **Reviewer disagreement with modeller within tolerance**: Sub-$1 deltas are expected from float/decimal rounding and must not fail the review.
- **Scenario with zero modifier**: A scenario whose net effect is zero must still be representable and must not be treated as a duplicate of another zero-effect scenario if its category differs.
- **Citation verifier false-positive on hallucinated title**: If the AI hallucinates a document title that happens to substring-match a retrieved chunk, verification must not pass on title-only match; a body-text check or title-integrity check is required.
- **Chat history with >20 scenarios**: Deduplication must operate without scanning the entire history on every write (use normalised-title unique constraint).
- **Multi-entity strategy on a single-entity plan**: The `requires_group_model` flag must apply based on strategy category, regardless of whether the plan contains one or many entities.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Data ingestion & projection

- **FR-001**: The system MUST annualise year-to-date income and expense figures to a projected full financial year whenever the loaded data covers fewer than 12 months of the active FY. The annualisation rule MUST be linear: `projected_total = (YTD_total / months_elapsed) × 12`. Accountants MUST be able to override the projected figures via the manual-entry form when a different baseline (e.g. seasonality-adjusted) is required.
- **FR-002**: The tax-position calculation engine MUST operate on the projected full-year figures only. Year-to-date-only figures MUST NOT be used as the basis for tax-payable calculations when a projection is available.
- **FR-003**: The system MUST NOT present the year-to-date and projected figures side-by-side in any prompt fed to the language model.
- **FR-004**: When the loaded data covers 12 or more months of the active FY, the system MUST NOT apply annualisation and MUST use figures as supplied.
- **FR-005**: When an accountant saves manually-entered financials, the system MUST treat the entered figures as user-confirmed full-year values and MUST NOT annualise them.

#### Payroll wiring & credits

- **FR-006**: When a tax plan is created for a Xero connection with payroll access and no recent payroll sync exists, the system MUST trigger a payroll sync on demand. The sync MUST be awaited synchronously for up to 15 seconds; if it completes in that window, the fresh data MUST be used. If it does not, plan creation MUST continue, the sync MUST be continued in the background, and the UI MUST display a "payroll still syncing" banner until the data arrives — at which point the tax position and credits MUST recompute against the fresh data.
- **FR-007**: The Xero-to-financials transform MUST propagate the year-to-date PAYG Withholding total from the payroll summary into the `credits.payg_withholding` field used by the tax-position calculator.
- **FR-008**: The Xero-to-financials transform MUST surface the year-to-date superannuation and PAYGW totals to every downstream AI agent that claims to evaluate super strategies.
- **FR-009**: When payroll data is unavailable (no payroll access, sync failure, or connection missing), the system MUST surface an explicit, actionable message to the accountant — not a silent $0 — and log the unavailability at WARNING level minimum.
- **FR-010**: Saving manually-entered financials MUST preserve all previously-loaded non-accountant-editable context — payroll summary, bank balances, strategy context, prior-year context — rather than overwriting the full financials structure.

#### Provenance

- **FR-011**: Every numeric field on a scenario (modified income, modified expenses, adjustments, and any other derived quantities) MUST carry a provenance tag drawn from the set `{confirmed, derived, estimated}`.
- **FR-012**: The modeller tool schema MUST require the language model to declare the provenance of every numeric field it outputs; outputs that omit provenance MUST be rejected.
- **FR-013**: The Analysis endpoint MUST include the confirmed financials data alongside AI-derived scenario output so the UI can render both.
- **FR-014**: The UI MUST render *estimated* figures with a distinct visual treatment (e.g. badge and tooltip) so the accountant cannot mistake them for confirmed inputs at a glance.
- **FR-015**: Each *estimated* figure MUST be rendered in the UI as an editable input prefilled with the AI's suggested value. The accountant MUST be able to (a) accept the prefilled value verbatim (e.g. by pressing Enter or blurring the field unchanged), (b) modify the value, or (c) clear it. On any of these actions the figure MUST transition to *confirmed* and persist with the final value the accountant left in place. The system MUST NOT offer a bulk "confirm all" action at the scenario or analysis level in this spec's scope.
- **FR-016**: A client-facing export MUST either omit *estimated* figures or prominently flag them; it MUST NOT silently present estimates as confirmed.

#### Multi-entity honesty flag

- **FR-017**: Every scenario produced by the scanner or modeller MUST carry a `strategy_category` drawn from a closed, code-defined enumeration (e.g. `prepayment`, `capex_deduction`, `super_contribution`, `director_salary`, `trust_distribution`, `dividend_timing`, `spouse_contribution`, `multi_entity_restructure`, `other`). The system MUST maintain a code-level mapping of which categories require the group model. Scenarios whose category is in the "requires group model" set MUST be persisted with `requires_group_model=true`. The scanner/modeller prompts MUST instruct the language model to select from the allowed categories and reject outputs that do not carry a valid category.
- **FR-018**: The UI MUST render scenarios with `requires_group_model=true` in a disabled state with an explanation that the precise multi-entity benefit cannot be modelled until the group tax model is available.
- **FR-019**: Flagged scenarios MUST NOT be included in a combined-strategy total unless the combined total also indicates incompleteness.

#### Reviewer independence

- **FR-020**: The reviewer agent MUST verify scenario numbers against an independently-derived ground truth computed from the raw confirmed financial inputs — not against the cached baseline the modeller used.
- **FR-021**: When the reviewer detects a divergence greater than $1 on any verified field, it MUST return `numbers_verified=false` with a specific field name and the numeric delta.
- **FR-022**: The UI MUST surface verification status visibly alongside analysis output. A failed verification (`numbers_verified=false`) MUST NOT block the analysis from rendering; instead, the UI MUST display a prominent top-of-page warning banner AND a per-scenario badge identifying the specific failing field(s) and numeric delta. The accountant retains discretion to use, correct, or regenerate the result.

#### Citation verification

- **FR-023**: The citation-verification layer MUST match citations against retrieved chunks by identifier (ruling number, section ref, title) AND by body-text fallback, so that legitimate citations referencing chunk body content are not wrongly flagged unverified.
- **FR-024**: The confidence-score computation MUST use the correct field name for chunk relevance scores; computation against a non-existent field that collapses the score to near-zero MUST be fixed.
- **FR-025**: The UI MUST distinguish a low-confidence decline from a no-citations state; the status enum on both backend and frontend MUST include every status the backend can emit.
- **FR-026**: The verifier MUST continue to flag hallucinated citations with no corresponding chunk as unverified — the fix MUST NOT introduce a permissive loophole.

#### Rate currency

- **FR-027**: No prompt module in the tax-planning or agents modules MAY contain pre-Stage-3 personal income tax rate strings (`"32.5"`, `"19%"`, `"$120,000"`). A contract test MUST enforce this.
- **FR-028**: The tax-planning system prompt MUST contain an explicit Stage-3 rate grounding block listing the current FY bracket thresholds and rates.
- **FR-029**: Test factory fixtures that carry a personal tax rate MUST use a Stage-3-aligned value.

#### Scenario deduplication

- **FR-030**: Persisted scenarios within a tax plan MUST be unique by `(plan_id, normalized_title)` where normalized title is case-insensitive and whitespace-trimmed.
- **FR-031**: Scenario persistence MUST use upsert semantics rather than blind insert, so refinements across chat turns update the existing row.
- **FR-032**: The chat system prompt MUST instruct the language model not to emit a scenario whose title is substantially similar to an existing scenario in the conversation history.

### Key Entities *(include if feature involves data)*

- **TaxPlan**: Existing entity representing a single-entity tax planning engagement. This spec does not change its shape beyond adding the `months_elapsed` and annualisation-applied flags surfaced on the financials data. Relationships to `TaxScenario` and `TaxPlanAnalysis` unchanged.
- **TaxScenario**: Existing entity representing one strategy option. This spec adds `requires_group_model` boolean flag and `provenance` tags on every numeric field of `impact_data` and `assumptions`. Adds uniqueness invariant on `(plan_id, normalised_title)`.
- **TaxPlanAnalysis**: Existing entity representing the multi-agent analysis output. This spec requires the Analysis endpoint response to include the confirmed financials alongside AI output.
- **CalculatorGroundTruth**: New conceptual entity — the deterministic re-derivation of taxable income and tax position from raw confirmed inputs, used by the reviewer agent to verify modeller output independently. May be represented as a helper function rather than a persisted entity.
- **PayrollSummary**: Existing computed view on `XeroPayRun` rows for a given Xero connection and FY. This spec ensures its `total_tax_withheld_ytd` flows into `credits.payg_withholding` and its super figures reach the scanner agent.
- **CitationVerificationResult**: Existing entity representing verification status for an AI response. This spec expands the matching logic to include body-text fallback and fixes the confidence score computation; the status enum gains explicit `low_confidence` representation on both backend and frontend.

---

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [x] **Authentication Events**: No new authentication or authorisation changes introduced by this spec.
- [x] **Data Access Events**: Tax plans read financial data (BAS figures, payroll, bank); access events are covered by existing tax-planning module auditing.
- [x] **Data Modification Events**: YES — scenario creation/update, manual financials save, scenario confirmation of estimates, provenance transitions, and reviewer verification outcomes are business-critical modifications that must be audited.
- [x] **Integration Events**: YES — on-demand payroll sync triggered by tax-plan creation is an integration event that must be audited.
- [x] **Compliance Events**: YES — the tax plan is part of the accountant's advisory record; correctness events (reviewer verification pass/fail, annualisation application, provenance confirmation) affect the compliance trail.

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| `tax_planning.financials.annualised` | `pull_xero_financials` or plan creation applies projection | `months_elapsed`, raw YTD totals, projected totals, projection rule used | 7 years | None |
| `tax_planning.payroll.sync_triggered` | On-demand payroll sync kicked off by tax-plan creation | Connection id, sync outcome, pay-run count, totals summary | 7 years | None |
| `tax_planning.payroll.unavailable` | Payroll data cannot be loaded (no access, sync failure) | Reason code, connection id | 7 years | None |
| `tax_planning.scenario.provenance_confirmed` | Accountant confirms an *estimated* figure | Scenario id, field name, before value (*estimated*), after value (*confirmed*), actor | 7 years | None |
| `tax_planning.scenario.requires_group_model_flag` | Scenario persisted with `requires_group_model=true` | Scenario id, strategy category, AI rationale | 7 years | None |
| `tax_planning.review.verification_failed` | Reviewer detects modeller/ground-truth divergence | Plan id, scenario id, field, delta | 7 years | None |
| `tax_planning.citation.verification_outcome` | Citation verification completes | Message id, total citations, verified count, confidence score, status | 7 years | None |
| `tax_planning.manual_financials.saved` | Accountant saves manual-entry form | Plan id, fields changed (before/after), preserved context keys | 7 years | None |

### Compliance Considerations

- **ATO Requirements**: This spec strengthens rather than changes the tax-plan compliance trail. The reviewer-verification-failed event, annualisation event, and provenance-confirmed event all strengthen defensibility for professional liability purposes.
- **Data Retention**: Follow standard 7-year retention. No extended retention required.
- **Access Logging**: Existing tax-planning module access logging is sufficient — no new access surfaces introduced.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the Zac Phillpott golden-dataset fixture, every figure in Tax Position, every scenario before/after, and the combined-strategy total match the ChangeGPS-equivalent reference output within $1.
- **SC-002**: Repeating the alpha-session scenario end-to-end on a clean client produces zero occurrences of any of the original seven P0 symptoms (YTD-basis tax payable, silent payroll $0, PAYGW-credit-ignored, AI-invented figures without provenance, pre-Stage-3 rate strings, duplicate scenarios, "sources could not be verified" on a legitimate citation).
- **SC-003**: 100% of numeric fields displayed in the Analysis tab and Scenarios tab carry a visible provenance tag.
- **SC-004**: The golden-dataset end-to-end test runs in continuous integration on every pull request that touches the tax-planning module and blocks merge on any regression.
- **SC-005**: The prompt-scan contract test catches any introduction of pre-Stage-3 rate strings within the same CI run, before any human review.
- **SC-006**: An injected modeller error (off by more than $1 on a verified field) causes the reviewer to emit `numbers_verified=false` with a specific field name and delta in ≥ 99% of injected-error test runs.
- **SC-007**: The accountant running the next live alpha session reports that they did not cross-check any Clairo number against an external tool during the session.
- **SC-008**: Legitimate AI responses with correctly-grounded citations are no longer replaced by the canned decline message; in a 20-question regression bank, ≤ 1 response is replaced by the decline when it should have been delivered.

---

## Dependencies

- **spec 049 (AI tax planning)** — base feature being corrected. This spec assumes 049 is shipped and stable.
- **spec 050 (RAG tax planning)** — citation verification infrastructure. This spec modifies how citation verification is invoked and fixes the confidence-score computation; does not change RAG retrieval itself.
- **spec 041 (multi-agent tax planning)** — agent orchestration pipeline (profiler / scanner / modeller / advisor / reviewer). This spec modifies the reviewer and modeller contracts; does not change orchestration structure.
- **spec 046 (tax planning intelligence)** — existing intelligence layer context.

## Out of Scope

- **Multi-entity (group) tax modelling** — deeper architectural fix for the Net-Benefit bug. Covered by a separate brief (`specs/briefs/2026-04-18-tax-planning-group-tax-model.md`) and will become its own spec. This spec only adds the `requires_group_model` honesty flag as an interim safety measure.
- **Tax-planning UX/UI rethink** (Excel-style layout, tax waterfall display, per-entity scenario breakdown, client-facing one-pager) — separate design and build track.
- **Engagement thread** (pre-meeting brief, in-meeting notes, post-meeting follow-up) — separate spec.
- **ATO integrations** (PAYG instalment feed, carry-forward super data) — separate spike.
- **Non-Xero client ingestion** — separate problem.

## Assumptions (💡)

- 💡 **Golden-dataset source**: Unni can supply the sanitised Zac Phillpott inputs and the ChangeGPS reference numbers for use as a fixture. If not, the test infrastructure is still built, but fixture population happens post-approval.
- 💡 **Annualisation rule override UX**: manual-entry form is the override path — no separate "projection rule selector". Accountant seasonality-adjusts by entering the adjusted figures directly.
- 💡 **Provenance storage**: provenance tags are stored on each scenario as a `source_tags` JSONB field rather than as a separate normalised table, avoiding a heavy schema migration.
- 💡 **Reviewer independence**: the reviewer becomes a deterministic re-derivation rather than an LLM-based "does this make sense" layer. An LLM reviewer is a possible future enhancement but not in this spec.
- 💡 **Prompt-scan strictness**: the contract test blocks occurrences of pre-Stage-3 strings everywhere in prompt modules (not whitelisted in comments), with the contract test file itself the only explicitly-whitelisted site.
- 💡 **Payroll sync recompute on arrival**: when the 15s synchronous window expires and payroll data arrives later from the background sync, the tax position, credits, and any scenario baselines automatically recompute. No manual refresh required.

## Open Questions (max 3)

_None outstanding — annualisation rule resolved in clarification session._
