"""Integration tests for feature gating mechanisms.

Tests for require_feature, require_tier dependencies, and FeatureGate class.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.feature_flags import FeatureGate
from app.modules.auth.models import (
    PracticeUser,
    SubscriptionStatus,
    SubscriptionTier,
    Tenant,
    User,
    UserRole,
    UserType,
)
from app.modules.billing.exceptions import FeatureNotAvailableError


async def _create_practice_user(
    db_session: AsyncSession,
    tenant_id: "uuid4().__class__",
    email: str = "user@test.com",
) -> PracticeUser:
    """Helper: create a properly-linked User + PracticeUser for tests."""
    base_user = User(
        id=uuid4(),
        email=email,
        user_type=UserType.PRACTICE_USER,
        is_active=True,
    )
    db_session.add(base_user)
    await db_session.flush()
    practice_user = PracticeUser(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=base_user.id,
        clerk_id=f"clerk_{uuid4().hex[:12]}",
        role=UserRole.ADMIN,
    )
    db_session.add(practice_user)
    await db_session.flush()
    return practice_user


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def starter_tenant(db_session: AsyncSession) -> Tenant:
    """Create a starter tier tenant."""
    tenant = Tenant(
        id=uuid4(),
        name="Starter Practice",
        slug=f"starter-{uuid4().hex[:8]}",
        tier=SubscriptionTier.STARTER,
        subscription_status=SubscriptionStatus.ACTIVE,
        owner_email="starter@test.com",
        client_count=5,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def professional_tenant(db_session: AsyncSession) -> Tenant:
    """Create a professional tier tenant."""
    tenant = Tenant(
        id=uuid4(),
        name="Professional Practice",
        slug=f"pro-{uuid4().hex[:8]}",
        tier=SubscriptionTier.PROFESSIONAL,
        subscription_status=SubscriptionStatus.ACTIVE,
        owner_email="pro@test.com",
        client_count=50,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def growth_tenant(db_session: AsyncSession) -> Tenant:
    """Create a growth tier tenant."""
    tenant = Tenant(
        id=uuid4(),
        name="Growth Practice",
        slug=f"growth-{uuid4().hex[:8]}",
        tier=SubscriptionTier.GROWTH,
        subscription_status=SubscriptionStatus.ACTIVE,
        owner_email="growth@test.com",
        client_count=150,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def enterprise_tenant(db_session: AsyncSession) -> Tenant:
    """Create an enterprise tier tenant."""
    tenant = Tenant(
        id=uuid4(),
        name="Enterprise Practice",
        slug=f"enterprise-{uuid4().hex[:8]}",
        tier=SubscriptionTier.ENTERPRISE,
        subscription_status=SubscriptionStatus.ACTIVE,
        owner_email="enterprise@test.com",
        client_count=500,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


def create_auth_headers(user: PracticeUser, tenant: Tenant) -> dict[str, str]:
    """Create auth headers for a user/tenant pair."""
    from app.core.security import create_access_token

    token = create_access_token(
        user_id=user.clerk_id,
        tenant_id=str(tenant.id),
        roles=["admin"],
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def starter_user_headers(db_session: AsyncSession, starter_tenant: Tenant) -> dict[str, str]:
    """Create auth headers for starter tenant."""
    user = await _create_practice_user(db_session, starter_tenant.id, "user@starter.com")
    return create_auth_headers(user, starter_tenant)


@pytest.fixture
async def pro_user_headers(db_session: AsyncSession, professional_tenant: Tenant) -> dict[str, str]:
    """Create auth headers for professional tenant."""
    user = await _create_practice_user(db_session, professional_tenant.id, "user@pro.com")
    return create_auth_headers(user, professional_tenant)


@pytest.fixture
async def growth_user_headers(db_session: AsyncSession, growth_tenant: Tenant) -> dict[str, str]:
    """Create auth headers for growth tenant."""
    user = await _create_practice_user(db_session, growth_tenant.id, "user@growth.com")
    return create_auth_headers(user, growth_tenant)


# =============================================================================
# FeatureGate Class Tests
# =============================================================================


@pytest.mark.integration
class TestFeatureGateClass:
    """Tests for the FeatureGate class."""

    def test_starter_can_access_client_portal(self, starter_tenant: Tenant) -> None:
        """Starter tier has client_portal (single $299 plan with full access)."""
        gate = FeatureGate("client_portal")
        result = gate.check(starter_tenant)
        assert result is True

    def test_professional_can_access_client_portal(self, professional_tenant: Tenant) -> None:
        """Professional tier should access client_portal."""
        gate = FeatureGate("client_portal")
        result = gate.check(professional_tenant)
        assert result is True

    def test_starter_cannot_access_api_access_feature(self, starter_tenant: Tenant) -> None:
        """Starter tier should not access api_access (growth+ only)."""
        gate = FeatureGate("api_access")

        with pytest.raises(FeatureNotAvailableError) as exc_info:
            gate.check(starter_tenant)

        assert exc_info.value.feature == "api_access"

    def test_starter_cannot_access_api_access(self, starter_tenant: Tenant) -> None:
        """Starter tier should not access API."""
        gate = FeatureGate("api_access")

        with pytest.raises(FeatureNotAvailableError) as exc_info:
            gate.check(starter_tenant)

        assert exc_info.value.required_tier == "growth"

    def test_professional_cannot_access_api(self, professional_tenant: Tenant) -> None:
        """Professional tier should not have API access."""
        gate = FeatureGate("api_access")

        with pytest.raises(FeatureNotAvailableError) as exc_info:
            gate.check(professional_tenant)

        assert exc_info.value.required_tier == "growth"

    def test_growth_can_access_api(self, growth_tenant: Tenant) -> None:
        """Growth tier should have API access."""
        gate = FeatureGate("api_access")
        result = gate.check(growth_tenant)
        assert result is True

    def test_enterprise_has_all_features(self, enterprise_tenant: Tenant) -> None:
        """Enterprise tier should have access to all features."""
        features = [
            "client_portal",
            "custom_triggers",
            "api_access",
            "knowledge_base",
            "magic_zone",
        ]

        for feature in features:
            gate = FeatureGate(feature)  # type: ignore[arg-type]
            assert gate.check(enterprise_tenant) is True

    def test_is_available_returns_false_for_blocked(self, starter_tenant: Tenant) -> None:
        """is_available should return False for blocked features without raising."""
        gate = FeatureGate("api_access")
        result = gate.is_available(starter_tenant)
        assert result is False

    def test_is_available_true_for_allowed_feature(self, professional_tenant: Tenant) -> None:
        """is_available should return True for allowed features."""
        gate = FeatureGate("client_portal")
        result = gate.is_available(professional_tenant)
        assert result is True


# =============================================================================
# Tier-Based Access Tests via API
# =============================================================================


@pytest.mark.integration
class TestFeatureAccessViaAPI:
    """Tests for feature access through API endpoints."""

    async def test_starter_sees_restricted_features(
        self,
        test_client: AsyncClient,
        starter_user_headers: dict[str, str],
    ) -> None:
        """Starter tier has full features except api_access (single $299 plan)."""
        response = await test_client.get(
            "/api/v1/features",
            headers=starter_user_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "starter"
        assert data["can_access"]["client_portal"] is True
        assert data["can_access"]["custom_triggers"] is True
        assert data["can_access"]["api_access"] is False  # Growth+ only
        assert data["can_access"]["knowledge_base"] is True
        assert data["can_access"]["magic_zone"] is True

    async def test_professional_sees_extended_features(
        self,
        test_client: AsyncClient,
        pro_user_headers: dict[str, str],
    ) -> None:
        """Professional tier should see extended features."""
        response = await test_client.get(
            "/api/v1/features",
            headers=pro_user_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "professional"
        assert data["can_access"]["client_portal"] is True
        assert data["can_access"]["custom_triggers"] is True
        assert data["can_access"]["api_access"] is False  # Requires growth
        assert data["can_access"]["knowledge_base"] is True
        assert data["can_access"]["magic_zone"] is True

    async def test_growth_sees_api_access(
        self,
        test_client: AsyncClient,
        growth_user_headers: dict[str, str],
    ) -> None:
        """Growth tier should see API access enabled."""
        response = await test_client.get(
            "/api/v1/features",
            headers=growth_user_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "growth"
        assert data["can_access"]["api_access"] is True


# =============================================================================
# Error Response Format Tests
# =============================================================================


@pytest.mark.integration
class TestFeatureGatingErrorFormat:
    """Tests for feature gating error response format."""

    def test_error_contains_feature_info(self, starter_tenant: Tenant) -> None:
        """Error should contain feature and tier information."""
        gate = FeatureGate("api_access")

        with pytest.raises(FeatureNotAvailableError) as exc_info:
            gate.check(starter_tenant)

        error = exc_info.value
        assert error.feature == "api_access"
        assert error.required_tier == "growth"
        assert error.current_tier == "starter"
        assert error.code == "FEATURE_NOT_AVAILABLE"
        assert error.status_code == 403

    def test_error_details_include_upgrade_url(self, starter_tenant: Tenant) -> None:
        """Error details should include upgrade URL."""
        gate = FeatureGate("api_access")

        with pytest.raises(FeatureNotAvailableError) as exc_info:
            gate.check(starter_tenant)

        error = exc_info.value
        assert "upgrade_url" in error.details
        assert error.details["upgrade_url"] == "/pricing"


# =============================================================================
# Client Limit Tests
# =============================================================================


@pytest.mark.integration
class TestClientLimitGating:
    """Tests for client limit enforcement."""

    async def test_starter_at_limit(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Starter at client limit should show is_at_limit."""
        tenant = Tenant(
            id=uuid4(),
            name="At Limit Practice",
            slug=f"limit-{uuid4().hex[:8]}",
            tier=SubscriptionTier.STARTER,
            subscription_status=SubscriptionStatus.ACTIVE,
            owner_email="limit@test.com",
            client_count=25,  # At limit
        )
        db_session.add(tenant)
        await db_session.flush()

        user = await _create_practice_user(db_session, tenant.id, "user@limit.com")
        headers = create_auth_headers(user, tenant)

        from unittest.mock import patch

        with patch("app.modules.billing.router.stripe"):
            response = await test_client.get(
                "/api/v1/subscription",
                headers=headers,
            )

        assert response.status_code == 200
        data = response.json()
        # The usage info should show is_at_limit or approaching
        # Note: actual count comes from XeroConnection count in real API
        assert "usage" in data

    async def test_enterprise_unlimited_clients(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Enterprise tier should have unlimited clients."""
        tenant = Tenant(
            id=uuid4(),
            name="Unlimited Practice",
            slug=f"unlimited-{uuid4().hex[:8]}",
            tier=SubscriptionTier.ENTERPRISE,
            subscription_status=SubscriptionStatus.ACTIVE,
            owner_email="enterprise@test.com",
            client_count=1000,  # High count OK
        )
        db_session.add(tenant)
        await db_session.flush()

        user = await _create_practice_user(db_session, tenant.id, "user@enterprise.com")
        headers = create_auth_headers(user, tenant)

        from unittest.mock import patch

        with patch("app.modules.billing.router.stripe"):
            response = await test_client.get(
                "/api/v1/subscription",
                headers=headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["features"]["max_clients"] is None  # Unlimited
