"""Pure-function Australian tax calculation engine.

All functions are deterministic and side-effect-free. Tax rates are passed as
parameters (loaded from the tax_rate_configs table by the caller).

Supports: Company, Individual (marginal rates + Medicare + LITO + HELP),
Trust (flat rate on undistributed income), Partnership (single-partner view).
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")


@dataclass
class TaxCalculationResult:
    """Result of a tax calculation for a single entity."""

    taxable_income: Decimal
    gross_tax: Decimal
    offsets: dict[str, Decimal] = field(default_factory=dict)
    medicare_levy: Decimal = ZERO
    help_repayment: Decimal = ZERO
    total_tax_payable: Decimal = ZERO
    effective_rate_pct: Decimal = ZERO
    calculation_method: str = ""

    def to_dict(self) -> dict:
        return {
            "taxable_income": float(self.taxable_income),
            "gross_tax": float(self.gross_tax),
            "offsets": {k: float(v) for k, v in self.offsets.items()},
            "medicare_levy": float(self.medicare_levy),
            "help_repayment": float(self.help_repayment),
            "total_tax_payable": float(self.total_tax_payable),
            "effective_rate_pct": float(self.effective_rate_pct),
            "calculation_method": self.calculation_method,
        }


def _d(value: float | int | str | Decimal) -> Decimal:
    """Convert to Decimal, quantized to 2 decimal places."""
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Company tax
# ---------------------------------------------------------------------------


def calculate_company_tax(
    taxable_income: Decimal,
    turnover: Decimal,
    rates: dict,
) -> TaxCalculationResult:
    """Calculate Australian company tax.

    Args:
        taxable_income: Company taxable income.
        turnover: Aggregated turnover for small business entity test.
        rates: Company rate config with keys:
            small_business_rate, standard_rate, small_business_turnover_threshold.
    """
    if taxable_income <= ZERO:
        return TaxCalculationResult(
            taxable_income=_d(taxable_income),
            gross_tax=ZERO,
            total_tax_payable=ZERO,
            effective_rate_pct=ZERO,
            calculation_method="company_no_income",
        )

    threshold = Decimal(str(rates["small_business_turnover_threshold"]))
    if turnover < threshold:
        rate = Decimal(str(rates["small_business_rate"]))
        method = "company_small_business"
    else:
        rate = Decimal(str(rates["standard_rate"]))
        method = "company_standard"

    gross_tax = _d(taxable_income * rate)
    effective = _d((gross_tax / taxable_income) * 100) if taxable_income > ZERO else ZERO

    return TaxCalculationResult(
        taxable_income=_d(taxable_income),
        gross_tax=gross_tax,
        total_tax_payable=gross_tax,
        effective_rate_pct=effective,
        calculation_method=method,
    )


# ---------------------------------------------------------------------------
# Individual tax (marginal rates)
# ---------------------------------------------------------------------------


def _calculate_marginal_tax(taxable_income: Decimal, brackets: list[dict]) -> Decimal:
    """Apply marginal tax brackets to taxable income."""
    tax = ZERO
    for bracket in brackets:
        lower = Decimal(str(bracket["min"]))
        upper = Decimal(str(bracket["max"])) if bracket["max"] is not None else None
        rate = Decimal(str(bracket["rate"]))

        if taxable_income <= lower:
            break

        if upper is None:
            taxable_in_bracket = taxable_income - lower
        else:
            taxable_in_bracket = min(taxable_income, upper) - lower

        if taxable_in_bracket > ZERO:
            tax += _d(taxable_in_bracket * rate)

    return tax


def _calculate_medicare_levy(taxable_income: Decimal, medicare_rates: dict) -> Decimal:
    """Calculate Medicare Levy with low-income phase-in."""
    rate = Decimal(str(medicare_rates["rate"]))
    low_threshold = Decimal(str(medicare_rates["low_income_threshold_single"]))
    phase_in_threshold = Decimal(str(medicare_rates["phase_in_threshold_single"]))
    shade_in_rate = Decimal(str(medicare_rates["shade_in_rate"]))

    if taxable_income <= low_threshold:
        return ZERO
    elif taxable_income <= phase_in_threshold:
        # Phase-in: shade-in rate on amount over low threshold
        return _d((taxable_income - low_threshold) * shade_in_rate)
    else:
        return _d(taxable_income * rate)


def _calculate_lito(taxable_income: Decimal, lito_rates: dict) -> Decimal:
    """Calculate Low Income Tax Offset (LITO)."""
    max_offset = Decimal(str(lito_rates["max_offset"]))
    full_threshold = Decimal(str(lito_rates["full_offset_threshold"]))
    first_reduction_rate = Decimal(str(lito_rates["first_reduction_rate"]))
    first_reduction_threshold = Decimal(str(lito_rates["first_reduction_threshold"]))
    second_reduction_rate = Decimal(str(lito_rates["second_reduction_rate"]))
    second_reduction_threshold = Decimal(str(lito_rates["second_reduction_threshold"]))

    if taxable_income <= full_threshold:
        return max_offset

    if taxable_income <= first_reduction_threshold:
        reduction = _d((taxable_income - full_threshold) * first_reduction_rate)
        return max(ZERO, _d(max_offset - reduction))

    if taxable_income <= second_reduction_threshold:
        # First stage reduction is fully applied
        first_reduction = _d((first_reduction_threshold - full_threshold) * first_reduction_rate)
        remaining = _d(max_offset - first_reduction)
        second_reduction = _d((taxable_income - first_reduction_threshold) * second_reduction_rate)
        return max(ZERO, _d(remaining - second_reduction))

    return ZERO


def _calculate_help_repayment(repayment_income: Decimal, help_rates: dict) -> Decimal:
    """Calculate HELP/HECS repayment amount."""
    thresholds = help_rates.get("thresholds", [])
    if not thresholds:
        return ZERO

    for threshold in thresholds:
        lower = Decimal(str(threshold["min"]))
        upper = Decimal(str(threshold["max"])) if threshold["max"] is not None else None
        rate = Decimal(str(threshold["rate"]))

        if upper is None:
            if repayment_income >= lower:
                return _d(repayment_income * rate)
        elif lower <= repayment_income <= upper:
            return _d(repayment_income * rate)

    return ZERO


def calculate_individual_tax(
    taxable_income: Decimal,
    rates: dict,
    medicare_rates: dict,
    lito_rates: dict,
    help_rates: dict | None = None,
) -> TaxCalculationResult:
    """Calculate Australian individual income tax.

    Includes marginal rates, Medicare Levy, LITO, and optional HELP repayment.

    Args:
        taxable_income: Individual taxable income.
        rates: Individual rate config with 'brackets' key.
        medicare_rates: Medicare Levy config.
        lito_rates: Low Income Tax Offset config.
        help_rates: HELP/HECS repayment config (None if no HELP debt).
    """
    if taxable_income <= ZERO:
        return TaxCalculationResult(
            taxable_income=_d(taxable_income),
            gross_tax=ZERO,
            total_tax_payable=ZERO,
            effective_rate_pct=ZERO,
            calculation_method="individual_no_income",
        )

    brackets = rates["brackets"]
    gross_tax = _calculate_marginal_tax(taxable_income, brackets)

    # LITO offset
    lito = _calculate_lito(taxable_income, lito_rates)
    tax_after_offsets = max(ZERO, _d(gross_tax - lito))

    # Medicare Levy
    medicare = _calculate_medicare_levy(taxable_income, medicare_rates)

    # HELP repayment
    help_amount = ZERO
    if help_rates:
        help_amount = _calculate_help_repayment(taxable_income, help_rates)

    total = _d(tax_after_offsets + medicare + help_amount)
    effective = _d((total / taxable_income) * 100) if taxable_income > ZERO else ZERO

    offsets: dict[str, Decimal] = {}
    if lito > ZERO:
        offsets["lito"] = lito

    return TaxCalculationResult(
        taxable_income=_d(taxable_income),
        gross_tax=gross_tax,
        offsets=offsets,
        medicare_levy=medicare,
        help_repayment=help_amount,
        total_tax_payable=total,
        effective_rate_pct=effective,
        calculation_method="individual_marginal",
    )


# ---------------------------------------------------------------------------
# Trust tax
# ---------------------------------------------------------------------------


def calculate_trust_tax(
    taxable_income: Decimal,
    rates: dict,
) -> TaxCalculationResult:
    """Calculate trust tax on undistributed income (flat rate).

    Phase 1: No distribution modelling — all income treated as undistributed.
    """
    if taxable_income <= ZERO:
        return TaxCalculationResult(
            taxable_income=_d(taxable_income),
            gross_tax=ZERO,
            total_tax_payable=ZERO,
            effective_rate_pct=ZERO,
            calculation_method="trust_no_income",
        )

    rate = Decimal(str(rates["undistributed_rate"]))
    gross_tax = _d(taxable_income * rate)

    return TaxCalculationResult(
        taxable_income=_d(taxable_income),
        gross_tax=gross_tax,
        total_tax_payable=gross_tax,
        effective_rate_pct=_d(rate * 100),
        calculation_method="trust_undistributed",
    )


# ---------------------------------------------------------------------------
# Partnership tax (simplified single-partner)
# ---------------------------------------------------------------------------


def calculate_partnership_tax(
    net_income: Decimal,
    individual_rates: dict,
    medicare_rates: dict,
    lito_rates: dict,
) -> TaxCalculationResult:
    """Calculate partnership tax — simplified single-partner view.

    Partnership net income is taxed in the partner's hands at individual rates.
    Phase 1: Single partner receives 100% of net income.
    """
    result = calculate_individual_tax(
        taxable_income=net_income,
        rates=individual_rates,
        medicare_rates=medicare_rates,
        lito_rates=lito_rates,
        help_rates=None,
    )
    result.calculation_method = "partnership_single_partner"
    return result


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def derive_taxable_income(financials_data: dict) -> Decimal:
    """Derive taxable income from financials data.

    taxable_income = total_income - total_expenses + add_backs - deductions
    """
    income = financials_data.get("income", {})
    expenses = financials_data.get("expenses", {})
    adjustments = financials_data.get("adjustments", [])

    total_income = Decimal(str(income.get("total_income", 0)))
    total_expenses = Decimal(str(expenses.get("total_expenses", 0)))

    adjustment_total = ZERO
    for adj in adjustments:
        amount = Decimal(str(adj.get("amount", 0)))
        adj_type = adj.get("type", "add_back")
        if adj_type == "add_back":
            adjustment_total += amount
        elif adj_type == "deduction":
            adjustment_total -= amount

    return _d(total_income - total_expenses + adjustment_total)


def calculate_tax_position(
    entity_type: str,
    financials_data: dict,
    rate_configs: dict[str, dict],
    has_help_debt: bool = False,
) -> dict:
    """Main entry point: calculate complete tax position.

    Args:
        entity_type: One of company, individual, trust, partnership.
        financials_data: Financials JSONB data from the tax plan.
        rate_configs: Dict keyed by rate_type (individual, company, trust,
            medicare, lito, help) with rates_data values.
        has_help_debt: Whether individual has HELP/HECS debt.

    Returns:
        Complete tax_position dict matching the JSONB schema.
    """
    taxable_income = derive_taxable_income(financials_data)
    turnover = Decimal(str(financials_data.get("turnover", 0)))

    credits_data = financials_data.get("credits", {})
    payg_instalments = Decimal(str(credits_data.get("payg_instalments", 0)))
    payg_withholding = Decimal(str(credits_data.get("payg_withholding", 0)))
    franking_credits = Decimal(str(credits_data.get("franking_credits", 0)))
    credits_total = _d(payg_instalments + payg_withholding + franking_credits)

    # Dispatch to entity-specific calculator
    if entity_type == "company":
        result = calculate_company_tax(
            taxable_income=taxable_income,
            turnover=turnover,
            rates=rate_configs["company"],
        )
    elif entity_type == "individual":
        help_rates = rate_configs.get("help") if has_help_debt else None
        result = calculate_individual_tax(
            taxable_income=taxable_income,
            rates=rate_configs["individual"],
            medicare_rates=rate_configs["medicare"],
            lito_rates=rate_configs["lito"],
            help_rates=help_rates,
        )
    elif entity_type == "trust":
        result = calculate_trust_tax(
            taxable_income=taxable_income,
            rates=rate_configs["trust"],
        )
    elif entity_type == "partnership":
        result = calculate_partnership_tax(
            net_income=taxable_income,
            individual_rates=rate_configs["individual"],
            medicare_rates=rate_configs["medicare"],
            lito_rates=rate_configs["lito"],
        )
    else:
        raise ValueError(f"Unsupported entity type: {entity_type}")

    net_position = _d(result.total_tax_payable - credits_total)

    return {
        "taxable_income": float(result.taxable_income),
        "gross_tax": float(result.gross_tax),
        "offsets": {k: float(v) for k, v in result.offsets.items()},
        "medicare_levy": float(result.medicare_levy),
        "help_repayment": float(result.help_repayment),
        "total_tax_payable": float(result.total_tax_payable),
        "credits_applied": {
            "payg_instalments": float(payg_instalments),
            "payg_withholding": float(payg_withholding),
            "franking_credits": float(franking_credits),
            "total": float(credits_total),
        },
        "net_position": float(net_position),
        "effective_rate_pct": float(result.effective_rate_pct),
        "calculation_method": result.calculation_method,
        "rate_config_year": rate_configs.get("_financial_year", "2025-26"),
    }
