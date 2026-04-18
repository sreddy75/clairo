---
description: "Tasks for Citation Substantive Validation (061)"
---

# Tasks: Citation Substantive Validation

**Input**: Design documents from `specs/061-citation-validation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/section_act_mapping.schema.yaml, quickstart.md

**Tests**: Included. Required by FR-008, FR-009 (TDD), SC-003, and Constitution Principle V.

**Organization**: By user story. Story 3 (unit-test safety net) is a **prerequisite** for Stories 1 and 2 per FR-009 and runs first among the story phases. Stories 1 and 2 each add a distinct capability to the verifier; Story 4 is independent and can land anytime after Story 1.

## Format

`- [ ] [TaskID] [P?] [Story?] Description with file path`

- `[P]` = parallelisable (different files, no incomplete dependencies)
- `[USn]` = maps to User Story n in spec.md

## Path Conventions

Backend-only. Two new directories will be created:
- `backend/app/modules/knowledge/data/`
- `backend/tests/unit/modules/knowledge/retrieval/`

---

## Phase 1: Setup

**Purpose**: Precondition checks; no code yet.

- [ ] T001 Confirm `061-citation-validation` branch is checked out and working tree is clean apart from `specs/061-citation-validation/` and the two pre-existing untracked files (`frontend/public/tax-planning-wireframes.html`, `specs/briefs/2026-04-18-llm-output-hardening.md`).
- [ ] T002 Read `specs/061-citation-validation/plan.md`, `research.md`, and `data-model.md` end-to-end to confirm the TDD order (Story 3 before Stories 1/2) and the `match_strength` ↔ `matched_by` invariant from R5.

---

## Phase 2: Foundational (Blocks all user stories)

**Purpose**: Create new directories, add YAML loader scaffolding, add the StrEnum. These are pure additions — they don't change verifier behaviour yet, so they are safe to land first.

- [ ] T003 [P] Create directory `backend/app/modules/knowledge/data/` with an empty `__init__.py`. Matches the planned structure in `plan.md`.
- [ ] T004 [P] Create directory `backend/tests/unit/modules/knowledge/retrieval/` with an empty `__init__.py`. Confirm Python `__init__.py` files are present up the chain (`tests/unit/modules/knowledge/` may need one; check and add if missing).
- [ ] T005 Create `backend/app/modules/knowledge/data/section_act_mapping.py` containing: (a) a pure `_normalise_section(raw: str) -> str` function implementing R7's rules (lowercase, strip whitespace, drop leading `s`/`section `/`sec.`, collapse internal whitespace), (b) a module-level `@functools.cache`d `get_section_act_mapping() -> Mapping[str, dict]` that loads the YAML from the same directory and returns a frozen dict keyed by normalised section id, (c) fail-fast validation: malformed YAML raises `RuntimeError` at load, duplicate normalised keys raise, missing `act`/`display_name` raises. No runtime file path configurability. Includes type hints on every signature.
- [ ] T006 Add `CitationReasonCode` `StrEnum` to `backend/app/modules/knowledge/retrieval/citation_verifier.py` with the six members from R3: `STRONG_MATCH`, `WEAK_MATCH_BODY_ONLY`, `WEAK_MATCH_NONE`, `WRONG_ACT_YEAR`, `UNKNOWN_SECTION`, `NO_CITATIONS`. Export via `__all__`.
- [ ] T007 Create `backend/app/modules/knowledge/data/section_act_mapping.yaml` as a **stub** with 5 seed entries (e.g., `82kzm`, `82kzmd`, `328-180`, `6-5`, `177a`). The full ≥100-entry curation happens in T027 during US2 — the stub is enough for unit tests and foundational loader work.

**Checkpoint**: After T003–T007, the directory + loader + enum exist. Nothing else has changed yet — verifier behaviour unchanged; existing tests still green.

---

## Phase 3: User Story 3 — Unit-Test Safety Net (Priority: P2 — PREREQUISITE)

**Story goal**: A comprehensive unit-test suite covers every extraction pattern and every match path in `CitationVerifier` before any behavioural change lands (FR-009).

**Independent test**: `cd backend && uv run pytest tests/unit/modules/knowledge/retrieval/test_citation_verifier.py -v` — all tests pass and together cover ≥85% of `citation_verifier.py`.

**Critical TDD note**: These tests are written to **describe the target behaviour**, not the current one. Tests for Stories 1 and 2 will intentionally FAIL after this phase lands (current verifier still blind-substring-matches and has no act-year check). Phases 4 and 5 make them pass.

- [ ] T008 [US3] In `backend/tests/unit/modules/knowledge/retrieval/test_citation_verifier.py`, add test fixtures: a `_make_chunk` helper that constructs a minimal chunk dict with `ruling_number`, `section_ref`, `title`, `text`, `relevance_score`; a `_make_verifier` helper that returns a `CitationVerifier` instance; a `monkeypatch`-based fixture that replaces `get_section_act_mapping` with a small test dict (`{"82kzm": {"act": "ITAA 1936", "display_name": "s 82KZM ITAA 1936"}, "328-180": {"act": "ITAA 1997", "display_name": "s 328-180 ITAA 1997"}}`).
- [ ] T009 [P] [US3] Add `test_ruling_metadata_equality_verifies_strong` — chunk with `ruling_number="TR 2024/1"`, response cites "TR 2024/1". Assert `verified=True`, `match_strength="strong"`, `matched_by="ruling_number"`, `reason_code == CitationReasonCode.STRONG_MATCH`. Satisfies FR-001.
- [ ] T010 [P] [US3] Add `test_ruling_body_text_only_is_weak_not_verified` — chunk with `ruling_number="TR 2023/5"` but `text` contains "see TR 2024/1 for prepayments"; response cites "TR 2024/1". Assert `verified=False`, `match_strength="weak"`, `reason_code == WEAK_MATCH_BODY_ONLY`. Satisfies FR-002.
- [ ] T011 [P] [US3] Add `test_hallucinated_ruling_no_match_anywhere` — no chunk has `ruling_number="TR 9999/99"` and no chunk body mentions it; response cites "TR 9999/99". Assert `verified=False`, `match_strength="none"`, `reason_code == WEAK_MATCH_NONE`. Satisfies FR-003.
- [ ] T012 [P] [US3] Add `test_section_wrong_act_year_flagged` — authoritative mapping records `82kzm → ITAA 1936`; response cites "s 82KZM ITAA 1997". Assert `verified=False`, `reason_code == WRONG_ACT_YEAR`. Uses the test mapping fixture from T008. Satisfies FR-005.
- [ ] T013 [P] [US3] Add `test_section_correct_act_year_verifies` — same mapping; response cites "s 82KZM ITAA 1936". Assert `verified=True` (subject to metadata/body-text matching still succeeding). Satisfies FR-005 positive path.
- [ ] T014 [P] [US3] Add `test_section_unknown_in_mapping_not_penalised` — response cites "s 9999Z ITAA 1997"; mapping has no entry for `9999z`. Assert the verifier does NOT flag `wrong_act_year`; falls through to metadata/body-text match logic. Satisfies FR-006.
- [ ] T015 [P] [US3] Add `test_section_no_act_year_attribution_skips_act_check` — response cites just "s82KZM" (no "ITAA ..." suffix). Mapping has entry for `82kzm`. Assert the act-year check is skipped (no `wrong_act_year` even though mapping expects ITAA 1936). Satisfies FR-006 second branch.
- [ ] T016 [P] [US3] Add `test_match_strength_matched_by_invariant` — run a small sweep of citations (strong, weak-body, weak-title, miss) and assert for each result: if `match_strength=="strong"` then `matched_by in {"ruling_number", "section_ref"}`; if `match_strength=="weak"` then `matched_by in {"body_text", "title", "numbered_index"}`; if `match_strength=="none"` then `matched_by == "unverified"`. Satisfies R5 invariant.
- [ ] T017 [US3] Add `test_normalise_section_handles_common_variants` — assert `_normalise_section` correctly folds `"Section 82KZM"`, `"s 82KZM"`, `"S82KZM"`, `"sec. 82kzm"`, `" s82KZM "` all to `"82kzm"`. Satisfies R7.
- [ ] T018 [US3] Run the unit-test suite: `cd backend && uv run pytest tests/unit/modules/knowledge/retrieval/test_citation_verifier.py -v`. Expect: T009-T017 RED (most failing — current verifier does not implement the new behaviour); T017 (normaliser) GREEN once T005 lands. This is the TDD baseline. **Document the failures in a comment commit** before Phase 4 starts.

**Checkpoint**: Unit tests exist and describe the target behaviour. Failing tests are the spec of what Phases 4 and 5 must deliver.

---

## Phase 4: User Story 1 — Topical Relevance for Ruling Citations (Priority: P1)

**Story goal**: Ruling citations verify only on metadata equality (`chunk.ruling_number == citation.value`). Body-text-only matches become explicit weak matches. Hallucinated rulings fall to `match_strength=none`.

**Independent test**: T009, T010, T011, T016 (from Phase 3) transition from RED to GREEN.

### Implementation

- [ ] T019 [US1] In `backend/app/modules/knowledge/retrieval/citation_verifier.py`, extend the `CitationVerificationResult` TypedDict (or equivalent internal dict) with new additive keys `match_strength: Literal["strong", "weak", "none"]` and `reason_code: CitationReasonCode`. Every existing code path that builds a result dict MUST set these two keys — no `None` defaults, no implicit backfills.
- [ ] T020 [US1] In the same file, rewrite `_find_chunk_for_reference` (currently lines ~199-249) for `ref_type="ruling"` so that:
  1. Iterate chunks; if any `chunk.ruling_number` equals `citation.value` (normalised), return it with `match_strength=strong`, `matched_by="ruling_number"`, `reason_code=STRONG_MATCH`.
  2. Otherwise iterate chunks looking for a body-text mention; if found, return it with `match_strength=weak`, `matched_by="body_text"`, `reason_code=WEAK_MATCH_BODY_ONLY`, `verified=False`.
  3. If neither, return a synthetic "none" result with `match_strength=none`, `matched_by="unverified"`, `reason_code=WEAK_MATCH_NONE`, `verified=False`.
  Preserve the `_find_chunk_for_reference` signature; only internal dispatch changes. Satisfies FR-001, FR-002, FR-003, FR-012.
- [ ] T021 [US1] Update `_build_citation_dict` (currently ~:251-295) to read the new `match_strength` / `reason_code` / `verified` decision from the match-result helper, and include them in the returned dict. Do NOT default `verified=True` anywhere — the decision must come from the helper.
- [ ] T022 [US1] Run T009, T010, T011, T016 specifically: `cd backend && uv run pytest tests/unit/modules/knowledge/retrieval/test_citation_verifier.py::test_ruling_metadata_equality_verifies_strong tests/unit/modules/knowledge/retrieval/test_citation_verifier.py::test_ruling_body_text_only_is_weak_not_verified tests/unit/modules/knowledge/retrieval/test_citation_verifier.py::test_hallucinated_ruling_no_match_anywhere tests/unit/modules/knowledge/retrieval/test_citation_verifier.py::test_match_strength_matched_by_invariant -v`. All four MUST pass. If T016 (invariant) fails, the return paths in T020 are inconsistent — fix before proceeding.
- [ ] T023 [US1] Run the e2e regression guard: `cd backend && uv run pytest tests/e2e/tax_planning/test_citation_regression_bank.py -v`. MUST stay green. Verifies FR-011, SC-005. If RED, the topical-relevance tightening accidentally declined a citation the 059 test fixture relies on — investigate and either fix the verifier logic or update the fixture expectations (the latter requires reviewer approval because the fixture was deliberately pinned).

**Checkpoint**: Story 1 code complete. Ruling hallucinations can no longer pass verification. Story 2 builds on this (both update the same file, so Story 2 comes next serially).

---

## Phase 5: User Story 2 — Act-Year Validation for Section Citations (Priority: P1)

**Story goal**: Section citations with an explicit act-year suffix are checked against the authoritative mapping. Wrong-act-year citations flag; correctly-attributed ones verify; unknown-in-mapping falls through.

**Independent test**: T012, T013, T014, T015 (from Phase 3) transition from RED to GREEN.

### Implementation

- [ ] T024 [US2] In `backend/app/modules/knowledge/chunkers/base.py`, extend `SECTION_REF_PATTERN` to capture the optional act-year suffix. Current pattern captures only the section number token (e.g., `s82KZM`); new pattern captures both the section token AND, when present, the trailing `" ITAA 1997"` / `" ITAA 1936"` / `" TAA 1953"` / etc. The regex must remain backwards-compatible: citations without an act suffix continue to extract with `act_year=None`. Add unit tests against the regex directly (co-located with T017's normaliser test if simpler). Satisfies FR-004.
- [ ] T025 [US2] In `backend/app/modules/knowledge/retrieval/citation_verifier.py`, extend `_extract_citations_from_response` (currently ~:141-197) so that section-type citations carry the captured `act_year` field on the `ExtractedCitation` dict. Other citation types (numbered, ruling) set `act_year=None`.
- [ ] T026 [US2] In the same file, extend the section-citation matching path inside `_find_chunk_for_reference` with the act-year comparator:
  1. If `citation.act_year` is None OR `normalised_section not in get_section_act_mapping()`: skip act-year check; fall through to existing metadata/body-text match logic (satisfies FR-006).
  2. Otherwise: if `mapping[normalised_section]["act"] != citation.act_year`: return `verified=False`, `reason_code=WRONG_ACT_YEAR`, with the `match_strength`/`matched_by` from whichever match path would have been taken (satisfies FR-005).
  3. If mapping agrees: fall through to existing match logic; returned result carries `reason_code=STRONG_MATCH` or the appropriate weak code based on the match-path outcome.
- [ ] T027 [US2] Curate `backend/app/modules/knowledge/data/section_act_mapping.yaml` to include at least 100 entries covering common Australian tax-law sections cited in tax planning. Structure: normalised section id → `{act, display_name, notes?}`. Source priority: (a) mine the last 12 months of `tax_plan_messages.citation_verification` JSONB in production for sections actually seen, rank by frequency, take the top 100; (b) if production mining is impractical locally, use a domain-curated list — top commonly-cited sections across ITAA 1997 Divisions 6, 8, 328, 355, 40, 385, ITAA 1936 Parts IVA, III Division 7A, 10C, prepayment sections (82KZL..82KZMF), TAA 1953 Schedule 1, GST Act 1999, FBTAA 1986. Mark the file as requiring domain-expert review in the commit message. Satisfies FR-007, SC-006.
- [ ] T028 [US2] Run T012, T013, T014, T015: `cd backend && uv run pytest tests/unit/modules/knowledge/retrieval/test_citation_verifier.py -k "act_year or unknown_in_mapping or no_act_year_attribution" -v`. All four MUST pass. If any fail, trace from the extractor (T025) → comparator (T026) → YAML loader (T005). Satisfies FR-004..FR-006.
- [ ] T029 [US2] Run the e2e regression guard again: `cd backend && uv run pytest tests/e2e/tax_planning/test_citation_regression_bank.py -v`. MUST stay green. If RED, the act-year check is firing on a citation the fixture expected to verify — investigate and either loosen the check (unlikely — the fixture should use correct attributions) or amend the fixture (requires reviewer approval).

**Checkpoint**: Story 2 code complete. Wrong-act-year citations are detected. Both P1 stories done.

---

## Phase 6: User Story 4 — Streaming / Non-Streaming Parity (Priority: P2)

**Story goal**: Sub-threshold confidence-gate handling is identical across streaming and non-streaming chat paths (Q2=C hybrid: preserve content, clear scenarios, warning banner).

**Independent test**: An integration test fires an identical sub-threshold input through both paths and asserts identical `(response_content, scenarios, status_label)`.

### Implementation

- [ ] T030 [US4] In `backend/app/modules/tax_planning/service.py`, add a private module-level function `_apply_subthreshold_gate(response_content: str, scenarios: list[dict], confidence_score: float, retrieved_chunks: list[dict]) -> tuple[str, list[dict], str]` implementing the contract in `data-model.md` (confidence < 0.5 AND chunks non-empty → preserve content, empty scenarios, status "low_confidence"; otherwise pass-through with status "ok"). Pure function, no I/O. Add type hints. Satisfies FR-010.
- [ ] T031 [US4] Refactor the non-streaming sub-threshold block (currently ~:1460-1482) to call `_apply_subthreshold_gate` and thread the returned tuple through. Remove any inline content-replacement or scenario-clearing that the helper now owns. Preserve existing audit log calls — they still fire when `status_label == "low_confidence"`.
- [ ] T032 [US4] Refactor the streaming sub-threshold block (currently ~:1747-1760) to call the same helper. Thread the cleared scenarios list into the streaming path's post-completion persistence. The streaming path's response-content handling needs to emit the preserved text (not a canned decline) and persist an empty scenarios list. If the current streaming path sets `status` differently, align on `status_label == "low_confidence"`.
- [ ] T033 [US4] In `backend/tests/unit/modules/tax_planning/test_subthreshold_gate.py` (new file), add unit tests for `_apply_subthreshold_gate`: (a) above-threshold pass-through, (b) below-threshold with chunks → preserve+clear+label, (c) below-threshold with no chunks → pass-through (gate doesn't fire), (d) idempotence (calling twice returns identical output). ≥4 tests, all <50ms. Verifies FR-010, SC-004.
- [ ] T034 [US4] Grep for any remaining "canned decline" strings in `service.py` to confirm they're only emitted via the helper (not inline): `grep -n "could not be verified\|low_confidence\|decline" backend/app/modules/tax_planning/service.py`. Every match should either be in the helper, in test assertions, or in unrelated code paths — no duplicated inline decline strings across the two chat paths.

**Checkpoint**: Streaming and non-streaming sub-threshold handling are symmetric. Story 4 complete.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Full-suite verification, lint, live UAT smoke, documentation, commits.

- [ ] T035 Run the full knowledge-module unit test suite: `cd backend && uv run pytest tests/unit/modules/knowledge/ -v`. Every test MUST pass (no regressions in other knowledge code). Verifies NFR-004 by omission (no cross-module regressions).
- [ ] T036 Run the full tax_planning unit test suite: `cd backend && uv run pytest tests/unit/modules/tax_planning/ -v`. Every test MUST pass. In particular the 142 tests that have been stable across 059-2 must remain green.
- [ ] T037 Run the e2e regression: `cd backend && uv run pytest tests/e2e/tax_planning/test_citation_regression_bank.py -v`. MUST stay green. Final guard for FR-011 + SC-005.
- [ ] T038 Check coverage: `cd backend && uv run pytest tests/unit/modules/knowledge/retrieval/test_citation_verifier.py --cov=app.modules.knowledge.retrieval.citation_verifier --cov-report=term-missing`. Assert coverage ≥85% (SC-003). If below, add tests for uncovered branches — do NOT lower the bar.
- [ ] T039 Lint + format: `cd backend && uv run ruff check app/modules/knowledge/retrieval/ app/modules/knowledge/data/ app/modules/knowledge/chunkers/ app/modules/tax_planning/service.py tests/unit/modules/knowledge/retrieval/ && uv run ruff format app/modules/knowledge/retrieval/ app/modules/knowledge/data/ app/modules/knowledge/chunkers/ app/modules/tax_planning/service.py tests/unit/modules/knowledge/retrieval/`. All checks pass.
- [ ] T040 Grep verifier for legacy substring-only ruling match: `grep -nE "ruling_ref.*in.*body|in chunk_text|in response_text" backend/app/modules/knowledge/retrieval/citation_verifier.py`. Ruling-citation match path MUST NOT rely solely on these predicates — metadata equality must be the primary gate for strong match. Verifies Story 1's structural guarantee.
- [ ] T041 Verify YAML seeding: `cd backend && uv run python -c "from app.modules.knowledge.data.section_act_mapping import get_section_act_mapping; m = get_section_act_mapping(); assert len(m) >= 100, f'Only {len(m)} entries; target is 100+'; print(f'{len(m)} entries loaded')"`. Verifies SC-006.
- [ ] T042 Live smoke: `docker restart clairo-celery-worker && docker restart clairo-backend && until docker ps --format "{{.Names}}\t{{.Status}}" | grep -q "clairo-backend.*healthy"; do sleep 2; done`. Trigger a chat query in the UI that produces a cited response (e.g. "What are the prepayment provisions?"). In the DB:
  ```sh
  docker exec clairo-postgres psql -U clairo -d clairo -c "SELECT jsonb_pretty(citation_verification->'citations') FROM tax_plan_messages ORDER BY created_at DESC LIMIT 1;"
  ```
  Confirm: every citation object carries `match_strength` and `reason_code` keys; a hallucinated-looking citation (if the LLM emits one) flags `reason_code=weak_match_none` not `verified=True`.
- [ ] T043 Live parity check: fire an identical sub-threshold query through both the streaming and non-streaming chat paths (toggle the UI mode or invoke the respective endpoints directly). Compare the two persisted `tax_plan_messages` rows — `response_content` preserved on both, `scenarios` empty on both, status `low_confidence` on both. Verifies SC-004.
- [ ] T044 Update `HANDOFF.md` — remove the "next-action priority: citation substantive validation" line item (it's now spec'd and implemented) OR update that line to point at the commit SHA. Remove the `specs/briefs/2026-04-18-citation-substantive-validation.md` reference in the Priority section, or mark it as superseded by `specs/061-citation-validation/`.
- [ ] T045 Stage and commit in logical chunks. Use `fix(061):` prefix for code commits and `docs(061):` for spec/HANDOFF updates. Suggested chunks:
  1. Spec artifacts + plan (`specs/061-citation-validation/` + HANDOFF update).
  2. Foundational: YAML loader + enum + directory scaffolding (T003–T007).
  3. Unit-test suite (T008–T018).
  4. Story 1 implementation (T019–T023).
  5. Story 2 implementation + YAML seeding (T024–T029).
  6. Story 4 parity helper (T030–T034).
  7. Polish commit if any lint-format-only diffs remain.
  Run `uv run pytest tests/unit/modules/knowledge/retrieval/test_citation_verifier.py` one final time before pushing. Do NOT push or open a PR unless explicitly asked.

---

## Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational: T003-T007 — T003/T004 [P] with each other)
    ↓
Phase 3 (US3 — Unit-test safety net: T008-T018. TDD gate for Phases 4 and 5.)
    ↓
Phase 4 (US1 — Topical relevance: T019-T023)
    ↓
Phase 5 (US2 — Act-year validation: T024-T029)
    ↘
     Phase 6 (US4 — Streaming parity: T030-T034) — independent of US1/US2, can run anytime post-Phase 3.
    ↘
     Phase 7 (Polish: T035-T045)
```

