"""Integration tests for portal API endpoints.

Tests cover:
- Portal invitation creation and magic link flow
- Portal session management
- Magic link verification
- Token refresh

Spec: 030-client-portal-document-requests
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.portal.auth.magic_link import generate_secure_token, hash_token
from app.modules.portal.enums import InvitationStatus
from app.modules.portal.models import PortalInvitation, PortalSession
from tests.factories.auth import PracticeUserFactory, TenantFactory, UserFactory
from tests.factories.portal import (
    PortalInvitationFactory,
    SentInvitationFactory,
)
from tests.factories.xero import XeroConnectionFactory

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_clerk_payload():
    """Create mock Clerk JWT payload."""
    return {
        "sub": "user_test_clerk_123",
        "email": "accountant@example.com",
        "email_verified": True,
        "exp": 9999999999,
        "iat": 1234567890,
    }


# =============================================================================
# Portal Invitation Tests
# =============================================================================


@pytest.mark.integration
class TestCreateInvitation:
    """Tests for POST /api/v1/portal/clients/{connection_id}/invite."""

    @pytest.mark.asyncio
    async def test_create_invitation_success(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Creating an invitation returns magic link URL."""
        # Create test data
        tenant = TenantFactory()
        user = UserFactory()
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id="user_test_clerk_create",
        )
        connection = XeroConnectionFactory(tenant_id=tenant.id)

        db_session.add_all([tenant, user, practice_user, connection])
        await db_session.flush()

        # Mock JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub="user_test_clerk_create",
                email="accountant@example.com",
                tenant_id=tenant.id,
                exp=9999999999,
                iat=1234567890,
            )

            response = await test_client.post(
                f"/api/v1/portal/clients/{connection.id}/invite",
                json={"email": "client@business.com"},
                headers={"Authorization": "Bearer mock_token"},
            )

        assert response.status_code == 201
        data = response.json()
        assert "magic_link_url" in data
        assert "invitation" in data
        assert data["invitation"]["email"] == "client@business.com"
        assert data["invitation"]["status"] == InvitationStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_create_invitation_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Creating invitation without auth returns 401."""
        connection_id = uuid4()
        response = await test_client.post(
            f"/api/v1/portal/clients/{connection_id}/invite",
            json={"email": "client@business.com"},
        )
        assert response.status_code == 401


@pytest.mark.integration
class TestListInvitations:
    """Tests for GET /api/v1/portal/clients/{connection_id}/invitations."""

    @pytest.mark.asyncio
    async def test_list_invitations_success(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Listing invitations returns paginated results."""
        # Create test data
        tenant = TenantFactory()
        user = UserFactory()
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id="user_test_clerk_list",
        )
        connection = XeroConnectionFactory(tenant_id=tenant.id)

        # Create invitations
        invitation1 = PortalInvitationFactory(
            tenant_id=tenant.id,
            connection_id=connection.id,
            email="client1@example.com",
        )
        invitation2 = SentInvitationFactory(
            tenant_id=tenant.id,
            connection_id=connection.id,
            email="client2@example.com",
        )

        db_session.add_all([tenant, user, practice_user, connection, invitation1, invitation2])
        await db_session.flush()

        # Mock JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub="user_test_clerk_list",
                email="accountant@example.com",
                tenant_id=tenant.id,
                exp=9999999999,
                iat=1234567890,
            )

            response = await test_client.get(
                f"/api/v1/portal/clients/{connection.id}/invitations",
                headers={"Authorization": "Bearer mock_token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "invitations" in data
        assert len(data["invitations"]) >= 1


@pytest.mark.integration
class TestPortalAccessStatus:
    """Tests for GET /api/v1/portal/clients/{connection_id}/portal-access."""

    @pytest.mark.asyncio
    async def test_get_portal_access_status_no_access(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Get status when client has no portal access."""
        # Create test data
        tenant = TenantFactory()
        user = UserFactory()
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id="user_test_clerk_status",
        )
        connection = XeroConnectionFactory(tenant_id=tenant.id)

        db_session.add_all([tenant, user, practice_user, connection])
        await db_session.flush()

        # Mock JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub="user_test_clerk_status",
                email="accountant@example.com",
                tenant_id=tenant.id,
                exp=9999999999,
                iat=1234567890,
            )

            response = await test_client.get(
                f"/api/v1/portal/clients/{connection.id}/portal-access",
                headers={"Authorization": "Bearer mock_token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["has_access"] is False
        assert data["active_sessions"] == 0


@pytest.mark.integration
class TestRevokePortalAccess:
    """Tests for DELETE /api/v1/portal/clients/{connection_id}/portal-access."""

    @pytest.mark.asyncio
    async def test_revoke_portal_access_success(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Revoking access returns success message."""
        # Create test data
        tenant = TenantFactory()
        user = UserFactory()
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id="user_test_clerk_revoke",
        )
        connection = XeroConnectionFactory(tenant_id=tenant.id)

        db_session.add_all([tenant, user, practice_user, connection])
        await db_session.flush()

        # Mock JWT validation
        with patch("app.modules.auth.middleware.JWTMiddleware._validate_token") as mock_validate:
            from app.modules.auth.clerk import ClerkTokenPayload

            mock_validate.return_value = ClerkTokenPayload(
                sub="user_test_clerk_revoke",
                email="accountant@example.com",
                tenant_id=tenant.id,
                exp=9999999999,
                iat=1234567890,
            )

            response = await test_client.delete(
                f"/api/v1/portal/clients/{connection.id}/portal-access",
                headers={"Authorization": "Bearer mock_token"},
                params={"reason": "Client relationship ended"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Portal access revoked"


# =============================================================================
# Magic Link Verification Tests
# =============================================================================


@pytest.mark.integration
class TestMagicLinkVerification:
    """Tests for POST /api/v1/client-portal/auth/verify."""

    @pytest.mark.asyncio
    async def test_verify_magic_link_success(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Verifying valid magic link creates session and returns tokens."""
        # Create test data
        tenant = TenantFactory()
        connection = XeroConnectionFactory(tenant_id=tenant.id)

        # Create invitation with known token
        token = generate_secure_token()
        token_hash = hash_token(token)
        invitation = PortalInvitation(
            tenant_id=tenant.id,
            connection_id=connection.id,
            email="client@business.com",
            token_hash=token_hash,
            status=InvitationStatus.SENT.value,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            invited_by=uuid4(),
        )

        db_session.add_all([tenant, connection, invitation])
        await db_session.flush()
        await db_session.commit()

        # Verify magic link
        response = await test_client.post(
            "/api/v1/client-portal/auth/verify",
            json={
                "token": token,
                "device_fingerprint": "test-device-fp",
                "user_agent": "Test Browser/1.0",
                "ip_address": "192.168.1.1",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["connection_id"] == str(connection.id)
        assert data["tenant_id"] == str(tenant.id)

    @pytest.mark.asyncio
    async def test_verify_magic_link_invalid_token(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Verifying invalid token returns 404."""
        response = await test_client.post(
            "/api/v1/client-portal/auth/verify",
            json={"token": generate_secure_token()},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_verify_magic_link_expired(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Verifying expired magic link returns 410."""
        # Create test data
        tenant = TenantFactory()
        connection = XeroConnectionFactory(tenant_id=tenant.id)

        # Create expired invitation
        token = generate_secure_token()
        token_hash = hash_token(token)
        invitation = PortalInvitation(
            tenant_id=tenant.id,
            connection_id=connection.id,
            email="client@business.com",
            token_hash=token_hash,
            status=InvitationStatus.SENT.value,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
            invited_by=uuid4(),
        )

        db_session.add_all([tenant, connection, invitation])
        await db_session.flush()
        await db_session.commit()

        response = await test_client.post(
            "/api/v1/client-portal/auth/verify",
            json={"token": token},
        )

        assert response.status_code == 410
        assert "expired" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_verify_magic_link_already_used(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Verifying already-used magic link returns 409."""
        # Create test data
        tenant = TenantFactory()
        connection = XeroConnectionFactory(tenant_id=tenant.id)

        # Create already accepted invitation
        token = generate_secure_token()
        token_hash = hash_token(token)
        invitation = PortalInvitation(
            tenant_id=tenant.id,
            connection_id=connection.id,
            email="client@business.com",
            token_hash=token_hash,
            status=InvitationStatus.ACCEPTED.value,  # Already used
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            invited_by=uuid4(),
            accepted_at=datetime.now(timezone.utc),
        )

        db_session.add_all([tenant, connection, invitation])
        await db_session.flush()
        await db_session.commit()

        response = await test_client.post(
            "/api/v1/client-portal/auth/verify",
            json={"token": token},
        )

        assert response.status_code == 409
        assert "already been used" in response.json()["detail"].lower()


# =============================================================================
# Token Refresh Tests
# =============================================================================


@pytest.mark.integration
class TestTokenRefresh:
    """Tests for POST /api/v1/client-portal/auth/refresh."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Refreshing valid token returns new access token."""
        # Create test data
        tenant = TenantFactory()
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

        response = await test_client.post(
            "/api/v1/client-portal/auth/refresh",
            json={
                "refresh_token": refresh_token,
                "ip_address": "192.168.1.1",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "expires_at" in data

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Refreshing invalid token returns 401."""
        response = await test_client.post(
            "/api/v1/client-portal/auth/refresh",
            json={"refresh_token": generate_secure_token()},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_revoked_session(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Refreshing revoked session returns 403."""
        # Create test data
        tenant = TenantFactory()
        connection = XeroConnectionFactory(tenant_id=tenant.id)

        # Create revoked session
        refresh_token = generate_secure_token()
        refresh_token_hash = hash_token(refresh_token)
        session = PortalSession(
            connection_id=connection.id,
            tenant_id=tenant.id,
            refresh_token_hash=refresh_token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            revoked=True,
            revoked_at=datetime.now(timezone.utc),
            revoke_reason="Access revoked",
        )

        db_session.add_all([tenant, connection, session])
        await db_session.flush()
        await db_session.commit()

        response = await test_client.post(
            "/api/v1/client-portal/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 403
        assert "revoked" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_refresh_token_expired_session(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Refreshing expired session returns 401."""
        # Create test data
        tenant = TenantFactory()
        connection = XeroConnectionFactory(tenant_id=tenant.id)

        # Create expired session
        refresh_token = generate_secure_token()
        refresh_token_hash = hash_token(refresh_token)
        session = PortalSession(
            connection_id=connection.id,
            tenant_id=tenant.id,
            refresh_token_hash=refresh_token_hash,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),  # Expired
            revoked=False,
        )

        db_session.add_all([tenant, connection, session])
        await db_session.flush()
        await db_session.commit()

        response = await test_client.post(
            "/api/v1/client-portal/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()


# =============================================================================
# Portal Health Check Tests
# =============================================================================


@pytest.mark.integration
class TestPortalHealth:
    """Tests for portal health check endpoints."""

    @pytest.mark.asyncio
    async def test_portal_health_check(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Portal health check returns OK."""
        response = await test_client.get("/api/v1/portal/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["module"] == "portal"

    @pytest.mark.asyncio
    async def test_client_portal_health_check(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Client portal health check returns OK."""
        response = await test_client.get("/api/v1/client-portal/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["module"] == "client-portal"


# =============================================================================
# Portal Auth Endpoint Tests
# =============================================================================


@pytest.mark.integration
class TestRequestMagicLink:
    """Tests for POST /api/v1/client-portal/auth/request-link."""

    @pytest.mark.asyncio
    async def test_request_link_returns_generic_message(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Requesting magic link returns generic message (for security)."""
        response = await test_client.post(
            "/api/v1/client-portal/auth/request-link",
            json={"email": "client@business.com"},
        )

        assert response.status_code == 200
        data = response.json()
        # Message should be vague for security (no email enumeration)
        assert "message" in data
        assert "portal access" in data["message"].lower() or "magic link" in data["message"].lower()


@pytest.mark.integration
class TestPortalLogout:
    """Tests for POST /api/v1/client-portal/auth/logout."""

    @pytest.mark.asyncio
    async def test_logout_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Logout requires authentication."""
        response = await test_client.post(
            "/api/v1/client-portal/auth/logout",
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_success(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Logout with valid session succeeds."""
        # Create test data
        tenant = TenantFactory()
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

        # First get an access token via refresh
        token_response = await test_client.post(
            "/api/v1/client-portal/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert token_response.status_code == 200
        access_token = token_response.json()["access_token"]

        # Now logout
        logout_response = await test_client.post(
            "/api/v1/client-portal/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert logout_response.status_code == 200
        assert "logged out" in logout_response.json()["message"].lower()


@pytest.mark.integration
class TestPortalSessionInfo:
    """Tests for GET /api/v1/client-portal/auth/me."""

    @pytest.mark.asyncio
    async def test_me_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Session info requires authentication."""
        response = await test_client.get(
            "/api/v1/client-portal/auth/me",
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_me_returns_session_info(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Session info returns connection and tenant IDs."""
        # Create test data
        tenant = TenantFactory()
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

        # Get session info
        me_response = await test_client.get(
            "/api/v1/client-portal/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert me_response.status_code == 200
        data = me_response.json()
        assert data["connection_id"] == str(connection.id)
        assert data["tenant_id"] == str(tenant.id)
        assert data["is_authenticated"] is True


# =============================================================================
# Portal Dashboard Tests
# =============================================================================


@pytest.mark.integration
class TestPortalDashboard:
    """Tests for GET /api/v1/portal/dashboard endpoints."""

    @pytest.mark.asyncio
    async def test_get_dashboard_success(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Authenticated client can get dashboard."""
        # Create test data
        tenant = TenantFactory()
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

        # Get dashboard
        response = await test_client.get(
            "/api/v1/portal/dashboard",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["connection_id"] == str(connection.id)
        assert data["organization_name"] == connection.organization_name
        assert "pending_requests" in data
        assert "unread_requests" in data
        assert "total_documents" in data
        assert "recent_requests" in data

    @pytest.mark.asyncio
    async def test_get_dashboard_unauthenticated(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await test_client.get("/api/v1/portal/dashboard")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_bas_status_success(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Authenticated client can get BAS status."""
        # Create test data
        tenant = TenantFactory()
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

        # Get BAS status
        response = await test_client.get(
            "/api/v1/portal/dashboard/bas-status",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "connection_id" in data
        assert "current_quarter" in data
        assert "status" in data

    @pytest.mark.asyncio
    async def test_get_recent_activity_success(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Authenticated client can get recent activity."""
        # Create test data
        tenant = TenantFactory()
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

        # Get recent activity
        response = await test_client.get(
            "/api/v1/portal/dashboard/activity",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
