"""Unit tests for the Australian tax calculation engine.

Accuracy requirement: all results must be within $1 of manual calculation (SC-003).
"""

from decimal import Decimal

import pytest

from app.modules.tax_planning.tax_calculator import (
    calculate_company_tax,
    calculate_individual_tax,
    calculate_partnership_tax,
    calculate_tax_position,
    calculate_trust_tax,
    derive_taxable_income,
)

# ---------------------------------------------------------------------------
# 2025-26 rate configs (matching seed data)
# ---------------------------------------------------------------------------

INDIVIDUAL_RATES = {
    "brackets": [
        {"min": 0, "max": 18200, "rate": 0.00},
        {"min": 18201, "max": 45000, "rate": 0.16},
        {"min": 45001, "max": 135000, "rate": 0.30},
        {"min": 135001, "max": 190000, "rate": 0.37},
        {"min": 190001, "max": None, "rate": 0.45},
    ]
}

COMPANY_RATES = {
    "small_business_rate": 0.25,
    "standard_rate": 0.30,
    "small_business_turnover_threshold": 50_000_000,
}

TRUST_RATES = {"undistributed_rate": 0.47}

MEDICARE_RATES = {
    "rate": 0.02,
    "low_income_threshold_single": 26000,
    "phase_in_threshold_single": 32500,
    "low_income_threshold_family": 43846,
    "shade_in_rate": 0.10,
}

LITO_RATES = {
    "max_offset": 700,
    "full_offset_threshold": 37500,
    "first_reduction_rate": 0.05,
    "first_reduction_threshold": 45000,
    "second_reduction_rate": 0.015,
    "second_reduction_threshold": 66667,
}

HELP_RATES = {
    "thresholds": [
        {"min": 54435, "max": 62850, "rate": 0.01},
        {"min": 62851, "max": 66620, "rate": 0.02},
        {"min": 66621, "max": 70618, "rate": 0.025},
        {"min": 70619, "max": 74855, "rate": 0.03},
        {"min": 74856, "max": 79346, "rate": 0.035},
        {"min": 79347, "max": 84107, "rate": 0.04},
        {"min": 84108, "max": 89154, "rate": 0.045},
        {"min": 89155, "max": 94503, "rate": 0.05},
        {"min": 94504, "max": 100174, "rate": 0.055},
        {"min": 100175, "max": 106185, "rate": 0.06},
        {"min": 106186, "max": 112556, "rate": 0.065},
        {"min": 112557, "max": 119310, "rate": 0.07},
        {"min": 119311, "max": 126467, "rate": 0.075},
        {"min": 126468, "max": 134056, "rate": 0.08},
        {"min": 134057, "max": 142100, "rate": 0.085},
        {"min": 142101, "max": 150626, "rate": 0.09},
        {"min": 150627, "max": 159663, "rate": 0.095},
        {"min": 159664, "max": None, "rate": 0.10},
    ]
}

ALL_RATE_CONFIGS = {
    "individual": INDIVIDUAL_RATES,
    "company": COMPANY_RATES,
    "trust": TRUST_RATES,
    "medicare": MEDICARE_RATES,
    "lito": LITO_RATES,
    "help": HELP_RATES,
    "_financial_year": "2025-26",
}


def _within_one(actual: float, expected: float) -> None:
    """Assert actual value is within $1 of expected."""
    assert abs(actual - expected) <= 1.0, (
        f"Expected ~${expected:,.2f}, got ${actual:,.2f} "
        f"(difference: ${abs(actual - expected):,.2f})"
    )


# ===========================================================================
# Company tax tests
# ===========================================================================


