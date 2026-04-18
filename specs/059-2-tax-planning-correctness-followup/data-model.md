# Phase 1 Data Model: Modeller Redesign

**Feature**: Tax Planning Modeller — Architectural Redesign
**Date**: 2026-04-18
**Scope**: Internal data shapes only. No database entities, no persisted schema changes, no API contract changes.

---

## Overview

The modeller's redesign changes the *control flow* between the language model and the tax calculator, not the data shapes it persists. Of the three entity types below:

- **ScenarioModification** is new — the forced-tool-call payload. Exists in-memory only, never persisted.
- **Scenario** is unchanged from Spec 059 — the per-strategy result after the calculator runs.
- **CombinedStrategy** is unchanged from Spec 059 — the aggregate summary.

All downstream consumers (advisor, reviewer, orchestrator, API router, frontend) see identical data. The only consumer of `ScenarioModification` is the modeller's own iteration loop.

---

## Entity 1: ScenarioModification (new, ephemeral)

**Source**: Forced tool-call payload from Anthropic. One entry per input strategy (LLM may omit or duplicate; see validation rules).
**Lifetime**: In-memory inside `modeller.run()`. Never written to disk.
**Validated by**: Anthropic API against `input_schema` (shape), then Python (`strategy_id` membership, dedupe, truncation).

| Field | Type | Required | Constraints | Notes |
|-------|------|----------|-------------|-------|
| `strategy_id` | str | ✅ | Must match one of the input strategies' `id` — else dropped | Addressing key. Verbatim scanner output. |
| `scenario_title` | str | ✅ | — | Human-readable label rendered in the UI and PDF. |
| `description` | str | ✅ | — | One-paragraph prose for the accountant brief. |
| `assumptions` | list[str] | optional | — | Bullet items shown in the scenario card. Default: `[]`. |
| `modified_income` | object | ✅ | At least one of `revenue`, `other_income` (enforced by LLM behaviour; absent keys fall back to base financials) | Diff against base — partial overrides. |
| `modified_income.revenue` | number | optional | ≥ 0 | |
| `modified_income.other_income` | number | optional | ≥ 0 | |
| `modified_expenses` | object | ✅ | At least one of `cost_of_sales`, `operating_expenses` | Diff against base — partial overrides. |
| `modified_expenses.cost_of_sales` | number | optional | ≥ 0 | |
| `modified_expenses.operating_expenses` | number | optional | ≥ 0 | |
| `modified_turnover` | number \| null | optional | ≥ 0 | Defaults to base turnover when absent. |
| `strategy_category` | str | optional | Coerced to `StrategyCategory` enum; falls back to `OTHER` on invalid | Drives `requires_group_model` gate. |
| `risk_rating` | str | optional | `"conservative"` \| `"moderate"` \| `"aggressive"`; falls back to `"moderate"` on invalid | |
| `compliance_notes` | str | optional | — | Rendered under the scenario card. |

### Validation rules (Python layer)

Applied in `modeller.run()` immediately after extracting the `modifications` list from the tool-use block:

1. **Unknown `strategy_id` → drop.**
   ```python
   input_ids = {s["id"] for s in input_strategies}
   if mod["strategy_id"] not in input_ids:
       logger.info("Modeller: dropping unknown strategy_id=%r", mod["strategy_id"])
       continue
   ```

2. **Duplicate `strategy_id` → dedupe (keep first).**
   ```python
   seen: set[str] = set()
   if mod["strategy_id"] in seen:
       logger.info("Modeller: dropping duplicate strategy_id=%r", mod["strategy_id"])
       continue
   seen.add(mod["strategy_id"])
   ```

3. **Count exceeds input → truncate** (defence-in-depth; dedupe alone bounds this).
   ```python
   validated_mods = validated_mods[: len(input_strategies)]
   ```

4. **Zero valid modifications → log and return empty.** Analysis status stays `succeeded`; UI shows "0 Strategies Modelled".
   ```python
   if not validated_mods:
       logger.warning("Modeller: no valid modifications returned; producing empty scenario list")
       return [], _build_combined_strategy([])
   ```

---

## Entity 2: Scenario (unchanged from Spec 059)

**Source**: Output of `_compute_scenario(modification, base_financials, entity_type, rate_configs)`.
**Lifetime**: In-memory inside `modeller.run()`, then returned to orchestrator, then persisted as `TaxPlanAnalysis.recommended_scenarios` (JSONB).
**Validated by**: `_compute_scenario` internal logic (Spec 059 provenance, enum coercion, group-model gate).

| Field | Type | Notes |
|-------|------|-------|
| `scenario_title` | str | Verbatim from modification. |
| `description` | str | Verbatim from modification. |
| `assumptions` | `{"items": list[str]}` | Wrapped for UI. |
| `strategy_id` | str | **CHANGE**: now the validated modification's `strategy_id` (not slug of title). Closes the scanner→modeller→scenario ID loop. |
| `strategy_category` | str | `StrategyCategory.value` after coercion. |
| `risk_rating` | str | Validated enum. |
| `requires_group_model` | bool | Derived from `strategy_category` via `strategy_category.requires_group_model()`. |
| `impact.before` | `{taxable_income, tax_payable}` | From `calculate_tax_position(base_financials)`. Provenance: `derived`. |
| `impact.after` | `{taxable_income, tax_payable}` | From `calculate_tax_position(modified_financials)`, OR `= impact.before` when `requires_group_model=True` (Spec 059 F-02 gate). Provenance: `estimated`. |
| `impact.change` | `{taxable_income_change, tax_saving}` | Difference. `tax_saving = 0` when `requires_group_model=True`. Provenance: `estimated`. |
| `cash_flow_impact` | float | `tax_saving - max(0, expense_increase)`. Provenance: `estimated`. |
| `source_tags` | `dict[str, str]` | Full tag map from Spec 059 FR-011..FR-016. Preserved verbatim. |
| `compliance_notes` | str | Verbatim from modification. |

