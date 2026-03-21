"""Capital Expenditure Analysis Service.

Provides functionality for analyzing capital expenditure patterns:
- Asset purchase trends by period and type
- Replacement planning based on asset age and depreciation
- Budget forecasting for future capital needs
- Fully depreciated asset detection

Spec 025: Fixed Assets & Enhanced Analysis
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.modules.integrations.xero.models import XeroAsset, XeroAssetStatus
from app.modules.integrations.xero.repository import XeroAssetRepository


@dataclass
class AssetPurchaseSummary:
    """Summary of asset purchases for a period."""

    period_label: str  # e.g., "FY2024/25", "Q1 2025", "Jan 2025"
    period_start: date
    period_end: date
    asset_count: int
    total_cost: Decimal
    asset_types: list[dict[str, Any]]  # [{"type": "name", "count": X, "cost": Y}]


@dataclass
class AssetReplacementCandidate:
    """Asset identified as needing potential replacement."""

    asset_id: UUID
    asset_name: str
    asset_number: str | None
    asset_type_name: str | None
    purchase_date: date | None
    age_years: Decimal
    purchase_price: Decimal
    book_value: Decimal
    depreciation_percentage: Decimal  # % of original value depreciated
    replacement_reason: str  # "fully_depreciated", "near_end_of_life", "old_asset"
    estimated_replacement_cost: Decimal | None  # Inflation-adjusted estimate


@dataclass
class CapexTrend:
    """Capital expenditure trend analysis."""

    direction: str  # "increasing", "decreasing", "stable"
    avg_annual_spend: Decimal
    peak_year: str | None
    peak_amount: Decimal | None
    low_year: str | None
    low_amount: Decimal | None
    trend_percentage: Decimal | None  # % change year-over-year


@dataclass
class CapexForecast:
    """Forward-looking capex forecast."""

    forecast_year: int
    estimated_replacement_cost: Decimal
    assets_reaching_end_of_life: int
    replacement_candidates: list[str]  # Asset names


@dataclass
class CapexAnalysisResult:
    """Comprehensive capital expenditure analysis."""

    # Summary metrics
    total_assets: int
    total_book_value: Decimal
    total_purchase_price: Decimal
    average_asset_age_years: Decimal

    # Purchase history
    purchase_history: list[AssetPurchaseSummary]

    # Trend analysis
    trend: CapexTrend | None

    # Replacement planning
    replacement_candidates: list[AssetReplacementCandidate]
    estimated_replacement_budget: Decimal

    # Fully depreciated assets
    fully_depreciated_count: int
    fully_depreciated_value: Decimal

    # Forecasts
    forecasts: list[CapexForecast]

    # Insights
    insights: list[
        dict[str, Any]
    ]  # {"type": "info/warning/opportunity", "title": str, "description": str}


def get_financial_year_for_date(d: date, fy_start_month: int = 7) -> tuple[int, int]:
    """Get the financial year (start, end) for a given date."""
    if d.month >= fy_start_month:
        return d.year, d.year + 1
    return d.year - 1, d.year


def get_fy_label(start_year: int, end_year: int) -> str:
    """Get financial year label like 'FY2024/25'."""
    return f"FY{start_year}/{str(end_year)[-2:]}"


class CapexAnalysisService:
    """Service for capital expenditure analysis.

    Provides insights on:
    - Historical spending patterns
    - Asset replacement needs
    - Future budget forecasting
    - Optimization opportunities
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        """Initialize the service.

        Args:
            session: Database session.
            settings: Application settings.
        """
        self.session = session
        self.settings = settings
        self.asset_repo = XeroAssetRepository(session)
        self.fy_start_month = settings.ato.financial_year_start_month

    async def analyze_capital_expenditure(
        self,
        connection_id: UUID,
        years_of_history: int = 5,
        include_forecasts: bool = True,
    ) -> CapexAnalysisResult:
        """Perform comprehensive capital expenditure analysis.

        Args:
            connection_id: Xero connection ID.
            years_of_history: Number of years to analyze for trends.
            include_forecasts: Whether to generate future forecasts.

        Returns:
            CapexAnalysisResult with complete analysis.
        """
        # Get all registered assets
        assets = await self.asset_repo.get_assets_by_status(
            connection_id=connection_id,
            status=XeroAssetStatus.REGISTERED,
        )

        if not assets:
            return CapexAnalysisResult(
                total_assets=0,
                total_book_value=Decimal(0),
                total_purchase_price=Decimal(0),
                average_asset_age_years=Decimal(0),
                purchase_history=[],
                trend=None,
                replacement_candidates=[],
                estimated_replacement_budget=Decimal(0),
                fully_depreciated_count=0,
                fully_depreciated_value=Decimal(0),
                forecasts=[],
                insights=[],
            )

        # Calculate basic metrics
        total_book_value = sum((a.book_value or Decimal(0)) for a in assets)
        total_purchase_price = sum((a.purchase_price or Decimal(0)) for a in assets)

        # Calculate average age
        today = date.today()
        ages = []
        for asset in assets:
            if asset.purchase_date:
                age_days = (today - asset.purchase_date).days
                ages.append(Decimal(str(age_days / 365.25)))
        avg_age = sum(ages) / len(ages) if ages else Decimal(0)

        # Analyze purchase history by financial year
        purchase_history = self._analyze_purchase_history(assets, years_of_history)

        # Analyze trends
        trend = self._analyze_trend(purchase_history) if len(purchase_history) >= 2 else None

        # Find replacement candidates
        replacement_candidates = self._identify_replacement_candidates(assets)
        estimated_replacement_budget = sum(
            (c.estimated_replacement_cost or c.purchase_price) for c in replacement_candidates
        )

        # Identify fully depreciated assets
        fully_depreciated = [
            a
            for a in assets
            if (a.book_value or Decimal(0)) <= Decimal(0)
            or (
                a.purchase_price
                and a.purchase_price > 0
                and (a.book_value or Decimal(0)) / a.purchase_price < Decimal("0.01")
            )
        ]
        fully_depreciated_count = len(fully_depreciated)
        fully_depreciated_value = sum((a.purchase_price or Decimal(0)) for a in fully_depreciated)

        # Generate forecasts
        forecasts = []
        if include_forecasts:
            forecasts = self._generate_forecasts(assets, years_ahead=3)

        # Generate insights
        insights = self._generate_insights(
            assets=assets,
            trend=trend,
            replacement_candidates=replacement_candidates,
            fully_depreciated_count=fully_depreciated_count,
            avg_age=avg_age,
        )

        return CapexAnalysisResult(
            total_assets=len(assets),
            total_book_value=total_book_value,
            total_purchase_price=total_purchase_price,
            average_asset_age_years=round(avg_age, 1),
            purchase_history=purchase_history,
            trend=trend,
            replacement_candidates=replacement_candidates,
            estimated_replacement_budget=estimated_replacement_budget,
            fully_depreciated_count=fully_depreciated_count,
            fully_depreciated_value=fully_depreciated_value,
            forecasts=forecasts,
            insights=insights,
        )

    def _analyze_purchase_history(
        self,
        assets: list[XeroAsset],
        years_of_history: int,
    ) -> list[AssetPurchaseSummary]:
        """Analyze purchase history by financial year."""
        today = date.today()
        current_fy_start, current_fy_end = get_financial_year_for_date(today, self.fy_start_month)

        # Build history for each financial year
        history: dict[str, AssetPurchaseSummary] = {}

        for asset in assets:
            if not asset.purchase_date:
                continue

            fy_start, fy_end = get_financial_year_for_date(asset.purchase_date, self.fy_start_month)

            # Skip if too old
            if fy_start < current_fy_start - years_of_history:
                continue

            fy_label = get_fy_label(fy_start, fy_end)

            if fy_label not in history:
                history[fy_label] = AssetPurchaseSummary(
                    period_label=fy_label,
                    period_start=date(fy_start, self.fy_start_month, 1),
                    period_end=date(fy_end, self.fy_start_month - 1, 30)
                    if self.fy_start_month > 1
                    else date(fy_end, 12, 31),
                    asset_count=0,
                    total_cost=Decimal(0),
                    asset_types=[],
                )

            summary = history[fy_label]
            summary.asset_count += 1
            summary.total_cost += asset.purchase_price or Decimal(0)

            # Track by type
            type_name = asset.asset_type_name or "Uncategorized"
            type_entry = next(
                (t for t in summary.asset_types if t["type"] == type_name),
                None,
            )
            if type_entry:
                type_entry["count"] += 1
                type_entry["cost"] += asset.purchase_price or Decimal(0)
            else:
                summary.asset_types.append(
                    {
                        "type": type_name,
                        "count": 1,
                        "cost": asset.purchase_price or Decimal(0),
                    }
                )

        # Sort by period (most recent first)
        return sorted(history.values(), key=lambda x: x.period_start, reverse=True)

    def _analyze_trend(
        self,
        purchase_history: list[AssetPurchaseSummary],
    ) -> CapexTrend:
        """Analyze spending trends from purchase history."""
        if not purchase_history:
            return CapexTrend(
                direction="stable",
                avg_annual_spend=Decimal(0),
                peak_year=None,
                peak_amount=None,
                low_year=None,
                low_amount=None,
                trend_percentage=None,
            )

        # Calculate average
        total_spend = sum(p.total_cost for p in purchase_history)
        avg_spend = total_spend / len(purchase_history)

        # Find peak and low
        sorted_by_cost = sorted(purchase_history, key=lambda x: x.total_cost)
        low = sorted_by_cost[0]
        peak = sorted_by_cost[-1]

        # Determine direction (compare most recent 2 years to older years)
        if len(purchase_history) >= 2:
            recent = purchase_history[0].total_cost
            previous = purchase_history[1].total_cost

            if previous > 0:
                change_pct = ((recent - previous) / previous) * 100
            else:
                change_pct = Decimal(0)

            if change_pct > 10:
                direction = "increasing"
            elif change_pct < -10:
                direction = "decreasing"
            else:
                direction = "stable"
        else:
            direction = "stable"
            change_pct = None

        return CapexTrend(
            direction=direction,
            avg_annual_spend=round(avg_spend, 2),
            peak_year=peak.period_label,
            peak_amount=peak.total_cost,
            low_year=low.period_label,
            low_amount=low.total_cost,
            trend_percentage=round(change_pct, 1) if change_pct is not None else None,
        )

    def _identify_replacement_candidates(
        self,
        assets: list[XeroAsset],
    ) -> list[AssetReplacementCandidate]:
        """Identify assets that may need replacement."""
        candidates = []
        today = date.today()
        inflation_rate = Decimal("0.03")  # 3% annual inflation for replacement cost estimate

        for asset in assets:
            if not asset.purchase_price or asset.purchase_price <= 0:
                continue

            book_value = asset.book_value or Decimal(0)
            purchase_price = asset.purchase_price

            # Calculate depreciation percentage
            depreciation_pct = ((purchase_price - book_value) / purchase_price) * 100

            # Calculate age
            if asset.purchase_date:
                age_days = (today - asset.purchase_date).days
                age_years = Decimal(str(age_days / 365.25))
            else:
                age_years = Decimal(0)

            # Determine replacement reason
            replacement_reason = None
            if depreciation_pct >= 100 or book_value <= 0:
                replacement_reason = "fully_depreciated"
            elif depreciation_pct >= 90:
                replacement_reason = "near_end_of_life"
            elif age_years >= 10:
                replacement_reason = "old_asset"

            if replacement_reason:
                # Estimate replacement cost with inflation
                years_old = int(age_years)
                inflation_factor = (1 + inflation_rate) ** years_old
                estimated_replacement = round(purchase_price * inflation_factor, 2)

                candidates.append(
                    AssetReplacementCandidate(
                        asset_id=asset.id,
                        asset_name=asset.asset_name,
                        asset_number=asset.asset_number,
                        asset_type_name=asset.asset_type_name,
                        purchase_date=asset.purchase_date,
                        age_years=round(age_years, 1),
                        purchase_price=purchase_price,
                        book_value=book_value,
                        depreciation_percentage=round(depreciation_pct, 1),
                        replacement_reason=replacement_reason,
                        estimated_replacement_cost=estimated_replacement,
                    )
                )

        # Sort by depreciation percentage (highest first)
        return sorted(candidates, key=lambda x: x.depreciation_percentage, reverse=True)

    def _generate_forecasts(
        self,
        assets: list[XeroAsset],
        years_ahead: int = 3,
    ) -> list[CapexForecast]:
        """Generate forward-looking replacement forecasts."""
        forecasts = []
        today = date.today()
        inflation_rate = Decimal("0.03")

        for year_offset in range(1, years_ahead + 1):
            forecast_year = today.year + year_offset
            candidates: list[str] = []
            total_cost = Decimal(0)

            for asset in assets:
                if not asset.purchase_price or asset.purchase_price <= 0:
                    continue
                if not asset.book_depreciation_effective_life_years:
                    continue
                if not asset.purchase_date:
                    continue

                # Calculate when asset reaches end of life
                effective_life = Decimal(str(asset.book_depreciation_effective_life_years))
                end_of_life_date = asset.purchase_date.replace(
                    year=asset.purchase_date.year + int(effective_life)
                )

                # Check if EOL falls in forecast year
                if end_of_life_date.year == forecast_year:
                    candidates.append(asset.asset_name)
                    # Inflation-adjusted replacement cost
                    years_old = year_offset + (today - asset.purchase_date).days / 365.25
                    inflation_factor = (1 + inflation_rate) ** int(years_old)
                    total_cost += round(asset.purchase_price * inflation_factor, 2)

            forecasts.append(
                CapexForecast(
                    forecast_year=forecast_year,
                    estimated_replacement_cost=total_cost,
                    assets_reaching_end_of_life=len(candidates),
                    replacement_candidates=candidates[:10],  # Top 10 only
                )
            )

        return forecasts

    def _generate_insights(
        self,
        assets: list[XeroAsset],
        trend: CapexTrend | None,
        replacement_candidates: list[AssetReplacementCandidate],
        fully_depreciated_count: int,
        avg_age: Decimal,
    ) -> list[dict[str, Any]]:
        """Generate capex insights."""
        insights = []

        # Trend-based insights
        if trend:
            if trend.direction == "increasing":
                insights.append(
                    {
                        "type": "info",
                        "title": "Increasing Capital Investment",
                        "description": f"Capital expenditure has increased by {trend.trend_percentage}% year-over-year. "
                        f"Average annual spend: ${trend.avg_annual_spend:,.2f}.",
                    }
                )
            elif trend.direction == "decreasing":
                insights.append(
                    {
                        "type": "warning",
                        "title": "Declining Capital Investment",
                        "description": f"Capital expenditure has decreased by {abs(trend.trend_percentage)}% year-over-year. "
                        "Consider reviewing asset replacement plans.",
                    }
                )

        # Replacement candidates insights
        fully_depreciated = [
            c for c in replacement_candidates if c.replacement_reason == "fully_depreciated"
        ]
        near_eol = [c for c in replacement_candidates if c.replacement_reason == "near_end_of_life"]

        if fully_depreciated_count > 0:
            total_replacement = sum(
                (c.estimated_replacement_cost or c.purchase_price) for c in fully_depreciated
            )
            insights.append(
                {
                    "type": "opportunity",
                    "title": f"{fully_depreciated_count} Fully Depreciated Assets",
                    "description": f"These assets have zero book value. Review for potential replacement or disposal. "
                    f"Estimated replacement cost: ${total_replacement:,.2f}.",
                }
            )

        if near_eol:
            total_near_eol = sum(
                (c.estimated_replacement_cost or c.purchase_price) for c in near_eol
            )
            insights.append(
                {
                    "type": "warning",
                    "title": f"{len(near_eol)} Assets Near End of Life",
                    "description": f"Assets with 90%+ depreciation may need replacement soon. "
                    f"Estimated budget needed: ${total_near_eol:,.2f}.",
                }
            )

        # Age insights
        if avg_age > Decimal(7):
            insights.append(
                {
                    "type": "info",
                    "title": "Aging Asset Base",
                    "description": f"Average asset age is {avg_age:.1f} years. "
                    "Consider developing a replacement schedule to avoid operational disruptions.",
                }
            )

        # Asset concentration insights
        type_counts: dict[str, int] = {}
        for asset in assets:
            type_name = asset.asset_type_name or "Uncategorized"
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        if type_counts:
            top_type = max(type_counts, key=type_counts.get)
            top_count = type_counts[top_type]
            if top_count / len(assets) > 0.6:  # More than 60% in one category
                insights.append(
                    {
                        "type": "info",
                        "title": "Asset Concentration",
                        "description": f"{top_count} of {len(assets)} assets ({top_count / len(assets) * 100:.0f}%) "
                        f"are in '{top_type}'. Consider diversification for risk management.",
                    }
                )

        return insights

    async def get_fully_depreciated_assets(
        self,
        connection_id: UUID,
    ) -> list[AssetReplacementCandidate]:
        """Get all fully depreciated assets.

        This is T042 - focused method for fully depreciated asset detection.

        Args:
            connection_id: Xero connection ID.

        Returns:
            List of fully depreciated assets as replacement candidates.
        """
        assets = await self.asset_repo.get_assets_by_status(
            connection_id=connection_id,
            status=XeroAssetStatus.REGISTERED,
        )

        candidates = []
        today = date.today()

        for asset in assets:
            if not asset.purchase_price or asset.purchase_price <= 0:
                continue

            book_value = asset.book_value or Decimal(0)
            purchase_price = asset.purchase_price

            # Check if fully depreciated
            depreciation_pct = ((purchase_price - book_value) / purchase_price) * 100
            if depreciation_pct < 99.9 and book_value > 0:
                continue

            # Calculate age
            if asset.purchase_date:
                age_days = (today - asset.purchase_date).days
                age_years = Decimal(str(age_days / 365.25))
            else:
                age_years = Decimal(0)

            # Estimate replacement cost (3% annual inflation)
            years_old = int(age_years)
            inflation_factor = Decimal("1.03") ** years_old
            estimated_replacement = round(purchase_price * inflation_factor, 2)

            candidates.append(
                AssetReplacementCandidate(
                    asset_id=asset.id,
                    asset_name=asset.asset_name,
                    asset_number=asset.asset_number,
                    asset_type_name=asset.asset_type_name,
                    purchase_date=asset.purchase_date,
                    age_years=round(age_years, 1),
                    purchase_price=purchase_price,
                    book_value=book_value,
                    depreciation_percentage=Decimal("100.0"),
                    replacement_reason="fully_depreciated",
                    estimated_replacement_cost=estimated_replacement,
                )
            )

        return sorted(candidates, key=lambda x: x.purchase_price, reverse=True)
