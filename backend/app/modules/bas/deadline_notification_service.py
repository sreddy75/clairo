"""Service for BAS lodgement deadline notifications.

Spec 011: Interim Lodgement
"""

import logging
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import PracticeUser
from app.modules.bas.models import BASAuditEventType, BASAuditLog
from app.modules.bas.repository import BASRepository
from app.modules.integrations.xero.models import XeroConnection
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import NotificationService

logger = logging.getLogger(__name__)

# Default notification thresholds (days before due date)
DEFAULT_NOTIFICATION_DAYS = [7, 3, 1]


class DeadlineNotificationService:
    """Service for generating BAS lodgement deadline notifications."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = BASRepository(session)

    async def check_and_notify_approaching_deadlines(
        self,
        tenant_id: UUID,
        notification_days: list[int] | None = None,
        reference_date: date | None = None,
    ) -> dict[str, int]:
        """Check for approaching deadlines and send notifications.

        Args:
            tenant_id: The tenant ID to check
            notification_days: Days before deadline to notify (default: [7, 3, 1])
            reference_date: Reference date for calculation (defaults to today)

        Returns:
            Dict with notification results
        """
        if notification_days is None:
            notification_days = DEFAULT_NOTIFICATION_DAYS

        if reference_date is None:
            reference_date = datetime.now(UTC).date()

        max_days = max(notification_days)
        sessions = await self.repo.get_sessions_with_approaching_deadlines(
            tenant_id=tenant_id,
            days_ahead=max_days,
            reference_date=reference_date,
        )

        results = {
            "sessions_checked": len(sessions),
            "notifications_sent": 0,
        }

        notification_service = NotificationService(self.session)

        # Get all practice users for the tenant (they all get notified)
        user_stmt = select(PracticeUser).where(PracticeUser.tenant_id == tenant_id)
        user_result = await self.session.execute(user_stmt)
        users = list(user_result.scalars().all())

        if not users:
            logger.warning(f"No practice users found for tenant {tenant_id}")
            return results

        for bas_session in sessions:
            period = bas_session.period
            days_remaining = (period.due_date - reference_date).days

            # Check if this is a notification threshold day
            if days_remaining not in notification_days:
                continue

            # Get client name from connection
            conn_stmt = select(XeroConnection).where(XeroConnection.id == period.connection_id)
            conn_result = await self.session.execute(conn_stmt)
            connection = conn_result.scalar_one_or_none()
            client_name = connection.organization_name if connection else "Unknown Client"

            # Determine notification urgency
            if days_remaining <= 1:
                title = f"⚠️ BAS due tomorrow: {client_name}"
            elif days_remaining <= 3:
                title = f"⏰ BAS due in {days_remaining} days: {client_name}"
            else:
                title = f"📅 BAS due in {days_remaining} days: {client_name}"

            message = (
                f"The {period.display_name} BAS for {client_name} "
                f"is due on {period.due_date.strftime('%d %b %Y')}. "
                f"Please ensure it is lodged before the deadline."
            )

            # Determine notification type based on urgency
            if days_remaining < 0:
                notification_type = NotificationType.DEADLINE_OVERDUE
            elif days_remaining == 0:
                notification_type = NotificationType.DEADLINE_TODAY
            elif days_remaining == 1:
                notification_type = NotificationType.DEADLINE_TOMORROW
            else:
                notification_type = NotificationType.DEADLINE_APPROACHING

            # Send notification to all practice users
            for user in users:
                try:
                    await notification_service.create_notification(
                        tenant_id=tenant_id,
                        user_id=user.id,
                        notification_type=notification_type,
                        title=title,
                        message=message,
                        entity_type="bas_session",
                        entity_id=bas_session.id,
                        entity_context={
                            "connection_id": str(period.connection_id),
                            "client_name": client_name,
                            "due_date": period.due_date.isoformat(),
                            "period_display_name": period.display_name,
                        },
                    )
                    results["notifications_sent"] += 1
                except Exception as e:
                    logger.error(f"Failed to send notification to user {user.id}: {e}")

            # Log audit event
            try:
                audit_log = BASAuditLog(
                    tenant_id=tenant_id,
                    session_id=bas_session.id,
                    event_type=BASAuditEventType.DEADLINE_NOTIFICATION_SENT.value,
                    event_description=f"Deadline notification sent ({days_remaining} days remaining)",
                    is_system_action=True,
                    event_metadata={
                        "days_remaining": days_remaining,
                        "due_date": period.due_date.isoformat(),
                        "users_notified": len(users),
                    },
                    created_at=datetime.now(UTC),
                )
                self.session.add(audit_log)
            except Exception as e:
                logger.error(f"Failed to create audit log: {e}")

        return results

    async def get_approaching_deadlines_for_user(
        self,
        tenant_id: UUID,
        days_ahead: int = 7,
        reference_date: date | None = None,
    ) -> list[dict]:
        """Get approaching deadlines for display in UI.

        Args:
            tenant_id: The tenant ID
            days_ahead: Number of days to look ahead
            reference_date: Reference date for calculation (defaults to today)

        Returns:
            List of deadline info dicts
        """
        if reference_date is None:
            reference_date = datetime.now(UTC).date()

        sessions = await self.repo.get_sessions_with_approaching_deadlines(
            tenant_id=tenant_id,
            days_ahead=days_ahead,
            reference_date=reference_date,
        )

        deadlines = []
        for bas_session in sessions:
            period = bas_session.period
            days_remaining = (period.due_date - reference_date).days

            # Get client name
            conn_stmt = select(XeroConnection).where(XeroConnection.id == period.connection_id)
            conn_result = await self.session.execute(conn_stmt)
            connection = conn_result.scalar_one_or_none()

            deadlines.append(
                {
                    "session_id": str(bas_session.id),
                    "connection_id": str(period.connection_id),
                    "client_name": connection.organization_name if connection else "Unknown",
                    "period_display_name": period.display_name,
                    "due_date": period.due_date.isoformat(),
                    "days_remaining": days_remaining,
                    "status": bas_session.status,
                }
            )

        return deadlines
