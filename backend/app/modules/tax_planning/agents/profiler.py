"""Agent 1: Client Profiler.

Analyses financial data to determine entity classification,
SBE eligibility, applicable tax rate, and key threshold positions.
"""

import json
import logging
from typing import Any

import anthropic

from app.modules.tax_planning.agents.prompts import PROFILER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

MAX_TOKENS = 8000


class ProfilerAgent:
    """Profiles the client entity from their financial data."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def run(
        self,
        financials_data: dict[str, Any],
        entity_type: str,
        financial_year: str,
    ) -> dict[str, Any]:
        """Analyse financials and produce a client profile.

        Returns:
            Client profile dict with entity classification, eligibility flags,
            applicable tax rate, and key threshold positions.
        """
        income = financials_data.get("income", {})
        expenses = financials_data.get("expenses", {})
        turnover = financials_data.get("turnover", income.get("total_income", 0))

        user_prompt = f"""Analyse this client for tax planning purposes.

Entity type: {entity_type}
Financial year: {financial_year}

Financial data:
- Revenue: ${income.get("revenue", 0):,.2f}
- Other Income: ${income.get("other_income", 0):,.2f}
- Total Income: ${income.get("total_income", 0):,.2f}
- Cost of Sales: ${expenses.get("cost_of_sales", 0):,.2f}
- Operating Expenses: ${expenses.get("operating_expenses", 0):,.2f}
- Total Expenses: ${expenses.get("total_expenses", 0):,.2f}
- Aggregated Turnover: ${turnover:,.2f}

Produce a JSON client profile. Output ONLY the JSON object, no other text."""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=PROFILER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        content = response.content[0].text if response.content else "{}"

        # Parse the JSON response
        try:
            # Handle markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            profile = json.loads(content)
        except (json.JSONDecodeError, IndexError):
            logger.warning("Failed to parse profiler JSON, using fallback")
            profile = self._build_fallback_profile(
                financials_data,
                entity_type,
                financial_year,
                turnover,
            )

        # Ensure required fields
        profile.setdefault("entity_type", entity_type)
        profile.setdefault("financial_year", financial_year)
        profile.setdefault("aggregated_turnover", turnover)

        logger.info(
            "Profiler: %s (%s, turnover=$%s, SBE=%s)",
            profile.get("entity_classification", "unknown"),
            entity_type,
            f"{turnover:,.0f}",
            profile.get("sbe_eligible", "unknown"),
        )

        return profile

    @staticmethod
    def _build_fallback_profile(
        financials_data: dict[str, Any],
        entity_type: str,
        financial_year: str,
        turnover: float,
    ) -> dict[str, Any]:
        """Build a basic profile when Claude's response can't be parsed."""
        income = financials_data.get("income", {})
        expenses = financials_data.get("expenses", {})
        total_income = float(income.get("total_income", 0))
        total_expenses = float(expenses.get("total_expenses", 0))
        net_profit = total_income - total_expenses

        sbe_eligible = turnover < 10_000_000
        tax_rate = 0.25 if (entity_type == "company" and sbe_eligible) else 0.30

        return {
            "entity_type": entity_type,
            "entity_classification": "Small Business Entity" if sbe_eligible else "Standard Entity",
            "sbe_eligible": sbe_eligible,
            "aggregated_turnover": turnover,
            "applicable_tax_rate": tax_rate,
            "has_help_debt": False,
            "financial_year": financial_year,
            "key_thresholds": {
                "sbe_turnover_limit": 10_000_000,
                "base_rate_entity_limit": 50_000_000,
                "instant_asset_writeoff_limit": 20_000,
            },
            "financials_summary": {
                "total_income": total_income,
                "total_expenses": total_expenses,
                "net_profit": net_profit,
                "taxable_income": net_profit,
            },
        }
