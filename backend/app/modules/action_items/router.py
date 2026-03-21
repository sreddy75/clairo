"""Action Items API router."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_tenant_id
from app.database import get_db
from app.modules.action_items.models import ActionItemPriority, ActionItemStatus
from app.modules.action_items.schemas import (
    ActionItemComplete,
    ActionItemCreate,
    ActionItemListResponse,
    ActionItemResponse,
    ActionItemStats,
    ActionItemUpdate,
)
from app.modules.action_items.service import ActionItemService

router = APIRouter(prefix="/api/v1/action-items", tags=["action-items"])


# Type aliases for dependencies
DbSession = Annotated[AsyncSession, Depends(get_db)]
TenantIdDep = Annotated[UUID, Depends(get_current_tenant_id)]


async def get_current_user_id(request: Request) -> str:
    """Get current user ID from Clerk JWT claims."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user.sub


UserIdDep = Annotated[str, Depends(get_current_user_id)]


@router.post("", response_model=ActionItemResponse, status_code=status.HTTP_201_CREATED)
async def create_action_item(
    data: ActionItemCreate,
    db: DbSession,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
) -> ActionItemResponse:
    """Create a new action item."""
    service = ActionItemService(db)
    item = await service.create(tenant_id, user_id, data)
    return ActionItemResponse.from_model(item)


@router.get("", response_model=ActionItemListResponse)
async def list_action_items(
    db: DbSession,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
    status: list[ActionItemStatus] | None = Query(None),
    priority: list[ActionItemPriority] | None = Query(None),
    assigned_to: str | None = Query(None, description="User ID or 'me' for current user"),
    client_id: UUID | None = Query(None),
    due_before: date | None = Query(None),
    due_after: date | None = Query(None),
    include_completed: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ActionItemListResponse:
    """List action items with filters."""
    # Handle 'me' shortcut for assigned_to
    assigned_to_user_id = user_id if assigned_to == "me" else assigned_to

    service = ActionItemService(db)
    items, total = await service.list(
        tenant_id,
        status=status,
        priority=priority,
        assigned_to_user_id=assigned_to_user_id,
        client_id=client_id,
        due_before=due_before,
        due_after=due_after,
        include_completed=include_completed,
        limit=limit,
        offset=offset,
    )

    return ActionItemListResponse(
        items=[ActionItemResponse.from_model(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=ActionItemStats)
async def get_action_item_stats(
    db: DbSession,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
    assigned_to: str | None = Query(None, description="User ID or 'me' for current user"),
) -> ActionItemStats:
    """Get action item statistics for dashboard widget."""
    assigned_to_user_id = user_id if assigned_to == "me" else assigned_to

    service = ActionItemService(db)
    return await service.get_stats(tenant_id, assigned_to_user_id)


@router.get("/{item_id}", response_model=ActionItemResponse)
async def get_action_item(
    item_id: UUID,
    db: DbSession,
    tenant_id: TenantIdDep,
    _user_id: UserIdDep,
) -> ActionItemResponse:
    """Get a single action item."""
    service = ActionItemService(db)
    item = await service.get_by_id(tenant_id, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action item not found",
        )
    return ActionItemResponse.from_model(item)


@router.patch("/{item_id}", response_model=ActionItemResponse)
async def update_action_item(
    item_id: UUID,
    data: ActionItemUpdate,
    db: DbSession,
    tenant_id: TenantIdDep,
    _user_id: UserIdDep,
) -> ActionItemResponse:
    """Update an action item."""
    service = ActionItemService(db)
    item = await service.update(tenant_id, item_id, data)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action item not found",
        )
    return ActionItemResponse.from_model(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_action_item(
    item_id: UUID,
    db: DbSession,
    tenant_id: TenantIdDep,
    _user_id: UserIdDep,
) -> None:
    """Delete an action item."""
    service = ActionItemService(db)
    deleted = await service.delete(tenant_id, item_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action item not found",
        )


@router.post("/{item_id}/start", response_model=ActionItemResponse)
async def start_action_item(
    item_id: UUID,
    db: DbSession,
    tenant_id: TenantIdDep,
    _user_id: UserIdDep,
) -> ActionItemResponse:
    """Mark an action item as in progress."""
    service = ActionItemService(db)
    item = await service.start(tenant_id, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action item not found or cannot be started",
        )
    return ActionItemResponse.from_model(item)


@router.post("/{item_id}/complete", response_model=ActionItemResponse)
async def complete_action_item(
    item_id: UUID,
    db: DbSession,
    tenant_id: TenantIdDep,
    _user_id: UserIdDep,
    data: ActionItemComplete | None = None,
) -> ActionItemResponse:
    """Mark an action item as completed."""
    service = ActionItemService(db)
    resolution_notes = data.resolution_notes if data else None
    item = await service.complete(tenant_id, item_id, resolution_notes)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action item not found or cannot be completed",
        )
    return ActionItemResponse.from_model(item)


@router.post("/{item_id}/cancel", response_model=ActionItemResponse)
async def cancel_action_item(
    item_id: UUID,
    db: DbSession,
    tenant_id: TenantIdDep,
    _user_id: UserIdDep,
) -> ActionItemResponse:
    """Cancel an action item."""
    service = ActionItemService(db)
    item = await service.cancel(tenant_id, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action item not found or cannot be cancelled",
        )
    return ActionItemResponse.from_model(item)
