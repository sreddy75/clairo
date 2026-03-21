"""Pydantic schemas for clients module.

CRITICAL: In Clairo, "client" = XeroConnection = one business = one BAS to lodge.
XeroClient = contacts (customers/suppliers) within a business.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
