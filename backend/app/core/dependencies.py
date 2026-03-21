"""Common FastAPI dependencies for Clairo.

Provides reusable dependencies for authentication, database access,
and other cross-cutting concerns.

Two authentication patterns are supported:
1. Clerk-based auth (JWT via middleware) - for production with Clerk
2. Local JWT auth (direct token validation) - for development/testing

Usage:
    from app.core.dependencies import DbSession, get_current_practice_user

    @router.get("/items")
    async def get_items(
        db: DbSession,
        user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    ) -> list[Item]:
        ...
"""

import uuid
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.core.security import (
    TokenPayload,
    decode_access_token,
    extract_token_from_header,
)
from app.database import get_db


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> TokenPayload:
    """FastAPI dependency to get the current authenticated user.

    Extracts and validates the JWT token from the Authorization header.

    Args:
        authorization: The Authorization header value.

    Returns:
        TokenPayload with the authenticated user's claims.

    Raises:
        AuthenticationError: If authentication fails.
    """
    if not authorization:
        raise AuthenticationError(message="Authorization header required")

    token = extract_token_from_header(authorization)
    return decode_access_token(token)


async def get_optional_user(
    authorization: Annotated[str | None, Header()] = None,
) -> TokenPayload | None:
    """FastAPI dependency to optionally get the current user.

    Unlike get_current_user, this returns None if no auth header is present
    instead of raising an error. Useful for endpoints that work with or
    without authentication.

    Args:
        authorization: The Authorization header value.

    Returns:
        TokenPayload if authenticated, None otherwise.
    """
    if not authorization:
        return None

    try:
        token = extract_token_from_header(authorization)
        return decode_access_token(token)
    except AuthenticationError:
        return None


def require_roles(*required_roles: str) -> Any:
    """Dependency factory for role-based access control.

    Creates a dependency that checks if the user has any of the required roles.

    Args:
        *required_roles: Roles that grant access (user needs at least one).

    Returns:
        A dependency function that validates roles.

    Usage:
        @router.get("/admin")
        async def admin_endpoint(
            user: CurrentUser,
            _: None = Depends(require_roles("admin", "superuser")),
        ) -> dict:
            ...
    """
    from app.core.security import verify_role

    async def role_checker(
        user: Annotated[TokenPayload, Depends(get_current_user)],
    ) -> None:
        verify_role(user, list(required_roles), require_all=False)

    return Depends(role_checker)


def require_tenant_access(tenant_id_param: str = "tenant_id") -> Any:
    """Dependency factory for tenant-based access control.

    Creates a dependency that checks if the user has access to the requested tenant.

    Args:
        tenant_id_param: The path/query parameter name containing the tenant ID.

    Returns:
        A dependency function that validates tenant access.

    Usage:
        @router.get("/{tenant_id}/items")
        async def get_tenant_items(
            tenant_id: UUID,
            user: CurrentUser,
            _: None = Depends(require_tenant_access()),
        ) -> list[Item]:
            ...
    """

    # Note: This is a simplified implementation.
    # In a real app, you'd extract tenant_id from the request path/query.
    async def tenant_checker(
        user: Annotated[TokenPayload, Depends(get_current_user)],
    ) -> None:
        if user.tenant_id:
            # User is already scoped to a tenant, access is allowed
            pass
        # For cross-tenant access, additional checks would be needed

    return Depends(tenant_checker)


# Type aliases for cleaner route signatures
DbSession = Annotated[AsyncSession, Depends(get_db)]
"""Annotated type for database session dependency."""

CurrentUser = Annotated[TokenPayload, Depends(get_current_user)]
"""Annotated type for authenticated user dependency."""

OptionalUser = Annotated[TokenPayload | None, Depends(get_optional_user)]
"""Annotated type for optional user dependency."""


# =============================================================================
# Clerk-based Authentication Dependencies
# =============================================================================
# These dependencies work with the JWTMiddleware and TenantMiddleware
# to provide user/tenant context from Clerk JWT claims.


async def get_clerk_user(request: Request) -> "ClerkTokenPayload":
    """Get current user from Clerk JWT (set by JWTMiddleware).

    This dependency retrieves the user claims that were validated
    and set by JWTMiddleware on the request state.

    Args:
        request: FastAPI request object.

    Returns:
        ClerkTokenPayload with validated JWT claims.

    Raises:
        HTTPException: If user is not authenticated.
    """

    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


