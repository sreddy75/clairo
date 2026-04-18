# Developer Quickstart — Tax Planning Calculation Correctness

**Feature**: `059-tax-planning-calculation-correctness`
**Date**: 2026-04-18

How to run, test, and extend this feature locally. Read `plan.md` for scope and `data-model.md` for schema.

---

## Prerequisites

- Local Clairo stack running via `docker-compose up -d` (Postgres, Redis, MinIO).
- Backend env configured (`backend/.env` populated; Pinecone + Anthropic keys not required for these tests — fake clients used).
- Python 3.12+ with `uv` (`cd backend && uv sync`).
- On branch `059-tax-planning-calculation-correctness`.

---

## Running the migration

```bash
cd backend && uv run alembic upgrade head
```

The new migration `20260418_059_tax_planning_correctness` adds three columns to `tax_scenarios` and the partial unique index. It is safe to run on an existing database — defaults populate new columns and duplicate-title rows are disambiguated before the index is created.

To roll back:

```bash
cd backend && uv run alembic downgrade -1
```

---

## Running the test suite for this feature

Full backend test run (includes this feature):

```bash
cd backend && uv run pytest
```

Just this feature's tests (fast feedback loop):

```bash
cd backend && uv run pytest tests/unit/modules/tax_planning tests/integration/modules/tax_planning tests/contract/modules/tax_planning
```

Golden-dataset E2E (requires the fixture — currently skipped if absent):

```bash
cd backend && uv run pytest tests/e2e/tax_planning/test_golden_dataset.py -v
```

Prompt-scan contract test in isolation:

```bash
cd backend && uv run pytest tests/contract/modules/tax_planning/test_prompt_stage3_scan.py -v
```

---

## Adding a new golden-dataset fixture

The golden dataset is the regression gate for correctness. Add a new client like so.

1. Create `backend/tests/e2e/tax_planning/fixtures/<client_slug>.json`:

   ```json
   {
     "inputs": {
       "tenant_id": "00000000-0000-0000-0000-000000000001",
       "client_id": "00000000-0000-0000-0000-000000000002",
       "financial_year": "2025-26",
       "reconciliation_date": "2026-03-31",
       "entity_type": "company",
       "xero_profit_loss": { "revenue": 500000, "total_expenses": 350000, "line_items": [ ... ] },
       "xero_pay_runs": [ { "period_start": "2025-07-01", "period_end": "2025-07-14", "total_wages": 10000, "total_super": 1100, "total_tax": 2500 } ],
       "bank_balances": { "total": 120000 },
       "prior_year_summary": null
     },
     "expected": {
       "tax_position": {
         "taxable_income": 150000.00,
         "total_tax_payable": 37500.00,
         "credits_applied_total": 25000.00,
         "net_position": 12500.00
       },
       "scenarios": [
         { "title": "Prepay rent", "strategy_category": "prepayment", "impact.change.tax_saving": 2500.00 }
       ]
     },
     "tolerance_dollars": 1.00,
     "source_notes": "Alpha session YYYY-MM-DD; reference: ChangeGPS export."
   }
   ```

2. Add a parametrised test case in `tests/e2e/tax_planning/test_golden_dataset.py`:

   ```python
   @pytest.mark.parametrize("fixture", ["zac_phillpott", "<client_slug>"])
   def test_golden_dataset_matches_reference(fixture): ...
   ```

3. Run the suite: `uv run pytest tests/e2e/tax_planning/ -k <client_slug> -v`.

4. Commit the fixture, the test case update, and any required model changes to Xero fake response shape together.

---

## Verifying payroll on-demand sync

From a running backend, create a plan for a Xero connection with payroll access:

```bash
curl -X POST http://localhost:8000/api/v1/tax-plans \
  -H "Authorization: Bearer $CLERK_JWT" \
  -H "Content-Type: application/json" \
  -d '{"client_id": "<uuid>", "entity_type": "company", "financial_year": "2025-26"}'
```

Inspect `payroll_sync_status` in the response:
- `ready` — sync completed inside 15s window; `financials_data.payroll_summary` populated.
- `pending` — background sync in flight; poll `GET /api/v1/tax-plans/{id}` to watch the status flip.
- `unavailable` — check `has_payroll_access` on the connection; re-authorise with payroll scope if needed.

