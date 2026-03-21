"""Service layer for dashboard business logic.

CRITICAL: In Clairo, "client" = XeroConnection = one business = one BAS to lodge.
Dashboard shows one row per XeroConnection (Xero organization), NOT per XeroClient (contact).
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dashboard.repository import DashboardRepository
from app.modules.dashboard.schemas import (
    ClientPortfolioItem,
    ClientPortfolioResponse,
    DashboardSummaryResponse,
    QualitySummary,
    StatusCounts,
)
from app.modules.integrations.xero.utils import (
    format_quarter,
    get_current_quarter,
    get_quarter_dates,
)
from app.modules.quality.repository import QualityRepository


class DashboardService:
    """Service for dashboard operations.

    All operations aggregate by XeroConnection (client business), not XeroClient (contact).
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = DashboardRepository(db)
        self.quality_repo = QualityRepository(db)

    async def get_summary(
        self,
        tenant_id: UUID,
        quarter: int | None = None,
        fy_year: int | None = None,
    ) -> DashboardSummaryResponse:
        """Get aggregated dashboard summary for the specified quarter.

        Aggregates data across all client businesses (XeroConnections) for the tenant.

        Args:
            tenant_id: Tenant UUID for RLS filtering
            quarter: BAS quarter (1-4), defaults to current
            fy_year: Financial year (e.g., 2025), defaults to current

        Returns:
            DashboardSummaryResponse with all metrics
        """
        # Get quarter info
        if quarter is None or fy_year is None:
            current_q, current_fy = get_current_quarter()
            quarter = quarter or current_q
            fy_year = fy_year or current_fy

        quarter_start, quarter_end = get_quarter_dates(quarter, fy_year)
        quarter_label = format_quarter(quarter, fy_year)

        # Get aggregated data
        summary_data = await self.repo.get_aggregated_summary(
            tenant_id=tenant_id,
            quarter_start=quarter_start,
            quarter_end=quarter_end,
        )

        # Get status counts
        status_counts = await self.repo.get_status_counts(
            tenant_id=tenant_id,
            quarter_start=quarter_start,
            quarter_end=quarter_end,
        )

        # Get quality summary across all connections
        quality_summary = await self.quality_repo.get_quality_summary_for_tenant(
            tenant_id=tenant_id,
            quarter=quarter,
            fy_year=fy_year,
        )

        # Calculate net GST
        net_gst = summary_data["gst_collected"] - summary_data["gst_paid"]

        return DashboardSummaryResponse(
            total_clients=summary_data["total_clients"],
            active_clients=summary_data["active_clients"],
            total_sales=summary_data["total_sales"],
            total_purchases=summary_data["total_purchases"],
            gst_collected=summary_data["gst_collected"],
            gst_paid=summary_data["gst_paid"],
            net_gst=net_gst,
            status_counts=StatusCounts(**status_counts),
            quality=QualitySummary(**quality_summary),
            quarter_label=quarter_label,
            quarter=quarter,
            fy_year=fy_year,
            quarter_start=quarter_start,
            quarter_end=quarter_end,
            last_sync_at=summary_data["last_sync_at"],
        )

    async def get_client_portfolio(
        self,
        tenant_id: UUID,
        quarter: int | None = None,
        fy_year: int | None = None,
        status: str | None = None,
        search: str | None = None,
        sort_by: str = "organization_name",
        sort_order: str = "asc",
        page: int = 1,
        limit: int = 25,
    ) -> ClientPortfolioResponse:
        """Get paginated list of client businesses with financial data.

        Each row = one XeroConnection = one business = one BAS to lodge.

        Args:
            tenant_id: Tenant UUID for RLS filtering
            quarter: BAS quarter (1-4), defaults to current
            fy_year: Financial year, defaults to current
            status: Optional filter by BAS status
            search: Optional search term for organization name
            sort_by: Column to sort by (organization_name, total_sales, etc.)
            sort_order: 'asc' or 'desc'
            page: Page number (1-indexed)
            limit: Items per page

        Returns:
            ClientPortfolioResponse with paginated client businesses
        """
        # Get quarter info
        if quarter is None or fy_year is None:
            current_q, current_fy = get_current_quarter()
            quarter = quarter or current_q
            fy_year = fy_year or current_fy

        quarter_start, quarter_end = get_quarter_dates(quarter, fy_year)

        # Calculate offset
        offset = (page - 1) * limit

        # Get connections from repository
        connections_data, total = await self.repo.list_connections_with_financials(
            tenant_id=tenant_id,
            quarter_start=quarter_start,
            quarter_end=quarter_end,
            status=status,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )

        # Get quality data for all connections in the list
        connection_ids = [c["id"] for c in connections_data]
        quality_data = await self.quality_repo.get_quality_scores_for_connections(
            connection_ids=connection_ids,
            quarter=quarter,
            fy_year=fy_year,
        )

        # Convert to schema objects
        clients = [
            ClientPortfolioItem(
                id=c["id"],
                organization_name=c["organization_name"],
                total_sales=c["total_sales"],
                total_purchases=c["total_purchases"],
                gst_collected=c["gst_collected"],
                gst_paid=c["gst_paid"],
                net_gst=c["net_gst"],
                invoice_count=c["invoice_count"],
                transaction_count=c["transaction_count"],
                activity_count=c["activity_count"],
                bas_status=c["bas_status"],
                quality_score=quality_data.get(c["id"], {}).get("overall_score"),
                critical_issues=quality_data.get(c["id"], {}).get("critical_issues", 0),
                last_synced_at=c["last_synced_at"],
            )
            for c in connections_data
        ]

        return ClientPortfolioResponse(
            clients=clients,
            total=total,
            page=page,
            limit=limit,
        )
