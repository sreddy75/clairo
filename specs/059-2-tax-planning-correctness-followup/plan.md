# Implementation Plan: Tax Planning Modeller — Architectural Redesign

**Branch**: `059-2-tax-planning-correctness-followup` | **Date**: 2026-04-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/059-2-tax-planning-correctness-followup/spec.md`

## Summary

Replace the language-model-controlled tool-use loop in `backend/app/modules/tax_planning/agents/modeller.py` with a **single forced-tool-call** pattern. The language model returns one structured response containing a list of strategy modifications; Python validates, dedupes, truncates, then iterates the list calling the existing deterministic tax calculator once per validated modification. Delete the three failed defensive filter layers (hard cap, keyword strip, ratio threshold) along with the dead re-filter inside `_build_combined_strategy`. No database, frontend, or sibling-agent changes. Preserves all Spec 059 per-scenario provenance behaviour.

## Technical Context

**Language/Version**: Python 3.12+ (backend only)
**Primary Dependencies**: `anthropic` SDK (AsyncAnthropic), Pydantic v2 (for optional modification validator), existing `app.modules.tax_planning.tax_calculator.calculate_tax_position`, existing `app.modules.tax_planning.strategy_category` enum
**Storage**: N/A — no schema changes. The only persisted outputs (`TaxPlanAnalysis.recommended_scenarios`, `TaxPlanAnalysis.combined_strategy`) retain their existing shape.
**Testing**: pytest + pytest-asyncio with `AsyncMock` for the Anthropic client. Test file: `backend/tests/modules/tax_planning/agents/test_modeller.py` (existing — extend with new cases)
**Target Platform**: Linux server (FastAPI + Celery worker running in Docker)
**Project Type**: Single backend module within the modular monolith — no frontend work, no cross-module changes
**Performance Goals**: A single synchronous Anthropic call with ≤8 modifications must complete within the provider's synchronous-response threshold (under 10 minutes by SDK contract; expected under 60s in practice). Per-agent latency stays under the existing budget.
**Constraints**: Must stay synchronous (no streaming API); must preserve `modeller.run() → tuple[list[dict], dict]` signature exactly; must preserve all source_tags, group-model gate, enum coercion from Spec 059.
**Scale/Scope**: Up to 8 strategies per modeller run (cap set by scanner). Single agent module, single file rewrite (~200 LOC net change), ~80 LOC of new tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Modular Monolith | ✅ Pass | Change is entirely within `modules/tax_planning/agents/`. No cross-module imports added or removed. |
| II. Technology Stack | ✅ Pass | Uses existing `anthropic` SDK, no new dependencies. |
| III. Repository Pattern | N/A | No DB access in the modeller — the persistence layer is the orchestrator, unchanged. |
| IV. Multi-Tenancy | ✅ Pass | Modeller operates on already-scoped inputs from the orchestrator. Tenant isolation is upstream. |
| V. Testing Strategy | ✅ Pass | Unit tests for three new structural guarantees (unknown-id drop, dedupe, truncation) plus arithmetic-correctness regression (FR-004). Test-first is the plan for the validation helper. |
| VI. Code Quality | ✅ Pass | Type hints throughout, Pydantic v2 for the modification validator, domain exceptions are unchanged. |
| VII. API Design | N/A | No HTTP API surface change. |
| VIII. External Integrations | ✅ Pass | Anthropic API usage is simpler (one call vs many); behaviour contract unchanged. |
| IX. Security | ✅ Pass | No new secret handling, no new user input surface. |
| X. Auditing & Compliance | ✅ Pass | Diagnostic log lines added (FR-009). No change to audit event schema — this is internal observability, not tenant-visible audit. |
| XI. AI/RAG Standards (Human-in-the-loop) | ✅ Pass | Accountant approval flow unchanged. The improvement strengthens the "AI suggests, human approves" guarantee by removing AI control over output count. |
| XII. Spec-Kit Process | ✅ Pass | This plan follows `/speckit.specify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement`. |

**Gate verdict**: PASS. No violations. Complexity tracking section omitted.

## Project Structure

### Documentation (this feature)

```text
specs/059-2-tax-planning-correctness-followup/
├── plan.md              # This file
├── research.md          # Phase 0 output (below)
├── data-model.md        # Phase 1 output (below) — internal data shapes
├── quickstart.md        # Phase 1 output (below) — dev verification steps
├── contracts/
│   └── submit_modifications_tool.json   # JSONSchema for the forced tool call
├── checklists/
│   └── requirements.md  # Already created by /speckit.specify
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── app/
│   └── modules/
│       └── tax_planning/
│           ├── agents/
│           │   ├── modeller.py            # REWRITE — core of this spec
│           │   ├── prompts.py             # EDIT — replace MODELLER_SYSTEM_PROMPT
│           │   └── (orchestrator.py, advisor.py, reviewer.py, scanner.py, profiler.py: UNTOUCHED)
│           ├── prompts.py                 # EDIT — add SUBMIT_MODIFICATIONS_TOOL; keep CALCULATE_TAX_TOOL for legacy chat agent
│           ├── tax_calculator.py          # UNTOUCHED — stable primitive
│           ├── strategy_category.py       # UNTOUCHED
│           └── agent.py                   # UNTOUCHED — legacy single-agent chat flow, still uses CALCULATE_TAX_TOOL
└── tests/
    └── modules/
        └── tax_planning/
            └── agents/
                └── test_modeller.py       # EDIT — add 4 new test cases; remove tests tied to deleted filter layers
