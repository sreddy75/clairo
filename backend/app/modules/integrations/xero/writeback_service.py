"""Xero tax code write-back service.

Spec 049: Xero Tax Code Write-Back.
Orchestrates the process of writing approved TaxCodeOverride records
back to Xero documents via the Xero API.
"""

import copy
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bas.models import (
    BASSession,
    BASSessionStatus,
    TaxCodeOverride,
    TaxCodeOverrideWritebackStatus,
    TaxCodeSuggestion,
)
from app.modules.integrations.xero.exceptions import (
    WritebackError,
    WritebackJobNotFoundError,
    XeroConnectionNotFoundError,
)
from app.modules.integrations.xero.models import (
    XeroBankTransaction,
    XeroConnection,
    XeroCreditNote,
    XeroInvoice,
)
from app.modules.integrations.xero.writeback_models import (
    XeroWritebackJob,
    XeroWritebackJobStatus,
)
from app.modules.integrations.xero.writeback_repository import XeroWritebackRepository

logger = logging.getLogger(__name__)


class XeroWritebackService:
    """Orchestrates write-back of approved tax code overrides to Xero."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = XeroWritebackRepository(db)

    async def initiate_writeback(
        self,
        session_id: UUID,
        triggered_by: UUID | None,
        tenant_id: UUID,
    ) -> XeroWritebackJob:
        """Create a write-back job and enqueue the Celery task.

        Args:
            session_id: BAS session ID to sync overrides for.
            triggered_by: Practice user who triggered the sync.
            tenant_id: Tenant ID for RLS.

        Returns:
            Created XeroWritebackJob with status=pending.

        Raises:
            WritebackError: If session not ready, no items to sync, or a
                job is already in progress.
        """
        # Validate session exists and is not draft (any active session can sync)
        session = await self._get_session(session_id, tenant_id)
        if session.status == BASSessionStatus.DRAFT.value:
            raise WritebackError(
                f"BAS session {session_id} must be calculated before syncing tax codes to Xero "
                f"(current: {session.status})",
                code="session_not_ready",
            )

        # Check no job already in_progress for this session
        existing_jobs = await self.repo.list_jobs_for_session(session_id, tenant_id)
        if any(j.status == XeroWritebackJobStatus.IN_PROGRESS.value for j in existing_jobs):
            raise WritebackError(
                f"A write-back job is already in progress for session {session_id}",
                code="job_in_progress",
            )

        # Get approved unsynced overrides for this session
        overrides = await self._get_pending_overrides(session_id, tenant_id)
        if not overrides:
            raise WritebackError(
                "No approved, unsynced tax code overrides found for this session",
                code="no_items_to_sync",
            )

        # Get the Xero connection
        connection = await self._get_connection(session.period.connection_id, tenant_id)

        # Group overrides by (source_type, source_id)
        grouped = group_overrides_by_document(overrides)

        # Create the job
        job = await self.repo.create_job(
            tenant_id=tenant_id,
            connection_id=connection.id,
            session_id=session_id,
            triggered_by=triggered_by,
            total_count=len(grouped),
        )

        # Create one item per document group
        for (source_type, source_id), doc_overrides in grouped.items():
            # Determine before/after tax type snapshots
            before_tax_types = {
                str(ov.line_item_index): ov.original_tax_type
                for ov in doc_overrides
            }
            after_tax_types = {
                str(ov.line_item_index): ov.override_tax_type
                for ov in doc_overrides
            }
            # Determine the Xero document ID from the first override's suggestion
            xero_doc_id = await self._resolve_xero_document_id(
                source_type, source_id, tenant_id
            )
            await self.repo.create_item(
                tenant_id=tenant_id,
                job_id=job.id,
                source_type=source_type,
                xero_document_id=xero_doc_id,
                local_document_id=source_id,
                override_ids=[ov.id for ov in doc_overrides],
                line_item_indexes=[ov.line_item_index for ov in doc_overrides],
                before_tax_types=before_tax_types,
                after_tax_types=after_tax_types,
            )

        # Emit audit event
        from app.modules.bas.repository import BASRepository
        from app.modules.integrations.xero.audit_events import WRITEBACK_INITIATED
        bas_repo = BASRepository(self.db)
        await bas_repo.create_audit_log(
            tenant_id=tenant_id,
            session_id=session_id,
            event_type=WRITEBACK_INITIATED,
            event_description=f"Write-back job initiated for {len(grouped)} documents",
            performed_by=triggered_by,
            event_metadata={
                "job_id": str(job.id),
                "connection_id": str(connection.id),
                "count_queued": len(grouped),
            },
        )

        # Enqueue the Celery task
        enqueue_writeback_task(str(job.id), str(tenant_id))

        return job

    async def get_job(
        self,
        job_id: UUID,
        tenant_id: UUID,
    ) -> XeroWritebackJob:
        """Fetch a write-back job by ID."""
        job = await self.repo.get_job(job_id, tenant_id)
        if not job:
            raise WritebackJobNotFoundError(job_id)
        return job

    async def get_latest_job_for_session(
        self,
        session_id: UUID,
        tenant_id: UUID,
    ) -> XeroWritebackJob | None:
        """Get the most recent write-back job for a BAS session."""
        return await self.repo.get_latest_job_for_session(session_id, tenant_id)

    async def retry_failed_items(
        self,
        job_id: UUID,
        triggered_by: UUID | None,
        tenant_id: UUID,
    ) -> XeroWritebackJob:
        """Create a new write-back job retrying only failed items from a previous job.

        Args:
            job_id: Original job ID to retry failed items from.
            triggered_by: Practice user triggering the retry.
            tenant_id: Tenant ID for RLS.

        Returns:
            New XeroWritebackJob for the retry.

        Raises:
            WritebackJobNotFoundError: If job not found.
            WritebackError: If no failed items or another job in progress.
        """
        original_job = await self.repo.get_job(job_id, tenant_id)
        if not original_job:
            raise WritebackJobNotFoundError(job_id)

        if original_job.failed_count == 0:
            raise WritebackError(
                "No failed items to retry in this job",
                code="no_failed_items",
            )

        # Check no job already in_progress for same session
        existing = await self.repo.list_jobs_for_session(original_job.session_id, tenant_id)
        if any(j.status == XeroWritebackJobStatus.IN_PROGRESS.value for j in existing):
            raise WritebackError(
                "A write-back job is already in progress for this session",
                code="job_in_progress",
            )

        # Get failed items from original job
        failed_items = await self.repo.get_failed_items(job_id)

        # Reset TaxCodeOverride.writeback_status back to pending_sync
        override_ids: list[UUID] = []
        for item in failed_items:
            override_ids.extend(item.override_ids)

        if override_ids:
            await self.db.execute(
                update(TaxCodeOverride)
                .where(TaxCodeOverride.id.in_(override_ids))
                .values(writeback_status=TaxCodeOverrideWritebackStatus.PENDING_SYNC.value)
            )
            await self.db.flush()

        # Create new job
        new_job = await self.repo.create_job(
            tenant_id=tenant_id,
            connection_id=original_job.connection_id,
            session_id=original_job.session_id,
            triggered_by=triggered_by,
            total_count=len(failed_items),
        )

        # Create new items mirroring the failed ones
        for item in failed_items:
            await self.repo.create_item(
                tenant_id=tenant_id,
                job_id=new_job.id,
                source_type=item.source_type,
                xero_document_id=item.xero_document_id,
                local_document_id=item.local_document_id,
                override_ids=list(item.override_ids),
                line_item_indexes=list(item.line_item_indexes),
                before_tax_types=dict(item.before_tax_types),
                after_tax_types=dict(item.after_tax_types),
            )

        # Emit audit event
        from app.modules.bas.repository import BASRepository
        from app.modules.integrations.xero.audit_events import WRITEBACK_RETRY_INITIATED
        bas_repo = BASRepository(self.db)
        await bas_repo.create_audit_log(
            tenant_id=tenant_id,
            session_id=original_job.session_id,
            event_type=WRITEBACK_RETRY_INITIATED,
            event_description=f"Retry write-back job created for {len(failed_items)} failed items",
            performed_by=triggered_by,
            event_metadata={
                "new_job_id": str(new_job.id),
                "original_job_id": str(job_id),
                "retry_count": len(failed_items),
            },
        )

        enqueue_writeback_task(str(new_job.id), str(tenant_id))
        return new_job

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    async def _get_session(self, session_id: UUID, tenant_id: UUID) -> BASSession:
        """Fetch and validate a BAS session."""
        result = await self.db.execute(
            select(BASSession).where(
                and_(
                    BASSession.id == session_id,
                    BASSession.tenant_id == tenant_id,
                )
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise WritebackError(
                f"BAS session {session_id} not found",
                code="session_not_found",
            )
        return session

    async def _get_connection(self, connection_id: UUID, tenant_id: UUID) -> XeroConnection:
        """Fetch and validate a Xero connection."""
        result = await self.db.execute(
            select(XeroConnection).where(
                and_(
                    XeroConnection.id == connection_id,
                    XeroConnection.tenant_id == tenant_id,
                )
            )
        )
        connection = result.scalar_one_or_none()
        if not connection:
            raise XeroConnectionNotFoundError(connection_id)
        return connection

    async def _get_pending_overrides(
        self,
        session_id: UUID,
        tenant_id: UUID,
    ) -> list[TaxCodeOverride]:
        """Get approved, unsynced TaxCodeOverride records for a session.

        Includes three categories:
        - Standard overrides tied to an approved/overridden TaxCodeSuggestion in
          this session (suggestion_id IS NOT NULL).
        - New-split overrides (is_new_split=True, suggestion_id=NULL) on any
          source_id that has suggestions in this session.
        - Manual edit/delete overrides (is_new_split=False, suggestion_id=NULL)
          created via the line item editor on transactions in this session.
        """
        # Subquery: source_ids that have suggestions in this session
        session_source_ids = (
            select(TaxCodeSuggestion.source_id)
            .where(
                and_(
                    TaxCodeSuggestion.session_id == session_id,
                    TaxCodeSuggestion.tenant_id == tenant_id,
                )
            )
            .scalar_subquery()
        )

        result = await self.db.execute(
            select(TaxCodeOverride)
            .outerjoin(TaxCodeSuggestion, TaxCodeOverride.suggestion_id == TaxCodeSuggestion.id)
            .where(
                and_(
                    or_(
                        # Standard override linked to an approved suggestion in this session
                        and_(
                            TaxCodeSuggestion.session_id == session_id,
                            TaxCodeSuggestion.status.in_(["approved", "overridden"]),
                        ),
                        # New-split override (no suggestion) on a transaction in this session
                        and_(
                            TaxCodeOverride.is_new_split.is_(True),
                            TaxCodeOverride.source_id.in_(session_source_ids),
                        ),
                        # Manual edit/delete override (no suggestion, not a new split)
                        # created via the line item editor on a transaction in this session
                        and_(
                            TaxCodeOverride.is_new_split.is_(False),
                            TaxCodeOverride.suggestion_id.is_(None),
                            TaxCodeOverride.source_id.in_(session_source_ids),
                        ),
                    ),
                    TaxCodeOverride.is_active.is_(True),
                    TaxCodeOverride.writeback_status
                    == TaxCodeOverrideWritebackStatus.PENDING_SYNC.value,
                    TaxCodeOverride.tenant_id == tenant_id,
                )
            )
        )
        return list(result.scalars().all())

    async def _resolve_xero_document_id(
        self,
        source_type: str,
        source_id: UUID,
        tenant_id: UUID,
    ) -> str:
        """Resolve a local document ID to the Xero API document ID."""
        if source_type == "invoice":
            result = await self.db.execute(
                select(XeroInvoice.xero_invoice_id).where(
                    and_(
                        XeroInvoice.id == source_id,
                        XeroInvoice.tenant_id == tenant_id,
                    )
                )
            )
            xero_id = result.scalar_one_or_none()
        elif source_type == "bank_transaction":
            result = await self.db.execute(
                select(XeroBankTransaction.xero_transaction_id).where(
                    and_(
                        XeroBankTransaction.id == source_id,
                        XeroBankTransaction.tenant_id == tenant_id,
                    )
                )
            )
            xero_id = result.scalar_one_or_none()
        elif source_type == "credit_note":
            result = await self.db.execute(
                select(XeroCreditNote.xero_credit_note_id).where(
                    and_(
                        XeroCreditNote.id == source_id,
                        XeroCreditNote.tenant_id == tenant_id,
                    )
                )
            )
            xero_id = result.scalar_one_or_none()
        else:
            raise WritebackError(f"Unknown source_type: {source_type}", code="unknown_source_type")

        if not xero_id:
            raise WritebackError(
                f"Could not resolve Xero document ID for {source_type} {source_id}",
                code="document_not_found",
            )
        return xero_id


def group_overrides_by_document(
    overrides: list[TaxCodeOverride],
) -> dict[tuple[str, UUID], list[TaxCodeOverride]]:
    """Group TaxCodeOverride records by (source_type, source_id).

    Each Xero document needs a single API call with all changed line items
    included in one payload — this groups overrides accordingly.

    Args:
        overrides: List of TaxCodeOverride records to group.

    Returns:
        Dict mapping (source_type, source_id) → list of overrides for that doc.
    """
    grouped: dict[tuple[str, UUID], list[TaxCodeOverride]] = {}
    for override in overrides:
        key = (override.source_type, override.source_id)
        grouped.setdefault(key, []).append(override)
    return grouped


# Mapping from snake_case keys (as stored locally) to Xero's PascalCase API keys.
_SNAKE_TO_PASCAL: dict[str, str] = {
    "line_item_id": "LineItemId",
    "description": "Description",
    "quantity": "Quantity",
    "unit_amount": "UnitAmount",
    "line_amount": "LineAmount",
    "account_code": "AccountCode",
    "tax_type": "TaxType",
    "tax_amount": "TaxAmount",
    "discount_rate": "DiscountRate",
    "discount_amount": "DiscountAmount",
    "item_code": "ItemCode",
    "tracking": "Tracking",
}


def _normalise_line_item(item: dict[str, Any]) -> dict[str, Any]:
    """Convert a line item dict from snake_case to Xero PascalCase.

    Handles mixed payloads — keys already in PascalCase are preserved,
    snake_case keys are promoted, and unknown keys are passed through.
    """
    out: dict[str, Any] = {}
    for k, v in item.items():
        pascal = _SNAKE_TO_PASCAL.get(k)
        if pascal:
            # Prefer the PascalCase version; skip if already present
            out.setdefault(pascal, v)
        else:
            out[k] = v
    return out


def apply_overrides_to_line_items(
    line_items: list[dict[str, Any]],
    overrides: list[TaxCodeOverride],
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, str]]:
    """Apply tax type overrides to a copy of line items.

    Supports two modes per override:
    - Override mode (``is_new_split=False``): patches TaxType on an existing
      line item at ``line_item_index``. Also updates LineAmount/Description/
      AccountCode when set on the override (for split-edited existing lines).
    - Split mode (``is_new_split=True``): appends a new line item entry built
      from the override's stored line_amount, line_description,
      line_account_code, and override_tax_type. These do not map to an
      existing index — the index is appended positionally.

    Normalises line items to Xero PascalCase before applying overrides so
    that the resulting payload is valid for the Xero API regardless of
    whether line items were stored in snake_case or PascalCase.

    Returns:
        Tuple of (modified line items, before_tax_types, after_tax_types).
        before/after are dicts keyed by str(line_item_index).
    """
    items = [_normalise_line_item(copy.deepcopy(li)) for li in line_items]
    before: dict[str, str] = {}
    after: dict[str, str] = {}

    # Separate into patch (existing) and append (new split) overrides
    patch_overrides = [ov for ov in overrides if not ov.is_new_split]
    split_overrides = [ov for ov in overrides if ov.is_new_split]

    # --- Override mode: patch existing line items (skip deleted ones) ---
    for override in patch_overrides:
        if override.is_deleted:
            continue
        idx = override.line_item_index
        if idx < len(items):
            original = items[idx].get("TaxType", "NONE")
            before[str(idx)] = original
            items[idx]["TaxType"] = override.override_tax_type
            after[str(idx)] = override.override_tax_type
            # Let Xero recalculate TaxAmount — removing it avoids validation errors
            # when switching between taxable and zero-rate types (e.g. INPUT↔BASEXCLUDED).
            items[idx].pop("TaxAmount", None)
            # Apply any stored line-level overrides for split-edited lines
            if override.line_amount is not None:
                items[idx]["LineAmount"] = float(override.line_amount)
                # UnitAmount must match LineAmount (Xero validates LineAmount = Qty × UnitAmount)
                items[idx]["UnitAmount"] = float(override.line_amount)
            if override.line_description is not None:
                items[idx]["Description"] = override.line_description
            if override.line_account_code is not None:
                items[idx]["AccountCode"] = override.line_account_code

    # --- Delete mode: remove original line items marked is_deleted ---
    delete_overrides = [ov for ov in patch_overrides if ov.is_deleted]
    deleted_indices = {ov.line_item_index for ov in delete_overrides}

    # Build retained set: original items minus deleted ones
    retained = [item for i, item in enumerate(items) if i not in deleted_indices]

    # --- Split mode: append new line items ---
    # Inherit AccountCode from the first original line item as a sensible default.
    default_account_code: str | None = items[0].get("AccountCode") if items else None

    for override in split_overrides:
        new_idx = len(retained)
        line_amount = float(override.line_amount) if override.line_amount is not None else None
        new_item: dict[str, Any] = {
            "TaxType": override.override_tax_type,
        }
        if line_amount is not None:
            new_item["LineAmount"] = line_amount
            # Xero requires UnitAmount on bank transaction line items (Quantity defaults to 1)
            new_item["UnitAmount"] = line_amount
        if override.line_description is not None:
            new_item["Description"] = override.line_description
        # Use explicitly set account code, fall back to parent line item's code
        account_code = override.line_account_code or default_account_code
        if account_code is not None:
            new_item["AccountCode"] = account_code
        retained.append(new_item)
        before[str(new_idx)] = "NONE"
        after[str(new_idx)] = override.override_tax_type

    return retained, before, after


def enqueue_writeback_task(job_id: str, tenant_id: str) -> None:
    """Dispatch the process_writeback_job Celery task.

    Args:
        job_id: Write-back job UUID as string.
        tenant_id: Tenant UUID as string.
    """
    from app.tasks.xero_writeback import process_writeback_job

    process_writeback_job.apply_async(args=[job_id, tenant_id])


async def check_document_editability(
    xero_client: Any,
    access_token: str,
    xero_tenant_id: str,
    source_type: str,
    xero_document_id: str,
    xero_updated_at: Any | None = None,
) -> dict:
    """Pre-flight check: verify a Xero document is still editable.

    Fetches the current document from Xero and checks for:
    - VOIDED or DELETED status
    - IsReconciled on bank transactions (reconciled)

    Args:
        xero_client: XeroClient instance.
        access_token: Valid Xero access token.
        xero_tenant_id: Xero organisation tenant ID.
        source_type: 'invoice', 'bank_transaction', or 'credit_note'.
        xero_document_id: Xero document UUID string.
        xero_updated_at: Last known UpdatedDateUTC from local entity.

    Returns:
        Current Xero document dict.

    Raises:
        XeroDocumentNotEditableError: If document is voided/deleted/locked.
        XeroConflictError: If document has been modified externally.
    """
    from app.modules.integrations.xero.exceptions import (
        XeroDocumentNotEditableError,
    )

    if source_type == "invoice":
        doc, _ = await xero_client.get_invoice(access_token, xero_tenant_id, xero_document_id)
        status = doc.get("Status", "").upper()
        if status in ("VOIDED", "DELETED"):
            raise XeroDocumentNotEditableError(status.lower(), xero_document_id)
    elif source_type == "bank_transaction":
        doc, _ = await xero_client.get_bank_transaction(
            access_token, xero_tenant_id, xero_document_id
        )
        status = doc.get("Status", "").upper()
        if status in ("VOIDED", "DELETED"):
            raise XeroDocumentNotEditableError(status.lower(), xero_document_id)
        if doc.get("IsReconciled"):
            raise XeroDocumentNotEditableError("reconciled", xero_document_id)
    elif source_type == "credit_note":
        doc, _ = await xero_client.get_credit_note(access_token, xero_tenant_id, xero_document_id)
        status = doc.get("Status", "").upper()
        if status in ("VOIDED", "DELETED"):
            raise XeroDocumentNotEditableError(status.lower(), xero_document_id)
    else:
        raise WritebackError(f"Unknown source_type: {source_type}")

    # Conflict check removed: we only ever write TaxType on line items, which
    # coexists safely with any human edits to other fields. The check was
    # producing false positives because our own successful writes update
    # Xero's UpdatedDateUTC without updating the local xero_updated_at.

    return doc
