"""Pydantic schemas for notifications API.

Spec 011: Interim Lodgement - In-app deadline notifications
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    """Response schema for a single notification."""

    id: UUID
    notification_type: str
    title: str
    message: str | None = None
    entity_type: str | None = None
    entity_id: UUID | None = None
    entity_context: dict | None = None
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationWithPriority(BaseModel):
    """Notification with calculated priority for dashboard display."""

    id: UUID
    notification_type: str
    title: str
    message: str | None = None
    entity_type: str | None = None
    entity_id: UUID | None = None
    entity_context: dict | None = None
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime
    priority: Literal["high", "medium", "low"]
    due_date: date | None = None
    days_remaining: int | None = None
    client_name: str | None = None
    connection_id: UUID | None = None

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    """Response schema for list of notifications."""

    notifications: list[NotificationResponse]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    """Response schema for unread notification count."""

    unread_count: int


class MarkReadRequest(BaseModel):
    """Request schema for marking notifications as read."""

    notification_ids: list[UUID] = Field(
        ...,
        description="List of notification IDs to mark as read",
        min_length=1,
    )


class MarkReadResponse(BaseModel):
    """Response schema for mark as read operation."""

    marked_count: int


class NotificationSummaryResponse(BaseModel):
    """Summary statistics for notifications dashboard."""

    total_unread: int
    high_priority: int
    overdue: int
    due_this_week: int


class BulkNotificationRequest(BaseModel):
    """Request for bulk notification actions."""

    notification_ids: list[UUID] = Field(
        ...,
        description="List of notification IDs to act on",
        min_length=1,
        max_length=100,
    )


class BulkActionResponse(BaseModel):
    """Response for bulk notification actions."""

    affected_count: int


class NotificationListWithPriorityResponse(BaseModel):
    """Response schema for paginated list of notifications with priority."""

    notifications: list[NotificationWithPriority]
    total: int
    unread_count: int
    page: int
    limit: int
    has_more: bool
