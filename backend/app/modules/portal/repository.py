"""Repository pattern for portal data access.

Provides database operations for:
- PortalInvitation
- PortalSession
- DocumentRequestTemplate
- DocumentRequest
- RequestResponse
- PortalDocument
- RequestEvent
- BulkRequest

Spec: 030-client-portal-document-requests
"""

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.portal.enums import (
    BulkRequestStatus,
    InvitationStatus,
    RequestPriority,
    RequestStatus,
)
from app.modules.portal.models import (
    BulkRequest,
    DocumentRequest,
    DocumentRequestTemplate,
    PortalDocument,
    PortalInvitation,
    PortalSession,
    RequestEvent,
    RequestResponse,
)

# =============================================================================
# Portal Invitation Repository
# =============================================================================


class PortalInvitationRepository:
    """Repository for PortalInvitation data access."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, invitation_id: UUID) -> PortalInvitation | None:
        """Get invitation by ID."""
        result = await self.session.execute(
            select(PortalInvitation).where(PortalInvitation.id == invitation_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_tenant(
        self, invitation_id: UUID, tenant_id: UUID
    ) -> PortalInvitation | None:
        """Get invitation by ID with tenant filtering."""
        result = await self.session.execute(
            select(PortalInvitation).where(
                PortalInvitation.id == invitation_id,
                PortalInvitation.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_token_hash(self, token_hash: str) -> PortalInvitation | None:
        """Get invitation by token hash."""
        result = await self.session.execute(
            select(PortalInvitation).where(PortalInvitation.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get_pending_by_connection(self, connection_id: UUID) -> PortalInvitation | None:
        """Get pending invitation for a connection."""
        result = await self.session.execute(
            select(PortalInvitation).where(
                PortalInvitation.connection_id == connection_id,
                PortalInvitation.status == InvitationStatus.PENDING.value,
                PortalInvitation.expires_at > datetime.now(timezone.utc),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, invitation: PortalInvitation) -> PortalInvitation:
        """Create a new invitation."""
        self.session.add(invitation)
        await self.session.flush()
        await self.session.refresh(invitation)
        return invitation

    async def update(self, invitation_id: UUID, data: dict[str, Any]) -> PortalInvitation | None:
        """Update an existing invitation."""
        invitation = await self.get_by_id(invitation_id)
        if not invitation:
            return None

        for key, value in data.items():
            if hasattr(invitation, key) and value is not None:
                setattr(invitation, key, value)

        await self.session.flush()
        await self.session.refresh(invitation)
        return invitation

    async def list_by_connection(
        self, connection_id: UUID, limit: int = 10
    ) -> list[PortalInvitation]:
        """List invitations for a connection."""
        result = await self.session.execute(
            select(PortalInvitation)
            .where(PortalInvitation.connection_id == connection_id)
            .order_by(PortalInvitation.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        status: InvitationStatus | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[PortalInvitation], int]:
        """List invitations for a tenant with pagination."""
        base_query = select(PortalInvitation).where(PortalInvitation.tenant_id == tenant_id)

        if status:
            base_query = base_query.where(PortalInvitation.status == status.value)

        # Count total
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar() or 0

        # Fetch paginated
        query = base_query.order_by(PortalInvitation.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def expire_old_invitations(self) -> int:
        """Mark expired invitations as EXPIRED. Returns count updated."""
        from sqlalchemy import update

        now = datetime.now(timezone.utc)
        stmt = (
            update(PortalInvitation)
            .where(
                PortalInvitation.status == InvitationStatus.PENDING.value,
                PortalInvitation.expires_at < now,
            )
            .values(status=InvitationStatus.EXPIRED.value)
        )
        result = await self.session.execute(stmt)
        return result.rowcount


# =============================================================================
# Portal Session Repository
# =============================================================================


class PortalSessionRepository:
    """Repository for PortalSession data access."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, session_id: UUID) -> PortalSession | None:
        """Get session by ID."""
        result = await self.session.execute(
            select(PortalSession).where(PortalSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_by_refresh_token_hash(self, token_hash: str) -> PortalSession | None:
        """Get session by refresh token hash."""
        result = await self.session.execute(
            select(PortalSession).where(PortalSession.refresh_token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get_active_by_connection(self, connection_id: UUID) -> list[PortalSession]:
        """Get all active sessions for a connection."""
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(PortalSession).where(
                PortalSession.connection_id == connection_id,
                PortalSession.revoked == False,  # noqa: E712
                PortalSession.expires_at > now,
            )
        )
        return list(result.scalars().all())

    async def create(self, portal_session: PortalSession) -> PortalSession:
        """Create a new portal session."""
        self.session.add(portal_session)
        await self.session.flush()
        await self.session.refresh(portal_session)
        return portal_session

    async def update(self, session_id: UUID, data: dict[str, Any]) -> PortalSession | None:
        """Update an existing session."""
        portal_session = await self.get_by_id(session_id)
        if not portal_session:
            return None

        for key, value in data.items():
            if hasattr(portal_session, key) and value is not None:
                setattr(portal_session, key, value)

        await self.session.flush()
        await self.session.refresh(portal_session)
        return portal_session

    async def revoke(self, session_id: UUID, reason: str | None = None) -> PortalSession | None:
        """Revoke a session."""
        return await self.update(
            session_id,
            {
                "revoked": True,
                "revoked_at": datetime.now(timezone.utc),
                "revoke_reason": reason,
            },
        )

    async def revoke_all_for_connection(
        self, connection_id: UUID, reason: str | None = None
    ) -> int:
        """Revoke all sessions for a connection. Returns count revoked."""
        from sqlalchemy import update

        now = datetime.now(timezone.utc)
        stmt = (
            update(PortalSession)
            .where(
                PortalSession.connection_id == connection_id,
                PortalSession.revoked == False,  # noqa: E712
            )
            .values(revoked=True, revoked_at=now, revoke_reason=reason)
        )
        result = await self.session.execute(stmt)
        return result.rowcount

    async def update_last_active(self, session_id: UUID) -> None:
        """Update last active timestamp."""
        from sqlalchemy import update

        stmt = (
            update(PortalSession)
            .where(PortalSession.id == session_id)
            .values(last_active_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)


# =============================================================================
# Document Request Template Repository
# =============================================================================


class DocumentRequestTemplateRepository:
    """Repository for DocumentRequestTemplate data access."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, template_id: UUID) -> DocumentRequestTemplate | None:
        """Get template by ID."""
        result = await self.session.execute(
            select(DocumentRequestTemplate).where(DocumentRequestTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_tenant(
        self, template_id: UUID, tenant_id: UUID
    ) -> DocumentRequestTemplate | None:
        """Get template by ID accessible to tenant (own or system)."""
        result = await self.session.execute(
            select(DocumentRequestTemplate).where(
                DocumentRequestTemplate.id == template_id,
                or_(
                    DocumentRequestTemplate.tenant_id == tenant_id,
                    DocumentRequestTemplate.is_system == True,  # noqa: E712
                ),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, template: DocumentRequestTemplate) -> DocumentRequestTemplate:
        """Create a new template."""
        self.session.add(template)
        await self.session.flush()
        await self.session.refresh(template)
        return template

    async def update(
        self, template_id: UUID, data: dict[str, Any]
    ) -> DocumentRequestTemplate | None:
        """Update an existing template."""
        template = await self.get_by_id(template_id)
        if not template:
            return None

        for key, value in data.items():
            if hasattr(template, key) and value is not None:
                setattr(template, key, value)

        await self.session.flush()
        await self.session.refresh(template)
        return template

    async def list_available(
        self, tenant_id: UUID, include_inactive: bool = False
    ) -> list[DocumentRequestTemplate]:
        """List templates available to a tenant (own + system)."""
        query = select(DocumentRequestTemplate).where(
            or_(
                DocumentRequestTemplate.tenant_id == tenant_id,
                DocumentRequestTemplate.is_system == True,  # noqa: E712
            )
        )

        if not include_inactive:
            query = query.where(DocumentRequestTemplate.is_active == True)  # noqa: E712

        query = query.order_by(
            DocumentRequestTemplate.is_system.desc(),
            DocumentRequestTemplate.name,
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())


# =============================================================================
# Document Request Repository
# =============================================================================


class DocumentRequestRepository:
    """Repository for DocumentRequest data access."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, request_id: UUID) -> DocumentRequest | None:
        """Get request by ID."""
        result = await self.session.execute(
            select(DocumentRequest).where(DocumentRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_tenant(
        self, request_id: UUID, tenant_id: UUID
    ) -> DocumentRequest | None:
        """Get request by ID with tenant filtering."""
        result = await self.session.execute(
            select(DocumentRequest).where(
                DocumentRequest.id == request_id,
                DocumentRequest.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_connection(
        self, request_id: UUID, connection_id: UUID
    ) -> DocumentRequest | None:
        """Get request by ID with connection filtering (for portal access)."""
        result = await self.session.execute(
            select(DocumentRequest).where(
                DocumentRequest.id == request_id,
                DocumentRequest.connection_id == connection_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_with_details(
        self, request_id: UUID, tenant_id: UUID | None = None
    ) -> DocumentRequest | None:
        """Get request with related responses, documents, and events."""
        query = (
            select(DocumentRequest)
            .options(
                selectinload(DocumentRequest.responses).selectinload(RequestResponse.documents),
                selectinload(DocumentRequest.events),
            )
            .where(DocumentRequest.id == request_id)
        )
        if tenant_id is not None:
            query = query.where(DocumentRequest.tenant_id == tenant_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create(self, request: DocumentRequest) -> DocumentRequest:
        """Create a new document request."""
        self.session.add(request)
        await self.session.flush()
        await self.session.refresh(request)
        return request

    async def update(self, request_id: UUID, data: dict[str, Any]) -> DocumentRequest | None:
        """Update an existing request."""
        request = await self.get_by_id(request_id)
        if not request:
            return None

        for key, value in data.items():
            if hasattr(request, key) and value is not None:
                setattr(request, key, value)

        await self.session.flush()
        await self.session.refresh(request)
        return request

    async def list_by_tenant(
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
        """List requests for a tenant with filters and pagination."""
        base_query = select(DocumentRequest).where(DocumentRequest.tenant_id == tenant_id)

        if connection_id:
            base_query = base_query.where(DocumentRequest.connection_id == connection_id)
        if status:
            base_query = base_query.where(DocumentRequest.status == status.value)
        if priority:
            base_query = base_query.where(DocumentRequest.priority == priority.value)
        if is_overdue:
            today = date.today()
            base_query = base_query.where(
                DocumentRequest.due_date < today,
                DocumentRequest.status.not_in(
                    [RequestStatus.COMPLETE.value, RequestStatus.CANCELLED.value]
                ),
            )
        if from_date:
            base_query = base_query.where(DocumentRequest.created_at >= from_date)
        if to_date:
            base_query = base_query.where(DocumentRequest.created_at <= to_date)
        if search:
            pattern = f"%{search}%"
            base_query = base_query.where(
                or_(
                    DocumentRequest.title.ilike(pattern),
                    DocumentRequest.description.ilike(pattern),
                )
            )

        # Count total
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar() or 0

        # Fetch paginated
        query = base_query.order_by(DocumentRequest.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def list_by_connection(
        self,
        connection_id: UUID,
        status: RequestStatus | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[DocumentRequest], int]:
        """List requests for a connection (portal view)."""
        base_query = select(DocumentRequest).where(
            DocumentRequest.connection_id == connection_id,
            DocumentRequest.status != RequestStatus.DRAFT.value,  # Hide drafts
        )

        if status:
            base_query = base_query.where(DocumentRequest.status == status.value)

        # Count total
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar() or 0

        # Fetch paginated
        query = base_query.order_by(DocumentRequest.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def get_pending_reminders(self, days_since_last: int = 3) -> list[DocumentRequest]:
        """Get requests due for auto-reminders."""
        from datetime import timedelta

        threshold = datetime.now(timezone.utc) - timedelta(days=days_since_last)

        result = await self.session.execute(
            select(DocumentRequest).where(
                DocumentRequest.auto_remind == True,  # noqa: E712
                DocumentRequest.status.in_(
                    [RequestStatus.PENDING.value, RequestStatus.VIEWED.value]
                ),
                or_(
                    DocumentRequest.last_reminder_at.is_(None),
                    DocumentRequest.last_reminder_at < threshold,
                ),
            )
        )
        return list(result.scalars().all())

    async def count_by_status(self, tenant_id: UUID) -> dict[str, int]:
        """Count requests by status for a tenant."""
        result = await self.session.execute(
            select(DocumentRequest.status, func.count(DocumentRequest.id))
            .where(DocumentRequest.tenant_id == tenant_id)
            .group_by(DocumentRequest.status)
        )
        return {status: count for status, count in result.all()}

    async def get_tracking_summary(self, tenant_id: UUID) -> dict:
        """Get tracking summary statistics for a tenant.

        Returns counts by status plus overdue, due_today, due_this_week.
        """
        from datetime import timedelta

        today = date.today()
        week_end = today + timedelta(days=7)

        # Get status counts
        status_result = await self.session.execute(
            select(DocumentRequest.status, func.count(DocumentRequest.id))
            .where(DocumentRequest.tenant_id == tenant_id)
            .group_by(DocumentRequest.status)
        )
        status_counts = {status: count for status, count in status_result.all()}

        # Count overdue (due_date < today, not complete/cancelled)
        overdue_result = await self.session.execute(
            select(func.count(DocumentRequest.id)).where(
                DocumentRequest.tenant_id == tenant_id,
                DocumentRequest.due_date < today,
                DocumentRequest.status.not_in(
                    [RequestStatus.COMPLETE.value, RequestStatus.CANCELLED.value]
                ),
            )
        )
        overdue = overdue_result.scalar() or 0

        # Count due today
        due_today_result = await self.session.execute(
            select(func.count(DocumentRequest.id)).where(
                DocumentRequest.tenant_id == tenant_id,
                DocumentRequest.due_date == today,
                DocumentRequest.status.not_in(
                    [RequestStatus.COMPLETE.value, RequestStatus.CANCELLED.value]
                ),
            )
        )
        due_today = due_today_result.scalar() or 0

        # Count due this week (today to +7 days)
        due_week_result = await self.session.execute(
            select(func.count(DocumentRequest.id)).where(
                DocumentRequest.tenant_id == tenant_id,
                DocumentRequest.due_date >= today,
                DocumentRequest.due_date <= week_end,
                DocumentRequest.status.not_in(
                    [RequestStatus.COMPLETE.value, RequestStatus.CANCELLED.value]
                ),
            )
        )
        due_this_week = due_week_result.scalar() or 0

        return {
            "total": sum(status_counts.values()),
            "pending": status_counts.get(RequestStatus.PENDING.value, 0),
            "viewed": status_counts.get(RequestStatus.VIEWED.value, 0),
            "in_progress": status_counts.get(RequestStatus.IN_PROGRESS.value, 0),
            "completed": status_counts.get(RequestStatus.COMPLETE.value, 0),
            "cancelled": status_counts.get(RequestStatus.CANCELLED.value, 0),
            "overdue": overdue,
            "due_today": due_today,
            "due_this_week": due_this_week,
        }

    async def list_for_tracking(
        self,
        tenant_id: UUID,
        status: RequestStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[DocumentRequest]:
        """List requests with connection info for tracking view.

        Returns requests with their connection (organization) loaded.
        """

        query = (
            select(DocumentRequest)
            .options(selectinload(DocumentRequest.connection))
            .where(
                DocumentRequest.tenant_id == tenant_id,
                # Exclude drafts from tracking
                DocumentRequest.status != RequestStatus.DRAFT.value,
            )
        )

        if status:
            query = query.where(DocumentRequest.status == status.value)

        query = (
            query.order_by(
                # Priority ordering: overdue first, then by due date
                DocumentRequest.due_date.asc().nulls_last(),
                DocumentRequest.created_at.desc(),
            )
            .offset(skip)
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_recent_activity(
        self,
        tenant_id: UUID,
        limit: int = 10,
    ) -> list[DocumentRequest]:
        """List recently active requests for tracking.

        Orders by most recent activity (viewed, responded, or updated).
        """
        query = (
            select(DocumentRequest)
            .options(selectinload(DocumentRequest.connection))
            .where(
                DocumentRequest.tenant_id == tenant_id,
                DocumentRequest.status != RequestStatus.DRAFT.value,
            )
            .order_by(DocumentRequest.updated_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())


# =============================================================================
# Request Response Repository
# =============================================================================


class RequestResponseRepository:
    """Repository for RequestResponse data access."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, response_id: UUID) -> RequestResponse | None:
        """Get response by ID."""
        result = await self.session.execute(
            select(RequestResponse).where(RequestResponse.id == response_id)
        )
        return result.scalar_one_or_none()

    async def get_with_documents(self, response_id: UUID) -> RequestResponse | None:
        """Get response with attached documents."""
        result = await self.session.execute(
            select(RequestResponse)
            .options(selectinload(RequestResponse.documents))
            .where(RequestResponse.id == response_id)
        )
        return result.scalar_one_or_none()

    async def create(self, response: RequestResponse) -> RequestResponse:
        """Create a new response."""
        self.session.add(response)
        await self.session.flush()
        await self.session.refresh(response)
        return response

    async def list_by_request(self, request_id: UUID) -> list[RequestResponse]:
        """List all responses for a request."""
        result = await self.session.execute(
            select(RequestResponse)
            .where(RequestResponse.request_id == request_id)
            .order_by(RequestResponse.submitted_at.desc())
        )
        return list(result.scalars().all())

    async def count_by_request(self, request_id: UUID) -> int:
        """Count responses for a request."""
        result = await self.session.execute(
            select(func.count(RequestResponse.id)).where(RequestResponse.request_id == request_id)
        )
        return result.scalar() or 0

    async def attach_documents(self, response_id: UUID, document_ids: list[UUID]) -> None:
        """Attach documents to a response.

        Updates the response_id on each PortalDocument.

        Args:
            response_id: The response ID to attach documents to.
            document_ids: List of document IDs to attach.
        """
        if not document_ids:
            return

        # Update documents to link to this response
        for doc_id in document_ids:
            await self.session.execute(
                PortalDocument.__table__.update()
                .where(PortalDocument.id == doc_id)
                .values(response_id=response_id)
            )
        await self.session.flush()


# =============================================================================
# Portal Document Repository
# =============================================================================


class PortalDocumentRepository:
    """Repository for PortalDocument data access."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, document_id: UUID) -> PortalDocument | None:
        """Get document by ID."""
        result = await self.session.execute(
            select(PortalDocument).where(PortalDocument.id == document_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_tenant(
        self, document_id: UUID, tenant_id: UUID
    ) -> PortalDocument | None:
        """Get document by ID with tenant filtering."""
        result = await self.session.execute(
            select(PortalDocument).where(
                PortalDocument.id == document_id,
                PortalDocument.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_connection(
        self, document_id: UUID, connection_id: UUID
    ) -> PortalDocument | None:
        """Get document by ID with connection filtering (for portal access)."""
        result = await self.session.execute(
            select(PortalDocument).where(
                PortalDocument.id == document_id,
                PortalDocument.connection_id == connection_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_s3_key(self, s3_key: str) -> PortalDocument | None:
        """Get document by S3 key."""
        result = await self.session.execute(
            select(PortalDocument).where(PortalDocument.s3_key == s3_key)
        )
        return result.scalar_one_or_none()

    async def create(self, document: PortalDocument) -> PortalDocument:
        """Create a new document record."""
        self.session.add(document)
        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def update(self, document_id: UUID, data: dict[str, Any]) -> PortalDocument | None:
        """Update an existing document."""
        document = await self.get_by_id(document_id)
        if not document:
            return None

        for key, value in data.items():
            if hasattr(document, key) and value is not None:
                setattr(document, key, value)

        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def delete(self, document_id: UUID) -> bool:
        """Delete a document. Returns True if deleted."""
        document = await self.get_by_id(document_id)
        if not document:
            return False

        await self.session.delete(document)
        await self.session.flush()
        return True

    async def list_by_connection(
        self,
        connection_id: UUID,
        document_type: str | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[PortalDocument], int]:
        """List documents for a connection with filters."""
        base_query = select(PortalDocument).where(PortalDocument.connection_id == connection_id)

        if document_type:
            base_query = base_query.where(PortalDocument.document_type == document_type)
        if period_start and period_end:
            base_query = base_query.where(
                and_(
                    PortalDocument.period_start >= period_start,
                    PortalDocument.period_end <= period_end,
                )
            )

        # Count total
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar() or 0

        # Fetch paginated
        query = base_query.order_by(PortalDocument.uploaded_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def list_by_response(self, response_id: UUID) -> list[PortalDocument]:
        """List documents attached to a response."""
        result = await self.session.execute(
            select(PortalDocument)
            .where(PortalDocument.response_id == response_id)
            .order_by(PortalDocument.uploaded_at.asc())
        )
        return list(result.scalars().all())

    async def count_by_connection(self, connection_id: UUID) -> int:
        """Count documents for a connection."""
        result = await self.session.execute(
            select(func.count(PortalDocument.id)).where(
                PortalDocument.connection_id == connection_id
            )
        )
        return result.scalar() or 0

    async def get_pending_scans(self, limit: int = 100) -> list[PortalDocument]:
        """Get documents pending virus scan."""
        from app.modules.portal.enums import ScanStatus

        result = await self.session.execute(
            select(PortalDocument)
            .where(PortalDocument.scan_status == ScanStatus.PENDING.value)
            .order_by(PortalDocument.uploaded_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())


# =============================================================================
# Request Event Repository
# =============================================================================


class RequestEventRepository:
    """Repository for RequestEvent data access."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def create(self, event: RequestEvent) -> RequestEvent:
        """Create a new event."""
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def list_by_request(self, request_id: UUID, limit: int = 50) -> list[RequestEvent]:
        """List events for a request."""
        result = await self.session.execute(
            select(RequestEvent)
            .where(RequestEvent.request_id == request_id)
            .order_by(RequestEvent.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_latest_by_type(self, request_id: UUID, event_type: str) -> RequestEvent | None:
        """Get the latest event of a specific type for a request."""
        result = await self.session.execute(
            select(RequestEvent)
            .where(
                RequestEvent.request_id == request_id,
                RequestEvent.event_type == event_type,
            )
            .order_by(RequestEvent.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


# =============================================================================
# Bulk Request Repository
# =============================================================================


class BulkRequestRepository:
    """Repository for BulkRequest data access."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, bulk_id: UUID) -> BulkRequest | None:
        """Get bulk request by ID."""
        result = await self.session.execute(select(BulkRequest).where(BulkRequest.id == bulk_id))
        return result.scalar_one_or_none()

    async def get_by_id_and_tenant(self, bulk_id: UUID, tenant_id: UUID) -> BulkRequest | None:
        """Get bulk request by ID with tenant filtering."""
        result = await self.session.execute(
            select(BulkRequest).where(
                BulkRequest.id == bulk_id,
                BulkRequest.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, bulk_request: BulkRequest) -> BulkRequest:
        """Create a new bulk request."""
        self.session.add(bulk_request)
        await self.session.flush()
        await self.session.refresh(bulk_request)
        return bulk_request

    async def update(self, bulk_id: UUID, data: dict[str, Any]) -> BulkRequest | None:
        """Update an existing bulk request."""
        bulk_request = await self.get_by_id(bulk_id)
        if not bulk_request:
            return None

        for key, value in data.items():
            if hasattr(bulk_request, key) and value is not None:
                setattr(bulk_request, key, value)

        await self.session.flush()
        await self.session.refresh(bulk_request)
        return bulk_request

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        status: BulkRequestStatus | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[BulkRequest], int]:
        """List bulk requests for a tenant."""
        base_query = select(BulkRequest).where(BulkRequest.tenant_id == tenant_id)

        if status:
            base_query = base_query.where(BulkRequest.status == status.value)

        # Count total
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar() or 0

        # Fetch paginated
        query = base_query.order_by(BulkRequest.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def get_pending(self) -> list[BulkRequest]:
        """Get all pending bulk requests for processing."""
        result = await self.session.execute(
            select(BulkRequest).where(
                BulkRequest.status.in_(
                    [BulkRequestStatus.PENDING.value, BulkRequestStatus.PROCESSING.value]
                )
            )
        )
        return list(result.scalars().all())
