"""Celery tasks for quality scoring."""

import logging
from uuid import UUID

from app.database import get_session_factory
from app.modules.quality.service import QualityService, get_current_quarter
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Number of quarters to calculate (covers full financial year + current)
NUM_QUARTERS_TO_CALCULATE = 6


def _get_previous_quarter(quarter: int, fy_year: int) -> tuple[int, int]:
    """Get the previous quarter and financial year."""
    if quarter == 1:
        return 4, fy_year - 1
    return quarter - 1, fy_year


def _get_quarters_to_calculate(
    num_quarters: int = NUM_QUARTERS_TO_CALCULATE,
) -> list[tuple[int, int]]:
    """Get list of quarters to calculate, starting from current going back.

    Args:
        num_quarters: Number of quarters to include.

    Returns:
        List of (quarter, fy_year) tuples.
    """
    quarters = []
    curr_quarter, curr_fy_year = get_current_quarter()

    q, fy = curr_quarter, curr_fy_year
    for _ in range(num_quarters):
        quarters.append((q, fy))
        q, fy = _get_previous_quarter(q, fy)

    return quarters


@celery_app.task(
    name="app.tasks.quality.calculate_quality_score",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def calculate_quality_score(
    self,
    connection_id: str,
    quarter: int | None = None,
    fy_year: int | None = None,
    trigger_reason: str = "sync",
    post_sync_task_id: str | None = None,
) -> dict:
    """Calculate quality score for a connection.

    This task is triggered after a Xero sync completes.

    When triggered by sync (no specific quarter), calculates for BOTH:
    - Current quarter (most relevant for upcoming BAS)
    - Previous quarter (accountants often still working on this)

    Args:
        connection_id: UUID of the connection.
        quarter: Quarter number (1-4). If None, calculates current + previous.
        fy_year: Financial year. If None, uses current.
        trigger_reason: Why the calculation was triggered.
        post_sync_task_id: Optional PostSyncTask ID for status tracking (Spec 043).

    Returns:
        Dict with calculation results.
    """
    import asyncio

    async def _calculate():
        # Track post-sync task status (Spec 043 — T036)
        if post_sync_task_id:
            from app.tasks.xero import _update_post_sync_task_status

            await _update_post_sync_task_status(post_sync_task_id, "in_progress")

        session_factory = get_session_factory()
        async with session_factory() as session:
            try:
                service = QualityService(session)
                results = []

                # If specific quarter requested, calculate only that
                if quarter is not None and fy_year is not None:
                    result = await service.calculate_quality(
                        connection_id=UUID(connection_id),
                        quarter=quarter,
                        fy_year=fy_year,
                        trigger_reason=trigger_reason,
                    )
                    results.append(
                        {
                            "quarter": quarter,
                            "fy_year": fy_year,
                            "overall_score": float(result.overall_score),
                            "issues_found": result.issues_found,
                        }
                    )
                else:
                    # Calculate for last N quarters (covers full FY + buffer)
                    quarters_to_calc = _get_quarters_to_calculate()

                    for q, fy in quarters_to_calc:
                        try:
                            result = await service.calculate_quality(
                                connection_id=UUID(connection_id),
                                quarter=q,
                                fy_year=fy,
                                trigger_reason=trigger_reason,
                            )
                            results.append(
                                {
                                    "quarter": q,
                                    "fy_year": fy,
                                    "overall_score": float(result.overall_score),
                                    "issues_found": result.issues_found,
                                }
                            )
                            logger.info(
                                f"Quality calculated for {connection_id} Q{q} FY{fy}: "
                                f"score={result.overall_score}%"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to calculate quality for {connection_id} Q{q} FY{fy}: {e}"
                            )

                task_result = {
                    "connection_id": connection_id,
                    "quarters_calculated": len(results),
                    "results": results,
                }

                # Mark post-sync task as completed (Spec 043 — T036)
                if post_sync_task_id:
                    from app.tasks.xero import _update_post_sync_task_status

                    await _update_post_sync_task_status(
                        post_sync_task_id,
                        "completed",
                        result_summary={
                            "quarters_calculated": len(results),
                        },
                    )

                return task_result

            except Exception as e:
                logger.error(f"Quality calculation failed for {connection_id}: {e}")
                # Mark post-sync task as failed (Spec 043 — T036)
                if post_sync_task_id:
                    from app.tasks.xero import _update_post_sync_task_status

                    await _update_post_sync_task_status(
                        post_sync_task_id,
                        "failed",
                        error_message=str(e),
                    )
                raise

    # Run the async function
    return asyncio.run(_calculate())
