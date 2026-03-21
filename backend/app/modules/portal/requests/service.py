"""Document Request Service.

Business logic for creating, sending, and managing document requests (ClientChase).

Spec: 030-client-portal-document-requests
Spec: 032-pwa-mobile-document-capture (push notification triggers)
"""

import logging
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.portal.enums import ActorType, RequestEventType, RequestPriority, RequestStatus
from app.modules.portal.exceptions import (
    PortalError,
    RequestNotFoundError,
    RequestTemplateNotFoundError,
)
from app.modules.portal.models import DocumentRequest, RequestEvent
from app.modules.portal.repository import (
    DocumentRequestRepository,
    DocumentRequestTemplateRepository,
    RequestEventRepository,
)
from app.modules.portal.schemas import RequestCreateRequest, RequestResponse

logger = logging.getLogger(__name__)


class DocumentRequestService:
    """Service for document request operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the service with a database session."""
        self.db = db
        self.request_repo = DocumentRequestRepository(db)
        self.template_repo = DocumentRequestTemplateRepository(db)
        self.event_repo = RequestEventRepository(db)

    async def create_request(
        self,
        tenant_id: UUID,
        user_id: UUID,
        data: RequestCreateRequest,
    ) -> DocumentRequest:
        """Create a new document request.

        Args:
            tenant_id: The tenant (accounting practice) ID.
            user_id: The ID of the user creating the request.
            data: The request creation data.

        Returns:
            The created document request.

        Raises:
            TemplateNotFoundError: If a template_id is provided but not found.
        """
        # If template provided, validate and get defaults
        description = data.description
        priority = data.priority
        due_days = 7  # default

        if data.template_id:
            template = await self.template_repo.get_by_id_and_tenant(
                template_id=data.template_id,
                tenant_id=tenant_id,
            )
            if not template:
                raise RequestTemplateNotFoundError(data.template_id)

            # Use template defaults if not overridden
            if data.priority == RequestPriority.NORMAL:
                priority = RequestPriority(template.default_priority)
            due_days = template.default_due_days

        # Calculate due date if not provided
        due_date = data.due_date
        if not due_date:
            due_date = date.today() + timedelta(days=due_days)

        # Determine initial status
        status = RequestStatus.PENDING if data.send_immediately else RequestStatus.DRAFT

        # Create the request
        request = DocumentRequest(
            tenant_id=tenant_id,
            connection_id=data.connection_id,
            template_id=data.template_id,
            title=data.title,
            description=description,
            recipient_email=data.recipient_email,
            due_date=due_date,
            priority=priority.value,
            period_start=data.period_start,
            period_end=data.period_end,
            status=status.value,
            auto_remind=data.auto_remind,
            created_by=user_id,
        )

        created = await self.request_repo.create(request)

        # Log creation event
        await self._log_event(
            request_id=created.id,
            event_type=RequestEventType.CREATED,
            actor_type=ActorType.USER,
            actor_id=user_id,
        )

        # If sending immediately, also send
        if data.send_immediately:
            await self._mark_sent(created, user_id)

        return created

    async def send_request(
        self,
        request_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
    ) -> DocumentRequest:
        """Send a document request (change status from draft to pending).

        Args:
            request_id: The request ID.
            tenant_id: The tenant ID for authorization.
            user_id: The user sending the request.

        Returns:
            The updated document request.

        Raises:
            RequestNotFoundError: If the request is not found.
            PortalError: If the request is not in draft status.
        """
        request = await self.request_repo.get_by_id_and_tenant(
            request_id=request_id,
            tenant_id=tenant_id,
        )

        if not request:
            raise RequestNotFoundError(request_id)

        # Can only send drafts
        if request.status != RequestStatus.DRAFT.value:
            raise PortalError(
                f"Cannot send request in status '{request.status}'. Only draft requests can be sent."
            )

        await self._mark_sent(request, user_id)

        # Refresh to get updated values
        await self.db.refresh(request)
        return request

    async def get_request(
        self,
        request_id: UUID,
        tenant_id: UUID,
    ) -> DocumentRequest:
        """Get a document request by ID.

        Args:
            request_id: The request ID.
            tenant_id: The tenant ID for authorization.

        Returns:
            The document request.

        Raises:
            RequestNotFoundError: If the request is not found.
        """
        request = await self.request_repo.get_by_id_and_tenant(
            request_id=request_id,
            tenant_id=tenant_id,
        )

        if not request:
            raise RequestNotFoundError(request_id)

        return request

    async def get_request_with_details(
        self,
        request_id: UUID,
        tenant_id: UUID,
    ) -> DocumentRequest:
        """Get a document request with responses and events.

        Args:
            request_id: The request ID.
            tenant_id: The tenant ID for authorization.

        Returns:
            The document request with related data.

        Raises:
            RequestNotFoundError: If the request is not found.
        """
        # First verify tenant access
        request = await self.request_repo.get_by_id_and_tenant(
            request_id=request_id,
            tenant_id=tenant_id,
        )
        if not request:
            raise RequestNotFoundError(request_id)

        # Get with details
        request_with_details = await self.request_repo.get_with_details(request_id)
        if not request_with_details:
            raise RequestNotFoundError(request_id)

        return request_with_details

    async def update_request(
        self,
        request_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        **update_data: dict,
    ) -> DocumentRequest:
        """Update a document request.

        Only draft or pending requests can be fully updated.
        Once viewed or responded to, only limited updates are allowed.

        Args:
            request_id: The request ID.
            tenant_id: The tenant ID for authorization.
            user_id: The user making the update.
            **update_data: Fields to update.

        Returns:
            The updated document request.

        Raises:
            RequestNotFoundError: If the request is not found.
            PortalError: If the update is not allowed.
        """
        request = await self.request_repo.get_by_id_and_tenant(
            request_id=request_id,
            tenant_id=tenant_id,
        )

        if not request:
            raise RequestNotFoundError(request_id)

        # Restrict updates for completed/cancelled requests
        if request.status in [RequestStatus.COMPLETE.value, RequestStatus.CANCELLED.value]:
            raise PortalError(f"Cannot update request in status '{request.status}'.")

        # For viewed/in_progress, only allow limited updates
        limited_fields = {"auto_remind", "due_date"}
        if request.status in [RequestStatus.VIEWED.value, RequestStatus.IN_PROGRESS.value]:
            disallowed = set(update_data.keys()) - limited_fields
            if disallowed:
                raise PortalError(
                    f"Cannot update fields {disallowed} for request in status '{request.status}'."
                )

        # Apply updates
        updated = await self.request_repo.update(request_id, update_data)

        # Log update event
        await self._log_event(
            request_id=request_id,
            event_type=RequestEventType.UPDATED,
            actor_type=ActorType.USER,
            actor_id=user_id,
            event_data={"fields": list(update_data.keys())},
        )

        return updated

    async def cancel_request(
        self,
        request_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        reason: str | None = None,
    ) -> DocumentRequest:
        """Cancel a document request.

        Args:
            request_id: The request ID.
            tenant_id: The tenant ID for authorization.
            user_id: The user cancelling the request.
            reason: Optional cancellation reason.

        Returns:
            The cancelled document request.

        Raises:
            RequestNotFoundError: If the request is not found.
            PortalError: If the request cannot be cancelled.
        """
        request = await self.request_repo.get_by_id_and_tenant(
            request_id=request_id,
            tenant_id=tenant_id,
        )

        if not request:
            raise RequestNotFoundError(request_id)

        # Cannot cancel already completed/cancelled
        if request.status in [RequestStatus.COMPLETE.value, RequestStatus.CANCELLED.value]:
            raise PortalError(f"Cannot cancel request in status '{request.status}'.")

        # Update status
        await self.request_repo.update(
            request_id,
            {"status": RequestStatus.CANCELLED.value},
        )

        # Log cancellation
        await self._log_event(
            request_id=request_id,
            event_type=RequestEventType.CANCELLED,
            actor_type=ActorType.USER,
            actor_id=user_id,
            event_data={"reason": reason} if reason else None,
        )

        await self.db.refresh(request)
        return request

    async def complete_request(
        self,
        request_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        note: str | None = None,
    ) -> DocumentRequest:
        """Mark a document request as complete.

        Args:
            request_id: The request ID.
            tenant_id: The tenant ID for authorization.
            user_id: The user completing the request.
            note: Optional completion note.

        Returns:
            The completed document request.

        Raises:
            RequestNotFoundError: If the request is not found.
            PortalError: If the request cannot be completed.
        """
        request = await self.request_repo.get_by_id_and_tenant(
            request_id=request_id,
            tenant_id=tenant_id,
        )

        if not request:
            raise RequestNotFoundError(request_id)

        # Cannot complete drafts or already completed/cancelled
        if request.status in [
            RequestStatus.DRAFT.value,
            RequestStatus.COMPLETE.value,
            RequestStatus.CANCELLED.value,
        ]:
            raise PortalError(f"Cannot complete request in status '{request.status}'.")

        now = datetime.now(timezone.utc)
        await self.request_repo.update(
            request_id,
            {
                "status": RequestStatus.COMPLETE.value,
                "completed_at": now,
                "completed_by": user_id,
            },
        )

        # Log completion
        await self._log_event(
            request_id=request_id,
            event_type=RequestEventType.COMPLETED,
            actor_type=ActorType.USER,
            actor_id=user_id,
            event_data={"note": note} if note else None,
        )

        await self.db.refresh(request)
        return request

    async def list_requests(
        self,
        tenant_id: UUID,
        connection_id: UUID | None = None,
        status: RequestStatus | None = None,
        priority: RequestPriority | None = None,
        is_overdue: bool | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[DocumentRequest], int]:
        """List document requests for a tenant with filters.

        Args:
            tenant_id: The tenant ID.
            connection_id: Filter by client (XeroConnection).
            status: Filter by status.
            priority: Filter by priority.
            is_overdue: Filter overdue requests.
            from_date: Filter by creation date (from).
            to_date: Filter by creation date (to).
            search: Search in title/description.
            skip: Pagination offset.
            limit: Pagination limit.

        Returns:
            Tuple of (requests list, total count).
        """
        return await self.request_repo.list_by_tenant(
            tenant_id=tenant_id,
            connection_id=connection_id,
            status=status,
            priority=priority,
            is_overdue=is_overdue,
            from_date=from_date,
            to_date=to_date,
            search=search,
            skip=skip,
            limit=limit,
        )

    # =========================================================================
    # Client-Facing Methods (Portal)
    # =========================================================================

    async def mark_viewed(
        self,
        request_id: UUID,
        connection_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> DocumentRequest:
        """Mark a request as viewed by the client.

        Called when a client opens the request in the portal.
        Only updates status if currently pending.

        Args:
            request_id: The request ID.
            connection_id: The client's connection ID for authorization.
            ip_address: Client IP address.
            user_agent: Client user agent.

        Returns:
            The updated document request.

        Raises:
            RequestNotFoundError: If the request is not found.
        """
        request = await self.request_repo.get_by_id_and_connection(
            request_id=request_id,
            connection_id=connection_id,
        )

        if not request:
            raise RequestNotFoundError(request_id)

        # Only mark viewed if currently pending
        if request.status == RequestStatus.PENDING.value:
            now = datetime.now(timezone.utc)
            await self.request_repo.update(
                request_id,
                {
                    "status": RequestStatus.VIEWED.value,
                    "viewed_at": now,
                },
            )

            await self._log_event(
                request_id=request_id,
                event_type=RequestEventType.VIEWED,
                actor_type=ActorType.CLIENT,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            await self.db.refresh(request)

        return request

    async def submit_response(
        self,
        request_id: UUID,
        connection_id: UUID,
        message: str | None = None,
        document_ids: list[UUID] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> DocumentRequest:
        """Submit a client response to a document request.

        Creates a RequestResponse and updates request status to in_progress.

        Args:
            request_id: The request ID.
            connection_id: The client's connection ID for authorization.
            message: Optional response message from client.
            document_ids: Optional list of document IDs to attach.
            ip_address: Client IP address.
            user_agent: Client user agent.

        Returns:
            The updated document request.

        Raises:
            RequestNotFoundError: If the request is not found.
            PortalError: If the request cannot accept responses.
        """
        from app.modules.portal.models import RequestResponse as RequestResponseModel
        from app.modules.portal.repository import RequestResponseRepository

        request = await self.request_repo.get_by_id_and_connection(
            request_id=request_id,
            connection_id=connection_id,
        )

        if not request:
            raise RequestNotFoundError(request_id)

        # Cannot respond to draft, complete, or cancelled requests
        if request.status in [
            RequestStatus.DRAFT.value,
            RequestStatus.COMPLETE.value,
            RequestStatus.CANCELLED.value,
        ]:
            raise PortalError(f"Cannot respond to request in status '{request.status}'.")

        now = datetime.now(timezone.utc)
        response_repo = RequestResponseRepository(self.db)

        # Create the response
        response = RequestResponseModel(
            request_id=request_id,
            connection_id=request.connection_id,
            note=message,
            submitted_at=now,
        )
        created_response = await response_repo.create(response)

        # Attach documents if provided
        if document_ids:
            await response_repo.attach_documents(created_response.id, document_ids)

        # Update request status to in_progress and set responded_at
        if request.status in [RequestStatus.PENDING.value, RequestStatus.VIEWED.value]:
            await self.request_repo.update(
                request_id,
                {
                    "status": RequestStatus.IN_PROGRESS.value,
                    "responded_at": now,
                },
            )

        # Log response event
        await self._log_event(
            request_id=request_id,
            event_type=RequestEventType.RESPONSE_SUBMITTED,
            actor_type=ActorType.CLIENT,
            event_data={
                "response_id": str(created_response.id),
                "has_message": bool(message),
                "document_count": len(document_ids) if document_ids else 0,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self.db.refresh(request)
        return request

    async def get_client_request(
        self,
        request_id: UUID,
        connection_id: UUID,
    ) -> DocumentRequest:
        """Get a request from the client's perspective.

        Args:
            request_id: The request ID.
            connection_id: The client's connection ID for authorization.

        Returns:
            The document request.

        Raises:
            RequestNotFoundError: If the request is not found.
        """
        request = await self.request_repo.get_by_id_and_connection(
            request_id=request_id,
            connection_id=connection_id,
        )

        if not request:
            raise RequestNotFoundError(request_id)

        return request

    async def list_client_requests(
        self,
        connection_id: UUID,
        status: RequestStatus | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[DocumentRequest], int]:
        """List requests visible to a client.

        Only returns non-draft, non-cancelled requests.

        Args:
            connection_id: The client's connection ID.
            status: Filter by status.
            skip: Pagination offset.
            limit: Pagination limit.

        Returns:
            Tuple of (requests list, total count).
        """
        return await self.request_repo.list_by_connection(
            connection_id=connection_id,
            status=status,
            skip=skip,
            limit=limit,
        )

    # =========================================================================
    # Reminder Methods
    # =========================================================================

    async def send_reminder(
        self,
        request_id: UUID,
        tenant_id: UUID,
        reminder_type: str = "scheduled",
    ) -> DocumentRequest:
        """Send a reminder for a document request.

        Args:
            request_id: The request ID.
            tenant_id: The tenant ID for authorization.
            reminder_type: Type of reminder (scheduled, manual, overdue).

        Returns:
            The updated document request.

        Raises:
            RequestNotFoundError: If the request is not found.
            PortalError: If the request cannot receive reminders.
        """
        request = await self.request_repo.get_by_id_and_tenant(
            request_id=request_id,
            tenant_id=tenant_id,
        )

        if not request:
            raise RequestNotFoundError(request_id)

        # Only send reminders for pending/viewed requests
        if request.status not in [RequestStatus.PENDING.value, RequestStatus.VIEWED.value]:
            raise PortalError(f"Cannot send reminder for request in status '{request.status}'.")

        # Check if auto-remind is enabled
        if not request.auto_remind and reminder_type == "scheduled":
            raise PortalError("Auto-remind is disabled for this request.")

        now = datetime.now(timezone.utc)

        # Update reminder tracking
        await self.request_repo.update(
            request_id,
            {
                "reminder_count": request.reminder_count + 1,
                "last_reminder_at": now,
            },
        )

        # Log reminder event
        await self._log_event(
            request_id=request_id,
            event_type=RequestEventType.REMINDER_SENT,
            actor_type=ActorType.SYSTEM,
            event_data={
                "reminder_type": reminder_type,
                "reminder_number": request.reminder_count + 1,
            },
        )

        # Send push notification reminder (Spec 032)
        is_overdue = request.due_date and request.due_date < date.today()
        await self._send_push_notification(
            connection_id=request.connection_id,
            notification_type="overdue" if is_overdue else "reminder",
            title="Document Request Reminder" if not is_overdue else "Overdue Document Request",
            body=f"{request.title}"
            + (f" - Was due {request.due_date}" if is_overdue else f" - Due {request.due_date}"),
            url=f"/portal/requests/{request.id}",
            priority=request.priority,
        )

        await self.db.refresh(request)
        return request

    async def toggle_auto_remind(
        self,
        request_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        enabled: bool,
    ) -> DocumentRequest:
        """Toggle auto-remind for a document request.

        Args:
            request_id: The request ID.
            tenant_id: The tenant ID for authorization.
            user_id: The user making the change.
            enabled: Whether to enable auto-remind.

        Returns:
            The updated document request.
        """
        request = await self.request_repo.get_by_id_and_tenant(
            request_id=request_id,
            tenant_id=tenant_id,
        )

        if not request:
            raise RequestNotFoundError(request_id)

        await self.request_repo.update(request_id, {"auto_remind": enabled})

        await self._log_event(
            request_id=request_id,
            event_type=RequestEventType.UPDATED,
            actor_type=ActorType.USER,
            actor_id=user_id,
            event_data={"auto_remind": enabled},
        )

        await self.db.refresh(request)
        return request

    async def get_requests_due_for_reminder(
        self,
        days_before_due: int = 3,
        days_after_due: int = 1,
        min_days_since_last_reminder: int = 3,
    ) -> list[DocumentRequest]:
        """Get requests that need reminders.

        Args:
            days_before_due: Send reminder this many days before due.
            days_after_due: Send overdue reminder this many days after due.
            min_days_since_last_reminder: Minimum days between reminders.

        Returns:
            List of requests needing reminders.
        """
        return await self.request_repo.get_pending_reminders(
            days_since_last=min_days_since_last_reminder
        )

    # =========================================================================
    # Tracking Methods
    # =========================================================================

    async def get_tracking_summary(
        self,
        tenant_id: UUID,
    ) -> dict:
        """Get tracking summary statistics for the tenant.

        Args:
            tenant_id: The tenant ID.

        Returns:
            Summary statistics dictionary.
        """
        return await self.request_repo.get_tracking_summary(tenant_id)

    async def get_tracking_data(
        self,
        tenant_id: UUID,
        status: RequestStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[dict, list[DocumentRequest]]:
        """Get full tracking data with grouped requests.

        Args:
            tenant_id: The tenant ID.
            status: Optional filter by status.
            skip: Pagination offset.
            limit: Pagination limit.

        Returns:
            Tuple of (summary, requests with connection info).
        """
        summary = await self.request_repo.get_tracking_summary(tenant_id)
        requests = await self.request_repo.list_for_tracking(
            tenant_id=tenant_id,
            status=status,
            skip=skip,
            limit=limit,
        )
        return summary, requests

    async def get_recent_activity(
        self,
        tenant_id: UUID,
        limit: int = 10,
    ) -> list[DocumentRequest]:
        """Get recently active requests for tracking.

        Args:
            tenant_id: The tenant ID.
            limit: Number of requests to return.

        Returns:
            List of recently active requests.
        """
        return await self.request_repo.list_recent_activity(tenant_id, limit)

    # =========================================================================
    # Internal Helper Methods
    # =========================================================================

    async def _mark_sent(self, request: DocumentRequest, user_id: UUID) -> None:
        """Mark a request as sent and update timestamps.

        Args:
            request: The document request.
            user_id: The user sending the request.
        """
        now = datetime.now(timezone.utc)
        await self.request_repo.update(
            request.id,
            {
                "status": RequestStatus.PENDING.value,
                "sent_at": now,
            },
        )

        await self._log_event(
            request_id=request.id,
            event_type=RequestEventType.SENT,
            actor_type=ActorType.USER,
            actor_id=user_id,
        )

        # Send push notification to client (Spec 032)
        await self._send_push_notification(
            connection_id=request.connection_id,
            notification_type="new_request",
            title="New Document Request",
            body=f"{request.title}" + (f" - Due {request.due_date}" if request.due_date else ""),
            url=f"/portal/requests/{request.id}",
            priority=request.priority,
        )

    async def _log_event(
        self,
        request_id: UUID,
        event_type: RequestEventType,
        actor_type: ActorType,
        actor_id: UUID | None = None,
        event_data: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> RequestEvent:
        """Log an event for a document request.

        Args:
            request_id: The request ID.
            event_type: Type of event.
            actor_type: Type of actor (user, client, system).
            actor_id: ID of the actor.
            event_data: Optional event metadata.
            ip_address: Client IP address.
            user_agent: Client user agent.

        Returns:
            The created event.
        """
        event = RequestEvent(
            request_id=request_id,
            event_type=event_type.value,
            event_data=event_data,
            actor_type=actor_type.value,
            actor_id=actor_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return await self.event_repo.create(event)

    async def _send_push_notification(
        self,
        connection_id: UUID,
        notification_type: str,
        title: str,
        body: str,
        url: str | None = None,
        priority: str | None = None,
    ) -> None:
        """Send a push notification to a client.

        Fails silently if push notifications are not configured or
        the client has no active subscriptions.

        Args:
            connection_id: The client's connection ID.
            notification_type: Type of notification (new_request, reminder, etc.)
            title: Notification title.
            body: Notification body.
            url: Optional URL to open on click.
            priority: Request priority for urgent notification styling.

        Spec: 032-pwa-mobile-document-capture
        """
        try:
            from app.modules.notifications.push.models import NotificationType
            from app.modules.notifications.push.schemas import PushNotificationPayload
            from app.modules.notifications.push.service import PushSubscriptionService

            # Map notification type
            type_mapping = {
                "new_request": NotificationType.NEW_REQUEST,
                "urgent_request": NotificationType.URGENT_REQUEST,
                "reminder": NotificationType.REQUEST_REMINDER,
                "overdue": NotificationType.REQUEST_OVERDUE,
            }

            # Use urgent type for high/urgent priority
            if priority in ["high", "urgent"] and notification_type == "new_request":
                push_type = NotificationType.URGENT_REQUEST
            else:
                push_type = type_mapping.get(notification_type, NotificationType.NEW_REQUEST)

            payload = PushNotificationPayload(
                notification_type=push_type,
                title=title,
                body=body,
                url=url or "/portal",
                data={
                    "connection_id": str(connection_id),
                    "type": notification_type,
                },
                require_interaction=priority in ["high", "urgent"],
            )

            push_service = PushSubscriptionService(self.db)
            await push_service.send_notification(
                client_id=connection_id,
                payload=payload,
            )

            logger.debug(
                f"Push notification sent for {notification_type}",
                extra={"connection_id": str(connection_id)},
            )

        except ImportError:
            # Push module not available
            logger.debug("Push notifications not available")
        except Exception as e:
            # Don't fail the main operation if push fails
            logger.warning(
                f"Failed to send push notification: {e}",
                extra={"connection_id": str(connection_id), "error": str(e)},
            )

    def to_response(self, request: DocumentRequest) -> RequestResponse:
        """Convert a DocumentRequest model to response schema.

        Args:
            request: The document request model.

        Returns:
            The response schema with computed fields.
        """
        # Calculate computed fields
        is_overdue = False
        days_until_due = None

        if request.due_date:
            today = date.today()
            days_until_due = (request.due_date - today).days

            if days_until_due < 0 and request.status not in [
                RequestStatus.COMPLETE.value,
                RequestStatus.CANCELLED.value,
            ]:
                is_overdue = True

        return RequestResponse(
            id=request.id,
            connection_id=request.connection_id,
            template_id=request.template_id,
            title=request.title,
            description=request.description,
            recipient_email=request.recipient_email,
            due_date=request.due_date,
            priority=RequestPriority(request.priority),
            period_start=request.period_start,
            period_end=request.period_end,
            status=RequestStatus(request.status),
            sent_at=request.sent_at,
            viewed_at=request.viewed_at,
            responded_at=request.responded_at,
            completed_at=request.completed_at,
            auto_remind=request.auto_remind,
            reminder_count=request.reminder_count,
            last_reminder_at=request.last_reminder_at,
            bulk_request_id=request.bulk_request_id,
            created_at=request.created_at,
            updated_at=request.updated_at,
            is_overdue=is_overdue,
            days_until_due=days_until_due,
            response_count=len(request.responses)
            if "responses" in request.__dict__ and request.responses
            else 0,
            document_count=sum(
                len(r.documents) if "documents" in r.__dict__ and r.documents else 0
                for r in (
                    request.responses
                    if "responses" in request.__dict__ and request.responses
                    else []
                )
            ),
        )
