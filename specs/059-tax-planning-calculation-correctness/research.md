# Phase 0 Research — Tax Planning Calculation Correctness

**Feature**: `059-tax-planning-calculation-correctness`
**Date**: 2026-04-18

This document captures decisions resolved during Phase 0 research so Phase 1 design and implementation are unambiguous. Spec-level `NEEDS CLARIFICATION` items were already resolved in `/speckit.clarify` (see spec "Clarifications" section). Remaining technical decisions are captured here.

---

## R1 — Annualisation placement

**Decision**: Apply linear annualisation inside `service.py._transform_xero_to_financials` (and its manual-path counterpart), writing a `projection_metadata` sub-key onto the resulting `financials_data` dict. The calculator consumes annualised figures with no awareness it was annualised.

**Rationale**:
- Annualise at ingest → exactly one representation of "the numbers" flows through the rest of the system. This is the whole point of this spec.
- `derive_taxable_income` stays pure and unchanged; only the data it reads is normalised earlier.
- `projection_metadata` sub-key (months_elapsed, months_projected, rule, ytd_snapshot, applied_at) preserves traceability for auditing and the Tax Position UI's "Projected from X months" chip.

**Alternatives considered**:
- *Annualise inside `derive_taxable_income`*: would leak "is this annualised?" decisions into the calculator, which is the wrong layering and risks double-annualisation if inputs already are.
- *Annualise in a new middleware layer between service and calculator*: extra layer, no benefit given only one call site.

---

## R2 — Annualisation formula

**Decision**: `projected_total = (ytd_total / months_elapsed) × 12`, where `months_elapsed = max(1, round((today - fy_start).days / 30.4375))` capped at 12.

**Rationale**:
- Matches the clarification ("linear, monthly_avg × 12").
- Integer-month granularity is honest — accountants think in quarterly BAS periods, not days.
- `max(1, …)` prevents divide-by-zero on day-one plans.
- Capped at 12 so a 12.5-month data window doesn't over-project.

**Edge cases resolved**:
- Less than one full month of data: treat as `months_elapsed=1`, extrapolate. Note in `projection_metadata` so UI can warn.
- Data covering 12+ months of the active FY: no annualisation; use figures as-is. This is the `months_elapsed=12` branch.

---

## R3 — Payroll on-demand sync channel

**Decision**: Use `asyncio.wait_for(sync_payroll(connection), timeout=15.0)` inside the tax-plan creation path. On `TimeoutError`, enqueue the existing Celery task `sync_xero_payroll` and return the plan response with `payroll_sync_status: "pending"`. Frontend polls `GET /tax-plans/{id}` every 3s (stopping after 2 min max) to pick up the recomputed tax position once payroll lands.

**Rationale**:
- `sync_payroll` already exists and is idempotent (`backend/app/modules/integrations/xero/payroll_service.py`). No new sync primitive.
- Celery `sync_xero_payroll` task already exists (`backend/app/tasks/xero.py:1296-1328`). No new infra.
- Polling is simpler than Server-Sent Events for a one-off 15-second window and matches existing patterns (e.g., bulk-import status polling). A full websocket/SSE channel for a single event is over-engineered.
- 2-minute polling cap limits wasted requests if payroll sync genuinely fails.

**Recompute on arrival**: when the background Celery task completes, it calls the existing `recompute_tax_position(plan_id)` service helper (added in this spec) which re-runs `calculate_tax_position` against the freshened `financials_data`. Frontend's next poll picks up the new numbers.

**Alternatives considered**:
- SSE/websocket push: more complex; polling is fine at this cadence.
- Blocking plan creation indefinitely: rejected in clarification Q5.
- Returning error if payroll not fresh: breaks any client without payroll access for valid reasons.

---

## R4 — Provenance storage shape

**Decision**: Add a single JSONB column `source_tags` on `tax_scenarios`. Shape: `{"<json_pointer>": "confirmed" | "derived" | "estimated"}` with JSON Pointer paths against `impact_data` and `assumptions` (e.g. `"impact_data.modified_expenses.operating_expenses"`, `"assumptions.0.amount"`).

**Rationale**:
- Single column, single migration.
- JSON Pointer is a standard (RFC 6901) — deterministic address into nested JSONB.
- Backward-compatible: existing scenarios get `source_tags={}`, rendered as absent-provenance (UI shows a neutral badge, not red).
- Queryable via PG JSONB operators if we later need analytics ("what % of confirmed scenarios used estimated baselines?").

**Alternatives considered**:
- Normalised `scenario_field_provenance` table: cleanest but heavy for v1; 30+ fields per scenario × many scenarios = lots of rows for little current gain.
- Inline into the existing `assumptions` JSONB: too fragile — every modeller schema change risks losing provenance metadata.

