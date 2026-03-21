"""Unit tests for Xero integration utility functions.

Tests cover:
- Australian Financial Year quarter date calculations
- Current quarter detection
- Quarter formatting
- Available quarters list generation
"""

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.integrations.xero.utils import (
    format_quarter,
    get_available_quarters,
    get_current_quarter,
    get_quarter_dates,
    get_quarter_for_date,
)


class TestGetQuarterDates:
    """Tests for get_quarter_dates function."""

    def test_q1_fy25(self):
        """Q1 FY25 should be July-September 2024."""
        start, end = get_quarter_dates(1, 2025)
        assert start == date(2024, 7, 1)
        assert end == date(2024, 9, 30)

    def test_q2_fy25(self):
        """Q2 FY25 should be October-December 2024."""
        start, end = get_quarter_dates(2, 2025)
        assert start == date(2024, 10, 1)
        assert end == date(2024, 12, 31)

    def test_q3_fy25(self):
        """Q3 FY25 should be January-March 2025."""
        start, end = get_quarter_dates(3, 2025)
        assert start == date(2025, 1, 1)
        assert end == date(2025, 3, 31)

    def test_q4_fy25(self):
        """Q4 FY25 should be April-June 2025."""
        start, end = get_quarter_dates(4, 2025)
        assert start == date(2025, 4, 1)
        assert end == date(2025, 6, 30)

    def test_q1_fy24(self):
        """Q1 FY24 should be July-September 2023."""
        start, end = get_quarter_dates(1, 2024)
        assert start == date(2023, 7, 1)
        assert end == date(2023, 9, 30)

    def test_q4_fy26(self):
        """Q4 FY26 should be April-June 2026."""
        start, end = get_quarter_dates(4, 2026)
        assert start == date(2026, 4, 1)
        assert end == date(2026, 6, 30)

    def test_invalid_quarter_zero(self):
        """Quarter 0 should raise ValueError."""
        with pytest.raises(ValueError, match="Quarter must be 1-4"):
            get_quarter_dates(0, 2025)

    def test_invalid_quarter_five(self):
        """Quarter 5 should raise ValueError."""
        with pytest.raises(ValueError, match="Quarter must be 1-4"):
            get_quarter_dates(5, 2025)

    def test_invalid_quarter_negative(self):
        """Negative quarter should raise ValueError."""
        with pytest.raises(ValueError, match="Quarter must be 1-4"):
            get_quarter_dates(-1, 2025)


class TestGetQuarterForDate:
    """Tests for get_quarter_for_date function."""

    def test_july_first_is_q1(self):
        """July 1 is the first day of Q1."""
        quarter, fy = get_quarter_for_date(date(2024, 7, 1))
        assert quarter == 1
        assert fy == 2025

    def test_september_last_is_q1(self):
        """September 30 is the last day of Q1."""
        quarter, fy = get_quarter_for_date(date(2024, 9, 30))
        assert quarter == 1
        assert fy == 2025

    def test_october_first_is_q2(self):
        """October 1 is the first day of Q2."""
        quarter, fy = get_quarter_for_date(date(2024, 10, 1))
        assert quarter == 2
        assert fy == 2025

    def test_december_last_is_q2(self):
        """December 31 is the last day of Q2."""
        quarter, fy = get_quarter_for_date(date(2024, 12, 31))
        assert quarter == 2
        assert fy == 2025

    def test_january_first_is_q3(self):
        """January 1 is the first day of Q3."""
        quarter, fy = get_quarter_for_date(date(2025, 1, 1))
        assert quarter == 3
        assert fy == 2025

    def test_march_last_is_q3(self):
        """March 31 is the last day of Q3."""
        quarter, fy = get_quarter_for_date(date(2025, 3, 31))
        assert quarter == 3
        assert fy == 2025

    def test_april_first_is_q4(self):
        """April 1 is the first day of Q4."""
        quarter, fy = get_quarter_for_date(date(2025, 4, 1))
        assert quarter == 4
        assert fy == 2025

    def test_june_last_is_q4(self):
        """June 30 is the last day of Q4."""
        quarter, fy = get_quarter_for_date(date(2025, 6, 30))
        assert quarter == 4
        assert fy == 2025

    def test_mid_august(self):
        """Mid August should be Q1."""
        quarter, fy = get_quarter_for_date(date(2024, 8, 15))
        assert quarter == 1
        assert fy == 2025

    def test_mid_november(self):
        """Mid November should be Q2."""
        quarter, fy = get_quarter_for_date(date(2024, 11, 15))
        assert quarter == 2
        assert fy == 2025

    def test_mid_february(self):
        """Mid February should be Q3."""
        quarter, fy = get_quarter_for_date(date(2025, 2, 15))
        assert quarter == 3
        assert fy == 2025

    def test_mid_may(self):
        """Mid May should be Q4."""
        quarter, fy = get_quarter_for_date(date(2025, 5, 15))
        assert quarter == 4
        assert fy == 2025


class TestGetCurrentQuarter:
    """Tests for get_current_quarter function."""

    @patch("app.modules.integrations.xero.utils.date")
    def test_august_returns_q1(self, mock_date):
        """August should return Q1 of the upcoming FY."""
        mock_date.today.return_value = date(2024, 8, 15)
        quarter, fy = get_current_quarter()
        assert quarter == 1
        assert fy == 2025

    @patch("app.modules.integrations.xero.utils.date")
    def test_november_returns_q2(self, mock_date):
        """November should return Q2."""
        mock_date.today.return_value = date(2024, 11, 15)
        quarter, fy = get_current_quarter()
        assert quarter == 2
        assert fy == 2025

    @patch("app.modules.integrations.xero.utils.date")
    def test_february_returns_q3(self, mock_date):
        """February should return Q3."""
        mock_date.today.return_value = date(2025, 2, 15)
        quarter, fy = get_current_quarter()
        assert quarter == 3
        assert fy == 2025

    @patch("app.modules.integrations.xero.utils.date")
    def test_may_returns_q4(self, mock_date):
        """May should return Q4."""
        mock_date.today.return_value = date(2025, 5, 15)
        quarter, fy = get_current_quarter()
        assert quarter == 4
        assert fy == 2025


