"""Billing module API router.

Endpoints for subscription management, feature access, and billing events.
"""

from typing import Annotated

import stripe
import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.dependencies import get_current_tenant
from app.core.feature_flags import TIER_PRICING, get_tier_features
from app.database import get_db
from app.modules.auth.models import Tenant
from app.modules.billing.schemas import (
    BillingEventResponse,
    BillingEventsResponse,
    CancelRequest,
    CheckoutRequest,
    CheckoutResponse,
    DowngradeRequest,
    FeaturesResponse,
    PortalResponse,
    ScheduledChange,
    SubscriptionResponse,
    TierFeatures,
    TierInfo,
    TiersResponse,
    TrialStatusResponse,
    UpgradeRequest,
    UsageAlertResponse,
    UsageAlertsResponse,
    UsageHistoryResponse,
    UsageInfo,
    UsageMetrics,
    UsageSnapshotResponse,
    WebhookResponse,
)
from app.modules.billing.service import BillingService
from app.modules.billing.stripe_client import StripeClient
from app.modules.billing.webhooks import WebhookHandler
from app.modules.integrations.xero.models import XeroConnection, XeroConnectionStatus

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["billing"])


# =============================================================================
# Dependencies
# =============================================================================


async def get_billing_service(
    session: AsyncSession = Depends(get_db),
) -> BillingService:
    """Get billing service instance."""
    return BillingService(session=session, stripe_client=StripeClient())


# =============================================================================
# Public Endpoints
# =============================================================================


@router.get("/features/tiers", response_model=TiersResponse)
async def list_tiers() -> TiersResponse:
    """List all available subscription tiers with features and pricing.

    This endpoint is public for the pricing page.
    """
    tiers = []
    tier_highlights = {
        "starter": [
            "Up to 25 clients",
            "Basic AI insights",
            "Email support",
        ],
        "professional": [
            "Up to 100 clients",
            "Full AI insights & Magic Zone",
            "Client portal access",
            "Custom triggers",
            "Priority support",
        ],
        "growth": [
            "Up to 250 clients",
            "Everything in Professional",
            "API access",
            "Advanced integrations",
            "Dedicated support",
        ],
        "enterprise": [
            "Unlimited clients",
            "Everything in Growth",
            "Custom integrations",
            "SLA guarantee",
            "Dedicated account manager",
        ],
    }

    for tier_name in ["starter", "professional", "growth", "enterprise"]:
        features = get_tier_features(tier_name)
        price = TIER_PRICING.get(tier_name)

        tiers.append(
            TierInfo(
                name=tier_name,  # type: ignore[arg-type]
                display_name=tier_name.title(),
                price_monthly=price or 0,
                price_id=getattr(get_settings(), f"stripe_price_{tier_name}", None),
                features=TierFeatures(**features),
                highlights=tier_highlights.get(tier_name, []),
            )
        )

    return TiersResponse(tiers=tiers)


# =============================================================================
# Trial Status (Spec 021)
# =============================================================================


@router.get("/trial-status", response_model=TrialStatusResponse)
async def get_trial_status(
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
) -> TrialStatusResponse:
    """Get trial status for the current tenant.

    Returns trial information including:
    - Whether in trial period
    - Days remaining in trial
    - Trial end date (first billing date)
    - Selected tier and price after trial

    Spec 021: Onboarding Flow - Free Trial Experience
    """
    from datetime import UTC, datetime

    from app.modules.auth.models import SubscriptionStatus

    is_trial = tenant.subscription_status == SubscriptionStatus.TRIAL
    tier = tenant.tier.value

    # Get price for tier
    price_monthly = TIER_PRICING.get(tier, 0)

    # Calculate days remaining if in trial
    days_remaining = None
    trial_end_date = None

    if is_trial and tenant.current_period_end:
        trial_end_date = tenant.current_period_end
        now = datetime.now(UTC)
        if trial_end_date.tzinfo is None:
            trial_end_date = trial_end_date.replace(tzinfo=UTC)
        delta = trial_end_date - now
        days_remaining = max(0, delta.days)

    return TrialStatusResponse(
        is_trial=is_trial,
        tier=tier,  # type: ignore[arg-type]
        trial_end_date=trial_end_date,
        days_remaining=days_remaining,
        price_monthly=price_monthly,
        billing_date=trial_end_date,  # First billing is when trial ends
    )


