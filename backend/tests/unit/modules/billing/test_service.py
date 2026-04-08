"""Unit tests for billing service module.

Tests for subscription management, checkout sessions, and billing operations.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.billing.exceptions import (
    ClientLimitExceededError,
    InvalidTierChangeError,
    SubscriptionError,
)
from app.modules.billing.service import BillingService


class MockTier:
    """Mock tier enum for testing."""

    def __init__(self, value: str) -> None:
        self.value = value


class MockTenant:
    """Mock tenant for testing."""

    def __init__(
        self,
        tier: str = "starter",
        client_count: int = 0,
        stripe_customer_id: str | None = None,
        stripe_subscription_id: str | None = None,
        owner_email: str | None = None,
        ai_queries_month: int = 0,
        documents_month: int = 0,
    ) -> None:
        self.id = uuid4()
        self.name = "Test Practice"
        self.slug = "test-practice"
        self.tier = MockTier(tier)
        self.client_count = client_count
        self.stripe_customer_id = stripe_customer_id
        self.stripe_subscription_id = stripe_subscription_id
        self.owner_email = owner_email
        self.ai_queries_month = ai_queries_month
        self.documents_month = documents_month


class TestCreateCheckoutSession:
    """Tests for create_checkout_session method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def mock_stripe_client(self):
        """Create a mock Stripe client."""
        client = MagicMock()
        client.create_customer = AsyncMock(return_value="cus_test123")
        client.create_checkout_session = AsyncMock(
            return_value=("https://checkout.stripe.com/...", "cs_test123")
        )
        return client

    @pytest.mark.asyncio
    async def test_enterprise_tier_raises_error(self, mock_session, mock_stripe_client):
        """Enterprise tier should raise SubscriptionError."""
        service = BillingService(mock_session, mock_stripe_client)
        tenant = MockTenant()

        with pytest.raises(SubscriptionError) as exc_info:
            await service.create_checkout_session(
                tenant=tenant,
                tier="enterprise",
                success_url="https://app.test.com/success",
                cancel_url="https://app.test.com/cancel",
            )

        assert "Enterprise tier requires manual setup" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_creates_stripe_customer_when_missing(self, mock_session, mock_stripe_client):
        """Should create Stripe customer if tenant doesn't have one."""
        service = BillingService(mock_session, mock_stripe_client)
        tenant = MockTenant(owner_email="test@example.com")

        checkout_url, session_id = await service.create_checkout_session(
            tenant=tenant,
            tier="professional",
            success_url="https://app.test.com/success",
            cancel_url="https://app.test.com/cancel",
        )

        mock_stripe_client.create_customer.assert_called_once()
        assert tenant.stripe_customer_id == "cus_test123"
        assert checkout_url == "https://checkout.stripe.com/..."
        assert session_id == "cs_test123"

    @pytest.mark.asyncio
    async def test_reuses_existing_stripe_customer(self, mock_session, mock_stripe_client):
        """Should reuse existing Stripe customer ID."""
        service = BillingService(mock_session, mock_stripe_client)
        tenant = MockTenant(stripe_customer_id="cus_existing123")

        await service.create_checkout_session(
            tenant=tenant,
            tier="starter",
            success_url="https://app.test.com/success",
            cancel_url="https://app.test.com/cancel",
        )

        mock_stripe_client.create_customer.assert_not_called()
        mock_stripe_client.create_checkout_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_fallback_email_when_owner_email_missing(
        self, mock_session, mock_stripe_client
    ):
        """Should use fallback email format when owner_email is None."""
        service = BillingService(mock_session, mock_stripe_client)
        tenant = MockTenant(owner_email=None)

        await service.create_checkout_session(
            tenant=tenant,
            tier="professional",
            success_url="https://app.test.com/success",
            cancel_url="https://app.test.com/cancel",
        )

        call_args = mock_stripe_client.create_customer.call_args
        assert "test-practice@clairo.com.au" in call_args.kwargs["email"]


