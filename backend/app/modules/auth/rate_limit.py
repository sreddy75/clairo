"""Rate limiting for authentication endpoints.

This module provides rate limiting to prevent abuse:
- Login failures: 5 per minute per email
- Invitation creation: 10 per tenant per hour
- Registration: 3 per IP per minute

Uses in-memory storage for development, Redis for production.

Usage:
    from app.modules.auth.rate_limit import (
        check_login_rate_limit,
        check_invitation_rate_limit,
    )

    # In endpoint
    if not await check_login_rate_limit(email):
        raise HTTPException(429, "Too many login attempts")
"""

import time
from dataclasses import dataclass
from threading import Lock
from uuid import UUID

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RateLimitEntry:
    """Entry tracking rate limit attempts.

    Attributes:
        count: Number of attempts.
        first_attempt: Timestamp of first attempt in window.
        window_seconds: Duration of the rate limit window.
    """

    count: int = 0
    first_attempt: float = 0.0
    window_seconds: int = 60

    def is_expired(self) -> bool:
        """Check if the rate limit window has expired."""
        return time.time() - self.first_attempt > self.window_seconds

    def increment(self) -> None:
        """Increment the attempt counter."""
        current_time = time.time()
        if self.is_expired() or self.first_attempt == 0:
            self.count = 1
            self.first_attempt = current_time
        else:
            self.count += 1


class InMemoryRateLimiter:
    """In-memory rate limiter for development.

    Thread-safe implementation using locks.
    Not suitable for multi-process deployments.

    Attributes:
        storage: Dict of rate limit entries by key.
        lock: Thread lock for concurrent access.
    """

    def __init__(self) -> None:
        """Initialize the rate limiter."""
        self._storage: dict[str, RateLimitEntry] = {}
        self._lock = Lock()

    def _cleanup_expired(self) -> None:
        """Remove expired entries from storage."""
        current_time = time.time()
        expired_keys = [
            key
            for key, entry in self._storage.items()
            if current_time - entry.first_attempt > entry.window_seconds
        ]
        for key in expired_keys:
            del self._storage[key]

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int = 60,
    ) -> tuple[bool, int, int]:
        """Check if request is within rate limit.

        Args:
            key: Unique identifier for the rate limit bucket.
            limit: Maximum number of requests allowed.
            window_seconds: Duration of the rate limit window.

        Returns:
            Tuple of (is_allowed, remaining, retry_after_seconds).
        """
        with self._lock:
            # Cleanup expired entries periodically
            if len(self._storage) > 1000:
                self._cleanup_expired()

            if key not in self._storage:
                self._storage[key] = RateLimitEntry(window_seconds=window_seconds)

            entry = self._storage[key]

            # Check if window expired
            if entry.is_expired():
                entry.count = 0
                entry.first_attempt = time.time()

            # Check limit
            if entry.count >= limit:
                retry_after = int(entry.window_seconds - (time.time() - entry.first_attempt))
                return False, 0, max(0, retry_after)

            # Increment counter
            entry.increment()
            remaining = limit - entry.count

            return True, remaining, 0

    async def reset(self, key: str) -> None:
        """Reset rate limit for a key.

        Args:
            key: Key to reset.
        """
        with self._lock:
            if key in self._storage:
                del self._storage[key]


# Global rate limiter instance
_rate_limiter: InMemoryRateLimiter | None = None


def get_rate_limiter() -> InMemoryRateLimiter:
    """Get the global rate limiter instance.

    Returns:
        Rate limiter instance.
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = InMemoryRateLimiter()
    return _rate_limiter


# =============================================================================
# Rate Limit Configuration
# =============================================================================


# Login failures: 5 per minute per email
LOGIN_RATE_LIMIT = 5
LOGIN_RATE_WINDOW = 60  # seconds

# Invitation creation: 10 per tenant per hour
INVITATION_RATE_LIMIT = 10
INVITATION_RATE_WINDOW = 3600  # seconds

# Registration: 3 per IP per minute
REGISTRATION_RATE_LIMIT = 3
REGISTRATION_RATE_WINDOW = 60  # seconds


# =============================================================================
# Rate Limit Functions
# =============================================================================


async def check_login_rate_limit(email: str) -> tuple[bool, int, int]:
    """Check login rate limit for an email.

    Args:
        email: Email address attempting login.

    Returns:
        Tuple of (is_allowed, remaining_attempts, retry_after_seconds).
    """
    limiter = get_rate_limiter()
    key = f"login:{email.lower()}"

    return await limiter.check_rate_limit(
        key=key,
        limit=LOGIN_RATE_LIMIT,
        window_seconds=LOGIN_RATE_WINDOW,
    )


async def reset_login_rate_limit(email: str) -> None:
    """Reset login rate limit after successful login.

    Args:
        email: Email address that logged in successfully.
    """
    limiter = get_rate_limiter()
    key = f"login:{email.lower()}"
    await limiter.reset(key)


async def check_invitation_rate_limit(tenant_id: UUID) -> tuple[bool, int, int]:
    """Check invitation creation rate limit for a tenant.

    Args:
        tenant_id: Tenant UUID.

    Returns:
        Tuple of (is_allowed, remaining_invitations, retry_after_seconds).
    """
    limiter = get_rate_limiter()
    key = f"invitation:{tenant_id}"

    return await limiter.check_rate_limit(
        key=key,
        limit=INVITATION_RATE_LIMIT,
        window_seconds=INVITATION_RATE_WINDOW,
    )


async def check_registration_rate_limit(ip_address: str) -> tuple[bool, int, int]:
    """Check registration rate limit for an IP address.

    Args:
        ip_address: Client IP address.

    Returns:
        Tuple of (is_allowed, remaining_attempts, retry_after_seconds).
    """
    limiter = get_rate_limiter()
    key = f"registration:{ip_address}"

    return await limiter.check_rate_limit(
        key=key,
        limit=REGISTRATION_RATE_LIMIT,
        window_seconds=REGISTRATION_RATE_WINDOW,
    )


# =============================================================================
# FastAPI Dependencies
# =============================================================================


from fastapi import HTTPException, Request, status


async def rate_limit_registration(request: Request) -> None:
    """FastAPI dependency for registration rate limiting.

    Args:
        request: FastAPI request object.

    Raises:
        HTTPException: If rate limit exceeded.
    """
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"

    is_allowed, remaining, retry_after = await check_registration_rate_limit(client_ip)

    if not is_allowed:
        logger.warning(
            "Registration rate limit exceeded",
            ip_address=client_ip,
            retry_after=retry_after,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )


async def rate_limit_invitation(tenant_id: UUID) -> None:
    """Check invitation rate limit for a tenant.

    Args:
        tenant_id: Tenant UUID.

    Raises:
        HTTPException: If rate limit exceeded.
    """
    is_allowed, remaining, retry_after = await check_invitation_rate_limit(tenant_id)

    if not is_allowed:
        logger.warning(
            "Invitation rate limit exceeded",
            tenant_id=str(tenant_id),
            retry_after=retry_after,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many invitations sent. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )
