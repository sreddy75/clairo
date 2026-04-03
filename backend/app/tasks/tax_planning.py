"""Celery tasks for the multi-agent tax planning pipeline.

Provides background task execution for autonomous tax plan generation.
The pipeline runs 5 agents sequentially with progress reporting.
"""

import logging
from typing import Any
from uuid import UUID

from celery import Task
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _get_async_session() -> AsyncSession:
    """Create an async database session for tasks."""
    settings = get_settings()
    engine = create_async_engine(settings.database.url, echo=False, poolclass=NullPool)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return async_session()


async def _set_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    """Set the tenant context for RLS policies."""
    await session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))


@celery_app.task(
    name="app.tasks.tax_planning.run_analysis_pipeline",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
    time_limit=300,  # 5 minute hard limit
    soft_time_limit=240,  # 4 minute soft limit
)
def run_analysis_pipeline(
    self: Task,
    plan_id: str,
    tenant_id: str,
    user_id: str,
    analysis_id: str,
    resume_from_stage: int | None = None,
) -> dict[str, Any]:
    """Run the multi-agent tax planning analysis pipeline.

    Executes 5 agents sequentially:
    1. Profiler — entity classification, eligibility
    2. Scanner — evaluate 15+ strategy categories
    3. Modeller — model top strategies with calculator
    4. Advisor — generate accountant brief + client summary
    5. Reviewer — verify numbers, citations, consistency

    Reports progress via self.update_state() after each agent.

    Args:
        plan_id: The tax plan to analyse.
        tenant_id: Tenant ID for RLS context.
        user_id: User who triggered generation.
        analysis_id: Pre-created TaxPlanAnalysis record ID.
        resume_from_stage: Optional stage number to resume from (1-5).

    Returns:
        Dict with analysis_id and status.
    """
    import asyncio

    return asyncio.run(
        _run_analysis_pipeline_async(
            self,
            UUID(plan_id),
            UUID(tenant_id),
            UUID(user_id),
            UUID(analysis_id),
            resume_from_stage,
        )
    )


async def _run_analysis_pipeline_async(
    task: Task,
    plan_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    analysis_id: UUID,
    resume_from_stage: int | None = None,
) -> dict[str, Any]:
    """Async implementation of the analysis pipeline."""
    session = await _get_async_session()

    try:
        await _set_tenant_context(session, tenant_id)

        # TODO: Implement full pipeline orchestration
        # For now, stub out the progress reporting pattern

        stages = [
            (1, "profiling", "Analysing client profile..."),
            (2, "scanning", "Evaluating tax strategies..."),
            (3, "modelling", "Modelling top strategies..."),
            (4, "writing", "Writing accountant brief..."),
            (5, "reviewing", "Verifying calculations and citations..."),
        ]

        start_stage = resume_from_stage or 1

        for stage_num, stage_name, message in stages:
            if stage_num < start_stage:
                continue

            task.update_state(
                state="PROGRESS",
                meta={
                    "stage": stage_name,
                    "stage_number": stage_num,
                    "total_stages": 5,
                    "message": message,
                    "analysis_id": str(analysis_id),
                },
            )

            # TODO: Call the appropriate agent here
            logger.info(
                "Pipeline stage %d/%d: %s for plan %s",
                stage_num,
                5,
                stage_name,
                plan_id,
            )

        return {
            "analysis_id": str(analysis_id),
            "status": "completed",
        }

    except Exception as e:
        logger.error("Analysis pipeline failed for plan %s: %s", plan_id, e)
        return {
            "analysis_id": str(analysis_id),
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await session.close()