class TestCompanyTax:
    def test_small_business_rate(self):
        """$500K revenue, $350K expenses → $150K taxable → 25% = $37,500."""
        result = calculate_company_tax(
            taxable_income=Decimal("150000"),
            turnover=Decimal("500000"),
            rates=COMPANY_RATES,
        )
        _within_one(float(result.gross_tax), 37500.0)
        assert result.calculation_method == "company_small_business"

    def test_standard_rate(self):
        """Turnover > $50M → 30% rate."""
        result = calculate_company_tax(
            taxable_income=Decimal("1000000"),
            turnover=Decimal("60000000"),
            rates=COMPANY_RATES,
        )
        _within_one(float(result.gross_tax), 300000.0)
        assert result.calculation_method == "company_standard"

    def test_zero_income(self):
        result = calculate_company_tax(
            taxable_income=Decimal("0"),
            turnover=Decimal("0"),
            rates=COMPANY_RATES,
        )
        assert float(result.gross_tax) == 0.0

    def test_negative_income(self):
        """Loss → no tax payable."""
        result = calculate_company_tax(
            taxable_income=Decimal("-50000"),
            turnover=Decimal("100000"),
            rates=COMPANY_RATES,
        )
        assert float(result.total_tax_payable) == 0.0

    def test_boundary_turnover(self):
        """Turnover exactly at threshold uses standard rate."""
        result = calculate_company_tax(
            taxable_income=Decimal("100000"),
            turnover=Decimal("50000000"),
            rates=COMPANY_RATES,
        )
        # At threshold → NOT small business (must be strictly less than)
        assert result.calculation_method == "company_standard"
        _within_one(float(result.gross_tax), 30000.0)


# ===========================================================================
# Individual tax tests
# ===========================================================================


class TestIndividualTax:
    def test_below_tax_free_threshold(self):
        """$18,200 → $0 tax."""
        result = calculate_individual_tax(
            taxable_income=Decimal("18200"),
            rates=INDIVIDUAL_RATES,
            medicare_rates=MEDICARE_RATES,
            lito_rates=LITO_RATES,
        )
        # Gross tax is 0, Medicare is 0 (below low threshold), LITO is $700
        assert float(result.gross_tax) == 0.0

    def test_45000_taxable(self):
        """$45,000 → 0% on $18,200 + 16% on $26,800 = $4,288."""
        result = calculate_individual_tax(
            taxable_income=Decimal("45000"),
            rates=INDIVIDUAL_RATES,
            medicare_rates=MEDICARE_RATES,
            lito_rates=LITO_RATES,
        )
        expected_gross = (45000 - 18200) * 0.16  # = 4,288
        _within_one(float(result.gross_tax), expected_gross)

    def test_90000_taxable(self):
        """$90,000 → three brackets applied correctly."""
        result = calculate_individual_tax(
            taxable_income=Decimal("90000"),
            rates=INDIVIDUAL_RATES,
            medicare_rates=MEDICARE_RATES,
            lito_rates=LITO_RATES,
        )
        # 0% on $18,200 = $0
        # 16% on $18,201-$45,000 = $4,288
        # 30% on $45,001-$90,000 = $13,500
        expected_gross = 4288 + 13500  # = $17,788
        _within_one(float(result.gross_tax), expected_gross)

    def test_200000_taxable(self):
        """$200,000 → all 5 brackets."""
        result = calculate_individual_tax(
            taxable_income=Decimal("200000"),
            rates=INDIVIDUAL_RATES,
            medicare_rates=MEDICARE_RATES,
            lito_rates=LITO_RATES,
        )
        # 0% on $0-$18,200 = $0
        # 16% on $18,201-$45,000 ($26,799) = $4,287.84
        # 30% on $45,001-$135,000 ($89,999) = $26,999.70
        # 37% on $135,001-$190,000 ($54,999) = $20,349.63
        # 45% on $190,001-$200,000 ($9,999) = $4,499.55
        # Total ≈ $56,136.72
        expected_gross = 56136.72
        _within_one(float(result.gross_tax), expected_gross)

    def test_zero_income(self):
        result = calculate_individual_tax(
            taxable_income=Decimal("0"),
            rates=INDIVIDUAL_RATES,
            medicare_rates=MEDICARE_RATES,
            lito_rates=LITO_RATES,
        )
        assert float(result.total_tax_payable) == 0.0

    def test_negative_income(self):
        result = calculate_individual_tax(
            taxable_income=Decimal("-10000"),
            rates=INDIVIDUAL_RATES,
            medicare_rates=MEDICARE_RATES,
            lito_rates=LITO_RATES,
        )
        assert float(result.total_tax_payable) == 0.0


# ===========================================================================
# LITO tests
# ===========================================================================


