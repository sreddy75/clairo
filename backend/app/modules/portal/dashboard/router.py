"""Portal dashboard API endpoints.

Client-facing endpoints for the portal dashboard.

Spec: 030-client-portal-document-requests
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.modules.portal.auth.dependencies import CurrentPortalClient
from app.modules.portal.dashboard.service import PortalDashboardService
from app.modules.portal.schemas import PortalDashboardResponse

router = APIRouter(prefix="/portal/dashboard", tags=["Portal Dashboard"])


@router.get(
    "",
    response_model=PortalDashboardResponse,
    summary="Get client portal dashboard",
)
async def get_dashboard(
    client: CurrentPortalClient,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PortalDashboardResponse:
    """Get the main dashboard for the authenticated client.

    Returns aggregated data including:
    - Pending document requests
    - Unread requests count
    - Total documents uploaded
    - Recent requests
    - Last activity timestamp
    """
    service = PortalDashboardService(db)
    return await service.get_dashboard(
        connection_id=client.connection_id,
        tenant_id=client.tenant_id,
    )


@router.get(
    "/bas-status",
    summary="Get BAS status for client",
)
async def get_bas_status(
    client: CurrentPortalClient,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get the current BAS status for the authenticated client.

    Returns information about:
    - Current quarter being prepared
    - BAS status (pending, in_progress, submitted)
    - Due date
    - Items pending action
    - Last lodged BAS
    """
    service = PortalDashboardService(db)
    return await service.get_bas_status(
        connection_id=client.connection_id,
        tenant_id=client.tenant_id,
    )


@router.get(
    "/activity",
    summary="Get recent activity for client",
)
async def get_recent_activity(
    client: CurrentPortalClient,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=10, ge=1, le=50, description="Max activities to return"),
) -> list[dict]:
    """Get recent activity for the authenticated client.

    Returns a chronological list of recent activities including:
    - Document requests received
    - Documents uploaded
    - Status changes
    """
    service = PortalDashboardService(db)
    return await service.get_recent_activity(
        connection_id=client.connection_id,
        tenant_id=client.tenant_id,
        limit=limit,
    )
