# Brief: Tax Planning — Calculation Correctness Audit

**Date**: 2026-04-18
**Source**: Unni's alpha feedback after first live client session (Zac & Angela Phillpott / OreScope Surveying), synthesised in `docs/beta launch/...` and `/Users/suren/Documents/Claude/Projects/Clairo/tax-planning-alpha-feedback-synthesis.md`
**Author**: Suren (product) + code review of `backend/app/modules/tax_planning/*`
**Related**: Split scope from a larger UX rethink — this brief covers **data accuracy only**. The multi-entity/group tax model is in a separate brief (`2026-04-18-tax-planning-group-tax-model.md`).

**Status**: Converted — see `specs/059-tax-planning-calculation-correctness/spec.md`

---

## Problem Statement

Unni ran Clairo live against a real client and the tax planning feature produced several materially wrong numbers. Investigation shows this is **not a bag of nine independent bugs** — it's a single correctness failure: the system has **no ground-truth contract** between input data, calculation engine, AI agents, and UI. Tax is calculated on YTD actuals while the LLM is shown both YTD and projected figures. Scenarios fabricate baseline assumptions (e.g. "$25k prepaid rent") that never came from the accountant. The "reviewer" agent rubber-stamps results by re-running the same broken calculation path. Citation verification is a brittle substring match with a dict-key typo that collapses it to a near-zero threshold.

None of the existing unit tests catch any of this because they only exercise the pure calculator in isolation — the bugs all live in the wiring above it (ingest → projection → prompt → tool call → scenario persistence → analysis endpoint).

**Unni's tolerance for wrong numbers in front of a paying client is zero — and should be.** Until this is fixed, we cannot run another live session.

---

## Users

- **Primary**: Accountants using Clairo's tax planning feature in front of their business-owner clients (Unni, Vik, beta cohort)
- **Secondary**: Business-owner clients who will eventually see a client-facing summary of recommendations
- **Context**: Real-time advisory sessions where every number is read aloud and trusted. Single wrong number destroys credibility.

---

## Confirmed Bugs (all P0 — block any further live session)

### Bug 1 (F1-3) — Tax calculated on YTD actuals, not projected FY
**Root cause**: `service.py:722` passes `plan.financials_data` (YTD) to `calculate_tax_position`. Projection IS computed at `service.py:229-244` but stored in a sibling key `financials_data["projection"]` which `derive_taxable_income` (`tax_calculator.py:311-332`) never reads. Flag `is_annualised=False` is set but nothing branches on it.
**Blast radius**: `tax_position`, every scenario's before/after via modeller, reviewer's "verification", PDF export, LLM system prompt (which also shows the projection in parallel — Claude is given contradictory numbers).
**Fix**: Single ingest-time annualisation path that rewrites `income.total_income` and `expenses.total_expenses` to projected FY values when `months_elapsed < 12`. Remove the sibling `projection` key. LLM prompt only ever sees one set of numbers.

### Bug 2 (F1-13) — Net Benefit is company-only, not group-level
**Scope note**: The structural fix (multi-entity data model + group-aware tool) belongs in the **Group Tax Model** brief. *This* brief carries the minimum behavioural fix: surface the single-entity limitation honestly. Stop labelling the single-entity saving "Net Benefit" (`agent.py:361`), rename it to `"entity_tax_saving"`, and block the UI from displaying a scenario whose strategy type is known to be multi-entity (director salary, trust distribution, dividend timing, spouse contribution) until the group model lands. Scenarios in those categories must be flagged `"requires_group_model": true` and rendered with a disabled state + explanation.

### Bug 3 (F1-7) — Pre-Stage 3 rates in prompts
**Root cause**: The calculator itself is clean (DB seed is correct Stage 3). But `backend/app/modules/agents/prompts.py:170, 181` contains example language with `"32.5%+"` fed to Claude verbatim. `tax_planning/prompts.py` does not explicitly ground Claude in current Stage 3 rates, so narrative explanations can drift.
**Fix**: Remove `"32.5%"` strings from all prompts. Add a grounded rate block to `TAX_PLANNING_SYSTEM_PROMPT` listing current FY brackets inline. Test factory value `0.325` in `tests/factories/tax_planning.py:34` updated to Stage 3. Unit test: string-assert none of the prompt modules contain `"32.5"` or `"$120,000"`.

