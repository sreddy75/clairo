"""Agent 3: Scenario Modeller.

Models top strategies in detail using Claude tool-use with the real
tax calculator. Produces exact before/after tax positions and
identifies the optimal strategy combination.
"""

import json
import logging
from typing import Any

import anthropic

from app.modules.tax_planning.agents.prompts import MODELLER_SYSTEM_PROMPT
from app.modules.tax_planning.prompts import CALCULATE_TAX_TOOL
from app.modules.tax_planning.strategy_category import (
    StrategyCategory,
    requires_group_model,
)
from app.modules.tax_planning.tax_calculator import calculate_tax_position

logger = logging.getLogger(__name__)

MAX_TOKENS = 8000


class ScenarioModellerAgent:
    """Models tax strategies with real calculator numbers via tool-use."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def run(
        self,
        strategies: list[dict[str, Any]],
        financials_data: dict[str, Any],
        entity_type: str,
        rate_configs: dict[str, dict],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Model top strategies with real tax calculator.

        Returns:
            Tuple of (recommended_scenarios, combined_strategy).
        """
        # Filter to applicable strategies only, take top 8
        applicable = [s for s in strategies if s.get("applicable")]
        top_strategies = applicable[:8]

        if not top_strategies:
            return [], {"recommended_combination": [], "total_tax_saving": 0}

        strategies_text = json.dumps(top_strategies, indent=2)
        income = financials_data.get("income", {})
        expenses = financials_data.get("expenses", {})

        user_prompt = f"""Model these tax strategies for the client. Use the calculate_tax_position
tool for EVERY strategy to get exact before/after numbers.

## Current Financials
- Revenue: ${income.get("revenue", 0):,.2f}
- Other Income: ${income.get("other_income", 0):,.2f}
- Cost of Sales: ${expenses.get("cost_of_sales", 0):,.2f}
- Operating Expenses: ${expenses.get("operating_expenses", 0):,.2f}
- Entity Type: {entity_type}

## Strategies to Model
{strategies_text}

Model each strategy individually, then model the BEST COMBINATION of compatible strategies.
For each, call calculate_tax_position with the modified financials."""

        messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
        scenarios: list[dict[str, Any]] = []

        # Tool-use loop (same pattern as existing TaxPlanningAgent)
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=MODELLER_SYSTEM_PROMPT,
            messages=messages,
            tools=[CALCULATE_TAX_TOOL],
        )

        while response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_result = self._execute_tool(
                        block.input,
                        financials_data,
                        entity_type,
                        rate_configs,
                    )
                    scenarios.append(tool_result)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(tool_result),
                        }
                    )

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=MODELLER_SYSTEM_PROMPT,
                messages=messages,
                tools=[CALCULATE_TAX_TOOL],
            )

        # Build combined strategy from scenarios
        combined = self._build_combined_strategy(scenarios)

        logger.info(
            "Modeller: produced %d scenarios, combined saving=$%s",
            len(scenarios),
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
        """Execute the calculate_tax_position tool.

        Reuses the same logic as TaxPlanningAgent._execute_tool.
        """
        modified_income = tool_input.get("modified_income", {})
        modified_expenses = tool_input.get("modified_expenses", {})

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
            "turnover": tool_input.get(
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

        base_position = calculate_tax_position(
            entity_type=entity_type,
            financials_data=base_financials,
            rate_configs=rate_configs,
        )

        modified_position = calculate_tax_position(
            entity_type=entity_type,
            financials_data=modified_financials,
            rate_configs=rate_configs,
        )

        tax_saving = base_position["total_tax_payable"] - modified_position["total_tax_payable"]
        expense_increase = modified_financials["expenses"]["total_expenses"] - base_financials.get(
            "expenses", {}
        ).get("total_expenses", 0)
        cash_flow_impact = tax_saving - max(0, expense_increase)

        # Spec 059 FR-017 — coerce strategy_category to the closed enum and
        # compute requires_group_model in code. Invalid or missing LLM output
        # falls back to OTHER rather than breaking persistence.
        raw_category = tool_input.get("strategy_category")
        try:
            category = StrategyCategory(raw_category) if raw_category else StrategyCategory.OTHER
        except ValueError:
            logger.warning(
                "Modeller emitted invalid strategy_category %r; falling back to OTHER",
                raw_category,
            )
            category = StrategyCategory.OTHER
        needs_group_model = requires_group_model(category)

        # Spec 059 FR-011..FR-016 — provenance tags on every numeric leaf.
        # `before.*` is derived from the accountant's confirmed financials via
        # the pure calculator, so it's `derived`. `after.*` and everything
        # downstream reflects LLM-chosen modifications — estimates until the
        # accountant confirms them via the inline PATCH endpoint.
        source_tags: dict[str, str] = {
            "impact_data.before.taxable_income": "derived",
            "impact_data.before.tax_payable": "derived",
            "impact_data.after.taxable_income": "estimated",
            "impact_data.after.tax_payable": "estimated",
            "impact_data.change.taxable_income_change": "estimated",
            "impact_data.change.tax_saving": "estimated",
            "cash_flow_impact": "estimated",
        }

        return {
            "scenario_title": tool_input.get("scenario_title", "Untitled"),
            "description": tool_input.get("description", ""),
            "assumptions": {"items": tool_input.get("assumptions", [])},
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
            "risk_rating": tool_input.get("risk_rating", "moderate"),
            "compliance_notes": tool_input.get("compliance_notes", ""),
            "strategy_id": tool_input.get("scenario_title", "").lower().replace(" ", "-"),
            "strategy_category": category.value,
            "requires_group_model": needs_group_model,
            "source_tags": source_tags,
        }

    @staticmethod
    def _build_combined_strategy(
        scenarios: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build a combined strategy summary from individual scenarios.

        Spec 059 FR-019 — scenarios flagged `requires_group_model=True`
        (director salary, trust distribution, dividend timing, spouse
        contribution, multi-entity restructure) cannot have their benefit
        computed honestly on a single entity, so they are excluded from the
        combined total. `excluded_count` surfaces to the UI subtotal.
        """
        if not scenarios:
            return {"recommended_combination": [], "total_tax_saving": 0, "excluded_count": 0}

        included = [s for s in scenarios if not s.get("requires_group_model")]
        excluded_count = len(scenarios) - len(included)

        total_saving = sum(
            s.get("impact", {}).get("change", {}).get("tax_saving", 0) for s in included
        )
        total_cash = sum(s.get("cash_flow_impact", 0) for s in included)

        return {
            "recommended_combination": [
                s.get("strategy_id", s.get("scenario_title", "")) for s in included
            ],
            "total_tax_saving": total_saving,
            "total_cash_outlay": -total_cash if total_cash < 0 else 0,
            "net_cash_benefit": total_cash,
            "strategy_count": len(included),
            "excluded_count": excluded_count,
        }