**Story independence after Phase 3**:
- US1 and US2 both modify `citation_verifier.py`. US2 builds on US1's refactored `_find_chunk_for_reference`; run US1 first.
- US4 modifies `tax_planning/service.py` only — can be parallel with US1 or US2 if two developers work in parallel.

**Critical dependency**: T020 (US1 match-path rewrite) is the load-bearing task. T026 (US2 act-year comparator) extends T020's output. T022/T028 are the gates proving the rewrites deliver the story outcomes.

---

## Parallel Execution Opportunities

| Parallel block | Tasks | Why safe |
|----------------|-------|----------|
| Foundational dirs | T003, T004 | Different files (`data/` vs `tests/unit/...`) |
| US3 tests | T009-T016 | Same test file but different test functions; separate diffs |
| US1 + US4 | Phase 4 + Phase 6 | Different files (`citation_verifier.py` vs `service.py`) — ok for two developers |

**Not parallelisable**: T019 → T020 → T021 all edit `citation_verifier.py` serially. T025 → T026 likewise serial within US2.

---

## FR → Task Traceability

| FR | Tasks |
|----|-------|
| FR-001 (topical relevance) | T009, T020, T022 |
| FR-002 (weak match distinction) | T010, T019, T020, T022 |
| FR-003 (hallucinated rejection) | T011, T020, T022 |
| FR-004 (act-year extraction) | T024, T025 |
| FR-005 (act-year validation) | T012, T013, T026, T028 |
| FR-006 (act-year leniency) | T014, T015, T026, T028 |
| FR-007 (authoritative mapping) | T005, T007, T027, T041 |
| FR-008 (unit-test coverage) | T008-T017, T038 |
| FR-009 (TDD order) | Phase 3 precedes Phase 4/5 structurally |
| FR-010 (streaming parity) | T030-T033, T043 |
| FR-011 (regression preservation) | T023, T029, T037 |
| FR-012 (observability / reason codes) | T006, T019, T020, T021, T026 |

