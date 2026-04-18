"""US4 — Multi-entity strategies do not silently mislead.

Verifies the honesty flag wiring at the modeller-output shape level:

- Every scenario the modeller emits carries a `strategy_category` from the
  closed enum.
- Scenarios in `REQUIRES_GROUP_MODEL` have `requires_group_model=True` —
  derived from the category in code, never from LLM output.
- Combined-strategy totals exclude flagged scenarios and report how many
  were excluded.

Spec 059 FR-017..FR-020, US4 tests T054-T057.
"""

from __future__ import annotations

from typing import Any

from app.modules.tax_planning.agents.modeller import ScenarioModellerAgent
from app.modules.tax_planning.strategy_category import (
    REQUIRES_GROUP_MODEL,
    StrategyCategory,
    requires_group_model,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _base_financials() -> dict:
    return {
        "income": {"revenue": 500_000, "other_income": 0, "total_income": 500_000},
        "expenses": {
            "cost_of_sales": 100_000,
            "operating_expenses": 250_000,
            "total_expenses": 350_000,
        },
        "credits": {"payg_instalments": 0, "payg_withholding": 0, "franking_credits": 0},
        "adjustments": [],
        "turnover": 500_000,
    }


def _company_rate_configs() -> dict:
    return {
        "_financial_year": "2025-26",
        "company": {
            "small_business_rate": 0.25,
            "standard_rate": 0.30,
            "small_business_turnover_threshold": 50_000_000,
        },
    }


def _invoke_modeller_tool(
    tool_input: dict[str, Any],
    financials: dict | None = None,
    rate_configs: dict | None = None,
) -> dict:
    """Invoke the modeller's pure tool-execution helper directly — skips the
    Anthropic round-trip, which is the right surface to verify the output
    contract."""
    agent = ScenarioModellerAgent.__new__(ScenarioModellerAgent)  # no __init__
    return agent._execute_tool(  # type: ignore[attr-defined]
        tool_input,
        financials or _base_financials(),
        "company",
        rate_configs or _company_rate_configs(),
    )


# ---------------------------------------------------------------------------
# T054 — every scenario emits a strategy_category
# ---------------------------------------------------------------------------


def test_every_scenario_has_strategy_category() -> None:
    """Modeller output must always carry a category. Missing or invalid LLM
    output falls back to `other` rather than failing persistence."""
    result = _invoke_modeller_tool(
        {
            "scenario_title": "Prepay rent",
            "description": "Prepay 12 months of rent",
            "modified_income": {"revenue": 500_000, "other_income": 0},
            "modified_expenses": {"cost_of_sales": 100_000, "operating_expenses": 275_000},
            "assumptions": ["25k prepayment"],
            "risk_rating": "conservative",
            "compliance_notes": "s82KZM ITAA 1936",
            "strategy_category": "prepayment",
        }
    )
    assert "strategy_category" in result
    assert result["strategy_category"] == "prepayment"


def test_invalid_strategy_category_falls_back_to_other() -> None:
    """LLM-emitted garbage in `strategy_category` gets coerced to OTHER."""
    result = _invoke_modeller_tool(
        {
            "scenario_title": "Weird scenario",
            "description": "Something",
            "modified_income": {"revenue": 500_000, "other_income": 0},
            "modified_expenses": {"cost_of_sales": 100_000, "operating_expenses": 250_000},
            "assumptions": [],
            "risk_rating": "moderate",
            "compliance_notes": "",
            "strategy_category": "not_a_real_category",
        }
    )
    assert result["strategy_category"] == "other"
    assert result["requires_group_model"] is False


def test_missing_strategy_category_defaults_to_other() -> None:
    """When the LLM omits the field entirely, the modeller still emits a
    scenario — just with category OTHER."""
    result = _invoke_modeller_tool(
        {
            "scenario_title": "Legacy-shaped scenario",
            "description": "Something",
            "modified_income": {"revenue": 500_000, "other_income": 0},
            "modified_expenses": {"cost_of_sales": 100_000, "operating_expenses": 250_000},
            "assumptions": [],
            "risk_rating": "moderate",
            "compliance_notes": "",
        }
    )
    assert result["strategy_category"] == "other"
    assert result["requires_group_model"] is False


# ---------------------------------------------------------------------------
# T055 — multi-entity category sets requires_group_model=True
# ---------------------------------------------------------------------------


def test_trust_distribution_sets_requires_group_model_true() -> None:
    result = _invoke_modeller_tool(
        {
            "scenario_title": "Distribute trust income to beneficiaries",
            "description": "Split distribution across spouse and adult child",
            "modified_income": {"revenue": 500_000, "other_income": 0},
            "modified_expenses": {"cost_of_sales": 100_000, "operating_expenses": 250_000},
            "assumptions": ["50/50 split"],
            "risk_rating": "moderate",
            "compliance_notes": "PCG 2023/2",
            "strategy_category": "trust_distribution",
        }
    )
    assert result["strategy_category"] == "trust_distribution"
    assert result["requires_group_model"] is True


def test_every_multi_entity_category_flags_group_model() -> None:
    """All five multi-entity categories trip the flag."""
    multi_entity_values = [c.value for c in REQUIRES_GROUP_MODEL]
    assert set(multi_entity_values) == {
        "director_salary",
        "trust_distribution",
        "dividend_timing",
        "spouse_contribution",
        "multi_entity_restructure",
    }
    for value in multi_entity_values:
        assert requires_group_model(StrategyCategory(value)) is True


# ---------------------------------------------------------------------------
# T056 — single-entity category does NOT flag
# ---------------------------------------------------------------------------


def test_prepayment_category_not_flagged() -> None:
    result = _invoke_modeller_tool(
        {
            "scenario_title": "Prepay rent",
            "description": "Prepay 12 months of rent",
            "modified_income": {"revenue": 500_000, "other_income": 0},
            "modified_expenses": {"cost_of_sales": 100_000, "operating_expenses": 275_000},
            "assumptions": ["25k prepayment"],
            "risk_rating": "conservative",
            "compliance_notes": "s82KZM",
            "strategy_category": "prepayment",
        }
    )
    assert result["requires_group_model"] is False


def test_single_entity_categories_never_flagged() -> None:
    for cat in (
        StrategyCategory.PREPAYMENT,
        StrategyCategory.CAPEX_DEDUCTION,
        StrategyCategory.SUPER_CONTRIBUTION,
        StrategyCategory.OTHER,
    ):
        assert requires_group_model(cat) is False


# ---------------------------------------------------------------------------
# T057 — combined strategy excludes flagged scenarios
# ---------------------------------------------------------------------------


def test_combined_total_excludes_flagged_scenarios() -> None:
    scenarios = [
        {
            "scenario_title": "Prepay rent",
            "strategy_id": "prepay-rent",
            "strategy_category": "prepayment",
            "requires_group_model": False,
            "impact": {"change": {"tax_saving": 6_000}},
            "cash_flow_impact": -3_000,
        },
        {
            "scenario_title": "Distribute trust income",
            "strategy_id": "trust-dist",
            "strategy_category": "trust_distribution",
            "requires_group_model": True,
            "impact": {"change": {"tax_saving": 15_000}},
            "cash_flow_impact": 15_000,
        },
    ]

    combined = ScenarioModellerAgent._build_combined_strategy(scenarios)

    # Saving reflects only the unflagged prepayment scenario.
    assert combined["total_tax_saving"] == 6_000
    # Explicitly report the excluded count so the UI can render subtotal text.
    assert combined["excluded_count"] == 1
    # Flagged strategy_id is excluded from the recommended_combination list.
    assert "trust-dist" not in combined["recommended_combination"]
    assert "prepay-rent" in combined["recommended_combination"]


def test_combined_strategy_no_exclusions_reports_zero() -> None:
    scenarios = [
        {
            "scenario_title": "Prepay rent",
            "strategy_id": "prepay-rent",
            "strategy_category": "prepayment",
            "requires_group_model": False,
            "impact": {"change": {"tax_saving": 6_000}},
            "cash_flow_impact": -3_000,
        },
    ]
    combined = ScenarioModellerAgent._build_combined_strategy(scenarios)
    assert combined["excluded_count"] == 0
    assert combined["total_tax_saving"] == 6_000
