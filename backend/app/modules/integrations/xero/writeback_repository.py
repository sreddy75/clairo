"""Repository for Xero write-back job and item persistence.

Spec 049: Xero Tax Code Write-Back.
All methods filter by tenant_id for multi-tenancy isolation.
All write methods use flush() — session lifecycle managed by caller.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.xero.writeback_models import (
    XeroWritebackItem,
    XeroWritebackItemStatus,
    XeroWritebackJob,
    XeroWritebackJobStatus,
)


class XeroWritebackRepository:
    """CRUD operations for XeroWritebackJob and XeroWritebackItem."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -------------------------------------------------------------------------
    # Job methods
    # -------------------------------------------------------------------------

    async def create_job(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        session_id: UUID,
        triggered_by: UUID | None,
        total_count: int,
    ) -> XeroWritebackJob:
        """Create a new write-back job record."""
        job = XeroWritebackJob(
            tenant_id=tenant_id,
            connection_id=connection_id,
            session_id=session_id,
            triggered_by=triggered_by,
            total_count=total_count,
            status=XeroWritebackJobStatus.PENDING.value,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_job(self, job_id: UUID, tenant_id: UUID) -> XeroWritebackJob | None:
        """Fetch a job by ID, scoped to tenant."""
        result = await self.session.execute(
            select(XeroWritebackJob).where(
                and_(
                    XeroWritebackJob.id == job_id,
                    XeroWritebackJob.tenant_id == tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_jobs_for_session(
        self,
        session_id: UUID,
        tenant_id: UUID,
    ) -> list[XeroWritebackJob]:
        """List all write-back jobs for a BAS session, newest first."""
        result = await self.session.execute(
            select(XeroWritebackJob)
            .where(
                and_(
                    XeroWritebackJob.session_id == session_id,
                    XeroWritebackJob.tenant_id == tenant_id,
                )
            )
            .order_by(XeroWritebackJob.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_latest_job_for_session(
        self,
        session_id: UUID,
        tenant_id: UUID,
    ) -> XeroWritebackJob | None:
        """Get the most recent write-back job for a BAS session."""
        result = await self.session.execute(
            select(XeroWritebackJob)
            .where(
                and_(
                    XeroWritebackJob.session_id == session_id,
                    XeroWritebackJob.tenant_id == tenant_id,
                )
            )
            .order_by(XeroWritebackJob.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_job_status(
        self,
        job_id: UUID,
        status: XeroWritebackJobStatus,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        duration_seconds: int | None = None,
        error_detail: str | None = None,
    ) -> None:
        """Update the status and timing of a write-back job."""
        values: dict[str, Any] = {"status": status.value}
        if started_at is not None:
            values["started_at"] = started_at
        if completed_at is not None:
            values["completed_at"] = completed_at
        if duration_seconds is not None:
            values["duration_seconds"] = duration_seconds
        if error_detail is not None:
            values["error_detail"] = error_detail

        await self.session.execute(
            update(XeroWritebackJob).where(XeroWritebackJob.id == job_id).values(**values)
        )
        await self.session.flush()

    async def update_job_counts(
        self,
        job_id: UUID,
        succeeded_count: int | None = None,
        skipped_count: int | None = None,
        failed_count: int | None = None,
    ) -> None:
        """Update the item counts on a write-back job."""
        values: dict[str, Any] = {}
        if succeeded_count is not None:
            values["succeeded_count"] = succeeded_count
        if skipped_count is not None:
            values["skipped_count"] = skipped_count
        if failed_count is not None:
            values["failed_count"] = failed_count

        if values:
            await self.session.execute(
                update(XeroWritebackJob).where(XeroWritebackJob.id == job_id).values(**values)
            )
            await self.session.flush()

    # -------------------------------------------------------------------------
    # Item methods
    # -------------------------------------------------------------------------

    async def create_item(
        self,
        tenant_id: UUID,
        job_id: UUID,
        source_type: str,
        xero_document_id: str,
        local_document_id: UUID,
        override_ids: list[UUID],
        line_item_indexes: list[int],
        before_tax_types: dict[str, Any],
        after_tax_types: dict[str, Any],
    ) -> XeroWritebackItem:
        """Create a new write-back item record."""
        item = XeroWritebackItem(
            tenant_id=tenant_id,
            job_id=job_id,
            source_type=source_type,
            xero_document_id=xero_document_id,
            local_document_id=local_document_id,
            override_ids=override_ids,
            line_item_indexes=line_item_indexes,
            before_tax_types=before_tax_types,
            after_tax_types=after_tax_types,
            status=XeroWritebackItemStatus.PENDING.value,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_items_for_job(self, job_id: UUID) -> list[XeroWritebackItem]:
        """Get all items for a write-back job."""
        result = await self.session.execute(
            select(XeroWritebackItem)
            .where(XeroWritebackItem.job_id == job_id)
            .order_by(XeroWritebackItem.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_failed_items(self, job_id: UUID) -> list[XeroWritebackItem]:
        """Get failed items for a write-back job (for retry)."""
        result = await self.session.execute(
            select(XeroWritebackItem).where(
                and_(
                    XeroWritebackItem.job_id == job_id,
                    XeroWritebackItem.status == XeroWritebackItemStatus.FAILED.value,
                )
            )
        )
        return list(result.scalars().all())

    async def update_item_status(
        self,
        item_id: UUID,
        status: XeroWritebackItemStatus,
        processed_at: datetime | None = None,
        skip_reason: str | None = None,
        error_detail: str | None = None,
        xero_http_status: int | None = None,
    ) -> None:
        """Update the status of a write-back item."""
        values: dict[str, Any] = {"status": status.value}
        if processed_at is not None:
            values["processed_at"] = processed_at
        if skip_reason is not None:
            values["skip_reason"] = skip_reason
        if error_detail is not None:
            values["error_detail"] = error_detail
        if xero_http_status is not None:
            values["xero_http_status"] = xero_http_status

        await self.session.execute(
            update(XeroWritebackItem).where(XeroWritebackItem.id == item_id).values(**values)
        )
        await self.session.flush()