class TestLITO:
    def test_full_offset(self):
        """$37,500 income → full $700 LITO."""
        result = calculate_individual_tax(
            taxable_income=Decimal("37500"),
            rates=INDIVIDUAL_RATES,
            medicare_rates=MEDICARE_RATES,
            lito_rates=LITO_RATES,
        )
        assert result.offsets.get("lito", Decimal("0")) == Decimal("700.00")

    def test_reduced_offset_first_stage(self):
        """$40,000 → $700 - ($40,000 - $37,500) * 0.05 = $700 - $125 = $575."""
        result = calculate_individual_tax(
            taxable_income=Decimal("40000"),
            rates=INDIVIDUAL_RATES,
            medicare_rates=MEDICARE_RATES,
            lito_rates=LITO_RATES,
        )
        expected_lito = 700 - (40000 - 37500) * 0.05  # = 575
        _within_one(float(result.offsets.get("lito", Decimal("0"))), expected_lito)

    def test_reduced_offset_second_stage(self):
        """$50,000 → first reduction fully applied, then second stage."""
        result = calculate_individual_tax(
            taxable_income=Decimal("50000"),
            rates=INDIVIDUAL_RATES,
            medicare_rates=MEDICARE_RATES,
            lito_rates=LITO_RATES,
        )
        # First: $700 - ($45,000 - $37,500) * 0.05 = $700 - $375 = $325
        # Second: $325 - ($50,000 - $45,000) * 0.015 = $325 - $75 = $250
        expected_lito = 250
        _within_one(float(result.offsets.get("lito", Decimal("0"))), expected_lito)

    def test_no_offset_high_income(self):
        """$70,000 → $0 LITO (above $66,667)."""
        result = calculate_individual_tax(
            taxable_income=Decimal("70000"),
            rates=INDIVIDUAL_RATES,
            medicare_rates=MEDICARE_RATES,
            lito_rates=LITO_RATES,
        )
        assert float(result.offsets.get("lito", Decimal("0"))) == 0.0


# ===========================================================================
# Medicare Levy tests
# ===========================================================================


class TestMedicareLevy:
    def test_standard_levy(self):
        """$50,000 → 2% = $1,000."""
        result = calculate_individual_tax(
            taxable_income=Decimal("50000"),
            rates=INDIVIDUAL_RATES,
            medicare_rates=MEDICARE_RATES,
            lito_rates=LITO_RATES,
        )
        _within_one(float(result.medicare_levy), 1000.0)

    def test_low_income_exempt(self):
        """$24,000 → $0 (below $26,000 threshold)."""
        result = calculate_individual_tax(
            taxable_income=Decimal("24000"),
            rates=INDIVIDUAL_RATES,
            medicare_rates=MEDICARE_RATES,
            lito_rates=LITO_RATES,
        )
        assert float(result.medicare_levy) == 0.0

    def test_phase_in(self):
        """$30,000 → phase-in: ($30,000 - $26,000) * 0.10 = $400."""
        result = calculate_individual_tax(
            taxable_income=Decimal("30000"),
            rates=INDIVIDUAL_RATES,
            medicare_rates=MEDICARE_RATES,
            lito_rates=LITO_RATES,
        )
        _within_one(float(result.medicare_levy), 400.0)

    def test_at_threshold(self):
        """$26,000 exactly → $0."""
        result = calculate_individual_tax(
            taxable_income=Decimal("26000"),
            rates=INDIVIDUAL_RATES,
            medicare_rates=MEDICARE_RATES,
            lito_rates=LITO_RATES,
        )
        assert float(result.medicare_levy) == 0.0


# ===========================================================================
# HELP repayment tests
# ===========================================================================


class TestHELPRepayment:
    def test_below_threshold(self):
        """$50,000 → $0 (below $54,435)."""
        result = calculate_individual_tax(
            taxable_income=Decimal("50000"),
            rates=INDIVIDUAL_RATES,
            medicare_rates=MEDICARE_RATES,
            lito_rates=LITO_RATES,
            help_rates=HELP_RATES,
        )
        assert float(result.help_repayment) == 0.0

    def test_first_threshold(self):
        """$60,000 → 1% = $600."""
        result = calculate_individual_tax(
            taxable_income=Decimal("60000"),
            rates=INDIVIDUAL_RATES,
            medicare_rates=MEDICARE_RATES,
            lito_rates=LITO_RATES,
            help_rates=HELP_RATES,
        )
        _within_one(float(result.help_repayment), 600.0)

    def test_no_help_debt(self):
        """No HELP rates → $0 repayment even with high income."""
        result = calculate_individual_tax(
            taxable_income=Decimal("100000"),
            rates=INDIVIDUAL_RATES,
            medicare_rates=MEDICARE_RATES,
            lito_rates=LITO_RATES,
            help_rates=None,
        )
        assert float(result.help_repayment) == 0.0