class TestCreatePortalSession:
    """Tests for create_portal_session method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_stripe_client(self):
        """Create a mock Stripe client."""
        client = MagicMock()
        client.create_portal_session = AsyncMock(return_value="https://billing.stripe.com/...")
        return client

    @pytest.mark.asyncio
    async def test_no_stripe_customer_raises_error(self, mock_session, mock_stripe_client):
        """Should raise error if tenant has no Stripe customer ID."""
        service = BillingService(mock_session, mock_stripe_client)
        tenant = MockTenant(stripe_customer_id=None)

        with pytest.raises(SubscriptionError) as exc_info:
            await service.create_portal_session(
                tenant=tenant,
                return_url="https://app.test.com/billing",
            )

        assert "No billing account found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_returns_portal_url(self, mock_session, mock_stripe_client):
        """Should return portal URL for valid customer."""
        service = BillingService(mock_session, mock_stripe_client)
        tenant = MockTenant(stripe_customer_id="cus_test123")

        portal_url = await service.create_portal_session(
            tenant=tenant,
            return_url="https://app.test.com/billing",
        )

        assert portal_url == "https://billing.stripe.com/..."
        mock_stripe_client.create_portal_session.assert_called_once_with(
            customer_id="cus_test123",
            return_url="https://app.test.com/billing",
        )


class TestUpgradeSubscription:
    """Tests for upgrade_subscription method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def mock_stripe_client(self):
        """Create a mock Stripe client."""
        client = MagicMock()
        client.upgrade_subscription = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_downgrade_raises_error(self, mock_session, mock_stripe_client):
        """Attempting to downgrade via upgrade should raise error."""
        service = BillingService(mock_session, mock_stripe_client)
        tenant = MockTenant(tier="professional", stripe_subscription_id="sub_test123")

        with pytest.raises(InvalidTierChangeError) as exc_info:
            await service.upgrade_subscription(tenant=tenant, new_tier="starter")

        assert "higher than current tier" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_same_tier_raises_error(self, mock_session, mock_stripe_client):
        """Attempting to upgrade to same tier should raise error."""
        service = BillingService(mock_session, mock_stripe_client)
        tenant = MockTenant(tier="professional", stripe_subscription_id="sub_test123")

        with pytest.raises(InvalidTierChangeError) as exc_info:
            await service.upgrade_subscription(tenant=tenant, new_tier="professional")

        assert "higher than current tier" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_enterprise_upgrade_raises_error(self, mock_session, mock_stripe_client):
        """Upgrading to enterprise should raise error (requires manual setup)."""
        service = BillingService(mock_session, mock_stripe_client)
        tenant = MockTenant(tier="growth", stripe_subscription_id="sub_test123")

        with pytest.raises(InvalidTierChangeError) as exc_info:
            await service.upgrade_subscription(tenant=tenant, new_tier="enterprise")

        assert "Enterprise tier requires manual setup" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_subscription_raises_error(self, mock_session, mock_stripe_client):
        """Upgrading without active subscription should raise error."""
        service = BillingService(mock_session, mock_stripe_client)
        tenant = MockTenant(tier="starter", stripe_subscription_id=None)

        with pytest.raises(SubscriptionError) as exc_info:
            await service.upgrade_subscription(tenant=tenant, new_tier="professional")

        assert "No active subscription" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_successful_upgrade(self, mock_session, mock_stripe_client):
        """Valid upgrade should update tier."""
        service = BillingService(mock_session, mock_stripe_client)
        tenant = MockTenant(tier="starter", stripe_subscription_id="sub_test123")

        await service.upgrade_subscription(tenant=tenant, new_tier="professional")

        mock_stripe_client.upgrade_subscription.assert_called_once_with(
            subscription_id="sub_test123",
            new_tier="professional",
        )
        assert tenant.tier == "professional"


