"""Depreciation Planning Service.

Provides functionality for depreciation analysis and tax planning insights:
- Current year depreciation totals by asset type and method
- Future depreciation projections
- Tax vs book depreciation comparison
- Fully depreciated asset identification

Spec 025: Fixed Assets & Enhanced Analysis
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.modules.integrations.xero.models import DepreciationMethod, XeroAsset, XeroAssetStatus
from app.modules.integrations.xero.repository import XeroAssetRepository


@dataclass
class AssetDepreciationDetail:
    """Depreciation details for a single asset."""

    asset_id: UUID
    asset_name: str
    asset_number: str | None
    asset_type_name: str | None
    purchase_date: date | None
    purchase_price: Decimal
    book_value: Decimal
    book_depreciation_this_year: Decimal
    book_accumulated_depreciation: Decimal
    book_depreciation_method: str | None
    book_depreciation_rate: Decimal | None
    tax_book_value: Decimal | None
    tax_depreciation_this_year: Decimal | None
    tax_accumulated_depreciation: Decimal | None
    tax_depreciation_method: str | None
    is_fully_depreciated: bool
    remaining_useful_life_years: Decimal | None


@dataclass
class DepreciationByType:
    """Depreciation breakdown by asset type."""

    asset_type_name: str
    asset_count: int
    total_purchase_price: Decimal
    total_book_value: Decimal
    total_depreciation_this_year: Decimal
    total_accumulated_depreciation: Decimal


@dataclass
class DepreciationByMethod:
    """Depreciation breakdown by depreciation method."""

    method: str
    method_display_name: str
    asset_count: int
    total_book_value: Decimal
    total_depreciation_this_year: Decimal


@dataclass
class TaxPlanningInsight:
    """Tax planning insight for depreciation."""

    insight_type: str  # "opportunity", "warning", "info"
    title: str
    description: str
    impact_amount: Decimal | None
    affected_assets: list[str]


@dataclass
class DepreciationSummary:
    """Comprehensive depreciation summary for tax planning."""

    # Totals
    total_assets: int
    total_purchase_price: Decimal
    total_book_value: Decimal
    total_book_depreciation_this_year: Decimal
    total_book_accumulated_depreciation: Decimal
    total_tax_depreciation_this_year: Decimal | None

    # Breakdowns
    by_asset_type: list[DepreciationByType]
    by_method: list[DepreciationByMethod]

    # Fully depreciated assets
    fully_depreciated_count: int
    fully_depreciated_assets: list[AssetDepreciationDetail]

    # Tax planning insights
    insights: list[TaxPlanningInsight]

    # Financial year info
    financial_year_start: date
    financial_year_end: date


def get_method_display_name(method: DepreciationMethod | str | None) -> str:
    """Get human-readable name for depreciation method."""
    if method is None:
        return "Not Set"

    method_str = method.value if isinstance(method, DepreciationMethod) else str(method)

    display_names = {
        "StraightLine": "Straight Line",
        "DiminishingValue100": "Diminishing Value (100%)",
        "DiminishingValue150": "Diminishing Value (150%)",
        "DiminishingValue200": "Diminishing Value (200%)",
        "NoDepreciation": "No Depreciation",
    }
    return display_names.get(method_str, method_str)


def get_financial_year_dates(
    reference_date: date | None = None,
    fy_start_month: int = 7,
) -> tuple[date, date]:
    """Get the start and end dates of the financial year."""
    if reference_date is None:
        reference_date = date.today()

    if reference_date.month >= fy_start_month:
        fy_start_year = reference_date.year
    else:
        fy_start_year = reference_date.year - 1

    fy_start = date(fy_start_year, fy_start_month, 1)

    from datetime import timedelta

    fy_end_year = fy_start_year + 1
    fy_end = date(fy_end_year, fy_start_month, 1) - timedelta(days=1)

    return fy_start, fy_end


class DepreciationService:
    """Service for depreciation analysis and tax planning.

    Provides comprehensive depreciation insights including:
    - Current year totals
    - Breakdown by asset type and method
    - Tax vs book comparison
    - Planning recommendations
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
        self.ato = settings.ato

    async def get_depreciation_summary(
        self,
        connection_id: UUID,
    ) -> DepreciationSummary:
        """Get comprehensive depreciation summary for tax planning.

        Args:
            connection_id: Xero connection ID.

        Returns:
            DepreciationSummary with totals, breakdowns, and insights.
        """
        # Get all registered assets
        assets = await self.asset_repo.get_assets_by_status(
            connection_id=connection_id,
            status=XeroAssetStatus.REGISTERED,
        )

        # Calculate totals
        total_purchase_price = Decimal(0)
        total_book_value = Decimal(0)
        total_book_depreciation_this_year = Decimal(0)
        total_book_accumulated = Decimal(0)
        total_tax_depreciation_this_year = Decimal(0)

        # Breakdowns
        by_type: dict[str, DepreciationByType] = {}
        by_method: dict[str, DepreciationByMethod] = {}

        # Fully depreciated
        fully_depreciated_assets: list[AssetDepreciationDetail] = []

        # Process each asset
        for asset in assets:
            purchase_price = asset.purchase_price or Decimal(0)
            book_value = asset.book_value or Decimal(0)
            book_dep_this_year = asset.book_depreciation_this_year or Decimal(0)
            book_accumulated = asset.book_accumulated_depreciation or Decimal(0)
            tax_dep_this_year = asset.tax_depreciation_this_year or Decimal(0)

            # Update totals
            total_purchase_price += purchase_price
            total_book_value += book_value
            total_book_depreciation_this_year += book_dep_this_year
            total_book_accumulated += book_accumulated
            total_tax_depreciation_this_year += tax_dep_this_year

            # Update by type
            type_name = asset.asset_type_name or "Uncategorized"
            if type_name not in by_type:
                by_type[type_name] = DepreciationByType(
                    asset_type_name=type_name,
                    asset_count=0,
                    total_purchase_price=Decimal(0),
                    total_book_value=Decimal(0),
                    total_depreciation_this_year=Decimal(0),
                    total_accumulated_depreciation=Decimal(0),
                )
            by_type[type_name].asset_count += 1
            by_type[type_name].total_purchase_price += purchase_price
            by_type[type_name].total_book_value += book_value
            by_type[type_name].total_depreciation_this_year += book_dep_this_year
            by_type[type_name].total_accumulated_depreciation += book_accumulated

            # Update by method
            method = asset.book_depreciation_method
            method_key = method.value if method else "NotSet"
            method_display = get_method_display_name(method)
            if method_key not in by_method:
                by_method[method_key] = DepreciationByMethod(
                    method=method_key,
                    method_display_name=method_display,
                    asset_count=0,
                    total_book_value=Decimal(0),
                    total_depreciation_this_year=Decimal(0),
                )
            by_method[method_key].asset_count += 1
            by_method[method_key].total_book_value += book_value
            by_method[method_key].total_depreciation_this_year += book_dep_this_year

            # Check if fully depreciated
            is_fully_depreciated = book_value <= Decimal(0) or (
                purchase_price > 0 and book_value / purchase_price < Decimal("0.01")
            )

            # Calculate remaining useful life
            remaining_life = None
            if asset.book_depreciation_effective_life_years and asset.purchase_date:
                years_since_purchase = (date.today() - asset.purchase_date).days / 365.25
                remaining_life = max(
                    Decimal(0),
                    Decimal(str(asset.book_depreciation_effective_life_years))
                    - Decimal(str(years_since_purchase)),
                )

            if is_fully_depreciated:
                fully_depreciated_assets.append(
                    AssetDepreciationDetail(
                        asset_id=asset.id,
                        asset_name=asset.asset_name,
                        asset_number=asset.asset_number,
                        asset_type_name=asset.asset_type_name,
                        purchase_date=asset.purchase_date,
                        purchase_price=purchase_price,
                        book_value=book_value,
                        book_depreciation_this_year=book_dep_this_year,
                        book_accumulated_depreciation=book_accumulated,
                        book_depreciation_method=method.value if method else None,
                        book_depreciation_rate=asset.book_depreciation_rate,
                        tax_book_value=asset.tax_book_value,
                        tax_depreciation_this_year=asset.tax_depreciation_this_year,
                        tax_accumulated_depreciation=asset.tax_accumulated_depreciation,
                        tax_depreciation_method=asset.tax_depreciation_method.value
                        if asset.tax_depreciation_method
                        else None,
                        is_fully_depreciated=True,
                        remaining_useful_life_years=Decimal(0),
                    )
                )

        # Generate insights
        insights = self._generate_insights(
            assets=assets,
            total_book_depreciation=total_book_depreciation_this_year,
            total_tax_depreciation=total_tax_depreciation_this_year,
            fully_depreciated_count=len(fully_depreciated_assets),
        )

        # Get financial year dates
        fy_start, fy_end = get_financial_year_dates(
            fy_start_month=self.ato.financial_year_start_month
        )

        return DepreciationSummary(
            total_assets=len(assets),
            total_purchase_price=total_purchase_price,
            total_book_value=total_book_value,
            total_book_depreciation_this_year=total_book_depreciation_this_year,
            total_book_accumulated_depreciation=total_book_accumulated,
            total_tax_depreciation_this_year=total_tax_depreciation_this_year
            if total_tax_depreciation_this_year > 0
            else None,
            by_asset_type=sorted(
                by_type.values(), key=lambda x: x.total_depreciation_this_year, reverse=True
            ),
            by_method=sorted(
                by_method.values(), key=lambda x: x.total_depreciation_this_year, reverse=True
            ),
            fully_depreciated_count=len(fully_depreciated_assets),
            fully_depreciated_assets=fully_depreciated_assets,
            insights=insights,
            financial_year_start=fy_start,
            financial_year_end=fy_end,
        )

    def _generate_insights(
        self,
        assets: list[XeroAsset],
        total_book_depreciation: Decimal,
        total_tax_depreciation: Decimal,
        fully_depreciated_count: int,
    ) -> list[TaxPlanningInsight]:
        """Generate tax planning insights based on depreciation data."""
        insights: list[TaxPlanningInsight] = []

        # Insight: Tax vs Book depreciation difference
        if total_tax_depreciation > 0:
            diff = total_tax_depreciation - total_book_depreciation
            if abs(diff) > Decimal("100"):
                if diff > 0:
                    insights.append(
                        TaxPlanningInsight(
                            insight_type="info",
                            title="Tax Depreciation Higher Than Book",
                            description=f"Tax depreciation is ${diff:,.2f} higher than book depreciation this year. "
                            "This may result in a temporary tax benefit.",
                            impact_amount=diff,
                            affected_assets=[],
                        )
                    )
                else:
                    insights.append(
                        TaxPlanningInsight(
                            insight_type="warning",
                            title="Book Depreciation Higher Than Tax",
                            description=f"Book depreciation is ${abs(diff):,.2f} higher than tax depreciation. "
                            "Ensure deferred tax liabilities are properly recorded.",
                            impact_amount=abs(diff),
                            affected_assets=[],
                        )
                    )

        # Insight: Fully depreciated assets
        if fully_depreciated_count > 0:
            insights.append(
                TaxPlanningInsight(
                    insight_type="opportunity",
                    title="Fully Depreciated Assets",
                    description=f"You have {fully_depreciated_count} fully depreciated asset(s). "
                    "Consider whether these should be disposed of or replaced for updated equipment.",
                    impact_amount=None,
                    affected_assets=[],
                )
            )

        # Insight: High depreciation this year
        if total_book_depreciation > Decimal("50000"):
            insights.append(
                TaxPlanningInsight(
                    insight_type="info",
                    title="Significant Depreciation Expense",
                    description=f"Total depreciation of ${total_book_depreciation:,.2f} this year will reduce taxable income. "
                    "Ensure this aligns with your tax planning strategy.",
                    impact_amount=total_book_depreciation,
                    affected_assets=[],
                )
            )

        # Insight: Assets with no depreciation method
        no_method_assets = [a for a in assets if a.book_depreciation_method is None]
        if no_method_assets:
            insights.append(
                TaxPlanningInsight(
                    insight_type="warning",
                    title="Assets Without Depreciation Method",
                    description=f"{len(no_method_assets)} asset(s) have no depreciation method set. "
                    "Review these to ensure correct tax treatment.",
                    impact_amount=None,
                    affected_assets=[a.asset_name for a in no_method_assets[:5]],
                )
            )

        return insights

    async def get_asset_depreciation_schedule(
        self,
        connection_id: UUID,
        asset_id: UUID,
    ) -> AssetDepreciationDetail | None:
        """Get detailed depreciation information for a single asset.

        Args:
            connection_id: Xero connection ID.
            asset_id: Asset ID.

        Returns:
            AssetDepreciationDetail or None if not found.
        """
        asset = await self.asset_repo.get_by_id(asset_id)

        if not asset or asset.connection_id != connection_id:
            return None

        # Calculate remaining useful life
        remaining_life = None
        if asset.book_depreciation_effective_life_years and asset.purchase_date:
            years_since_purchase = (date.today() - asset.purchase_date).days / 365.25
            remaining_life = max(
                Decimal(0),
                Decimal(str(asset.book_depreciation_effective_life_years))
                - Decimal(str(years_since_purchase)),
            )

        book_value = asset.book_value or Decimal(0)
        purchase_price = asset.purchase_price or Decimal(0)

        is_fully_depreciated = book_value <= Decimal(0) or (
            purchase_price > 0 and book_value / purchase_price < Decimal("0.01")
        )

        return AssetDepreciationDetail(
            asset_id=asset.id,
            asset_name=asset.asset_name,
            asset_number=asset.asset_number,
            asset_type_name=asset.asset_type_name,
            purchase_date=asset.purchase_date,
            purchase_price=purchase_price,
            book_value=book_value,
            book_depreciation_this_year=asset.book_depreciation_this_year or Decimal(0),
            book_accumulated_depreciation=asset.book_accumulated_depreciation or Decimal(0),
            book_depreciation_method=asset.book_depreciation_method.value
            if asset.book_depreciation_method
            else None,
            book_depreciation_rate=asset.book_depreciation_rate,
            tax_book_value=asset.tax_book_value,
            tax_depreciation_this_year=asset.tax_depreciation_this_year,
            tax_accumulated_depreciation=asset.tax_accumulated_depreciation,
            tax_depreciation_method=asset.tax_depreciation_method.value
            if asset.tax_depreciation_method
            else None,
            is_fully_depreciated=is_fully_depreciated,
            remaining_useful_life_years=remaining_life,
        )