```

**Structure Decision**: The feature touches three files of production code (all inside `backend/app/modules/tax_planning/`) plus one test file. No new modules, no new directories, no cross-module boundary crossings. Matches Constitution I (modular monolith, single-module change).

## Phase 0 Output: Research (`research.md` content)

### R1 — Anthropic forced `tool_choice` behaviour

**Decision**: Use `tool_choice={"type": "tool", "name": "submit_modifications"}` on the `messages.create` call with a single tool definition.

**Rationale**: Per Anthropic's tool-use documentation, specifying `tool_choice` with a named tool forces the model to emit a `tool_use` content block for that tool. The response's `stop_reason` is `tool_use`, and `response.content` contains at least one block of type `tool_use` with `name == "submit_modifications"` and a validated `input` object matching the declared `input_schema`. Schema violations are caught at the API boundary — the SDK raises `anthropic.BadRequestError`, which means invalid JSON cannot reach our code. This gives us Pydantic-grade validation for free at the boundary, and we only need to validate semantic correctness (`strategy_id` membership) in our code.

**Alternatives considered**:
- *Prose/JSON extraction*: ask the model to return JSON inline and parse. Rejected — fragile (markdown fences, prose preamble, hallucinated keys) and requires our own schema validator. Forced tool use is strictly better.
- *Parallel tool calls*: use Anthropic's `disable_parallel_tool_use` toggle with a many-call loop. Rejected — keeps the LLM in the control-flow loop, which is exactly what this spec is eliminating.
- *Streaming API*: use `client.messages.stream(...)` with a tool-use loop. Rejected — addresses only the secondary streaming-threshold symptom, not the primary double-counting root cause.

### R2 — Token budget for the single forced call

**Decision**: Set `MAX_TOKENS` on the modeller's single call to **12,000**.

**Rationale**:
- Output content for the forced tool call is a JSON payload with up to 8 modification objects. Each modification is ~300-600 tokens (title, description, 3-5 assumptions, modifiers, category, risk rating, compliance notes). Upper bound: 8 × 600 = 4,800 tokens.
- 12,000 leaves 7,200 tokens of headroom for Claude's reasoning plus the tool-call scaffolding wrapper.
- 12,000 stays well below the Anthropic-enforced synchronous-response threshold that triggered the "Streaming is required" error at 32,000.
- Consistent with the advisor's `max_tokens=64000` for much longer generations (which uses streaming) — the modeller's output is smaller by design.

**Alternatives considered**:
- *8,000*: too tight — would risk truncation if Claude writes verbose compliance notes.
- *16,000*: probably also fine but closer to the threshold; 12,000 gives more margin.
- *Dynamic sizing based on input strategy count*: unnecessary complexity — the upper bound of 8 strategies is known.

### R3 — Tool input schema shape

**Decision**: `SUBMIT_MODIFICATIONS_TOOL` accepts an object with a single `modifications` array. Each array entry contains exactly the fields needed to recreate the existing `_execute_tool` input plus the addressing key (`strategy_id`).

**Rationale**: Mirror the existing `CALCULATE_TAX_TOOL` schema so the per-modification payload stays drop-in compatible with `_execute_tool`'s current input shape. Only differences: (a) `strategy_id` is mandatory and must match an input strategy ID (enforced in code, not schema); (b) multiple entries in a single call instead of one entry per call. No need for Pydantic runtime validation inside Python — the Anthropic SDK validates against `input_schema` at the API boundary.

**Alternatives considered**:
- *Pydantic model for runtime re-validation*: rejected as redundant belt-and-braces. If the API-boundary validation passes, the JSON shape is guaranteed. We only need semantic validation (`strategy_id` membership) in code.
- *Two-tool design (one for "plan modifications", one for "finalise")*: rejected — reintroduces multi-call semantics.

### R4 — `strategy_id` addressing convention

**Decision**: Input strategies are already keyed by their `id` field (set by the scanner agent). The modifications payload references this `id` verbatim. Code validates with a simple `set` membership check.

**Rationale**: The scanner already emits strategies with stable IDs (e.g., `prepay-deductible-expenses`, `carry-forward-concessional-cap`). These IDs are opaque to the modeller, which treats them as tokens. The strategy_id on each returned scenario (line 318 in the current modeller: `tool_input.get("scenario_title", "").lower().replace(" ", "-")`) is currently a slug of the free-form title — this needs to change to use the input `id` directly, because slugs of LLM-chosen titles don't match input IDs.

**Alternatives considered**:
- *Fuzzy/semantic match of titles to input strategies*: rejected — non-deterministic, reintroduces ambiguity, defeats the "code is law" property.
- *Integer index addressing*: workable but more error-prone (off-by-one, reordering). String IDs are human-readable in logs and durable.

### R5 — Extract `_execute_tool` to pure `_compute_scenario`

**Decision**: Refactor `_execute_tool(tool_input, base_financials, entity_type, rate_configs)` into a module-level pure function `_compute_scenario(modification, base_financials, entity_type, rate_configs)`. Semantics identical — it takes one modification object and returns one scenario dict. Rename because "tool" no longer fits the architecture.

**Rationale**: The entire body of `_execute_tool` (lines 190-322 of the current `modeller.py`) is correct and carries the Spec 059 behaviour we must preserve (source_tags, group-model gate, enum coercion). Lifting it out of the class and off the tool-use call-site makes it independently testable without needing to mock an Anthropic response.

**Alternatives considered**:
- *Keep as method with same name*: rejected — name lies about what it does in the new design.
- *Inline into the iteration loop*: rejected — makes unit testing harder.

### R6 — Test strategy for the redesigned modeller

**Decision**: Four new unit tests in `backend/tests/modules/tax_planning/agents/test_modeller.py`:

1. `test_drops_unknown_strategy_id` — stubbed Anthropic response contains a modification with `strategy_id="hallucinated-meta"` not in input; assert it is not in returned scenarios.
2. `test_dedupes_duplicate_strategy_ids` — stub returns two modifications with the same `strategy_id`; assert only the first survives.
3. `test_truncates_to_input_count` — stub returns N+1 modifications for N input strategies; assert returned scenarios is length ≤ N.
4. `test_combined_total_equals_sum_of_scenarios` — stub returns 3 valid modifications with known savings; assert `combined.total_tax_saving == sum(scenario.tax_saving)` exactly.

Plus one regression test:

5. `test_group_model_scenario_excluded_from_combined` — modification with a group-model category yields `tax_saving=0` and is excluded from the combined total (preserves Spec 059 behaviour).

Delete any existing tests that assert behaviour of the three filter layers being removed.

**Rationale**: Tests exercise exactly the structural guarantees the spec promises. Each is fast (mocked client), independent, and fails clearly if the guarantee regresses.

## Phase 1 Output: Design (`data-model.md` content)

### Internal data shapes

This feature is entirely internal to the modeller. No database entities, no API schemas, no frontend types. The only data shapes are:

#### Scenario Modification (LLM output → Python input)

Shape of each entry in the `modifications` array returned by the forced tool call.

```python
ScenarioModification = TypedDict:
    strategy_id: str               # MUST match one of the input strategies' `id`
    scenario_title: str            # Human-readable display title
    description: str               # One-paragraph explanation for the brief
    assumptions: list[str]         # Bullet-point items rendered in the UI
    modified_income: dict          # {revenue?: float, other_income?: float}
    modified_expenses: dict        # {cost_of_sales?: float, operating_expenses?: float}
    modified_turnover: float | None
    strategy_category: str         # StrategyCategory enum value (coerced, OTHER fallback)
    risk_rating: str               # "conservative" | "moderate" | "aggressive" (coerced)
    compliance_notes: str