class TestScheduleDowngrade:
    """Tests for schedule_downgrade method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_stripe_client(self):
        """Create a mock Stripe client."""
        client = MagicMock()
        client.schedule_downgrade = AsyncMock(return_value=datetime(2025, 2, 1, 0, 0, 0))
        return client

    @pytest.mark.asyncio
    async def test_upgrade_via_downgrade_raises_error(self, mock_session, mock_stripe_client):
        """Attempting to upgrade via downgrade should raise error."""
        service = BillingService(mock_session, mock_stripe_client)
        tenant = MockTenant(tier="starter", stripe_subscription_id="sub_test123")

        with pytest.raises(InvalidTierChangeError) as exc_info:
            await service.schedule_downgrade(tenant=tenant, new_tier="professional")

        assert "lower than current tier" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_same_tier_raises_error(self, mock_session, mock_stripe_client):
        """Attempting to downgrade to same tier should raise error."""
        service = BillingService(mock_session, mock_stripe_client)
        tenant = MockTenant(tier="professional", stripe_subscription_id="sub_test123")

        with pytest.raises(InvalidTierChangeError) as exc_info:
            await service.schedule_downgrade(tenant=tenant, new_tier="professional")

        assert "lower than current tier" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_subscription_raises_error(self, mock_session, mock_stripe_client):
        """Downgrading without subscription should raise error."""
        service = BillingService(mock_session, mock_stripe_client)
        tenant = MockTenant(tier="professional", stripe_subscription_id=None)

        with pytest.raises(SubscriptionError) as exc_info:
            await service.schedule_downgrade(tenant=tenant, new_tier="starter")

        assert "No active subscription" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_successful_downgrade(self, mock_session, mock_stripe_client):
        """Valid downgrade should return effective date."""
        service = BillingService(mock_session, mock_stripe_client)
        tenant = MockTenant(tier="professional", stripe_subscription_id="sub_test123")

        effective_date = await service.schedule_downgrade(tenant=tenant, new_tier="starter")

        assert effective_date == datetime(2025, 2, 1, 0, 0, 0)
        mock_stripe_client.schedule_downgrade.assert_called_once()


class TestCancelSubscription:
    """Tests for cancel_subscription method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_stripe_client(self):
        """Create a mock Stripe client."""
        client = MagicMock()
        client.cancel_subscription = AsyncMock(return_value=datetime(2025, 2, 1, 0, 0, 0))
        return client

    @pytest.mark.asyncio
    async def test_no_subscription_raises_error(self, mock_session, mock_stripe_client):
        """Cancelling without subscription should raise error."""
        service = BillingService(mock_session, mock_stripe_client)
        tenant = MockTenant(stripe_subscription_id=None)

        with pytest.raises(SubscriptionError) as exc_info:
            await service.cancel_subscription(tenant=tenant)

        assert "No active subscription to cancel" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_successful_cancellation(self, mock_session, mock_stripe_client):
        """Valid cancellation should return effective date."""
        service = BillingService(mock_session, mock_stripe_client)
        tenant = MockTenant(stripe_subscription_id="sub_test123")

        effective_date = await service.cancel_subscription(
            tenant=tenant,
            reason="Too expensive",
            feedback="Great product but budget issues",
        )

        assert effective_date == datetime(2025, 2, 1, 0, 0, 0)
        mock_stripe_client.cancel_subscription.assert_called_once_with(
            subscription_id="sub_test123",
            reason="Too expensive",
            feedback="Great product but budget issues",
        )