class TestFormatQuarter:
    """Tests for format_quarter function."""

    def test_q1_fy25(self):
        """Q1 FY25 should format as 'Q1 FY25'."""
        assert format_quarter(1, 2025) == "Q1 FY25"

    def test_q2_fy25(self):
        """Q2 FY25 should format as 'Q2 FY25'."""
        assert format_quarter(2, 2025) == "Q2 FY25"

    def test_q3_fy24(self):
        """Q3 FY24 should format as 'Q3 FY24'."""
        assert format_quarter(3, 2024) == "Q3 FY24"

    def test_q4_fy30(self):
        """Q4 FY30 should format as 'Q4 FY30'."""
        assert format_quarter(4, 2030) == "Q4 FY30"

    def test_q1_fy00(self):
        """Q1 FY00 (2100) should format as 'Q1 FY00'."""
        assert format_quarter(1, 2100) == "Q1 FY00"

    def test_q2_fy99(self):
        """Q2 FY99 should format as 'Q2 FY99'."""
        assert format_quarter(2, 2099) == "Q2 FY99"


class TestGetAvailableQuarters:
    """Tests for get_available_quarters function."""

    def test_returns_current_and_previous_quarters(self):
        """Should return current quarter plus 4 previous by default."""
        # Q2 FY25 - mid November (more than 30 days from quarter end)
        quarters = get_available_quarters(reference_date=date(2024, 11, 15))

        # Should have current + 4 previous = 5 quarters
        assert len(quarters) == 5

        # First should be current (Q2 FY25)
        assert quarters[0] == (2, 2025)

        # Rest should be previous quarters in order
        assert quarters[1] == (1, 2025)
        assert quarters[2] == (4, 2024)
        assert quarters[3] == (3, 2024)
        assert quarters[4] == (2, 2024)

    def test_includes_next_quarter_near_end(self):
        """Should include next quarter when within 30 days of quarter end."""
        # September 15 - within 15 days of Q1 end (Sept 30)
        quarters = get_available_quarters(reference_date=date(2024, 9, 15))

        # Should have next + current + 4 previous = 6 quarters
        assert len(quarters) == 6

        # First should be next (Q2 FY25)
        assert quarters[0] == (2, 2025)

        # Second should be current (Q1 FY25)
        assert quarters[1] == (1, 2025)

    def test_no_next_quarter_early_in_quarter(self):
        """Should not include next quarter when more than 30 days from end."""
        # August 1 - early in Q1 (60 days from Sept 30)
        quarters = get_available_quarters(reference_date=date(2024, 8, 1))

        # Should have current + 4 previous = 5 quarters
        assert len(quarters) == 5

        # First should be current (Q1 FY25)
        assert quarters[0] == (1, 2025)

    def test_custom_num_previous(self):
        """Should respect custom num_previous parameter."""
        # Q2 FY25 - mid November
        quarters = get_available_quarters(num_previous=2, reference_date=date(2024, 11, 15))

        # Should have current + 2 previous = 3 quarters
        assert len(quarters) == 3
        assert quarters[0] == (2, 2025)
        assert quarters[1] == (1, 2025)
        assert quarters[2] == (4, 2024)

    def test_disable_include_next(self):
        """Should not include next quarter when include_next=False."""
        # September 29 - 1 day before Q1 end
        quarters = get_available_quarters(include_next=False, reference_date=date(2024, 9, 29))

        # Should have current + 4 previous = 5 quarters (no next)
        assert len(quarters) == 5
        assert quarters[0] == (1, 2025)  # Current, not next


class TestQuarterEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_fy_year_boundary_q4_to_q1(self):
        """Q4 to Q1 should increment FY year."""
        # June 30 is last day of Q4 FY25
        q, fy = get_quarter_for_date(date(2025, 6, 30))
        assert q == 4
        assert fy == 2025

        # July 1 is first day of Q1 FY26
        q, fy = get_quarter_for_date(date(2025, 7, 1))
        assert q == 1
        assert fy == 2026

    def test_calendar_year_boundary_q2_to_q3(self):
        """Q2 to Q3 crosses calendar year but same FY."""
        # December 31 is last day of Q2 FY25
        q, fy = get_quarter_for_date(date(2024, 12, 31))
        assert q == 2
        assert fy == 2025

        # January 1 is first day of Q3 FY25
        q, fy = get_quarter_for_date(date(2025, 1, 1))
        assert q == 3
        assert fy == 2025

    def test_leap_year_q3(self):
        """Q3 should handle leap year February correctly."""
        # February 29, 2024 (leap year)
        q, fy = get_quarter_for_date(date(2024, 2, 29))
        assert q == 3
        assert fy == 2024

    def test_dates_round_trip(self):
        """Getting quarter for start/end dates should return correct quarter."""
        for quarter in range(1, 5):
            for fy_year in [2024, 2025, 2026]:
                start, end = get_quarter_dates(quarter, fy_year)

                # Start date should be in the correct quarter
                q_start, fy_start = get_quarter_for_date(start)
                assert q_start == quarter
                assert fy_start == fy_year

                # End date should be in the correct quarter
                q_end, fy_end = get_quarter_for_date(end)
                assert q_end == quarter
                assert fy_end == fy_year
