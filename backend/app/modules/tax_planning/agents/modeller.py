"""Agent 3: Scenario Modeller.

Models strategies in detail using the deterministic tax calculator. The
language model's role is narrowed: it returns a structured list of strategy
modifications in a single forced tool call, and Python iterates that list
calling the calculator once per validated modification.

This design replaces the earlier LLM-controlled tool-use loop so that the
number of scenarios is bounded by code, not inferred from model behaviour.
See spec 059-2-tax-planning-correctness-followup.
"""

import json
import logging
from typing import Any

import anthropic

from app.modules.tax_planning.agents.prompts import MODELLER_SYSTEM_PROMPT
from app.modules.tax_planning.prompts import SUBMIT_MODIFICATIONS_TOOL
from app.modules.tax_planning.strategy_category import (
    StrategyCategory,
    requires_group_model,
)
from app.modules.tax_planning.tax_calculator import calculate_tax_position

logger = logging.getLogger(__name__)

MAX_TOKENS = 12_000


def _compute_scenario(
    modification: dict[str, Any],
    base_financials: dict[str, Any],
    entity_type: str,
    rate_configs: dict[str, dict],
) -> dict[str, Any]:
    """Run the tax calculator for one strategy modification and return a
    scenario dict in the shape persisted under `TaxPlanAnalysis.recommended_scenarios`.

    This is the deterministic core of the modeller — no language-model calls,
    no loops, no meta-scenarios. Pure function, trivially unit-testable.

    Spec 059 provenance (source_tags), group-model gate (`requires_group_model`),
    and enum coercion (strategy_category, risk_rating) are preserved here
    verbatim from the prior implementation.
    """
    modified_income = modification.get("modified_income", {}) or {}
    modified_expenses = modification.get("modified_expenses", {}) or {}

    modified_financials = {
        "income": {
            "revenue": modified_income.get(
                "revenue",
                base_financials.get("income", {}).get("revenue", 0),
            ),
            "other_income": modified_income.get(
                "other_income",
                base_financials.get("income", {}).get("other_income", 0),
            ),
            "total_income": 0,
        },
        "expenses": {
            "cost_of_sales": modified_expenses.get(
                "cost_of_sales",
                base_financials.get("expenses", {}).get("cost_of_sales", 0),
            ),
            "operating_expenses": modified_expenses.get(
                "operating_expenses",
                base_financials.get("expenses", {}).get("operating_expenses", 0),
            ),
            "total_expenses": 0,
        },
        "credits": base_financials.get("credits", {}),
        "adjustments": base_financials.get("adjustments", []),
        "turnover": modification.get(
            "modified_turnover",
            base_financials.get("turnover", 0),
        ),
    }

    modified_financials["income"]["total_income"] = (
        modified_financials["income"]["revenue"] + modified_financials["income"]["other_income"]
    )
    modified_financials["expenses"]["total_expenses"] = (
        modified_financials["expenses"]["cost_of_sales"]
        + modified_financials["expenses"]["operating_expenses"]
    )

    # Coerce strategy_category before deciding requires_group_model so the
    # group-model gate below uses the validated value, not raw LLM output.
    raw_category = modification.get("strategy_category")
    try:
        category = StrategyCategory(raw_category) if raw_category else StrategyCategory.OTHER
    except ValueError:
        logger.warning(
            "Modeller emitted invalid strategy_category %r; falling back to OTHER",
            raw_category,
        )
        category = StrategyCategory.OTHER
    needs_group_model = requires_group_model(category)

    base_position = calculate_tax_position(
        entity_type=entity_type,
        financials_data=base_financials,
        rate_configs=rate_configs,
    )

    # F-02: group-model strategies cannot be quantified on a single-entity
    # basis — force modified_position == base_position in code so the
    # tax_saving is always exactly $0 regardless of what the LLM passed.
    if needs_group_model:
        modified_position = base_position
    else:
        modified_position = calculate_tax_position(
            entity_type=entity_type,
            financials_data=modified_financials,
            rate_configs=rate_configs,
        )

    tax_saving = round(
        base_position["total_tax_payable"] - modified_position["total_tax_payable"], 2
    )
    expense_increase = modified_financials["expenses"]["total_expenses"] - base_financials.get(
        "expenses", {}
    ).get("total_expenses", 0)
    cash_flow_impact = round(tax_saving - max(0, expense_increase), 2)

    # Spec 059 FR-011..FR-016 — provenance tags on every numeric leaf.
    source_tags: dict[str, str] = {
        "impact_data.before.taxable_income": "derived",
        "impact_data.before.tax_payable": "derived",
        "impact_data.after.taxable_income": "estimated",
        "impact_data.after.tax_payable": "estimated",
        "impact_data.change.taxable_income_change": "estimated",
        "impact_data.change.tax_saving": "estimated",
        "cash_flow_impact": "estimated",
    }

    # strategy_id: prefer the validated ID from the modification (new forced-tool-call
    # flow). Fall back to a slug of the title when absent (keeps the legacy
    # `ScenarioModellerAgent._execute_tool` direct-invocation tests working —
    # they don't supply strategy_id because the old flow derived it from the
    # scenario_title).
    strategy_id = modification.get("strategy_id") or (
        modification.get("scenario_title", "").lower().replace(" ", "-")
    )

    raw_risk = modification.get("risk_rating", "moderate")
    risk_rating = raw_risk if raw_risk in {"conservative", "moderate", "aggressive"} else "moderate"

    return {
        "scenario_title": modification.get("scenario_title", "Untitled"),
        "description": modification.get("description", ""),
        "assumptions": {"items": modification.get("assumptions", [])},
        "impact": {
            "before": {
                "taxable_income": base_position["taxable_income"],
                "tax_payable": base_position["total_tax_payable"],
            },
            "after": {
                "taxable_income": modified_position["taxable_income"],
                "tax_payable": modified_position["total_tax_payable"],
            },
            "change": {
                "taxable_income_change": (
                    modified_position["taxable_income"] - base_position["taxable_income"]
                ),
                "tax_saving": tax_saving,
            },
        },
        "cash_flow_impact": cash_flow_impact,
        "risk_rating": risk_rating,
        "compliance_notes": modification.get("compliance_notes", ""),
        "strategy_id": strategy_id,
        "strategy_category": category.value,
        "requires_group_model": needs_group_model,
        "source_tags": source_tags,
    }