# ===========================================================================
# Trust tax tests
# ===========================================================================


class TestTrustTax:
    def test_undistributed_income(self):
        """$100,000 undistributed → 47% = $47,000."""
        result = calculate_trust_tax(
            taxable_income=Decimal("100000"),
            rates=TRUST_RATES,
        )
        _within_one(float(result.gross_tax), 47000.0)

    def test_zero_income(self):
        result = calculate_trust_tax(
            taxable_income=Decimal("0"),
            rates=TRUST_RATES,
        )
        assert float(result.total_tax_payable) == 0.0


# ===========================================================================
# Partnership tax tests
# ===========================================================================


class TestPartnershipTax:
    def test_single_partner_individual_rates(self):
        """Partnership $90K → taxed at individual marginal rates."""
        result = calculate_partnership_tax(
            net_income=Decimal("90000"),
            individual_rates=INDIVIDUAL_RATES,
            medicare_rates=MEDICARE_RATES,
            lito_rates=LITO_RATES,
        )
        assert result.calculation_method == "partnership_single_partner"
        # Should match individual calculation for same income
        individual_result = calculate_individual_tax(
            taxable_income=Decimal("90000"),
            rates=INDIVIDUAL_RATES,
            medicare_rates=MEDICARE_RATES,
            lito_rates=LITO_RATES,
        )
        assert float(result.total_tax_payable) == float(individual_result.total_tax_payable)


# ===========================================================================
# derive_taxable_income tests
# ===========================================================================


class TestDeriveTaxableIncome:
    def test_basic(self):
        financials = {
            "income": {"total_income": 500000},
            "expenses": {"total_expenses": 350000},
            "adjustments": [],
        }
        assert derive_taxable_income(financials) == Decimal("150000.00")

    def test_with_add_back(self):
        financials = {
            "income": {"total_income": 500000},
            "expenses": {"total_expenses": 350000},
            "adjustments": [
                {"amount": 5000, "type": "add_back"},
            ],
        }
        assert derive_taxable_income(financials) == Decimal("155000.00")

    def test_with_deduction(self):
        financials = {
            "income": {"total_income": 500000},
            "expenses": {"total_expenses": 350000},
            "adjustments": [
                {"amount": 10000, "type": "deduction"},
            ],
        }
        assert derive_taxable_income(financials) == Decimal("140000.00")


# ===========================================================================
# Integration: calculate_tax_position
# ===========================================================================


class TestCalculateTaxPosition:
    def test_company_full_position(self):
        """Spec acceptance: $500K revenue, $350K expenses → $150K → $37,500."""
        financials = {
            "income": {"total_income": 500000},
            "expenses": {"total_expenses": 350000},
            "credits": {
                "payg_instalments": 25000,
                "payg_withholding": 0,
                "franking_credits": 0,
            },
            "adjustments": [],
            "turnover": 500000,
        }
        result = calculate_tax_position(
            entity_type="company",
            financials_data=financials,
            rate_configs=ALL_RATE_CONFIGS,
        )
        _within_one(result["taxable_income"], 150000.0)
        _within_one(result["total_tax_payable"], 37500.0)
        _within_one(result["credits_applied"]["total"], 25000.0)
        _within_one(result["net_position"], 12500.0)  # 37500 - 25000

    def test_individual_with_credits(self):
        """Individual $90K taxable, $15K PAYG paid → net position."""
        financials = {
            "income": {"total_income": 120000},
            "expenses": {"total_expenses": 30000},
            "credits": {
                "payg_instalments": 15000,
                "payg_withholding": 0,
                "franking_credits": 0,
            },
            "adjustments": [],
            "turnover": 120000,
        }
        result = calculate_tax_position(
            entity_type="individual",
            financials_data=financials,
            rate_configs=ALL_RATE_CONFIGS,
        )
        _within_one(result["taxable_income"], 90000.0)
        assert result["credits_applied"]["payg_instalments"] == 15000.0
        # Net position = tax_payable - credits
        _within_one(result["net_position"], result["total_tax_payable"] - 15000.0)

    def test_unsupported_entity_type(self):
        with pytest.raises(ValueError, match="Unsupported entity type"):
            calculate_tax_position(
                entity_type="smsf",
                financials_data={"income": {"total_income": 0}, "expenses": {"total_expenses": 0}},
                rate_configs=ALL_RATE_CONFIGS,
            )
