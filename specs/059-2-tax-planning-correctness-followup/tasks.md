---
description: "Tasks for Tax Planning Modeller — Architectural Redesign (059-2)"
---

# Tasks: Tax Planning Modeller — Architectural Redesign

**Input**: Design documents from `specs/059-2-tax-planning-correctness-followup/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/submit_modifications_tool.json, quickstart.md

**Tests**: Included. Required by SC-005 and Constitution Principle V.

**Organization**: By user story. Stories 1–4 all land from the same core rewrite, so US1 contains the structural change and later stories layer only verification + additional tests on top.

## Format

`- [ ] [TaskID] [P?] [Story?] Description with file path`

- `[P]` = parallelisable (different files, no incomplete dependencies)
- `[USn]` = maps to User Story n in spec.md

## Path Conventions

Backend: `backend/app/modules/tax_planning/` and `backend/tests/modules/tax_planning/`. No frontend work.

---

## Phase 1: Setup

**Purpose**: Precondition checks; no new scaffolding needed.

- [x] T001 Confirm branch `059-2-tax-planning-correctness-followup` is checked out and clean (`git status` shows only `specs/059-2-tax-planning-correctness-followup/` tracked files plus `specs/briefs/2026-04-18-llm-output-hardening.md` + `frontend/public/tax-planning-wireframes.html` — both untracked and unrelated to this work)
- [x] T002 Re-read `HANDOFF.md` and `specs/059-2-tax-planning-correctness-followup/spec.md` to confirm the problem framing matches the current symptom before coding

---

## Phase 2: Foundational (Blocks all user stories)

**Purpose**: Add the new tool schema and system prompt constants that the rewrite consumes. These are pure additions — they do not delete or alter existing behaviour, so they are safe to land first even if the rewrite is paused.

- [x] T003 [P] Add `SUBMIT_MODIFICATIONS_TOOL` constant in `backend/app/modules/tax_planning/prompts.py` — Python `dict` literal matching `specs/059-2-tax-planning-correctness-followup/contracts/submit_modifications_tool.json` exactly. Keep existing `CALCULATE_TAX_TOOL` constant unchanged (still used by legacy `agent.py` chat flow).
- [x] T004 [P] Rewrite `MODELLER_SYSTEM_PROMPT` in `backend/app/modules/tax_planning/agents/prompts.py` to instruct the model to: (a) call `submit_modifications` exactly once with the full list, (b) use `strategy_id` values verbatim from input strategies, (c) omit strategies not worth modelling (no empty placeholders), (d) NOT include any combined/package/integrated/optimal meta-scenario entry. Remove all language referring to a multi-round tool-use loop.

**Checkpoint**: After T003–T004, both constants exist. Nothing else has changed yet — pipeline still runs the old code path.

---

## Phase 3: User Story 1 — Correct Total Tax Saving headline (Priority: P1) — MVP

**Story goal**: Accountant sees a correct, single-sourced Total Tax Saving figure equal to the exact sum of individual scenario savings. No meta-scenarios possible by construction.

**Independent test**: Golden-dataset run — `combined_strategy.total_tax_saving` equals arithmetic sum of individual `tax_saving` values (within 2dp rounding). No scenario with `strategy_id` absent from input strategies.

This phase contains the **core code change**. Stories 2–4 are verification layers on top.

### Tests (TDD — write before implementation)

- [x] T005 [US1] In `backend/tests/unit/modules/tax_planning/test_modeller.py` (repo convention path — differs from plan.md), add `test_combined_total_equals_sum_of_scenarios` — stub `AsyncAnthropic` to return a single tool-use block with three valid modifications whose computed savings are known ($5k, $3k, $4k); assert `combined["total_tax_saving"] == 12000.0` within 2dp. Satisfies FR-004, SC-001.
- [x] T006 [US1] In same file, add `test_group_model_scenario_excluded_from_combined` — stub returns one modification with a group-model `strategy_category`; assert returned scenario has `tax_saving = 0` and is NOT in `combined["recommended_combination"]`. Satisfies NFR-001 (Spec 059 FR-019 regression coverage).
- [x] T007 [US1] In same file, DELETE any existing test whose purpose is to assert behaviour of the three removed filter layers. Specifically grep for and remove tests referencing `_META_KEYWORDS`, `max_tool_calls`, `structural-filter`, `name-filter stripped`, or the `1.1 ×` ratio predicate. Each deletion is a separate `git diff` hunk so the removals are visible in review.

### Implementation

- [x] T008 [US1] In `backend/app/modules/tax_planning/agents/modeller.py`, extract the current `_execute_tool` method body (lines 190-322) to a new module-level pure function `_compute_scenario(modification: dict, base_financials: dict, entity_type: str, rate_configs: dict) -> dict`. Keep its body byte-for-byte identical except: (a) rename the parameter `tool_input` → `modification`, (b) read `strategy_id` directly from `modification["strategy_id"]` (not slugged from title — implements R4). Satisfies FR-010.
- [x] T009 [US1] In `modeller.py`, rewrite `ScenarioModellerAgent.run()` to:
  1. Build the user prompt listing input strategies with their IDs.
  2. Make ONE call to `self.client.messages.create(...)` with `tools=[SUBMIT_MODIFICATIONS_TOOL]` and `tool_choice={"type": "tool", "name": "submit_modifications"}`.
  3. Extract the first `tool_use` block with `name == "submit_modifications"` from `response.content`; read `block.input["modifications"]`.
  4. Validate each modification: drop when `strategy_id ∉ input_ids` (log `Modeller: dropping unknown strategy_id=%r`); dedupe by first occurrence (log `Modeller: dropping duplicate strategy_id=%r`); truncate to `len(input_strategies)`.
  5. For each validated modification, call `_compute_scenario(...)` to build one scenario dict.
  6. Call existing `_build_combined_strategy(scenarios)` for the summary.
  7. Emit the completion log line `"Modeller: produced %d scenarios (from %d validated modifications), combined saving=$%s"`.
  8. Return `(scenarios, combined)` — signature UNCHANGED. Satisfies FR-001, FR-002, FR-003, FR-005, FR-006, FR-009. Delete the entire old tool-use `while` loop and all three filter layers (hard cap with `max_tool_calls`, `_META_KEYWORDS` filter, structural `1.1 ×` ratio). Satisfies FR-008.
- [x] T010 [US1] In `_build_combined_strategy` (same file), DELETE the internal `_META_KEYWORDS` re-filter (current lines 343-349) and the `_is_meta_scenario` helper. Replace `real_scenarios = [s for s in scenarios if not _is_meta_scenario(s)]` with `real_scenarios = scenarios` (pass-through). Satisfies FR-008 (remaining piece).
- [x] T011 [US1] In `modeller.py`, change `MAX_TOKENS = 32000` to `MAX_TOKENS = 12000`. Satisfies FR-007 (primary driver — see FR-007 also exercised by US2 verification).

### Verification

- [x] T012 [US1] Run `cd backend && uv run pytest tests/modules/tax_planning/agents/test_modeller.py -v` and confirm T005 + T006 pass. Verifies Story 1 Independent Test criterion.

**Checkpoint**: US1 code complete. Meta-scenarios are now structurally impossible; Total Tax Saving equals sum of per-strategy savings. The rewrite needed for US2, US3, and US4 is already in place.

---

## Phase 4: User Story 2 — Analysis runs complete without streaming errors (Priority: P1)

**Story goal**: End-to-end analysis run succeeds in a single synchronous request cycle.

**Independent test**: Golden-dataset live run returns status `succeeded`, no "Streaming is required" error in worker logs.

The code change that enables this landed in T011 (MAX_TOKENS reduction) + T009 (elimination of multi-round loop). This phase is verification-only.

- [ ] T013 [US2] Restart celery worker to pick up new code: `docker restart clairo-celery-worker && until docker ps --format "{{.Names}}\t{{.Status}}" | grep -q "clairo-celery-worker.*healthy"; do sleep 2; done`. In the UI, trigger a fresh analysis against the KR8 IT tax plan (or another client with ≥3 applicable strategies).
- [ ] T014 [US2] Tail `docker logs clairo-celery-worker` during and after the run and confirm:
  - Exit status of the Celery task is `succeeded`, not `failed`.
  - No log line contains `"Streaming is required"`.
  - The completion log line `"Modeller: produced N scenarios"` appears, with N ≤ number of applicable strategies.

  Verifies FR-006, FR-007, SC-002, Story 2 Independent Test criterion.

**Checkpoint**: US2 complete. Pipeline runs end-to-end. US3/US4 can now verify downstream properties.

---

## Phase 5: User Story 3 — Scenario count bounded by input (Priority: P2)

**Story goal**: Structural guarantee that the number of returned scenarios cannot exceed input count, and every `strategy_id` belongs to the input set.

**Independent test**: Unit tests stubbing LLM responses with unknown/duplicate/excess entries.

Implementation landed in T009 (validation steps). Phase is tests-only — they codify the guarantee.

- [ ] T015 [US3] In `backend/tests/modules/tax_planning/agents/test_modeller.py`, add `test_drops_unknown_strategy_id` — stub Anthropic response with a modification whose `strategy_id="hallucinated-meta"` is not in the input strategies; assert the returned scenarios list does not contain an entry with that ID; assert a log line `Modeller: dropping unknown strategy_id='hallucinated-meta'` was emitted (use `caplog` fixture). Satisfies FR-001, FR-009.
- [ ] T016 [US3] In same file, add `test_dedupes_duplicate_strategy_ids` — stub returns two modifications with the same `strategy_id="prepay-deductible-expenses"`; assert only the first occurrence appears in returned scenarios; assert the deduplication log line was emitted. Satisfies FR-002, FR-009.
- [ ] T017 [US3] In same file, add `test_truncates_to_input_count` — stub returns N+1 unique valid modifications for N input strategies (e.g., 4 mods for 3 inputs, with all 4 `strategy_id` values present in the input set of 3 — achievable by testing with the `truncation` path alone, not membership). In practice, membership + dedupe already bound the count; this test covers the pathological case where the LLM returns more than N unique valid entries by testing with an input list smaller than the stubbed response. Assert `len(scenarios) ≤ N`. Satisfies FR-003.
- [ ] T018 [US3] Run `cd backend && uv run pytest tests/modules/tax_planning/agents/test_modeller.py -v` and confirm T015–T017 pass alongside T005–T006. Verifies Story 3 Independent Test criterion.

**Checkpoint**: US3 complete. Structural guarantees codified in tests.

---

## Phase 6: User Story 4 — Reviewer no longer false-positives on combined-total mismatch (Priority: P2)

**Story goal**: Observational consequence — with the rewrite in place, the reviewer's combined-total consistency check no longer fires.

**Independent test**: Live run's reviewer output free of combined-total findings; UI does not show "Needs Review" for this cause.

No code change. Pure verification.

- [ ] T019 [US4] Using the analysis run from T013 (or a fresh one), inspect `TaxPlanAnalysis.review_result` in the DB (via `docker exec clairo-postgres psql -U postgres -d clairo -c "SELECT review_result FROM tax_plan_analyses ORDER BY created_at DESC LIMIT 1;"`) OR via the router response. Confirm:
  - `review_result["findings"]` (or equivalent) does NOT contain substrings matching: "combined strategy" + "inconsistency", "double-counting", "total tax saving" + "mismatch", or any arithmetic-combined-total complaint.
  - If the reviewer flags other quality issues (substance, not arithmetic), that is acceptable — this task asserts only the absence of the combined-total class.
- [ ] T020 [US4] In the browser on the Analysis tab, confirm the top banner does not read "Needs Review" for the combined-total arithmetic reason. Capture a screenshot for the PR. Verifies SC-003, Story 4 Independent Test criterion.

**Checkpoint**: US4 complete. All four user stories delivered.

---

## Phase 7: Polish & Cross-Cutting Verification

**Purpose**: Static checks, regression coverage, documentation.

- [ ] T021 Static grep — verify legacy filter identifiers are gone:
  ```sh
  grep -nE "_META_KEYWORDS|max_tool_calls|1\.1 \*|_is_meta_scenario" backend/app/modules/tax_planning/agents/modeller.py
  ```
  MUST return zero matches (grep exit status 1). Satisfies SC-004.
- [ ] T022 Run the full tax_planning test suite with no filter: `cd backend && uv run pytest tests/modules/tax_planning/ -v`. All existing advisor/reviewer/scanner/profiler/orchestrator tests MUST still pass (no regressions). Verifies NFR-004.
- [ ] T023 Run `cd backend && uv run ruff check app/modules/tax_planning/ tests/modules/tax_planning/` and `cd backend && uv run ruff format app/modules/tax_planning/ tests/modules/tax_planning/`. Zero lint errors. Satisfies Constitution Principle VI.
- [ ] T024 Walk through `specs/059-2-tax-planning-correctness-followup/quickstart.md` end-to-end against a live client (KR8 IT or equivalent). Confirm every step in the "Definition of done" checkbox passes. Satisfies SC-006.
- [ ] T025 Update `HANDOFF.md` — replace the "Active Problem: Meta-Scenario Double-Counting in Tax Planning Modeller" section with a "Resolved" note linking to `specs/059-2-tax-planning-correctness-followup/` and explaining (one paragraph) that the architectural redesign replaced the LLM-controlled tool-use loop with a forced single tool call + Python-driven iteration, making meta-scenarios structurally impossible.
- [ ] T026 Commit the work in logical chunks (foundational constants, rewrite, tests, HANDOFF update). Use `fix(059-2):` prefix on commits. Run `cd backend && uv run pytest tests/modules/tax_planning/agents/test_modeller.py` one final time before pushing.

---

## Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational: T003, T004 — parallelisable [P])
    ↓
Phase 3 (US1 — MVP: T005..T012)
    ↓                            ↘
Phase 4 (US2: T013, T014)    Phase 5 (US3: T015..T018)    Phase 6 (US4: T019, T020)
    ↘                            ↙                            ↙
               Phase 7 (Polish: T021..T026)
```

