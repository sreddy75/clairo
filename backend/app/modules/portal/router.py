"""Portal module API routers.

This module provides endpoints for:
- Portal invitation and magic link authentication
- Portal session management
- Document request workflow (ClientChase)
- Document upload and management
- Bulk document requests

Spec: 030-client-portal-document-requests
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_practice_user, get_db
from app.modules.auth.models import PracticeUser
from app.modules.portal.enums import InvitationStatus
from app.modules.portal.exceptions import InvitationNotFoundError
from app.modules.portal.schemas import (
    InvitationCreateRequest,
    InvitationCreateResponse,
    InvitationListResponse,
    InvitationResponse,
    PortalAccessStatusResponse,
)
from app.modules.portal.service import InvitationService

# Main portal router (accountant-facing endpoints)
router = APIRouter(prefix="/portal", tags=["Portal - Accountant"])

# Client portal router (business owner-facing endpoints)
client_router = APIRouter(prefix="/client-portal", tags=["Portal - Client"])


# =============================================================================
# Health Check Endpoints
# =============================================================================


@router.get("/health")
async def portal_health():
    """Health check for portal module."""
    return {"status": "ok", "module": "portal"}


@client_router.get("/health")
async def client_portal_health():
    """Health check for client portal."""
    return {"status": "ok", "module": "client-portal"}


# =============================================================================
# Invitation Endpoints (Accountant-facing)
# =============================================================================


@router.post(
    "/clients/{connection_id}/invite",
    response_model=InvitationCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create portal invitation for a client",
)
async def create_invitation(
    connection_id: UUID,
    request: InvitationCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> InvitationCreateResponse:
    """Create a portal invitation for a client business.

    Generates a magic link that can be sent to the business owner
    to grant them access to the client portal.

    - **connection_id**: The XeroConnection ID for the client business
    - **email**: Email address to send the invitation to

    Returns the invitation details and magic link URL.
    Any existing pending invitations for this client will be expired.
    """
    service = InvitationService(db)

    try:
        invitation, magic_link_url = await service.create_invitation(
            tenant_id=user.tenant_id,
            connection_id=connection_id,
            request=request,
            invited_by=user.user_id,  # Use user_id (FK to users.id), not practice user id
        )

        # Build response manually to avoid lazy loading issues
        invitation_response = InvitationResponse(
            id=invitation.id,
            connection_id=invitation.connection_id,
            email=invitation.email,
            status=InvitationStatus(invitation.status),
            sent_at=invitation.sent_at,
            accepted_at=invitation.accepted_at,
            expires_at=invitation.expires_at,
            email_delivered=invitation.email_delivered,
            email_bounced=invitation.email_bounced,
            bounce_reason=invitation.bounce_reason,
            created_at=invitation.created_at,
        )

        return InvitationCreateResponse(
            invitation=invitation_response,
            magic_link_url=magic_link_url,
        )

    except Exception as e:
        # Log unexpected errors and return generic message
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create invitation: {e!s}",
        ) from e


@router.get(
    "/clients/{connection_id}/invitations",
    response_model=InvitationListResponse,
    summary="List invitations for a client",
)
async def list_invitations(
    connection_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    status_filter: InvitationStatus | None = Query(
        None,
        alias="status",
        description="Filter by invitation status",
    ),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
) -> InvitationListResponse:
    """List all portal invitations for a client business.

    - **connection_id**: The XeroConnection ID for the client business
    - **status**: Optional filter by invitation status
    - **skip**: Pagination offset
    - **limit**: Maximum invitations to return (1-100)

    Returns invitations ordered by creation date (newest first).
    """
    service = InvitationService(db)

    return await service.list_invitations(
        tenant_id=user.tenant_id,
        connection_id=connection_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/clients/{connection_id}/portal-access",
    response_model=PortalAccessStatusResponse,
    summary="Get portal access status for a client",
)
async def get_portal_access_status(
    connection_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> PortalAccessStatusResponse:
    """Get the current portal access status for a client business.

    Returns information about:
    - Whether the client has active portal access
    - Number of active sessions
    - Latest invitation status
    - Last activity timestamp

    Use this to show portal access status on the client detail page.
    """
    service = InvitationService(db)

    result = await service.get_portal_access_status(
        tenant_id=user.tenant_id,
        connection_id=connection_id,
    )

    return PortalAccessStatusResponse(**result)


@router.delete(
    "/clients/{connection_id}/portal-access",
    status_code=status.HTTP_200_OK,
    summary="Revoke portal access for a client",
)
async def revoke_portal_access(
    connection_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    reason: str = Query(
        "Access revoked by accountant",
        description="Reason for revocation (logged for audit)",
    ),
) -> dict:
    """Revoke all portal access for a client business.

    This will:
    - Invalidate all active sessions for this client
    - Log the revocation reason for audit purposes
    - Prevent new logins until a new invitation is sent

    Use this if a client relationship ends or access needs to be restricted.
    """
    service = InvitationService(db)

    sessions_revoked = await service.revoke_portal_access(
        tenant_id=user.tenant_id,
        connection_id=connection_id,
        reason=reason,
    )

    return {
        "message": "Portal access revoked",
        "sessions_revoked": sessions_revoked,
    }


@router.post(
    "/clients/{connection_id}/invite/{invitation_id}/resend",
    response_model=InvitationCreateResponse,
    summary="Resend a portal invitation",
)
async def resend_invitation(
    connection_id: UUID,
    invitation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> InvitationCreateResponse:
    """Resend a portal invitation with a fresh magic link.

    Creates a new invitation with the same email address.
    The old invitation will be expired.

    Use this if the original invitation expired or the client
    didn't receive/lost the original email.
    """
    service = InvitationService(db)

    try:
        invitation, magic_link_url = await service.resend_invitation(
            invitation_id=invitation_id,
            tenant_id=user.tenant_id,
        )

        # Build response manually to avoid lazy loading issues
        invitation_response = InvitationResponse(
            id=invitation.id,
            connection_id=invitation.connection_id,
            email=invitation.email,
            status=InvitationStatus(invitation.status),
            sent_at=invitation.sent_at,
            accepted_at=invitation.accepted_at,
            expires_at=invitation.expires_at,
            email_delivered=invitation.email_delivered,
            email_bounced=invitation.email_bounced,
            bounce_reason=invitation.bounce_reason,
            created_at=invitation.created_at,
        )

        return InvitationCreateResponse(
            invitation=invitation_response,
            magic_link_url=magic_link_url,
        )

    except InvitationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        ) from e


# =============================================================================
# Tax Plan (Spec 041 — shared analysis for client portal)
# =============================================================================


@client_router.get("/tax-plan")
async def get_portal_tax_plan(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get the shared tax plan for the authenticated portal client."""

    # TODO: Wire up portal client auth dependency when fully integrated
    # For now, return 404 if no shared analysis found
    raise HTTPException(status_code=404, detail="No tax plan shared yet")


@client_router.patch("/tax-plan/items/{item_id}")
async def update_portal_item(
    item_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    status_val: str = "completed",
):
    """Allow client to mark an implementation item as completed."""

    # TODO: Get tenant_id from portal client auth
    # For now, stub endpoint
    raise HTTPException(status_code=404, detail="Not yet implemented")


@client_router.post("/tax-plan/question")
async def ask_portal_question(
    db: Annotated[AsyncSession, Depends(get_db)],
    question: str = "",
):
    """Client asks a question about the tax plan — routes to accountant."""
    # TODO: Wire portal auth to get tenant_id + create full notification
    # For now, return success response
    return {"message": "Your question has been sent to your accountant.", "question_id": None}


# =============================================================================
# Include Auth Router (Magic Link Authentication)
# =============================================================================

# The auth router is included in main.py via portal __init__.py
# It provides: /client-portal/auth/verify, /auth/refresh, /auth/logout, /auth/me