class TestGetUsageInfo:
    """Tests for get_usage_info method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    def test_unlimited_tier(self, mock_session):
        """Enterprise tier should return unlimited usage info."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="enterprise", client_count=500)

        usage = service.get_usage_info(tenant)

        assert usage.client_count == 500
        assert usage.client_limit is None
        assert usage.is_at_limit is False
        assert usage.is_approaching_limit is False
        assert usage.percentage_used is None

    def test_starter_tier_unlimited(self, mock_session):
        """Starter tier is unlimited — no client limit or percentage."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="starter", client_count=10)

        usage = service.get_usage_info(tenant)

        assert usage.client_count == 10
        assert usage.client_limit is None
        assert usage.is_at_limit is False
        assert usage.is_approaching_limit is False
        assert usage.percentage_used is None

    def test_professional_tier_at_limit(self, mock_session):
        """Tier at limit should show is_at_limit=True."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="professional", client_count=100)

        usage = service.get_usage_info(tenant)

        assert usage.client_count == 100
        assert usage.client_limit == 100
        assert usage.is_at_limit is True
        assert usage.is_approaching_limit is True
        assert usage.percentage_used == 100.0

    def test_approaching_limit_threshold(self, mock_session):
        """Should be approaching limit at 80% or above."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="professional", client_count=80)  # 80% of 100

        usage = service.get_usage_info(tenant)

        assert usage.is_approaching_limit is True
        assert usage.percentage_used == 80.0

    def test_not_approaching_limit_below_threshold(self, mock_session):
        """Should not be approaching limit below 80%."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="professional", client_count=76)  # 76% of 100

        usage = service.get_usage_info(tenant)

        assert usage.is_approaching_limit is False
        assert usage.percentage_used == 76.0


class TestCheckClientLimit:
    """Tests for check_client_limit method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    def test_unlimited_tier_always_allows(self, mock_session):
        """Enterprise tier should always allow new clients."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="enterprise", client_count=1000)

        result = service.check_client_limit(tenant)

        assert result is True

    def test_below_limit_allows(self, mock_session):
        """Below limit should allow new clients."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="starter", client_count=20)

        result = service.check_client_limit(tenant)

        assert result is True

    def test_at_limit_raises_error(self, mock_session):
        """At limit should raise ClientLimitExceededError."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="professional", client_count=100)

        with pytest.raises(ClientLimitExceededError) as exc_info:
            service.check_client_limit(tenant)

        assert exc_info.value.current_count == 100
        assert exc_info.value.limit == 100
        assert exc_info.value.required_tier == "growth"

    def test_above_limit_raises_error(self, mock_session):
        """Above limit (legacy data) should raise error."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="professional", client_count=110)

        with pytest.raises(ClientLimitExceededError) as exc_info:
            service.check_client_limit(tenant)

        assert exc_info.value.current_count == 110


class TestGetTierFeaturesForTenant:
    """Tests for get_tier_features_for_tenant method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    def test_starter_tier_features(self, mock_session):
        """Starter tier is all-inclusive — unlimited clients and all features."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="starter")

        features = service.get_tier_features_for_tenant(tenant)

        assert features.max_clients is None
        assert features.ai_insights == "full"
        assert features.client_portal is True
        assert features.custom_triggers is True
        assert features.api_access is False
        assert features.knowledge_base is True
        assert features.magic_zone is True

    def test_professional_tier_features(self, mock_session):
        """Professional tier should have extended features."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="professional")

        features = service.get_tier_features_for_tenant(tenant)

        assert features.max_clients == 100
        assert features.ai_insights == "full"
        assert features.client_portal is True
        assert features.custom_triggers is True
        assert features.api_access is False
        assert features.knowledge_base is True
        assert features.magic_zone is True

    def test_enterprise_tier_features(self, mock_session):
        """Enterprise tier should have all features."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="enterprise")

        features = service.get_tier_features_for_tenant(tenant)

        assert features.max_clients is None  # Unlimited
        assert features.ai_insights == "full"
        assert features.client_portal is True
        assert features.api_access is True


class TestRecordBillingEvent:
    """Tests for record_billing_event method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_event_repository(self):
        """Create a mock event repository."""
        repo = AsyncMock()
        repo.get_by_stripe_event_id = AsyncMock(return_value=None)
        repo.create = AsyncMock()
        return repo

    @pytest.mark.asyncio
    async def test_new_event_recorded(self, mock_session, mock_event_repository):
        """New event should be recorded."""
        service = BillingService(mock_session)
        service.event_repository = mock_event_repository

        tenant_id = uuid4()
        result = await service.record_billing_event(
            tenant_id=tenant_id,
            stripe_event_id="evt_test123",
            event_type="invoice.paid",
            event_data={"amount": 29900},
            amount_cents=29900,
        )

        assert result is True
        mock_event_repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_event_not_recorded(self, mock_session, mock_event_repository):
        """Duplicate event should return False."""
        mock_event_repository.get_by_stripe_event_id = AsyncMock(
            return_value=MagicMock()  # Existing event
        )

        service = BillingService(mock_session)
        service.event_repository = mock_event_repository

        result = await service.record_billing_event(
            tenant_id=uuid4(),
            stripe_event_id="evt_test123",
            event_type="invoice.paid",
            event_data={},
        )

        assert result is False
        mock_event_repository.create.assert_not_called()


