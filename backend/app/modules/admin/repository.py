"""Admin module repository for database operations.

Provides repositories for admin dashboard operations:
- AdminRepository: Multi-tenant queries for admin operations
- FeatureFlagOverrideRepository: Feature flag override CRUD

Spec 022: Admin Dashboard (Internal)
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.modules.admin.models import FeatureFlagOverride
from app.modules.auth.models import (
    PracticeUser,
    SubscriptionStatus,
    SubscriptionTier,
    Tenant,
)
from app.modules.billing.models import BillingEvent
from app.modules.integrations.xero.models import XpmClient

# =============================================================================
# Type aliases
# =============================================================================

TenantStatusFilter = Literal["active", "inactive", "all"]
TenantSortField = Literal["name", "created_at", "mrr", "client_count"]
SortOrder = Literal["asc", "desc"]


# =============================================================================
# Admin Repository
# =============================================================================


class AdminRepository:
    """Repository for admin dashboard multi-tenant operations.

    This repository bypasses normal tenant isolation to allow
    admins to view and manage all tenants.

    Spec 022: Admin Dashboard (Internal)
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository.

        Args:
            session: Async database session.
        """
        self._session = session

    async def list_tenants(
        self,
        *,
        search: str | None = None,
        tier: SubscriptionTier | None = None,
        status: TenantStatusFilter = "all",
        sort_by: TenantSortField = "created_at",
        sort_order: SortOrder = "desc",
        page: int = 1,
        limit: int = 20,
    ) -> tuple[Sequence[Tenant], int]:
        """List all tenants with filtering, sorting, and pagination.

        Args:
            search: Search string for tenant name or email.
            tier: Filter by subscription tier.
            status: Filter by active/inactive status.
            sort_by: Field to sort by.
            sort_order: Sort direction (asc/desc).
            page: Page number (1-indexed).
            limit: Page size.

        Returns:
            Tuple of (tenants, total_count).
        """
        # Base query with client count subquery
        client_count_subquery = (
            select(
                XpmClient.tenant_id,
                func.count(XpmClient.id).label("client_count"),
            )
            .group_by(XpmClient.tenant_id)
            .subquery()
        )

        # Build base query
        query = (
            select(Tenant)
            .outerjoin(
                client_count_subquery,
                Tenant.id == client_count_subquery.c.tenant_id,
            )
            .options(joinedload(Tenant.practice_users).joinedload(PracticeUser.user))
        )

        # Apply filters
        filters = []

        if search:
            search_pattern = f"%{search.lower()}%"
            # Search in tenant name
            filters.append(func.lower(Tenant.name).like(search_pattern))

        if tier:
            filters.append(Tenant.tier == tier)

        if status == "active":
            filters.append(Tenant.is_active == True)  # noqa: E712
        elif status == "inactive":
            filters.append(Tenant.is_active == False)  # noqa: E712

        if filters:
            query = query.where(and_(*filters))

        # Get total count (before pagination)
        count_query = select(func.count()).select_from(Tenant)
        if filters:
            count_query = count_query.where(and_(*filters))
        total = await self._session.scalar(count_query) or 0

        # Apply sorting
        sort_column = {
            "name": Tenant.name,
            "created_at": Tenant.created_at,
            "mrr": Tenant.stripe_subscription_id,  # Use as proxy for MRR
            "client_count": func.coalesce(client_count_subquery.c.client_count, 0),
        }.get(sort_by, Tenant.created_at)

        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        # Execute query
        result = await self._session.execute(query)
        tenants = result.unique().scalars().all()

        return tenants, total

    async def get_tenant(
        self,
        tenant_id: UUID,
        *,
        load_users: bool = True,
        load_billing_events: bool = True,
    ) -> Tenant | None:
        """Get a tenant by ID with optional relationships.

        Args:
            tenant_id: The tenant's UUID.
            load_users: Whether to load practice users.
            load_billing_events: Whether to load billing history.

        Returns:
            The tenant if found, None otherwise.
        """
        query = select(Tenant).where(Tenant.id == tenant_id)

        if load_users:
            query = query.options(joinedload(Tenant.practice_users).joinedload(PracticeUser.user))

        result = await self._session.execute(query)
        tenant = result.unique().scalar_one_or_none()

        return tenant

    async def get_tenant_client_count(self, tenant_id: UUID) -> int:
        """Get the current client count for a tenant.

        Args:
            tenant_id: The tenant's UUID.

        Returns:
            Client count.
        """
        query = select(func.count()).select_from(XpmClient).where(XpmClient.tenant_id == tenant_id)
        return await self._session.scalar(query) or 0

    async def update_tenant_tier(
        self,
        tenant_id: UUID,
        new_tier: SubscriptionTier,
    ) -> Tenant | None:
        """Update a tenant's subscription tier.

        Args:
            tenant_id: The tenant's UUID.
            new_tier: The new tier to set.

        Returns:
            The updated tenant if found, None otherwise.
        """
        await self._session.execute(
            update(Tenant)
            .where(Tenant.id == tenant_id)
            .values(tier=new_tier, updated_at=datetime.now(UTC))
        )
        await self._session.flush()
        return await self.get_tenant(tenant_id, load_billing_events=False)

    async def get_billing_events_for_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int = 20,
    ) -> Sequence[BillingEvent]:
        """Get recent billing events for a tenant.

        Args:
            tenant_id: The tenant's UUID.
            limit: Maximum number of events to return.

        Returns:
            List of billing events.
        """
        query = (
            select(BillingEvent)
            .where(BillingEvent.tenant_id == tenant_id)
            .order_by(BillingEvent.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(query)
        return result.scalars().all()

    async def create_billing_event(
        self,
        *,
        tenant_id: UUID,
        event_type: str,
        event_data: dict,
        amount_cents: int | None = None,
        admin_id: UUID | None = None,
    ) -> BillingEvent:
        """Create a billing event for audit purposes.

        Args:
            tenant_id: The tenant's UUID.
            event_type: Type of event (e.g., "tier_change", "credit_applied").
            event_data: Event details.
            amount_cents: Amount in cents if applicable.
            admin_id: ID of admin who performed the action.

        Returns:
            The created billing event.
        """
        from app.modules.billing.models import BillingEventStatus

        # Generate a unique event ID for admin actions
        stripe_event_id = f"admin_{event_type}_{datetime.now(UTC).timestamp()}"

        event = BillingEvent(
            tenant_id=tenant_id,
            stripe_event_id=stripe_event_id,
            event_type=event_type,
            event_data={
                **event_data,
                "performed_by_admin": str(admin_id) if admin_id else None,
            },
            amount_cents=amount_cents,
            currency="aud",
            status=BillingEventStatus.PROCESSED,
            processed_at=datetime.now(UTC),
        )
        self._session.add(event)
        await self._session.flush()
        return event

    # -------------------------------------------------------------------------
    # Revenue Analytics
    # -------------------------------------------------------------------------

    async def get_active_tenant_count(self) -> int:
        """Get total count of active tenants."""
        query = (
            select(func.count())
            .select_from(Tenant)
            .where(
                Tenant.is_active == True  # noqa: E712
            )
        )
        return await self._session.scalar(query) or 0

    async def get_tenant_count_by_tier(self) -> dict[str, int]:
        """Get tenant counts grouped by tier."""
        query = (
            select(Tenant.tier, func.count(Tenant.id))
            .where(Tenant.is_active == True)  # noqa: E712
            .group_by(Tenant.tier)
        )
        result = await self._session.execute(query)
        return {row[0].value: row[1] for row in result.all()}

    async def get_churned_tenants(
        self,
        since: datetime,
    ) -> Sequence[Tenant]:
        """Get tenants that churned since a given date.

        Args:
            since: Start date for churn calculation.

        Returns:
            List of churned tenants.
        """
        query = select(Tenant).where(
            Tenant.is_active == False,  # noqa: E712
            Tenant.updated_at >= since,
        )
        result = await self._session.execute(query)
        return result.scalars().all()

    async def get_new_subscriptions(
        self,
        since: datetime,
    ) -> Sequence[Tenant]:
        """Get tenants that subscribed since a given date.

        Args:
            since: Start date.

        Returns:
            List of new tenants.
        """
        query = select(Tenant).where(
            Tenant.created_at >= since,
            Tenant.subscription_status == SubscriptionStatus.ACTIVE,
        )
        result = await self._session.execute(query)
        return result.scalars().all()


# =============================================================================
# Feature Flag Override Repository
# =============================================================================


class FeatureFlagOverrideRepository:
    """Repository for feature flag override operations.

    Manages per-tenant feature flag overrides that take precedence
    over tier-based defaults.

    Spec 022: Admin Dashboard (Internal)
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository.

        Args:
            session: Async database session.
        """
        self._session = session

    async def get_by_tenant(
        self,
        tenant_id: UUID,
    ) -> Sequence[FeatureFlagOverride]:
        """Get all feature flag overrides for a tenant.

        Args:
            tenant_id: The tenant's UUID.

        Returns:
            List of overrides.
        """
        query = (
            select(FeatureFlagOverride)
            .where(FeatureFlagOverride.tenant_id == tenant_id)
            .options(
                joinedload(FeatureFlagOverride.creator),
                joinedload(FeatureFlagOverride.updater),
            )
            .order_by(FeatureFlagOverride.feature_key)
        )
        result = await self._session.execute(query)
        return result.scalars().all()

    async def get_override(
        self,
        tenant_id: UUID,
        feature_key: str,
    ) -> FeatureFlagOverride | None:
        """Get a specific feature flag override.

        Args:
            tenant_id: The tenant's UUID.
            feature_key: The feature key.

        Returns:
            The override if found, None otherwise.
        """
        query = (
            select(FeatureFlagOverride)
            .where(
                FeatureFlagOverride.tenant_id == tenant_id,
                FeatureFlagOverride.feature_key == feature_key,
            )
            .options(
                joinedload(FeatureFlagOverride.creator),
                joinedload(FeatureFlagOverride.updater),
            )
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def upsert_override(
        self,
        *,
        tenant_id: UUID,
        feature_key: str,
        value: bool,
        reason: str,
        admin_id: UUID,
    ) -> FeatureFlagOverride:
        """Create or update a feature flag override.

        Args:
            tenant_id: The tenant's UUID.
            feature_key: The feature key.
            value: The override value (True=enable, False=disable).
            reason: Reason for the override.
            admin_id: ID of the admin making the change.

        Returns:
            The created or updated override.
        """
        existing = await self.get_override(tenant_id, feature_key)

        if existing:
            # Update existing override
            existing.override_value = value
            existing.reason = reason
            existing.updated_by = admin_id
            existing.updated_at = datetime.now(UTC)
            await self._session.flush()
            await self._session.refresh(existing)
            return existing
        else:
            # Create new override
            override = FeatureFlagOverride(
                tenant_id=tenant_id,
                feature_key=feature_key,
                override_value=value,
                reason=reason,
                created_by=admin_id,
            )
            self._session.add(override)
            await self._session.flush()
            await self._session.refresh(override)
            return override

    async def delete_override(
        self,
        tenant_id: UUID,
        feature_key: str,
    ) -> bool:
        """Delete a feature flag override (revert to tier default).

        Args:
            tenant_id: The tenant's UUID.
            feature_key: The feature key.

        Returns:
            True if deleted, False if not found.
        """
        override = await self.get_override(tenant_id, feature_key)
        if override:
            await self._session.delete(override)
            await self._session.flush()
            return True
        return False

    async def get_all_overrides_for_feature(
        self,
        feature_key: str,
    ) -> Sequence[FeatureFlagOverride]:
        """Get all overrides for a specific feature across all tenants.

        Useful for auditing and bulk operations.

        Args:
            feature_key: The feature key.

        Returns:
            List of overrides.
        """
        query = (
            select(FeatureFlagOverride)
            .where(FeatureFlagOverride.feature_key == feature_key)
            .options(joinedload(FeatureFlagOverride.tenant))
            .order_by(FeatureFlagOverride.created_at.desc())
        )
        result = await self._session.execute(query)
        return result.scalars().all()
