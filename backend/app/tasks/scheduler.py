"""Scheduled tasks for automatic data synchronization.

This module contains Celery tasks that run on a schedule to keep
data fresh across all tenants without manual intervention.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.modules.integrations.xero.models import XeroConnection, XeroSyncJob
from app.modules.integrations.xero.schemas import XeroSyncType
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _get_async_session() -> AsyncSession:
    """Create a fresh async database session for scheduler tasks.

    Creates a new engine per call to avoid event loop issues with Celery.
    Uses NullPool to avoid connection leaks in Celery's asyncio.run() context.
    """
    settings = get_settings()
    engine = create_async_engine(settings.database.url, echo=False, poolclass=NullPool)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return async_session()


async def _create_sync_job(
    session: AsyncSession,
    connection: XeroConnection,
) -> XeroSyncJob:
    """Create a sync job for a connection.

    Args:
        session: Database session.
        connection: The Xero connection.

    Returns:
        The created sync job.
    """
    job = XeroSyncJob(
        tenant_id=connection.tenant_id,
        connection_id=connection.id,
        sync_type=XeroSyncType.FULL,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


# Threshold for considering data stale (24 hours)
STALE_THRESHOLD_HOURS = 24


@celery_app.task(
    name="app.tasks.scheduler.sync_all_stale_connections",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def sync_all_stale_connections(self) -> dict:
    """Sync all Xero connections that haven't been synced in 24+ hours.

    This task runs daily and:
    1. Finds all active connections with stale data (>24hrs since last sync)
    2. Creates a sync job for each connection
    3. Triggers the sync task for each job
    4. Quality scores are calculated automatically after each sync

    Returns:
        Dict with sync statistics.
    """
    import asyncio

    async def _sync_stale():
        from app.tasks.xero import run_phased_sync

        session = await _get_async_session()
        try:
            # Calculate the staleness threshold
            stale_threshold = datetime.now(UTC) - timedelta(hours=STALE_THRESHOLD_HOURS)

            # Find all active connections that are stale
            query = select(XeroConnection).where(
                XeroConnection.status == "active",
                # Either never synced or synced more than 24 hours ago
                (XeroConnection.last_full_sync_at.is_(None))
                | (XeroConnection.last_full_sync_at < stale_threshold),
            )

            result = await session.execute(query)
            stale_connections = result.scalars().all()

            synced_count = 0
            skipped_count = 0
            failed_count = 0
            job_ids = []

            logger.info(f"Found {len(stale_connections)} stale connections to sync")

            for connection in stale_connections:
                try:
                    # Check for existing sync in progress
                    existing_job_query = select(XeroSyncJob).where(
                        XeroSyncJob.connection_id == connection.id,
                        XeroSyncJob.status.in_(["pending", "in_progress"]),
                    )
                    existing_result = await session.execute(existing_job_query)
                    existing_job = existing_result.scalar_one_or_none()

                    if existing_job:
                        logger.info(f"Sync already in progress for {connection.id}, skipping")
                        skipped_count += 1
                        continue

                    # Create sync job
                    job = await _create_sync_job(session, connection)

                    # Trigger async sync task
                    # Use phased sync with incremental mode by default.
                    # force_full=True only if the connection has never had
                    # per-entity timestamps (first sync after migration).
                    needs_full = connection.last_credit_notes_sync_at is None
                    run_phased_sync.delay(
                        job_id=str(job.id),
                        connection_id=str(connection.id),
                        tenant_id=str(connection.tenant_id),
                        sync_type="full",
                        force_full=needs_full,
                    )
                    synced_count += 1
                    job_ids.append(str(job.id))
                    logger.info(
                        f"Triggered sync job {job.id} for connection {connection.id} "
                        f"({connection.organization_name})"
                    )
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to trigger sync for connection {connection.id}: {e}")

            return {
                "total_stale": len(stale_connections),
                "synced": synced_count,
                "skipped": skipped_count,
                "failed": failed_count,
                "job_ids": job_ids,
                "checked_at": datetime.now(UTC).isoformat(),
            }
        finally:
            await session.close()

    return asyncio.run(_sync_stale())


@celery_app.task(
    name="app.tasks.scheduler.sync_connection_if_stale",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def sync_connection_if_stale(self, connection_id: str) -> dict:
    """Sync a specific connection if its data is stale (>24hrs).

    This task can be called on-demand to check and sync a specific
    connection without forcing a sync if data is fresh.

    Args:
        connection_id: UUID of the connection to check.

    Returns:
        Dict indicating whether sync was triggered or skipped.
    """
    import asyncio

    async def _check_and_sync():
        from app.tasks.xero import run_phased_sync

        session = await _get_async_session()
        try:
            # Get the connection
            query = select(XeroConnection).where(
                XeroConnection.id == UUID(connection_id),
            )
            result = await session.execute(query)
            connection = result.scalar_one_or_none()

            if not connection:
                logger.warning(f"Connection {connection_id} not found")
                return {"status": "not_found", "connection_id": connection_id}

            if connection.status != "active":
                logger.info(f"Connection {connection_id} is not active, skipping")
                return {"status": "skipped", "reason": "inactive", "connection_id": connection_id}

            # Check for existing sync in progress
            existing_job_query = select(XeroSyncJob).where(
                XeroSyncJob.connection_id == connection.id,
                XeroSyncJob.status.in_(["pending", "in_progress"]),
            )
            existing_result = await session.execute(existing_job_query)
            existing_job = existing_result.scalar_one_or_none()

            if existing_job:
                logger.info(f"Sync already in progress for {connection_id}")
                return {
                    "status": "skipped",
                    "reason": "sync_in_progress",
                    "connection_id": connection_id,
                    "job_id": str(existing_job.id),
                }

            # Check if stale
            stale_threshold = datetime.now(UTC) - timedelta(hours=STALE_THRESHOLD_HOURS)
            is_stale = (
                connection.last_full_sync_at is None
                or connection.last_full_sync_at < stale_threshold
            )

            if is_stale:
                # Create sync job
                job = await _create_sync_job(session, connection)

                # Use phased sync with incremental mode by default.
                needs_full = connection.last_credit_notes_sync_at is None
                run_phased_sync.delay(
                    job_id=str(job.id),
                    connection_id=str(connection.id),
                    tenant_id=str(connection.tenant_id),
                    sync_type="full",
                    force_full=needs_full,
                )
                logger.info(
                    f"Triggered phased sync job {job.id} for stale connection {connection_id}"
                )
                return {
                    "status": "sync_triggered",
                    "connection_id": connection_id,
                    "job_id": str(job.id),
                    "last_sync": connection.last_full_sync_at.isoformat()
                    if connection.last_full_sync_at
                    else None,
                }
            else:
                hours_since_sync = (
                    (datetime.now(UTC) - connection.last_full_sync_at).total_seconds() / 3600
                    if connection.last_full_sync_at
                    else None
                )
                logger.info(
                    f"Connection {connection_id} is fresh "
                    f"(synced {hours_since_sync:.1f}h ago), skipping"
                )
                return {
                    "status": "skipped",
                    "reason": "fresh",
                    "connection_id": connection_id,
                    "hours_since_sync": round(hours_since_sync, 1) if hours_since_sync else None,
                }
        finally:
            await session.close()

    return asyncio.run(_check_and_sync())


# Threshold for considering a sync job stuck (60 minutes)
STUCK_JOB_THRESHOLD_MINUTES = 60


@celery_app.task(
    name="app.tasks.scheduler.cleanup_stuck_sync_jobs",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def cleanup_stuck_sync_jobs(self) -> dict:
    """Find and fail sync jobs stuck in pending/in_progress for too long.

    Jobs can get stuck when a Celery worker dies mid-sync (Railway deploys,
    OOM kills, etc.). Without cleanup, these ghost jobs block the scheduler
    from triggering new syncs for the same connection.

    Runs every 15 minutes and marks jobs older than 60 minutes as failed.

    Returns:
        Dict with cleanup statistics.
    """
    import asyncio

    async def _cleanup():
        from sqlalchemy import update

        session = await _get_async_session()
        try:
            stuck_threshold = datetime.now(UTC) - timedelta(minutes=STUCK_JOB_THRESHOLD_MINUTES)

            # Find jobs stuck in pending or in_progress.
            # Use updated_at so that actively-progressing jobs (whose row is
            # modified each time an entity batch completes) are not killed.
            stuck_query = select(XeroSyncJob).where(
                XeroSyncJob.status.in_(["pending", "in_progress"]),
                XeroSyncJob.updated_at < stuck_threshold,
            )
            result = await session.execute(stuck_query)
            stuck_jobs = result.scalars().all()

            if not stuck_jobs:
                return {
                    "status": "completed",
                    "stuck_jobs_found": 0,
                    "checked_at": datetime.now(UTC).isoformat(),
                }

            logger.warning(f"Found {len(stuck_jobs)} stuck sync jobs to clean up")

            cleaned_ids = []
            for job in stuck_jobs:
                age_minutes = (datetime.now(UTC) - job.updated_at).total_seconds() / 60

                # Mark as failed with descriptive error
                await session.execute(
                    update(XeroSyncJob)
                    .where(XeroSyncJob.id == job.id)
                    .values(
                        status="failed",
                        error_message=(
                            f"Automatically failed: job stuck for "
                            f"{age_minutes:.0f} minutes (threshold: "
                            f"{STUCK_JOB_THRESHOLD_MINUTES}m). "
                            f"Likely caused by worker crash or deployment."
                        ),
                        completed_at=datetime.now(UTC),
                    )
                )
                cleaned_ids.append(str(job.id))
                logger.info(
                    f"Cleaned up stuck job {job.id} for connection "
                    f"{job.connection_id} (stuck for {age_minutes:.0f}m)"
                )

            await session.commit()

            return {
                "status": "completed",
                "stuck_jobs_found": len(stuck_jobs),
                "cleaned_job_ids": cleaned_ids,
                "checked_at": datetime.now(UTC).isoformat(),
            }
        finally:
            await session.close()

    return asyncio.run(_cleanup())


# =============================================================================
# Token Keepalive — proactively refresh Xero tokens before they expire
# =============================================================================

# Refresh tokens that will expire within this window (hours).
# Xero access tokens last 30 min; refresh tokens expire after 60 days of
# non-use.  Running every 12 hours with a 24-hour lookahead means we'll
# touch every active connection at least once a day, keeping refresh
# tokens alive indefinitely.
TOKEN_REFRESH_LOOKAHEAD_HOURS = 24


@celery_app.task(
    name="app.tasks.scheduler.keepalive_xero_tokens",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def keepalive_xero_tokens(self) -> dict:
    """Proactively refresh Xero tokens for all active connections.

    Prevents refresh tokens from expiring due to inactivity (Xero's
    60-day TTL).  For each active connection whose access token expires
    within TOKEN_REFRESH_LOOKAHEAD_HOURS, performs a token refresh using
    the distributed lock to avoid conflicts with concurrent syncs.

    Runs every 12 hours via Celery beat.

    Returns:
        Dict with keepalive statistics.
    """
    import asyncio

    async def _keepalive():
        from app.config import get_settings as _get_settings
        from app.modules.integrations.xero.connection_service import (
            XeroConnectionService,
        )

        session = await _get_async_session()
        settings = _get_settings()

        try:
            # Find all active connections
            query = select(XeroConnection).where(
                XeroConnection.status == "active",
            )
            result = await session.execute(query)
            connections = result.scalars().all()

            refreshed = 0
            skipped = 0
            failed = 0
            errors: list[str] = []

            logger.info(
                "Token keepalive: checking %d active connections", len(connections)
            )

            for conn in connections:
                try:
                    # Check if token expires within the lookahead window
                    if conn.token_expires_at:
                        threshold = datetime.now(UTC) + timedelta(
                            hours=TOKEN_REFRESH_LOOKAHEAD_HOURS
                        )
                        if conn.token_expires_at > threshold:
                            # Token is fresh enough, skip
                            skipped += 1
                            continue

                    # Refresh using the distributed lock
                    conn_service = XeroConnectionService(session, settings)
                    await conn_service.ensure_valid_token(conn.id)
                    await session.commit()
                    refreshed += 1

                    logger.info(
                        "Token keepalive: refreshed %s (%s)",
                        conn.id,
                        conn.organization_name,
                    )

                except Exception as e:
                    failed += 1
                    errors.append(f"{conn.organization_name}: {e}")
                    logger.warning(
                        "Token keepalive: failed for %s (%s): %s",
                        conn.id,
                        conn.organization_name,
                        e,
                    )
                    # Rollback the failed transaction so the next
                    # connection can proceed
                    await session.rollback()

            return {
                "total_connections": len(connections),
                "refreshed": refreshed,
                "skipped": skipped,
                "failed": failed,
                "errors": errors[:10],  # Cap to avoid huge payloads
                "checked_at": datetime.now(UTC).isoformat(),
            }
        finally:
            await session.close()

    return asyncio.run(_keepalive())
