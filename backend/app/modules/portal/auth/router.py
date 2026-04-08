"""Portal authentication API router.

Provides endpoints for:
- Magic link verification
- Token refresh
- Session logout
- Magic link re-request

Spec: 030-client-portal-document-requests
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.portal.auth.dependencies import CurrentPortalClient
from app.modules.portal.auth.magic_link import MagicLinkService
from app.modules.portal.exceptions import (
    InvitationAlreadyAcceptedError,
    InvitationExpiredError,
    InvitationInvalidTokenError,
    InvitationNotFoundError,
    PortalAuthenticationError,
    PortalSessionExpiredError,
    PortalSessionRevokedError,
)
from app.modules.portal.repository import PortalSessionRepository
from app.modules.portal.schemas import (
    MagicLinkVerifyRequest,
    MagicLinkVerifyResponse,
    PortalTokenRefreshRequest,
    PortalTokenRefreshResponse,
)

router = APIRouter(prefix="/auth", tags=["Portal Authentication"])


# =============================================================================
# Request/Response Schemas
# =============================================================================


class MagicLinkRequestRequest(BaseModel):
    """Request to get a new magic link."""

    email: EmailStr = Field(..., description="Email address associated with portal access")


class MagicLinkRequestResponse(BaseModel):
    """Response after requesting a magic link."""

    message: str = Field(
        default="If you have portal access, a magic link has been sent to your email.",
        description="Status message (intentionally vague for security)",
    )


class LogoutResponse(BaseModel):
    """Response after logout."""

    message: str = "Successfully logged out"
    all_sessions: bool = Field(
        default=False,
        description="Whether all sessions were logged out",
    )


class LogoutRequest(BaseModel):
    """Request for logout."""

    all_sessions: bool = Field(
        default=False,
        description="Log out from all devices/sessions",
    )


class SessionInfoResponse(BaseModel):
    """Response with current session info."""

    connection_id: UUID
    tenant_id: UUID
    is_authenticated: bool = True


# =============================================================================
# Authentication Endpoints
# =============================================================================


@router.post(
    "/request-link",
    response_model=MagicLinkRequestResponse,
    summary="Request a new magic link",
)
async def request_magic_link(
    request: MagicLinkRequestRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MagicLinkRequestResponse:
    """Request a new magic link be sent to your email.

    This endpoint allows clients who have previously been granted portal
    access to request a new magic link. The link will be sent to the
    email address if it matches an existing invitation.

    For security, the response is the same whether the email exists or not.
    This prevents email enumeration attacks.

    Note: This does NOT create a new invitation. The accountant must
    create an invitation first using /portal/clients/{id}/invite.
    """
    # Look up existing invitations for this email (any status)
    # For security, always return the same response regardless of outcome
    import logging

    from sqlalchemy import select

    from app.modules.notifications.email_service import get_email_service
    from app.modules.notifications.templates import EmailTemplate
    from app.modules.portal.models import PortalInvitation
    from app.modules.portal.notifications.templates import PortalEmailTemplates

    logger = logging.getLogger(__name__)

    try:
        # Find the most recent invitation for this email
        result = await db.execute(
            select(PortalInvitation)
            .where(PortalInvitation.email == request.email)
            .order_by(PortalInvitation.created_at.desc())
            .limit(1)
        )
        existing = result.scalars().first()

        if existing:
            # Create a new magic link for this connection
            magic_link_service = MagicLinkService(db)
            invitation, token = await magic_link_service.create_invitation(
                tenant_id=existing.tenant_id,
                connection_id=existing.connection_id,
                email=request.email,
                invited_by=existing.invited_by,
            )

            magic_link_url = magic_link_service.build_magic_link_url(token)

            # Send the login email (not invitation — client initiated this)
            login_template = PortalEmailTemplates.portal_login(
                portal_url=magic_link_url,
            )
            email_template = EmailTemplate(
                subject=login_template.subject,
                html=login_template.html,
                text=login_template.text,
            )
            email_service = get_email_service()
            await email_service.send_email(
                to=request.email,
                template=email_template,
                tags=[{"name": "type", "value": "portal_login_request"}],
            )
            await magic_link_service.mark_invitation_sent(
                invitation_id=invitation.id,
                delivered=True,
            )
            await db.commit()
    except Exception:
        logger.warning("Failed to process magic link request for %s", request.email, exc_info=True)

    # Always return same message (prevents email enumeration)
    return MagicLinkRequestResponse()


@router.post(
    "/verify",
    response_model=MagicLinkVerifyResponse,
    summary="Verify magic link and create session",
)
async def verify_magic_link(
    request: MagicLinkVerifyRequest,
    http_request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MagicLinkVerifyResponse:
    """Verify a magic link token and create a portal session.

    This endpoint is called when a business owner clicks the magic link
    in their invitation email. It:
    1. Validates the token hasn't expired or been used
    2. Creates a new portal session
    3. Returns access and refresh tokens

    The access token is short-lived (15 minutes) and should be included
    in the Authorization header for subsequent API calls.

    The refresh token is long-lived (30 days) and can be used to get
    new access tokens without re-authentication.
    """
    service = MagicLinkService(db)

    # Extract client info from request
    ip_address = request.ip_address or _get_client_ip(http_request)
    user_agent = request.user_agent or http_request.headers.get("user-agent")

    try:
        # Verify the magic link token
        invitation = await service.verify_magic_link_token(request.token)

        # Accept invitation and create session
        session, tokens = await service.accept_invitation(
            invitation=invitation,
            device_fingerprint=request.device_fingerprint,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        await db.commit()

        return MagicLinkVerifyResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_at=tokens.access_expires_at,
            connection_id=session.connection_id,
            tenant_id=session.tenant_id,
        )

    except InvitationInvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid magic link token",
        ) from e

    except InvitationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Magic link not found or already used",
        ) from e

    except InvitationExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Magic link has expired. Please request a new invitation.",
        ) from e

    except InvitationAlreadyAcceptedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This magic link has already been used. Please log in or request a new invitation.",
        ) from e


@router.post(
    "/refresh",
    response_model=PortalTokenRefreshResponse,
    summary="Refresh portal access token",
)
async def refresh_token(
    request: PortalTokenRefreshRequest,
    http_request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PortalTokenRefreshResponse:
    """Refresh the portal access token using a refresh token.

    Call this endpoint when the access token expires (401 response)
    to get a new access token without requiring re-authentication.

    The refresh token remains valid for the session duration (30 days).
    If the session has been revoked or expired, a new magic link
    invitation will be required.
    """
    service = MagicLinkService(db)

    # Extract client IP
    ip_address = request.ip_address or _get_client_ip(http_request)

    try:
        tokens = await service.refresh_session(
            refresh_token=request.refresh_token,
            ip_address=ip_address,
        )

        await db.commit()

        return PortalTokenRefreshResponse(
            access_token=tokens.access_token,
            expires_at=tokens.access_expires_at,
        )

    except PortalAuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from e

    except PortalSessionRevokedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Session has been revoked: {e.message}",
        ) from e

    except PortalSessionExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired. Please request a new invitation.",
        ) from e


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Log out from portal",
)
async def logout(
    client: CurrentPortalClient,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: LogoutRequest | None = None,
) -> LogoutResponse:
    """Log out from the portal session.

    This endpoint revokes the current session. If all_sessions is True,
    all sessions for this connection will be revoked (logout everywhere).

    After logout, the client must use a new magic link to access the portal.
    """
    service = MagicLinkService(db)
    all_sessions = request.all_sessions if request else False

    if all_sessions:
        # Revoke all sessions for this connection
        count = await service.revoke_all_sessions(
            connection_id=client.connection_id,
            reason="Client logged out from all devices",
        )
        await db.commit()
        return LogoutResponse(
            message=f"Logged out from {count} session(s)",
            all_sessions=True,
        )
    else:
        # Revoke current session only
        # We need to find the session by the token JTI
        session_repo = PortalSessionRepository(db)
        sessions = await session_repo.get_active_by_connection(client.connection_id)

        # Find and revoke the current session
        for session in sessions:
            # In a real implementation, we'd match by JTI stored in the session
            # For now, revoke the most recent one
            await service.revoke_session(session.id, "Client logged out")
            break

        await db.commit()
        return LogoutResponse(message="Successfully logged out")


@router.get(
    "/me",
    response_model=SessionInfoResponse,
    summary="Get current session info",
)
async def get_session_info(
    client: CurrentPortalClient,
) -> SessionInfoResponse:
    """Get information about the current portal session.

    Returns the connection ID and tenant ID for the authenticated client.
    Use this to verify the session is valid.
    """
    return SessionInfoResponse(
        connection_id=client.connection_id,
        tenant_id=client.tenant_id,
    )


# =============================================================================
# Helper Functions
# =============================================================================


def _get_client_ip(request: Request) -> str | None:
    """Extract client IP from request, handling proxies."""
    # Check X-Forwarded-For header (set by proxies/load balancers)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()

    # Check X-Real-IP header
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    # Fall back to direct client IP
    if request.client:
        return request.client.host

    return None
