"""Pydantic schemas for client transaction classification.

Spec 047: Client Transaction Classification.
Spec 049: Xero Tax Code Write-Back (send-back extensions).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .classification_constants import VALID_CATEGORY_IDS

# ---------------------------------------------------------------------------
# Request Schemas (Accountant Side)
# ---------------------------------------------------------------------------


class ManualReceiptFlag(BaseModel):
    """A transaction the accountant wants to flag for receipt upload."""

    source_type: str
    source_id: UUID
    line_item_index: int
    reason: str | None = None


class ClassificationRequestCreate(BaseModel):
    """Create a classification request for the client."""

    message: str | None = Field(None, max_length=500)
    transaction_ids: list[dict] | None = Field(
        None,
        description="Subset of transactions to include. Null = all unresolved.",
    )
    email_override: str | None = Field(None, description="Override client email if missing")
    manual_receipt_flags: list[ManualReceiptFlag] | None = None


class ClassificationResolve(BaseModel):
    """Approve, override, or reject a client classification."""

    action: str = Field(..., description="approved / overridden / rejected")
    tax_type: str | None = Field(None, description="Required if action is overridden")
    reason: str | None = Field(None, description="Required if action is overridden")

    @model_validator(mode="after")
    def validate_override_fields(self) -> ClassificationResolve:
        if self.action == "overridden" and not self.tax_type:
            msg = "tax_type is required when action is 'overridden'"
            raise ValueError(msg)
        if self.action not in {"approved", "overridden", "rejected"}:
            msg = f"Invalid action: {self.action}. Must be approved, overridden, or rejected."
            raise ValueError(msg)
        return self


class ClassificationBulkApprove(BaseModel):
    """Bulk approve classifications above a confidence threshold."""

    min_confidence: Decimal = Field(Decimal("0.80"), ge=Decimal("0"), le=Decimal("1"))
    exclude_personal: bool = True
    exclude_needs_help: bool = True


# ---------------------------------------------------------------------------
# Request Schemas (Client Side)
# ---------------------------------------------------------------------------


class ClientClassificationSave(BaseModel):
    """Save a client's classification for a single transaction."""

    category: str | None = Field(None, description="Category ID from taxonomy")
    description: str | None = Field(None, max_length=500, description="Free-text description")
    is_personal: bool = False
    needs_help: bool = False

    @model_validator(mode="after")
    def at_least_one_field(self) -> ClientClassificationSave:
        if not any([self.category, self.description, self.is_personal, self.needs_help]):
            msg = "At least one of category, description, is_personal, or needs_help must be provided."
            raise ValueError(msg)
        if self.category and self.category not in VALID_CATEGORY_IDS:
            msg = f"Invalid category: {self.category}"
            raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------


class ClassificationRequestResponse(BaseModel):
    """Response after creating a classification request."""

    id: UUID
    status: str
    client_email: str
    transaction_count: int
    magic_link_sent: bool = True
    expires_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClassificationRequestStatusResponse(BaseModel):
    """Current status of a classification request."""

    id: UUID
    status: str
    client_email: str
    message: str | None = None
    transaction_count: int
    classified_count: int
    submitted_at: datetime | None = None
    expires_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClassificationReviewItem(BaseModel):
    """A single classification for the accountant review screen."""

    id: UUID
    source_type: str
    source_id: UUID
    line_item_index: int
    transaction_date: str | None = None
    line_amount: Decimal
    description: str | None = None
    contact_name: str | None = None
    account_code: str | None = None

    # Client input
    client_category: str | None = None
    client_category_label: str | None = None
    client_description: str | None = None
    client_is_personal: bool = False
    client_needs_help: bool = False
    classified_at: datetime | None = None

    # AI mapping
    ai_suggested_tax_type: str | None = None
    ai_confidence: Decimal | None = None
    needs_attention: bool = False

    # Receipt
    receipt_required: bool = False
    receipt_reason: str | None = None
    receipt_attached: bool = False
    receipt_document_id: UUID | None = None

    # Accountant action
    suggestion_id: UUID | None = None
    accountant_action: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ClassificationReviewSummary(BaseModel):
    """Summary counts for the review screen."""

    total: int = 0
    classified_by_client: int = 0
    marked_personal: int = 0
    needs_help: int = 0
    auto_mappable: int = 0
    needs_attention: int = 0
    already_reviewed: int = 0
    receipts_required: int = 0
    receipts_attached: int = 0
    receipts_missing: int = 0


