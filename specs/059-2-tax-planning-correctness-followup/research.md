# Phase 0 Research: Modeller Redesign

**Feature**: Tax Planning Modeller — Architectural Redesign
**Date**: 2026-04-18
**Status**: Complete — all decisions below resolved; no open `NEEDS CLARIFICATION` markers

---

## R1 — Anthropic forced `tool_choice` behaviour

**Decision**: Use `tool_choice={"type": "tool", "name": "submit_modifications"}` on a single `client.messages.create` call with one tool definition.

**Rationale**:
- Anthropic's tool-use API, when given `tool_choice` with a named tool, forces the model to emit a `tool_use` content block for that tool on its first stop. The response's `stop_reason` is `tool_use` and `response.content` contains at least one block of type `tool_use` whose `name` equals `submit_modifications` and whose `input` is a JSON object validated against the declared `input_schema`.
- Schema validation is enforced by Anthropic at the API boundary — malformed JSON cannot reach our code; the SDK raises `anthropic.BadRequestError`. This is free Pydantic-grade validation for shape.
- Our Python layer then only needs to validate *semantic* correctness (`strategy_id` membership in the input strategies set), not shape.
- The LLM cannot emit a second call in the same request cycle — we process only the first `tool_use` block and never re-issue the request. This breaks the "LLM controls the loop" property at the root.

**Alternatives considered**:

| Alternative | Why rejected |
|---|---|
| Prose / fenced JSON extraction | Fragile: markdown fences, hallucinated keys, prose preamble. Requires hand-rolled schema validator. Strictly worse than forced tool call. |
| Multi-call loop with `disable_parallel_tool_use` | Keeps LLM in the control-flow loop — the exact property we're eliminating. |
| Streaming API with multi-call loop | Addresses only the secondary "streaming required" symptom; doesn't fix double-counting. |
| Two-tool design ("plan" + "finalise") | Reintroduces multi-call semantics with no correctness benefit. |

---

## R2 — Token budget for the single forced call

**Decision**: `MAX_TOKENS = 12_000` on the modeller's single Anthropic call.

**Rationale**:
- Output payload is one JSON object with up to 8 modification entries. Per-entry token estimate: ~300-600 (title + description + 3-5 assumptions + modifiers + category + risk rating + compliance notes). Upper bound: 8 × 600 = ~4,800 tokens for the modifications array.
- 12,000 provides ~7,000 tokens of headroom for Claude's reasoning text plus the tool-call framing.
- 12,000 stays well below the Anthropic-enforced synchronous-response threshold that 32,000 crossed (triggering the "Streaming is required for operations that may take longer than 10 minutes" rejection observed in logs 2026-04-18).
- Consistent with Spec 059 convention: advisor uses 64k (with multi-paragraph output), scanner 16k, profiler 8k. The modeller's structured-output shape justifies a figure between scanner and advisor.

**Alternatives considered**:

| Alternative | Why rejected |
|---|---|
| 8,000 | Too tight — verbose compliance notes across 8 strategies could truncate. |
| 16,000 | Works, but closer to the streaming threshold. 12k has more margin and handles worst-case output comfortably. |
| Dynamic budget = `base + 800 × len(input_strategies)` | Premature optimisation. Input strategy count is capped at 8 upstream. |

---

## R3 — Tool input schema shape

**Decision**: `SUBMIT_MODIFICATIONS_TOOL` exposes one top-level property `modifications` (array). Each entry mirrors the existing `CALCULATE_TAX_TOOL` per-call schema plus a mandatory `strategy_id` referencing an input strategy.

**Rationale**:
- Keeping per-entry fields identical to `CALCULATE_TAX_TOOL` means `_execute_tool`'s current body (Spec 059 provenance, group-model gate, enum coercion — all of which are correct) can be reused for each modification with minimal adaptation.
- Anthropic's JSONSchema validation at the API boundary guarantees shape conformance. No need for additional Pydantic validation in Python — that would be redundant belt-and-braces.
- One top-level `modifications` array (vs a flat object with N positional fields) gives the LLM a natural "list" abstraction that matches the task.

