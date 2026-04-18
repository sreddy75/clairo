"""Agent 5: Quality Reviewer.

Verifies the pipeline output:
- All tax figures match calculator results
- Cited ATO provisions exist in the knowledge base
- Strategies don't contradict each other
- Implementation deadlines are correct
"""

import json
import logging
from decimal import Decimal
from typing import Any

import anthropic

from app.modules.tax_planning.agents.prompts import REVIEWER_SYSTEM_PROMPT
from app.modules.tax_planning.tax_calculator import compute_ground_truth

logger = logging.getLogger(__name__)

# $1 tolerance matches SC-001 / SC-006 and mirrors the `_within_one` helper in
# the existing calculator tests. Holds for every numeric comparison below.
TOLERANCE_DOLLARS = Decimal("1")

MAX_TOKENS = 8000


class ReviewerAgent:
    """Quality-reviews the analysis pipeline output."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
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
        # Step 1: Independent ground-truth re-derivation and per-scenario
        # comparison (Spec 059 US5 FR-011..FR-014). Returns a legacy human
        # string list plus the structured disagreements the UI consumes.
        number_issues, disagreements = self._verify_calculator_numbers(
            recommended_scenarios,
            financials_data,
            entity_type,
            rate_configs,
        )

        # Build scenario summary so the reviewer doesn't re-derive totals by hand
        non_group_scenarios = [s for s in recommended_scenarios if not s.get("requires_group_model")]
        scenario_total = sum(
            (s.get("impact") or s.get("impact_data") or {})
            .get("change", {})
            .get("tax_saving", 0)
            for s in non_group_scenarios
        )
        group_model_count = len(recommended_scenarios) - len(non_group_scenarios)

        # Step 2: Use Claude to review documents, citations, consistency
        user_prompt = f"""Review this tax plan analysis for quality.

## Client Profile
{json.dumps(client_profile, indent=2)}

## Recommended Scenarios ({len(non_group_scenarios)} single-entity + {group_model_count} multi-entity/group-model excluded)
{json.dumps(recommended_scenarios, indent=2)}

## Combined Strategy
{json.dumps(combined_strategy, indent=2)}

## Pre-verified Totals (do not re-derive these — they are calculator-computed)
- Sum of single-entity scenario tax savings: ${scenario_total:,.2f}
- combined_strategy.total_tax_saving: ${combined_strategy.get('total_tax_saving', 0):,.2f}
- These two figures should match. If the documents show a different total, flag it.

## Accountant Brief (first 4000 chars — may be truncated for length; do not flag incompleteness due to truncation)
{accountant_brief[:4000]}

## Client Summary (first 2000 chars — may be truncated for length; do not flag incompleteness due to truncation)
{client_summary[:2000]}

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

        # Merge our calculator verification with Claude's review. The
        # structured disagreements list is always populated (empty when clean)
        # so the frontend can render either the OK state or the banner.
        review_result["disagreements"] = disagreements
        if number_issues:
            review_result["numbers_issues"] = number_issues
            review_result["numbers_verified"] = False
        else:
            review_result.setdefault("numbers_verified", True)

        passed = review_result.get("overall_passed", False) and not disagreements

        logger.info(
            "Reviewer: passed=%s, number_issues=%d, disagreements=%d",
            passed,
            len(number_issues),
            len(disagreements),
        )

        return review_result, passed

    @staticmethod
    def _verify_calculator_numbers(
        scenarios: list[dict[str, Any]],
        financials_data: dict[str, Any],
        entity_type: str,
        rate_configs: dict[str, dict],
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """Compare every recommended scenario's `before.*` numbers against an
        independent ground-truth re-derivation with a $1 tolerance.

        Returns `(issue_strings, disagreements)`. The issue strings are kept
        for backward compatibility with the existing reviewer LLM prompt;
        `disagreements` is the structured list consumed by the UI banner and
        per-scenario badge (Spec 059 FR-013).
        """
        issues: list[str] = []
        disagreements: list[dict[str, Any]] = []

        try:
            truth = compute_ground_truth(
                financials_data=financials_data,
                rate_configs=rate_configs,
                entity_type=entity_type,
            )
        except Exception as e:
            issues.append(f"Could not compute ground truth: {e}")
            return issues, disagreements

        expected_fields: list[tuple[str, Decimal]] = [
            ("impact.before.tax_payable", truth.total_tax_payable),
            ("impact.before.taxable_income", truth.taxable_income),
        ]

        for scenario in scenarios:
            scenario_id = scenario.get("id") or scenario.get("scenario_title", "?")
            title = scenario.get("scenario_title", "?")
            # Modeller output uses `impact_data` (DB column) in some paths and
            # `impact` in others — accept either.
            impact = scenario.get("impact") or scenario.get("impact_data") or {}
            before = impact.get("before", {})

            for field_path, expected in expected_fields:
                leaf = field_path.rsplit(".", 1)[-1]
                got_raw = before.get(leaf)
                if got_raw is None:
                    continue
                try:
                    got = Decimal(str(got_raw))
                except (TypeError, ValueError, ArithmeticError):
                    continue
                delta = abs(got - expected)
                if delta > TOLERANCE_DOLLARS:
                    disagreements.append(
                        {
                            "scenario_id": str(scenario_id),
                            "field_path": field_path,
                            "expected": float(expected),
                            "got": float(got),
                            "delta": float(delta),
                        }
                    )
                    issues.append(
                        f"Scenario '{title}' {field_path}: "
                        f"expected ${expected:,.2f}, got ${got:,.2f} "
                        f"(delta ${delta:,.2f})"
                    )

        return issues, disagreements
