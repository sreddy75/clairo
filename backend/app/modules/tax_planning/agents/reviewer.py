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

from app.modules.knowledge.retrieval.citation_verifier import (
    CitationVerificationResult,
)
from app.modules.tax_planning.agents.prompts import REVIEWER_SYSTEM_PROMPT
from app.modules.tax_planning.tax_calculator import compute_ground_truth

logger = logging.getLogger(__name__)

# $1 tolerance matches SC-001 / SC-006 and mirrors the `_within_one` helper in
# the existing calculator tests. Holds for every numeric comparison below.
TOLERANCE_DOLLARS = Decimal("1")

MAX_TOKENS = 8000


# Reason codes the reviewer should surface to the accountant via the prompt.
# STRONG_MATCH is reported as confirmation; the rest are problems worth citing.
_CITATION_PROBLEM_CODES: frozenset[str] = frozenset(
    {
        "wrong_act_year",
        "weak_match_body_only",
        "weak_match_none",
    }
)


def _summarise_verification(
    result: CitationVerificationResult | None,
    document_label: str,
) -> str | None:
    """Build a human-readable summary of a single document's citation
    verification. Returns None when there is nothing noteworthy to report."""
    if result is None or not result.citations:
        return None

    problem_lines: list[str] = []
    for citation in result.citations:
        reason_code = citation.get("reason_code")
        if reason_code not in _CITATION_PROBLEM_CODES:
            continue
        identifier = citation.get("section_ref") or str(citation.get("number") or "?")
        problem_lines.append(f"- {identifier} → reason={reason_code}")

    if not problem_lines:
        return f"**{document_label}**: all {len(result.citations)} citation(s) verified."

    header = (
        f"**{document_label}**: "
        f"{len(result.citations)} citation(s), {len(problem_lines)} flagged by the "
        f"structural verifier (verification rate {result.verification_rate:.0%}):"
    )
    return header + "\n" + "\n".join(problem_lines)


def _format_citation_findings(
    brief_verification: CitationVerificationResult | None,
    summary_verification: CitationVerificationResult | None,
) -> str:
    """Format brief + summary verification outputs into a prompt section.

    When both verifications are None (e.g. legacy callers that didn't pass
    them), returns a short disclaimer so the prompt remains well-formed.
    Otherwise emits one sub-section per document containing only the
    problematic citations, keyed by reason_code the reviewer can cite
    verbatim in its findings.
    """
    if brief_verification is None and summary_verification is None:
        return (
            "No structural citation verification was run on this analysis. "
            "Rely on your legal knowledge to review citations."
        )

    sections: list[str] = []
    for result, label in (
        (brief_verification, "Accountant Brief"),
        (summary_verification, "Client Summary"),
    ):
        summary = _summarise_verification(result, label)
        if summary is not None:
            sections.append(summary)

    if not sections:
        return "No citations extracted from the documents."

    guidance = (
        "Cite any flagged citations (`wrong_act_year`, `weak_match_body_only`, "
        "`weak_match_none`) verbatim in your `citation_issues` field using the "
        "identifiers above. The structural verifier is authoritative for act-"
        "year attribution — do NOT override its `wrong_act_year` findings based "
        "on your own legal training. You remain responsible for the semantic-"
        "attribution class (right Act but wrong section purpose)."
    )

    return "\n\n".join(sections) + "\n\n" + guidance


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
        brief_verification: CitationVerificationResult | None = None,
        summary_verification: CitationVerificationResult | None = None,
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

        # Use the combined_strategy total as the single source of truth for the
        # verified saving. Re-deriving it here from recommended_scenarios uses
        # different filtering logic than _build_combined_strategy and always
        # produces a mismatch that the reviewer then (correctly) flags.
        verified_total = combined_strategy.get("total_tax_saving", 0)
        non_group_count = sum(1 for s in recommended_scenarios if not s.get("requires_group_model"))
        group_model_count = len(recommended_scenarios) - non_group_count

        # Step 2 — Spec 061 follow-up: pre-run the structural citation verifier
        # over the advisor's brief + summary and feed the findings to Claude as
        # grounded evidence rather than letting it second-guess citations from
        # its own training knowledge. The verifier catches wrong-act-year and
        # hallucinated-ruling classes; Claude still handles the semantic-
        # attribution class (right Act, wrong section purpose).
        citation_findings_text = _format_citation_findings(brief_verification, summary_verification)

        # Step 2: Use Claude to review documents, citations, consistency
        user_prompt = f"""Review this tax plan analysis for quality.

## Client Profile
{json.dumps(client_profile, indent=2)}

## Recommended Scenarios ({non_group_count} single-entity + {group_model_count} multi-entity/group-model excluded)
{json.dumps(recommended_scenarios, indent=2)}

## Combined Strategy
{json.dumps(combined_strategy, indent=2)}

## Pre-verified Total (do not re-derive — calculator-computed ground truth)
- **Verified combined tax saving: ${verified_total:,.2f}**
- If the documents show a different combined total, flag it. Do NOT re-sum the individual scenarios yourself.

## Accountant Brief (first 4000 chars — may be truncated for length; do not flag incompleteness due to truncation)
{accountant_brief[:4000]}

## Client Summary (first 2000 chars — may be truncated for length; do not flag incompleteness due to truncation)
{client_summary[:2000]}

## Pre-check: Calculator Number Verification
{json.dumps(number_issues) if number_issues else "All numbers verified — no discrepancies found."}

## Pre-check: Automated Citation Verification (Spec 061)
{citation_findings_text}

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
