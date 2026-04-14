"""Celery tasks for the multi-agent tax planning pipeline.

Provides background task execution for autonomous tax plan generation
and automatic financial data refresh on Xero reconnection.
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
    from app.modules.tax_planning.agents.orchestrator import AnalysisPipelineOrchestrator

    settings = get_settings()
    session = await _get_async_session()

    try:
        await _set_tenant_context(session, tenant_id)

        def on_progress(stage: str, stage_number: int, message: str) -> None:
            task.update_state(
                state="PROGRESS",
                meta={
                    "stage": stage,
                    "stage_number": stage_number,
                    "total_stages": 5,
                    "message": message,
                    "analysis_id": str(analysis_id),
                },
            )

        orchestrator = AnalysisPipelineOrchestrator(session, settings)
        result_id = await orchestrator.run(
            plan_id=plan_id,
            tenant_id=tenant_id,
            analysis_id=analysis_id,
            on_progress=on_progress,
        )

        return {
            "analysis_id": str(result_id),
            "status": "completed",
        }

    except Exception as e:
        logger.error("Analysis pipeline failed for plan %s: %s", plan_id, e, exc_info=True)
        return {
            "analysis_id": str(analysis_id),
            "status": "failed",
            "error_message": str(e),
        }

    finally:
        await session.close()


@celery_app.task(
    name="app.tasks.tax_planning.refresh_connection_tax_plans",
    bind=True,
    max_retries=1,
    default_retry_delay=10,
    time_limit=60,
    soft_time_limit=45,
)
def refresh_connection_tax_plans(
    self: Task,
    connection_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    """Refresh Tax Plan financials after a Xero connection is re-activated.

    Finds all active (draft/in_progress) Tax Plans for this connection and
    pulls fresh P&L data from Xero. Dispatched automatically when a
    connection transitions from needs_reauth to active.
    """
    import asyncio

    return asyncio.run(_refresh_connection_tax_plans_async(UUID(connection_id), UUID(tenant_id)))


async def _refresh_connection_tax_plans_async(
    connection_id: UUID,
    tenant_id: UUID,
) -> dict[str, Any]:
    """Async implementation of connection tax plan refresh."""
    from app.modules.tax_planning.repository import TaxPlanRepository
    from app.modules.tax_planning.service import TaxPlanningService

    settings = get_settings()
    session = await _get_async_session()

    refreshed: list[str] = []
    failed: list[str] = []

    try:
        await _set_tenant_context(session, tenant_id)

        repo = TaxPlanRepository(session)
        plans = await repo.list_by_connection(connection_id, tenant_id)

        # Only refresh plans that have missing or stale data
        plans_to_refresh = [p for p in plans if not p.financials_data or p.data_source == "xero"]

        if not plans_to_refresh:
            return {"refreshed": [], "skipped": len(plans), "failed": []}

        service = TaxPlanningService(session, settings)
        for plan in plans_to_refresh:
            try:
                await service.pull_xero_financials(plan.id, tenant_id, force_refresh=True)
                await session.commit()
                refreshed.append(str(plan.id))
                logger.info("Auto-refreshed tax plan %s after Xero reconnection", plan.id)
            except Exception:
                await session.rollback()
                await _set_tenant_context(session, tenant_id)
                failed.append(str(plan.id))
                logger.warning(
                    "Failed to auto-refresh tax plan %s after Xero reconnection",
                    plan.id,
                    exc_info=True,
                )

        return {"refreshed": refreshed, "failed": failed}

    except Exception as e:
        logger.error(
            "Connection tax plan refresh failed for connection %s: %s",
            connection_id,
            e,
            exc_info=True,
        )
        return {"refreshed": refreshed, "failed": failed, "error": str(e)}

    finally:
        await session.close()
