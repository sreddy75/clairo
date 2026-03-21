"""Celery tasks for proactive insight generation.

Generates insights after Xero sync and on a scheduled basis.
Insights surface issues that need attention without the user asking.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from celery import Task
from sqlalchemy import select, text, update
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
    name="app.tasks.insights.generate_for_connection",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def generate_insights_for_connection(
    self: Task,
    connection_id: str,
    tenant_id: str,
    trigger_reason: str = "post_sync",
    post_sync_task_id: str | None = None,
) -> dict[str, Any]:
    """Generate insights for a single client after sync.

    This task is triggered after Xero sync and aggregation complete.
    It runs all analyzers for the client and saves new insights.

    Args:
        connection_id: Xero connection ID.
        tenant_id: Tenant ID for RLS context.
        trigger_reason: What triggered generation (post_sync, manual).
        post_sync_task_id: Optional PostSyncTask ID for status tracking (Spec 043).

    Returns:
        Dict with insight generation statistics.
    """
    import asyncio

    return asyncio.run(
        _generate_for_connection_async(
            UUID(connection_id),
            UUID(tenant_id),
            trigger_reason,
            post_sync_task_id,
        )
    )


def _create_pinecone_and_voyage() -> tuple:
    """Create PineconeService and VoyageService for Celery tasks.

    Returns:
        Tuple of (PineconeService, VoyageService). Either may be None
        if configuration is missing.
    """
    try:
        from app.core.pinecone_service import PineconeService
        from app.core.voyage import VoyageService

        settings = get_settings()
        pinecone = PineconeService(settings.pinecone)
        voyage = VoyageService(settings.voyage)
        return pinecone, voyage
    except Exception as e:
        logger.warning(f"Could not initialize Pinecone/Voyage for dedup: {e}")
        return None, None


async def _generate_for_connection_async(
    connection_id: UUID,
    tenant_id: UUID,
    trigger_reason: str,
    post_sync_task_id: str | None = None,
) -> dict[str, Any]:
    """Async implementation of insight generation for a connection."""
    from app.modules.insights.generator import InsightGenerator

    # Track post-sync task status (Spec 043 — T036)
    if post_sync_task_id:
        from app.tasks.xero import _update_post_sync_task_status

        await _update_post_sync_task_status(post_sync_task_id, "in_progress")

    session = await _get_async_session()
    pinecone, voyage = _create_pinecone_and_voyage()

    try:
        await _set_tenant_context(session, tenant_id)

        logger.info(
            f"Generating insights for connection {connection_id} (trigger: {trigger_reason})"
        )

        generator = InsightGenerator(session, pinecone=pinecone, voyage=voyage)
        insights = await generator.generate_for_client(
            tenant_id=tenant_id,
            client_id=connection_id,
            source=trigger_reason,
        )

        await session.commit()

        logger.info(f"Generated {len(insights)} insights for connection {connection_id}")

        task_result = {
            "connection_id": str(connection_id),
            "tenant_id": str(tenant_id),
            "trigger_reason": trigger_reason,
            "status": "completed",
            "insights_generated": len(insights),
            "insight_ids": [str(i.id) for i in insights],
        }

        # Mark post-sync task as completed (Spec 043 — T036)
        if post_sync_task_id:
            from app.tasks.xero import _update_post_sync_task_status

            await _update_post_sync_task_status(
                post_sync_task_id,
                "completed",
                result_summary={
                    "insights_generated": len(insights),
                },
            )

        return task_result

    except Exception as e:
        logger.error(f"Insight generation failed for connection {connection_id}: {e}")
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
    name="app.tasks.insights.generate_for_all_tenants",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def generate_insights_for_all_tenants(self: Task) -> dict[str, Any]:
    """Generate insights for all tenants.

    This task runs on a schedule (daily) to ensure all clients
    have fresh insights even if their sync hasn't triggered recently.

    Returns:
        Dict with generation statistics.
    """
    import asyncio

    return asyncio.run(_generate_for_all_tenants_async())


async def _generate_for_all_tenants_async() -> dict[str, Any]:
    """Async implementation of insight generation for all tenants."""
    from app.modules.auth.models import Tenant
    from app.modules.insights.generator import InsightGenerator

    session = await _get_async_session()
    pinecone, voyage = _create_pinecone_and_voyage()

    try:
        # Get all active tenants
        result = await session.execute(select(Tenant).where(Tenant.subscription_status == "active"))
        tenants = list(result.scalars().all())

        logger.info(f"Generating insights for {len(tenants)} tenants")

        total_insights = 0
        tenant_results = []

        for tenant in tenants:
            try:
                await _set_tenant_context(session, tenant.id)

                generator = InsightGenerator(session, pinecone=pinecone, voyage=voyage)
                insights = await generator.generate_for_tenant(
                    tenant_id=tenant.id,
                    source="scheduled",
                )

                await session.commit()

                total_insights += len(insights)
                tenant_results.append(
                    {
                        "tenant_id": str(tenant.id),
                        "insights_generated": len(insights),
                        "status": "completed",
                    }
                )

                logger.info(f"Generated {len(insights)} insights for tenant {tenant.id}")

            except Exception as e:
                logger.error(f"Failed to generate insights for tenant {tenant.id}: {e}")
                await session.rollback()
                tenant_results.append(
                    {
                        "tenant_id": str(tenant.id),
                        "status": "failed",
                        "error_message": str(e),
                    }
                )

        return {
            "status": "completed",
            "total_tenants": len(tenants),
            "total_insights": total_insights,
            "generated_at": datetime.now(UTC).isoformat(),
            "tenant_results": tenant_results,
        }

    except Exception as e:
        logger.error(f"Failed to generate insights for all tenants: {e}")
        return {
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await session.close()


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.insights.cleanup_expired",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def cleanup_expired_insights(self: Task) -> dict[str, Any]:
    """Mark expired insights as expired.

    This task runs on a schedule (daily) to update the status
    of insights that have passed their expiry date.

    Returns:
        Dict with cleanup statistics.
    """
    import asyncio

    return asyncio.run(_cleanup_expired_async())


async def _cleanup_expired_async() -> dict[str, Any]:
    """Async implementation of expired insight cleanup."""
    from app.modules.insights.models import Insight, InsightStatus

    session = await _get_async_session()
    pinecone, voyage = _create_pinecone_and_voyage()

    try:
        now = datetime.now(UTC)

        # Update all expired insights
        result = await session.execute(
            update(Insight)
            .where(
                Insight.expires_at.is_not(None),
                Insight.expires_at < now,
                Insight.status.notin_([InsightStatus.EXPIRED.value, InsightStatus.RESOLVED.value]),
            )
            .values(status=InsightStatus.EXPIRED.value, updated_at=now)
            .returning(Insight.id)
        )

        expired_rows = result.fetchall()
        expired_ids = [str(row[0]) for row in expired_rows]
        await session.commit()

        logger.info(f"Marked {len(expired_ids)} insights as expired")

        # Batch-delete dedup vectors for expired insights
        if expired_ids and pinecone and voyage:
            try:
                from app.modules.insights.dedup import InsightDedupService

                dedup = InsightDedupService(pinecone, voyage, session)
                await dedup.remove_insights_batch([UUID(eid) for eid in expired_ids])
            except Exception as e:
                logger.warning(f"Failed to remove dedup vectors for expired insights: {e}")

        return {
            "status": "completed",
            "expired_count": len(expired_ids),
            "expired_ids": expired_ids,
            "cleaned_at": now.isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to cleanup expired insights: {e}")
        await session.rollback()
        return {
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await session.close()
