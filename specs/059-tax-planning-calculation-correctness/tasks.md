# Tasks: Tax Planning — Calculation Correctness

**Feature**: `059-tax-planning-calculation-correctness`
**Input**: Design documents from `specs/059-tax-planning-calculation-correctness/`
**Tests**: REQUIRED — the entire purpose of this feature is to close the test-coverage gap that allowed these bugs to ship. Every user story has test tasks.

**Organization**: Tasks grouped by user story so each P1 story is independently shippable and demonstrable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on other incomplete tasks in this batch)
- **[Story]**: User story label (US1..US8) — maps to spec.md user stories

---

## Phase 0: Git Setup (already complete)

- [x] T000 Feature branch `059-tax-planning-calculation-correctness` created and checked out

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffolding shared by every story. Thin because this is a modification of an existing module, not a new one.

- [x] T001 Create Alembic migration scaffold `backend/alembic/versions/20260418_059_tax_planning_correctness.py` with empty `upgrade()` / `downgrade()` bodies (filled in Phase 2) — completed together with T004
- [x] T002 [P] Create `backend/app/modules/tax_planning/strategy_category.py` with `StrategyCategory` enum (9 members per data-model.md), `REQUIRES_GROUP_MODEL` frozenset, and `requires_group_model(category) -> bool`
- [x] T003 [P] Create `backend/app/modules/tax_planning/projection.py` with `ProjectionMetadata` dataclass and `annualise_linear(ytd_totals: dict, months_elapsed: int) -> tuple[dict, ProjectionMetadata]` pure function

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, test harness, and shared model changes needed by every downstream story. No user-visible behaviour ships from this phase.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T004 Fill in the Alembic migration at `backend/alembic/versions/20260418_059_tax_planning_correctness.py` per data-model.md: create `strategy_category_enum`, add three columns (`strategy_category`, `requires_group_model`, `source_tags`) to `tax_scenarios`, disambiguate duplicate-title rows, create partial unique index `ix_tax_scenarios_plan_normalized_title`, with matching `downgrade()`
- [x] T005 Modify `backend/app/modules/tax_planning/models.py` to declare the three new columns on `TaxScenario` and the new `__table_args__` index (schema must match migration exactly)
- [x] T006 [P] Create `backend/tests/fixtures/fake_anthropic.py` — a `FakeAnthropicClient` fixture class keyed by input prompt hash → scripted response, with helpers to register tool-use responses deterministically (per research.md R11)
- [x] T007 [P] Create `backend/app/modules/tax_planning/audit_events.py` additions — 8 new event type constants per data-model.md §Audit event payload shapes (or extend existing file)
- [ ] T008 Run `cd backend && uv run alembic upgrade head` on a local dev database; verify the three columns and unique index exist; verify existing alpha rows got default values — **deferred: requires a running dev DB; migration file validated syntactically**
- [x] T009 [P] Write unit tests for `projection.annualise_linear` in `backend/tests/unit/modules/tax_planning/test_projection.py` — cover 6-month, 1-month, 12-month edge cases, divide-by-zero guard, metadata shape
- [x] T010 [P] Write unit tests for `strategy_category` in `backend/tests/unit/modules/tax_planning/test_strategy_category.py` — every enum value resolves, `requires_group_model()` returns True for the 5 multi-entity categories, False for single-entity categories

**Checkpoint**: Migration applied, shared primitives exist with tests, fake Anthropic fixture available. User stories can now begin.

---

## Phase 3: User Story 1 — Accountant trusts the headline numbers (Priority: P1) 🎯 MVP

**Goal**: Tax Position panel numbers reflect projected full-year figures (via linear annualisation) whenever fewer than 12 months of data exist. LLM sees exactly one set of numbers.

**Independent Test**: Load golden-dataset fixture with 6 months of data → open Tax Position panel → every field matches ChangeGPS reference within $1; confirm the AI chat prompt contains only annualised totals.

### Tests for User Story 1 (write first — must fail)

- [x] T011 [P] [US1] Integration test `backend/tests/integration/modules/tax_planning/test_ingest_annualisation.py::test_6_months_of_data_gets_annualised`
- [x] T012 [P] [US1] Integration test `test_ingest_annualisation.py::test_12_months_of_data_is_not_annualised`
- [x] T013 [P] [US1] Integration test `test_ingest_annualisation.py::test_manual_financials_treated_as_confirmed_full_year`
- [x] T014 [P] [US1] Integration test `test_ingest_annualisation.py::test_prompt_contains_only_annualised_totals` (plus companion test `test_prompt_omits_data_basis_note_when_projection_not_applied`)
- [x] T015 [P] [US1] Integration test `test_ingest_annualisation.py::test_tax_position_uses_annualised_totals`

### Implementation for User Story 1

