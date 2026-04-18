# Golden-dataset fixtures

Each `.json` file in this directory is a sanitised client scenario with
expected ground-truth numbers. The harness at
`tests/e2e/tax_planning/test_golden_dataset.py` runs every fixture here and
fails CI if the calculator disagrees with the expected numbers by more than
`tolerance_dollars`.

## Current fixtures

*(none yet — waiting on Unni's alpha session artefacts)*

Files starting with `_` (like this README) are ignored by the harness.

## Format

See the docstring of `test_golden_dataset.py`. Minimal shape:

```json
{
  "inputs": {
    "financial_year": "2025-26",
    "entity_type": "company",
    "has_help_debt": false,
    "financials_data": { "income": {...}, "expenses": {...}, "credits": {...}, "adjustments": [], "turnover": 500000 },
    "rate_configs": {
      "company": { "small_business_rate": 0.25, "standard_rate": 0.30, "small_business_turnover_threshold": 50000000 }
    }
  },
  "expected": {
    "taxable_income": 150000.00,
    "total_tax_payable": 37500.00,
    "credits_total": 5000.00,
    "net_position": 32500.00
  },
  "tolerance_dollars": 1.00,
  "source_notes": "FY2025-26 · ChangeGPS reference · alpha session 2026-04-08"
}
```

## Adding a fixture

1. Get ChangeGPS (or equivalent) output for the client.
2. Copy their income/expense breakdown into `inputs.financials_data`.
3. Copy the expected tax position fields into `expected`.
4. Name the file after the client pseudonym (`zac_phillpott.json`, not real
   names; this directory is checked in).
5. Run `uv run pytest tests/e2e/tax_planning/` — should go green.
6. Any future calculator change must keep all fixtures green.
