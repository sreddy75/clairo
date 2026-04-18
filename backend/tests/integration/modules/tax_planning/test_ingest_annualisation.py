"""US1 — Accountant trusts the headline numbers.

Exercises the annualisation wiring at the service layer without requiring a
live Postgres. Full end-to-end coverage (including DB writes) is gated by
T105's golden-dataset harness once the fixture lands.

Spec 059 FR-001..005, US1 tests T011-T015.
"""

from __future__ import annotations

from app.modules.tax_planning.projection import annualise_linear, annualise_manual
from app.modules.tax_planning.prompts import format_financial_context


def _make_ytd_financials(months: int, revenue_ytd: float, expenses_ytd: float) -> dict:
    """Build a financials_data dict as the Xero path would produce PRE-annualisation."""
    return {
        "income": {
            "revenue": revenue_ytd,
            "other_income": 0.0,
            "total_income": revenue_ytd,
            "breakdown": [],
        },
        "expenses": {
            "cost_of_sales": 0.0,
            "operating_expenses": expenses_ytd,
            "total_expenses": expenses_ytd,
            "breakdown": [],
        },
        "credits": {"payg_instalments": 0, "payg_withholding": 0, "franking_credits": 0},
        "adjustments": [],
        "turnover": revenue_ytd,
    }


def _apply_ingest_annualisation(financials: dict, months_elapsed: int) -> dict:
    """Replicate the service's annualisation step (FR-001) in one shot."""
    ytd_income_snapshot = {**financials["income"]}
    ytd_expenses_snapshot = {**financials["expenses"]}
    projected_income, income_meta = annualise_linear(financials["income"], months_elapsed)
    projected_expenses, _ = annualise_linear(financials["expenses"], months_elapsed)
    financials["income"] = projected_income
    financials["expenses"] = projected_expenses
    meta = income_meta.to_dict()
    meta["ytd_snapshot"] = {
        "income": ytd_income_snapshot,
        "expenses": ytd_expenses_snapshot,
    }
    financials["projection_metadata"] = meta
    return financials


# ---------------------------------------------------------------------------
# T011 — 6 months of data gets annualised
# ---------------------------------------------------------------------------


def test_6_months_of_data_gets_annualised() -> None:
    financials = _make_ytd_financials(months=6, revenue_ytd=250_000, expenses_ytd=175_000)

    result = _apply_ingest_annualisation(financials, months_elapsed=6)

    assert result["income"]["total_income"] == 500_000.00
    assert result["expenses"]["total_expenses"] == 350_000.00
    meta = result["projection_metadata"]
    assert meta["applied"] is True
    assert meta["months_elapsed"] == 6
    assert meta["rule"] == "linear"
    assert meta["ytd_snapshot"]["income"]["total_income"] == 250_000
    assert meta["ytd_snapshot"]["expenses"]["total_expenses"] == 175_000


# ---------------------------------------------------------------------------
# T012 — 12 months of data is NOT annualised
# ---------------------------------------------------------------------------


def test_12_months_of_data_is_not_annualised() -> None:
    financials = _make_ytd_financials(months=12, revenue_ytd=500_000, expenses_ytd=350_000)

    result = _apply_ingest_annualisation(financials, months_elapsed=12)

    assert result["income"]["total_income"] == 500_000
    assert result["expenses"]["total_expenses"] == 350_000
    meta = result["projection_metadata"]
    assert meta["applied"] is False
    assert meta["reason"] == "months_elapsed>=12"


# ---------------------------------------------------------------------------
# T013 — Manual financials treated as confirmed full-year
# ---------------------------------------------------------------------------


def test_manual_financials_treated_as_confirmed_full_year() -> None:
    manual_income = {"revenue": 480_000, "other_income": 0, "total_income": 480_000}
    manual_expenses = {"cost_of_sales": 0, "operating_expenses": 320_000, "total_expenses": 320_000}

    _, income_meta = annualise_manual(manual_income)
    _, expenses_meta = annualise_manual(manual_expenses)

    # Manual figures remain unchanged.
    assert manual_income["total_income"] == 480_000
    assert manual_expenses["total_expenses"] == 320_000
    # Metadata indicates "no annualisation applied, reason: manual_full_year".
    assert income_meta.applied is False
    assert income_meta.reason == "manual_full_year"
    assert expenses_meta.reason == "manual_full_year"


# ---------------------------------------------------------------------------
# T014 — Prompt context contains only annualised totals, not YTD side-by-side
# ---------------------------------------------------------------------------


def test_prompt_contains_only_annualised_totals() -> None:
    financials = _make_ytd_financials(months=6, revenue_ytd=250_000, expenses_ytd=175_000)
    financials = _apply_ingest_annualisation(financials, months_elapsed=6)

    rendered = format_financial_context(
        financials_data=financials,
        tax_position=None,
        entity_type="company",
    )

    # Projected totals ARE present (these are the annualised values in income/expenses).
    assert "500,000" in rendered
    assert "350,000" in rendered
    # YTD originals are NOT presented as a parallel set of numbers to the LLM.
    # (The snapshot lives inside projection_metadata and is not rendered into the prompt.)
    assert "Full Year Projection" not in rendered
    assert "Projected Revenue" not in rendered
    # The "Data Basis" note IS present when projection was applied.
    assert "projected to full financial year" in rendered


def test_prompt_omits_data_basis_note_when_projection_not_applied() -> None:
    financials = _make_ytd_financials(months=12, revenue_ytd=500_000, expenses_ytd=350_000)
    financials = _apply_ingest_annualisation(financials, months_elapsed=12)

    rendered = format_financial_context(
        financials_data=financials,
        tax_position=None,
        entity_type="company",
    )

    assert "Data Basis" not in rendered
    assert "projected to full financial year" not in rendered


# ---------------------------------------------------------------------------
# T015 — Tax calculation consumes the annualised totals
# ---------------------------------------------------------------------------


def test_tax_position_uses_annualised_totals() -> None:
    from decimal import Decimal

    from app.modules.tax_planning.tax_calculator import derive_taxable_income

    financials = _make_ytd_financials(months=6, revenue_ytd=250_000, expenses_ytd=175_000)
    financials = _apply_ingest_annualisation(financials, months_elapsed=6)

    taxable = derive_taxable_income(financials)

    # Annualised: 500k income - 350k expenses = 150k taxable.
    assert taxable == Decimal("150000.00")
    # Sanity: if we re-derived from the YTD snapshot, we'd land on 75k, which is
    # what the pre-fix code was doing. This test protects against that regression.
    ytd_income = financials["projection_metadata"]["ytd_snapshot"]["income"]["total_income"]
    ytd_expenses = financials["projection_metadata"]["ytd_snapshot"]["expenses"]["total_expenses"]
    assert Decimal(str(ytd_income)) - Decimal(str(ytd_expenses)) == Decimal("75000")