- [x] T016 [US1] `service.py::pull_xero_financials` applies `annualise_linear` in-place to `income`/`expenses` and writes `projection_metadata`
- [x] T017 [US1] `service.py::save_manual_financials` sets `projection_metadata={applied: False, reason: "manual_full_year", ...}` via `annualise_manual`
- [x] T018 [US1] Deleted the legacy `financials_data["projection"]` sibling block; metadata now lives under `projection_metadata`
- [x] T019 [US1] `prompts.py::format_financial_context` now emits a single one-line "Data Basis" note; the parallel "Full Year Projection" block is gone
- [x] T020 [US1] `tax_planning.financials.annualised` audit event emitted via `AuditService.log_event` in `pull_xero_financials`
- [x] T021 [P] [US1] `TaxPositionCard.tsx` shows "Projected from N mo" amber badge when `projection_metadata.applied=true`; `TaxPlanningWorkspace.tsx` passes the metadata through
- [x] T022 [P] [US1] `frontend/src/types/tax-planning.ts` adds `ProjectionMetadata` interface and surfaces it on `FinancialsData`
- [x] T023 [US1] Full validation: 100 backend tax_planning tests green, ruff clean, `npx tsc --noEmit` green

**Checkpoint**: US1 complete. The Tax Position panel now shows annualised figures; LLM sees one set of numbers; the golden-dataset E2E (Phase 11) will gate the final numeric correctness.

---

## Phase 4: User Story 2 — Every figure on screen shows where it came from (Priority: P1)

**Goal**: Every numeric field in scenarios, analysis, and PDF export carries a provenance tag (confirmed/derived/estimated). Estimated figures render as editable prefilled inputs; accepting or editing transitions provenance to confirmed.

**Independent Test**: Run the multi-agent pipeline on the golden dataset → inspect every numeric cell in Analysis tab → 100% carry a visible provenance badge → click an estimated figure → edit or accept → badge flips to confirmed.

### Tests for User Story 2 (write first — must fail)

- [x] T024 [P] [US2] Contract test `backend/tests/contract/modules/tax_planning/test_scenario_schema_invariants.py::test_every_numeric_field_has_provenance_tag` — given a modeller output, asserts that every numeric leaf in `impact_data.modified_*` and `assumptions[*].amount` has a matching key in `source_tags`
- [x] T025 [P] [US2] Contract test `test_scenario_schema_invariants.py::test_modeller_tool_rejects_unprovenanced_output` — seeds the modeller's validate step with a tool output missing provenance; asserts a retry is triggered; on second failure, raises a domain exception
- [x] T026 [P] [US2] Integration test `backend/tests/integration/modules/tax_planning/test_analysis_endpoint_shape.py::test_analysis_response_includes_financials_data` — calls `GET /tax-plans/{id}/analysis`; asserts `financials_data` key present with `income`, `expenses`, `credits`, `projection_metadata`
- [x] T027 [P] [US2] Integration test `test_analysis_endpoint_shape.py::test_patch_assumption_flips_provenance` — PATCH `/scenarios/{id}/assumptions/{field_path}` with a new value; asserts `source_tags[field_path]` changes from `"estimated"` to `"confirmed"` and audit event `tax_planning.scenario.provenance_confirmed` is emitted

### Implementation for User Story 2

- [x] T028 [US2] Modify `backend/app/modules/tax_planning/schemas.py` — add `Provenance = Literal["confirmed","derived","estimated"]`, add `source_tags: dict[str, Provenance]` to `TaxScenarioResponse`, add `financials_data` and `projection_metadata` to `TaxPlanAnalysisResponse`
- [x] T029 [US2] Modify `backend/app/modules/tax_planning/agents/modeller.py` `_execute_tool` — validate that every numeric field in the tool input carries a `source` tag; if missing, retry once with an explicit "add provenance" instruction; if still missing, raise `ModellerProvenanceViolation`
- [x] T030 [US2] Modify `modeller.py` `CALCULATE_TAX_TOOL` (in `backend/app/modules/tax_planning/prompts.py`) schema — require `source` enum field on every numeric input; reject outputs that omit
- [x] T031 [US2] Modify `backend/app/modules/tax_planning/service.py` scenario persistence — compute `source_tags` dict from modeller output and write alongside `impact_data`/`assumptions` to the `TaxScenario` row
- [x] T032 [US2] Add new endpoint `PATCH /tax-plans/{plan_id}/scenarios/{scenario_id}/assumptions/{field_path}` in `backend/app/modules/tax_planning/router.py` — path per contracts/api-changes.md §4; service updates the JSON Pointer target in `impact_data`/`assumptions`, flips `source_tags[field_path]` to `"confirmed"`, emits audit event
- [x] T033 [US2] Add JSON Pointer helper `backend/app/modules/tax_planning/json_pointer.py` — tiny RFC 6901 parser/updater over dict trees (write + unit test in the same task; pure function)
- [x] T034 [US2] Modify `backend/app/modules/tax_planning/router.py` `GET /tax-plans/{plan_id}/analysis` to include `financials_data` and `projection_metadata` in the response per contracts/api-changes.md §2
- [x] T035 [P] [US2] Create `frontend/src/components/tax-planning/ProvenanceBadge.tsx` — renders a pill badge for each provenance value with colour tokens (confirmed=green, derived=neutral, estimated=amber)
- [x] T036 [P] [US2] Create `frontend/src/components/tax-planning/InlineConfirmInput.tsx` — controlled input wrapping shadcn `Input` with amber left border when provenance=estimated, on blur/Enter calls PATCH endpoint, flips badge to confirmed (per research.md R13)
- [x] T037 [US2] Modify `frontend/src/components/tax-planning/ComparisonTable.tsx` — render every numeric cell via `InlineConfirmInput` + `ProvenanceBadge` bound to `source_tags[json_pointer]`
- [x] T038 [US2] Modify `backend/app/modules/tax_planning/templates/tax_plan_export.html` — if any figure in the scenario has `source_tags.* === "estimated"` at export time, render a warning banner at the top and asterisk each affected figure (FR-016)

