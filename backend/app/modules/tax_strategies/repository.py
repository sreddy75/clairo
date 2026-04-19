"""Repository layer for the tax_strategies module (Spec 060).

All DB access goes through this class. Service layer never queries models
directly (constitution §III).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tax_strategies.models import TaxStrategy, TaxStrategyAuthoringJob


class TaxStrategyRepository:
    """Data access for TaxStrategy and TaxStrategyAuthoringJob.

    Methods use session.flush() not session.commit() — session lifecycle
    is managed by the caller per project convention.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --------------------------------------------------------------
    # TaxStrategy
    # --------------------------------------------------------------

    async def create(self, data: dict[str, Any]) -> TaxStrategy:
        strategy = TaxStrategy(**data)
        self.session.add(strategy)
        await self.session.flush()
        return strategy

    async def get_by_id(self, id_: UUID) -> TaxStrategy | None:
        return await self.session.get(TaxStrategy, id_)

    async def get_live_version(self, strategy_id: str) -> TaxStrategy | None:
        """Return the current (non-superseded) row for a Clairo identifier.

        The partial unique index uq_tax_strategies_strategy_id_live guarantees
        at most one such row per identifier.
        """
        stmt = select(TaxStrategy).where(
            TaxStrategy.strategy_id == strategy_id,
            TaxStrategy.superseded_by_strategy_id.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_live_versions(self, strategy_ids: Sequence[str]) -> list[TaxStrategy]:
        """Batch fetch live rows for the given identifiers.

        Used by the two-pass retrieval parent-fetch step (FR-018).
        """
        if not strategy_ids:
            return []
        stmt = select(TaxStrategy).where(
            TaxStrategy.strategy_id.in_(list(strategy_ids)),
            TaxStrategy.superseded_by_strategy_id.is_(None),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_versions(self, strategy_id: str) -> list[TaxStrategy]:
        """Return every row for the Clairo identifier, newest version first."""
        stmt = (
            select(TaxStrategy)
            .where(TaxStrategy.strategy_id == strategy_id)
            .order_by(TaxStrategy.version.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def exists_by_strategy_id(self, strategy_id: str) -> bool:
        """Used by seed idempotency check."""
        stmt = select(TaxStrategy.id).where(TaxStrategy.strategy_id == strategy_id).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def list_with_filters(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        tenant_id: str | None = None,
        query: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[TaxStrategy], int]:
        """List endpoint backing query. Returns (rows, total_count)."""
        stmt = select(TaxStrategy)
        count_stmt = select(func.count()).select_from(TaxStrategy)

        if status is not None:
            stmt = stmt.where(TaxStrategy.status == status)
            count_stmt = count_stmt.where(TaxStrategy.status == status)
        if tenant_id is not None:
            stmt = stmt.where(TaxStrategy.tenant_id == tenant_id)
            count_stmt = count_stmt.where(TaxStrategy.tenant_id == tenant_id)
        if category is not None:
            stmt = stmt.where(TaxStrategy.categories.any(category))
            count_stmt = count_stmt.where(TaxStrategy.categories.any(category))
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(
                TaxStrategy.name.ilike(pattern) | TaxStrategy.strategy_id.ilike(pattern)
            )
            count_stmt = count_stmt.where(
                TaxStrategy.name.ilike(pattern) | TaxStrategy.strategy_id.ilike(pattern)
            )

        stmt = stmt.order_by(TaxStrategy.strategy_id).offset(offset).limit(limit)

        rows_result = await self.session.execute(stmt)
        total_result = await self.session.execute(count_stmt)
        return list(rows_result.scalars().all()), int(total_result.scalar_one())

    async def count_by_status(self) -> dict[str, int]:
        """Pipeline dashboard aggregation."""
        stmt = select(TaxStrategy.status, func.count(TaxStrategy.id)).group_by(
            TaxStrategy.status
        )
        result = await self.session.execute(stmt)
        return {row[0]: int(row[1]) for row in result.all()}

    async def update_status(
        self,
        strategy: TaxStrategy,
        *,
        new_status: str,
        reviewer_clerk_user_id: str | None = None,
        reviewer_display_name: str | None = None,
        last_reviewed_at: datetime | None = None,
    ) -> TaxStrategy:
        """Low-level mutation helper. Callers should go through
        TaxStrategyService._transition_status — not this method directly —
        so the state machine and audit events stay consistent.
        """
        strategy.status = new_status
        if reviewer_clerk_user_id is not None:
            strategy.reviewer_clerk_user_id = reviewer_clerk_user_id
        if reviewer_display_name is not None:
            strategy.reviewer_display_name = reviewer_display_name
        if last_reviewed_at is not None:
            strategy.last_reviewed_at = last_reviewed_at
        await self.session.flush()
        return strategy

    # --------------------------------------------------------------
    # TaxStrategyAuthoringJob
    # --------------------------------------------------------------

    async def create_job(
        self,
        *,
        strategy_id: str,
        stage: str,
        triggered_by: str,
        input_payload: dict | None = None,
    ) -> TaxStrategyAuthoringJob:
        job = TaxStrategyAuthoringJob(
            strategy_id=strategy_id,
            stage=stage,
            triggered_by=triggered_by,
            input_payload=input_payload or {},
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_job(self, job_id: UUID) -> TaxStrategyAuthoringJob | None:
        return await self.session.get(TaxStrategyAuthoringJob, job_id)

    async def list_jobs_for_strategy(
        self, strategy_id: str
    ) -> list[TaxStrategyAuthoringJob]:
        stmt = (
            select(TaxStrategyAuthoringJob)
            .where(TaxStrategyAuthoringJob.strategy_id == strategy_id)
            .order_by(TaxStrategyAuthoringJob.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_job(
        self,
        job: TaxStrategyAuthoringJob,
        *,
        status: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        output_payload: dict | None = None,
        error: str | None = None,
    ) -> TaxStrategyAuthoringJob:
        if status is not None:
            job.status = status
        if started_at is not None:
            job.started_at = started_at
        if completed_at is not None:
            job.completed_at = completed_at
        if output_payload is not None:
            job.output_payload = output_payload
        if error is not None:
            job.error = error
        await self.session.flush()
        return job
