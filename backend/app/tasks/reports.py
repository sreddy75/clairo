"""Celery tasks for Xero Reports API synchronization.

Provides background tasks for:
- Syncing all report types for a connection
- Nightly batch sync of reports for all active connections

All tasks use automatic retry with exponential backoff.

Spec 023: Xero Reports API Integration
"""

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
from app.modules.integrations.xero.exceptions import XeroRateLimitExceededError
from app.modules.integrations.xero.models import XeroConnection, XeroReportSyncJob
from app.modules.integrations.xero.service import XeroReportService
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Report sync task configuration
REPORT_SYNC_TASK_CONFIG = {
    "bind": True,
    "max_retries": 3,
    "default_retry_delay": 60,
    "autoretry_for": (XeroRateLimitExceededError, ConnectionError, TimeoutError),
    "retry_backoff": True,
    "retry_backoff_max": 600,
    "retry_jitter": True,
}


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
    name="app.tasks.reports.sync_reports_for_connection",
    **REPORT_SYNC_TASK_CONFIG,
)
def sync_reports_for_connection(
    self: Task,
    connection_id: str,
    tenant_id: str,
    report_types: list[str] | None = None,
    triggered_by: str = "scheduled",
) -> dict[str, Any]:
    """Sync all report types for a single Xero connection.

    This task syncs all 7 report types from Xero Reports API:
    - Profit & Loss
    - Balance Sheet
    - Aged Receivables
    - Aged Payables
    - Trial Balance
    - Bank Summary
    - Budget Summary (if available)

    Args:
        connection_id: Xero connection ID.
        tenant_id: Tenant ID for RLS context.
        report_types: Optional list of specific report types to sync.
        triggered_by: Who/what triggered this sync.

    Returns:
        Dict with sync results including reports_synced and reports_failed.
    """
    import asyncio

    return asyncio.run(
        _sync_reports_for_connection_async(
            self,
            UUID(connection_id),
            UUID(tenant_id),
            report_types,
            triggered_by,
        )
    )


async def _sync_reports_for_connection_async(
    task: Task,
    connection_id: UUID,
    tenant_id: UUID,
    report_types: list[str] | None,
    triggered_by: str,
) -> dict[str, Any]:
    """Async implementation of report sync."""
    settings = get_settings()
    session = await _get_async_session()

    try:
        await _set_tenant_context(session, tenant_id)

        # Create sync job record
        sync_job = XeroReportSyncJob(
            tenant_id=tenant_id,
            connection_id=connection_id,
            report_type="all" if not report_types else ",".join(report_types),
            status="in_progress",
            triggered_by=triggered_by,
            started_at=datetime.now(UTC),
        )
        session.add(sync_job)
        await session.commit()
        await session.refresh(sync_job)

        # Perform report sync
        report_service = XeroReportService(session, settings)
        result = await report_service.sync_all_reports(
            connection_id=connection_id,
            report_types=report_types,
        )

        # Update sync job with results
        sync_job.status = "completed" if result["reports_failed"] == 0 else "partial"
        sync_job.completed_at = datetime.now(UTC)
        sync_job.duration_ms = int(
            (sync_job.completed_at - sync_job.started_at).total_seconds() * 1000
        )
        sync_job.rows_fetched = result["reports_synced"]
        if result["errors"]:
            sync_job.error_message = "; ".join(
                f"{e['report_type']}: {e['error']}" for e in result["errors"]
            )

        await session.commit()

        logger.info(
            f"Report sync completed for connection {connection_id}: "
            f"{result['reports_synced']} synced, {result['reports_failed']} failed"
        )

        return {
            "job_id": str(sync_job.id),
            "connection_id": str(connection_id),
            "status": sync_job.status,
            "reports_synced": result["reports_synced"],
            "reports_failed": result["reports_failed"],
            "errors": result.get("errors", []),
        }

    except XeroRateLimitExceededError as e:
        logger.warning(f"Rate limit exceeded for report sync: {e}")
        raise  # Re-raise for Celery auto-retry

    except Exception as e:
        logger.error(f"Report sync failed for connection {connection_id}: {e}")
        return {
            "connection_id": str(connection_id),
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await session.close()


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.reports.nightly_report_sync",
    bind=True,
    max_retries=0,  # No retries for orchestrator task
)
def nightly_report_sync(self: Task) -> dict[str, Any]:
    """Nightly sync of reports for all active Xero connections.

    Queries all active connections and queues sync_reports_for_connection
    tasks for each, staggering to respect rate limits.

    This task should be scheduled via Celery Beat at 2:00 AM AEST daily.

    Returns:
        Dict with summary of queued syncs.
    """
    import asyncio

    return asyncio.run(_nightly_report_sync_async(self))


