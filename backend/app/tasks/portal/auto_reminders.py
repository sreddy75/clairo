"""Celery tasks for automatic document request reminders.

Sends reminders for pending/viewed document requests based on:
- Days until due date
- Days since last reminder
- Tenant reminder settings

Spec: 030-client-portal-document-requests
"""

import asyncio
from datetime import date, timedelta
from typing import Any

from celery import shared_task

from app.core.logging import get_logger
from app.database import get_db_context

logger = get_logger(__name__)


@shared_task(
    name="portal.send_auto_reminders",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    acks_late=True,
)
def send_auto_reminders_task(
    self,
    days_before_due: int = 3,
    overdue_reminder_days: list[int] | None = None,
    min_days_between_reminders: int = 3,
) -> dict[str, Any]:
    """Send automatic reminders for pending document requests.

    Args:
        days_before_due: Days before due date to send first reminder.
        overdue_reminder_days: List of days after due date to send reminders.
            Defaults to [1, 3, 7] (1 day overdue, 3 days overdue, 7 days overdue).
        min_days_between_reminders: Minimum days between reminders to same request.

    Returns:
        Summary of reminders sent.
    """
    if overdue_reminder_days is None:
        overdue_reminder_days = [1, 3, 7]

    logger.info(
        "Starting auto-reminder task",
        days_before_due=days_before_due,
        overdue_reminder_days=overdue_reminder_days,
        min_days_between_reminders=min_days_between_reminders,
    )

    try:
        result = asyncio.get_event_loop().run_until_complete(
            _process_reminders(
                days_before_due=days_before_due,
                overdue_reminder_days=overdue_reminder_days,
                min_days_between_reminders=min_days_between_reminders,
            )
        )
        return result
    except RuntimeError:
        # No running event loop, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                _process_reminders(
                    days_before_due=days_before_due,
                    overdue_reminder_days=overdue_reminder_days,
                    min_days_between_reminders=min_days_between_reminders,
                )
            )
            return result
        finally:
            loop.close()


async def _process_reminders(
    days_before_due: int,
    overdue_reminder_days: list[int],
    min_days_between_reminders: int,
) -> dict[str, Any]:
    """Process and send reminders for eligible requests.

    Returns:
        Summary statistics.
    """
    from app.modules.portal.repository import DocumentRequestRepository
    from app.modules.portal.requests.service import DocumentRequestService

    today = date.today()
    reminder_due_date = today + timedelta(days=days_before_due)

    sent_count = 0
    failed_count = 0
    skipped_count = 0

    async with get_db_context() as db:
        repo = DocumentRequestRepository(db)
        service = DocumentRequestService(db)

        # Get all requests needing reminders
        requests = await repo.get_pending_reminders(days_since_last=min_days_between_reminders)

        logger.info(f"Found {len(requests)} requests eligible for reminders")

        for request in requests:
            try:
                # Determine reminder type
                reminder_type = _determine_reminder_type(
                    request, today, days_before_due, overdue_reminder_days
                )

                if not reminder_type:
                    skipped_count += 1
                    continue

                # Send the reminder
                await service.send_reminder(
                    request_id=request.id,
                    tenant_id=request.tenant_id,
                    reminder_type=reminder_type,
                )

                logger.info(
                    "Sent reminder",
                    request_id=str(request.id),
                    reminder_type=reminder_type,
                    reminder_count=request.reminder_count + 1,
                )

                sent_count += 1

            except Exception as e:
                logger.error(
                    "Failed to send reminder",
                    request_id=str(request.id),
                    error=str(e),
                )
                failed_count += 1

        await db.commit()

    result = {
        "total_eligible": len(requests),
        "sent": sent_count,
        "failed": failed_count,
        "skipped": skipped_count,
    }

    logger.info("Completed auto-reminder task", **result)
    return result


def _determine_reminder_type(
    request,
    today: date,
    days_before_due: int,
    overdue_reminder_days: list[int],
) -> str | None:
    """Determine what type of reminder to send, if any.

    Returns:
        Reminder type string, or None if no reminder needed.
    """
    if not request.due_date:
        return None

    days_until_due = (request.due_date - today).days

    # Check for pre-due reminder
    if 0 < days_until_due <= days_before_due:
        return f"due_in_{days_until_due}_days"

    # Check for due today
    if days_until_due == 0:
        return "due_today"

    # Check for overdue reminders
    if days_until_due < 0:
        days_overdue = abs(days_until_due)
        if days_overdue in overdue_reminder_days:
            return f"overdue_{days_overdue}_days"

    return None


@shared_task(
    name="portal.send_single_reminder",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_single_reminder_task(
    self,
    request_id: str,
    tenant_id: str,
    reminder_type: str = "manual",
) -> dict[str, Any]:
    """Send a single reminder for a specific request.

    Args:
        request_id: The request ID.
        tenant_id: The tenant ID.
        reminder_type: Type of reminder (manual, scheduled, etc.).

    Returns:
        Result of sending the reminder.
    """
    from uuid import UUID

    logger.info(
        "Sending single reminder",
        request_id=request_id,
        reminder_type=reminder_type,
    )

    try:
        result = asyncio.get_event_loop().run_until_complete(
            _send_single_reminder(
                UUID(request_id),
                UUID(tenant_id),
                reminder_type,
            )
        )
        return result
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                _send_single_reminder(
                    UUID(request_id),
                    UUID(tenant_id),
                    reminder_type,
                )
            )
            return result
        finally:
            loop.close()


async def _send_single_reminder(
    request_id,
    tenant_id,
    reminder_type: str,
) -> dict[str, Any]:
    """Send a single reminder asynchronously."""
    from app.modules.portal.requests.service import DocumentRequestService

    async with get_db_context() as db:
        service = DocumentRequestService(db)

        request = await service.send_reminder(
            request_id=request_id,
            tenant_id=tenant_id,
            reminder_type=reminder_type,
        )

        await db.commit()

        return {
            "success": True,
            "request_id": str(request.id),
            "reminder_count": request.reminder_count,
        }
