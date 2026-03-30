"""TaxPlanningAgent — standalone AI agent with Claude tool-use.

Uses anthropic AsyncAnthropic client for non-blocking LLM calls.
The agent calls calculate_tax_position as a tool to produce accurate
before/after tax figures (never generates numbers from the LLM).
"""

import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

import anthropic

from app.modules.tax_planning.prompts import (
    CALCULATE_TAX_TOOL,
    TAX_PLANNING_SYSTEM_PROMPT,
    format_financial_context,
    format_scenario_history,
)
from app.modules.tax_planning.tax_calculator import calculate_tax_position

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4000


@dataclass
class AgentResponse:
    """Response from the TaxPlanningAgent."""

    content: str
    scenarios: list[dict[str, Any]] = field(default_factory=list)
    token_usage: dict[str, int] = field(default_factory=dict)


class TaxPlanningAgent:
    """AI agent for tax scenario modelling using Claude tool-use."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def process_message(
        self,
        message: str,
        plan_financials: dict,
        plan_tax_position: dict | None,
        entity_type: str,
        financial_year: str,
        conversation_history: list[dict[str, str]],
        existing_scenarios: list,
        rate_configs: dict[str, dict],
    ) -> AgentResponse:
        """Process a user message and generate scenario responses.

        Uses Claude tool-use loop: Claude calls calculate_tax_position,
        we execute the tool and return the result, Claude continues.
        """
        system_prompt = self._build_system_prompt(
            plan_financials,
            plan_tax_position,
            entity_type,
            financial_year,
            existing_scenarios,
        )

        messages = self._build_messages(conversation_history, message)
        scenarios: list[dict[str, Any]] = []

        # Tool-use loop
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=messages,
            tools=[CALCULATE_TAX_TOOL],
        )

        # Handle tool calls in a loop
        while response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_input = block.input
                    tool_result = self._execute_tool(
                        tool_input,
                        plan_financials,
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

            # Continue the conversation with tool results
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=messages,
                tools=[CALCULATE_TAX_TOOL],
            )

        # Extract final text content
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        token_usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

        return AgentResponse(
            content=content,
            scenarios=scenarios,
            token_usage=token_usage,
        )

    async def process_message_streaming(
        self,
        message: str,
        plan_financials: dict,
        plan_tax_position: dict | None,
        entity_type: str,
        financial_year: str,
        conversation_history: list[dict[str, str]],
        existing_scenarios: list,
        rate_configs: dict[str, dict],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a response with SSE events.

        Yields dicts with 'type' and event-specific fields.
        """
        system_prompt = self._build_system_prompt(
            plan_financials,
            plan_tax_position,
            entity_type,
            financial_year,
            existing_scenarios,
        )
        messages = self._build_messages(conversation_history, message)
        scenarios: list[dict[str, Any]] = []

        yield {"type": "thinking", "content": "Analysing scenario..."}

        # Initial call
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=messages,
            tools=[CALCULATE_TAX_TOOL],
        )

        # Tool-use loop
        while response.stop_reason == "tool_use":
            yield {"type": "thinking", "content": "Calculating tax impact..."}

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_input = block.input
                    tool_result = self._execute_tool(
                        tool_input,
                        plan_financials,
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
                    yield {"type": "scenario", "scenario": tool_result}

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=messages,
                tools=[CALCULATE_TAX_TOOL],
            )

        # Stream final text
        for block in response.content:
            if hasattr(block, "text"):
                yield {"type": "content", "content": block.text}

        yield {
            "type": "done",
            "scenarios_created": [s.get("scenario_title", "") for s in scenarios],
        }

    def _build_system_prompt(
        self,
        financials: dict,
        tax_position: dict | None,
        entity_type: str,
        financial_year: str,
        existing_scenarios: list,
    ) -> str:
        financial_context = format_financial_context(
            financials,
            tax_position,
            entity_type,
        )
        scenario_history = format_scenario_history(existing_scenarios)

        return TAX_PLANNING_SYSTEM_PROMPT.format(
            financial_context=financial_context,
            financial_year=financial_year,
            entity_type=entity_type,
            scenario_history=scenario_history,
        )

    def _build_messages(
        self,
        conversation_history: list[dict[str, str]],
        new_message: str,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for msg in conversation_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": new_message})
        return messages

    def _execute_tool(
        self,
        tool_input: dict[str, Any],
        base_financials: dict,
        entity_type: str,
        rate_configs: dict[str, dict],
    ) -> dict[str, Any]:
        """Execute the calculate_tax_position tool with modified financials."""
        # Build modified financials from tool input
        modified_income = tool_input.get("modified_income", {})
        modified_expenses = tool_input.get("modified_expenses", {})

        modified_financials = {
            "income": {
                "revenue": modified_income.get(
                    "revenue", base_financials.get("income", {}).get("revenue", 0)
                ),
                "other_income": modified_income.get(
                    "other_income",
                    base_financials.get("income", {}).get("other_income", 0),
                ),
                "total_income": 0,  # Will be calculated
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
                "total_expenses": 0,  # Will be calculated
            },
            "credits": base_financials.get("credits", {}),
            "adjustments": base_financials.get("adjustments", []),
            "turnover": tool_input.get("modified_turnover", base_financials.get("turnover", 0)),
        }

        # Recalculate totals
        modified_financials["income"]["total_income"] = (
            modified_financials["income"]["revenue"] + modified_financials["income"]["other_income"]
        )
        modified_financials["expenses"]["total_expenses"] = (
            modified_financials["expenses"]["cost_of_sales"]
            + modified_financials["expenses"]["operating_expenses"]
        )

        # Calculate base and modified positions
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

        # Build impact data
        tax_saving = base_position["total_tax_payable"] - modified_position["total_tax_payable"]
        taxable_income_change = (
            modified_position["taxable_income"] - base_position["taxable_income"]
        )

        # Estimate cash flow impact
        # Simple heuristic: net cash impact = tax saving - additional outlay
        # The outlay is the increase in expenses
        expense_increase = modified_financials["expenses"]["total_expenses"] - base_financials.get(
            "expenses", {}
        ).get("total_expenses", 0)
        cash_flow_impact = tax_saving - max(0, expense_increase)

        return {
            "scenario_title": tool_input.get("scenario_title", "Untitled Scenario"),
            "description": tool_input.get("description", ""),
            "assumptions": {"items": tool_input.get("assumptions", [])},
            "impact_data": {
                "before": {
                    "taxable_income": base_position["taxable_income"],
                    "tax_payable": base_position["total_tax_payable"],
                    "net_position": base_position["net_position"],
                },
                "after": {
                    "taxable_income": modified_position["taxable_income"],
                    "tax_payable": modified_position["total_tax_payable"],
                    "net_position": modified_position["net_position"],
                },
                "change": {
                    "taxable_income_change": taxable_income_change,
                    "tax_saving": tax_saving,
                    "net_benefit": tax_saving,
                },
            },
            "risk_rating": tool_input.get("risk_rating", "moderate"),
            "compliance_notes": tool_input.get("compliance_notes", ""),
            "cash_flow_impact": cash_flow_impact,
        }