**Story independence**:
- US1 is the MVP — delivering it alone closes the headline correctness defect and produces a working pipeline.
- US2 is a live-run verification; runs independently after US1 lands.
- US3 is unit-test codification; can be added in any order post-US1.
- US4 is observational; runs against the same live-run artefact as US2.

**Critical dependency**: T009 (the core rewrite) must complete before T012, T013, T019. All other dependencies are conventional (test file ordering, grep after code changes).

---

## Parallel Execution Opportunities

| Parallel block | Tasks | Why safe |
|----------------|-------|----------|
| Foundational | T003, T004 | Different files (`prompts.py` vs `agents/prompts.py`), no shared state |
| US1 tests | T005, T006 | Same file but different test functions; lint-clean separate diffs |
| US3 tests | T015, T016, T017 | Same file but different test functions |
| Post-US1 verification | Phases 4, 5, 6 | All depend on US1 landing but are independent of each other |

**Not parallelisable**: T008 → T009 → T010 → T011 all mutate `modeller.py` in sequence. T007 is a separate concern (test file deletions) and MAY run parallel to T008-T011 [P] if executed against a clean checkout.

---

## FR → Task traceability

| FR | Tasks |
|----|-------|
| FR-001 (drop unknown strategy_id) | T009, T015 |
| FR-002 (dedupe by strategy_id) | T009, T016 |
| FR-003 (truncate to input count) | T009, T017 |
| FR-004 (combined total = sum of scenarios) | T005, T009, T012 |
| FR-005 (count bounded by code) | T009 (core rewrite) |
| FR-006 (single synchronous call) | T009, T014 |
| FR-007 (no streaming error) | T011, T014 |
| FR-008 (delete three legacy filters) | T009, T010, T021 |
| FR-009 (diagnostic log entries) | T009, T015, T016 |
| FR-010 (preserve Spec 059 provenance) | T008, T006 |

