"""API endpoints for quality scoring."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_practice_user, get_db
from app.modules.auth.models import PracticeUser
from app.modules.integrations.xero.repository import XeroConnectionRepository
from app.modules.quality.schemas import (
    DismissIssueRequest,
    DismissIssueResponse,
    QualityIssuesListResponse,
    QualityRecalculateResponse,
    QualityScoreResponse,
)
from app.modules.quality.service import QualityService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clients", tags=["quality"])


async def verify_connection_access(
    connection_id: UUID,
    session: AsyncSession,
    user: PracticeUser,
) -> None:
    """Verify the user has access to the connection."""
    repo = XeroConnectionRepository(session)
    connection = await repo.get_by_id(connection_id)

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found",
        )

    if connection.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )


@router.get(
    "/{connection_id}/quality",
    response_model=QualityScoreResponse,
    summary="Get quality score",
    description="Get quality score summary for a client connection.",
)
async def get_quality_score(
    connection_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    quarter: int | None = Query(None, ge=1, le=4, description="Quarter (1-4)"),
    fy_year: int | None = Query(None, ge=2020, description="Financial year (e.g., 2025)"),
) -> QualityScoreResponse:
    """Get quality score for a connection."""
    await verify_connection_access(connection_id, session, user)

    service = QualityService(session)
    return await service.get_quality_summary(
        connection_id=connection_id,
        quarter=quarter,
        fy_year=fy_year,
    )


@router.get(
    "/{connection_id}/quality/issues",
    response_model=QualityIssuesListResponse,
    summary="Get quality issues",
    description="Get list of quality issues for a client connection.",
)
async def get_quality_issues(
    connection_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    quarter: int | None = Query(None, ge=1, le=4, description="Quarter (1-4)"),
    fy_year: int | None = Query(None, ge=2020, description="Financial year"),
    severity: str | None = Query(None, description="Filter by severity"),
    issue_type: str | None = Query(None, description="Filter by issue code"),
    include_dismissed: bool = Query(False, description="Include dismissed issues"),
) -> QualityIssuesListResponse:
    """Get quality issues for a connection."""
    await verify_connection_access(connection_id, session, user)

    service = QualityService(session)
    return await service.get_issues(
        connection_id=connection_id,
        quarter=quarter,
        fy_year=fy_year,
        severity=severity,
        issue_type=issue_type,
        include_dismissed=include_dismissed,
    )


@router.post(
    "/{connection_id}/quality/recalculate",
    response_model=QualityRecalculateResponse,
    summary="Recalculate quality",
    description="Trigger quality score recalculation for a client connection.",
)
async def recalculate_quality(
    connection_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    quarter: int | None = Query(None, ge=1, le=4, description="Quarter (1-4)"),
    fy_year: int | None = Query(None, ge=2020, description="Financial year"),
) -> QualityRecalculateResponse:
    """Recalculate quality score for a connection."""
    await verify_connection_access(connection_id, session, user)

    service = QualityService(session)

    try:
        result = await service.calculate_quality(
            connection_id=connection_id,
            quarter=quarter,
            fy_year=fy_year,
            trigger_reason="manual",
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/{connection_id}/quality/issues/{issue_id}/dismiss",
    response_model=DismissIssueResponse,
    summary="Dismiss quality issue",
    description="Dismiss a quality issue with a reason.",
)
async def dismiss_quality_issue(
    connection_id: UUID,
    issue_id: UUID,
    request: DismissIssueRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> DismissIssueResponse:
    """Dismiss a quality issue."""
    await verify_connection_access(connection_id, session, user)

    service = QualityService(session)

    try:
        result = await service.dismiss_issue(
            issue_id=issue_id,
            user_id=user.id,
            reason=request.reason,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
