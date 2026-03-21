"""Integration tests for MFA enforcement.

Tests cover:
- PATCH /api/v1/auth/tenant/settings can toggle mfa_required
- User mfa_enabled status is synced from Clerk
- Tenant MFA requirement is respected
- MFA events are audited

Requirements:
- User Story 8 - MFA Enforcement
"""

import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLog
from app.modules.auth.models import (
    SubscriptionStatus,
    UserRole,
)
from tests.factories.auth import (
    PracticeUserFactory,
    TenantFactory,
    UserFactory,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mfa_user_data() -> dict[str, Any]:
    """Create test user data for MFA tests."""
    return {
        "clerk_id": f"user_mfa_test_{uuid.uuid4().hex[:8]}",
        "email": f"mfa_{uuid.uuid4().hex[:8]}@example.com",
    }


# =============================================================================
# GET /api/v1/auth/tenant/settings Tests
# =============================================================================


class TestGetTenantSettings:
    """Tests for GET /api/v1/auth/tenant/settings."""

    @pytest.mark.asyncio
    async def test_get_tenant_settings_returns_mfa_status(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
        mfa_user_data: dict[str, Any],
    ) -> None:
        """Test that tenant settings include mfa_required status."""
        # Create tenant with MFA disabled
        tenant = TenantFactory(mfa_required=False)
        user = UserFactory(email=mfa_user_data["email"])
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id=mfa_user_data["clerk_id"],
            role=UserRole.ADMIN,
        )

        db_session.add(tenant)
        db_session.add(user)
        db_session.add(practice_user)
        await db_session.flush()

        # Mock JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub=mfa_user_data["clerk_id"],
                tenant_id=tenant.id,
                role="admin",
                exp=9999999999,
                iat=1234567890,
            )

            response = await test_client.get(
                "/api/v1/auth/tenant/settings",
                headers={"Authorization": "Bearer mock_token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "mfa_required" in data
        assert data["mfa_required"] is False

    @pytest.mark.asyncio
    async def test_get_tenant_settings_non_admin_forbidden(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
        mfa_user_data: dict[str, Any],
    ) -> None:
        """Test that non-admin users cannot access tenant settings."""
        # Create tenant with staff user
        tenant = TenantFactory()
        user = UserFactory(email=mfa_user_data["email"])
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id=mfa_user_data["clerk_id"],
            role=UserRole.STAFF,  # Not admin
        )

        db_session.add(tenant)
        db_session.add(user)
        db_session.add(practice_user)
        await db_session.flush()

        # Mock JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub=mfa_user_data["clerk_id"],
                tenant_id=tenant.id,
                role="staff",
                exp=9999999999,
                iat=1234567890,
            )

            response = await test_client.get(
                "/api/v1/auth/tenant/settings",
                headers={"Authorization": "Bearer mock_token"},
            )

        assert response.status_code == 403


# =============================================================================
# PATCH /api/v1/auth/tenant/settings Tests
# =============================================================================


