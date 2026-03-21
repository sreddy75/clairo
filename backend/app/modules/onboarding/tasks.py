"""Celery tasks for onboarding background processing.

Tasks:
- bulk_import_clients: Import clients from Xero/XPM
- check_trial_reminders: Send trial reminder emails
- send_onboarding_drip_emails: Send nudge emails for incomplete onboardings
"""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from celery import shared_task

from app.core.logging import get_logger
from app.database import get_celery_db_context
from app.modules.onboarding.models import BulkImportJobStatus

logger = get_logger(__name__)


@shared_task(bind=True, max_retries=3)
def bulk_import_clients(self, job_id: str, client_ids: list[str]) -> dict:
    """Import clients from Xero/XPM in background.

    This task processes client imports one by one, updating progress
    every 5 clients for real-time UI updates.

    Args:
        job_id: UUID of the BulkImportJob
        client_ids: List of XPM/Xero client IDs to import

    Returns:
        Dict with import results
    """
    return asyncio.get_event_loop().run_until_complete(
        _bulk_import_clients_async(job_id, client_ids)
    )


async def _bulk_import_clients_async(job_id: str, client_ids: list[str]) -> dict:
    """Async implementation of bulk import."""
    from app.modules.onboarding.repository import BulkImportJobRepository

    job_uuid = UUID(job_id)
    imported_count = 0
    failed_count = 0
    imported_clients: list[dict] = []
    failed_clients: list[dict] = []

    async with get_celery_db_context() as db:
        repo = BulkImportJobRepository(db)
        job = await repo.get_by_id(job_uuid)

        if not job:
            logger.error("Import job not found", job_id=job_id)
            return {"error": "Job not found"}

        # Update status to in_progress
        await repo.update(job_uuid, {"status": BulkImportJobStatus.IN_PROGRESS})

        # Process each client
        for i, client_id in enumerate(client_ids):
            try:
                # TODO: Fetch client from XPM/Xero
                # TODO: Create client record
                # TODO: Sync transactions

                # Simulate success for now
                imported_count += 1
                imported_clients.append(
                    {
                        "xero_id": client_id,
                        "client_id": str(UUID(int=i)),
                        "name": f"Client {client_id}",
                        "transactions_synced": 0,
                    }
                )

            except Exception as e:
                failed_count += 1
                failed_clients.append(
                    {
                        "xero_id": client_id,
                        "name": f"Client {client_id}",
                        "error": str(e),
                    }
                )
                logger.warning(
                    "Client import failed",
                    job_id=job_id,
                    client_id=client_id,
                    error=str(e),
                )

            # Update progress every 5 clients
            if (i + 1) % 5 == 0 or i == len(client_ids) - 1:
                progress = int((i + 1) / len(client_ids) * 100)
                await repo.update(
                    job_uuid,
                    {
                        "imported_count": imported_count,
                        "failed_count": failed_count,
                        "progress_percent": progress,
                        "imported_clients": imported_clients,
                        "failed_clients": failed_clients,
                    },
                )

        # Determine final status
        if failed_count == 0:
            final_status = BulkImportJobStatus.COMPLETED
        elif imported_count > 0:
            final_status = BulkImportJobStatus.PARTIAL_FAILURE
        else:
            final_status = BulkImportJobStatus.FAILED

        # Final update
        await repo.update(
            job_uuid,
            {
                "status": final_status,
                "completed_at": datetime.now(UTC),
                "imported_count": imported_count,
                "failed_count": failed_count,
                "progress_percent": 100,
                "imported_clients": imported_clients,
                "failed_clients": failed_clients,
            },
        )

        logger.info(
            "Bulk import completed",
            job_id=job_id,
            imported=imported_count,
            failed=failed_count,
            status=final_status.value,
        )

    return {
        "status": final_status.value,
        "imported_count": imported_count,
        "failed_count": failed_count,
    }


@shared_task
def check_trial_reminders() -> dict:
    """Check for trials ending soon and send reminder emails.

    Runs daily at 9am AEDT.
    Sends reminders for trials ending in 3 days and 1 day.
    """
    return asyncio.get_event_loop().run_until_complete(_check_trial_reminders_async())


async def _check_trial_reminders_async() -> dict:
    """Async implementation of trial reminder check."""

    from sqlalchemy import select

    from app.modules.auth.models import SubscriptionStatus, Tenant
    from app.modules.onboarding.repository import EmailDripRepository

    reminders_sent = 0

    async with get_celery_db_context() as db:
        email_repo = EmailDripRepository(db)
        now = datetime.now(UTC)

        # Find tenants in trial
        result = await db.execute(
            select(Tenant).where(
                Tenant.subscription_status == SubscriptionStatus.TRIAL,
                Tenant.is_active == True,  # noqa: E712
            )
        )
        tenants = result.scalars().all()

        for tenant in tenants:
            # Check trial end date
            if not tenant.current_period_end:
                continue

            days_remaining = (tenant.current_period_end - now).days

            # Send 3-day reminder
            if days_remaining == 3:
                if not await email_repo.has_sent(tenant.id, "trial_3_day"):
                    # TODO: Send email via NotificationService
                    logger.info(
                        "Sending 3-day trial reminder",
                        tenant_id=str(tenant.id),
                    )
                    reminders_sent += 1

            # Send 1-day reminder
            elif days_remaining == 1:
                if not await email_repo.has_sent(tenant.id, "trial_1_day"):
                    # TODO: Send email via NotificationService
                    logger.info(
                        "Sending 1-day trial reminder",
                        tenant_id=str(tenant.id),
                    )
                    reminders_sent += 1

    logger.info("Trial reminder check completed", reminders_sent=reminders_sent)
    return {"reminders_sent": reminders_sent}


@shared_task
def send_onboarding_drip_emails() -> dict:
    """Send nudge emails for incomplete onboardings.

    Runs daily.
    - 24h: Connect Xero reminder (if no Xero connection)
    - 48h: Import clients reminder (if no clients imported)
    """
    return asyncio.get_event_loop().run_until_complete(_send_onboarding_drip_emails_async())


async def _send_onboarding_drip_emails_async() -> dict:
    """Async implementation of onboarding drip emails."""
    from app.modules.onboarding.repository import (
        EmailDripRepository,
        OnboardingRepository,
    )

    emails_sent = 0

    async with get_celery_db_context() as db:
        onboarding_repo = OnboardingRepository(db)
        email_repo = EmailDripRepository(db)

        # Get incomplete onboardings
        incomplete = await onboarding_repo.list_incomplete()
        now = datetime.now(UTC)

        for progress in incomplete:
            elapsed = now - progress.started_at.replace(tzinfo=UTC)
            elapsed_hours = elapsed.total_seconds() / 3600

            # 24h: Connect Xero reminder
            if elapsed_hours >= 24 and not progress.xero_connected_at:
                if not await email_repo.has_sent(progress.tenant_id, "connect_xero"):
                    # TODO: Send email via NotificationService
                    logger.info(
                        "Sending connect Xero reminder",
                        tenant_id=str(progress.tenant_id),
                    )
                    emails_sent += 1

            # 48h: Import clients reminder
            if elapsed_hours >= 48 and not progress.clients_imported_at:
                if not await email_repo.has_sent(progress.tenant_id, "import_clients"):
                    # TODO: Send email via NotificationService
                    logger.info(
                        "Sending import clients reminder",
                        tenant_id=str(progress.tenant_id),
                    )
                    emails_sent += 1

    logger.info("Onboarding drip emails sent", emails_sent=emails_sent)
    return {"emails_sent": emails_sent}
