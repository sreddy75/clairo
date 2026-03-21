"""Portal dashboard service.

Provides dashboard data aggregation for client portal.

Spec: 030-client-portal-document-requests
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.xero.models import XeroConnection
from app.modules.portal.enums import RequestStatus
from app.modules.portal.models import DocumentRequest, PortalDocument, PortalSession
from app.modules.portal.schemas import PortalDashboardResponse, RequestResponse


class PortalDashboardService:
    """Service for aggregating client portal dashboard data."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize service with database session."""
        self.session = session

    async def get_dashboard(
        self,
        connection_id: UUID,
        tenant_id: UUID,
    ) -> PortalDashboardResponse:
        """Get aggregated dashboard data for a client.

        Args:
            connection_id: The XeroConnection ID.
            tenant_id: The tenant ID for access control.

        Returns:
            Dashboard data including pending requests, documents, etc.
        """
        # Get organization name from XeroConnection
        connection_result = await self.session.execute(
            select(XeroConnection).where(
                XeroConnection.id == connection_id,
                XeroConnection.tenant_id == tenant_id,
            )
        )
        connection = connection_result.scalar_one_or_none()
        organization_name = connection.organization_name if connection else "Unknown"

        # Count pending requests (sent but not completed)
        pending_result = await self.session.execute(
            select(func.count(DocumentRequest.id)).where(
                DocumentRequest.connection_id == connection_id,
                DocumentRequest.status.in_(
                    [
                        RequestStatus.PENDING.value,
                        RequestStatus.VIEWED.value,
                        RequestStatus.IN_PROGRESS.value,
                    ]
                ),
            )
        )
        pending_requests = pending_result.scalar() or 0

        # Count unread requests (sent but not viewed)
        unread_result = await self.session.execute(
            select(func.count(DocumentRequest.id)).where(
                DocumentRequest.connection_id == connection_id,
                DocumentRequest.status == RequestStatus.PENDING.value,
                DocumentRequest.viewed_at.is_(None),
            )
        )
        unread_requests = unread_result.scalar() or 0

        # Count total documents
        docs_result = await self.session.execute(
            select(func.count(PortalDocument.id)).where(
                PortalDocument.connection_id == connection_id,
            )
        )
        total_documents = docs_result.scalar() or 0

        # Get recent requests (last 5)
        recent_result = await self.session.execute(
            select(DocumentRequest)
            .where(DocumentRequest.connection_id == connection_id)
            .order_by(DocumentRequest.created_at.desc())
            .limit(5)
        )
        recent_requests_models = recent_result.scalars().all()

        # Convert to response schemas
        recent_requests = []
        for req in recent_requests_models:
            # Calculate computed fields
            is_overdue = False
            days_until_due = None
            if req.due_date:
                today = datetime.now(timezone.utc).date()
                days_until_due = (req.due_date - today).days
                is_overdue = days_until_due < 0 and req.status not in [
                    RequestStatus.COMPLETE.value,
                    RequestStatus.CANCELLED.value,
                ]

            recent_requests.append(
                RequestResponse(
                    id=req.id,
                    connection_id=req.connection_id,
                    template_id=req.template_id,
                    title=req.title,
                    description=req.description,
                    recipient_email=req.recipient_email,
                    due_date=req.due_date,
                    priority=req.priority,
                    period_start=req.period_start,
                    period_end=req.period_end,
                    status=req.status,
                    sent_at=req.sent_at,
                    viewed_at=req.viewed_at,
                    responded_at=req.responded_at,
                    completed_at=req.completed_at,
                    auto_remind=req.auto_remind,
                    reminder_count=req.reminder_count,
                    last_reminder_at=req.last_reminder_at,
                    bulk_request_id=req.bulk_request_id,
                    created_at=req.created_at,
                    updated_at=req.updated_at,
                    is_overdue=is_overdue,
                    days_until_due=days_until_due,
                )
            )

        # Get last activity timestamp
        last_session_result = await self.session.execute(
            select(PortalSession.last_active_at)
            .where(PortalSession.connection_id == connection_id)
            .order_by(PortalSession.last_active_at.desc())
            .limit(1)
        )
        last_activity_at = last_session_result.scalar_one_or_none()

        return PortalDashboardResponse(
            connection_id=connection_id,
            organization_name=organization_name,
            pending_requests=pending_requests,
            unread_requests=unread_requests,
            total_documents=total_documents,
            recent_requests=recent_requests,
            last_activity_at=last_activity_at,
        )

    async def get_bas_status(
        self,
        connection_id: UUID,
        tenant_id: UUID,
    ) -> dict:
        """Get BAS status for the client.

        Args:
            connection_id: The XeroConnection ID.
            tenant_id: The tenant ID for access control.

        Returns:
            Dictionary with current BAS status information.
        """
        # For now, return basic status
        # TODO: Integrate with BAS module for actual status
        return {
            "connection_id": str(connection_id),
            "current_quarter": "Q3 FY26",
            "status": "in_progress",
            "due_date": "2026-01-28",
            "items_pending": 3,
            "last_lodged": "Q2 FY26",
            "last_lodged_date": "2025-10-28",
        }

    async def get_recent_activity(
        self,
        connection_id: UUID,
        tenant_id: UUID,
        limit: int = 10,
    ) -> list[dict]:
        """Get recent activity for the client portal.

        Args:
            connection_id: The XeroConnection ID.
            tenant_id: The tenant ID for access control.
            limit: Maximum number of activities to return.

        Returns:
            List of recent activity items.
        """
        activities = []

        # Get recent document requests
        requests_result = await self.session.execute(
            select(DocumentRequest)
            .where(DocumentRequest.connection_id == connection_id)
            .order_by(DocumentRequest.created_at.desc())
            .limit(limit)
        )
        for req in requests_result.scalars():
            activities.append(
                {
                    "type": "document_request",
                    "id": str(req.id),
                    "title": req.title,
                    "status": req.status.value if hasattr(req.status, "value") else req.status,
                    "timestamp": req.created_at.isoformat(),
                }
            )

        # Get recent documents
        docs_result = await self.session.execute(
            select(PortalDocument)
            .where(PortalDocument.connection_id == connection_id)
            .order_by(PortalDocument.uploaded_at.desc())
            .limit(limit)
        )
        for doc in docs_result.scalars():
            activities.append(
                {
                    "type": "document_upload",
                    "id": str(doc.id),
                    "filename": doc.original_filename,
                    "timestamp": doc.uploaded_at.isoformat(),
                }
            )

        # Sort by timestamp and limit
        activities.sort(key=lambda x: x["timestamp"], reverse=True)
        return activities[:limit]