### State transition

None. Scenario is immutable once computed.

### Persistence path

`modeller.run()` → `orchestrator.run()` → `analysis_repo.update(analysis, {"recommended_scenarios": scenarios})` → JSONB column. No schema change.

---

## Entity 3: CombinedStrategy (unchanged from Spec 059)

**Source**: Output of `_build_combined_strategy(scenarios)`.
**Lifetime**: Returned alongside scenarios; persisted as `TaxPlanAnalysis.combined_strategy` (JSONB).

| Field | Type | Derivation |
|-------|------|------------|
| `recommended_combination` | list[str] | `[s["strategy_id"] for s in included]` |
| `total_tax_saving` | float | `round(sum(s["impact"]["change"]["tax_saving"] for s in included), 2)` |
| `total_cash_outlay` | float | `-total_cash` when `total_cash < 0`, else `0` |
| `net_cash_benefit` | float | `round(sum(s["cash_flow_impact"] for s in included), 2)` |
| `strategy_count` | int | `len(included)` |
| `excluded_count` | int | `len(real_scenarios) - len(included)` |

Where:
- `real_scenarios = scenarios` (because this redesign makes filtering moot — the list reaching `_build_combined_strategy` has *no* meta-scenarios by construction)
- `included = [s for s in real_scenarios if not s["requires_group_model"] and s["impact"]["change"]["tax_saving"] > 0]`

### Changes from the current code

The current `_build_combined_strategy` (modeller.py:324-371) applies a duplicate `_META_KEYWORDS` name filter internally before computing `included`. This filter is **deleted** — it's dead code in the redesigned flow because meta-scenarios can no longer reach this function. Net diff: `real_scenarios = scenarios` (pass-through; the defensive name re-filter and its helper `_is_meta_scenario` are both removed).

### Contract

This shape is consumed by:
- `advisor._build_brief_header` (reads `total_tax_saving`, `strategy_count`)
- `advisor._build_summary_header` (reads `total_tax_saving`)
- `reviewer` (reads `total_tax_saving` into `verified_total`)
- Frontend `TaxPlanningWorkspace.tsx:946` (reads `total_tax_saving` for the headline)
- PDF export template (reads the whole object)

None of these consumers changes. The shape contract is preserved.

---

## Data-flow diagram (redesigned)

```
INPUT                                                    OUTPUT
─────                                                    ──────

strategies        ┌─────────────────────────────┐
(up to 8,    ───▶ │  modeller.run()             │
from scanner)     │                             │
                  │  1. Build user prompt       │
                  │  2. client.messages.create( │
                  │       tool_choice=          │
                  │       "submit_modifications"│
                  │     )                       │
financials    ───▶│  3. Extract tool_use block  │
                  │  4. Validate modifications: │ ───┐
entity_type   ───▶│     - drop unknown ids      │    │  (3) diagnostic log
                  │     - dedupe by id          │    │      lines on every
rate_configs  ───▶│     - truncate to input N   │    │      drop/dedupe
                  │  5. For each validated mod: │    │
                  │       _compute_scenario(...)│    │
                  │  6. _build_combined_strategy│    │
                  │                             │    ▼
                  └──────────────┬──────────────┘
                                 │
                                 ▼
                    (scenarios, combined)  ──▶  orchestrator persists
                                                to TaxPlanAnalysis
```

**Key property**: scenario count is bounded by `len(input_strategies)` at step 4. The LLM cannot add a scenario with no matching `strategy_id`. This is what makes meta-scenarios structurally impossible.

---

## Diagnostic logging (FR-009)

The modeller emits `INFO`-level log lines at these decision points:

| Event | Log message | Purpose |
|-------|-------------|---------|
| Drop unknown strategy_id | `Modeller: dropping unknown strategy_id=%r` | Visibility into LLM attempts to invent strategies |
| Dedupe duplicate strategy_id | `Modeller: dropping duplicate strategy_id=%r` | Visibility into LLM repetition |
| Truncate | `Modeller: truncating from %d to %d modifications` | Visibility into over-production (rare) |
| Zero valid modifications | `Modeller: no valid modifications returned; producing empty scenario list` | Visibility into total LLM failure (rare) |
| Completion (replaces current log) | `Modeller: produced %d scenarios (from %d validated modifications), combined saving=$%s` | Per-run summary; replaces the current "produced N scenarios" line |

These are engineering-observability logs, not tenant-visible audit events. Standard app-log retention applies.

---

## Summary

- One new ephemeral shape (`ScenarioModification`) — lives only in modeller RAM.
- Two existing persisted shapes (`Scenario`, `CombinedStrategy`) — unchanged.
- One field semantic change: `Scenario.strategy_id` is now the validated modification's ID (not a slug of the title). Code is simpler; consumers unaffected.
- Zero database schema changes. Zero API contract changes. Zero frontend changes.
