"""API endpoints for dashboard.

CRITICAL: In Clairo, "client" = XeroConnection = one business = one BAS to lodge.
Each row in /clients represents one Xero organization, NOT a contact within an org.
"""

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.a2ui import A2UIMessage, get_device_context_from_request
from app.database import get_db
from app.modules.auth.models import PracticeUser
from app.modules.auth.permissions import Permission, require_permission
from app.modules.dashboard.a2ui_generator import generate_dashboard_ui
from app.modules.dashboard.schemas import (
    ClientPortfolioResponse,
    DashboardSummaryResponse,
)
from app.modules.dashboard.service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/ui", response_model=A2UIMessage, tags=["A2UI"])
async def get_dashboard_ui(
    quarter: int | None = Query(None, ge=1, le=4, description="BAS quarter (1-4)"),
    fy_year: int | None = Query(None, ge=2020, le=2100, description="Financial year"),
    demo: bool = Query(False, description="Enable demo mode to showcase A2UI components"),
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    db: AsyncSession = Depends(get_db),
    user_agent: str | None = Header(None, alias="user-agent"),
    x_device_type: str | None = Header(None, alias="X-Device-Type"),
) -> A2UIMessage:
    """Get A2UI for the dashboard.

    Returns a personalized dashboard UI that adapts based on:
    - Time of day (morning focus, afternoon review, evening summary)
    - Day of week (Monday planning, Friday wrap-up)
    - Quarter end urgency (BAS deadline proximity)
    - Device type (mobile vs desktop layout)
    - Current workload and priorities
    """
    device_context = get_device_context_from_request(user_agent, x_device_type)
    return await generate_dashboard_ui(
        db=db,
        tenant_id=current_user.tenant_id,
        device_context=device_context,
        quarter=quarter,
        fy_year=fy_year,
        demo=demo,
    )


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    quarter: int | None = Query(None, ge=1, le=4, description="BAS quarter (1-4)"),
    fy_year: int | None = Query(None, ge=2020, le=2100, description="Financial year"),
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummaryResponse:
    """Get aggregated dashboard summary for the specified quarter.

    Returns summary metrics across all client businesses (XeroConnections):
    - Total and active client counts (number of businesses)
    - Aggregate sales, purchases, and GST amounts
    - Status counts (ready, needs review, no activity, missing data)
    - Quarter information

    Defaults to current BAS quarter if not specified.
    """
    service = DashboardService(db)
    return await service.get_summary(
        tenant_id=current_user.tenant_id,
        quarter=quarter,
        fy_year=fy_year,
    )


@router.get("/clients", response_model=ClientPortfolioResponse)
async def get_client_portfolio(
    quarter: int | None = Query(None, ge=1, le=4, description="BAS quarter (1-4)"),
    fy_year: int | None = Query(None, ge=2020, le=2100, description="Financial year"),
    status: str | None = Query(
        None,
        description="Filter by BAS status: ready, needs_review, no_activity, missing_data",
    ),
    search: str | None = Query(None, description="Search by organization name"),
    sort_by: str = Query(
        "organization_name",
        description="Sort by: organization_name, total_sales, total_purchases, net_gst, activity_count",
    ),
    sort_order: str = Query("asc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(25, ge=1, le=100, description="Items per page"),
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    db: AsyncSession = Depends(get_db),
) -> ClientPortfolioResponse:
    """Get paginated list of client businesses with financial data.

    Each row represents one XeroConnection (client business) = one BAS to lodge.

    Returns businesses with their financial summaries for the specified quarter,
    including total sales, purchases, GST amounts, and BAS readiness status.

    Supports filtering by status, searching by organization name, sorting, and pagination.
    """
    service = DashboardService(db)
    return await service.get_client_portfolio(
        tenant_id=current_user.tenant_id,
        quarter=quarter,
        fy_year=fy_year,
        status=status,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        limit=limit,
    )