class TestListBillingEvents:
    """Tests for list_billing_events method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_list_events(self, mock_session):
        """Should return formatted billing events."""
        mock_event = MagicMock()
        mock_event.id = uuid4()
        mock_event.event_type = "invoice.paid"
        mock_event.amount_cents = 29900
        mock_event.currency = "aud"
        mock_event.status.value = "processed"
        mock_event.created_at = datetime(2025, 1, 1, 12, 0, 0)

        mock_repository = AsyncMock()
        mock_repository.list_by_tenant = AsyncMock(return_value=([mock_event], 1))

        service = BillingService(mock_session)
        service.event_repository = mock_repository

        events, total = await service.list_billing_events(
            tenant_id=uuid4(),
            limit=20,
            offset=0,
        )

        assert total == 1
        assert len(events) == 1
        assert events[0]["event_type"] == "invoice.paid"
        assert events[0]["amount_cents"] == 29900


class TestCheckCanAddClients:
    """Tests for check_can_add_clients method (Spec 020).

    Tests batch client addition limit checking for operations like Xero sync.
    """

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    def test_unlimited_tier_allows_any_count(self, mock_session):
        """Enterprise tier should allow adding any number of clients."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="enterprise", client_count=500)

        result = service.check_can_add_clients(tenant, count=1000)

        assert result is True

    def test_single_client_below_limit(self, mock_session):
        """Adding single client below limit should succeed."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="starter", client_count=20)  # 20/25

        result = service.check_can_add_clients(tenant, count=1)

        assert result is True

    def test_batch_clients_within_limit(self, mock_session):
        """Adding batch of clients within limit should succeed."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="starter", client_count=20)  # 20/25

        result = service.check_can_add_clients(tenant, count=5)  # 25/25

        assert result is True

    def test_batch_clients_exceeds_limit(self, mock_session):
        """Adding batch that exceeds limit should raise error."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="professional", client_count=95)  # 95/100

        with pytest.raises(ClientLimitExceededError) as exc_info:
            service.check_can_add_clients(tenant, count=10)  # Would be 105/100

        assert exc_info.value.current_count == 95
        assert exc_info.value.limit == 100
        assert exc_info.value.required_tier == "growth"

    def test_already_at_limit_single_client(self, mock_session):
        """Adding one client when at limit should raise error."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="professional", client_count=100)  # 100/100

        with pytest.raises(ClientLimitExceededError) as exc_info:
            service.check_can_add_clients(tenant, count=1)

        assert exc_info.value.current_count == 100
        assert exc_info.value.limit == 100

    def test_default_count_is_one(self, mock_session):
        """Default count parameter should be 1."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="starter", client_count=24)  # 24/25

        # Should not raise - only adding 1 by default
        result = service.check_can_add_clients(tenant)

        assert result is True

    def test_exactly_at_limit_after_add(self, mock_session):
        """Adding clients to exactly reach limit should succeed."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="professional", client_count=95)  # 95/100

        result = service.check_can_add_clients(tenant, count=5)  # 100/100

        assert result is True

    def test_error_includes_next_tier(self, mock_session):
        """Error should include the required tier for upgrade."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="professional", client_count=100)  # 100/100

        with pytest.raises(ClientLimitExceededError) as exc_info:
            service.check_can_add_clients(tenant, count=1)

        # Professional's next tier is Growth
        assert exc_info.value.required_tier == "growth"

    def test_growth_tier_next_is_enterprise(self, mock_session):
        """Growth tier should suggest enterprise for upgrade."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="growth", client_count=250)  # 250/250

        with pytest.raises(ClientLimitExceededError) as exc_info:
            service.check_can_add_clients(tenant, count=1)

        assert exc_info.value.required_tier == "enterprise"


