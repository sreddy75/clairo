"""Clerk authentication integration.

This module provides:
- ClerkClient: JWKS fetching and token validation
- ClerkTokenPayload: Pydantic model for JWT claims
- ClerkUser: Pydantic model for Clerk user data
- JWKS caching with in-memory + optional Redis

Clerk is the external authentication provider that handles:
- User signup/signin flows
- MFA (Multi-Factor Authentication)
- Session management
- User metadata storage

Usage:
    from app.modules.auth.clerk import ClerkClient, ClerkTokenPayload

    client = ClerkClient(settings=clerk_settings)
    payload = await client.validate_token(token)
    user = await client.get_user(payload.sub)
"""

import json
import time
import uuid
from typing import Any

import httpx
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError
from pydantic import BaseModel, Field, field_validator

from app.config import ClerkSettings
from app.core.exceptions import AuthenticationError, ExternalServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)


class ClerkTokenPayload(BaseModel):
    """Pydantic model for Clerk JWT claims.

    Clerk JWTs contain standard claims plus custom claims for
    tenant_id and role which we add via Clerk's public metadata.

    Attributes:
        sub: Subject (Clerk user ID, e.g., "user_abc123").
        email: User's primary email address.
        email_verified: Whether the email is verified.
        tenant_id: Tenant UUID from Clerk public metadata.
        role: User role from Clerk public metadata.
        exp: Expiration timestamp.
        iat: Issued at timestamp.
        nbf: Not before timestamp.
        iss: Issuer (Clerk domain).
        azp: Authorized party (frontend URL).
    """

    sub: str = Field(..., description="Clerk user ID")
    email: str | None = Field(default=None, description="User email")
    email_verified: bool = Field(default=False, description="Email verified status")
    tenant_id: uuid.UUID | None = Field(default=None, description="Tenant ID from metadata")
    role: str | None = Field(default=None, description="User role from metadata")
    exp: int = Field(..., description="Token expiration timestamp")
    iat: int = Field(..., description="Token issued at timestamp")
    nbf: int | None = Field(default=None, description="Not before timestamp")
    iss: str | None = Field(default=None, description="Token issuer")
    azp: str | None = Field(default=None, description="Authorized party")

    @field_validator("tenant_id", mode="before")
    @classmethod
    def parse_tenant_id(cls, v: Any) -> uuid.UUID | None:
        """Parse tenant_id from string or UUID."""
        if v is None:
            return None
        if isinstance(v, uuid.UUID):
            return v
        if isinstance(v, str):
            try:
                return uuid.UUID(v)
            except ValueError:
                return None
        return None


class ClerkEmailAddress(BaseModel):
    """Clerk email address object."""

    email_address: str
    verification: dict[str, Any] | None = None


class ClerkUser(BaseModel):
    """Pydantic model for Clerk user data.

    Represents the user object returned by Clerk's API.

    Attributes:
        id: Clerk user ID.
        email_addresses: List of email addresses.
        first_name: User's first name.
        last_name: User's last name.
        public_metadata: Public metadata (tenant_id, role).
        private_metadata: Private metadata.
    """

    id: str
    email_addresses: list[ClerkEmailAddress] = Field(default_factory=list)
    first_name: str | None = None
    last_name: str | None = None
    public_metadata: dict[str, Any] = Field(default_factory=dict)
    private_metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def primary_email(self) -> str | None:
        """Get the primary email address."""
        if self.email_addresses:
            return self.email_addresses[0].email_address
        return None

    @property
    def is_email_verified(self) -> bool:
        """Check if the primary email is verified."""
        if not self.email_addresses:
            return False
        verification = self.email_addresses[0].verification
        if verification is None:
            return False
        return verification.get("status") == "verified"

    @property
    def full_name(self) -> str:
        """Get the full name."""
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p)

    @property
    def tenant_id(self) -> uuid.UUID | None:
        """Get tenant_id from public metadata."""
        tenant_id_str = self.public_metadata.get("tenant_id")
        if tenant_id_str:
            try:
                return uuid.UUID(tenant_id_str)
            except ValueError:
                return None
        return None

    @property
    def has_mfa_enabled(self) -> bool:
        """Check if MFA is enabled (from Clerk metadata)."""
        return self.public_metadata.get("mfa_enabled", False)


