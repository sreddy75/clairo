"""Integration tests for billing endpoints.

Tests for subscription management, feature access, and billing API endpoints.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import PracticeUser, SubscriptionStatus, SubscriptionTier, Tenant

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def test_tenant(db_session: AsyncSession) -> Tenant:
    """Create a test tenant for billing tests."""
    tenant = Tenant(
        id=uuid4(),
        name="Test Practice",
        slug="test-practice",
        tier=SubscriptionTier.PROFESSIONAL,
        subscription_status=SubscriptionStatus.ACTIVE,
        owner_email="owner@test.com",
        stripe_customer_id="cus_test123",
        stripe_subscription_id="sub_test123",
        client_count=10,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def test_starter_tenant(db_session: AsyncSession) -> Tenant:
    """Create a starter tier tenant for feature gating tests."""
    tenant = Tenant(
        id=uuid4(),
        name="Starter Practice",
        slug="starter-practice",
        tier=SubscriptionTier.STARTER,
        subscription_status=SubscriptionStatus.ACTIVE,
        owner_email="starter@test.com",
        stripe_customer_id="cus_starter123",
        stripe_subscription_id="sub_starter123",
        client_count=5,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


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


# =============================================================================
# Public Endpoints
# =============================================================================


@pytest.mark.integration
class TestListTiers:
    """Tests for GET /api/v1/billing/features/tiers."""

    async def test_returns_all_tiers(self, test_client: AsyncClient) -> None:
        """Should return all subscription tiers."""
        response = await test_client.get("/api/v1/billing/features/tiers")

        assert response.status_code == 200
        data = response.json()
        assert "tiers" in data
        tier_names = [t["name"] for t in data["tiers"]]
        assert "starter" in tier_names
        assert "professional" in tier_names
        assert "growth" in tier_names
        assert "enterprise" in tier_names

    async def test_tiers_have_required_fields(self, test_client: AsyncClient) -> None:
        """Each tier should have required fields."""
        response = await test_client.get("/api/v1/billing/features/tiers")

        data = response.json()
        for tier in data["tiers"]:
            assert "name" in tier
            assert "display_name" in tier
            assert "price_monthly" in tier
            assert "features" in tier

    async def test_tier_features_structure(self, test_client: AsyncClient) -> None:
        """Tier features should have expected structure."""
        response = await test_client.get("/api/v1/billing/features/tiers")

        data = response.json()
        for tier in data["tiers"]:
            features = tier["features"]
            assert "max_clients" in features
            assert "ai_insights" in features
            assert "client_portal" in features
            assert "custom_triggers" in features


# =============================================================================
# Subscription Endpoints
# =============================================================================


@pytest.mark.integration
class TestGetSubscription:
    """Tests for GET /api/v1/billing/subscription."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.get("/api/v1/billing/subscription")
        assert response.status_code == 401

    async def test_returns_subscription_info(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
        test_tenant: Tenant,
    ) -> None:
        """Should return current subscription info."""
        with patch("app.modules.billing.router.stripe") as mock_stripe:
            mock_stripe.Subscription.retrieve.return_value = MagicMock(
                cancel_at_period_end=False,
                schedule=None,
            )

            response = await test_client.get(
                "/api/v1/billing/subscription",
                headers=auth_headers_for_tenant,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "professional"
        assert data["status"] == "active"
        assert "features" in data
        assert "usage" in data

    async def test_returns_feature_details(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Should return feature access details."""
        with patch("app.modules.billing.router.stripe"):
            response = await test_client.get(
                "/api/v1/billing/subscription",
                headers=auth_headers_for_tenant,
            )

        data = response.json()
        features = data["features"]
        assert features["client_portal"] is True
        assert features["magic_zone"] is True


@pytest.mark.integration
class TestCreateCheckoutSession:
    """Tests for POST /api/v1/billing/subscription/checkout."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.post(
            "/api/v1/billing/subscription/checkout",
            json={"tier": "professional"},
        )
        assert response.status_code == 401

    async def test_creates_checkout_session(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Should create Stripe checkout session."""
        with patch("app.modules.billing.service.StripeClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.create_checkout_session = AsyncMock(
                return_value=("https://checkout.stripe.com/test", "cs_test123")
            )
            mock_client.create_customer = AsyncMock(return_value="cus_new123")

            response = await test_client.post(
                "/api/v1/billing/subscription/checkout",
                headers=auth_headers_for_tenant,
                json={"tier": "growth"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "checkout_url" in data
        assert "session_id" in data

    async def test_enterprise_tier_rejected(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Enterprise tier should be rejected for self-service."""
        response = await test_client.post(
            "/api/v1/billing/subscription/checkout",
            headers=auth_headers_for_tenant,
            json={"tier": "enterprise"},
        )

        assert response.status_code == 400
        assert "Enterprise" in response.json()["detail"]


@pytest.mark.integration
class TestCreatePortalSession:
    """Tests for POST /api/v1/billing/subscription/portal."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.post("/api/v1/billing/subscription/portal")
        assert response.status_code == 401

    async def test_creates_portal_session(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Should create Stripe portal session."""
        with patch("app.modules.billing.service.StripeClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.create_portal_session = AsyncMock(
                return_value="https://billing.stripe.com/portal"
            )

            response = await test_client.post(
                "/api/v1/billing/subscription/portal",
                headers=auth_headers_for_tenant,
            )

        assert response.status_code == 200
        data = response.json()
        assert "portal_url" in data


# =============================================================================
# Features Endpoints
# =============================================================================


@pytest.mark.integration
class TestGetFeatures:
    """Tests for GET /api/v1/billing/features."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.get("/api/v1/billing/features")
        assert response.status_code == 401

    async def test_returns_feature_access(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Should return feature access map."""
        response = await test_client.get(
            "/api/v1/billing/features",
            headers=auth_headers_for_tenant,
        )

        assert response.status_code == 200
        data = response.json()
        assert "tier" in data
        assert "features" in data
        assert "can_access" in data
        assert isinstance(data["can_access"], dict)

    async def test_professional_tier_features(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Professional tier should have portal access."""
        response = await test_client.get(
            "/api/v1/billing/features",
            headers=auth_headers_for_tenant,
        )

        data = response.json()
        assert data["tier"] == "professional"
        assert data["can_access"]["client_portal"] is True
        assert data["can_access"]["magic_zone"] is True


@pytest.mark.integration
class TestStarterTierFeatureGating:
    """Tests for starter tier feature restrictions."""

    @pytest.fixture
    async def starter_auth_headers(
        self,
        db_session: AsyncSession,
        test_starter_tenant: Tenant,
    ) -> dict[str, str]:
        """Create auth headers for starter tier tenant."""
        user = PracticeUser(
            id=uuid4(),
            tenant_id=test_starter_tenant.id,
            clerk_user_id=f"clerk_{uuid4().hex[:12]}",
            email="starter@test.com",
            name="Starter User",
            role="owner",
        )
        db_session.add(user)
        await db_session.flush()

        from app.core.security import create_access_token

        token = create_access_token(
            user_id=str(user.id),
            tenant_id=str(test_starter_tenant.id),
            roles=["owner"],
        )
        return {"Authorization": f"Bearer {token}"}

    async def test_starter_tier_restricted_features(
        self,
        test_client: AsyncClient,
        starter_auth_headers: dict[str, str],
    ) -> None:
        """Starter tier should have restricted features."""
        response = await test_client.get(
            "/api/v1/billing/features",
            headers=starter_auth_headers,
        )

        data = response.json()
        assert data["tier"] == "starter"
        assert data["can_access"]["client_portal"] is False
        assert data["can_access"]["custom_triggers"] is False
        assert data["can_access"]["api_access"] is False


# =============================================================================
# Billing Events Endpoints
# =============================================================================


@pytest.mark.integration
class TestListBillingEvents:
    """Tests for GET /api/v1/billing/billing/events."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.get("/api/v1/billing/billing/events")
        assert response.status_code == 401

    async def test_returns_empty_events_list(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Should return empty events list for new tenant."""
        response = await test_client.get(
            "/api/v1/billing/billing/events",
            headers=auth_headers_for_tenant,
        )

        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "total" in data
        assert data["total"] == 0

    async def test_pagination_parameters(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Should respect pagination parameters."""
        response = await test_client.get(
            "/api/v1/billing/billing/events?limit=10&offset=5",
            headers=auth_headers_for_tenant,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 5


# =============================================================================
# Usage Endpoints (Spec 020)
# =============================================================================


@pytest.mark.integration
class TestGetUsage:
    """Tests for GET /api/v1/billing/billing/usage."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.get("/api/v1/billing/billing/usage")
        assert response.status_code == 401

    async def test_returns_usage_metrics(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
        test_tenant: Tenant,
    ) -> None:
        """Should return current usage metrics."""
        response = await test_client.get(
            "/api/v1/billing/billing/usage",
            headers=auth_headers_for_tenant,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert "client_count" in data
        assert "client_limit" in data
        assert "ai_queries_month" in data
        assert "documents_month" in data
        assert "is_at_limit" in data
        assert "is_approaching_limit" in data
        assert "tier" in data

    async def test_returns_correct_tier(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
        test_tenant: Tenant,
    ) -> None:
        """Should return correct tier from tenant."""
        response = await test_client.get(
            "/api/v1/billing/billing/usage",
            headers=auth_headers_for_tenant,
        )

        data = response.json()
        assert data["tier"] == "professional"
        assert data["client_limit"] == 100  # Professional tier limit

    async def test_returns_next_tier_for_upgrade(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Should include next tier for upgrade prompt."""
        response = await test_client.get(
            "/api/v1/billing/billing/usage",
            headers=auth_headers_for_tenant,
        )

        data = response.json()
        # Professional's next tier is Growth
        assert data["next_tier"] == "growth"

    async def test_threshold_warning_not_approaching(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Should not show threshold warning when not approaching limit."""
        response = await test_client.get(
            "/api/v1/billing/billing/usage",
            headers=auth_headers_for_tenant,
        )

        data = response.json()
        # test_tenant has 10 clients, limit is 100 (10%)
        assert data["is_approaching_limit"] is False
        assert data["threshold_warning"] is None

    @pytest.fixture
    async def tenant_at_80_percent(self, db_session: AsyncSession) -> tuple[Tenant, dict[str, str]]:
        """Create a tenant at 80% of client limit."""
        tenant = Tenant(
            id=uuid4(),
            name="At Limit Practice",
            slug="at-limit-practice",
            tier=SubscriptionTier.STARTER,  # Limit of 25
            subscription_status=SubscriptionStatus.ACTIVE,
            owner_email="atlimit@test.com",
            stripe_customer_id="cus_atlimit",
            stripe_subscription_id="sub_atlimit",
            client_count=20,  # 80% of 25
        )
        db_session.add(tenant)
        await db_session.flush()

        user = PracticeUser(
            id=uuid4(),
            tenant_id=tenant.id,
            clerk_user_id=f"clerk_{uuid4().hex[:12]}",
            email="atlimit@test.com",
            name="At Limit User",
            role="owner",
        )
        db_session.add(user)
        await db_session.flush()

        from app.core.security import create_access_token

        token = create_access_token(
            user_id=str(user.id),
            tenant_id=str(tenant.id),
            roles=["owner"],
        )
        return tenant, {"Authorization": f"Bearer {token}"}

    async def test_threshold_warning_at_80_percent(
        self,
        test_client: AsyncClient,
        tenant_at_80_percent: tuple[Tenant, dict[str, str]],
    ) -> None:
        """Should show 80% threshold warning when approaching limit."""
        _tenant, headers = tenant_at_80_percent

        response = await test_client.get(
            "/api/v1/billing/billing/usage",
            headers=headers,
        )

        data = response.json()
        assert data["is_approaching_limit"] is True
        assert data["threshold_warning"] == "80%"

    @pytest.fixture
    async def tenant_at_90_percent(self, db_session: AsyncSession) -> tuple[Tenant, dict[str, str]]:
        """Create a tenant at 90% of client limit."""
        tenant = Tenant(
            id=uuid4(),
            name="Near Limit Practice",
            slug="near-limit-practice",
            tier=SubscriptionTier.PROFESSIONAL,  # Limit of 100
            subscription_status=SubscriptionStatus.ACTIVE,
            owner_email="nearlimit@test.com",
            stripe_customer_id="cus_nearlimit",
            stripe_subscription_id="sub_nearlimit",
            client_count=90,  # 90% of 100
        )
        db_session.add(tenant)
        await db_session.flush()

        user = PracticeUser(
            id=uuid4(),
            tenant_id=tenant.id,
            clerk_user_id=f"clerk_{uuid4().hex[:12]}",
            email="nearlimit@test.com",
            name="Near Limit User",
            role="owner",
        )
        db_session.add(user)
        await db_session.flush()

        from app.core.security import create_access_token

        token = create_access_token(
            user_id=str(user.id),
            tenant_id=str(tenant.id),
            roles=["owner"],
        )
        return tenant, {"Authorization": f"Bearer {token}"}

    async def test_threshold_warning_at_90_percent(
        self,
        test_client: AsyncClient,
        tenant_at_90_percent: tuple[Tenant, dict[str, str]],
    ) -> None:
        """Should show 90% threshold warning when near limit."""
        _tenant, headers = tenant_at_90_percent

        response = await test_client.get(
            "/api/v1/billing/billing/usage",
            headers=headers,
        )

        data = response.json()
        assert data["is_approaching_limit"] is True
        assert data["threshold_warning"] == "90%"
        assert data["client_percentage"] == 90.0

    @pytest.fixture
    async def tenant_at_100_percent(
        self, db_session: AsyncSession
    ) -> tuple[Tenant, dict[str, str]]:
        """Create a tenant at 100% of client limit."""
        tenant = Tenant(
            id=uuid4(),
            name="At Limit Practice",
            slug="at-limit-practice-100",
            tier=SubscriptionTier.STARTER,  # Limit of 25
            subscription_status=SubscriptionStatus.ACTIVE,
            owner_email="atlimit100@test.com",
            stripe_customer_id="cus_atlimit100",
            stripe_subscription_id="sub_atlimit100",
            client_count=25,  # 100% of 25
        )
        db_session.add(tenant)
        await db_session.flush()

        user = PracticeUser(
            id=uuid4(),
            tenant_id=tenant.id,
            clerk_user_id=f"clerk_{uuid4().hex[:12]}",
            email="atlimit100@test.com",
            name="At Limit 100 User",
            role="owner",
        )
        db_session.add(user)
        await db_session.flush()

        from app.core.security import create_access_token

        token = create_access_token(
            user_id=str(user.id),
            tenant_id=str(tenant.id),
            roles=["owner"],
        )
        return tenant, {"Authorization": f"Bearer {token}"}

    async def test_threshold_warning_at_100_percent(
        self,
        test_client: AsyncClient,
        tenant_at_100_percent: tuple[Tenant, dict[str, str]],
    ) -> None:
        """Should show 100% threshold warning when at limit."""
        _tenant, headers = tenant_at_100_percent

        response = await test_client.get(
            "/api/v1/billing/billing/usage",
            headers=headers,
        )

        data = response.json()
        assert data["is_at_limit"] is True
        assert data["threshold_warning"] == "100%"
        assert data["client_percentage"] == 100.0

    async def test_at_limit_shows_upgrade_tier(
        self,
        test_client: AsyncClient,
        tenant_at_100_percent: tuple[Tenant, dict[str, str]],
    ) -> None:
        """Should suggest upgrade tier when at limit."""
        _tenant, headers = tenant_at_100_percent

        response = await test_client.get(
            "/api/v1/billing/billing/usage",
            headers=headers,
        )

        data = response.json()
        assert data["tier"] == "starter"
        assert data["next_tier"] == "professional"


# =============================================================================
# Limit Enforcement Tests (Spec 020)
# =============================================================================


@pytest.mark.integration
class TestClientLimitEnforcement:
    """Tests for client limit enforcement (Spec 020).

    Tests verify that client limits are correctly tracked and
    that appropriate warnings/errors are returned.
    """

    @pytest.fixture
    async def starter_tenant_near_limit(
        self, db_session: AsyncSession
    ) -> tuple[Tenant, dict[str, str]]:
        """Create a starter tenant with 24/25 clients (one slot remaining)."""
        tenant = Tenant(
            id=uuid4(),
            name="Near Limit Starter",
            slug="near-limit-starter",
            tier=SubscriptionTier.STARTER,  # Limit of 25
            subscription_status=SubscriptionStatus.ACTIVE,
            owner_email="nearlimit-starter@test.com",
            stripe_customer_id="cus_nearlimit_starter",
            stripe_subscription_id="sub_nearlimit_starter",
            client_count=24,  # 24/25 - one slot left
        )
        db_session.add(tenant)
        await db_session.flush()

        user = PracticeUser(
            id=uuid4(),
            tenant_id=tenant.id,
            clerk_user_id=f"clerk_{uuid4().hex[:12]}",
            email="nearlimit-starter@test.com",
            name="Near Limit Starter User",
            role="owner",
        )
        db_session.add(user)
        await db_session.flush()

        from app.core.security import create_access_token

        token = create_access_token(
            user_id=str(user.id),
            tenant_id=str(tenant.id),
            roles=["owner"],
        )
        return tenant, {"Authorization": f"Bearer {token}"}

    async def test_usage_shows_remaining_capacity(
        self,
        test_client: AsyncClient,
        starter_tenant_near_limit: tuple[Tenant, dict[str, str]],
    ) -> None:
        """Usage endpoint should show correct capacity info."""
        _tenant, headers = starter_tenant_near_limit

        response = await test_client.get(
            "/api/v1/billing/billing/usage",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["client_count"] == 24
        assert data["client_limit"] == 25
        assert data["client_percentage"] == 96.0  # 24/25
        assert data["is_approaching_limit"] is True
        assert data["is_at_limit"] is False

    @pytest.fixture
    async def enterprise_tenant(self, db_session: AsyncSession) -> tuple[Tenant, dict[str, str]]:
        """Create an enterprise tenant with unlimited clients."""
        tenant = Tenant(
            id=uuid4(),
            name="Enterprise Practice",
            slug="enterprise-practice",
            tier=SubscriptionTier.ENTERPRISE,  # Unlimited
            subscription_status=SubscriptionStatus.ACTIVE,
            owner_email="enterprise@test.com",
            stripe_customer_id="cus_enterprise",
            stripe_subscription_id="sub_enterprise",
            client_count=500,  # Many clients, no limit
        )
        db_session.add(tenant)
        await db_session.flush()

        user = PracticeUser(
            id=uuid4(),
            tenant_id=tenant.id,
            clerk_user_id=f"clerk_{uuid4().hex[:12]}",
            email="enterprise@test.com",
            name="Enterprise User",
            role="owner",
        )
        db_session.add(user)
        await db_session.flush()

        from app.core.security import create_access_token

        token = create_access_token(
            user_id=str(user.id),
            tenant_id=str(tenant.id),
            roles=["owner"],
        )
        return tenant, {"Authorization": f"Bearer {token}"}

    async def test_enterprise_tier_unlimited(
        self,
        test_client: AsyncClient,
        enterprise_tenant: tuple[Tenant, dict[str, str]],
    ) -> None:
        """Enterprise tier should show unlimited capacity."""
        _tenant, headers = enterprise_tenant

        response = await test_client.get(
            "/api/v1/billing/billing/usage",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["client_count"] == 500
        assert data["client_limit"] is None
        assert data["client_percentage"] is None
        assert data["is_at_limit"] is False
        assert data["is_approaching_limit"] is False
        assert data["threshold_warning"] is None

    async def test_growth_tier_limits(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Growth tier should have 250 client limit."""
        tenant = Tenant(
            id=uuid4(),
            name="Growth Practice",
            slug="growth-practice",
            tier=SubscriptionTier.GROWTH,  # Limit of 250
            subscription_status=SubscriptionStatus.ACTIVE,
            owner_email="growth@test.com",
            stripe_customer_id="cus_growth",
            stripe_subscription_id="sub_growth",
            client_count=200,  # 80% of 250
        )
        db_session.add(tenant)
        await db_session.flush()

        user = PracticeUser(
            id=uuid4(),
            tenant_id=tenant.id,
            clerk_user_id=f"clerk_{uuid4().hex[:12]}",
            email="growth@test.com",
            name="Growth User",
            role="owner",
        )
        db_session.add(user)
        await db_session.flush()

        from app.core.security import create_access_token

        token = create_access_token(
            user_id=str(user.id),
            tenant_id=str(tenant.id),
            roles=["owner"],
        )
        headers = {"Authorization": f"Bearer {token}"}

        response = await test_client.get(
            "/api/v1/billing/billing/usage",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["client_limit"] == 250
        assert data["tier"] == "growth"
        assert data["next_tier"] == "enterprise"
        assert data["is_approaching_limit"] is True
        assert data["threshold_warning"] == "80%"


# =============================================================================
# Usage History Tests (Spec 020)
# =============================================================================


@pytest.mark.integration
class TestGetUsageHistory:
    """Tests for GET /api/v1/billing/billing/usage/history."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.get("/api/v1/billing/billing/usage/history")
        assert response.status_code == 401

    async def test_returns_history_response(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Should return usage history response."""
        response = await test_client.get(
            "/api/v1/billing/billing/usage/history",
            headers=auth_headers_for_tenant,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert "snapshots" in data
        assert "period_start" in data
        assert "period_end" in data
        assert isinstance(data["snapshots"], list)

    async def test_respects_months_parameter(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Should respect the months query parameter."""
        response = await test_client.get(
            "/api/v1/billing/billing/usage/history?months=1",
            headers=auth_headers_for_tenant,
        )

        assert response.status_code == 200
        data = response.json()
        assert "period_start" in data
        assert "period_end" in data

    async def test_months_validation_min(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Months parameter should be at least 1."""
        response = await test_client.get(
            "/api/v1/billing/billing/usage/history?months=0",
            headers=auth_headers_for_tenant,
        )

        assert response.status_code == 422

    async def test_months_validation_max(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Months parameter should be at most 12."""
        response = await test_client.get(
            "/api/v1/billing/billing/usage/history?months=24",
            headers=auth_headers_for_tenant,
        )

        assert response.status_code == 422

    async def test_empty_history_for_new_tenant(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """New tenant should have empty history."""
        response = await test_client.get(
            "/api/v1/billing/billing/usage/history",
            headers=auth_headers_for_tenant,
        )

        data = response.json()
        # New tenant has no snapshots yet
        assert len(data["snapshots"]) == 0


@pytest.mark.integration
class TestGetUsageAlerts:
    """Tests for GET /api/v1/billing/billing/usage/alerts."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.get("/api/v1/billing/billing/usage/alerts")
        assert response.status_code == 401

    async def test_returns_alerts_response(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Should return usage alerts response."""
        response = await test_client.get(
            "/api/v1/billing/billing/usage/alerts",
            headers=auth_headers_for_tenant,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert "alerts" in data
        assert "total" in data
        assert isinstance(data["alerts"], list)

    async def test_empty_alerts_for_new_tenant(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """New tenant should have no alerts."""
        response = await test_client.get(
            "/api/v1/billing/billing/usage/alerts",
            headers=auth_headers_for_tenant,
        )

        data = response.json()
        assert data["total"] == 0
        assert len(data["alerts"]) == 0

    async def test_respects_pagination(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Should respect pagination parameters."""
        response = await test_client.get(
            "/api/v1/billing/billing/usage/alerts?limit=10&offset=5",
            headers=auth_headers_for_tenant,
        )

        assert response.status_code == 200


# =============================================================================
# Recalculate Client Count Tests (Spec 020)
# =============================================================================


@pytest.mark.integration
class TestRecalculateClientCount:
    """Tests for POST /api/v1/billing/billing/usage/recalculate."""

    async def test_unauthenticated_returns_401(self, test_client: AsyncClient) -> None:
        """Unauthenticated request should return 401."""
        response = await test_client.post("/api/v1/billing/billing/usage/recalculate")
        assert response.status_code == 401

    async def test_recalculates_client_count(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
        test_tenant: Tenant,
    ) -> None:
        """Should recalculate client count and return updated metrics."""
        response = await test_client.post(
            "/api/v1/billing/billing/usage/recalculate",
            headers=auth_headers_for_tenant,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify returns usage metrics structure
        assert "client_count" in data
        assert "client_limit" in data
        assert "tier" in data
        assert "is_at_limit" in data
        assert "is_approaching_limit" in data

    async def test_returns_updated_usage_metrics(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
    ) -> None:
        """Should return complete usage metrics after recalculation."""
        response = await test_client.post(
            "/api/v1/billing/billing/usage/recalculate",
            headers=auth_headers_for_tenant,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify all required usage metrics fields
        assert "client_count" in data
        assert "client_limit" in data
        assert "client_percentage" in data
        assert "ai_queries_month" in data
        assert "documents_month" in data
        assert "is_at_limit" in data
        assert "is_approaching_limit" in data
        assert "threshold_warning" in data
        assert "tier" in data
        assert "next_tier" in data

    async def test_correct_tier_info_returned(
        self,
        test_client: AsyncClient,
        auth_headers_for_tenant: dict[str, str],
        test_tenant: Tenant,
    ) -> None:
        """Should return correct tier information after recalculation."""
        response = await test_client.post(
            "/api/v1/billing/billing/usage/recalculate",
            headers=auth_headers_for_tenant,
        )

        assert response.status_code == 200
        data = response.json()

        # test_tenant is professional tier
        assert data["tier"] == "professional"
        assert data["client_limit"] == 100
        assert data["next_tier"] == "growth"
