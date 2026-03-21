"""Push notification service.

Handles:
- Push subscription management
- Sending push notifications via Web Push API
- Notification delivery tracking
- PWA analytics events

Spec: 032-pwa-mobile-document-capture
"""

import json
import logging
import os
from typing import Any
from uuid import UUID

from pywebpush import WebPushException, webpush
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.push.models import (
    PushNotificationLog,
    PushSubscription,
    PWAEventType,
    PWAInstallationEvent,
)
from app.modules.notifications.push.repository import (
    PushNotificationLogRepository,
    PushSubscriptionRepository,
    PWAInstallationEventRepository,
)
from app.modules.notifications.push.schemas import (
    PushNotificationPayload,
    PushSubscriptionCreate,
    PWAEventCreate,
)

logger = logging.getLogger(__name__)


# =============================================================================
# VAPID Configuration
# =============================================================================


def get_vapid_keys() -> tuple[str, str]:
    """Get VAPID keys from environment.

    Returns:
        Tuple of (private_key, public_key) both base64-encoded.
    """
    private_key = os.getenv("VAPID_PRIVATE_KEY")
    public_key = os.getenv("VAPID_PUBLIC_KEY")

    if not private_key or not public_key:
        logger.warning(
            "VAPID keys not configured. Push notifications will not work. "
            "Generate keys with: npx web-push generate-vapid-keys"
        )
        return "", ""

    return private_key, public_key


def get_vapid_claims() -> dict[str, str]:
    """Get VAPID claims for push subscription."""
    return {"sub": f"mailto:{os.getenv('VAPID_CONTACT_EMAIL', 'support@clairo.com.au')}"}


# =============================================================================
# Push Subscription Service
# =============================================================================


