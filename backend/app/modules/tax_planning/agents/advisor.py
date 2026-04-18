"""Agent 4: Document Advisor.

Generates two documents from the analysis results:
1. Accountant Brief — technical analysis with ATO references
2. Client Summary — plain-language recommendations with action items
"""

import json
import logging
from typing import Any

import anthropic

from app.modules.tax_planning.agents.prompts import ADVISOR_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

MAX_TOKENS = 12000


class AdvisorAgent:
    """Generates dual-audience tax planning documents."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def run(
        self,
        client_profile: dict[str, Any],
        scenarios: list[dict[str, Any]],
        combined_strategy: dict[str, Any],
        strategies_evaluated: list[dict[str, Any]],
        financials_data: dict[str, Any],
        financial_year: str,
    ) -> tuple[str, str]:
        """Generate accountant brief and client summary.

        Returns:
            Tuple of (accountant_brief_markdown, client_summary_markdown).
        """
        applicable_strategies = [s for s in strategies_evaluated if s.get("applicable")]

        calculated_total = combined_strategy.get("total_tax_saving", 0)
        excluded_count = combined_strategy.get("excluded_count", 0)
        excluded_note = (
            f" ({excluded_count} multi-entity strateg{'y' if excluded_count == 1 else 'ies'} "
            f"excluded — require group tax model)"
            if excluded_count
            else ""
        )

        user_prompt = f"""Generate both documents for this tax plan analysis.

## Client Profile
{json.dumps(client_profile, indent=2)}

## Financial Year
{financial_year}

## Strategies Evaluated ({len(strategies_evaluated)} total, {len(applicable_strategies)} applicable)
{json.dumps(applicable_strategies[:10], indent=2)}

## Recommended Scenarios (modelled with real calculator)
{json.dumps(scenarios, indent=2)}

## Combined Strategy Impact
{json.dumps(combined_strategy, indent=2)}

IMPORTANT: The verified total tax saving is **${calculated_total:,.0f}**{excluded_note}. \
Use this exact figure in both documents — do not recalculate or estimate a different total.

Generate both documents now. Use "## Accountant Brief" and "## Client Summary" as headers
to separate the two documents."""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=ADVISOR_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        content = response.content[0].text if response.content else ""

        # Split into two documents
        accountant_brief, client_summary = self._split_documents(content)

        logger.info(
            "Advisor: generated brief (%d chars) + summary (%d chars)",
            len(accountant_brief),
            len(client_summary),
        )

        return accountant_brief, client_summary

    @staticmethod
    def _split_documents(content: str) -> tuple[str, str]:
        """Split the response into accountant brief and client summary."""
        # Try to split on common headers
        split_markers = [
            "## Client Summary",
            "# Client Summary",
            "## Document 2:",
            "---\n## Client",
            "---\n# Client",
        ]

        for marker in split_markers:
            if marker in content:
                parts = content.split(marker, 1)
                brief = parts[0].strip()
                summary = marker + parts[1] if len(parts) > 1 else ""
                # Clean up the brief header
                brief = brief.replace("## Document 1:", "").replace(
                    "## Accountant Brief", "# Accountant Brief"
                )
                if not brief.startswith("#"):
                    brief = "# Accountant Brief\n\n" + brief
                return brief, summary.strip()

        # Fallback: use entire content as brief, generate minimal summary
        return content, "# Client Summary\n\nPlease see the accountant brief for details."
