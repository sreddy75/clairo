"""Pydantic schemas for clients module.

CRITICAL: In Clairo, "client" = XeroConnection = one business = one BAS to lodge.
XeroClient = contacts (customers/suppliers) within a business.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BASStatus(str, Enum):
    """BAS readiness status for a client business."""

    READY = "ready"
    NEEDS_REVIEW = "needs_review"
    NO_ACTIVITY = "no_activity"
    MISSING_DATA = "missing_data"


class ContactType(str, Enum):
    """Type of contact."""

    CUSTOMER = "customer"
    SUPPLIER = "supplier"
    BOTH = "both"


class InvoiceType(str, Enum):
    """Type of invoice."""

    ACCREC = "accrec"  # Sales
    ACCPAY = "accpay"  # Purchases


class InvoiceStatus(str, Enum):
    """Status of invoice."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    AUTHORISED = "authorised"
    PAID = "paid"
    VOIDED = "voided"
    DELETED = "deleted"


class TransactionType(str, Enum):
    """Type of bank transaction."""

    RECEIVE = "receive"
    SPEND = "spend"
    RECEIVE_OVERPAYMENT = "receive_overpayment"
    SPEND_OVERPAYMENT = "spend_overpayment"
    RECEIVE_PREPAYMENT = "receive_prepayment"
    SPEND_PREPAYMENT = "spend_prepayment"


# =============================================================================
# Practice Client Schemas (Spec 058)
# =============================================================================


class PracticeClientCreate(BaseModel):
    """Schema for creating a non-Xero client manually."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255, description="Client business name")
    abn: str | None = Field(None, max_length=11, description="Australian Business Number")
    accounting_software: str = Field(
        ..., description="Software type: quickbooks, myob, email, other"
    )
    assigned_user_id: UUID | None = Field(None, description="Team member to assign")
    notes: str | None = Field(None, max_length=5000, description="Persistent client notes")

    @field_validator("abn")
    @classmethod
    def validate_abn(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip().replace(" ", "")
            if not v:
                return None
            if not v.isdigit():
                raise ValueError("ABN must contain only digits")
        return v

    @field_validator("accounting_software")
    @classmethod
    def validate_software(cls, v: str) -> str:
        allowed = {"quickbooks", "myob", "email", "other"}
        if v not in allowed:
            raise ValueError(f"Must be one of: {', '.join(sorted(allowed))}")
        return v


class PracticeClientUpdate(BaseModel):
    """Schema for updating a practice client."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=255)
    abn: str | None = Field(None, max_length=11)
    assigned_user_id: UUID | None = None
    gst_reporting_basis: str | None = Field(
        None,
        description="GST reporting basis: 'cash' or 'accrual'",
    )

    @field_validator("gst_reporting_basis")
    @classmethod
    def validate_gst_basis(cls, v: str | None) -> str | None:
        if v is not None and v not in {"cash", "accrual"}:
            raise ValueError("gst_reporting_basis must be 'cash' or 'accrual'")
        return v


