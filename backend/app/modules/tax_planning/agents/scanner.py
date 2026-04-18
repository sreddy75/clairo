"""Agent 2: Strategy Scanner.

Evaluates 15+ tax strategy categories against the client profile,
using RAG retrieval for ATO compliance citations.
"""

import json
import logging
from typing import Any

import anthropic

from app.modules.tax_planning.agents.prompts import SCANNER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

MAX_TOKENS = 8000


class StrategyScannerAgent:
    """Scans and evaluates applicable tax strategies."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def run(
        self,
        client_profile: dict[str, Any],
        financials_data: dict[str, Any],
        tax_position: dict[str, Any] | None,
        knowledge_chunks: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Evaluate all strategy categories against the client profile.

        Returns:
            List of strategy evaluations with applicability, impact, risk, citations.
        """
        # Build reference material from RAG chunks
        reference_material = ""
        if knowledge_chunks:
            refs = []
            for i, chunk in enumerate(knowledge_chunks, 1):
                title = chunk.get("title", "")
                ruling = chunk.get("ruling_number", "")
                section = chunk.get("section_ref", "")
                text = chunk.get("text", "")[:500]
                identifier = ruling or section or title
                refs.append(f"[{i}] {identifier}: {text}")
            reference_material = "\n\n".join(refs)

        income = financials_data.get("income", {})
        expenses = financials_data.get("expenses", {})
        total_income = float(income.get("total_income", 0))
        total_expenses = float(expenses.get("total_expenses", 0))
        net_profit = total_income - total_expenses
        current_tax = float(tax_position.get("total_tax_payable", 0)) if tax_position else 0

        # Spec 059 FR-008: inline payroll figures into the prompt text so the
        # LLM actually sees them. Nested JSON under client_profile is not
        # sufficient — the scanner frequently treats super/PAYGW as missing
        # and surfaces spurious "set up payroll" strategies otherwise.
        payroll_summary = financials_data.get("payroll_summary") or {}
        payroll_lines = ""
        if payroll_summary:
            total_super_ytd = float(payroll_summary.get("total_super_ytd", 0) or 0)
            total_paygw_ytd = float(payroll_summary.get("total_tax_withheld_ytd", 0) or 0)
            total_wages_ytd = float(payroll_summary.get("total_wages_ytd", 0) or 0)
            employee_count = payroll_summary.get("employee_count", 0)
            payroll_lines = (
                "\n## Payroll (YTD)\n"
                f"- Employees: {employee_count}\n"
                f"- Total Wages YTD: ${total_wages_ytd:,.2f}\n"
                f"- Total Super YTD: ${total_super_ytd:,.2f}\n"
                f"- Total PAYG Withheld YTD: ${total_paygw_ytd:,.2f}\n"
            )
        elif financials_data.get("payroll_status") in {"pending", "unavailable"}:
            payroll_lines = (
                f"\n## Payroll\n- Status: {financials_data.get('payroll_status')} "
                "(figures not yet available; do not fabricate)\n"
            )

        user_prompt = f"""Evaluate tax planning strategies for this client.

## Client Profile
{json.dumps(client_profile, indent=2)}

## Current Financial Position
- Total Income: ${total_income:,.2f}
- Total Expenses: ${total_expenses:,.2f}
- Net Profit: ${net_profit:,.2f}
- Current Tax Payable: ${current_tax:,.2f}
{payroll_lines}
## Reference Material (ATO Knowledge Base)
{reference_material if reference_material else 'No specific references available — use your training knowledge and note "verify independently" for compliance_refs.'}

Evaluate ALL 15+ strategy categories. For each strategy, determine if it is applicable
to this specific client and explain why. Output a JSON array of strategy objects.
Output ONLY the JSON array, no other text."""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=SCANNER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        content = response.content[0].text if response.content else "[]"

        # Parse JSON response
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            strategies = json.loads(content)
            if not isinstance(strategies, list):
                strategies = [strategies]
        except (json.JSONDecodeError, IndexError):
            logger.warning("Failed to parse scanner JSON response")
            strategies = []

        applicable_count = sum(1 for s in strategies if s.get("applicable"))
        logger.info(
            "Scanner: evaluated %d strategies, %d applicable",
            len(strategies),
            applicable_count,
        )

        return strategies
