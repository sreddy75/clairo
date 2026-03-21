"""Admin module Pydantic schemas.

Request and response schemas for admin dashboard endpoints.

Spec 022: Admin Dashboard (Internal)
"""

from datetime import date as DateType, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.billing.schemas import SubscriptionTierType

# =============================================================================
# Enums as Literal types
# =============================================================================

FeatureKeyType = Literal[
    "ai_insights",
    "client_portal",
    "custom_triggers",
    "api_access",
    "knowledge_base",
    "magic_zone",
]

CreditType = Literal["one_time", "recurring"]

TenantStatusFilter = Literal["active", "inactive", "all"]

TenantSortField = Literal["name", "created_at", "mrr", "client_count"]

SortOrder = Literal["asc", "desc"]

RevenuePeriod = Literal["daily", "weekly", "monthly"]


# =============================================================================
# Tenant Management Schemas
# =============================================================================


class TenantSummary(BaseModel):
    """Summary of a tenant for list view."""

    id: UUID = Field(description="Tenant ID")
    name: str = Field(description="Practice name")
    owner_email: str | None = Field(default=None, description="Owner email address")
    tier: SubscriptionTierType = Field(description="Current subscription tier")
    client_count: int = Field(description="Current client count")
    client_limit: int | None = Field(default=None, description="Client limit (null = unlimited)")
    is_active: bool = Field(description="Whether tenant is active")
    created_at: datetime = Field(description="When tenant was created")
    last_login_at: datetime | None = Field(default=None, description="Last user login")
    mrr_cents: int = Field(default=0, description="Monthly recurring revenue in cents")


class TenantListResponse(BaseModel):
    """Paginated list of tenants."""

    tenants: list[TenantSummary] = Field(description="List of tenant summaries")
    total: int = Field(description="Total tenant count matching filters")
    page: int = Field(description="Current page number (1-indexed)")
    limit: int = Field(description="Page size")
    has_more: bool = Field(description="Whether more pages exist")


class BillingEventSummary(BaseModel):
    """Summary of a billing event."""

    id: UUID = Field(description="Event ID")
    event_type: str = Field(description="Event type")
    created_at: datetime = Field(description="When event occurred")
    details: dict = Field(default_factory=dict, description="Event details")


class ActivityItem(BaseModel):
    """Recent activity item."""

    type: str = Field(description="Activity type")
    description: str = Field(description="Human-readable description")
    timestamp: datetime = Field(description="When activity occurred")
    user: str | None = Field(default=None, description="User who performed action")


class FeatureFlagStatus(BaseModel):
    """Status of a feature flag for a tenant."""

    feature_key: FeatureKeyType = Field(description="Feature identifier")
    tier_default: bool = Field(description="Default value based on tier")
    override_value: bool | None = Field(
        default=None, description="Override value (null if no override)"
    )
    effective_value: bool = Field(description="Actual value (override or tier default)")
    is_overridden: bool = Field(description="Whether there's an override")
    override_reason: str | None = Field(default=None, description="Reason for override")
    override_created_at: datetime | None = Field(
        default=None, description="When override was created"
    )
    override_created_by: str | None = Field(default=None, description="Admin who created override")


class TenantDetailResponse(BaseModel):
    """Detailed tenant information."""

    id: UUID = Field(description="Tenant ID")
    name: str = Field(description="Practice name")
    owner_email: str | None = Field(default=None, description="Owner email")
    tier: SubscriptionTierType = Field(description="Current tier")
    is_active: bool = Field(description="Whether tenant is active")
    created_at: datetime = Field(description="When created")

    # Billing
    stripe_customer_id: str | None = Field(default=None, description="Stripe customer ID")
    stripe_subscription_id: str | None = Field(default=None, description="Stripe subscription ID")
    subscription_status: str = Field(description="Subscription status")
    next_billing_date: datetime | None = Field(default=None, description="Next billing date")
    mrr_cents: int = Field(default=0, description="Monthly recurring revenue in cents")

    # Usage
    client_count: int = Field(description="Current client count")
    client_limit: int | None = Field(default=None, description="Client limit")
    ai_queries_month: int = Field(default=0, description="AI queries this month")
    documents_month: int = Field(default=0, description="Documents processed this month")

    # Users
    user_count: int = Field(default=0, description="Number of users in tenant")

    # History and activity
    subscription_history: list[BillingEventSummary] = Field(
        default_factory=list, description="Billing event history"
    )
    recent_activity: list[ActivityItem] = Field(default_factory=list, description="Recent activity")

    # Feature flags
    feature_flags: list[FeatureFlagStatus] = Field(
        default_factory=list, description="Feature flag statuses"
    )


# =============================================================================
# Revenue Analytics Schemas
# =============================================================================


class MRRMetrics(BaseModel):
    """MRR (Monthly Recurring Revenue) metrics."""

    current_cents: int = Field(description="Current MRR in cents")
    previous_cents: int = Field(description="MRR at start of period in cents")
    change_percentage: float = Field(description="Percentage change")


class ChurnMetrics(BaseModel):
    """Churn metrics."""

    rate_percentage: float = Field(description="Churn rate as percentage")
    lost_cents: int = Field(description="Lost MRR in cents")
    tenant_count: int = Field(description="Number of churned tenants")