### Bug 4 (F1-2) — Super YTD / PAYGW YTD $0, and PAYGW never becomes a credit
**Root cause**: Multiple failure modes:
- `service.py:386-437`: tax planning reads `XeroPayRun` rows but does not trigger a payroll sync. If sync has never run for this connection (or ran before `has_payroll_access` was set), the table is empty → `sum()==0`.
- `service.py:433-437`: both the `has_payroll_access=False` branch and the `except Exception` branch silently set `payroll_summary=None`, with only DEBUG-level logging.
- `service.py:492-496`: Xero transform **hardcodes `credits.payg_withholding = 0`**. Even when `payroll_summary.total_tax_withheld_ytd` is populated, it is never fed into `credits.payg_withholding`, so the calculator never subtracts PAYGW already remitted — inflating the "before" tax baseline for every scenario.
- Scanner prompt claims to evaluate super strategies "if payroll data is provided" (`prompts.py:70`) but the user_prompt never inlines payroll fields, so the scanner is blind to them regardless.
- `save_manual_financials` (`service.py:668-690`) wipes `payroll_summary`, `bank_balances`, `strategy_context`, `prior_years` whenever an accountant saves the manual-entry form.

**Fix**: Trigger payroll sync on demand when a tax plan is created for a connection with `has_payroll_access=True`. Wire `credits.payg_withholding ← payroll_summary.total_tax_withheld_ytd`. Raise silent swallows to WARNING + surface a "payroll data not available" banner in the UI. Preserve all non-accountant-editable fields through `save_manual_financials`. Inline payroll fields into scanner prompt.

### Bug 5 (F1-12) — Analysis tab uses LLM-invented figures
**Root cause**: `modeller._execute_tool` (`modeller.py:122-217`) accepts arbitrary `modified_expenses` and free-text `assumptions` from Claude (e.g. "Prepay $25,000 of rent") with no schema constraint relative to the confirmed baseline. No `confirmed_vs_estimated` field exists anywhere (`models.py`, `schemas.py`). Advisor dumps this JSON into markdown (`advisor.py:45-62`); Reviewer checks brief-vs-scenarios *internal* consistency (`reviewer.py:118-152`), not ground-truth consistency. Analysis endpoint (`router.py:539-599`) returns only AI-derived fields and does not include `financials_data` alongside.
**Fix**:
- Every numeric field in a scenario's `modified_expenses`, `modified_income`, `adjustments` must carry a `source` tag: `"confirmed"` (from `FinancialsInput`), `"derived"` (transformed from confirmed by a deterministic rule), or `"estimated"` (AI-generated, pending confirmation).
- Modeller tool schema tightened: `modified_expenses` must reference a `baseline_ref` from the confirmed financials; any novel line item must be declared explicitly with `"source": "estimated"`.
- Analysis tab endpoint includes `financials_data` so the UI can render confirmed-source-of-truth alongside AI narrative.
- UI renders `"estimated"` figures with a visible badge + tooltip. Accountant must explicitly confirm before a scenario is "recommended".

### Bug 6 (F1-14) — "Sources could not be verified" false alarms
**Root cause**: `_build_citation_verification` (`service.py:888-958`) is a two-way substring match between the `[Source: ...]` inner text and the top-5 retrieved chunks' `ruling_number`/`section_ref`/`title`. No fallback to chunk text body. Plus **a dict-key bug**: `service.py:1057` reads `c.get("score", 0.0)` but chunks use `"relevance_score"` (`service.py:870`), so `confidence_score` collapses to `0.3 * verification_rate` — any verification rate < ~0.83 flips to `low_confidence` and **the entire AI response is replaced with a canned decline message** while the UI shows a "General knowledge" badge (frontend enum doesn't know `low_confidence`, `types/tax-planning.ts:183`). There is a more sophisticated verifier at `knowledge/retrieval/citation_verifier.py` that is unused.
**Fix**:
- Fix the `"score"` → `"relevance_score"` key mismatch (one-liner, should ship immediately as a hotfix).
- Replace `_build_citation_verification` with a call to `knowledge/retrieval/citation_verifier.py` which includes a chunk-text fallback.
- Add `"low_confidence"` to the frontend status enum; render a distinct badge.
- Streaming race: emit the verification event before `done`, or have the UI merge it on arrival (`ScenarioChat.tsx:179-194`).

