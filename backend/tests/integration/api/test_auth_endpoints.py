"""Integration tests for auth API endpoints.

Tests cover:
- POST /api/v1/auth/register creates user and tenant
- POST /api/v1/auth/register with duplicate email returns error
- GET /api/v1/auth/me returns current user with permissions
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import UserRole
from tests.factories.auth import (
    InvitationFactory,
    PracticeUserFactory,
    TenantFactory,
    UserFactory,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_clerk_token_payload() -> dict[str, Any]:
    """Create mock JWT claims from Clerk."""
    return {
        "sub": "user_clerk_test123",
        "email": "test@example.com",
        "email_verified": True,
        "iss": "https://test.clerk.dev",
        "azp": "http://localhost:3000",
    }


@pytest.fixture
def auth_headers_mock() -> dict[str, str]:
    """Provide mock authorization headers."""
    return {"Authorization": "Bearer mock_clerk_token"}


# =============================================================================
# POST /api/v1/auth/register Tests
# =============================================================================


class TestRegisterEndpoint:
    """Tests for POST /api/v1/auth/register."""

    @pytest.mark.asyncio
    async def test_register_creates_user_and_tenant(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
        auth_headers_mock: dict[str, str],
        mock_clerk_token_payload: dict[str, Any],
    ) -> None:
        """Test that register creates a new user and tenant."""
        # Mock the JWT validation to return our test payload
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub=mock_clerk_token_payload["sub"],
                email=mock_clerk_token_payload["email"],
                email_verified=True,
                exp=9999999999,
                iat=1234567890,
            )

            # Mock ClerkClient.get_user
            with patch("app.modules.auth.service.AuthService._get_clerk_user") as mock_get_user:
                mock_get_user.return_value = MagicMock(
                    id=mock_clerk_token_payload["sub"],
                    primary_email=mock_clerk_token_payload["email"],
                    first_name="John",
                    last_name="Doe",
                )

                response = await test_client.post(
                    "/api/v1/auth/register",
                    json={"tenant_name": "Test Practice"},
                    headers=auth_headers_mock,
                )

        # Verify response
        assert response.status_code == 201
        data = response.json()
        assert data["is_new_tenant"] is True
        assert data["user"]["email"] == mock_clerk_token_payload["email"]
        assert data["user"]["role"] == "admin"  # First user is admin
        assert data["tenant"]["name"] == "Test Practice"

    @pytest.mark.asyncio
    async def test_register_with_duplicate_email_returns_conflict(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
        auth_headers_mock: dict[str, str],
    ) -> None:
        """Test that registering with existing email returns 409 conflict."""
        # Create existing user
        existing_email = "existing@example.com"
        tenant = TenantFactory()
        user = UserFactory(email=existing_email)
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
        )

        db_session.add(tenant)
        db_session.add(user)
        db_session.add(practice_user)
        await db_session.flush()

        # Mock the JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub="user_new_clerk_id",
                email=existing_email,  # Same email as existing user
                email_verified=True,
                exp=9999999999,
                iat=1234567890,
            )

            with patch("app.modules.auth.service.AuthService._get_clerk_user") as mock_get_user:
                mock_get_user.return_value = MagicMock(
                    id="user_new_clerk_id",
                    primary_email=existing_email,
                )

                response = await test_client.post(
                    "/api/v1/auth/register",
                    json={"tenant_name": "Another Practice"},
                    headers=auth_headers_mock,
                )

        assert response.status_code == 409
        assert "already registered" in response.json()["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_register_with_invitation_joins_tenant(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
        auth_headers_mock: dict[str, str],
    ) -> None:
        """Test that registering with invitation joins existing tenant."""
        # Create existing tenant and invitation
        tenant = TenantFactory()
        inviter_user = UserFactory()
        inviter = PracticeUserFactory(
            user_id=inviter_user.id,
            tenant_id=tenant.id,
            role=UserRole.ADMIN,
        )
        invitation = InvitationFactory(
            tenant_id=tenant.id,
            invited_by=inviter.id,
            email="invited@example.com",
            role=UserRole.ACCOUNTANT,
        )

        db_session.add(tenant)
        db_session.add(inviter_user)
        db_session.add(inviter)
        db_session.add(invitation)
        await db_session.flush()

        # Mock the JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub="user_invited_clerk",
                email="invited@example.com",
                email_verified=True,
                exp=9999999999,
                iat=1234567890,
            )

            with patch("app.modules.auth.service.AuthService._get_clerk_user") as mock_get_user:
                mock_get_user.return_value = MagicMock(
                    id="user_invited_clerk",
                    primary_email="invited@example.com",
                )

                response = await test_client.post(
                    "/api/v1/auth/register",
                    json={"invitation_token": invitation.token},
                    headers=auth_headers_mock,
                )

        assert response.status_code == 201
        data = response.json()
        assert data["is_new_tenant"] is False
        assert data["user"]["role"] == "accountant"  # Role from invitation
        assert data["tenant"]["id"] == str(tenant.id)


# =============================================================================
# GET /api/v1/auth/me Tests
# =============================================================================


class TestMeEndpoint:
    """Tests for GET /api/v1/auth/me."""

    @pytest.mark.asyncio
    async def test_me_returns_current_user_with_permissions(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Test that /me returns current user with permissions list."""
        # Create user
        tenant = TenantFactory()
        user = UserFactory(email="me@example.com")
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id="user_me_clerk",
            role=UserRole.ADMIN,
        )

        db_session.add(tenant)
        db_session.add(user)
        db_session.add(practice_user)
        await db_session.flush()

        # Mock the JWT validation with tenant_id
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub="user_me_clerk",
                email="me@example.com",
                email_verified=True,
                tenant_id=tenant.id,
                role="admin",
                exp=9999999999,
                iat=1234567890,
            )

            response = await test_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer mock_token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == "me@example.com"
        assert data["user"]["role"] == "admin"
        assert data["user"]["tenant"]["id"] == str(tenant.id)
        assert "permissions" in data
        # Admin should have all permissions
        assert len(data["permissions"]) > 0

    @pytest.mark.asyncio
    async def test_me_without_token_returns_401(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Test that /me without token returns 401."""
        response = await test_client.get("/api/v1/auth/me")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_me_with_invalid_token_returns_401(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Test that /me with invalid token returns 401."""
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.core.exceptions import AuthenticationError

            mock_validate.side_effect = AuthenticationError("Invalid token")

            response = await test_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer invalid_token"},
            )

        assert response.status_code == 401


# =============================================================================
# POST /api/v1/auth/logout Tests
# =============================================================================


class TestLogoutEndpoint:
    """Tests for POST /api/v1/auth/logout."""

    @pytest.mark.asyncio
    async def test_logout_returns_success(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Test that logout returns success message."""
        # Create user
        tenant = TenantFactory()
        user = UserFactory()
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id="user_logout_clerk",
        )

        db_session.add(tenant)
        db_session.add(user)
        db_session.add(practice_user)
        await db_session.flush()

        # Mock the JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub="user_logout_clerk",
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

    @pytest.mark.asyncio
    async def test_logout_all_devices(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Test logout with all_devices flag."""
        # Create user
        tenant = TenantFactory()
        user = UserFactory()
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id="user_logout_all_clerk",
        )

        db_session.add(tenant)
        db_session.add(user)
        db_session.add(practice_user)
        await db_session.flush()

        # Mock the JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub="user_logout_all_clerk",
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
