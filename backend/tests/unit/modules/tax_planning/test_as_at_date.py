"""Spec 059.1 — user-selectable "as at" date anchor.

Unit-style coverage of the effective-date resolution logic and the
BAS-quarter helpers. The full end-to-end Xero pull is exercised by the
integration path; here we pin the pure logic that decides which date
drives the projection basis.
"""

from __future__ import annotations

from datetime import date


def _resolve_effective_date(
    as_at_date: date | None,
    recon_date: date | None,
    today: date,
) -> tuple[date, bool]:
    """Replicates the precedence rule in `pull_xero_financials`:
    `plan.as_at_date > recon_date > today`, capped at today. Returns
    (effective_date, is_override_active)."""
    anchor_candidates = [d for d in (as_at_date, recon_date) if d is not None]
    effective = min(anchor_candidates[0], today) if anchor_candidates else today
    is_override_active = as_at_date is not None and as_at_date <= today
    return effective, is_override_active


# ---------------------------------------------------------------------------
# Effective-date precedence
# ---------------------------------------------------------------------------


def test_as_at_date_wins_over_recon_date() -> None:
    """When the accountant has set a BAS quarter end, the projection anchors
    there even if Xero has reconciled to a later date."""
    eff, override = _resolve_effective_date(
        as_at_date=date(2026, 3, 31),
        recon_date=date(2026, 4, 13),
        today=date(2026, 4, 18),
    )
    assert eff == date(2026, 3, 31)
    assert override is True


def test_recon_date_used_when_as_at_date_is_null() -> None:
    eff, override = _resolve_effective_date(
        as_at_date=None,
        recon_date=date(2026, 4, 13),
        today=date(2026, 4, 18),
    )
    assert eff == date(2026, 4, 13)
    assert override is False


def test_today_used_when_no_inputs_available() -> None:
    eff, override = _resolve_effective_date(
        as_at_date=None, recon_date=None, today=date(2026, 4, 18)
    )
    assert eff == date(2026, 4, 18)
    assert override is False


def test_future_as_at_date_caps_at_today() -> None:
    """A nonsensical future date should be treated as 'right now' rather
    than projecting from data we don't have yet."""
    eff, override = _resolve_effective_date(
        as_at_date=date(2026, 12, 31),
        recon_date=date(2026, 4, 13),
        today=date(2026, 4, 18),
    )
    assert eff == date(2026, 4, 18)
    # Override flag is False — caller's date was ignored because it was in
    # the future; we shouldn't label the result as "user-anchored" in that
    # case.
    assert override is False


# ---------------------------------------------------------------------------
# months_elapsed — end-of-month rule
# ---------------------------------------------------------------------------


def _months_elapsed(fy_start: date, effective: date) -> int:
    # Matches the calculation in service.pull_xero_financials.
    months = (effective.year - fy_start.year) * 12 + (effective.month - fy_start.month)
    if effective.day >= 28 and months < 12:
        months += 1
    return max(1, min(months, 12))


def test_march_31_counts_as_nine_months_for_fy_starting_july() -> None:
    # FY 2025-26 starts 2025-07-01; Mar 31 2026 = 9 months elapsed.
    assert _months_elapsed(date(2025, 7, 1), date(2026, 3, 31)) == 9


def test_march_13_counts_as_eight_months() -> None:
    # Mid-month (not an end-of-month anchor) — 8 whole months elapsed.
    assert _months_elapsed(date(2025, 7, 1), date(2026, 3, 13)) == 8


def test_full_fy_caps_at_twelve_months() -> None:
    assert _months_elapsed(date(2025, 7, 1), date(2026, 6, 30)) == 12
    assert _months_elapsed(date(2025, 7, 1), date(2026, 7, 15)) == 12


def test_day_one_minimum_one_month() -> None:
    assert _months_elapsed(date(2025, 7, 1), date(2025, 7, 1)) == 1


# ---------------------------------------------------------------------------
# BAS quarter boundaries — matches _get_unreconciled_summary logic
# ---------------------------------------------------------------------------


def _bas_quarter(fy_start_year: int, anchor: date) -> tuple[date, date]:
    """Returns (q_start, q_end) as dates for the BAS quarter containing
    `anchor`. Mirrors the logic in service._get_unreconciled_summary."""
    month = anchor.month
    if month in (7, 8, 9):
        return date(fy_start_year, 7, 1), date(fy_start_year, 9, 30)
    if month in (10, 11, 12):
        return date(fy_start_year, 10, 1), date(fy_start_year, 12, 31)
    if month in (1, 2, 3):
        return date(fy_start_year + 1, 1, 1), date(fy_start_year + 1, 3, 31)
    return date(fy_start_year + 1, 4, 1), date(fy_start_year + 1, 6, 30)


def test_march_31_anchors_to_jan_mar_quarter() -> None:
    start, end = _bas_quarter(2025, date(2026, 3, 31))
    assert start == date(2026, 1, 1)
    assert end == date(2026, 3, 31)


def test_december_31_anchors_to_oct_dec_quarter() -> None:
    start, end = _bas_quarter(2025, date(2025, 12, 31))
    assert start == date(2025, 10, 1)
    assert end == date(2025, 12, 31)


def test_september_30_anchors_to_jul_sep_quarter() -> None:
    start, end = _bas_quarter(2025, date(2025, 9, 30))
    assert start == date(2025, 7, 1)
    assert end == date(2025, 9, 30)


def test_june_30_anchors_to_apr_jun_quarter() -> None:
    start, end = _bas_quarter(2025, date(2026, 6, 30))
    assert start == date(2026, 4, 1)
    assert end == date(2026, 6, 30)