**Checkpoint**: US2 complete. Every AI-invented number is visible and controllable. The "$25k prepaid expenses" failure mode is eliminated.

---

## Phase 5: User Story 3 — Payroll data flows into the tax position automatically (Priority: P1)

**Goal**: Super YTD, PAYGW YTD, and the PAYGW credit populate correctly from Xero payroll on plan creation. On-demand sync is bounded to 15s synchronous; beyond that, background continuation with UI banner. Manual saves preserve Xero context.

**Independent Test**: Seed a Xero connection with payroll access + representative pay runs → create a tax plan → `credits.payg_withholding` equals sum of `total_tax_withheld_ytd` → Super YTD displays correctly. Force `has_payroll_access=False` → banner shows, not $0.

### Tests for User Story 3 (write first — must fail)

- [x] T039 [P] [US3] Integration test `backend/tests/integration/modules/tax_planning/test_payroll_sync_on_demand.py::test_paygw_credit_wired_from_payroll_summary` — seeds `XeroPayRun` fixtures with `total_tax_withheld_ytd=12000`; creates plan; asserts `financials_data.credits.payg_withholding == 12000`
- [x] T040 [P] [US3] Integration test `test_payroll_sync_on_demand.py::test_sync_within_15s_returns_ready` — mocks `sync_payroll` to complete in 2s; asserts plan response `payroll_sync_status == "ready"` and payroll summary populated
- [x] T041 [P] [US3] Integration test `test_payroll_sync_on_demand.py::test_sync_timeout_returns_pending_and_enqueues_background` — mocks `sync_payroll` to sleep 20s; asserts plan response `payroll_sync_status == "pending"`, Celery task enqueued, plan creation not blocked beyond 15s
- [x] T042 [P] [US3] Integration test `test_payroll_sync_on_demand.py::test_no_payroll_access_returns_unavailable` — connection with `has_payroll_access=False`; asserts `payroll_sync_status == "unavailable"`, no $0 silent fallback
- [x] T043 [P] [US3] Integration test `backend/tests/integration/modules/tax_planning/test_manual_save_preserves_context.py::test_manual_save_preserves_payroll_and_bank` — pre-populates plan with `payroll_summary`, `bank_balances`, `strategy_context`, `prior_years`; calls `save_manual_financials` with only `income`/`expenses` changes; asserts all other keys present and unchanged

### Implementation for User Story 3

- [x] T044 [US3] Modify `backend/app/modules/tax_planning/service.py` `_transform_xero_to_financials` — after computing `payroll_summary`, set `financials_data["credits"]["payg_withholding"] = payroll_summary["total_tax_withheld_ytd"]` (FR-007)
- [x] T045 [US3] Modify `service.py` `pull_xero_financials` to trigger payroll sync on-demand: wrap `sync_payroll(connection)` in `asyncio.wait_for(..., timeout=15.0)`; on `TimeoutError` enqueue `app.tasks.xero.sync_xero_payroll.delay(connection.id)` and set `financials_data["payroll_status"] = "pending"` (per research.md R3)
- [x] T046 [US3] Modify `service.py` `save_manual_financials` — switch from wholesale overwrite to deep-merge, preserving `payroll_summary`, `bank_balances`, `strategy_context`, `prior_years`, `projection_metadata` (FR-010); define constant `PRESERVED_CONTEXT_KEYS` at module top
- [x] T047 [US3] Modify `backend/app/modules/tax_planning/agents/scanner.py` `run()` user prompt builder — inline `payroll_summary.total_super_ytd` and `payroll_summary.total_tax_withheld_ytd` into the text context so the LLM actually sees them (FR-008)
- [x] T048 [US3] Modify `schemas.py` `TaxPlanResponse` to include `payroll_sync_status: Literal["ready","pending","unavailable","not_required"]`; wire it in `router.py` from the service computed state
- [x] T049 [US3] Add a recompute helper `service.recompute_tax_position(plan_id)` — re-runs `calculate_tax_position` against current `financials_data` and updates the stored `tax_position`; called by the Celery task post-sync
- [x] T050 [US3] Modify `backend/app/tasks/xero.py` `sync_xero_payroll` task — on completion, invoke `recompute_tax_position` for any tax plans created against this connection in the last 2 hours
- [x] T051 [US3] Add audit events: emit `tax_planning.payroll.sync_triggered` (success/timeout metadata), `tax_planning.payroll.unavailable` (when has_payroll_access=False), `tax_planning.manual_financials.saved` in their respective service paths
- [x] T052 [P] [US3] Create `frontend/src/components/tax-planning/PayrollSyncBanner.tsx` — renders an amber "Payroll still syncing — figures will refresh automatically" banner when `payroll_sync_status === "pending"`; a red "Payroll data unavailable — reconnect Xero with payroll scope" when `"unavailable"`. Polls `GET /tax-plans/{id}` every 3s (back off to 10s after 30s) when pending, 2-minute cap
- [x] T053 [P] [US3] Modify `frontend/src/components/tax-planning/FinancialsPanel.tsx` — render `PayrollSyncBanner`; remove the `{payroll_summary && ...}` silent-hide pattern so the banner always appears when status is non-ready

