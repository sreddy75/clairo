"""Portal authentication dependencies.

Provides FastAPI dependencies for portal authentication:
- get_current_portal_client: Validates portal access tokens
- get_current_portal_session: Retrieves the PortalSession from DB
- get_optional_portal_client: Optional authentication

Spec: 030-client-portal-document-requests
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.portal.auth.magic_link import MagicLinkService
from app.modules.portal.exceptions import PortalAuthenticationError
from app.modules.portal.models import PortalSession


class PortalClient(BaseModel):
    """Authenticated portal client context.

    Represents the authenticated business owner accessing the portal.
    """

    connection_id: UUID
    """The XeroConnection ID this client has access to."""

    tenant_id: UUID
    """The tenant (accounting practice) ID."""

    token_id: str
    """Unique identifier for this token (jti claim)."""

    class Config:
        frozen = True


async def get_current_portal_client(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> PortalClient:
    """Get the current authenticated portal client.

    Validates the portal access token from the Authorization header
    and returns the client context.

    Args:
        authorization: The Authorization header value (Bearer <token>).
        db: Database session for token validation.

    Returns:
        PortalClient with connection and tenant context.

    Raises:
        HTTPException: 401 if authentication fails.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract token from Bearer scheme
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    # Verify the access token
    service = MagicLinkService(db)

    try:
        payload = await service.verify_access_token(token)

        return PortalClient(
            connection_id=UUID(payload.sub),
            tenant_id=UUID(payload.tenant_id),
            token_id=payload.jti,
        )

    except PortalAuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_optional_portal_client(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> PortalClient | None:
    """Optionally get the current portal client.

    Unlike get_current_portal_client, this returns None if no valid
    authentication is present, instead of raising an error.

    Args:
        authorization: The Authorization header value.
        db: Database session.

    Returns:
        PortalClient if authenticated, None otherwise.
    """
    if not authorization:
        return None

    try:
        return await get_current_portal_client(authorization, db)
    except HTTPException:
        return None


async def get_current_portal_session(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> PortalSession:
    """Get the current authenticated portal session.

    Validates the portal access token and retrieves the PortalSession from DB.

    Args:
        authorization: The Authorization header value (Bearer <token>).
        db: Database session.

    Returns:
        PortalSession model from the database.

    Raises:
        HTTPException: 401 if authentication fails or session not found.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract token from Bearer scheme
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    # Verify the access token
    service = MagicLinkService(db)

    try:
        payload = await service.verify_access_token(token)

        # Get the session from database
        result = await db.execute(
            select(PortalSession).where(PortalSession.id == UUID(payload.session_id))
        )
        session = result.scalar_one_or_none()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if session has expired
        from datetime import datetime, timezone

        if session.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return session

    except PortalAuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


# Type aliases for cleaner route signatures
CurrentPortalClient = Annotated[PortalClient, Depends(get_current_portal_client)]
"""Annotated type for required portal client authentication."""

OptionalPortalClient = Annotated[PortalClient | None, Depends(get_optional_portal_client)]
"""Annotated type for optional portal client authentication."""

CurrentPortalSession = Annotated[PortalSession, Depends(get_current_portal_session)]
"""Annotated type for required portal session authentication."""