### Bug 7 (F1-11) — Duplicate scenarios
**Root cause**: No `UniqueConstraint` on `TaxScenario`; no dedupe in `repository.create`; no "don't replay an existing scenario" instruction in the chat prompt. Most likely an accumulation pattern across chat turns, not single-call duplication.
**Fix**: Add `UniqueConstraint(tax_plan_id, normalized_title)` (where `normalized_title = lower(trim(title))`); convert `scenario_repo.create` to upsert semantics. Add explicit instruction to the chat system prompt: "Do not produce a scenario with a title substantially similar to an existing scenario in the conversation history — instead, reference and refine the existing one."

### Bug 8 (cross-cutting) — Reviewer agent is a rubber stamp
**Root cause**: `reviewer.py:129-134` verifies scenarios by re-running `calculate_tax_position` on the **same `base_financials`** the modeller used — so it returns `numbers_verified=True` whenever the modeller is self-consistent, even when modeller and reviewer are wrong in the same way.
**Fix**: Reviewer must compute an **independent ground truth** — re-derive taxable income from the raw `income.total_income`, `expenses.total_expenses`, `adjustments` straight from `financials_data` (not from a cached `base_financials`), compare against scenarios with tolerance, flag any disagreement loudly.

---

## Testing & Regression Strategy

**This is the load-bearing section of this brief.** The reason these bugs shipped is that the test pyramid was inverted: we had 500 lines of tight unit tests on `tax_calculator.py` (the one part that was *already correct*) and zero tests at the wiring layers where every actual bug lives.

### Test pyramid we need

```
                    ┌─────────────────────────┐
                    │   Golden-dataset E2E    │  ← 1-2 curated real clients
                    │   (Zac, Angela, …)      │     full pipeline assert
                    └─────────────────────────┘
                  ┌─────────────────────────────┐
                  │   Integration tests          │  ← ingest→calc→scenario→
                  │   (service + agents wired)   │     analysis, w/ fake LLM
                  └─────────────────────────────┘
              ┌───────────────────────────────────┐
              │   Contract tests (prompt + tool)   │  ← prompt strings, tool
              │   + schema invariants              │     schema, provenance
              └───────────────────────────────────┘
          ┌───────────────────────────────────────────┐
          │   Unit tests (tax_calculator.py pure fns)  │  ← exists today, keep
          └───────────────────────────────────────────┘
```

### New test suites to add

**1. Golden-dataset E2E (highest value, do first)**
- Fixture: Zac Phillpott's real inputs (sanitised) — financial year, entity type, income, expenses, credits, payroll summary, bank balance, prior-year state.
- Expected output fixture: the numbers Unni/ChangeGPS arrived at for the same inputs — `total_tax_payable`, `net_position`, `combined_strategy.total_tax_saving`, and for each recommended scenario the `entity_tax_saving` and key `assumptions`.
- Test runs the **full** pipeline: `pull_xero_financials` (with a fake Xero client returning the fixture data) → `calculate_tax_position` → analysis orchestrator → result. Asserts every number within $1.
- Rerun on every PR that touches `backend/app/modules/tax_planning/**` (CI gate).
- **Start with one client, add more as we find them.** Vik's clients next. Each locked-in client permanently protects against its failure mode.

**2. Integration tests for wiring**
- `test_pull_xero_financials_annualises_when_lt_12_months` — ingest at month 6, assert `income.total_income` is doubled (or whatever the rule is), not stashed in a sibling key.
- `test_payg_withholding_credit_wired_from_payroll_summary` — seed `XeroPayRun` rows, call `pull_xero_financials`, assert `credits.payg_withholding == total_tax_withheld_ytd`.
- `test_manual_financials_preserves_xero_context` — save manual financials, assert `payroll_summary` / `bank_balances` still present.
- `test_reviewer_catches_modeller_disagreement` — inject a modeller result with deliberately wrong `before.tax_payable`, assert reviewer returns `numbers_verified=False`.
- `test_scenario_dedupe` — persist two scenarios with normalised-identical titles, assert only one exists.
- `test_citation_verifier_matches_body_text` — citation references a chunk by section-ref paraphrase, assert `verified`.
- `test_confidence_score_uses_relevance_score_key` — mock chunks with `relevance_score`, assert `confidence_score > 0`.
- All run with a **fake Anthropic client** (deterministic responses keyed by prompt hash) so the tests are fast and stable.

