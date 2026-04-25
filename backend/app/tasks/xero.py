"""Celery tasks for Xero data synchronization.

Provides background tasks for:
- Syncing contacts, invoices, bank transactions, accounts
- Full sync orchestration (phased and legacy)
- Job status management
- Per-entity sync with progress tracking
- Post-sync task dispatching

All tasks use automatic retry with exponential backoff.
"""

import asyncio
import logging
import warnings
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from celery import Task
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.modules.integrations.xero.exceptions import (
    XeroConnectionInactiveError,
    XeroRateLimitExceededError,
)
from app.modules.integrations.xero.models import XeroSyncStatus, XeroSyncType
from app.modules.integrations.xero.repository import (
    XeroConnectionRepository,
    XeroSyncJobRepository,
)
from app.modules.integrations.xero.schemas import XeroConnectionUpdate
from app.modules.integrations.xero.service import XeroDataService
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Maximum concurrent Xero API sync connections per tenant.
# Each entity sync may make multiple paginated API calls, so this must be
# conservative relative to Xero's 60 calls/minute rate limit.
MAX_CONCURRENT_SYNCS_PER_TENANT = 5

# Redis key prefix for per-tenant concurrency tracking
SYNC_CONCURRENCY_KEY_PREFIX = "xero_sync_concurrency"

# Sync task configuration
SYNC_TASK_CONFIG = {
    "bind": True,
    "max_retries": 3,
    "default_retry_delay": 60,
    "autoretry_for": (XeroRateLimitExceededError, ConnectionError, TimeoutError),
    "retry_backoff": True,
    "retry_backoff_max": 600,
    "retry_jitter": True,
}


def _friendly_sync_error(raw: str) -> str:
    """Map raw exception text to a user-friendly sync error message."""
    lowered = raw.lower()
    if "token refresh failed" in lowered or "invalid_client" in lowered:
        return "Xero connection expired. Please reconnect your Xero account."
    if "invalid or expired access token" in lowered or "401" in lowered:
        return "Xero access expired. Please reconnect your Xero account."
    if "rate limit" in lowered or "429" in lowered:
        return "Xero API rate limit reached. Please try again shortly."
    if "connection is not active" in lowered:
        return "Xero connection is inactive. Please reconnect."
    if "not found" in lowered:
        return "Xero connection not found."
    # Fallback: cap length and strip tracebacks
    if len(raw) > 120:
        return raw[:117] + "..."
    return raw


async def _get_async_session() -> AsyncSession:
    """Create an async database session for tasks.

    Uses NullPool to avoid connection leaks. Each Celery task runs inside
    asyncio.run() which creates and destroys an event loop. The default
    QueuePool holds connections open after the loop closes, leaking them.
    NullPool closes connections immediately when returned.
    """
    settings = get_settings()
    engine = create_async_engine(settings.database.url, echo=False, poolclass=NullPool)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return async_session()


async def _set_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    """Set the tenant context for RLS policies.

    Uses session-scoped SET (not SET LOCAL) because Celery tasks commit
    multiple times during execution. SET LOCAL is transaction-scoped and
    would be cleared after each commit, causing subsequent queries to fail
    against RLS-protected tables.

    Args:
        session: Database session.
        tenant_id: Tenant ID to set in session context.
    """
    # Note: SET doesn't support parameter binding with asyncpg,
    # so we embed the UUID directly. This is safe since tenant_id is a UUID.
    await session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))


async def _update_job_status(
    session: AsyncSession,
    job_id: UUID,
    status: XeroSyncStatus,
    error_message: str | None = None,
    progress_details: dict[str, Any] | None = None,
    records_processed: int = 0,
    records_created: int = 0,
    records_updated: int = 0,
    records_failed: int = 0,
) -> None:
    """Update sync job status and metrics.

    Args:
        session: Database session.
        job_id: Job ID to update.
        status: New status.
        error_message: Optional error message.
        progress_details: Optional progress details dict.
        records_processed: Number of records processed.
        records_created: Number of records created.
        records_updated: Number of records updated.
        records_failed: Number of records failed.
    """
    job_repo = XeroSyncJobRepository(session)

    if status == XeroSyncStatus.IN_PROGRESS:
        await job_repo.update_status(job_id, status)
    elif status in (XeroSyncStatus.COMPLETED, XeroSyncStatus.FAILED):
        await job_repo.update_status(job_id, status, error_message)

    await job_repo.update_progress(
        job_id,
        records_processed=records_processed,
        records_created=records_created,
        records_updated=records_updated,
        records_failed=records_failed,
        progress_details=progress_details,
    )
    await session.commit()


