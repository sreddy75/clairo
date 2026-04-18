# Implementation Plan: Tax Planning — Calculation Correctness

**Branch**: `059-tax-planning-calculation-correctness` | **Date**: 2026-04-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/059-tax-planning-calculation-correctness/spec.md`

## Summary

Close the ground-truth gap between Xero data ingestion, the deterministic tax calculator, the multi-agent scenario pipeline, and the UI. The calculator itself is correct; every known bug lives in the layers above it. This plan delivers: (1) a single linear annualisation step applied at ingest so only one financials shape exists downstream, (2) payroll data wired into the tax-credit path with a bounded on-demand sync, (3) provenance tags on every AI-emitted numeric field plus inline edit-to-confirm UX, (4) a `strategy_category` enum that powers a "requires group model" honesty flag, (5) an independent deterministic reviewer, (6) a citation-verifier swap to the existing knowledge-module implementation plus the `relevance_score` key fix, (7) a prompt-scan contract test that blocks pre-Stage-3 rate strings, (8) a normalised-title uniqueness constraint with upsert scenarios, and (9) a golden-dataset end-to-end regression gate seeded from Unni's Zac Phillpott alpha session.

The strategy: minimal schema churn (three small columns, one unique index, no new tables), surgical edits at six well-identified wiring sites, and a new test layer that will have caught every one of these bugs on the next PR if it had existed on the last.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic, Anthropic SDK, Voyage 3.5 lite, Pinecone (for citation verifier swap), React 18 + shadcn/ui
**Storage**: PostgreSQL 16 — 3 new columns on `tax_scenarios`, 1 new partial-unique index on `tax_scenarios`, 1 new key on `tax_plans.financials_data` JSONB (`projection_metadata`). No new tables.
**Testing**: pytest + pytest-asyncio, factory_boy, httpx AsyncClient for integration tests. Deterministic fake Anthropic client for agent tests.
**Target Platform**: Linux server (backend via Docker), Vercel (frontend)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Payroll on-demand sync bounded to 15 seconds synchronously (FR-006); tax plan creation end-to-end ≤ 3s p95 when payroll cache is warm; contract tests add ≤ 10s to CI.
**Constraints**: No new Pinecone indexes or namespaces; reuse existing `knowledge/retrieval/citation_verifier.py` (no reinvention); no new database tables; maintain backward compatibility for existing TaxPlan records (migration back-fills metadata).
**Scale/Scope**: ~ 32 functional requirements, 8 user stories, ~10 new integration test cases, 1 new golden-dataset E2E fixture, 2 new contract tests (prompt-scan + schema-invariants).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Layer ordering (L3 after L1/L2) | PASS | L3/L4 feature fixing a shipped L3 feature. L1/L2 complete. |
| Modular monolith boundaries | PASS | `tax_planning` module internally modified; `knowledge.retrieval.citation_verifier` called via its public service interface (constitution §I). |
| Repository pattern | PASS | `TaxScenarioRepository.upsert_by_normalized_title` added via existing repo. No cross-module DB access. |
| Multi-tenancy (`tenant_id`) | PASS | All affected tables already scope by `tenant_id`. Unique index includes `tax_plan_id` which is tenant-scoped. |
| Audit trail (§X) | PASS | 8 new audit events defined in spec, implemented via existing `@audited` decorator + `audit_event()` helper. |
| Human-in-the-loop (§XI) | PASS | Provenance + inline confirm is a direct strengthening of this principle. No autonomous AI writes without human gate. |
| Source citations on all answers (§XI) | PASS | Citation verifier fix strengthens this; no regression. |
| RAG retrieval < 3 seconds | PASS | Verifier change is a matcher swap; no added retrieval. |
| Testing coverage targets (§V) | PASS | Golden-dataset E2E, integration wiring tests, prompt-scan contract test, reviewer error-injection tests — all planned. |
| No HTTPException in services (§VI) | PASS | New service-layer errors use existing domain exception pattern. |
| No tax advice (§XI) | PASS | Unchanged — provenance actually reduces advice-like fabrication risk. |

**Post-Phase 1 re-check**: PASS — Design uses existing modules via service interfaces, no new cross-module coupling introduced, migration is backward-compatible.

## Project Structure

### Documentation (this feature)

```text
specs/059-tax-planning-calculation-correctness/
├── plan.md                 # This file
├── spec.md                 # Feature specification (clarified)
├── research.md             # Phase 0 research output
├── data-model.md           # Phase 1 data model
├── quickstart.md           # Phase 1 developer quickstart
├── contracts/
│   └── api-changes.md      # API contract changes (endpoints, schemas)
└── checklists/
    └── requirements.md     # Spec quality checklist
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── modules/
│   │   ├── tax_planning/
│   │   │   ├── tax_calculator.py       # MODIFIED: add compute_ground_truth() independent re-derivation
│   │   │   ├── projection.py           # NEW: linear annualisation helper (isolable, easily testable)
│   │   │   ├── service.py              # MODIFIED: annualise at ingest, on-demand bounded payroll sync, wire payg_withholding credit, preserve manual-save context
│   │   │   ├── agent.py                # MODIFIED: enforce provenance in tool schema, dedupe via upsert
│   │   │   ├── agents/
│   │   │   │   ├── modeller.py         # MODIFIED: strategy_category + source_tags on every tool output
│   │   │   │   ├── scanner.py          # MODIFIED: inline payroll into prompt, emit strategy_category
│   │   │   │   ├── reviewer.py         # MODIFIED: call compute_ground_truth; report field+delta on disagreement
│   │   │   │   ├── orchestrator.py     # MODIFIED: propagate verification result unchanged (don't block render)
│   │   │   │   ├── advisor.py          # MODIFIED: render provenance badges inline
│   │   │   │   └── prompts.py          # MODIFIED: remove "32.5%", add Stage-3 grounding, instruct enum usage
│   │   │   ├── prompts.py              # MODIFIED: Stage-3 grounding block; single-set-of-numbers in context
│   │   │   ├── strategy_category.py    # NEW: enum + requires_group_model mapping
│   │   │   ├── models.py               # MODIFIED: add strategy_category, requires_group_model, source_tags on TaxScenario; unique index
│   │   │   ├── schemas.py              # MODIFIED: add provenance + category fields; analysis response includes financials_data
│   │   │   ├── repository.py           # MODIFIED: TaxScenarioRepository.upsert_by_normalized_title
│   │   │   ├── audit_events.py         # MODIFIED: add 8 new event types
│   │   │   └── router.py               # MODIFIED: PATCH /scenarios/{id}/assumption endpoint; analysis response shape
│   │   ├── knowledge/
│   │   │   └── retrieval/
│   │   │       └── citation_verifier.py # USED AS-IS: swap tax_planning to call this
│   │   └── integrations/xero/
│   │       └── payroll_service.py       # USED AS-IS: called with asyncio.wait_for(15)
│   ├── core/
│   │   └── audit.py                    # USED AS-IS
│   └── tasks/
│       └── xero.py                     # USED AS-IS: background continuation of payroll sync
├── alembic/versions/
│   └── 20260418_059_tax_planning_correctness.py  # NEW: 3 columns + 1 partial unique index
└── tests/
    ├── unit/modules/tax_planning/
    │   ├── test_projection.py                   # NEW: linear annualisation unit tests
    │   ├── test_strategy_category.py            # NEW: enum mapping tests
    │   ├── test_ground_truth.py                 # NEW: independent re-derivation tests
    │   └── test_tax_calculator.py               # EXISTING: unchanged (still valuable)
    ├── integration/modules/tax_planning/
    │   ├── test_ingest_annualisation.py         # NEW: YTD → projected wiring
    │   ├── test_payroll_sync_on_demand.py       # NEW: 15s timeout, credit wiring, unavailable states
    │   ├── test_manual_save_preserves_context.py # NEW: FR-010
    │   ├── test_scenario_upsert.py              # NEW: dedupe semantics
    │   ├── test_reviewer_independent.py         # NEW: inject error, assert disagreement
    │   └── test_analysis_endpoint_shape.py      # NEW: confirmed financials included
    ├── contract/modules/tax_planning/
    │   ├── test_prompt_stage3_scan.py           # NEW: CI gate for pre-Stage-3 strings
    │   ├── test_scenario_schema_invariants.py   # NEW: provenance + category required
    │   └── test_citation_verification_contract.py # NEW: relevance_score fix + low_confidence status
    └── e2e/tax_planning/
        ├── fixtures/
        │   └── zac_phillpott.json               # NEW: golden dataset (sanitised)
        └── test_golden_dataset.py               # NEW: full pipeline $1 tolerance

