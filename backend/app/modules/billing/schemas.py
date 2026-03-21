"""Billing module Pydantic schemas.

Request and response schemas for subscription management endpoints.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

# =============================================================================
# Enums as Literal types for API
# =============================================================================

SubscriptionTierType = Literal["starter", "professional", "growth", "enterprise"]
SubscriptionStatusType = Literal[
    "trial", "active", "past_due", "cancelled", "suspended", "grandfathered"
]
AIInsightsType = Literal["basic", "full"]


# =============================================================================
# Feature and Tier Info
# =============================================================================


class TierFeatures(BaseModel):
    """Features available for a subscription tier."""

    max_clients: int | None = Field(description="Client limit (null = unlimited)")
    ai_insights: AIInsightsType = Field(description="AI insights level")
    client_portal: bool = Field(description="Client portal access")
    custom_triggers: bool = Field(description="Custom triggers access")
    api_access: bool = Field(description="API access")
    knowledge_base: bool = Field(description="Knowledge base access")
    magic_zone: bool = Field(description="Magic Zone access")


class UsageInfo(BaseModel):
    """Client usage information for a tenant."""

    client_count: int = Field(description="Current client count")
    client_limit: int | None = Field(description="Client limit (null = unlimited)")
    is_at_limit: bool = Field(description="Whether at client limit")
    is_approaching_limit: bool = Field(description="Whether approaching limit (80%)")
    percentage_used: float | None = Field(default=None, description="Percentage of limit used")


class TierInfo(BaseModel):
    """Information about a subscription tier for pricing display."""

    name: SubscriptionTierType = Field(description="Tier identifier")
    display_name: str = Field(description="Human-readable tier name")
    price_monthly: int = Field(description="Price in cents (AUD)")
    price_id: str | None = Field(default=None, description="Stripe price ID")
    features: TierFeatures = Field(description="Features included")
    highlights: list[str] = Field(default_factory=list, description="Marketing highlights")


class ScheduledChange(BaseModel):
    """Information about a scheduled subscription change."""

    new_tier: SubscriptionTierType | None = Field(
        default=None, description="New tier after change (None = cancellation)"
    )
    effective_date: datetime = Field(description="When change takes effect")
    is_cancellation: bool = Field(
        default=False, description="True if this is a scheduled cancellation"
    )


# =============================================================================
# Subscription Responses
# =============================================================================


class SubscriptionResponse(BaseModel):
    """Current subscription status response."""

    tier: SubscriptionTierType = Field(description="Current tier")
    status: SubscriptionStatusType = Field(description="Subscription status")
    stripe_customer_id: str | None = Field(default=None, description="Stripe customer ID")
    current_period_end: datetime | None = Field(
        default=None, description="Current billing period end"
    )
    scheduled_change: ScheduledChange | None = Field(
        default=None, description="Scheduled tier change"
    )
    features: TierFeatures = Field(description="Available features")
    usage: UsageInfo = Field(description="Client usage info")


class FeaturesResponse(BaseModel):
    """Feature access status response."""

    tier: SubscriptionTierType = Field(description="Current tier")
    features: TierFeatures = Field(description="Tier features")
    can_access: dict[str, bool] = Field(description="Map of feature name to access boolean")


class TiersResponse(BaseModel):
    """List of available subscription tiers."""

    tiers: list[TierInfo] = Field(description="Available tiers")


# =============================================================================
# Trial Status (Spec 021)
# =============================================================================


class TrialStatusResponse(BaseModel):
    """Trial status information for the onboarding flow.

    Spec 021: Onboarding Flow - Free Trial Experience
    """

    is_trial: bool = Field(description="Whether tenant is currently in trial period")
    tier: SubscriptionTierType = Field(description="Current/selected subscription tier")
    trial_end_date: datetime | None = Field(
        default=None, description="When trial ends (null if not in trial)"
    )
    days_remaining: int | None = Field(
        default=None, description="Days remaining in trial (null if not in trial)"
    )
    price_monthly: int = Field(description="Monthly price in cents that will apply after trial")
    billing_date: datetime | None = Field(
        default=None, description="First billing date (same as trial_end_date)"
    )


# =============================================================================
# Checkout Requests/Responses
# =============================================================================


class CheckoutRequest(BaseModel):
    """Request to create a Stripe checkout session."""

    tier: SubscriptionTierType = Field(description="Tier to subscribe to")
    success_url: HttpUrl | None = Field(
        default=None, description="URL to redirect after successful payment"
    )
    cancel_url: HttpUrl | None = Field(default=None, description="URL to redirect if user cancels")


class CheckoutResponse(BaseModel):
    """Response with Stripe checkout session details."""

    checkout_url: str = Field(description="Stripe Checkout URL to redirect user")
    session_id: str = Field(description="Stripe Checkout session ID")


class PortalResponse(BaseModel):
    """Response with Stripe Customer Portal URL."""

    portal_url: str = Field(description="Stripe Customer Portal URL")


# =============================================================================
# Subscription Management Requests
# =============================================================================


class UpgradeRequest(BaseModel):
    """Request to upgrade subscription tier."""

    new_tier: SubscriptionTierType = Field(description="Tier to upgrade to")


class DowngradeRequest(BaseModel):
    """Request to downgrade subscription tier."""

    new_tier: SubscriptionTierType = Field(description="Tier to downgrade to")


class CancelRequest(BaseModel):
    """Request to cancel subscription."""

    reason: str | None = Field(default=None, description="Cancellation reason")
    feedback: str | None = Field(default=None, description="Optional feedback")


# =============================================================================
# Billing Events
# =============================================================================


class BillingEventResponse(BaseModel):
    """Single billing event response."""

    id: UUID = Field(description="Event ID")
    event_type: str = Field(description="Event type")
    amount_cents: int | None = Field(default=None, description="Amount in cents")
    currency: str = Field(default="aud", description="Currency code")
    status: str = Field(description="Processing status")
    created_at: datetime = Field(description="Event timestamp")


class BillingEventsResponse(BaseModel):
    """Paginated billing events response."""

    events: list[BillingEventResponse] = Field(description="Billing events")
    total: int = Field(description="Total event count")
    limit: int = Field(description="Page size")
    offset: int = Field(description="Page offset")


# =============================================================================
# Webhook Response
# =============================================================================


class WebhookResponse(BaseModel):
    """Response from webhook processing."""

    status: Literal["success", "already_processed"] = Field(description="Processing status")


# =============================================================================
# Error Responses
# =============================================================================


class FeatureGatedError(BaseModel):
    """Error response when feature is gated."""

    error: str = Field(description="Error message")
    code: str = Field(default="feature_not_available", description="Error code")
    feature: str = Field(description="Feature that was blocked")
    required_tier: SubscriptionTierType = Field(description="Minimum required tier")
    current_tier: SubscriptionTierType = Field(description="User's current tier")


class ClientLimitError(BaseModel):
    """Error response when client limit is exceeded."""

    error: str = Field(description="Error message")
    code: str = Field(default="client_limit_exceeded", description="Error code")
    current_count: int = Field(description="Current client count")
    limit: int = Field(description="Client limit for tier")
    required_tier: SubscriptionTierType = Field(description="Tier with higher limit")


# =============================================================================
# Usage Tracking Schemas (Spec 020)
# =============================================================================

UsageAlertTypeLiteral = Literal["threshold_80", "threshold_90", "limit_reached"]
ThresholdWarningType = Literal["80%", "90%", "100%"]


class UsageMetrics(BaseModel):
    """Extended usage metrics for the usage dashboard.

    Spec 020: Usage Tracking & Limits
    """

    client_count: int = Field(description="Current active client count")
    client_limit: int | None = Field(description="Client limit (null = unlimited)")
    client_percentage: float | None = Field(
        default=None, description="Percentage of client limit used"
    )
    ai_queries_month: int = Field(description="AI queries this billing period")
    documents_month: int = Field(description="Documents processed this billing period")
    is_at_limit: bool = Field(description="Whether at client limit")
    is_approaching_limit: bool = Field(description="Whether approaching limit (>=80%)")
    threshold_warning: ThresholdWarningType | None = Field(
        default=None, description="Warning level if applicable"
    )
    tier: SubscriptionTierType = Field(description="Current subscription tier")
    next_tier: SubscriptionTierType | None = Field(
        default=None, description="Next available tier for upgrade"
    )


class UsageSnapshotResponse(BaseModel):
    """Usage snapshot for API response.

    Spec 020: Usage Tracking & Limits
    """

    id: UUID = Field(description="Snapshot ID")
    captured_at: datetime = Field(description="When snapshot was captured")
    client_count: int = Field(description="Client count at snapshot time")
    ai_queries_count: int = Field(description="AI queries at snapshot time")
    documents_count: int = Field(description="Documents at snapshot time")
    tier: str = Field(description="Tier at snapshot time")
    client_limit: int | None = Field(description="Client limit at snapshot time")


class UsageHistoryResponse(BaseModel):
    """Historical usage data for charting.

    Spec 020: Usage Tracking & Limits
    """

    snapshots: list[UsageSnapshotResponse] = Field(description="Usage snapshots")
    period_start: datetime = Field(description="History period start")
    period_end: datetime = Field(description="History period end")


class UsageAlertResponse(BaseModel):
    """Usage alert record for API response.

    Spec 020: Usage Tracking & Limits
    """

    id: UUID = Field(description="Alert ID")
    alert_type: UsageAlertTypeLiteral = Field(description="Alert type")
    billing_period: str = Field(description="Billing period (YYYY-MM)")
    threshold_percentage: int = Field(description="Threshold percentage (80, 90, 100)")
    client_count_at_alert: int = Field(description="Client count when triggered")
    client_limit_at_alert: int = Field(description="Client limit when triggered")
    sent_at: datetime = Field(description="When alert was sent")


class UsageAlertsResponse(BaseModel):
    """Paginated usage alerts response.

    Spec 020: Usage Tracking & Limits
    """

    alerts: list[UsageAlertResponse] = Field(description="Usage alerts")
    total: int = Field(description="Total alert count")


class AdminUsageStats(BaseModel):
    """Aggregate usage statistics for admin dashboard.

    Spec 020: Usage Tracking & Limits
    """

    total_tenants: int = Field(description="Total tenant count")
    total_clients: int = Field(description="Total client count across all tenants")
    average_clients_per_tenant: float = Field(description="Average clients per tenant")
    tenants_at_limit: int = Field(description="Tenants at client limit")
    tenants_approaching_limit: int = Field(description="Tenants at >=80% of limit")
    tenants_by_tier: dict[str, int] = Field(description="Tenant count per tier")


class UpsellOpportunity(BaseModel):
    """Tenant approaching limit - potential upsell.

    Spec 020: Usage Tracking & Limits
    """

    tenant_id: UUID = Field(description="Tenant ID")
    tenant_name: str = Field(description="Tenant name")
    owner_email: str = Field(description="Owner email for outreach")
    current_tier: SubscriptionTierType = Field(description="Current tier")
    client_count: int = Field(description="Current client count")
    client_limit: int = Field(description="Current client limit")
    percentage_used: float = Field(description="Percentage of limit used")


class UpsellOpportunitiesResponse(BaseModel):
    """Paginated upsell opportunities response.

    Spec 020: Usage Tracking & Limits
    """

    opportunities: list[UpsellOpportunity] = Field(description="Upsell opportunities")
    total: int = Field(description="Total opportunity count")


class AdminTenantUsageResponse(BaseModel):
    """Detailed usage for a specific tenant (admin view).

    Spec 020: Usage Tracking & Limits
    """

    tenant_id: UUID = Field(description="Tenant ID")
    tenant_name: str = Field(description="Tenant name")
    tier: SubscriptionTierType = Field(description="Current tier")
    usage: UsageMetrics = Field(description="Current usage metrics")
    history: list[UsageSnapshotResponse] = Field(description="Usage history")
    alerts: list[UsageAlertResponse] = Field(description="Recent alerts")