class ScenarioModellerAgent:
    """Models tax strategies via a single forced tool call + deterministic iteration.

    The language model returns one structured list of per-strategy modifications.
    Python validates that list (membership, dedupe, truncation) and iterates it
    calling `_compute_scenario` once per validated entry. The number of
    scenarios returned is bounded by `len(input_strategies)` — it cannot exceed
    the input count regardless of what the model emits.
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def run(
        self,
        strategies: list[dict[str, Any]],
        financials_data: dict[str, Any],
        entity_type: str,
        rate_configs: dict[str, dict],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Model applicable strategies with the deterministic tax calculator.

        Returns:
            Tuple of (recommended_scenarios, combined_strategy). Signature is
            stable across the 059-2 redesign — orchestrator contract unchanged.
        """
        applicable = [s for s in strategies if s.get("applicable")]
        top_strategies = applicable[:8]

        if not top_strategies:
            return [], _build_combined_strategy([])

        # Scanner emits `strategy_id` (kebab-case, category-prefixed). Accept
        # `id` as a fallback for any upstream that uses the shorter key.
        input_ids: set[str] = {
            s.get("strategy_id") or s.get("id")
            for s in top_strategies
            if s.get("strategy_id") or s.get("id")
        }

        strategies_text = json.dumps(top_strategies, indent=2)
        income = financials_data.get("income", {})
        expenses = financials_data.get("expenses", {})

        user_prompt = f"""Describe how each applicable tax strategy below would modify this client's
full-year financials. Call `submit_modifications` exactly once with one entry per strategy
you want to model. Copy each strategy's `strategy_id` value VERBATIM into the `strategy_id`
field of your modification — no renaming, no paraphrasing.

## Current Financials (full financial year)
- Revenue: ${income.get("revenue", 0):,.2f}
- Other Income: ${income.get("other_income", 0):,.2f}
- Cost of Sales: ${expenses.get("cost_of_sales", 0):,.2f}
- Operating Expenses: ${expenses.get("operating_expenses", 0):,.2f}
- Entity Type: {entity_type}

## Strategies to Model
{strategies_text}

Return ONLY the `submit_modifications` tool call. The tax calculator runs in code
over your modifications — you do not compute tax figures yourself."""

        messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=MODELLER_SYSTEM_PROMPT,
            messages=messages,
            tools=[SUBMIT_MODIFICATIONS_TOOL],
            tool_choice={"type": "tool", "name": "submit_modifications"},
        )

        # Extract the forced tool-use block. Schema validation at the API boundary
        # guarantees the `input` object shape — we only validate semantic
        # correctness (strategy_id membership, dedupe) below.
        modifications_raw: list[dict[str, Any]] = []
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_modifications":
                modifications_raw = block.input.get("modifications", []) or []
                break

        if not modifications_raw:
            logger.warning(
                "Modeller: LLM returned no modifications (stop_reason=%r); "
                "producing empty scenario list",
                response.stop_reason,
            )
            return [], _build_combined_strategy([])

        # Validate modifications: drop unknown strategy_ids, dedupe by first
        # occurrence, truncate to input count. These are the three structural
        # guarantees that make meta-scenarios impossible by construction.
        validated: list[dict[str, Any]] = []
        seen: set[str] = set()
        dropped_unknown = 0
        dropped_duplicate = 0
        for mod in modifications_raw:
            sid = mod.get("strategy_id")
            if sid not in input_ids:
                logger.info(
                    "Modeller: dropping unknown strategy_id=%r (not in input set)",
                    sid,
                )
                dropped_unknown += 1
                continue
            if sid in seen:
                logger.info(
                    "Modeller: dropping duplicate strategy_id=%r (first occurrence kept)",
                    sid,
                )
                dropped_duplicate += 1
                continue
            seen.add(sid)
            validated.append(mod)

        if len(validated) > len(top_strategies):
            logger.info(
                "Modeller: truncating %d modifications to input count %d",
                len(validated),
                len(top_strategies),
            )
            validated = validated[: len(top_strategies)]

        # Run the deterministic calculator over each validated modification.
        scenarios = [
            _compute_scenario(mod, financials_data, entity_type, rate_configs) for mod in validated
        ]

        combined = _build_combined_strategy(scenarios)

        logger.info(
            "Modeller: produced %d scenarios (from %d validated modifications, "
            "dropped %d unknown + %d duplicate), combined saving=$%s",
            len(scenarios),
            len(validated),
            dropped_unknown,
            dropped_duplicate,
            f"{combined.get('total_tax_saving', 0):,.0f}",
        )

        return scenarios, combined

    def _execute_tool(
        self,
        tool_input: dict[str, Any],
        base_financials: dict[str, Any],
        entity_type: str,
        rate_configs: dict[str, dict],
    ) -> dict[str, Any]:
        """Thin backwards-compatible alias for `_compute_scenario`.

        Retained so legacy direct-invocation tests (test_provenance.py,
        test_strategy_category_honesty.py) keep working without modification.
        New code should call `_compute_scenario` directly.
        """
        return _compute_scenario(tool_input, base_financials, entity_type, rate_configs)


