"""Usage tracking Celery tasks.

This module contains scheduled tasks for:
- Daily usage snapshot capture
- Monthly usage counter reset

Spec 020: Usage Tracking & Limits
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.core.feature_flags import get_client_limit
from app.modules.auth.models import Tenant
from app.modules.billing.models import UsageSnapshot
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _get_async_session() -> AsyncSession:
    """Create a fresh async database session for scheduler tasks.

    Creates a new engine per call to avoid event loop issues with Celery.
    Uses NullPool to avoid connection leaks in Celery's asyncio.run() context.
    """
    settings = get_settings()
    engine = create_async_engine(settings.database.url, echo=False, poolclass=NullPool)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return async_session()


@celery_app.task(
    name="app.tasks.usage.capture_daily_usage_snapshots",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def capture_daily_usage_snapshots(self) -> dict:
    """Capture daily usage snapshots for all active tenants.

    This task runs daily at midnight UTC and:
    1. Queries all active tenants
    2. Creates a UsageSnapshot for each tenant with:
       - Current client count
       - AI queries this month
       - Documents processed this month
       - Current tier and client limit

    Used for historical trend analysis in usage dashboards.

    Returns:
        Dict with snapshot statistics.
    """
    import asyncio

    async def _capture_snapshots():
        session = await _get_async_session()
        try:
            # Get all active tenants
            query = select(Tenant).where(Tenant.is_active == True)  # noqa: E712
            result = await session.execute(query)
            tenants = result.scalars().all()

            captured_count = 0
            failed_count = 0

            logger.info(f"Capturing usage snapshots for {len(tenants)} active tenants")

            for tenant in tenants:
                try:
                    tier_value = (
                        tenant.tier.value if hasattr(tenant.tier, "value") else str(tenant.tier)
                    )
                    client_limit = get_client_limit(tier_value)

                    snapshot = UsageSnapshot(
                        tenant_id=tenant.id,
                        client_count=tenant.client_count,
                        ai_queries_count=tenant.ai_queries_month,
                        documents_count=tenant.documents_month,
                        tier=tier_value,
                        client_limit=client_limit,
                    )
                    session.add(snapshot)
                    captured_count += 1

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to capture snapshot for tenant {tenant.id}: {e}")

            await session.commit()

            logger.info(
                f"Usage snapshots captured: {captured_count} success, {failed_count} failed"
            )

            return {
                "total_tenants": len(tenants),
                "captured": captured_count,
                "failed": failed_count,
                "captured_at": datetime.now(UTC).isoformat(),
            }

        finally:
            await session.close()

    return asyncio.run(_capture_snapshots())


@celery_app.task(
    name="app.tasks.usage.reset_monthly_usage_counters",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def reset_monthly_usage_counters(self) -> dict:
    """Reset monthly usage counters for all tenants.

    This task runs on the 1st of each month at 00:05 UTC and:
    1. Resets ai_queries_month to 0 for all tenants
    2. Resets documents_month to 0 for all tenants
    3. Updates usage_month_reset date

    Returns:
        Dict with reset statistics.
    """
    import asyncio

    async def _reset_counters():
        session = await _get_async_session()
        try:
            # Get all tenants
            query = select(Tenant)
            result = await session.execute(query)
            tenants = result.scalars().all()

            reset_count = 0
            failed_count = 0
            today = datetime.now(UTC).date()

            logger.info(f"Resetting monthly usage counters for {len(tenants)} tenants")

            for tenant in tenants:
                try:
                    tenant.ai_queries_month = 0
                    tenant.documents_month = 0
                    tenant.usage_month_reset = today
                    reset_count += 1

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to reset counters for tenant {tenant.id}: {e}")

            await session.commit()

            logger.info(f"Monthly counters reset: {reset_count} success, {failed_count} failed")

            return {
                "total_tenants": len(tenants),
                "reset": reset_count,
                "failed": failed_count,
                "reset_date": today.isoformat(),
            }

        finally:
            await session.close()

    return asyncio.run(_reset_counters())