class JWKSCache:
    """In-memory JWKS cache with TTL.

    Caches JWKS keys to avoid fetching on every request.
    Also stores stale keys for fallback when fetch fails.

    Attributes:
        ttl_seconds: Time-to-live for cached keys.
    """

    def __init__(self, ttl_seconds: int = 3600) -> None:
        """Initialize the cache.

        Args:
            ttl_seconds: Time-to-live for cached keys.
        """
        self._ttl_seconds = ttl_seconds
        self._data: dict[str, Any] | None = None
        self._expires_at: float = 0

    def get(self) -> dict[str, Any] | None:
        """Get cached JWKS if not expired.

        Returns:
            Cached JWKS or None if expired/empty.
        """
        if self.is_expired():
            return None
        return self._data

    def get_stale(self) -> dict[str, Any] | None:
        """Get cached JWKS even if expired.

        Used as fallback when fresh fetch fails.

        Returns:
            Cached JWKS or None if empty.
        """
        return self._data

    def set(self, data: dict[str, Any]) -> None:
        """Store JWKS in cache.

        Args:
            data: JWKS data to cache.
        """
        self._data = data
        self._expires_at = time.time() + self._ttl_seconds

    def is_expired(self) -> bool:
        """Check if cache has expired.

        Returns:
            True if cache is expired or empty.
        """
        return self._data is None or time.time() > self._expires_at


