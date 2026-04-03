"""Agent 3: Scenario Modeller.

Models top strategies in detail using Claude tool-use with the real
tax calculator. Produces exact before/after tax positions and
identifies the optimal strategy combination.
"""

import logging
from typing import Any

import anthropic

logger = logging.getLogger(__name__)


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
            All tax figures come from calculate_tax_position, not AI estimates.
        """
        raise NotImplementedError("ScenarioModellerAgent.run() not yet implemented")
