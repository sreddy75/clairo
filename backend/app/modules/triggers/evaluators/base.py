"""Base class for trigger evaluators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.triggers.models import Trigger


class BaseTriggerEvaluator(ABC):
    """Base class for all trigger evaluators.

    Evaluators determine whether a trigger should fire based on
    its configuration and current conditions.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    @abstractmethod
    async def should_fire(
        self,
        trigger: Trigger,
        client_id: UUID | None = None,
        **kwargs,
    ) -> bool:
        """Determine if the trigger should fire.

        Args:
            trigger: The trigger configuration
            client_id: Optional client ID for data triggers
            **kwargs: Additional context (e.g., event payload)

        Returns:
            True if the trigger should fire, False otherwise
        """
        pass

    @abstractmethod
    async def get_matching_clients(
        self,
        trigger: Trigger,
        tenant_id: UUID,
    ) -> list[UUID]:
        """Get all clients that match the trigger conditions.

        Args:
            trigger: The trigger configuration
            tenant_id: The tenant ID to scope the query

        Returns:
            List of client IDs that match the trigger conditions
        """
        pass