class ExpansionMetrics(BaseModel):
    """Expansion revenue metrics."""

    amount_cents: int = Field(description="Net expansion in cents")
    upgrade_count: int = Field(description="Number of upgrades")
    downgrade_count: int = Field(description="Number of downgrades")


class TenantCounts(BaseModel):
    """Tenant count breakdown."""

    total_active: int = Field(description="Total active tenants")
    by_tier: dict[str, int] = Field(description="Count per tier")


class PeriodRange(BaseModel):
    """Date range for metrics."""

    start_date: DateType = Field(description="Period start date")
    end_date: DateType = Field(description="Period end date")


class RevenueMetricsResponse(BaseModel):
    """Revenue metrics response."""

    period: PeriodRange = Field(description="Date range")
    mrr: MRRMetrics = Field(description="MRR metrics")
    churn: ChurnMetrics = Field(description="Churn metrics")
    expansion: ExpansionMetrics = Field(description="Expansion metrics")
    tenant_counts: TenantCounts = Field(description="Tenant counts")


class RevenueTrendDataPoint(BaseModel):
    """Single data point for revenue trends."""

    date: DateType = Field(description="Date of data point")
    mrr_cents: int = Field(description="MRR at this date in cents")
    tenant_count: int = Field(description="Tenant count at this date")
    new_subscriptions: int = Field(default=0, description="New subscriptions")
    churned_subscriptions: int = Field(default=0, description="Churned subscriptions")


class RevenueTrendsResponse(BaseModel):
    """Revenue trends over time."""

    period: RevenuePeriod = Field(description="Aggregation period")
    data_points: list[RevenueTrendDataPoint] = Field(description="Trend data points")


# =============================================================================
# Subscription Management Schemas
# =============================================================================


class TierChangeRequest(BaseModel):
    """Request to change a tenant's tier."""

    new_tier: SubscriptionTierType = Field(description="New subscription tier")
    reason: str = Field(min_length=10, max_length=500, description="Reason for change")
    force_downgrade: bool = Field(
        default=False,
        description="Force downgrade even with excess clients",
    )


class TierChangeResponse(BaseModel):
    """Response after tier change."""

    success: bool = Field(description="Whether change succeeded")
    tenant_id: UUID = Field(description="Tenant ID")
    old_tier: SubscriptionTierType = Field(description="Previous tier")
    new_tier: SubscriptionTierType = Field(description="New tier")
    effective_at: datetime = Field(description="When change took effect")
    stripe_subscription_id: str | None = Field(default=None, description="Stripe subscription ID")
    billing_event_id: UUID = Field(description="Audit event ID")


class TierChangeConflict(BaseModel):
    """Conflict response when tier change blocked."""

    error: str = Field(description="Error message")
    code: Literal["excess_clients", "pending_payment", "stripe_error"] = Field(
        description="Error code"
    )
    details: dict = Field(description="Additional details")


class CreditRequest(BaseModel):
    """Request to apply credit to tenant."""

    amount_cents: int = Field(ge=1, le=10000000, description="Credit amount in cents")
    credit_type: CreditType = Field(description="One-time or recurring credit")
    reason: str = Field(min_length=10, max_length=500, description="Reason for credit")


class CreditResponse(BaseModel):
    """Response after applying credit."""

    success: bool = Field(description="Whether credit was applied")
    tenant_id: UUID = Field(description="Tenant ID")
    amount_cents: int = Field(description="Credit amount in cents")
    credit_type: CreditType = Field(description="Credit type")
    effective_at: datetime = Field(description="When credit was applied")
    billing_event_id: UUID = Field(description="Audit event ID")


# =============================================================================
# Feature Flag Schemas
# =============================================================================


class FeatureFlagsResponse(BaseModel):
    """All feature flags for a tenant."""

    tenant_id: UUID = Field(description="Tenant ID")
    tier: SubscriptionTierType = Field(description="Current tier")
    flags: list[FeatureFlagStatus] = Field(description="All feature flags")


class FeatureFlagOverrideRequest(BaseModel):
    """Request to set a feature flag override."""

    value: bool = Field(description="True to enable, False to disable")
    reason: str = Field(min_length=10, max_length=500, description="Reason for override")


class FeatureFlagOverrideResponse(BaseModel):
    """Response after setting override."""

    success: bool = Field(description="Whether override was set")
    tenant_id: UUID = Field(description="Tenant ID")
    feature_key: FeatureKeyType = Field(description="Feature key")
    old_value: bool | None = Field(default=None, description="Previous effective value")
    new_value: bool = Field(description="New effective value")
    effective_at: datetime = Field(description="When override took effect")


# =============================================================================
# Usage Analytics Schemas
# =============================================================================


class PlatformUsageMetrics(BaseModel):
    """Aggregate platform usage metrics."""

    total_clients: int = Field(description="Total clients across all tenants")
    total_syncs: int = Field(description="Total syncs performed")
    total_ai_queries: int = Field(description="Total AI queries")
    by_tier: dict[str, dict[str, int]] = Field(description="Metrics by tier")


class TopUserEntry(BaseModel):
    """Entry in top users list."""

    tenant_id: UUID = Field(description="Tenant ID")
    tenant_name: str = Field(description="Tenant name")
    value: int = Field(description="Metric value")


class TopUsersResponse(BaseModel):
    """Top users by a specific metric."""

    metric: str = Field(description="Metric used for ranking")
    users: list[TopUserEntry] = Field(description="Top users list")
