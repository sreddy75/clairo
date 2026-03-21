"""Action Item Pydantic schemas."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.action_items.models import ActionItemPriority, ActionItemStatus

if TYPE_CHECKING:
    from app.modules.action_items.models import ActionItem


class ActionItemCreate(BaseModel):
    """Schema for creating an action item."""

    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    notes: str | None = None  # Internal notes
    source_insight_id: UUID | None = None
    client_id: UUID | None = None
    client_name: str | None = None
    assigned_to_user_id: str | None = None
    assigned_to_name: str | None = None
    due_date: date | None = None
    priority: ActionItemPriority = ActionItemPriority.MEDIUM


class ActionItemUpdate(BaseModel):
    """Schema for updating an action item."""

    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    notes: str | None = None
    assigned_to_user_id: str | None = None
    assigned_to_name: str | None = None
    due_date: date | None = None
    priority: ActionItemPriority | None = None
    resolution_notes: str | None = None


class ActionItemComplete(BaseModel):
    """Schema for completing an action item."""

    resolution_notes: str | None = None


class ActionItemResponse(BaseModel):
    """Schema for action item response."""

    id: UUID
    tenant_id: UUID
    title: str
    description: str | None
    notes: str | None
    source_insight_id: UUID | None
    client_id: UUID | None
    client_name: str | None
    assigned_to_user_id: str | None
    assigned_to_name: str | None
    assigned_by_user_id: str
    due_date: date | None
    priority: ActionItemPriority
    status: ActionItemStatus
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    resolution_notes: str | None

    # Computed fields
    is_overdue: bool = False

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, item: ActionItem) -> ActionItemResponse:
        """Create response from model with computed fields."""
        today = datetime.now(UTC).date()

        is_overdue = (
            item.due_date is not None
            and item.due_date < today
            and item.status not in (ActionItemStatus.COMPLETED, ActionItemStatus.CANCELLED)
        )

        return cls(
            id=item.id,
            tenant_id=item.tenant_id,
            title=item.title,
            description=item.description,
            notes=item.notes,
            source_insight_id=item.source_insight_id,
            client_id=item.client_id,
            client_name=item.client_name,
            assigned_to_user_id=item.assigned_to_user_id,
            assigned_to_name=item.assigned_to_name,
            assigned_by_user_id=item.assigned_by_user_id,
            due_date=item.due_date,
            priority=item.priority,
            status=item.status,
            created_at=item.created_at,
            updated_at=item.updated_at,
            started_at=item.started_at,
            completed_at=item.completed_at,
            resolution_notes=item.resolution_notes,
            is_overdue=is_overdue,
        )


class ActionItemListResponse(BaseModel):
    """Schema for paginated action item list."""

    items: list[ActionItemResponse]
    total: int
    limit: int
    offset: int


class ActionItemStats(BaseModel):
    """Schema for action item statistics."""

    total: int = 0
    pending: int = 0
    in_progress: int = 0
    completed: int = 0
    cancelled: int = 0
    overdue: int = 0

    # By priority
    urgent: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class ConvertInsightRequest(BaseModel):
    """Schema for converting an insight to an action item."""

    title: str | None = None  # Override insight title
    description: str | None = None
    notes: str | None = None  # Internal notes
    assigned_to_user_id: str | None = None
    assigned_to_name: str | None = None
    due_date: date | None = None
    priority: ActionItemPriority | None = None  # Override insight priority