async def _nightly_report_sync_async(task: Task) -> dict[str, Any]:
    """Async implementation of nightly report sync orchestration."""
    session = await _get_async_session()

    try:
        # Query all active Xero connections
        result = await session.execute(
            select(XeroConnection).where(
                XeroConnection.is_active == True,  # noqa: E712
                XeroConnection.access_token.isnot(None),
            )
        )
        connections = result.scalars().all()

        if not connections:
            logger.info("No active Xero connections found for nightly report sync")
            return {
                "status": "completed",
                "connections_queued": 0,
                "message": "No active connections",
            }

        queued_count = 0
        failed_count = 0

        for i, connection in enumerate(connections):
            try:
                # Stagger tasks to respect rate limits (10 connections per minute)
                countdown = (i // 10) * 60  # 60 second delay per batch of 10

                sync_reports_for_connection.apply_async(
                    args=[str(connection.id), str(connection.tenant_id)],
                    kwargs={"triggered_by": "nightly_sync"},
                    countdown=countdown,
                )
                queued_count += 1

                logger.debug(
                    f"Queued report sync for connection {connection.id} with countdown {countdown}s"
                )

            except Exception as e:
                logger.error(f"Failed to queue report sync for {connection.id}: {e}")
                failed_count += 1

        logger.info(
            f"Nightly report sync: {queued_count} connections queued, "
            f"{failed_count} failed to queue"
        )

        return {
            "status": "completed",
            "connections_queued": queued_count,
            "connections_failed": failed_count,
            "total_connections": len(connections),
        }

    except Exception as e:
        logger.error(f"Nightly report sync failed: {e}")
        return {
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await session.close()


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.reports.sync_single_report",
    **REPORT_SYNC_TASK_CONFIG,
)
def sync_single_report(
    self: Task,
    connection_id: str,
    tenant_id: str,
    report_type: str,
    period_key: str,
    triggered_by: str = "on_demand",
    user_id: str | None = None,
) -> dict[str, Any]:
    """Sync a single report for a connection.

    Used for on-demand report refresh when user clicks "Refresh from Xero".

    Args:
        connection_id: Xero connection ID.
        tenant_id: Tenant ID for RLS context.
        report_type: The report type to sync (e.g., 'profit_and_loss').
        period_key: The period key (e.g., '2024-01' or '2024-FY').
        triggered_by: Who/what triggered this sync.
        user_id: Optional user ID who triggered the sync.

    Returns:
        Dict with sync result.
    """
    import asyncio

    return asyncio.run(
        _sync_single_report_async(
            self,
            UUID(connection_id),
            UUID(tenant_id),
            report_type,
            period_key,
            triggered_by,
            UUID(user_id) if user_id else None,
        )
    )


async def _sync_single_report_async(
    task: Task,
    connection_id: UUID,
    tenant_id: UUID,
    report_type: str,
    period_key: str,
    triggered_by: str,
    user_id: UUID | None,
) -> dict[str, Any]:
    """Async implementation of single report sync."""
    settings = get_settings()
    session = await _get_async_session()

    try:
        await _set_tenant_context(session, tenant_id)

        report_service = XeroReportService(session, settings)
        result = await report_service.refresh_report(
            connection_id=connection_id,
            report_type=report_type,
            period_key=period_key,
            user_id=user_id,
        )

        logger.info(f"Single report sync completed: {report_type} for connection {connection_id}")

        return {
            "connection_id": str(connection_id),
            "report_type": report_type,
            "period_key": period_key,
            "status": "completed",
            "report_id": str(result.get("report_id")) if result.get("report_id") else None,
        }

    except XeroRateLimitExceededError as e:
        logger.warning(f"Rate limit exceeded for single report sync: {e}")
        raise  # Re-raise for Celery auto-retry

    except Exception as e:
        logger.error(f"Single report sync failed: {e}")
        return {
            "connection_id": str(connection_id),
            "report_type": report_type,
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await session.close()


# =============================================================================
# Post-Sync Report Cache Invalidation
# =============================================================================


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.reports.invalidate_report_cache",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_jitter=True,
)
def invalidate_report_cache(
    self: Task,
    connection_id: str,
    tenant_id: str,
    post_sync_task_id: str | None = None,
) -> dict[str, Any]:
    """Invalidate cached Xero reports for a connection after data sync.

    Triggered as a post-sync task after Xero data sync phase 2 completes.
    Sets cache_expires_at = now() so the next read fetches fresh data.

    Tax plan auto-refresh on load (lazy) handles the actual P&L re-pull
    when the accountant opens the plan — no eager fetching needed here.

    Args:
        connection_id: Xero connection ID.
        tenant_id: Tenant ID for RLS context.
        post_sync_task_id: Optional PostSyncTask ID for status tracking.

    Returns:
        Dict with invalidation results.
    """
    import asyncio

    return asyncio.run(
        _invalidate_report_cache_async(
            self,
            UUID(connection_id),
            UUID(tenant_id),
            post_sync_task_id,
        )
    )


async def _invalidate_report_cache_async(
    task: Task,
    connection_id: UUID,
    tenant_id: UUID,
    post_sync_task_id: str | None = None,
) -> dict[str, Any]:
    """Async implementation of report cache invalidation."""
    if post_sync_task_id:
        from app.tasks.xero import _update_post_sync_task_status

        await _update_post_sync_task_status(post_sync_task_id, "in_progress")

    session = await _get_async_session()

    try:
        await _set_tenant_context(session, tenant_id)

        from app.modules.integrations.xero.repository import XeroReportRepository

        report_repo = XeroReportRepository(session)
        invalidated = await report_repo.invalidate_by_connection(connection_id)
        await session.commit()

        logger.info(
            "Invalidated %d cached reports for connection %s",
            invalidated,
            connection_id,
        )

        result = {
            "connection_id": str(connection_id),
            "status": "completed",
            "reports_invalidated": invalidated,
        }

        if post_sync_task_id:
            from app.tasks.xero import _update_post_sync_task_status

            await _update_post_sync_task_status(
                post_sync_task_id,
                "completed",
                result_summary=result,
            )

        return result

    except Exception as e:
        logger.error(
            "Report cache invalidation failed for connection %s: %s",
            connection_id,
            e,
        )
        await session.rollback()

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
