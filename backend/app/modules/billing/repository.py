"""Billing module repository for database operations.

Follows the repository pattern for database access.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.models import (
    BillingEvent,
    BillingEventStatus,
    UsageAlert,
    UsageAlertType,
    UsageSnapshot,
)


class BillingEventRepository:
    """Repository for BillingEvent database operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        tenant_id: UUID,
        stripe_event_id: str,
        event_type: str,
        event_data: dict,
        amount_cents: int | None = None,
        currency: str = "aud",
        status: BillingEventStatus = BillingEventStatus.PROCESSED,
    ) -> BillingEvent:
        """Create a new billing event."""
        event = BillingEvent(
            tenant_id=tenant_id,
            stripe_event_id=stripe_event_id,
            event_type=event_type,
            event_data=event_data,
            amount_cents=amount_cents,
            currency=currency,
            status=status,
            processed_at=datetime.now(UTC) if status == BillingEventStatus.PROCESSED else None,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_by_stripe_event_id(self, stripe_event_id: str) -> BillingEvent | None:
        """Get a billing event by Stripe event ID.

        Used for idempotency checking.
        """
        result = await self.session.execute(
            select(BillingEvent).where(BillingEvent.stripe_event_id == stripe_event_id)
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[BillingEvent], int]:
        """List billing events for a tenant with pagination.

        Returns a tuple of (events, total_count).
        """
        # Get total count
        count_query = (
            select(func.count())
            .select_from(BillingEvent)
            .where(BillingEvent.tenant_id == tenant_id)
        )
        total = await self.session.scalar(count_query) or 0

        # Get events
        query = (
            select(BillingEvent)
            .where(BillingEvent.tenant_id == tenant_id)
            .order_by(BillingEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        events = result.scalars().all()

        return events, total

    async def update_status(
        self,
        event_id: UUID,
        status: BillingEventStatus,
    ) -> BillingEvent | None:
        """Update the status of a billing event."""
        result = await self.session.execute(select(BillingEvent).where(BillingEvent.id == event_id))
        event = result.scalar_one_or_none()
        if event:
            event.status = status
            if status == BillingEventStatus.PROCESSED:
                event.processed_at = datetime.now(UTC)
            await self.session.flush()
        return event


# =============================================================================
# Usage Tracking Repository (Spec 020)
# =============================================================================


class UsageRepository:
    """Repository for usage tracking database operations.

    Spec 020: Usage Tracking & Limits
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -------------------------------------------------------------------------
    # Usage Snapshots
    # -------------------------------------------------------------------------

    async def create_snapshot(
        self,
        *,
        tenant_id: UUID,
        client_count: int,
        ai_queries_count: int,
        documents_count: int,
        tier: str,
        client_limit: int | None,
    ) -> UsageSnapshot:
        """Create a new usage snapshot."""
        snapshot = UsageSnapshot(
            tenant_id=tenant_id,
            client_count=client_count,
            ai_queries_count=ai_queries_count,
            documents_count=documents_count,
            tier=tier,
            client_limit=client_limit,
        )
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    async def get_usage_snapshots_for_tenant(
        self,
        tenant_id: UUID,
        *,
        months: int = 3,
        limit: int = 100,
    ) -> Sequence[UsageSnapshot]:
        """Get usage snapshots for a tenant within the specified months.

        Args:
            tenant_id: The tenant ID.
            months: Number of months of history to retrieve (default 3).
            limit: Maximum number of snapshots to return.

        Returns:
            List of usage snapshots ordered by captured_at descending.
        """
        start_date = datetime.now(UTC) - timedelta(days=months * 30)

        query = (
            select(UsageSnapshot)
            .where(
                UsageSnapshot.tenant_id == tenant_id,
                UsageSnapshot.captured_at >= start_date,
            )
            .order_by(UsageSnapshot.captured_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_usage_history(
        self,
        tenant_id: UUID,
        *,
        months: int = 3,
    ) -> tuple[Sequence[UsageSnapshot], datetime, datetime]:
        """Get usage history with period bounds.

        Args:
            tenant_id: The tenant ID.
            months: Number of months of history.

        Returns:
            Tuple of (snapshots, period_start, period_end).
        """
        period_end = datetime.now(UTC)
        period_start = period_end - timedelta(days=months * 30)

        snapshots = await self.get_usage_snapshots_for_tenant(tenant_id, months=months)
        return snapshots, period_start, period_end

    # -------------------------------------------------------------------------
    # Usage Alerts
    # -------------------------------------------------------------------------

    async def create_alert(
        self,
        *,
        tenant_id: UUID,
        alert_type: UsageAlertType,
        billing_period: str,
        threshold_percentage: int,
        client_count_at_alert: int,
        client_limit_at_alert: int,
        recipient_email: str,
    ) -> UsageAlert:
        """Create a new usage alert record."""
        alert = UsageAlert(
            tenant_id=tenant_id,
            alert_type=alert_type,
            billing_period=billing_period,
            threshold_percentage=threshold_percentage,
            client_count_at_alert=client_count_at_alert,
            client_limit_at_alert=client_limit_at_alert,
            recipient_email=recipient_email,
        )
        self.session.add(alert)
        await self.session.flush()
        return alert

    async def check_alert_exists(
        self,
        tenant_id: UUID,
        alert_type: UsageAlertType,
        billing_period: str,
    ) -> bool:
        """Check if an alert already exists for this tenant/type/period.

        Used for deduplication to prevent sending the same alert twice.
        """
        query = (
            select(func.count())
            .select_from(UsageAlert)
            .where(
                UsageAlert.tenant_id == tenant_id,
                UsageAlert.alert_type == alert_type,
                UsageAlert.billing_period == billing_period,
            )
        )
        count = await self.session.scalar(query) or 0
        return count > 0

    async def get_usage_alerts_for_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[UsageAlert], int]:
        """Get usage alerts for a tenant with pagination.

        Returns:
            Tuple of (alerts, total_count).
        """
        # Get total count
        count_query = (
            select(func.count()).select_from(UsageAlert).where(UsageAlert.tenant_id == tenant_id)
        )
        total = await self.session.scalar(count_query) or 0

        # Get alerts
        query = (
            select(UsageAlert)
            .where(UsageAlert.tenant_id == tenant_id)
            .order_by(UsageAlert.sent_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        alerts = result.scalars().all()

        return alerts, total