**Contract file**: `contracts/submit_modifications_tool.json`

**Alternatives considered**:

| Alternative | Why rejected |
|---|---|
| Pydantic model re-validation in Python | Redundant — API boundary already validates shape. Adds complexity for no correctness gain. |
| Per-strategy positional fields (`modification_1`, `modification_2`, …) | Rigid, non-extensible, awkward. Array is the right primitive. |

---

## R4 — `strategy_id` addressing convention

**Decision**: Input strategies already carry an `id` field (set by the scanner). The modifications payload references this `id` verbatim via the `strategy_id` field. Python validates with a `set` membership check against `{s["id"] for s in input_strategies}`.

**Implementation note**: the current modeller computes `strategy_id` as `scenario_title.lower().replace(" ", "-")` (a slug of an LLM-chosen title, line 318 of `modeller.py`). This must change: the scenario's `strategy_id` is now taken from the *validated modification's* `strategy_id` field, which by construction equals an input strategy's `id`. This closes the loop between scanner output IDs, modeller input IDs, and persisted scenario IDs.

**Rationale**:
- Scanner IDs are deterministic, stable, and human-readable (`prepay-deductible-expenses`, `carry-forward-concessional-cap`, etc.).
- String IDs are durable in logs and debugging.
- Set membership is O(1) and trivially unit-testable.

**Alternatives considered**:

| Alternative | Why rejected |
|---|---|
| Fuzzy / semantic match of titles to input strategies | Non-deterministic, reintroduces ambiguity, defeats "code is law". |
| Integer index addressing | More error-prone (off-by-one, reordering). Opaque in logs. |
| Keep slug-of-title as before | Meta-scenarios would get a unique slug and pass through — defeats the core guarantee. |

---

## R5 — Extract `_execute_tool` to pure `_compute_scenario`

**Decision**: Rename and lift `_execute_tool(tool_input, base_financials, entity_type, rate_configs)` out of the class to a module-level pure function `_compute_scenario(modification, base_financials, entity_type, rate_configs) -> dict`. Body is unchanged — it carries the correct Spec 059 behaviour and must not regress.

**Rationale**:
- The term "tool" no longer fits — there is no iterative tool-use loop in the redesign.
- Pure function is independently testable without mocking the Anthropic client.
- Forces the behaviour to be callable from the iteration loop in `run()` and from unit tests symmetrically.

**Alternatives considered**:

| Alternative | Why rejected |
|---|---|
| Keep as method with same name | Misleading name, ongoing confusion. |
| Inline into the iteration loop in `run()` | Harder to unit-test in isolation. |

---

## R6 — Test strategy for redesigned modeller

**Decision**: Five unit tests in `backend/tests/modules/tax_planning/agents/test_modeller.py`, all using `AsyncMock` for the Anthropic client:

1. `test_drops_unknown_strategy_id` — stub returns a modification with `strategy_id="hallucinated-meta"` not in the input; assert it's absent from returned scenarios.
2. `test_dedupes_duplicate_strategy_ids` — stub returns two modifications with the same `strategy_id`; assert only the first survives.
3. `test_truncates_to_input_count` — stub returns N+1 modifications for N input strategies; assert `len(scenarios) ≤ N`.
4. `test_combined_total_equals_sum_of_scenarios` — stub returns 3 valid modifications with known savings; assert `combined["total_tax_saving"]` equals arithmetic sum (within 2dp rounding).
5. `test_group_model_scenario_excluded_from_combined` — modification tagged with a group-model category yields `tax_saving=0` and is excluded from `combined.total_tax_saving` (regression coverage for Spec 059 FR-019).

**Deletions**: any existing test asserting behaviour of the three removed filter layers (e.g., `test_name_filter_strips_combined`, `test_structural_filter_strips_meta`, `test_hard_cap_rejects_extra_call`) is deleted. Their assertions are moot — the paths are gone.

**Rationale**: each test exercises exactly one structural guarantee, runs in <100ms (mocked client), and fails with a clear diagnostic. CI signal is strong.

---

## Open questions

None. All decisions resolved. Proceeding to Phase 1 design.