---

## R5 — Strategy category enum

**Decision**: `StrategyCategory` enum in `backend/app/modules/tax_planning/strategy_category.py` with members drawn from the set in FR-017. Stored on `TaxScenario.strategy_category` as a PostgreSQL Enum type.

**REQUIRES_GROUP_MODEL** set: `{director_salary, trust_distribution, dividend_timing, spouse_contribution, multi_entity_restructure}`.

**Rationale**:
- Closed enum at the DB level → the policy is enforced in storage, not just in code.
- Pure mapping in Python → trivially testable, no import of LLM code.
- Adding a new category later is a standard Alembic enum migration.

**Alternatives considered**:
- String column with application-level validation: easier to change but defeats the "authoritative closed set" intent.
- Separate `strategy_category_metadata` table: overkill for a ~10-value enum.

---

## R6 — Reviewer independent ground truth

**Decision**: New pure function `tax_calculator.compute_ground_truth(financials_data, rate_configs, has_help_debt) -> GroundTruth` that re-derives taxable income from `income.total_income`, `expenses.total_expenses`, `adjustments` directly — explicitly **does not** accept a pre-computed `base_financials` dict. The reviewer passes raw `financials_data` from `TaxPlan`, not the modeller's cached copy.

**Rationale**:
- Independence by construction: the function cannot read the modeller's possibly-wrong intermediate state because it doesn't accept it.
- Deterministic — same inputs, same output, $0 variance.
- No LLM call → no cost, no latency, no non-determinism in the final gate.

**Tolerance**: $1 (matches SC-001, SC-006 and the existing `_within_one` helper in `test_tax_calculator.py`).

**Alternatives considered**:
- LLM-based "does this make sense" reviewer: interesting but non-deterministic, expensive, and unbounded in failure modes. Deferred as future work (noted in spec assumptions).

---

## R7 — Citation verifier swap

**Decision**: Replace the inline `_build_citation_verification` in `tax_planning/service.py:888-958` with a call to `knowledge.retrieval.citation_verifier.verify_citations(response_content, retrieved_chunks)`. Keep thin wrapper in tax_planning service to shape output to the existing `CitationVerificationResult` response schema.

**Rationale**:
- The knowledge-module verifier already implements chunk-text body fallback (`knowledge/retrieval/citation_verifier.py:199-249`) which is exactly what's missing in tax_planning.
- Calling across module boundaries via public service interface is the constitution-approved pattern.
- No duplication of citation-matching logic.

**`relevance_score` hotfix**: one-line change, `c.get("score", 0.0)` → `c.get("relevance_score", 0.0)` at `service.py:1057`. Ships independently (Phase 5 step 1) and is safe to deploy ahead of the rest.

---

## R8 — Scenario upsert implementation

**Decision**: Partial unique index on `tax_scenarios (tax_plan_id, lower(trim(title)))`; `TaxScenarioRepository.upsert_by_normalized_title` uses SQLAlchemy's `insert().on_conflict_do_update(...)` against the unique index.

**Rationale**:
- Enforced at DB level → even a buggy agent retry cannot create a duplicate row.
- `lower(trim(title))` normalised inline in the index expression; no separate "normalised_title" column needed.
- Upsert semantics preserve the scenario's UUID across refinements, which means the frontend's stable React keys keep working.

**Normalisation depth**: for v1, case-insensitive + whitespace-trim. Stemming/lemmatisation (e.g. "Prepay rent" ≡ "Prepaying rent") is **not** included — it's harder to get right and the chat-prompt instruction plus the LLM's own context awareness are the first line of defence. Noted as a possible extension.

---

## R9 — Prompt-scan contract test

**Decision**: A pytest-time contract test `backend/tests/contract/modules/tax_planning/test_prompt_stage3_scan.py` walks `app/modules/tax_planning/**/*.py` and `app/modules/agents/**/*.py`, reads each file, and asserts none of these tokens appear anywhere (comments included): `"32.5"`, `"19%"` (word-boundary), `"$120,000"`, `"$120k"`.

**Rationale**:
- Comments and docstrings are read by humans who then copy into Slack answers or PR descriptions — drift risk is real.
- The test file itself is explicitly excluded (self-reference).
- Runs in <1s — no reason to exclude from the standard CI suite.

**Positive grounding**: complementary positive test asserts `TAX_PLANNING_SYSTEM_PROMPT` contains the Stage-3 thresholds (`"18,200"`, `"45,000"`, `"135,000"`, `"190,000"`).