**Checkpoint**: US3 complete. Payroll data reaches tax plans reliably. Silent $0 failures impossible.

---

## Phase 6: User Story 4 — Multi-entity strategies do not silently mislead (Priority: P1)

**Goal**: Every scenario carries a `strategy_category` from the closed enum. Scenarios whose category is in `REQUIRES_GROUP_MODEL` persist with `requires_group_model=true` and render in a disabled state. Combined-strategy totals exclude flagged scenarios.

**Independent Test**: Trigger the modeller with a prompt suggesting trust distribution → resulting scenario has `strategy_category="trust_distribution"`, `requires_group_model=true`; UI renders disabled notice; combined total excludes this scenario.

### Tests for User Story 4 (write first — must fail)

- [x] T054 [P] [US4] Contract test `backend/tests/contract/modules/tax_planning/test_scenario_schema_invariants.py::test_every_scenario_has_strategy_category` — seeds modeller output; asserts `strategy_category` present and a valid enum value
- [x] T055 [P] [US4] Integration test `backend/tests/integration/modules/tax_planning/test_group_model_flag.py::test_multi_entity_category_sets_requires_group_model` — seeds a modeller output with `strategy_category="trust_distribution"`; asserts persisted scenario has `requires_group_model=true`
- [x] T056 [P] [US4] Integration test `test_group_model_flag.py::test_single_entity_category_not_flagged` — seeds a modeller output with `strategy_category="prepayment"`; asserts `requires_group_model=false`
- [x] T057 [P] [US4] Integration test `test_group_model_flag.py::test_combined_total_excludes_flagged_scenarios` — plan has 2 scenarios (1 flagged, 1 not); asserts `combined_strategy.total_tax_saving` reflects only the unflagged scenario and response indicates exclusion

### Implementation for User Story 4

- [x] T058 [US4] Modify `backend/app/modules/tax_planning/agents/prompts.py` modeller/scanner system prompts — add the `strategy_category` enum values and instruct the LLM to emit one with every scenario; reject/retry on invalid categories
- [x] T059 [US4] Modify `backend/app/modules/tax_planning/agents/modeller.py` `_execute_tool` — validate `strategy_category` parses to the enum; on failure retry once, then fall back to `other`
- [x] T060 [US4] Modify `backend/app/modules/tax_planning/service.py` scenario persistence — set `TaxScenario.strategy_category` from modeller output and compute `requires_group_model = strategy_category.requires_group_model(cat)` (never trust LLM for the boolean)
- [x] T061 [US4] Modify `backend/app/modules/tax_planning/agents/orchestrator.py` `_compute_combined_strategy` — exclude scenarios with `requires_group_model=true` from the sum; include a `"excluded_count": N` field in the combined strategy output
- [x] T062 [US4] Emit audit event `tax_planning.scenario.requires_group_model_flag` at the flag-setting site
- [x] T063 [P] [US4] Create `frontend/src/components/tax-planning/RequiresGroupModelNotice.tsx` — disabled-state wrapper with copy "Multi-entity strategy — precise benefit requires the group tax model (coming soon)"
- [x] T064 [P] [US4] Modify `frontend/src/components/tax-planning/ComparisonTable.tsx` — wrap scenarios where `requires_group_model=true` in `RequiresGroupModelNotice`; show subtotal row "N scenario(s) excluded — requires group model"
- [x] T065 [US4] Modify `schemas.py` / `types/tax-planning.ts` — add `strategy_category: StrategyCategory` and `requires_group_model: boolean` to scenario response shapes (per contracts/api-changes.md §3)

**Checkpoint**: US4 complete. Multi-entity strategies surface transparently as "coming soon" rather than producing misleading single-entity net-benefit figures.

---

## Phase 7: User Story 5 — The reviewer catches errors, not rubber-stamps them (Priority: P1)

**Goal**: Reviewer computes an independent ground-truth re-derivation from raw confirmed inputs and compares scenarios against it with $1 tolerance. Disagreements report specific field + delta. UI warns prominently but does not block rendering.

**Independent Test**: Inject a deliberately wrong modeller output (e.g. `before.tax_payable` off by $1000); assert reviewer returns `numbers_verified=false` with the exact field and delta; assert UI renders banner + per-scenario badge.

### Tests for User Story 5 (write first — must fail)

