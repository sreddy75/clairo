"""Integration tests for push notification API endpoints.

Tests cover:
- VAPID public key retrieval
- Push subscription management (subscribe, list, unsubscribe)
- Notification click tracking
- PWA analytics events

Spec: 032-pwa-mobile-document-capture
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.push.models import (
    NotificationType,
    PushNotificationLog,
    PushSubscription,
    PWAEventType,
)
from app.modules.portal.auth.magic_link import generate_secure_token, hash_token
from app.modules.portal.models import PortalSession
from tests.factories.auth import TenantFactory
from tests.factories.xero import XeroConnectionFactory

# =============================================================================
# Test Fixtures
# =============================================================================


async def get_portal_access_token(
    test_client: AsyncClient,
    db_session: AsyncSession,
    tenant=None,
    connection=None,
) -> tuple[str, "TenantFactory", "XeroConnectionFactory"]:
    """Create portal session and return access token.

    Returns:
        Tuple of (access_token, tenant, connection)
    """
    if tenant is None:
        tenant = TenantFactory()
    if connection is None:
        connection = XeroConnectionFactory(tenant_id=tenant.id)

    # Create session with known refresh token
    refresh_token = generate_secure_token()
    refresh_token_hash = hash_token(refresh_token)
    session = PortalSession(
        connection_id=connection.id,
        tenant_id=tenant.id,
        refresh_token_hash=refresh_token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        revoked=False,
    )

    db_session.add_all([tenant, connection, session])
    await db_session.flush()
    await db_session.commit()

    # Get access token
    token_response = await test_client.post(
        "/api/v1/client-portal/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert token_response.status_code == 200
    access_token = token_response.json()["access_token"]
    return access_token, tenant, connection


# =============================================================================
# VAPID Key Endpoint Tests
# =============================================================================


@pytest.mark.integration
class TestGetVAPIDKey:
    """Tests for GET /api/v1/portal/push/vapid-key."""

    @pytest.mark.asyncio
    async def test_get_vapid_key_success(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Getting VAPID key returns base64-encoded public key."""
        with patch(
            "app.modules.notifications.push.service.PushSubscriptionService.get_vapid_public_key"
        ) as mock_get_key:
            mock_get_key.return_value = "BEl62iUYgUivxIkv69yViEuiBYVY..."

            response = await test_client.get("/api/v1/portal/push/vapid-key")

        assert response.status_code == 200
        data = response.json()
        assert "public_key" in data
        assert data["public_key"] == "BEl62iUYgUivxIkv69yViEuiBYVY..."

    @pytest.mark.asyncio
    async def test_get_vapid_key_not_configured(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Getting VAPID key when not configured returns 503."""
        with patch(
            "app.modules.notifications.push.service.PushSubscriptionService.get_vapid_public_key"
        ) as mock_get_key:
            mock_get_key.return_value = None

            response = await test_client.get("/api/v1/portal/push/vapid-key")

        assert response.status_code == 503
        assert "not configured" in response.json()["detail"].lower()


# =============================================================================
# Push Subscription Tests
# =============================================================================


@pytest.mark.integration
class TestSubscribe:
    """Tests for POST /api/v1/portal/push/subscribe."""

    @pytest.mark.asyncio
    async def test_subscribe_success(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Subscribing creates push subscription."""
        access_token, tenant, connection = await get_portal_access_token(test_client, db_session)

        response = await test_client.post(
            "/api/v1/portal/push/subscribe",
            json={
                "endpoint": "https://fcm.googleapis.com/fcm/send/test-endpoint-123",
                "keys": {
                    "p256dh": "BPyQ7bVG9FGmkUxFZDPqJ1pZ...",
                    "auth": "8GBwNqAAzDI...",
                },
                "device_name": "iPhone 15",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["endpoint"] == "https://fcm.googleapis.com/fcm/send/test-endpoint-123"
        assert data["device_name"] == "iPhone 15"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_subscribe_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Subscribing without auth returns 401."""
        response = await test_client.post(
            "/api/v1/portal/push/subscribe",
            json={
                "endpoint": "https://fcm.googleapis.com/fcm/send/test",
                "keys": {
                    "p256dh": "test-key",
                    "auth": "test-auth",
                },
            },
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_subscribe_duplicate_endpoint_updates(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Subscribing with existing endpoint updates the subscription."""
        access_token, tenant, connection = await get_portal_access_token(test_client, db_session)

        endpoint = "https://fcm.googleapis.com/fcm/send/test-duplicate"

        # First subscription
        response1 = await test_client.post(
            "/api/v1/portal/push/subscribe",
            json={
                "endpoint": endpoint,
                "keys": {
                    "p256dh": "key1",
                    "auth": "auth1",
                },
                "device_name": "Device 1",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response1.status_code == 201
        first_id = response1.json()["id"]

        # Second subscription with same endpoint but different device name
        response2 = await test_client.post(
            "/api/v1/portal/push/subscribe",
            json={
                "endpoint": endpoint,
                "keys": {
                    "p256dh": "key2",
                    "auth": "auth2",
                },
                "device_name": "Device 2",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response2.status_code == 201
        # Should return the same subscription (updated)
        assert response2.json()["id"] == first_id
        assert response2.json()["device_name"] == "Device 2"


@pytest.mark.integration
class TestListSubscriptions:
    """Tests for GET /api/v1/portal/push/subscriptions."""

    @pytest.mark.asyncio
    async def test_list_subscriptions_empty(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Listing subscriptions when none exist returns empty list."""
        access_token, tenant, connection = await get_portal_access_token(test_client, db_session)

        response = await test_client.get(
            "/api/v1/portal/push/subscriptions",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["subscriptions"] == []
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_list_subscriptions_with_data(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Listing subscriptions returns all active subscriptions."""
        access_token, tenant, connection = await get_portal_access_token(test_client, db_session)

        # Create subscriptions
        for i in range(3):
            await test_client.post(
                "/api/v1/portal/push/subscribe",
                json={
                    "endpoint": f"https://fcm.googleapis.com/fcm/send/test-{i}",
                    "keys": {
                        "p256dh": f"key-{i}",
                        "auth": f"auth-{i}",
                    },
                    "device_name": f"Device {i}",
                },
                headers={"Authorization": f"Bearer {access_token}"},
            )

        response = await test_client.get(
            "/api/v1/portal/push/subscriptions",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3
        assert len(data["subscriptions"]) == 3

    @pytest.mark.asyncio
    async def test_list_subscriptions_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Listing subscriptions without auth returns 401."""
        response = await test_client.get("/api/v1/portal/push/subscriptions")
        assert response.status_code == 401


@pytest.mark.integration
class TestUnsubscribe:
    """Tests for DELETE /api/v1/portal/push/unsubscribe."""

    @pytest.mark.asyncio
    async def test_unsubscribe_by_endpoint_success(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Unsubscribing by endpoint removes subscription."""
        access_token, tenant, connection = await get_portal_access_token(test_client, db_session)

        endpoint = "https://fcm.googleapis.com/fcm/send/to-remove"

        # Create subscription
        await test_client.post(
            "/api/v1/portal/push/subscribe",
            json={
                "endpoint": endpoint,
                "keys": {
                    "p256dh": "key",
                    "auth": "auth",
                },
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        # Unsubscribe
        response = await test_client.delete(
            f"/api/v1/portal/push/unsubscribe?endpoint={endpoint}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 204

        # Verify subscription is removed
        list_response = await test_client.get(
            "/api/v1/portal/push/subscriptions",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert list_response.json()["count"] == 0

    @pytest.mark.asyncio
    async def test_unsubscribe_not_found(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Unsubscribing non-existent endpoint returns 404."""
        access_token, tenant, connection = await get_portal_access_token(test_client, db_session)

        response = await test_client.delete(
            "/api/v1/portal/push/unsubscribe?endpoint=https://not.found/endpoint",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 404


@pytest.mark.integration
class TestDeleteSubscription:
    """Tests for DELETE /api/v1/portal/push/subscriptions/{subscription_id}."""

    @pytest.mark.asyncio
    async def test_delete_subscription_success(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Deleting subscription by ID removes it."""
        access_token, tenant, connection = await get_portal_access_token(test_client, db_session)

        # Create subscription
        create_response = await test_client.post(
            "/api/v1/portal/push/subscribe",
            json={
                "endpoint": "https://fcm.googleapis.com/fcm/send/to-delete",
                "keys": {
                    "p256dh": "key",
                    "auth": "auth",
                },
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        subscription_id = create_response.json()["id"]

        # Delete subscription
        response = await test_client.delete(
            f"/api/v1/portal/push/subscriptions/{subscription_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_subscription_not_found(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Deleting non-existent subscription returns 404."""
        access_token, tenant, connection = await get_portal_access_token(test_client, db_session)

        response = await test_client.delete(
            f"/api/v1/portal/push/subscriptions/{uuid4()}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 404


# =============================================================================
# Notification Click Tracking Tests
# =============================================================================


@pytest.mark.integration
class TestNotificationClicked:
    """Tests for POST /api/v1/portal/push/clicked."""

    @pytest.mark.asyncio
    async def test_notification_clicked_success(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Tracking notification click updates clicked_at timestamp."""
        # Create test data
        tenant = TenantFactory()
        connection = XeroConnectionFactory(tenant_id=tenant.id)

        subscription = PushSubscription(
            client_id=connection.id,
            tenant_id=tenant.id,
            endpoint="https://fcm.googleapis.com/fcm/send/test",
            p256dh_key="test-key",
            auth_key="test-auth",
            is_active=True,
        )

        db_session.add_all([tenant, connection, subscription])
        await db_session.flush()

        notification_log = PushNotificationLog(
            subscription_id=subscription.id,
            notification_type=NotificationType.NEW_REQUEST.value,
            title="New Document Request",
            body="You have a new document request",
            sent_at=datetime.now(timezone.utc),
        )

        db_session.add(notification_log)
        await db_session.flush()
        await db_session.commit()

        # Track click
        response = await test_client.post(
            "/api/v1/portal/push/clicked",
            json={"notification_id": str(notification_log.id)},
        )

        assert response.status_code == 204

        # Verify clicked_at is set
        await db_session.refresh(notification_log)
        assert notification_log.clicked_at is not None

    @pytest.mark.asyncio
    async def test_notification_clicked_not_found(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Tracking click for non-existent notification still returns 204.

        We return 204 even for non-existent notifications to avoid
        information leakage and for resilience.
        """
        response = await test_client.post(
            "/api/v1/portal/push/clicked",
            json={"notification_id": str(uuid4())},
        )

        assert response.status_code == 204


# =============================================================================
# PWA Analytics Events Tests
# =============================================================================


@pytest.mark.integration
class TestLogPWAEvent:
    """Tests for POST /api/v1/portal/push/events."""

    @pytest.mark.asyncio
    async def test_log_event_install_prompt_shown(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Logging install prompt shown event creates record."""
        access_token, tenant, connection = await get_portal_access_token(test_client, db_session)

        response = await test_client.post(
            "/api/v1/portal/push/events",
            json={
                "event_type": PWAEventType.INSTALL_PROMPT_SHOWN.value,
                "platform": "ios",
                "metadata": {"browser": "Safari"},
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["event_type"] == PWAEventType.INSTALL_PROMPT_SHOWN.value
        assert data["platform"] == "ios"

    @pytest.mark.asyncio
    async def test_log_event_app_installed(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Logging app installed event creates record."""
        access_token, tenant, connection = await get_portal_access_token(test_client, db_session)

        response = await test_client.post(
            "/api/v1/portal/push/events",
            json={
                "event_type": PWAEventType.APP_INSTALLED.value,
                "platform": "android",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["event_type"] == PWAEventType.APP_INSTALLED.value

    @pytest.mark.asyncio
    async def test_log_event_push_permission_granted(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Logging push permission granted event creates record."""
        access_token, tenant, connection = await get_portal_access_token(test_client, db_session)

        response = await test_client.post(
            "/api/v1/portal/push/events",
            json={
                "event_type": PWAEventType.PUSH_PERMISSION_GRANTED.value,
                "platform": "desktop",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_log_event_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Logging PWA event without auth returns 401."""
        response = await test_client.post(
            "/api/v1/portal/push/events",
            json={
                "event_type": PWAEventType.INSTALL_PROMPT_SHOWN.value,
            },
        )

        assert response.status_code == 401


# =============================================================================
# Admin Analytics Endpoints Tests (for accountant dashboard)
# =============================================================================


@pytest.mark.integration
class TestAdminAdoptionStats:
    """Tests for GET /api/v1/push/adoption-stats."""

    @pytest.mark.asyncio
    async def test_get_adoption_stats(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Getting adoption stats returns metrics."""
        tenant = TenantFactory()
        db_session.add(tenant)
        await db_session.flush()
        await db_session.commit()

        response = await test_client.get(f"/api/v1/push/adoption-stats?tenant_id={tenant.id}")

        assert response.status_code == 200
        data = response.json()
        assert "prompts_shown" in data
        assert "prompts_accepted" in data
        assert "apps_installed" in data
        assert "push_enabled" in data
        assert "install_rate" in data
        assert "push_opt_in_rate" in data
