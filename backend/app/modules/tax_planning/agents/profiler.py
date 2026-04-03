"""Agent 1: Client Profiler.

Analyses financial data to determine entity classification,
SBE eligibility, applicable tax rate, and key threshold positions.
"""

import logging
from typing import Any

import anthropic

logger = logging.getLogger(__name__)


class ProfilerAgent:
    """Profiles the client entity from their financial data."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
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
        raise NotImplementedError("ProfilerAgent.run() not yet implemented")
