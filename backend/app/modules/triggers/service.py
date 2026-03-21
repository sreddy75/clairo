"""Trigger service for managing triggers and executions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.triggers.models import Trigger, TriggerExecution, TriggerStatus
from app.modules.triggers.schemas import (
    TriggerCreate,
    TriggerExecutionListResponse,
    TriggerExecutionResponse,
    TriggerListResponse,
    TriggerResponse,
    TriggerUpdate,
)


class TriggerService:
    """Service for managing triggers and their executions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ========================================================================
    # Trigger CRUD
    # ========================================================================

    async def create(
        self,
        tenant_id: UUID,
        data: TriggerCreate,
    ) -> Trigger:
        """Create a new trigger."""
        trigger = Trigger(
            tenant_id=tenant_id,
            name=data.name,
            description=data.description,
            trigger_type=data.trigger_type,
            config=data.config,
            target_analyzers=data.target_analyzers,
            dedup_window_hours=data.dedup_window_hours,
            status=TriggerStatus.ACTIVE,
            is_system_default=False,
        )
        self.db.add(trigger)
        await self.db.flush()
        await self.db.refresh(trigger)
        return trigger

    async def get_by_id(
        self,
        tenant_id: UUID,
        trigger_id: UUID,
    ) -> Trigger | None:
        """Get a trigger by ID."""
        result = await self.db.execute(
            select(Trigger).where(Trigger.id == trigger_id).where(Trigger.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        tenant_id: UUID,
        trigger_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> TriggerListResponse:
        """List triggers with optional filtering."""
        query = select(Trigger).where(Trigger.tenant_id == tenant_id)

        if trigger_type:
            query = query.where(Trigger.trigger_type == trigger_type)
        if status:
            query = query.where(Trigger.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Get paginated results
        query = query.order_by(Trigger.created_at.desc())
        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        triggers = list(result.scalars().all())

        # Convert to response with stats
        items = []
        for trigger in triggers:
            response = await self._to_response(trigger)
            items.append(response)

        return TriggerListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )

    async def update(
        self,
        tenant_id: UUID,
        trigger_id: UUID,
        data: TriggerUpdate,
    ) -> Trigger | None:
        """Update a trigger."""
        trigger = await self.get_by_id(tenant_id, trigger_id)
        if not trigger:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(trigger, field, value)

        await self.db.flush()
        await self.db.refresh(trigger)
        return trigger

    async def delete(
        self,
        tenant_id: UUID,
        trigger_id: UUID,
    ) -> bool:
        """Delete a trigger."""
        trigger = await self.get_by_id(tenant_id, trigger_id)
        if not trigger:
            return False

        await self.db.delete(trigger)
        await self.db.flush()
        return True

    # ========================================================================
    # Trigger Actions
    # ========================================================================

    async def enable(
        self,
        tenant_id: UUID,
        trigger_id: UUID,
    ) -> Trigger | None:
        """Enable a trigger."""
        trigger = await self.get_by_id(tenant_id, trigger_id)
        if not trigger:
            return None

        trigger.status = TriggerStatus.ACTIVE
        trigger.consecutive_failures = 0
        trigger.last_error = None
        await self.db.flush()
        await self.db.refresh(trigger)
        return trigger

    async def disable(
        self,
        tenant_id: UUID,
        trigger_id: UUID,
    ) -> Trigger | None:
        """Disable a trigger."""
        trigger = await self.get_by_id(tenant_id, trigger_id)
        if not trigger:
            return None

        trigger.status = TriggerStatus.DISABLED
        await self.db.flush()
        await self.db.refresh(trigger)
        return trigger

    async def mark_executed(
        self,
        trigger: Trigger,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Update trigger after execution."""
        trigger.last_executed_at = datetime.now(UTC)

        if success:
            trigger.consecutive_failures = 0
            trigger.last_error = None
        else:
            trigger.consecutive_failures += 1
            trigger.last_error = error

            # Auto-disable after 3 consecutive failures
            if trigger.consecutive_failures >= 3:
                trigger.status = TriggerStatus.ERROR

        await self.db.flush()

    # ========================================================================
    # Trigger Executions
    # ========================================================================

    async def get_executions(
        self,
        tenant_id: UUID,
        trigger_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> TriggerExecutionListResponse:
        """Get trigger execution history."""
        query = select(TriggerExecution).where(TriggerExecution.tenant_id == tenant_id)

        if trigger_id:
            query = query.where(TriggerExecution.trigger_id == trigger_id)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Get paginated results
        query = query.order_by(TriggerExecution.started_at.desc())
        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        executions = list(result.scalars().all())

        # Convert to response
        items = []
        for execution in executions:
            # Get trigger name
            trigger = await self.get_by_id(tenant_id, execution.trigger_id)
            items.append(
                TriggerExecutionResponse(
                    id=execution.id,
                    trigger_id=execution.trigger_id,
                    tenant_id=execution.tenant_id,
                    started_at=execution.started_at,
                    completed_at=execution.completed_at,
                    duration_ms=execution.duration_ms,
                    status=execution.status,
                    clients_evaluated=execution.clients_evaluated,
                    insights_created=execution.insights_created,
                    insights_deduplicated=execution.insights_deduplicated,
                    error_message=execution.error_message,
                    trigger_name=trigger.name if trigger else None,
                )
            )

        return TriggerExecutionListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )

    async def create_execution(
        self,
        trigger: Trigger,
        tenant_id: UUID,
    ) -> TriggerExecution:
        """Create a new trigger execution record."""
        execution = TriggerExecution(
            trigger_id=trigger.id,
            tenant_id=tenant_id,
            status="running",
        )
        self.db.add(execution)
        await self.db.flush()
        await self.db.refresh(execution)
        return execution

    async def complete_execution(
        self,
        execution: TriggerExecution,
        success: bool,
        clients_evaluated: int,
        insights_created: int,
        insights_deduplicated: int,
        client_ids: list[str],
        error_message: str | None = None,
        error_details: dict | None = None,
    ) -> None:
        """Complete a trigger execution."""
        execution.completed_at = datetime.now(UTC)
        execution.status = "success" if success else "failed"
        execution.clients_evaluated = clients_evaluated
        execution.insights_created = insights_created
        execution.insights_deduplicated = insights_deduplicated
        execution.client_ids = client_ids
        execution.error_message = error_message
        execution.error_details = error_details

        if execution.started_at:
            duration = datetime.now(UTC) - execution.started_at
            execution.duration_ms = int(duration.total_seconds() * 1000)

        await self.db.flush()

    # ========================================================================
    # Query Methods
    # ========================================================================

    async def get_active_triggers_by_type(
        self,
        tenant_id: UUID,
        trigger_type: str,
    ) -> list[Trigger]:
        """Get all active triggers of a specific type."""
        result = await self.db.execute(
            select(Trigger)
            .where(Trigger.tenant_id == tenant_id)
            .where(Trigger.trigger_type == trigger_type)
            .where(Trigger.status == TriggerStatus.ACTIVE)
        )
        return list(result.scalars().all())

    async def get_all_active_triggers(
        self,
        tenant_id: UUID,
    ) -> list[Trigger]:
        """Get all active triggers for a tenant."""
        result = await self.db.execute(
            select(Trigger)
            .where(Trigger.tenant_id == tenant_id)
            .where(Trigger.status == TriggerStatus.ACTIVE)
        )
        return list(result.scalars().all())

    # ========================================================================
    # Helpers
    # ========================================================================

    # ========================================================================
    # Seeding
    # ========================================================================

    async def seed_defaults(self, tenant_id: UUID) -> list[Trigger]:
        """Seed default triggers for a new tenant.

        Creates all default triggers from the defaults.py configuration.
        Skips any triggers that already exist (by name).

        Args:
            tenant_id: The tenant to seed triggers for.

        Returns:
            List of created triggers.
        """
        from app.modules.triggers.defaults import DEFAULT_TRIGGERS

        created_triggers = []

        for trigger_config in DEFAULT_TRIGGERS:
            # Check if trigger with same name already exists
            existing = await self.db.execute(
                select(Trigger)
                .where(Trigger.tenant_id == tenant_id)
                .where(Trigger.name == trigger_config["name"])
            )
            if existing.scalar_one_or_none():
                continue

            trigger = Trigger(
                tenant_id=tenant_id,
                name=trigger_config["name"],
                description=trigger_config.get("description"),
                trigger_type=trigger_config["trigger_type"],
                config=trigger_config["config"],
                target_analyzers=trigger_config["target_analyzers"],
                dedup_window_hours=trigger_config.get("dedup_window_hours", 168),
                status=TriggerStatus.ACTIVE,
                is_system_default=True,
            )
            self.db.add(trigger)
            created_triggers.append(trigger)

        await self.db.flush()

        for trigger in created_triggers:
            await self.db.refresh(trigger)

        return created_triggers

    # ========================================================================
    # Helpers
    # ========================================================================

    async def _to_response(self, trigger: Trigger) -> TriggerResponse:
        """Convert trigger to response with stats."""
        # Get execution stats for last 24 hours
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        stats_query = select(
            func.count(TriggerExecution.id).label("executions"),
            func.sum(TriggerExecution.insights_created).label("insights"),
        ).where(
            TriggerExecution.trigger_id == trigger.id,
            TriggerExecution.started_at > cutoff,
        )
        stats_result = await self.db.execute(stats_query)
        stats = stats_result.one()

        return TriggerResponse(
            id=trigger.id,
            tenant_id=trigger.tenant_id,
            name=trigger.name,
            description=trigger.description,
            trigger_type=trigger.trigger_type,
            config=trigger.config,
            target_analyzers=trigger.target_analyzers,
            dedup_window_hours=trigger.dedup_window_hours,
            status=trigger.status,
            is_system_default=trigger.is_system_default,
            last_executed_at=trigger.last_executed_at,
            last_error=trigger.last_error,
            consecutive_failures=trigger.consecutive_failures,
            created_at=trigger.created_at,
            updated_at=trigger.updated_at,
            executions_24h=stats.executions or 0,
            insights_24h=int(stats.insights or 0),
        )
