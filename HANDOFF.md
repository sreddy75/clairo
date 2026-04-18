# Clairo Handoff Document

---

## Active Problem: Meta-Scenario Double-Counting in Tax Planning Modeller

**Status**: Partially mitigated, not solved. Needs a rethink.
**Branch**: `059-2-tax-planning-correctness-followup`
**Recommended next model**: Claude Opus 4.7 — the problem requires reasoning about LLM behaviour patterns, not just code fixes.

---

### What the problem is

The multi-agent tax planning pipeline (Spec 041/059) includes a **Scenario Modeller** agent (`backend/app/modules/tax_planning/agents/modeller.py`). It is given up to 8 tax strategies and told to call the `calculate_tax_position` tool once per strategy to compute exact before/after tax figures.

Despite explicit prompt instructions not to, Claude **reliably creates an additional "combined" or "meta" scenario** — a final tool call that models all strategies together simultaneously. This meta-scenario's `tax_saving` equals approximately the combined savings of all individual strategies. When it enters `recommended_scenarios` and then `_build_combined_strategy` sums every scenario's savings, the meta-scenario's figure is added on top of the individual strategy totals, **doubling the reported tax saving**.

The reviewer agent then flags the inflated combined total as a quality failure, causing the UI to show "Needs Review" on every analysis run.

---

### What has been tried (all failed)

Every fix so far treats symptoms. None addresses the root cause (the LLM's behaviour pattern).

| Attempt | What was tried | Why it failed |
|---------|---------------|---------------|
| 1 | Prompt instruction: "do not call the tool for a combined scenario" | LLM ignored it |
| 2 | Prompt: stronger wording with ⚠️ warning | LLM ignored it |
| 3 | Name filter in `_build_combined_strategy`: strip scenarios whose title contains `("combination", "package", "combined", "optimal strategy", "best strategy")` | LLM named it "Integrated Tax Minimisation Strategy" or similar — not caught |
| 4 | Name filter moved to `modeller.run()` before return (earlier in the pipeline) | Same LLM evasion — different name each run |
| 5 | Hard cap: reject tool calls beyond `len(top_strategies)` with an API error result | **May work** if the meta-scenario is always the N+1th call, but fails if LLM reorders and calls meta-scenario within the cap |
| 6 | Structural detection: strip any scenario whose `tax_saving > 1.1 × sum_of_others` | Mathematically sound but the 1.1× threshold may still miss or falsely trigger in edge cases |

Fixes 5 and 6 are both live in the current codebase (`6997fb8`). They have not yet been verified to work end-to-end.

---

### Why prompt instructions alone will never work here

This is the "prompts are suggestions, code is law" principle from CLAUDE.md. The LLM's behaviour pattern is deeply ingrained — combining strategies at the end is a natural summarisation behaviour. No phrasing has suppressed it consistently across multiple runs. The solution must be purely structural.

---

### The core architectural question

**Should the modeller be using tool-use at all?**

The current design gives Claude free rein over how many tool calls to make. The tool-use loop continues as long as `stop_reason == "tool_use"`, meaning Claude decides when to stop. This is the design that permits the meta-scenario.

An alternative design: **remove tool-use from the modeller entirely**. Instead:

1. The modeller returns structured JSON describing *what changes to make to financials* (e.g., "add $25,000 to operating_expenses") without calling the calculator.
2. The orchestrator iterates over each strategy's JSON and calls `calculate_tax_position` directly in Python, one call per strategy — no LLM involvement in the loop.
3. The LLM cannot create extra scenarios because it never controls the tool-use loop.

This separates concerns cleanly: **LLM decides what modifications to model; Python decides how many calculations to run.**

---

### Relevant files

| File | Role |
|------|------|
| `backend/app/modules/tax_planning/agents/modeller.py` | The broken agent — tool-use loop + three-layer filter |
| `backend/app/modules/tax_planning/agents/orchestrator.py` | Pipeline orchestrator — calls `modeller.run()`, stores `scenarios` and `combined` |
| `backend/app/modules/tax_planning/agents/reviewer.py` | Quality reviewer — flags combined total mismatch |
| `backend/app/modules/tax_planning/prompts.py` | `CALCULATE_TAX_TOOL` tool schema used by the modeller |
| `backend/app/modules/tax_planning/tax_calculator.py` | Pure Python calculator — `calculate_tax_position()` |

---

### Key data structures

The modeller's `_execute_tool` returns a scenario dict:
```python
{
    "scenario_title": "...",
    "strategy_id": "...",          # slug of scenario_title
    "impact": {
        "before": {"taxable_income": ..., "tax_payable": ...},
        "after":  {"taxable_income": ..., "tax_payable": ...},
        "change": {"taxable_income_change": ..., "tax_saving": 1234.56},
    },
    "cash_flow_impact": ...,
    "requires_group_model": bool,  # True → tax_saving forced to $0 (F-02)
    "strategy_category": "...",    # StrategyCategory enum value
    "risk_rating": "...",          # conservative | moderate | aggressive
    "source_tags": {...},
}
```

`_build_combined_strategy` sums `impact.change.tax_saving` for all scenarios where `requires_group_model=False` and `tax_saving > 0`. The meta-scenario (if not stripped) is always included here because it has `requires_group_model=False` and a large positive saving.

---

### Suggested approach for the new session

1. **Verify whether fixes 5+6 actually solved it** — run the analysis and check the logs for "Modeller: rejecting tool call" or "structural-filter stripped". If yes, close the issue. If no, proceed.

2. **If not solved**: consider the architectural redesign:
   - Change `CALCULATE_TAX_TOOL` to just be a structured output schema (no tool call) — the modeller returns a list of `{strategy_id, modified_income, modified_expenses, modified_turnover, assumptions, ...}` objects as JSON.
   - The orchestrator loops over these and calls `calculate_tax_position` in Python for each.
   - The modeller prompt becomes: "For each strategy, output a JSON array of modification objects."

3. **If redesign is out of scope**: add a deduplication step — after all filters, if two scenarios have `tax_saving` values that sum to within 5% of a third scenario's `tax_saving`, the third is almost certainly a meta-scenario and should be stripped.

---

### Spec 059 stories remaining

After the meta-scenario problem is resolved, these stories still need verification:

- **Story 6**: Citation verification / semantic similarity threshold (the `semantic=0` bug)
- **Story 7**: No "pre-Stage-3" rate language in documents
- **Story 8**: Duplicate scenario titles don't accumulate (upsert logic)

---

### Recent commits on this branch

```
6997fb8  fix(059): three-layer meta-scenario elimination in modeller
d3c2f70  fix(059): eliminate reviewer false positives and float precision
e16a58e  fix(059): harden LLM output across all tax planning agents
19b51fc  fix(tax-planning): double-counting, rounding, provenance, review UX
```
