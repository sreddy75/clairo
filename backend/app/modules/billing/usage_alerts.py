"""Usage alert service for sending threshold notifications.

Handles checking usage thresholds and sending email alerts to tenant owners
when approaching or reaching client limits.

Spec 020: Usage Tracking & Limits
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.feature_flags import get_client_limit
from app.modules.billing.models import UsageAlertType
from app.modules.billing.repository import UsageRepository
from app.modules.notifications.email_service import EmailService, get_email_service

if TYPE_CHECKING:
    from app.modules.auth.models import Tenant

logger = structlog.get_logger(__name__)


class UsageAlertService:
    """Service for checking and sending usage threshold alerts.

    Handles the business logic for:
    - Detecting when tenants cross 80%, 90%, or 100% thresholds
    - Sending appropriate email notifications
    - Recording alerts to prevent duplicates within a billing period
    """

    def __init__(
        self,
        session: AsyncSession,
        email_service: EmailService | None = None,
    ) -> None:
        self.session = session
        self.usage_repository = UsageRepository(session)
        self.email_service = email_service or get_email_service()

    @staticmethod
    def get_current_billing_period() -> str:
        """Get the current billing period in YYYY-MM format.

        Returns:
            String like "2025-01" for January 2025.
        """
        now = datetime.now(tz=UTC)
        return now.strftime("%Y-%m")

    async def check_and_send_threshold_alerts(
        self,
        tenant: "Tenant",
    ) -> list[UsageAlertType]:
        """Check if tenant has crossed any thresholds and send alerts.

        This method is idempotent - it won't send duplicate alerts for the
        same threshold in the same billing period.

        Args:
            tenant: The tenant to check.

        Returns:
            List of alert types that were sent.
        """
        from app.modules.billing.schemas import SubscriptionTierType

        tier: SubscriptionTierType = tenant.tier.value  # type: ignore[assignment]
        limit = get_client_limit(tier)

        # No alerts for unlimited tiers
        if limit is None:
            return []

        client_count = tenant.client_count
        percentage = (client_count / limit * 100) if limit > 0 else 0
        billing_period = self.get_current_billing_period()
        alerts_sent: list[UsageAlertType] = []

        # Determine which thresholds have been crossed
        if percentage >= 100:
            # Check and send 100% (limit reached) alert
            sent = await self._send_alert_if_not_exists(
                tenant=tenant,
                alert_type=UsageAlertType.LIMIT_REACHED,
                billing_period=billing_period,
                threshold_percentage=100,
                client_count=client_count,
                client_limit=limit,
            )
            if sent:
                alerts_sent.append(UsageAlertType.LIMIT_REACHED)

        if percentage >= 90:
            # Check and send 90% alert
            sent = await self._send_alert_if_not_exists(
                tenant=tenant,
                alert_type=UsageAlertType.THRESHOLD_90,
                billing_period=billing_period,
                threshold_percentage=90,
                client_count=client_count,
                client_limit=limit,
            )
            if sent:
                alerts_sent.append(UsageAlertType.THRESHOLD_90)

        if percentage >= 80:
            # Check and send 80% alert
            sent = await self._send_alert_if_not_exists(
                tenant=tenant,
                alert_type=UsageAlertType.THRESHOLD_80,
                billing_period=billing_period,
                threshold_percentage=80,
                client_count=client_count,
                client_limit=limit,
            )
            if sent:
                alerts_sent.append(UsageAlertType.THRESHOLD_80)

        return alerts_sent

    async def _send_alert_if_not_exists(
        self,
        tenant: "Tenant",
        alert_type: UsageAlertType,
        billing_period: str,
        threshold_percentage: int,
        client_count: int,
        client_limit: int,
    ) -> bool:
        """Send an alert if one hasn't been sent this billing period.

        Args:
            tenant: The tenant to alert.
            alert_type: Type of alert to send.
            billing_period: Current billing period (YYYY-MM).
            threshold_percentage: The threshold that was crossed.
            client_count: Current client count.
            client_limit: Client limit for the tier.

        Returns:
            True if alert was sent, False if already sent or skipped.
        """
        # Check if we already sent this alert
        exists = await self.usage_repository.check_alert_exists(
            tenant_id=tenant.id,
            alert_type=alert_type,
            billing_period=billing_period,
        )

        if exists:
            logger.debug(
                "Alert already sent, skipping",
                tenant_id=str(tenant.id),
                alert_type=alert_type.value,
                billing_period=billing_period,
            )
            return False

        # Get recipient email
        recipient_email = tenant.owner_email
        if not recipient_email:
            logger.warning(
                "No owner email for tenant, cannot send alert",
                tenant_id=str(tenant.id),
                alert_type=alert_type.value,
            )
            return False

        # Get user name (fallback to tenant name)
        user_name = tenant.name  # Could be improved with actual owner name

        # Send the appropriate email
        tier_value: str = tenant.tier.value  # type: ignore[assignment]

        try:
            if alert_type == UsageAlertType.LIMIT_REACHED:
                await self.email_service.send_usage_limit_reached(
                    to=recipient_email,
                    user_name=user_name,
                    practice_name=tenant.name,
                    client_count=client_count,
                    client_limit=client_limit,
                    tier=tier_value,
                )
            else:
                # Threshold 80 or 90
                await self.email_service.send_usage_threshold_alert(
                    to=recipient_email,
                    user_name=user_name,
                    practice_name=tenant.name,
                    percentage=threshold_percentage,
                    client_count=client_count,
                    client_limit=client_limit,
                    tier=tier_value,
                )

            # Record the alert to prevent duplicates
            await self.usage_repository.create_alert(
                tenant_id=tenant.id,
                alert_type=alert_type,
                billing_period=billing_period,
                threshold_percentage=threshold_percentage,
                client_count_at_alert=client_count,
                client_limit_at_alert=client_limit,
                recipient_email=recipient_email,
            )

            logger.info(
                "Usage alert sent",
                tenant_id=str(tenant.id),
                alert_type=alert_type.value,
                threshold=threshold_percentage,
                client_count=client_count,
                client_limit=client_limit,
                recipient=recipient_email,
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to send usage alert",
                tenant_id=str(tenant.id),
                alert_type=alert_type.value,
                error=str(e),
            )
            # Don't raise - we don't want to fail the main operation
            return False

    async def get_alerts_for_tenant(
        self,
        tenant_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Get usage alerts for a tenant.

        Args:
            tenant_id: The tenant ID.
            limit: Maximum alerts to return.
            offset: Pagination offset.

        Returns:
            Tuple of (alerts as dicts, total count).
        """
        alerts, total = await self.usage_repository.get_usage_alerts_for_tenant(
            tenant_id=tenant_id,
            limit=limit,
            offset=offset,
        )

        return [
            {
                "id": str(alert.id),
                "alert_type": alert.alert_type.value,
                "billing_period": alert.billing_period,
                "threshold_percentage": alert.threshold_percentage,
                "client_count_at_alert": alert.client_count_at_alert,
                "client_limit_at_alert": alert.client_limit_at_alert,
                "sent_at": alert.sent_at.isoformat(),
            }
            for alert in alerts
        ], total
