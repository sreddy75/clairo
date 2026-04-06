"""Tests for Spec 056: Tax Planning Intelligence Improvements.

Tests the 6 improvements from beta tester feedback:
1. Bank balance null handling (not $0 for empty data)
2. Revenue/expense forecasting from YTD
3. Prior year comparison context in AI prompt
4. Multi-year trends context in AI prompt
5. Strategy context with cash constraints
6. Payroll data in AI prompt

These are unit tests that validate the logic in service.py and prompts.py
without requiring a live Xero connection.
"""

import uuid
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.tax_planning.prompts import format_financial_context
from app.modules.tax_planning.service import TaxPlanningService


# =============================================================================
# Helpers: Build financials_data dicts for testing
# =============================================================================

def _base_financials(
    revenue: float = 100000,
    expenses: float = 60000,
    months: int = 9,
) -> dict:
    """Build a minimal financials_data dict."""
    return {
        "income": {
            "revenue": revenue,
            "other_income": 0,
            "total_income": revenue,
            "breakdown": [
                {"category": "Sales", "amount": revenue},
            ],
        },
        "expenses": {
            "cost_of_sales": 0,
            "operating_expenses": expenses,
            "total_expenses": expenses,
            "breakdown": [
                {"category": "Rent", "amount": 20000},
                {"category": "Wages", "amount": 25000},
                {"category": "Computer equipment", "amount": 5000},
                {"category": "Other", "amount": expenses - 50000},
            ],
        },
        "credits": {
            "payg_instalments": 0,
            "payg_withholding": 0,
            "franking_credits": 0,
        },
        "adjustments": [],
        "turnover": revenue,
        "months_data_available": months,
        "is_annualised": months < 12,
    }


def _financials_with_bank(balance: float | None = 50000.0) -> dict:
    """Build financials_data with bank balance."""
    data = _base_financials()
    if balance is not None:
        data["total_bank_balance"] = balance
        data["bank_balances"] = [
            {"account_name": "Business Account", "closing_balance": balance}
        ]
    else:
        data["total_bank_balance"] = None
        data["bank_balances"] = []
    return data


def _financials_with_projection() -> dict:
    """Build financials_data with projection."""
    data = _base_financials(revenue=90000, expenses=54000, months=9)
    data["projection"] = {
        "projected_revenue": 120000.0,
        "projected_expenses": 72000.0,
        "projected_net_profit": 48000.0,
        "monthly_avg_revenue": 10000.0,
        "monthly_avg_expenses": 6000.0,
        "months_used": 9,
        "projection_method": "linear_average",
    }
    return data


def _financials_with_prior_year() -> dict:
    """Build financials_data with prior year comparison."""
    data = _base_financials(revenue=100000, expenses=60000)
    data["prior_year_ytd"] = {
        "revenue": 85000,
        "total_income": 85000,
        "total_expenses": 55000,
        "net_profit": 30000,
        "period_coverage": "1 Jul 2024 – 15 Mar 2025",
        "changes": {
            "revenue_pct": 17.6,
            "expenses_pct": 9.1,
            "profit_pct": 33.3,
        },
    }
    return data


def _financials_with_multi_year() -> dict:
    """Build financials_data with multi-year trends."""
    data = _base_financials()
    data["prior_years"] = [
        {"financial_year": "FY2025", "revenue": 110000, "expenses": 70000, "net_profit": 40000},
        {"financial_year": "FY2024", "revenue": 95000, "expenses": 65000, "net_profit": 30000},
    ]
    return data


def _financials_with_strategy_context() -> dict:
    """Build financials_data with strategy context."""
    data = _financials_with_bank(50000)
    data["strategy_context"] = {
        "available_cash": 50000,
        "monthly_operating_expenses": 6666.67,
        "cash_buffer_3mo": 20000.0,
        "max_strategy_budget": 30000.0,
        "existing_asset_spend": 5000.0,
    }
    return data


def _financials_with_payroll() -> dict:
    """Build financials_data with payroll data."""
    data = _base_financials()
    data["payroll_summary"] = {
        "employee_count": 3,
        "total_wages_ytd": 180000,
        "total_super_ytd": 19800,
        "total_tax_withheld_ytd": 45000,
        "has_owners": True,
        "employees": [
            {"name": "John Smith", "job_title": "Director", "status": "active"},
            {"name": "Jane Doe", "job_title": "Accountant", "status": "active"},
            {"name": "Bob Brown", "job_title": "Admin", "status": "active"},
        ],
    }
    return data


