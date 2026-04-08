"""Pydantic schemas for BAS preparation workflow."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

# =============================================================================
# Period Schemas
# =============================================================================


class BASPeriodCreate(BaseModel):
    """Request to create a BAS period."""

    quarter: int = Field(..., ge=1, le=4, description="Quarter (1-4)")
    fy_year: int = Field(..., ge=2020, description="Financial year")


class BASPeriodResponse(BaseModel):
    """BAS period response."""

    id: UUID
    connection_id: UUID
    period_type: str
    quarter: int | None
    month: int | None
    fy_year: int
    start_date: date
    end_date: date
    due_date: date
    display_name: str
    has_session: bool
    session_id: UUID | None = None
    session_status: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BASPeriodListResponse(BaseModel):
    """List of BAS periods."""

    periods: list[BASPeriodResponse]
    total: int


# =============================================================================
# Session Schemas
# =============================================================================


class BASSessionCreate(BaseModel):
    """Request to create a BAS session."""

    quarter: int = Field(..., ge=1, le=4, description="Quarter (1-4)")
    fy_year: int = Field(..., ge=2020, description="Financial year")


class BASSessionUpdate(BaseModel):
    """Request to update a BAS session."""

    status: (
        Literal[
            "draft",
            "in_progress",
            "ready_for_review",
            "approved",
            "lodged",
        ]
        | None
    ) = None
    internal_notes: str | None = None


class ApproveSessionRequest(BaseModel):
    """Request to approve a BAS session."""

    notes: str | None = None


class RequestChangesRequest(BaseModel):
    """Request to send changes back for a BAS session."""

    feedback: str


class ReopenSessionRequest(BaseModel):
    """Request to reopen an approved BAS session."""

    reason: str | None = None


class BASSessionResponse(BaseModel):
    """BAS session response."""

    id: UUID
    period_id: UUID
    status: str
    period_display_name: str
    quarter: int | None
    fy_year: int
    start_date: date
    end_date: date
    due_date: date
    created_by: UUID
    created_by_name: str | None = None
    approved_by: UUID | None
    approved_at: datetime | None
    gst_calculated_at: datetime | None
    payg_calculated_at: datetime | None
    internal_notes: str | None
    has_calculation: bool
    quality_score: Decimal | None = None
    # Auto-creation and review tracking
    auto_created: bool = False
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    reviewed_by_name: str | None = None
    # Lodgement tracking (Spec 011)
    lodged_at: datetime | None = None
    lodged_by: UUID | None = None
    lodged_by_name: str | None = None
    lodgement_method: str | None = None
    lodgement_method_description: str | None = None
    ato_reference_number: str | None = None
    lodgement_notes: str | None = None
    is_lodged: bool = False
    can_record_lodgement: bool = False
    # Xero write-back tracking (Spec 049)
    approved_unsynced_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BASSessionListResponse(BaseModel):
    """List of BAS sessions."""

    sessions: list[BASSessionResponse]
    total: int


# =============================================================================
# Calculation Schemas
# =============================================================================


class GSTBreakdown(BaseModel):
    """GST calculation breakdown."""

    # G-fields
    g1_total_sales: Decimal = Field(default=Decimal("0"), description="Total sales including GST")
    g2_export_sales: Decimal = Field(default=Decimal("0"), description="Export sales")
    g3_gst_free_sales: Decimal = Field(default=Decimal("0"), description="Other GST-free sales")
    g10_capital_purchases: Decimal = Field(default=Decimal("0"), description="Capital purchases")
    g11_non_capital_purchases: Decimal = Field(
        default=Decimal("0"), description="Non-capital purchases"
    )

    # Calculated fields
    field_1a_gst_on_sales: Decimal = Field(default=Decimal("0"), description="GST on sales")
    field_1b_gst_on_purchases: Decimal = Field(default=Decimal("0"), description="GST on purchases")
    gst_payable: Decimal = Field(default=Decimal("0"), description="Net GST (1A - 1B)")

    # Metadata
    invoice_count: int = 0
    transaction_count: int = 0


class PAYGBreakdown(BaseModel):
    """PAYG calculation breakdown."""

    w1_total_wages: Decimal = Field(default=Decimal("0"), description="Total salary/wages")
    w2_amount_withheld: Decimal = Field(default=Decimal("0"), description="PAYG withheld")
    pay_run_count: int = 0
    has_payroll: bool = False


class BASCalculationResponse(BaseModel):
    """BAS calculation response."""

    id: UUID
    session_id: UUID

    # GST fields
    g1_total_sales: Decimal
    g2_export_sales: Decimal
    g3_gst_free_sales: Decimal
    g10_capital_purchases: Decimal
    g11_non_capital_purchases: Decimal
    field_1a_gst_on_sales: Decimal
    field_1b_gst_on_purchases: Decimal

    # PAYG fields
    w1_total_wages: Decimal
    w2_amount_withheld: Decimal

    # Summary
    gst_payable: Decimal
    total_payable: Decimal
    is_refund: bool

    # Metadata
    calculated_at: datetime
    calculation_duration_ms: int | None
    transaction_count: int
    invoice_count: int
    pay_run_count: int

    model_config = {"from_attributes": True}


class BASCalculateTriggerResponse(BaseModel):
    """Response after triggering BAS calculation."""

    session_id: UUID
    gst: GSTBreakdown
    payg: PAYGBreakdown
    total_payable: Decimal
    is_refund: bool
    calculated_at: datetime
    calculation_duration_ms: int


class BASSummaryResponse(BaseModel):
    """Complete BAS summary for review."""

    session: BASSessionResponse
    calculation: BASCalculationResponse | None
    adjustments: list["BASAdjustmentResponse"]
    adjusted_totals: dict[str, Decimal]
    quality_score: Decimal | None
    quality_issues_count: int
    can_approve: bool
    blocking_issues: list[str]


# =============================================================================
# Adjustment Schemas
# =============================================================================


class BASAdjustmentCreate(BaseModel):
    """Request to create a BAS adjustment."""

    field_name: Literal[
        "g1_total_sales",
        "g2_export_sales",
        "g3_gst_free_sales",
        "g10_capital_purchases",
        "g11_non_capital_purchases",
        "field_1a_gst_on_sales",
        "field_1b_gst_on_purchases",
        "w1_total_wages",
        "w2_amount_withheld",
    ] = Field(..., description="Field to adjust")
    adjustment_amount: Decimal = Field(..., description="Amount to add/subtract")
    reason: str = Field(..., min_length=1, max_length=1000, description="Reason for adjustment")
    reference: str | None = Field(None, max_length=255, description="Optional reference")


class BASAdjustmentResponse(BaseModel):
    """BAS adjustment response."""

    id: UUID
    session_id: UUID
    field_name: str
    adjustment_amount: Decimal
    reason: str
    reference: str | None
    created_by: UUID
    created_by_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BASAdjustmentListResponse(BaseModel):
    """List of BAS adjustments."""

    adjustments: list[BASAdjustmentResponse]
    total: int


# =============================================================================
# Variance Schemas
# =============================================================================


class FieldVariance(BaseModel):
    """Variance for a single field."""

    field_name: str
    field_label: str
    current_value: Decimal
    prior_value: Decimal | None
    absolute_change: Decimal | None
    percent_change: Decimal | None
    severity: Literal["normal", "warning", "critical"]
    comparison_period: str | None  # e.g., "Q1 FY2025" or None


class VarianceComparison(BaseModel):
    """Variance comparison against a prior period."""

    comparison_type: Literal["prior_quarter", "same_quarter_prior_year"]
    comparison_period_name: str | None
    has_data: bool
    variances: list[FieldVariance]


class VarianceAnalysisResponse(BaseModel):
    """Complete variance analysis."""

    session_id: UUID
    current_period: str
    prior_quarter: VarianceComparison
    same_quarter_prior_year: VarianceComparison


# =============================================================================
# Export Schemas
# =============================================================================


class ExportRequest(BaseModel):
    """Request to export BAS working papers."""

    format: Literal["pdf", "excel", "csv"] = "pdf"
    include_lodgement_summary: bool = True


class ExportResponse(BaseModel):
    """Export response metadata."""

    filename: str
    content_type: str
    size_bytes: int


# =============================================================================
# Field Transaction Drilldown Schemas
# =============================================================================


class BASFieldTransaction(BaseModel):
    """A single transaction contributing to a BAS field."""

    id: str
    source: Literal["invoice", "bank_transaction"]
    date: date
    reference: str | None
    description: str
    contact_name: str | None
    line_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    tax_type: str | None


class BASFieldTransactionsResponse(BaseModel):
    """Response with transactions for a specific BAS field."""

    session_id: UUID
    field_name: str
    field_label: str
    period_start: date
    period_end: date
    total_amount: Decimal
    transaction_count: int
    transactions: list[BASFieldTransaction]


# =============================================================================
# Lodgement Schemas (Spec 011)
# =============================================================================


class LodgementRecordRequest(BaseModel):
    """Request to record BAS lodgement."""

    lodgement_date: date = Field(..., description="Date when BAS was lodged")
    lodgement_method: Literal["ATO_PORTAL", "XERO", "OTHER"] = Field(
        ..., description="Method used to lodge BAS"
    )
    lodgement_method_description: str | None = Field(
        None,
        max_length=255,
        description="Required when lodgement_method is OTHER",
    )
    ato_reference_number: str | None = Field(
        None, max_length=50, description="ATO lodgement reference number"
    )
    lodgement_notes: str | None = Field(None, description="Additional notes about the lodgement")

    @model_validator(mode="after")
    def validate_other_method(self) -> Self:
        """Validate that OTHER method has a description."""
        if self.lodgement_method == "OTHER" and not self.lodgement_method_description:
            raise ValueError("Description is required when lodgement method is OTHER")
        return self


class LodgementUpdateRequest(BaseModel):
    """Request to update lodgement details."""

    ato_reference_number: str | None = Field(
        None, max_length=50, description="ATO lodgement reference number"
    )
    lodgement_notes: str | None = Field(None, description="Additional notes about the lodgement")


class LodgementSummaryResponse(BaseModel):
    """Lodgement summary for a BAS session."""

    session_id: UUID
    is_lodged: bool
    lodged_at: datetime | None
    lodged_by: UUID | None
    lodged_by_name: str | None
    lodgement_method: str | None
    lodgement_method_description: str | None
    ato_reference_number: str | None
    lodgement_notes: str | None


class ApproachingDeadline(BaseModel):
    """BAS session with approaching deadline."""

    session_id: UUID
    connection_id: UUID
    client_name: str
    period_display_name: str
    due_date: date
    days_remaining: int
    status: str


class DeadlineNotificationSettings(BaseModel):
    """User preferences for deadline notifications."""

    enabled: bool = True
    days_before: list[int] = Field(default=[7, 3, 1])
    email_enabled: bool = False


class NotificationResult(BaseModel):
    """Result of deadline notification check."""

    sessions_checked: int
    notifications_sent: int
    emails_sent: int


class LodgementField(BaseModel):
    """A single BAS field for ATO lodgement summary."""

    field_code: str
    field_description: str
    amount: int  # Whole dollars per ATO requirements


# =============================================================================
# Lodgement Workboard Schemas (Spec 011 - User Story 8)
# =============================================================================


class LodgementWorkboardItem(BaseModel):
    """Single item in lodgement workboard."""

    connection_id: UUID
    client_name: str
    period_id: UUID
    period_display_name: str
    quarter: int | None
    financial_year: str
    due_date: date
    days_remaining: int
    session_id: UUID | None
    session_status: str | None
    is_lodged: bool
    lodged_at: datetime | None
    urgency: Literal["overdue", "critical", "warning", "normal"]


class LodgementWorkboardResponse(BaseModel):
    """Response for lodgement workboard."""

    items: list[LodgementWorkboardItem]
    total: int
    page: int
    limit: int
    total_pages: int


class LodgementWorkboardSummaryResponse(BaseModel):
    """Summary statistics for workboard."""

    total_periods: int
    overdue: int
    due_this_week: int
    due_this_month: int
    lodged: int
    not_started: int


# =============================================================================
# Tax Code Resolution Schemas (Spec 046)
# =============================================================================

# Valid tax types that can be used for overrides (non-excluded from TAX_TYPE_MAPPING)
VALID_TAX_TYPES = {
    "OUTPUT",
    "INPUT",
    "INPUTTAXED",
    "CAPEXINPUT",
    "EXEMPTCAPITAL",
    "EXEMPTOUTPUT",
    "EXEMPTEXPENSES",
    "EXEMPTEXPORT",
    "GSTONIMPORTS",
    "GSTONCAPIMPORTS",
    "BASEXCLUDED",
}


class TaxCodeSuggestionResponse(BaseModel):
    """Single tax code suggestion."""

    id: UUID
    source_type: str
    source_id: UUID
    line_item_index: int
    line_item_id: str | None
    original_tax_type: str
    suggested_tax_type: str | None
    applied_tax_type: str | None
    confidence_score: Decimal | None
    confidence_tier: str | None
    suggestion_basis: str | None
    status: str
    resolved_by: UUID | None
    resolved_at: datetime | None
    dismissal_reason: str | None
    account_code: str | None
    account_name: str | None
    description: str | None
    line_amount: Decimal | None
    tax_amount: Decimal | None
    contact_name: str | None
    transaction_date: date | None

    model_config = {"from_attributes": True}


class TaxCodeSuggestionSummaryResponse(BaseModel):
    """Summary for the exclusion banner."""

    excluded_count: int
    excluded_amount: Decimal
    resolved_count: int
    unresolved_count: int
    has_suggestions: bool
    high_confidence_pending: int
    can_bulk_approve: bool
    blocks_approval: bool


class TaxCodeSuggestionListResponse(BaseModel):
    """List of tax code suggestions with summary."""

    suggestions: list[TaxCodeSuggestionResponse]
    summary: TaxCodeSuggestionSummaryResponse


class GenerateSuggestionsResponse(BaseModel):
    """Result of suggestion generation."""

    generated: int
    skipped_already_resolved: int
    breakdown: dict[str, int]


class ApproveSuggestionRequest(BaseModel):
    """Request to approve a suggestion."""

    notes: str | None = None


class RejectSuggestionRequest(BaseModel):
    """Request to reject a suggestion."""

    reason: str | None = None


class OverrideSuggestionRequest(BaseModel):
    """Request to override a suggestion with a different tax code."""

    tax_type: str = Field(..., description="Valid Xero tax type")
    reason: str | None = None

    @model_validator(mode="after")
    def validate_tax_type(self) -> Self:
        """Validate tax_type is a valid non-excluded type."""
        if self.tax_type.upper() not in VALID_TAX_TYPES:
            raise ValueError(
                f"'{self.tax_type}' is not a valid tax type. "
                f"Must be one of: {', '.join(sorted(VALID_TAX_TYPES))}"
            )
        self.tax_type = self.tax_type.upper()
        return self


class DismissSuggestionRequest(BaseModel):
    """Request to dismiss a suggestion (confirm exclusion is correct)."""

    reason: str | None = None


class BulkApproveRequest(BaseModel):
    """Request to bulk-approve suggestions by confidence threshold."""

    min_confidence: Decimal | None = Field(None, ge=0, le=1)
    confidence_tier: str | None = None

    @model_validator(mode="after")
    def validate_at_least_one(self) -> Self:
        """At least one filter must be provided."""
        if self.min_confidence is None and self.confidence_tier is None:
            raise ValueError("At least one of min_confidence or confidence_tier must be provided")
        return self


class BulkApproveResponse(BaseModel):
    """Result of bulk approval."""

    approved_count: int
    suggestion_ids: list[UUID]


class RecalculateResponse(BaseModel):
    """Result of BAS recalculation after applying tax code resolutions."""

    applied_count: int
    recalculation: dict[str, Decimal]


class SuggestionResolutionResponse(BaseModel):
    """Response after resolving a single suggestion."""

    id: UUID
    status: str
    applied_tax_type: str | None
    resolved_by: UUID | None
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class ConflictResponse(BaseModel):
    """A single re-sync conflict."""

    override_id: UUID
    source_type: str
    source_id: UUID
    line_item_index: int
    override_tax_type: str
    xero_new_tax_type: str | None
    description: str | None
    line_amount: Decimal | None
    account_code: str | None
    detected_at: datetime | None


class ConflictListResponse(BaseModel):
    """List of re-sync conflicts."""

    conflicts: list[ConflictResponse]
    total: int


class ResolveConflictRequest(BaseModel):
    """Request to resolve a re-sync conflict."""

    resolution: Literal["keep_override", "accept_xero"] = Field(
        ..., description="keep_override or accept_xero"
    )
    reason: str | None = None


class ResolveConflictResponse(BaseModel):
    """Result of conflict resolution."""

    override_id: UUID
    resolution: str
    applied_tax_type: str


# ---------------------------------------------------------------------------
# Split management (Spec 049 line-items extension)
# ---------------------------------------------------------------------------


class TaxCodeOverrideWithSplitResponse(BaseModel):
    """TaxCodeOverride row including split fields, returned by split endpoints."""

    id: UUID
    source_type: str
    source_id: UUID
    line_item_index: int
    original_tax_type: str
    override_tax_type: str
    writeback_status: str
    is_new_split: bool
    is_deleted: bool = False
    line_amount: Decimal | None = None
    line_description: str | None = None
    line_account_code: str | None = None
    is_active: bool
    applied_at: datetime

    model_config = {"from_attributes": True}


class SplitCreateRequest(BaseModel):
    """Create or upsert a line item override on a bank transaction.

    - is_new_split=True (default): add a new line item (line_amount required).
    - is_new_split=False: edit or delete an existing original line item.
    - is_deleted=True with is_new_split=False: remove that original from the Xero payload.
    """

    line_item_index: int = Field(..., ge=0)
    override_tax_type: str = Field(..., min_length=1)
    line_amount: Decimal | None = Field(None, gt=0)
    line_description: str | None = None
    line_account_code: str | None = None
    is_new_split: bool = True
    is_deleted: bool = False

    @model_validator(mode="after")
    def validate_new_split_requires_amount(self) -> "SplitCreateRequest":
        if self.is_new_split and self.line_amount is None:
            raise ValueError("line_amount is required when is_new_split=True")
        return self


class SplitUpdateRequest(BaseModel):
    """Update an existing split or line item override."""

    override_tax_type: str | None = None
    line_amount: Decimal | None = Field(None, gt=0)
    line_description: str | None = None
    line_account_code: str | None = None
    is_deleted: bool | None = None


class SplitValidationError(BaseModel):
    """422 response body for split balance violations."""

    detail: str
    expected_total: Decimal | None = None
    actual_total: Decimal | None = None


class XeroLineItemView(BaseModel):
    """A single line item as stored on the Xero document (read-only view)."""

    index: int
    tax_type: str | None = None
    line_amount: Decimal | None = None
    description: str | None = None
    account_code: str | None = None


class TransactionSplitsResponse(BaseModel):
    """Combined response for GET .../splits: original Xero line items + any overrides."""

    original_line_items: list[XeroLineItemView]
    overrides: list[TaxCodeOverrideWithSplitResponse]

