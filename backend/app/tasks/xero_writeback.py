"""Celery task for Xero tax code write-back.

Spec 049: Xero Tax Code Write-Back.
Processes all pending XeroWritebackItems in a job sequentially:
1. Pre-flight: fetch current Xero document, check editability
2. Reconstruct full line_items payload with tax type changes
3. POST to Xero, handle rate limiting and error categories
4. Update XeroWritebackItem status and TaxCodeOverride.writeback_status
5. Emit audit events per item and for job completion
"""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from celery import Task
from sqlalchemy import and_, select, text, update
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


async def _run_writeback_job(job_id_str: str, tenant_id_str: str) -> None:
    """Core async implementation of the write-back job processor."""
    from app.modules.bas.exceptions import SplitAmountMismatchError
    from app.modules.bas.models import TaxCodeOverride, TaxCodeOverrideWritebackStatus
    from app.modules.bas.repository import BASRepository
    from app.modules.integrations.xero.audit_events import (
        WRITEBACK_COMPLETED,
        WRITEBACK_ITEM_FAILED,
        WRITEBACK_ITEM_SKIPPED,
        WRITEBACK_ITEM_SUCCESS,
    )
    from app.modules.integrations.xero.client import XeroClient
    from app.modules.integrations.xero.exceptions import (
        WritebackError,
        XeroConflictError,
        XeroDocumentNotEditableError,
    )
    from app.modules.integrations.xero.models import (
        XeroConnection,
    )
    from app.modules.integrations.xero.rate_limiter import XeroRateLimiter
    from app.modules.integrations.xero.writeback_models import (
        XeroWritebackItemStatus,
        XeroWritebackJobStatus,
    )
    from app.modules.integrations.xero.writeback_repository import XeroWritebackRepository
    from app.modules.integrations.xero.writeback_service import (
        apply_overrides_to_line_items,
        check_document_editability,
    )

    job_id = UUID(job_id_str)
    tenant_id = UUID(tenant_id_str)
    settings = get_settings()

    async with await _get_async_session() as db:
        await _set_tenant_context(db, tenant_id)

        repo = XeroWritebackRepository(db)
        bas_repo = BASRepository(db)

        # Load job
        job = await repo.get_job(job_id, tenant_id)
        if not job:
            logger.error("Write-back job %s not found for tenant %s", job_id, tenant_id)
            return

        # Load connection
        result = await db.execute(
            select(XeroConnection).where(XeroConnection.id == job.connection_id)
        )
        connection = result.scalar_one_or_none()
        if not connection:
            await repo.update_job_status(
                job_id,
                XeroWritebackJobStatus.FAILED,
                error_detail="Xero connection not found",
            )
            await db.commit()
            return

        # Mark job as in_progress
        now = datetime.now(UTC)
        await repo.update_job_status(
            job_id,
            XeroWritebackJobStatus.IN_PROGRESS,
            started_at=now,
        )
        await db.commit()

        # Load all pending items
        items = await repo.get_items_for_job(job_id)
        pending_items = [i for i in items if i.status != XeroWritebackItemStatus.SUCCESS.value]

        succeeded = 0
        skipped = 0
        failed = 0

        xero_tenant_id = connection.xero_tenant_id

        # Acquire initial access token via ensure_valid_token (grant-scoped lock,
        # handles rotation races with sibling connections).
        from app.modules.integrations.xero.connection_service import XeroConnectionService
        from app.modules.integrations.xero.exceptions import XeroAuthRequiredError
        conn_service = XeroConnectionService(db, settings)
        try:
            access_token = await conn_service.ensure_valid_token(connection.id)
        except XeroAuthRequiredError:
            logger.error(
                "Writeback job %s aborted: Xero re-authorization required for connection %s",
                job_id,
                connection.id,
            )
            await repo.update_job_status(
                job_id,
                XeroWritebackJobStatus.FAILED,
                error_detail="xero_reauth_required: please reconnect Xero",
                completed_at=datetime.now(UTC),
            )
            await db.commit()
            return

        rate_limiter = XeroRateLimiter()

        async with XeroClient(settings.xero) as xero_client:
            # Fetch org tax rates once and build valid code set for validation
            try:
                tax_rates = await xero_client.get_tax_rates(access_token, xero_tenant_id)
                valid_tax_types = {r["TaxType"] for r in tax_rates if r.get("TaxType")}
            except Exception as e:
                logger.warning(
                    "Could not fetch tax rates for validation (will skip validation): %s", e
                )
                valid_tax_types = None  # Skip validation if TaxRates endpoint fails

            for item in pending_items:
                # Refresh token mid-loop if needed (long-running writeback jobs can
                # outlast the 30-minute access token). Uses grant-scoped lock.
                try:
                    access_token = await conn_service.ensure_valid_token(connection.id)
                except XeroAuthRequiredError as e:
                    logger.error(
                        "Token refresh failed mid-writeback for job %s: %s", job_id, e
                    )
                    for remaining_item in pending_items:
                        if remaining_item.status == XeroWritebackItemStatus.PENDING.value:
                            await repo.update_item_status(
                                remaining_item.id,
                                XeroWritebackItemStatus.FAILED,
                                processed_at=datetime.now(UTC),
                                error_detail="xero_reauth_required: please reconnect Xero",
                            )
                            failed += 1
                    await repo.update_job_status(
                        job_id,
                        XeroWritebackJobStatus.FAILED,
                        error_detail="xero_reauth_required: please reconnect Xero",
                        completed_at=datetime.now(UTC),
                    )
                    await db.commit()
                    return

                # Mark item as in_progress
                await repo.update_item_status(item.id, XeroWritebackItemStatus.IN_PROGRESS)
                await db.flush()

                item_processed_at = datetime.now(UTC)

                try:
                    # Load local entity to get line_items and xero_updated_at
                    local_entity = await _load_local_entity(
                        db, item.source_type, item.local_document_id, tenant_id
                    )
                    if not local_entity:
                        raise WritebackError(
                            f"Local entity not found: {item.source_type}/{item.local_document_id}"
                        )

                    # Validate tax type codes against org's known rates — but only for
                    # codes the accountant has *changed* (not codes that came from Xero
                    # originally, which are always valid by definition).
                    if (
                        valid_tax_types is not None
                        and item.after_tax_types
                        and item.before_tax_types
                    ):
                        new_codes = {
                            code
                            for idx, code in item.after_tax_types.items()
                            if code != item.before_tax_types.get(idx)
                        }
                        invalid = [code for code in new_codes if code not in valid_tax_types]
                        if invalid:
                            logger.warning(
                                "Invalid tax type(s) %s for item %s — valid: %s",
                                invalid,
                                item.id,
                                sorted(valid_tax_types),
                            )
                            raise XeroDocumentNotEditableError(
                                "invalid_tax_type", item.xero_document_id
                            )

                    # Pre-flight: check document is still editable in Xero.
                    # Returns the live Xero document — use its LineItems as the
                    # base to avoid stale/stripped data stored locally in the DB.
                    xero_doc = await check_document_editability(
                        xero_client=xero_client,
                        access_token=access_token,
                        xero_tenant_id=xero_tenant_id,
                        source_type=item.source_type,
                        xero_document_id=item.xero_document_id,
                        xero_updated_at=getattr(local_entity, "xero_updated_at", None),
                    )

                    # Load overrides for this item
                    overrides_result = await db.execute(
                        select(TaxCodeOverride).where(TaxCodeOverride.id.in_(item.override_ids))
                    )
                    overrides = list(overrides_result.scalars().all())

                    # Use live Xero line items as the base — the locally cached
                    # line_items may be stripped (missing UnitAmount/LineAmount/
                    # AccountCode) after previous syncs update only TaxType.
                    raw_line_items = xero_doc.get("LineItems", local_entity.line_items or [])
                    modified_line_items, before_types, after_types = apply_overrides_to_line_items(
                        raw_line_items, overrides
                    )
                    logger.warning(
                        "Sending to Xero %s: before=%s after=%s payload=%s",
                        item.xero_document_id,
                        before_types,
                        after_types,
                        [
                            {
                                k: v
                                for k, v in li.items()
                                if k in ("TaxType", "TaxAmount", "LineItemID")
                            }
                            for li in modified_line_items
                        ],
                    )

                    # Write to Xero — idempotency key prevents double-writes on Celery retry
                    idempotency_key = str(item.id)
                    if item.source_type == "invoice":
                        updated_doc, rate_state = await xero_client.update_invoice(
                            access_token,
                            xero_tenant_id,
                            item.xero_document_id,
                            modified_line_items,
                            idempotency_key=idempotency_key,
                        )
                        local_entity.line_items = updated_doc.get("LineItems", modified_line_items)
                    elif item.source_type == "bank_transaction":
                        updated_doc, rate_state = await xero_client.update_bank_transaction(
                            access_token,
                            xero_tenant_id,
                            item.xero_document_id,
                            modified_line_items,
                            idempotency_key=idempotency_key,
                        )
                        logger.warning(
                            "Xero response line items: %s",
                            [
                                {
                                    k: v
                                    for k, v in li.items()
                                    if k in ("TaxType", "TaxAmount", "LineItemID")
                                }
                                for li in updated_doc.get("LineItems", [])
                            ],
                        )
                        local_entity.line_items = updated_doc.get("LineItems", modified_line_items)
                    elif item.source_type == "credit_note":
                        updated_doc, rate_state = await xero_client.update_credit_note(
                            access_token,
                            xero_tenant_id,
                            item.xero_document_id,
                            modified_line_items,
                            idempotency_key=idempotency_key,
                        )
                        local_entity.line_items = updated_doc.get("LineItems", modified_line_items)
                    else:
                        raise WritebackError(f"Unknown source_type: {item.source_type}")

                    # Update local xero_updated_at from Xero's response so the next
                    # writeback doesn't falsely detect a conflict against this write.
                    from app.modules.integrations.xero.transformers import parse_xero_date

                    new_updated_at = parse_xero_date(updated_doc.get("UpdatedDateUTC"))
                    if new_updated_at is not None and hasattr(local_entity, "xero_updated_at"):
                        local_entity.xero_updated_at = new_updated_at

                    # Mark item success
                    await repo.update_item_status(
                        item.id,
                        XeroWritebackItemStatus.SUCCESS,
                        processed_at=item_processed_at,
                    )

                    # Update TaxCodeOverride records: synced + deactivate
                    await db.execute(
                        update(TaxCodeOverride)
                        .where(TaxCodeOverride.id.in_(item.override_ids))
                        .values(
                            writeback_status=TaxCodeOverrideWritebackStatus.SYNCED.value,
                            is_active=False,
                        )
                    )
                    await db.flush()
                    succeeded += 1

                    # Audit: item success
                    await bas_repo.create_audit_log(
                        tenant_id=tenant_id,
                        session_id=job.session_id,
                        event_type=WRITEBACK_ITEM_SUCCESS,
                        event_description=f"Written {item.source_type} {item.xero_document_id}",
                        is_system_action=True,
                        event_metadata={
                            "job_id": str(job_id),
                            "item_id": str(item.id),
                            "xero_document_id": item.xero_document_id,
                            "source_type": item.source_type,
                            "line_item_indexes": item.line_item_indexes,
                            "before_tax_types": before_types,
                            "after_tax_types": after_types,
                        },
                    )

                    # Rate limit handling: wait if needed before next item
                    wait_time = rate_limiter.get_wait_time(rate_state)
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)

                except XeroDocumentNotEditableError as e:
                    await repo.update_item_status(
                        item.id,
                        XeroWritebackItemStatus.SKIPPED,
                        processed_at=item_processed_at,
                        skip_reason=e.skip_reason,
                    )
                    skipped += 1
                    await bas_repo.create_audit_log(
                        tenant_id=tenant_id,
                        session_id=job.session_id,
                        event_type=WRITEBACK_ITEM_SKIPPED,
                        event_description=f"Skipped {item.source_type}: {e.skip_reason}",
                        is_system_action=True,
                        event_metadata={
                            "job_id": str(job_id),
                            "item_id": str(item.id),
                            "xero_document_id": item.xero_document_id,
                            "skip_reason": e.skip_reason,
                        },
                    )

                except XeroConflictError as e:
                    await repo.update_item_status(
                        item.id,
                        XeroWritebackItemStatus.SKIPPED,
                        processed_at=item_processed_at,
                        skip_reason="conflict_changed",
                    )
                    skipped += 1
                    await bas_repo.create_audit_log(
                        tenant_id=tenant_id,
                        session_id=job.session_id,
                        event_type=WRITEBACK_ITEM_SKIPPED,
                        event_description=f"Skipped {item.source_type}: conflict_changed",
                        is_system_action=True,
                        event_metadata={
                            "job_id": str(job_id),
                            "item_id": str(item.id),
                            "xero_document_id": e.xero_document_id,
                            "skip_reason": "conflict_changed",
                        },
                    )

                except SplitAmountMismatchError as e:
                    await repo.update_item_status(
                        item.id,
                        XeroWritebackItemStatus.SKIPPED,
                        processed_at=item_processed_at,
                        skip_reason="split_amount_mismatch",
                    )
                    skipped += 1
                    await bas_repo.create_audit_log(
                        tenant_id=tenant_id,
                        session_id=job.session_id,
                        event_type=WRITEBACK_ITEM_SKIPPED,
                        event_description=f"Skipped {item.source_type}: split_amount_mismatch",
                        is_system_action=True,
                        event_metadata={
                            "job_id": str(job_id),
                            "item_id": str(item.id),
                            "skip_reason": "split_amount_mismatch",
                            "expected_total": str(e.expected_total),
                            "actual_total": str(e.actual_total),
                        },
                    )

                except Exception as e:
                    # Check for period-locked or credit-note-applied HTTP 400
                    error_str = str(e).lower()
                    xero_status = getattr(e, "status_code", None)
                    skip_reason = None

                    if xero_status == 400:
                        if "period" in error_str or "accounting period" in error_str:
                            skip_reason = "period_locked"
                        elif "cannot modify line items" in error_str or "has payments" in error_str:
                            skip_reason = "authorised_locked"
                        elif "credit note" in error_str or "credit_note" in error_str:
                            skip_reason = "credit_note_applied"
                        elif (
                            "taxtype" in error_str.replace(" ", "")
                            or "tax type" in error_str
                            or "tax code" in error_str
                        ) and (
                            "does not exist" in error_str
                            or "cannot be used" in error_str
                            or "invalid" in error_str
                        ):
                            skip_reason = "invalid_tax_type"

                    if skip_reason:
                        await repo.update_item_status(
                            item.id,
                            XeroWritebackItemStatus.SKIPPED,
                            processed_at=item_processed_at,
                            skip_reason=skip_reason,
                            xero_http_status=xero_status,
                        )
                        skipped += 1
                        await bas_repo.create_audit_log(
                            tenant_id=tenant_id,
                            session_id=job.session_id,
                            event_type=WRITEBACK_ITEM_SKIPPED,
                            event_description=f"Skipped {item.source_type}: {skip_reason}",
                            is_system_action=True,
                            event_metadata={
                                "job_id": str(job_id),
                                "item_id": str(item.id),
                                "skip_reason": skip_reason,
                                "xero_http_status": xero_status,
                            },
                        )
                    else:
                        await repo.update_item_status(
                            item.id,
                            XeroWritebackItemStatus.FAILED,
                            processed_at=item_processed_at,
                            error_detail=str(e),
                            xero_http_status=xero_status,
                        )
                        failed += 1
                        await bas_repo.create_audit_log(
                            tenant_id=tenant_id,
                            session_id=job.session_id,
                            event_type=WRITEBACK_ITEM_FAILED,
                            event_description=f"Failed {item.source_type}: {e}",
                            is_system_action=True,
                            event_metadata={
                                "job_id": str(job_id),
                                "item_id": str(item.id),
                                "error_detail": str(e),
                                "xero_http_status": xero_status,
                            },
                        )

                await db.commit()

        # Determine final job status
        total = len(pending_items)
        completed_at = datetime.now(UTC)
        started_at = job.started_at or now
        duration = int((completed_at - started_at).total_seconds())

        if failed == 0 and skipped < total:
            final_status = XeroWritebackJobStatus.COMPLETED
        elif succeeded > 0 and failed > 0:
            final_status = XeroWritebackJobStatus.PARTIAL
        elif succeeded == 0 and failed == total:
            final_status = XeroWritebackJobStatus.FAILED
        else:
            final_status = XeroWritebackJobStatus.COMPLETED

        await repo.update_job_status(
            job_id,
            final_status,
            completed_at=completed_at,
            duration_seconds=duration,
        )
        await repo.update_job_counts(
            job_id,
            succeeded_count=succeeded,
            skipped_count=skipped,
            failed_count=failed,
        )

        # Audit: job completed
        await bas_repo.create_audit_log(
            tenant_id=tenant_id,
            session_id=job.session_id,
            event_type=WRITEBACK_COMPLETED,
            event_description=(
                f"Write-back completed: {succeeded} synced, {skipped} skipped, {failed} failed"
            ),
            is_system_action=True,
            event_metadata={
                "job_id": str(job_id),
                "total": total,
                "succeeded": succeeded,
                "skipped": skipped,
                "failed": failed,
                "duration_seconds": duration,
                "final_status": final_status.value,
            },
        )

        await db.commit()
        logger.info(
            "Write-back job %s completed: status=%s succeeded=%d skipped=%d failed=%d",
            job_id,
            final_status.value,
            succeeded,
            skipped,
            failed,
        )


