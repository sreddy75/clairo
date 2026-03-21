"""API router for notifications.

Spec 011: Interim Lodgement - In-app deadline notifications
"""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_practice_user, get_db
from app.modules.auth.models import PracticeUser
from app.modules.notifications.schemas import (
    BulkActionResponse,
    BulkNotificationRequest,
    MarkReadResponse,
    NotificationListResponse,
    NotificationListWithPriorityResponse,
    NotificationResponse,
    NotificationSummaryResponse,
    NotificationWithPriority,
    UnreadCountResponse,
)
from app.modules.notifications.service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="List notifications for current user",
)
async def list_notifications(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    unread_only: bool = Query(False, description="Only return unread notifications"),
    limit: int = Query(50, ge=1, le=100, description="Maximum notifications to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> NotificationListResponse:
    """Get notifications for the current user.

    Returns notifications ordered by creation date (newest first).
    Includes total count and unread count for pagination.
    """
    service = NotificationService(db)

    notifications = await service.get_user_notifications(
        user_id=user.id,
        tenant_id=user.tenant_id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )

    unread_count = await service.get_unread_count(
        user_id=user.id,
        tenant_id=user.tenant_id,
    )

    # Get total count (approximate using unread + read in current batch)
    total = len(notifications) + offset
    if len(notifications) == limit:
        # There might be more, use unread_count as minimum
        total = max(total, unread_count)

    return NotificationListResponse(
        notifications=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
        unread_count=unread_count,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Get unread notification count",
)
async def get_unread_count(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> UnreadCountResponse:
    """Get the count of unread notifications for the current user.

    This is a lightweight endpoint for updating notification badges.
    """
    service = NotificationService(db)

    count = await service.get_unread_count(
        user_id=user.id,
        tenant_id=user.tenant_id,
    )

    return UnreadCountResponse(unread_count=count)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark a notification as read",
)
async def mark_notification_read(
    notification_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> NotificationResponse:
    """Mark a single notification as read.

    Returns the updated notification.
    """
    service = NotificationService(db)

    success = await service.mark_as_read(
        notification_id=notification_id,
        user_id=user.id,
        tenant_id=user.tenant_id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or already read",
        )

    await db.commit()

    # Fetch the updated notification
    notifications = await service.get_user_notifications(
        user_id=user.id,
        tenant_id=user.tenant_id,
        limit=100,
    )

    for n in notifications:
        if n.id == notification_id:
            return NotificationResponse.model_validate(n)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Notification not found",
    )


@router.post(
    "/mark-all-read",
    response_model=MarkReadResponse,
    summary="Mark all notifications as read",
)
async def mark_all_read(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> MarkReadResponse:
    """Mark all unread notifications as read for the current user."""
    service = NotificationService(db)

    count = await service.mark_all_as_read(
        user_id=user.id,
        tenant_id=user.tenant_id,
    )

    await db.commit()

    return MarkReadResponse(marked_count=count)


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a notification",
)
async def delete_notification(
    notification_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> None:
    """Delete a notification.

    This is a soft action - the notification is removed from the user's view.
    """
    service = NotificationService(db)

    success = await service.delete_notification(
        notification_id=notification_id,
        user_id=user.id,
        tenant_id=user.tenant_id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    await db.commit()


# ============================================================================
# Dashboard endpoints (Spec 011 - User Story 7: Notifications & Actions Dashboard)
# ============================================================================


@router.get(
    "/dashboard",
    response_model=NotificationListWithPriorityResponse,
    summary="List notifications for dashboard with filtering and priority",
)
async def list_notifications_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    status_filter: Literal["all", "unread", "read"] = Query(
        "all", alias="status", description="Filter by read status"
    ),
    notification_type: list[str] | None = Query(None, description="Filter by notification types"),
    priority: Literal["all", "high", "medium", "low"] = Query(
        "all", description="Filter by priority level"
    ),
    search: str | None = Query(
        None, max_length=100, description="Search in title, message, client name"
    ),
    date_from: date | None = Query(None, description="Filter by created date start"),
    date_to: date | None = Query(None, description="Filter by created date end"),
    sort_by: Literal["priority", "due_date", "created_at", "client_name"] = Query(
        "created_at", description="Sort column"
    ),
    sort_order: Literal["asc", "desc"] = Query("desc", description="Sort direction"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
) -> NotificationListWithPriorityResponse:
    """Get notifications for the dashboard with comprehensive filtering.

    Returns notifications with calculated priority, pagination, and sorting.
    Supports filtering by status, type, priority, date range, and text search.
    """
    service = NotificationService(db)
    offset = (page - 1) * limit

    notifications, total = await service.get_notifications_with_filters(
        user_id=user.id,
        tenant_id=user.tenant_id,
        status=status_filter,
        notification_types=notification_type,
        priority=priority,
        search=search,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )

    unread_count = await service.get_unread_count(
        user_id=user.id,
        tenant_id=user.tenant_id,
    )

    return NotificationListWithPriorityResponse(
        notifications=[NotificationWithPriority(**n) for n in notifications],
        total=total,
        unread_count=unread_count,
        page=page,
        limit=limit,
        has_more=(offset + len(notifications)) < total,
    )


@router.get(
    "/summary",
    response_model=NotificationSummaryResponse,
    summary="Get notification summary statistics",
)
async def get_notification_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> NotificationSummaryResponse:
    """Get summary statistics for notifications.

    Returns counts for: total unread, high priority, overdue, and due this week.
    """
    service = NotificationService(db)

    summary = await service.get_summary(
        user_id=user.id,
        tenant_id=user.tenant_id,
    )

    return NotificationSummaryResponse(**summary)


@router.post(
    "/bulk/read",
    response_model=BulkActionResponse,
    summary="Mark multiple notifications as read",
)
async def bulk_mark_read(
    request: BulkNotificationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> BulkActionResponse:
    """Mark multiple notifications as read in a single operation."""
    service = NotificationService(db)

    count = await service.bulk_mark_as_read(
        notification_ids=request.notification_ids,
        user_id=user.id,
        tenant_id=user.tenant_id,
    )

    await db.commit()

    return BulkActionResponse(affected_count=count)


@router.post(
    "/bulk/dismiss",
    response_model=BulkActionResponse,
    summary="Dismiss multiple notifications",
)
async def bulk_dismiss(
    request: BulkNotificationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> BulkActionResponse:
    """Dismiss (delete) multiple notifications in a single operation."""
    service = NotificationService(db)

    count = await service.bulk_dismiss(
        notification_ids=request.notification_ids,
        user_id=user.id,
        tenant_id=user.tenant_id,
    )

    await db.commit()

    return BulkActionResponse(affected_count=count)