## SC → Verification task traceability

| SC | Task |
|----|------|
| SC-001 (arithmetic correctness × 10 runs) | T005, T024 |
| SC-002 (100% succeeded across UAT week) | T013, T014, T024 |
| SC-003 (0% Needs Review from arithmetic) | T019, T020 |
| SC-004 (legacy filter identifiers removed) | T021 |
| SC-005 (unit test coverage) | T005, T006, T015, T016, T017, T018 |
| SC-006 (accountant reconciles headline line-by-line) | T024 |

---

## MVP Scope

**MVP = Phase 1 + Phase 2 + Phase 3 (T001–T012)**. This delivers User Story 1 standalone: the headline number is correct and the pipeline runs. Stories 2/3/4 are either live-run verifications that ride on US1's code or unit tests that codify guarantees already implemented in US1.

If time-boxed: ship T001–T012 first, open PR, then layer T013–T026 before merge. If scope needs to compress further: Phases 4+5+6 can run in any order; Phase 7 cannot be skipped (lint + regressions + HANDOFF update are release-blocking).

---

## Task count: 26

- Phase 1 Setup: 2 tasks
- Phase 2 Foundational: 2 tasks
- Phase 3 US1 (MVP): 8 tasks
- Phase 4 US2: 2 tasks
- Phase 5 US3: 4 tasks
- Phase 6 US4: 2 tasks
- Phase 7 Polish: 6 tasks
