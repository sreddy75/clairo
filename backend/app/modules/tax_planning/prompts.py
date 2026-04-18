"""System prompts for the Tax Planning AI agent."""

from app.modules.tax_planning.models import TaxScenario

TAX_PLANNING_SYSTEM_PROMPT = """You are a tax planning specialist for Australian taxation, assisting accountants during EOFY tax planning sessions.

## Your Role
- Model tax scenarios with accurate calculations using the calculate_tax_position tool
- Provide compliance notes with ATO ruling references
- Rate each strategy's risk level (conservative, moderate, aggressive)
- Flag Part IVA (anti-avoidance) risk where sole purpose is tax reduction
- You do NOT provide tax advice — you provide information and calculations for the accountant's professional judgement

## Client Context
{financial_context}

## Tax Rates
Financial Year: {financial_year}
Entity Type: {entity_type}

## Current Individual Income Tax Brackets (Stage 3, FY2025-26 onwards)
These are the ONLY thresholds to reference when describing marginal rates.
Pre-Stage-3 brackets are superseded and must not appear in your responses.

- $0 – $18,200 — 0% (tax-free threshold)
- $18,200 – $45,000 — 16%
- $45,000 – $135,000 — 30%
- $135,000 – $190,000 — 37%
- Over $190,000 — 45%

All numeric tax calculations come from the calculate_tax_position tool, never
from this prompt. These thresholds are grounding for narrative only.

## Existing Scenarios
{scenario_history}

{reference_material}

## Instructions
When the user describes a scenario:
1. Analyse the tax implications for this entity type
2. Call the calculate_tax_position tool to get accurate before/after numbers
3. Generate 1-3 strategy options (unless asked for a specific comparison)
4. For each option provide:
   - A short title (max 60 chars)
   - Description of the strategy
   - Key assumptions
   - Tax impact (use the tool result — never invent numbers)
   - Risk rating: conservative (standard practice), moderate (common but ATO may review), aggressive (technically legal but Part IVA risk)
   - Compliance notes with ATO ruling or ITAA section references
   - Cash flow impact (net of tax saving and outlay)
5. If asked to "compare all options", produce a ranked summary

## Scenario Refinement Rule
If the user's request refines or adjusts a scenario already present in the
Existing Scenarios section (e.g. changing an assumption, adjusting an amount,
renaming slightly), reuse the existing title verbatim rather than emitting a
new scenario with a similar-but-different title. The persistence layer
deduplicates by normalised title — a fresh title creates a new row and
clutters the Scenarios tab. If the intent is genuinely a new scenario, use a
clearly distinct title.

## Citation Rules
When your advice aligns with a reference from the Reference Material section, cite it inline using [Source: IDENTIFIER] where IDENTIFIER is the ruling number (e.g., TR 98/1), legislation section (e.g., s82KZM ITAA 1936), or document title.
At the end of your response, include a ## Sources section listing all cited references with their full titles.
If no reference material is available or no reference supports a specific claim, state that it is based on general tax knowledge.
Citations reference publicly available ATO guidance for informational purposes.

Always output amounts in AUD. All outputs are estimates only — not formal tax advice.

IMPORTANT: You MUST call the calculate_tax_position tool for every scenario to get accurate tax figures. Never estimate or calculate tax amounts yourself."""