async def _emit_sync_audit_event(
    session: AsyncSession,
    event_type: str,
    action: str,
    outcome: str,
    tenant_id: UUID,
    connection_id: UUID,
    job_id: UUID,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit an audit event for a sync operation.

    Logs sync lifecycle events (started, completed, failed) to the audit
    log for ATO compliance. Failures in audit logging are caught and logged
    but do not interrupt the sync workflow.

    Args:
        session: Database session.
        event_type: Audit event type (e.g. integration.xero.sync.started).
        action: Action performed (e.g. sync).
        outcome: Result of the action (success or failure).
        tenant_id: Tenant ID.
        connection_id: Xero connection ID.
        job_id: Sync job ID.
        metadata: Additional context to include in the audit record.
    """
    try:
        from app.core.audit import AuditService

        audit_metadata = {
            "job_id": str(job_id),
            "connection_id": str(connection_id),
        }
        if metadata:
            audit_metadata.update(metadata)

        audit_service = AuditService(session)
        await audit_service.log_event(
            event_type=event_type,
            event_category="integration",
            actor_type="system",
            tenant_id=tenant_id,
            resource_type="xero_sync_job",
            resource_id=job_id,
            action=action,
            outcome=outcome,
            metadata=audit_metadata,
        )
        await session.commit()
    except Exception as audit_err:
        # Audit logging failures must not block sync operations
        logger.warning(
            "Failed to emit audit event %s for job %s: %s",
            event_type,
            job_id,
            audit_err,
        )


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.xero.sync_contacts",
    **SYNC_TASK_CONFIG,
)
def sync_xero_contacts(
    self: Task,
    job_id: str,
    connection_id: str,
    tenant_id: str,
    force_full: bool = False,
) -> dict[str, Any]:
    """Sync contacts from Xero.

    Args:
        job_id: Sync job ID.
        connection_id: Xero connection ID.
        tenant_id: Tenant ID for RLS context.
        force_full: Force full sync ignoring last sync timestamp.

    Returns:
        Dict with sync results.
    """
    import asyncio

    return asyncio.run(
        _sync_contacts_async(
            self,
            UUID(job_id),
            UUID(connection_id),
            UUID(tenant_id),
            force_full,
        )
    )


async def _sync_contacts_async(
    task: Task,
    job_id: UUID,
    connection_id: UUID,
    tenant_id: UUID,
    force_full: bool,
) -> dict[str, Any]:
    """Async implementation of contacts sync."""
    settings = get_settings()
    session = await _get_async_session()

    try:
        await _set_tenant_context(session, tenant_id)

        # Update job status to in_progress
        await _update_job_status(session, job_id, XeroSyncStatus.IN_PROGRESS)

        # Get connection for incremental sync timestamp
        conn_repo = XeroConnectionRepository(session)
        connection = await conn_repo.get_by_id(connection_id)

        if not connection:
            raise XeroConnectionInactiveError(connection_id)

        # Determine modified_since for incremental sync
        modified_since = None
        if not force_full and connection.last_contacts_sync_at:
            modified_since = connection.last_contacts_sync_at

        # Perform sync
        data_service = XeroDataService(session, settings)
        result = await data_service.sync_contacts(
            connection_id,
            modified_since=modified_since,
        )

        # Update job with results
        status = XeroSyncStatus.COMPLETED if not result.error_message else XeroSyncStatus.FAILED
        await _update_job_status(
            session,
            job_id,
            status,
            error_message=result.error_message,
            progress_details={"entity": "contacts"},
            records_processed=result.records_processed,
            records_created=result.records_created,
            records_updated=result.records_updated,
            records_failed=result.records_failed,
        )

        # Update connection timestamp
        await conn_repo.update(
            connection_id,
            XeroConnectionUpdate(last_used_at=datetime.now(UTC)),
        )
        await session.commit()

        # Mark onboarding clients_imported if contacts were synced
        if result.records_processed > 0:
            try:
                from app.modules.onboarding.service import OnboardingService

                connection = await conn_repo.get_by_id(connection_id)
                if connection:
                    onboarding_service = OnboardingService(session=session)
                    await onboarding_service.mark_clients_imported(connection.tenant_id)
                    await session.commit()
            except Exception as e:
                logger.warning(
                    "Failed to update onboarding progress for client import", error=str(e)
                )

        logger.info(
            f"Contacts sync completed for connection {connection_id}: "
            f"{result.records_processed} processed, {result.records_created} created, "
            f"{result.records_updated} updated, {result.records_failed} failed"
        )

        return {
            "job_id": str(job_id),
            "status": status.value,
            "records_processed": result.records_processed,
            "records_created": result.records_created,
            "records_updated": result.records_updated,
            "records_failed": result.records_failed,
            "error_message": result.error_message,
        }

    except XeroRateLimitExceededError as e:
        logger.warning(f"Rate limit exceeded for contacts sync: {e}")
        await _update_job_status(
            session,
            job_id,
            XeroSyncStatus.PENDING,
            error_message=f"Rate limited, will retry: {e}",
        )
        await session.commit()
        raise  # Re-raise for Celery auto-retry

    except Exception as e:
        logger.error(f"Contacts sync failed: {e}")
        await session.rollback()
        await _update_job_status(
            session,
            job_id,
            XeroSyncStatus.FAILED,
            error_message=str(e),
        )
        await session.commit()
        return {
            "job_id": str(job_id),
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await session.close()


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.xero.sync_invoices",
    **SYNC_TASK_CONFIG,
)
def sync_xero_invoices(
    self: Task,
    job_id: str,
    connection_id: str,
    tenant_id: str,
    force_full: bool = False,
) -> dict[str, Any]:
    """Sync invoices from Xero."""
    import asyncio

    return asyncio.run(
        _sync_invoices_async(
            self,
            UUID(job_id),
            UUID(connection_id),
            UUID(tenant_id),
            force_full,
        )
    )


async def _sync_invoices_async(
    task: Task,
    job_id: UUID,
    connection_id: UUID,
    tenant_id: UUID,
    force_full: bool,
) -> dict[str, Any]:
    """Async implementation of invoices sync."""
    settings = get_settings()
    session = await _get_async_session()

    try:
        await _set_tenant_context(session, tenant_id)
        await _update_job_status(session, job_id, XeroSyncStatus.IN_PROGRESS)

        conn_repo = XeroConnectionRepository(session)
        connection = await conn_repo.get_by_id(connection_id)

        if not connection:
            raise XeroConnectionInactiveError(connection_id)

        modified_since = None
        if not force_full and connection.last_invoices_sync_at:
            modified_since = connection.last_invoices_sync_at

        data_service = XeroDataService(session, settings)
        result = await data_service.sync_invoices(
            connection_id,
            modified_since=modified_since,
        )

        status = XeroSyncStatus.COMPLETED if not result.error_message else XeroSyncStatus.FAILED
        await _update_job_status(
            session,
            job_id,
            status,
            error_message=result.error_message,
            progress_details={"entity": "invoices"},
            records_processed=result.records_processed,
            records_created=result.records_created,
            records_updated=result.records_updated,
            records_failed=result.records_failed,
        )

        await conn_repo.update(
            connection_id,
            XeroConnectionUpdate(last_used_at=datetime.now(UTC)),
        )
        await session.commit()

        logger.info(
            f"Invoices sync completed for connection {connection_id}: "
            f"{result.records_processed} processed"
        )

        return {
            "job_id": str(job_id),
            "status": status.value,
            "records_processed": result.records_processed,
            "records_created": result.records_created,
            "records_updated": result.records_updated,
            "records_failed": result.records_failed,
            "error_message": result.error_message,
        }

    except XeroRateLimitExceededError as e:
        logger.warning(f"Rate limit exceeded for invoices sync: {e}")
        await _update_job_status(
            session,
            job_id,
            XeroSyncStatus.PENDING,
            error_message=f"Rate limited, will retry: {e}",
        )
        await session.commit()
        raise

    except Exception as e:
        logger.error(f"Invoices sync failed: {e}")
        await session.rollback()
        await _update_job_status(
            session,
            job_id,
            XeroSyncStatus.FAILED,
            error_message=str(e),
        )
        await session.commit()
        return {
            "job_id": str(job_id),
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await session.close()


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.xero.sync_bank_transactions",
    **SYNC_TASK_CONFIG,
)
def sync_xero_bank_transactions(
    self: Task,
    job_id: str,
    connection_id: str,
    tenant_id: str,
    force_full: bool = False,
) -> dict[str, Any]:
    """Sync bank transactions from Xero."""
    import asyncio

    return asyncio.run(
        _sync_bank_transactions_async(
            self,
            UUID(job_id),
            UUID(connection_id),
            UUID(tenant_id),
            force_full,
        )
    )


async def _sync_bank_transactions_async(
    task: Task,
    job_id: UUID,
    connection_id: UUID,
    tenant_id: UUID,
    force_full: bool,
) -> dict[str, Any]:
    """Async implementation of bank transactions sync."""
    settings = get_settings()
    session = await _get_async_session()

    try:
        await _set_tenant_context(session, tenant_id)
        await _update_job_status(session, job_id, XeroSyncStatus.IN_PROGRESS)

        conn_repo = XeroConnectionRepository(session)
        connection = await conn_repo.get_by_id(connection_id)

        if not connection:
            raise XeroConnectionInactiveError(connection_id)

        modified_since = None
        if not force_full and connection.last_transactions_sync_at:
            modified_since = connection.last_transactions_sync_at

        data_service = XeroDataService(session, settings)
        result = await data_service.sync_bank_transactions(
            connection_id,
            modified_since=modified_since,
        )

        status = XeroSyncStatus.COMPLETED if not result.error_message else XeroSyncStatus.FAILED
        await _update_job_status(
            session,
            job_id,
            status,
            error_message=result.error_message,
            progress_details={"entity": "bank_transactions"},
            records_processed=result.records_processed,
            records_created=result.records_created,
            records_updated=result.records_updated,
            records_failed=result.records_failed,
        )

        await conn_repo.update(
            connection_id,
            XeroConnectionUpdate(last_used_at=datetime.now(UTC)),
        )
        await session.commit()

        logger.info(
            f"Bank transactions sync completed for connection {connection_id}: "
            f"{result.records_processed} processed"
        )

        return {
            "job_id": str(job_id),
            "status": status.value,
            "records_processed": result.records_processed,
            "records_created": result.records_created,
            "records_updated": result.records_updated,
            "records_failed": result.records_failed,
            "error_message": result.error_message,
        }

    except XeroRateLimitExceededError as e:
        logger.warning(f"Rate limit exceeded for bank transactions sync: {e}")
        await _update_job_status(
            session,
            job_id,
            XeroSyncStatus.PENDING,
            error_message=f"Rate limited, will retry: {e}",
        )
        await session.commit()
        raise

    except Exception as e:
        logger.error(f"Bank transactions sync failed: {e}")
        await session.rollback()
        await _update_job_status(
            session,
            job_id,
            XeroSyncStatus.FAILED,
            error_message=str(e),
        )
        await session.commit()
        return {
            "job_id": str(job_id),
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await session.close()


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.xero.sync_accounts",
    **SYNC_TASK_CONFIG,
)
def sync_xero_accounts(
    self: Task,
    job_id: str,
    connection_id: str,
    tenant_id: str,
    force_full: bool = False,
) -> dict[str, Any]:
    """Sync chart of accounts from Xero."""
    import asyncio

    return asyncio.run(
        _sync_accounts_async(
            self,
            UUID(job_id),
            UUID(connection_id),
            UUID(tenant_id),
            force_full,
        )
    )


async def _sync_accounts_async(
    task: Task,
    job_id: UUID,
    connection_id: UUID,
    tenant_id: UUID,
    force_full: bool,
) -> dict[str, Any]:
    """Async implementation of accounts sync."""
    settings = get_settings()
    session = await _get_async_session()

    try:
        await _set_tenant_context(session, tenant_id)
        await _update_job_status(session, job_id, XeroSyncStatus.IN_PROGRESS)

        conn_repo = XeroConnectionRepository(session)
        connection = await conn_repo.get_by_id(connection_id)

        if not connection:
            raise XeroConnectionInactiveError(connection_id)

        # Accounts don't support modified_since, always full sync
        data_service = XeroDataService(session, settings)
        result = await data_service.sync_accounts(connection_id)

        status = XeroSyncStatus.COMPLETED if not result.error_message else XeroSyncStatus.FAILED
        await _update_job_status(
            session,
            job_id,
            status,
            error_message=result.error_message,
            progress_details={"entity": "accounts"},
            records_processed=result.records_processed,
            records_created=result.records_created,
            records_updated=result.records_updated,
            records_failed=result.records_failed,
        )

        await conn_repo.update(
            connection_id,
            XeroConnectionUpdate(last_used_at=datetime.now(UTC)),
        )
        await session.commit()

        logger.info(
            f"Accounts sync completed for connection {connection_id}: "
            f"{result.records_processed} processed"
        )

        return {
            "job_id": str(job_id),
            "status": status.value,
            "records_processed": result.records_processed,
            "records_created": result.records_created,
            "records_updated": result.records_updated,
            "records_failed": result.records_failed,
            "error_message": result.error_message,
        }

    except XeroRateLimitExceededError as e:
        logger.warning(f"Rate limit exceeded for accounts sync: {e}")
        await _update_job_status(
            session,
            job_id,
            XeroSyncStatus.PENDING,
            error_message=f"Rate limited, will retry: {e}",
        )
        await session.commit()
        raise

    except Exception as e:
        logger.error(f"Accounts sync failed: {e}")
        await session.rollback()
        await _update_job_status(
            session,
            job_id,
            XeroSyncStatus.FAILED,
            error_message=str(e),
        )
        await session.commit()
        return {
            "job_id": str(job_id),
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await session.close()


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.xero.run_sync",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    autoretry_for=(XeroRateLimitExceededError, ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def run_sync(
    self: Task,
    job_id: str,
    sync_type: str = "full",
    force_full: bool = False,
) -> dict[str, Any]:
    """Run a full sync operation (DEPRECATED).

    .. deprecated::
        Use ``run_phased_sync`` instead. This legacy task runs all entity
        syncs sequentially in a single Celery task and does not support
        per-entity progress tracking, parallel entity execution, or
        post-sync task dispatching. Retained as a fallback only.

    Args:
        job_id: Sync job ID.
        sync_type: Type of sync (full, contacts, invoices, etc).
        force_full: Force full sync ignoring timestamps.

    Returns:
        Dict with aggregated sync results.
    """
    import asyncio

    warnings.warn(
        "run_sync is deprecated; use run_phased_sync instead. "
        "This task will be removed in a future release.",
        DeprecationWarning,
        stacklevel=1,
    )
    logger.warning(
        "Legacy run_sync task invoked for job %s. Callers should migrate to run_phased_sync.",
        job_id,
    )

    return asyncio.run(
        _run_sync_async(
            self,
            UUID(job_id),
            XeroSyncType(sync_type),
            force_full,
        )
    )


async def _run_sync_async(
    task: Task,
    job_id: UUID,
    sync_type: XeroSyncType,
    force_full: bool,
) -> dict[str, Any]:
    """Async implementation of full sync orchestration."""
    settings = get_settings()
    session = await _get_async_session()

    try:
        # Get job to find connection and tenant
        job_repo = XeroSyncJobRepository(session)
        job = await job_repo.get_by_id(job_id)

        if not job:
            raise ValueError(f"Sync job {job_id} not found")

        connection_id = job.connection_id
        tenant_id = job.tenant_id

        await _set_tenant_context(session, tenant_id)
        await _update_job_status(session, job_id, XeroSyncStatus.IN_PROGRESS)

        conn_repo = XeroConnectionRepository(session)
        connection = await conn_repo.get_by_id(connection_id)

        if not connection:
            raise XeroConnectionInactiveError(connection_id)

        data_service = XeroDataService(session, settings)

        # Initialize aggregated results
        total_processed = 0
        total_created = 0
        total_updated = 0
        total_failed = 0
        progress_details: dict[str, Any] = {}
        error_messages: list[str] = []

        # Define sync order based on sync_type
        if sync_type == XeroSyncType.FULL:
            entity_syncs = [
                ("accounts", data_service.sync_accounts, None),
                (
                    "contacts",
                    data_service.sync_contacts,
                    connection.last_contacts_sync_at if not force_full else None,
                ),
                (
                    "invoices",
                    data_service.sync_invoices,
                    connection.last_invoices_sync_at if not force_full else None,
                ),
                (
                    "bank_transactions",
                    data_service.sync_bank_transactions,
                    connection.last_transactions_sync_at if not force_full else None,
                ),
                # Spec 024: Credit Notes, Payments, Journals
                ("credit_notes", data_service.sync_credit_notes, None),
                ("payments", data_service.sync_payments, None),
                ("overpayments", data_service.sync_overpayments, None),
                ("prepayments", data_service.sync_prepayments, None),
                ("journals", data_service.sync_journals, None),
                ("manual_journals", data_service.sync_manual_journals, None),
                # Spec 025: Purchase Orders, Repeating Invoices, Tracking Categories, Quotes
                ("purchase_orders", data_service.sync_purchase_orders, None),
                ("repeating_invoices", data_service.sync_repeating_invoices, None),
                ("tracking_categories", data_service.sync_tracking_categories, None),
                ("quotes", data_service.sync_quotes, None),
            ]
            # Include payroll sync if connection has payroll access
            include_payroll = connection.has_payroll_access
            # Check if connection has assets scope (Spec 025)
            has_assets_scope = any("assets" in scope.lower() for scope in (connection.scopes or []))
        elif sync_type == XeroSyncType.CONTACTS:
            entity_syncs = [
                (
                    "contacts",
                    data_service.sync_contacts,
                    connection.last_contacts_sync_at if not force_full else None,
                ),
            ]
            include_payroll = False
            has_assets_scope = False
        elif sync_type == XeroSyncType.INVOICES:
            entity_syncs = [
                (
                    "invoices",
                    data_service.sync_invoices,
                    connection.last_invoices_sync_at if not force_full else None,
                ),
            ]
            include_payroll = False
            has_assets_scope = False
        elif sync_type == XeroSyncType.BANK_TRANSACTIONS:
            entity_syncs = [
                (
                    "bank_transactions",
                    data_service.sync_bank_transactions,
                    connection.last_transactions_sync_at if not force_full else None,
                ),
            ]
            include_payroll = False
            has_assets_scope = False
        elif sync_type == XeroSyncType.ACCOUNTS:
            entity_syncs = [
                ("accounts", data_service.sync_accounts, None),
            ]
            include_payroll = False
            has_assets_scope = False
        elif (
            sync_type == XeroSyncType.PAYROLL
            or sync_type == XeroSyncType.EMPLOYEES
            or sync_type == XeroSyncType.PAY_RUNS
        ):
            entity_syncs = []
            include_payroll = connection.has_payroll_access
            has_assets_scope = False
        else:
            entity_syncs = []
            include_payroll = False
            has_assets_scope = False

        # Execute syncs in order
        # Entities that don't support modified_since parameter
        no_modified_since_entities = {
            "accounts",
            "purchase_orders",
            "repeating_invoices",
            "tracking_categories",
            "quotes",
        }
        for entity_name, sync_func, modified_since in entity_syncs:
            try:
                logger.info(f"Starting {entity_name} sync for job {job_id}")

                if entity_name in no_modified_since_entities:
                    result = await sync_func(connection_id)
                else:
                    result = await sync_func(connection_id, modified_since=modified_since)

                progress_details[entity_name] = {
                    "processed": result.records_processed,
                    "created": result.records_created,
                    "updated": result.records_updated,
                    "failed": result.records_failed,
                    "status": "completed" if not result.error_message else "failed",
                }

                total_processed += result.records_processed
                total_created += result.records_created
                total_updated += result.records_updated
                total_failed += result.records_failed

                if result.error_message:
                    error_messages.append(f"{entity_name}: {result.error_message}")

                # Update job progress after each entity
                await _update_job_status(
                    session,
                    job_id,
                    XeroSyncStatus.IN_PROGRESS,
                    progress_details=progress_details,
                    records_processed=total_processed,
                    records_created=total_created,
                    records_updated=total_updated,
                    records_failed=total_failed,
                )

                logger.info(
                    f"Completed {entity_name} sync: {result.records_processed} records processed"
                )

            except XeroRateLimitExceededError:
                # Re-raise rate limit errors for Celery retry
                raise

            except Exception as e:
                logger.error(f"Failed to sync {entity_name}: {e}")
                error_messages.append(f"{entity_name}: {e!s}")
                progress_details[entity_name] = {"status": "failed", "error": str(e)}
                # Continue with other entity types

        # Sync payroll if included and connection has access
        if include_payroll:
            try:
                from app.modules.integrations.xero.payroll_service import XeroPayrollService

                logger.info(f"Starting payroll sync for job {job_id}")
                payroll_service = XeroPayrollService(session, settings)
                payroll_result = await payroll_service.sync_payroll(connection_id)

                employees_synced = payroll_result.get("employees_synced", 0)
                pay_runs_synced = payroll_result.get("pay_runs_synced", 0)

                progress_details["payroll"] = {
                    "employees_synced": employees_synced,
                    "pay_runs_synced": pay_runs_synced,
                    "status": payroll_result.get("status", "complete"),
                    "reason": payroll_result.get("reason"),
                }

                total_processed += employees_synced + pay_runs_synced

                # Update job progress
                await _update_job_status(
                    session,
                    job_id,
                    XeroSyncStatus.IN_PROGRESS,
                    progress_details=progress_details,
                    records_processed=total_processed,
                    records_created=total_created,
                    records_updated=total_updated,
                    records_failed=total_failed,
                )

                logger.info(
                    f"Completed payroll sync: "
                    f"{employees_synced} employees, {pay_runs_synced} pay runs"
                )

            except Exception as e:
                logger.error(f"Failed to sync payroll: {e}")
                error_messages.append(f"payroll: {e!s}")
                progress_details["payroll"] = {"status": "failed", "error": str(e)}

        # Sync fixed assets if connection has assets scope (Spec 025)
        if has_assets_scope:
            try:
                logger.info(f"Starting assets sync for job {job_id}")

                # Sync asset types first (required for asset references)
                asset_types_result = await data_service.sync_asset_types(connection_id)
                progress_details["asset_types"] = {
                    "processed": asset_types_result.records_processed,
                    "created": asset_types_result.records_created,
                    "updated": asset_types_result.records_updated,
                    "failed": asset_types_result.records_failed,
                    "status": "completed" if not asset_types_result.error_message else "failed",
                }
                total_processed += asset_types_result.records_processed
                total_created += asset_types_result.records_created
                total_updated += asset_types_result.records_updated

                if asset_types_result.error_message:
                    error_messages.append(f"asset_types: {asset_types_result.error_message}")

                # Sync assets
                assets_result = await data_service.sync_assets(connection_id)
                progress_details["assets"] = {
                    "processed": assets_result.records_processed,
                    "created": assets_result.records_created,
                    "updated": assets_result.records_updated,
                    "failed": assets_result.records_failed,
                    "status": "completed" if not assets_result.error_message else "failed",
                }
                total_processed += assets_result.records_processed
                total_created += assets_result.records_created
                total_updated += assets_result.records_updated

                if assets_result.error_message:
                    error_messages.append(f"assets: {assets_result.error_message}")

                # Update job progress
                await _update_job_status(
                    session,
                    job_id,
                    XeroSyncStatus.IN_PROGRESS,
                    progress_details=progress_details,
                    records_processed=total_processed,
                    records_created=total_created,
                    records_updated=total_updated,
                    records_failed=total_failed,
                )

                logger.info(
                    f"Completed assets sync: "
                    f"{asset_types_result.records_processed} asset types, "
                    f"{assets_result.records_processed} assets"
                )

            except Exception as e:
                logger.error(f"Failed to sync assets: {e}")
                error_messages.append(f"assets: {e!s}")
                progress_details["assets"] = {"status": "failed", "error": str(e)}

        # Sync organisation profile (for client context chat)
        # This fetches entity type, ABN, GST status from Xero Organisation API
        if sync_type == XeroSyncType.FULL:
            try:
                logger.info(f"Syncing organisation profile for connection {connection_id}")
                org_data = await data_service.sync_organisation_profile(connection_id)

                if org_data:
                    progress_details["organisation_profile"] = {
                        "status": "completed",
                        "entity_type": org_data.get("OrganisationType"),
                        "gst_registered": bool(
                            org_data.get("TaxNumber") and org_data.get("SalesTaxBasis")
                        ),
                    }
                    logger.info(
                        f"Organisation profile synced: type={org_data.get('OrganisationType')}"
                    )
                else:
                    progress_details["organisation_profile"] = {
                        "status": "skipped",
                        "reason": "No organisation data returned",
                    }

            except Exception as e:
                logger.warning(f"Failed to sync organisation profile: {e}")
                # Don't add to error_messages - this is non-critical
                progress_details["organisation_profile"] = {
                    "status": "failed",
                    "error": str(e),
                }

        # Determine final status
        if not error_messages:
            final_status = XeroSyncStatus.COMPLETED
            error_message = None
        elif total_processed > 0:
            # Partial success
            final_status = XeroSyncStatus.COMPLETED
            error_message = "; ".join(error_messages)
        else:
            final_status = XeroSyncStatus.FAILED
            error_message = "; ".join(error_messages)

        # Final job update
        await _update_job_status(
            session,
            job_id,
            final_status,
            error_message=error_message,
            progress_details=progress_details,
            records_processed=total_processed,
            records_created=total_created,
            records_updated=total_updated,
            records_failed=total_failed,
        )

        # Update connection timestamps based on what was synced
        now = datetime.now(UTC)
        update_data = XeroConnectionUpdate(last_used_at=now)

        if sync_type == XeroSyncType.FULL:
            update_data.last_full_sync_at = now
            update_data.last_accounts_sync_at = now
            update_data.last_contacts_sync_at = now
            update_data.last_invoices_sync_at = now
            update_data.last_transactions_sync_at = now
            if include_payroll:
                update_data.last_payroll_sync_at = now
                update_data.last_employees_sync_at = now
        elif sync_type == XeroSyncType.PAYROLL:
            update_data.last_payroll_sync_at = now
            update_data.last_employees_sync_at = now
        elif sync_type == XeroSyncType.EMPLOYEES:
            update_data.last_employees_sync_at = now
        elif sync_type == XeroSyncType.PAY_RUNS:
            update_data.last_payroll_sync_at = now
        elif sync_type == XeroSyncType.CONTACTS:
            update_data.last_contacts_sync_at = now
        elif sync_type == XeroSyncType.INVOICES:
            update_data.last_invoices_sync_at = now
        elif sync_type == XeroSyncType.BANK_TRANSACTIONS:
            update_data.last_transactions_sync_at = now
        elif sync_type == XeroSyncType.ACCOUNTS:
            update_data.last_accounts_sync_at = now

        await conn_repo.update(connection_id, update_data)
        await session.commit()

        logger.info(
            f"Sync job {job_id} completed with status {final_status.value}: "
            f"{total_processed} total records processed"
        )

        # Trigger post-sync calculations asynchronously
        if final_status == XeroSyncStatus.COMPLETED:
            try:
                from app.tasks.quality import calculate_quality_score

                calculate_quality_score.delay(
                    connection_id=str(connection_id),
                    trigger_reason="sync",
                )
                logger.info(f"Quality calculation triggered for connection {connection_id}")
            except Exception as e:
                logger.warning(f"Failed to trigger quality calculation: {e}")

            # Trigger BAS calculation for recent quarters
            try:
                from app.tasks.bas import calculate_bas_periods

                calculate_bas_periods.delay(
                    connection_id=str(connection_id),
                    tenant_id=str(tenant_id),
                    num_quarters=6,
                    trigger_reason="sync",
                )
                logger.info(f"BAS calculation triggered for connection {connection_id}")
            except Exception as e:
                logger.warning(f"Failed to trigger BAS calculation: {e}")

            # Trigger client AI context aggregation (Spec 013)
            try:
                from app.tasks.aggregation import compute_aggregations

                compute_aggregations.delay(
                    connection_id=str(connection_id),
                    tenant_id=str(tenant_id),
                    trigger_reason="sync",
                )
                logger.info(f"Aggregation triggered for connection {connection_id}")
            except Exception as e:
                logger.warning(f"Failed to trigger aggregation: {e}")

            # Trigger insight generation (Spec 016)
            # Generates proactive insights after data sync completes
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

            # Evaluate data triggers (Spec 017)
            # Checks data threshold triggers and generates insights if conditions met
            try:
                from app.tasks.triggers import evaluate_data_triggers

                evaluate_data_triggers.delay(
                    connection_id=str(connection_id),
                    tenant_id=str(tenant_id),
                )
                logger.info(f"Data trigger evaluation triggered for connection {connection_id}")
            except Exception as e:
                logger.warning(f"Failed to trigger data trigger evaluation: {e}")

            # Check and send usage threshold alerts (Spec 020)
            # Sends email alerts at 80%, 90%, or 100% of client limit
            if total_created > 0:  # Only check if new clients were created
                try:
                    from sqlalchemy import select

                    from app.modules.auth.models import Tenant
                    from app.modules.billing.usage_alerts import UsageAlertService

                    tenant = await session.scalar(select(Tenant).where(Tenant.id == tenant_id))
                    if tenant:
                        alert_service = UsageAlertService(session)
                        alerts_sent = await alert_service.check_and_send_threshold_alerts(tenant)
                        if alerts_sent:
                            logger.info(
                                f"Usage alerts sent for tenant {tenant_id}: "
                                f"{[a.value for a in alerts_sent]}"
                            )
                except Exception as e:
                    logger.warning(f"Failed to check usage alerts: {e}")

        return {
            "job_id": str(job_id),
            "status": final_status.value,
            "records_processed": total_processed,
            "records_created": total_created,
            "records_updated": total_updated,
            "records_failed": total_failed,
            "progress_details": progress_details,
            "error_message": error_message,
        }

    except XeroRateLimitExceededError as e:
        logger.warning(f"Rate limit exceeded during sync: {e}")
        await _update_job_status(
            session,
            job_id,
            XeroSyncStatus.PENDING,
            error_message=f"Rate limited, will retry: {e}",
        )
        await session.commit()
        raise

    except Exception as e:
        logger.error(f"Sync job {job_id} failed: {e}")
        await session.rollback()
        await _update_job_status(
            session,
            job_id,
            XeroSyncStatus.FAILED,
            error_message=str(e),
        )
        await session.commit()
        return {
            "job_id": str(job_id),
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await session.close()


# =============================================================================
# Payroll Sync Tasks
# =============================================================================


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.xero.sync_payroll",
    **SYNC_TASK_CONFIG,
)
def sync_xero_payroll(
    self: Task,
    connection_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    """Sync payroll data (employees and pay runs) from Xero.

    This task syncs:
    - Employees from Xero Payroll API
    - Pay runs with PAYG withholding data

    Only runs for connections with payroll access enabled.

    Args:
        connection_id: Xero connection ID.
        tenant_id: Tenant ID for RLS context.

    Returns:
        Dict with sync results including employees_synced and pay_runs_synced.
    """
    import asyncio

    return asyncio.run(
        _sync_payroll_async(
            self,
            UUID(connection_id),
            UUID(tenant_id),
        )
    )


async def _sync_payroll_async(
    task: Task,
    connection_id: UUID,
    tenant_id: UUID,
) -> dict[str, Any]:
    """Async implementation of payroll sync."""
    from app.modules.integrations.xero.payroll_service import XeroPayrollService

    settings = get_settings()
    session = await _get_async_session()

    try:
        await _set_tenant_context(session, tenant_id)

        # Perform payroll sync
        payroll_service = XeroPayrollService(session, settings)
        result = await payroll_service.sync_payroll(connection_id)

        logger.info(
            f"Payroll sync completed for connection {connection_id}: "
            f"{result.get('employees_synced', 0)} employees, "
            f"{result.get('pay_runs_synced', 0)} pay runs"
        )

        # Spec 059 FR-006 — recompute tax position on any recent plan that was
        # created while payroll sync was still in flight. The sync itself
        # arrives after the plan was returned to the UI with status=pending;
        # the frontend's next poll will pick up the refreshed numbers.
        try:
            from datetime import UTC, datetime, timedelta

            from sqlalchemy import select

            from app.modules.tax_planning.models import TaxPlan
            from app.modules.tax_planning.service import TaxPlanningService

            recent_cutoff = datetime.now(UTC) - timedelta(hours=2)
            plans_result = await session.execute(
                select(TaxPlan).where(
                    TaxPlan.xero_connection_id == connection_id,
                    TaxPlan.created_at >= recent_cutoff,
                )
            )
            recent_plans = list(plans_result.scalars().all())
            if recent_plans:
                tax_planning_service = TaxPlanningService(session, settings)
                for plan in recent_plans:
                    try:
                        await tax_planning_service.recompute_tax_position(plan.id, plan.tenant_id)
                    except Exception:
                        logger.warning(
                            "Tax position recompute failed for plan %s after payroll sync",
                            plan.id,
                            exc_info=True,
                        )
                await session.commit()
        except Exception:
            logger.warning(
                "Post-payroll-sync tax position recompute pass failed",
                exc_info=True,
            )

        return {
            "connection_id": str(connection_id),
            "status": result.get("status", "complete"),
            "employees_synced": result.get("employees_synced", 0),
            "pay_runs_synced": result.get("pay_runs_synced", 0),
            "reason": result.get("reason"),
        }

    except Exception as e:
        logger.error(f"Payroll sync failed for connection {connection_id}: {e}")
        return {
            "connection_id": str(connection_id),
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await session.close()


# =============================================================================
# Phased Sync Tasks (Spec 043: Progressive Xero Data Sync)
# =============================================================================

# Mapping of entity type strings to their XeroDataService method names.
# Used by sync_entity to resolve the correct sync function.
ENTITY_SYNC_MAP: dict[str, str] = {
    "accounts": "sync_accounts",
    "contacts": "sync_contacts",
    "invoices": "sync_invoices",
    "bank_transactions": "sync_bank_transactions",
    "credit_notes": "sync_credit_notes",
    "payments": "sync_payments",
    "overpayments": "sync_overpayments",
    "prepayments": "sync_prepayments",
    "journals": "sync_journals",
    "manual_journals": "sync_manual_journals",
    "purchase_orders": "sync_purchase_orders",
    "repeating_invoices": "sync_repeating_invoices",
    "tracking_categories": "sync_tracking_categories",
    "quotes": "sync_quotes",
}

# Entities that do NOT support the If-Modified-Since header.
# These always perform a full sync regardless of modified_since parameter.
NO_MODIFIED_SINCE_ENTITIES: set[str] = {
    "accounts",
    "purchase_orders",
    "repeating_invoices",
    "tracking_categories",
    "quotes",
}

# Phase definitions for phased sync orchestration.
# Phase 1: Essential data needed for immediate display
# Phase 2: Recent transactional data
# Phase 3: Full historical and reference data
SYNC_PHASES: dict[int, list[str]] = {
    1: ["accounts", "contacts", "invoices"],
    2: ["bank_transactions", "payments", "credit_notes", "overpayments", "prepayments"],
    3: [
        "journals",
        "manual_journals",
        "purchase_orders",
        "repeating_invoices",
        "tracking_categories",
        "quotes",
    ],
}

# Total number of sync phases
TOTAL_SYNC_PHASES = len(SYNC_PHASES)


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.xero.sync_entity",
    # Rate limit: max 30 entity syncs per minute per worker.
    # Each entity sync may make multiple paginated Xero API calls.
    # Xero allows 60 calls/minute — 30/m leaves headroom for retries and other calls.
    rate_limit="30/m",
    # Disable time limits: BankTransactions can have 100+ pages at ~40s each
    # from Xero API (~70+ min). Larger accounts take even longer.
    # The cleanup_stuck_sync_jobs scheduler (every 15 min) handles stuck tasks.
    soft_time_limit=None,
    time_limit=None,
    **SYNC_TASK_CONFIG,
)
def sync_entity(
    self: Task,
    job_id: str,
    entity_type: str,
    connection_id: str,
    tenant_id: str,
    modified_since: str | None = None,
    force_full: bool = False,
    max_new_clients: int | None = None,
) -> dict[str, Any]:
    """Sync a single entity type from Xero with its own isolated DB session.

    This is the generic per-entity sync task used by the phased sync orchestrator.
    Each entity runs in its own Celery task with independent error handling and
    progress tracking via XeroSyncEntityProgress records.

    Args:
        job_id: Parent sync job ID.
        entity_type: Entity type to sync (e.g., 'contacts', 'invoices').
        connection_id: Xero connection ID.
        tenant_id: Tenant ID for RLS context.
        modified_since: ISO format datetime for incremental sync. Ignored
            for entities that don't support If-Modified-Since.
        force_full: Force full sync ignoring timestamps.
        max_new_clients: Maximum new clients to create (contacts only).

    Returns:
        Dict with entity_type, status, record counts, and error_message.
    """
    import asyncio

    return asyncio.run(
        _sync_entity_async(
            self,
            UUID(job_id),
            entity_type,
            UUID(connection_id),
            UUID(tenant_id),
            modified_since,
            force_full,
            max_new_clients,
        )
    )


async def _sync_entity_async(
    task: Task,
    job_id: UUID,
    entity_type: str,
    connection_id: UUID,
    tenant_id: UUID,
    modified_since_iso: str | None,
    force_full: bool,
    max_new_clients: int | None,
) -> dict[str, Any]:
    """Async implementation of generic per-entity sync.

    Creates its own DB session, updates XeroSyncEntityProgress records,
    and publishes progress via Redis pub/sub.
    """
    from app.modules.integrations.xero.models import XeroSyncEntityProgressStatus
    from app.modules.integrations.xero.repository import XeroSyncEntityProgressRepository
    from app.modules.integrations.xero.sync_progress import SyncProgressPublisher

    settings = get_settings()
    session = await _get_async_session()
    publisher = SyncProgressPublisher()

    try:
        await _set_tenant_context(session, tenant_id)

        # Validate entity type
        sync_method_name = ENTITY_SYNC_MAP.get(entity_type)
        if not sync_method_name:
            raise ValueError(f"Unknown entity type: {entity_type}")

        # Look up the entity progress record for this job + entity
        progress_repo = XeroSyncEntityProgressRepository(session)
        entity_progress = await progress_repo.get_by_job_and_entity(job_id, entity_type)

        if not entity_progress:
            raise ValueError(
                f"No XeroSyncEntityProgress record found for job={job_id}, entity={entity_type}"
            )

        # Mark entity as in-progress
        start_time = datetime.now(UTC)
        await progress_repo.update_status(
            entity_progress.id,
            XeroSyncEntityProgressStatus.IN_PROGRESS,
            started_at=start_time,
        )
        await session.commit()

        logger.info(
            "Entity sync started",
            extra={
                "entity_type": entity_type,
                "job_id": str(job_id),
                "connection_id": str(connection_id),
                "tenant_id": str(tenant_id),
                "force_full": force_full,
                "has_modified_since": modified_since_iso is not None,
            },
        )

        # Publish entity progress: in_progress
        await publisher.publish_entity_progress(
            connection_id=connection_id,
            entity_type=entity_type,
            status="in_progress",
        )

        # Parse modified_since from ISO string
        modified_since_dt: datetime | None = None
        if modified_since_iso and not force_full and entity_type not in NO_MODIFIED_SINCE_ENTITIES:
            modified_since_dt = datetime.fromisoformat(modified_since_iso)

        # Create the data service and resolve the sync method
        data_service = XeroDataService(session, settings)
        sync_method = getattr(data_service, sync_method_name)

        # Build keyword arguments based on entity type
        kwargs: dict[str, Any] = {"connection_id": connection_id}
        if entity_type in NO_MODIFIED_SINCE_ENTITIES:
            # These methods don't accept modified_since
            pass
        else:
            kwargs["modified_since"] = modified_since_dt

        # contacts accepts max_new_clients
        if entity_type == "contacts" and max_new_clients is not None:
            kwargs["max_new_clients"] = max_new_clients

        # Wire up a progress callback that publishes intermediate
        # entity_progress events after each page of records.
        def progress_callback(
            records_processed: int,
            records_created: int,
            records_updated: int,
        ) -> None:
            asyncio.create_task(
                publisher.publish_entity_progress(
                    connection_id=connection_id,
                    entity_type=entity_type,
                    status="in_progress",
                    records_processed=records_processed,
                    records_created=records_created,
                    records_updated=records_updated,
                )
            )

        kwargs["progress_callback"] = progress_callback

        # Execute the sync
        result = await sync_method(**kwargs)

        # Calculate duration
        end_time = datetime.now(UTC)
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        # Determine status based on result
        if result.error_message:
            entity_status = XeroSyncEntityProgressStatus.FAILED
            status_str = "failed"
        else:
            entity_status = XeroSyncEntityProgressStatus.COMPLETED
            status_str = "completed"

        # Update entity progress record with results
        await progress_repo.update_status(
            entity_progress.id,
            entity_status,
            records_processed=result.records_processed,
            records_created=result.records_created,
            records_updated=result.records_updated,
            records_failed=result.records_failed,
            error_message=result.error_message,
            completed_at=end_time,
            duration_ms=duration_ms,
        )
        await session.commit()

        # Update per-entity sync timestamp on connection so subsequent
        # incremental syncs use the correct If-Modified-Since value.
        if entity_status == XeroSyncEntityProgressStatus.COMPLETED:
            _ENTITY_TIMESTAMP_COLUMN: dict[str, str] = {
                "contacts": "last_contacts_sync_at",
                "invoices": "last_invoices_sync_at",
                "bank_transactions": "last_transactions_sync_at",
                "credit_notes": "last_credit_notes_sync_at",
                "payments": "last_payments_sync_at",
                "overpayments": "last_overpayments_sync_at",
                "prepayments": "last_prepayments_sync_at",
                "journals": "last_journals_sync_at",
                "manual_journals": "last_manual_journals_sync_at",
                "accounts": "last_accounts_sync_at",
            }
            ts_column = _ENTITY_TIMESTAMP_COLUMN.get(entity_type)
            if ts_column:
                await session.execute(
                    text(
                        f"UPDATE xero_connections SET {ts_column} = :now WHERE id = :conn_id"
                    ).bindparams(now=end_time, conn_id=connection_id)
                )
                await session.commit()

        # Publish entity progress: completed/failed
        await publisher.publish_entity_progress(
            connection_id=connection_id,
            entity_type=entity_type,
            status=status_str,
            records_processed=result.records_processed,
            records_created=result.records_created,
            records_updated=result.records_updated,
            records_failed=result.records_failed,
        )

        logger.info(
            "Entity sync completed",
            extra={
                "entity_type": entity_type,
                "job_id": str(job_id),
                "connection_id": str(connection_id),
                "tenant_id": str(tenant_id),
                "status": status_str,
                "records_processed": result.records_processed,
                "records_created": result.records_created,
                "records_updated": result.records_updated,
                "records_failed": result.records_failed,
                "duration_ms": duration_ms,
            },
        )

        return {
            "entity_type": entity_type,
            "status": status_str,
            "records_processed": result.records_processed,
            "records_created": result.records_created,
            "records_updated": result.records_updated,
            "records_failed": result.records_failed,
            "error_message": result.error_message,
        }

    except XeroRateLimitExceededError as e:
        logger.warning(
            "Rate limit exceeded during entity sync",
            extra={
                "entity_type": entity_type,
                "job_id": str(job_id),
                "connection_id": str(connection_id),
                "tenant_id": str(tenant_id),
                "rate_limit_error": str(e),
            },
        )
        # Update entity progress to reflect retry state
        try:
            progress_repo = XeroSyncEntityProgressRepository(session)
            entity_progress = await progress_repo.get_by_job_and_entity(job_id, entity_type)
            if entity_progress:
                await progress_repo.update_status(
                    entity_progress.id,
                    XeroSyncEntityProgressStatus.PENDING,
                    error_message=f"Rate limited, will retry: {e}",
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to update entity progress after rate limit")
        raise  # Re-raise for Celery auto-retry

    except Exception as e:
        logger.error(
            "Entity sync failed",
            extra={
                "entity_type": entity_type,
                "job_id": str(job_id),
                "connection_id": str(connection_id),
                "tenant_id": str(tenant_id),
                "error": str(e),
            },
        )
        # Map raw errors to user-friendly messages
        raw_error = str(e)
        user_message = _friendly_sync_error(raw_error)

        # Rollback failed transaction before attempting status update
        await session.rollback()
        # Update entity progress record with failure
        try:
            progress_repo = XeroSyncEntityProgressRepository(session)
            entity_progress = await progress_repo.get_by_job_and_entity(job_id, entity_type)
            if entity_progress:
                end_time = datetime.now(UTC)
                started = entity_progress.started_at or end_time
                duration_ms = int((end_time - started).total_seconds() * 1000)
                await progress_repo.update_status(
                    entity_progress.id,
                    XeroSyncEntityProgressStatus.FAILED,
                    error_message=user_message,
                    completed_at=end_time,
                    duration_ms=duration_ms,
                )
                await session.commit()

            # Publish failure event
            await publisher.publish_entity_progress(
                connection_id=connection_id,
                entity_type=entity_type,
                status="failed",
            )
        except Exception:
            logger.exception("Failed to update entity progress after error")

        return {
            "entity_type": entity_type,
            "status": "failed",
            "records_processed": 0,
            "records_created": 0,
            "records_updated": 0,
            "records_failed": 0,
            "error_message": user_message,
        }

    finally:
        await publisher.close()
        await session.close()


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.xero.run_phased_sync",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
)
def run_phased_sync(
    self: Task,
    job_id: str,
    connection_id: str,
    tenant_id: str,
    sync_type: str = "full",
    force_full: bool = False,
) -> dict[str, Any]:
    """Orchestrate a phased sync operation across multiple entity types.

    Uses a non-blocking chord/callback pattern: initializes the job, then
    dispatches Phase 1 as a chord with on_phase_complete as the callback.
    Each phase completion triggers the next phase or finalization.

    This avoids the previous blocking group.get() pattern that could
    deadlock when orchestrator + entity tasks exceeded worker_concurrency.

    Phase 1 (Essential): accounts, contacts, invoices
    Phase 2 (Recent): bank_transactions, payments, credit_notes,
                       overpayments, prepayments
    Phase 3 (Full): journals, manual_journals, purchase_orders,
                     repeating_invoices, tracking_categories, quotes

    After Phase 3, payroll (if connection has access) and org profile
    (for full syncs) are synced in the finalization task.

    Args:
        job_id: The sync job ID.
        connection_id: Xero connection ID.
        tenant_id: Tenant ID for RLS context.
        sync_type: Type of sync (full, contacts, etc.).
        force_full: Force full sync ignoring timestamps.

    Returns:
        Dict confirming the sync was initiated.
    """
    import asyncio

    return asyncio.run(
        _run_phased_sync_setup(
            UUID(job_id),
            UUID(connection_id),
            UUID(tenant_id),
            sync_type,
            force_full,
        )
    )


async def _run_phased_sync_setup(
    job_id: UUID,
    connection_id: UUID,
    tenant_id: UUID,
    sync_type: str,
    force_full: bool,
) -> dict[str, Any]:
    """Async setup for phased sync: initialize job then dispatch Phase 1 chord.

    This task returns immediately after dispatching the first phase,
    freeing its worker slot. Subsequent phases are chained via callbacks.
    """
    from app.modules.integrations.xero.repository import (
        XeroSyncEntityProgressRepository,
    )
    from app.modules.integrations.xero.sync_progress import SyncProgressPublisher

    session = await _get_async_session()
    publisher = SyncProgressPublisher()

    try:
        await _set_tenant_context(session, tenant_id)

        # =====================================================================
        # Job Initialization
        # =====================================================================

        conn_repo = XeroConnectionRepository(session)
        connection = await conn_repo.get_by_id(connection_id)

        if not connection:
            raise XeroConnectionInactiveError(connection_id)

        # Idempotency guard: if the job is already IN_PROGRESS (e.g. due to
        # task_acks_late requeue after worker crash), skip re-initialization
        # to prevent duplicate chord dispatches.
        job_repo = XeroSyncJobRepository(session)
        job_row = await session.execute(
            text("SELECT status FROM xero_sync_jobs WHERE id = :jid").bindparams(jid=job_id)
        )
        current_status = job_row.scalar_one_or_none()
        if current_status and current_status in ("in_progress", "completed"):
            logger.warning(
                "Job %s already %s, skipping duplicate orchestration",
                job_id,
                current_status,
            )
            return {
                "job_id": str(job_id),
                "status": "skipped",
                "reason": f"Job already {current_status}",
            }

        # Update job status to IN_PROGRESS
        await job_repo.update_status(job_id, XeroSyncStatus.IN_PROGRESS)
        await session.commit()

        # Emit audit event: sync started
        await _emit_sync_audit_event(
            session=session,
            event_type="integration.xero.sync.started",
            action="sync",
            outcome="success",
            tenant_id=tenant_id,
            connection_id=connection_id,
            job_id=job_id,
            metadata={
                "sync_type": sync_type,
                "force_full": force_full,
                "triggered_by": "user",
            },
        )

        # Build modified_since map for incremental sync
        entity_modified_since: dict[str, str | None] = {}
        if not force_full:
            timestamp_map: dict[str, datetime | None] = {
                "contacts": connection.last_contacts_sync_at,
                "invoices": connection.last_invoices_sync_at,
                "bank_transactions": connection.last_transactions_sync_at,
                "credit_notes": connection.last_credit_notes_sync_at,
                "payments": connection.last_payments_sync_at,
                "overpayments": connection.last_overpayments_sync_at,
                "prepayments": connection.last_prepayments_sync_at,
                "journals": connection.last_journals_sync_at,
                "manual_journals": connection.last_manual_journals_sync_at,
            }
            for entity, ts in timestamp_map.items():
                entity_modified_since[entity] = ts.isoformat() if ts else None

        # Determine total entities across all phases
        all_entities: list[str] = []
        for phase_entities in SYNC_PHASES.values():
            all_entities.extend(phase_entities)

        # Publish sync_started event
        await publisher.publish_sync_started(
            connection_id=connection_id,
            job_id=job_id,
            phase=1,
            total_entities=len(all_entities),
        )

        logger.info(
            "Phased sync started",
            extra={
                "job_id": str(job_id),
                "connection_id": str(connection_id),
                "tenant_id": str(tenant_id),
                "total_entities": len(all_entities),
                "total_phases": TOTAL_SYNC_PHASES,
                "force_full": force_full,
                "sync_type": sync_type,
            },
        )

        # =====================================================================
        # Dispatch Phase 1 as a chord (non-blocking)
        # =====================================================================

        first_phase = min(SYNC_PHASES.keys())
        _dispatch_phase_chord(
            session=session,
            job_id=job_id,
            connection_id=connection_id,
            tenant_id=tenant_id,
            phase_num=first_phase,
            entity_modified_since=entity_modified_since,
            force_full=force_full,
            sync_type=sync_type,
        )

        # Create entity progress records for Phase 1
        progress_repo = XeroSyncEntityProgressRepository(session)
        await progress_repo.bulk_create_for_job(
            job_id=job_id,
            tenant_id=tenant_id,
            entity_types=SYNC_PHASES[first_phase],
        )
        await session.execute(
            text("UPDATE xero_sync_jobs SET sync_phase = :phase WHERE id = :job_id").bindparams(
                phase=first_phase, job_id=job_id
            )
        )
        await session.commit()

        return {
            "job_id": str(job_id),
            "status": "initiated",
            "phase": first_phase,
            "message": "Phase 1 chord dispatched, orchestrator released.",
        }

    except Exception as e:
        logger.error("Phased sync setup failed for job %s: %s", job_id, e)
        await session.rollback()
        await _update_job_status(
            session,
            job_id,
            XeroSyncStatus.FAILED,
            error_message=str(e),
        )
        await session.commit()

        await _emit_sync_audit_event(
            session=session,
            event_type="integration.xero.sync.failed",
            action="sync",
            outcome="failure",
            tenant_id=tenant_id,
            connection_id=connection_id,
            job_id=job_id,
            metadata={"error": str(e), "sync_type": sync_type},
        )

        await publisher.publish_sync_failed(
            connection_id=connection_id,
            job_id=job_id,
            error=str(e),
        )

        return {
            "job_id": str(job_id),
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await publisher.close()
        await session.close()


def _dispatch_phase_chord(
    session: Any,
    job_id: UUID,
    connection_id: UUID,
    tenant_id: UUID,
    phase_num: int,
    entity_modified_since: dict[str, str | None],
    force_full: bool,
    sync_type: str,
) -> None:
    """Build and dispatch a chord for a sync phase.

    The chord runs all entity sync tasks in parallel, then calls
    on_phase_complete as the callback when all are done.
    """
    from celery import chord

    phase_entities = SYNC_PHASES[phase_num]

    entity_tasks = []
    for entity in phase_entities:
        task_kwargs: dict[str, Any] = {
            "job_id": str(job_id),
            "entity_type": entity,
            "connection_id": str(connection_id),
            "tenant_id": str(tenant_id),
            "modified_since": entity_modified_since.get(entity),
            "force_full": force_full,
        }
        entity_tasks.append(sync_entity.s(**task_kwargs))

    # The callback receives the list of entity results as first arg
    callback = on_phase_complete.s(
        job_id=str(job_id),
        connection_id=str(connection_id),
        tenant_id=str(tenant_id),
        phase_num=phase_num,
        entity_modified_since=entity_modified_since,
        force_full=force_full,
        sync_type=sync_type,
    )

    chord(entity_tasks)(callback)

    logger.info(
        "Dispatched phase %d chord with %d entities for job %s",
        phase_num,
        len(entity_tasks),
        job_id,
    )


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.xero.on_phase_complete",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def on_phase_complete(
    self: Task,
    phase_results: list[dict[str, Any]],
    job_id: str,
    connection_id: str,
    tenant_id: str,
    phase_num: int,
    entity_modified_since: dict[str, str | None],
    force_full: bool,
    sync_type: str,
) -> dict[str, Any]:
    """Callback after a sync phase completes. Aggregates results and chains.

    Called automatically by Celery chord when all entity tasks in a phase
    finish. Aggregates results, dispatches post-sync tasks, then either
    starts the next phase chord or calls finalize_sync_job.

    Args:
        phase_results: List of result dicts from sync_entity tasks.
        job_id: Sync job ID.
        connection_id: Xero connection ID.
        tenant_id: Tenant ID.
        phase_num: The phase that just completed.
        entity_modified_since: Modified-since timestamps for incremental sync.
        force_full: Whether to force full sync.
        sync_type: Type of sync.

    Returns:
        Dict with phase aggregation results.
    """
    import asyncio

    return asyncio.run(
        _on_phase_complete_async(
            phase_results=phase_results,
            job_id=UUID(job_id),
            connection_id=UUID(connection_id),
            tenant_id=UUID(tenant_id),
            phase_num=phase_num,
            entity_modified_since=entity_modified_since,
            force_full=force_full,
            sync_type=sync_type,
        )
    )


async def _on_phase_complete_async(
    phase_results: list[dict[str, Any]],
    job_id: UUID,
    connection_id: UUID,
    tenant_id: UUID,
    phase_num: int,
    entity_modified_since: dict[str, str | None],
    force_full: bool,
    sync_type: str,
) -> dict[str, Any]:
    """Async implementation of phase completion callback."""
    from app.modules.integrations.xero.repository import (
        XeroSyncEntityProgressRepository,
    )
    from app.modules.integrations.xero.sync_progress import SyncProgressPublisher

    session = await _get_async_session()
    publisher = SyncProgressPublisher()

    try:
        await _set_tenant_context(session, tenant_id)

        # =================================================================
        # Aggregate phase results
        # =================================================================

        phase_processed = 0
        phase_created = 0
        phase_updated = 0
        phase_failed = 0
        phase_entities_completed = 0
        error_messages: list[str] = []
        progress_details: dict[str, Any] = {}

        for result in phase_results:
            if isinstance(result, dict):
                entity_name = result.get("entity_type", "unknown")
                progress_details[entity_name] = {
                    "processed": result.get("records_processed", 0),
                    "created": result.get("records_created", 0),
                    "updated": result.get("records_updated", 0),
                    "failed": result.get("records_failed", 0),
                    "status": result.get("status", "unknown"),
                }

                phase_processed += result.get("records_processed", 0)
                phase_created += result.get("records_created", 0)
                phase_updated += result.get("records_updated", 0)
                phase_failed += result.get("records_failed", 0)

                if result.get("status") == "completed":
                    phase_entities_completed += 1
                elif result.get("error_message"):
                    error_messages.append(f"{entity_name}: {result['error_message']}")
            elif isinstance(result, Exception):
                error_messages.append(f"Phase {phase_num} task error: {result}")

        # =================================================================
        # Update job progress in DB (accumulate with previous phases)
        # =================================================================

        job_repo = XeroSyncJobRepository(session)
        # Read current job to accumulate totals across phases
        job = await session.execute(
            text(
                "SELECT records_processed, records_created, records_updated, "
                "records_failed, progress_details FROM xero_sync_jobs WHERE id = :jid"
            ).bindparams(jid=job_id)
        )
        job_row = job.one_or_none()

        cumulative_processed = (job_row.records_processed or 0) + phase_processed
        cumulative_created = (job_row.records_created or 0) + phase_created
        cumulative_updated = (job_row.records_updated or 0) + phase_updated
        cumulative_failed = (job_row.records_failed or 0) + phase_failed
        cumulative_details = dict(job_row.progress_details or {})
        cumulative_details.update(progress_details)

        await job_repo.update_progress(
            job_id,
            records_processed=cumulative_processed,
            records_created=cumulative_created,
            records_updated=cumulative_updated,
            records_failed=cumulative_failed,
            progress_details=cumulative_details,
        )
        await session.commit()

        # Publish phase_complete event
        next_phase = phase_num + 1 if phase_num < TOTAL_SYNC_PHASES else None
        await publisher.publish_phase_complete(
            connection_id=connection_id,
            phase=phase_num,
            next_phase=next_phase,
            entities_completed=phase_entities_completed,
            records_processed=phase_processed,
        )

        logger.info(
            "Sync phase completed",
            extra={
                "phase": phase_num,
                "total_phases": TOTAL_SYNC_PHASES,
                "job_id": str(job_id),
                "connection_id": str(connection_id),
                "entities_completed": phase_entities_completed,
                "records_processed": phase_processed,
                "next_phase": next_phase,
            },
        )

        # Dispatch post-sync tasks for this phase
        if not error_messages or phase_entities_completed > 0:
            await _dispatch_post_sync_tasks(
                session=session,
                publisher=publisher,
                connection_id=connection_id,
                tenant_id=tenant_id,
                job_id=job_id,
                phase_num=phase_num,
            )

        # =================================================================
        # Chain: start next phase or finalize
        # =================================================================

        if next_phase and next_phase in SYNC_PHASES:
            # Create entity progress records for next phase
            progress_repo = XeroSyncEntityProgressRepository(session)
            await progress_repo.bulk_create_for_job(
                job_id=job_id,
                tenant_id=tenant_id,
                entity_types=SYNC_PHASES[next_phase],
            )
            await session.execute(
                text("UPDATE xero_sync_jobs SET sync_phase = :phase WHERE id = :job_id").bindparams(
                    phase=next_phase, job_id=job_id
                )
            )
            await session.commit()

            # Dispatch next phase chord
            _dispatch_phase_chord(
                session=session,
                job_id=job_id,
                connection_id=connection_id,
                tenant_id=tenant_id,
                phase_num=next_phase,
                entity_modified_since=entity_modified_since,
                force_full=force_full,
                sync_type=sync_type,
            )

            logger.info(
                "Chained to phase %d for job %s",
                next_phase,
                job_id,
            )
        else:
            # All phases done — dispatch finalization task
            finalize_sync_job.delay(
                job_id=str(job_id),
                connection_id=str(connection_id),
                tenant_id=str(tenant_id),
                sync_type=sync_type,
            )
            logger.info(
                "All phases complete, dispatched finalization for job %s",
                job_id,
            )

        return {
            "job_id": str(job_id),
            "phase": phase_num,
            "status": "phase_complete",
            "entities_completed": phase_entities_completed,
            "records_processed": phase_processed,
            "next_phase": next_phase,
        }

    except Exception as e:
        logger.error(
            "Phase %d callback failed for job %s: %s",
            phase_num,
            job_id,
            e,
        )
        await session.rollback()
        # Mark job as failed
        await _update_job_status(
            session,
            job_id,
            XeroSyncStatus.FAILED,
            error_message=f"Phase {phase_num} callback error: {e}",
        )
        await session.commit()
        await publisher.publish_sync_failed(
            connection_id=connection_id,
            job_id=job_id,
            error=f"Phase {phase_num} callback: {e}",
        )
        return {
            "job_id": str(job_id),
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await publisher.close()
        await session.close()


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.xero.finalize_sync_job",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def finalize_sync_job(
    self: Task,
    job_id: str,
    connection_id: str,
    tenant_id: str,
    sync_type: str = "full",
) -> dict[str, Any]:
    """Finalize a sync job after all phases complete.

    Handles payroll sync, org profile sync, final status update,
    connection timestamp update, and audit events.

    Args:
        job_id: Sync job ID.
        connection_id: Xero connection ID.
        tenant_id: Tenant ID.
        sync_type: Type of sync.

    Returns:
        Dict with final job status and totals.
    """
    import asyncio

    return asyncio.run(
        _finalize_sync_job_async(
            UUID(job_id),
            UUID(connection_id),
            UUID(tenant_id),
            sync_type,
        )
    )


async def _finalize_sync_job_async(
    job_id: UUID,
    connection_id: UUID,
    tenant_id: UUID,
    sync_type: str,
) -> dict[str, Any]:
    """Async implementation of sync job finalization."""
    from app.modules.integrations.xero.sync_progress import SyncProgressPublisher

    settings = get_settings()
    session = await _get_async_session()
    publisher = SyncProgressPublisher()

    try:
        await _set_tenant_context(session, tenant_id)

        conn_repo = XeroConnectionRepository(session)
        connection = await conn_repo.get_by_id(connection_id)

        # Read accumulated totals from the job record
        job_row = await session.execute(
            text(
                "SELECT records_processed, records_created, records_updated, "
                "records_failed, progress_details, error_message "
                "FROM xero_sync_jobs WHERE id = :jid"
            ).bindparams(jid=job_id)
        )
        row = job_row.one_or_none()
        if not row:
            raise ValueError(f"Sync job {job_id} not found for finalization")

        total_processed = row.records_processed or 0
        total_created = row.records_created or 0
        total_updated = row.records_updated or 0
        total_failed = row.records_failed or 0
        progress_details: dict[str, Any] = dict(row.progress_details or {})
        error_messages: list[str] = []
        if row.error_message:
            error_messages.append(row.error_message)

        # =================================================================
        # Post-Phase Processing (payroll and org profile)
        # =================================================================

        if connection and connection.has_payroll_access:
            try:
                from app.modules.integrations.xero.payroll_service import XeroPayrollService

                logger.info("Starting payroll sync for phased job %s", job_id)
                payroll_service = XeroPayrollService(session, settings)
                payroll_result = await payroll_service.sync_payroll(connection_id)

                employees_synced = payroll_result.get("employees_synced", 0)
                pay_runs_synced = payroll_result.get("pay_runs_synced", 0)

                progress_details["payroll"] = {
                    "employees_synced": employees_synced,
                    "pay_runs_synced": pay_runs_synced,
                    "status": payroll_result.get("status", "complete"),
                    "reason": payroll_result.get("reason"),
                }
                total_processed += employees_synced + pay_runs_synced

            except Exception as e:
                logger.error("Failed to sync payroll for job %s: %s", job_id, e)
                error_messages.append(f"payroll: {e!s}")
                progress_details["payroll"] = {"status": "failed", "error": str(e)}

        if sync_type == "full":
            try:
                data_service = XeroDataService(session, settings)
                org_data = await data_service.sync_organisation_profile(connection_id)
                if org_data:
                    progress_details["organisation_profile"] = {
                        "status": "completed",
                        "entity_type": org_data.get("OrganisationType"),
                        "gst_registered": bool(
                            org_data.get("TaxNumber") and org_data.get("SalesTaxBasis")
                        ),
                    }
                else:
                    progress_details["organisation_profile"] = {
                        "status": "skipped",
                        "reason": "No organisation data returned",
                    }
            except Exception as e:
                logger.warning(
                    "Failed to sync org profile for job %s: %s",
                    job_id,
                    e,
                )
                progress_details["organisation_profile"] = {
                    "status": "failed",
                    "error": str(e),
                }

        # =================================================================
        # Job Finalization
        # =================================================================

        if not error_messages:
            final_status = XeroSyncStatus.COMPLETED
            error_message = None
        elif total_processed > 0:
            final_status = XeroSyncStatus.COMPLETED
            error_message = "; ".join(error_messages)
        else:
            final_status = XeroSyncStatus.FAILED
            error_message = "; ".join(error_messages)

        await _update_job_status(
            session,
            job_id,
            final_status,
            error_message=error_message,
            progress_details=progress_details,
            records_processed=total_processed,
            records_created=total_created,
            records_updated=total_updated,
            records_failed=total_failed,
        )

        # Update connection timestamps
        now = datetime.now(UTC)
        update_data = XeroConnectionUpdate(
            last_used_at=now,
            last_full_sync_at=now,
        )
        if connection and connection.has_payroll_access:
            update_data.last_payroll_sync_at = now
            update_data.last_employees_sync_at = now

        await conn_repo.update(connection_id, update_data)
        await session.commit()

        # Publish sync_complete event
        await publisher.publish_sync_complete(
            connection_id=connection_id,
            job_id=job_id,
            status=final_status.value,
            records_processed=total_processed,
            records_created=total_created,
            records_updated=total_updated,
            records_failed=total_failed,
        )

        # Emit audit event: sync completed
        await _emit_sync_audit_event(
            session=session,
            event_type="integration.xero.sync.completed",
            action="sync",
            outcome="success" if final_status == XeroSyncStatus.COMPLETED else "failure",
            tenant_id=tenant_id,
            connection_id=connection_id,
            job_id=job_id,
            metadata={
                "sync_type": sync_type,
                "records_processed": total_processed,
                "records_created": total_created,
                "records_updated": total_updated,
                "records_failed": total_failed,
                "phases_completed": TOTAL_SYNC_PHASES,
            },
        )

        logger.info(
            "Phased sync finalized",
            extra={
                "job_id": str(job_id),
                "connection_id": str(connection_id),
                "tenant_id": str(tenant_id),
                "status": final_status.value,
                "records_processed": total_processed,
                "records_created": total_created,
                "records_updated": total_updated,
                "records_failed": total_failed,
                "sync_type": sync_type,
            },
        )

        return {
            "job_id": str(job_id),
            "status": final_status.value,
            "records_processed": total_processed,
            "records_created": total_created,
            "records_updated": total_updated,
            "records_failed": total_failed,
            "progress_details": progress_details,
            "error_message": error_message,
        }

    except Exception as e:
        logger.error("Sync finalization failed for job %s: %s", job_id, e)
        await session.rollback()
        await _update_job_status(
            session,
            job_id,
            XeroSyncStatus.FAILED,
            error_message=str(e),
        )
        await session.commit()
        await publisher.publish_sync_failed(
            connection_id=connection_id,
            job_id=job_id,
            error=str(e),
        )
        return {
            "job_id": str(job_id),
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await publisher.close()
        await session.close()


# =============================================================================
# Post-Sync Task Helpers (Spec 043 — T035, T036, T037)
# =============================================================================

# Mapping of sync phase numbers to the post-sync tasks they trigger.
# Phase 1 complete: (no post-sync tasks — transactional data not yet available)
# Phase 2 complete: quality_score + bas_calculation + aggregation
#   Quality score needs bank_transactions (Phase 2) for completeness checks.
# Phase 3 complete: insights + triggers (proactive insights, data triggers)
PHASE_POST_SYNC_TASKS: dict[int, list[str]] = {
    2: ["quality_score", "bas_calculation", "aggregation", "tax_plan_refresh"],
    3: ["insights", "triggers"],
}


async def _dispatch_post_sync_tasks(
    session: AsyncSession,
    publisher: Any,
    connection_id: UUID,
    tenant_id: UUID,
    job_id: UUID,
    phase_num: int,
) -> None:
    """Dispatch post-sync tasks for a completed sync phase.

    Creates PostSyncTask records and dispatches the corresponding Celery
    tasks. Each downstream task receives its post_sync_task_id so it can
    report status back to the PostSyncTask record.

    Args:
        session: Active database session.
        publisher: Redis pub/sub publisher for progress events.
        connection_id: Xero connection ID.
        tenant_id: Tenant ID.
        job_id: Parent sync job ID.
        phase_num: Completed phase number (1, 2, or 3).
    """
    from app.modules.integrations.xero.models import (
        PostSyncTask,
        PostSyncTaskStatus,
    )

    task_types = PHASE_POST_SYNC_TASKS.get(phase_num, [])

    for task_type in task_types:
        # Create PostSyncTask record to track execution
        post_sync_task = PostSyncTask(
            tenant_id=tenant_id,
            job_id=job_id,
            connection_id=connection_id,
            task_type=task_type,
            status=PostSyncTaskStatus.PENDING,
            sync_phase=phase_num,
        )
        session.add(post_sync_task)
        await session.flush()

        # Dispatch the corresponding Celery task
        try:
            if task_type == "quality_score":
                from app.tasks.quality import calculate_quality_score

                calculate_quality_score.delay(
                    connection_id=str(connection_id),
                    trigger_reason="sync",
                    post_sync_task_id=str(post_sync_task.id),
                )
            elif task_type == "bas_calculation":
                from app.tasks.bas import calculate_bas_periods

                calculate_bas_periods.delay(
                    connection_id=str(connection_id),
                    tenant_id=str(tenant_id),
                    num_quarters=6,
                    trigger_reason="sync",
                    post_sync_task_id=str(post_sync_task.id),
                )
            elif task_type == "aggregation":
                from app.tasks.aggregation import compute_aggregations

                compute_aggregations.delay(
                    connection_id=str(connection_id),
                    tenant_id=str(tenant_id),
                    trigger_reason="sync",
                    post_sync_task_id=str(post_sync_task.id),
                )
            elif task_type == "insights":
                from app.tasks.insights import generate_insights_for_connection

                generate_insights_for_connection.delay(
                    connection_id=str(connection_id),
                    tenant_id=str(tenant_id),
                    trigger_reason="post_sync",
                    post_sync_task_id=str(post_sync_task.id),
                )
            elif task_type == "triggers":
                from app.tasks.triggers import evaluate_data_triggers

                evaluate_data_triggers.delay(
                    connection_id=str(connection_id),
                    tenant_id=str(tenant_id),
                    post_sync_task_id=str(post_sync_task.id),
                )
            elif task_type == "tax_plan_refresh":
                from app.tasks.reports import invalidate_report_cache

                invalidate_report_cache.delay(
                    connection_id=str(connection_id),
                    tenant_id=str(tenant_id),
                    post_sync_task_id=str(post_sync_task.id),
                )

            logger.info(
                "Dispatched post-sync task %s (phase %d) for job %s",
                task_type,
                phase_num,
                job_id,
            )
        except Exception as e:
            logger.warning(
                "Failed to dispatch post-sync task %s for job %s: %s",
                task_type,
                job_id,
                e,
            )

    await session.commit()


async def _update_post_sync_task_status(
    post_sync_task_id: str | None,
    status: str,
    error_message: str | None = None,
    result_summary: dict | None = None,
) -> None:
    """Update a PostSyncTask record's status and publish a progress event.

    Called by downstream Celery tasks (quality, BAS, aggregation, insights,
    triggers) to report their execution status back to the PostSyncTask
    record. Also publishes a Redis pub/sub event for real-time SSE
    consumption by the frontend.

    Args:
        post_sync_task_id: PostSyncTask record ID, or None to skip.
        status: New status string (in_progress, completed, failed).
        error_message: Error message if status is failed.
        result_summary: Optional dict summarising task results.
    """
    if not post_sync_task_id:
        return

    try:
        session = await _get_async_session()
        try:
            from sqlalchemy import select as sa_select

            from app.modules.integrations.xero.models import (
                PostSyncTask as PostSyncTaskModel,
                PostSyncTaskStatus,
            )
            from app.modules.integrations.xero.repository import (
                PostSyncTaskRepository,
            )

            # Fetch the task record to get connection_id for pub/sub channel
            task_record = await session.scalar(
                sa_select(PostSyncTaskModel).where(PostSyncTaskModel.id == UUID(post_sync_task_id))
            )

            if not task_record:
                logger.warning(
                    "PostSyncTask %s not found, skipping status update",
                    post_sync_task_id,
                )
                return

            # Build kwargs for the repository update
            update_kwargs: dict[str, Any] = {}
            if status == "in_progress":
                update_kwargs["started_at"] = datetime.now(UTC)
            elif status in ("completed", "failed"):
                update_kwargs["completed_at"] = datetime.now(UTC)

            if error_message:
                update_kwargs["error_message"] = error_message
            if result_summary:
                update_kwargs["result_summary"] = result_summary

            # Set RLS context using the task's tenant_id
            await _set_tenant_context(session, task_record.tenant_id)

            repo = PostSyncTaskRepository(session)
            await repo.update_status(
                UUID(post_sync_task_id),
                PostSyncTaskStatus(status),
                **update_kwargs,
            )
            await session.commit()

            # Publish progress event via Redis pub/sub (T037)
            try:
                from app.modules.integrations.xero.sync_progress import (
                    SyncProgressPublisher,
                )

                publisher = SyncProgressPublisher()
                await publisher.publish_post_sync_progress(
                    connection_id=task_record.connection_id,
                    task_type=task_record.task_type,
                    status=status,
                    result_summary=result_summary,
                )
                await publisher.close()
            except Exception as pub_err:
                logger.debug(
                    "Best-effort pub/sub for post-sync task %s failed: %s",
                    post_sync_task_id,
                    pub_err,
                )

        finally:
            await session.close()
    except Exception as e:
        logger.warning(
            "Failed to update post-sync task %s: %s",
            post_sync_task_id,
            e,
        )


# =============================================================================
# Bulk Import Tasks (Phase 035)
# =============================================================================

MAX_CONCURRENT_SYNCS = 10


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.xero.run_bulk_xero_import",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def run_bulk_xero_import(
    self: Task,
    job_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    """Orchestrate bulk import of multiple Xero organizations.

    Fetches the BulkImportJob and its associated BulkImportOrganization records,
    then processes each pending org sequentially (with concurrency limit),
    dispatching a full sync for each connection.

    Args:
        job_id: BulkImportJob ID.
        tenant_id: Tenant ID for RLS context.

    Returns:
        Dict with aggregated results.
    """
    import asyncio

    return asyncio.run(
        _run_bulk_import_async(
            self,
            UUID(job_id),
            UUID(tenant_id),
        )
    )


async def _run_bulk_import_async(
    task: Task,
    job_id: UUID,
    tenant_id: UUID,
) -> dict[str, Any]:
    """Async implementation of bulk import orchestration."""
    import time

    from app.modules.onboarding.models import BulkImportJobStatus
    from app.modules.onboarding.repository import (
        BulkImportJobRepository,
        BulkImportOrganizationRepository,
    )

    settings = get_settings()
    session = await _get_async_session()

    try:
        await _set_tenant_context(session, tenant_id)

        job_repo = BulkImportJobRepository(session)
        org_repo = BulkImportOrganizationRepository(session)

        # Get the job
        job = await job_repo.get_by_id(job_id)
        if not job:
            raise ValueError(f"Bulk import job {job_id} not found")

        # Update job status to IN_PROGRESS
        await job_repo.update(
            job_id,
            {
                "status": BulkImportJobStatus.IN_PROGRESS,
                "started_at": datetime.now(UTC),
            },
        )
        await session.commit()

        # Get pending organizations
        all_orgs = await org_repo.get_by_job_id(job_id, tenant_id=tenant_id)

        # Audit: bulk sync start
        from app.core.audit import AuditService

        audit = AuditService(session)
        await audit.log_event(
            event_type="integration.xero.bulk_sync.start",
            event_category="integration",
            resource_type="bulk_import_job",
            resource_id=job_id,
            action="sync",
            outcome="in_progress",
            tenant_id=tenant_id,
            new_values={"total_orgs": len(all_orgs)},
        )
        await session.commit()
        pending_orgs = [
            org for org in all_orgs if org.status == "pending" and org.selected_for_import
        ]

        imported_count = 0
        failed_count = 0
        imported_clients: list[dict[str, Any]] = []
        failed_clients: list[dict[str, Any]] = []

        for org in pending_orgs:
            try:
                # Update org status to "importing"
                await org_repo.update_status(org.id, "importing")
                await session.commit()

                # Check if connection exists
                if not org.connection_id:
                    raise ValueError(f"No connection created for org {org.xero_tenant_id}")

                # Update org status to "syncing"
                await org_repo.update_status(
                    org.id,
                    "syncing",
                    sync_started_at=datetime.now(UTC),
                )
                await session.commit()

                # Create a sync job for this connection
                conn_repo = XeroConnectionRepository(session)
                connection = await conn_repo.get_by_id(org.connection_id)
                if not connection:
                    raise ValueError(f"Connection {org.connection_id} not found")

                sync_job_repo = XeroSyncJobRepository(session)
                sync_job = await sync_job_repo.create(
                    connection_id=connection.id,
                    tenant_id=tenant_id,
                    sync_type=XeroSyncType.FULL,
                )
                await session.commit()

                # Run sync inline (not via separate Celery task) for better control
                data_service = XeroDataService(session, settings)

                # Sync key entities: accounts, contacts, invoices, transactions
                entity_syncs = [
                    ("accounts", data_service.sync_accounts, None),
                    ("contacts", data_service.sync_contacts, None),
                    ("invoices", data_service.sync_invoices, None),
                    ("bank_transactions", data_service.sync_bank_transactions, None),
                ]

                for entity_name, sync_fn, since in entity_syncs:
                    try:
                        result = await sync_fn(connection.id, since)
                        logger.info(
                            f"Bulk import: synced {entity_name} for {org.organization_name}"
                        )
                    except Exception as sync_err:
                        logger.warning(
                            f"Bulk import: {entity_name} sync failed for "
                            f"{org.organization_name}: {sync_err}"
                        )

                # Mark org as completed
                await org_repo.update_status(
                    org.id,
                    "completed",
                    sync_completed_at=datetime.now(UTC),
                )
                imported_count += 1
                imported_clients.append(
                    {
                        "xero_tenant_id": org.xero_tenant_id,
                        "org_name": org.organization_name,
                        "connection_id": str(org.connection_id),
                    }
                )

                # Update job progress
                total_actionable = len(pending_orgs)
                processed = imported_count + failed_count
                progress = int(processed / total_actionable * 100) if total_actionable > 0 else 0

                await job_repo.update(
                    job_id,
                    {
                        "imported_count": imported_count,
                        "failed_count": failed_count,
                        "progress_percent": progress,
                        "imported_clients": imported_clients,
                        "failed_clients": failed_clients,
                    },
                )
                await session.commit()

                logger.info(
                    f"Bulk import: completed org {org.organization_name} "
                    f"({imported_count}/{total_actionable})"
                )

            except Exception as org_err:
                logger.error(f"Bulk import: failed org {org.organization_name}: {org_err}")
                await org_repo.update_status(
                    org.id,
                    "failed",
                    error_message=str(org_err),
                    sync_completed_at=datetime.now(UTC),
                )
                failed_count += 1
                failed_clients.append(
                    {
                        "xero_tenant_id": org.xero_tenant_id,
                        "org_name": org.organization_name,
                        "error": str(org_err),
                    }
                )

                # Update job progress even on failure
                total_actionable = len(pending_orgs)
                processed = imported_count + failed_count
                progress = int(processed / total_actionable * 100) if total_actionable > 0 else 0

                await job_repo.update(
                    job_id,
                    {
                        "imported_count": imported_count,
                        "failed_count": failed_count,
                        "progress_percent": progress,
                        "imported_clients": imported_clients,
                        "failed_clients": failed_clients,
                    },
                )
                await session.commit()

            # Brief delay between orgs to avoid rate limit spikes
            time.sleep(2)

        # Determine final job status
        if failed_count == 0:
            final_status = BulkImportJobStatus.COMPLETED
        elif imported_count > 0:
            final_status = BulkImportJobStatus.PARTIAL_FAILURE
        else:
            final_status = BulkImportJobStatus.FAILED

        await job_repo.update(
            job_id,
            {
                "status": final_status,
                "progress_percent": 100,
                "completed_at": datetime.now(UTC),
                "imported_count": imported_count,
                "failed_count": failed_count,
                "imported_clients": imported_clients,
                "failed_clients": failed_clients,
            },
        )
        await session.commit()

        # Audit: bulk import complete
        await audit.log_event(
            event_type="integration.xero.bulk_import.complete",
            event_category="integration",
            resource_type="bulk_import_job",
            resource_id=job_id,
            action="sync",
            outcome="success" if failed_count == 0 else "partial_failure",
            tenant_id=tenant_id,
            new_values={
                "status": final_status.value,
                "imported_count": imported_count,
                "failed_count": failed_count,
            },
        )
        await session.commit()

        logger.info(
            f"Bulk import job {job_id} finished: status={final_status.value}, "
            f"imported={imported_count}, failed={failed_count}"
        )

        return {
            "job_id": str(job_id),
            "status": final_status.value,
            "imported_count": imported_count,
            "failed_count": failed_count,
        }

    except Exception as e:
        logger.error(f"Bulk import job {job_id} failed: {e}")

        try:
            from app.modules.onboarding.models import BulkImportJobStatus as BIStatus
            from app.modules.onboarding.repository import BulkImportJobRepository as BJRepo

            j_repo = BJRepo(session)
            await j_repo.update(
                job_id,
                {
                    "status": BIStatus.FAILED,
                    "error_message": str(e),
                    "completed_at": datetime.now(UTC),
                },
            )
            await session.commit()

            # Audit: bulk sync fail
            from app.core.audit import AuditService as AuditSvc

            audit_svc = AuditSvc(session)
            await audit_svc.log_event(
                event_type="integration.xero.bulk_sync.fail",
                event_category="integration",
                resource_type="bulk_import_job",
                resource_id=job_id,
                action="sync",
                outcome="failure",
                tenant_id=tenant_id,
                new_values={"error": str(e)},
            )
            await session.commit()
        except Exception:
            logger.error(f"Failed to update job {job_id} status after error")

        return {
            "job_id": str(job_id),
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await session.close()


# =============================================================================
# Webhook Event Processing (Phase 8 — US6)
# =============================================================================


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.xero.process_webhook_events",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def process_webhook_events(self: Task) -> dict[str, Any]:
    """Process pending Xero webhook events.

    Fetches all pending webhook events, batches them by connection and
    entity type, and dispatches a targeted incremental sync for each
    batch. This avoids redundant API calls when multiple events arrive
    for the same entity type on the same connection.

    Returns:
        Dict with processing results including batches processed and events handled.
    """
    import asyncio

    return asyncio.run(_process_webhook_events_async(self))


async def _process_webhook_events_async(
    task: Task,
) -> dict[str, Any]:
    """Async implementation of webhook event processing.

    1. Fetch all pending webhook events
    2. Batch by (connection_id, entity_type)
    3. For each batch, dispatch a targeted sync_entity task
    4. Mark events as processed or failed
    """
    import uuid as uuid_mod

    from app.modules.integrations.xero.models import (
        XeroSyncEntityProgress,
        XeroSyncEntityProgressStatus,
        XeroSyncJob,
    )
    from app.modules.integrations.xero.repository import XeroWebhookEventRepository
    from app.modules.integrations.xero.webhook_handler import (
        batch_events_by_connection_and_entity,
        get_earliest_event_timestamp,
    )

    session = await _get_async_session()
    batch_id = uuid_mod.uuid4()

    total_events = 0
    batches_processed = 0
    events_processed = 0
    events_failed = 0

    try:
        webhook_repo = XeroWebhookEventRepository(session)

        # Fetch all pending events
        pending_events = await webhook_repo.get_all_pending()
        total_events = len(pending_events)

        if not pending_events:
            logger.info("No pending webhook events to process")
            return {
                "status": "completed",
                "total_events": 0,
                "batches_processed": 0,
            }

        logger.info(
            "Processing webhook events",
            extra={"total_events": total_events, "batch_id": str(batch_id)},
        )

        # Batch events by (connection_id, entity_type)
        batches = batch_events_by_connection_and_entity(pending_events)

        for (connection_id, entity_type), events in batches.items():
            try:
                # Get the earliest event timestamp as modified_since
                modified_since = get_earliest_event_timestamp(events)
                modified_since_iso = modified_since.isoformat() if modified_since else None

                # Get tenant_id from the first event (all events in a batch
                # share the same connection, thus the same tenant)
                tenant_id = events[0].tenant_id

                # Set tenant context for the job creation
                await _set_tenant_context(session, tenant_id)

                # Create a sync job for the targeted sync
                sync_job = XeroSyncJob(
                    tenant_id=tenant_id,
                    connection_id=connection_id,
                    sync_type=XeroSyncType.FULL,
                    status=XeroSyncStatus.PENDING,
                    triggered_by="webhook",
                )
                session.add(sync_job)
                await session.flush()

                # Create an entity progress record for the targeted entity
                entity_progress = XeroSyncEntityProgress(
                    tenant_id=tenant_id,
                    job_id=sync_job.id,
                    entity_type=entity_type,
                    status=XeroSyncEntityProgressStatus.PENDING,
                    modified_since=modified_since,
                )
                session.add(entity_progress)
                await session.flush()

                # Mark all events in this batch as processed
                for event in events:
                    await webhook_repo.mark_processed(event.id, batch_id=batch_id)
                    events_processed += 1

                await session.commit()

                # Dispatch the targeted sync_entity task
                celery_app.send_task(
                    "app.tasks.xero.sync_entity",
                    args=[
                        str(sync_job.id),
                        entity_type,
                        str(connection_id),
                        str(tenant_id),
                    ],
                    kwargs={
                        "modified_since": modified_since_iso,
                        "force_full": False,
                    },
                )

                batches_processed += 1
                logger.info(
                    "Dispatched targeted sync for webhook batch",
                    extra={
                        "connection_id": str(connection_id),
                        "entity_type": entity_type,
                        "events_in_batch": len(events),
                        "modified_since": modified_since_iso,
                        "job_id": str(sync_job.id),
                    },
                )

            except Exception as e:
                logger.error(
                    "Failed to process webhook event batch",
                    extra={
                        "connection_id": str(connection_id),
                        "entity_type": entity_type,
                        "error": str(e),
                    },
                    exc_info=True,
                )
                # Mark events in this batch as failed
                for event in events:
                    try:
                        await webhook_repo.mark_failed(
                            event.id,
                            error_message=str(e),
                            batch_id=batch_id,
                        )
                        events_failed += 1
                    except Exception:
                        logger.error(
                            "Failed to mark webhook event as failed",
                            extra={"event_id": str(event.id)},
                        )
                await session.commit()

        result = {
            "status": "completed",
            "batch_id": str(batch_id),
            "total_events": total_events,
            "batches_processed": batches_processed,
            "events_processed": events_processed,
            "events_failed": events_failed,
        }
        logger.info("Webhook event processing completed", extra=result)
        return result

    except Exception as e:
        logger.error(
            "Webhook event processing failed",
            extra={"error": str(e)},
            exc_info=True,
        )
        return {
            "status": "failed",
            "error_message": str(e),
            "total_events": total_events,
            "batches_processed": batches_processed,
            "events_processed": events_processed,
            "events_failed": events_failed,
        }

    finally:
        await session.close()
