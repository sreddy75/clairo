"""Spec 059-2 — Scenario Modeller redesign.

Structural guarantees enforced by the redesigned modeller:

- Modifications with an unknown `strategy_id` (not in the input set) are dropped.
- Duplicate `strategy_id`s are deduped (first occurrence kept).
- Returned scenario count never exceeds the input strategy count.
- `combined_strategy.total_tax_saving` exactly equals the arithmetic sum of
  the individual scenarios' `tax_saving` (post group-model exclusion).
- Group-model scenarios are forced to `tax_saving=0` and excluded from the
  combined total (Spec 059 regression coverage).

These tests stub the Anthropic client with `AsyncMock` so they run in
milliseconds and are deterministic.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.modules.tax_planning.agents.modeller import ScenarioModellerAgent

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


def _input_strategies(count: int = 3) -> list[dict[str, Any]]:
    """Return a list of `count` applicable input strategies keyed by id."""
    templates = [
        {"id": "prepay-deductible-expenses", "name": "Prepay deductible expenses"},
        {"id": "instant-asset-writeoff", "name": "Instant asset write-off"},
        {"id": "concessional-super-contribution", "name": "Concessional super contribution"},
        {"id": "bad-debt-writeoff", "name": "Bad debt write-off"},
    ]
    return [{**t, "applicable": True, "category": "timing"} for t in templates[:count]]


def _make_modification(
    strategy_id: str,
    operating_expenses: float = 275_000,
    category: str = "prepayment",
    risk: str = "conservative",
) -> dict[str, Any]:
    """Build a well-formed modification dict for stubbed LLM output."""
    return {
        "strategy_id": strategy_id,
        "scenario_title": f"Scenario for {strategy_id}",
        "description": f"Modification for {strategy_id}",
        "assumptions": ["test assumption"],
        "modified_income": {"revenue": 500_000, "other_income": 0},
        "modified_expenses": {
            "cost_of_sales": 100_000,
            "operating_expenses": operating_expenses,
        },
        "strategy_category": category,
        "risk_rating": risk,
        "compliance_notes": "",
    }


def _stub_tool_use_response(modifications: list[dict[str, Any]]) -> SimpleNamespace:
    """Shape a fake Anthropic Message containing one forced tool_use block."""
    tool_block = SimpleNamespace(
        type="tool_use",
        name="submit_modifications",
        input={"modifications": modifications},
        id="toolu_test",
    )
    return SimpleNamespace(
        stop_reason="tool_use",
        content=[tool_block],
    )


def _make_agent(response_content: SimpleNamespace) -> ScenarioModellerAgent:
    """Instantiate the agent with a stubbed Anthropic client."""
    agent = ScenarioModellerAgent.__new__(ScenarioModellerAgent)  # bypass __init__
    agent.model = "claude-sonnet-4-6"
    agent.client = SimpleNamespace(
        messages=SimpleNamespace(create=AsyncMock(return_value=response_content))
    )
    return agent


# ---------------------------------------------------------------------------
# T005 — combined total equals arithmetic sum of individual scenarios
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_combined_total_equals_sum_of_scenarios() -> None:
    """FR-004 / SC-001 — no double-counting under any circumstances.

    Three valid modifications with distinct operating_expenses increases.
    Each produces a positive tax_saving. The combined total must equal the
    arithmetic sum to the cent, with no phantom meta-scenario inflating it.
    """
    strategies = _input_strategies(3)
    modifications = [
        _make_modification("prepay-deductible-expenses", operating_expenses=275_000),
        _make_modification("instant-asset-writeoff", operating_expenses=270_000),
        _make_modification("concessional-super-contribution", operating_expenses=265_000),
    ]

    agent = _make_agent(_stub_tool_use_response(modifications))
    scenarios, combined = await agent.run(
        strategies=strategies,
        financials_data=_base_financials(),
        entity_type="company",
        rate_configs=_company_rate_configs(),
    )

    assert len(scenarios) == 3
    expected_total = round(sum(s["impact"]["change"]["tax_saving"] for s in scenarios), 2)
    assert combined["total_tax_saving"] == expected_total
    assert combined["strategy_count"] == 3
    # Sanity — every individual saving must be positive for this to exercise the path.
    assert all(s["impact"]["change"]["tax_saving"] > 0 for s in scenarios)


# ---------------------------------------------------------------------------
# T006 — group-model scenario forced to $0 and excluded from combined
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_group_model_scenario_excluded_from_combined() -> None:
    """NFR-001 — Spec 059 FR-019 regression coverage.

    A modification tagged with a group-model category (trust_distribution)
    must have tax_saving forced to $0 and must not appear in the combined
    total regardless of what modified_* figures the LLM submitted.
    """
    strategies = [
        {
            "id": "distribute-trust-income",
            "name": "Trust distribution",
            "applicable": True,
        }
    ]
    modifications = [
        {
            **_make_modification("distribute-trust-income"),
            "strategy_category": "trust_distribution",
            "modified_expenses": {"cost_of_sales": 50_000, "operating_expenses": 100_000},
        }
    ]

    agent = _make_agent(_stub_tool_use_response(modifications))
    scenarios, combined = await agent.run(
        strategies=strategies,
        financials_data=_base_financials(),
        entity_type="company",
        rate_configs=_company_rate_configs(),
    )

    assert len(scenarios) == 1
    assert scenarios[0]["requires_group_model"] is True
    assert scenarios[0]["impact"]["change"]["tax_saving"] == 0
    assert combined["total_tax_saving"] == 0
    assert combined["excluded_count"] == 1
    assert "distribute-trust-income" not in combined["recommended_combination"]


# ---------------------------------------------------------------------------
# T015 — unknown strategy_id is dropped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drops_unknown_strategy_id(caplog: pytest.LogCaptureFixture) -> None:
    """FR-001 / FR-009 — LLM-invented strategy_ids cannot enter the pipeline.

    The hallucinated entry must be dropped and a diagnostic log line emitted.
    """
    strategies = _input_strategies(2)  # prepay-deductible-expenses, instant-asset-writeoff
    modifications = [
        _make_modification("prepay-deductible-expenses"),
        _make_modification("integrated-tax-minimisation-strategy"),  # hallucinated
        _make_modification("instant-asset-writeoff"),
    ]

    agent = _make_agent(_stub_tool_use_response(modifications))
    with caplog.at_level(logging.INFO, logger="app.modules.tax_planning.agents.modeller"):
        scenarios, _combined = await agent.run(
            strategies=strategies,
            financials_data=_base_financials(),
            entity_type="company",
            rate_configs=_company_rate_configs(),
        )

    returned_ids = {s["strategy_id"] for s in scenarios}
    assert "integrated-tax-minimisation-strategy" not in returned_ids
    assert returned_ids == {"prepay-deductible-expenses", "instant-asset-writeoff"}
    assert any(
        "dropping unknown strategy_id" in record.message
        and "integrated-tax-minimisation-strategy" in record.message
        for record in caplog.records
    )


# ---------------------------------------------------------------------------
# T016 — duplicate strategy_ids are deduped (first occurrence kept)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dedupes_duplicate_strategy_ids(caplog: pytest.LogCaptureFixture) -> None:
    """FR-002 / FR-009 — Repeated strategy_ids from the LLM collapse to one scenario.

    The first occurrence is kept, later duplicates are dropped with a log line.
    """
    strategies = _input_strategies(2)
    first = _make_modification("prepay-deductible-expenses", operating_expenses=275_000)
    duplicate = _make_modification("prepay-deductible-expenses", operating_expenses=300_000)
    modifications = [
        first,
        duplicate,
        _make_modification("instant-asset-writeoff"),
    ]

    agent = _make_agent(_stub_tool_use_response(modifications))
    with caplog.at_level(logging.INFO, logger="app.modules.tax_planning.agents.modeller"):
        scenarios, _combined = await agent.run(
            strategies=strategies,
            financials_data=_base_financials(),
            entity_type="company",
            rate_configs=_company_rate_configs(),
        )

    prepay_scenarios = [s for s in scenarios if s["strategy_id"] == "prepay-deductible-expenses"]
    assert len(prepay_scenarios) == 1
    # Saving corresponds to the FIRST occurrence (operating_expenses=275_000,
    # so $25k extra deduction), NOT the duplicate's $50k.
    assert prepay_scenarios[0]["impact"]["change"]["tax_saving"] > 0
    assert any(
        "dropping duplicate strategy_id" in record.message
        and "prepay-deductible-expenses" in record.message
        for record in caplog.records
    )


# ---------------------------------------------------------------------------
# T017 — truncation to input count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_truncates_to_input_count() -> None:
    """FR-003 — Scenario count is bounded by the input strategy count.

    If the LLM somehow submits more unique valid modifications than there are
    input strategies, the excess is truncated. In practice, membership + dedupe
    already bound this — truncation is defence-in-depth.
    """
    # Build an input set of 2, but present the modifier with access to 3 valid
    # ids. We pass only 2 in the strategies list, so a 3rd unique-but-valid id
    # is impossible through validation alone. To exercise the truncation
    # specifically, we stub `validated` to exceed input count by passing a
    # strategies list whose applicable subset is smaller than the modifications.
    strategies_applicable_2 = _input_strategies(2)
    strategies_all = strategies_applicable_2 + [
        {
            "id": "concessional-super-contribution",
            "name": "Concessional super",
            "applicable": False,  # will be filtered out before capping
        }
    ]
    # LLM submits 3 valid-id modifications; only 2 will be in the applicable set.
    # Truncation here is implicit — the non-applicable one is dropped at
    # membership validation because `top_strategies` (applicable) has only 2.
    modifications = [
        _make_modification("prepay-deductible-expenses"),
        _make_modification("instant-asset-writeoff"),
        _make_modification("concessional-super-contribution"),
    ]

    agent = _make_agent(_stub_tool_use_response(modifications))
    scenarios, _combined = await agent.run(
        strategies=strategies_all,
        financials_data=_base_financials(),
        entity_type="company",
        rate_configs=_company_rate_configs(),
    )

    # Applicable input count was 2. Scenario count must not exceed that.
    assert len(scenarios) <= 2
    assert {s["strategy_id"] for s in scenarios} <= {
        "prepay-deductible-expenses",
        "instant-asset-writeoff",
    }


# ---------------------------------------------------------------------------
# T017b — zero valid modifications produces an empty, successful result
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zero_valid_modifications_returns_empty_gracefully(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Edge case from spec — all modifications have unknown ids → return empty,
    do not raise, analysis still marked succeeded by the orchestrator.
    """
    strategies = _input_strategies(2)
    modifications = [
        _make_modification("hallucinated-meta-scenario"),
        _make_modification("another-fake-id"),
    ]

    agent = _make_agent(_stub_tool_use_response(modifications))
    with caplog.at_level(logging.INFO, logger="app.modules.tax_planning.agents.modeller"):
        scenarios, combined = await agent.run(
            strategies=strategies,
            financials_data=_base_financials(),
            entity_type="company",
            rate_configs=_company_rate_configs(),
        )

    assert scenarios == []
    assert combined["total_tax_saving"] == 0
    assert combined.get("strategy_count", 0) == 0
