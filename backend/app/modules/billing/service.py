"""Billing module business logic service.

Handles subscription management, checkout sessions, and billing operations.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.feature_flags import (
    TIER_ORDER,
    get_client_limit,
    get_next_tier,
    get_tier_features,
)
from app.modules.billing.exceptions import (
    ClientLimitExceededError,
    InvalidTierChangeError,
    SubscriptionError,
)
from app.modules.billing.repository import BillingEventRepository, UsageRepository
from app.modules.billing.schemas import (
    SubscriptionTierType,
    ThresholdWarningType,
    TierFeatures,
    UsageInfo,
    UsageMetrics,
)
from app.modules.billing.stripe_client import StripeClient

if TYPE_CHECKING:
    from app.modules.auth.models import Tenant

logger = structlog.get_logger(__name__)


class BillingService:
    """Service for billing and subscription operations."""

    def __init__(
        self,
        session: AsyncSession,
        stripe_client: StripeClient | None = None,
    ) -> None:
        self.session = session
        self.stripe_client = stripe_client or StripeClient()
        self.event_repository = BillingEventRepository(session)
        self.usage_repository = UsageRepository(session)

    # =========================================================================
    # Checkout Operations
    # =========================================================================

    async def create_checkout_session(
        self,
        tenant: "Tenant",
        tier: SubscriptionTierType,
        success_url: str,
        cancel_url: str,
        trial_period_days: int | None = None,
    ) -> tuple[str, str]:
        """Create a Stripe checkout session for subscription.

        Args:
            tenant: The tenant subscribing
            tier: Subscription tier
            success_url: URL to redirect on success
            cancel_url: URL to redirect on cancel
            trial_period_days: Optional free trial days (default 14 for onboarding)

        Returns tuple of (checkout_url, session_id).
        """
        if tier == "enterprise":
            raise SubscriptionError("Enterprise tier requires manual setup. Contact sales.")

        # Create or get Stripe customer
        if not tenant.stripe_customer_id:
            customer_id = await self.stripe_client.create_customer(
                email=tenant.owner_email or f"{tenant.slug}@clairo.com.au",
                name=tenant.name,
                metadata={"tenant_id": str(tenant.id)},
            )
            tenant.stripe_customer_id = customer_id
            await self.session.flush()
        else:
            customer_id = tenant.stripe_customer_id

        # Create checkout session with optional trial
        checkout_url, session_id = await self.stripe_client.create_checkout_session(
            customer_id=customer_id,
            tier=tier,
            success_url=success_url,
            cancel_url=cancel_url,
            tenant_id=str(tenant.id),
            trial_period_days=trial_period_days,
        )

        logger.info(
            "checkout_session_created",
            tenant_id=str(tenant.id),
            tier=tier,
            session_id=session_id,
            trial_days=trial_period_days,
        )

        return checkout_url, session_id

    async def start_trial(
        self,
        tenant: "Tenant",
        tier: SubscriptionTierType,
        trial_period_days: int = 14,
    ) -> dict:
        """Create a Stripe trial subscription (no payment method required).

        Args:
            tenant: The tenant subscribing
            tier: Subscription tier
            trial_period_days: Trial period in days (default: 14)

        Returns dict with id, status, current_period_end from Stripe.

        Raises:
            SubscriptionError: If tenant already has a subscription or tier is enterprise.
        """
        from app.modules.auth.models import SubscriptionStatus

        if tier == "enterprise":
            raise SubscriptionError("Enterprise tier requires manual setup. Contact sales.")

        if tenant.stripe_subscription_id:
            raise SubscriptionError("Tenant already has an active subscription.")

        # Create or get Stripe customer
        if not tenant.stripe_customer_id:
            customer_id = await self.stripe_client.create_customer(
                email=tenant.owner_email or f"{tenant.slug}@clairo.com.au",
                name=tenant.name,
                metadata={"tenant_id": str(tenant.id)},
            )
            tenant.stripe_customer_id = customer_id
            await self.session.flush()
        else:
            customer_id = tenant.stripe_customer_id

        # Create trial subscription
        result = await self.stripe_client.create_trial_subscription(
            customer_id=customer_id,
            tier=tier,
            tenant_id=str(tenant.id),
            trial_period_days=trial_period_days,
        )

        # Update tenant
        tenant.stripe_subscription_id = result["id"]
        tenant.tier = tier  # type: ignore[assignment]
        tenant.subscription_status = SubscriptionStatus.TRIAL
        tenant.current_period_end = result["current_period_end"]
        await self.session.flush()

        logger.info(
            "trial_started",
            tenant_id=str(tenant.id),
            tier=tier,
            subscription_id=result["id"],
            trial_days=trial_period_days,
        )

        return result

    async def create_portal_session(
        self,
        tenant: "Tenant",
        return_url: str,
    ) -> str:
        """Create a Stripe Customer Portal session.

        Returns the portal URL.
        """
        if not tenant.stripe_customer_id:
            raise SubscriptionError("No billing account found. Subscribe first.")

        portal_url = await self.stripe_client.create_portal_session(
            customer_id=tenant.stripe_customer_id,
            return_url=return_url,
        )

        return portal_url

    # =========================================================================
    # Subscription Management
    # =========================================================================

    async def upgrade_subscription(
        self,
        tenant: "Tenant",
        new_tier: SubscriptionTierType,
    ) -> None:
        """Upgrade subscription to a higher tier with proration.

        Updates are immediate with prorated charge.
        """
        current_tier: SubscriptionTierType = tenant.tier.value  # type: ignore[assignment]
        current_index = TIER_ORDER.index(current_tier)
        new_index = TIER_ORDER.index(new_tier)

        if new_index <= current_index:
            raise InvalidTierChangeError(
                current_tier=current_tier,
                requested_tier=new_tier,
                reason="New tier must be higher than current tier for upgrade",
            )

        if new_tier == "enterprise":
            raise InvalidTierChangeError(
                current_tier=current_tier,
                requested_tier=new_tier,
                reason="Enterprise tier requires manual setup. Contact sales.",
            )

        if not tenant.stripe_subscription_id:
            raise SubscriptionError("No active subscription. Use checkout to subscribe.")

        await self.stripe_client.upgrade_subscription(
            subscription_id=tenant.stripe_subscription_id,
            new_tier=new_tier,
        )

        # Update local record (webhook will confirm)
        tenant.tier = new_tier  # type: ignore[assignment]
        await self.session.flush()

        logger.info(
            "subscription_upgraded",
            tenant_id=str(tenant.id),
            from_tier=current_tier,
            to_tier=new_tier,
        )

    async def schedule_downgrade(
        self,
        tenant: "Tenant",
        new_tier: SubscriptionTierType,
    ) -> datetime:
        """Schedule a downgrade to take effect at next billing cycle.

        Returns the effective date of the change.
        """
        current_tier: SubscriptionTierType = tenant.tier.value  # type: ignore[assignment]
        current_index = TIER_ORDER.index(current_tier)
        new_index = TIER_ORDER.index(new_tier)

        if new_index >= current_index:
            raise InvalidTierChangeError(
                current_tier=current_tier,
                requested_tier=new_tier,
                reason="New tier must be lower than current tier for downgrade",
            )

        # Check client limit
        new_limit = get_client_limit(new_tier)
        if new_limit is not None and tenant.client_count > new_limit:
            # Allow downgrade but warn - they won't be able to add more clients
            logger.warning(
                "downgrade_exceeds_client_limit",
                tenant_id=str(tenant.id),
                current_count=tenant.client_count,
                new_limit=new_limit,
                new_tier=new_tier,
            )

        if not tenant.stripe_subscription_id:
            raise SubscriptionError("No active subscription.")

        effective_date = await self.stripe_client.schedule_downgrade(
            subscription_id=tenant.stripe_subscription_id,
            new_tier=new_tier,
        )

        logger.info(
            "subscription_downgrade_scheduled",
            tenant_id=str(tenant.id),
            from_tier=current_tier,
            to_tier=new_tier,
            effective_date=effective_date.isoformat(),
        )

        return effective_date

    async def cancel_subscription(
        self,
        tenant: "Tenant",
        reason: str | None = None,
        feedback: str | None = None,
    ) -> datetime:
        """Cancel subscription at end of current period.

        Returns the date access ends.
        """
        if not tenant.stripe_subscription_id:
            raise SubscriptionError("No active subscription to cancel.")

        effective_date = await self.stripe_client.cancel_subscription(
            subscription_id=tenant.stripe_subscription_id,
            reason=reason,
            feedback=feedback,
        )

        logger.info(
            "subscription_cancellation_scheduled",
            tenant_id=str(tenant.id),
            tier=tenant.tier.value,
            effective_date=effective_date.isoformat(),
            reason=reason,
        )

        return effective_date

    # =========================================================================
    # Usage & Limits
    # =========================================================================

    def get_usage_info(self, tenant: "Tenant") -> UsageInfo:
        """Get client usage information for a tenant."""
        tier: SubscriptionTierType = tenant.tier.value  # type: ignore[assignment]
        limit = get_client_limit(tier)
        count = tenant.client_count

        if limit is None:
            # Unlimited
            return UsageInfo(
                client_count=count,
                client_limit=None,
                is_at_limit=False,
                is_approaching_limit=False,
                percentage_used=None,
            )

        percentage = (count / limit * 100) if limit > 0 else 0
        return UsageInfo(
            client_count=count,
            client_limit=limit,
            is_at_limit=count >= limit,
            is_approaching_limit=percentage >= 80,
            percentage_used=percentage,
        )

    def check_client_limit(self, tenant: "Tenant") -> bool:
        """Check if tenant can add a new client.

        Returns True if allowed, raises ClientLimitExceededError if not.
        """
        return self.check_can_add_clients(tenant, count=1)

    def check_can_add_clients(self, tenant: "Tenant", count: int = 1) -> bool:
        """Check if tenant can add the specified number of clients.

        Used for batch operations like Xero sync that may add multiple clients at once.

        Args:
            tenant: The tenant to check.
            count: Number of clients to be added (default 1).

        Returns:
            True if allowed, raises ClientLimitExceededError if not.

        Raises:
            ClientLimitExceededError: If adding would exceed the limit.
        """
        tier: SubscriptionTierType = tenant.tier.value  # type: ignore[assignment]
        limit = get_client_limit(tier)

        if limit is None:
            return True  # Unlimited

        projected_count = tenant.client_count + count
        if projected_count > limit:
            next_tier = get_next_tier(tier)
            raise ClientLimitExceededError(
                current_count=tenant.client_count,
                limit=limit,
                required_tier=next_tier,
            )

        return True

    def get_remaining_client_slots(self, tenant: "Tenant") -> int | None:
        """Get the number of clients that can still be added.

        Returns:
            Number of available slots, or None if unlimited.
        """
        tier: SubscriptionTierType = tenant.tier.value  # type: ignore[assignment]
        limit = get_client_limit(tier)

        if limit is None:
            return None  # Unlimited

        return max(0, limit - tenant.client_count)

    def get_tier_features_for_tenant(self, tenant: "Tenant") -> TierFeatures:
        """Get feature configuration for a tenant's tier."""
        tier: SubscriptionTierType = tenant.tier.value  # type: ignore[assignment]
        features = get_tier_features(tier)
        return TierFeatures(**features)

    def _get_threshold_warning(self, percentage: float | None) -> ThresholdWarningType | None:
        """Determine threshold warning level based on usage percentage."""
        if percentage is None:
            return None
        if percentage >= 100:
            return "100%"
        if percentage >= 90:
            return "90%"
        if percentage >= 80:
            return "80%"
        return None

    def get_usage_metrics(self, tenant: "Tenant") -> UsageMetrics:
        """Get extended usage metrics for the usage dashboard.

        Includes client count, AI queries, documents, and threshold warnings.
        """
        tier: SubscriptionTierType = tenant.tier.value  # type: ignore[assignment]
        limit = get_client_limit(tier)
        count = tenant.client_count

        # Calculate percentage
        if limit is None:
            percentage = None
            is_at_limit = False
            is_approaching = False
        else:
            percentage = (count / limit * 100) if limit > 0 else 0
            is_at_limit = count >= limit
            is_approaching = percentage >= 80

        # Determine threshold warning
        threshold_warning = self._get_threshold_warning(percentage)

        # Get next tier for upgrade prompt
        next_tier = get_next_tier(tier)

        return UsageMetrics(
            client_count=count,
            client_limit=limit,
            client_percentage=percentage,
            ai_queries_month=tenant.ai_queries_month,
            documents_month=tenant.documents_month,
            is_at_limit=is_at_limit,
            is_approaching_limit=is_approaching,
            threshold_warning=threshold_warning,
            tier=tier,
            next_tier=next_tier,
        )

    # =========================================================================
    # Billing Events
    # =========================================================================

    async def record_billing_event(
        self,
        tenant_id: UUID,
        stripe_event_id: str,
        event_type: str,
        event_data: dict,
        amount_cents: int | None = None,
    ) -> bool:
        """Record a billing event from Stripe webhook.

        Returns True if recorded, False if already processed (idempotent).
        """
        # Check for existing event
        existing = await self.event_repository.get_by_stripe_event_id(stripe_event_id)
        if existing:
            return False

        await self.event_repository.create(
            tenant_id=tenant_id,
            stripe_event_id=stripe_event_id,
            event_type=event_type,
            event_data=event_data,
            amount_cents=amount_cents,
        )

        return True

    async def list_billing_events(
        self,
        tenant_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """List billing events for a tenant."""
        events, total = await self.event_repository.list_by_tenant(
            tenant_id=tenant_id,
            limit=limit,
            offset=offset,
        )

        return [
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "amount_cents": event.amount_cents,
                "currency": event.currency,
                "status": event.status.value,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ], total