class PracticeClientResponse(BaseModel):
    """Full response for a practice client."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    abn: str | None = None
    accounting_software: str
    xero_connection_id: UUID | None = None
    has_xero_connection: bool = False
    assigned_user_id: UUID | None = None
    assigned_user_name: str | None = None
    notes: str | None = None
    notes_preview: str | None = None
    notes_updated_at: datetime | None = None
    notes_updated_by_name: str | None = None
    manual_status: str | None = None
    # GST basis (Spec 062)
    gst_reporting_basis: str | None = None
    gst_basis_updated_at: datetime | None = None
    gst_basis_updated_by: UUID | None = None
    created_at: datetime


class PracticeClientAssignRequest(BaseModel):
    """Schema for assigning a team member to a client."""

    model_config = ConfigDict(extra="forbid")

    assigned_user_id: UUID | None = Field(
        ..., description="Team member ID, or null to unassign"
    )


class PracticeClientBulkAssignRequest(BaseModel):
    """Schema for bulk-assigning team members."""

    model_config = ConfigDict(extra="forbid")

    client_ids: list[UUID] = Field(..., min_length=1, max_length=100)
    assigned_user_id: UUID | None = Field(
        ..., description="Team member ID, or null to unassign all"
    )


class BulkAssignResponse(BaseModel):
    """Response for bulk assignment."""

    updated_count: int
    clients: list[PracticeClientResponse]


class PracticeClientNotesUpdate(BaseModel):
    """Schema for updating persistent client notes."""

    model_config = ConfigDict(extra="forbid")

    notes: str = Field(..., max_length=5000, description="Note content (empty string to clear)")


class ManualStatusUpdate(BaseModel):
    """Schema for updating BAS status on non-Xero clients."""

    model_config = ConfigDict(extra="forbid")

    manual_status: str = Field(..., description="not_started, in_progress, completed, lodged")

    @field_validator("manual_status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"not_started", "in_progress", "completed", "lodged"}
        if v not in allowed:
            raise ValueError(f"Must be one of: {', '.join(sorted(allowed))}")
        return v


class NoteHistoryEntry(BaseModel):
    """Single entry in note change history."""

    model_config = ConfigDict(from_attributes=True)

    note_text: str
    edited_by_name: str | None = None
    edited_at: datetime


class NoteHistoryResponse(BaseModel):
    """Response for note change history."""

    history: list[NoteHistoryEntry]


# =============================================================================
# Client Exclusion Schemas (Spec 058)
# =============================================================================


class ClientExclusionCreate(BaseModel):
    """Schema for excluding a client from a quarter."""

    model_config = ConfigDict(extra="forbid")

    quarter: int = Field(..., ge=1, le=4, description="Quarter number (1-4)")
    fy_year: str = Field(..., description="Financial year (e.g., '2025-26')")
    reason: str | None = Field(
        None,
        description="Reason: dormant, lodged_externally, gst_cancelled, left_practice, other",
    )
    reason_detail: str | None = Field(None, max_length=500, description="Free text (for 'other')")


class ClientExclusionResponse(BaseModel):
    """Response for a client exclusion."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    quarter: int
    fy_year: str
    reason: str | None = None
    reason_detail: str | None = None
    excluded_by_name: str | None = None
    excluded_at: datetime


class ClientExclusionReversedResponse(BaseModel):
    """Response when an exclusion is reversed."""

    id: UUID
    reversed_at: datetime
    reversed_by_name: str | None = None


class ClientExclusionBrief(BaseModel):
    """Brief exclusion info for dashboard display."""

    id: UUID
    reason: str | None = None
    excluded_by_name: str | None = None
    excluded_at: datetime


# =============================================================================
# Client Detail Schemas
# =============================================================================


class ClientDetailResponse(BaseModel):
    """Detailed view of a client business (XeroConnection)."""

    id: UUID
    organization_name: str
    xero_tenant_id: str
    status: str
    last_full_sync_at: datetime | None
    bas_status: BASStatus

    # Contact info (from XPM client if linked)
    contact_email: str | None = Field(default=None, description="Primary contact email")

    # Financial summary for quarter (GST)
    total_sales: Decimal = Field(default=Decimal("0.00"))
    total_purchases: Decimal = Field(default=Decimal("0.00"))
    gst_collected: Decimal = Field(default=Decimal("0.00"))
    gst_paid: Decimal = Field(default=Decimal("0.00"))
    net_gst: Decimal = Field(default=Decimal("0.00"))
    invoice_count: int = 0
    transaction_count: int = 0
    contact_count: int = 0

    # Payroll/PAYG summary for quarter
    has_payroll: bool = False
    total_wages: Decimal = Field(default=Decimal("0.00"), description="BAS W1")
    total_tax_withheld: Decimal = Field(default=Decimal("0.00"), description="BAS W2/4")
    total_super: Decimal = Field(default=Decimal("0.00"))
    pay_run_count: int = 0
    employee_count: int = 0
    last_payroll_sync_at: datetime | None = None

    # Quality score summary
    quality_score: Decimal | None = Field(default=None, description="Overall quality %")
    critical_issues: int = Field(default=0, description="Count of critical issues")

    # Quarter info
    quarter_label: str
    quarter: int
    fy_year: int

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Contact Schemas
# =============================================================================


class ContactItem(BaseModel):
    """Single contact (XeroClient) within a business."""

    id: UUID
    name: str
    email: str | None = None
    contact_number: str | None = None
    abn: str | None = None
    contact_type: ContactType
    is_active: bool = True
    addresses: list[dict[str, Any]] | None = None
    phones: list[dict[str, Any]] | None = None

    model_config = ConfigDict(from_attributes=True)


class ContactListResponse(BaseModel):
    """Paginated list of contacts for a client business."""

    contacts: list[ContactItem]
    total: int
    page: int
    limit: int


# =============================================================================
# Invoice Schemas
# =============================================================================


