"""Repository pattern for push notification data access.

Provides database operations for:
- PushSubscription
- PushNotificationLog
- WebAuthnCredential
- PWAInstallationEvent

Spec: 032-pwa-mobile-document-capture
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.push.models import (
    NotificationType,
    PushNotificationLog,
    PushSubscription,
    PWAEventType,
    PWAInstallationEvent,
    WebAuthnCredential,
)

# =============================================================================
# Push Subscription Repository
# =============================================================================


class PushSubscriptionRepository:
    """Repository for PushSubscription data access."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, subscription_id: UUID) -> PushSubscription | None:
        """Get subscription by ID."""
        result = await self.session.execute(
            select(PushSubscription).where(PushSubscription.id == subscription_id)
        )
        return result.scalar_one_or_none()

    async def get_by_endpoint(self, endpoint: str) -> PushSubscription | None:
        """Get subscription by endpoint URL."""
        result = await self.session.execute(
            select(PushSubscription).where(PushSubscription.endpoint == endpoint)
        )
        return result.scalar_one_or_none()

    async def get_active_by_client(self, client_id: UUID) -> list[PushSubscription]:
        """Get all active subscriptions for a client."""
        result = await self.session.execute(
            select(PushSubscription).where(
                PushSubscription.client_id == client_id,
                PushSubscription.is_active == True,  # noqa: E712
            )
        )
        return list(result.scalars().all())

    async def get_active_by_tenant(self, tenant_id: UUID) -> list[PushSubscription]:
        """Get all active subscriptions for a tenant."""
        result = await self.session.execute(
            select(PushSubscription).where(
                PushSubscription.tenant_id == tenant_id,
                PushSubscription.is_active == True,  # noqa: E712
            )
        )
        return list(result.scalars().all())

    async def create(self, subscription: PushSubscription) -> PushSubscription:
        """Create a new subscription."""
        self.session.add(subscription)
        await self.session.flush()
        await self.session.refresh(subscription)
        return subscription

    async def update(self, subscription_id: UUID, data: dict[str, Any]) -> PushSubscription | None:
        """Update an existing subscription."""
        subscription = await self.get_by_id(subscription_id)
        if not subscription:
            return None

        for key, value in data.items():
            if hasattr(subscription, key) and value is not None:
                setattr(subscription, key, value)

        await self.session.flush()
        await self.session.refresh(subscription)
        return subscription

    async def deactivate(self, subscription_id: UUID) -> bool:
        """Deactivate a subscription. Returns True if found."""
        subscription = await self.get_by_id(subscription_id)
        if not subscription:
            return False

        subscription.is_active = False
        await self.session.flush()
        return True

    async def deactivate_by_endpoint(self, endpoint: str) -> bool:
        """Deactivate subscription by endpoint URL. Returns True if found."""
        subscription = await self.get_by_endpoint(endpoint)
        if not subscription:
            return False

        subscription.is_active = False
        await self.session.flush()
        return True

    async def update_last_used(self, subscription_id: UUID) -> None:
        """Update the last_used_at timestamp."""
        stmt = (
            update(PushSubscription)
            .where(PushSubscription.id == subscription_id)
            .values(last_used_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)

    async def delete(self, subscription_id: UUID) -> bool:
        """Delete a subscription. Returns True if deleted."""
        subscription = await self.get_by_id(subscription_id)
        if not subscription:
            return False

        await self.session.delete(subscription)
        await self.session.flush()
        return True

    async def count_by_client(self, client_id: UUID) -> int:
        """Count active subscriptions for a client."""
        result = await self.session.execute(
            select(func.count(PushSubscription.id)).where(
                PushSubscription.client_id == client_id,
                PushSubscription.is_active == True,  # noqa: E712
            )
        )
        return result.scalar() or 0


# =============================================================================
# Push Notification Log Repository
# =============================================================================


class PushNotificationLogRepository:
    """Repository for PushNotificationLog data access."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, log_id: UUID) -> PushNotificationLog | None:
        """Get log entry by ID."""
        result = await self.session.execute(
            select(PushNotificationLog).where(PushNotificationLog.id == log_id)
        )
        return result.scalar_one_or_none()

    async def create(self, log: PushNotificationLog) -> PushNotificationLog:
        """Create a new log entry."""
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def mark_delivered(self, log_id: UUID, fcm_message_id: str | None = None) -> None:
        """Mark a notification as delivered."""
        stmt = (
            update(PushNotificationLog)
            .where(PushNotificationLog.id == log_id)
            .values(
                delivered_at=datetime.now(timezone.utc),
                fcm_message_id=fcm_message_id,
            )
        )
        await self.session.execute(stmt)

    async def mark_clicked(self, log_id: UUID) -> None:
        """Mark a notification as clicked."""
        stmt = (
            update(PushNotificationLog)
            .where(PushNotificationLog.id == log_id)
            .values(clicked_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)

    async def mark_failed(self, log_id: UUID, error_message: str) -> None:
        """Mark a notification as failed."""
        stmt = (
            update(PushNotificationLog)
            .where(PushNotificationLog.id == log_id)
            .values(error_message=error_message)
        )
        await self.session.execute(stmt)

    async def list_by_subscription(
        self,
        subscription_id: UUID,
        notification_type: NotificationType | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[PushNotificationLog]:
        """List log entries for a subscription."""
        query = select(PushNotificationLog).where(
            PushNotificationLog.subscription_id == subscription_id
        )

        if notification_type:
            query = query.where(PushNotificationLog.notification_type == notification_type.value)

        query = query.order_by(PushNotificationLog.sent_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_delivery_stats(self, subscription_id: UUID) -> dict[str, int]:
        """Get delivery statistics for a subscription."""
        base_query = select(PushNotificationLog).where(
            PushNotificationLog.subscription_id == subscription_id
        )

        total_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = total_result.scalar() or 0

        delivered_result = await self.session.execute(
            select(func.count()).select_from(
                base_query.where(PushNotificationLog.delivered_at.is_not(None)).subquery()
            )
        )
        delivered = delivered_result.scalar() or 0

        clicked_result = await self.session.execute(
            select(func.count()).select_from(
                base_query.where(PushNotificationLog.clicked_at.is_not(None)).subquery()
            )
        )
        clicked = clicked_result.scalar() or 0

        failed_result = await self.session.execute(
            select(func.count()).select_from(
                base_query.where(PushNotificationLog.error_message.is_not(None)).subquery()
            )
        )
        failed = failed_result.scalar() or 0

        return {
            "total": total,
            "delivered": delivered,
            "clicked": clicked,
            "failed": failed,
        }


# =============================================================================
# WebAuthn Credential Repository
# =============================================================================


class WebAuthnCredentialRepository:
    """Repository for WebAuthnCredential data access."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, credential_id_uuid: UUID) -> WebAuthnCredential | None:
        """Get credential by its table ID."""
        result = await self.session.execute(
            select(WebAuthnCredential).where(WebAuthnCredential.id == credential_id_uuid)
        )
        return result.scalar_one_or_none()

    async def get_by_credential_id(self, credential_id: bytes) -> WebAuthnCredential | None:
        """Get credential by WebAuthn credential ID."""
        result = await self.session.execute(
            select(WebAuthnCredential).where(WebAuthnCredential.credential_id == credential_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_client(self, client_id: UUID) -> list[WebAuthnCredential]:
        """Get all active credentials for a client."""
        result = await self.session.execute(
            select(WebAuthnCredential).where(
                WebAuthnCredential.client_id == client_id,
                WebAuthnCredential.is_active == True,  # noqa: E712
            )
        )
        return list(result.scalars().all())

    async def create(self, credential: WebAuthnCredential) -> WebAuthnCredential:
        """Create a new credential."""
        self.session.add(credential)
        await self.session.flush()
        await self.session.refresh(credential)
        return credential

    async def update_sign_count(self, credential_id: bytes, sign_count: int) -> None:
        """Update the sign count after authentication."""
        stmt = (
            update(WebAuthnCredential)
            .where(WebAuthnCredential.credential_id == credential_id)
            .values(
                sign_count=sign_count,
                last_used_at=datetime.now(timezone.utc),
            )
        )
        await self.session.execute(stmt)

    async def deactivate(self, credential_id_uuid: UUID) -> bool:
        """Deactivate a credential. Returns True if found."""
        credential = await self.get_by_id(credential_id_uuid)
        if not credential:
            return False

        credential.is_active = False
        await self.session.flush()
        return True

    async def delete(self, credential_id_uuid: UUID) -> bool:
        """Delete a credential. Returns True if deleted."""
        credential = await self.get_by_id(credential_id_uuid)
        if not credential:
            return False

        await self.session.delete(credential)
        await self.session.flush()
        return True


# =============================================================================
# PWA Installation Event Repository
# =============================================================================


class PWAInstallationEventRepository:
    """Repository for PWAInstallationEvent data access."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def create(self, event: PWAInstallationEvent) -> PWAInstallationEvent:
        """Create a new installation event."""
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        event_type: PWAEventType | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[PWAInstallationEvent]:
        """List events for a tenant."""
        query = select(PWAInstallationEvent).where(PWAInstallationEvent.tenant_id == tenant_id)

        if event_type:
            query = query.where(PWAInstallationEvent.event_type == event_type.value)

        query = query.order_by(PWAInstallationEvent.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_adoption_stats(self, tenant_id: UUID) -> dict[str, int]:
        """Get PWA adoption statistics for a tenant."""
        result = await self.session.execute(
            select(
                PWAInstallationEvent.event_type,
                func.count(PWAInstallationEvent.id),
            )
            .where(PWAInstallationEvent.tenant_id == tenant_id)
            .group_by(PWAInstallationEvent.event_type)
        )

        stats = {event_type: count for event_type, count in result.all()}

        return {
            "prompts_shown": stats.get(PWAEventType.INSTALL_PROMPT_SHOWN.value, 0),
            "prompts_accepted": stats.get(PWAEventType.INSTALL_PROMPT_ACCEPTED.value, 0),
            "prompts_dismissed": stats.get(PWAEventType.INSTALL_PROMPT_DISMISSED.value, 0),
            "apps_installed": stats.get(PWAEventType.APP_INSTALLED.value, 0),
            "push_enabled": stats.get(PWAEventType.PUSH_PERMISSION_GRANTED.value, 0),
            "push_denied": stats.get(PWAEventType.PUSH_PERMISSION_DENIED.value, 0),
            "biometric_registered": stats.get(PWAEventType.BIOMETRIC_REGISTERED.value, 0),
        }