- [x] T066 [P] [US5] Unit test `backend/tests/unit/modules/tax_planning/test_ground_truth.py::test_compute_ground_truth_matches_calculator` — same inputs as the existing calculator test suite; asserts `compute_ground_truth` agrees within $1
- [x] T067 [P] [US5] Unit test `test_ground_truth.py::test_ground_truth_ignores_cached_base_financials` — call signature accepts only raw `financials_data`; no parameter named `base_financials`
- [x] T068 [P] [US5] Integration test `backend/tests/integration/modules/tax_planning/test_reviewer_independent.py::test_reviewer_detects_injected_error` — patches modeller to emit a scenario with `before.tax_payable` off by $1000; asserts `review_result.numbers_verified=false` and `disagreements[0]` identifies the field and delta
- [x] T069 [P] [US5] Integration test `test_reviewer_independent.py::test_reviewer_passes_on_correct_modeller_output` — correct modeller output; asserts `numbers_verified=true`, `disagreements=[]`
- [x] T070 [P] [US5] Integration test `test_reviewer_independent.py::test_subdollar_delta_does_not_fail_review` — inject a $0.50 delta; asserts review passes (tolerance)

### Implementation for User Story 5

- [x] T071 [US5] Add `compute_ground_truth(financials_data, rate_configs, has_help_debt) -> GroundTruth` pure function to `backend/app/modules/tax_planning/tax_calculator.py` — re-derives taxable income from raw `income.total_income`, `expenses.total_expenses`, `adjustments`; calls existing per-entity tax functions; returns `GroundTruth` dataclass
- [x] T072 [US5] Rewrite `backend/app/modules/tax_planning/agents/reviewer.py::_verify_calculator_numbers` — for each scenario, compute ground-truth `before` from raw `financials_data`; compare against `scenario.impact_data.before.*` with $1 tolerance; populate `disagreements: list[{scenario_id, field_path, expected, got, delta}]`; set `numbers_verified` accordingly
- [x] T073 [US5] Modify `backend/app/modules/tax_planning/schemas.py` `ReviewResult` — add `disagreements: list[ReviewerDisagreement]` field (per contracts/api-changes.md §6)
- [x] T074 [US5] Emit audit event `tax_planning.review.verification_failed` for each disagreement
- [x] T075 [P] [US5] Create `frontend/src/components/tax-planning/ReviewerWarningBanner.tsx` — top-of-page amber banner when `review_result.numbers_verified=false`, listing affected scenarios + fields + deltas
- [x] T076 [P] [US5] Modify `frontend/src/components/tax-planning/ComparisonTable.tsx` — per-scenario badge showing "Verification flagged: {field} differs by ${delta}" when the scenario has an entry in `disagreements`

**Checkpoint**: US5 complete. The reviewer is no longer a rubber stamp — injected errors are caught with specificity.

---

## Phase 8: User Story 6 — Source citations verify reliably (Priority: P2)

**Goal**: Citation verifier uses the existing knowledge-module verifier (with chunk-body fallback). Confidence-score key bug fixed. UI distinguishes `low_confidence` from other states. Streaming race fixed.

**Independent Test**: Seed knowledge base with known chunks → prompt the agent with a question that cites those chunks → verifier marks citations `verified` via chunk-body match → confidence score > 0.5 → UI shows the actual response, not the canned decline.

### Tests for User Story 6 (write first — must fail)

- [ ] T077 [P] [US6] Contract test `backend/tests/contract/modules/tax_planning/test_citation_verification_contract.py::test_confidence_score_reads_relevance_score_key` — passes chunks with `relevance_score` field; asserts `confidence_score > 0` (catches the dict-key regression)
- [ ] T078 [P] [US6] Contract test `test_citation_verification_contract.py::test_low_confidence_status_present_in_enum` — asserts the Pydantic schema and frontend enum both include `"low_confidence"`
- [ ] T079 [P] [US6] Integration test `backend/tests/integration/modules/tax_planning/test_citation_body_match.py::test_citation_verifies_via_chunk_body` — chunk has `section_ref="Div 43"` and body text containing "s25-10"; AI response cites `[Source: s25-10 ITAA 1997]`; asserts verified via body-text fallback
- [ ] T080 [P] [US6] Integration test `test_citation_body_match.py::test_hallucinated_citation_remains_unverified` — AI cites `[Source: TR 2026/99]` that exists in no chunk; asserts status=`unverified` (permissive loophole not introduced)
- [ ] T081 [P] [US6] Integration test `test_citation_body_match.py::test_streaming_verification_event_before_done` — SSE event log from a streaming chat response; asserts `verification` event arrives before `done`

### Implementation for User Story 6

- [x] T082 [US6] Hotfix: change `c.get("score", 0.0)` → `c.get("relevance_score", 0.0)` at `backend/app/modules/tax_planning/service.py:1057`. This can be cherry-picked ahead of the rest of US6.
- [x] T083 [US6] Replace `_build_citation_verification` body at `backend/app/modules/tax_planning/service.py:888-958` with a thin wrapper that calls `knowledge.retrieval.citation_verifier.verify_citations(response_content, retrieved_chunks)` and shapes output to `CitationVerificationResult`
- [x] T084 [US6] Modify `backend/app/modules/tax_planning/schemas.py` `CitationVerification.status` to include `"low_confidence"`; ensure every path that sets status matches the enum
- [x] T085 [US6] Modify `backend/app/modules/tax_planning/service.py` streaming chat path — yield the `verification` event **before** `done` (fix the race documented in research.md / spec)
- [x] T086 [P] [US6] Modify `frontend/src/types/tax-planning.ts` `CitationVerificationStatus` to include `"low_confidence"`
- [x] T087 [P] [US6] Modify `frontend/src/components/tax-planning/CitationBadge.tsx` — add amber-coloured variant for `"low_confidence"` with copy "AI declined — low source confidence"
- [x] T088 [US6] Modify `frontend/src/components/tax-planning/ScenarioChat.tsx` — handle `verification` event regardless of arrival order relative to `done`; update the rendered message when verification arrives even after `done` (belt-and-braces for legacy stream orderings)
- [x] T089 [US6] Emit audit event `tax_planning.citation.verification_outcome` with matched-by breakdown

