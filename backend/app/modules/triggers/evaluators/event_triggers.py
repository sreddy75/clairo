"""Event-based trigger evaluator."""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.triggers.evaluators.base import BaseTriggerEvaluator
from app.modules.triggers.models import Trigger


class EventTriggerEvaluator(BaseTriggerEvaluator):
    """Evaluator for event-based triggers.

    Evaluates whether an event matches the trigger configuration.

    Supported events:
    - xero_connection_created: New Xero connection established
    - xero_sync_complete: Xero data sync completed
    - bas_lodged: BAS was lodged/recorded
    - action_item_due_soon: Action item approaching deadline

    Config options:
    - event: Event type to match
    - conditions: Optional additional conditions (JSON)
    """

    # Supported event types
    SUPPORTED_EVENTS: ClassVar[set[str]] = {
        "xero_connection_created",
        "xero_sync_complete",
        "bas_lodged",
        "action_item_due_soon",
    }

    def __init__(self, db: AsyncSession):
        super().__init__(db)

    async def should_fire(
        self,
        trigger: Trigger,
        client_id: UUID | None = None,
        **kwargs,
    ) -> bool:
        """Check if the event matches the trigger configuration."""
        config = trigger.config
        expected_event = config.get("event")
        conditions = config.get("conditions", {})

        # Get the actual event from kwargs
        actual_event = kwargs.get("event_type")
        event_payload = kwargs.get("payload", {})

        if not expected_event or not actual_event:
            return False

        # Check event type matches
        if expected_event != actual_event:
            return False

        # Check additional conditions if specified
        if conditions:
            for key, expected_value in conditions.items():
                actual_value = event_payload.get(key)
                if actual_value != expected_value:
                    return False

        return True

    async def get_matching_clients(
        self,
        trigger: Trigger,
        tenant_id: UUID,
    ) -> list[UUID]:
        """Get clients affected by the event.

        For event triggers, this is typically called with a specific
        client_id in kwargs, so this returns that client.
        """
        # Event triggers are typically fired for a specific client
        # The client ID should come from the event payload
        return []

    async def get_triggers_for_event(
        self,
        tenant_id: UUID,
        event_type: str,
    ) -> list[Trigger]:
        """Find all triggers that match an event type."""
        from app.modules.triggers.models import TriggerStatus, TriggerType

        result = await self.db.execute(
            select(Trigger)
            .where(Trigger.tenant_id == tenant_id)
            .where(Trigger.trigger_type == TriggerType.EVENT_BASED)
            .where(Trigger.status == TriggerStatus.ACTIVE)
        )
        triggers = list(result.scalars().all())

        # Filter to triggers that match this event
        matching = []
        for trigger in triggers:
            if trigger.config.get("event") == event_type:
                matching.append(trigger)

        return matching

    @classmethod
    def is_valid_event(cls, event_type: str) -> bool:
        """Check if an event type is supported."""
        return event_type in cls.SUPPORTED_EVENTS