class PushSubscriptionService:
    """Service for managing push subscriptions."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize service with database session."""
        self.session = session
        self.subscription_repo = PushSubscriptionRepository(session)
        self.log_repo = PushNotificationLogRepository(session)
        self.event_repo = PWAInstallationEventRepository(session)

    async def get_vapid_public_key(self) -> str:
        """Get the VAPID public key for client subscription."""
        _, public_key = get_vapid_keys()
        return public_key

    async def subscribe(
        self,
        client_id: UUID,
        tenant_id: UUID,
        subscription_data: PushSubscriptionCreate,
    ) -> PushSubscription:
        """Create or update a push subscription.

        If the endpoint already exists, updates the keys.
        Otherwise creates a new subscription.
        """
        # Check if subscription with this endpoint exists
        existing = await self.subscription_repo.get_by_endpoint(subscription_data.endpoint)

        if existing:
            # Update existing subscription
            await self.subscription_repo.update(
                existing.id,
                {
                    "p256dh_key": subscription_data.keys.p256dh,
                    "auth_key": subscription_data.keys.auth,
                    "device_name": subscription_data.device_name,
                    "user_agent": subscription_data.user_agent,
                    "is_active": True,
                },
            )
            await self.subscription_repo.update_last_used(existing.id)
            return existing

        # Create new subscription
        subscription = PushSubscription(
            client_id=client_id,
            tenant_id=tenant_id,
            endpoint=subscription_data.endpoint,
            p256dh_key=subscription_data.keys.p256dh,
            auth_key=subscription_data.keys.auth,
            device_name=subscription_data.device_name,
            user_agent=subscription_data.user_agent,
        )
        subscription = await self.subscription_repo.create(subscription)

        # Log the event
        await self._log_pwa_event(
            client_id=client_id,
            tenant_id=tenant_id,
            event_type=PWAEventType.PUSH_PERMISSION_GRANTED,
            user_agent=subscription_data.user_agent,
        )

        return subscription

    async def unsubscribe(self, endpoint: str) -> bool:
        """Unsubscribe a push subscription by endpoint."""
        return await self.subscription_repo.deactivate_by_endpoint(endpoint)

    async def unsubscribe_by_id(self, subscription_id: UUID) -> bool:
        """Unsubscribe a push subscription by ID."""
        return await self.subscription_repo.deactivate(subscription_id)

    async def list_subscriptions(self, client_id: UUID) -> list[PushSubscription]:
        """List all active subscriptions for a client."""
        return await self.subscription_repo.get_active_by_client(client_id)

    async def send_notification(
        self,
        client_id: UUID,
        payload: PushNotificationPayload,
    ) -> list[UUID]:
        """Send a push notification to all subscriptions for a client.

        Returns list of log IDs for tracking.
        """
        subscriptions = await self.subscription_repo.get_active_by_client(client_id)

        if not subscriptions:
            logger.debug(f"No active push subscriptions for client {client_id}")
            return []

        log_ids = []
        for subscription in subscriptions:
            log_id = await self._send_to_subscription(subscription, payload)
            if log_id:
                log_ids.append(log_id)

        return log_ids

    async def broadcast_notification(
        self,
        client_ids: list[UUID],
        payload: PushNotificationPayload,
    ) -> dict[UUID, list[UUID]]:
        """Send a push notification to multiple clients.

        Returns dict mapping client_id to list of log IDs.
        """
        results: dict[UUID, list[UUID]] = {}

        for client_id in client_ids:
            log_ids = await self.send_notification(client_id, payload)
            if log_ids:
                results[client_id] = log_ids

        return results

    async def _send_to_subscription(
        self,
        subscription: PushSubscription,
        payload: PushNotificationPayload,
    ) -> UUID | None:
        """Send a push notification to a specific subscription.

        Returns the log ID if sent successfully.
        """
        private_key, public_key = get_vapid_keys()

        if not private_key or not public_key:
            logger.error("VAPID keys not configured, cannot send push notification")
            return None

        # Create notification payload
        notification_data = {
            "title": payload.title,
            "body": payload.body,
            "icon": payload.icon or "/icons/icon.svg",
            "badge": payload.badge or "/icons/badge.png",
            "data": {
                **payload.data,
                "url": payload.url or "/portal",
                "notificationId": None,  # Will be set after log creation
            },
            "tag": payload.tag,
            "requireInteraction": payload.require_interaction,
        }

        # Create log entry
        log = PushNotificationLog(
            subscription_id=subscription.id,
            notification_type=payload.notification_type.value,
            title=payload.title,
            body=payload.body,
            data=payload.data,
        )
        log = await self.log_repo.create(log)

        # Add log ID to notification data for click tracking
        notification_data["data"]["notificationId"] = str(log.id)

        # Prepare subscription info for webpush
        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh_key,
                "auth": subscription.auth_key,
            },
        }

        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(notification_data),
                vapid_private_key=private_key,
                vapid_claims=get_vapid_claims(),
            )

            # Mark as delivered
            await self.log_repo.mark_delivered(log.id)
            await self.subscription_repo.update_last_used(subscription.id)

            logger.info(
                f"Push notification sent to subscription {subscription.id}",
                extra={
                    "subscription_id": str(subscription.id),
                    "notification_type": payload.notification_type.value,
                },
            )

            return log.id

        except WebPushException as e:
            error_msg = str(e)
            logger.error(
                f"Failed to send push notification: {error_msg}",
                extra={"subscription_id": str(subscription.id)},
            )

            # Mark as failed
            await self.log_repo.mark_failed(log.id, error_msg)

            # If subscription is invalid (410 Gone), deactivate it
            if e.response is not None and e.response.status_code in (404, 410):
                await self.subscription_repo.deactivate(subscription.id)
                logger.info(f"Deactivated invalid subscription {subscription.id}")

            return log.id

        except Exception as e:
            error_msg = str(e)
            logger.exception(f"Unexpected error sending push notification: {error_msg}")
            await self.log_repo.mark_failed(log.id, error_msg)
            return log.id

    async def mark_notification_clicked(self, log_id: UUID) -> None:
        """Mark a notification as clicked."""
        await self.log_repo.mark_clicked(log_id)

    async def _log_pwa_event(
        self,
        client_id: UUID | None,
        tenant_id: UUID,
        event_type: PWAEventType,
        user_agent: str | None = None,
        platform: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PWAInstallationEvent:
        """Log a PWA installation/permission event."""
        event = PWAInstallationEvent(
            client_id=client_id,
            tenant_id=tenant_id,
            event_type=event_type.value,
            user_agent=user_agent,
            platform=platform,
            metadata=metadata or {},
        )
        return await self.event_repo.create(event)


# =============================================================================
# PWA Analytics Service
# =============================================================================


class PWAAnalyticsService:
    """Service for PWA installation analytics."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize service with database session."""
        self.session = session
        self.event_repo = PWAInstallationEventRepository(session)

    async def log_event(
        self,
        tenant_id: UUID,
        event_data: PWAEventCreate,
        client_id: UUID | None = None,
        user_agent: str | None = None,
    ) -> PWAInstallationEvent:
        """Log a PWA event."""
        event = PWAInstallationEvent(
            client_id=client_id,
            tenant_id=tenant_id,
            event_type=event_data.event_type.value,
            platform=event_data.platform,
            user_agent=user_agent,
            metadata=event_data.metadata,
        )
        return await self.event_repo.create(event)

    async def get_adoption_stats(self, tenant_id: UUID) -> dict[str, Any]:
        """Get PWA adoption statistics for a tenant."""
        stats = await self.event_repo.get_adoption_stats(tenant_id)

        # Calculate rates
        prompts_shown = stats.get("prompts_shown", 0)
        apps_installed = stats.get("apps_installed", 0)
        push_enabled = stats.get("push_enabled", 0)

        install_rate = (apps_installed / prompts_shown * 100) if prompts_shown > 0 else 0
        push_opt_in_rate = (push_enabled / apps_installed * 100) if apps_installed > 0 else 0

        return {
            **stats,
            "install_rate": round(install_rate, 1),
            "push_opt_in_rate": round(push_opt_in_rate, 1),
        }
