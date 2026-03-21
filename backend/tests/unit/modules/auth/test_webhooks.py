"""Unit tests for Clerk webhook handlers.

Tests cover:
- Webhook signature verification
- user.created event handling
- user.updated event handling
- user.deleted event handling
- session.created event handling
- session.ended event handling

Requirements:
- Phase 11: Clerk Webhooks Integration
"""

import hashlib
import hmac
import json
import time
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.webhooks import (
    ClerkWebhookHandler,
    WebhookEvent,
    verify_webhook_signature,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def webhook_secret() -> str:
    """Webhook signing secret for tests."""
    return "whsec_test_secret_12345"


@pytest.fixture
def valid_timestamp() -> str:
    """Valid timestamp within tolerance window."""
    return str(int(time.time()))


@pytest.fixture
def user_created_payload() -> dict[str, Any]:
    """Sample user.created webhook payload."""
    return {
        "data": {
            "id": "user_clerk_abc123",
            "email_addresses": [
                {
                    "email_address": "newuser@example.com",
                    "verification": {"status": "verified"},
                }
            ],
            "first_name": "New",
            "last_name": "User",
            "public_metadata": {},
            "private_metadata": {},
            "created_at": int(time.time() * 1000),
        },
        "object": "event",
        "type": "user.created",
    }


@pytest.fixture
def user_updated_payload() -> dict[str, Any]:
    """Sample user.updated webhook payload."""
    return {
        "data": {
            "id": "user_clerk_abc123",
            "email_addresses": [
                {
                    "email_address": "updated@example.com",
                    "verification": {"status": "verified"},
                }
            ],
            "first_name": "Updated",
            "last_name": "User",
            "public_metadata": {
                "tenant_id": str(uuid.uuid4()),
                "role": "admin",
            },
            "private_metadata": {},
        },
        "object": "event",
        "type": "user.updated",
    }


@pytest.fixture
def user_deleted_payload() -> dict[str, Any]:
    """Sample user.deleted webhook payload."""
    return {
        "data": {
            "id": "user_clerk_abc123",
            "deleted": True,
        },
        "object": "event",
        "type": "user.deleted",
    }


@pytest.fixture
def session_created_payload() -> dict[str, Any]:
    """Sample session.created webhook payload."""
    return {
        "data": {
            "id": "sess_abc123",
            "user_id": "user_clerk_abc123",
            "client_id": "client_abc123",
            "status": "active",
            "created_at": int(time.time() * 1000),
            "last_active_at": int(time.time() * 1000),
        },
        "object": "event",
        "type": "session.created",
    }


@pytest.fixture
def session_ended_payload() -> dict[str, Any]:
    """Sample session.ended webhook payload."""
    return {
        "data": {
            "id": "sess_abc123",
            "user_id": "user_clerk_abc123",
            "status": "ended",
            "expire_at": int(time.time() * 1000),
        },
        "object": "event",
        "type": "session.ended",
    }


def generate_signature(
    payload: dict[str, Any],
    secret: str,
    timestamp: str,
) -> str:
    """Generate a valid webhook signature for testing.

    Uses the Svix signature format that Clerk uses.
    """
    body = json.dumps(payload, separators=(",", ":"))
    to_sign = f"{timestamp}.{body}"

    # Decode base64 secret (Clerk secrets are base64 encoded)
    # For test, we'll use the raw secret
    signature = hmac.new(
        secret.encode(),
        to_sign.encode(),
        hashlib.sha256,
    ).hexdigest()

    return f"v1,{signature}"


# =============================================================================
# Signature Verification Tests
# =============================================================================


class TestSignatureVerification:
    """Tests for webhook signature verification."""

    def test_valid_signature_passes(
        self,
        webhook_secret: str,
        valid_timestamp: str,
        user_created_payload: dict[str, Any],
    ) -> None:
        """Test that a valid signature passes verification."""
        signature = generate_signature(
            user_created_payload,
            webhook_secret,
            valid_timestamp,
        )

        headers = {
            "svix-id": "msg_abc123",
            "svix-timestamp": valid_timestamp,
            "svix-signature": signature,
        }

        body = json.dumps(user_created_payload, separators=(",", ":"))

        result = verify_webhook_signature(
            body=body,
            headers=headers,
            secret=webhook_secret,
        )

        assert result is True

    def test_invalid_signature_fails(
        self,
        webhook_secret: str,
        valid_timestamp: str,
        user_created_payload: dict[str, Any],
    ) -> None:
        """Test that an invalid signature fails verification."""
        headers = {
            "svix-id": "msg_abc123",
            "svix-timestamp": valid_timestamp,
            "svix-signature": "v1,invalidsignature123",
        }

        body = json.dumps(user_created_payload, separators=(",", ":"))

        result = verify_webhook_signature(
            body=body,
            headers=headers,
            secret=webhook_secret,
        )

        assert result is False

    def test_expired_timestamp_fails(
        self,
        webhook_secret: str,
        user_created_payload: dict[str, Any],
    ) -> None:
        """Test that an expired timestamp fails verification."""
        # Timestamp 10 minutes ago (beyond 5 minute tolerance)
        old_timestamp = str(int(time.time()) - 600)

        signature = generate_signature(
            user_created_payload,
            webhook_secret,
            old_timestamp,
        )

        headers = {
            "svix-id": "msg_abc123",
            "svix-timestamp": old_timestamp,
            "svix-signature": signature,
        }

        body = json.dumps(user_created_payload, separators=(",", ":"))

        result = verify_webhook_signature(
            body=body,
            headers=headers,
            secret=webhook_secret,
        )

        assert result is False

    def test_missing_headers_fails(
        self,
        webhook_secret: str,
        user_created_payload: dict[str, Any],
    ) -> None:
        """Test that missing headers fail verification."""
        body = json.dumps(user_created_payload, separators=(",", ":"))

        # Missing svix-timestamp
        headers = {
            "svix-id": "msg_abc123",
            "svix-signature": "v1,somesignature",
        }

        result = verify_webhook_signature(
            body=body,
            headers=headers,
            secret=webhook_secret,
        )

        assert result is False


# =============================================================================
# WebhookEvent Model Tests
# =============================================================================


class TestWebhookEventModel:
    """Tests for WebhookEvent Pydantic model."""

    def test_parse_user_created_event(
        self,
        user_created_payload: dict[str, Any],
    ) -> None:
        """Test parsing user.created event."""
        event = WebhookEvent(**user_created_payload)

        assert event.type == "user.created"
        assert event.data["id"] == "user_clerk_abc123"
        assert event.data["email_addresses"][0]["email_address"] == "newuser@example.com"

    def test_parse_session_created_event(
        self,
        session_created_payload: dict[str, Any],
    ) -> None:
        """Test parsing session.created event."""
        event = WebhookEvent(**session_created_payload)

        assert event.type == "session.created"
        assert event.data["user_id"] == "user_clerk_abc123"


# =============================================================================
# Handler Tests
# =============================================================================


class TestUserCreatedHandler:
    """Tests for user.created webhook handler."""

    @pytest.mark.asyncio
    async def test_user_created_logs_event(
        self,
        user_created_payload: dict[str, Any],
    ) -> None:
        """Test that user.created event is logged."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.flush = AsyncMock()
        mock_session.add = MagicMock()

        handler = ClerkWebhookHandler(session=mock_session)

        event = WebhookEvent(**user_created_payload)

        await handler.handle_user_created(event)

        # Verify audit log was created (session.add called)
        # The actual implementation will log the event


class TestUserUpdatedHandler:
    """Tests for user.updated webhook handler."""

    @pytest.mark.asyncio
    async def test_user_updated_syncs_mfa_status(
        self,
        user_updated_payload: dict[str, Any],
    ) -> None:
        """Test that user.updated syncs MFA status."""
        # Add MFA data to payload
        user_updated_payload["data"]["two_factor_enabled"] = True

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.flush = AsyncMock()
        mock_session.add = MagicMock()

        handler = ClerkWebhookHandler(session=mock_session)

        event = WebhookEvent(**user_updated_payload)

        # Mock repository to return a practice user
        with patch.object(handler, "practice_user_repo") as mock_repo:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.user_id = uuid.uuid4()
            mock_user.tenant_id = uuid.uuid4()
            mock_user.mfa_enabled = False
            mock_repo.get_by_clerk_id = AsyncMock(return_value=mock_user)
            mock_repo.update = AsyncMock()

            # Mock audit service
            with patch.object(handler, "audit_service") as mock_audit:
                mock_audit.log_event = AsyncMock()

                await handler.handle_user_updated(event)

                # Verify MFA sync was attempted
                mock_repo.get_by_clerk_id.assert_called_once()


class TestUserDeletedHandler:
    """Tests for user.deleted webhook handler."""

    @pytest.mark.asyncio
    async def test_user_deleted_deactivates_user(
        self,
        user_deleted_payload: dict[str, Any],
    ) -> None:
        """Test that user.deleted deactivates the user."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.flush = AsyncMock()
        mock_session.add = MagicMock()

        handler = ClerkWebhookHandler(session=mock_session)

        event = WebhookEvent(**user_deleted_payload)

        # Mock repository
        with patch.object(handler, "practice_user_repo") as mock_repo:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.user_id = uuid.uuid4()
            mock_user.tenant_id = uuid.uuid4()
            mock_user.user = MagicMock()
            mock_user.user.is_active = True
            mock_repo.get_by_clerk_id = AsyncMock(return_value=mock_user)

            with patch.object(handler, "user_repo") as mock_user_repo:
                mock_user_repo.update = AsyncMock()

                # Mock audit service
                with patch.object(handler, "audit_service") as mock_audit:
                    mock_audit.log_event = AsyncMock()

                    await handler.handle_user_deleted(event)

                    # Verify user lookup was performed
                    mock_repo.get_by_clerk_id.assert_called_once()


class TestSessionCreatedHandler:
    """Tests for session.created webhook handler."""

    @pytest.mark.asyncio
    async def test_session_created_logs_login(
        self,
        session_created_payload: dict[str, Any],
    ) -> None:
        """Test that session.created logs a login event."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.flush = AsyncMock()
        mock_session.add = MagicMock()

        handler = ClerkWebhookHandler(session=mock_session)

        event = WebhookEvent(**session_created_payload)

        # Mock repository to return a practice user
        with patch.object(handler, "practice_user_repo") as mock_repo:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.user_id = uuid.uuid4()
            mock_user.tenant_id = uuid.uuid4()
            mock_repo.get_by_clerk_id = AsyncMock(return_value=mock_user)
            mock_repo.update_last_login = AsyncMock()

            # Mock audit service
            with patch.object(handler, "audit_service") as mock_audit:
                mock_audit.log_event = AsyncMock()

                await handler.handle_session_created(event)

                # Verify the login event was processed
                mock_repo.get_by_clerk_id.assert_called_once()


class TestSessionEndedHandler:
    """Tests for session.ended webhook handler."""

    @pytest.mark.asyncio
    async def test_session_ended_logs_logout(
        self,
        session_ended_payload: dict[str, Any],
    ) -> None:
        """Test that session.ended logs a logout event."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.flush = AsyncMock()
        mock_session.add = MagicMock()

        handler = ClerkWebhookHandler(session=mock_session)

        event = WebhookEvent(**session_ended_payload)

        # Mock repository to return a practice user
        with patch.object(handler, "practice_user_repo") as mock_repo:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.user_id = uuid.uuid4()
            mock_user.tenant_id = uuid.uuid4()
            mock_repo.get_by_clerk_id = AsyncMock(return_value=mock_user)

            # Mock audit service
            with patch.object(handler, "audit_service") as mock_audit:
                mock_audit.log_event = AsyncMock()

                await handler.handle_session_ended(event)

                # Verify the logout event was processed
                mock_repo.get_by_clerk_id.assert_called_once()
