"""Bulk Document Request Service.

Handles creating and processing bulk document requests across multiple clients.

Spec: 030-client-portal-document-requests
"""

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.portal.enums import (
    ActorType,
    BulkRequestStatus,
    RequestEventType,
    RequestPriority,
    RequestStatus,
)
from app.modules.portal.exceptions import (
    BulkRequestNotFoundError,
    PortalError,
    RequestTemplateNotFoundError,
)
from app.modules.portal.models import BulkRequest, DocumentRequest, RequestEvent
from app.modules.portal.repository import (
    BulkRequestRepository,
    DocumentRequestRepository,
    DocumentRequestTemplateRepository,
    RequestEventRepository,
)
from app.modules.portal.schemas import (
    BulkRequestCreateRequest,
    BulkRequestResponse,
)


class BulkRequestService:
    """Service for bulk document request operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the service with a database session."""
        self.db = db
        self.bulk_repo = BulkRequestRepository(db)
        self.request_repo = DocumentRequestRepository(db)
        self.template_repo = DocumentRequestTemplateRepository(db)
        self.event_repo = RequestEventRepository(db)

    async def create_bulk_request(
        self,
        tenant_id: UUID,
        user_id: UUID,
        data: BulkRequestCreateRequest,
    ) -> BulkRequest:
        """Create a new bulk document request.

        This creates the bulk request record and queues it for processing.
        The actual individual requests are created asynchronously via Celery.

        Args:
            tenant_id: The tenant (accounting practice) ID.
            user_id: The ID of the user creating the request.
            data: The bulk request creation data.

        Returns:
            The created bulk request.

        Raises:
            RequestTemplateNotFoundError: If a template_id is provided but not found.
            PortalError: If connection_ids list is empty.
        """
        if not data.connection_ids:
            raise PortalError("At least one client must be selected")

        # Validate template if provided
        if data.template_id:
            template = await self.template_repo.get_by_id_and_tenant(
                template_id=data.template_id,
                tenant_id=tenant_id,
            )
            if not template:
                raise RequestTemplateNotFoundError(data.template_id)

        # Create the bulk request record
        bulk_request = BulkRequest(
            tenant_id=tenant_id,
            template_id=data.template_id,
            title=data.title,
            due_date=data.due_date,
            total_clients=len(data.connection_ids),
            sent_count=0,
            failed_count=0,
            status=BulkRequestStatus.PENDING.value,
            created_by=user_id,
        )

        created = await self.bulk_repo.create(bulk_request)
        return created

    async def get_bulk_request(
        self,
        bulk_id: UUID,
        tenant_id: UUID,
    ) -> BulkRequest:
        """Get a bulk request by ID.

        Args:
            bulk_id: The bulk request ID.
            tenant_id: The tenant ID for authorization.

        Returns:
            The bulk request.

        Raises:
            BulkRequestNotFoundError: If the bulk request is not found.
        """
        bulk_request = await self.bulk_repo.get_by_id_and_tenant(
            bulk_id=bulk_id,
            tenant_id=tenant_id,
        )

        if not bulk_request:
            raise BulkRequestNotFoundError(bulk_id)

        return bulk_request

    async def list_bulk_requests(
        self,
        tenant_id: UUID,
        status: BulkRequestStatus | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[BulkRequest], int]:
        """List bulk requests for a tenant.

        Args:
            tenant_id: The tenant ID.
            status: Filter by status.
            skip: Pagination offset.
            limit: Pagination limit.

        Returns:
            Tuple of (bulk requests list, total count).
        """
        return await self.bulk_repo.list_by_tenant(
            tenant_id=tenant_id,
            status=status,
            skip=skip,
            limit=limit,
        )

    async def preview_bulk_request(
        self,
        tenant_id: UUID,
        connection_ids: list[UUID],
    ) -> dict:
        """Preview a bulk request before sending.

        Returns information about the clients that will receive the request.

        Args:
            tenant_id: The tenant ID.
            connection_ids: List of connection IDs to preview.

        Returns:
            Preview information including client count and any issues.
        """
        # In a real implementation, you'd validate each connection
        # and check for any issues (e.g., no email, inactive, etc.)
        return {
            "total_clients": len(connection_ids),
            "valid_clients": len(connection_ids),
            "invalid_clients": 0,
            "issues": [],
        }

    async def process_bulk_request(
        self,
        bulk_id: UUID,
        connection_ids: list[UUID],
        title: str,
        description: str,
        priority: RequestPriority,
        due_date: date | None,
        template_id: UUID | None,
        tenant_id: UUID,
        user_id: UUID,
    ) -> dict:
        """Process a bulk request by creating individual document requests.

        This method is called by the Celery task to actually create the requests.

        Args:
            bulk_id: The bulk request ID.
            connection_ids: List of connection IDs to send requests to.
            title: Request title.
            description: Request description.
            priority: Request priority.
            due_date: Optional due date.
            template_id: Optional template ID.
            tenant_id: The tenant ID.
            user_id: The user who created the bulk request.

        Returns:
            Processing results with success/failure counts.
        """
        # Update bulk request to processing status
        await self.bulk_repo.update(
            bulk_id,
            {"status": BulkRequestStatus.PROCESSING.value},
        )

        sent_count = 0
        failed_count = 0
        failed_connections: list[UUID] = []

        for connection_id in connection_ids:
            try:
                # Create individual document request
                request = DocumentRequest(
                    tenant_id=tenant_id,
                    connection_id=connection_id,
                    template_id=template_id,
                    title=title,
                    description=description,
                    due_date=due_date,
                    priority=priority.value,
                    status=RequestStatus.PENDING.value,
                    sent_at=datetime.now(timezone.utc),
                    auto_remind=True,
                    bulk_request_id=bulk_id,
                    created_by=user_id,
                )

                created_request = await self.request_repo.create(request)

                # Log creation and send events
                await self._log_event(
                    request_id=created_request.id,
                    event_type=RequestEventType.CREATED,
                    actor_type=ActorType.SYSTEM,
                    event_data={"bulk_request_id": str(bulk_id)},
                )
                await self._log_event(
                    request_id=created_request.id,
                    event_type=RequestEventType.SENT,
                    actor_type=ActorType.SYSTEM,
                )

                sent_count += 1

            except Exception:
                failed_count += 1
                failed_connections.append(connection_id)

            # Update progress periodically
            if (sent_count + failed_count) % 10 == 0:
                await self.bulk_repo.update(
                    bulk_id,
                    {"sent_count": sent_count, "failed_count": failed_count},
                )
                await self.db.commit()

        # Final update
        now = datetime.now(timezone.utc)
        final_status = (
            BulkRequestStatus.COMPLETED.value
            if failed_count == 0
            else (
                BulkRequestStatus.PARTIAL.value
                if sent_count > 0
                else BulkRequestStatus.FAILED.value
            )
        )

        await self.bulk_repo.update(
            bulk_id,
            {
                "sent_count": sent_count,
                "failed_count": failed_count,
                "status": final_status,
                "completed_at": now,
            },
        )

        return {
            "bulk_id": str(bulk_id),
            "sent_count": sent_count,
            "failed_count": failed_count,
            "failed_connections": [str(c) for c in failed_connections],
            "status": final_status,
        }

    async def _log_event(
        self,
        request_id: UUID,
        event_type: RequestEventType,
        actor_type: ActorType,
        actor_id: UUID | None = None,
        event_data: dict | None = None,
    ) -> RequestEvent:
        """Log an event for a document request."""
        event = RequestEvent(
            request_id=request_id,
            event_type=event_type.value,
            event_data=event_data,
            actor_type=actor_type.value,
            actor_id=actor_id,
        )
        return await self.event_repo.create(event)

    def to_response(self, bulk_request: BulkRequest) -> BulkRequestResponse:
        """Convert a BulkRequest model to response schema.

        Args:
            bulk_request: The bulk request model.

        Returns:
            The response schema with computed fields.
        """
        progress_percent = 0
        if bulk_request.total_clients > 0:
            processed = bulk_request.sent_count + bulk_request.failed_count
            progress_percent = int((processed / bulk_request.total_clients) * 100)

        return BulkRequestResponse(
            id=bulk_request.id,
            template_id=bulk_request.template_id,
            title=bulk_request.title,
            due_date=bulk_request.due_date,
            total_clients=bulk_request.total_clients,
            sent_count=bulk_request.sent_count,
            failed_count=bulk_request.failed_count,
            status=BulkRequestStatus(bulk_request.status),
            completed_at=bulk_request.completed_at,
            created_at=bulk_request.created_at,
            updated_at=bulk_request.updated_at,
            progress_percent=progress_percent,
        )
