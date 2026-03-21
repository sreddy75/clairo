"""API endpoints for productivity features and day summaries."""

from __future__ import annotations

import logging
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.a2ui import DeviceContext
from app.core.dependencies import get_current_practice_user, get_db
from app.modules.agents.summary_agent import generate_day_summary
from app.modules.auth.models import PracticeUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/productivity", tags=["productivity"])


# =============================================================================
# Schemas
# =============================================================================


class DaySummaryResponse(BaseModel):
    """Response for day summary endpoint."""

    correlation_id: str = Field(..., description="Unique correlation ID")
    summary_date: str = Field(..., description="Date of the summary (ISO format)")
    text_summary: str = Field(..., description="Text summary for fallback")
    a2ui_message: dict[str, Any] | None = Field(None, description="A2UI message for rendering")
    metrics: dict[str, int] = Field(default_factory=dict, description="Summary metrics")


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "/day-summary/ui",
    response_model=DaySummaryResponse,
    summary="Get end-of-day summary with A2UI",
    description="Generate personalized end-of-day summary with visual components.",
)
async def get_day_summary_ui(
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    summary_date: date | None = None,
    is_mobile: bool = False,
    is_tablet: bool = False,
) -> DaySummaryResponse:
    """
    Generate end-of-day summary with A2UI visualization.

    The summary includes:
    - Key metrics (clients worked, BAS completed, time saved)
    - Completed work items (collapsible)
    - Highlights and achievements
    - Pending items
    - Tomorrow's priorities

    ## Parameters

    - **summary_date**: Date for the summary (defaults to today)
    - **is_mobile**: Whether viewing on mobile device
    - **is_tablet**: Whether viewing on tablet

    ## Response

    Returns an A2UI message that can be rendered using the A2UIRenderer
    component, along with a text fallback for non-visual contexts.
    """
    # Create device context
    device_context = DeviceContext(
        isMobile=is_mobile,
        isTablet=is_tablet,
    )

    try:
        # In production, we would:
        # 1. Query completed work items from the database
        # 2. Get pending items from action_items/tasks
        # 3. Calculate metrics from audit logs
        # 4. Generate highlights from insights
        # 5. Compute tomorrow's priorities from due dates

        # For now, use the agent with mock data
        result = await generate_day_summary(
            user_id=str(user.id),
            summary_date=summary_date,
            device_context=device_context,
        )

        return DaySummaryResponse(
            correlation_id=result["correlation_id"],
            summary_date=result["summary_date"],
            text_summary=result["text_summary"],
            a2ui_message=result["a2ui_message"].model_dump(by_alias=True)
            if result.get("a2ui_message")
            else None,
            metrics=result.get("metrics", {}),
        )

    except Exception as e:
        logger.exception(f"Error generating day summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate day summary",
        ) from e


@router.get(
    "/stats",
    summary="Get productivity statistics",
    description="Get productivity statistics for the current user.",
)
async def get_productivity_stats(
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    period: str = "week",
) -> dict[str, Any]:
    """
    Get productivity statistics.

    ## Parameters

    - **period**: Time period for stats - "day", "week", "month", "quarter"

    ## Response

    Returns aggregated productivity statistics for the specified period.
    """
    # Mock data - in production, query from activity logs
    stats = {
        "period": period,
        "clients_worked": 24,
        "bas_completed": 18,
        "bas_submitted": 12,
        "queries_answered": 45,
        "documents_processed": 32,
        "total_time_saved_minutes": 480,
        "average_bas_time_minutes": 35,
        "completion_rate": 0.85,
    }

    return stats


@router.get(
    "/activity",
    summary="Get recent activity",
    description="Get recent activity log for the current user.",
)
async def get_recent_activity(
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 20,
) -> dict[str, Any]:
    """
    Get recent activity.

    ## Parameters

    - **limit**: Maximum number of activity items to return (default 20)

    ## Response

    Returns a list of recent activities with timestamps and details.
    """
    # Mock data - in production, query from audit logs
    activities = [
        {
            "id": "1",
            "type": "bas_completed",
            "title": "BAS Preparation Complete",
            "client_name": "Acme Corp",
            "timestamp": "2024-12-15T14:30:00Z",
        },
        {
            "id": "2",
            "type": "query_answered",
            "title": "Query Answered",
            "client_name": "Tech Solutions",
            "timestamp": "2024-12-15T14:15:00Z",
        },
        {
            "id": "3",
            "type": "document_processed",
            "title": "Invoice Processed",
            "client_name": "Global Services",
            "timestamp": "2024-12-15T13:45:00Z",
        },
    ]

    return {
        "activities": activities[:limit],
        "total": len(activities),
    }