async def get_current_tenant_id(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> uuid.UUID:
    """Get current tenant ID from request or database lookup.

    This dependency retrieves the tenant ID from the user claims.
    If not in claims, falls back to database lookup using Clerk user ID.
    It requires the user to be authenticated and have a tenant association.

    Args:
        request: FastAPI request object.
        session: Database session for fallback lookup.

    Returns:
        Tenant UUID.

    Raises:
        HTTPException: If tenant context is not set.
    """
    from sqlalchemy import select

    from app.modules.auth.clerk import ClerkTokenPayload
    from app.modules.auth.models import PracticeUser

    user: ClerkTokenPayload | None = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authentication required",
        )

    # Try JWT claims first
    if user.tenant_id is not None:
        return user.tenant_id

    # Fallback: lookup from database using Clerk user ID
    result = await session.execute(
        select(PracticeUser.tenant_id).where(PracticeUser.clerk_id == user.sub)
    )
    tenant_id = result.scalar_one_or_none()

    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant context required - user not registered",
        )
    return tenant_id


async def get_or_create_onboarding_tenant(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> uuid.UUID:
    """Get or create tenant for onboarding flow.

    This dependency is specifically for onboarding endpoints where the tenant
    may not exist yet. It:
    1. Checks if a tenant exists for the Clerk user
    2. If not, creates a new tenant and practice user
    3. Returns the tenant_id

    Args:
        request: FastAPI request object.
        session: Database session.

    Returns:
        Tenant UUID (existing or newly created).

    Raises:
        HTTPException: If user is not authenticated.
    """
    from sqlalchemy import select

    from app.modules.auth.clerk import ClerkTokenPayload
    from app.modules.auth.models import PracticeUser, Tenant, User

    user: ClerkTokenPayload | None = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authentication required",
        )

    # Try JWT claims first
    if user.tenant_id is not None:
        return user.tenant_id

    # Check if user already has a tenant
    result = await session.execute(
        select(PracticeUser.tenant_id).where(PracticeUser.clerk_id == user.sub)
    )
    tenant_id = result.scalar_one_or_none()

    if tenant_id is not None:
        return tenant_id

    # Create new tenant and user for onboarding
    # Extract user info from Clerk claims
    from datetime import UTC, datetime, timedelta

    from app.modules.auth.models import SubscriptionStatus, SubscriptionTier, UserRole, UserType

    email = user.email or f"{user.sub}@placeholder.clairo.com"
    # Derive name from email (ClerkTokenPayload doesn't have name field)
    name = email.split("@")[0].replace(".", " ").replace("_", " ").title()

    # Calculate trial end date (14 days from now)
    trial_end_date = datetime.now(UTC) + timedelta(days=14)

    # Create tenant
    tenant = Tenant(
        name=f"{name}'s Practice",
        slug=f"practice-{user.sub[:8]}",
        tier=SubscriptionTier.STARTER,  # Default, will be updated after tier selection
        subscription_status=SubscriptionStatus.TRIAL,  # Start as trial
        current_period_end=trial_end_date,  # Trial ends in 14 days
        owner_email=email,  # For billing communications
    )
    session.add(tenant)
    await session.flush()  # Get tenant ID

    # Create base user (User model only has email, user_type, is_active)
    base_user = User(
        email=email,
        is_active=True,
        user_type=UserType.PRACTICE_USER,
    )
    session.add(base_user)
    await session.flush()

    # Create practice user linking Clerk ID to tenant
    practice_user = PracticeUser(
        user_id=base_user.id,
        tenant_id=tenant.id,
        clerk_id=user.sub,
        role=UserRole.ADMIN,  # First user is admin/owner
    )
    session.add(practice_user)
    await session.commit()

    return tenant.id


async def get_current_practice_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> "PracticeUser":
    """Get current practice user with full database record.

    This dependency:
    1. Gets user claims from JWTMiddleware
    2. Looks up the full PracticeUser record from the database
    3. Returns the user with relationships loaded

    Use this when you need the full user record, not just JWT claims.

    Args:
        request: FastAPI request object.
        session: Database session.

    Returns:
        PracticeUser with user and tenant relationships loaded.

    Raises:
        HTTPException: If user is not authenticated or not found.
    """
    from app.modules.auth.clerk import ClerkTokenPayload
    from app.modules.auth.repository import PracticeUserRepository

    # Get user claims from middleware
    user: ClerkTokenPayload | None = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # Get practice user from database
    repo = PracticeUserRepository(session)
    practice_user = await repo.get_by_clerk_id(user.sub, load_relations=True)

    if practice_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in database",
        )

    return practice_user


async def get_current_active_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> "PracticeUser":
    """Get current active practice user.

    Same as get_current_practice_user but also verifies the user is active.
    Use this for endpoints that should reject deactivated users.

    Args:
        request: FastAPI request object.
        session: Database session.

    Returns:
        Active PracticeUser with relationships loaded.

    Raises:
        HTTPException: If user is not authenticated, not found, or deactivated.
    """
    practice_user = await get_current_practice_user(request, session)

    # Check if user is active (via base User)
    if not practice_user.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return practice_user


