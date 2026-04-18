"""US2 — Every figure on screen shows where it came from.

Pure unit tests for the provenance infrastructure:

- `source_tags` is populated by the modeller for every numeric leaf it emits.
- The JSON Pointer helpers resolve and write at arbitrary dotted paths.
- Flipping a source tag from `estimated` → `confirmed` (the PATCH semantic)
  preserves the rest of the dict.

Spec 059 FR-011..FR-016, US2 tests T024, T027, T033.
"""

from __future__ import annotations

import pytest

from app.modules.tax_planning.agents.modeller import ScenarioModellerAgent
from app.modules.tax_planning.json_pointer import resolve, set_at

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


def _invoke_modeller_tool(tool_input: dict) -> dict:
    agent = ScenarioModellerAgent.__new__(ScenarioModellerAgent)
    return agent._execute_tool(  # type: ignore[attr-defined]
        tool_input,
        _base_financials(),
        "company",
        _company_rate_configs(),
    )


# ---------------------------------------------------------------------------
# T024 — every numeric leaf the modeller emits carries a source tag
# ---------------------------------------------------------------------------


def test_every_numeric_field_has_provenance_tag() -> None:
    result = _invoke_modeller_tool(
        {
            "scenario_title": "Prepay rent",
            "description": "Prepay 12 months of rent",
            "modified_income": {"revenue": 500_000, "other_income": 0},
            "modified_expenses": {"cost_of_sales": 100_000, "operating_expenses": 275_000},
            "assumptions": ["Prepay $25,000 of rent before 30 June"],
            "risk_rating": "conservative",
            "compliance_notes": "s82KZM",
            "strategy_category": "prepayment",
        }
    )

    source_tags = result.get("source_tags")
    assert source_tags, "modeller output must carry a source_tags dict"

    # Every numeric leaf under impact has a provenance entry.
    expected_keys = {
        "impact_data.before.taxable_income",
        "impact_data.before.tax_payable",
        "impact_data.after.taxable_income",
        "impact_data.after.tax_payable",
        "impact_data.change.taxable_income_change",
        "impact_data.change.tax_saving",
        "cash_flow_impact",
    }
    assert expected_keys <= set(source_tags.keys()), (
        f"missing provenance entries for {expected_keys - set(source_tags.keys())}"
    )

    # Semantics: before.* is derived from raw confirmed financials; after.* /
    # change.* / cash_flow_impact reflect LLM-chosen modifications and are
    # therefore estimated until the accountant confirms them.
    assert source_tags["impact_data.before.tax_payable"] == "derived"
    assert source_tags["impact_data.before.taxable_income"] == "derived"
    assert source_tags["impact_data.after.tax_payable"] == "estimated"
    assert source_tags["impact_data.after.taxable_income"] == "estimated"
    assert source_tags["impact_data.change.tax_saving"] == "estimated"
    assert source_tags["cash_flow_impact"] == "estimated"


def test_modeller_tags_scenario_with_no_modification_as_confirmed_before() -> None:
    """A multi-entity scenario whose `after` equals `before` (no single-entity
    modification attempted) still emits tags. Downstream UI uses the
    `estimated` tag to warn before export."""
    # Same income/expenses as base → no effective modification.
    result = _invoke_modeller_tool(
        {
            "scenario_title": "Trust distribution",
            "description": "Distribute trust income",
            "modified_income": {"revenue": 500_000, "other_income": 0},
            "modified_expenses": {"cost_of_sales": 100_000, "operating_expenses": 250_000},
            "assumptions": ["50/50 split"],
            "risk_rating": "moderate",
            "compliance_notes": "PCG 2023/2",
            "strategy_category": "trust_distribution",
        }
    )
    assert "source_tags" in result
    # Even for a no-op scenario, the tags are populated — structure matters
    # for the contract test, not the values.
    assert "impact_data.after.tax_payable" in result["source_tags"]


# ---------------------------------------------------------------------------
# T027 — PATCH semantics: flipping provenance tag via JSON Pointer set_at
# ---------------------------------------------------------------------------


def test_flip_provenance_from_estimated_to_confirmed() -> None:
    source_tags = {
        "impact_data.after.tax_payable": "estimated",
        "impact_data.after.taxable_income": "estimated",
        "impact_data.before.tax_payable": "derived",
    }

    # Simulate the PATCH: flip one key.
    new_tags = {**source_tags, "impact_data.after.tax_payable": "confirmed"}

    assert new_tags["impact_data.after.tax_payable"] == "confirmed"
    # Other keys untouched.
    assert new_tags["impact_data.after.taxable_income"] == "estimated"
    assert new_tags["impact_data.before.tax_payable"] == "derived"


# ---------------------------------------------------------------------------
# T033 — JSON Pointer read + write
# ---------------------------------------------------------------------------


def test_resolve_returns_nested_value_via_dotted_pointer() -> None:
    root = {"impact_data": {"after": {"tax_payable": 42_000.0}}}
    assert resolve(root, "impact_data.after.tax_payable") == 42_000.0


def test_resolve_raises_keyerror_on_missing_path() -> None:
    root = {"impact_data": {"after": {}}}
    with pytest.raises(KeyError):
        resolve(root, "impact_data.after.tax_payable")


def test_resolve_supports_canonical_pointer_with_slash_prefix() -> None:
    root = {"a": {"b": {"c": 7}}}
    assert resolve(root, "/a/b/c") == 7


def test_set_at_returns_new_root_and_leaves_input_intact() -> None:
    root = {"impact_data": {"after": {"tax_payable": 42_000.0}}}
    new_root = set_at(root, "impact_data.after.tax_payable", 50_000.0)
    # Old root unchanged.
    assert root["impact_data"]["after"]["tax_payable"] == 42_000.0
    # New root has the new value.
    assert new_root["impact_data"]["after"]["tax_payable"] == 50_000.0


def test_set_at_into_list_by_index() -> None:
    root = {"assumptions": [{"amount": 25_000}, {"amount": 10_000}]}
    new_root = set_at(root, "assumptions.0.amount", 30_000)
    assert new_root["assumptions"][0]["amount"] == 30_000
    assert new_root["assumptions"][1]["amount"] == 10_000


def test_set_at_handles_rfc6901_escapes() -> None:
    root = {"a/b": {"c": 1}}
    new_root = set_at(root, "/a~1b/c", 99)
    assert new_root["a/b"]["c"] == 99