class TestGetRemainingClientSlots:
    """Tests for get_remaining_client_slots method (Spec 020).

    Tests calculation of available client slots for a tenant.
    """

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    def test_unlimited_tier_returns_none(self, mock_session):
        """Enterprise tier should return None (unlimited)."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="enterprise", client_count=500)

        result = service.get_remaining_client_slots(tenant)

        assert result is None

    def test_starter_tier_remaining_slots(self, mock_session):
        """Starter tier is unlimited — returns None for remaining slots."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="starter", client_count=10)

        result = service.get_remaining_client_slots(tenant)

        assert result is None

    def test_professional_tier_remaining_slots(self, mock_session):
        """Professional tier should return correct remaining slots."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="professional", client_count=75)  # 75/100

        result = service.get_remaining_client_slots(tenant)

        assert result == 25  # 100 - 75

    def test_at_limit_returns_zero(self, mock_session):
        """At limit should return 0 remaining slots."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="professional", client_count=100)  # 100/100

        result = service.get_remaining_client_slots(tenant)

        assert result == 0

    def test_over_limit_returns_zero(self, mock_session):
        """Over limit (legacy data) should return 0, not negative."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="professional", client_count=110)  # 110/100

        result = service.get_remaining_client_slots(tenant)

        assert result == 0  # max(0, 100 - 110) = 0

    def test_empty_tenant_full_slots(self, mock_session):
        """Empty tenant should have full slots available."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="professional", client_count=0)

        result = service.get_remaining_client_slots(tenant)

        assert result == 100  # Full professional limit