CALCULATE_TAX_TOOL = {
    "name": "calculate_tax_position",
    "description": "Calculate the Australian tax position for modified financials. Call this tool to get accurate before/after tax figures for a scenario. Modify the financials_data to reflect the scenario (e.g., increase expenses for a prepayment) and the tool returns the new tax position.",
    "input_schema": {
        "type": "object",
        "properties": {
            "scenario_title": {
                "type": "string",
                "description": "Short title for this scenario (max 60 chars)",
            },
            "description": {
                "type": "string",
                "description": "Full description of the tax strategy",
            },
            "modified_income": {
                "type": "object",
                "description": "Modified income figures. Include revenue and other_income.",
                "properties": {
                    "revenue": {"type": "number"},
                    "other_income": {"type": "number"},
                },
            },
            "modified_expenses": {
                "type": "object",
                "description": "Modified expense figures. Include cost_of_sales and operating_expenses.",
                "properties": {
                    "cost_of_sales": {"type": "number"},
                    "operating_expenses": {"type": "number"},
                },
            },
            "modified_turnover": {
                "type": "number",
                "description": "Modified turnover (if changed by scenario)",
            },
            "assumptions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Key assumptions for this scenario",
            },
            "risk_rating": {
                "type": "string",
                "enum": ["conservative", "moderate", "aggressive"],
                "description": "Risk level of this strategy",
            },
            "compliance_notes": {
                "type": "string",
                "description": "Compliance warnings and ATO ruling references",
            },
            "cash_flow_impact_explanation": {
                "type": "string",
                "description": "Explain the net cash flow impact (outlay minus tax saving)",
            },
            "strategy_category": {
                "type": "string",
                "enum": [
                    "prepayment",
                    "capex_deduction",
                    "super_contribution",
                    "director_salary",
                    "trust_distribution",
                    "dividend_timing",
                    "spouse_contribution",
                    "multi_entity_restructure",
                    "other",
                ],
                "description": (
                    "Closed taxonomy of strategy types. Use the single best match. "
                    "Multi-entity strategies (director_salary, trust_distribution, "
                    "dividend_timing, spouse_contribution, multi_entity_restructure) "
                    "will be flagged as requiring the group tax model and excluded "
                    "from combined totals — DO NOT invent a single-entity net benefit "
                    "figure for these."
                ),
            },
        },
        "required": [
            "scenario_title",
            "description",
            "modified_income",
            "modified_expenses",
            "assumptions",
            "risk_rating",
            "compliance_notes",
            "strategy_category",
        ],
    },
}


