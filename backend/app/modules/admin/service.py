"""Admin dashboard business logic service.

Handles admin operations for multi-tenant management:
- Tenant listing, search, filtering
- Subscription tier changes
- Credit application
- Feature flag overrides
- Revenue analytics

Spec 022: Admin Dashboard (Internal)
"""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.feature_flags import (
    TIER_PRICING,
    get_client_limit,
    has_feature,
    is_downgrade,
)
from app.modules.admin.exceptions import (
    CreditApplicationError,
    InvalidFeatureKeyError,
    SelfModificationBlockedError,
    TenantNotFoundError,
    TierDowngradeBlockedError,
)
from app.modules.admin.repository import (
    AdminRepository,
    FeatureFlagOverrideRepository,
    SortOrder,
    TenantSortField,
    TenantStatusFilter,
)
from app.modules.admin.schemas import (
    ActivityItem,
    BillingEventSummary,
    ChurnMetrics,
    CreditResponse,
    CreditType,
    ExpansionMetrics,
    FeatureFlagOverrideResponse,
    FeatureFlagsResponse,
    FeatureFlagStatus,
    FeatureKeyType,
    MRRMetrics,
    PeriodRange,
    PlatformUsageMetrics,
    RevenueMetricsResponse,
    RevenuePeriod,
    RevenueTrendDataPoint,
    RevenueTrendsResponse,
    SubscriptionTierType,
    TenantCounts,
    TenantDetailResponse,
    TenantListResponse,
    TenantSummary,
    TierChangeResponse,
    TopUsersResponse,
)
from app.modules.auth.models import SubscriptionTier
from app.modules.billing.stripe_client import StripeClient

if TYPE_CHECKING:
    from app.modules.auth.models import PracticeUser

logger = structlog.get_logger(__name__)

# Valid feature keys for the admin module
VALID_FEATURE_KEYS: frozenset[str] = frozenset(
    [
        "ai_insights",
        "client_portal",
        "custom_triggers",
        "api_access",
        "knowledge_base",
        "magic_zone",
    ]
)


