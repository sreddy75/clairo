"""Celery tasks for client AI context aggregation.

Computes financial summaries from synced Xero data for use in
AI chat context injection.

Triggered automatically after Xero sync completes.
"""

import logging
from typing import Any
from uuid import UUID

from celery import Task
from sqlalchemy import text
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


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.aggregation.compute_aggregations",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def compute_aggregations(
    self: Task,
    connection_id: str,
    tenant_id: str,
    trigger_reason: str = "sync",
    post_sync_task_id: str | None = None,
) -> dict[str, Any]:
    """Compute client AI context aggregations for a connection.

    This task is triggered after Xero sync completes. It computes
    financial summaries for all clients associated with the connection.

    Computed aggregations:
    - Client AI profiles (entity type, revenue bracket, GST status)
    - Expense summaries (by account code, by category)
    - AR/AP aging buckets (current, 31-60, 61-90, 90+ days)
    - GST summaries (sales, purchases, net GST)
    - Monthly trends (revenue, expenses, cashflow)
    - Compliance summaries (wages, PAYG, super)

    Args:
        connection_id: Xero connection ID.
        tenant_id: Tenant ID for RLS context.
        trigger_reason: What triggered the aggregation (sync, manual).
        post_sync_task_id: Optional PostSyncTask ID for status tracking (Spec 043).

    Returns:
        Dict with aggregation counts by type.
    """
    import asyncio

    return asyncio.run(
        _compute_aggregations_async(
            self,
            UUID(connection_id),
            UUID(tenant_id),
            trigger_reason,
            post_sync_task_id,
        )
    )


async def _compute_aggregations_async(
    task: Task,
    connection_id: UUID,
    tenant_id: UUID,
    trigger_reason: str,
    post_sync_task_id: str | None = None,
) -> dict[str, Any]:
    """Async implementation of aggregation computation."""
    from app.modules.knowledge.aggregation_service import AggregationService

    # Track post-sync task status (Spec 043 — T036)
    if post_sync_task_id:
        from app.tasks.xero import _update_post_sync_task_status

        await _update_post_sync_task_status(post_sync_task_id, "in_progress")

    session = await _get_async_session()

    try:
        await _set_tenant_context(session, tenant_id)

        logger.info(
            f"Starting aggregation computation for connection {connection_id} "
            f"(trigger: {trigger_reason})"
        )

        service = AggregationService(session)
        stats = await service.compute_all_for_connection(connection_id, tenant_id)

        await session.commit()

        logger.info(f"Aggregation computation completed for connection {connection_id}: {stats}")

        # Trigger insight generation after successful aggregation (Spec 016)
        try:
            from app.tasks.insights import generate_insights_for_connection

            generate_insights_for_connection.delay(
                connection_id=str(connection_id),
                tenant_id=str(tenant_id),
                trigger_reason="post_sync",
            )
            logger.info(f"Insight generation triggered for connection {connection_id}")
        except Exception as e:
            logger.warning(f"Failed to trigger insight generation: {e}")

        task_result = {
            "connection_id": str(connection_id),
            "tenant_id": str(tenant_id),
            "trigger_reason": trigger_reason,
            "status": "completed",
            **stats,
        }

        # Mark post-sync task as completed (Spec 043 — T036)
        if post_sync_task_id:
            from app.tasks.xero import _update_post_sync_task_status

            await _update_post_sync_task_status(
                post_sync_task_id,
                "completed",
                result_summary=stats,
            )

        return task_result

    except Exception as e:
        logger.error(f"Aggregation computation failed for connection {connection_id}: {e}")
        await session.rollback()
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


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.aggregation.compute_single_client",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def compute_single_client_aggregations(
    self: Task,
    client_id: str,
    tenant_id: str,
    connection_id: str,
) -> dict[str, Any]:
    """Compute aggregations for a single client.

    Use this for on-demand refresh of a specific client's context.

    Args:
        client_id: Xero client ID.
        tenant_id: Tenant ID for RLS context.
        connection_id: Xero connection ID.

    Returns:
        Dict with aggregation counts.
    """
    import asyncio

    return asyncio.run(
        _compute_single_client_async(
            self,
            UUID(client_id),
            UUID(tenant_id),
            UUID(connection_id),
        )
    )


async def _compute_single_client_async(
    task: Task,
    client_id: UUID,
    tenant_id: UUID,
    connection_id: UUID,
) -> dict[str, Any]:
    """Async implementation of single client aggregation."""
    from collections import defaultdict

    from app.modules.knowledge.aggregation_service import AggregationService

    session = await _get_async_session()

    try:
        await _set_tenant_context(session, tenant_id)

        logger.info(f"Computing aggregations for client {client_id}")

        service = AggregationService(session)
        stats: dict[str, int] = defaultdict(int)

        await service._compute_client_aggregations(
            tenant_id=tenant_id,
            client_id=client_id,
            connection_id=connection_id,
            stats=stats,
        )

        await session.commit()

        logger.info(f"Aggregation completed for client {client_id}: {dict(stats)}")

        return {
            "client_id": str(client_id),
            "status": "completed",
            **dict(stats),
        }

    except Exception as e:
        logger.error(f"Aggregation failed for client {client_id}: {e}")
        await session.rollback()
        return {
            "client_id": str(client_id),
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await session.close()
