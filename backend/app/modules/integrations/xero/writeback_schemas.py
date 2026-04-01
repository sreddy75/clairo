"""Pydantic schemas for Xero write-back API responses.

Spec 049: Xero Tax Code Write-Back.
Matches the contracts/writeback.yaml contract specification.
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.integrations.xero.writeback_models import (
    XeroWritebackItemStatus,
    XeroWritebackJobStatus,
    XeroWritebackSkipReason,
)


class WritebackTransactionContext(BaseModel):
    """Denormalised transaction context for a write-back item display."""

    contact_name: str | None = None
    transaction_date: date | None = None
    description: str | None = None
    total_line_amount: float | None = None


class WritebackItemResponse(BaseModel):
    """Response schema for a single write-back item."""

    id: UUID
    job_id: UUID
    source_type: str
    xero_document_id: str
    local_document_id: UUID
    override_ids: list[UUID]
    line_item_indexes: list[int]
    before_tax_types: dict[str, Any]
    after_tax_types: dict[str, Any]
    status: XeroWritebackItemStatus
    skip_reason: XeroWritebackSkipReason | None = None
    error_detail: str | None = None
    xero_http_status: int | None = None
    processed_at: datetime | None = None
    created_at: datetime
    transaction_context: WritebackTransactionContext | None = None

    model_config = {"from_attributes": True}


class WritebackJobResponse(BaseModel):
    """Response schema for a write-back job (summary, no items)."""

    id: UUID
    tenant_id: UUID
    connection_id: UUID
    session_id: UUID
    triggered_by: UUID | None = None
    status: XeroWritebackJobStatus
    total_count: int = 0
    succeeded_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: int | None = None
    error_detail: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class WritebackJobDetailResponse(WritebackJobResponse):
    """Response schema for a write-back job including all items."""

    items: list[WritebackItemResponse] = Field(default_factory=list)