class TestGetUsageMetrics:
    """Tests for get_usage_metrics method (Spec 020).

    Tests the extended usage metrics for the usage dashboard.
    """

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    def test_unlimited_tier_metrics(self, mock_session):
        """Enterprise tier should have unlimited metrics."""
        service = BillingService(mock_session)
        tenant = MockTenant(
            tier="enterprise",
            client_count=500,
            ai_queries_month=1000,
            documents_month=200,
        )

        metrics = service.get_usage_metrics(tenant)

        assert metrics.client_count == 500
        assert metrics.client_limit is None
        assert metrics.client_percentage is None
        assert metrics.is_at_limit is False
        assert metrics.is_approaching_limit is False
        assert metrics.threshold_warning is None
        assert metrics.tier == "enterprise"
        # Enterprise returns 'enterprise' as next tier (already at highest)
        assert metrics.next_tier == "enterprise"

    def test_starter_tier_unlimited_metrics(self, mock_session):
        """Starter tier is unlimited — no client limit or percentage warnings."""
        service = BillingService(mock_session)
        tenant = MockTenant(
            tier="starter",
            client_count=15,
            ai_queries_month=50,
            documents_month=10,
        )

        metrics = service.get_usage_metrics(tenant)

        assert metrics.client_count == 15
        assert metrics.client_limit is None
        assert metrics.client_percentage is None
        assert metrics.ai_queries_month == 50
        assert metrics.documents_month == 10
        assert metrics.is_at_limit is False
        assert metrics.is_approaching_limit is False
        assert metrics.threshold_warning is None
        assert metrics.tier == "starter"
        assert metrics.next_tier == "professional"

    def test_threshold_warning_at_80(self, mock_session):
        """At 80% should show 80% warning."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="professional", client_count=80)  # 80% of 100

        metrics = service.get_usage_metrics(tenant)

        assert metrics.is_approaching_limit is True
        assert metrics.threshold_warning == "80%"

    def test_threshold_warning_at_90(self, mock_session):
        """At 90% should show 90% warning."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="professional", client_count=90)  # 90%

        metrics = service.get_usage_metrics(tenant)

        assert metrics.is_approaching_limit is True
        assert metrics.threshold_warning == "90%"

    def test_threshold_warning_at_100(self, mock_session):
        """At 100% should show 100% warning."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="professional", client_count=100)  # 100% of 100

        metrics = service.get_usage_metrics(tenant)

        assert metrics.is_at_limit is True
        assert metrics.is_approaching_limit is True
        assert metrics.threshold_warning == "100%"

    def test_over_100_still_shows_100_warning(self, mock_session):
        """Over 100% (legacy) should still show 100% warning."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="professional", client_count=110)  # 110% of 100

        metrics = service.get_usage_metrics(tenant)

        assert metrics.is_at_limit is True
        assert metrics.threshold_warning == "100%"

    def test_next_tier_for_professional(self, mock_session):
        """Professional tier next should be Growth."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="professional", client_count=50)

        metrics = service.get_usage_metrics(tenant)

        assert metrics.tier == "professional"
        assert metrics.next_tier == "growth"

    def test_next_tier_for_growth(self, mock_session):
        """Growth tier next should be Enterprise."""
        service = BillingService(mock_session)
        tenant = MockTenant(tier="growth", client_count=100)

        metrics = service.get_usage_metrics(tenant)

        assert metrics.tier == "growth"
        assert metrics.next_tier == "enterprise"


class TestGetThresholdWarning:
    """Tests for _get_threshold_warning private method (Spec 020).

    Tests threshold warning level determination based on usage percentage.
    """

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    def test_none_percentage_returns_none(self, mock_session):
        """None percentage should return None warning."""
        service = BillingService(mock_session)

        result = service._get_threshold_warning(None)

        assert result is None

    def test_below_80_returns_none(self, mock_session):
        """Below 80% should return no warning."""
        service = BillingService(mock_session)

        assert service._get_threshold_warning(0) is None
        assert service._get_threshold_warning(50.0) is None
        assert service._get_threshold_warning(79.9) is None

    def test_at_80_returns_80_warning(self, mock_session):
        """At exactly 80% should return 80% warning."""
        service = BillingService(mock_session)

        result = service._get_threshold_warning(80.0)

        assert result == "80%"

    def test_between_80_and_90_returns_80_warning(self, mock_session):
        """Between 80% and 90% should return 80% warning."""
        service = BillingService(mock_session)

        assert service._get_threshold_warning(85.0) == "80%"
        assert service._get_threshold_warning(89.9) == "80%"

    def test_at_90_returns_90_warning(self, mock_session):
        """At exactly 90% should return 90% warning."""
        service = BillingService(mock_session)

        result = service._get_threshold_warning(90.0)

        assert result == "90%"

    def test_between_90_and_100_returns_90_warning(self, mock_session):
        """Between 90% and 100% should return 90% warning."""
        service = BillingService(mock_session)

        assert service._get_threshold_warning(95.0) == "90%"
        assert service._get_threshold_warning(99.9) == "90%"

    def test_at_100_returns_100_warning(self, mock_session):
        """At exactly 100% should return 100% warning."""
        service = BillingService(mock_session)

        result = service._get_threshold_warning(100.0)

        assert result == "100%"

    def test_above_100_returns_100_warning(self, mock_session):
        """Above 100% should return 100% warning."""
        service = BillingService(mock_session)

        assert service._get_threshold_warning(110.0) == "100%"
        assert service._get_threshold_warning(200.0) == "100%"
