"""Service layer for the tax_strategies module (Spec 060).

Owns the lifecycle state machine, seed action, and stage-trigger
orchestration. All TaxStrategy.status mutations go through
_transition_status — centralised chokepoint guarantees state-machine
validity and audit emission (constitution §X).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditService
from app.modules.tax_strategies import audit_events as events
from app.modules.tax_strategies.exceptions import InvalidStatusTransitionError
from app.modules.tax_strategies.models import TaxStrategy
from app.modules.tax_strategies.repository import TaxStrategyRepository

logger = logging.getLogger(__name__)


# Allowed (from, to) state transitions — data-model §1.2.
# Any transition not listed is rejected by _transition_status.
_ALLOWED_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("stub", "researching"),
        ("researching", "drafted"),
        ("drafted", "enriched"),
        ("enriched", "in_review"),
        # Research/draft/enrich may be re-run on an already-enriched strategy
        # (e.g., reject from in_review → drafted then re-draft).
        ("enriched", "researching"),
        ("enriched", "drafted"),
        ("in_review", "approved"),
        ("in_review", "drafted"),  # reject path
        ("approved", "published"),
        ("published", "superseded"),
        # Archive is a manual kill-switch allowed from any non-terminal state.
        ("stub", "archived"),
        ("researching", "archived"),
        ("drafted", "archived"),
        ("enriched", "archived"),
        ("in_review", "archived"),
        ("approved", "archived"),
        ("published", "archived"),
    }
)


class TaxStrategyService:
    """Orchestrates tax strategy lifecycle, seeding, and stage triggers.

    _transition_status is the SINGLE chokepoint for status mutations. No
    other code path should write TaxStrategy.status directly.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = TaxStrategyRepository(session)

    async def _transition_status(
        self,
        strategy: TaxStrategy,
        new_status: str,
        *,
        actor_clerk_user_id: str,
        actor_user_id: UUID | None = None,
        tenant_id: UUID | None = None,
        reviewer_display_name: str | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> TaxStrategy:
        """Validate state-machine edge, update status, emit audit events.

        On in_review → approved, captures reviewer identity on the row.
        On approved → published, emits the dedicated .published event with
        chunk-count metadata (caller passes via extra_metadata).
        On published → superseded, emits .superseded event.
        """
        old_status = strategy.status
        if old_status == new_status:
            return strategy
        if (old_status, new_status) not in _ALLOWED_TRANSITIONS:
            raise InvalidStatusTransitionError(
                strategy.strategy_id, old_status, new_status
            )

        now = datetime.now(UTC)
        is_approval = old_status == "in_review" and new_status == "approved"

        await self.repo.update_status(
            strategy,
            new_status=new_status,
            reviewer_clerk_user_id=actor_clerk_user_id if is_approval else None,
            reviewer_display_name=reviewer_display_name if is_approval else None,
            last_reviewed_at=now if is_approval else None,
        )

        audit = AuditService(self.session)
        common_metadata: dict[str, Any] = {
            "strategy_id": strategy.strategy_id,
            "version": strategy.version,
            "from_status": old_status,
            "to_status": new_status,
            "actor_clerk_user_id": actor_clerk_user_id,
        }
        if extra_metadata:
            common_metadata.update(extra_metadata)

        # Always emit the generic status_changed event.
        await audit.log_event(
            event_type=events.TAX_STRATEGY_STATUS_CHANGED,
            event_category="data",
            actor_type="user",
            actor_id=actor_user_id,
            tenant_id=tenant_id,
            resource_type="tax_strategy",
            resource_id=strategy.id,
            action="update",
            outcome="success",
            old_values={"status": old_status},
            new_values={"status": new_status},
            metadata=common_metadata,
        )

        # Additional per-event emissions for high-consequence transitions.
        if is_approval:
            await audit.log_event(
                event_type=events.TAX_STRATEGY_APPROVED,
                event_category="compliance",
                actor_type="user",
                actor_id=actor_user_id,
                tenant_id=tenant_id,
                resource_type="tax_strategy",
                resource_id=strategy.id,
                action="update",
                outcome="success",
                new_values={
                    "reviewer_clerk_user_id": actor_clerk_user_id,
                    "reviewer_display_name": reviewer_display_name,
                },
                metadata=common_metadata,
            )
        elif old_status == "approved" and new_status == "published":
            await audit.log_event(
                event_type=events.TAX_STRATEGY_PUBLISHED,
                event_category="compliance",
                actor_type="user",
                actor_id=actor_user_id,
                tenant_id=tenant_id,
                resource_type="tax_strategy",
                resource_id=strategy.id,
                action="update",
                outcome="success",
                metadata=common_metadata,
            )
        elif old_status == "published" and new_status == "superseded":
            await audit.log_event(
                event_type=events.TAX_STRATEGY_SUPERSEDED,
                event_category="data",
                actor_type="user",
                actor_id=actor_user_id,
                tenant_id=tenant_id,
                resource_type="tax_strategy",
                resource_id=strategy.id,
                action="update",
                outcome="success",
                metadata=common_metadata,
            )

        logger.info(
            "tax_strategy %s transitioned %s → %s",
            strategy.strategy_id,
            old_status,
            new_status,
        )
        return strategy
