"""Utility functions for BAS preparation workflow.

Australian Financial Year:
- FY runs July 1 to June 30
- Q1: July 1 - September 30
- Q2: October 1 - December 31
- Q3: January 1 - March 31
- Q4: April 1 - June 30

ATO Due Dates (Standard):
- Q1: October 28
- Q2: February 28
- Q3: April 28
- Q4: July 28

Agent Lodgement Program Extensions:
- Adds approximately 4 weeks to standard due dates
"""

from datetime import date, datetime

# Import quarter utilities from quality module for consistency
from app.modules.quality.service import get_current_quarter, get_quarter_dates  # noqa: F401


def get_period_dates(quarter: int, fy_year: int) -> tuple[date, date]:
    """Get start and end dates for an Australian financial year quarter.

    Args:
        quarter: Quarter number (1-4)
        fy_year: Financial year (e.g., 2025 for FY2024-25)

    Returns:
        Tuple of (start_date, end_date) as date objects
    """
    if quarter == 1:
        # July 1 - September 30
        start = date(fy_year - 1, 7, 1)
        end = date(fy_year - 1, 9, 30)
    elif quarter == 2:
        # October 1 - December 31
        start = date(fy_year - 1, 10, 1)
        end = date(fy_year - 1, 12, 31)
    elif quarter == 3:
        # January 1 - March 31
        start = date(fy_year, 1, 1)
        end = date(fy_year, 3, 31)
    else:  # Q4
        # April 1 - June 30
        start = date(fy_year, 4, 1)
        end = date(fy_year, 6, 30)

    return start, end


def get_due_date(quarter: int, fy_year: int, agent_extension: bool = True) -> date:
    """Get ATO lodgement due date for a quarter.

    Args:
        quarter: Quarter number (1-4)
        fy_year: Financial year
        agent_extension: Whether to apply agent lodgement program extension (default True)

    Returns:
        Due date as date object
    """
    # Standard due dates
    if quarter == 1:
        # Q1 (Jul-Sep) due October 28
        base_due = date(fy_year - 1, 10, 28)
    elif quarter == 2:
        # Q2 (Oct-Dec) due February 28
        base_due = date(fy_year, 2, 28)
    elif quarter == 3:
        # Q3 (Jan-Mar) due April 28
        base_due = date(fy_year, 4, 28)
    else:  # Q4
        # Q4 (Apr-Jun) due July 28
        base_due = date(fy_year, 7, 28)

    # Agent lodgement program typically adds ~4 weeks
    if agent_extension:
        # Add 28 days for agent extension
        from datetime import timedelta

        base_due = base_due + timedelta(days=28)

    return base_due


def get_quarter_display_name(quarter: int, fy_year: int) -> str:
    """Get human-readable quarter name.

    Args:
        quarter: Quarter number (1-4)
        fy_year: Financial year

    Returns:
        Display name like "Q1 FY2025"
    """
    return f"Q{quarter} FY{fy_year}"


def get_quarter_from_date(d: date | datetime) -> tuple[int, int]:
    """Get quarter and FY year from a date.

    Args:
        d: Date to convert

    Returns:
        Tuple of (quarter, fy_year)
    """
    if isinstance(d, datetime):
        d = d.date()

    month = d.month

    # Determine FY year (FY starts July 1)
    fy_year = d.year + 1 if month >= 7 else d.year

    # Determine quarter
    if month in (7, 8, 9):
        quarter = 1
    elif month in (10, 11, 12):
        quarter = 2
    elif month in (1, 2, 3):
        quarter = 3
    else:
        quarter = 4

    return quarter, fy_year


def is_current_quarter(quarter: int, fy_year: int) -> bool:
    """Check if the given quarter is the current quarter.

    Args:
        quarter: Quarter number (1-4)
        fy_year: Financial year

    Returns:
        True if this is the current quarter
    """
    current_q, current_fy = get_current_quarter()
    return quarter == current_q and fy_year == current_fy


def get_quarters_for_fy(fy_year: int) -> list[tuple[int, int]]:
    """Get all quarters for a financial year.

    Args:
        fy_year: Financial year

    Returns:
        List of (quarter, fy_year) tuples in chronological order
    """
    return [(q, fy_year) for q in range(1, 5)]


def get_recent_quarters(count: int = 8) -> list[tuple[int, int]]:
    """Get recent quarters, most recent first.

    Args:
        count: Number of quarters to return

    Returns:
        List of (quarter, fy_year) tuples
    """
    quarters = []
    curr_q, curr_fy = get_current_quarter()
    q, fy = curr_q, curr_fy

    for _ in range(count):
        quarters.append((q, fy))
        # Move to previous quarter
        if q == 1:
            q = 4
            fy -= 1
        else:
            q -= 1

    return quarters