# =============================================================================
# Subscription Endpoints (Authenticated)
# =============================================================================


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
    service: Annotated[BillingService, Depends(get_billing_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionResponse:
    """Get current subscription status."""
    features = service.get_tier_features_for_tenant(tenant)

    # Count active XeroConnections for this tenant (actual client count)
    # Only count active/needs_reauth - not disconnected
    count_query = select(func.count(XeroConnection.id)).where(
        XeroConnection.tenant_id == tenant.id,
        XeroConnection.status != XeroConnectionStatus.DISCONNECTED,
    )
    result = await db.execute(count_query)
    actual_client_count = result.scalar() or 0

    # Get usage info and override with actual count
    usage = service.get_usage_info(tenant)
    usage = UsageInfo(
        client_count=actual_client_count,
        client_limit=usage.client_limit,
        is_at_limit=usage.client_limit is not None and actual_client_count >= usage.client_limit,
        is_approaching_limit=usage.client_limit is not None
        and actual_client_count >= (usage.client_limit * 0.8),
        percentage_used=(actual_client_count / usage.client_limit * 100)
        if usage.client_limit
        else None,
    )

    # Check Stripe for scheduled changes or cancellation
    scheduled_change = None
    if tenant.stripe_subscription_id:
        try:
            import stripe

            settings = get_settings()
            stripe.api_key = settings.stripe.secret_key.get_secret_value()
            sub = stripe.Subscription.retrieve(tenant.stripe_subscription_id)

            if sub.cancel_at_period_end:
                # Get period end from invoice
                period_end = tenant.current_period_end
                if sub.latest_invoice:
                    invoice = stripe.Invoice.retrieve(sub.latest_invoice)
                    if invoice.lines and invoice.lines.data:
                        from datetime import UTC, datetime

                        period_end = datetime.fromtimestamp(
                            invoice.lines.data[0].period.get("end", 0), tz=UTC
                        )
                scheduled_change = ScheduledChange(
                    new_tier=None,
                    effective_date=period_end or tenant.current_period_end,
                    is_cancellation=True,
                )
            elif sub.schedule:
                # Check for scheduled tier change
                schedule = stripe.SubscriptionSchedule.retrieve(sub.schedule)
                if len(schedule.phases) > 1:
                    next_phase = schedule.phases[1]
                    tier = next_phase.get("metadata", {}).get("tier")
                    if tier:
                        from datetime import UTC, datetime

                        scheduled_change = ScheduledChange(
                            new_tier=tier,
                            effective_date=datetime.fromtimestamp(next_phase["start_date"], tz=UTC),
                            is_cancellation=False,
                        )
        except Exception as e:
            logger.warning("failed_to_check_stripe_schedule", error=str(e))

    return SubscriptionResponse(
        tier=tenant.tier.value,  # type: ignore[arg-type]
        status=tenant.subscription_status.value,  # type: ignore[arg-type]
        stripe_customer_id=tenant.stripe_customer_id,
        current_period_end=tenant.current_period_end,
        scheduled_change=scheduled_change,
        features=features,
        usage=usage,
    )


@router.post("/subscription/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    request: CheckoutRequest,
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
    service: Annotated[BillingService, Depends(get_billing_service)],
) -> CheckoutResponse:
    """Create a Stripe Checkout session for subscription."""
    # Default URLs
    base_url = str(get_settings().frontend_url).rstrip("/")
    success_url = (
        str(request.success_url) if request.success_url else f"{base_url}/settings/billing/success"
    )
    cancel_url = str(request.cancel_url) if request.cancel_url else f"{base_url}/settings/billing"

    try:
        checkout_url, session_id = await service.create_checkout_session(
            tenant=tenant,
            tier=request.tier,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except Exception as e:
        logger.error("checkout_session_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None

    return CheckoutResponse(
        checkout_url=checkout_url,
        session_id=session_id,
    )


@router.post("/subscription/portal", response_model=PortalResponse)
async def create_portal_session(
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
    service: Annotated[BillingService, Depends(get_billing_service)],
) -> PortalResponse:
    """Create a Stripe Customer Portal session for self-service billing."""
    base_url = str(get_settings().frontend_url).rstrip("/")
    return_url = f"{base_url}/settings/billing"

    try:
        portal_url = await service.create_portal_session(
            tenant=tenant,
            return_url=return_url,
        )
    except Exception as e:
        logger.error("portal_session_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None

    return PortalResponse(portal_url=portal_url)


@router.post("/subscription/upgrade", response_model=SubscriptionResponse)
async def upgrade_subscription(
    request: UpgradeRequest,
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
    service: Annotated[BillingService, Depends(get_billing_service)],
) -> SubscriptionResponse:
    """Upgrade subscription to a higher tier."""
    try:
        await service.upgrade_subscription(
            tenant=tenant,
            new_tier=request.new_tier,
        )
    except Exception as e:
        logger.error("upgrade_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None

    # Return updated subscription
    features = service.get_tier_features_for_tenant(tenant)
    usage = service.get_usage_info(tenant)

    return SubscriptionResponse(
        tier=tenant.tier.value,  # type: ignore[arg-type]
        status=tenant.subscription_status.value,  # type: ignore[arg-type]
        stripe_customer_id=tenant.stripe_customer_id,
        current_period_end=tenant.current_period_end,
        scheduled_change=None,
        features=features,
        usage=usage,
    )


@router.post("/subscription/downgrade", response_model=SubscriptionResponse)
async def downgrade_subscription(
    request: DowngradeRequest,
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
    service: Annotated[BillingService, Depends(get_billing_service)],
) -> SubscriptionResponse:
    """Schedule a downgrade for the next billing cycle."""
    try:
        effective_date = await service.schedule_downgrade(
            tenant=tenant,
            new_tier=request.new_tier,
        )
    except Exception as e:
        logger.error("downgrade_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None

    features = service.get_tier_features_for_tenant(tenant)
    usage = service.get_usage_info(tenant)

    return SubscriptionResponse(
        tier=tenant.tier.value,  # type: ignore[arg-type]
        status=tenant.subscription_status.value,  # type: ignore[arg-type]
        stripe_customer_id=tenant.stripe_customer_id,
        current_period_end=tenant.current_period_end,
        scheduled_change=ScheduledChange(
            new_tier=request.new_tier,
            effective_date=effective_date,
        ),
        features=features,
        usage=usage,
    )


@router.post("/subscription/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    request: CancelRequest,
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
    service: Annotated[BillingService, Depends(get_billing_service)],
) -> SubscriptionResponse:
    """Cancel subscription at end of current period."""
    try:
        effective_date = await service.cancel_subscription(
            tenant=tenant,
            reason=request.reason,
            feedback=request.feedback,
        )
    except Exception as e:
        logger.error("cancel_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None

    features = service.get_tier_features_for_tenant(tenant)
    usage = service.get_usage_info(tenant)

    return SubscriptionResponse(
        tier=tenant.tier.value,  # type: ignore[arg-type]
        status=tenant.subscription_status.value,  # type: ignore[arg-type]
        stripe_customer_id=tenant.stripe_customer_id,
        current_period_end=tenant.current_period_end,
        scheduled_change=ScheduledChange(
            new_tier=None,
            effective_date=effective_date,
            is_cancellation=True,
        ),
        features=features,
        usage=usage,
    )


# =============================================================================
# Features Endpoints
# =============================================================================


@router.get("/features", response_model=FeaturesResponse)
async def get_features(
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
    service: Annotated[BillingService, Depends(get_billing_service)],
) -> FeaturesResponse:
    """Get feature access status for current tenant."""
    tier = tenant.tier.value
    features = get_tier_features(tier)

    # Build can_access map
    can_access = {
        "ai_insights": True,  # All tiers have some level
        "client_portal": features.get("client_portal", False),
        "custom_triggers": features.get("custom_triggers", False),
        "api_access": features.get("api_access", False),
        "knowledge_base": features.get("knowledge_base", False),
        "magic_zone": features.get("magic_zone", False),
    }

    return FeaturesResponse(
        tier=tier,  # type: ignore[arg-type]
        features=TierFeatures(**features),
        can_access=can_access,
    )


# =============================================================================
# Billing Events Endpoints
# =============================================================================


@router.get("/billing/events", response_model=BillingEventsResponse)
async def list_billing_events(
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
    service: Annotated[BillingService, Depends(get_billing_service)],
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
) -> BillingEventsResponse:
    """List billing events for current tenant."""
    events, total = await service.list_billing_events(
        tenant_id=tenant.id,
        limit=limit,
        offset=offset,
    )

    return BillingEventsResponse(
        events=[BillingEventResponse(**e) for e in events],
        total=total,
        limit=limit,
        offset=offset,
    )


# =============================================================================
# Usage Endpoints (Spec 020)
# =============================================================================


@router.get("/billing/usage", response_model=UsageMetrics)
async def get_usage(
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
    service: Annotated[BillingService, Depends(get_billing_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UsageMetrics:
    """Get current usage metrics for the tenant's billing dashboard.

    Returns real-time usage data including:
    - Client count vs limit
    - AI queries this billing period
    - Documents processed this billing period
    - Threshold warnings if approaching limits
    - Next tier for upgrade prompts
    """
    # Get actual client count from XeroConnections
    count_query = select(func.count(XeroConnection.id)).where(
        XeroConnection.tenant_id == tenant.id,
        XeroConnection.status != XeroConnectionStatus.DISCONNECTED,
    )
    result = await db.execute(count_query)
    actual_client_count = result.scalar() or 0

    # Get usage metrics from service
    metrics = service.get_usage_metrics(tenant)

    # Override client count with actual count from XeroConnections
    return UsageMetrics(
        client_count=actual_client_count,
        client_limit=metrics.client_limit,
        client_percentage=(
            (actual_client_count / metrics.client_limit * 100) if metrics.client_limit else None
        ),
        ai_queries_month=metrics.ai_queries_month,
        documents_month=metrics.documents_month,
        is_at_limit=metrics.client_limit is not None
        and actual_client_count >= metrics.client_limit,
        is_approaching_limit=metrics.client_limit is not None
        and actual_client_count >= (metrics.client_limit * 0.8),
        threshold_warning=service._get_threshold_warning(
            (actual_client_count / metrics.client_limit * 100) if metrics.client_limit else None
        ),
        tier=metrics.tier,
        next_tier=metrics.next_tier,
    )


@router.get("/billing/usage/alerts", response_model=UsageAlertsResponse)
async def get_usage_alerts(
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
) -> UsageAlertsResponse:
    """Get usage alert history for the tenant.

    Returns a list of usage alerts that have been sent to the tenant,
    including threshold warnings (80%, 90%) and limit reached notifications.
    """
    from app.modules.billing.usage_alerts import UsageAlertService

    alert_service = UsageAlertService(db)
    alerts, total = await alert_service.get_alerts_for_tenant(
        tenant_id=tenant.id,
        limit=limit,
        offset=offset,
    )

    return UsageAlertsResponse(
        alerts=[UsageAlertResponse(**a) for a in alerts],
        total=total,
    )


@router.get("/billing/usage/history", response_model=UsageHistoryResponse)
async def get_usage_history(
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
    months: int = Query(default=3, ge=1, le=12),
) -> UsageHistoryResponse:
    """Get usage history for the tenant.

    Returns daily usage snapshots for trend analysis and charting.
    Data includes:
    - Client count over time
    - AI queries and documents processed
    - Tier and limit at each snapshot

    Used by the billing dashboard to show usage trends.
    """
    from app.modules.billing.repository import UsageRepository

    usage_repo = UsageRepository(db)
    snapshots, period_start, period_end = await usage_repo.get_usage_history(
        tenant_id=tenant.id,
        months=months,
    )

    return UsageHistoryResponse(
        snapshots=[
            UsageSnapshotResponse(
                id=s.id,
                captured_at=s.captured_at,
                client_count=s.client_count,
                ai_queries_count=s.ai_queries_count,
                documents_count=s.documents_count,
                tier=s.tier,
                client_limit=s.client_limit,
            )
            for s in snapshots
        ],
        period_start=period_start,
        period_end=period_end,
    )


@router.post("/billing/usage/recalculate", response_model=UsageMetrics)
async def recalculate_client_count(
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
    service: Annotated[BillingService, Depends(get_billing_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UsageMetrics:
    """Recalculate client count from XeroConnections.

    Recovery endpoint for fixing client count after sync issues.
    Recounts all XeroConnections where status != 'disconnected'
    and updates the tenant's client_count field.

    Returns updated usage metrics after recalculation.
    """
    from sqlalchemy import update

    # Count active XeroConnections
    count_query = select(func.count(XeroConnection.id)).where(
        XeroConnection.tenant_id == tenant.id,
        XeroConnection.status != XeroConnectionStatus.DISCONNECTED,
    )
    result = await db.execute(count_query)
    actual_client_count = result.scalar() or 0

    # Update tenant.client_count
    await db.execute(
        update(Tenant).where(Tenant.id == tenant.id).values(client_count=actual_client_count)
    )
    await db.commit()

    # Refresh tenant to get updated values
    await db.refresh(tenant)

    logger.info(
        "recalculated_client_count",
        tenant_id=str(tenant.id),
        new_count=actual_client_count,
    )

    # Return updated usage metrics
    metrics = service.get_usage_metrics(tenant)
    return UsageMetrics(
        client_count=actual_client_count,
        client_limit=metrics.client_limit,
        client_percentage=(
            (actual_client_count / metrics.client_limit * 100) if metrics.client_limit else None
        ),
        ai_queries_month=metrics.ai_queries_month,
        documents_month=metrics.documents_month,
        is_at_limit=metrics.client_limit is not None
        and actual_client_count >= metrics.client_limit,
        is_approaching_limit=metrics.client_limit is not None
        and actual_client_count >= (metrics.client_limit * 0.8),
        threshold_warning=service._get_threshold_warning(
            (actual_client_count / metrics.client_limit * 100) if metrics.client_limit else None
        ),
        tier=metrics.tier,
        next_tier=metrics.next_tier,
    )


# =============================================================================
# Webhook Endpoint
# =============================================================================


@router.post("/webhooks/stripe", response_model=WebhookResponse)
async def stripe_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    stripe_signature: Annotated[str, Header(alias="stripe-signature")],
) -> WebhookResponse:
    """Handle Stripe webhook events."""
    # Get raw body for signature verification
    payload = await request.body()

    # Verify signature
    try:
        webhook_secret = get_settings().stripe_webhook_secret
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=webhook_secret,
        )
    except stripe.SignatureVerificationError as e:
        logger.error("webhook_signature_invalid", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        ) from None
    except Exception as e:
        logger.error("webhook_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None

    # Process event
    handler = WebhookHandler(session=session)
    processed = await handler.process_event(dict(event))

    await session.commit()

    return WebhookResponse(status="success" if processed else "already_processed")
