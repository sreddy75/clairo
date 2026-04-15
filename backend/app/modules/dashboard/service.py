"""Service layer for dashboard business logic.

CRITICAL: In Clairo, "client" = XeroConnection = one business = one BAS to lodge.
Dashboard shows one row per XeroConnection (Xero organization), NOT per XeroClient (contact).
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dashboard.repository import DashboardRepository
from app.modules.dashboard.schemas import (
    ClientExclusionBrief,
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
        assigned_user_id: UUID | None = None,
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

        # Format fy_year for exclusion queries (e.g., 2025 -> "2025-26")
        fy_year_str = f"{fy_year}-{str(fy_year + 1)[-2:]}"

        # Get status counts
        status_counts = await self.repo.get_status_counts(
            tenant_id=tenant_id,
            quarter_start=quarter_start,
            quarter_end=quarter_end,
            assigned_user_id=assigned_user_id,
            quarter=quarter,
            fy_year=fy_year_str,
        )

        # Get excluded count
        excluded_count = await self.repo.get_excluded_count(
            tenant_id=tenant_id,
            quarter=quarter,
            fy_year=fy_year_str,
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
            excluded_count=excluded_count,
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
        assigned_user_id: UUID | None = None,
        show_unassigned: bool = False,
        show_excluded: bool = False,
        software: str | None = None,
    ) -> ClientPortfolioResponse:
        """Get paginated list of practice clients with financial data.

        Each row = one PracticeClient = one business the practice manages.

        Args:
            tenant_id: Tenant UUID for RLS filtering
            quarter: BAS quarter (1-4), defaults to current
            fy_year: Financial year, defaults to current
            status: Optional filter by BAS status
            search: Optional search term for client name
            sort_by: Column to sort by
            sort_order: 'asc' or 'desc'
            page: Page number (1-indexed)
            limit: Items per page
            assigned_user_id: Filter by team member
            show_excluded: Show excluded clients instead of active
            software: Filter by accounting software type

        Returns:
            ClientPortfolioResponse with paginated practice clients
        """
        # Get quarter info
        if quarter is None or fy_year is None:
            current_q, current_fy = get_current_quarter()
            quarter = quarter or current_q
            fy_year = fy_year or current_fy

        quarter_start, quarter_end = get_quarter_dates(quarter, fy_year)
        fy_year_str = f"{fy_year}-{str(fy_year + 1)[-2:]}"

        # Calculate offset
        offset = (page - 1) * limit

        # Get clients from repository
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
            assigned_user_id=assigned_user_id,
            show_unassigned=show_unassigned,
            show_excluded=show_excluded,
            software=software,
            quarter=quarter,
            fy_year=fy_year_str,
        )

        # Get quality data for Xero-connected clients only
        # Must use xero_connection_id (XeroConnection.id), not c["id"] (PracticeClient.id)
        connection_ids = [
            UUID(c["xero_connection_id"])
            for c in connections_data
            if c.get("has_xero_connection") and c.get("xero_connection_id")
        ]
        quality_data = {}
        if connection_ids:
            quality_data = await self.quality_repo.get_quality_scores_for_connections(
                connection_ids=connection_ids,
                quarter=quarter,
                fy_year=fy_year,
            )

        # Convert to schema objects
        clients = []
        for c in connections_data:
            exclusion_brief = None
            if c.get("exclusion"):
                exc = c["exclusion"]
                exclusion_brief = ClientExclusionBrief(
                    id=exc["id"],
                    reason=exc.get("reason"),
                    excluded_by_name=exc.get("excluded_by_name"),
                    excluded_at=exc["excluded_at"],
                )

            clients.append(
                ClientPortfolioItem(
                    id=c["id"],
                    organization_name=c["organization_name"],
                    assigned_user_id=c.get("assigned_user_id"),
                    assigned_user_name=c.get("assigned_user_name"),
                    accounting_software=c.get("accounting_software", "xero"),
                    has_xero_connection=c.get("has_xero_connection", True),
                    xero_connection_id=c.get("xero_connection_id"),
                    notes_preview=c.get("notes_preview"),
                    unreconciled_count=c.get("unreconciled_count", 0),
                    manual_status=c.get("manual_status"),
                    exclusion=exclusion_brief,
                    total_sales=c["total_sales"],
                    total_purchases=c["total_purchases"],
                    gst_collected=c["gst_collected"],
                    gst_paid=c["gst_paid"],
                    net_gst=c["net_gst"],
                    invoice_count=c["invoice_count"],
                    transaction_count=c["transaction_count"],
                    activity_count=c["activity_count"],
                    bas_status=c["bas_status"],
                    quality_score=quality_data.get(UUID(c["xero_connection_id"]) if c.get("xero_connection_id") else None, {}).get("overall_score"),
                    critical_issues=quality_data.get(UUID(c["xero_connection_id"]) if c.get("xero_connection_id") else None, {}).get("critical_issues", 0),
                    last_synced_at=c["last_synced_at"],
                )
            )

        return ClientPortfolioResponse(
            clients=clients,
            total=total,
            page=page,
            limit=limit,
        )
