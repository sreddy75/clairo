# Brief: Chat-Flow Scenario Deduplication (Tax Planning)

**Date**: 2026-04-18
**Source**: Spec 059 Story 8, rescoped after 059-2 architectural redesign
**Author**: Suren + codebase confirmation of `backend/app/modules/tax_planning/agent.py`
**Related**: Narrows the original "Story 8 — Duplicate scenarios accumulating across chat turns" scope. The analysis-pipeline side of the problem is resolved by the 059-2 modeller redesign (validated strategy_id dedupe in code). This brief covers the remaining chat-flow side only.

---

## Problem Statement

When the accountant uses the **tax planning chatbot** to refine an existing scenario, Claude's tool-use loop often emits a slightly-renamed scenario rather than updating the existing one. Examples seen in UAT:

- "Prepay Rent" → "Prepay Rent - Updated"
- "Super Contribution" → "Super Contribution (Maximum Cap)"
- "Trust Distribution" → "Trust Distribution v2"

The persistence layer at `agent.py:1528` and `agent.py:1709` uses `TaxScenarioRepository.upsert_by_normalized_title` to dedupe, but normalisation is string-level: titles that differ by more than case/whitespace normalise to distinct keys, so both get persisted and both appear in the Scenarios tab — cluttering the UI and making it unclear which row is "the current" version of a strategy.

This is the **same class of LLM-behaviour problem** that 059-2 solved for the multi-agent analysis pipeline: the LLM controls what gets persisted, and no amount of prompt tuning will consistently prevent the drift. The fix is the same shape: **add a code-layer guard that forces deduplication by strategy semantics, not by string-normalised title.**

### What is NOT broken

- The multi-agent analysis pipeline (`orchestrator.py` → `modeller.py`). After 059-2, the modeller dedupes by `strategy_id` in code — duplicates are structurally impossible in that flow.
- Scenario creation in principle — upsert works when the LLM uses identical titles across turns.

### What IS still broken

Only the chat flow (`backend/app/modules/tax_planning/agent.py` — the legacy single-agent `TaxPlanningAgent`). Every tool call from that loop creates or upserts a scenario row; title drift creates duplicate rows.

---

## Users

- **Primary**: Accountants using the tax planning chat to refine scenarios during a client session.
- **Observable pain**: Scenarios tab shows multiple rows for what is conceptually one scenario. Client summary PDF may double-count or reference stale variants.

---

## Identified Options (not prescriptive)

### Option A — LLM-assisted dedupe

Add a tool-call-time pre-check: before upserting, compare the proposed scenario's content (category + top modifications) against existing scenarios on the plan. If the match score exceeds a threshold, treat as an update on the existing row. Uses the existing scenarios-already-in-plan context.

**Risk**: inherits the same "LLM-behaviour pattern" fragility. Threshold tuning is an endless battle.

### Option B — Strategy-ID addressing (parallel to 059-2)

Require the chatbot's tool schema to take a `strategy_id` that must match either (a) an existing scenario on the plan, or (b) a stable ID from a fixed catalogue of strategy types. "Update existing" vs "create new" is resolved structurally by whether the ID already exists on the plan. No string normalisation required.

**Risk**: requires prompt rewrite so Claude understands the ID semantics. Mirrors 059-2 pattern so well-trodden.

### Option C — UI-layer cleanup ("Merge scenarios")

Leave the data model as-is; add a UI affordance to merge duplicate scenarios. Cheap but passes the problem to the accountant.

**Risk**: accountants don't want to fix the AI's mess — they want the AI to not make a mess. Treats a symptom, not the cause.

### Recommended: Option B

Matches the principle already validated by 059-2 — LLM proposes, code disposes. Smallest cross-cutting change consistent with the rest of the architecture.

---

## Success Criteria (direction only — finalise in a full spec)

- **SC-A**: In a chat session, asking the AI to refine an existing scenario by any wording ("update the prepay rent scenario to $30k", "change my super contribution to max cap", "revise trust distribution") MUST update the existing row, not create a new one.
- **SC-B**: Creating a genuinely new scenario type MUST create a new row.
- **SC-C**: Scenarios tab never shows two rows that correspond to the same strategy type on the same tax plan — verifiable by invariant check in data-integrity tests.

---

## Out of Scope

- Analysis-pipeline scenarios (fixed by 059-2).
- Scenario versioning / history ("I want to see what this scenario looked like 3 turns ago"). Separate concern.
- Cross-plan dedupe (scenarios for different clients/plans are expected to share IDs — this brief is per-plan only).
- Migrating existing duplicate rows in production DB. A backfill would be a separate task post-spec.

---

## Open Questions

1. Is there already a canonical catalogue of strategy types (beyond the `StrategyCategory` enum)? The modeller uses category+title; the chat flow may need finer-grained IDs.
2. Does the chat flow already have access to "scenarios already on this plan" in its prompt context? If yes, Option A might be cheaper than it looks. If no, Option B is clearly cheaper.
3. How should the UI distinguish "updated in this turn" vs "untouched this turn"? Post-update visual cue (e.g., timestamp or badge) probably useful, but not part of this spec's core scope.

---

## Priority

- **After Citation Substantive Validation** (2026-04-18-citation-substantive-validation.md) — citation quality is more frequently user-visible and more directly affects professional-liability risk.
- **Before** any work on scenario history/versioning — dedupe semantics underpin history, not the other way round.

This brief is ready to promote to a spec when the team picks it up. Estimated 2-3 day implementation once specced (prompt rewrite + tool schema + repository change + tests).
