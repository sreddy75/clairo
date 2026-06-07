"""FastAPI router for authentication endpoints.

This module provides endpoints for:
- User registration and authentication
- Current user profile
- Session management (logout)
- User management (Admin only)
- Invitation management (Admin only)
- Tenant settings (Admin only)
- Clerk webhooks

All endpoints are documented with OpenAPI schemas.

Usage:
    from app.modules.auth.router import router

    app.include_router(router, prefix="/api/v1/auth", tags=["auth"])
"""

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.database import get_db as get_db_session

from .clerk import ClerkTokenPayload
from .middleware import get_current_user
from .models import PracticeUser
from .permissions import Permission, require_permission
from .schemas import (
    AcceptTermsRequest,
    AcceptTermsResponse,
    BootstrapResponse,
    InvitationCreate,
    InvitationListResponse,
    InvitationPublic,
    InvitationResponse,
    LogoutRequest,
    LogoutResponse,
    MeResponse,
    PracticeUserDeactivate,
    PracticeUserResponse,
    PracticeUserRoleUpdate,
    PracticeUserWithTenant,
    RegisterRequest,
    RegisterResponse,
    TenantResponse,
    TenantSettingsResponse,
    TenantSummary,
    TenantUpdate,
    TosVersionResponse,
    UserActionResponse,
    UserListResponse,
)
from .service import AuthService, InvitationService, UserService

logger = structlog.get_logger(__name__)

router = APIRouter()


# =============================================================================
# Helper Dependencies
# =============================================================================


async def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthService:
    """Get AuthService instance.

    Args:
        session: Database session.

    Returns:
        Configured AuthService.
    """
    return AuthService(session=session)


