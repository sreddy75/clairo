"""Magic link authentication service for client portal.

Provides secure, passwordless authentication for business owner clients.
Magic links are single-use, time-limited tokens sent via email.

Security Model:
- Tokens are 32-byte random strings (256-bit entropy)
- Only SHA-256 hashes are stored in the database
- Tokens expire after configurable duration (default: 24 hours)
- Sessions are tied to device fingerprint and IP for security
- Refresh tokens enable session extension without re-authentication

Spec: 030-client-portal-document-requests
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import NamedTuple
from uuid import UUID

from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.modules.portal.enums import InvitationStatus
from app.modules.portal.exceptions import (
    InvitationAlreadyAcceptedError,
    InvitationExpiredError,
    InvitationInvalidTokenError,
    InvitationNotFoundError,
    PortalAuthenticationError,
    PortalSessionExpiredError,
    PortalSessionRevokedError,
)
from app.modules.portal.models import PortalInvitation, PortalSession
from app.modules.portal.repository import (
    PortalInvitationRepository,
    PortalSessionRepository,
)

# =============================================================================
# Token Configuration
# =============================================================================

# Token lengths
MAGIC_LINK_TOKEN_BYTES = 32  # 256-bit entropy
REFRESH_TOKEN_BYTES = 32

# Token expiration
DEFAULT_INVITATION_HOURS = 24
DEFAULT_SESSION_DAYS = 30
DEFAULT_ACCESS_TOKEN_MINUTES = 15


class TokenPair(NamedTuple):
    """Access and refresh token pair."""

    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime


class PortalTokenPayload(BaseModel):
    """JWT token payload for portal authentication."""

    sub: str  # connection_id
    tenant_id: str
    session_id: str  # portal session ID for session lookups
    exp: datetime
    iat: datetime
    token_type: str  # "access" or "refresh"
    jti: str  # Unique token ID


# =============================================================================
# Token Utilities
# =============================================================================


def generate_secure_token(num_bytes: int = MAGIC_LINK_TOKEN_BYTES) -> str:
    """Generate a cryptographically secure random token.

    Args:
        num_bytes: Number of random bytes (default: 32 for 256-bit entropy).

    Returns:
        URL-safe base64-encoded token string.
    """
    return secrets.token_urlsafe(num_bytes)


def hash_token(token: str) -> str:
    """Create SHA-256 hash of a token for secure storage.

    Args:
        token: The plain token to hash.

    Returns:
        Hexadecimal SHA-256 hash string.
    """
    return hashlib.sha256(token.encode()).hexdigest()


# =============================================================================
# Magic Link Service
# =============================================================================


class MagicLinkService:
    """Service for magic link authentication.

    Handles the complete flow:
    1. Generate magic link token for invitation
    2. Verify magic link token when clicked
    3. Create session with access/refresh tokens
    4. Refresh sessions with new access tokens
    5. Revoke sessions on logout
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize service with database session.

        Args:
            session: Async SQLAlchemy session for database operations.
        """
        self.session = session
        self.invitation_repo = PortalInvitationRepository(session)
        self.session_repo = PortalSessionRepository(session)
        self._settings = get_settings()

    # -------------------------------------------------------------------------
    # Token Generation
    # -------------------------------------------------------------------------

    def generate_magic_link_token(self) -> tuple[str, str]:
        """Generate a new magic link token.

        Returns:
            Tuple of (plain_token, token_hash).
            The plain token is sent to the client, the hash is stored.
        """
        token = generate_secure_token(MAGIC_LINK_TOKEN_BYTES)
        token_hash = hash_token(token)
        return token, token_hash

    def generate_refresh_token(self) -> tuple[str, str]:
        """Generate a new refresh token.

        Returns:
            Tuple of (plain_token, token_hash).
        """
        token = generate_secure_token(REFRESH_TOKEN_BYTES)
        token_hash = hash_token(token)
        return token, token_hash

    # -------------------------------------------------------------------------
    # Invitation Management
    # -------------------------------------------------------------------------

    async def create_invitation(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        email: str,
        invited_by: UUID,
        expires_hours: int = DEFAULT_INVITATION_HOURS,
    ) -> tuple[PortalInvitation, str]:
        """Create a portal invitation with magic link.

        Args:
            tenant_id: The tenant (accounting practice) ID.
            connection_id: The XeroConnection (client business) ID.
            email: Email address to send invitation to.
            invited_by: User ID of the accountant sending the invitation.
            expires_hours: Hours until invitation expires.

        Returns:
            Tuple of (invitation record, plain magic link token).
        """
        # Invalidate any existing pending invitations
        existing = await self.invitation_repo.get_pending_by_connection(connection_id)
        if existing:
            await self.invitation_repo.update(
                existing.id,
                {"status": InvitationStatus.EXPIRED.value},
            )

        # Generate new magic link
        token, token_hash = self.generate_magic_link_token()

        # Create invitation record
        invitation = PortalInvitation(
            tenant_id=tenant_id,
            connection_id=connection_id,
            email=email,
            token_hash=token_hash,
            status=InvitationStatus.PENDING.value,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_hours),
            invited_by=invited_by,
        )

        invitation = await self.invitation_repo.create(invitation)
        return invitation, token

    async def mark_invitation_sent(
        self,
        invitation_id: UUID,
        delivered: bool = True,
        bounce_reason: str | None = None,
    ) -> PortalInvitation | None:
        """Mark invitation as sent (or failed).

        Args:
            invitation_id: The invitation ID.
            delivered: Whether email was delivered successfully.
            bounce_reason: Reason for bounce if delivery failed.

        Returns:
            Updated invitation or None if not found.
        """
        data = {
            "sent_at": datetime.now(timezone.utc),
            "status": InvitationStatus.SENT.value if delivered else InvitationStatus.FAILED.value,
            "email_delivered": delivered,
            "email_bounced": not delivered,
        }
        if bounce_reason:
            data["bounce_reason"] = bounce_reason

        return await self.invitation_repo.update(invitation_id, data)

    # -------------------------------------------------------------------------
    # Token Verification
    # -------------------------------------------------------------------------

    async def verify_magic_link_token(self, token: str) -> PortalInvitation:
        """Verify a magic link token and return the invitation.

        Args:
            token: The plain magic link token from the URL.

        Returns:
            The associated invitation record.

        Raises:
            InvitationInvalidTokenError: If token format is invalid.
            InvitationNotFoundError: If token doesn't match any invitation.
            InvitationExpiredError: If invitation has expired.
            InvitationAlreadyAcceptedError: If invitation was already used.
        """
        # Validate token format
        if not token or len(token) < 32:
            raise InvitationInvalidTokenError()

        # Hash the token and look up
        token_hash = hash_token(token)
        invitation = await self.invitation_repo.get_by_token_hash(token_hash)

        if not invitation:
            raise InvitationNotFoundError()

        # Check status
        if invitation.status == InvitationStatus.ACCEPTED.value:
            raise InvitationAlreadyAcceptedError(invitation.id)

        if invitation.status == InvitationStatus.EXPIRED.value:
            raise InvitationExpiredError(invitation.id)

        # Check expiration
        if invitation.expires_at < datetime.now(timezone.utc):
            await self.invitation_repo.update(
                invitation.id,
                {"status": InvitationStatus.EXPIRED.value},
            )
            raise InvitationExpiredError(invitation.id)

        return invitation

    async def accept_invitation(
        self,
        invitation: PortalInvitation,
        device_fingerprint: str | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[PortalSession, TokenPair]:
        """Accept an invitation and create a portal session.

        Args:
            invitation: The verified invitation.
            device_fingerprint: Optional device fingerprint for security.
            user_agent: Client user agent string.
            ip_address: Client IP address.

        Returns:
            Tuple of (session record, token pair).
        """
        # Mark invitation as accepted
        await self.invitation_repo.update(
            invitation.id,
            {
                "status": InvitationStatus.ACCEPTED.value,
                "accepted_at": datetime.now(timezone.utc),
            },
        )

        # Create session
        session, tokens = await self.create_session(
            connection_id=invitation.connection_id,
            tenant_id=invitation.tenant_id,
            device_fingerprint=device_fingerprint,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        return session, tokens

    # -------------------------------------------------------------------------
    # Session Management
    # -------------------------------------------------------------------------

    async def create_session(
        self,
        connection_id: UUID,
        tenant_id: UUID,
        device_fingerprint: str | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
        session_days: int = DEFAULT_SESSION_DAYS,
    ) -> tuple[PortalSession, TokenPair]:
        """Create a new portal session with tokens.

        Args:
            connection_id: The XeroConnection (client business) ID.
            tenant_id: The tenant ID.
            device_fingerprint: Optional device fingerprint.
            user_agent: Client user agent string.
            ip_address: Client IP address.
            session_days: Session duration in days.

        Returns:
            Tuple of (session record, token pair with access/refresh tokens).
        """
        # Generate refresh token
        refresh_token, refresh_token_hash = self.generate_refresh_token()

        # Calculate expiration
        now = datetime.now(timezone.utc)
        session_expires_at = now + timedelta(days=session_days)

        # Create session record
        portal_session = PortalSession(
            connection_id=connection_id,
            tenant_id=tenant_id,
            refresh_token_hash=refresh_token_hash,
            device_fingerprint=device_fingerprint,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=session_expires_at,
        )

        portal_session = await self.session_repo.create(portal_session)

        # Create token pair (now includes session_id)
        tokens = self.create_session_tokens(
            connection_id=connection_id,
            tenant_id=tenant_id,
            session_id=portal_session.id,
            refresh_token=refresh_token,
            session_expires_at=session_expires_at,
        )

        return portal_session, tokens

    def create_session_tokens(
        self,
        connection_id: UUID,
        tenant_id: UUID,
        session_id: UUID,
        refresh_token: str,
        session_expires_at: datetime,
        access_token_minutes: int = DEFAULT_ACCESS_TOKEN_MINUTES,
    ) -> TokenPair:
        """Create JWT access and refresh tokens.

        Args:
            connection_id: The XeroConnection ID (becomes subject claim).
            tenant_id: The tenant ID.
            session_id: The portal session ID.
            refresh_token: The plain refresh token.
            session_expires_at: When the session expires.
            access_token_minutes: Access token lifetime in minutes.

        Returns:
            TokenPair with access and refresh tokens.
        """
        security = self._settings.security
        now = datetime.now(timezone.utc)
        access_expires_at = now + timedelta(minutes=access_token_minutes)

        # Create access token
        access_payload = {
            "sub": str(connection_id),
            "tenant_id": str(tenant_id),
            "session_id": str(session_id),
            "exp": access_expires_at,
            "iat": now,
            "token_type": "portal_access",
            "jti": secrets.token_hex(16),
        }

        access_token = jwt.encode(
            access_payload,
            security.secret_key.get_secret_value(),
            algorithm=security.algorithm,
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=access_expires_at,
            refresh_expires_at=session_expires_at,
        )

    async def refresh_session(
        self,
        refresh_token: str,
        ip_address: str | None = None,
    ) -> TokenPair:
        """Refresh a session and get new access token.

        Args:
            refresh_token: The plain refresh token.
            ip_address: Current client IP for session update.

        Returns:
            New TokenPair with fresh access token and same refresh token.

        Raises:
            PortalAuthenticationError: If refresh token is invalid.
            PortalSessionExpiredError: If session has expired.
            PortalSessionRevokedError: If session was revoked.
        """
        # Look up session by refresh token hash
        token_hash = hash_token(refresh_token)
        session = await self.session_repo.get_by_refresh_token_hash(token_hash)

        if not session:
            raise PortalAuthenticationError("Invalid refresh token")

        # Check if revoked
        if session.revoked:
            raise PortalSessionRevokedError(session.revoke_reason)

        # Check if expired
        if session.expires_at < datetime.now(timezone.utc):
            raise PortalSessionExpiredError()

        # Update last active
        await self.session_repo.update(
            session.id,
            {
                "last_active_at": datetime.now(timezone.utc),
                "ip_address": ip_address,
            },
        )

        # Create new tokens (same refresh token, new access token)
        return self.create_session_tokens(
            connection_id=session.connection_id,
            tenant_id=session.tenant_id,
            session_id=session.id,
            refresh_token=refresh_token,
            session_expires_at=session.expires_at,
        )

    async def verify_access_token(self, token: str) -> PortalTokenPayload:
        """Verify a portal access token.

        Args:
            token: The JWT access token.

        Returns:
            Decoded token payload.

        Raises:
            PortalAuthenticationError: If token is invalid or expired.
        """
        security = self._settings.security

        try:
            payload = jwt.decode(
                token,
                security.secret_key.get_secret_value(),
                algorithms=[security.algorithm],
            )

            # Verify it's a portal access token
            if payload.get("token_type") != "portal_access":
                raise PortalAuthenticationError("Invalid token type")

            return PortalTokenPayload(**payload)

        except JWTError as e:
            raise PortalAuthenticationError(f"Invalid or expired token: {e}") from e

    async def revoke_session(
        self,
        session_id: UUID,
        reason: str | None = None,
    ) -> bool:
        """Revoke a portal session (logout).

        Args:
            session_id: The session ID to revoke.
            reason: Optional reason for revocation.

        Returns:
            True if session was revoked, False if not found.
        """
        session = await self.session_repo.revoke(session_id, reason)
        return session is not None

    async def revoke_all_sessions(
        self,
        connection_id: UUID,
        reason: str = "All sessions revoked",
    ) -> int:
        """Revoke all sessions for a connection.

        Args:
            connection_id: The XeroConnection ID.
            reason: Reason for revocation.

        Returns:
            Number of sessions revoked.
        """
        return await self.session_repo.revoke_all_for_connection(connection_id, reason)

    # -------------------------------------------------------------------------
    # URL Generation
    # -------------------------------------------------------------------------

    def build_magic_link_url(
        self,
        token: str,
        base_url: str | None = None,
    ) -> str:
        """Build the complete magic link URL.

        Args:
            token: The plain magic link token.
            base_url: Optional base URL override.

        Returns:
            Complete magic link URL for email.
        """
        if base_url is None:
            base_url = self._settings.frontend_url

        return f"{base_url}/portal/verify?token={token}"
