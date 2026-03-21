"""Push notification API endpoints.

Provides endpoints for:
- VAPID public key retrieval
- Push subscription management
- Notification click tracking
- PWA analytics events

Spec: 032-pwa-mobile-document-capture
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.notifications.push.schemas import (
    NotificationClickedRequest,
    PushSubscriptionCreate,
    PushSubscriptionList,
    PushSubscriptionResponse,
    PWAAdoptionStats,
    PWAEventCreate,
    PWAEventResponse,
    VAPIDPublicKeyResponse,
    WebAuthnAuthenticationOptions,
    WebAuthnAuthenticationResponse,
    WebAuthnCredentialResponse,
    WebAuthnRegistrationOptions,
    WebAuthnRegistrationResponse,
)
from app.modules.notifications.push.service import (
    PushSubscriptionService,
    PWAAnalyticsService,
)
from app.modules.notifications.push.webauthn_service import WebAuthnService
from app.modules.portal.dependencies import get_current_portal_session

router = APIRouter(prefix="/portal/push", tags=["Portal Push Notifications"])


# =============================================================================
# VAPID Key Endpoint
# =============================================================================


@router.get(
    "/vapid-key",
    response_model=VAPIDPublicKeyResponse,
    summary="Get VAPID public key",
    description="Get the VAPID public key needed for PushManager.subscribe()",
)
async def get_vapid_key(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VAPIDPublicKeyResponse:
    """Get VAPID public key for push subscription."""
    service = PushSubscriptionService(db)
    public_key = await service.get_vapid_public_key()

    if not public_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Push notifications not configured",
        )

    return VAPIDPublicKeyResponse(public_key=public_key)


# =============================================================================
# Push Subscription Endpoints
# =============================================================================


@router.post(
    "/subscribe",
    response_model=PushSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subscribe to push notifications",
    description="Register a push subscription for the current client session",
)
async def subscribe(
    subscription_data: PushSubscriptionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    session: Annotated[dict, Depends(get_current_portal_session)],
    user_agent: Annotated[str | None, Header(alias="User-Agent")] = None,
) -> PushSubscriptionResponse:
    """Subscribe to push notifications."""
    service = PushSubscriptionService(db)

    # Add user agent from header if not provided
    if not subscription_data.user_agent and user_agent:
        subscription_data.user_agent = user_agent

    subscription = await service.subscribe(
        client_id=session["connection_id"],
        tenant_id=session["tenant_id"],
        subscription_data=subscription_data,
    )

    await db.commit()
    return PushSubscriptionResponse.model_validate(subscription)


@router.delete(
    "/unsubscribe",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unsubscribe from push notifications",
    description="Remove a push subscription by endpoint URL",
)
async def unsubscribe(
    endpoint: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    session: Annotated[dict, Depends(get_current_portal_session)],
) -> None:
    """Unsubscribe from push notifications."""
    service = PushSubscriptionService(db)
    found = await service.unsubscribe(endpoint)

    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    await db.commit()


@router.get(
    "/subscriptions",
    response_model=PushSubscriptionList,
    summary="List push subscriptions",
    description="List all active push subscriptions for the current client",
)
async def list_subscriptions(
    db: Annotated[AsyncSession, Depends(get_db)],
    session: Annotated[dict, Depends(get_current_portal_session)],
) -> PushSubscriptionList:
    """List all active push subscriptions for the client."""
    service = PushSubscriptionService(db)
    subscriptions = await service.list_subscriptions(session["connection_id"])

    return PushSubscriptionList(
        subscriptions=[PushSubscriptionResponse.model_validate(s) for s in subscriptions],
        count=len(subscriptions),
    )


@router.delete(
    "/subscriptions/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a push subscription",
    description="Remove a specific push subscription by ID",
)
async def delete_subscription(
    subscription_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    session: Annotated[dict, Depends(get_current_portal_session)],
) -> None:
    """Delete a specific push subscription."""
    service = PushSubscriptionService(db)
    found = await service.unsubscribe_by_id(subscription_id)

    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    await db.commit()


# =============================================================================
# Notification Click Tracking
# =============================================================================


@router.post(
    "/clicked",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Track notification click",
    description="Track when a user clicks on a push notification",
)
async def notification_clicked(
    request: NotificationClickedRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Track a notification click event.

    This endpoint doesn't require authentication since it's called from
    the service worker which may not have session context.
    """
    service = PushSubscriptionService(db)
    await service.mark_notification_clicked(request.notification_id)
    await db.commit()


# =============================================================================
# PWA Analytics Events
# =============================================================================


@router.post(
    "/events",
    response_model=PWAEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log PWA event",
    description="Log a PWA installation or permission event for analytics",
)
async def log_pwa_event(
    event_data: PWAEventCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    session: Annotated[dict, Depends(get_current_portal_session)],
    user_agent: Annotated[str | None, Header(alias="User-Agent")] = None,
) -> PWAEventResponse:
    """Log a PWA event for analytics."""
    service = PWAAnalyticsService(db)

    event = await service.log_event(
        tenant_id=session["tenant_id"],
        event_data=event_data,
        client_id=session["connection_id"],
        user_agent=user_agent,
    )

    await db.commit()
    return PWAEventResponse.model_validate(event)


# =============================================================================
# Admin Analytics Endpoints (for accountant dashboard)
# =============================================================================

admin_router = APIRouter(prefix="/push", tags=["Push Notifications Admin"])