SUBMIT_MODIFICATIONS_TOOL = {
    "name": "submit_modifications",
    "description": (
        "Return the FULL list of strategy modifications for the accountant in a single tool call. "
        "For every strategy provided in the user prompt that is worth modelling, include exactly one "
        "entry in the `modifications` array. Use the strategy_id EXACTLY as given in the input — do not "
        "invent new strategy_ids or paraphrase them. Do NOT include any combined/package/integrated/"
        "optimal-strategy entry: the system combines the individual strategies in code. If a strategy "
        "is not worth modelling (e.g. inapplicable, zero benefit), omit it."
    ),
    "input_schema": {
        "type": "object",
        "required": ["modifications"],
        "additionalProperties": False,
        "properties": {
            "modifications": {
                "type": "array",
                "description": (
                    "One entry per input strategy worth modelling. Order does not matter. "
                    "Maximum one entry per strategy_id."
                ),
                "items": {
                    "type": "object",
                    "required": [
                        "strategy_id",
                        "scenario_title",
                        "description",
                        "modified_income",
                        "modified_expenses",
                    ],
                    "additionalProperties": False,
                    "properties": {
                        "strategy_id": {
                            "type": "string",
                            "description": (
                                "Verbatim copy of the `id` field of one of the input strategies. "
                                "MUST match exactly — no paraphrasing, no slugification, no meta/"
                                "combined IDs."
                            ),
                        },
                        "scenario_title": {
                            "type": "string",
                            "description": "Human-readable display title for the scenario (e.g. 'Prepay deductible expenses').",
                        },
                        "description": {
                            "type": "string",
                            "description": "One-paragraph plain-English explanation of the modification, written for the accountant's client-facing brief.",
                        },
                        "assumptions": {
                            "type": "array",
                            "description": "Short bullet items listing the assumptions underlying the modification (e.g. amounts, timing, eligibility).",
                            "items": {"type": "string"},
                        },
                        "modified_income": {
                            "type": "object",
                            "description": "Overrides to the client's base income. Any key omitted uses the base figure unchanged.",
                            "additionalProperties": False,
                            "properties": {
                                "revenue": {
                                    "type": "number",
                                    "minimum": 0,
                                    "description": "Revised projected revenue for the full financial year.",
                                },
                                "other_income": {
                                    "type": "number",
                                    "minimum": 0,
                                    "description": "Revised projected other income for the full financial year.",
                                },
                            },
                        },
                        "modified_expenses": {
                            "type": "object",
                            "description": "Overrides to the client's base expenses. Any key omitted uses the base figure unchanged.",
                            "additionalProperties": False,
                            "properties": {
                                "cost_of_sales": {
                                    "type": "number",
                                    "minimum": 0,
                                    "description": "Revised projected cost of sales for the full financial year.",
                                },
                                "operating_expenses": {
                                    "type": "number",
                                    "minimum": 0,
                                    "description": "Revised projected operating expenses for the full financial year.",
                                },
                            },
                        },
                        "modified_turnover": {
                            "type": "number",
                            "minimum": 0,
                            "description": "Revised projected annual turnover. Optional — defaults to base turnover.",
                        },
                        "strategy_category": {
                            "type": "string",
                            "enum": [
                                "prepayment",
                                "capex_deduction",
                                "super_contribution",
                                "director_salary",
                                "trust_distribution",
                                "dividend_timing",
                                "spouse_contribution",
                                "multi_entity_restructure",
                                "other",
                            ],
                            "description": "StrategyCategory enum value. Multi-entity categories are flagged requires_group_model=True in code and excluded from combined totals.",
                        },
                        "risk_rating": {
                            "type": "string",
                            "enum": ["conservative", "moderate", "aggressive"],
                            "description": "Risk rating for the strategy. Defaults to 'moderate' in code if invalid.",
                        },
                        "compliance_notes": {
                            "type": "string",
                            "description": "Short compliance notes referencing ATO rulings, eligibility conditions, or caveats. Rendered in the scenario card.",
                        },
                    },
                },
            }
        },
    },
}


def format_reference_material(chunks: list[dict]) -> str:
    """Format retrieved knowledge base chunks as numbered references for the system prompt.

    Args:
        chunks: List of retrieved chunks, each with keys:
            title, source_type, ruling_number, section_ref, text, relevance_score

    Returns:
        Formatted reference material block, or empty placeholder if no chunks.
    """
    if not chunks:
        return "## Reference Material\nNo reference material available for this query."

    max_chunks = 5
    max_text_chars = 2000  # ~500 tokens

    lines = ["## Reference Material"]
    for i, chunk in enumerate(chunks[:max_chunks], 1):
        identifier = (
            chunk.get("ruling_number")
            or chunk.get("section_ref")
            or chunk.get("title", "Unknown source")
        )
        title = chunk.get("title", "")
        text = chunk.get("text", "")
        if len(text) > max_text_chars:
            text = text[:max_text_chars] + "..."

        source_type = chunk.get("source_type", "")
        superseded = chunk.get("is_superseded", False)
        superseded_note = (
            " (Note: this ruling has been superseded — check for current version)"
            if superseded
            else ""
        )

        lines.append(f"\n[{i}] {title} ({identifier}){superseded_note}")
        lines.append(f"Source type: {source_type}")
        lines.append(text)

    return "\n".join(lines)


