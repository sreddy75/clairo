"""Pydantic schemas for push notifications.

Spec: 032-pwa-mobile-document-capture
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.notifications.push.models import NotificationType, PWAEventType

# =============================================================================
# Push Subscription Schemas
# =============================================================================


class PushSubscriptionKeys(BaseModel):
    """Web Push subscription keys."""

    p256dh: str = Field(..., description="P-256 Diffie-Hellman public key")
    auth: str = Field(..., description="Authentication secret")


class PushSubscriptionCreate(BaseModel):
    """Schema for creating a push subscription."""

    endpoint: str = Field(..., description="Push service endpoint URL")
    keys: PushSubscriptionKeys
    device_name: str | None = Field(None, max_length=255)
    user_agent: str | None = None


class PushSubscriptionResponse(BaseModel):
    """Schema for push subscription response."""

    id: UUID
    endpoint: str
    device_name: str | None
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None

    model_config = {"from_attributes": True}


class PushSubscriptionList(BaseModel):
    """List of push subscriptions."""

    subscriptions: list[PushSubscriptionResponse]
    count: int


# =============================================================================
# VAPID Key Schemas
# =============================================================================


class VAPIDPublicKeyResponse(BaseModel):
    """Response containing VAPID public key for client subscription."""

    public_key: str = Field(
        ..., description="Base64-encoded VAPID public key for PushManager.subscribe()"
    )


# =============================================================================
# Push Notification Schemas
# =============================================================================


class PushNotificationPayload(BaseModel):
    """Payload for sending a push notification."""

    notification_type: NotificationType
    title: str = Field(..., max_length=255)
    body: str = Field(..., max_length=500)
    icon: str | None = Field(None, description="URL to notification icon")
    badge: str | None = Field(None, description="URL to badge icon")
    data: dict[str, Any] = Field(default_factory=dict, description="Custom data for click handling")
    url: str | None = Field(None, description="URL to open on click")
    tag: str | None = Field(None, description="Tag for notification replacement/grouping")
    require_interaction: bool = Field(
        False, description="Whether notification requires user interaction"
    )


class PushNotificationSend(BaseModel):
    """Schema for sending a push notification to a client."""

    client_id: UUID
    payload: PushNotificationPayload


class PushNotificationBroadcast(BaseModel):
    """Schema for broadcasting a push notification to multiple clients."""

    client_ids: list[UUID]
    payload: PushNotificationPayload


class PushNotificationLogResponse(BaseModel):
    """Response for a push notification log entry."""

    id: UUID
    subscription_id: UUID
    notification_type: str
    title: str
    body: str
    sent_at: datetime
    delivered_at: datetime | None
    clicked_at: datetime | None
    error_message: str | None

    model_config = {"from_attributes": True}


class PushDeliveryStats(BaseModel):
    """Push notification delivery statistics."""

    total: int
    delivered: int
    clicked: int
    failed: int
    delivery_rate: float = Field(..., description="Percentage of notifications delivered")
    click_rate: float = Field(..., description="Percentage of delivered notifications clicked")


# =============================================================================
# Notification Click Tracking
# =============================================================================


class NotificationClickedRequest(BaseModel):
    """Request to track notification click."""

    notification_id: UUID


# =============================================================================
# PWA Installation Event Schemas
# =============================================================================


class PWAEventCreate(BaseModel):
    """Schema for creating a PWA installation event."""

    event_type: PWAEventType
    platform: str | None = Field(None, max_length=50)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PWAEventResponse(BaseModel):
    """Response for a PWA installation event."""

    id: UUID
    event_type: str
    platform: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PWAAdoptionStats(BaseModel):
    """PWA adoption statistics for a tenant."""

    prompts_shown: int
    prompts_accepted: int
    prompts_dismissed: int
    apps_installed: int
    push_enabled: int
    push_denied: int
    biometric_registered: int
    install_rate: float = Field(..., description="Percentage of prompts that led to install")
    push_opt_in_rate: float = Field(..., description="Percentage of installs that enabled push")


# =============================================================================
# WebAuthn Schemas (for biometric auth)
# =============================================================================


class WebAuthnRegistrationOptions(BaseModel):
    """Options for WebAuthn credential registration."""

    challenge: str = Field(..., description="Base64-encoded challenge")
    rp: dict[str, str] = Field(..., description="Relying party info")
    user: dict[str, str] = Field(..., description="User info")
    pub_key_cred_params: list[dict[str, Any]] = Field(
        ..., description="Supported credential parameters"
    )
    timeout: int = Field(60000, description="Timeout in milliseconds")
    authenticator_selection: dict[str, Any] = Field(
        default_factory=dict, description="Authenticator requirements"
    )
    attestation: str = Field("none", description="Attestation preference")


class WebAuthnRegistrationResponse(BaseModel):
    """Response from WebAuthn credential registration."""

    id: str = Field(..., description="Base64url-encoded credential ID")
    raw_id: str = Field(..., description="Base64url-encoded raw credential ID")
    type: str = Field("public-key")
    response: dict[str, str] = Field(
        ..., description="Authenticator response with clientDataJSON and attestationObject"
    )


class WebAuthnCredentialResponse(BaseModel):
    """Response for a WebAuthn credential."""

    id: UUID
    device_name: str | None
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None

    model_config = {"from_attributes": True}


class WebAuthnAuthenticationOptions(BaseModel):
    """Options for WebAuthn authentication."""

    challenge: str = Field(..., description="Base64-encoded challenge")
    timeout: int = Field(60000, description="Timeout in milliseconds")
    rp_id: str = Field(..., description="Relying party ID")
    allow_credentials: list[dict[str, Any]] = Field(
        ..., description="Allowed credential descriptors"
    )
    user_verification: str = Field("preferred", description="User verification requirement")


class WebAuthnAuthenticationResponse(BaseModel):
    """Response from WebAuthn authentication."""

    id: str = Field(..., description="Base64url-encoded credential ID")
    raw_id: str = Field(..., description="Base64url-encoded raw credential ID")
    type: str = Field("public-key")
    response: dict[str, str] = Field(
        ...,
        description="Authenticator response with clientDataJSON, authenticatorData, signature",
    )
