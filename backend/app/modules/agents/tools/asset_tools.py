"""Asset analysis tools for AI agents.

Spec 025: Fixed Assets & Enhanced Analysis

Provides tools for AI agents to:
- Detect instant asset write-off eligibility (T031)
- Analyze depreciation for tax planning (T036)
- Analyze tracking category profitability (T060)
"""

import json
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings


async def get_write_off_eligibility_tool(
    session: AsyncSession,
    settings: Settings,
    connection_id: UUID,
    estimated_turnover: Decimal | None = None,
    is_gst_registered: bool = True,
) -> str:
    """Detect assets eligible for instant asset write-off.

    Tool for AI agents to identify fixed assets that qualify for
    immediate tax deduction under the instant asset write-off scheme.

    Args:
        session: Database session.
        settings: Application settings.
        connection_id: The Xero connection ID.
        estimated_turnover: Business turnover for threshold calculation.
        is_gst_registered: Whether the business is GST registered.

    Returns:
        JSON string with write-off eligibility analysis.
    """
    from app.modules.integrations.xero.write_off import InstantWriteOffService

    write_off_service = InstantWriteOffService(session, settings)

    summary = await write_off_service.get_eligible_assets(
        connection_id=connection_id,
        is_gst_registered=is_gst_registered,
        estimated_turnover=estimated_turnover,
    )

    result = {
        "type": "instant_write_off_analysis",
        "eligibility": {
            "is_eligible_business": summary.is_eligible_business,
            "ineligibility_reason": summary.ineligibility_reason,
            "write_off_threshold": float(summary.write_off_threshold),
            "threshold_type": summary.threshold_type,
        },
        "financial_year": {
            "start": summary.financial_year_start.isoformat(),
            "end": summary.financial_year_end.isoformat(),
        },
        "eligible_assets": [
            {
                "asset_name": asset.asset_name,
                "asset_number": asset.asset_number,
                "purchase_date": asset.purchase_date.isoformat() if asset.purchase_date else None,
                "purchase_price": float(asset.purchase_price),
                "asset_type": asset.asset_type_name,
                "status": asset.status.value,
            }
            for asset in summary.eligible_assets
        ],
        "summary": {
            "total_eligible_amount": float(summary.total_eligible_amount),
            "asset_count": summary.asset_count,
        },
        "insights": _generate_write_off_insights(summary),
    }

    return json.dumps(result, indent=2, default=str)


async def get_depreciation_analysis_tool(
    session: AsyncSession,
    settings: Settings,
    connection_id: UUID,
) -> str:
    """Analyze depreciation for tax planning.

    Tool for AI agents to provide depreciation insights including
    current year totals, breakdown by asset type, and tax planning advice.

    Args:
        session: Database session.
        settings: Application settings.
        connection_id: The Xero connection ID.

    Returns:
        JSON string with depreciation analysis.
    """
    from app.modules.integrations.xero.depreciation import DepreciationService

    depreciation_service = DepreciationService(session, settings)

    summary = await depreciation_service.get_depreciation_summary(connection_id)

    result = {
        "type": "depreciation_analysis",
        "financial_year": {
            "start": summary.financial_year_start.isoformat(),
            "end": summary.financial_year_end.isoformat(),
        },
        "totals": {
            "depreciation_this_year": float(summary.total_depreciation_this_year),
            "book_value": float(summary.total_book_value),
            "purchase_price": float(summary.total_purchase_price),
            "asset_count": summary.asset_count,
        },
        "by_asset_type": [
            {
                "asset_type_name": item.asset_type_name,
                "depreciation_this_year": float(item.depreciation_this_year),
                "book_value": float(item.book_value),
                "count": item.count,
            }
            for item in summary.by_asset_type
        ],
        "by_method": [
            {
                "depreciation_method": item.depreciation_method,
                "depreciation_this_year": float(item.depreciation_this_year),
                "book_value": float(item.book_value),
                "count": item.count,
            }
            for item in summary.by_method
        ],
        "insights": _generate_depreciation_insights(summary),
    }

    return json.dumps(result, indent=2, default=str)


