"""Portal module business logic services.

Provides services for:
- Invitation management
- Document request management
- Portal dashboard
- Bulk operations

Spec: 030-client-portal-document-requests
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.email_service import get_email_service
from app.modules.notifications.templates import EmailTemplate
from app.modules.portal.auth.magic_link import MagicLinkService
from app.modules.portal.enums import InvitationStatus, RequestStatus
from app.modules.portal.exceptions import (
    InvitationNotFoundError,
)
from app.modules.portal.models import (
    PortalInvitation,
)
from app.modules.portal.notifications.templates import PortalEmailTemplates
from app.modules.portal.repository import (
    DocumentRequestRepository,
    PortalDocumentRepository,
    PortalInvitationRepository,
    PortalSessionRepository,
)
from app.modules.portal.schemas import (
    InvitationCreateRequest,
    InvitationListResponse,
    InvitationResponse,
    PortalDashboardResponse,
    RequestResponse,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Invitation Service
# =============================================================================


class InvitationService:
    """Service for managing portal invitations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize service with database session."""
        self.session = session
        self.invitation_repo = PortalInvitationRepository(session)
        self.session_repo = PortalSessionRepository(session)
        self.magic_link_service = MagicLinkService(session)

    async def create_invitation(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        request: InvitationCreateRequest,
        invited_by: UUID,
    ) -> tuple[PortalInvitation, str]:
        """Create a portal invitation.

        Args:
            tenant_id: The tenant ID.
            connection_id: The XeroConnection ID.
            request: Invitation creation request.
            invited_by: User ID creating the invitation.

        Returns:
            Tuple of (invitation, magic_link_url).
        """
        invitation, token = await self.magic_link_service.create_invitation(
            tenant_id=tenant_id,
            connection_id=connection_id,
            email=request.email,
            invited_by=invited_by,
        )

        magic_link_url = self.magic_link_service.build_magic_link_url(token)

        # Send invitation email via Resend
        try:
            portal_template = PortalEmailTemplates.portal_invitation(
                business_name=getattr(request, "business_name", "your business"),
                practice_name=getattr(request, "practice_name", "your accountant"),
                inviter_name=getattr(request, "inviter_name", "Your accountant"),
                portal_url=magic_link_url,
                message=request.message if hasattr(request, "message") else None,
            )
            email_template = EmailTemplate(
                subject=portal_template.subject,
                html=portal_template.html,
                text=portal_template.text,
            )
            email_service = get_email_service()
            await email_service.send_email(
                to=request.email,
                template=email_template,
                tags=[{"name": "type", "value": "portal_invitation"}],
            )
            await self.magic_link_service.mark_invitation_sent(
                invitation_id=invitation.id,
                delivered=True,
            )
        except Exception:
            logger.warning(
                "Failed to send portal invitation email to %s",
                request.email,
                exc_info=True,
            )
            await self.magic_link_service.mark_invitation_sent(
                invitation_id=invitation.id,
                delivered=False,
            )

        return invitation, magic_link_url

    async def get_invitation(
        self,
        invitation_id: UUID,
        tenant_id: UUID,
    ) -> PortalInvitation:
        """Get an invitation by ID.

        Args:
            invitation_id: The invitation ID.
            tenant_id: The tenant ID for access control.

        Returns:
            The invitation.

        Raises:
            InvitationNotFoundError: If invitation not found.
        """
        invitation = await self.invitation_repo.get_by_id_and_tenant(invitation_id, tenant_id)
        if not invitation:
            raise InvitationNotFoundError(invitation_id)
        return invitation

    async def list_invitations(
        self,
        tenant_id: UUID,
        connection_id: UUID | None = None,
        status: InvitationStatus | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> InvitationListResponse:
        """List invitations for a tenant.

        Args:
            tenant_id: The tenant ID.
            connection_id: Optional filter by connection.
            status: Optional filter by status.
            skip: Pagination offset.
            limit: Page size.

        Returns:
            List of invitations with total count.
        """
        if connection_id:
            invitations = await self.invitation_repo.list_by_connection(connection_id, limit=limit)
            total = len(invitations)
        else:
            invitations, total = await self.invitation_repo.list_by_tenant(
                tenant_id, status=status, skip=skip, limit=limit
            )

        # Build responses manually to avoid lazy loading issues
        invitation_responses = [
            InvitationResponse(
                id=inv.id,
                connection_id=inv.connection_id,
                email=inv.email,
                status=InvitationStatus(inv.status),
                sent_at=inv.sent_at,
                accepted_at=inv.accepted_at,
                expires_at=inv.expires_at,
                email_delivered=inv.email_delivered,
                email_bounced=inv.email_bounced,
                bounce_reason=inv.bounce_reason,
                created_at=inv.created_at,
            )
            for inv in invitations
        ]

        return InvitationListResponse(
            invitations=invitation_responses,
            total=total,
        )

    async def resend_invitation(
        self,
        invitation_id: UUID,
        tenant_id: UUID,
    ) -> tuple[PortalInvitation, str]:
        """Resend an invitation (generate new token).

        Args:
            invitation_id: The invitation ID.
            tenant_id: The tenant ID.

        Returns:
            Tuple of (invitation, new_magic_link_url).

        Raises:
            InvitationNotFoundError: If invitation not found.
        """
        invitation = await self.get_invitation(invitation_id, tenant_id)

        # Create new invitation with same details
        new_invitation, token = await self.magic_link_service.create_invitation(
            tenant_id=invitation.tenant_id,
            connection_id=invitation.connection_id,
            email=invitation.email,
            invited_by=invitation.invited_by,
        )

        magic_link_url = self.magic_link_service.build_magic_link_url(token)
        return new_invitation, magic_link_url

    async def get_portal_access_status(
        self,
        tenant_id: UUID,
        connection_id: UUID,
    ) -> dict:
        """Get portal access status for a connection.

        Args:
            tenant_id: The tenant ID.
            connection_id: The XeroConnection ID.

        Returns:
            Dict with access status information.
        """
        # Get latest invitation
        invitations = await self.invitation_repo.list_by_connection(connection_id, limit=1)
        latest_invitation = invitations[0] if invitations else None

        # Get active sessions
        active_sessions = await self.session_repo.get_active_by_connection(connection_id)

        has_access = bool(active_sessions)
        invitation_status = (
            InvitationStatus(latest_invitation.status) if latest_invitation else None
        )

        # Build invitation response manually to avoid lazy loading issues
        latest_invitation_response = None
        if latest_invitation:
            latest_invitation_response = InvitationResponse(
                id=latest_invitation.id,
                connection_id=latest_invitation.connection_id,
                email=latest_invitation.email,
                status=InvitationStatus(latest_invitation.status),
                sent_at=latest_invitation.sent_at,
                accepted_at=latest_invitation.accepted_at,
                expires_at=latest_invitation.expires_at,
                email_delivered=latest_invitation.email_delivered,
                email_bounced=latest_invitation.email_bounced,
                bounce_reason=latest_invitation.bounce_reason,
                created_at=latest_invitation.created_at,
            )

        return {
            "has_access": has_access,
            "active_sessions": len(active_sessions),
            "latest_invitation": latest_invitation_response,
            "invitation_status": invitation_status,
        }

    async def revoke_portal_access(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        reason: str = "Access revoked by accountant",
    ) -> int:
        """Revoke all portal access for a connection.

        Args:
            tenant_id: The tenant ID.
            connection_id: The XeroConnection ID.
            reason: Reason for revocation.

        Returns:
            Number of sessions revoked.
        """
        return await self.magic_link_service.revoke_all_sessions(connection_id, reason)


# =============================================================================
# Portal Dashboard Service
# =============================================================================


class PortalDashboardService:
    """Service for portal dashboard data."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize service with database session."""
        self.session = session
        self.request_repo = DocumentRequestRepository(session)
        self.document_repo = PortalDocumentRepository(session)

    async def get_dashboard(
        self,
        connection_id: UUID,
        organization_name: str,
    ) -> PortalDashboardResponse:
        """Get dashboard data for a client portal.

        Args:
            connection_id: The XeroConnection ID.
            organization_name: The organization display name.

        Returns:
            Dashboard response with metrics and recent requests.
        """
        # Get request counts
        requests, _ = await self.request_repo.list_by_connection(connection_id, limit=100)

        pending_count = sum(
            1
            for r in requests
            if r.status in [RequestStatus.PENDING.value, RequestStatus.VIEWED.value]
        )
        unread_count = sum(
            1 for r in requests if r.status == RequestStatus.PENDING.value and r.viewed_at is None
        )

        # Get document count
        document_count = await self.document_repo.count_by_connection(connection_id)

        # Get recent requests (last 5)
        recent_requests, _ = await self.request_repo.list_by_connection(connection_id, limit=5)

        # Find last activity
        last_activity = None
        if requests:
            dates = [r.responded_at or r.viewed_at or r.created_at for r in requests]
            last_activity = max(d for d in dates if d is not None)

        return PortalDashboardResponse(
            connection_id=connection_id,
            organization_name=organization_name,
            pending_requests=pending_count,
            unread_requests=unread_count,
            total_documents=document_count,
            recent_requests=[RequestResponse.model_validate(r) for r in recent_requests],
            last_activity_at=last_activity,
        )
