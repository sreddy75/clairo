"""Admin usage service for aggregate statistics and upsell identification.

Provides platform-level usage analytics for admin users.

Spec 020: Usage Tracking & Limits
"""

from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.feature_flags import get_client_limit
from app.modules.auth.models import SubscriptionTier, Tenant
from app.modules.billing.models import UsageAlert, UsageSnapshot
from app.modules.billing.schemas import (
    AdminTenantUsageResponse,
    AdminUsageStats,
    SubscriptionTierType,
    ThresholdWarningType,
    UpsellOpportunity,
    UsageAlertResponse,
    UsageMetrics,
    UsageSnapshotResponse,
)

logger = structlog.get_logger(__name__)


def get_next_tier(current_tier: str) -> str | None:
    """Get the next upgrade tier for a given tier.

    Args:
        current_tier: Current subscription tier.

    Returns:
        Next tier name or None if at highest.
    """
    tier_order = ["starter", "professional", "growth", "enterprise"]
    try:
        current_index = tier_order.index(current_tier)
        if current_index < len(tier_order) - 1:
            return tier_order[current_index + 1]
        return current_tier  # Already at enterprise
    except ValueError:
        return None


def _get_threshold_warning(percentage: float) -> ThresholdWarningType | None:
    """Determine threshold warning based on percentage.

    Args:
        percentage: Usage percentage (0-100+).

    Returns:
        Threshold warning type or None if below 80%.
    """
    if percentage >= 100:
        return "100%"
    elif percentage >= 90:
        return "90%"
    elif percentage >= 80:
        return "80%"
    return None


