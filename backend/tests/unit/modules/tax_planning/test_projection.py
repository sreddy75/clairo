"""Unit tests for linear annualisation of YTD financials.

Covers spec 059 FR-001 arithmetic + research.md R2 edge cases.
"""

from decimal import Decimal

import pytest

from app.modules.tax_planning.projection import (
    ProjectionMetadata,
    annualise_linear,
    annualise_manual,
)


class TestAnnualiseLinear:
    def test_6_months_of_data_doubles_totals(self) -> None:
        ytd = {"income": {"total_income": 250_000}, "expenses": {"total_expenses": 175_000}}

        projected, meta = annualise_linear(ytd, months_elapsed=6)

        assert projected["income"]["total_income"] == 500_000.00
        assert projected["expenses"]["total_expenses"] == 350_000.00
        assert meta.applied is True
        assert meta.months_elapsed == 6
        assert meta.months_projected == 6
        assert meta.rule == "linear"
        assert meta.reason is None
        # Snapshot preserves the original YTD values so auditors can compare.
        assert meta.ytd_snapshot["income"]["total_income"] == 250_000

    def test_1_month_projects_to_full_year(self) -> None:
        ytd = {"revenue": 10_000}

        projected, meta = annualise_linear(ytd, months_elapsed=1)

        assert projected["revenue"] == 120_000.00
        assert meta.months_elapsed == 1

    def test_12_months_is_not_annualised(self) -> None:
        ytd = {"revenue": 500_000}

        projected, meta = annualise_linear(ytd, months_elapsed=12)

        assert projected["revenue"] == 500_000
        assert meta.applied is False
        assert meta.reason == "months_elapsed>=12"
        assert meta.months_projected == 0

    def test_over_12_months_is_not_annualised(self) -> None:
        ytd = {"revenue": 500_000}

        projected, meta = annualise_linear(ytd, months_elapsed=14)

        assert projected["revenue"] == 500_000
        assert meta.applied is False
        assert meta.reason == "months_elapsed>=12"

    def test_zero_months_is_clamped_to_one(self) -> None:
        ytd = {"revenue": 1_000}

        projected, meta = annualise_linear(ytd, months_elapsed=0)

        assert projected["revenue"] == 12_000.00
        assert meta.months_elapsed == 1

    def test_negative_months_is_clamped_to_one(self) -> None:
        ytd = {"revenue": 500}

        projected, meta = annualise_linear(ytd, months_elapsed=-3)

        assert projected["revenue"] == 6_000.00
        assert meta.months_elapsed == 1

    def test_nested_non_numeric_values_pass_through(self) -> None:
        ytd = {"income": {"total_income": 100_000, "currency": "AUD"}}

        projected, _ = annualise_linear(ytd, months_elapsed=6)

        assert projected["income"]["currency"] == "AUD"
        assert projected["income"]["total_income"] == 200_000.00

    def test_decimal_values_preserve_decimal_type(self) -> None:
        ytd = {"revenue": Decimal("250000.50")}

        projected, _ = annualise_linear(ytd, months_elapsed=6)

        assert isinstance(projected["revenue"], Decimal)
        assert projected["revenue"] == Decimal("500001.00")

    def test_to_dict_produces_json_serialisable_payload(self) -> None:
        _, meta = annualise_linear({"revenue": 100}, months_elapsed=6)

        payload = meta.to_dict()

        assert payload["applied"] is True
        assert payload["rule"] == "linear"
        assert isinstance(payload["applied_at"], str)  # ISO 8601 string, JSON-ready


class TestAnnualiseManual:
    def test_manual_returns_totals_unchanged_with_full_year_metadata(self) -> None:
        entered = {"income": {"total_income": 480_000}}

        projected, meta = annualise_manual(entered)

        assert projected == entered
        assert meta.applied is False
        assert meta.reason == "manual_full_year"
        assert meta.months_elapsed == 12

    def test_manual_and_linear_metadata_are_distinct(self) -> None:
        _, linear_meta = annualise_linear({"x": 100}, months_elapsed=6)
        _, manual_meta = annualise_manual({"x": 100})

        assert linear_meta.reason != manual_meta.reason
        assert linear_meta.applied is True
        assert manual_meta.applied is False


@pytest.mark.parametrize(
    ("months", "expected_factor"),
    [
        (1, 12),
        (2, 6),
        (3, 4),
        (4, 3),
        (6, 2),
        (11, 12 / 11),
    ],
)
def test_scaling_factor_matches_12_over_months(months: int, expected_factor: float) -> None:
    projected, _ = annualise_linear({"x": 100}, months_elapsed=months)
    assert projected["x"] == pytest.approx(100 * expected_factor, abs=0.01)


def test_metadata_is_frozen_dataclass_immutable_from_callers() -> None:
    _, meta = annualise_linear({"x": 100}, months_elapsed=6)
    with pytest.raises((AttributeError, TypeError)):
        meta.applied = False  # type: ignore[misc]
    assert isinstance(meta, ProjectionMetadata)