@admin_router.get(
    "/adoption-stats",
    response_model=PWAAdoptionStats,
    summary="Get PWA adoption stats",
    description="Get PWA adoption statistics for the tenant",
)
async def get_adoption_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: UUID,  # This should come from auth in real implementation
) -> PWAAdoptionStats:
    """Get PWA adoption statistics for admin dashboard."""
    service = PWAAnalyticsService(db)
    stats = await service.get_adoption_stats(tenant_id)
    return PWAAdoptionStats(**stats)


# =============================================================================
# WebAuthn Endpoints (Biometric Authentication)
# =============================================================================


class WebAuthnRegisterRequest(BaseModel):
    """Request to complete WebAuthn registration."""

    credential: WebAuthnRegistrationResponse
    device_name: str | None = None


class WebAuthnAuthenticateRequest(BaseModel):
    """Request to complete WebAuthn authentication."""

    credential: WebAuthnAuthenticationResponse


class WebAuthnCredentialList(BaseModel):
    """List of WebAuthn credentials."""

    credentials: list[WebAuthnCredentialResponse]
    count: int


class BiometricStatusResponse(BaseModel):
    """Response for biometric status check."""

    has_credentials: bool
    credential_count: int


# Import BaseModel at the top if not already imported


@router.get(
    "/webauthn/status",
    response_model=BiometricStatusResponse,
    summary="Check biometric status",
    description="Check if the client has registered biometric credentials",
)
async def check_biometric_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    session: Annotated[dict, Depends(get_current_portal_session)],
) -> BiometricStatusResponse:
    """Check if client has biometric credentials."""
    service = WebAuthnService(db)
    credentials = await service.list_credentials(session["connection_id"])

    return BiometricStatusResponse(
        has_credentials=len(credentials) > 0,
        credential_count=len(credentials),
    )


@router.post(
    "/webauthn/register/options",
    response_model=WebAuthnRegistrationOptions,
    summary="Get registration options",
    description="Get WebAuthn options for credential registration",
)
async def get_registration_options(
    db: Annotated[AsyncSession, Depends(get_db)],
    session: Annotated[dict, Depends(get_current_portal_session)],
) -> WebAuthnRegistrationOptions:
    """Get WebAuthn registration options for navigator.credentials.create()."""
    service = WebAuthnService(db)

    # Use email from session as user name
    user_name = session.get("primary_contact_email", "user@example.com")
    display_name = session.get("organisation_name", user_name)

    options = await service.get_registration_options(
        client_id=session["connection_id"],
        tenant_id=session["tenant_id"],
        user_name=user_name,
        user_display_name=display_name,
    )

    return WebAuthnRegistrationOptions(**options)


@router.post(
    "/webauthn/register/verify",
    response_model=WebAuthnCredentialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Complete registration",
    description="Verify and store WebAuthn credential from registration",
)
async def verify_registration(
    request: WebAuthnRegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    session: Annotated[dict, Depends(get_current_portal_session)],
) -> WebAuthnCredentialResponse:
    """Verify and store WebAuthn registration response."""
    service = WebAuthnService(db)

    try:
        credential = await service.verify_registration(
            client_id=session["connection_id"],
            tenant_id=session["tenant_id"],
            credential_response=request.credential.model_dump(),
            device_name=request.device_name,
        )
        await db.commit()
        return WebAuthnCredentialResponse.model_validate(credential)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/webauthn/authenticate/options",
    response_model=WebAuthnAuthenticationOptions,
    summary="Get authentication options",
    description="Get WebAuthn options for authentication",
)
async def get_authentication_options(
    db: Annotated[AsyncSession, Depends(get_db)],
    session: Annotated[dict, Depends(get_current_portal_session)],
) -> WebAuthnAuthenticationOptions:
    """Get WebAuthn authentication options for navigator.credentials.get()."""
    service = WebAuthnService(db)

    try:
        options = await service.get_authentication_options(
            client_id=session["connection_id"],
        )
        return WebAuthnAuthenticationOptions(**options)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/webauthn/authenticate/verify",
    status_code=status.HTTP_200_OK,
    summary="Verify authentication",
    description="Verify WebAuthn authentication assertion",
)
async def verify_authentication(
    request: WebAuthnAuthenticateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    session: Annotated[dict, Depends(get_current_portal_session)],
) -> dict[str, bool]:
    """Verify WebAuthn authentication response."""
    service = WebAuthnService(db)

    try:
        await service.verify_authentication(
            client_id=session["connection_id"],
            assertion_response=request.credential.model_dump(),
        )
        await db.commit()
        return {"authenticated": True}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.get(
    "/webauthn/credentials",
    response_model=WebAuthnCredentialList,
    summary="List credentials",
    description="List all WebAuthn credentials for the current client",
)
async def list_credentials(
    db: Annotated[AsyncSession, Depends(get_db)],
    session: Annotated[dict, Depends(get_current_portal_session)],
) -> WebAuthnCredentialList:
    """List all WebAuthn credentials for the client."""
    service = WebAuthnService(db)
    credentials = await service.list_credentials(session["connection_id"])

    return WebAuthnCredentialList(
        credentials=[WebAuthnCredentialResponse.model_validate(c) for c in credentials],
        count=len(credentials),
    )


@router.delete(
    "/webauthn/credentials/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete credential",
    description="Delete a WebAuthn credential",
)
async def delete_credential(
    credential_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    session: Annotated[dict, Depends(get_current_portal_session)],
) -> None:
    """Delete a WebAuthn credential."""
    service = WebAuthnService(db)
    found = await service.revoke_credential(
        client_id=session["connection_id"],
        credential_id=credential_id,
    )

    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found",
        )

    await db.commit()
