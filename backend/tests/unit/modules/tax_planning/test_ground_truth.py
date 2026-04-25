"""US5 — The reviewer catches errors, not rubber-stamps them.

Unit tests for the independent ground-truth re-derivation used by the
reviewer agent. The reviewer passes raw `financials_data` from TaxPlan, not
the modeller's cached intermediate state, so injected errors are caught by
direct comparison with a $1 tolerance.

Spec 059 FR-011..FR-014, US5 tests T066-T070.
"""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest

from app.modules.tax_planning.tax_calculator import (
    GroundTruth,
    calculate_tax_position,
    compute_ground_truth,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def company_rate_configs() -> dict:
    return {
        "_financial_year": "2025-26",
        "company": {
            "small_business_rate": 0.25,
            "standard_rate": 0.30,
            "small_business_turnover_threshold": 50_000_000,
        },
    }


@pytest.fixture
def company_financials() -> dict:
    return {
        "income": {"total_income": 500_000},
        "expenses": {"total_expenses": 350_000},
        "credits": {
            "payg_instalments": 25_000,
            "payg_withholding": 12_000,
            "franking_credits": 0,
        },
        "adjustments": [],
        "turnover": 500_000,
    }


# ---------------------------------------------------------------------------
# T066 — compute_ground_truth matches calculator for matching inputs
# ---------------------------------------------------------------------------


def test_compute_ground_truth_matches_calculator(
    company_financials: dict, company_rate_configs: dict
) -> None:
    calculator_result = calculate_tax_position(
        entity_type="company",
        financials_data=company_financials,
        rate_configs=company_rate_configs,
    )

    truth = compute_ground_truth(
        financials_data=company_financials,
        rate_configs=company_rate_configs,
        entity_type="company",
    )

    assert isinstance(truth, GroundTruth)
    # Within $1 tolerance (same formula — identical down to the cent, but we
    # guard against any future divergence caused by separate evolution paths).
    assert abs(truth.taxable_income - Decimal(str(calculator_result["taxable_income"]))) < 1
    assert abs(truth.gross_tax - Decimal(str(calculator_result["gross_tax"]))) < 1
    assert abs(truth.total_tax_payable - Decimal(str(calculator_result["total_tax_payable"]))) < 1
    assert (
        abs(truth.credits_total - Decimal(str(calculator_result["credits_applied"]["total"]))) < 1
    )
    assert abs(truth.net_position - Decimal(str(calculator_result["net_position"]))) < 1


def test_compute_ground_truth_runs_on_individual(company_rate_configs: dict) -> None:
    # Individual with LITO + Medicare — verifies the dispatch path, not just
    # the company happy path.
    rate_configs = dict(company_rate_configs)
    rate_configs["individual"] = {
        "brackets": [
            {"min": 0, "max": 18_200, "rate": 0.0},
            {"min": 18_200, "max": 45_000, "rate": 0.19},
            {"min": 45_000, "max": 135_000, "rate": 0.30},
            {"min": 135_000, "max": 190_000, "rate": 0.37},
            {"min": 190_000, "max": None, "rate": 0.45},
        ],
    }
    rate_configs["medicare"] = {
        "rate": 0.02,
        "low_income_threshold_single": 26_000,
        "phase_in_threshold_single": 32_500,
        "shade_in_rate": 0.10,
    }
    rate_configs["lito"] = {
        "max_offset": 700,
        "full_offset_threshold": 37_500,
        "first_reduction_rate": 0.05,
        "first_reduction_threshold": 45_000,
        "second_reduction_rate": 0.015,
        "second_reduction_threshold": 66_667,
    }
    financials = {
        "income": {"total_income": 100_000},
        "expenses": {"total_expenses": 20_000},
        "credits": {"payg_withholding": 5_000},
        "adjustments": [],
        "turnover": 100_000,
    }

    truth = compute_ground_truth(
        financials_data=financials,
        rate_configs=rate_configs,
        entity_type="individual",
    )

    # Taxable income = 100k - 20k = 80k.
    assert truth.taxable_income == Decimal("80000.00")
    # Net position = tax - credits; we just assert it's populated.
    assert truth.net_position == truth.total_tax_payable - truth.credits_total


# ---------------------------------------------------------------------------
# T067 — no `base_financials` parameter — cannot be duped by cached state
# ---------------------------------------------------------------------------


def test_ground_truth_signature_has_no_base_financials() -> None:
    """R6 invariant: the reviewer ground-truth function accepts only raw
    inputs. A parameter named `base_financials` would allow a buggy or
    hostile modeller output to propagate into the verification step."""
    sig = inspect.signature(compute_ground_truth)
    assert "base_financials" not in sig.parameters
    assert "financials_data" in sig.parameters
    assert "rate_configs" in sig.parameters
    assert "entity_type" in sig.parameters


# ---------------------------------------------------------------------------
# T068..T070 — Reviewer integration helper (unit-style, no Anthropic)
# ---------------------------------------------------------------------------


def _run_reviewer_number_check(
    scenarios: list[dict],
    financials: dict,
    rate_configs: dict,
    entity_type: str = "company",
) -> tuple[list[str], list[dict]]:
    """Invoke the reviewer's pure number-verification helper directly.

    Skips the Anthropic round-trip and the JSON-parse path so we can assert
    directly on the disagreement list, which is the contract we care about.
    """
    from app.modules.tax_planning.agents.reviewer import ReviewerAgent

    return ReviewerAgent._verify_calculator_numbers(  # type: ignore[attr-defined]
        scenarios,
        financials,
        entity_type,
        rate_configs,
    )


def test_reviewer_detects_injected_error(
    company_financials: dict, company_rate_configs: dict
) -> None:
    """T068: inject a deliberately wrong before.tax_payable on the scenario;
    the reviewer must flag it with the exact field and delta."""
    truth = compute_ground_truth(
        financials_data=company_financials,
        rate_configs=company_rate_configs,
        entity_type="company",
    )
    correct_before_tax = float(truth.total_tax_payable)

    bad_scenario = {
        "id": "abc-123",
        "scenario_title": "Hostile scenario",
        "impact": {
            "before": {
                "tax_payable": correct_before_tax + 1_000,  # $1000 off
                "taxable_income": float(truth.taxable_income),
            },
        },
    }

    issues, disagreements = _run_reviewer_number_check(
        [bad_scenario], company_financials, company_rate_configs
    )

    assert len(disagreements) == 1
    d = disagreements[0]
    assert d["scenario_id"] == "abc-123"
    assert d["field_path"] == "impact.before.tax_payable"
    assert abs(d["delta"] - 1_000) < 1
    assert issues  # legacy string issues list is populated too


def test_reviewer_passes_on_correct_modeller_output(
    company_financials: dict, company_rate_configs: dict
) -> None:
    """T069: correct scenario — reviewer returns no disagreements."""
    truth = compute_ground_truth(
        financials_data=company_financials,
        rate_configs=company_rate_configs,
        entity_type="company",
    )
    correct_scenario = {
        "id": "def-456",
        "scenario_title": "Honest scenario",
        "impact": {
            "before": {
                "tax_payable": float(truth.total_tax_payable),
                "taxable_income": float(truth.taxable_income),
            },
        },
    }

    issues, disagreements = _run_reviewer_number_check(
        [correct_scenario], company_financials, company_rate_configs
    )

    assert disagreements == []
    assert issues == []


def test_subdollar_delta_does_not_fail_review(
    company_financials: dict, company_rate_configs: dict
) -> None:
    """T070: $0.50 rounding delta must not fail the review — the $1 tolerance
    exists precisely to tolerate floating-point / rounding noise."""
    truth = compute_ground_truth(
        financials_data=company_financials,
        rate_configs=company_rate_configs,
        entity_type="company",
    )

    scenario = {
        "id": "rounding-ok",
        "scenario_title": "Rounding edge case",
        "impact": {
            "before": {
                "tax_payable": float(truth.total_tax_payable) + 0.50,
                "taxable_income": float(truth.taxable_income),
            },
        },
    }

    issues, disagreements = _run_reviewer_number_check(
        [scenario], company_financials, company_rate_configs
    )

    assert disagreements == []
    assert issues == []


def test_reviewer_uses_impact_data_key_when_impact_absent(
    company_financials: dict, company_rate_configs: dict
) -> None:
    """Modeller output uses `impact_data` (DB column name) in some paths and
    `impact` in others. Both must be understood by the reviewer."""
    truth = compute_ground_truth(
        financials_data=company_financials,
        rate_configs=company_rate_configs,
        entity_type="company",
    )
    scenario = {
        "id": "shape-test",
        "scenario_title": "impact_data shape",
        "impact_data": {
            "before": {
                "tax_payable": float(truth.total_tax_payable) + 2_000,
                "taxable_income": float(truth.taxable_income),
            },
        },
    }

    _, disagreements = _run_reviewer_number_check(
        [scenario], company_financials, company_rate_configs
    )

    assert len(disagreements) == 1
    assert disagreements[0]["field_path"].endswith("before.tax_payable")