**3. Contract / invariant tests**
- `test_prompts_contain_no_pre_stage_3_rates` — walk every `*.py` in `app/modules/tax_planning/` and `app/modules/agents/`, string-assert none of: `"32.5"`, `"19%"`, `"$120,000"`, `"$120k"`.
- `test_tax_planning_system_prompt_grounds_stage_3_rates` — assert `TAX_PLANNING_SYSTEM_PROMPT` contains the four current bracket thresholds.
- `test_calculate_tax_tool_schema_requires_provenance` — every numeric field in `CALCULATE_TAX_TOOL.inputs` carries a `source` enum.
- `test_scenario_response_has_source_tags` — every scenario emitted by the modeller has `source` tags on all numeric fields.

**4. LLM behavioural tests (lightweight, nightly not per-PR)**
- Run the actual chat flow against a small bank of scripted accountant questions (10-20), snapshot the response, assert no Stage-3-violating phrases, no citations that fail the verifier, no scenarios missing `source` tags. Budget: a few cents per run, runs nightly on main.

### What NOT to test
- Do not add more unit tests to `test_tax_calculator.py`. It's fine. The bugs aren't there.
- Do not mock the calculator in integration tests. Use the real calculator; only mock the LLM and Xero.
- Do not write snapshot tests of LLM output verbatim — they're brittle and will force constant updates. Assert on structured properties (field presence, source tags, numeric tolerance).

### Regression gate
Before any tax planning PR merges:
1. All unit + contract + integration tests pass (current CI gate, extended).
2. Golden dataset E2E passes within $1 tolerance.
3. Manual Stage 3 prompt-scan test passes.
4. `ruff check` + `mypy` green (current gate).

### Ongoing
- Any bug reported from a live session → reproduce in the golden-dataset fixture before fixing. No fix lands without a test that fails beforehand.
- Nightly LLM snapshot run; regressions open a ticket automatically (future — not in this brief's scope).

---

## Out of Scope (explicitly)

- **Multi-entity / group tax model** — covered by `2026-04-18-tax-planning-group-tax-model.md`. Bug 2 here only adds the "requires_group_model" honesty flag.
- **UX/UI rethink** — Unni's feedback Section 2 (Excel-style layout, waterfall display, per-entity scenario breakdown) is a separate design+build track. Nothing in this brief changes the UI beyond the provenance badge and the disabled-scenario state for multi-entity strategies.
- **Engagement thread** (pre-meeting brief, in-meeting notes, post-meeting follow-up) — Unni's feedback Section 3. Separate spec.
- **ATO integrations** (PAYG feed, carry-forward super) — Section 4. Separate spec / spike.
- **Non-Xero client ingest** — separate problem.

---

## Success Criteria

1. Unni runs the same Zac dataset through Clairo and ChangeGPS side-by-side, and every number matches within $1.
2. Running a clean alpha session on a different client does not produce any of F1-2, F1-3, F1-7, F1-11, F1-12, F1-13, F1-14 symptoms.
3. Every scenario in the Scenarios tab and Analysis tab shows provenance (confirmed / derived / estimated) for every numeric field.
4. No pre-Stage-3 string exists in any prompt fed to Claude (enforced by test).
5. The golden-dataset E2E test exists, runs in CI, and fails loudly on any regression.
6. Unni says: "I can run this in front of a client without checking the numbers myself."

---

## Open Questions

1. **Golden-dataset source**: Do we have Zac's inputs and the ChangeGPS output numbers available in a form we can put in a test fixture today, or do we need Unni to re-supply them? Assumption: yes, from the alpha session notes.
2. **Annualisation rule**: Simple linear (monthly_avg × 12)? Seasonality-adjusted? Pro-rata to reconciliation date? Default to linear for alpha, flag for Unni to confirm.
3. **"Estimated" figure flow**: When the accountant "confirms" an AI-estimated assumption, where does that confirmation live — a new column on the scenario, a new table, or replay into `FinancialsInput`? Suggest: new `confirmed_assumptions` JSONB on `TaxScenario`, no schema migration needed beyond one column.
4. **Reviewer agent cost**: If the reviewer re-derives from raw inputs, it's effectively a second calculator pass — essentially free. But if Unni wants an LLM-based "does this make sense" layer on top, that's a separate design choice. Default: deterministic reviewer, no LLM.
5. **Prompt scan strictness**: Block on any occurrence of `"32.5"`, or allow in comments/docstrings? Default: block everywhere; explicitly whitelist the test file that asserts absence.