class AdminDashboardService:
    """Service for admin dashboard operations.

    Provides methods for:
    - Multi-tenant listing with search/filter/sort
    - Tenant detail view
    - Subscription management (tier changes, credits)
    - Feature flag overrides
    - Revenue analytics

    Spec 022: Admin Dashboard (Internal)
    """

    def __init__(
        self,
        session: AsyncSession,
        stripe_client: StripeClient | None = None,
    ) -> None:
        """Initialize the admin dashboard service.

        Args:
            session: Async database session.
            stripe_client: Optional Stripe client for billing operations.
        """
        self.session = session
        self.stripe_client = stripe_client or StripeClient()
        self.admin_repo = AdminRepository(session)
        self.feature_flag_repo = FeatureFlagOverrideRepository(session)

    # =========================================================================
    # Tenant Listing
    # =========================================================================

    async def list_tenants(
        self,
        *,
        search: str | None = None,
        tier: SubscriptionTierType | None = None,
        status: TenantStatusFilter = "all",
        sort_by: TenantSortField = "created_at",
        sort_order: SortOrder = "desc",
        page: int = 1,
        limit: int = 20,
    ) -> TenantListResponse:
        """List all tenants with filtering, sorting, and pagination.

        Args:
            search: Search string for tenant name or email.
            tier: Filter by subscription tier.
            status: Filter by active/inactive status.
            sort_by: Field to sort by.
            sort_order: Sort direction.
            page: Page number (1-indexed).
            limit: Page size.

        Returns:
            Paginated list of tenant summaries.
        """
        logger.info(
            "listing_tenants",
            search=search,
            tier=tier,
            status=status,
            sort_by=sort_by,
            page=page,
            limit=limit,
        )

        # Convert tier string to enum if provided
        tier_enum = SubscriptionTier(tier) if tier else None

        tenants, total = await self.admin_repo.list_tenants(
            search=search,
            tier=tier_enum,
            status=status,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            limit=limit,
        )

        # Convert to summaries
        summaries = []
        for tenant in tenants:
            # Get client count
            client_count = await self.admin_repo.get_tenant_client_count(tenant.id)
            client_limit = get_client_limit(tenant.tier.value)

            # Find owner email
            owner_email = None
            if tenant.practice_users:
                for pu in tenant.practice_users:
                    if pu.role.value == "owner":
                        owner_email = pu.user.email if pu.user else None
                        break
                if not owner_email and tenant.practice_users:
                    owner_email = (
                        tenant.practice_users[0].user.email
                        if tenant.practice_users[0].user
                        else None
                    )

            # Calculate MRR
            mrr_cents = TIER_PRICING.get(tenant.tier.value, 0) or 0

            # Get last login
            last_login = None
            if tenant.practice_users:
                logins = [pu.last_login_at for pu in tenant.practice_users if pu.last_login_at]
                if logins:
                    last_login = max(logins)

            summaries.append(
                TenantSummary(
                    id=tenant.id,
                    name=tenant.name,
                    owner_email=owner_email,
                    tier=tenant.tier.value,
                    client_count=client_count,
                    client_limit=client_limit,
                    is_active=tenant.is_active,
                    created_at=tenant.created_at,
                    last_login_at=last_login,
                    mrr_cents=mrr_cents if tenant.is_active else 0,
                )
            )

        has_more = (page * limit) < total

        return TenantListResponse(
            tenants=summaries,
            total=total,
            page=page,
            limit=limit,
            has_more=has_more,
        )

    # =========================================================================
    # Tenant Detail
    # =========================================================================

    async def get_tenant_detail(
        self,
        tenant_id: UUID,
    ) -> TenantDetailResponse:
        """Get detailed tenant information.

        Args:
            tenant_id: The tenant's UUID.

        Returns:
            Detailed tenant information.

        Raises:
            TenantNotFoundError: If tenant not found.
        """
        logger.info("getting_tenant_detail", tenant_id=str(tenant_id))

        tenant = await self.admin_repo.get_tenant(tenant_id)
        if not tenant:
            raise TenantNotFoundError(tenant_id)

        # Get client count
        client_count = await self.admin_repo.get_tenant_client_count(tenant_id)
        client_limit = get_client_limit(tenant.tier.value)

        # Get billing events
        billing_events = await self.admin_repo.get_billing_events_for_tenant(tenant_id)
        subscription_history = [
            BillingEventSummary(
                id=event.id,
                event_type=event.event_type,
                created_at=event.created_at,
                details=event.event_data,
            )
            for event in billing_events[:10]  # Last 10 events
        ]

        # Build recent activity from billing events
        recent_activity = [
            ActivityItem(
                type=event.event_type,
                description=self._format_event_description(event),
                timestamp=event.created_at,
                user=event.event_data.get("performed_by_admin"),
            )
            for event in billing_events[:5]
        ]

        # Get feature flags
        overrides = await self.feature_flag_repo.get_by_tenant(tenant_id)
        feature_flags = self._build_feature_flags(tenant.tier.value, overrides)

        # Find owner email
        owner_email = None
        user_count = 0
        if tenant.practice_users:
            user_count = len(tenant.practice_users)
            for pu in tenant.practice_users:
                if pu.role.value == "owner":
                    owner_email = pu.user.email if pu.user else None
                    break

        # Calculate MRR
        mrr_cents = TIER_PRICING.get(tenant.tier.value, 0) or 0

        return TenantDetailResponse(
            id=tenant.id,
            name=tenant.name,
            owner_email=owner_email,
            tier=tenant.tier.value,
            is_active=tenant.is_active,
            created_at=tenant.created_at,
            stripe_customer_id=tenant.stripe_customer_id,
            stripe_subscription_id=tenant.stripe_subscription_id,
            subscription_status=tenant.subscription_status.value,
            next_billing_date=tenant.current_period_end,
            mrr_cents=mrr_cents if tenant.is_active else 0,
            client_count=client_count,
            client_limit=client_limit,
            ai_queries_month=0,  # TODO: Integrate with usage tracking
            documents_month=0,  # TODO: Integrate with usage tracking
            user_count=user_count,
            subscription_history=subscription_history,
            recent_activity=recent_activity,
            feature_flags=feature_flags,
        )

    def _format_event_description(self, event) -> str:
        """Format a billing event into a human-readable description."""
        event_type = event.event_type
        data = event.event_data

        if event_type == "tier_change":
            old = data.get("old_tier", "unknown")
            new = data.get("new_tier", "unknown")
            return f"Tier changed from {old} to {new}"
        elif event_type == "credit_applied":
            amount = data.get("amount_cents", 0) / 100
            return f"Credit of ${amount:.2f} applied"
        elif event_type == "subscription_created":
            return "Subscription created"
        elif event_type == "subscription_canceled":
            return "Subscription canceled"
        else:
            return event_type.replace("_", " ").title()

    def _build_feature_flags(
        self,
        tier: str,
        overrides: list,
    ) -> list[FeatureFlagStatus]:
        """Build feature flag status list for a tenant."""
        flags = []
        override_map = {o.feature_key: o for o in overrides}

        for feature_key in VALID_FEATURE_KEYS:
            tier_default = has_feature(tier, feature_key)
            override = override_map.get(feature_key)

            if override and override.override_value is not None:
                effective_value = override.override_value
                is_overridden = True
            else:
                effective_value = tier_default
                is_overridden = False

            flags.append(
                FeatureFlagStatus(
                    feature_key=feature_key,  # type: ignore[arg-type]
                    tier_default=tier_default,
                    override_value=override.override_value if override else None,
                    effective_value=effective_value,
                    is_overridden=is_overridden,
                    override_reason=override.reason if override else None,
                    override_created_at=override.created_at if override else None,
                    override_created_by=(
                        override.creator.user.email
                        if override and override.creator and override.creator.user
                        else None
                    ),
                )
            )

        return flags

    # =========================================================================
    # Tier Management
    # =========================================================================

    async def change_tenant_tier(
        self,
        tenant_id: UUID,
        new_tier: SubscriptionTierType,
        reason: str,
        admin_user: "PracticeUser",
        *,
        force_downgrade: bool = False,
    ) -> TierChangeResponse:
        """Change a tenant's subscription tier.

        Args:
            tenant_id: The tenant's UUID.
            new_tier: The new tier to set.
            reason: Reason for the change.
            admin_user: The admin making the change.
            force_downgrade: Force downgrade even with excess clients.

        Returns:
            Tier change response.

        Raises:
            TenantNotFoundError: If tenant not found.
            TierDowngradeBlockedError: If downgrade blocked due to excess clients.
            SelfModificationBlockedError: If admin tries to modify their own tenant.
        """
        logger.info(
            "changing_tenant_tier",
            tenant_id=str(tenant_id),
            new_tier=new_tier,
            admin_id=str(admin_user.id),
        )

        # Prevent self-modification
        if admin_user.tenant_id == tenant_id:
            raise SelfModificationBlockedError(admin_user.id, tenant_id)

        tenant = await self.admin_repo.get_tenant(tenant_id, load_billing_events=False)
        if not tenant:
            raise TenantNotFoundError(tenant_id)

        old_tier = tenant.tier.value

        # Check downgrade limits
        if is_downgrade(old_tier, new_tier) and not force_downgrade:
            client_count = await self.admin_repo.get_tenant_client_count(tenant_id)
            new_limit = get_client_limit(new_tier)

            if new_limit is not None and client_count > new_limit:
                raise TierDowngradeBlockedError(
                    tenant_id=tenant_id,
                    current_tier=old_tier,
                    new_tier=new_tier,
                    current_clients=client_count,
                    new_limit=new_limit,
                )

        # Update tier in database
        new_tier_enum = SubscriptionTier(new_tier)
        await self.admin_repo.update_tenant_tier(tenant_id, new_tier_enum)

        # Create audit event
        event = await self.admin_repo.create_billing_event(
            tenant_id=tenant_id,
            event_type="tier_change",
            event_data={
                "old_tier": old_tier,
                "new_tier": new_tier,
                "reason": reason,
                "forced": force_downgrade,
            },
            admin_id=admin_user.id,
        )

        # Update Stripe subscription if exists
        stripe_sub_id = None
        if tenant.stripe_subscription_id:
            try:
                await self.stripe_client.update_subscription_tier(
                    tenant.stripe_subscription_id,
                    new_tier,
                )
                stripe_sub_id = tenant.stripe_subscription_id
            except Exception as e:
                logger.error(
                    "stripe_tier_update_failed",
                    tenant_id=str(tenant_id),
                    error=str(e),
                )
                # Don't fail the operation, DB is updated

        logger.info(
            "tenant_tier_changed",
            tenant_id=str(tenant_id),
            old_tier=old_tier,
            new_tier=new_tier,
        )

        return TierChangeResponse(
            success=True,
            tenant_id=tenant_id,
            old_tier=old_tier,
            new_tier=new_tier,
            effective_at=datetime.now(UTC),
            stripe_subscription_id=stripe_sub_id,
            billing_event_id=event.id,
        )

    # =========================================================================
    # Credits
    # =========================================================================

    async def apply_credit(
        self,
        tenant_id: UUID,
        amount_cents: int,
        credit_type: CreditType,
        reason: str,
        admin_user: "PracticeUser",
    ) -> CreditResponse:
        """Apply a credit to a tenant's account.

        Args:
            tenant_id: The tenant's UUID.
            amount_cents: Credit amount in cents.
            credit_type: One-time or recurring credit.
            reason: Reason for the credit.
            admin_user: The admin applying the credit.

        Returns:
            Credit response.

        Raises:
            TenantNotFoundError: If tenant not found.
            SelfModificationBlockedError: If admin tries to modify their own tenant.
            CreditApplicationError: If credit application fails.
        """
        logger.info(
            "applying_credit",
            tenant_id=str(tenant_id),
            amount_cents=amount_cents,
            credit_type=credit_type,
            admin_id=str(admin_user.id),
        )

        # Prevent self-modification
        if admin_user.tenant_id == tenant_id:
            raise SelfModificationBlockedError(admin_user.id, tenant_id)

        tenant = await self.admin_repo.get_tenant(tenant_id, load_billing_events=False)
        if not tenant:
            raise TenantNotFoundError(tenant_id)

        # Apply credit via Stripe if customer exists
        if tenant.stripe_customer_id:
            try:
                await self.stripe_client.create_credit_note(
                    tenant.stripe_customer_id,
                    amount_cents,
                    reason,
                )
            except Exception as e:
                logger.error(
                    "stripe_credit_failed",
                    tenant_id=str(tenant_id),
                    error=str(e),
                )
                raise CreditApplicationError(
                    f"Failed to apply credit via Stripe: {e!s}",
                    tenant_id=tenant_id,
                    amount_cents=amount_cents,
                )

        # Create audit event
        event = await self.admin_repo.create_billing_event(
            tenant_id=tenant_id,
            event_type="credit_applied",
            event_data={
                "amount_cents": amount_cents,
                "credit_type": credit_type,
                "reason": reason,
            },
            amount_cents=-amount_cents,  # Negative = credit
            admin_id=admin_user.id,
        )

        logger.info(
            "credit_applied",
            tenant_id=str(tenant_id),
            amount_cents=amount_cents,
        )

        return CreditResponse(
            success=True,
            tenant_id=tenant_id,
            amount_cents=amount_cents,
            credit_type=credit_type,
            effective_at=datetime.now(UTC),
            billing_event_id=event.id,
        )

    # =========================================================================
    # Feature Flags
    # =========================================================================

    async def get_tenant_feature_flags(
        self,
        tenant_id: UUID,
    ) -> FeatureFlagsResponse:
        """Get all feature flags for a tenant.

        Args:
            tenant_id: The tenant's UUID.

        Returns:
            Feature flags response.

        Raises:
            TenantNotFoundError: If tenant not found.
        """
        tenant = await self.admin_repo.get_tenant(
            tenant_id,
            load_users=False,
            load_billing_events=False,
        )
        if not tenant:
            raise TenantNotFoundError(tenant_id)

        overrides = await self.feature_flag_repo.get_by_tenant(tenant_id)
        flags = self._build_feature_flags(tenant.tier.value, overrides)

        return FeatureFlagsResponse(
            tenant_id=tenant_id,
            tier=tenant.tier.value,
            flags=flags,
        )

    async def set_feature_flag_override(
        self,
        tenant_id: UUID,
        feature_key: FeatureKeyType,
        value: bool,
        reason: str,
        admin_user: "PracticeUser",
    ) -> FeatureFlagOverrideResponse:
        """Set a feature flag override for a tenant.

        Args:
            tenant_id: The tenant's UUID.
            feature_key: The feature to override.
            value: True to enable, False to disable.
            reason: Reason for the override.
            admin_user: The admin making the change.

        Returns:
            Override response.

        Raises:
            TenantNotFoundError: If tenant not found.
            InvalidFeatureKeyError: If feature key is invalid.
            SelfModificationBlockedError: If admin tries to modify their own tenant.
        """
        logger.info(
            "setting_feature_flag_override",
            tenant_id=str(tenant_id),
            feature_key=feature_key,
            value=value,
            admin_id=str(admin_user.id),
        )

        # Validate feature key
        if feature_key not in VALID_FEATURE_KEYS:
            raise InvalidFeatureKeyError(feature_key, tenant_id)

        # Prevent self-modification
        if admin_user.tenant_id == tenant_id:
            raise SelfModificationBlockedError(admin_user.id, tenant_id)

        tenant = await self.admin_repo.get_tenant(
            tenant_id,
            load_users=False,
            load_billing_events=False,
        )
        if not tenant:
            raise TenantNotFoundError(tenant_id)

        # Get old value
        existing = await self.feature_flag_repo.get_override(tenant_id, feature_key)
        old_value: bool | None = None
        if existing:
            old_value = existing.override_value
        else:
            old_value = has_feature(tenant.tier.value, feature_key)

        # Create/update override
        await self.feature_flag_repo.upsert_override(
            tenant_id=tenant_id,
            feature_key=feature_key,
            value=value,
            reason=reason,
            admin_id=admin_user.id,
        )

        logger.info(
            "feature_flag_override_set",
            tenant_id=str(tenant_id),
            feature_key=feature_key,
            old_value=old_value,
            new_value=value,
        )

        return FeatureFlagOverrideResponse(
            success=True,
            tenant_id=tenant_id,
            feature_key=feature_key,
            old_value=old_value,
            new_value=value,
            effective_at=datetime.now(UTC),
        )

    async def delete_feature_flag_override(
        self,
        tenant_id: UUID,
        feature_key: FeatureKeyType,
        admin_user: "PracticeUser",
    ) -> FeatureFlagOverrideResponse:
        """Delete a feature flag override (revert to tier default).

        Args:
            tenant_id: The tenant's UUID.
            feature_key: The feature to revert.
            admin_user: The admin making the change.

        Returns:
            Override response.

        Raises:
            TenantNotFoundError: If tenant not found.
            SelfModificationBlockedError: If admin tries to modify their own tenant.
        """
        logger.info(
            "deleting_feature_flag_override",
            tenant_id=str(tenant_id),
            feature_key=feature_key,
            admin_id=str(admin_user.id),
        )

        # Prevent self-modification
        if admin_user.tenant_id == tenant_id:
            raise SelfModificationBlockedError(admin_user.id, tenant_id)

        tenant = await self.admin_repo.get_tenant(
            tenant_id,
            load_users=False,
            load_billing_events=False,
        )
        if not tenant:
            raise TenantNotFoundError(tenant_id)

        # Get current override
        existing = await self.feature_flag_repo.get_override(tenant_id, feature_key)
        old_value: bool | None = None
        if existing:
            old_value = existing.override_value

        # Delete override
        await self.feature_flag_repo.delete_override(tenant_id, feature_key)

        # New value is tier default
        new_value = has_feature(tenant.tier.value, feature_key)

        logger.info(
            "feature_flag_override_deleted",
            tenant_id=str(tenant_id),
            feature_key=feature_key,
        )

        return FeatureFlagOverrideResponse(
            success=True,
            tenant_id=tenant_id,
            feature_key=feature_key,
            old_value=old_value,
            new_value=new_value,
            effective_at=datetime.now(UTC),
        )

    # =========================================================================
    # Revenue Analytics
    # =========================================================================

    async def get_revenue_metrics(
        self,
        *,
        period_days: int = 30,
    ) -> RevenueMetricsResponse:
        """Get aggregate revenue metrics.

        Args:
            period_days: Number of days for the period (default 30).

        Returns:
            Revenue metrics response.
        """
        logger.info("getting_revenue_metrics", period_days=period_days)

        now = datetime.now(UTC)
        period_start = now - timedelta(days=period_days)
        previous_period_start = period_start - timedelta(days=period_days)

        # Get current tenant counts
        tenant_counts = await self.admin_repo.get_tenant_count_by_tier()
        total_active = await self.admin_repo.get_active_tenant_count()

        # Calculate current MRR
        current_mrr = 0
        for tier, count in tenant_counts.items():
            tier_price = TIER_PRICING.get(tier, 0) or 0
            current_mrr += tier_price * count

        # Calculate previous MRR (simplified - using same counts)
        # In production, would use historical snapshots
        previous_mrr = current_mrr

        # Get churn data
        churned_tenants = await self.admin_repo.get_churned_tenants(period_start)
        churn_lost = sum(TIER_PRICING.get(t.tier.value, 0) or 0 for t in churned_tenants)

        churn_rate = 0.0
        if total_active > 0:
            churn_rate = (len(churned_tenants) / total_active) * 100

        # Get new subscriptions for expansion calculation
        new_subs = await self.admin_repo.get_new_subscriptions(period_start)
        expansion_amount = sum(TIER_PRICING.get(t.tier.value, 0) or 0 for t in new_subs)

        # Calculate MRR change
        mrr_change = 0.0
        if previous_mrr > 0:
            mrr_change = ((current_mrr - previous_mrr) / previous_mrr) * 100

        return RevenueMetricsResponse(
            period=PeriodRange(
                start_date=period_start.date(),
                end_date=now.date(),
            ),
            mrr=MRRMetrics(
                current_cents=current_mrr,
                previous_cents=previous_mrr,
                change_percentage=mrr_change,
            ),
            churn=ChurnMetrics(
                rate_percentage=churn_rate,
                lost_cents=churn_lost,
                tenant_count=len(churned_tenants),
            ),
            expansion=ExpansionMetrics(
                amount_cents=expansion_amount,
                upgrade_count=len(new_subs),
                downgrade_count=0,  # TODO: Track downgrades
            ),
            tenant_counts=TenantCounts(
                total_active=total_active,
                by_tier=tenant_counts,
            ),
        )

    async def get_revenue_trends(
        self,
        period: RevenuePeriod = "daily",
        *,
        lookback_days: int = 30,
    ) -> RevenueTrendsResponse:
        """Get revenue trends over time.

        Args:
            period: Aggregation period (daily, weekly, monthly).
            lookback_days: Number of days to look back.

        Returns:
            Revenue trends response.
        """
        logger.info("getting_revenue_trends", period=period, lookback_days=lookback_days)

        # Simplified implementation - generate sample data points
        # In production, would query historical usage snapshots
        data_points = []
        now = datetime.now(UTC)

        tenant_counts = await self.admin_repo.get_tenant_count_by_tier()
        total_active = await self.admin_repo.get_active_tenant_count()

        # Calculate current MRR
        current_mrr = 0
        for tier, count in tenant_counts.items():
            tier_price = TIER_PRICING.get(tier, 0) or 0
            current_mrr += tier_price * count

        # Generate data points based on period
        if period == "daily":
            interval = timedelta(days=1)
            num_points = lookback_days
        elif period == "weekly":
            interval = timedelta(weeks=1)
            num_points = lookback_days // 7
        else:  # monthly
            interval = timedelta(days=30)
            num_points = lookback_days // 30

        for i in range(num_points):
            point_date = now - (interval * (num_points - i - 1))
            # Simplified: use current values with slight variation
            data_points.append(
                RevenueTrendDataPoint(
                    date=point_date.date(),
                    mrr_cents=current_mrr,
                    tenant_count=total_active,
                    new_subscriptions=0,
                    churned_subscriptions=0,
                )
            )

        return RevenueTrendsResponse(
            period=period,
            data_points=data_points,
        )

    # =========================================================================
    # Usage Analytics
    # =========================================================================

    async def get_platform_usage(self) -> PlatformUsageMetrics:
        """Get aggregate platform usage metrics.

        Returns:
            Platform usage metrics.
        """
        logger.info("getting_platform_usage")

        # TODO: Integrate with usage tracking module
        tenant_counts = await self.admin_repo.get_tenant_count_by_tier()

        return PlatformUsageMetrics(
            total_clients=0,  # TODO: Sum from all tenants
            total_syncs=0,  # TODO: Track sync operations
            total_ai_queries=0,  # TODO: Track AI usage
            by_tier={
                tier: {
                    "tenants": count,
                    "clients": 0,
                    "syncs": 0,
                    "ai_queries": 0,
                }
                for tier, count in tenant_counts.items()
            },
        )

    async def get_top_users(
        self,
        metric: str = "clients",
        *,
        limit: int = 10,
    ) -> TopUsersResponse:
        """Get top tenants by a specific metric.

        Args:
            metric: Metric to rank by (clients, syncs, ai_queries).
            limit: Number of top users to return.

        Returns:
            Top users response.
        """
        logger.info("getting_top_users", metric=metric, limit=limit)

        # TODO: Implement based on usage tracking
        return TopUsersResponse(
            metric=metric,
            users=[],  # Would return TopUserEntry list
        )
