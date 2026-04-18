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

## Spec 059 stories remaining

After this meta-scenario resolution, these stories from the original Spec 059 still need attention:

- **Story 6**: Citation verification / semantic similarity threshold (the `semantic=0` bug) — surfaced again during 059-2 UAT: the reviewer flagged "TR 2012/8" as possibly fabricated and cited prepayment provisions as ITAA 1997 when they are ITAA 1936. This is the citation verifier's job.
- **Story 7**: No "pre-Stage-3" rate language in documents
- **Story 8**: Duplicate scenario titles don't accumulate (upsert logic)

Also noted during 059-2 UAT but out of scope: an unresolved interaction between the Instant Asset Write-Off and SBE Simplified Depreciation Pooling scenarios — they both assume SBE regime election but don't cross-reference. This is a substantive strategy-design concern, not an arithmetic one. Candidate for a future strategy-consistency spec.