# Type aliases for Clerk-based auth
ClerkUser = Annotated["ClerkTokenPayload", Depends(get_clerk_user)]
"""Annotated type for Clerk JWT claims dependency."""

TenantId = Annotated[uuid.UUID, Depends(get_current_tenant_id)]
"""Annotated type for current tenant ID dependency."""

OnboardingTenantId = Annotated[uuid.UUID, Depends(get_or_create_onboarding_tenant)]
"""Annotated type for onboarding tenant ID (creates tenant if needed)."""

PracticeUserDep = Annotated["PracticeUser", Depends(get_current_practice_user)]
"""Annotated type for current practice user dependency."""

ActivePracticeUser = Annotated["PracticeUser", Depends(get_current_active_user)]
"""Annotated type for current active practice user dependency."""


# Import type hints only for type checking
if False:  # TYPE_CHECKING equivalent that avoids circular imports
    from app.modules.auth.clerk import ClerkTokenPayload
    from app.modules.auth.models import PracticeUser


# =============================================================================
# AI/Knowledge Base Dependencies
# =============================================================================

# Cached service instances
_pinecone_service: "PineconeService | None" = None
_voyage_service: "VoyageService | None" = None


async def get_pinecone_service() -> "PineconeService":
    """Get cached Pinecone service instance.

    The service is created lazily on first request and cached for reuse.
    This avoids creating multiple client connections.

    Returns:
        PineconeService instance.
    """
    global _pinecone_service

    if _pinecone_service is None:
        from app.config import get_settings
        from app.core.pinecone_service import PineconeService

        settings = get_settings()
        _pinecone_service = PineconeService(settings.pinecone)

    return _pinecone_service


async def get_voyage_service() -> "VoyageService":
    """Get cached Voyage embedding service instance.

    The service is created lazily on first request and cached for reuse.

    Returns:
        VoyageService instance.

    Raises:
        ValueError: If VOYAGE_API_KEY is not configured.
    """
    global _voyage_service

    if _voyage_service is None:
        from app.config import get_settings
        from app.core.voyage import VoyageService

        settings = get_settings()
        _voyage_service = VoyageService(settings.voyage)

    return _voyage_service


# Type aliases for AI dependencies
PineconeDep = Annotated["PineconeService", Depends(get_pinecone_service)]
"""Annotated type for Pinecone service dependency."""

VoyageDep = Annotated["VoyageService", Depends(get_voyage_service)]
"""Annotated type for Voyage embedding service dependency."""


# Cached chatbot instance
_chatbot_service: "KnowledgeChatbot | None" = None


async def get_chatbot_service() -> "KnowledgeChatbot":
    """Get cached Knowledge Chatbot service instance.

    The service is created lazily on first request and cached for reuse.

    Returns:
        KnowledgeChatbot instance.

    Raises:
        ValueError: If ANTHROPIC_API_KEY is not configured.
    """
    global _chatbot_service

    if _chatbot_service is None:
        from app.config import get_settings
        from app.modules.knowledge.chatbot import KnowledgeChatbot

        settings = get_settings()
        pinecone = await get_pinecone_service()
        voyage = await get_voyage_service()
        _chatbot_service = KnowledgeChatbot(settings.anthropic, pinecone, voyage)

    return _chatbot_service


async def get_current_tenant(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> "Tenant":
    """Get current tenant with full database record.

    This dependency:
    1. Gets tenant ID from the request context
    2. Looks up the full Tenant record from the database
    3. Returns the tenant with relationships loaded

    Use this when you need the full tenant record for operations.

    Args:
        request: FastAPI request object.
        session: Database session.

    Returns:
        Tenant object with all fields loaded.

    Raises:
        HTTPException: If tenant is not found.
    """
    from sqlalchemy import select

    from app.modules.auth.models import Tenant

    # Get tenant ID from middleware context
    tenant_id = await get_current_tenant_id(request, session)

    # Fetch full tenant record
    result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    return tenant


# Type aliases for AI dependencies
ChatbotDep = Annotated["KnowledgeChatbot", Depends(get_chatbot_service)]
"""Annotated type for Knowledge Chatbot service dependency."""

# Type alias for tenant dependency
TenantDep = Annotated["Tenant", Depends(get_current_tenant)]
"""Annotated type for current tenant dependency."""


# Extended type hints
if TYPE_CHECKING:
    from app.core.pinecone_service import PineconeService
    from app.core.voyage import VoyageService
    from app.modules.knowledge.chatbot import KnowledgeChatbot

# Import Tenant at module level for FastAPI annotation resolution
from app.modules.auth.models import Tenant
