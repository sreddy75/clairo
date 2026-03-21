"""Celery tasks for trigger execution.

Provides background tasks for:
- Evaluating data triggers after Xero sync
- Running time-scheduled triggers via Celery Beat
- Handling business events (BAS lodged, etc.)

All triggers respect the three-layer deduplication strategy:
- Layer 3: Trigger-level throttle (per-trigger, configurable window)
- Layer 1: Cross-trigger dedup (24-hour window, same category)
- Layer 2: InsightGenerator dedup (7-day content-based)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from celery import Task
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _get_async_session() -> AsyncSession:
    """Create an async database session for tasks.

    Uses NullPool to avoid connection leaks in Celery's asyncio.run() context.
    """
    settings = get_settings()
    engine = create_async_engine(settings.database.url, echo=False, poolclass=NullPool)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return async_session()


async def _set_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    """Set the tenant context for RLS policies.

    Uses session-scoped SET (not SET LOCAL) so tenant context persists
    across multiple commits within the same Celery task.
    """
    await session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))


# =============================================================================
# Data Trigger Tasks
# =============================================================================


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.triggers.evaluate_data_triggers",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def evaluate_data_triggers(
    self: Task,
    connection_id: str,
    tenant_id: str,
    post_sync_task_id: str | None = None,
) -> dict[str, Any]:
    """Evaluate data threshold triggers for a client after sync.

    This task is triggered after Xero sync completes.
    It checks all active data triggers and executes any that match.

    Args:
        connection_id: Xero connection ID (client ID).
        tenant_id: Tenant ID for RLS context.
        post_sync_task_id: Optional PostSyncTask ID for status tracking (Spec 043).

    Returns:
        Dict with trigger evaluation results.
    """
    import asyncio

    return asyncio.run(
        _evaluate_data_triggers_async(
            UUID(connection_id),
            UUID(tenant_id),
            post_sync_task_id,
        )
    )


async def _evaluate_data_triggers_async(
    connection_id: UUID,
    tenant_id: UUID,
    post_sync_task_id: str | None = None,
) -> dict[str, Any]:
    """Async implementation of data trigger evaluation."""
    from app.modules.triggers.executor import TriggerExecutor
    from app.modules.triggers.models import TriggerType
    from app.modules.triggers.service import TriggerService

    # Track post-sync task status (Spec 043 — T036)
    if post_sync_task_id:
        from app.tasks.xero import _update_post_sync_task_status

        await _update_post_sync_task_status(post_sync_task_id, "in_progress")

    session = await _get_async_session()

    try:
        await _set_tenant_context(session, tenant_id)

        logger.info(
            f"Evaluating data triggers for connection {connection_id} (tenant: {tenant_id})"
        )

        # Get all active data threshold triggers
        service = TriggerService(session)
        triggers = await service.get_active_triggers_by_type(
            tenant_id, TriggerType.DATA_THRESHOLD.value
        )

        if not triggers:
            logger.info(f"No active data triggers found for tenant {tenant_id}")
            task_result = {
                "connection_id": str(connection_id),
                "tenant_id": str(tenant_id),
                "status": "skipped",
                "reason": "no_active_triggers",
            }
            # Mark post-sync task as completed even if skipped (Spec 043 — T036)
            if post_sync_task_id:
                from app.tasks.xero import _update_post_sync_task_status

                await _update_post_sync_task_status(
                    post_sync_task_id,
                    "completed",
                    result_summary={"triggers_evaluated": 0, "reason": "no_active_triggers"},
                )
            return task_result

        # Execute each trigger for this client
        executor = TriggerExecutor(session)
        results = []
        total_insights = 0

        for trigger in triggers:
            try:
                result = await executor.execute(
                    trigger=trigger,
                    tenant_id=tenant_id,
                    client_ids=[connection_id],
                )
                await session.commit()

                results.append(
                    {
                        "trigger_id": str(trigger.id),
                        "trigger_name": trigger.name,
                        "success": result.success,
                        "insights_created": result.insights_created,
                        "insights_deduplicated": result.insights_deduplicated,
                    }
                )
                total_insights += result.insights_created

            except Exception as e:
                logger.error(
                    f"Failed to execute trigger {trigger.id} for client {connection_id}: {e}"
                )
                await session.rollback()
                results.append(
                    {
                        "trigger_id": str(trigger.id),
                        "trigger_name": trigger.name,
                        "success": False,
                        "error": str(e),
                    }
                )

        logger.info(
            f"Data trigger evaluation complete for {connection_id}: "
            f"{len(triggers)} triggers, {total_insights} insights created"
        )

        task_result = {
            "connection_id": str(connection_id),
            "tenant_id": str(tenant_id),
            "status": "completed",
            "triggers_evaluated": len(triggers),
            "total_insights_created": total_insights,
            "results": results,
        }

        # Mark post-sync task as completed (Spec 043 — T036)
        if post_sync_task_id:
            from app.tasks.xero import _update_post_sync_task_status

            await _update_post_sync_task_status(
                post_sync_task_id,
                "completed",
                result_summary={
                    "triggers_evaluated": len(triggers),
                    "total_insights_created": total_insights,
                },
            )

        return task_result

    except Exception as e:
        logger.error(f"Data trigger evaluation failed for connection {connection_id}: {e}")
        # Mark post-sync task as failed (Spec 043 — T036)
        if post_sync_task_id:
            from app.tasks.xero import _update_post_sync_task_status

            await _update_post_sync_task_status(
                post_sync_task_id,
                "failed",
                error_message=str(e),
            )
        return {
            "connection_id": str(connection_id),
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await session.close()


# =============================================================================
# Time-Scheduled Trigger Tasks
# =============================================================================


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.triggers.run_time_triggers",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def run_time_triggers(self: Task) -> dict[str, Any]:
    """Run all time-scheduled triggers across all tenants.

    This task runs on a schedule (via Celery Beat) and:
    1. Finds all active time-scheduled triggers
    2. Checks if each should fire based on cron expression
    3. Executes matching triggers

    Returns:
        Dict with execution statistics.
    """
    import asyncio

    return asyncio.run(_run_time_triggers_async())


async def _run_time_triggers_async() -> dict[str, Any]:
    """Async implementation of time trigger execution."""
    from app.modules.auth.models import Tenant
    from app.modules.triggers.evaluators.time_triggers import TimeScheduleEvaluator
    from app.modules.triggers.executor import TriggerExecutor
    from app.modules.triggers.models import Trigger, TriggerStatus, TriggerType

    session = await _get_async_session()

    try:
        # Get all active tenants
        result = await session.execute(select(Tenant).where(Tenant.subscription_status == "active"))
        tenants = list(result.scalars().all())

        logger.info(f"Running time triggers for {len(tenants)} tenants")

        total_triggers_fired = 0
        total_insights = 0
        tenant_results = []

        for tenant in tenants:
            try:
                await _set_tenant_context(session, tenant.id)

                # Get all active time-scheduled triggers for this tenant
                result = await session.execute(
                    select(Trigger)
                    .where(Trigger.tenant_id == tenant.id)
                    .where(Trigger.trigger_type == TriggerType.TIME_SCHEDULED)
                    .where(Trigger.status == TriggerStatus.ACTIVE)
                )
                triggers = list(result.scalars().all())

                if not triggers:
                    continue

                time_evaluator = TimeScheduleEvaluator(session)
                executor = TriggerExecutor(session)

                triggers_fired = 0
                insights_created = 0

                for trigger in triggers:
                    # Check if this trigger should fire now
                    if not await time_evaluator.should_fire(trigger):
                        continue

                    try:
                        result = await executor.execute(
                            trigger=trigger,
                            tenant_id=tenant.id,
                        )
                        await session.commit()

                        if result.success:
                            triggers_fired += 1
                            insights_created += result.insights_created

                    except Exception as e:
                        logger.error(
                            f"Failed to execute time trigger {trigger.id} "
                            f"for tenant {tenant.id}: {e}"
                        )
                        await session.rollback()

                if triggers_fired > 0:
                    total_triggers_fired += triggers_fired
                    total_insights += insights_created
                    tenant_results.append(
                        {
                            "tenant_id": str(tenant.id),
                            "triggers_fired": triggers_fired,
                            "insights_created": insights_created,
                        }
                    )

            except Exception as e:
                logger.error(f"Failed to process time triggers for tenant {tenant.id}: {e}")
                await session.rollback()

        logger.info(
            f"Time triggers complete: {total_triggers_fired} triggers fired, "
            f"{total_insights} insights created"
        )

        return {
            "status": "completed",
            "total_tenants": len(tenants),
            "triggers_fired": total_triggers_fired,
            "insights_created": total_insights,
            "executed_at": datetime.now(UTC).isoformat(),
            "tenant_results": tenant_results,
        }

    except Exception as e:
        logger.error(f"Failed to run time triggers: {e}")
        return {
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await session.close()


# =============================================================================
# Event-Based Trigger Tasks
# =============================================================================


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.triggers.handle_business_event",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def handle_business_event(
    self: Task,
    event_type: str,
    tenant_id: str,
    client_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Handle a business event and fire matching triggers.

    Supported events:
    - xero_connection_created: New Xero connection established
    - xero_sync_complete: Xero data sync completed
    - bas_lodged: BAS was lodged/recorded
    - action_item_due_soon: Action item approaching deadline

    Args:
        event_type: Type of event that occurred.
        tenant_id: Tenant ID for RLS context.
        client_id: Optional client (connection) ID related to the event.
        payload: Optional event-specific payload data.

    Returns:
        Dict with trigger execution results.
    """
    import asyncio

    return asyncio.run(
        _handle_business_event_async(
            event_type=event_type,
            tenant_id=UUID(tenant_id),
            client_id=UUID(client_id) if client_id else None,
            payload=payload or {},
        )
    )


