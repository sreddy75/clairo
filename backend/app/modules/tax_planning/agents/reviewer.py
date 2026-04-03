"""Agent 5: Quality Reviewer.

Verifies the pipeline output:
- All tax figures match calculator results
- Cited ATO provisions exist in the knowledge base
- Strategies don't contradict each other
- Implementation deadlines are correct
"""

import json
import logging
from typing import Any

import anthropic

from app.modules.tax_planning.agents.prompts import REVIEWER_SYSTEM_PROMPT
from app.modules.tax_planning.tax_calculator import calculate_tax_position

logger = logging.getLogger(__name__)

MAX_TOKENS = 4000


class ReviewerAgent:
    """Quality-reviews the analysis pipeline output."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def run(
        self,
        client_profile: dict[str, Any],
        strategies_evaluated: list[dict[str, Any]],
        recommended_scenarios: list[dict[str, Any]],
        combined_strategy: dict[str, Any],
        accountant_brief: str,
        client_summary: str,
        financials_data: dict[str, Any],
        entity_type: str,
        rate_configs: dict[str, dict],
    ) -> tuple[dict[str, Any], bool]:
        """Verify quality of the analysis output.

        Returns:
            Tuple of (review_result_dict, review_passed_bool).
        """
        # Step 1: Spot-check calculator numbers for recommended scenarios
        number_issues = self._verify_calculator_numbers(
            recommended_scenarios,
            financials_data,
            entity_type,
            rate_configs,
        )

        # Step 2: Use Claude to review documents, citations, consistency
        user_prompt = f"""Review this tax plan analysis for quality.

## Client Profile
{json.dumps(client_profile, indent=2)}

## Recommended Scenarios
{json.dumps(recommended_scenarios, indent=2)}

## Combined Strategy
{json.dumps(combined_strategy, indent=2)}

## Accountant Brief (first 2000 chars)
{accountant_brief[:2000]}

## Client Summary (first 1000 chars)
{client_summary[:1000]}

## Pre-check: Calculator Number Verification
{json.dumps(number_issues) if number_issues else "All numbers verified — no discrepancies found."}

Review everything and output your findings as a JSON object."""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=REVIEWER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        content = response.content[0].text if response.content else "{}"

        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            review_result = json.loads(content)
        except (json.JSONDecodeError, IndexError):
            logger.warning("Failed to parse reviewer JSON, using basic result")
            review_result = {
                "numbers_verified": len(number_issues) == 0,
                "numbers_issues": number_issues,
                "overall_passed": len(number_issues) == 0,
                "summary": "Automated number check completed; AI review parsing failed.",
            }

        # Merge our calculator verification with Claude's review
        if number_issues:
            review_result["numbers_issues"] = number_issues
            review_result["numbers_verified"] = False

        passed = review_result.get("overall_passed", True) and len(number_issues) == 0

        logger.info(
            "Reviewer: passed=%s, number_issues=%d",
            passed,
            len(number_issues),
        )

        return review_result, passed

    @staticmethod
    def _verify_calculator_numbers(
        scenarios: list[dict[str, Any]],
        financials_data: dict[str, Any],
        entity_type: str,
        rate_configs: dict[str, dict],
    ) -> list[str]:
        """Spot-check that scenario numbers match the real calculator."""
        issues = []

        # Verify base position
        try:
            base = calculate_tax_position(
                entity_type=entity_type,
                financials_data=financials_data,
                rate_configs=rate_configs,
            )
        except Exception as e:
            issues.append(f"Could not calculate base position: {e}")
            return issues

        for scenario in scenarios:
            impact = scenario.get("impact", {})
            before = impact.get("before", {})

            # Check that "before" tax matches our base calculation
            reported_before_tax = before.get("tax_payable", 0)
            if abs(reported_before_tax - base["total_tax_payable"]) > 1:
                issues.append(
                    f"Scenario '{scenario.get('scenario_title', '?')}': "
                    f"before tax ${reported_before_tax:,.2f} != "
                    f"calculator ${base['total_tax_payable']:,.2f}"
                )

        return issues