async def get_practice_user(
    current_user: Annotated[ClerkTokenPayload, Depends(get_current_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> PracticeUser:
    """Get current practice user from database.

    Args:
        current_user: JWT claims from middleware.
        auth_service: Auth service instance.

    Returns:
        Practice user with relationships loaded.

    Raises:
        HTTPException: If user not found in database.
    """
    practice_user = await auth_service.get_current_user(current_user.sub)
    if practice_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in database",
        )
    return practice_user


# =============================================================================
# Registration Endpoints
# =============================================================================


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Complete user registration",
    description="""
    Complete registration after Clerk authentication.

    This endpoint should be called after the user has authenticated with Clerk
    but before they are fully registered in the system.

    Either provide:
    - `tenant_name` to create a new practice (user becomes admin)
    - `invitation_token` to join an existing practice
    """,
    responses={
        201: {"description": "Registration successful"},
        400: {"description": "Invalid request (validation error)"},
        404: {"description": "Invitation not found"},
        409: {"description": "Email already registered"},
    },
)
async def register(
    request: RegisterRequest,
    current_user: Annotated[ClerkTokenPayload, Depends(get_current_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> RegisterResponse:
    """Complete user registration after Clerk authentication.

    Args:
        request: Registration request.
        current_user: JWT claims from Clerk.
        auth_service: Auth service instance.

    Returns:
        Registration result.
    """
    try:
        result = await auth_service.register_user(
            clerk_id=current_user.sub,
            request=request,
        )

        # Build response
        practice_user_response = PracticeUserResponse(
            id=result.practice_user.id,
            user_id=result.user.id,
            tenant_id=result.tenant.id,
            clerk_id=result.practice_user.clerk_id,
            email=result.user.email,
            role=result.practice_user.role,
            is_active=result.user.is_active,
            mfa_enabled=result.practice_user.mfa_enabled,
            last_login_at=result.practice_user.last_login_at,
            created_at=result.practice_user.created_at,
            updated_at=result.practice_user.updated_at,
        )

        tenant_response = TenantResponse(
            id=result.tenant.id,
            name=result.tenant.name,
            slug=result.tenant.slug,
            subscription_status=result.tenant.subscription_status,
            mfa_required=result.tenant.mfa_required,
            is_active=result.tenant.is_active,
            created_at=result.tenant.created_at,
            updated_at=result.tenant.updated_at,
        )

        return RegisterResponse(
            user=practice_user_response,
            tenant=tenant_response,
            is_new_tenant=result.is_new_tenant,
        )

    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": e.code, "message": e.message}},
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": e.code, "message": e.message}},
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": e.message}},
        )


# =============================================================================
# Current User Endpoints
# =============================================================================


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Get current user profile",
    description="""
    Get the current authenticated user's profile including:
    - User details
    - Tenant information
    - List of permissions based on role
    """,
    responses={
        200: {"description": "Current user profile"},
        401: {"description": "Not authenticated"},
        404: {"description": "User not found"},
    },
)
async def get_me(
    current_user: Annotated[ClerkTokenPayload, Depends(get_current_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> MeResponse:
    """Get current user profile.

    Args:
        current_user: JWT claims from Clerk.
        auth_service: Auth service instance.

    Returns:
        Current user with tenant and permissions.
    """
    practice_user = await auth_service.get_current_user(current_user.sub)
    if practice_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in database",
        )

    # Get user's base identity
    user = practice_user.user
    tenant = practice_user.tenant

    # Build tenant summary
    tenant_summary = TenantSummary(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
    )

    # Build practice user with tenant response
    practice_user_with_tenant = PracticeUserWithTenant(
        id=practice_user.id,
        user_id=user.id,
        tenant_id=tenant.id,
        clerk_id=practice_user.clerk_id,
        email=user.email,
        role=practice_user.role,
        is_active=user.is_active,
        mfa_enabled=practice_user.mfa_enabled,
        last_login_at=practice_user.last_login_at,
        created_at=practice_user.created_at,
        updated_at=practice_user.updated_at,
        tenant=tenant_summary,
    )

    # Get permissions for role
    permissions = auth_service.get_permissions_for_role(practice_user.role)

    return MeResponse(
        user=practice_user_with_tenant,
        permissions=permissions,
    )


# =============================================================================
# Bootstrap Endpoint (combines /me + /features + /trial-status)
# =============================================================================


@router.get(
    "/bootstrap",
    response_model=BootstrapResponse,
    summary="Bootstrap data for frontend layout",
    description="""
    Get all data needed for the frontend layout in a single request.

    Combines the responses from:
    - GET /api/v1/auth/me (user profile, tenant, permissions)
    - GET /api/v1/features (tier feature access)
    - GET /api/v1/trial-status (trial period info)

    Each sub-call is independent; a failure in features or trial_status
    will not prevent the user data from being returned.
    """,
    responses={
        200: {"description": "Bootstrap data"},
        401: {"description": "Not authenticated"},
        404: {"description": "User not found"},
    },
)
async def get_bootstrap(
    current_user: Annotated[ClerkTokenPayload, Depends(get_current_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BootstrapResponse:
    """Get bootstrap data combining user profile, features, and trial status.

    Args:
        current_user: JWT claims from Clerk.
        auth_service: Auth service instance.
        session: Database session.

    Returns:
        Combined bootstrap response with user, features, and trial status.
    """
    # ── 1. User profile (same logic as /me) ──────────────────────────────
    practice_user = await auth_service.get_current_user(current_user.sub)
    if practice_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in database",
        )

    user = practice_user.user
    tenant = practice_user.tenant

    tenant_summary = TenantSummary(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
    )

    practice_user_with_tenant = PracticeUserWithTenant(
        id=practice_user.id,
        user_id=user.id,
        tenant_id=tenant.id,
        clerk_id=practice_user.clerk_id,
        email=user.email,
        role=practice_user.role,
        is_active=user.is_active,
        mfa_enabled=practice_user.mfa_enabled,
        last_login_at=practice_user.last_login_at,
        created_at=practice_user.created_at,
        updated_at=practice_user.updated_at,
        tenant=tenant_summary,
    )

    permissions = auth_service.get_permissions_for_role(practice_user.role)

    me_response = MeResponse(
        user=practice_user_with_tenant,
        permissions=permissions,
    )

    # ── Fetch full tenant record for features + trial status ────────────
    full_tenant = None
    try:
        from sqlalchemy import select as sa_select

        from app.modules.auth.models import Tenant

        tenant_result = await session.execute(sa_select(Tenant).where(Tenant.id == tenant.id))
        full_tenant = tenant_result.scalar_one_or_none()
    except Exception:
        logger.warning(
            "bootstrap_tenant_fetch_failed",
            clerk_id=current_user.sub,
            exc_info=True,
        )

    # ── 2. Features (same logic as GET /features) ────────────────────────
    features_response = None
    try:
        if full_tenant is not None:
            from app.core.feature_flags import get_tier_features
            from app.modules.billing.schemas import (
                FeaturesResponse,
                TierFeatures as BillingTierFeatures,
            )

            tier = full_tenant.tier.value
            features = get_tier_features(tier)

            can_access = {
                "ai_insights": True,
                "client_portal": features.get("client_portal", False),
                "custom_triggers": features.get("custom_triggers", False),
                "api_access": features.get("api_access", False),
                "knowledge_base": features.get("knowledge_base", False),
                "magic_zone": features.get("magic_zone", False),
            }

            features_response = FeaturesResponse(
                tier=tier,  # type: ignore[arg-type]
                features=BillingTierFeatures(**features),
                can_access=can_access,
            )
    except Exception:
        logger.warning(
            "bootstrap_features_failed",
            clerk_id=current_user.sub,
            exc_info=True,
        )

    # ── 3. Trial status (same logic as GET /trial-status) ────────────────
    trial_status_response = None
    try:
        if full_tenant is not None:
            from datetime import UTC, datetime

            from app.core.feature_flags import TIER_PRICING
            from app.modules.auth.models import SubscriptionStatus
            from app.modules.billing.schemas import TrialStatusResponse

            is_trial = full_tenant.subscription_status == SubscriptionStatus.TRIAL
            tier_val = full_tenant.tier.value
            price_monthly = TIER_PRICING.get(tier_val, 0)

            days_remaining = None
            trial_end_date = None

            if is_trial and full_tenant.current_period_end:
                trial_end_date = full_tenant.current_period_end
                now = datetime.now(UTC)
                if trial_end_date.tzinfo is None:
                    trial_end_date = trial_end_date.replace(tzinfo=UTC)
                delta = trial_end_date - now
                days_remaining = max(0, delta.days)

            trial_status_response = TrialStatusResponse(
                is_trial=is_trial,
                tier=tier_val,  # type: ignore[arg-type]
                trial_end_date=trial_end_date,
                days_remaining=days_remaining,
                price_monthly=price_monthly,
                billing_date=trial_end_date,
            )
    except Exception:
        logger.warning(
            "bootstrap_trial_status_failed",
            clerk_id=current_user.sub,
            exc_info=True,
        )

    # ── 4. Subscription status for access gating ──────────────────────────
    sub_status = None
    sub_can_access = True
    if full_tenant is not None:
        sub_status = full_tenant.subscription_status.value
        sub_can_access = full_tenant.can_access

    return BootstrapResponse(
        user=me_response,
        features=features_response,
        trial_status=trial_status_response,
        tos_accepted_at=user.tos_accepted_at if user else None,
        tos_version_accepted=user.tos_version_accepted if user else None,
        subscription_status=sub_status,
        can_access=sub_can_access,
    )


# =============================================================================
# Terms of Service Endpoints
# =============================================================================


@router.get(
    "/tos-version",
    response_model=TosVersionResponse,
    summary="Get current ToS version",
    description="Returns the current Terms of Service version. Public endpoint.",
)
async def get_tos_version() -> TosVersionResponse:
    """Get the current ToS version."""
    from app.core.constants import TOS_CURRENT_VERSION, TOS_EFFECTIVE_DATE

    return TosVersionResponse(
        version=TOS_CURRENT_VERSION,
        effective_date=TOS_EFFECTIVE_DATE,
    )


@router.post(
    "/accept-terms",
    response_model=AcceptTermsResponse,
    summary="Accept Terms of Service",
    description="Record the user's acceptance of the current Terms of Service.",
)
async def accept_terms(
    request_body: AcceptTermsRequest,
    current_user: Annotated[ClerkTokenPayload, Depends(get_current_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    request: Request,
) -> AcceptTermsResponse:
    """Accept the Terms of Service.

    Args:
        request_body: Contains the ToS version being accepted.
        current_user: JWT claims from Clerk.
        auth_service: Auth service instance.
        request: FastAPI request for IP address.
    """
    # Get the base user from Clerk ID
    practice_user = await auth_service.get_current_user(current_user.sub)
    if practice_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    ip_address = request.client.host if request.client else None

    try:
        user = await auth_service.accept_terms(
            user_id=practice_user.user_id,
            version=request_body.version,
            ip_address=ip_address,
            tenant_id=practice_user.tenant_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return AcceptTermsResponse(
        tos_accepted_at=user.tos_accepted_at,
        tos_version_accepted=user.tos_version_accepted,
    )


# =============================================================================
# Session Management Endpoints
# =============================================================================


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Log out current session",
    description="""
    Log out the current session.

    If `all_devices` is true, logs out all sessions for this user.
    Actual session invalidation is handled by Clerk; this endpoint
    creates an audit log entry.
    """,
    responses={
        200: {"description": "Logged out successfully"},
        401: {"description": "Not authenticated"},
    },
)
async def logout(
    request: LogoutRequest | None = None,
    current_user: Annotated[ClerkTokenPayload, Depends(get_current_user)] = None,
    practice_user: Annotated[PracticeUser, Depends(get_practice_user)] = None,
    auth_service: Annotated[AuthService, Depends(get_auth_service)] = None,
) -> LogoutResponse:
    """Log out current session.

    Args:
        request: Logout request with options.
        current_user: JWT claims from Clerk.
        practice_user: Current practice user.
        auth_service: Auth service instance.

    Returns:
        Logout confirmation.
    """
    all_devices = request.all_devices if request else False

    await auth_service.handle_logout(
        practice_user_id=practice_user.id,
        logout_all=all_devices,
    )

    return LogoutResponse(
        message="Logged out successfully",
        all_devices=all_devices,
    )


@router.post(
    "/logout-all",
    response_model=LogoutResponse,
    summary="Log out all sessions",
    description="Log out all sessions for the current user on all devices.",
    responses={
        200: {"description": "All sessions logged out"},
        401: {"description": "Not authenticated"},
    },
)
async def logout_all(
    current_user: Annotated[ClerkTokenPayload, Depends(get_current_user)],
    practice_user: Annotated[PracticeUser, Depends(get_practice_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> LogoutResponse:
    """Log out all sessions.

    Args:
        current_user: JWT claims from Clerk.
        practice_user: Current practice user.
        auth_service: Auth service instance.

    Returns:
        Logout confirmation.
    """
    await auth_service.handle_logout(
        practice_user_id=practice_user.id,
        logout_all=True,
    )

    return LogoutResponse(
        message="Logged out from all devices",
        all_devices=True,
    )


# =============================================================================
# Sync Endpoint
# =============================================================================


@router.post(
    "/sync",
    response_model=PracticeUserResponse,
    summary="Sync user data from Clerk",
    description="""
    Synchronize local user data with Clerk.

    Updates:
    - MFA status
    - Last login timestamp

    This is called automatically on login but can be triggered manually.
    """,
    responses={
        200: {"description": "User synced successfully"},
        401: {"description": "Not authenticated"},
        404: {"description": "User not found"},
    },
)
async def sync_user(
    current_user: Annotated[ClerkTokenPayload, Depends(get_current_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> PracticeUserResponse:
    """Sync user data from Clerk.

    Args:
        current_user: JWT claims from Clerk.
        auth_service: Auth service instance.

    Returns:
        Updated practice user.
    """
    practice_user = await auth_service.sync_user_from_clerk(current_user.sub)
    if practice_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in database",
        )

    user = practice_user.user

    return PracticeUserResponse(
        id=practice_user.id,
        user_id=user.id,
        tenant_id=practice_user.tenant_id,
        clerk_id=practice_user.clerk_id,
        email=user.email,
        role=practice_user.role,
        is_active=user.is_active,
        mfa_enabled=practice_user.mfa_enabled,
        last_login_at=practice_user.last_login_at,
        created_at=practice_user.created_at,
        updated_at=practice_user.updated_at,
    )


# =============================================================================
# User Management Endpoints (Admin Only)
# =============================================================================


async def get_user_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.USER_READ))],
) -> UserService:
    """Get UserService instance with actor context.

    Args:
        session: Database session.
        current_user: Current authenticated user (for audit).

    Returns:
        Configured UserService.
    """
    return UserService(
        session=session,
        actor_id=current_user.user_id,
        actor_email=current_user.email,
        tenant_id=current_user.tenant_id,
    )


def _practice_user_to_response(practice_user: PracticeUser) -> PracticeUserResponse:
    """Convert PracticeUser model to response schema.

    Args:
        practice_user: Practice user with relationships loaded.

    Returns:
        PracticeUserResponse schema.
    """
    return PracticeUserResponse(
        id=practice_user.id,
        user_id=practice_user.user_id,
        tenant_id=practice_user.tenant_id,
        clerk_id=practice_user.clerk_id,
        email=practice_user.email,
        display_name=practice_user.display_name,
        role=practice_user.role,
        is_active=practice_user.user.is_active,
        mfa_enabled=practice_user.mfa_enabled,
        last_login_at=practice_user.last_login_at,
        created_at=practice_user.created_at,
        updated_at=practice_user.updated_at,
    )


@router.get(
    "/users",
    response_model=UserListResponse,
    summary="List users in tenant",
    description="""
    List all users in the current tenant.

    **Required Permission**: `user.read`

    By default, only active users are returned. Set `include_inactive=true`
    to include deactivated users.
    """,
    responses={
        200: {"description": "List of users"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
    },
)
async def list_users(
    include_inactive: bool = False,
    current_user: PracticeUser = Depends(require_permission(Permission.USER_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> UserListResponse:
    """List users in the tenant.

    Args:
        include_inactive: Whether to include deactivated users.
        current_user: Current authenticated user.
        session: Database session.

    Returns:
        List of practice users.
    """
    user_service = UserService(
        session=session,
        actor_id=current_user.user_id,
        actor_email=current_user.email,
        tenant_id=current_user.tenant_id,
    )

    users = await user_service.list_tenant_users(
        tenant_id=current_user.tenant_id,
        active_only=not include_inactive,
    )

    # Fix placeholder emails from Clerk dev environment
    from app.config import get_settings
    from app.modules.auth.clerk import ClerkClient

    clerk_client = ClerkClient(settings=get_settings().clerk)
    for u in users:
        if "@placeholder." in u.email:
            try:
                clerk_user = await clerk_client.get_user(u.clerk_id)
                real_email = clerk_user.primary_email
                if real_email and "@placeholder." not in real_email:
                    u.user.email = real_email
                    await session.flush()
            except Exception:
                pass

    user_responses = [_practice_user_to_response(u) for u in users]

    return UserListResponse(
        users=user_responses,
        total=len(user_responses),
    )


@router.get(
    "/users/{user_id}",
    response_model=PracticeUserResponse,
    summary="Get user by ID",
    description="""
    Get a specific user by their practice user ID.

    **Required Permission**: `user.read`
    """,
    responses={
        200: {"description": "User details"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "User not found"},
    },
)
async def get_user(
    user_id: uuid.UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.USER_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> PracticeUserResponse:
    """Get user by ID.

    Args:
        user_id: Practice user UUID.
        current_user: Current authenticated user.
        session: Database session.

    Returns:
        Practice user details.
    """
    user_service = UserService(
        session=session,
        actor_id=current_user.user_id,
        actor_email=current_user.email,
        tenant_id=current_user.tenant_id,
    )

    practice_user = await user_service.get_user(user_id)
    if practice_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Ensure user is in the same tenant
    if practice_user.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return _practice_user_to_response(practice_user)


@router.patch(
    "/users/{user_id}/role",
    response_model=PracticeUserResponse,
    summary="Update user role",
    description="""
    Change a user's role within the tenant.

    **Required Permission**: `user.write` (Admin only)

    Available roles:
    - `admin`: Full access to all operations
    - `accountant`: Full access to client/BAS operations
    - `staff`: Read-only access
    """,
    responses={
        200: {"description": "Role updated"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "User not found"},
    },
)
async def update_user_role(
    user_id: uuid.UUID,
    request: PracticeUserRoleUpdate,
    current_user: PracticeUser = Depends(require_permission(Permission.USER_WRITE)),
    session: AsyncSession = Depends(get_db_session),
) -> PracticeUserResponse:
    """Update a user's role.

    Args:
        user_id: Practice user UUID.
        request: Role update request.
        current_user: Current authenticated user.
        session: Database session.

    Returns:
        Updated practice user.
    """
    user_service = UserService(
        session=session,
        actor_id=current_user.user_id,
        actor_email=current_user.email,
        tenant_id=current_user.tenant_id,
    )

    try:
        practice_user = await user_service.update_role(
            practice_user_id=user_id,
            new_role=request.role,
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Ensure user is in the same tenant
    if practice_user.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return _practice_user_to_response(practice_user)


@router.post(
    "/users/{user_id}/deactivate",
    response_model=UserActionResponse,
    summary="Deactivate user",
    description="""
    Deactivate a user, preventing them from accessing the system.

    **Required Permission**: `user.write` (Admin only)

    A reason must be provided for audit purposes.
    Cannot deactivate the last admin in a tenant.
    """,
    responses={
        200: {"description": "User deactivated"},
        400: {"description": "Cannot deactivate (e.g., last admin)"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "User not found"},
    },
)
async def deactivate_user(
    user_id: uuid.UUID,
    request: PracticeUserDeactivate,
    current_user: PracticeUser = Depends(require_permission(Permission.USER_WRITE)),
    session: AsyncSession = Depends(get_db_session),
) -> UserActionResponse:
    """Deactivate a user.

    Args:
        user_id: Practice user UUID.
        request: Deactivation request with reason.
        current_user: Current authenticated user.
        session: Database session.

    Returns:
        Deactivation result.
    """
    user_service = UserService(
        session=session,
        actor_id=current_user.user_id,
        actor_email=current_user.email,
        tenant_id=current_user.tenant_id,
    )

    try:
        practice_user = await user_service.deactivate_user(
            practice_user_id=user_id,
            reason=request.reason,
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": e.message}},
        )

    # Ensure user is in the same tenant
    if practice_user.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserActionResponse(
        user=_practice_user_to_response(practice_user),
        message="User deactivated successfully",
    )


@router.post(
    "/users/{user_id}/activate",
    response_model=UserActionResponse,
    summary="Activate user",
    description="""
    Reactivate a previously deactivated user.

    **Required Permission**: `user.write` (Admin only)
    """,
    responses={
        200: {"description": "User activated"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "User not found"},
    },
)
async def activate_user(
    user_id: uuid.UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.USER_WRITE)),
    session: AsyncSession = Depends(get_db_session),
) -> UserActionResponse:
    """Activate a user.

    Args:
        user_id: Practice user UUID.
        current_user: Current authenticated user.
        session: Database session.

    Returns:
        Activation result.
    """
    user_service = UserService(
        session=session,
        actor_id=current_user.user_id,
        actor_email=current_user.email,
        tenant_id=current_user.tenant_id,
    )

    try:
        practice_user = await user_service.activate_user(
            practice_user_id=user_id,
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Ensure user is in the same tenant
    if practice_user.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserActionResponse(
        user=_practice_user_to_response(practice_user),
        message="User activated successfully",
    )


# =============================================================================
# Tenant Settings Endpoints (Admin Only)
# =============================================================================


@router.get(
    "/tenant/settings",
    response_model=TenantSettingsResponse,
    summary="Get tenant settings",
    description="""
    Get settings for the current tenant.

    **Required Permission**: `tenant.read`
    """,
    responses={
        200: {"description": "Tenant settings"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions or tenant suspended"},
    },
)
async def get_tenant_settings(
    current_user: PracticeUser = Depends(require_permission(Permission.TENANT_READ)),
    auth_service: AuthService = Depends(get_auth_service),
) -> TenantSettingsResponse:
    """Get tenant settings.

    Args:
        current_user: Current authenticated user.
        auth_service: Auth service instance.

    Returns:
        Tenant settings.
    """
    tenant = current_user.tenant

    # Check if tenant is suspended
    is_suspended = tenant.subscription_status.value == "suspended"

    return TenantSettingsResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        mfa_required=tenant.mfa_required,
        subscription_status=tenant.subscription_status,
        settings=tenant.settings or {},
        is_active=tenant.is_active,
        is_suspended=is_suspended,
    )


@router.patch(
    "/tenant/settings",
    response_model=TenantSettingsResponse,
    summary="Update tenant settings",
    description="""
    Update settings for the current tenant.

    **Required Permission**: `tenant.write` (Admin only)

    Settings that can be updated:
    - `name`: Practice name
    - `mfa_required`: Require MFA for all users
    - `settings`: Custom configuration
    """,
    responses={
        200: {"description": "Settings updated"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions or tenant suspended"},
    },
)
async def update_tenant_settings(
    request: TenantUpdate,
    current_user: PracticeUser = Depends(require_permission(Permission.TENANT_WRITE)),
    auth_service: AuthService = Depends(get_auth_service),
) -> TenantSettingsResponse:
    """Update tenant settings.

    Args:
        request: Settings update request.
        current_user: Current authenticated user.
        auth_service: Auth service instance.

    Returns:
        Updated tenant settings.
    """
    tenant = current_user.tenant

    # Check if tenant is suspended
    if tenant.subscription_status.value == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant is suspended. Please contact support.",
        )

    # Update via service (includes audit logging)
    updated_tenant = await auth_service.update_tenant_settings(
        tenant_id=tenant.id,
        update_data=request,
        actor_id=current_user.user_id,
        actor_email=current_user.email,
    )

    is_suspended = updated_tenant.subscription_status.value == "suspended"

    return TenantSettingsResponse(
        id=updated_tenant.id,
        name=updated_tenant.name,
        slug=updated_tenant.slug,
        mfa_required=updated_tenant.mfa_required,
        subscription_status=updated_tenant.subscription_status,
        settings=updated_tenant.settings or {},
        is_active=updated_tenant.is_active,
        is_suspended=is_suspended,
    )


# =============================================================================
# Invitation Management Endpoints (Admin Only)
# =============================================================================


def _invitation_to_response(invitation) -> InvitationResponse:
    """Convert Invitation model to response schema.

    Args:
        invitation: Invitation model.

    Returns:
        InvitationResponse schema.
    """
    from .models import InvitationStatus

    # Determine status based on state
    if invitation.accepted_at is not None:
        status_val = InvitationStatus.ACCEPTED
    elif invitation.revoked_at is not None:
        status_val = InvitationStatus.REVOKED
    elif invitation.expires_at < __import__("datetime").datetime.now(__import__("datetime").UTC):
        status_val = InvitationStatus.EXPIRED
    else:
        status_val = InvitationStatus.PENDING

    return InvitationResponse(
        id=invitation.id,
        tenant_id=invitation.tenant_id,
        invited_by=invitation.invited_by,
        email=invitation.email,
        role=invitation.role,
        token=invitation.token,
        status=status_val,
        expires_at=invitation.expires_at,
        accepted_at=invitation.accepted_at,
        created_at=invitation.created_at,
        inviter=None,  # Not loaded by default
    )


@router.post(
    "/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an invitation",
    description="""
    Create an invitation to invite a new user to the tenant.

    **Required Permission**: `user.write` (Admin only)

    The invitation will be sent to the specified email address.
    It expires in 7 days by default.
    """,
    responses={
        201: {"description": "Invitation created"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Email already invited or registered"},
    },
)
async def create_invitation(
    request: InvitationCreate,
    current_user: PracticeUser = Depends(require_permission(Permission.USER_WRITE)),
    session: AsyncSession = Depends(get_db_session),
) -> InvitationResponse:
    """Create an invitation.

    Args:
        request: Invitation creation request.
        current_user: Current authenticated user.
        session: Database session.

    Returns:
        Created invitation.
    """
    invitation_service = InvitationService(
        session=session,
        actor_id=current_user.user_id,
        actor_email=current_user.email,
    )

    try:
        invitation = await invitation_service.create_invitation(
            tenant_id=current_user.tenant_id,
            invited_by=current_user.id,
            email=request.email,
            role=request.role,
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": e.code, "message": e.message}},
        )

    return _invitation_to_response(invitation)


@router.get(
    "/invitations",
    response_model=InvitationListResponse,
    summary="List invitations",
    description="""
    List all invitations for the current tenant.

    **Required Permission**: `user.read`

    Set `pending_only=true` to show only pending invitations.
    """,
    responses={
        200: {"description": "List of invitations"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
    },
)
async def list_invitations(
    pending_only: bool = False,
    current_user: PracticeUser = Depends(require_permission(Permission.USER_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> InvitationListResponse:
    """List invitations.

    Args:
        pending_only: Whether to show only pending invitations.
        current_user: Current authenticated user.
        session: Database session.

    Returns:
        List of invitations.
    """
    invitation_service = InvitationService(
        session=session,
        actor_id=current_user.user_id,
        actor_email=current_user.email,
    )

    invitations = await invitation_service.list_all(
        tenant_id=current_user.tenant_id,
        pending_only=pending_only,
    )

    invitation_responses = [_invitation_to_response(inv) for inv in invitations]

    return InvitationListResponse(
        invitations=invitation_responses,
        total=len(invitation_responses),
    )


@router.get(
    "/invitations/{invitation_id}",
    response_model=InvitationResponse,
    summary="Get invitation by ID",
    description="""
    Get a specific invitation by ID.

    **Required Permission**: `user.read`
    """,
    responses={
        200: {"description": "Invitation details"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Invitation not found"},
    },
)
async def get_invitation(
    invitation_id: uuid.UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.USER_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> InvitationResponse:
    """Get invitation by ID.

    Args:
        invitation_id: Invitation UUID.
        current_user: Current authenticated user.
        session: Database session.

    Returns:
        Invitation details.
    """
    invitation_service = InvitationService(
        session=session,
        actor_id=current_user.user_id,
        actor_email=current_user.email,
    )

    invitation = await invitation_service.invitation_repo.get_by_id(invitation_id)
    if invitation is None or invitation.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    return _invitation_to_response(invitation)


@router.post(
    "/invitations/{invitation_id}/revoke",
    response_model=InvitationResponse,
    summary="Revoke invitation",
    description="""
    Revoke a pending invitation, preventing it from being used.

    **Required Permission**: `user.write` (Admin only)
    """,
    responses={
        200: {"description": "Invitation revoked"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Invitation not found"},
    },
)
async def revoke_invitation(
    invitation_id: uuid.UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.USER_WRITE)),
    session: AsyncSession = Depends(get_db_session),
) -> InvitationResponse:
    """Revoke an invitation.

    Args:
        invitation_id: Invitation UUID.
        current_user: Current authenticated user.
        session: Database session.

    Returns:
        Revoked invitation.
    """
    invitation_service = InvitationService(
        session=session,
        actor_id=current_user.user_id,
        actor_email=current_user.email,
    )

    revoked = await invitation_service.revoke(
        invitation_id=invitation_id,
        tenant_id=current_user.tenant_id,
    )

    if revoked is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    return _invitation_to_response(revoked)


@router.get(
    "/invitations/token/{token}",
    response_model=InvitationPublic,
    summary="Get invitation by token (public)",
    description="""
    Get public information about an invitation by its token.

    This endpoint is public (no authentication required) and is used
    to display invitation details before the user signs up.
    """,
    responses={
        200: {"description": "Invitation details"},
        404: {"description": "Invitation not found or expired"},
    },
)
async def get_invitation_by_token(
    token: str,
    session: AsyncSession = Depends(get_db_session),
) -> InvitationPublic:
    """Get invitation by token (public endpoint).

    Args:
        token: Invitation token.
        session: Database session.

    Returns:
        Public invitation details.
    """
    from .models import InvitationStatus

    invitation_service = InvitationService(session=session)
    invitation = await invitation_service.get_valid_invitation(token)

    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found or expired",
        )

    return InvitationPublic(
        email=invitation.email,
        role=invitation.role,
        status=InvitationStatus.PENDING,
        expires_at=invitation.expires_at,
        tenant_name=invitation.tenant.name if invitation.tenant else "Unknown",
    )


# =============================================================================
# Webhook Endpoints
# =============================================================================


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Clerk webhook receiver",
    description="""
    Receives webhook events from Clerk for user and session lifecycle management.

    **No JWT authentication required** - signature verification is used instead.

    Supported events:
    - `user.created`: Sync new user metadata
    - `user.updated`: Sync user changes (including MFA status)
    - `user.deleted`: Deactivate user
    - `session.created`: Log login event
    - `session.ended`: Log logout event
    """,
    responses={
        200: {"description": "Webhook processed successfully"},
        401: {"description": "Invalid webhook signature"},
        500: {"description": "Processing error"},
    },
    include_in_schema=False,  # Don't show in public OpenAPI docs
)
async def clerk_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Handle Clerk webhook events.

    Args:
        request: FastAPI request object.
        session: Database session.

    Returns:
        Processing result.
    """
    from app.config import get_settings

    from .webhooks import ClerkWebhookHandler, WebhookEvent, verify_webhook_signature

    settings = get_settings()

    # Get raw body for signature verification
    body = await request.body()
    body_str = body.decode("utf-8")

    # Get headers for signature verification
    headers = {
        "svix-id": request.headers.get("svix-id"),
        "svix-timestamp": request.headers.get("svix-timestamp"),
        "svix-signature": request.headers.get("svix-signature"),
    }

    # Verify webhook signature
    webhook_secret = settings.clerk.webhook_secret.get_secret_value()

    if not verify_webhook_signature(
        body=body_str,
        headers=headers,
        secret=webhook_secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # Parse the event
    try:
        import json

        payload = json.loads(body_str)
        event = WebhookEvent(**payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook payload: {e!s}",
        )

    # Process the event
    handler = ClerkWebhookHandler(session=session)
    result = await handler.handle_event(event)

    return {"received": True, "event_type": event.type, "result": result}


# =============================================================================
# Health Check Endpoint
# =============================================================================


@router.get(
    "/health",
    summary="Auth module health check",
    description="Returns health status of the auth module.",
    responses={
        200: {"description": "Auth module is healthy"},
    },
)
async def auth_health() -> dict:
    """Health check for auth module.

    Returns:
        Health status.
    """
    from app.config import get_settings

    settings = get_settings()

    return {
        "status": "healthy",
        "module": "auth",
        "clerk_configured": bool(
            settings.clerk.publishable_key
            and settings.clerk.publishable_key != "pk_test_placeholder"
        ),
    }