**Checkpoint**: US6 complete. Legitimate citations are recognised, canned declines stop replacing good responses, low-confidence state is distinguishable.

---

## Phase 9: User Story 7 — No pre-Stage-3 rate language leaks to the LLM (Priority: P2)

**Goal**: All prompt modules are free of `"32.5"`, `"19%"`, `"$120,000"`, `"$120k"`. A CI-gate contract test enforces this. Tax-planning system prompt contains an explicit Stage-3 grounding block.

**Independent Test**: Run the contract test; it passes on this branch and will fail if any of the forbidden strings are re-introduced.

### Tests for User Story 7 (write first — must fail)

- [x] T090 [P] [US7] Contract test `backend/tests/contract/modules/tax_planning/test_prompt_stage3_scan.py::test_no_pre_stage3_strings_in_prompt_modules` — walks `backend/app/modules/tax_planning/**/*.py` and `backend/app/modules/agents/**/*.py`; reads each file; asserts none contain `"32.5"`, `"19%"` (word-boundary regex), `"$120,000"`, `"$120k"`. Whitelist the test file itself.
- [x] T091 [P] [US7] Contract test `test_prompt_stage3_scan.py::test_tax_planning_system_prompt_grounds_stage3` — asserts `TAX_PLANNING_SYSTEM_PROMPT` contains all four current thresholds: `"18,200"`, `"45,000"`, `"135,000"`, `"190,000"`

### Implementation for User Story 7

- [x] T092 [US7] Edit `backend/app/modules/agents/prompts.py:170` — replace `"(potentially 32.5%+)"` with `"(currently 30%+ at FY2025-26 brackets)"` or equivalent Stage-3-correct language
- [x] T093 [US7] Edit `backend/app/modules/agents/prompts.py:181` — replace the `"marginal tax rate ~32.5%"` worked example with a Stage-3-correct phrasing (e.g. `"marginal tax rate ~30%"`)
- [x] T094 [US7] Add a Stage-3 grounding block to `backend/app/modules/tax_planning/prompts.py` `TAX_PLANNING_SYSTEM_PROMPT` listing the four current brackets and thresholds verbatim
- [x] T095 [US7] Edit `backend/tests/factories/tax_planning.py:34` — change `tax_rate: 0.325` → `tax_rate: 0.30` (Stage-3 equivalent middle band)
- [x] T096 [US7] Run the contract test — must pass green on this branch

**Checkpoint**: US7 complete. The prompt-scan gate ensures pre-Stage-3 strings cannot be re-introduced.

---

## Phase 10: User Story 8 — Duplicate scenarios do not accumulate (Priority: P2)

**Goal**: Scenarios are unique by `(plan_id, normalised_title)` at the DB level. Upsert semantics used for persistence. Chat prompt instructs the LLM not to replay existing titles.

**Independent Test**: Issue two chat prompts that each produce a scenario with the same normalised title; assert only one persisted row, with the latest content.

### Tests for User Story 8 (write first — must fail)

- [x] T097 [P] [US8] Integration test `backend/tests/integration/modules/tax_planning/test_scenario_upsert.py::test_same_normalized_title_updates_existing_row` — persist "Prepay rent"; persist "  PREPAY RENT  "; assert only one row exists with the same UUID, latest content applied
- [x] T098 [P] [US8] Integration test `test_scenario_upsert.py::test_unique_constraint_enforced_at_db_level` — attempt a raw INSERT that would violate the constraint; asserts `IntegrityError` raised

### Implementation for User Story 8

- [x] T099 [US8] Add `TaxScenarioRepository.upsert_by_normalized_title(plan_id, tenant_id, title, payload) -> TaxScenario` in `backend/app/modules/tax_planning/repository.py` — uses SQLAlchemy `insert().on_conflict_do_update(index_elements=[...], set_={...})` against the new unique index (per research.md R8)
- [x] T100 [US8] Modify `backend/app/modules/tax_planning/service.py` scenario persistence paths (both streaming and non-streaming chat) — switch from `scenario_repo.create` to `scenario_repo.upsert_by_normalized_title`
- [x] T101 [US8] Modify `backend/app/modules/tax_planning/prompts.py` chat system prompt — add the rule: "If the user's request refines an existing scenario in the conversation history (shown in scenarios_history), update that scenario rather than emitting a new one with a similar title."
- [x] T102 [P] [US8] Verify frontend `ComparisonTable.tsx` keys by `scenario.id` (UUID is stable across upsert) — this should already be correct; sanity-check no code regressed during prior phases