frontend/
├── src/
│   ├── components/
│   │   └── tax-planning/
│   │       ├── ProvenanceBadge.tsx              # NEW: confirmed/derived/estimated visual treatment
│   │       ├── InlineConfirmInput.tsx           # NEW: prefilled input, edit-to-confirm (FR-015)
│   │       ├── ReviewerWarningBanner.tsx        # NEW: top-of-page + per-scenario verification badge
│   │       ├── RequiresGroupModelNotice.tsx     # NEW: disabled-state explainer
│   │       ├── PayrollSyncBanner.tsx            # NEW: "payroll still syncing" banner
│   │       ├── CitationBadge.tsx                # MODIFIED: add low_confidence status
│   │       ├── ScenarioChat.tsx                 # MODIFIED: fix verification-event timing
│   │       ├── ComparisonTable.tsx              # MODIFIED: render provenance + group-model flag
│   │       ├── TaxPositionCard.tsx              # MODIFIED: show projection metadata ("Projected from X months")
│   │       └── FinancialsPanel.tsx              # MODIFIED: payroll banner + unavailable state
│   └── types/
│       └── tax-planning.ts                      # MODIFIED: add source_tags, strategy_category, requires_group_model, low_confidence
```

**Structure Decision**: Standard Clairo modular monolith (constitution §I). All backend changes live inside the existing `tax_planning` module except a single call out to `knowledge/retrieval/citation_verifier.py` via its public interface. Frontend changes live inside the existing `components/tax-planning/` folder. One new Alembic migration. The `projection.py` and `strategy_category.py` new files exist solely to keep those concerns isolated and unit-testable without loading the full service stack — both are essentially pure functions over data.

## Implementation Phases

### Phase 1 — Ground truth at ingest (P1 — Stories 1, 3)

Establishes the "one set of numbers" invariant. Nothing else is trustworthy until this lands.

1. **Migration**: `projection_metadata` key convention on `TaxPlan.financials_data` JSONB (no schema change — just documented contract). Alembic migration adds `strategy_category`, `requires_group_model`, `source_tags` columns to `tax_scenarios` plus the partial unique index `(tax_plan_id, lower(trim(title)))`. Back-fill: existing scenarios get `strategy_category='other'`, `requires_group_model=false`, `source_tags={}`.
2. **`projection.py`**: pure function `annualise_linear(ytd_totals, months_elapsed)` returning projected totals + metadata record.
3. **`service.py`** `pull_xero_financials` / `_transform_xero_to_financials` / `save_manual_financials`:
   - Apply annualisation in the Xero path when `months_elapsed < 12`; write `projection_metadata` (months_elapsed, months_projected, rule='linear', ytd_snapshot).
   - Manual path: treat as confirmed full-year, set `projection_metadata={applied: false, reason: 'manual_full_year'}`.
   - Manual save preserves `payroll_summary`, `bank_balances`, `strategy_context`, `prior_years` by merging rather than overwriting.
4. **`prompts.py`**: delete `projection` parallel block; only one set of numbers appears in `format_financial_context`. Add explicit Stage-3 grounding block.
5. **Payroll wiring**: in `_transform_xero_to_financials`, propagate `payroll_summary.total_tax_withheld_ytd` → `credits.payg_withholding`. Inline super + PAYGW totals into the scanner's user prompt.
6. **On-demand bounded sync**: at plan creation, if `has_payroll_access=True` and `last_payroll_sync > 24h` or None, kick `sync_payroll` inside `asyncio.wait_for(15)`. On timeout: return 202-ish "payroll pending" via plan-creation response, enqueue background Celery task, frontend renders banner. Re-computation on completion is triggered by an existing event bus signal or short polling — specific channel chosen in research.md.
7. **Tests**: unit `test_projection.py`; integration `test_ingest_annualisation.py`, `test_payroll_sync_on_demand.py`, `test_manual_save_preserves_context.py`.

### Phase 2 — Provenance + inline confirm (P1 — Story 2)

Makes AI-invented figures visible and controllable.

1. **`models.py`** `TaxScenario.source_tags`: JSONB of shape `{field_path: provenance_enum}` e.g. `{"modified_expenses.operating_expenses": "estimated", "assumptions[0].amount": "estimated"}`.
2. **`schemas.py`**: `ScenarioAssumption` gains `source: Literal["confirmed","derived","estimated"]` and `baseline_ref: str | None`. Analysis response shape adds `financials_data` alongside the AI blocks.
3. **`agents/modeller.py`**: tool schema requires provenance on every numeric input; tool-result post-validation rejects unprovenanced outputs and asks the model to retry once.
4. **`router.py`**: new `PATCH /tax-plans/{plan_id}/scenarios/{scenario_id}/assumptions/{field_path}` — body carries `{value: number}`. Service sets the field to `confirmed` with the supplied value; writes `tax_planning.scenario.provenance_confirmed` audit event.
5. **Frontend**: `ProvenanceBadge.tsx`, `InlineConfirmInput.tsx`. `ComparisonTable.tsx` uses them for every numeric cell. Export path (PDF template) reads `source_tags`; if any `estimated` remain, export renders a warning banner at the top and flags each affected figure (FR-016).
6. **Tests**: contract `test_scenario_schema_invariants.py` asserts every numeric scenario field has a provenance tag; integration `test_analysis_endpoint_shape.py` asserts financials included.

### Phase 3 — Strategy category + multi-entity honesty flag (P1 — Story 4)

Ensures we don't silently mislead until the group tax model lands.

1. **`strategy_category.py`**: enum (`prepayment`, `capex_deduction`, `super_contribution`, `director_salary`, `trust_distribution`, `dividend_timing`, `spouse_contribution`, `multi_entity_restructure`, `other`); constant `REQUIRES_GROUP_MODEL` set; `requires_group_model(category) -> bool` pure.
2. **`models.py`**: `TaxScenario.strategy_category` (Enum column, default `other`); `requires_group_model` (Bool, default False). Populated in service on scenario persist based on modeller output.
3. **`agents/prompts.py` / `agents/modeller.py` / `agents/scanner.py`**: prompts instruct the LLM to emit `strategy_category` from the enum. Tool-result validation rejects invalid categories (one retry, then fallback to `other`). Service computes `requires_group_model` from the category using the mapping — not from the LLM.
4. **Frontend**: `RequiresGroupModelNotice.tsx` disabled state. `ComparisonTable.tsx` excludes flagged scenarios from combined totals, shows "(excluded — requires group model)" subtotal row.
5. **Tests**: unit `test_strategy_category.py`; integration tests assert flagged categories don't count in total.

### Phase 4 — Independent reviewer (P1 — Story 5)

Closes the rubber-stamp loophole.

1. **`tax_calculator.py`** add `compute_ground_truth(financials_data, rate_configs, has_help_debt) -> GroundTruth` — re-derives taxable income purely from raw confirmed inputs (`income.total_income`, `expenses.total_expenses`, `adjustments`), computes expected before-position. Pure function. No access to modeller output or cached baselines.
2. **`agents/reviewer.py`** `_verify_calculator_numbers` rewritten: for each scenario, compute ground-truth `before` from raw inputs, compare with `scenario.impact_data.before.*` with $1 tolerance, report `{field, expected, got, delta}` on any disagreement. Pass through `numbers_verified: false` with detail.
3. **`orchestrator.py`**: review result is propagated unchanged; UI renders warning but does not block (per FR-022 clarification).
4. **Frontend**: `ReviewerWarningBanner.tsx` — top-of-page when any scenario failed verification, plus per-scenario badge with delta + field.
5. **Tests**: unit `test_ground_truth.py` (pure math); integration `test_reviewer_independent.py` (injects deliberate modeller error, asserts detection).

### Phase 5 — Citation verifier swap + low-confidence UX (P2 — Story 6)

Two fixes — a hotfixable one-liner and a matcher swap.

1. **`service.py:1057` hotfix**: `c.get("score", 0.0)` → `c.get("relevance_score", 0.0)`. Can ship ahead of everything else.
2. **`service.py` `_build_citation_verification`**: replace local substring-only matcher with a call to `knowledge.retrieval.citation_verifier.verify_citations(response, chunks)` which already includes chunk-text body fallback.
3. **`schemas.py` / frontend `types/tax-planning.ts`**: add `"low_confidence"` to the CitationVerificationStatus enum on both sides.
4. **`CitationBadge.tsx`**: new visual treatment for `low_confidence` (amber + "AI declined — low source confidence").
5. **`ScenarioChat.tsx`**: fix streaming race so verification badge renders live, not only on reload.
6. **Tests**: contract `test_citation_verification_contract.py` (asserts `relevance_score` key usage + status enum parity); integration `test_citation_body_match.py`.

### Phase 6 — Rate currency contract test + scenario dedupe (P2 — Stories 7, 8)

1. **Prompt-scan contract test**: `test_prompt_stage3_scan.py` walks every `.py` in `app/modules/tax_planning/` and `app/modules/agents/`, fails on any occurrence of `"32.5"`, `"19%"`, `"$120,000"`, `"$120k"`. Whitelist this test file by path.
2. **Remove pre-Stage-3 strings** from `app/modules/agents/prompts.py:170,181`. Add Stage-3 grounding block to `tax_planning/prompts.py` (already done in Phase 1 step 4 — cross-reference).
3. **Test factory fix**: `tests/factories/tax_planning.py:34` update `tax_rate: 0.325 → 0.30`.
4. **Scenario upsert**: `TaxScenarioRepository.upsert_by_normalized_title(plan_id, normalized_title, payload)` uses `ON CONFLICT (tax_plan_id, normalized_title) DO UPDATE`. Service switches from `create` to `upsert`.
5. **Prompt instruction**: chat system prompt (`tax_planning/prompts.py`) gets a "do not replay existing scenarios; refine instead" rule referencing the existing `scenarios_history` block.
6. **Tests**: contract `test_prompt_stage3_scan.py`; integration `test_scenario_upsert.py`.

### Phase 7 — Golden-dataset E2E (capstone)

1. **Fixture**: `backend/tests/e2e/tax_planning/fixtures/zac_phillpott.json` — sanitised Zac inputs + expected ChangeGPS numbers. Authored from Unni's alpha-session notes. Committed once available.
2. **Harness**: `test_golden_dataset.py` runs `pull_xero_financials` against a fake Xero client wired to the fixture, creates a plan, runs the full analysis pipeline with a fake Anthropic client (deterministic tool-use script), asserts every numeric output within $1 of expected.
3. **CI gate**: test path added to the standard backend test suite so every PR touching `app/modules/tax_planning/**` blocks on regression.
4. **Fallback**: if Unni's fixture is not yet ready at merge time, commit the harness with a skipped fixture so infrastructure is in place; unblock once fixture arrives. Spec SC-004 explicitly tolerates this sequencing.

## Implementation Phases — mapping to user stories

| Phase | User Stories | FRs | Tests | Dependencies |
|-------|--------------|-----|-------|--------------|
| 1 — Ground truth at ingest | US1, US3 | FR-001 to FR-010 | projection unit, ingest+payroll integration | — |
| 2 — Provenance + inline confirm | US2 | FR-011 to FR-016 | schema invariants, analysis shape | 1 |
| 3 — Strategy category + honesty flag | US4 | FR-017 to FR-019 | category unit, flag integration | 2 |
| 4 — Independent reviewer | US5 | FR-020 to FR-022 | ground-truth unit, reviewer integration | 1 |
| 5 — Citation + low-confidence | US6 | FR-023 to FR-026 | citation contract + integration | — (parallel OK) |
| 6 — Rate currency + dedupe | US7, US8 | FR-027 to FR-032 | prompt-scan contract, upsert integration | — (parallel OK) |
| 7 — Golden-dataset E2E | all | SC-001..SC-008 | E2E harness | 1–6 |

**Critical path**: Phase 1 → 2 → 4 → 7. Phases 3, 5, 6 can run in parallel once Phase 2 is ≥50%.

## Complexity Tracking

> No constitution violations to justify. The only complexity-adjacent decision is introducing two tiny new files (`projection.py`, `strategy_category.py`) rather than inlining into `service.py` / `models.py`. Justification below for traceability, not because it violates anything.

| Decision | Why | Simpler Alternative Rejected Because |
|----------|-----|--------------------------------------|
| New `projection.py` | Pure fn, isolated unit testable, easily swapped if seasonality rule arrives later | Inline in `service.py` — harder to test in isolation; F1-3 partly happened because this logic was buried in a ~500-line service method |
| New `strategy_category.py` | Enum + `REQUIRES_GROUP_MODEL` mapping used by scanner, modeller, service, and tests | Inline in `models.py` — creates a circular import risk between agents and models, and the mapping is conceptually policy not data |