## SC → Verification Task Traceability

| SC | Task |
|----|------|
| SC-001 (zero false-verified hallucinated rulings) | T042 (live smoke), T011 (unit) |
| SC-002 (wrong-act fixture 100% detection) | T012, T013, T028 |
| SC-003 (≥85% coverage, ≥8 tests, <1s) | T038 |
| SC-004 (streaming parity) | T033, T043 |
| SC-005 (e2e regression preserved) | T023, T029, T037 |
| SC-006 (≥100 mapping entries) | T027, T041 |

---

## MVP Scope

**Minimum viable ship**: Phase 1 + Phase 2 + Phase 3 + Phase 4 + Phase 7 polish subset (T035, T036, T037, T039, T044, T045).

That delivers **User Story 1 standalone**: the highest-severity defect (hallucinated rulings verifying) is fixed, with full unit-test coverage behind it. Stories 2, 4 can follow incrementally. Spec's Story 2 also P1 — so the true MVP is Phase 1-5 + minimal polish, but if time pressure forces a split, US1 ships alone and US2 follows.

---

## Task count: 45

- Phase 1 Setup: 2 tasks
- Phase 2 Foundational: 5 tasks
- Phase 3 US3 (Tests): 11 tasks (T008-T018)
- Phase 4 US1: 5 tasks
- Phase 5 US2: 6 tasks
- Phase 6 US4: 5 tasks
- Phase 7 Polish: 11 tasks
