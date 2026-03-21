"""Integration tests for onboarding API endpoints.

Tests for:
- Onboarding progress management
- Tier selection
- Xero connection
- Bulk client import
- Product tour
- Checklist management
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import PracticeUser, SubscriptionStatus, SubscriptionTier, Tenant
from app.modules.onboarding.models import OnboardingProgress, OnboardingStatus

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def test_tenant(db_session: AsyncSession) -> Tenant:
    """Create a test tenant for onboarding tests."""
    tenant = Tenant(
        id=uuid4(),
        name="Test Practice",
        slug="test-practice",
        tier=SubscriptionTier.STARTER,
        subscription_status=SubscriptionStatus.TRIAL,
        owner_email="owner@test.com",
        client_count=0,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def test_tenant_with_progress(db_session: AsyncSession) -> tuple[Tenant, OnboardingProgress]:
    """Create a test tenant with onboarding progress."""
    tenant = Tenant(
        id=uuid4(),
        name="Test Practice With Progress",
        slug="test-practice-progress",
        tier=SubscriptionTier.PROFESSIONAL,
        subscription_status=SubscriptionStatus.ACTIVE,
        owner_email="owner@test.com",
        stripe_customer_id="cus_test123",
        client_count=5,
    )
    db_session.add(tenant)
    await db_session.flush()

    progress = OnboardingProgress(
        id=uuid4(),
        tenant_id=tenant.id,
        status=OnboardingStatus.PAYMENT_SETUP,
        current_step="connect_xero",
        started_at=datetime.now(UTC),
        tier_selected_at=datetime.now(UTC),
        payment_setup_at=datetime.now(UTC),
    )
    db_session.add(progress)
    await db_session.flush()

    return tenant, progress


@pytest.fixture
async def test_practice_user(db_session: AsyncSession, test_tenant: Tenant) -> PracticeUser:
    """Create a practice user for the test tenant."""
    user = PracticeUser(
        id=uuid4(),
        tenant_id=test_tenant.id,
        clerk_user_id=f"clerk_{uuid4().hex[:12]}",
        email="user@test.com",
        name="Test User",
        role="owner",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
def auth_headers_for_tenant(
    test_practice_user: PracticeUser, test_tenant: Tenant
) -> dict[str, str]:
    """Create auth headers for the test tenant."""
    from app.core.security import create_access_token

    token = create_access_token(
        user_id=str(test_practice_user.id),
        tenant_id=str(test_tenant.id),
        roles=["owner"],
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def auth_headers_with_progress(
    db_session: AsyncSession,
    test_tenant_with_progress: tuple[Tenant, OnboardingProgress],
) -> dict[str, str]:
    """Create auth headers for tenant with progress."""
    from app.core.security import create_access_token

    tenant, _ = test_tenant_with_progress
    user = PracticeUser(
        id=uuid4(),
        tenant_id=tenant.id,
        clerk_user_id=f"clerk_{uuid4().hex[:12]}",
        email="user@test.com",
        name="Test User",
        role="owner",
    )
    db_session.add(user)
    await db_session.flush()

    token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(tenant.id),
        roles=["owner"],
    )
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Progress Endpoints Tests
# =============================================================================


@pytest.mark.integration
class TestGetOnboardingProgress:
    """Tests for GET /api/v1/onboarding/progress."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.get("/api/v1/onboarding/progress")
        assert response.status_code == 401

    async def test_no_progress_returns_404(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Should return 404 when no progress exists."""
        response = await test_client.get(
            "/api/v1/onboarding/progress",
            headers=auth_headers_for_tenant,
        )
        assert response.status_code == 404

    async def test_returns_progress(
        self,
        test_client: AsyncClient,
        auth_headers_with_progress: dict[str, str],
    ) -> None:
        """Should return progress when it exists."""
        response = await test_client.get(
            "/api/v1/onboarding/progress",
            headers=auth_headers_with_progress,
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "checklist" in data


@pytest.mark.integration
class TestStartOnboarding:
    """Tests for POST /api/v1/onboarding/start."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.post("/api/v1/onboarding/start")
        assert response.status_code == 401

    async def test_starts_onboarding(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Should start onboarding and return progress."""
        response = await test_client.post(
            "/api/v1/onboarding/start",
            headers=auth_headers_for_tenant,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "started"
        assert data["current_step"] == "start"


# =============================================================================
# Tier Selection Tests
# =============================================================================


@pytest.mark.integration
class TestSelectTier:
    """Tests for POST /api/v1/onboarding/tier."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.post(
            "/api/v1/onboarding/tier",
            json={
                "tier": "professional",
                "success_url": "https://test.com/success",
                "cancel_url": "https://test.com/cancel",
            },
        )
        assert response.status_code == 401

    async def test_invalid_tier_returns_422(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Invalid tier should return 422."""
        response = await test_client.post(
            "/api/v1/onboarding/tier",
            headers=auth_headers_for_tenant,
            json={
                "tier": "invalid_tier",
                "success_url": "https://test.com/success",
                "cancel_url": "https://test.com/cancel",
            },
        )
        assert response.status_code == 422

    @patch("app.modules.billing.service.BillingService.create_checkout_session")
    async def test_valid_tier_returns_checkout_url(
        self,
        mock_checkout: AsyncMock,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Valid tier should return checkout URL."""
        mock_checkout.return_value = ("https://checkout.stripe.com/...", "cs_test123")

        response = await test_client.post(
            "/api/v1/onboarding/tier",
            headers=auth_headers_for_tenant,
            json={
                "tier": "professional",
                "success_url": "https://test.com/success",
                "cancel_url": "https://test.com/cancel",
                "with_trial": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "checkout_url" in data
        assert "session_id" in data


# =============================================================================
# Xero Connection Tests
# =============================================================================


@pytest.mark.integration
class TestConnectXero:
    """Tests for POST /api/v1/onboarding/xero/connect."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.post("/api/v1/onboarding/xero/connect")
        assert response.status_code == 401

    async def test_returns_authorization_url(
        self,
        test_client: AsyncClient,
        auth_headers_with_progress: dict[str, str],
    ) -> None:
        """Should return Xero authorization URL."""
        response = await test_client.post(
            "/api/v1/onboarding/xero/connect",
            headers=auth_headers_with_progress,
        )
        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data


@pytest.mark.integration
class TestSkipXero:
    """Tests for POST /api/v1/onboarding/xero/skip."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.post("/api/v1/onboarding/xero/skip")
        assert response.status_code == 401

    async def test_skips_xero_connection(
        self,
        test_client: AsyncClient,
        auth_headers_with_progress: dict[str, str],
    ) -> None:
        """Should mark Xero as skipped."""
        response = await test_client.post(
            "/api/v1/onboarding/xero/skip",
            headers=auth_headers_with_progress,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["xero_skipped"] is True


# =============================================================================
# Client Import Tests
# =============================================================================


@pytest.mark.integration
class TestGetAvailableClients:
    """Tests for GET /api/v1/onboarding/clients/available."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.get("/api/v1/onboarding/clients/available")
        assert response.status_code == 401

    async def test_returns_available_clients(
        self,
        test_client: AsyncClient,
        auth_headers_with_progress: dict[str, str],
    ) -> None:
        """Should return list of available clients."""
        response = await test_client.get(
            "/api/v1/onboarding/clients/available",
            headers=auth_headers_with_progress,
        )
        assert response.status_code == 200
        data = response.json()
        assert "clients" in data
        assert "total" in data
        assert "tier_limit" in data


@pytest.mark.integration
class TestStartBulkImport:
    """Tests for POST /api/v1/onboarding/clients/import."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.post(
            "/api/v1/onboarding/clients/import",
            json={"client_ids": ["client1", "client2"]},
        )
        assert response.status_code == 401

    async def test_starts_bulk_import(
        self,
        test_client: AsyncClient,
        auth_headers_with_progress: dict[str, str],
    ) -> None:
        """Should start bulk import job."""
        response = await test_client.post(
            "/api/v1/onboarding/clients/import",
            headers=auth_headers_with_progress,
            json={"client_ids": ["client1", "client2"]},
        )
        assert response.status_code == 202
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"
        assert data["total_clients"] == 2


@pytest.mark.integration
class TestGetImportJobStatus:
    """Tests for GET /api/v1/onboarding/import/{job_id}."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        job_id = uuid4()
        response = await test_client.get(f"/api/v1/onboarding/import/{job_id}")
        assert response.status_code == 401

    async def test_job_not_found_returns_404(
        self,
        test_client: AsyncClient,
        auth_headers_with_progress: dict[str, str],
    ) -> None:
        """Should return 404 when job not found."""
        job_id = uuid4()
        response = await test_client.get(
            f"/api/v1/onboarding/import/{job_id}",
            headers=auth_headers_with_progress,
        )
        assert response.status_code == 404


# =============================================================================
# Tour Endpoints Tests
# =============================================================================


@pytest.mark.integration
class TestCompleteTour:
    """Tests for POST /api/v1/onboarding/tour/complete."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.post("/api/v1/onboarding/tour/complete")
        assert response.status_code == 401

    async def test_completes_tour(
        self,
        test_client: AsyncClient,
        auth_headers_with_progress: dict[str, str],
    ) -> None:
        """Should mark tour as completed."""
        response = await test_client.post(
            "/api/v1/onboarding/tour/complete",
            headers=auth_headers_with_progress,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tour_completed_at"] is not None


@pytest.mark.integration
class TestSkipTour:
    """Tests for POST /api/v1/onboarding/tour/skip."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.post("/api/v1/onboarding/tour/skip")
        assert response.status_code == 401

    async def test_skips_tour(
        self,
        test_client: AsyncClient,
        auth_headers_with_progress: dict[str, str],
    ) -> None:
        """Should mark tour as skipped."""
        response = await test_client.post(
            "/api/v1/onboarding/tour/skip",
            headers=auth_headers_with_progress,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tour_skipped"] is True


# =============================================================================
# Checklist Endpoints Tests
# =============================================================================


@pytest.mark.integration
class TestDismissChecklist:
    """Tests for POST /api/v1/onboarding/checklist/dismiss."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.post("/api/v1/onboarding/checklist/dismiss")
        assert response.status_code == 401

    async def test_dismisses_checklist(
        self,
        test_client: AsyncClient,
        auth_headers_with_progress: dict[str, str],
    ) -> None:
        """Should dismiss the onboarding checklist."""
        response = await test_client.post(
            "/api/v1/onboarding/checklist/dismiss",
            headers=auth_headers_with_progress,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["checklist"]["dismissed"] is True