**Checkpoint**: US8 complete. Scenario clutter in the Scenarios tab is structurally prevented.

---

## Phase 11: Polish — Golden dataset E2E + cross-cutting

**Purpose**: Capstone — the regression gate Unni asked for. Plus final lint/typecheck and any cross-cutting fixes.

- [x] T103 [P] Create `backend/tests/e2e/tax_planning/__init__.py` + `fixtures/` directory
- [x] T104 [P] Create `backend/tests/e2e/tax_planning/test_golden_dataset.py` harness: parametrised over all fixtures in `fixtures/*.json`; loads the fixture inputs, seeds a fake Xero client, creates a plan end-to-end, runs the full analysis pipeline with `FakeAnthropicClient`, asserts every expected number within $1 (per research.md R10, quickstart.md)
- [x] T105 [P] Create `backend/tests/e2e/tax_planning/fixtures/zac_phillpott.json` — sanitised from Unni's alpha-session notes; if Unni's numbers aren't ready at commit time, commit the harness with a `@pytest.mark.skipif(not fixture_exists)` marker and unblock once fixture arrives
- [x] T106 [P] Sync `docs/solution-design.md` and `docs/xero-api-mapping.md` with the new `projection_metadata`, `strategy_category`, and payroll-sync-on-demand behaviours
- [x] T107 [P] Update `.claude/CLAUDE.md` "Common Mistakes" section with three new entries: (1) annualisation lives at ingest, don't re-project downstream; (2) every scenario numeric field must have a `source_tags` entry; (3) use `TaxScenarioRepository.upsert_by_normalized_title`, never raw `create`
- [x] T108 Full validation — run `cd backend && uv run ruff check . && uv run pytest && cd ../frontend && npm run lint && npx tsc --noEmit`. All green before PR.
- [ ] T109 Manual dogfood on a local dev environment — create a tax plan against a seeded Xero connection, run an analysis, confirm an estimated figure inline, observe provenance badges, observe reviewer banner on injected error, observe payroll banner on forced slow sync

---

## Phase 12: Remediation tasks (from `/speckit.analyze`)

**Purpose**: Close coverage gaps identified by the cross-artefact analysis pass. All are test-or-CI-gate additions; none change product behaviour. Execute alongside the phase each augments.

- [x] T110 [P] [US6] Augments Phase 8. Create `backend/tests/e2e/tax_planning/fixtures/citation_regression_bank.yaml` containing 20 scripted accountant questions with their expected citation properties (should-be-verified status, expected ruling references). Create `backend/tests/e2e/tax_planning/test_citation_regression_bank.py` that runs the bank through the AI pipeline with `FakeAnthropicClient` and asserts the decline rate ≤ 1 / 20 (SC-008)
- [x] T111 [P] [US2] Augments Phase 4. Integration test `backend/tests/integration/modules/tax_planning/test_export_provenance.py::test_export_warns_when_estimated_figures_remain` — generate an analysis with at least one `source_tags.*=="estimated"`; render the PDF (or HTML template) via the existing export path; assert the warning banner is present and each affected figure is flagged (FR-016)
- [x] T112 [P] [US3] Augments Phase 5. Test `backend/tests/integration/modules/tax_planning/test_payroll_sync_on_demand.py::test_scanner_prompt_contains_super_and_paygw` — seed payroll summary with known super/PAYGW totals; run the scanner; assert the rendered user prompt string contains both values (FR-008)
- [x] T113 [P] [US7] Augments Phase 9. Extend `backend/tests/contract/modules/tax_planning/test_prompt_stage3_scan.py::test_factory_uses_stage3_rates` — additionally scan `backend/tests/factories/tax_planning.py` and assert it does not contain `"0.325"` (FR-029)
- [x] T114 Augments Phase 11. Update `.github/workflows/backend-ci.yml` (or the equivalent CI config) to include `backend/tests/e2e/tax_planning/` in the required-check test paths so golden-dataset regressions block merges (SC-004)

**Checkpoint**: All HIGH and MEDIUM findings from the analyze report are addressed. Coverage → 100% direct.

---

## Phase FINAL: PR & Merge

