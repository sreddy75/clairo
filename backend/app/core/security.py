"""Security utilities for authentication and authorization.

Provides JWT token creation/validation and multi-tenancy access control.

Usage:
    from app.core.security import create_access_token, decode_access_token

    # Create a token
    token = create_access_token(user_id=str(user.id), tenant_id=str(tenant.id))

    # Decode a token
    payload = decode_access_token(token)
"""

import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.exceptions import AuthenticationError, AuthorizationError


class TokenPayload(BaseModel):
    """JWT token payload structure.

    Contains claims that identify the user and their access context.
    """

    sub: str = Field(..., description="Subject (user ID)")
    exp: datetime = Field(..., description="Expiration time")
    iat: datetime = Field(..., description="Issued at time")
    tenant_id: str | None = Field(default=None, description="Tenant ID for multi-tenancy")
    roles: list[str] = Field(default_factory=list, description="User roles")
    jti: str = Field(default_factory=lambda: str(uuid.uuid4()), description="JWT ID")


def create_access_token(
    user_id: str,
    tenant_id: str | None = None,
    roles: list[str] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token.

    Args:
        user_id: The user's unique identifier.
        tenant_id: The tenant ID for multi-tenancy (optional).
        roles: List of user roles (optional).
        expires_delta: Custom expiration time (optional).

    Returns:
        Encoded JWT token string.
    """
    settings = get_settings()
    security = settings.security

    if expires_delta is None:
        expires_delta = timedelta(minutes=security.access_token_expire_minutes)

    now = datetime.now(UTC)
    expire = now + expires_delta

    payload = TokenPayload(
        sub=user_id,
        exp=expire,
        iat=now,
        tenant_id=tenant_id,
        roles=roles or [],
    )

    encoded_jwt: str = jwt.encode(
        payload.model_dump(),
        security.secret_key.get_secret_value(),
        algorithm=security.algorithm,
    )
    return encoded_jwt


def create_refresh_token(
    user_id: str,
    tenant_id: str | None = None,
) -> str:
    """Create a JWT refresh token.

    Refresh tokens have longer expiration and are used to obtain new access tokens.

    Args:
        user_id: The user's unique identifier.
        tenant_id: The tenant ID for multi-tenancy (optional).

    Returns:
        Encoded JWT refresh token string.
    """
    settings = get_settings()
    security = settings.security

    expires_delta = timedelta(days=security.refresh_token_expire_days)
    now = datetime.now(UTC)
    expire = now + expires_delta

    payload = TokenPayload(
        sub=user_id,
        exp=expire,
        iat=now,
        tenant_id=tenant_id,
        roles=[],  # Refresh tokens don't carry roles
    )

    encoded_jwt: str = jwt.encode(
        payload.model_dump(),
        security.secret_key.get_secret_value(),
        algorithm=security.algorithm,
    )
    return encoded_jwt


def decode_access_token(token: str) -> TokenPayload:
    """Decode and validate a JWT access token.

    Args:
        token: The JWT token string.

    Returns:
        TokenPayload with decoded claims.

    Raises:
        AuthenticationError: If the token is invalid or expired.
    """
    settings = get_settings()
    security = settings.security

    try:
        payload = jwt.decode(
            token,
            security.secret_key.get_secret_value(),
            algorithms=[security.algorithm],
        )
        return TokenPayload(**payload)
    except JWTError as e:
        raise AuthenticationError(
            message="Invalid or expired token",
            details={"error": str(e)},
        ) from e


def verify_tenant_access(
    payload: TokenPayload,
    tenant_id: str | uuid.UUID,
) -> bool:
    """Verify that a user has access to a specific tenant.

    Args:
        payload: The decoded token payload.
        tenant_id: The tenant ID to check access for.

    Returns:
        True if the user has access.

    Raises:
        AuthorizationError: If the user doesn't have access to the tenant.
    """
    tenant_id_str = str(tenant_id)

    # If payload has no tenant_id, user is a system/admin user
    if payload.tenant_id is None:
        # Check if user has admin role for cross-tenant access
        if "admin" in payload.roles or "system" in payload.roles:
            return True
        raise AuthorizationError(
            message="Tenant access required",
            resource="tenant",
            action="access",
        )

    # Check if the tenant ID matches
    if payload.tenant_id != tenant_id_str:
        raise AuthorizationError(
            message="Access denied to this tenant",
            resource="tenant",
            action="access",
        )

    return True


def verify_role(
    payload: TokenPayload,
    required_roles: list[str],
    require_all: bool = False,
) -> bool:
    """Verify that a user has the required role(s).

    Args:
        payload: The decoded token payload.
        required_roles: List of roles to check for.
        require_all: If True, user must have ALL roles. If False, any one role suffices.

    Returns:
        True if the user has the required role(s).

    Raises:
        AuthorizationError: If the user doesn't have the required role(s).
    """
    user_roles = set(payload.roles)

    if require_all:
        has_access = all(role in user_roles for role in required_roles)
    else:
        has_access = any(role in user_roles for role in required_roles)

    if not has_access:
        raise AuthorizationError(
            message="Insufficient permissions",
            resource="role",
            action="access",
        )

    return True


def extract_token_from_header(authorization: str | None) -> str:
    """Extract the token from an Authorization header.

    Args:
        authorization: The Authorization header value (e.g., "Bearer xxx").

    Returns:
        The extracted token string.

    Raises:
        AuthenticationError: If the header is missing or malformed.
    """
    if not authorization:
        raise AuthenticationError(message="Authorization header missing")

    parts = authorization.split()

    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationError(message="Invalid authorization header format")

    return parts[1]


def hash_password(password: str) -> str:
    """Hash a password for storage.

    Args:
        password: The plain text password.

    Returns:
        The hashed password.
    """
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed: str = pwd_context.hash(password)
    return hashed


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Args:
        plain_password: The plain text password to verify.
        hashed_password: The stored hashed password.

    Returns:
        True if the password matches, False otherwise.
    """
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    result: bool = pwd_context.verify(plain_password, hashed_password)
    return result
