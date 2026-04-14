"""Xero sync orchestration service — validates preconditions, creates sync jobs, dispatches Celery tasks."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.modules.auth.models import Tenant
from app.modules.billing.service import BillingService
from app.modules.integrations.xero.exceptions import (
    XeroConnectionInactiveError,
    XeroConnectionNotFoundError as XeroConnectionNotFoundExc,
    XeroRateLimitExceededError,
    XeroSyncInProgressError,
    XeroSyncJobNotFoundError,
)
from app.modules.integrations.xero.models import (
    XeroConnection,
    XeroConnectionStatus,
    XeroSyncJob,
    XeroSyncStatus,
    XeroSyncType,
)
from app.modules.integrations.xero.rate_limiter import RateLimitState, XeroRateLimiter
from app.modules.integrations.xero.repository import (
    XeroConnectionRepository,
    XeroSyncJobRepository,
)
from app.modules.integrations.xero.schemas import (
    MultiClientQueuedConnection,
    MultiClientSkippedConnection,
    MultiClientSyncResponse,
    XeroConnectionUpdate,
    XeroSyncHistoryResponse,
    XeroSyncJobResponse,
)

if TYPE_CHECKING:
    from celery import Celery

logger = logging.getLogger(__name__)


class XeroSyncService:
    """Service for orchestrating Xero sync operations.

    Manages sync jobs, validates preconditions, and coordinates
    the sync workflow.
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        celery_app: Celery | None = None,
    ) -> None:
        """Initialize sync service.

        Args:
            session: Database session.
            settings: Application settings.
            celery_app: Optional Celery app for queuing tasks.
        """
        self.session = session
        self.settings = settings
        self.celery_app = celery_app
        self.connection_repo = XeroConnectionRepository(session)
        self.job_repo = XeroSyncJobRepository(session)
        self.rate_limiter = XeroRateLimiter()

    async def initiate_sync(
        self,
        connection_id: UUID,
        sync_type: XeroSyncType = XeroSyncType.FULL,
        force_full: bool = False,
        check_client_limit: bool = True,
    ) -> XeroSyncJobResponse:
        """Initiate a new sync operation.

        Creates a sync job and queues a Celery task.

        Args:
            connection_id: The connection ID.
            sync_type: Type of sync to perform.
            force_full: Force full sync even if incremental available.
            check_client_limit: Whether to check client limit before sync (Spec 020).

        Returns:
            XeroSyncJobResponse with job details.

        Raises:
            XeroConnectionNotFoundExc: If connection not found.
            XeroConnectionInactiveError: If connection not active.
            XeroSyncInProgressError: If sync already in progress.
            XeroRateLimitExceededError: If rate limits exceeded.
            ClientLimitExceededError: If tenant is at client limit (Spec 020).
        """
        # Validate connection exists and is active
        connection = await self.connection_repo.get_by_id(connection_id)
        if connection is None:
            raise XeroConnectionNotFoundExc(connection_id)

        if connection.status != XeroConnectionStatus.ACTIVE:
            raise XeroConnectionInactiveError(connection_id)

        # Check client limit before starting sync (Spec 020)
        if check_client_limit:
            from sqlalchemy import select

            tenant = await self.session.scalar(
                select(Tenant).where(Tenant.id == connection.tenant_id)
            )
            if tenant:
                billing_service = BillingService(self.session)
                # This raises ClientLimitExceededError if at limit
                billing_service.check_client_limit(tenant)

        # Check for existing sync in progress
        existing_job = await self.job_repo.get_active_for_connection(connection_id)
        if existing_job:
            # Auto-expire stale jobs stuck as in_progress for over 30 minutes
            stale_threshold = datetime.now(UTC) - timedelta(minutes=30)
            if existing_job.updated_at.replace(tzinfo=UTC) < stale_threshold:
                await self.job_repo.update_status(
                    existing_job.id,
                    XeroSyncStatus.FAILED,
                    error_message="Auto-expired: job stale for over 30 minutes",
                )
                await self.session.flush()
            else:
                raise XeroSyncInProgressError(connection_id, existing_job.id)

        # Check rate limits
        state = RateLimitState(
            daily_remaining=connection.rate_limit_daily_remaining or 5000,
            minute_remaining=connection.rate_limit_minute_remaining or 60,
            # Note: rate_limit_reset_at tracks when the minute bucket resets,
            # NOT when we're rate limited until. We're only rate limited if
            # we've actually hit a 429. So we don't set rate_limited_until here.
        )
        if not self.rate_limiter.can_make_request(state):
            wait_seconds = self.rate_limiter.get_wait_time(state)
            raise XeroRateLimitExceededError(wait_seconds)

        # Delegate to start_phased_sync for the actual job creation and dispatch
        return await self.start_phased_sync(
            connection=connection,
            sync_type=sync_type,
            force_full=force_full,
            triggered_by="user",
        )

    async def start_phased_sync(
        self,
        connection: XeroConnection,
        sync_type: XeroSyncType = XeroSyncType.FULL,
        force_full: bool = False,
        triggered_by: str = "user",
    ) -> XeroSyncJobResponse:
        """Create a sync job and dispatch the phased sync Celery task.

        This method creates a XeroSyncJob with the triggered_by field and
        dispatches the run_phased_sync Celery task (not the legacy run_sync).

        Args:
            connection: The validated, active XeroConnection.
            sync_type: Type of sync to perform.
            force_full: Force full sync even if incremental is available.
            triggered_by: What triggered this sync (user, schedule, webhook, system).

        Returns:
            XeroSyncJobResponse with the created job details.
        """
        # Create sync job with phased sync fields
        job = await self.job_repo.create(
            tenant_id=connection.tenant_id,
            connection_id=connection.id,
            sync_type=sync_type,
        )
        # Set the triggered_by field on the job
        job.triggered_by = triggered_by
        await self.session.flush()

        # Mark connection as sync in progress
        await self.connection_repo.update(
            connection.id,
            XeroConnectionUpdate(last_used_at=datetime.now(UTC)),
        )

        # Queue phased sync Celery task if available
        if self.celery_app:
            self.celery_app.send_task(
                "app.tasks.xero.run_phased_sync",
                kwargs={
                    "job_id": str(job.id),
                    "connection_id": str(connection.id),
                    "tenant_id": str(connection.tenant_id),
                    "sync_type": sync_type.value,
                    "force_full": force_full,
                },
            )

        logger.info(
            "Phased sync job created and dispatched",
            extra={
                "job_id": str(job.id),
                "connection_id": str(connection.id),
                "tenant_id": str(connection.tenant_id),
                "sync_type": sync_type.value,
                "force_full": force_full,
                "triggered_by": triggered_by,
            },
        )

        return XeroSyncJobResponse(
            id=job.id,
            connection_id=job.connection_id,
            sync_type=job.sync_type,
            status=job.status,
            started_at=job.started_at,
            completed_at=job.completed_at,
            records_processed=job.records_processed,
            records_created=job.records_created,
            records_updated=job.records_updated,
            records_failed=job.records_failed,
            error_message=job.error_message,
            progress_details=job.progress_details,
            created_at=job.created_at,
            sync_phase=job.sync_phase,
            triggered_by=job.triggered_by,
        )

    async def get_sync_status(self, job_id: UUID) -> XeroSyncJobResponse:
        """Get status of a sync job.

        Args:
            job_id: The job ID.

        Returns:
            XeroSyncJobResponse with current status.

        Raises:
            XeroSyncJobNotFoundError: If job not found.
        """
        job = await self.job_repo.get_by_id(job_id)
        if job is None:
            raise XeroSyncJobNotFoundError(job_id)

        return XeroSyncJobResponse(
            id=job.id,
            connection_id=job.connection_id,
            sync_type=job.sync_type,
            status=job.status,
            started_at=job.started_at,
            completed_at=job.completed_at,
            records_processed=job.records_processed,
            records_created=job.records_created,
            records_updated=job.records_updated,
            records_failed=job.records_failed,
            error_message=job.error_message,
            progress_details=job.progress_details,
            created_at=job.created_at,
            sync_phase=job.sync_phase,
            triggered_by=job.triggered_by,
        )

    async def get_sync_history(
        self,
        connection_id: UUID,
        limit: int = 10,
        offset: int = 0,
    ) -> XeroSyncHistoryResponse:
        """Get sync job history for a connection.

        Args:
            connection_id: The connection ID.
            limit: Max jobs to return.
            offset: Number of jobs to skip.

        Returns:
            XeroSyncHistoryResponse with paginated jobs.
        """
        jobs, total = await self.job_repo.list_by_connection(
            connection_id,
            limit=limit,
            offset=offset,
        )

        return XeroSyncHistoryResponse(
            jobs=[
                XeroSyncJobResponse(
                    id=job.id,
                    connection_id=job.connection_id,
                    sync_type=job.sync_type,
                    status=job.status,
                    started_at=job.started_at,
                    completed_at=job.completed_at,
                    records_processed=job.records_processed,
                    records_created=job.records_created,
                    records_updated=job.records_updated,
                    records_failed=job.records_failed,
                    error_message=job.error_message,
                    progress_details=job.progress_details,
                    created_at=job.created_at,
                    sync_phase=job.sync_phase,
                    triggered_by=job.triggered_by,
                )
                for job in jobs
            ],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def cancel_sync(self, job_id: UUID) -> XeroSyncJobResponse:
        """Cancel a sync job.

        Args:
            job_id: The job ID.

        Returns:
            XeroSyncJobResponse with updated status.

        Raises:
            XeroSyncJobNotFoundError: If job not found.
        """
        job = await self.job_repo.get_by_id(job_id)
        if job is None:
            raise XeroSyncJobNotFoundError(job_id)

        # Only cancel if pending or in_progress
        if job.status in (XeroSyncStatus.PENDING, XeroSyncStatus.IN_PROGRESS):
            await self.job_repo.update_status(
                job_id,
                XeroSyncStatus.CANCELLED,
                error_message="Cancelled by user",
            )

        # Refresh job
        job = await self.job_repo.get_by_id(job_id)

        return XeroSyncJobResponse(
            id=job.id,
            connection_id=job.connection_id,
            sync_type=job.sync_type,
            status=job.status,
            started_at=job.started_at,
            completed_at=job.completed_at,
            records_processed=job.records_processed,
            records_created=job.records_created,
            records_updated=job.records_updated,
            records_failed=job.records_failed,
            error_message=job.error_message,
            progress_details=job.progress_details,
            created_at=job.created_at,
            sync_phase=job.sync_phase,
            triggered_by=job.triggered_by,
        )

    async def start_multi_client_sync(
        self,
        tenant_id: UUID,
        force_full: bool = False,
    ) -> MultiClientSyncResponse:
        """Start phased sync for all active connections in a tenant.

        Fetches all active Xero connections for the given tenant, skips any
        that already have an active sync job, creates a new sync job for each
        eligible connection, and dispatches phased sync tasks with staggered
        delays to avoid Xero API rate limit spikes.

        Args:
            tenant_id: The tenant ID to sync all connections for.
            force_full: Force full sync even if incremental is available.

        Returns:
            MultiClientSyncResponse with batch_id, totals, and per-connection details.
        """
        import uuid

        batch_id = uuid.uuid4()

        # Get all active connections for this tenant
        connections = await self.connection_repo.get_all_active(tenant_id)

        jobs_queued: list[MultiClientQueuedConnection] = []
        jobs_skipped: list[MultiClientSkippedConnection] = []

        for i, connection in enumerate(connections):
            # Check for existing active sync (pending or in_progress)
            active_job = await self.job_repo.get_active_for_connection(connection.id)
            if active_job:
                jobs_skipped.append(
                    MultiClientSkippedConnection(
                        connection_id=connection.id,
                        organization_name=connection.organization_name or "Unknown",
                        reason="sync_in_progress",
                    )
                )
                continue

            # Create sync job for this connection
            job = XeroSyncJob(
                tenant_id=tenant_id,
                connection_id=connection.id,
                sync_type=XeroSyncType.FULL,
                status=XeroSyncStatus.PENDING,
                triggered_by="system",
            )
            self.session.add(job)
            await self.session.flush()

            # Dispatch phased sync with staggered countdown to avoid rate limit spikes.
            # Each connection is delayed by 2 seconds relative to the previous one.
            if self.celery_app:
                self.celery_app.send_task(
                    "app.tasks.xero.run_phased_sync",
                    kwargs={
                        "job_id": str(job.id),
                        "connection_id": str(connection.id),
                        "tenant_id": str(tenant_id),
                        "sync_type": "full",
                        "force_full": force_full,
                    },
                    countdown=i * 2,
                )

            jobs_queued.append(
                MultiClientQueuedConnection(
                    connection_id=connection.id,
                    organization_name=connection.organization_name or "Unknown",
                    job_id=job.id,
                )
            )

        await self.session.commit()

        logger.info(
            "Multi-client sync batch dispatched",
            extra={
                "batch_id": str(batch_id),
                "tenant_id": str(tenant_id),
                "total_connections": len(connections),
                "jobs_queued": len(jobs_queued),
                "jobs_skipped": len(jobs_skipped),
                "force_full": force_full,
            },
        )

        return MultiClientSyncResponse(
            batch_id=batch_id,
            total_connections=len(connections),
            jobs_queued=len(jobs_queued),
            jobs_skipped=len(jobs_skipped),
            queued=jobs_queued,
            skipped=jobs_skipped,
        )