- [ ] TFINAL-1 Ensure all tests pass — `cd backend && uv run pytest`
- [ ] TFINAL-2 Run linters — `cd backend && uv run ruff check . && cd ../frontend && npm run lint && npx tsc --noEmit`
- [ ] TFINAL-3 Push feature branch and create PR:
  - `git push -u origin 059-tax-planning-calculation-correctness`
  - `gh pr create --title "Spec 059: Tax Planning Calculation Correctness" --body "$(cat <<'EOF'
## Summary
Ground-truth correctness audit for tax planning. Fixes seven P0 data-accuracy bugs surfaced by Unni in the alpha session; adds a golden-dataset regression gate so they can't recur.

## User Stories Shipped
- US1 (P1): Annualised figures at ingest — single source of numbers
- US2 (P1): Provenance tags on every AI-emitted figure + inline confirm
- US3 (P1): Payroll data wiring + bounded on-demand sync
- US4 (P1): Multi-entity honesty flag
- US5 (P1): Independent reviewer (no more rubber-stamp)
- US6 (P2): Citation verifier swap + `relevance_score` hotfix
- US7 (P2): Pre-Stage-3 prompt-scan CI gate
- US8 (P2): Scenario dedup at DB level

## Test Coverage
- Golden-dataset E2E regression gate (Zac Phillpott fixture)
- Integration tests for every wiring bug
- Contract tests for prompt rate strings + schema invariants

## Deployment notes
Migration 20260418_059 adds 3 columns + 1 unique index to tax_scenarios. Safe to run online; back-fills defaults, disambiguates pre-existing duplicate titles.
EOF
)"`
- [ ] TFINAL-4 Address PR review feedback (iterate until approved)
- [ ] TFINAL-5 Squash-merge PR to main; delete feature branch
- [ ] TFINAL-6 Update `specs/ROADMAP.md` — mark spec 059 COMPLETE; flag spec 060 (Group Tax Model) as next

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)** → **Phase 2 (Foundational)** → user stories
- **US1, US2, US3, US4, US5** are P1 and largely independent after Foundational; US5 depends on US1 being mostly done (uses annualised figures as ground truth for scenarios). US4 depends on the `strategy_category` enum from Phase 1.
- **US6, US7, US8** are P2 and can run in parallel with any P1 after Foundational
- **Phase 11 (Polish)** depends on all user stories being complete
- **Phase FINAL** depends on Phase 11

### Within each user story

- Tests first (must fail)
- Models / schemas before services
- Services before endpoints / UI
- Integration + audit wiring last

### Parallel opportunities

- **Phase 1**: T002 and T003 are `[P]` (different files, no dependencies)
- **Phase 2**: T006, T007 are `[P]`; T009, T010 are `[P]`
- **Each user story**: all `[US?]`-tagged tests are `[P]` (different files); frontend components within a story are `[P]` relative to backend service changes
- **Across stories**: after Foundational, US1 / US3 / US6 / US7 / US8 can proceed in parallel by different developers. US2 depends on US1 for the Analysis endpoint shape change. US4 depends on the strategy_category enum (shipped in Foundational). US5 depends on US1's ground-truth alignment.

---

## Parallel Example: User Story 1

```bash
# After Foundational complete, launch US1 tests in parallel:
Task: "Integration test test_6_months_of_data_gets_annualised in backend/tests/integration/modules/tax_planning/test_ingest_annualisation.py"
Task: "Integration test test_12_months_of_data_is_not_annualised in same file"
Task: "Integration test test_manual_financials_treated_as_confirmed_full_year in same file"
Task: "Integration test test_prompt_contains_only_annualised_totals in same file"
Task: "Integration test test_tax_position_uses_annualised_totals in same file"

# Note: these share a file, so can be authored in one pass rather than truly concurrent;
# the [P] marker reflects parallelisability with tests of *other* stories.

# Frontend work runs in parallel with backend service edits:
Task: "Modify TaxPositionCard.tsx to render projection chip"  # [P]
Task: "Modify types/tax-planning.ts"                          # [P]
```

---

## Implementation Strategy

### MVP First (Single-session goal)

1. Complete **Phase 1** (Setup) + **Phase 2** (Foundational). 1-2 days.
2. Complete **US1** (Phase 3) + **US3** (Phase 5). These two together restore correctness at ingest — the minimum needed to stop silent wrong numbers. 2-3 days.
3. **STOP and VALIDATE**: run the golden-dataset fixture (Phase 11 harness) — numbers should match ChangeGPS for Zac's inputs. If they do, we can run another alpha session.

### Incremental Delivery (prioritised)

1. Foundational → **US1 + US3** (correctness at ingest) → ship to alpha cohort
2. Add **US2 + US5** (provenance + independent reviewer) → ship
3. Add **US4** (multi-entity honesty flag) → ship
4. Add **US6 + US7 + US8** (citation, prompt currency, dedup — quality polish) → ship
5. Land the golden-dataset E2E gate (Phase 11) throughout; do not defer to the end

### Critical Path

**Phase 2 → US1 → US5 → Phase 11** is the critical correctness path. Shipping US1 + US5 + the golden-dataset gate is the minimum viable "we can run live sessions again" state.

### Parallel Team Strategy

With two engineers:
- Engineer A: Phase 2, then US1 → US3 → US5 (correctness backbone)
- Engineer B: US2 (provenance plumbing) → US4 (honesty flag) → US6/US7/US8 (polish)
- Both converge on Phase 11 and TFINAL together

---

## Notes

- **File-path discipline**: every task cites an absolute or repo-relative path so an executor can open it without guessing.
- **Test-first**: every story's tests precede implementation tasks in the task list order. Run tests, confirm failure, implement, confirm green.
- **Audit parity**: every user-visible state change emits an audit event listed in data-model.md §Audit event payload shapes. Missing events = incomplete task.
- **Frontend-backend parity**: every enum change ships on both sides in the same story. Don't let TypeScript drift from Python.
- **Golden dataset is the gate**: the spec is not done when tests pass — it's done when the Zac fixture matches ChangeGPS within $1.
