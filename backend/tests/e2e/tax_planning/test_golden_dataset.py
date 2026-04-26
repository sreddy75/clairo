"""Golden-dataset regression gate for tax-planning correctness.

The capstone of spec 059: a parametrised harness that runs each fixture in
`fixtures/*.json` through the tax-plan calculation pipeline and asserts every
expected number matches within the fixture-specified tolerance.

The harness runs CALCULATOR-LEVEL checks, not the full multi-agent AI
pipeline (which requires an async Anthropic fake that isn't the concern of
this gate — AI output is checked separately by the US5 reviewer tests). The
gate's job is to catch *calculation* regressions: if we accidentally change
the annualisation formula, the bracket boundaries, or the credit wiring,
Zac's numbers stop matching ChangeGPS and CI fails.

Fixture format (per research.md R10):

    {
      "inputs": {
        "financial_year": "2025-26",
        "entity_type": "company",
        "has_help_debt": false,
        "financials_data": { ...same shape as TaxPlan.financials_data... },
        "rate_configs": { ...keyed by rate_type... }
      },
      "expected": {
        "taxable_income": 123456.00,
        "total_tax_payable": 30864.00,
        "credits_total": 5000.00,
        "net_position": 25864.00
      },
      "tolerance_dollars": 1.00,
      "source_notes": "Derived from Unni alpha session 2026-04-08; ChangeGPS reference."
    }

When `fixtures/` is empty (e.g. awaiting the alpha session artefacts), the
test self-skips — the harness is committed so CI gates are ready the moment
fixtures land (spec SC-004).

Spec 059 task T104.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.modules.tax_planning.tax_calculator import (
    compute_ground_truth,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _fixture_files() -> list[Path]:
    if not FIXTURE_DIR.exists():
        return []
    return sorted(
        p for p in FIXTURE_DIR.glob("*.json") if p.is_file() and not p.name.startswith("_")
    )


def _fixture_id(path: Path) -> str:
    return path.stem


@pytest.mark.parametrize(
    "fixture_path",
    _fixture_files() or [pytest.param(None, marks=pytest.mark.skip(reason="no fixtures"))],
    ids=lambda p: _fixture_id(p) if p else "no-fixtures",
)
def test_golden_dataset_matches_expected(fixture_path: Path | None) -> None:
    """Per-fixture assertion that the calculator agrees with ChangeGPS within
    `tolerance_dollars` (defaults to $1.00 per SC-001).

    A failing fixture means one of:
    - We shipped a calculation regression (most common).
    - The fixture is stale vs a bracket / rate change (update rate_configs).
    - Expected values came from a different calculation basis (update notes).
    """
    if fixture_path is None:  # covered by skip marker, but keep mypy happy
        return
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    inputs = data["inputs"]
    expected = data["expected"]
    tolerance = Decimal(str(data.get("tolerance_dollars", 1.00)))

    truth = compute_ground_truth(
        financials_data=inputs["financials_data"],
        rate_configs=inputs["rate_configs"],
        entity_type=inputs["entity_type"],
        has_help_debt=inputs.get("has_help_debt", False),
    )

    failures: list[str] = []
    for field, expected_value in expected.items():
        got = getattr(truth, field, None)
        if got is None:
            failures.append(f"  {field}: no attribute on GroundTruth")
            continue
        delta = abs(Decimal(str(got)) - Decimal(str(expected_value)))
        if delta > tolerance:
            failures.append(
                f"  {field}: expected ${expected_value}, got ${got} "
                f"(delta ${delta}, tolerance ${tolerance})"
            )

    assert not failures, f"Golden dataset {_fixture_id(fixture_path)} failed:\n" + "\n".join(
        failures
    )