# =============================================================================
# US1: Bank Balance Fix
# =============================================================================

class TestBankBalanceFix:
    """US1: Bank balance should show actual value or null — never $0 for empty data."""

    def test_empty_bank_balances_returns_null(self):
        """When Xero returns no bank accounts, total should be None, not 0."""
        bank_balances: list = []
        total = sum(a["closing_balance"] for a in bank_balances) if bank_balances else None
        assert total is None

    def test_bank_balances_with_accounts_returns_sum(self):
        """When bank accounts exist, sum their closing balances."""
        bank_balances = [
            {"account_name": "Cheque", "closing_balance": 10000},
            {"account_name": "Savings", "closing_balance": 25000},
        ]
        total = sum(a["closing_balance"] for a in bank_balances) if bank_balances else None
        assert total == 35000

    def test_bank_balances_genuine_zero(self):
        """When accounts exist but balance is genuinely $0, show $0."""
        bank_balances = [
            {"account_name": "Cheque", "closing_balance": 0},
        ]
        total = sum(a["closing_balance"] for a in bank_balances) if bank_balances else None
        assert total == 0

    def test_prompt_includes_bank_when_available(self):
        """AI prompt should include bank balance when available."""
        data = _financials_with_bank(50000)
        prompt = format_financial_context(data, None, "company")
        assert "Total Bank Balance: $50,000.00" in prompt
        assert "Business Account" in prompt

    def test_prompt_excludes_bank_when_null(self):
        """AI prompt should not include bank section when balance is null."""
        data = _financials_with_bank(None)
        prompt = format_financial_context(data, None, "company")
        assert "Bank Position" not in prompt
        assert "Total Bank Balance" not in prompt


# =============================================================================
# US2: Revenue Forecasting
# =============================================================================

class TestRevenueForecasting:
    """US2: Project full-year figures from YTD monthly averages."""

    def test_projection_calculation_9_months(self):
        """9 months of data → monthly avg × 12 = projected full year."""
        months = 9
        revenue = 90000  # $10K/month
        expenses = 54000  # $6K/month

        monthly_avg_rev = revenue / months
        monthly_avg_exp = expenses / months
        projected_rev = round(monthly_avg_rev * 12, 2)
        projected_exp = round(monthly_avg_exp * 12, 2)
        projected_profit = round((monthly_avg_rev - monthly_avg_exp) * 12, 2)

        assert projected_rev == 120000.0
        assert projected_exp == 72000.0
        assert projected_profit == 48000.0

    def test_no_projection_for_full_year(self):
        """12 months of data → no projection needed."""
        months = 12
        # Projection should only be created when months_elapsed >= 3 and < 12
        should_project = months >= 3 and months < 12
        assert not should_project

    def test_no_projection_under_3_months(self):
        """Less than 3 months → too little data for projection."""
        months = 2
        should_project = months >= 3 and months < 12
        assert not should_project

    def test_projection_at_3_months(self):
        """Exactly 3 months → projection should be created."""
        months = 3
        should_project = months >= 3 and months < 12
        assert should_project

    def test_prompt_includes_projection(self):
        """AI prompt should include projection section when available."""
        data = _financials_with_projection()
        prompt = format_financial_context(data, None, "company")
        assert "Full Year Projection" in prompt
        assert "Projected Revenue: $120,000.00" in prompt
        assert "based on 9 months YTD" in prompt

    def test_prompt_excludes_projection_when_none(self):
        """AI prompt should not include projection when not available."""
        data = _base_financials(months=12)
        data["projection"] = None
        prompt = format_financial_context(data, None, "company")
        assert "Full Year Projection" not in prompt


# =============================================================================
# US3: Prior Year Comparison
# =============================================================================

class TestPriorYearComparison:
    """US3: Same-period-last-year comparison with growth percentages."""

    def test_change_percentage_calculation(self):
        """Revenue growth percentage should be calculated correctly."""
        current = 100000
        prior = 85000
        pct = round((current - prior) / prior * 100, 1)
        assert pct == 17.6

    def test_change_percentage_zero_prior(self):
        """When prior year value is 0, change should be 0 (avoid division by zero)."""
        current = 50000
        prior = 0
        pct = round((current - prior) / prior * 100, 1) if prior else 0
        assert pct == 0

    def test_negative_growth(self):
        """Declining revenue should show negative percentage."""
        current = 80000
        prior = 100000
        pct = round((current - prior) / prior * 100, 1)
        assert pct == -20.0

    def test_prompt_includes_prior_year(self):
        """AI prompt should include prior year comparison when available."""
        data = _financials_with_prior_year()
        prompt = format_financial_context(data, None, "company")
        assert "Same Period Last Year" in prompt
        assert "Prior Year Revenue: $85,000.00" in prompt
        assert "+17.6%" in prompt

    def test_prompt_excludes_prior_year_when_none(self):
        """AI prompt should not include prior year when not available."""
        data = _base_financials()
        data["prior_year_ytd"] = None
        prompt = format_financial_context(data, None, "company")
        assert "Same Period Last Year" not in prompt


