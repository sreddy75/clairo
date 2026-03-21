"""Utility functions for Xero integration.

This module provides helper functions for:
- Australian Financial Year quarter calculations
- Date range utilities for BAS periods
"""

from datetime import date


def get_quarter_dates(quarter: int, fy_year: int) -> tuple[date, date]:
    """Get start and end dates for an Australian Financial Year quarter.

    Australian FY runs July to June. For example:
    - FY25 = July 2024 to June 2025
    - Q1 FY25 = July 2024 to September 2024
    - Q2 FY25 = October 2024 to December 2024
    - Q3 FY25 = January 2025 to March 2025
    - Q4 FY25 = April 2025 to June 2025

    Args:
        quarter: Quarter number (1-4)
        fy_year: Financial year (e.g., 2025 for FY25)

    Returns:
        Tuple of (start_date, end_date) for the quarter

    Raises:
        ValueError: If quarter is not 1-4

    Examples:
        >>> get_quarter_dates(1, 2025)
        (datetime.date(2024, 7, 1), datetime.date(2024, 9, 30))
        >>> get_quarter_dates(2, 2025)
        (datetime.date(2024, 10, 1), datetime.date(2024, 12, 31))
        >>> get_quarter_dates(3, 2025)
        (datetime.date(2025, 1, 1), datetime.date(2025, 3, 31))
        >>> get_quarter_dates(4, 2025)
        (datetime.date(2025, 4, 1), datetime.date(2025, 6, 30))
    """
    if quarter not in (1, 2, 3, 4):
        raise ValueError(f"Quarter must be 1-4, got {quarter}")

    # Q1 and Q2 are in the calendar year before the FY year
    # Q3 and Q4 are in the FY year
    if quarter == 1:
        # July - September (previous calendar year)
        return date(fy_year - 1, 7, 1), date(fy_year - 1, 9, 30)
    elif quarter == 2:
        # October - December (previous calendar year)
        return date(fy_year - 1, 10, 1), date(fy_year - 1, 12, 31)
    elif quarter == 3:
        # January - March (FY year)
        return date(fy_year, 1, 1), date(fy_year, 3, 31)
    else:  # quarter == 4
        # April - June (FY year)
        return date(fy_year, 4, 1), date(fy_year, 6, 30)


def get_current_quarter() -> tuple[int, int]:
    """Get the current Australian Financial Year quarter and year.

    Returns:
        Tuple of (quarter_number, fy_year)

    Examples:
        If today is 2024-08-15:
        >>> get_current_quarter()
        (1, 2025)

        If today is 2024-11-20:
        >>> get_current_quarter()
        (2, 2025)

        If today is 2025-02-10:
        >>> get_current_quarter()
        (3, 2025)

        If today is 2025-05-01:
        >>> get_current_quarter()
        (4, 2025)
    """
    today = date.today()
    return get_quarter_for_date(today)


def get_quarter_for_date(d: date) -> tuple[int, int]:
    """Get the Australian FY quarter and year for a specific date.

    Args:
        d: The date to get the quarter for

    Returns:
        Tuple of (quarter_number, fy_year)

    Examples:
        >>> get_quarter_for_date(date(2024, 8, 15))
        (1, 2025)
        >>> get_quarter_for_date(date(2024, 12, 31))
        (2, 2025)
        >>> get_quarter_for_date(date(2025, 1, 1))
        (3, 2025)
        >>> get_quarter_for_date(date(2025, 6, 30))
        (4, 2025)
    """
    month = d.month
    year = d.year

    if month >= 7:
        # July-December: Q1 or Q2, FY is next calendar year
        fy_year = year + 1
        if month <= 9:
            quarter = 1
        else:
            quarter = 2
    else:
        # January-June: Q3 or Q4, FY is current calendar year
        fy_year = year
        if month <= 3:
            quarter = 3
        else:
            quarter = 4

    return quarter, fy_year


def format_quarter(quarter: int, fy_year: int) -> str:
    """Format a quarter for display.

    Args:
        quarter: Quarter number (1-4)
        fy_year: Financial year (e.g., 2025)

    Returns:
        Formatted string like "Q2 FY25"

    Examples:
        >>> format_quarter(1, 2025)
        'Q1 FY25'
        >>> format_quarter(3, 2024)
        'Q3 FY24'
    """
    return f"Q{quarter} FY{fy_year % 100:02d}"


def get_available_quarters(
    num_previous: int = 4,
    include_next: bool = True,
    reference_date: date | None = None,
) -> list[tuple[int, int]]:
    """Get a list of available quarters for selection.

    Returns the current quarter, previous quarters, and optionally the next quarter
    if we're within the last month of the current quarter.

    Args:
        num_previous: Number of previous quarters to include
        include_next: Whether to include the next quarter if near end of current
        reference_date: Date to use as "today" (for testing), defaults to actual today

    Returns:
        List of (quarter, fy_year) tuples, most recent first
    """
    today = reference_date or date.today()
    current_quarter, current_fy = get_quarter_for_date(today)
    quarters = []

    # Check if we should include next quarter (within last month of current)
    if include_next:
        _, end_date = get_quarter_dates(current_quarter, current_fy)
        days_until_end = (end_date - today).days
        if days_until_end <= 30:
            # Add next quarter
            next_q, next_fy = _next_quarter(current_quarter, current_fy)
            quarters.append((next_q, next_fy))

    # Add current quarter
    quarters.append((current_quarter, current_fy))

    # Add previous quarters
    q, fy = current_quarter, current_fy
    for _ in range(num_previous):
        q, fy = _previous_quarter(q, fy)
        quarters.append((q, fy))

    return quarters


def _next_quarter(quarter: int, fy_year: int) -> tuple[int, int]:
    """Get the next quarter after the given one."""
    if quarter == 4:
        return 1, fy_year + 1
    return quarter + 1, fy_year


def _previous_quarter(quarter: int, fy_year: int) -> tuple[int, int]:
    """Get the previous quarter before the given one."""
    if quarter == 1:
        return 4, fy_year - 1
    return quarter - 1, fy_year
