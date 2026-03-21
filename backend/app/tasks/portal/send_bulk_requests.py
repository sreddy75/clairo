"""Celery task for processing bulk document requests.

Processes individual document requests asynchronously for each client
in a bulk request batch.

Spec: 030-client-portal-document-requests
"""

import asyncio
from datetime import date
from uuid import UUID

from celery import shared_task

from app.database import get_celery_db_context
from app.modules.portal.enums import RequestPriority
from app.modules.portal.requests.bulk import BulkRequestService


@shared_task(
    name="portal.send_bulk_requests",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    acks_late=True,
)
def process_bulk_request_task(
    self,
    bulk_id: str,
    connection_ids: list[str],
    title: str,
    description: str,
    priority: str,
    due_date: str | None,
    template_id: str | None,
    tenant_id: str,
    user_id: str,
) -> dict:
    """Process a bulk document request.

    Creates individual document requests for each connection in the list.

    Args:
        bulk_id: The bulk request ID.
        connection_ids: List of connection IDs to send requests to.
        title: Request title.
        description: Request description.
        priority: Request priority (low, normal, high, urgent).
        due_date: Optional due date (ISO format string).
        template_id: Optional template ID.
        tenant_id: The tenant ID.
        user_id: The user who created the bulk request.

    Returns:
        Processing results with success/failure counts.
    """
    # Run the async processing function
    return asyncio.get_event_loop().run_until_complete(
        _process_bulk_request_async(
            bulk_id=bulk_id,
            connection_ids=connection_ids,
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            template_id=template_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
    )


async def _process_bulk_request_async(
    bulk_id: str,
    connection_ids: list[str],
    title: str,
    description: str,
    priority: str,
    due_date: str | None,
    template_id: str | None,
    tenant_id: str,
    user_id: str,
) -> dict:
    """Async implementation of bulk request processing."""
    async with get_celery_db_context() as db:
        service = BulkRequestService(db)

        # Parse date if provided
        parsed_due_date: date | None = None
        if due_date:
            parsed_due_date = date.fromisoformat(due_date)

        result = await service.process_bulk_request(
            bulk_id=UUID(bulk_id),
            connection_ids=[UUID(c) for c in connection_ids],
            title=title,
            description=description,
            priority=RequestPriority(priority),
            due_date=parsed_due_date,
            template_id=UUID(template_id) if template_id else None,
            tenant_id=UUID(tenant_id),
            user_id=UUID(user_id),
        )

        await db.commit()
        return result