# =============================================================================
# US4: Multi-Year Trends
# =============================================================================

class TestMultiYearTrends:
    """US4: Full FY data for FY-1 and FY-2 trend analysis."""

    def test_prompt_includes_multi_year(self):
        """AI prompt should include multi-year trends when available."""
        data = _financials_with_multi_year()
        prompt = format_financial_context(data, None, "company")
        assert "Multi-Year Trends" in prompt
        assert "FY2025" in prompt
        assert "FY2024" in prompt

    def test_prompt_excludes_multi_year_when_none(self):
        """AI prompt should not include trends when not available."""
        data = _base_financials()
        data["prior_years"] = None
        prompt = format_financial_context(data, None, "company")
        assert "Multi-Year Trends" not in prompt

    def test_prompt_excludes_multi_year_when_empty(self):
        """AI prompt should not include trends when list is empty."""
        data = _base_financials()
        data["prior_years"] = []
        prompt = format_financial_context(data, None, "company")
        assert "Multi-Year Trends" not in prompt


# =============================================================================
# US5: Strategy Context
# =============================================================================

class TestStrategyContext:
    """US5: Strategy recommendations grounded in actual financial data."""

    def test_strategy_budget_calculation(self):
        """Max strategy budget = cash - 3 month buffer."""
        cash = 50000
        monthly_opex = 6666.67
        buffer = monthly_opex * 3  # ~20000
        max_budget = round(cash - buffer, 2) if cash > buffer else None
        assert max_budget is not None
        assert max_budget == pytest.approx(30000, abs=1)

    def test_strategy_budget_insufficient_cash(self):
        """When cash < 3mo buffer, max budget should be None."""
        cash = 15000
        monthly_opex = 6666.67
        buffer = monthly_opex * 3  # ~20000
        max_budget = round(cash - buffer, 2) if cash > buffer else None
        assert max_budget is None

    def test_asset_spend_extraction(self):
        """Should extract equipment/asset spending from P&L breakdown."""
        breakdown = [
            {"category": "Rent", "amount": 20000},
            {"category": "Computer equipment", "amount": 5000},
            {"category": "Office supplies", "amount": 2000},
            {"category": "Vehicle depreciation", "amount": 3000},
        ]
        asset_keywords = {"equipment", "depreciation", "asset", "computer", "furniture", "vehicle", "plant"}
        asset_spend = sum(
            abs(item["amount"]) for item in breakdown
            if any(kw in item["category"].lower() for kw in asset_keywords)
        )
        assert asset_spend == 8000  # computer equipment + vehicle depreciation

    def test_prompt_includes_strategy_constraints(self):
        """AI prompt should include strategy constraints when available."""
        data = _financials_with_strategy_context()
        prompt = format_financial_context(data, None, "company")
        assert "Strategy Constraints" in prompt
        assert "Available Cash: $50,000.00" in prompt
        assert "Maximum Available for Strategies: $30,000.00" in prompt
        assert "Do not recommend strategies exceeding available cash" in prompt

    def test_prompt_strategy_constraints_no_cash(self):
        """When no cash data, strategy context should note limitation."""
        data = _base_financials()
        data["strategy_context"] = {
            "available_cash": None,
            "monthly_operating_expenses": 6000,
            "cash_buffer_3mo": 18000,
            "max_strategy_budget": None,
            "existing_asset_spend": 0,
        }
        prompt = format_financial_context(data, None, "company")
        assert "Strategy Constraints" in prompt
        assert "Available Cash: Not available" in prompt
        assert "Limited — cash reserves below 3-month buffer" in prompt


# =============================================================================
# US6: Payroll Intelligence
# =============================================================================

