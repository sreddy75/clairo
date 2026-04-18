"""Agent 4: Document Advisor.

Generates two documents from the analysis results:
1. Accountant Brief — technical analysis with ATO references
2. Client Summary — plain-language recommendations with action items

The executive summary headers are code-generated from calculator-derived
figures so numbers are always consistent. Claude writes the narrative body
(per-strategy analysis, compliance notes, implementation steps, risk).
"""

import json
import logging
from typing import Any

import anthropic

from app.modules.tax_planning.agents.prompts import ADVISOR_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

MAX_TOKENS = 64000


class AdvisorAgent:
    """Generates dual-audience tax planning documents."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
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
        """Generate accountant brief and client summary."""
        applicable_strategies = [s for s in strategies_evaluated if s.get("applicable")]

        user_prompt = f"""Generate the body sections of both documents for this tax plan.

## Client Profile
{json.dumps(client_profile, indent=2)}

## Financial Year
{financial_year}

## Strategies Evaluated ({len(strategies_evaluated)} total, {len(applicable_strategies)} applicable)
{json.dumps(applicable_strategies[:10], indent=2)}

## Recommended Scenarios (modelled with real calculator — exact before/after figures)
{json.dumps(scenarios, indent=2)}

## Combined Strategy Impact (calculator-derived)
{json.dumps(combined_strategy, indent=2)}

DO NOT write an executive summary or total savings header — those are injected separately.
DO NOT state a combined total tax saving figure — the system provides this.

Write the following sections only:

### Accountant Brief body sections:
- Per-Strategy Analysis (each recommended scenario: description, tax impact from the scenario data above, ATO references, compliance notes)
- Implementation Timeline (specific deadlines relative to EOFY {financial_year})
- Risk Assessment (overall profile, strategies requiring special documentation)
- Compliance Checklist

### Client Summary body sections:
- What to Do (each recommended action as a numbered step with deadline, plain English)
- What You Need to Provide (documents/information the client must gather)
- Important Notes (brief disclaimer, no jargon)

Use "## Accountant Brief Body" and "## Client Summary Body" as section headers."""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=ADVISOR_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        content = response.content[0].text if response.content else ""
        brief_body, summary_body = self._split_documents(content)

        # Prepend code-generated headers with calculator-derived numbers
        brief_header = self._build_brief_header(combined_strategy, scenarios, financial_year)
        summary_header = self._build_summary_header(combined_strategy, scenarios)

        accountant_brief = brief_header + "\n\n" + brief_body
        client_summary = summary_header + "\n\n" + summary_body

        logger.info(
            "Advisor: generated brief (%d chars) + summary (%d chars)",
            len(accountant_brief),
            len(client_summary),
        )

        return accountant_brief, client_summary

    @staticmethod
    def _build_brief_header(
        combined_strategy: dict[str, Any],
        scenarios: list[dict[str, Any]],
        financial_year: str,
    ) -> str:
        total_saving = combined_strategy.get("total_tax_saving", 0)
        strategy_count = combined_strategy.get("strategy_count", len(scenarios))
        excluded_count = combined_strategy.get("excluded_count", 0)
        cash_outlay = combined_strategy.get("total_cash_outlay", 0)

        lines = [
            "# Accountant Brief",
            "",
            "## Executive Summary",
            "",
            f"- **Total Potential Tax Saving:** ${total_saving:,.0f}",
            f"- **Strategies Recommended:** {strategy_count}",
        ]
        if excluded_count:
            lines.append(
                f"- **Multi-Entity Strategies (excluded from total):** {excluded_count} "
                f"— require group tax model to quantify"
            )
        if cash_outlay:
            lines.append(f"- **Estimated Cash Outlay Required:** ${cash_outlay:,.0f}")
        lines.append(f"- **Financial Year:** {financial_year}")
        lines.append(f"- **Implementation Deadline:** 30 June {financial_year.split('-')[1]}")

        return "\n".join(lines)

    @staticmethod
    def _build_summary_header(
        combined_strategy: dict[str, Any],
        scenarios: list[dict[str, Any]],
    ) -> str:
        total_saving = combined_strategy.get("total_tax_saving", 0)
        strategy_count = combined_strategy.get("strategy_count", len(scenarios))
        excluded_count = combined_strategy.get("excluded_count", 0)

        lines = [
            "# Your Tax Savings Summary",
            "",
            f"**We have identified {strategy_count} tax saving strateg"
            f"{'y' if strategy_count == 1 else 'ies'} that could save you "
            f"approximately ${total_saving:,.0f} in tax this financial year.**",
        ]
        if excluded_count:
            lines.append(
                f"\n*Note: {excluded_count} additional strateg"
                f"{'y' if excluded_count == 1 else 'ies'} involving multiple "
                f"entities or related parties may also apply — your accountant "
                f"will discuss these separately.*"
            )
        lines.append(
            "\n*These are estimates based on your current financials. "
            "Your accountant will confirm final figures before implementation.*"
        )
        return "\n".join(lines)

    @staticmethod
    def _split_documents(content: str) -> tuple[str, str]:
        """Split the response into brief body and summary body."""
        split_markers = [
            "## Client Summary Body",
            "## Client Summary",
            "# Client Summary Body",
            "# Client Summary",
            "## Document 2:",
        ]

        for marker in split_markers:
            if marker in content:
                parts = content.split(marker, 1)
                brief = parts[0].strip()
                summary = (marker + parts[1]).strip() if len(parts) > 1 else ""
                return brief, summary

        return content, ""
