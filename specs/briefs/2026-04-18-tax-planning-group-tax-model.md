# Brief: Tax Planning — Group Tax Model (Multi-Entity)

**Date**: 2026-04-18
**Source**: Unni's alpha feedback (Zac & Angela / OreScope session), plus code review of `backend/app/modules/tax_planning/models.py` + `tax_calculator.py`
**Author**: Suren (product) + code analysis
**Related**: Split from `2026-04-18-tax-planning-calculation-correctness.md`. That brief fixes data-accuracy bugs that live above the calculator; this brief changes the **shape** of the tax domain model itself to support multi-entity (group) tax planning. This is the load-bearing abstraction underneath Unni's xlsx layout, the "Net Benefit" bug (F1-13), and the "Distributions from group" UI pattern Feedback 2 called out as the key missing piece.

---

## Problem Statement

Real Australian tax planning is almost always **group tax planning**. A typical client structure is: a Pty Ltd operating company, a family trust, two individual directors/beneficiaries (often spouses), occasionally an SMSF or partnership. Strategies move income **between** these entities — director salary ($X from company to individual), trust distribution ($Y to spouse at their marginal rate), SMSF contribution, franking credit flow. Every strategy that matters is multi-entity.

Clairo today models **one entity per TaxPlan**. `TaxPlan.entity_type` is a single string column. `calculate_tax_position(entity_type, financials_data, …)` dispatches to one of four per-entity functions and has no notion of aggregation. `calculate_trust_tax` is explicitly documented as "Phase 1: No distribution modelling — all income treated as undistributed" (`tax_calculator.py:256`) and taxes undistributed trust income at the flat 0.47 top-marginal rate. `calculate_partnership_tax` similarly notes "Phase 1: Single partner receives 100% of net income" (`tax_calculator.py:292`).

The consequence is F1-13: **"Net Benefit"** reports the tax saving of the single modelled entity, ignoring the offsetting tax paid by the receiving entity. In Unni's session, a strategy that "saved" $44,250 at the company actually saved $4,100 at the group level — an order of magnitude wrong in the accountant-flattering direction. The tool schema `CALCULATE_TAX_TOOL` (`prompts.py:52-115`) exposes only single-entity `modified_income` / `modified_expenses` fields, so the LLM **cannot** express a cross-entity shift even if it wanted to.

