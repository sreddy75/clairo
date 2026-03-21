"""API routes for triggers."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_tenant_id
from app.database import get_db
from app.modules.triggers.schemas import (
    TriggerCreate,
    TriggerExecutionListResponse,
    TriggerListResponse,
    TriggerResponse,
    TriggerUpdate,
)
from app.modules.triggers.service import TriggerService

router = APIRouter(prefix="/api/v1/triggers", tags=["triggers"])


# Type aliases
DbSession = Annotated[AsyncSession, Depends(get_db)]
TenantIdDep = Annotated[UUID, Depends(get_current_tenant_id)]


async def get_trigger_service(db: DbSession) -> TriggerService:
    """Dependency to get trigger service."""
    return TriggerService(db)


TriggerServiceDep = Annotated[TriggerService, Depends(get_trigger_service)]


# ============================================================================
# Execution History Endpoints (MUST come before /{trigger_id} routes)
# ============================================================================


@router.get("/executions", response_model=TriggerExecutionListResponse)
async def list_executions(
    service: TriggerServiceDep,
    tenant_id: TenantIdDep,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> TriggerExecutionListResponse:
    """List recent trigger executions across all triggers."""
    return await service.get_executions(
        tenant_id=tenant_id,
        trigger_id=None,
        limit=limit,
        offset=offset,
    )


# ============================================================================
# Trigger CRUD Endpoints
# ============================================================================


@router.get("", response_model=TriggerListResponse)
async def list_triggers(
    service: TriggerServiceDep,
    tenant_id: TenantIdDep,
    trigger_type: str | None = Query(None, description="Filter by trigger type"),
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> TriggerListResponse:
    """List all triggers for the tenant."""
    return await service.list(
        tenant_id=tenant_id,
        trigger_type=trigger_type,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=TriggerResponse, status_code=status.HTTP_201_CREATED)
async def create_trigger(
    data: TriggerCreate,
    service: TriggerServiceDep,
    tenant_id: TenantIdDep,
    db: DbSession,
) -> TriggerResponse:
    """Create a new trigger."""
    trigger = await service.create(tenant_id, data)
    await db.commit()
    return await service._to_response(trigger)


@router.get("/{trigger_id}", response_model=TriggerResponse)
async def get_trigger(
    trigger_id: UUID,
    service: TriggerServiceDep,
    tenant_id: TenantIdDep,
) -> TriggerResponse:
    """Get a trigger by ID."""
    trigger = await service.get_by_id(tenant_id, trigger_id)
    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trigger not found",
        )
    return await service._to_response(trigger)


@router.patch("/{trigger_id}", response_model=TriggerResponse)
async def update_trigger(
    trigger_id: UUID,
    data: TriggerUpdate,
    service: TriggerServiceDep,
    tenant_id: TenantIdDep,
    db: DbSession,
) -> TriggerResponse:
    """Update a trigger."""
    trigger = await service.update(tenant_id, trigger_id, data)
    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trigger not found",
        )
    await db.commit()
    return await service._to_response(trigger)


@router.delete("/{trigger_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trigger(
    trigger_id: UUID,
    service: TriggerServiceDep,
    tenant_id: TenantIdDep,
    db: DbSession,
) -> None:
    """Delete a trigger."""
    # Check if it's a system default
    trigger = await service.get_by_id(tenant_id, trigger_id)
    if trigger and trigger.is_system_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete system default triggers. Disable instead.",
        )

    deleted = await service.delete(tenant_id, trigger_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trigger not found",
        )
    await db.commit()


# ============================================================================
# Trigger Action Endpoints
# ============================================================================


@router.post("/{trigger_id}/enable", response_model=TriggerResponse)
async def enable_trigger(
    trigger_id: UUID,
    service: TriggerServiceDep,
    tenant_id: TenantIdDep,
    db: DbSession,
) -> TriggerResponse:
    """Enable a trigger."""
    trigger = await service.enable(tenant_id, trigger_id)
    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trigger not found",
        )
    await db.commit()
    return await service._to_response(trigger)


@router.post("/{trigger_id}/disable", response_model=TriggerResponse)
async def disable_trigger(
    trigger_id: UUID,
    service: TriggerServiceDep,
    tenant_id: TenantIdDep,
    db: DbSession,
) -> TriggerResponse:
    """Disable a trigger."""
    trigger = await service.disable(tenant_id, trigger_id)
    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trigger not found",
        )
    await db.commit()
    return await service._to_response(trigger)


@router.get("/{trigger_id}/executions", response_model=TriggerExecutionListResponse)
async def list_trigger_executions(
    trigger_id: UUID,
    service: TriggerServiceDep,
    tenant_id: TenantIdDep,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> TriggerExecutionListResponse:
    """List executions for a specific trigger."""
    # Verify trigger exists
    trigger = await service.get_by_id(tenant_id, trigger_id)
    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trigger not found",
        )

    return await service.get_executions(
        tenant_id=tenant_id,
        trigger_id=trigger_id,
        limit=limit,
        offset=offset,
    )


# ============================================================================
# Admin Endpoints
# ============================================================================


@router.post("/seed-defaults", response_model=TriggerListResponse)
async def seed_default_triggers(
    service: TriggerServiceDep,
    tenant_id: TenantIdDep,
    db: DbSession,
) -> TriggerListResponse:
    """Seed default triggers for the current tenant.

    Creates the default trigger configuration if not already present.
    This is useful for:
    - New tenants that need initial triggers
    - Re-seeding after accidental deletion

    Only creates triggers that don't already exist (by name).
    """
    triggers = await service.seed_defaults(tenant_id)
    await db.commit()

    # Return the list of all triggers (including existing ones)
    return await service.list(tenant_id=tenant_id)