class InvoiceLineItem(BaseModel):
    """Line item within an invoice."""

    description: str | None = None
    quantity: Decimal | None = None
    unit_amount: Decimal | None = None
    account_code: str | None = None
    tax_type: str | None = None
    line_amount: Decimal | None = None

    model_config = ConfigDict(from_attributes=True)


class InvoiceItem(BaseModel):
    """Single invoice for a client business."""

    id: UUID
    invoice_number: str | None = None
    invoice_type: InvoiceType
    contact_name: str | None = None
    status: InvoiceStatus
    issue_date: datetime
    due_date: datetime | None = None
    subtotal: Decimal = Field(default=Decimal("0.00"))
    tax_amount: Decimal = Field(default=Decimal("0.00"))
    total_amount: Decimal = Field(default=Decimal("0.00"))
    currency: str = "AUD"
    line_items: list[InvoiceLineItem] | None = None

    model_config = ConfigDict(from_attributes=True)


class InvoiceListResponse(BaseModel):
    """Paginated list of invoices for a client business."""

    invoices: list[InvoiceItem]
    total: int
    page: int
    limit: int


# =============================================================================
# Transaction Schemas
# =============================================================================


class TransactionItem(BaseModel):
    """Single bank transaction for a client business."""

    id: UUID
    transaction_type: TransactionType
    contact_name: str | None = None
    status: str
    transaction_date: datetime
    reference: str | None = None
    subtotal: Decimal = Field(default=Decimal("0.00"))
    tax_amount: Decimal = Field(default=Decimal("0.00"))
    total_amount: Decimal = Field(default=Decimal("0.00"))

    model_config = ConfigDict(from_attributes=True)


class TransactionListResponse(BaseModel):
    """Paginated list of transactions for a client business."""

    transactions: list[TransactionItem]
    total: int
    page: int
    limit: int


# =============================================================================
# Summary Schemas
# =============================================================================


class FinancialSummaryResponse(BaseModel):
    """Financial summary for a client business in a quarter."""

    quarter_label: str
    quarter: int
    fy_year: int

    # GST data
    total_sales: Decimal = Field(default=Decimal("0.00"))
    total_purchases: Decimal = Field(default=Decimal("0.00"))
    gst_collected: Decimal = Field(default=Decimal("0.00"))
    gst_paid: Decimal = Field(default=Decimal("0.00"))
    net_gst: Decimal = Field(default=Decimal("0.00"))
    invoice_count: int = 0
    transaction_count: int = 0

    # Payroll/PAYG data
    has_payroll: bool = False
    total_wages: Decimal = Field(default=Decimal("0.00"), description="BAS W1")
    total_tax_withheld: Decimal = Field(default=Decimal("0.00"), description="BAS W2/4")
    total_super: Decimal = Field(default=Decimal("0.00"))
    pay_run_count: int = 0
    employee_count: int = 0


# =============================================================================
# Employee Schemas (Payroll)
# =============================================================================


class EmployeeStatus(str, Enum):
    """Employment status."""

    ACTIVE = "active"
    TERMINATED = "terminated"


class EmployeeItem(BaseModel):
    """Single employee from Xero Payroll."""

    id: UUID
    xero_employee_id: str
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    status: EmployeeStatus
    start_date: datetime | None = None
    termination_date: datetime | None = None
    job_title: str | None = None

    model_config = ConfigDict(from_attributes=True)


class EmployeeListResponse(BaseModel):
    """Paginated list of employees for a client business."""

    employees: list[EmployeeItem]
    total: int
    page: int
    limit: int


# =============================================================================
# Pay Run Schemas (Payroll)
# =============================================================================


class PayRunStatus(str, Enum):
    """Pay run status."""

    DRAFT = "draft"
    POSTED = "posted"


class PayRunItem(BaseModel):
    """Single pay run from Xero Payroll."""

    id: UUID
    xero_pay_run_id: str
    status: PayRunStatus
    period_start: datetime | None = None
    period_end: datetime | None = None
    payment_date: datetime | None = None
    total_wages: Decimal = Field(default=Decimal("0.00"))
    total_tax: Decimal = Field(default=Decimal("0.00"))
    total_super: Decimal = Field(default=Decimal("0.00"))
    total_net_pay: Decimal = Field(default=Decimal("0.00"))
    employee_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class PayRunListResponse(BaseModel):
    """Paginated list of pay runs for a client business."""

    pay_runs: list[PayRunItem]
    total: int
    page: int
    limit: int