async def get_capex_analysis_tool(
    session: AsyncSession,
    settings: Settings,
    connection_id: UUID,
    years_of_history: int = 5,
) -> str:
    """Analyze capital expenditure patterns.

    Tool for AI agents to identify CapEx trends, replacement needs,
    and provide strategic insights on asset investment.

    Args:
        session: Database session.
        settings: Application settings.
        connection_id: The Xero connection ID.
        years_of_history: Number of years to analyze.

    Returns:
        JSON string with capital expenditure analysis.
    """
    from app.modules.integrations.xero.capex import CapexAnalysisService

    capex_service = CapexAnalysisService(session, settings)

    analysis = await capex_service.analyze_capital_expenditure(
        connection_id=connection_id,
        years_of_history=years_of_history,
        include_forecasts=True,
    )

    result = {
        "type": "capex_analysis",
        "overview": {
            "total_assets": analysis.total_assets,
            "total_book_value": float(analysis.total_book_value),
            "total_purchase_price": float(analysis.total_purchase_price),
            "average_asset_age_years": float(analysis.average_asset_age_years),
        },
        "trend": {
            "direction": analysis.trend.direction if analysis.trend else "unknown",
            "avg_annual_spend": float(analysis.trend.avg_annual_spend) if analysis.trend else 0,
            "trend_percentage": float(analysis.trend.trend_percentage)
            if analysis.trend and analysis.trend.trend_percentage
            else None,
        }
        if analysis.trend
        else None,
        "replacement_needs": {
            "fully_depreciated_count": analysis.fully_depreciated_count,
            "fully_depreciated_value": float(analysis.fully_depreciated_value),
            "estimated_replacement_budget": float(analysis.estimated_replacement_budget),
            "candidates": [
                {
                    "asset_name": c.asset_name,
                    "asset_type": c.asset_type_name,
                    "age_years": float(c.age_years),
                    "reason": c.replacement_reason,
                    "estimated_cost": float(c.estimated_replacement_cost)
                    if c.estimated_replacement_cost
                    else None,
                }
                for c in analysis.replacement_candidates[:10]  # Top 10
            ],
        },
        "forecasts": [
            {
                "year": f.forecast_year,
                "estimated_cost": float(f.estimated_replacement_cost),
                "assets_count": f.assets_reaching_end_of_life,
            }
            for f in analysis.forecasts
        ],
        "insights": analysis.insights,
    }

    return json.dumps(result, indent=2, default=str)


async def get_tracking_category_analysis_tool(
    session: AsyncSession,
    connection_id: UUID,
) -> str:
    """Analyze tracking categories for profitability insights.

    Tool for AI agents to provide breakdown of tracking categories
    (projects, departments, cost centers) for management reporting.

    Args:
        session: Database session.
        connection_id: The Xero connection ID.

    Returns:
        JSON string with tracking category analysis.
    """
    from app.modules.integrations.xero.repository import (
        XeroTrackingCategoryRepository,
        XeroTrackingOptionRepository,
    )

    category_repo = XeroTrackingCategoryRepository(session)
    option_repo = XeroTrackingOptionRepository(session)

    # Get categories - we need to pass tenant_id but we can get it from the connection
    # For now, we'll just list the categories without tenant filtering in this context
    # The actual filtering happens at the API layer

    # Note: In production, this would need proper tenant context
    # For the AI tool, we'll use a simplified query
    from sqlalchemy import select

    from app.modules.integrations.xero.models import XeroTrackingCategory, XeroTrackingOption

    # Get categories for this connection
    stmt = select(XeroTrackingCategory).where(XeroTrackingCategory.connection_id == connection_id)
    result = await session.execute(stmt)
    categories = result.scalars().all()

    category_data = []
    for cat in categories:
        # Get options for this category
        opt_stmt = select(XeroTrackingOption).where(
            XeroTrackingOption.tracking_category_id == cat.id
        )
        opt_result = await session.execute(opt_stmt)
        options = opt_result.scalars().all()

        category_data.append(
            {
                "name": cat.name,
                "status": cat.status,
                "options": [{"name": opt.name, "status": opt.status} for opt in options],
                "option_count": len(options),
            }
        )

    result_data = {
        "type": "tracking_category_analysis",
        "categories": category_data,
        "summary": {
            "total_categories": len(categories),
            "active_categories": len([c for c in categories if c.status == "ACTIVE"]),
        },
        "insights": _generate_tracking_insights(category_data),
    }

    return json.dumps(result_data, indent=2, default=str)


def _generate_write_off_insights(summary: Any) -> list[str]:
    """Generate insights for write-off eligibility.

    Args:
        summary: Write-off eligibility summary.

    Returns:
        List of insight strings.
    """
    insights = []

    if not summary.is_eligible_business:
        insights.append(
            f"Business is NOT eligible for instant asset write-off: {summary.ineligibility_reason}"
        )
        return insights

    if summary.asset_count == 0:
        insights.append(
            f"No assets currently qualify for instant write-off (threshold: ${summary.write_off_threshold:,.2f})"
        )
        insights.append("Consider timing of asset purchases to maximize tax benefits.")
        return insights

    insights.append(f"Found {summary.asset_count} asset(s) eligible for instant write-off.")
    insights.append(f"Total potential tax deduction: ${float(summary.total_eligible_amount):,.2f}")
    insights.append(
        f"Current threshold: ${float(summary.write_off_threshold):,.2f} ({summary.threshold_type})"
    )

    # Tax planning advice
    if summary.asset_count >= 3:
        insights.append(
            "Multiple eligible assets found - consider claiming all in this financial year "
            "for maximum tax benefit."
        )

    # Timing advice
    today = date.today()
    days_to_fy_end = (summary.financial_year_end - today).days
    if days_to_fy_end <= 90:
        insights.append(
            f"URGENT: Only {days_to_fy_end} days until end of financial year. "
            "Review write-off claims promptly."
        )

    return insights