async def _handle_business_event_async(
    event_type: str,
    tenant_id: UUID,
    client_id: UUID | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Async implementation of business event handling."""
    from app.modules.triggers.evaluators.event_triggers import EventTriggerEvaluator
    from app.modules.triggers.executor import TriggerExecutor

    session = await _get_async_session()

    try:
        await _set_tenant_context(session, tenant_id)

        logger.info(
            f"Handling business event '{event_type}' for tenant {tenant_id} (client: {client_id})"
        )

        # Get triggers that match this event
        event_evaluator = EventTriggerEvaluator(session)
        matching_triggers = await event_evaluator.get_triggers_for_event(tenant_id, event_type)

        if not matching_triggers:
            logger.info(f"No triggers registered for event '{event_type}'")
            return {
                "event_type": event_type,
                "tenant_id": str(tenant_id),
                "status": "no_matching_triggers",
            }

        # Execute each matching trigger
        executor = TriggerExecutor(session)
        results = []
        total_insights = 0

        for trigger in matching_triggers:
            # Verify the trigger should fire (check conditions)
            should_fire = await event_evaluator.should_fire(
                trigger,
                client_id=client_id,
                event_type=event_type,
                payload=payload,
            )

            if not should_fire:
                continue

            try:
                # Determine client IDs - use provided client_id or get from payload
                client_ids = None
                if client_id:
                    client_ids = [client_id]
                elif "client_id" in payload:
                    client_ids = [UUID(payload["client_id"])]

                result = await executor.execute(
                    trigger=trigger,
                    tenant_id=tenant_id,
                    client_ids=client_ids,
                )
                await session.commit()

                results.append(
                    {
                        "trigger_id": str(trigger.id),
                        "trigger_name": trigger.name,
                        "success": result.success,
                        "insights_created": result.insights_created,
                    }
                )
                total_insights += result.insights_created

            except Exception as e:
                logger.error(f"Failed to execute event trigger {trigger.id}: {e}")
                await session.rollback()
                results.append(
                    {
                        "trigger_id": str(trigger.id),
                        "trigger_name": trigger.name,
                        "success": False,
                        "error": str(e),
                    }
                )

        logger.info(
            f"Event '{event_type}' handling complete: "
            f"{len(results)} triggers executed, {total_insights} insights created"
        )

        return {
            "event_type": event_type,
            "tenant_id": str(tenant_id),
            "client_id": str(client_id) if client_id else None,
            "status": "completed",
            "triggers_executed": len(results),
            "insights_created": total_insights,
            "results": results,
        }

    except Exception as e:
        logger.error(f"Failed to handle business event '{event_type}': {e}")
        return {
            "event_type": event_type,
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await session.close()


# =============================================================================
# Manual Trigger Execution Task
# =============================================================================


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.triggers.execute_trigger",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def execute_trigger(
    self: Task,
    trigger_id: str,
    tenant_id: str,
    client_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Execute a specific trigger manually.

    This task allows manual execution of any trigger, useful for:
    - Testing trigger configurations
    - Re-running failed triggers
    - Forcing insight generation

    Args:
        trigger_id: The trigger to execute.
        tenant_id: Tenant ID for RLS context.
        client_ids: Optional list of specific clients to evaluate.

    Returns:
        Dict with execution results.
    """
    import asyncio

    return asyncio.run(
        _execute_trigger_async(
            trigger_id=UUID(trigger_id),
            tenant_id=UUID(tenant_id),
            client_ids=[UUID(cid) for cid in client_ids] if client_ids else None,
        )
    )


async def _execute_trigger_async(
    trigger_id: UUID,
    tenant_id: UUID,
    client_ids: list[UUID] | None,
) -> dict[str, Any]:
    """Async implementation of manual trigger execution."""
    from app.modules.triggers.executor import TriggerExecutor
    from app.modules.triggers.service import TriggerService

    session = await _get_async_session()

    try:
        await _set_tenant_context(session, tenant_id)

        # Get the trigger
        service = TriggerService(session)
        trigger = await service.get_by_id(tenant_id, trigger_id)

        if not trigger:
            return {
                "trigger_id": str(trigger_id),
                "status": "failed",
                "error_message": "Trigger not found",
            }

        logger.info(
            f"Manually executing trigger {trigger_id} ({trigger.name}) for tenant {tenant_id}"
        )

        # Execute the trigger
        executor = TriggerExecutor(session)
        result = await executor.execute(
            trigger=trigger,
            tenant_id=tenant_id,
            client_ids=client_ids,
        )
        await session.commit()

        return {
            "trigger_id": str(trigger_id),
            "trigger_name": trigger.name,
            "status": "completed" if result.success else "failed",
            "clients_evaluated": result.clients_evaluated,
            "insights_created": result.insights_created,
            "insights_deduplicated": result.insights_deduplicated,
            "error_message": result.error_message,
        }

    except Exception as e:
        logger.error(f"Failed to execute trigger {trigger_id}: {e}")
        return {
            "trigger_id": str(trigger_id),
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await session.close()
