"""Stripe API client wrapper.

Encapsulates all Stripe API interactions for subscription management.
"""

from datetime import UTC, datetime
from functools import lru_cache

import stripe

from app.config import get_settings
from app.modules.billing.schemas import SubscriptionTierType


@lru_cache
def get_tier_price_ids() -> dict[SubscriptionTierType, str]:
    """Get tier to Stripe price ID mapping from settings."""
    settings = get_settings()
    return {
        "starter": settings.stripe.price_starter or "",
        "professional": settings.stripe.price_professional or "",
        "growth": settings.stripe.price_growth or "",
        "enterprise": "",  # Enterprise is manual
    }


class StripeClient:
    """Client for Stripe API operations."""

    def __init__(self) -> None:
        """Initialize Stripe client with API key from settings."""
        settings = get_settings()
        if settings.stripe and settings.stripe.secret_key:
            stripe.api_key = settings.stripe.secret_key.get_secret_value()

    async def create_customer(
        self,
        email: str,
        name: str,
        metadata: dict | None = None,
    ) -> str:
        """Create a Stripe customer.

        Returns the Stripe customer ID.
        """
        customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata=metadata or {},
        )
        return customer.id

    async def create_checkout_session(
        self,
        customer_id: str,
        tier: SubscriptionTierType,
        success_url: str,
        cancel_url: str,
        tenant_id: str,
        trial_period_days: int | None = None,
    ) -> tuple[str, str]:
        """Create a Stripe Checkout session for subscription.

        Args:
            customer_id: Stripe customer ID
            tier: Subscription tier
            success_url: URL to redirect on success
            cancel_url: URL to redirect on cancel
            tenant_id: Clairo tenant ID
            trial_period_days: Optional trial period in days (default: None)

        Returns tuple of (checkout_url, session_id).
        """
        price_id = get_tier_price_ids().get(tier)
        if not price_id:
            raise ValueError(f"No price configured for tier: {tier}")

        subscription_data: dict = {
            "metadata": {
                "tenant_id": tenant_id,
                "tier": tier,
            }
        }

        # Add trial period if specified
        if trial_period_days and trial_period_days > 0:
            subscription_data["trial_period_days"] = trial_period_days

        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "tenant_id": tenant_id,
                "tier": tier,
            },
            subscription_data=subscription_data,
        )

        return session.url or "", session.id

    async def create_trial_subscription(
        self,
        customer_id: str,
        tier: SubscriptionTierType,
        tenant_id: str,
        trial_period_days: int = 14,
    ) -> dict:
        """Create a Stripe subscription with a free trial (no payment method required).

        Args:
            customer_id: Stripe customer ID
            tier: Subscription tier
            tenant_id: Clairo tenant ID
            trial_period_days: Trial period in days (default: 14)

        Returns dict with id, status, current_period_end.
        """
        price_id = get_tier_price_ids().get(tier)
        if not price_id:
            raise ValueError(f"No price configured for tier: {tier}")

        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            trial_period_days=trial_period_days,
            trial_settings={
                "end_behavior": {"missing_payment_method": "pause"},
            },
            payment_settings={
                "save_default_payment_method": "on_subscription",
            },
            metadata={
                "tenant_id": tenant_id,
                "tier": tier,
            },
        )

        period_end = self._get_subscription_period_end(subscription)
        return {
            "id": subscription.id,
            "status": subscription.status,
            "current_period_end": datetime.fromtimestamp(period_end, tz=UTC),
        }

    async def create_portal_session(
        self,
        customer_id: str,
        return_url: str,
    ) -> str:
        """Create a Stripe Customer Portal session.

        Returns the portal URL.
        """
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return session.url

    async def get_subscription_details(
        self,
        subscription_id: str,
    ) -> dict:
        """Get subscription details from Stripe."""
        subscription = stripe.Subscription.retrieve(subscription_id)
        period_end = self._get_subscription_period_end(subscription)
        return {
            "id": subscription.id,
            "status": subscription.status,
            "current_period_end": datetime.fromtimestamp(period_end, tz=UTC),
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "metadata": dict(subscription.metadata or {}),
        }

    async def upgrade_subscription(
        self,
        subscription_id: str,
        new_tier: SubscriptionTierType,
    ) -> None:
        """Upgrade subscription to a new tier with proration.

        Changes are immediate with prorated charge.
        """
        price_id = get_tier_price_ids().get(new_tier)
        if not price_id:
            raise ValueError(f"No price configured for tier: {new_tier}")

        subscription = stripe.Subscription.retrieve(subscription_id)

        stripe.Subscription.modify(
            subscription_id,
            items=[
                {
                    "id": subscription["items"]["data"][0]["id"],
                    "price": price_id,
                }
            ],
            proration_behavior="create_prorations",
            metadata={
                **dict(subscription.metadata or {}),
                "tier": new_tier,
            },
        )

    def _get_subscription_period_end(self, subscription: stripe.Subscription) -> int:
        """Get the current period end timestamp from a subscription.

        Stripe API may not include current_period_end directly on subscription,
        so we fall back to getting it from the latest invoice's line items.
        """
        # Try direct access first
        if hasattr(subscription, "current_period_end") and subscription.current_period_end is not None:
            return subscription.current_period_end

        # Fall back to invoice line items
        if subscription.latest_invoice:
            invoice = stripe.Invoice.retrieve(subscription.latest_invoice)
            if invoice.lines and invoice.lines.data:
                return getattr(invoice.lines.data[0].period, "end", 0)

        # Last resort: billing_cycle_anchor + 30 days
        return subscription.billing_cycle_anchor + (30 * 24 * 60 * 60)

    async def schedule_downgrade(
        self,
        subscription_id: str,
        new_tier: SubscriptionTierType,
    ) -> datetime:
        """Schedule a downgrade at the end of current billing period.

        Returns the effective date of the change.
        """
        price_id = get_tier_price_ids().get(new_tier)
        if not price_id:
            raise ValueError(f"No price configured for tier: {new_tier}")

        subscription = stripe.Subscription.retrieve(subscription_id)
        period_end = self._get_subscription_period_end(subscription)
        current_price_id = subscription["items"]["data"][0]["price"]["id"]

        # Check if subscription already has a schedule
        if subscription.schedule:
            schedule = stripe.SubscriptionSchedule.retrieve(subscription.schedule)
        else:
            # Create schedule from subscription (no phases allowed with from_subscription)
            schedule = stripe.SubscriptionSchedule.create(
                from_subscription=subscription_id,
            )

        # Update the schedule with the downgrade phases
        stripe.SubscriptionSchedule.modify(
            schedule.id,
            phases=[
                {
                    "items": [{"price": current_price_id}],
                    "start_date": schedule.phases[0]["start_date"],
                    "end_date": period_end,
                },
                {
                    "items": [{"price": price_id}],
                    "metadata": {"tier": new_tier},
                },
            ],
        )

        return datetime.fromtimestamp(period_end, tz=UTC)

    async def cancel_subscription(
        self,
        subscription_id: str,
        reason: str | None = None,
        feedback: str | None = None,
    ) -> datetime:
        """Cancel subscription at end of current period.

        Returns the date when access ends.
        """
        metadata: dict = {}
        if reason:
            metadata["cancel_reason"] = reason
        if feedback:
            metadata["cancel_feedback"] = feedback

        subscription = stripe.Subscription.retrieve(subscription_id)

        # Check if subscription is managed by a schedule
        if subscription.schedule:
            # Cancel by releasing the schedule and setting cancel_at_period_end
            stripe.SubscriptionSchedule.release(subscription.schedule)
            # Now we can modify the subscription
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True,
                metadata=metadata,
            )
        else:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True,
                metadata=metadata,
            )

        period_end = self._get_subscription_period_end(subscription)
        return datetime.fromtimestamp(period_end, tz=UTC)

    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        webhook_secret: str,
    ) -> dict:
        """Verify Stripe webhook signature and return the event.

        Raises stripe.error.SignatureVerificationError if invalid.
        """
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=webhook_secret,
        )
        return dict(event)