To force the "pending" path for manual testing, add a slow sleep inside `sync_payroll` temporarily, or mock out the fast path.

---

## Confirming an estimated figure from the UI (local)

1. Run the frontend: `cd frontend && npm run dev`.
2. Open a tax plan that has a scenario with AI assumptions.
3. Find the amber-bordered `InlineConfirmInput` showing an estimated amount.
4. Either press Enter without changing the value (accepts verbatim) or type a new value and blur. The badge flips from "Estimated" to "Confirmed".
5. Check the Network tab — you'll see `PATCH /api/v1/tax-plans/{id}/scenarios/{scenario_id}/assumptions/{field_path}`.

---

## Running the prompt-scan contract test

The contract test walks `app/modules/tax_planning/**` and `app/modules/agents/**` and fails on any occurrence of `"32.5"`, `"19%"`, `"$120,000"`, `"$120k"`.

Runs in <1s. Always green on this branch:

```bash
cd backend && uv run pytest tests/contract/modules/tax_planning/test_prompt_stage3_scan.py
```

If a future PR adds a pre-Stage-3 string, this test will fail in CI before the PR gets reviewed.

---

## Injecting a reviewer error (sanity test)

To verify the reviewer agent actually catches modeller errors, patch the modeller briefly to emit a wrong `before.tax_payable`:

```python
# tests/integration/modules/tax_planning/test_reviewer_independent.py
def test_reviewer_detects_injected_error(inject_modeller_error):
    inject_modeller_error(field="impact_data.before.tax_payable", delta=1000)
    result = run_analysis_pipeline(fixture="zac_phillpott")
    assert result.review_result.numbers_verified is False
    assert result.review_result.disagreements[0].field_path == "impact_data.before.tax_payable"
    assert result.review_result.disagreements[0].delta == pytest.approx(1000, abs=1)
```

If this test passes, the reviewer is genuinely checking against the independent ground-truth re-derivation. If it fails, the reviewer is still rubber-stamping — do not ship.

---

## Updating the frontend types

When the backend schema changes, regenerate frontend types:

```bash
cd backend && uv run python -m scripts.generate_openapi  # writes shared/openapi/schema.json
cd frontend && npx openapi-typescript ../shared/openapi/schema.json -o src/types/api.ts
```

Manual additions in `frontend/src/types/tax-planning.ts` (e.g. the `Provenance` type) are not auto-generated — keep them in sync by hand.

---

## Common pitfalls

- **`save_manual_financials` wiping Xero context**: the fix merges rather than overwrites. If you add a new financials-derived key, add it to the `PRESERVED_CONTEXT_KEYS` constant in `service.py` so manual saves don't eat it.
- **Forgetting provenance on a new numeric field**: the contract test `test_scenario_schema_invariants.py` will fail. Tag it explicitly in the modeller tool output and in the schema.
- **New strategy category**: enum change + Alembic migration. Update `REQUIRES_GROUP_MODEL` set at the same time, or the honesty flag misses the new category.
- **Golden dataset drift**: do not edit the `expected.*` values in a fixture to make tests pass. If the reference numbers have changed, update the `source_notes` with the ChangeGPS export date and the reason.

---

## Where to look when something breaks

| Symptom | Likely location |
|---------|----------------|
| Tax position on a mid-year plan is "wrong" | `service.py` annualisation call + `projection.py` |
| Super YTD / PAYGW YTD = $0 | `service.py` payroll read block; `has_payroll_access` on connection |
| PAYGW credit not applied | `service.py._transform_xero_to_financials` — `credits.payg_withholding` wire |
| Scenario rendered without provenance badge | `modeller.py` tool-result post-validation; `ComparisonTable.tsx` |
| Duplicate scenario rows | `TaxScenarioRepository.upsert_by_normalized_title` call site in `service.py` |
| "Sources could not be verified" on a good response | `_build_citation_verification` now delegates to `knowledge/retrieval/citation_verifier.py`; check both sides |
| Canned decline replacing a legitimate response | `service.py:1057` — confirm `relevance_score` key is used |
| Reviewer reports "all good" on a known error | `reviewer.py._verify_calculator_numbers` — must call `compute_ground_truth`, not reuse `base_financials` |

---

**Status**: Quickstart complete. Ready for `/speckit.tasks` to generate the actionable task list.
