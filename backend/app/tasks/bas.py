"""Celery tasks for BAS operations.

Provides background tasks for:
- Auto-calculating BAS for recent quarters after sync
- Creating BAS periods if they don't exist
- Checking and sending deadline notifications (Spec 011)
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.modules.auth.models import PracticeUser
from app.modules.bas.service import BASService
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Default number of quarters to calculate
DEFAULT_QUARTERS_TO_CALCULATE = 6


async def _get_async_session() -> AsyncSession:
    """Create an async database session for tasks.

    Uses NullPool to avoid connection leaks in Celery's asyncio.run() context.
    """
    settings = get_settings()
    engine = create_async_engine(settings.database.url, echo=False, poolclass=NullPool)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return async_session()


async def _set_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    """Set the tenant context for RLS policies.

    Uses session-scoped SET (not SET LOCAL) so tenant context persists
    across multiple commits within the same Celery task.
    """
    await session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))


def _get_recent_quarters(num_quarters: int = 6) -> list[tuple[int, int]]:
    """Get the most recent quarters (quarter, fy_year).

    Australian financial year: July 1 - June 30
    Q1: Jul-Sep, Q2: Oct-Dec, Q3: Jan-Mar, Q4: Apr-Jun

    Args:
        num_quarters: Number of quarters to return

    Returns:
        List of (quarter, fy_year) tuples, most recent first
    """
    today = datetime.now(UTC).date()
    month = today.month
    year = today.year

    # Determine current quarter and FY year
    if month >= 7 and month <= 9:
        current_quarter = 1
        current_fy = year + 1  # FY2026 starts July 2025
    elif month >= 10 and month <= 12:
        current_quarter = 2
        current_fy = year + 1
    elif month >= 1 and month <= 3:
        current_quarter = 3
        current_fy = year
    else:  # Apr-Jun
        current_quarter = 4
        current_fy = year

    quarters = []
    q = current_quarter
    fy = current_fy

    for _ in range(num_quarters):
        quarters.append((q, fy))
        # Go back one quarter
        q -= 1
        if q < 1:
            q = 4
            fy -= 1

    return quarters


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.bas.calculate_bas_periods",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def calculate_bas_periods(
    self,
    connection_id: str,
    tenant_id: str,
    num_quarters: int = DEFAULT_QUARTERS_TO_CALCULATE,
    trigger_reason: str = "manual",
    post_sync_task_id: str | None = None,
) -> dict[str, Any]:
    """Calculate BAS for recent quarters.

    Creates BAS periods and sessions if they don't exist, then triggers
    calculations for each quarter.

    Args:
        connection_id: Xero connection ID
        tenant_id: Tenant ID for RLS context
        num_quarters: Number of recent quarters to calculate (default 6)
        trigger_reason: Why this calculation was triggered (sync, manual, scheduled)
        post_sync_task_id: Optional PostSyncTask ID for status tracking (Spec 043).

    Returns:
        Dict with calculation results for each quarter
    """
    import asyncio

    return asyncio.run(
        _calculate_bas_periods_async(
            UUID(connection_id),
            UUID(tenant_id),
            num_quarters,
            trigger_reason,
            post_sync_task_id,
        )
    )


async def _get_first_practice_user(session: AsyncSession, tenant_id: UUID) -> UUID | None:
    """Get the first practice user for a tenant to use for auto-created sessions."""
    result = await session.execute(
        select(PracticeUser.id)
        .where(PracticeUser.tenant_id == tenant_id)
        .order_by(PracticeUser.created_at)
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row


async def _calculate_bas_periods_async(
    connection_id: UUID,
    tenant_id: UUID,
    num_quarters: int,
    trigger_reason: str,
    post_sync_task_id: str | None = None,
) -> dict[str, Any]:
    """Async implementation of BAS period calculation."""
    # Track post-sync task status (Spec 043 — T036)
    if post_sync_task_id:
        from app.tasks.xero import _update_post_sync_task_status

        await _update_post_sync_task_status(post_sync_task_id, "in_progress")

    session = await _get_async_session()

    try:
        await _set_tenant_context(session, tenant_id)

        bas_service = BASService(session)
        quarters = _get_recent_quarters(num_quarters)

        # Get first practice user for auto-creating sessions
        auto_user_id = await _get_first_practice_user(session, tenant_id)
        if not auto_user_id:
            logger.warning(
                f"No practice user found for tenant {tenant_id}, cannot auto-create sessions"
            )

        results: dict[str, Any] = {
            "connection_id": str(connection_id),
            "trigger_reason": trigger_reason,
            "quarters_processed": 0,
            "quarters_calculated": 0,
            "quarters_created": 0,
            "quarters_failed": 0,
            "details": [],
        }

        for quarter, fy_year in quarters:
            quarter_result = {
                "quarter": quarter,
                "fy_year": fy_year,
                "status": "pending",
            }

            try:
                # Get or create period
                period = await bas_service.get_or_create_period(
                    connection_id=connection_id,
                    quarter=quarter,
                    fy_year=fy_year,
                    tenant_id=tenant_id,
                )
                quarter_result["period_id"] = str(period.id)

                # Get or create session for this period
                # Check if a session already exists
                sessions_response = await bas_service.list_sessions(connection_id, limit=100)
                existing_session = None
                for s in sessions_response.sessions:
                    if str(s.period_id) == str(period.id):
                        existing_session = s
                        break

                if existing_session:
                    bas_session = existing_session
                    quarter_result["session_id"] = str(bas_session.id)
                    quarter_result["session_existed"] = True
                else:
                    # Auto-create session if we have a user ID
                    if not auto_user_id:
                        quarter_result["status"] = "skipped"
                        quarter_result["reason"] = "no_practice_user"
                        results["details"].append(quarter_result)
                        results["quarters_processed"] += 1
                        continue

                    # Create new session (auto-created by system)
                    bas_session = await bas_service.create_session(
                        connection_id=connection_id,
                        quarter=quarter,
                        fy_year=fy_year,
                        user_id=auto_user_id,
                        tenant_id=tenant_id,
                        auto_created=True,
                    )
                    quarter_result["session_id"] = str(bas_session.id)
                    quarter_result["session_created"] = True
                    results["quarters_created"] += 1
                    logger.info(f"Auto-created BAS session for Q{quarter} FY{fy_year}")

                # Skip auto-calculation if session has been reviewed by accountant
                # Reviewed sessions can only be recalculated manually from the UI
                if bas_session.reviewed_by:
                    quarter_result["status"] = "skipped"
                    quarter_result["reason"] = "already_reviewed"
                    logger.info(f"Skipping Q{quarter} FY{fy_year} - already reviewed by accountant")
                # Only calculate if session is in draft or in_progress status
                elif bas_session.status in ("draft", "in_progress"):
                    # Trigger calculation
                    calc_result = await bas_service.calculate(
                        session_id=bas_session.id,
                        tenant_id=tenant_id,
                    )

                    quarter_result["status"] = "calculated"
                    quarter_result["gst_payable"] = str(calc_result.gst.gst_payable)
                    quarter_result["total_payable"] = str(calc_result.total_payable)
                    results["quarters_calculated"] += 1
                else:
                    quarter_result["status"] = "skipped"
                    quarter_result["reason"] = f"session_status_{bas_session.status}"

                results["quarters_processed"] += 1

            except Exception as e:
                logger.error(f"Failed to calculate BAS for Q{quarter} FY{fy_year}: {e}")
                quarter_result["status"] = "failed"
                quarter_result["error"] = str(e)
                results["quarters_failed"] += 1
                results["quarters_processed"] += 1

            results["details"].append(quarter_result)

        await session.commit()

        logger.info(
            f"BAS calculation completed for connection {connection_id}: "
            f"{results['quarters_created']} created, {results['quarters_calculated']}/{results['quarters_processed']} calculated"
        )

        # Mark post-sync task as completed (Spec 043 — T036)
        if post_sync_task_id:
            from app.tasks.xero import _update_post_sync_task_status

            await _update_post_sync_task_status(
                post_sync_task_id,
                "completed",
                result_summary={
                    "quarters_calculated": results["quarters_calculated"],
                    "quarters_created": results["quarters_created"],
                    "quarters_failed": results["quarters_failed"],
                },
            )

        return results

    except Exception as e:
        logger.error(f"BAS calculation task failed: {e}")
        # Mark post-sync task as failed (Spec 043 — T036)
        if post_sync_task_id:
            from app.tasks.xero import _update_post_sync_task_status

            await _update_post_sync_task_status(
                post_sync_task_id,
                "failed",
                error_message=str(e),
            )
        return {
            "connection_id": str(connection_id),
            "status": "failed",
            "error": str(e),
        }

    finally:
        await session.close()


# =============================================================================
# Deadline Notification Tasks (Spec 011)
# =============================================================================


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.bas.check_lodgement_deadlines",
    bind=True,
    max_retries=2,
    default_retry_delay=300,  # 5 minutes
)
def check_lodgement_deadlines(
    self,
    notification_days: list[int] | None = None,
) -> dict[str, Any]:
    """Check all tenants for approaching BAS deadlines and send notifications.

    This task runs daily (scheduled at 6 AM AEST) and sends in-app notifications
    for BAS sessions with approaching lodgement deadlines.

    Args:
        notification_days: Days before deadline to notify (default: [7, 3, 1])

    Returns:
        Dict with notification results across all tenants
    """
    import asyncio

    return asyncio.run(_check_lodgement_deadlines_async(notification_days))


async def _check_lodgement_deadlines_async(
    notification_days: list[int] | None,
) -> dict[str, Any]:
    """Async implementation of deadline notification check."""
    from app.modules.auth.models import Tenant
    from app.modules.bas.deadline_notification_service import DeadlineNotificationService

    session = await _get_async_session()

    results: dict[str, Any] = {
        "tenants_checked": 0,
        "total_notifications_sent": 0,
        "tenant_results": [],
    }

    try:
        # Get all active tenants
        result = await session.execute(
            select(Tenant).where(Tenant.is_active == True)  # noqa: E712
        )
        tenants = list(result.scalars().all())

        for tenant in tenants:
            try:
                # Set tenant context for RLS
                await _set_tenant_context(session, tenant.id)

                # Check deadlines for this tenant
                deadline_service = DeadlineNotificationService(session)
                tenant_result = await deadline_service.check_and_notify_approaching_deadlines(
                    tenant_id=tenant.id,
                    notification_days=notification_days,
                )

                results["tenants_checked"] += 1
                results["total_notifications_sent"] += tenant_result["notifications_sent"]
                results["tenant_results"].append(
                    {
                        "tenant_id": str(tenant.id),
                        "tenant_name": tenant.name,
                        **tenant_result,
                    }
                )

            except Exception as e:
                logger.error(f"Failed to check deadlines for tenant {tenant.id}: {e}")
                results["tenant_results"].append(
                    {
                        "tenant_id": str(tenant.id),
                        "status": "failed",
                        "error": str(e),
                    }
                )

        await session.commit()

        logger.info(
            f"Deadline notification check completed: "
            f"{results['tenants_checked']} tenants, {results['total_notifications_sent']} notifications sent"
        )

        return results

    except Exception as e:
        logger.error(f"Deadline notification task failed: {e}")
        return {
            "status": "failed",
            "error": str(e),
        }

    finally:
        await session.close()


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.bas.check_tenant_deadlines",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def check_tenant_deadlines(
    self,
    tenant_id: str,
    notification_days: list[int] | None = None,
) -> dict[str, Any]:
    """Check a specific tenant for approaching BAS deadlines.

    Can be triggered manually from the API if needed.

    Args:
        tenant_id: The tenant ID to check
        notification_days: Days before deadline to notify (default: [7, 3, 1])

    Returns:
        Dict with notification results
    """
    import asyncio

    return asyncio.run(_check_tenant_deadlines_async(UUID(tenant_id), notification_days))


async def _check_tenant_deadlines_async(
    tenant_id: UUID,
    notification_days: list[int] | None,
) -> dict[str, Any]:
    """Async implementation for single tenant deadline check."""
    from app.modules.bas.deadline_notification_service import DeadlineNotificationService

    session = await _get_async_session()

    try:
        await _set_tenant_context(session, tenant_id)

        deadline_service = DeadlineNotificationService(session)
        result = await deadline_service.check_and_notify_approaching_deadlines(
            tenant_id=tenant_id,
            notification_days=notification_days,
        )

        await session.commit()

        logger.info(
            f"Tenant deadline check completed for {tenant_id}: "
            f"{result['notifications_sent']} notifications sent"
        )

        return {
            "tenant_id": str(tenant_id),
            "status": "completed",
            **result,
        }

    except Exception as e:
        logger.error(f"Tenant deadline check failed for {tenant_id}: {e}")
        return {
            "tenant_id": str(tenant_id),
            "status": "failed",
            "error": str(e),
        }

    finally:
        await session.close()


# =============================================================================
# Tax Code Suggestion Tasks (Spec 046)
# =============================================================================


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.bas.generate_tax_code_suggestions",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def generate_tax_code_suggestions(
    self,
    connection_id: str,
    tenant_id: str,
    trigger_reason: str = "sync",
    post_sync_task_id: str | None = None,
) -> dict[str, Any]:
    """Generate tax code suggestions for BAS sessions after sync."""
    import asyncio

    return asyncio.run(
        _generate_suggestions_async(
            UUID(connection_id), UUID(tenant_id), trigger_reason, post_sync_task_id
        )
    )


async def _generate_suggestions_async(
    connection_id: UUID,
    tenant_id: UUID,
    trigger_reason: str,
    post_sync_task_id: str | None,
) -> dict[str, Any]:
    """Async implementation of suggestion generation."""
    session = await _get_async_session()
    try:
        await session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))

        from app.modules.bas.models import BASSession
        from app.modules.bas.tax_code_service import TaxCodeService

        result = await session.execute(
            select(BASSession).where(
                BASSession.tenant_id == tenant_id,
                BASSession.gst_calculated_at.isnot(None),
            )
        )
        sessions = result.scalars().all()

        total_generated = 0
        session_count = 0
        for bas_session in sessions:
            if bas_session.period and bas_session.period.connection_id == connection_id:
                try:
                    service = TaxCodeService(session)
                    gen_result = await service.detect_and_generate(bas_session.id, tenant_id)
                    total_generated += gen_result.get("generated", 0)
                    session_count += 1
                except Exception as e:
                    logger.warning(
                        f"Suggestion generation failed for session {bas_session.id}: {e}"
                    )

        await session.commit()
        logger.info(
            f"Generated {total_generated} suggestions across {session_count} sessions "
            f"for connection {connection_id} (trigger: {trigger_reason})"
        )
        return {
            "connection_id": str(connection_id),
            "sessions_processed": session_count,
            "total_generated": total_generated,
        }
    except Exception as e:
        logger.error(f"Tax code suggestion generation failed: {e}")
        await session.rollback()
        return {"connection_id": str(connection_id), "status": "failed", "error": str(e)}
    finally:
        await session.close()


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.bas.check_tax_code_conflicts",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def check_tax_code_conflicts(
    self,
    connection_id: str,
    tenant_id: str,
    post_sync_task_id: str | None = None,
) -> dict[str, Any]:
    """Check for re-sync conflicts on tax code overrides."""
    import asyncio

    return asyncio.run(
        _check_conflicts_async(UUID(connection_id), UUID(tenant_id), post_sync_task_id)
    )


async def _check_conflicts_async(
    connection_id: UUID,
    tenant_id: UUID,
    post_sync_task_id: str | None,
) -> dict[str, Any]:
    """Async implementation of conflict detection."""
    session = await _get_async_session()
    try:
        await session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))

        from app.modules.bas.tax_code_service import TaxCodeService

        service = TaxCodeService(session)
        conflicts = await service.detect_conflicts(connection_id, tenant_id)
        await session.commit()
        return {"connection_id": str(connection_id), "conflicts_found": len(conflicts)}
    except Exception as e:
        logger.error(f"Tax code conflict check failed: {e}")
        await session.rollback()
        return {"connection_id": str(connection_id), "status": "failed", "error": str(e)}
    finally:
        await session.close()