def format_financial_context(
    financials_data: dict,
    tax_position: dict | None,
    entity_type: str,
) -> str:
    """Format financial data for the system prompt."""
    if not financials_data:
        return "No financial data loaded yet."

    income = financials_data.get("income", {})
    expenses = financials_data.get("expenses", {})
    credits = financials_data.get("credits", {})

    lines = [
        f"Entity Type: {entity_type}",
        f"Revenue: ${income.get('revenue', 0):,.2f}",
        f"Other Income: ${income.get('other_income', 0):,.2f}",
        f"Total Income: ${income.get('total_income', 0):,.2f}",
        f"Cost of Sales: ${expenses.get('cost_of_sales', 0):,.2f}",
        f"Operating Expenses: ${expenses.get('operating_expenses', 0):,.2f}",
        f"Total Expenses: ${expenses.get('total_expenses', 0):,.2f}",
        f"Net Profit: ${income.get('total_income', 0) - expenses.get('total_expenses', 0):,.2f}",
        f"Turnover: ${financials_data.get('turnover', 0):,.2f}",
    ]

    if credits.get("payg_instalments", 0) > 0:
        lines.append(f"PAYG Instalments Paid: ${credits['payg_instalments']:,.2f}")
    if credits.get("payg_withholding", 0) > 0:
        lines.append(f"PAYG Withholding: ${credits['payg_withholding']:,.2f}")

    if tax_position:
        lines.extend(
            [
                "",
                "--- Current Tax Position ---",
                f"Taxable Income: ${tax_position.get('taxable_income', 0):,.2f}",
                f"Total Tax Payable: ${tax_position.get('total_tax_payable', 0):,.2f}",
                f"Credits Applied: ${tax_position.get('credits_applied', {}).get('total', 0):,.2f}",
                f"Net Position: ${tax_position.get('net_position', 0):,.2f}",
                f"Effective Rate: {tax_position.get('effective_rate_pct', 0):.1f}%",
            ]
        )

    # Bank context (FR-015, FR-016, FR-017, FR-018)
    period_coverage = financials_data.get("period_coverage")
    if period_coverage:
        lines.extend(["", "--- Data Currency ---", f"Period: {period_coverage}"])

    recon_date = financials_data.get("last_reconciliation_date")
    if recon_date:
        lines.append(f"Last Bank Reconciliation: {recon_date}")

    total_bank = financials_data.get("total_bank_balance")
    if total_bank is not None:
        lines.extend(["", "--- Bank Position ---", f"Total Bank Balance: ${total_bank:,.2f}"])
        for acct in financials_data.get("bank_balances", []):
            lines.append(f"  {acct['account_name']}: ${acct['closing_balance']:,.2f}")

    unrecon = financials_data.get("unreconciled_summary")
    if unrecon and unrecon.get("transaction_count", 0) > 0:
        lines.extend(
            [
                "",
                f"--- Unreconciled Transactions ({unrecon.get('quarter', 'current quarter')}) [PROVISIONAL] ---",
                f"Count: {unrecon['transaction_count']}",
                f"Unreconciled Income: ${unrecon.get('unreconciled_income', 0):,.2f}",
                f"Unreconciled Expenses: ${unrecon.get('unreconciled_expenses', 0):,.2f}",
                f"Estimated GST Collected: ${unrecon.get('gst_collected_estimate', 0):,.2f}",
                f"Estimated GST Paid: ${unrecon.get('gst_paid_estimate', 0):,.2f}",
                "Note: These are provisional estimates from unreconciled transactions.",
            ]
        )

    # Spec 059 FR-003 — a single set of numbers flows to the LLM.
    # Income and expenses above are ALREADY projected to full FY when
    # projection_metadata.applied is true; this block only notes the
    # projection origin, it does NOT re-show the numbers side-by-side.
    projection_metadata = financials_data.get("projection_metadata")
    if projection_metadata and projection_metadata.get("applied"):
        months = projection_metadata.get("months_elapsed", 0)
        lines.extend(
            [
                "",
                "--- Data Basis ---",
                f"Figures above are projected to full financial year from {months} months of YTD data using linear monthly averaging.",
                "YTD actuals are available on request; do not re-project these totals in your reasoning.",
            ]
        )

    # Prior year same-period comparison (Spec 056 - US3)
    prior_ytd = financials_data.get("prior_year_ytd")
    if prior_ytd:
        changes = prior_ytd.get("changes", {})
        lines.extend(
            [
                "",
                f"--- Same Period Last Year ({prior_ytd.get('period_coverage', 'prior year')}) ---",
                f"Prior Year Revenue: ${prior_ytd.get('revenue', 0):,.2f} (change: {changes.get('revenue_pct', 0):+.1f}%)",
                f"Prior Year Expenses: ${prior_ytd.get('total_expenses', 0):,.2f} (change: {changes.get('expenses_pct', 0):+.1f}%)",
                f"Prior Year Net Profit: ${prior_ytd.get('net_profit', 0):,.2f} (change: {changes.get('profit_pct', 0):+.1f}%)",
            ]
        )

    # Multi-year trends (Spec 056 - US4)
    prior_years = financials_data.get("prior_years")
    if prior_years:
        lines.extend(["", "--- Multi-Year Trends ---"])
        for py in prior_years:
            lines.append(
                f"  {py['financial_year']}: Revenue ${py['revenue']:,.2f} | Expenses ${py['expenses']:,.2f} | Net Profit ${py['net_profit']:,.2f}"
            )

    # Strategy constraints (Spec 056 - US5)
    strategy_ctx = financials_data.get("strategy_context")
    if strategy_ctx:
        lines.extend(
            [
                "",
                "--- Strategy Constraints ---",
                f"Available Cash: ${strategy_ctx['available_cash']:,.2f}"
                if strategy_ctx.get("available_cash") is not None
                else "Available Cash: Not available",
                f"Monthly Operating Expenses: ${strategy_ctx['monthly_operating_expenses']:,.2f}",
                f"3-Month Cash Buffer: ${strategy_ctx['cash_buffer_3mo']:,.2f}",
            ]
        )
        if strategy_ctx.get("max_strategy_budget") is not None:
            lines.append(
                f"Maximum Available for Strategies: ${strategy_ctx['max_strategy_budget']:,.2f}"
            )
        else:
            lines.append(
                "Maximum Available for Strategies: Limited — cash reserves below 3-month buffer"
            )
        if strategy_ctx.get("existing_asset_spend", 0) > 0:
            lines.append(
                f"Existing Asset/Equipment Spend YTD: ${strategy_ctx['existing_asset_spend']:,.2f}"
            )
        lines.append(
            "IMPORTANT: Do not recommend strategies exceeding available cash without explicit justification."
        )

    # Payroll data (Spec 056 - US6)
    payroll = financials_data.get("payroll_summary")
    if payroll:
        lines.extend(
            [
                "",
                "--- Payroll Data ---",
                f"Employees: {payroll['employee_count']}",
                f"Total Wages YTD: ${payroll['total_wages_ytd']:,.2f}",
                f"Total Superannuation YTD: ${payroll['total_super_ytd']:,.2f}",
                f"Total PAYG Withheld YTD: ${payroll['total_tax_withheld_ytd']:,.2f}",
            ]
        )
        if payroll.get("has_owners"):
            lines.append(
                "Note: Business has owner/director employees — consider salary vs dividend optimisation and super contribution strategies."
            )
        lines.append(
            "Consider: maximising concessional super contributions ($30,000 cap), catch-up contributions (if eligible), salary packaging options."
        )

    return "\n".join(lines)


def format_scenario_history(scenarios: list[TaxScenario]) -> str:
    """Format existing scenarios for context injection."""
    if not scenarios:
        return "No scenarios modelled yet."

    lines = []
    for i, s in enumerate(scenarios, 1):
        change = s.impact_data.get("change", {})
        lines.append(
            f"{i}. {s.title} — Tax saving: ${change.get('tax_saving', 0):,.2f}, "
            f"Risk: {s.risk_rating.value if hasattr(s.risk_rating, 'value') else s.risk_rating}"
        )

    return "\n".join(lines)
