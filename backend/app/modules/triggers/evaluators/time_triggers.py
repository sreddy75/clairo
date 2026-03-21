"""Time-based trigger evaluator."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.triggers.evaluators.base import BaseTriggerEvaluator
from app.modules.triggers.models import Trigger


class TimeScheduleEvaluator(BaseTriggerEvaluator):
    """Evaluator for time-scheduled triggers.

    Evaluates whether a trigger should fire based on cron expressions
    and optional deadline-based conditions.

    Config options:
    - cron: Cron expression (e.g., "0 6 * * *" for 6am daily)
    - timezone: Timezone for the schedule (default: Australia/Sydney)
    - days_before_deadline: For BAS deadline triggers, days before deadline
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db)

    async def should_fire(
        self,
        trigger: Trigger,
        client_id: UUID | None = None,
        **kwargs,
    ) -> bool:
        """Check if the schedule indicates the trigger should fire now.

        This is typically called by Celery Beat at the scheduled time,
        so we just verify the cron matches the current time window.
        """
        config = trigger.config
        cron_expr = config.get("cron")
        timezone_str = config.get("timezone", "Australia/Sydney")

        if not cron_expr:
            return False

        try:
            tz = ZoneInfo(timezone_str)
            now = datetime.now(tz)

            # Check if we're within the execution window
            # (within 5 minutes of the scheduled time)
            cron = croniter(cron_expr, now - timedelta(minutes=5))
            next_run = cron.get_next(datetime)

            # If next run is within the next 10 minutes, we're in the window
            return next_run <= now + timedelta(minutes=5)

        except Exception:
            return False

    async def get_matching_clients(
        self,
        trigger: Trigger,
        tenant_id: UUID,
    ) -> list[UUID]:
        """Get all clients for time-based trigger.

        For most time triggers, all active clients are included.
        For deadline triggers, only clients with upcoming deadlines.
        """
        config = trigger.config
        days_before_deadline = config.get("days_before_deadline")

        # Import here to avoid circular imports
        from app.modules.integrations.xero.models import XeroConnection

        if days_before_deadline:
            # Filter to clients with upcoming BAS deadlines
            return await self._get_clients_with_upcoming_deadline(tenant_id, days_before_deadline)

        # Default: all active clients
        result = await self.db.execute(
            select(XeroConnection.id)
            .where(XeroConnection.tenant_id == tenant_id)
            .where(XeroConnection.is_active.is_(True))
        )
        return [row[0] for row in result.all()]

    async def _get_clients_with_upcoming_deadline(
        self,
        tenant_id: UUID,
        days_before: int,
    ) -> list[UUID]:
        """Get clients with BAS deadlines within the specified days."""
        # Import here to avoid circular imports
        from app.modules.bas.models import BASSession

        deadline_date = datetime.now().date() + timedelta(days=days_before)

        # Find active BAS sessions with deadlines approaching
        result = await self.db.execute(
            select(BASSession.connection_id)
            .where(BASSession.tenant_id == tenant_id)
            .where(BASSession.lodgement_deadline <= deadline_date)
            .where(BASSession.lodgement_deadline >= datetime.now().date())
            .where(BASSession.status.in_(["draft", "in_progress", "pending_review"]))
            .distinct()
        )
        return [row[0] for row in result.all()]

    def get_next_run_time(
        self,
        trigger: Trigger,
        after: datetime | None = None,
    ) -> datetime | None:
        """Calculate the next run time for a trigger."""
        config = trigger.config
        cron_expr = config.get("cron")
        timezone_str = config.get("timezone", "Australia/Sydney")

        if not cron_expr:
            return None

        try:
            tz = ZoneInfo(timezone_str)
            base_time = after or datetime.now(tz)
            cron = croniter(cron_expr, base_time)
            return cron.get_next(datetime)
        except Exception:
            return None