def _generate_depreciation_insights(summary: Any) -> list[str]:
    """Generate insights for depreciation analysis.

    Args:
        summary: Depreciation summary.

    Returns:
        List of insight strings.
    """
    insights = []

    if summary.asset_count == 0:
        insights.append("No depreciating assets found.")
        return insights

    insights.append(
        f"Total depreciation expense this year: ${float(summary.total_depreciation_this_year):,.2f}"
    )
    insights.append(f"Total book value of fixed assets: ${float(summary.total_book_value):,.2f}")

    # Depreciation as % of original cost
    if summary.total_purchase_price > 0:
        depreciation_ratio = (
            float(summary.total_purchase_price - summary.total_book_value)
            / float(summary.total_purchase_price)
            * 100
        )
        insights.append(f"Assets are {depreciation_ratio:.1f}% depreciated on average.")

    # Asset type breakdown
    if summary.by_asset_type:
        top_type = max(summary.by_asset_type, key=lambda x: x.depreciation_this_year)
        insights.append(
            f"Highest depreciation category: {top_type.asset_type_name} "
            f"(${float(top_type.depreciation_this_year):,.2f})"
        )

    # Method breakdown
    if summary.by_method:
        methods = [m.depreciation_method for m in summary.by_method]
        if "DiminishingValue" in str(methods):
            insights.append(
                "Some assets use diminishing value depreciation - higher deductions in early years."
            )

    return insights


def _generate_tracking_insights(categories: list[dict]) -> list[str]:
    """Generate insights for tracking categories.

    Args:
        categories: List of tracking category data.

    Returns:
        List of insight strings.
    """
    insights = []

    if not categories:
        insights.append(
            "No tracking categories configured. Consider setting up categories "
            "for better cost and revenue analysis by project, department, or location."
        )
        return insights

    active = [c for c in categories if c["status"] == "ACTIVE"]
    insights.append(f"Found {len(active)} active tracking categories.")

    for cat in active:
        if cat["option_count"] > 0:
            insights.append(
                f"'{cat['name']}' has {cat['option_count']} options for detailed tracking."
            )

    # Suggest use cases
    category_names = [c["name"].lower() for c in categories]
    if not any("project" in name for name in category_names):
        insights.append(
            "Consider adding a 'Project' tracking category for project-based profitability analysis."
        )
    if not any("department" in name or "team" in name for name in category_names):
        insights.append("Consider adding a 'Department' category for departmental cost analysis.")

    return insights


# Tool definitions for LangChain/LangGraph integration
ASSET_ANALYSIS_TOOLS = [
    {
        "name": "get_write_off_eligibility",
        "description": (
            "Check which fixed assets are eligible for instant asset write-off "
            "under Australian tax law. Identifies assets under the threshold that "
            "can be immediately deducted. Use when asked about tax deductions, "
            "write-offs, or asset tax benefits."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "connection_id": {
                    "type": "string",
                    "description": "The Xero connection ID (UUID)",
                },
                "estimated_turnover": {
                    "type": "number",
                    "description": "Annual business turnover for threshold calculation",
                },
                "is_gst_registered": {
                    "type": "boolean",
                    "description": "Whether business is GST registered (affects threshold)",
                    "default": True,
                },
            },
            "required": ["connection_id"],
        },
    },
    {
        "name": "get_depreciation_analysis",
        "description": (
            "Analyze depreciation for tax planning. Returns current year depreciation "
            "totals, breakdown by asset type and method. Use when asked about "
            "depreciation, asset expenses, or tax planning for fixed assets."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "connection_id": {
                    "type": "string",
                    "description": "The Xero connection ID (UUID)",
                },
            },
            "required": ["connection_id"],
        },
    },
    {
        "name": "get_capex_analysis",
        "description": (
            "Analyze capital expenditure patterns and replacement needs. "
            "Identifies trends, fully depreciated assets needing replacement, "
            "and forecasts future CapEx requirements. Use when asked about "
            "asset investment, replacement planning, or capital budgeting."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "connection_id": {
                    "type": "string",
                    "description": "The Xero connection ID (UUID)",
                },
                "years_of_history": {
                    "type": "integer",
                    "description": "Years of purchase history to analyze (default 5)",
                    "default": 5,
                },
            },
            "required": ["connection_id"],
        },
    },
    {
        "name": "get_tracking_category_analysis",
        "description": (
            "Analyze tracking categories (projects, departments, locations) "
            "configured in Xero. Returns category structure and options for "
            "profitability analysis. Use when asked about project tracking, "
            "department costs, or cost center analysis."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "connection_id": {
                    "type": "string",
                    "description": "The Xero connection ID (UUID)",
                },
            },
            "required": ["connection_id"],
        },
    },
]
