"""Stripe webhook handlers.

Processes incoming Stripe webhook events for subscription management.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import SubscriptionStatus, SubscriptionTier, Tenant
from app.modules.billing.repository import BillingEventRepository

logger = structlog.get_logger(__name__)


class WebhookHandler:
    """Handles Stripe webhook events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.event_repository = BillingEventRepository(session)

    async def process_event(self, event: dict) -> bool:
        """Process a Stripe webhook event.

        Returns True if processed, False if already handled (idempotent).
        """
        event_id = event.get("id", "")
        event_type = event.get("type", "")
        event_data = event.get("data", {}).get("object", {})

        # Check for idempotency
        existing = await self.event_repository.get_by_stripe_event_id(event_id)
        if existing:
            logger.info("webhook_already_processed", event_id=event_id, event_type=event_type)
            return False

        # Get tenant from event metadata
        tenant_id = await self._get_tenant_id_from_event(event_data)
        if not tenant_id:
            logger.warning("webhook_no_tenant", event_id=event_id, event_type=event_type)
            return True

        # Verify the tenant actually exists before processing
        tenant = await self._get_tenant(tenant_id)
        if not tenant:
            logger.warning(
                "webhook_tenant_not_found",
                event_id=event_id,
                event_type=event_type,
                tenant_id=str(tenant_id),
            )
            return True

        # Route to appropriate handler
        handler_map = {
            "checkout.session.completed": self._handle_checkout_session_completed,
            "customer.subscription.created": self._handle_subscription_created,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "customer.subscription.trial_will_end": self._handle_trial_will_end,
            "invoice.paid": self._handle_invoice_paid,
            "invoice.payment_failed": self._handle_invoice_payment_failed,
        }

        handler = handler_map.get(event_type)
        if handler:
            await handler(tenant_id, event_data)

        # Record the event
        await self.event_repository.create(
            tenant_id=tenant_id,
            stripe_event_id=event_id,
            event_type=event_type,
            event_data=event,
            amount_cents=self._extract_amount(event_data),
        )

        logger.info("webhook_processed", event_id=event_id, event_type=event_type)
        return True

    async def _get_tenant_id_from_event(self, event_data: dict) -> UUID | None:
        """Extract tenant_id from event metadata or customer lookup."""
        # Try metadata first
        metadata = event_data.get("metadata", {})
        tenant_id_str = metadata.get("tenant_id")
        if tenant_id_str:
            try:
                return UUID(tenant_id_str)
            except ValueError:
                pass

        # Try to find by customer ID
        customer_id = event_data.get("customer")
        if customer_id:
            result = await self.session.execute(
                select(Tenant).where(Tenant.stripe_customer_id == customer_id)
            )
            tenant = result.scalar_one_or_none()
            if tenant:
                return tenant.id

        return None

    def _extract_amount(self, event_data: dict) -> int | None:
        """Extract amount in cents from event data."""
        # For invoice events
        if "amount_paid" in event_data:
            return event_data["amount_paid"]
        if "amount_due" in event_data:
            return event_data["amount_due"]
        return None

    async def _get_tenant(self, tenant_id: UUID) -> Tenant | None:
        """Get tenant by ID."""
        result = await self.session.execute(select(Tenant).where(Tenant.id == tenant_id))
        return result.scalar_one_or_none()

    async def _handle_checkout_session_completed(
        self, tenant_id: UUID, event_data: dict[str, Any]
    ) -> None:
        """Handle checkout.session.completed event.

        This event fires when a customer completes Stripe Checkout.
        We use it to update the tenant's tier from the session metadata,
        ensuring the selected tier is applied even if the subscription
        webhook is delayed or fails.
        """
        tenant = await self._get_tenant(tenant_id)
        if not tenant:
            logger.warning(
                "checkout_session_completed_no_tenant",
                tenant_id=str(tenant_id),
            )
            return

        # Get tier from session metadata
        metadata = event_data.get("metadata", {})
        tier_str = metadata.get("tier")

        if tier_str:
            try:
                tier = SubscriptionTier(tier_str)
                tenant.tier = tier
                logger.info(
                    "checkout_session_tier_updated",
                    tenant_id=str(tenant_id),
                    tier=tier_str,
                )
            except ValueError:
                logger.warning(
                    "checkout_session_invalid_tier",
                    tenant_id=str(tenant_id),
                    tier=tier_str,
                )
        else:
            logger.warning(
                "checkout_session_no_tier_metadata",
                tenant_id=str(tenant_id),
                metadata=metadata,
            )

        # Update subscription ID if present
        subscription_id = event_data.get("subscription")
        if subscription_id:
            tenant.stripe_subscription_id = subscription_id

        # Update customer ID if present and not already set
        customer_id = event_data.get("customer")
        if customer_id and not tenant.stripe_customer_id:
            tenant.stripe_customer_id = customer_id

        # Set status to trial or active based on subscription mode
        mode = event_data.get("mode")
        if mode == "subscription":
            # If trial period was set, status will be TRIAL
            # The subscription.created webhook will set the correct status
            # For now, ensure we're not in an invalid state
            if tenant.subscription_status == SubscriptionStatus.TRIAL:
                pass  # Keep trial status
            else:
                tenant.subscription_status = SubscriptionStatus.ACTIVE

        await self.session.flush()
        logger.info(
            "checkout_session_completed",
            tenant_id=str(tenant_id),
            tier=tier_str,
            subscription_id=subscription_id,
        )

    async def _handle_subscription_created(
        self, tenant_id: UUID, event_data: dict[str, Any]
    ) -> None:
        """Handle subscription.created event."""
        tenant = await self._get_tenant(tenant_id)
        if not tenant:
            return

        # Extract tier from metadata or price
        metadata = event_data.get("metadata", {})
        tier_str = metadata.get("tier", "professional")
        tier = SubscriptionTier(tier_str)

        tenant.tier = tier
        tenant.stripe_subscription_id = event_data.get("id")

        # Set status based on Stripe subscription status
        stripe_status = event_data.get("status", "active")
        if stripe_status == "trialing":
            tenant.subscription_status = SubscriptionStatus.TRIAL
        else:
            tenant.subscription_status = SubscriptionStatus.ACTIVE

        tenant.current_period_end = datetime.fromtimestamp(
            event_data.get("current_period_end", 0), tz=UTC
        )

        await self.session.flush()
        logger.info(
            "subscription_created",
            tenant_id=str(tenant_id),
            tier=tier_str,
            subscription_id=tenant.stripe_subscription_id,
        )

    async def _handle_subscription_updated(
        self, tenant_id: UUID, event_data: dict[str, Any]
    ) -> None:
        """Handle subscription.updated event."""
        tenant = await self._get_tenant(tenant_id)
        if not tenant:
            return

        # Update tier if changed
        metadata = event_data.get("metadata", {})
        tier_str = metadata.get("tier")
        if tier_str:
            tenant.tier = SubscriptionTier(tier_str)

        # Update status
        stripe_status = event_data.get("status", "")
        if stripe_status == "active":
            tenant.subscription_status = SubscriptionStatus.ACTIVE
        elif stripe_status == "trialing":
            tenant.subscription_status = SubscriptionStatus.TRIAL
        elif stripe_status == "paused":
            tenant.subscription_status = SubscriptionStatus.SUSPENDED
        elif stripe_status == "past_due":
            tenant.subscription_status = SubscriptionStatus.PAST_DUE
        elif stripe_status in ("canceled", "cancelled"):
            tenant.subscription_status = SubscriptionStatus.CANCELLED

        # Update period end
        period_end = event_data.get("current_period_end")
        if period_end:
            tenant.current_period_end = datetime.fromtimestamp(period_end, tz=UTC)

        await self.session.flush()
        logger.info(
            "subscription_updated",
            tenant_id=str(tenant_id),
            status=tenant.subscription_status.value,
        )

    async def _handle_subscription_deleted(
        self, tenant_id: UUID, _event_data: dict[str, Any]
    ) -> None:
        """Handle subscription.deleted event."""
        tenant = await self._get_tenant(tenant_id)
        if not tenant:
            return

        tenant.subscription_status = SubscriptionStatus.CANCELLED
        tenant.stripe_subscription_id = None

        await self.session.flush()
        logger.info("subscription_deleted", tenant_id=str(tenant_id))

    async def _handle_invoice_paid(self, tenant_id: UUID, event_data: dict[str, Any]) -> None:
        """Handle invoice.paid event.

        If this is the first invoice after trial, this is a trial conversion.
        Updates subscription status and sends confirmation email.

        Spec 021: Onboarding Flow - Free Trial Experience
        """
        tenant = await self._get_tenant(tenant_id)
        if not tenant:
            return

        # Check if this is trial conversion (first payment after trial)
        was_trial = tenant.subscription_status == SubscriptionStatus.TRIAL
        billing_reason = event_data.get("billing_reason", "")
        is_trial_conversion = was_trial or billing_reason == "subscription_cycle"

        # Update period end from invoice
        period_end = event_data.get("lines", {}).get("data", [{}])[0].get("period", {}).get("end")
        next_billing_date = None
        if period_end:
            next_billing_date = datetime.fromtimestamp(period_end, tz=UTC)
            tenant.current_period_end = next_billing_date

        # Update status to active (handles both trial conversion and past_due recovery)
        if tenant.subscription_status in (SubscriptionStatus.TRIAL, SubscriptionStatus.PAST_DUE):
            tenant.subscription_status = SubscriptionStatus.ACTIVE

        await self.session.flush()

        # Send trial conversion email if applicable
        if was_trial and event_data.get("amount_paid", 0) > 0:
            await self._send_trial_converted_email(tenant, next_billing_date)

        logger.info(
            "invoice_paid",
            tenant_id=str(tenant_id),
            amount=event_data.get("amount_paid", 0),
            was_trial=was_trial,
            is_trial_conversion=is_trial_conversion,
        )

    async def _handle_invoice_payment_failed(
        self, tenant_id: UUID, event_data: dict[str, Any]
    ) -> None:
        """Handle invoice.payment_failed event.

        Updates subscription status to PAST_DUE and sends payment failed email.
        Starts 7-day grace period before suspension.

        Spec 021: Onboarding Flow - Free Trial Experience
        """
        tenant = await self._get_tenant(tenant_id)
        if not tenant:
            return

        # Update status to past_due (grace period starts)
        was_trial = tenant.subscription_status == SubscriptionStatus.TRIAL
        tenant.subscription_status = SubscriptionStatus.PAST_DUE

        await self.session.flush()

        # Send payment failed email (7-day grace period)
        await self._send_payment_failed_email(tenant, grace_period_days=7)

        logger.warning(
            "invoice_payment_failed",
            tenant_id=str(tenant_id),
            amount=event_data.get("amount_due", 0),
            was_trial=was_trial,
        )

    async def _handle_trial_will_end(self, tenant_id: UUID, event_data: dict[str, Any]) -> None:
        """Handle subscription.trial_will_end event.

        Sent by Stripe 3 days before trial ends.
        Sends final trial reminder email.

        Spec 021: Onboarding Flow - Free Trial Experience
        """
        tenant = await self._get_tenant(tenant_id)
        if not tenant:
            return

        # Only send if actually in trial
        if tenant.subscription_status != SubscriptionStatus.TRIAL:
            logger.info(
                "trial_will_end_skipped_not_trial",
                tenant_id=str(tenant_id),
                status=tenant.subscription_status.value,
            )
            return

        # Send final trial reminder email
        await self._send_trial_reminder_email(tenant, days_remaining=3)

        logger.info(
            "trial_will_end_handled",
            tenant_id=str(tenant_id),
            tier=tenant.tier.value,
        )

    # =========================================================================
    # Email Helpers (Spec 021)
    # =========================================================================

    async def _send_trial_reminder_email(self, tenant: Tenant, days_remaining: int) -> None:
        """Send trial reminder email to tenant owner.

        Spec 021: Onboarding Flow - Free Trial Experience
        """
        from app.config import get_settings
        from app.core.feature_flags import TIER_PRICING
        from app.modules.notifications.email_service import EmailService
        from app.modules.notifications.templates import EmailTemplates

        if not tenant.owner_email:
            logger.warning(
                "trial_reminder_no_email",
                tenant_id=str(tenant.id),
            )
            return

        settings = get_settings()
        price_monthly = TIER_PRICING.get(tenant.tier.value, 0)
        billing_date = (
            tenant.current_period_end.strftime("%B %d, %Y") if tenant.current_period_end else "soon"
        )

        template = EmailTemplates.trial_reminder(
            user_name=tenant.name,
            practice_name=tenant.name,
            days_remaining=days_remaining,
            tier=tenant.tier.value,
            price_monthly=price_monthly,
            billing_date=billing_date,
            billing_url=f"{settings.frontend_url}/settings/billing",
        )

        try:
            email_service = EmailService()
            await email_service.send(
                to_email=tenant.owner_email,
                subject=template.subject,
                html_content=template.html,
                text_content=template.text,
            )
            logger.info(
                "trial_reminder_sent",
                tenant_id=str(tenant.id),
                days_remaining=days_remaining,
            )
        except Exception as e:
            logger.error(
                "trial_reminder_failed",
                tenant_id=str(tenant.id),
                error=str(e),
            )

    async def _send_trial_converted_email(
        self, tenant: Tenant, next_billing_date: datetime | None
    ) -> None:
        """Send trial conversion success email.

        Spec 021: Onboarding Flow - Free Trial Experience
        """
        from app.config import get_settings
        from app.core.feature_flags import TIER_PRICING
        from app.modules.notifications.email_service import EmailService
        from app.modules.notifications.templates import EmailTemplates

        if not tenant.owner_email:
            return

        settings = get_settings()
        price_monthly = TIER_PRICING.get(tenant.tier.value, 0)
        next_billing_str = (
            next_billing_date.strftime("%B %d, %Y") if next_billing_date else "next month"
        )

        template = EmailTemplates.trial_converted(
            user_name=tenant.name,
            practice_name=tenant.name,
            tier=tenant.tier.value,
            price_monthly=price_monthly,
            next_billing_date=next_billing_str,
            dashboard_url=f"{settings.frontend_url}/dashboard",
        )

        try:
            email_service = EmailService()
            await email_service.send(
                to_email=tenant.owner_email,
                subject=template.subject,
                html_content=template.html,
                text_content=template.text,
            )
            logger.info("trial_converted_email_sent", tenant_id=str(tenant.id))
        except Exception as e:
            logger.error(
                "trial_converted_email_failed",
                tenant_id=str(tenant.id),
                error=str(e),
            )

    async def _send_payment_failed_email(self, tenant: Tenant, grace_period_days: int) -> None:
        """Send payment failed email with grace period notice.

        Spec 021: Onboarding Flow - Free Trial Experience
        """
        from app.config import get_settings
        from app.modules.notifications.email_service import EmailService
        from app.modules.notifications.templates import EmailTemplates

        if not tenant.owner_email:
            return

        settings = get_settings()

        template = EmailTemplates.payment_failed(
            user_name=tenant.name,
            practice_name=tenant.name,
            tier=tenant.tier.value,
            grace_period_days=grace_period_days,
            update_payment_url=f"{settings.frontend_url}/settings/billing",
        )

        try:
            email_service = EmailService()
            await email_service.send(
                to_email=tenant.owner_email,
                subject=template.subject,
                html_content=template.html,
                text_content=template.text,
            )
            logger.info("payment_failed_email_sent", tenant_id=str(tenant.id))
        except Exception as e:
            logger.error(
                "payment_failed_email_failed",
                tenant_id=str(tenant.id),
                error=str(e),
            )