def _build_combined_strategy(
    scenarios: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a combined strategy summary from individual scenarios.

    Spec 059 FR-019 — scenarios flagged `requires_group_model=True`
    (director salary, trust distribution, dividend timing, spouse
    contribution, multi-entity restructure) cannot have their benefit
    computed honestly on a single entity, so they are excluded from the
    combined total. `excluded_count` surfaces to the UI subtotal.

    Note (059-2): the three legacy meta-scenario filter layers (hard cap,
    keyword name strip, structural 1.1x ratio) have been removed. The
    redesigned `run()` can no longer produce meta-scenarios — any modification
    whose strategy_id is not in the input set is dropped at validation, so by
    the time scenarios reach this function there is nothing to filter.
    """
    if not scenarios:
        return {"recommended_combination": [], "total_tax_saving": 0, "excluded_count": 0}

    included = [
        s
        for s in scenarios
        if not s.get("requires_group_model")
        and (s.get("impact") or s.get("impact_data") or {}).get("change", {}).get("tax_saving", 0)
        > 0
    ]
    excluded_count = len(scenarios) - len(included)

    total_saving = round(
        sum(s.get("impact", {}).get("change", {}).get("tax_saving", 0) for s in included),
        2,
    )
    total_cash = round(sum(s.get("cash_flow_impact", 0) for s in included), 2)

    return {
        "recommended_combination": [
            s.get("strategy_id", s.get("scenario_title", "")) for s in included
        ],
        "total_tax_saving": total_saving,
        "total_cash_outlay": round(-total_cash, 2) if total_cash < 0 else 0,
        "net_cash_benefit": total_cash,
        "strategy_count": len(included),
        "excluded_count": excluded_count,
    }


# Backwards-compatible class-level alias — pre-059-2 tests call
# `ScenarioModellerAgent._build_combined_strategy(scenarios)` as a staticmethod.
# Assigned after both definitions exist at module scope.
ScenarioModellerAgent._build_combined_strategy = staticmethod(_build_combined_strategy)  # type: ignore[attr-defined]
