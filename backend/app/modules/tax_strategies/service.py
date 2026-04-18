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
from app.modules.tax_strategies.exceptions import (
    InvalidStatusTransitionError,
    StrategyNotFoundError,
)
from app.modules.tax_strategies.models import TaxStrategy, TaxStrategyAuthoringJob
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

    # -----------------------------------------------------------------
    # Stage triggers (T029)
    # -----------------------------------------------------------------
    # research/draft/enrich queue Celery tasks; submit/approve/reject
    # apply transitions synchronously. approve_and_publish transitions
    # to 'approved' and then queues the publish task — the publish
    # task itself performs the approved → published transition on
    # success.

    async def trigger_stage(
        self,
        strategy_id: str,
        stage: str,
        actor_clerk_user_id: str,
    ) -> TaxStrategyAuthoringJob:
        """Queue a Celery task for the given pipeline stage.

        stage ∈ {'research', 'draft', 'enrich', 'publish'}. The corresponding
        async status transition is the task's responsibility — this method
        only creates the job row and dispatches the task.
        """
        strategy = await self._load_strategy(strategy_id)
        self._validate_stage_precondition(strategy.status, stage)

        job = await self.repo.create_job(
            strategy_id=strategy_id,
            stage=stage,
            triggered_by=actor_clerk_user_id,
            input_payload={"version": strategy.version},
        )
        _dispatch_stage_task(stage, strategy_id, actor_clerk_user_id)
        return job

    async def submit_for_review(
        self,
        strategy_id: str,
        actor_clerk_user_id: str,
        actor_user_id: UUID | None = None,
        tenant_id: UUID | None = None,
    ) -> TaxStrategy:
        """Transition enriched → in_review."""
        strategy = await self._load_strategy(strategy_id)
        return await self._transition_status(
            strategy,
            new_status="in_review",
            actor_clerk_user_id=actor_clerk_user_id,
            actor_user_id=actor_user_id,
            tenant_id=tenant_id,
        )

    async def approve(
        self,
        strategy_id: str,
        actor_clerk_user_id: str,
        reviewer_display_name: str,
        actor_user_id: UUID | None = None,
        tenant_id: UUID | None = None,
    ) -> tuple[TaxStrategy, TaxStrategyAuthoringJob]:
        """Transition in_review → approved and queue the publish task.

        Returns the updated strategy and the queued authoring job row.
        """
        strategy = await self._load_strategy(strategy_id)
        strategy = await self._transition_status(
            strategy,
            new_status="approved",
            actor_clerk_user_id=actor_clerk_user_id,
            actor_user_id=actor_user_id,
            tenant_id=tenant_id,
            reviewer_display_name=reviewer_display_name,
        )
        job = await self.repo.create_job(
            strategy_id=strategy_id,
            stage="publish",
            triggered_by=actor_clerk_user_id,
            input_payload={"version": strategy.version},
        )
        _dispatch_stage_task("publish", strategy_id, actor_clerk_user_id)
        return strategy, job

    async def reject(
        self,
        strategy_id: str,
        actor_clerk_user_id: str,
        reviewer_notes: str,
        actor_user_id: UUID | None = None,
        tenant_id: UUID | None = None,
    ) -> TaxStrategy:
        """Transition in_review → drafted (with reviewer notes)."""
        strategy = await self._load_strategy(strategy_id)
        return await self._transition_status(
            strategy,
            new_status="drafted",
            actor_clerk_user_id=actor_clerk_user_id,
            actor_user_id=actor_user_id,
            tenant_id=tenant_id,
            extra_metadata={"reviewer_notes": reviewer_notes},
        )

    async def _load_strategy(self, strategy_id: str) -> TaxStrategy:
        strategy = await self.repo.get_live_version(strategy_id)
        if strategy is None:
            raise StrategyNotFoundError(strategy_id)
        return strategy

    @staticmethod
    def _validate_stage_precondition(current_status: str, stage: str) -> None:
        """Reject stage triggers when the current status doesn't allow them."""
        allowed: dict[str, frozenset[str]] = {
            "research": frozenset({"stub", "enriched", "drafted"}),
            "draft": frozenset({"researching", "enriched"}),
            "enrich": frozenset({"drafted"}),
            "publish": frozenset({"approved"}),
        }
        expected = allowed.get(stage)
        if expected is None:
            raise ValueError(f"Unknown stage {stage!r}")
        if current_status not in expected:
            # Uses the transition-error type so API layer can 409 consistently
            # even though this isn't a direct status write.
            raise InvalidStatusTransitionError(
                strategy_id="(stage-precondition)",
                from_status=current_status,
                to_status=f"stage:{stage}",
            )


def _dispatch_stage_task(
    stage: str, strategy_id: str, actor_clerk_user_id: str
) -> None:
    """Queue the Celery task for the given stage.

    Import locally to avoid a circular dependency (tasks module imports
    service indirectly via models.py registration).
    """
    from app.tasks.tax_strategy_authoring import (
        draft_strategy,
        enrich_strategy,
        publish_strategy,
        research_strategy,
    )

    dispatch_map = {
        "research": research_strategy,
        "draft": draft_strategy,
        "enrich": enrich_strategy,
        "publish": publish_strategy,
    }
    task = dispatch_map[stage]
    task.apply_async(args=[strategy_id, actor_clerk_user_id])