---

## R10 — Golden-dataset fixture format

**Decision**: JSON file under `backend/tests/e2e/tax_planning/fixtures/zac_phillpott.json`. Top-level shape:

```json
{
  "inputs": {
    "tenant_id": "...",
    "client_id": "...",
    "financial_year": "2025-26",
    "reconciliation_date": "2026-03-31",
    "entity_type": "company",
    "xero_profit_loss": { /* mirror of XeroProfitLoss shape */ },
    "xero_pay_runs": [ /* mirror of XeroPayRun rows */ ],
    "bank_balances": { /* aggregated */ },
    "prior_year_summary": { /* optional */ }
  },
  "expected": {
    "tax_position": {
      "taxable_income": 123456.00,
      "total_tax_payable": 45678.00,
      "credits_applied_total": 5000.00,
      "net_position": 40678.00
    },
    "scenarios": [
      { "strategy_category": "prepayment", "impact.change.tax_saving": 2500.00 }
    ],
    "combined_strategy": { "total_tax_saving": 2500.00 }
  },
  "tolerance_dollars": 1.00,
  "source_notes": "Derived from Unni alpha session 2026-04-08; ChangeGPS export reference."
}
```

**Rationale**:
- Plain JSON → easy to diff in PRs, trivially extendable to more fixtures (one per additional golden client).
- Self-describing `tolerance_dollars` keeps the assertion helper simple.
- `source_notes` documents provenance for future maintenance.

**Fallback plan**: the harness runs even without the fixture (skipped with a specific marker `@pytest.mark.skipif(fixture_missing)`). Once Unni supplies the data, the fixture is committed and the test runs. Spec SC-004 explicitly allows this sequencing.

---

## R11 — Fake Anthropic client for agent tests

**Decision**: A minimal in-module `FakeAnthropicClient` fixture keyed by input prompt hash → scripted response. Lives under `backend/tests/fixtures/fake_anthropic.py`.

**Rationale**:
- Real Anthropic calls in tests are slow, costly, and non-deterministic.
- Existing codebase uses `unittest.mock` against the SDK in a few places (see `backend/tests/unit/modules/tax_planning/test_tax_planning_intelligence.py` patterns). Formalise as a reusable fixture to avoid per-test re-invention.
- Scripted responses let us inject deliberate errors for reviewer-independence tests (Phase 4).

---

## R12 — Migration strategy and backward compatibility

**Decision**: Single Alembic migration `20260418_059_tax_planning_correctness.py`:
1. Add `strategy_category` column (Enum, default `'other'`, NOT NULL).
2. Add `requires_group_model` column (Boolean, default `false`, NOT NULL).
3. Add `source_tags` column (JSONB, default `'{}'`, NOT NULL).
4. Create partial unique index `ix_tax_scenarios_plan_normalized_title` on `(tax_plan_id, lower(trim(title)))`.
5. Back-fill for existing rows via `UPDATE … SET strategy_category='other', requires_group_model=false, source_tags='{}'` (no-op since defaults do the work, but explicit for clarity).

**Rationale**:
- Defaults make the migration safe to run online with no downtime.
- Existing rows that would violate the new unique index are vanishingly unlikely (alpha has few plans, and pre-existing duplicates are precisely the bug we're fixing — the migration logs + skips them with a warning during back-fill; the first scenario keeps the row, the duplicate gets its title suffixed with `" (duplicate)"` to preserve history).
- `downgrade` drops the index and columns in reverse order.

---

## R13 — Frontend provenance + confirm UX micro-decisions

**Decision**: `InlineConfirmInput` is a small controlled component wrapping shadcn/ui `Input`. While `source=estimated`, the field renders with an amber left-border and a `ProvenanceBadge` ("Estimated"). On blur or Enter, if the value is non-empty, the component calls the PATCH endpoint and the badge flips to green ("Confirmed"). Empty confirms show an explicit warning, not auto-confirm.

**Rationale**:
- Controlled component keeps React state predictable.
- Blur-to-confirm matches natural tabbing behaviour in data-entry forms.
- Explicit warning on empty avoids ambiguous "I confirm nothing" state.

---

## Outstanding items (low-impact, deferred to implementation)

- Exact colour choices for `ProvenanceBadge` (will use existing Clairo design tokens; no new colours).
- Specific polling cadence for payroll sync banner (3s initial, back off to 10s after 30s wall clock; can tune at implementation time).
- Exact wording of "requires group model" explanatory copy — will draft during implementation, review with Unni.

---

**Status**: All Phase 0 unknowns resolved. Proceed to Phase 1 artefacts (data-model, contracts, quickstart).
