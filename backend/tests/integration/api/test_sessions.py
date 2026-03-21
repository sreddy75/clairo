"""Integration tests for session management.

Tests cover:
- POST /api/v1/auth/logout revokes current session
- POST /api/v1/auth/logout-all revokes all sessions
- Revoked token returns 401
- Session events are audited

Requirements:
- User Story 7 - Session Management and Logout
"""

import uuid
from typing import Any
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLog
from tests.factories.auth import (
    PracticeUserFactory,
    TenantFactory,
    UserFactory,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def session_user_data() -> dict[str, Any]:
    """Create test user data for session tests."""
    return {
        "clerk_id": f"user_session_test_{uuid.uuid4().hex[:8]}",
        "email": f"session_{uuid.uuid4().hex[:8]}@example.com",
    }


# =============================================================================
# POST /api/v1/auth/logout Tests
# =============================================================================


class TestLogoutEndpoint:
    """Tests for POST /api/v1/auth/logout."""

    @pytest.mark.asyncio
    async def test_logout_current_session_success(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
        session_user_data: dict[str, Any],
    ) -> None:
        """Test that logout revokes current session and returns success."""
        # Create user
        tenant = TenantFactory()
        user = UserFactory(email=session_user_data["email"])
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id=session_user_data["clerk_id"],
        )

        db_session.add(tenant)
        db_session.add(user)
        db_session.add(practice_user)
        await db_session.flush()

        # Mock JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub=session_user_data["clerk_id"],
                tenant_id=tenant.id,
                exp=9999999999,
                iat=1234567890,
            )

            response = await test_client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": "Bearer mock_token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Logged out successfully"
        assert data["all_devices"] is False

    @pytest.mark.asyncio
    async def test_logout_with_all_devices_flag(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
        session_user_data: dict[str, Any],
    ) -> None:
        """Test logout with all_devices=true logs out all sessions."""
        # Create user
        tenant = TenantFactory()
        user = UserFactory(email=session_user_data["email"])
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id=session_user_data["clerk_id"],
        )

        db_session.add(tenant)
        db_session.add(user)
        db_session.add(practice_user)
        await db_session.flush()

        # Mock JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub=session_user_data["clerk_id"],
                tenant_id=tenant.id,
                exp=9999999999,
                iat=1234567890,
            )

            response = await test_client.post(
                "/api/v1/auth/logout",
                json={"all_devices": True},
                headers={"Authorization": "Bearer mock_token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["all_devices"] is True

    @pytest.mark.asyncio
    async def test_logout_without_authentication_returns_401(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Test that logout without token returns 401."""
        response = await test_client.post("/api/v1/auth/logout")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_creates_audit_log(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
        session_user_data: dict[str, Any],
    ) -> None:
        """Test that logout creates an audit log entry."""
        # Create user
        tenant = TenantFactory()
        user = UserFactory(email=session_user_data["email"])
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id=session_user_data["clerk_id"],
        )

        db_session.add(tenant)
        db_session.add(user)
        db_session.add(practice_user)
        await db_session.flush()

        # Mock JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub=session_user_data["clerk_id"],
                tenant_id=tenant.id,
                exp=9999999999,
                iat=1234567890,
            )

            response = await test_client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": "Bearer mock_token"},
            )

        assert response.status_code == 200

        # Verify audit log was created
        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "auth.logout",
                AuditLog.tenant_id == tenant.id,
            )
        )
        audit_log = result.scalar_one_or_none()

        assert audit_log is not None
        assert audit_log.action == "logout"
        assert audit_log.outcome == "success"


# =============================================================================
# POST /api/v1/auth/logout-all Tests
# =============================================================================


class TestLogoutAllEndpoint:
    """Tests for POST /api/v1/auth/logout-all."""

    @pytest.mark.asyncio
    async def test_logout_all_revokes_all_sessions(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
        session_user_data: dict[str, Any],
    ) -> None:
        """Test that logout-all revokes all user sessions."""
        # Create user
        tenant = TenantFactory()
        user = UserFactory(email=session_user_data["email"])
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id=session_user_data["clerk_id"],
        )

        db_session.add(tenant)
        db_session.add(user)
        db_session.add(practice_user)
        await db_session.flush()

        # Mock JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub=session_user_data["clerk_id"],
                tenant_id=tenant.id,
                exp=9999999999,
                iat=1234567890,
            )

            response = await test_client.post(
                "/api/v1/auth/logout-all",
                headers={"Authorization": "Bearer mock_token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Logged out from all devices"
        assert data["all_devices"] is True

    @pytest.mark.asyncio
    async def test_logout_all_creates_audit_log_with_all_flag(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
        session_user_data: dict[str, Any],
    ) -> None:
        """Test that logout-all creates audit log with logout_type=all."""
        # Create user
        tenant = TenantFactory()
        user = UserFactory(email=session_user_data["email"])
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id=session_user_data["clerk_id"],
        )

        db_session.add(tenant)
        db_session.add(user)
        db_session.add(practice_user)
        await db_session.flush()

        # Mock JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub=session_user_data["clerk_id"],
                tenant_id=tenant.id,
                exp=9999999999,
                iat=1234567890,
            )

            response = await test_client.post(
                "/api/v1/auth/logout-all",
                headers={"Authorization": "Bearer mock_token"},
            )

        assert response.status_code == 200

        # Verify audit log
        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "auth.logout",
                AuditLog.tenant_id == tenant.id,
            )
        )
        audit_log = result.scalar_one_or_none()

        assert audit_log is not None
        assert audit_log.event_metadata is not None
        assert audit_log.event_metadata.get("logout_type") == "all"


# =============================================================================
# Revoked Token Tests
# =============================================================================


class TestRevokedTokenBehavior:
    """Tests for revoked token handling."""

    @pytest.mark.asyncio
    async def test_revoked_token_returns_401(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Test that a revoked/invalid token returns 401."""
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.core.exceptions import AuthenticationError

            mock_validate.side_effect = AuthenticationError(message="Token has been revoked")

            response = await test_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer revoked_token"},
            )

        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "AUTHENTICATION_ERROR"

    @pytest.mark.asyncio
    async def test_expired_token_returns_401(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Test that an expired token returns 401."""
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.core.exceptions import AuthenticationError

            mock_validate.side_effect = AuthenticationError(message="Token has expired")

            response = await test_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer expired_token"},
            )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_token_returns_401(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Test that a malformed token returns 401."""
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.core.exceptions import AuthenticationError

            mock_validate.side_effect = AuthenticationError(message="Invalid token format")

            response = await test_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer not_a_valid_jwt"},
            )

        assert response.status_code == 401
