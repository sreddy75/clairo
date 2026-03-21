"""Integration tests for admin usage endpoints.

Tests for aggregate usage statistics, upsell opportunities,
and tenant usage details.

Spec 020: Usage Tracking & Limits
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import (
    PracticeUser,
    SubscriptionStatus,
    SubscriptionTier,
    Tenant,
    User,
    UserRole,
    UserType,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def admin_tenant(db_session: AsyncSession) -> Tenant:
    """Create a tenant with an admin user for testing."""
    tenant = Tenant(
        id=uuid4(),
        name="Admin Practice",
        slug="admin-practice",
        tier=SubscriptionTier.PROFESSIONAL,
        subscription_status=SubscriptionStatus.ACTIVE,
        owner_email="admin@test.com",
        stripe_customer_id="cus_admin123",
        stripe_subscription_id="sub_admin123",
        client_count=50,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def admin_base_user(db_session: AsyncSession) -> User:
    """Create a base user for the admin practice user."""
    user = User(
        id=uuid4(),
        email="admin@test.com",
        user_type=UserType.PRACTICE_USER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def admin_practice_user(
    db_session: AsyncSession,
    admin_tenant: Tenant,
    admin_base_user: User,
) -> PracticeUser:
    """Create an admin practice user."""
    practice_user = PracticeUser(
        id=uuid4(),
        user_id=admin_base_user.id,
        tenant_id=admin_tenant.id,
        clerk_id=f"clerk_{uuid4().hex[:12]}",
        role=UserRole.ADMIN,
    )
    db_session.add(practice_user)
    await db_session.flush()
    return practice_user


@pytest.fixture
def admin_auth_headers(
    admin_practice_user: PracticeUser,
    admin_tenant: Tenant,
) -> dict[str, str]:
    """Create auth headers for admin user."""
    from app.core.security import create_access_token

    token = create_access_token(
        user_id=str(admin_practice_user.id),
        tenant_id=str(admin_tenant.id),
        roles=["admin"],
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def non_admin_base_user(db_session: AsyncSession) -> User:
    """Create a base user for the non-admin practice user."""
    user = User(
        id=uuid4(),
        email="accountant@test.com",
        user_type=UserType.PRACTICE_USER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def non_admin_practice_user(
    db_session: AsyncSession,
    admin_tenant: Tenant,
    non_admin_base_user: User,
) -> PracticeUser:
    """Create a non-admin practice user."""
    practice_user = PracticeUser(
        id=uuid4(),
        user_id=non_admin_base_user.id,
        tenant_id=admin_tenant.id,
        clerk_id=f"clerk_{uuid4().hex[:12]}",
        role=UserRole.ACCOUNTANT,
    )
    db_session.add(practice_user)
    await db_session.flush()
    return practice_user


@pytest.fixture
def non_admin_auth_headers(
    non_admin_practice_user: PracticeUser,
    admin_tenant: Tenant,
) -> dict[str, str]:
    """Create auth headers for non-admin user."""
    from app.core.security import create_access_token

    token = create_access_token(
        user_id=str(non_admin_practice_user.id),
        tenant_id=str(admin_tenant.id),
        roles=["accountant"],
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def multiple_tenants(db_session: AsyncSession) -> list[Tenant]:
    """Create multiple tenants for aggregate stats testing."""
    tenants = [
        # Starter tier at 80%
        Tenant(
            id=uuid4(),
            name="Starter Practice 1",
            slug="starter-practice-1",
            tier=SubscriptionTier.STARTER,
            subscription_status=SubscriptionStatus.ACTIVE,
            owner_email="starter1@test.com",
            client_count=20,  # 80% of 25
        ),
        # Starter tier at 100%
        Tenant(
            id=uuid4(),
            name="Starter Practice 2",
            slug="starter-practice-2",
            tier=SubscriptionTier.STARTER,
            subscription_status=SubscriptionStatus.ACTIVE,
            owner_email="starter2@test.com",
            client_count=25,  # 100% of 25
        ),
        # Professional tier at 50%
        Tenant(
            id=uuid4(),
            name="Professional Practice 1",
            slug="professional-practice-1",
            tier=SubscriptionTier.PROFESSIONAL,
            subscription_status=SubscriptionStatus.ACTIVE,
            owner_email="pro1@test.com",
            client_count=50,  # 50% of 100
        ),
        # Growth tier at 90%
        Tenant(
            id=uuid4(),
            name="Growth Practice 1",
            slug="growth-practice-1",
            tier=SubscriptionTier.GROWTH,
            subscription_status=SubscriptionStatus.ACTIVE,
            owner_email="growth1@test.com",
            client_count=225,  # 90% of 250
        ),
        # Enterprise tier (unlimited)
        Tenant(
            id=uuid4(),
            name="Enterprise Practice 1",
            slug="enterprise-practice-1",
            tier=SubscriptionTier.ENTERPRISE,
            subscription_status=SubscriptionStatus.ACTIVE,
            owner_email="enterprise1@test.com",
            client_count=500,
        ),
    ]
    for tenant in tenants:
        db_session.add(tenant)
    await db_session.flush()
    return tenants


# =============================================================================
# Admin Usage Stats Tests
# =============================================================================


@pytest.mark.integration
class TestGetUsageStats:
    """Tests for GET /api/v1/admin/usage/stats."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.get("/api/v1/admin/usage/stats")
        assert response.status_code == 401

    async def test_non_admin_returns_403(
        self,
        test_client: AsyncClient,
        non_admin_auth_headers: dict[str, str],
    ) -> None:
        """Non-admin user should get 403."""
        response = await test_client.get(
            "/api/v1/admin/usage/stats",
            headers=non_admin_auth_headers,
        )
        assert response.status_code == 403

    async def test_returns_aggregate_stats(
        self,
        test_client: AsyncClient,
        admin_auth_headers: dict[str, str],
        multiple_tenants: list[Tenant],
    ) -> None:
        """Should return aggregate usage statistics."""
        response = await test_client.get(
            "/api/v1/admin/usage/stats",
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert "total_tenants" in data
        assert "total_clients" in data
        assert "average_clients_per_tenant" in data
        assert "tenants_at_limit" in data
        assert "tenants_approaching_limit" in data
        assert "tenants_by_tier" in data

    async def test_stats_include_tier_distribution(
        self,
        test_client: AsyncClient,
        admin_auth_headers: dict[str, str],
        multiple_tenants: list[Tenant],
    ) -> None:
        """Should include tenant count by tier."""
        response = await test_client.get(
            "/api/v1/admin/usage/stats",
            headers=admin_auth_headers,
        )

        data = response.json()
        assert "starter" in data["tenants_by_tier"]
        assert "professional" in data["tenants_by_tier"]
        assert "growth" in data["tenants_by_tier"]
        assert "enterprise" in data["tenants_by_tier"]


# =============================================================================
# Admin Upsell Opportunities Tests
# =============================================================================


@pytest.mark.integration
class TestGetUpsellOpportunities:
    """Tests for GET /api/v1/admin/usage/opportunities."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.get("/api/v1/admin/usage/opportunities")
        assert response.status_code == 401

    async def test_non_admin_returns_403(
        self,
        test_client: AsyncClient,
        non_admin_auth_headers: dict[str, str],
    ) -> None:
        """Non-admin user should get 403."""
        response = await test_client.get(
            "/api/v1/admin/usage/opportunities",
            headers=non_admin_auth_headers,
        )
        assert response.status_code == 403

    async def test_returns_opportunities(
        self,
        test_client: AsyncClient,
        admin_auth_headers: dict[str, str],
        multiple_tenants: list[Tenant],
    ) -> None:
        """Should return upsell opportunities."""
        response = await test_client.get(
            "/api/v1/admin/usage/opportunities",
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "opportunities" in data
        assert "total" in data
        assert isinstance(data["opportunities"], list)

    async def test_default_threshold_80_percent(
        self,
        test_client: AsyncClient,
        admin_auth_headers: dict[str, str],
        multiple_tenants: list[Tenant],
    ) -> None:
        """Default threshold should be 80%."""
        response = await test_client.get(
            "/api/v1/admin/usage/opportunities",
            headers=admin_auth_headers,
        )

        data = response.json()
        # Should include tenants at 80%, 90%, and 100%
        # But NOT the one at 50%, and NOT enterprise (unlimited)
        for opp in data["opportunities"]:
            assert opp["percentage_used"] >= 80

    async def test_custom_threshold(
        self,
        test_client: AsyncClient,
        admin_auth_headers: dict[str, str],
        multiple_tenants: list[Tenant],
    ) -> None:
        """Should respect custom threshold parameter."""
        response = await test_client.get(
            "/api/v1/admin/usage/opportunities?threshold=90",
            headers=admin_auth_headers,
        )

        data = response.json()
        for opp in data["opportunities"]:
            assert opp["percentage_used"] >= 90

    async def test_tier_filter(
        self,
        test_client: AsyncClient,
        admin_auth_headers: dict[str, str],
        multiple_tenants: list[Tenant],
    ) -> None:
        """Should filter by tier when specified."""
        response = await test_client.get(
            "/api/v1/admin/usage/opportunities?tier=starter",
            headers=admin_auth_headers,
        )

        data = response.json()
        for opp in data["opportunities"]:
            assert opp["current_tier"] == "starter"

    async def test_opportunities_sorted_by_percentage(
        self,
        test_client: AsyncClient,
        admin_auth_headers: dict[str, str],
        multiple_tenants: list[Tenant],
    ) -> None:
        """Opportunities should be sorted by percentage descending."""
        response = await test_client.get(
            "/api/v1/admin/usage/opportunities",
            headers=admin_auth_headers,
        )

        data = response.json()
        percentages = [o["percentage_used"] for o in data["opportunities"]]
        assert percentages == sorted(percentages, reverse=True)

    async def test_opportunities_exclude_enterprise(
        self,
        test_client: AsyncClient,
        admin_auth_headers: dict[str, str],
        multiple_tenants: list[Tenant],
    ) -> None:
        """Enterprise tier should not appear in opportunities (unlimited)."""
        response = await test_client.get(
            "/api/v1/admin/usage/opportunities?threshold=1",  # Very low threshold
            headers=admin_auth_headers,
        )

        data = response.json()
        for opp in data["opportunities"]:
            assert opp["current_tier"] != "enterprise"

    async def test_opportunity_fields(
        self,
        test_client: AsyncClient,
        admin_auth_headers: dict[str, str],
        multiple_tenants: list[Tenant],
    ) -> None:
        """Each opportunity should have required fields."""
        response = await test_client.get(
            "/api/v1/admin/usage/opportunities",
            headers=admin_auth_headers,
        )

        data = response.json()
        if data["opportunities"]:
            opp = data["opportunities"][0]
            assert "tenant_id" in opp
            assert "tenant_name" in opp
            assert "owner_email" in opp
            assert "current_tier" in opp
            assert "client_count" in opp
            assert "client_limit" in opp
            assert "percentage_used" in opp


# =============================================================================
# Admin Tenant Usage Details Tests
# =============================================================================


@pytest.mark.integration
class TestGetTenantUsageDetails:
    """Tests for GET /api/v1/admin/usage/tenant/{tenant_id}."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.get(f"/api/v1/admin/usage/tenant/{uuid4()}")
        assert response.status_code == 401

    async def test_non_admin_returns_403(
        self,
        test_client: AsyncClient,
        non_admin_auth_headers: dict[str, str],
    ) -> None:
        """Non-admin user should get 403."""
        response = await test_client.get(
            f"/api/v1/admin/usage/tenant/{uuid4()}",
            headers=non_admin_auth_headers,
        )
        assert response.status_code == 403

    async def test_unknown_tenant_returns_404(
        self,
        test_client: AsyncClient,
        admin_auth_headers: dict[str, str],
    ) -> None:
        """Unknown tenant ID should return 404."""
        response = await test_client.get(
            f"/api/v1/admin/usage/tenant/{uuid4()}",
            headers=admin_auth_headers,
        )
        assert response.status_code == 404

    async def test_returns_tenant_details(
        self,
        test_client: AsyncClient,
        admin_auth_headers: dict[str, str],
        admin_tenant: Tenant,
    ) -> None:
        """Should return detailed usage for a tenant."""
        response = await test_client.get(
            f"/api/v1/admin/usage/tenant/{admin_tenant.id}",
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert data["tenant_id"] == str(admin_tenant.id)
        assert data["tenant_name"] == admin_tenant.name
        assert "tier" in data
        assert "usage" in data
        assert "history" in data
        assert "alerts" in data

    async def test_usage_metrics_included(
        self,
        test_client: AsyncClient,
        admin_auth_headers: dict[str, str],
        admin_tenant: Tenant,
    ) -> None:
        """Should include full usage metrics."""
        response = await test_client.get(
            f"/api/v1/admin/usage/tenant/{admin_tenant.id}",
            headers=admin_auth_headers,
        )

        data = response.json()
        usage = data["usage"]

        assert "client_count" in usage
        assert "client_limit" in usage
        assert "ai_queries_month" in usage
        assert "documents_month" in usage
        assert "is_at_limit" in usage
        assert "is_approaching_limit" in usage
        assert "tier" in usage
        assert "next_tier" in usage

    async def test_history_is_list(
        self,
        test_client: AsyncClient,
        admin_auth_headers: dict[str, str],
        admin_tenant: Tenant,
    ) -> None:
        """History should be a list (possibly empty)."""
        response = await test_client.get(
            f"/api/v1/admin/usage/tenant/{admin_tenant.id}",
            headers=admin_auth_headers,
        )

        data = response.json()
        assert isinstance(data["history"], list)

    async def test_alerts_is_list(
        self,
        test_client: AsyncClient,
        admin_auth_headers: dict[str, str],
        admin_tenant: Tenant,
    ) -> None:
        """Alerts should be a list (possibly empty)."""
        response = await test_client.get(
            f"/api/v1/admin/usage/tenant/{admin_tenant.id}",
            headers=admin_auth_headers,
        )

        data = response.json()
        assert isinstance(data["alerts"], list)
