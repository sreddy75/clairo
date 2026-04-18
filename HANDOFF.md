# Clairo Handoff Document

---

## Resolved: Meta-Scenario Double-Counting in Tax Planning Modeller

**Status**: **Resolved 2026-04-18** via `specs/059-2-tax-planning-correctness-followup/`.
**Branch**: `059-2-tax-planning-correctness-followup`
**Verification**: Live UAT run against KR8 IT (~370s) produced `$24,375` Total Tax Saving with the reviewer explicitly confirming "arithmetically consistent" — no doubling, no meta-scenarios.

### Resolution summary

The three-layer defensive filter approach (hard cap on tool calls, keyword name strip, structural `1.1×` ratio threshold) was abandoned in favour of an architectural redesign: the modeller no longer runs an LLM-controlled tool-use loop. It now makes a single forced tool call (`tool_choice={"type": "tool", "name": "submit_modifications"}`) returning a structured list of strategy modifications, which Python validates (unknown-ID drop, dedupe, truncation) and iterates calling the deterministic `calculate_tax_position` calculator once per validated entry.

Meta-scenarios are structurally impossible in the new design: any modification whose `strategy_id` is not present in the input strategy set is dropped at validation. The LLM has no mechanism to inject a scenario the calculator will execute.

A second, independent failure mode surfaced during verification: the advisor agent (`MAX_TOKENS=64_000`) was crossing Anthropic's "Streaming is required for operations that may take longer than 10 minutes" threshold. The advisor's single `messages.create()` call was converted to `messages.stream()` + `get_final_message()` — a transport-only change with no output-shape impact. Celery's `soft_time_limit` was raised from 240s→540s (hard 300s→600s) because the honest pipeline is legitimately longer than the pre-fix broken runs.

See `specs/059-2-tax-planning-correctness-followup/spec.md`, `plan.md`, `research.md`, and `tasks.md` for the full decision record.

### Key lesson for future sessions

The "prompts are suggestions, code is law" principle from CLAUDE.md is structural, not stylistic. Any rule that must hold deterministically must be enforced by a code-layer guard that does not depend on LLM behaviour. When a rule can only be enforced by filtering LLM output, the filter is fighting a losing adversarial game — the LLM will find an edge case. The right answer is usually to remove the LLM's ability to violate the rule in the first place, typically by inverting control (LLM proposes structured data, Python decides what to execute).

---

## Spec 059 stories — status after 059-2

Each of the three originally-open follow-up stories was re-evaluated against the post-059-2 codebase. Outcome:

### Story 6 — Citation verification: **implemented in 061-citation-validation**

The original `semantic=0` bug was already resolved under Spec 059.

The two new defects surfaced during 059-2 UAT — hallucinated-ruling verification + wrong-act-year misattribution — are resolved under Spec 061 (`specs/061-citation-validation/`). The verifier now requires metadata equality on `chunk.ruling_number` for rulings to earn the "verified" badge (body-text mentions are classified as weak matches), and a hand-curated ≥125-entry section→Act mapping enables wrong-act-year detection. A shared `_apply_subthreshold_gate` helper gives streaming and non-streaming chat paths identical sub-threshold treatment (Q2=C: preserve content, clear scenarios, warning banner).

Brief that drove the spec: `specs/briefs/2026-04-18-citation-substantive-validation.md` (kept for historical reference; spec is canonical).

### Story 7 — Pre-Stage-3 rate language: **verified resolved**

Full grep across `backend/app/modules/tax_planning/` for pre-Stage-3 threshold markers (`32.5%`, `$120,000`, `$120k`, `$180,000`) returns zero matches. The only hit for `37%` is the correct post-Stage-3 `$135,000–$190,000` bracket. The chat agent's `TAX_PLANNING_SYSTEM_PROMPT` already includes explicit Stage 3 brackets and disclaims "Pre-Stage-3 brackets are superseded and must not appear." No code change needed. Closed without ceremony.

### Story 8 — Duplicate scenario titles: **narrowed to chat-flow only**

The analysis-pipeline half of the problem is resolved by 059-2 — the modeller now dedupes by validated `strategy_id` in code, so duplicates are structurally impossible in that flow. The **chat flow** (`backend/app/modules/tax_planning/agent.py` — the legacy single-agent `TaxPlanningAgent`) is untouched by 059-2 and still exhibits the original drift pattern: LLM emits renamed scenarios ("Prepay Rent" → "Prepay Rent - Updated"), `upsert_by_normalized_title` fails to merge them, the Scenarios tab accumulates duplicates.

Captured as a focused brief: `specs/briefs/2026-04-18-chat-scenario-dedup.md`. Recommended approach: apply the same "structured ID addressing" pattern that solved 059-2 to the chat flow's tool schema. Ready to promote to a full spec.

### Non-Story followup surfaced during 059-2 UAT

An unresolved interaction between the Instant Asset Write-Off and SBE Simplified Depreciation Pooling scenarios — both assume SBE regime election but don't cross-reference. Substantive strategy-design concern, not arithmetic. Not yet brief'd; candidate for a future strategy-consistency spec if it recurs.

---

## Next-action priority

Based on the above, the user-visible impact order is:

1. ~~**Citation substantive validation**~~ — **resolved** in Spec 061. Requires ≥125-entry YAML mapping to be reviewed by a domain expert before the next UAT session; file header flags this.
2. **Chat-flow scenario dedup** (`specs/briefs/2026-04-18-chat-scenario-dedup.md`) — medium. UX annoyance; not a correctness bug, but clutters the Scenarios tab.
3. Strategy-consistency spec — monitor. No brief yet.