This is not a bug to patch. It is a missing abstraction. Every subsequent UX improvement (Unni's per-entity column layout, the tax waterfall, the scenarios table with entity rows, the "Distributions from group" row, multi-entity strategy selection) depends on it.

---

## Users

- **Primary**: Accountants doing tax planning for clients with group structures (~>80% of tax planning engagements in Unni's and Vik's practices)
- **Secondary**: Business owner clients who receive the final recommendation — they need to see consolidated group-level numbers, not per-entity fragments
- **Context**: The accountant's mental model is the xlsx layout — columns per entity, rows of line items, distribution flow between columns, group totals on the right. Clairo's current one-entity-at-a-time model is alien to this.

---

## Jobs to Be Done

### Job 1: Represent a group (MUST HAVE)

**The need**: "I'm doing tax planning for Zac's company, Angela's individual return, and their family trust — all together, not three separate plans."

**What to build**:
- A new domain concept: `TaxPlanGroup` (or extend `TaxPlan` to optionally be a group container). Contains N `TaxPlanEntity` rows — each with its own `entity_type`, `financials_data`, `tax_position`, and relationships to other entities in the group (e.g. "is beneficiary of trust X", "is director of company Y").
- Relationships are explicit: `DistributionFlow` (trust → beneficiary), `SalaryFlow` (company → director), `DividendFlow` (company → shareholder), `ContributionFlow` (any entity → SMSF). Each flow has a `base_amount` (current-state) and per-scenario overrides.
- Existing single-entity TaxPlans remain supported (solo trader, single Pty Ltd) — the group is just a degenerate case with one entity and no flows.

**Data model sketch** (for eng review, not binding):
```
TaxPlan (existing)
  ├─ entities: List[TaxPlanEntity]     ← new
  └─ flows:    List[TaxPlanFlow]       ← new

TaxPlanEntity
  ├─ entity_type, financials_data, tax_position
  ├─ toggles: HELP/TSL, MLS, Div 293, RESC, etc. (per F1-6)
  └─ display_name, display_order

TaxPlanFlow
  ├─ flow_type: "distribution" | "salary" | "dividend" | "contribution"
  ├─ source_entity_id, target_entity_id
  ├─ base_amount, scenario_overrides: dict[scenario_id, amount]
  └─ metadata: franking_rate, super_type, …
```

### Job 2: Group-aware tax calculation (MUST HAVE)

**The need**: "When I shift $90k from the company to Angela's salary, show me the company saving AND Angela's extra tax, AND the net group benefit."

**What to build**:
- New function `calculate_group_tax_position(entities, flows, rate_configs)` that:
  1. Applies all flows to adjust each entity's `financials_data` (trust income reduced by distributions, director taxable income increased by salary, etc.)
  2. Calls `calculate_tax_position` per entity on the adjusted figures
  3. Aggregates: `group_total_tax_payable = sum(entity.tax_payable)`, `group_net_position = sum(entity.net_position)`
  4. Returns both per-entity breakdown AND group totals
- Existing single-entity `calculate_tax_position` remains and is used by `calculate_group_tax_position` under the hood.

### Job 3: Multi-entity strategy modelling (MUST HAVE)

**The need**: "The AI should be able to say 'pay Angela $90k salary, keep $50k in the company, distribute the rest to the trust' as a single strategy, and model it correctly."

**What to build**:
- Replace/extend `CALCULATE_TAX_TOOL` (`prompts.py:52-115`) with a group-aware tool that accepts a `flow_changes` array: `{source_entity_id, target_entity_id, flow_type, amount}`. The calculator applies these and returns per-entity and group numbers.
- Update modeller system prompt (`agents/prompts.py`) to describe the group model, entity references, and legal flow types per entity pair.
- Update scanner prompt to surface multi-entity opportunities (which are structurally invisible today).
- Update reviewer to verify group-level aggregation, not just per-entity consistency.

### Job 4: Per-entity UI (MUST HAVE)

**The need**: "Show me Zac's column, Angela's column, the trust's column, and the group totals. Like my spreadsheet."

**What to build**:
- Position tab: entity columns left-to-right, with a Group Totals column on the right. Rows are the tax waterfall (per `tax-planning-alpha-feedback-synthesis.md` Section 2b).
- Scenarios tab: per-scenario, show a table with entity columns and the key rows (Taxable Income / Tax Assessed / Credits / Payable), plus a Group Totals row. Match ChangeGPS page 6 layout.
- "Distributions from Group" row between entity columns showing the flow amounts (the specific visual pattern Unni called out in Feedback 2).
- Client-facing summary (`tax-planning-alpha-feedback-synthesis.md` Section 2d) consolidates to group level only.

### Job 5: Honest degradation (MUST HAVE)

**The need**: "Don't pretend to know a group when I've only set up one entity."

**What to build**:
- Solo traders, single Pty Ltd without distributions — single entity, no flows — continue to work unchanged.
- If a user tries to create a multi-entity strategy on a single-entity plan, surface a prompt to add the missing entity first.
- AI must refuse to fabricate entities. Strategies reference `entity_id`s that exist; if the plan is single-entity, scanner/modeller cannot propose multi-entity strategies.

---

## What NOT to Build

- **Full Division 7A loan modelling** — out of scope for v1, flag only.
- **Full PSI engine** — Unni's PSI catch in the alpha session is important, but it's a separate spec (covered implicitly under "engagement thread — pre-meeting brief", a separate future brief).
- **Inter-entity loan tracking** — flag known loans as metadata only; don't model interest/repayment implications in v1.
- **Consolidated groups** (tax consolidation under Division 701) — not for v1. Assume each entity is a separate taxpayer.
- **SMSF full modelling** — treat SMSF as a contribution-receiving entity with a flat concessional-cap check. Full SMSF tax calc out of scope.
- **FBT calculation** — show reportable FBT as an input toggle (already in F1-6), do not compute.
- **Schema migration of existing alpha TaxPlans** — alpha plans are few and disposable. Fresh migration only; existing plans can be archived.

---

## Technical Context

**Key models to change**:
- `backend/app/modules/tax_planning/models.py:127` — `TaxPlan.entity_type` moves to `TaxPlanEntity.entity_type`; `TaxPlan` becomes a group container
- `backend/app/modules/tax_planning/models.py:345-348` — `TaxPlanAnalysis.entities` / `group_structure` / `distribution_plan` / `entity_summaries` JSONB columns already exist but are unwritten. **Repurpose** these as the first iteration's storage (avoid a schema migration) OR promote to normalised tables — eng call during `/speckit.plan`.

**Key services to change**:
- `backend/app/modules/tax_planning/tax_calculator.py` — add `calculate_group_tax_position`
- `backend/app/modules/tax_planning/agents/modeller.py` — multi-entity tool
- `backend/app/modules/tax_planning/agents/scanner.py` — multi-entity strategy awareness
- `backend/app/modules/tax_planning/prompts.py` — `CALCULATE_TAX_TOOL` schema rewrite
- `backend/app/modules/tax_planning/service.py` — plan creation, scenario persistence, analysis endpoint

**Frontend surfaces**:
- Position tab (`TaxPositionCard.tsx`) — entity columns layout
- Scenarios tab (`ComparisonTable.tsx`) — per-entity rows + group total
- Financials input panel — entity toggles row per entity
- New component: `DistributionFlowRow` — the between-column flow visualisation

**Relationships to existing domain**:
- `XpmClient` / Xero client records represent a single ABN. A tax plan group references **one primary client** plus associated individuals (directors/beneficiaries) that are linked manually or via Xero practice staff data.
- No assumption that Xero has all entities. Non-Xero entities (individuals, trusts) will typically be manual.

---

## Testing & Regression Strategy

**Same philosophy as the correctness brief.** The calculator-level unit tests are insufficient. Group tax introduces a whole new class of invariants that need testing above the calculator.

### New test layers this brief must land

**1. Group calculator unit tests (extend `test_tax_calculator.py`)**
- `test_group_with_company_and_director_salary` — $500k company profit, shift $150k to director salary, assert company tax drops by $150k × 25% = $37.5k AND director tax increases by correct individual-bracket amount, AND group total is the sum.
- `test_group_with_trust_distribution_to_spouse` — trust $200k undistributed (taxed at 47% = $94k) vs distributed $200k to spouse on $0 other income (individual brackets = $60.8k). Group saving = $33.2k.
- `test_group_with_zero_flows_matches_single_entity` — degenerate case: group of one entity, no flows, output identical to single-entity calc.
- `test_group_flow_consistency_invariants` — every flow's source reduction equals target increase (no flow "leaks" income out of the group).

**2. Modeller/agent tests**
- `test_modeller_cannot_fabricate_entities` — scenario referencing an entity_id not in the plan is rejected.
- `test_scanner_surfaces_multi_entity_strategies_when_group_exists` — seed a group, assert scanner output includes at least one flow-type strategy.
- `test_reviewer_catches_group_aggregation_error` — inject a scenario with inconsistent entity/group totals, assert reviewer flags.

**3. Golden-dataset E2E extension**
- Add a group fixture: Zac (company) + Angela (individual) + Phillpott Family Trust. Full pipeline run. Assert group totals match ChangeGPS and per-entity rows match per-entity expected values.
- This sits alongside the single-entity golden fixture from the correctness brief.

**4. Schema invariant tests**
- `test_no_scenario_has_company_only_net_benefit_label` — the string `"net_benefit"` never appears alone without accompanying `"group_net_benefit"` when entity count > 1.
- `test_tax_plan_single_entity_backward_compat` — old-shape TaxPlan records (one entity) still render correctly.

**5. Migration / contract test**
- `test_existing_single_entity_plans_migrate_to_group_of_one` — any serialisation path that touches a legacy plan produces a group shape with one entity and no flows.

### What to test first
- Group calculator unit tests — fastest, pinpoint the math.
- Modeller tool contract test — the new tool schema must parse and reject malformed flows.
- Golden group E2E — the proof-of-correctness that ties it all together.

---

## Success Criteria

1. A tax plan for Zac + Angela + trust can be created, has three entity columns in the UI, and shows a correct group total.
2. A strategy that shifts $90k from company to director salary shows: company saving, individual extra tax, group net benefit — all three numbers, all correct within $1.
3. The AI modeller can express a multi-entity strategy as a single scenario (not three separate scenarios).
4. Scenarios tab matches the ChangeGPS page-6 layout (entity rows, columns for Taxable Income / Tax Assessed / Credits / Payable, total row).
5. "Distributions from Group" row renders visually between the trust column and beneficiary columns.
6. Single-entity plans (existing behaviour) remain functional with no regressions.
7. Unni says: "This is what my xlsx does, but better."

---

## Open Questions

1. **Storage shape**: Do `TaxPlanEntity` and `TaxPlanFlow` become normalised tables, or do we pack them into `TaxPlanAnalysis.group_structure` JSONB (already exists at `models.py:345-348`)? Normalised is cleaner for querying and scenario-override overlays; JSONB is faster to ship. Default recommendation: JSONB for v1, promote to tables in v2 once patterns are stable.
2. **Entity identity across Xero**: If an individual is a director of two Xero-connected companies, do they share one `TaxPlanEntity` across groups, or is each group independent? Default: independent per group for v1.
3. **Flow default sourcing**: For existing clients with trust distribution history in Xero (if available) or manual entry, do we pre-populate flow base amounts? Default: pre-populate from prior-year data where available, otherwise start at $0.
4. **Scenario override scope**: When a scenario modifies a flow, does it override just that flow, or can it restructure entirely (add/remove flows)? Default: full restructuring allowed — scenarios are full "what-if" snapshots.
5. **UI complexity**: Entity columns could get wide (5+ entities). Horizontal scroll, hide-show columns, or limit to 4? Ask Unni.
6. **LLM prompt size**: A group with 4 entities each having 17-line-item income + expenses is a lot of context. Do we need to summarise for the LLM? Default: yes, pass financials_data but summarise the tax_position and key toggles only; full raw data available via tool call.

---

## Sequencing

This brief is the second sprint in Unni's synthesis. It cannot start until the correctness brief is done, because:
- The group calculator is built on top of the per-entity calculator (which must be correct first).
- The new tool schema must include the provenance fields introduced in the correctness brief.
- The reviewer's ground-truth verification approach is shared.

Rough effort: the correctness brief is 2 weeks. This brief is 3-4 weeks. Total 5-6 weeks before Clairo can credibly replace ChangeGPS on tax calculations for real clients — matches Unni's synthesis.