class ClassificationReviewResponse(BaseModel):
    """Full review data for the accountant."""

    request_id: UUID
    request_status: str
    classifications: list[ClassificationReviewItem]
    summary: ClassificationReviewSummary


class ClassificationResolveResponse(BaseModel):
    """Response after resolving a classification."""

    id: UUID
    accountant_action: str
    final_tax_type: str | None = None
    suggestion_id: UUID | None = None


class ClassificationBulkApproveResponse(BaseModel):
    """Response after bulk-approving classifications."""

    approved_count: int
    skipped_count: int


# ---------------------------------------------------------------------------
# Client-Facing Response Schemas
# ---------------------------------------------------------------------------


class ClientTransactionView(BaseModel):
    """A transaction as seen by the client (no tax codes or Xero IDs)."""

    id: UUID
    transaction_date: str | None = None
    amount: Decimal
    description: str | None = None
    hint: str | None = None
    current_category: str | None = None
    current_description: str | None = None
    is_classified: bool = False
    receipt_required: bool = False
    receipt_reason: str | None = None
    receipt_attached: bool = False


class ClientCategoryView(BaseModel):
    """A category as shown to the client."""

    id: str
    label: str
    group: str


class ClientClassifyProgressView(BaseModel):
    """Progress indicator for the classification page."""

    total: int
    classified: int
    remaining: int


class ClientClassifyPageResponse(BaseModel):
    """Full page data for the client classification page."""

    request_id: UUID
    practice_name: str
    message: str | None = None
    expires_at: datetime
    transactions: list[ClientTransactionView]
    categories: list[ClientCategoryView]
    progress: ClientClassifyProgressView


class ClientClassificationSaveResponse(BaseModel):
    """Response after saving a classification."""

    id: UUID
    is_classified: bool = True
    classified_at: datetime | None = None


class ClientClassificationSubmitResponse(BaseModel):
    """Response after submitting all classifications."""

    request_id: UUID
    status: str
    classified_count: int
    total_count: int
    submitted_at: datetime


# ---------------------------------------------------------------------------
# Send-Back Schemas (Spec 049)
# ---------------------------------------------------------------------------


class AgentNoteCreate(BaseModel):
    """Create a per-transaction agent note."""

    source_type: str
    source_id: UUID
    line_item_index: int
    note_text: str = Field(..., min_length=1, max_length=1000)
    is_send_back_comment: bool = False


class AgentNoteResponse(BaseModel):
    """Response for an agent transaction note."""

    id: UUID
    request_id: UUID
    source_type: str
    source_id: UUID
    line_item_index: int
    note_text: str
    is_send_back_comment: bool
    created_by: UUID | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SendBackItemRequest(BaseModel):
    """One IDK item to send back with an agent comment."""

    classification_id: UUID
    agent_comment: str = Field(..., min_length=1, max_length=2000)


class SendBackRequest(BaseModel):
    """Request to send IDK items back to the client for clarification."""

    items: list[SendBackItemRequest] = Field(..., min_length=1)


class SendBackResponse(BaseModel):
    """Response after sending items back to the client."""

    new_request_id: UUID
    round_number: int
    client_email: str
    item_count: int
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClassificationRoundResponse(BaseModel):
    """One round in the send-back conversation thread for a transaction."""

    id: UUID
    session_id: UUID
    source_type: str
    source_id: UUID
    line_item_index: int
    round_number: int
    request_id: UUID
    agent_comment: str | None = None
    client_response_category: str | None = None
    client_response_description: str | None = None
    client_needs_help: bool = False
    responded_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