class TestUpdateTenantSettings:
    """Tests for PATCH /api/v1/auth/tenant/settings."""

    @pytest.mark.asyncio
    async def test_update_mfa_required_to_true(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
        mfa_user_data: dict[str, Any],
    ) -> None:
        """Test that admin can enable MFA requirement."""
        # Create tenant with MFA disabled
        tenant = TenantFactory(mfa_required=False)
        user = UserFactory(email=mfa_user_data["email"])
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id=mfa_user_data["clerk_id"],
            role=UserRole.ADMIN,
        )

        db_session.add(tenant)
        db_session.add(user)
        db_session.add(practice_user)
        await db_session.flush()

        # Mock JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub=mfa_user_data["clerk_id"],
                tenant_id=tenant.id,
                role="admin",
                exp=9999999999,
                iat=1234567890,
            )

            response = await test_client.patch(
                "/api/v1/auth/tenant/settings",
                json={"mfa_required": True},
                headers={"Authorization": "Bearer mock_token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["mfa_required"] is True

    @pytest.mark.asyncio
    async def test_update_mfa_required_to_false(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
        mfa_user_data: dict[str, Any],
    ) -> None:
        """Test that admin can disable MFA requirement."""
        # Create tenant with MFA enabled
        tenant = TenantFactory(mfa_required=True)
        user = UserFactory(email=mfa_user_data["email"])
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id=mfa_user_data["clerk_id"],
            role=UserRole.ADMIN,
        )

        db_session.add(tenant)
        db_session.add(user)
        db_session.add(practice_user)
        await db_session.flush()

        # Mock JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub=mfa_user_data["clerk_id"],
                tenant_id=tenant.id,
                role="admin",
                exp=9999999999,
                iat=1234567890,
            )

            response = await test_client.patch(
                "/api/v1/auth/tenant/settings",
                json={"mfa_required": False},
                headers={"Authorization": "Bearer mock_token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["mfa_required"] is False

    @pytest.mark.asyncio
    async def test_update_mfa_creates_audit_log(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
        mfa_user_data: dict[str, Any],
    ) -> None:
        """Test that MFA setting change creates audit log."""
        # Create tenant
        tenant = TenantFactory(mfa_required=False)
        user = UserFactory(email=mfa_user_data["email"])
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id=mfa_user_data["clerk_id"],
            role=UserRole.ADMIN,
        )

        db_session.add(tenant)
        db_session.add(user)
        db_session.add(practice_user)
        await db_session.flush()

        # Mock JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub=mfa_user_data["clerk_id"],
                tenant_id=tenant.id,
                role="admin",
                exp=9999999999,
                iat=1234567890,
            )

            response = await test_client.patch(
                "/api/v1/auth/tenant/settings",
                json={"mfa_required": True},
                headers={"Authorization": "Bearer mock_token"},
            )

        assert response.status_code == 200

        # Verify audit log
        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "tenant.settings.changed",
                AuditLog.tenant_id == tenant.id,
            )
        )
        audit_log = result.scalar_one_or_none()

        assert audit_log is not None
        assert audit_log.action == "update"
        assert audit_log.outcome == "success"

    @pytest.mark.asyncio
    async def test_update_suspended_tenant_forbidden(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
        mfa_user_data: dict[str, Any],
    ) -> None:
        """Test that suspended tenant cannot update settings."""
        # Create suspended tenant
        tenant = TenantFactory(subscription_status=SubscriptionStatus.SUSPENDED)
        user = UserFactory(email=mfa_user_data["email"])
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id=mfa_user_data["clerk_id"],
            role=UserRole.ADMIN,
        )

        db_session.add(tenant)
        db_session.add(user)
        db_session.add(practice_user)
        await db_session.flush()

        # Mock JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub=mfa_user_data["clerk_id"],
                tenant_id=tenant.id,
                role="admin",
                exp=9999999999,
                iat=1234567890,
            )

            response = await test_client.patch(
                "/api/v1/auth/tenant/settings",
                json={"mfa_required": True},
                headers={"Authorization": "Bearer mock_token"},
            )

        assert response.status_code == 403
        assert "suspended" in response.json()["detail"].lower()


# =============================================================================
# User MFA Status Tests
# =============================================================================


class TestUserMfaStatus:
    """Tests for user MFA status tracking."""

    @pytest.mark.asyncio
    async def test_user_mfa_status_in_me_response(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
        mfa_user_data: dict[str, Any],
    ) -> None:
        """Test that /me endpoint returns user's mfa_enabled status."""
        # Create user with MFA enabled
        tenant = TenantFactory()
        user = UserFactory(email=mfa_user_data["email"])
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id=mfa_user_data["clerk_id"],
            role=UserRole.ADMIN,
            mfa_enabled=True,
        )

        db_session.add(tenant)
        db_session.add(user)
        db_session.add(practice_user)
        await db_session.flush()

        # Mock JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub=mfa_user_data["clerk_id"],
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
        assert data["user"]["mfa_enabled"] is True

    @pytest.mark.asyncio
    async def test_sync_updates_mfa_status_from_clerk(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
        mfa_user_data: dict[str, Any],
    ) -> None:
        """Test that /sync endpoint updates MFA status from Clerk."""
        # Create user with MFA disabled locally
        tenant = TenantFactory()
        user = UserFactory(email=mfa_user_data["email"])
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id=mfa_user_data["clerk_id"],
            role=UserRole.ADMIN,
            mfa_enabled=False,
        )

        db_session.add(tenant)
        db_session.add(user)
        db_session.add(practice_user)
        await db_session.flush()

        # Mock JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub=mfa_user_data["clerk_id"],
                tenant_id=tenant.id,
                role="admin",
                exp=9999999999,
                iat=1234567890,
            )

            # Mock Clerk API to return MFA enabled
            with patch("app.modules.auth.service.AuthService._get_clerk_user") as mock_get_user:
                mock_clerk_user = MagicMock()
                mock_clerk_user.has_mfa_enabled = True
                mock_get_user.return_value = mock_clerk_user

                response = await test_client.post(
                    "/api/v1/auth/sync",
                    headers={"Authorization": "Bearer mock_token"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["mfa_enabled"] is True