class AdminUsageService:
    """Service for admin-level usage analytics.

    Provides aggregate statistics across all tenants and identifies
    upsell opportunities for tenants approaching their limits.

    Spec 020: Usage Tracking & Limits
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_aggregate_stats(self) -> AdminUsageStats:
        """Get aggregate usage statistics across all tenants.

        Returns:
            AdminUsageStats with platform-wide usage metrics.
        """
        # Get total tenant count
        total_tenants_query = (
            select(func.count())
            .select_from(Tenant)
            .where(
                Tenant.is_active == True  # noqa: E712
            )
        )
        total_tenants = await self.session.scalar(total_tenants_query) or 0

        # Get total client count
        total_clients_query = select(func.sum(Tenant.client_count)).where(
            Tenant.is_active == True  # noqa: E712
        )
        total_clients = await self.session.scalar(total_clients_query) or 0

        # Calculate average clients per tenant
        average_clients = float(total_clients) / total_tenants if total_tenants > 0 else 0.0

        # Get tenants at limit (non-enterprise tiers at 100%)
        tenants_at_limit = 0
        tenants_approaching = 0

        # Query all active tenants with their tiers and client counts
        tenants_query = select(Tenant.tier, Tenant.client_count).where(
            Tenant.is_active == True  # noqa: E712
        )
        result = await self.session.execute(tenants_query)
        tenant_data = result.all()

        # Count tenants by tier and check limits
        tenants_by_tier: dict[str, int] = {
            "starter": 0,
            "professional": 0,
            "growth": 0,
            "enterprise": 0,
        }

        for tier, client_count in tenant_data:
            tier_value = tier.value if hasattr(tier, "value") else str(tier)
            tenants_by_tier[tier_value] = tenants_by_tier.get(tier_value, 0) + 1

            # Get limit for this tier
            limit = get_client_limit(tier_value)
            if limit is not None and limit > 0:
                percentage = (client_count / limit) * 100
                if percentage >= 100:
                    tenants_at_limit += 1
                elif percentage >= 80:
                    tenants_approaching += 1

        logger.info(
            "Admin usage stats calculated",
            total_tenants=total_tenants,
            total_clients=total_clients,
            tenants_at_limit=tenants_at_limit,
            tenants_approaching_limit=tenants_approaching,
        )

        return AdminUsageStats(
            total_tenants=total_tenants,
            total_clients=total_clients,
            average_clients_per_tenant=round(average_clients, 2),
            tenants_at_limit=tenants_at_limit,
            tenants_approaching_limit=tenants_approaching,
            tenants_by_tier=tenants_by_tier,
        )

    async def get_upsell_opportunities(
        self,
        threshold: int = 80,
        tier: SubscriptionTierType | None = None,
        limit: int = 50,
    ) -> tuple[list[UpsellOpportunity], int]:
        """Get tenants approaching their client limit.

        These are upsell opportunities where tenants are at or near
        their tier's client limit and may benefit from upgrading.

        Args:
            threshold: Minimum percentage to consider (default 80).
            tier: Optional filter by specific tier.
            limit: Maximum results to return.

        Returns:
            Tuple of (list of opportunities, total count).
        """
        # Build base query
        query = select(
            Tenant.id,
            Tenant.name,
            Tenant.owner_email,
            Tenant.tier,
            Tenant.client_count,
        ).where(
            Tenant.is_active == True,  # noqa: E712
            Tenant.tier != SubscriptionTier.ENTERPRISE,  # Exclude unlimited
        )

        # Filter by tier if specified
        if tier:
            tier_enum = SubscriptionTier(tier)
            query = query.filter(Tenant.tier == tier_enum)

        result = await self.session.execute(query)
        all_tenants = result.all()

        # Filter by threshold and build opportunities
        opportunities: list[UpsellOpportunity] = []

        for tenant_id, name, owner_email, tenant_tier, client_count in all_tenants:
            tier_value = tenant_tier.value if hasattr(tenant_tier, "value") else str(tenant_tier)
            tier_limit = get_client_limit(tier_value)

            if tier_limit is None or tier_limit <= 0:
                continue

            percentage = (client_count / tier_limit) * 100

            if percentage >= threshold:
                opportunities.append(
                    UpsellOpportunity(
                        tenant_id=tenant_id,
                        tenant_name=name,
                        owner_email=owner_email or "",
                        current_tier=tier_value,  # type: ignore[arg-type]
                        client_count=client_count,
                        client_limit=tier_limit,
                        percentage_used=round(percentage, 1),
                    )
                )

        # Sort by percentage descending (highest usage first)
        opportunities.sort(key=lambda x: x.percentage_used, reverse=True)

        total = len(opportunities)

        logger.info(
            "Upsell opportunities found",
            threshold=threshold,
            tier_filter=tier,
            total=total,
            returning=min(limit, total),
        )

        return opportunities[:limit], total

    async def get_tenant_usage_details(
        self,
        tenant_id: UUID,
    ) -> AdminTenantUsageResponse | None:
        """Get detailed usage information for a specific tenant.

        Args:
            tenant_id: The tenant's UUID.

        Returns:
            AdminTenantUsageResponse with full usage details, or None if not found.
        """
        # Get tenant
        tenant_query = select(Tenant).where(Tenant.id == tenant_id)
        tenant = await self.session.scalar(tenant_query)

        if not tenant:
            logger.warning("Tenant not found for usage details", tenant_id=str(tenant_id))
            return None

        tier_value: SubscriptionTierType = tenant.tier.value  # type: ignore[assignment]
        client_limit = get_client_limit(tier_value)

        # Calculate percentage
        if client_limit is not None and client_limit > 0:
            percentage = (tenant.client_count / client_limit) * 100
        else:
            percentage = None

        # Build usage metrics
        usage = UsageMetrics(
            client_count=tenant.client_count,
            client_limit=client_limit,
            client_percentage=round(percentage, 1) if percentage else None,
            ai_queries_month=tenant.ai_queries_month,
            documents_month=tenant.documents_month,
            is_at_limit=percentage is not None and percentage >= 100,
            is_approaching_limit=percentage is not None and percentage >= 80,
            threshold_warning=_get_threshold_warning(percentage) if percentage else None,
            tier=tier_value,
            next_tier=get_next_tier(tier_value),  # type: ignore[arg-type]
        )

        # Get usage history (last 3 months of snapshots)
        history_query = (
            select(UsageSnapshot)
            .where(UsageSnapshot.tenant_id == tenant_id)
            .order_by(UsageSnapshot.captured_at.desc())
            .limit(90)  # ~90 days of daily snapshots
        )
        history_result = await self.session.execute(history_query)
        snapshots = history_result.scalars().all()

        history = [
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
        ]

        # Get recent alerts (last 10)
        alerts_query = (
            select(UsageAlert)
            .where(UsageAlert.tenant_id == tenant_id)
            .order_by(UsageAlert.sent_at.desc())
            .limit(10)
        )
        alerts_result = await self.session.execute(alerts_query)
        alert_records = alerts_result.scalars().all()

        alerts = [
            UsageAlertResponse(
                id=a.id,
                alert_type=a.alert_type.value,  # type: ignore[arg-type]
                billing_period=a.billing_period,
                threshold_percentage=a.threshold_percentage,
                client_count_at_alert=a.client_count_at_alert,
                client_limit_at_alert=a.client_limit_at_alert,
                sent_at=a.sent_at,
            )
            for a in alert_records
        ]

        logger.info(
            "Tenant usage details retrieved",
            tenant_id=str(tenant_id),
            tenant_name=tenant.name,
            client_count=tenant.client_count,
            history_count=len(history),
            alerts_count=len(alerts),
        )

        return AdminTenantUsageResponse(
            tenant_id=tenant.id,
            tenant_name=tenant.name,
            tier=tier_value,
            usage=usage,
            history=history,
            alerts=alerts,
        )

    async def get_platform_usage(self) -> dict:
        """Get aggregate platform usage metrics.

        Returns:
            Dictionary with platform-wide usage metrics.
        """
        from app.modules.admin.schemas import PlatformUsageMetrics

        # Get total clients
        total_clients_query = select(func.sum(Tenant.client_count)).where(
            Tenant.is_active == True  # noqa: E712
        )
        total_clients = await self.session.scalar(total_clients_query) or 0

        # Get total AI queries
        total_ai_queries_query = select(func.sum(Tenant.ai_queries_month)).where(
            Tenant.is_active == True  # noqa: E712
        )
        total_ai_queries = await self.session.scalar(total_ai_queries_query) or 0

        # Get tenant data by tier
        tenants_query = select(Tenant.tier, Tenant.client_count, Tenant.ai_queries_month).where(
            Tenant.is_active == True
        )  # noqa: E712
        result = await self.session.execute(tenants_query)
        tenant_data = result.all()

        # Build metrics by tier
        by_tier: dict[str, dict[str, int]] = {
            "starter": {"tenants": 0, "clients": 0, "ai_queries": 0},
            "professional": {"tenants": 0, "clients": 0, "ai_queries": 0},
            "growth": {"tenants": 0, "clients": 0, "ai_queries": 0},
            "enterprise": {"tenants": 0, "clients": 0, "ai_queries": 0},
        }

        for tier, client_count, ai_queries in tenant_data:
            tier_value = tier.value if hasattr(tier, "value") else str(tier)
            if tier_value in by_tier:
                by_tier[tier_value]["tenants"] += 1
                by_tier[tier_value]["clients"] += client_count or 0
                by_tier[tier_value]["ai_queries"] += ai_queries or 0

        # Count total syncs (approximate from xero connections)
        total_syncs = 0
        try:
            from app.modules.integrations.xero.models import XeroConnection

            syncs_query = (
                select(func.count())
                .select_from(XeroConnection)
                .where(XeroConnection.last_sync_at.isnot(None))
            )
            total_syncs = await self.session.scalar(syncs_query) or 0
        except Exception:
            pass  # Xero module may not be available

        logger.info(
            "Platform usage metrics calculated",
            total_clients=total_clients,
            total_ai_queries=total_ai_queries,
            total_syncs=total_syncs,
        )

        return PlatformUsageMetrics(
            total_clients=total_clients,
            total_syncs=total_syncs,
            total_ai_queries=total_ai_queries,
            by_tier=by_tier,
        )

    async def get_top_users(
        self,
        metric: str = "clients",
        limit: int = 10,
    ) -> dict:
        """Get top tenants by a specific metric.

        Args:
            metric: Metric to rank by (clients, syncs, ai_queries).
            limit: Maximum number of results.

        Returns:
            Dictionary with metric and top users list.
        """
        from app.modules.admin.schemas import TopUserEntry, TopUsersResponse

        # Determine which column to order by
        if metric == "clients":
            order_column = Tenant.client_count
        elif metric == "ai_queries":
            order_column = Tenant.ai_queries_month
        else:
            order_column = Tenant.client_count  # Default to clients

        # Query top tenants
        query = (
            select(Tenant.id, Tenant.name, order_column)
            .where(Tenant.is_active == True)  # noqa: E712
            .order_by(order_column.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        tenant_data = result.all()

        users = [
            TopUserEntry(
                tenant_id=tenant_id,
                tenant_name=name,
                value=value or 0,
            )
            for tenant_id, name, value in tenant_data
        ]

        logger.info(
            "Top users retrieved",
            metric=metric,
            limit=limit,
            count=len(users),
        )

        return TopUsersResponse(
            metric=metric,
            users=users,
        )