async def _load_local_entity(
    db: AsyncSession,
    source_type: str,
    local_document_id: UUID,
    tenant_id: UUID,
) -> object | None:
    """Load the local Xero entity (Invoice/BankTransaction/CreditNote) from DB."""
    from app.modules.integrations.xero.models import (
        XeroBankTransaction,
        XeroCreditNote,
        XeroInvoice,
    )

    if source_type == "invoice":
        result = await db.execute(
            select(XeroInvoice).where(
                and_(
                    XeroInvoice.id == local_document_id,
                    XeroInvoice.tenant_id == tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    elif source_type == "bank_transaction":
        result = await db.execute(
            select(XeroBankTransaction).where(
                and_(
                    XeroBankTransaction.id == local_document_id,
                    XeroBankTransaction.tenant_id == tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    elif source_type == "credit_note":
        result = await db.execute(
            select(XeroCreditNote).where(
                and_(
                    XeroCreditNote.id == local_document_id,
                    XeroCreditNote.tenant_id == tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    return None


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="xero.writeback.process_job",
    max_retries=0,
)
def process_writeback_job(self: Task, job_id: str, tenant_id: str) -> None:
    """Process all pending XeroWritebackItems in a write-back job sequentially.

    Idempotent: skips items already in SUCCESS status.

    Args:
        job_id: Write-back job UUID string.
        tenant_id: Tenant UUID string.
    """
    asyncio.run(_run_writeback_job(job_id, tenant_id))