```

#### Scenario (Python output, persisted — UNCHANGED from Spec 059)

```python
Scenario = dict:
    scenario_title: str
    description: str
    assumptions: {"items": list[str]}
    strategy_id: str               # Now taken verbatim from the modification (not slug of title)
    strategy_category: str         # Validated StrategyCategory.value
    risk_rating: str               # Validated risk rating
    requires_group_model: bool     # Derived from strategy_category
    impact: {
        before: {taxable_income: float, tax_payable: float},
        after:  {taxable_income: float, tax_payable: float},
        change: {taxable_income_change: float, tax_saving: float},
    }
    cash_flow_impact: float
    source_tags: dict[str, str]    # Exactly as today — "derived"/"estimated" per leaf
    compliance_notes: str
```

#### Combined Strategy (Python output, persisted — UNCHANGED from Spec 059)

```python
CombinedStrategy = dict:
    recommended_combination: list[str]   # list of strategy_ids included
    total_tax_saving: float              # sum of included scenarios' tax_saving (post group-model exclusion)
    total_cash_outlay: float             # -total_cash when total_cash < 0 else 0
    net_cash_benefit: float              # sum of included scenarios' cash_flow_impact
    strategy_count: int                  # len(included)
    excluded_count: int                  # len(real_scenarios) - len(included)