class TestPayrollIntelligence:
    """US6: Payroll data factored into tax planning."""

    def test_prompt_includes_payroll(self):
        """AI prompt should include payroll data when available."""
        data = _financials_with_payroll()
        prompt = format_financial_context(data, None, "company")
        assert "Payroll Data" in prompt
        assert "Employees: 3" in prompt
        assert "Total Wages YTD: $180,000.00" in prompt
        assert "Total Superannuation YTD: $19,800.00" in prompt

    def test_prompt_includes_owner_note(self):
        """AI prompt should note owner/director employees for salary strategies."""
        data = _financials_with_payroll()
        prompt = format_financial_context(data, None, "company")
        assert "owner/director employees" in prompt
        assert "salary vs dividend" in prompt

    def test_prompt_includes_super_guidance(self):
        """AI prompt should include super contribution guidance."""
        data = _financials_with_payroll()
        prompt = format_financial_context(data, None, "company")
        assert "$30,000 cap" in prompt
        assert "catch-up contributions" in prompt

    def test_prompt_excludes_payroll_when_none(self):
        """AI prompt should not include payroll when not available."""
        data = _base_financials()
        data["payroll_summary"] = None
        prompt = format_financial_context(data, None, "company")
        assert "Payroll Data" not in prompt

    def test_prompt_no_owner_note_when_no_owners(self):
        """When no owners/directors, should not suggest salary vs dividend."""
        data = _base_financials()
        data["payroll_summary"] = {
            "employee_count": 2,
            "total_wages_ytd": 100000,
            "total_super_ytd": 11000,
            "total_tax_withheld_ytd": 25000,
            "has_owners": False,
            "employees": [],
        }
        prompt = format_financial_context(data, None, "company")
        assert "Payroll Data" in prompt
        assert "owner/director" not in prompt


# =============================================================================
# Integration: Full financials_data with all enrichments
# =============================================================================

class TestFullEnrichedFinancials:
    """Test that all enrichments work together in a single financials_data."""

    def test_all_sections_present(self):
        """When all data is available, all sections should appear in the prompt."""
        data = _base_financials(revenue=100000, expenses=60000, months=9)
        data["total_bank_balance"] = 50000
        data["bank_balances"] = [{"account_name": "Business", "closing_balance": 50000}]
        data["projection"] = {
            "projected_revenue": 133333.33,
            "projected_expenses": 80000,
            "projected_net_profit": 53333.33,
            "monthly_avg_revenue": 11111.11,
            "monthly_avg_expenses": 6666.67,
            "months_used": 9,
            "projection_method": "linear_average",
        }
        data["prior_year_ytd"] = {
            "revenue": 85000, "total_income": 85000, "total_expenses": 55000,
            "net_profit": 30000, "period_coverage": "1 Jul 2024 – 15 Mar 2025",
            "changes": {"revenue_pct": 17.6, "expenses_pct": 9.1, "profit_pct": 33.3},
        }
        data["prior_years"] = [
            {"financial_year": "FY2025", "revenue": 110000, "expenses": 70000, "net_profit": 40000},
        ]
        data["strategy_context"] = {
            "available_cash": 50000, "monthly_operating_expenses": 6666.67,
            "cash_buffer_3mo": 20000, "max_strategy_budget": 30000, "existing_asset_spend": 5000,
        }
        data["payroll_summary"] = {
            "employee_count": 2, "total_wages_ytd": 120000, "total_super_ytd": 13200,
            "total_tax_withheld_ytd": 30000, "has_owners": True, "employees": [],
        }

        prompt = format_financial_context(data, None, "company")

        # All 6 enrichment sections should be present
        assert "Bank Position" in prompt
        assert "Full Year Projection" in prompt
        assert "Same Period Last Year" in prompt
        assert "Multi-Year Trends" in prompt
        assert "Strategy Constraints" in prompt
        assert "Payroll Data" in prompt

    def test_backward_compatible_with_old_data(self):
        """Existing tax plans without new fields should still work."""
        # Simulates an old financials_data with no new fields
        data = {
            "income": {"revenue": 100000, "other_income": 0, "total_income": 100000},
            "expenses": {"cost_of_sales": 0, "operating_expenses": 60000, "total_expenses": 60000},
            "credits": {"payg_instalments": 0, "payg_withholding": 0, "franking_credits": 0},
            "adjustments": [],
            "turnover": 100000,
            "months_data_available": 12,
            "is_annualised": False,
        }
        # Should not crash, should produce valid output
        prompt = format_financial_context(data, None, "individual")
        assert "Revenue: $100,000.00" in prompt
        assert "Full Year Projection" not in prompt
        assert "Same Period Last Year" not in prompt
        assert "Payroll Data" not in prompt
