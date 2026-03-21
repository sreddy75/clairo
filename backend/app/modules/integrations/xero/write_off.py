"""Instant Asset Write-Off Detection Service.

Provides functionality to identify assets eligible for instant asset write-off
under ATO small business rules. Supports the following scenarios:

- Identify assets under the threshold purchased in the current financial year
- Calculate total potential write-off deduction
- Check business eligibility based on turnover
- Handle GST-inclusive vs GST-exclusive thresholds

References:
- ATO: Instant asset write-off for eligible businesses
  https://www.ato.gov.au/Business/Depreciation-and-capital-expenses-and-allowances/Simpler-depreciation-for-small-business/Instant-asset-write-off/

Spec 025: Fixed Assets & Enhanced Analysis
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.modules.integrations.xero.models import XeroAsset, XeroAssetStatus
from app.modules.integrations.xero.repository import XeroAssetRepository


@dataclass
class WriteOffEligibleAsset:
    """Asset eligible for instant write-off."""

    asset_id: UUID
    xero_asset_id: str
    asset_name: str
    asset_number: str | None
    purchase_date: date | None
    purchase_price: Decimal
    asset_type_name: str | None
    status: XeroAssetStatus


@dataclass
class WriteOffSummary:
    """Summary of instant asset write-off eligibility."""

    is_eligible_business: bool
    ineligibility_reason: str | None
    write_off_threshold: Decimal
    threshold_type: str  # "gst_exclusive" or "gst_inclusive"
    financial_year_start: date
    financial_year_end: date
    eligible_assets: list[WriteOffEligibleAsset]
    total_eligible_amount: Decimal
    asset_count: int


def get_financial_year_dates(
    reference_date: date | None = None,
    fy_start_month: int = 7,
) -> tuple[date, date]:
    """Get the start and end dates of the financial year.

    Args:
        reference_date: Date to use as reference (defaults to today)
        fy_start_month: Month the financial year starts (1-12)

    Returns:
        Tuple of (fy_start, fy_end) dates
    """
    if reference_date is None:
        reference_date = date.today()

    # Determine the financial year start
    if reference_date.month >= fy_start_month:
        fy_start_year = reference_date.year
    else:
        fy_start_year = reference_date.year - 1

    fy_start = date(fy_start_year, fy_start_month, 1)

    # Financial year ends the day before the next FY starts
    fy_end_year = fy_start_year + 1
    fy_end = date(fy_end_year, fy_start_month, 1)
    # Subtract one day to get the last day of the financial year
    from datetime import timedelta

    fy_end = fy_end - timedelta(days=1)

    return fy_start, fy_end


class InstantWriteOffService:
    """Service for detecting instant asset write-off eligibility.

    Analyzes fixed assets to identify those qualifying for instant
    asset write-off under ATO small business rules.
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        """Initialize the service.

        Args:
            session: Database session.
            settings: Application settings with ATO configuration.
        """
        self.session = session
        self.settings = settings
        self.asset_repo = XeroAssetRepository(session)
        self.ato = settings.ato

    async def get_eligible_assets(
        self,
        connection_id: UUID,
        is_gst_registered: bool = True,
        estimated_turnover: Decimal | None = None,
    ) -> WriteOffSummary:
        """Get assets eligible for instant asset write-off.

        Args:
            connection_id: Xero connection ID.
            is_gst_registered: Whether the business is GST registered.
            estimated_turnover: Estimated annual turnover for eligibility check.

        Returns:
            WriteOffSummary with eligible assets and totals.
        """
        # Check business eligibility
        is_eligible_business = True
        ineligibility_reason = None

        if estimated_turnover is not None:
            turnover_threshold = Decimal(self.ato.small_business_turnover_threshold)
            if estimated_turnover > turnover_threshold:
                is_eligible_business = False
                ineligibility_reason = (
                    f"Business turnover exceeds the small business threshold "
                    f"of ${turnover_threshold:,.0f}"
                )

        # Calculate threshold
        base_threshold = Decimal(self.ato.instant_write_off_threshold)
        gst_rate = Decimal(str(self.ato.gst_rate))

        if is_gst_registered:
            # GST-exclusive threshold for GST-registered businesses
            threshold = base_threshold
            threshold_type = "gst_exclusive"
        else:
            # GST-inclusive threshold for non-GST registered businesses
            threshold = base_threshold * (1 + gst_rate)
            threshold_type = "gst_inclusive"

        # Get financial year dates
        fy_start, fy_end = get_financial_year_dates(
            fy_start_month=self.ato.financial_year_start_month
        )

        # Get eligible assets from database
        if is_eligible_business:
            assets = await self.asset_repo.get_eligible_for_instant_write_off(
                connection_id=connection_id,
                threshold=threshold,
                from_date=fy_start,
                to_date=fy_end,
            )
        else:
            assets = []

        # Convert to eligible assets
        eligible_assets = [
            WriteOffEligibleAsset(
                asset_id=asset.id,
                xero_asset_id=asset.xero_asset_id,
                asset_name=asset.asset_name,
                asset_number=asset.asset_number,
                purchase_date=asset.purchase_date,
                purchase_price=asset.purchase_price or Decimal(0),
                asset_type_name=asset.asset_type_name,
                status=asset.status,
            )
            for asset in assets
        ]

        # Calculate total eligible amount
        total_eligible = sum(asset.purchase_price for asset in eligible_assets)

        return WriteOffSummary(
            is_eligible_business=is_eligible_business,
            ineligibility_reason=ineligibility_reason,
            write_off_threshold=threshold,
            threshold_type=threshold_type,
            financial_year_start=fy_start,
            financial_year_end=fy_end,
            eligible_assets=eligible_assets,
            total_eligible_amount=total_eligible,
            asset_count=len(eligible_assets),
        )

    async def check_asset_eligibility(
        self,
        asset: XeroAsset,
        is_gst_registered: bool = True,
    ) -> tuple[bool, str | None]:
        """Check if a specific asset is eligible for instant write-off.

        Args:
            asset: The asset to check.
            is_gst_registered: Whether the business is GST registered.

        Returns:
            Tuple of (is_eligible, reason_if_not)
        """
        # Check if asset has a purchase price
        if not asset.purchase_price:
            return False, "Asset has no purchase price"

        # Calculate threshold
        base_threshold = Decimal(self.ato.instant_write_off_threshold)
        gst_rate = Decimal(str(self.ato.gst_rate))

        if is_gst_registered:
            threshold = base_threshold
        else:
            threshold = base_threshold * (1 + gst_rate)

        # Check price against threshold
        if asset.purchase_price >= threshold:
            return False, f"Purchase price exceeds threshold of ${threshold:,.2f}"

        # Check purchase date
        if not asset.purchase_date:
            return False, "Asset has no purchase date"

        fy_start, fy_end = get_financial_year_dates(
            fy_start_month=self.ato.financial_year_start_month
        )

        if asset.purchase_date < fy_start or asset.purchase_date > fy_end:
            return False, (
                f"Asset not purchased in current financial year "
                f"({fy_start.strftime('%d %b %Y')} - {fy_end.strftime('%d %b %Y')})"
            )

        # Check status
        if asset.status == XeroAssetStatus.DISPOSED:
            return False, "Asset has already been disposed"

        return True, None
