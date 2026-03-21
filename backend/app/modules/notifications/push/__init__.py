"""Push notification module for PWA support.

Spec: 032-pwa-mobile-document-capture

This module provides:
- Web Push subscription management
- Push notification delivery via Web Push API
- WebAuthn credential storage for biometric auth
- PWA installation analytics
"""

from .models import (
    NotificationType,
    PushNotificationLog,
    PushSubscription,
    PWAEventType,
    PWAInstallationEvent,
    WebAuthnCredential,
)
from .repository import (
    PushNotificationLogRepository,
    PushSubscriptionRepository,
    PWAInstallationEventRepository,
    WebAuthnCredentialRepository,
)
from .router import admin_router, router
from .service import (
    PushSubscriptionService,
    PWAAnalyticsService,
)

__all__ = [
    # Models
    "PushSubscription",
    "WebAuthnCredential",
    "PushNotificationLog",
    "PWAInstallationEvent",
    "NotificationType",
    "PWAEventType",
    # Repositories
    "PushSubscriptionRepository",
    "PushNotificationLogRepository",
    "WebAuthnCredentialRepository",
    "PWAInstallationEventRepository",
    # Services
    "PushSubscriptionService",
    "PWAAnalyticsService",
    # Routers
    "router",
    "admin_router",
]