class ClerkClient:
    """Client for Clerk authentication services.

    Handles JWKS fetching, token validation, and user management
    via Clerk's APIs.

    Attributes:
        _settings: Clerk configuration settings.
        _redis: Optional Redis client for distributed caching.
        _jwks_cache: In-memory JWKS cache.
    """

    def __init__(
        self,
        settings: ClerkSettings,
        redis: Any | None = None,
    ) -> None:
        """Initialize the Clerk client.

        Args:
            settings: Clerk configuration settings.
            redis: Optional Redis client for distributed caching.
        """
        self._settings = settings
        self._redis = redis
        self._jwks_cache = JWKSCache(ttl_seconds=settings.jwks_cache_ttl_seconds)

    async def get_jwks(self) -> dict[str, Any]:
        """Fetch JWKS from Clerk's well-known endpoint.

        Uses cached keys when available. Falls back to stale cache
        if fresh fetch fails.

        Returns:
            JWKS data containing public keys.

        Raises:
            ExternalServiceError: If JWKS cannot be fetched and no cache available.
        """
        # Check in-memory cache first
        cached = self._jwks_cache.get()
        if cached is not None:
            return cached

        # Check Redis cache if available
        if self._redis is not None:
            try:
                redis_cached = await self._redis.get("clerk:jwks")
                if redis_cached:
                    jwks = json.loads(redis_cached)
                    self._jwks_cache.set(jwks)
                    return jwks
            except Exception as e:
                logger.warning("Redis cache read failed", error=str(e))

        # Fetch from Clerk
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self._settings.jwks_url)

                if response.status_code != 200:
                    raise ExternalServiceError(
                        service="Clerk",
                        message=f"JWKS fetch failed: HTTP {response.status_code}",
                    )

                jwks = response.json()

                # Update caches
                self._jwks_cache.set(jwks)

                if self._redis is not None:
                    try:
                        await self._redis.setex(
                            "clerk:jwks",
                            self._settings.jwks_cache_ttl_seconds,
                            json.dumps(jwks),
                        )
                    except Exception as e:
                        logger.warning("Redis cache write failed", error=str(e))

                return jwks

        except httpx.HTTPError as e:
            logger.warning("JWKS fetch failed, using stale cache", error=str(e))

            # Try stale cache
            stale = self._jwks_cache.get_stale()
            if stale is not None:
                return stale

            raise ExternalServiceError(
                service="Clerk",
                message="Unable to fetch JWKS and no cache available",
                original_error=str(e),
            )

        except Exception as e:
            logger.error("Unexpected error fetching JWKS", error=str(e))

            # Try stale cache
            stale = self._jwks_cache.get_stale()
            if stale is not None:
                return stale

            raise ExternalServiceError(
                service="Clerk",
                message="Unable to fetch JWKS",
                original_error=str(e),
            )

    async def validate_token(self, token: str) -> ClerkTokenPayload:
        """Validate a Clerk JWT and return the payload.

        Validates the token signature using JWKS and checks expiration.

        Args:
            token: JWT string from Authorization header.

        Returns:
            Validated token payload.

        Raises:
            AuthenticationError: If token is invalid or expired.
        """
        try:
            # Get JWKS for validation
            logger.debug("Validating token", token_prefix=token[:50] if token else "")
            jwks = await self.get_jwks()
            logger.debug("Got JWKS", keys_count=len(jwks.get("keys", [])))

            # Decode and validate the token
            # Note: python-jose handles key selection from JWKS automatically
            options = {
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "verify_aud": False,  # Clerk doesn't use audience
                "require": ["exp", "iat", "sub"],
                "leeway": self._settings.jwt_clock_skew_seconds,
            }

            # Decode the token
            claims = jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],
                options=options,
            )

            # Map Clerk claims to our payload model
            return ClerkTokenPayload(
                sub=claims["sub"],
                email=claims.get("email"),
                email_verified=claims.get("email_verified", False),
                tenant_id=claims.get("tenant_id") or claims.get("metadata", {}).get("tenant_id"),
                role=claims.get("role") or claims.get("metadata", {}).get("role"),
                exp=claims["exp"],
                iat=claims["iat"],
                nbf=claims.get("nbf"),
                iss=claims.get("iss"),
                azp=claims.get("azp"),
            )

        except ExpiredSignatureError:
            logger.warning("Token expired", token_prefix=token[:20] if token else "")
            raise AuthenticationError(
                message="Token has expired",
                details={"reason": "expired"},
            )

        except JWTClaimsError as e:
            logger.warning("JWT claims error", error=str(e))
            raise AuthenticationError(
                message="Invalid token claims",
                details={"reason": "invalid_claims"},
            )

        except JWTError as e:
            logger.warning(
                "JWT validation failed",
                error=str(e),
                error_type=type(e).__name__,
                token_prefix=token[:50] if token else "",
            )
            raise AuthenticationError(
                message="Invalid or expired token",
                details={"reason": "validation_failed", "error": str(e)},
            )

        except Exception as e:
            logger.error("Unexpected error validating token", error=str(e))
            raise AuthenticationError(
                message="Token validation failed",
                details={"reason": "unknown"},
            )

    async def get_user(self, clerk_id: str) -> ClerkUser:
        """Fetch user data from Clerk's API.

        Args:
            clerk_id: Clerk user ID (e.g., "user_abc123").

        Returns:
            Clerk user data.

        Raises:
            ExternalServiceError: If user cannot be fetched.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"https://api.clerk.com/v1/users/{clerk_id}",
                    headers={
                        "Authorization": f"Bearer {self._settings.secret_key.get_secret_value()}",
                        "Content-Type": "application/json",
                    },
                )

                if response.status_code == 404:
                    raise ExternalServiceError(
                        service="Clerk",
                        message=f"User not found: {clerk_id}",
                    )

                if response.status_code != 200:
                    raise ExternalServiceError(
                        service="Clerk",
                        message=f"User fetch failed: HTTP {response.status_code}",
                    )

                data = response.json()
                return ClerkUser(**data)

        except httpx.HTTPError as e:
            logger.error("Failed to fetch Clerk user", clerk_id=clerk_id, error=str(e))
            raise ExternalServiceError(
                service="Clerk",
                message="Unable to fetch user from Clerk",
                original_error=str(e),
            )

    async def update_user_metadata(
        self,
        clerk_id: str,
        public_metadata: dict[str, Any] | None = None,
        private_metadata: dict[str, Any] | None = None,
    ) -> ClerkUser:
        """Update user metadata in Clerk.

        Used to store tenant_id and role after registration.

        Args:
            clerk_id: Clerk user ID.
            public_metadata: Public metadata to update.
            private_metadata: Private metadata to update.

        Returns:
            Updated Clerk user data.

        Raises:
            ExternalServiceError: If update fails.
        """
        try:
            payload: dict[str, Any] = {}
            if public_metadata is not None:
                payload["public_metadata"] = public_metadata
            if private_metadata is not None:
                payload["private_metadata"] = private_metadata

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.patch(
                    f"https://api.clerk.com/v1/users/{clerk_id}",
                    headers={
                        "Authorization": f"Bearer {self._settings.secret_key.get_secret_value()}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

                if response.status_code not in (200, 201):
                    raise ExternalServiceError(
                        service="Clerk",
                        message=f"User metadata update failed: HTTP {response.status_code}",
                    )

                data = response.json()
                return ClerkUser(**data)

        except httpx.HTTPError as e:
            logger.error(
                "Failed to update Clerk user metadata",
                clerk_id=clerk_id,
                error=str(e),
            )
            raise ExternalServiceError(
                service="Clerk",
                message="Unable to update user metadata in Clerk",
                original_error=str(e),
            )


def get_clerk_client(redis: Any | None = None) -> ClerkClient:
    """Create a ClerkClient instance with settings from config.

    Args:
        redis: Optional Redis client for distributed caching.

    Returns:
        Configured ClerkClient instance.
    """
    from app.config import get_settings

    settings = get_settings()
    return ClerkClient(settings=settings.clerk, redis=redis)