```

### Validation rules (enforced in Python)

1. **Membership**: `modification.strategy_id ∈ {s["id"] for s in input_strategies}` — else drop entry, log diagnostic.
2. **Dedupe**: iterate modifications in order; for each, skip if `strategy_id` already seen — log diagnostic.
3. **Truncation**: after membership + dedupe, slice to first `len(input_strategies)` entries (defence-in-depth — in practice dedupe alone bounds this).
4. **Group-model gate** (unchanged from Spec 059): if coerced `strategy_category` maps to `requires_group_model=True`, force `modified_position = base_position` so `tax_saving = 0`. Applied inside `_compute_scenario`, not in validation.

### State transitions

None — the modeller is a stateless transform: `(input_strategies, financials, entity_type, rate_configs) → (scenarios, combined_strategy)`.

## Phase 1 Output: Contracts (`contracts/submit_modifications_tool.json`)

The only contract here is the tool-call input schema. See `contracts/submit_modifications_tool.json` (created by `/speckit.tasks` or during implementation).

Shape overview:

```json
{
  "name": "submit_modifications",
  "description": "Return the full list of strategy modifications in a single call. One entry per input strategy. Do NOT invent strategies not in the input list.",
  "input_schema": {
    "type": "object",
    "required": ["modifications"],
    "properties": {
      "modifications": {
        "type": "array",
        "items": {
          "type": "object",
          "required": ["strategy_id", "scenario_title", "description", "modified_income", "modified_expenses"],
          "properties": {
            "strategy_id": {"type": "string"},
            "scenario_title": {"type": "string"},
            "description": {"type": "string"},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "modified_income": {
              "type": "object",
              "properties": {
                "revenue": {"type": "number"},
                "other_income": {"type": "number"}
              }
            },
            "modified_expenses": {
              "type": "object",
              "properties": {
                "cost_of_sales": {"type": "number"},
                "operating_expenses": {"type": "number"}
              }
            },
            "modified_turnover": {"type": "number"},
            "strategy_category": {"type": "string"},
            "risk_rating": {"type": "string", "enum": ["conservative", "moderate", "aggressive"]},
            "compliance_notes": {"type": "string"}
          }
        }
      }
    }
  }
}
```

## Phase 1 Output: Quickstart (`quickstart.md` content)

### Verifying the redesign locally

1. **Unit tests** — fast, no Docker needed:
   ```sh
   cd backend && uv run pytest tests/modules/tax_planning/agents/test_modeller.py -v
   ```
   Expect: all 5 tests pass (3 structural guarantees + 1 arithmetic regression + 1 group-model regression).

2. **Static check — three deleted filters are actually gone**:
   ```sh
   grep -nE "_META_KEYWORDS|max_tool_calls|1\.1 \*" backend/app/modules/tax_planning/agents/modeller.py
   ```
   Expect: no matches. Grep exits 1.

3. **End-to-end against real Anthropic API** — requires running Docker stack:
   ```sh
   docker-compose up -d
   docker restart clairo-celery-worker  # pick up new modeller code
   ```
   Open the app, navigate to a client's tax planning tab, click "Re-generate Analysis". Watch worker logs:
   ```sh
   docker logs -f clairo-celery-worker 2>&1 | grep -iE "modeller|tax_saving"
   ```
   Expect: `Modeller: produced N scenarios, combined saving=$X` where N ≤ number of applicable strategies. No "Streaming is required" error. No "rejecting tool call", "name-filter stripped", "structural-filter stripped" log lines (these paths are deleted).

4. **UI verification**: the "Total Tax Saving" headline on the Analysis tab must equal the arithmetic sum of the per-strategy savings shown below. No "Needs Review" banner from combined-total discrepancy.

### Agent context update

Run `.specify/scripts/bash/update-agent-context.sh claude` to refresh the agent context file with new technology facts.

## Re-evaluation: Constitution Check (Post-Design)

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Modular Monolith | ✅ Pass | Confirmed — three files edited, all within `backend/app/modules/tax_planning/`. |
| II. Technology Stack | ✅ Pass | No new deps. |
| V. Testing Strategy | ✅ Pass | Five targeted unit tests; existing Spec 059 integration coverage remains effective since `modeller.run()` signature is stable. |
| VI. Code Quality | ✅ Pass | Type hints retained; extraction of `_compute_scenario` improves testability. |
| X. Auditing | ✅ Pass | Diagnostic logs added; no audit event schema change. |
| XI. AI/RAG Standards | ✅ Pass | "Code is law" principle now *structurally* enforced for modeller output — strongest possible compliance. |

**Post-design gate verdict**: PASS. No new violations introduced by the design decisions.

## Complexity Tracking

*(Omitted — no constitution violations.)*
