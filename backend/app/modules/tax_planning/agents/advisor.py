"""Agent 4: Document Advisor.

Generates two documents from the analysis results:
1. Accountant Brief — technical analysis with ATO references
2. Client Summary — plain-language recommendations with action items
"""

import logging
from typing import Any

import anthropic

logger = logging.getLogger(__name__)


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
        raise NotImplementedError("AdvisorAgent.run() not yet implemented")
