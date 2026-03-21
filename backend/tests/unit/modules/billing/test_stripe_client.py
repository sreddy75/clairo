"""Unit tests for Stripe client module.

Tests for Stripe API wrapper functions.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import stripe

from app.modules.billing.stripe_client import StripeClient, get_tier_price_ids


class TestGetTierPriceIds:
    """Tests for get_tier_price_ids function."""

    def test_returns_price_mapping(self):
        """Should return a dict mapping tiers to price IDs."""
        # Clear cache for testing
        get_tier_price_ids.cache_clear()

        with patch("app.modules.billing.stripe_client.get_settings") as mock_settings:
            mock_stripe_settings = MagicMock()
            mock_stripe_settings.price_starter = "price_starter123"
            mock_stripe_settings.price_professional = "price_pro123"
            mock_stripe_settings.price_growth = "price_growth123"
            mock_settings.return_value.stripe = mock_stripe_settings

            prices = get_tier_price_ids()

            assert prices["starter"] == "price_starter123"
            assert prices["professional"] == "price_pro123"
            assert prices["growth"] == "price_growth123"
            assert prices["enterprise"] == ""  # Always empty

        # Clear cache after test
        get_tier_price_ids.cache_clear()


class TestStripeClientInit:
    """Tests for StripeClient initialization."""

    def test_sets_api_key_from_settings(self):
        """Should set stripe.api_key from settings."""
        with patch("app.modules.billing.stripe_client.get_settings") as mock_settings:
            mock_secret = MagicMock()
            mock_secret.get_secret_value.return_value = "sk_test_123"
            mock_stripe_settings = MagicMock()
            mock_stripe_settings.secret_key = mock_secret
            mock_settings.return_value.stripe = mock_stripe_settings

            with patch("app.modules.billing.stripe_client.stripe") as mock_stripe:
                StripeClient()
                assert mock_stripe.api_key == "sk_test_123"


class TestCreateCustomer:
    """Tests for create_customer method."""

    @pytest.fixture
    def client(self):
        """Create client with mocked settings."""
        with patch("app.modules.billing.stripe_client.get_settings"):
            return StripeClient()

    @pytest.mark.asyncio
    async def test_creates_customer(self, client):
        """Should create Stripe customer with provided details."""
        with patch("stripe.Customer.create") as mock_create:
            mock_create.return_value = MagicMock(id="cus_test123")

            customer_id = await client.create_customer(
                email="test@example.com",
                name="Test Practice",
                metadata={"tenant_id": "uuid-123"},
            )

            assert customer_id == "cus_test123"
            mock_create.assert_called_once_with(
                email="test@example.com",
                name="Test Practice",
                metadata={"tenant_id": "uuid-123"},
            )

    @pytest.mark.asyncio
    async def test_creates_customer_without_metadata(self, client):
        """Should create customer with empty metadata when None provided."""
        with patch("stripe.Customer.create") as mock_create:
            mock_create.return_value = MagicMock(id="cus_test123")

            await client.create_customer(
                email="test@example.com",
                name="Test Practice",
            )

            mock_create.assert_called_once_with(
                email="test@example.com",
                name="Test Practice",
                metadata={},
            )


class TestCreateCheckoutSession:
    """Tests for create_checkout_session method."""

    @pytest.fixture
    def client(self):
        """Create client with mocked settings."""
        with patch("app.modules.billing.stripe_client.get_settings"):
            return StripeClient()

    @pytest.mark.asyncio
    async def test_creates_checkout_session(self, client):
        """Should create checkout session with correct parameters."""
        get_tier_price_ids.cache_clear()

        with (
            patch("app.modules.billing.stripe_client.get_tier_price_ids") as mock_prices,
            patch("stripe.checkout.Session.create") as mock_create,
        ):
            mock_prices.return_value = {"professional": "price_pro123"}
            mock_create.return_value = MagicMock(
                url="https://checkout.stripe.com/session",
                id="cs_test123",
            )

            checkout_url, session_id = await client.create_checkout_session(
                customer_id="cus_123",
                tier="professional",
                success_url="https://app.test.com/success",
                cancel_url="https://app.test.com/cancel",
                tenant_id="tenant-uuid",
            )

            assert checkout_url == "https://checkout.stripe.com/session"
            assert session_id == "cs_test123"
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_error_for_missing_price(self, client):
        """Should raise ValueError if tier has no configured price."""
        get_tier_price_ids.cache_clear()

        with patch("app.modules.billing.stripe_client.get_tier_price_ids") as mock_prices:
            mock_prices.return_value = {"professional": ""}  # Empty price

            with pytest.raises(ValueError) as exc_info:
                await client.create_checkout_session(
                    customer_id="cus_123",
                    tier="professional",
                    success_url="https://test.com/success",
                    cancel_url="https://test.com/cancel",
                    tenant_id="tenant-uuid",
                )

            assert "No price configured" in str(exc_info.value)


class TestCreatePortalSession:
    """Tests for create_portal_session method."""

    @pytest.fixture
    def client(self):
        """Create client with mocked settings."""
        with patch("app.modules.billing.stripe_client.get_settings"):
            return StripeClient()

    @pytest.mark.asyncio
    async def test_creates_portal_session(self, client):
        """Should create customer portal session."""
        with patch("stripe.billing_portal.Session.create") as mock_create:
            mock_create.return_value = MagicMock(url="https://billing.stripe.com/portal")

            portal_url = await client.create_portal_session(
                customer_id="cus_123",
                return_url="https://app.test.com/billing",
            )

            assert portal_url == "https://billing.stripe.com/portal"
            mock_create.assert_called_once_with(
                customer="cus_123",
                return_url="https://app.test.com/billing",
            )


class TestGetSubscriptionDetails:
    """Tests for get_subscription_details method."""

    @pytest.fixture
    def client(self):
        """Create client with mocked settings."""
        with patch("app.modules.billing.stripe_client.get_settings"):
            return StripeClient()

    @pytest.mark.asyncio
    async def test_returns_subscription_details(self, client):
        """Should return formatted subscription details."""
        with patch("stripe.Subscription.retrieve") as mock_retrieve:
            mock_sub = MagicMock()
            mock_sub.id = "sub_123"
            mock_sub.status = "active"
            mock_sub.current_period_end = 1735689600  # 2025-01-01
            mock_sub.cancel_at_period_end = False
            mock_sub.metadata = {"tier": "professional"}
            mock_retrieve.return_value = mock_sub

            details = await client.get_subscription_details("sub_123")

            assert details["id"] == "sub_123"
            assert details["status"] == "active"
            assert details["cancel_at_period_end"] is False
            assert details["metadata"]["tier"] == "professional"


class TestUpgradeSubscription:
    """Tests for upgrade_subscription method."""

    @pytest.fixture
    def client(self):
        """Create client with mocked settings."""
        with patch("app.modules.billing.stripe_client.get_settings"):
            return StripeClient()

    @pytest.mark.asyncio
    async def test_upgrades_subscription(self, client):
        """Should upgrade subscription with proration."""
        get_tier_price_ids.cache_clear()

        with (
            patch("app.modules.billing.stripe_client.get_tier_price_ids") as mock_prices,
            patch("stripe.Subscription.retrieve") as mock_retrieve,
            patch("stripe.Subscription.modify") as mock_modify,
        ):
            mock_prices.return_value = {"professional": "price_pro123"}
            mock_sub = MagicMock()
            mock_sub.__getitem__ = lambda self, key: {"items": {"data": [{"id": "si_123"}]}}[key]
            mock_sub.metadata = {"tier": "starter"}
            mock_retrieve.return_value = mock_sub

            await client.upgrade_subscription(
                subscription_id="sub_123",
                new_tier="professional",
            )

            mock_modify.assert_called_once()
            call_kwargs = mock_modify.call_args.kwargs
            assert call_kwargs["proration_behavior"] == "create_prorations"

    @pytest.mark.asyncio
    async def test_raises_error_for_missing_price(self, client):
        """Should raise ValueError for tier without price."""
        get_tier_price_ids.cache_clear()

        with patch("app.modules.billing.stripe_client.get_tier_price_ids") as mock_prices:
            mock_prices.return_value = {"growth": ""}

            with pytest.raises(ValueError) as exc_info:
                await client.upgrade_subscription("sub_123", "growth")

            assert "No price configured" in str(exc_info.value)


class TestScheduleDowngrade:
    """Tests for schedule_downgrade method."""

    @pytest.fixture
    def client(self):
        """Create client with mocked settings."""
        with patch("app.modules.billing.stripe_client.get_settings"):
            return StripeClient()

    @pytest.mark.asyncio
    async def test_schedules_downgrade(self, client):
        """Should create subscription schedule for downgrade."""
        get_tier_price_ids.cache_clear()

        with (
            patch("app.modules.billing.stripe_client.get_tier_price_ids") as mock_prices,
            patch("stripe.Subscription.retrieve") as mock_retrieve,
            patch("stripe.SubscriptionSchedule.create") as mock_schedule_create,
            patch("stripe.SubscriptionSchedule.modify") as mock_schedule_modify,
        ):
            mock_prices.return_value = {"starter": "price_starter123"}
            mock_sub = MagicMock()
            mock_sub.current_period_end = 1735689600
            mock_sub.schedule = None
            mock_sub.__getitem__ = lambda self, key: {
                "items": {"data": [{"price": {"id": "price_pro123"}}]}
            }[key]
            mock_retrieve.return_value = mock_sub

            mock_schedule = MagicMock()
            mock_schedule.id = "sub_sched_123"
            mock_schedule.phases = [{"start_date": 1704067200}]
            mock_schedule_create.return_value = mock_schedule

            effective_date = await client.schedule_downgrade(
                subscription_id="sub_123",
                new_tier="starter",
            )

            assert isinstance(effective_date, datetime)
            mock_schedule_create.assert_called_once()
            mock_schedule_modify.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_existing_schedule(self, client):
        """Should use existing schedule if present."""
        get_tier_price_ids.cache_clear()

        with (
            patch("app.modules.billing.stripe_client.get_tier_price_ids") as mock_prices,
            patch("stripe.Subscription.retrieve") as mock_retrieve,
            patch("stripe.SubscriptionSchedule.retrieve") as mock_schedule_retrieve,
            patch("stripe.SubscriptionSchedule.create") as mock_schedule_create,
            patch("stripe.SubscriptionSchedule.modify") as mock_schedule_modify,
        ):
            mock_prices.return_value = {"starter": "price_starter123"}
            mock_sub = MagicMock()
            mock_sub.current_period_end = 1735689600
            mock_sub.schedule = "sub_sched_existing"
            mock_sub.__getitem__ = lambda self, key: {
                "items": {"data": [{"price": {"id": "price_pro123"}}]}
            }[key]
            mock_retrieve.return_value = mock_sub

            mock_schedule = MagicMock()
            mock_schedule.id = "sub_sched_existing"
            mock_schedule.phases = [{"start_date": 1704067200}]
            mock_schedule_retrieve.return_value = mock_schedule

            await client.schedule_downgrade("sub_123", "starter")

            mock_schedule_create.assert_not_called()
            mock_schedule_retrieve.assert_called_once()


class TestCancelSubscription:
    """Tests for cancel_subscription method."""

    @pytest.fixture
    def client(self):
        """Create client with mocked settings."""
        with patch("app.modules.billing.stripe_client.get_settings"):
            return StripeClient()

    @pytest.mark.asyncio
    async def test_cancels_subscription_at_period_end(self, client):
        """Should set cancel_at_period_end to True."""
        with (
            patch("stripe.Subscription.retrieve") as mock_retrieve,
            patch("stripe.Subscription.modify") as mock_modify,
        ):
            mock_sub = MagicMock()
            mock_sub.schedule = None
            mock_sub.current_period_end = 1735689600
            mock_retrieve.return_value = mock_sub
            mock_modify.return_value = mock_sub

            effective_date = await client.cancel_subscription(
                subscription_id="sub_123",
                reason="Too expensive",
                feedback="Budget cuts",
            )

            assert isinstance(effective_date, datetime)
            mock_modify.assert_called_once()
            call_kwargs = mock_modify.call_args.kwargs
            assert call_kwargs["cancel_at_period_end"] is True
            assert call_kwargs["metadata"]["cancel_reason"] == "Too expensive"
            assert call_kwargs["metadata"]["cancel_feedback"] == "Budget cuts"

    @pytest.mark.asyncio
    async def test_releases_schedule_before_cancel(self, client):
        """Should release schedule if subscription has one."""
        with (
            patch("stripe.Subscription.retrieve") as mock_retrieve,
            patch("stripe.Subscription.modify") as mock_modify,
            patch("stripe.SubscriptionSchedule.release") as mock_release,
        ):
            mock_sub = MagicMock()
            mock_sub.schedule = "sub_sched_123"
            mock_sub.current_period_end = 1735689600
            mock_retrieve.return_value = mock_sub
            mock_modify.return_value = mock_sub

            await client.cancel_subscription("sub_123")

            mock_release.assert_called_once_with("sub_sched_123")


class TestVerifyWebhookSignature:
    """Tests for verify_webhook_signature method."""

    @pytest.fixture
    def client(self):
        """Create client with mocked settings."""
        with patch("app.modules.billing.stripe_client.get_settings"):
            return StripeClient()

    def test_verifies_valid_signature(self, client):
        """Should return event for valid signature."""
        with patch("stripe.Webhook.construct_event") as mock_construct:
            mock_event = MagicMock()
            mock_event.__iter__ = lambda self: iter({"type": "invoice.paid", "data": {}}.items())
            mock_construct.return_value = mock_event

            event = client.verify_webhook_signature(
                payload=b'{"test": "data"}',
                signature="sig_123",
                webhook_secret="whsec_123",
            )

            mock_construct.assert_called_once_with(
                payload=b'{"test": "data"}',
                sig_header="sig_123",
                secret="whsec_123",
            )

    def test_raises_on_invalid_signature(self, client):
        """Should raise SignatureVerificationError for invalid signature."""
        with patch("stripe.Webhook.construct_event") as mock_construct:
            mock_construct.side_effect = stripe.error.SignatureVerificationError(
                "Invalid signature", "sig_123"
            )

            with pytest.raises(stripe.error.SignatureVerificationError):
                client.verify_webhook_signature(
                    payload=b'{"test": "data"}',
                    signature="invalid_sig",
                    webhook_secret="whsec_123",
                )


class TestGetSubscriptionPeriodEnd:
    """Tests for _get_subscription_period_end helper method."""

    @pytest.fixture
    def client(self):
        """Create client with mocked settings."""
        with patch("app.modules.billing.stripe_client.get_settings"):
            return StripeClient()

    def test_returns_direct_period_end(self, client):
        """Should return current_period_end when directly available."""
        mock_sub = MagicMock()
        mock_sub.current_period_end = 1735689600

        result = client._get_subscription_period_end(mock_sub)

        assert result == 1735689600

    def test_falls_back_to_invoice(self, client):
        """Should get period end from invoice when not on subscription."""
        with patch("stripe.Invoice.retrieve") as mock_invoice_retrieve:
            mock_sub = MagicMock()
            mock_sub.current_period_end = None
            mock_sub.latest_invoice = "in_123"
            mock_sub.billing_cycle_anchor = 1704067200

            mock_invoice = MagicMock()
            mock_invoice.lines.data = [MagicMock()]
            mock_invoice.lines.data[0].period = {"end": 1735689600}
            mock_invoice_retrieve.return_value = mock_invoice

            result = client._get_subscription_period_end(mock_sub)

            assert result == 1735689600

    def test_falls_back_to_billing_anchor(self, client):
        """Should calculate from billing_cycle_anchor as last resort."""
        mock_sub = MagicMock()
        mock_sub.current_period_end = None
        mock_sub.latest_invoice = None
        mock_sub.billing_cycle_anchor = 1704067200

        result = client._get_subscription_period_end(mock_sub)

        # billing_cycle_anchor + 30 days
        expected = 1704067200 + (30 * 24 * 60 * 60)
        assert result == expected
