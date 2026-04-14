"""Pydantic schemas for Xero integration.

Request and response schemas for:
- OAuth flow (auth URL, callback)
- Connection management (list, get, disconnect)
- Token operations (refresh)
- Sync operations (initiate, status, history)
- Synced entities (clients, invoices, transactions, accounts)
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.integrations.xero.models import (
    XeroAccountClass,
    XeroConnectionStatus,
    XeroContactType,
    XeroCreditNoteStatus,
    XeroCreditNoteType,
    XeroInvoiceStatus,
    XeroInvoiceType,
    XeroJournalSourceType,
    XeroManualJournalStatus,
    XeroOverpaymentStatus,
    XeroPaymentStatus,
    XeroPaymentType,
    XeroPrepaymentStatus,
    XeroSyncStatus,
    XeroSyncType,
    XpmClientConnectionStatus,
)

# =============================================================================
# Request Schemas
# =============================================================================


class XeroConnectRequest(BaseModel):
    """Request to initiate Xero OAuth flow."""

    redirect_uri: str = Field(
        ...,
        description="Frontend URI to redirect after OAuth completion",
        examples=["http://localhost:3000/settings/integrations/xero/callback"],
    )


class XeroCallbackRequest(BaseModel):
    """OAuth callback parameters from Xero redirect."""

    code: str = Field(
        ...,
        description="Authorization code from Xero",
        min_length=1,
    )
    state: str = Field(
        ...,
        description="State parameter for CSRF validation",
        min_length=1,
    )


class XeroDisconnectRequest(BaseModel):
    """Request to disconnect a Xero organization."""

    reason: str | None = Field(
        default=None,
        description="Optional reason for disconnecting (for audit)",
        max_length=500,
    )


class XeroDeleteConnectionRequest(BaseModel):
    """Request to permanently delete a Xero connection and all associated data."""

    confirmation_name: str = Field(
        ...,
        description="Organization name typed by user to confirm deletion",
        min_length=1,
    )
    reason: str | None = Field(
        default=None,
        description="Optional reason for deletion (for audit)",
        max_length=500,
    )


class XeroConnectionDataCounts(BaseModel):
    """Counts of data associated with a connection, shown before deletion."""

    clients: int = 0
    invoices: int = 0
    bank_transactions: int = 0
    payments: int = 0
    credit_notes: int = 0
    journals: int = 0
    accounts: int = 0
    employees: int = 0
    bas_periods: int = 0
    quality_scores: int = 0
    sync_jobs: int = 0


# =============================================================================
# Response Schemas
# =============================================================================


class XeroAuthUrlResponse(BaseModel):
    """Response containing OAuth authorization URL."""

    auth_url: str = Field(
        ...,
        description="Full Xero authorization URL to redirect user to",
    )
    state: str = Field(
        ...,
        description="State parameter for client-side tracking (optional)",
    )


class XeroConnectionSummary(BaseModel):
    """Summary of a Xero connection for list views."""

    id: UUID
    organization_name: str
    status: XeroConnectionStatus
    connected_at: datetime
    last_full_sync_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class XeroConnectionResponse(BaseModel):
    """Full details of a Xero connection."""

    id: UUID
    xero_tenant_id: str
    organization_name: str
    status: XeroConnectionStatus
    scopes: list[str]
    connected_at: datetime
    last_used_at: datetime | None
    last_full_sync_at: datetime | None = None

    # Rate limit info (included for visibility)
    rate_limit_daily_remaining: int
    rate_limit_minute_remaining: int

    model_config = ConfigDict(from_attributes=True)


class XeroConnectionListResponse(BaseModel):
    """Response for listing Xero connections."""

    connections: list[XeroConnectionSummary]
    total: int


class XeroCallbackSuccessResponse(BaseModel):
    """Response after successful OAuth callback."""

    connection: XeroConnectionSummary
    message: str = Field(
        default="Successfully connected to Xero",
        description="Success message for UI",
    )


class XeroCallbackResponse(BaseModel):
    """Response after OAuth callback processing."""

    connection_id: UUID = Field(..., description="ID of the created/updated connection")
    organization_name: str = Field(..., description="Name of the connected Xero organization")
    status: XeroConnectionStatus = Field(..., description="Connection status")
    message: str = Field(
        default="Successfully connected to Xero",
        description="Success message for UI",
    )


# =============================================================================
# Internal Schemas (not exposed via API)
# =============================================================================


class TokenResponse(BaseModel):
    """Token response from Xero token endpoint."""

    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str
    scope: str

    @property
    def scopes_list(self) -> list[str]:
        """Get scopes as a list."""
        return self.scope.split()


class XeroOrganization(BaseModel):
    """Xero organization from connections endpoint.

    Represents a Xero organization that the user has authorized access to.
    The authEventId groups organizations authorized in the same OAuth flow
    (important for bulk connections).
    """

    id: str = Field(..., alias="tenantId")
    auth_event_id: str | None = Field(default=None, alias="authEventId")
    tenant_type: str = Field(..., alias="tenantType")
    tenant_name: str | None = Field(default=None, alias="tenantName")
    created_date_utc: datetime | None = Field(default=None, alias="createdDateUtc")
    updated_date_utc: datetime | None = Field(default=None, alias="updatedDateUtc")

    model_config = ConfigDict(populate_by_name=True)

    @property
    def display_name(self) -> str:
        """Get display name, falling back to ID if name not available."""
        return self.tenant_name or f"Organization {self.id[:8]}..."

    @property
    def is_organisation(self) -> bool:
        """Check if this is an ORGANISATION (not PRACTICE)."""
        return self.tenant_type.upper() == "ORGANISATION"

    @property
    def is_practice(self) -> bool:
        """Check if this is a PRACTICE (XPM)."""
        return self.tenant_type.upper() == "PRACTICE"


class XeroOrganisationDetails(BaseModel):
    """Detailed Xero organisation info from Organisation endpoint.

    Maps to Xero's Organisation API response which provides
    entity type, tax number (ABN), and registration details.
    """

    organisation_id: str = Field(..., alias="OrganisationID")
    name: str = Field(..., alias="Name")
    legal_name: str | None = Field(default=None, alias="LegalName")
    short_code: str | None = Field(default=None, alias="ShortCode")

    # Entity classification
    organisation_type: str | None = Field(default=None, alias="OrganisationType")
    # Values: COMPANY, CHARITY, CLUBSOCIETY, PARTNERSHIP, PRACTICE, PERSON, SOLETRADER, TRUST

    # Tax/Registration numbers (ABN/ACN for AU)
    tax_number: str | None = Field(default=None, alias="TaxNumber")  # ABN for AU
    registration_number: str | None = Field(default=None, alias="RegistrationNumber")  # ACN for AU

    # Location
    country_code: str | None = Field(default=None, alias="CountryCode")
    base_currency: str | None = Field(default=None, alias="BaseCurrency")
    timezone: str | None = Field(default=None, alias="Timezone")

    # Status
    organisation_status: str | None = Field(default=None, alias="OrganisationStatus")
    is_demo_company: bool = Field(default=False, alias="IsDemoCompany")

    # Financial year
    financial_year_end_day: int | None = Field(default=None, alias="FinancialYearEndDay")
    financial_year_end_month: int | None = Field(default=None, alias="FinancialYearEndMonth")

    # Sales tax (GST) settings
    sales_tax_basis: str | None = Field(default=None, alias="SalesTaxBasis")
    sales_tax_period: str | None = Field(default=None, alias="SalesTaxPeriod")

    model_config = ConfigDict(populate_by_name=True)

    @property
    def entity_type_display(self) -> str | None:
        """Get human-readable entity type."""
        type_map = {
            "COMPANY": "Company",
            "SOLETRADER": "Sole Trader",
            "PARTNERSHIP": "Partnership",
            "TRUST": "Trust",
            "CHARITY": "Charity",
            "CLUBSOCIETY": "Club/Society",
            "PRACTICE": "Practice",
            "PERSON": "Individual",
        }
        return type_map.get(self.organisation_type or "", self.organisation_type)

    @property
    def is_gst_registered(self) -> bool:
        """Check if likely GST registered (has ABN and sales tax settings)."""
        return bool(self.tax_number and self.sales_tax_basis)


class XeroConnectionCreate(BaseModel):
    """Internal schema for creating a connection."""

    tenant_id: UUID
    xero_tenant_id: str
    organization_name: str
    access_token: str  # Will be encrypted before storage
    refresh_token: str  # Will be encrypted before storage
    token_expires_at: datetime
    scopes: list[str]
    connected_by: UUID | None = None
    has_payroll_access: bool = False
    auth_event_id: str | None = None
    connection_type: str = "practice"

    @property
    def has_payroll_scopes(self) -> bool:
        """Check if payroll scopes are included."""
        payroll_scopes = ["payroll.employees", "payroll.payruns"]
        return all(scope in self.scopes for scope in payroll_scopes)


class XeroConnectionUpdate(BaseModel):
    """Internal schema for updating a connection."""

    access_token: str | None = None
    refresh_token: str | None = None
    token_expires_at: datetime | None = None
    status: XeroConnectionStatus | None = None
    rate_limit_daily_remaining: int | None = None
    rate_limit_minute_remaining: int | None = None
    rate_limit_reset_at: datetime | None = None
    last_used_at: datetime | None = None
    # Sync timestamps
    last_contacts_sync_at: datetime | None = None
    last_invoices_sync_at: datetime | None = None
    last_transactions_sync_at: datetime | None = None
    last_accounts_sync_at: datetime | None = None
    last_full_sync_at: datetime | None = None
    sync_in_progress: bool | None = None
    # Spec 043: New per-entity sync timestamps
    last_credit_notes_sync_at: datetime | None = None
    last_payments_sync_at: datetime | None = None
    last_overpayments_sync_at: datetime | None = None
    last_prepayments_sync_at: datetime | None = None
    last_journals_sync_at: datetime | None = None
    last_manual_journals_sync_at: datetime | None = None
    # Payroll
    has_payroll_access: bool | None = None
    last_payroll_sync_at: datetime | None = None
    last_employees_sync_at: datetime | None = None


# =============================================================================
# Sync Request/Response Schemas
# =============================================================================


class XeroSyncRequest(BaseModel):
    """Request to initiate a sync operation."""

    sync_type: XeroSyncType = Field(
        default=XeroSyncType.FULL,
        description="Type of sync to perform",
    )
    force_full: bool = Field(
        default=False,
        description="Force full sync even if incremental is available",
    )


class XeroSyncJobResponse(BaseModel):
    """Response containing sync job details."""

    id: UUID
    connection_id: UUID
    sync_type: XeroSyncType
    status: XeroSyncStatus
    started_at: datetime | None
    completed_at: datetime | None
    records_processed: int
    records_created: int
    records_updated: int
    records_failed: int
    error_message: str | None
    progress_details: dict[str, Any] | None
    created_at: datetime
    # Phased sync fields (Spec 043: Progressive Sync)
    sync_phase: int | None = None
    triggered_by: str = "user"

    model_config = ConfigDict(from_attributes=True)


class XeroSyncHistoryResponse(BaseModel):
    """Response for listing sync job history."""

    jobs: list[XeroSyncJobResponse]
    total: int
    limit: int
    offset: int


class SyncResult(BaseModel):
    """Result of a sync operation (internal use)."""

    sync_type: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    records_processed: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_failed: int = 0
    error_message: str | None = None


# =============================================================================
# Synced Entity Response Schemas
# =============================================================================


class XeroClientResponse(BaseModel):
    """Response for a synced Xero client."""

    id: UUID
    connection_id: UUID
    xero_contact_id: str
    name: str
    email: str | None
    contact_number: str | None
    abn: str | None
    contact_type: XeroContactType
    is_active: bool
    addresses: list[dict[str, Any]] | None
    phones: list[dict[str, Any]] | None
    xero_updated_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class XeroClientListResponse(BaseModel):
    """Response for listing synced clients."""

    clients: list[XeroClientResponse]
    total: int
    limit: int
    offset: int


class XeroInvoiceLineItem(BaseModel):
    """Line item within an invoice."""

    line_item_id: str | None = None
    description: str | None = None
    quantity: Decimal | None = None
    unit_amount: Decimal | None = None
    line_amount: Decimal | None = None
    account_code: str | None = None
    tax_type: str | None = None
    tax_amount: Decimal | None = None


class XeroInvoiceResponse(BaseModel):
    """Response for a synced Xero invoice."""

    id: UUID
    connection_id: UUID
    client_id: UUID | None
    xero_invoice_id: str
    xero_contact_id: str | None
    invoice_number: str | None
    invoice_type: XeroInvoiceType
    status: XeroInvoiceStatus
    issue_date: datetime
    due_date: datetime | None
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    currency: str
    line_items: list[dict[str, Any]] | None
    xero_updated_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class XeroInvoiceListResponse(BaseModel):
    """Response for listing synced invoices."""

    invoices: list[XeroInvoiceResponse]
    total: int
    limit: int
    offset: int


class XeroBankTransactionResponse(BaseModel):
    """Response for a synced Xero bank transaction."""

    id: UUID
    connection_id: UUID
    client_id: UUID | None
    xero_transaction_id: str
    xero_contact_id: str | None
    xero_bank_account_id: str | None
    transaction_type: str
    status: str
    transaction_date: datetime
    reference: str | None
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    line_items: list[dict[str, Any]] | None
    xero_updated_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class XeroBankTransactionListResponse(BaseModel):
    """Response for listing synced bank transactions."""

    transactions: list[XeroBankTransactionResponse]
    total: int
    limit: int
    offset: int


class XeroAccountResponse(BaseModel):
    """Response for a synced Xero account."""

    id: UUID
    connection_id: UUID
    xero_account_id: str
    account_code: str | None
    account_name: str
    account_type: str
    account_class: XeroAccountClass | None
    default_tax_type: str | None
    is_active: bool
    reporting_code: str | None
    is_bas_relevant: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class XeroAccountListResponse(BaseModel):
    """Response for listing synced accounts."""

    accounts: list[XeroAccountResponse]
    total: int


# =============================================================================
# Client View Schemas (Spec 005)
# =============================================================================


class QuarterInfo(BaseModel):
    """Represents an Australian Financial Year quarter."""

    quarter: int = Field(..., ge=1, le=4, description="Quarter number (1-4)")
    fy_year: int = Field(..., description="Financial year (e.g., 2025 for FY25)")
    label: str = Field(..., description="Display label (e.g., 'Q2 FY25')")
    start_date: datetime = Field(..., description="Quarter start date")
    end_date: datetime = Field(..., description="Quarter end date")


class AvailableQuartersResponse(BaseModel):
    """Response for available quarters selection."""

    quarters: list[QuarterInfo]
    current: QuarterInfo


class ClientFinancialSummaryResponse(BaseModel):
    """Financial summary for a client within a quarter."""

    client_id: UUID
    quarter: int
    fy_year: int
    quarter_label: str = Field(..., description="Display label (e.g., 'Q2 FY25')")

    # Sales (income received from customer)
    total_sales: Decimal = Field(default=Decimal("0.00"), description="Total sales/income")
    gst_collected: Decimal = Field(default=Decimal("0.00"), description="GST collected on sales")

    # Purchases (expenses paid to supplier)
    total_purchases: Decimal = Field(
        default=Decimal("0.00"), description="Total purchases/expenses"
    )
    gst_paid: Decimal = Field(default=Decimal("0.00"), description="GST paid on purchases")

    # Counts
    invoice_count: int = Field(default=0, description="Number of invoices in period")
    transaction_count: int = Field(default=0, description="Number of transactions in period")

    # Net position
    net_gst: Decimal = Field(default=Decimal("0.00"), description="Net GST (collected - paid)")


class XeroClientDetailResponse(XeroClientResponse):
    """Extended client response with connection metadata."""

    organization_name: str = Field(..., description="Xero organization name")
    connection_status: XeroConnectionStatus | None = Field(None, description="Connection status")
    last_synced_at: datetime | None = Field(None, description="When data was last synced")


# =============================================================================
# Payroll Response Schemas (Spec 007)
# =============================================================================


class XeroEmployeeResponse(BaseModel):
    """Response for a synced Xero employee."""

    id: UUID
    xero_employee_id: str
    first_name: str | None
    last_name: str | None
    full_name: str | None
    email: str | None
    status: str
    start_date: datetime | None
    termination_date: datetime | None
    job_title: str | None

    model_config = ConfigDict(from_attributes=True)


class XeroEmployeeListResponse(BaseModel):
    """Response for listing employees."""

    employees: list[XeroEmployeeResponse]
    total: int
    limit: int
    offset: int


class XeroPayRunResponse(BaseModel):
    """Response for a synced Xero pay run."""

    id: UUID
    xero_pay_run_id: str
    status: str
    period_start: datetime | None
    period_end: datetime | None
    payment_date: datetime | None
    total_wages: Decimal
    total_tax: Decimal
    total_super: Decimal
    total_net_pay: Decimal
    employee_count: int

    model_config = ConfigDict(from_attributes=True)


class XeroPayRunListResponse(BaseModel):
    """Response for listing pay runs."""

    pay_runs: list[XeroPayRunResponse]
    total: int
    limit: int
    offset: int


class XeroPayrollSummaryResponse(BaseModel):
    """Payroll summary for BAS (PAYG withholding)."""

    has_payroll: bool = Field(..., description="Whether payroll data is available")
    total_wages: Decimal = Field(default=Decimal("0.00"), description="Total wages (BAS W1)")
    total_tax_withheld: Decimal = Field(
        default=Decimal("0.00"), description="Total tax withheld (BAS W2/4)"
    )
    total_super: Decimal = Field(default=Decimal("0.00"), description="Total superannuation")
    pay_run_count: int = Field(default=0, description="Number of pay runs in period")
    employee_count: int = Field(default=0, description="Number of active employees")
    last_payroll_sync_at: datetime | None = Field(None, description="Last payroll sync timestamp")


class XeroPayrollSyncResponse(BaseModel):
    """Response for payroll sync operation."""

    connection_id: UUID
    status: str = Field(..., description="Sync status (complete, skipped, failed)")
    employees_synced: int = Field(default=0, description="Number of employees synced")
    pay_runs_synced: int = Field(default=0, description="Number of pay runs synced")
    reason: str | None = Field(None, description="Reason if skipped or error message")


# =============================================================================
# XPM Client Schemas (Spec 021 - Client Organization Authorization)
# =============================================================================


class XpmClientCreate(BaseModel):
    """Schema for creating/upserting XPM client from XPM sync.

    Used internally when syncing client list from Xero Practice Manager.
    """

    tenant_id: UUID = Field(..., description="Clairo tenant ID (the accounting practice)")
    xpm_client_id: str = Field(
        ..., min_length=1, max_length=50, description="XPM's unique client identifier"
    )
    name: str = Field(..., min_length=1, max_length=500, description="Client business name")
    abn: str | None = Field(
        default=None, max_length=11, description="Australian Business Number (11 digits)"
    )
    email: str | None = Field(default=None, max_length=255, description="Primary contact email")
    phone: str | None = Field(default=None, max_length=50, description="Primary contact phone")
    address: dict[str, Any] | None = Field(default=None, description="Business address")
    contact_person: str | None = Field(
        default=None, max_length=255, description="Primary contact name"
    )
    xpm_updated_at: datetime | None = Field(
        default=None, description="Last update timestamp from XPM"
    )
    extra_data: dict[str, Any] | None = Field(default=None, description="Additional XPM metadata")


class XpmClientResponse(BaseModel):
    """Response schema for XPM client.

    Represents a client from Xero Practice Manager with their
    Xero organization connection status.
    """

    id: UUID
    tenant_id: UUID
    xpm_client_id: str
    name: str
    abn: str | None = None
    email: str | None = None
    phone: str | None = None
    address: dict[str, Any] | None = None
    contact_person: str | None = None

    # Xero connection fields
    xero_connection_id: UUID | None = None
    xero_org_name: str | None = None
    connection_status: XpmClientConnectionStatus
    xero_connected_at: datetime | None = None

    # Timestamps
    xpm_updated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class XpmClientListResponse(BaseModel):
    """Response for listing XPM clients with pagination."""

    clients: list[XpmClientResponse]
    total: int
    limit: int
    offset: int


class XpmClientConnectionUpdate(BaseModel):
    """Request to update XPM client's Xero connection.

    Used when linking a client to their authorized Xero organization.
    """

    xero_connection_id: UUID = Field(
        ..., description="ID of the XeroConnection to link to this client"
    )
    xero_org_name: str | None = Field(
        default=None, description="Xero organization name (cached for display)"
    )


class XpmClientUnlinkRequest(BaseModel):
    """Request to unlink XPM client from their Xero organization."""

    reason: str | None = Field(
        default=None, max_length=500, description="Optional reason for unlinking (for audit)"
    )


class XpmClientLinkByTenantIdRequest(BaseModel):
    """Request to link XPM client by Xero tenant ID.

    Used when manually matching an unmatched Xero organization to a client.
    """

    xero_tenant_id: str = Field(
        ...,
        description="The Xero organization's tenant ID (from Xero API)",
        min_length=1,
    )


class XpmClientStatusCounts(BaseModel):
    """Count of XPM clients by connection status.

    Useful for dashboard statistics and progress tracking.
    """

    not_connected: int = Field(default=0, description="Clients without Xero org connected")
    connected: int = Field(default=0, description="Clients with Xero org connected")
    disconnected: int = Field(default=0, description="Previously connected, now disconnected")
    no_access: int = Field(default=0, description="Accountant doesn't have access to client's Xero")
    total: int = Field(default=0, description="Total number of XPM clients")


class XpmClientConnectionProgress(BaseModel):
    """Progress summary for client organization connections.

    Shows how many clients have their Xero orgs authorized.
    """

    status_counts: XpmClientStatusCounts
    connection_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Percentage of clients connected (0-1)"
    )
    all_connected: bool = Field(..., description="Whether all clients are connected")


class XpmClientSearchRequest(BaseModel):
    """Request for searching XPM clients."""

    query: str = Field(..., min_length=1, max_length=100, description="Search query (name or ABN)")
    connection_status: XpmClientConnectionStatus | None = Field(
        default=None, description="Filter by connection status"
    )
    limit: int = Field(default=10, ge=1, le=50, description="Max results to return")


class XpmClientConnectXeroRequest(BaseModel):
    """Request to initiate OAuth for a specific client's Xero org.

    Used when accountant wants to authorize access to a client's Xero organization.
    """

    redirect_uri: str = Field(..., description="Frontend URI to redirect after OAuth completion")


class XpmClientConnectXeroResponse(BaseModel):
    """Response with OAuth URL for client Xero authorization."""

    client_id: UUID = Field(..., description="XPM client ID being connected")
    client_name: str = Field(..., description="Client business name")
    authorization_url: str = Field(..., description="Xero OAuth authorization URL")
    state: str = Field(..., description="OAuth state for verification")


# =============================================================================
# Xero Reports Schemas (Spec 023)
# =============================================================================


class ReportCell(BaseModel):
    """A single cell in a report row."""

    value: str | None = Field(
        default=None,
        alias="Value",
        description="Cell value (may be empty)",
    )
    attributes: list[dict[str, str]] = Field(
        default_factory=list,
        alias="Attributes",
        description="Cell attributes (e.g., account ID, contact ID)",
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ReportRow(BaseModel):
    """A row in a Xero report."""

    row_type: str = Field(
        ...,
        alias="RowType",
        description="Row type: Header, Section, Row, SummaryRow",
    )
    title: str | None = Field(
        default=None,
        alias="Title",
        description="Row title (for Section rows)",
    )
    cells: list[ReportCell] = Field(
        default_factory=list,
        alias="Cells",
        description="Cells in this row",
    )
    rows: list["ReportRow"] = Field(
        default_factory=list,
        alias="Rows",
        description="Nested rows (for Section rows)",
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ReportSummary(BaseModel):
    """Summary metrics extracted from a report.

    The specific fields depend on report type. This is a flexible
    container for key metrics.
    """

    model_config = ConfigDict(from_attributes=True, extra="allow")


class ProfitAndLossSummary(ReportSummary):
    """Summary metrics for Profit & Loss report."""

    revenue: Decimal = Field(default=Decimal("0.00"), description="Total revenue")
    other_income: Decimal = Field(default=Decimal("0.00"), description="Other income")
    total_income: Decimal = Field(
        default=Decimal("0.00"), description="Total income (revenue + other)"
    )
    cost_of_sales: Decimal = Field(default=Decimal("0.00"), description="Cost of goods sold")
    gross_profit: Decimal = Field(
        default=Decimal("0.00"), description="Gross profit (income - COGS)"
    )
    operating_expenses: Decimal = Field(default=Decimal("0.00"), description="Operating expenses")
    total_expenses: Decimal = Field(default=Decimal("0.00"), description="Total expenses")
    operating_profit: Decimal = Field(
        default=Decimal("0.00"), description="Operating profit (gross - opex)"
    )
    net_profit: Decimal = Field(default=Decimal("0.00"), description="Net profit (bottom line)")
    gross_margin_pct: float | None = Field(default=None, description="Gross margin percentage")
    net_margin_pct: float | None = Field(default=None, description="Net margin percentage")
    expense_ratio_pct: float | None = Field(
        default=None, description="Expense ratio (expenses / revenue)"
    )


class BalanceSheetSummary(ReportSummary):
    """Summary metrics for Balance Sheet report."""

    current_assets: Decimal = Field(default=Decimal("0.00"), description="Total current assets")
    non_current_assets: Decimal = Field(
        default=Decimal("0.00"), description="Total non-current assets"
    )
    total_assets: Decimal = Field(default=Decimal("0.00"), description="Total assets")
    current_liabilities: Decimal = Field(
        default=Decimal("0.00"), description="Total current liabilities"
    )
    non_current_liabilities: Decimal = Field(
        default=Decimal("0.00"), description="Total non-current liabilities"
    )
    total_liabilities: Decimal = Field(default=Decimal("0.00"), description="Total liabilities")
    equity: Decimal = Field(default=Decimal("0.00"), description="Total equity")
    current_ratio: float | None = Field(
        default=None, description="Current ratio (current assets / current liabilities)"
    )
    debt_to_equity: float | None = Field(default=None, description="Debt to equity ratio")


class AgedReceivablesSummary(ReportSummary):
    """Summary metrics for Aged Receivables report."""

    total: Decimal = Field(default=Decimal("0.00"), description="Total receivables")
    current: Decimal = Field(default=Decimal("0.00"), description="Current (not overdue)")
    overdue_30: Decimal = Field(default=Decimal("0.00"), description="1-30 days overdue")
    overdue_60: Decimal = Field(default=Decimal("0.00"), description="31-60 days overdue")
    overdue_90: Decimal = Field(default=Decimal("0.00"), description="61-90 days overdue")
    overdue_90_plus: Decimal = Field(default=Decimal("0.00"), description="90+ days overdue")
    overdue_total: Decimal = Field(default=Decimal("0.00"), description="Total overdue amount")
    overdue_pct: float | None = Field(default=None, description="Percentage overdue")
    high_risk_contacts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Contacts with significant overdue amounts",
    )


class AgedPayablesSummary(ReportSummary):
    """Summary metrics for Aged Payables report."""

    total: Decimal = Field(default=Decimal("0.00"), description="Total payables")
    current: Decimal = Field(default=Decimal("0.00"), description="Current (not overdue)")
    overdue_30: Decimal = Field(default=Decimal("0.00"), description="1-30 days overdue")
    overdue_60: Decimal = Field(default=Decimal("0.00"), description="31-60 days overdue")
    overdue_90: Decimal = Field(default=Decimal("0.00"), description="61-90 days overdue")
    overdue_90_plus: Decimal = Field(default=Decimal("0.00"), description="90+ days overdue")
    overdue_total: Decimal = Field(default=Decimal("0.00"), description="Total overdue amount")


class TrialBalanceSummary(ReportSummary):
    """Summary metrics for Trial Balance report."""

    total_debits: Decimal = Field(default=Decimal("0.00"), description="Total debit balances")
    total_credits: Decimal = Field(default=Decimal("0.00"), description="Total credit balances")
    is_balanced: bool = Field(default=True, description="Whether debits equal credits")
    account_count: int = Field(default=0, description="Number of accounts with balances")


class BankSummarySummary(ReportSummary):
    """Summary metrics for Bank Summary report."""

    total_opening: Decimal = Field(default=Decimal("0.00"), description="Total opening balance")
    total_received: Decimal = Field(default=Decimal("0.00"), description="Total received")
    total_spent: Decimal = Field(default=Decimal("0.00"), description="Total spent")
    total_closing: Decimal = Field(default=Decimal("0.00"), description="Total closing balance")
    net_movement: Decimal = Field(default=Decimal("0.00"), description="Net cash movement")
    account_count: int = Field(default=0, description="Number of bank accounts")


class BudgetSummarySummary(ReportSummary):
    """Summary metrics for Budget Summary report."""

    total_budget: Decimal = Field(default=Decimal("0.00"), description="Total budgeted amount")
    total_actual: Decimal = Field(default=Decimal("0.00"), description="Total actual amount")
    total_variance: Decimal = Field(
        default=Decimal("0.00"), description="Total variance (actual - budget)"
    )
    variance_pct: float | None = Field(default=None, description="Variance percentage")
    has_budget: bool = Field(default=False, description="Whether a budget is configured")


class ReportResponse(BaseModel):
    """Full response for a single report."""

    id: UUID = Field(..., description="Report record ID")
    report_type: str = Field(..., description="Type of report")
    report_name: str = Field(..., description="Report name from Xero")
    report_titles: list[str] = Field(default_factory=list, description="Report titles from Xero")
    period_key: str = Field(..., description="Period identifier")
    period_start: datetime | None = Field(default=None, description="Period start date")
    period_end: datetime | None = Field(default=None, description="Period end date")
    as_of_date: datetime | None = Field(
        default=None, description="Report as-of date (for point-in-time reports)"
    )
    summary: dict[str, Any] = Field(default_factory=dict, description="Extracted summary metrics")
    rows: list[ReportRow] = Field(default_factory=list, description="Full report rows")
    fetched_at: datetime = Field(..., description="When data was fetched from Xero")
    cache_expires_at: datetime = Field(..., description="When cached data expires")
    is_current_period: bool = Field(default=True, description="Whether this is the current period")
    is_stale: bool = Field(default=False, description="Whether cache has expired")

    model_config = ConfigDict(from_attributes=True)


class ReportStatusItem(BaseModel):
    """Status of a single report type for a connection."""

    report_type: str = Field(..., description="Type of report")
    display_name: str = Field(..., description="Human-readable report name")
    is_available: bool = Field(default=True, description="Whether this report type is available")
    last_synced_at: datetime | None = Field(default=None, description="When last synced")
    is_stale: bool = Field(default=False, description="Whether data is stale")
    sync_status: str | None = Field(default=None, description="Current sync status if syncing")
    periods_available: list[str] = Field(default_factory=list, description="Available period keys")


class ReportListResponse(BaseModel):
    """Response listing available reports for a connection."""

    connection_id: UUID = Field(..., description="Xero connection ID")
    organization_name: str = Field(..., description="Xero organization name")
    reports: list[ReportStatusItem] = Field(
        default_factory=list, description="Available report types and status"
    )


class RefreshReportRequest(BaseModel):
    """Request to refresh a specific report."""

    period_key: str = Field(
        ...,
        description="Period to refresh (e.g., '2025-FY', '2025-Q4', '2025-12')",
    )
    force: bool = Field(
        default=False,
        description="Force refresh even if cache is valid",
    )


class ReportPendingResponse(BaseModel):
    """Response when report sync is in progress."""

    report_type: str = Field(..., description="Type of report being synced")
    status: str = Field(default="pending", description="Sync status")
    job_id: UUID = Field(..., description="Sync job ID for tracking")
    message: str = Field(
        default="Report sync is in progress",
        description="User-friendly message",
    )
    retry_after_seconds: int = Field(
        default=5,
        description="Suggested wait time before checking again",
    )


class SyncJobResponse(BaseModel):
    """Response for a report sync job."""

    id: UUID = Field(..., description="Sync job ID")
    report_type: str = Field(..., description="Type of report")
    status: str = Field(..., description="Job status")
    started_at: datetime | None = Field(default=None, description="When job started")
    completed_at: datetime | None = Field(default=None, description="When job completed")
    duration_ms: int | None = Field(default=None, description="Duration in milliseconds")
    rows_fetched: int | None = Field(default=None, description="Number of rows fetched")
    error_code: str | None = Field(default=None, description="Error code if failed")
    error_message: str | None = Field(default=None, description="Error message if failed")
    triggered_by: str = Field(default="on_demand", description="How sync was triggered")

    model_config = ConfigDict(from_attributes=True)


class RateLimitResponse(BaseModel):
    """Response when rate limit prevents operation."""

    error: str = Field(default="rate_limited", description="Error code")
    message: str = Field(..., description="User-friendly message")
    retry_after_seconds: int = Field(..., description="Seconds to wait before retrying")
    last_sync_at: datetime | None = Field(default=None, description="When last sync occurred")


class ReportQueryParams(BaseModel):
    """Common query parameters for report requests."""

    period: str = Field(
        default="current",
        description="Period: 'current', 'YYYY-FY', 'YYYY-QN', 'YYYY-MM', 'YYYY-MM-DD'",
    )
    periods: int = Field(default=1, ge=1, le=12, description="Number of comparison periods")
    timeframe: str = Field(
        default="MONTH",
        description="Timeframe for comparison: MONTH, QUARTER, YEAR",
    )
    standard_layout: bool = Field(default=True, description="Use standard chart of accounts layout")
    payments_only: bool = Field(default=False, description="Cash basis (true) vs accrual (false)")


# =============================================================================
# Credit Notes, Payments, Journals Schemas (Spec 024)
# =============================================================================


# -----------------------------------------------------------------------------
# Credit Notes
# -----------------------------------------------------------------------------


class CreditNoteAllocationSchema(BaseModel):
    """Allocation of credit note to invoice."""

    xero_allocation_id: str = Field(..., description="Xero allocation ID")
    invoice_number: str | None = Field(None, description="Invoice number allocated to")
    amount: Decimal = Field(..., description="Amount allocated")
    applied_at: datetime | None = Field(None, description="When allocation was applied")

    model_config = ConfigDict(from_attributes=True)


class CreditNoteSchema(BaseModel):
    """Response for a synced Xero credit note."""

    id: UUID
    connection_id: UUID
    client_id: UUID | None = None
    xero_credit_note_id: str
    xero_contact_id: str | None = None
    credit_note_number: str | None = None
    credit_note_type: XeroCreditNoteType
    status: XeroCreditNoteStatus
    issue_date: datetime
    due_date: datetime | None = None
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    remaining_credit: Decimal
    currency: str
    reference: str | None = None
    contact_name: str | None = Field(None, description="Contact name for display")
    line_items: list[dict[str, Any]] | None = None
    xero_updated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreditNoteDetailSchema(CreditNoteSchema):
    """Extended credit note with allocations."""

    allocations: list[CreditNoteAllocationSchema] = Field(
        default_factory=list,
        description="Allocations to invoices",
    )
    fully_allocated: bool = Field(
        default=False,
        description="Whether credit is fully applied",
    )


class CreditNoteListResponse(BaseModel):
    """Response for listing credit notes."""

    credit_notes: list[CreditNoteSchema]
    total: int
    limit: int
    offset: int


class CreditNoteSummary(BaseModel):
    """Summary of credit notes for a period (used in GST calculations)."""

    period_start: datetime
    period_end: datetime
    sales_credit_notes_count: int = Field(default=0, description="Number of ACCRECCREDIT notes")
    sales_credit_notes_subtotal: Decimal = Field(
        default=Decimal("0.00"), description="Total sales credit notes (excl GST)"
    )
    sales_credit_notes_gst: Decimal = Field(
        default=Decimal("0.00"), description="GST on sales credit notes"
    )
    purchase_credit_notes_count: int = Field(default=0, description="Number of ACCPAYCREDIT notes")
    purchase_credit_notes_subtotal: Decimal = Field(
        default=Decimal("0.00"), description="Total purchase credit notes (excl GST)"
    )
    purchase_credit_notes_gst: Decimal = Field(
        default=Decimal("0.00"), description="GST on purchase credit notes"
    )


# -----------------------------------------------------------------------------
# Payments
# -----------------------------------------------------------------------------


class PaymentSchema(BaseModel):
    """Response for a synced Xero payment."""

    id: UUID
    connection_id: UUID
    client_id: UUID | None = None
    xero_payment_id: str
    xero_contact_id: str | None = None
    xero_invoice_id: str | None = None
    xero_account_id: str | None = None
    payment_type: XeroPaymentType
    status: XeroPaymentStatus
    payment_date: datetime
    amount: Decimal
    currency: str
    reference: str | None = None
    invoice_number: str | None = Field(None, description="Invoice number for display")
    account_name: str | None = Field(None, description="Account name for display")
    contact_name: str | None = Field(None, description="Contact name for display")
    xero_updated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentDetailSchema(PaymentSchema):
    """Extended payment with additional details."""

    bank_amount: Decimal | None = Field(
        None, description="Amount in bank account currency (if different)"
    )
    currency_rate: Decimal | None = Field(None, description="Exchange rate used")
    has_validations_to_publish: bool = Field(
        default=False, description="Whether validation errors exist"
    )


class PaymentListResponse(BaseModel):
    """Response for listing payments."""

    payments: list[PaymentSchema]
    total: int
    limit: int
    offset: int


# -----------------------------------------------------------------------------
# Overpayments
# -----------------------------------------------------------------------------


class OverpaymentSchema(BaseModel):
    """Response for a synced Xero overpayment."""

    id: UUID
    connection_id: UUID
    client_id: UUID | None = None
    xero_overpayment_id: str
    xero_contact_id: str | None = None
    status: XeroOverpaymentStatus
    overpayment_date: datetime
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    remaining_credit: Decimal
    currency: str
    contact_name: str | None = Field(None, description="Contact name for display")
    line_items: list[dict[str, Any]] | None = None
    allocations: list[dict[str, Any]] | None = None
    xero_updated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OverpaymentListResponse(BaseModel):
    """Response for listing overpayments."""

    overpayments: list[OverpaymentSchema]
    total: int
    limit: int
    offset: int


# -----------------------------------------------------------------------------
# Prepayments
# -----------------------------------------------------------------------------


class PrepaymentSchema(BaseModel):
    """Response for a synced Xero prepayment."""

    id: UUID
    connection_id: UUID
    client_id: UUID | None = None
    xero_prepayment_id: str
    xero_contact_id: str | None = None
    status: XeroPrepaymentStatus
    prepayment_date: datetime
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    remaining_credit: Decimal
    currency: str
    reference: str | None = None
    contact_name: str | None = Field(None, description="Contact name for display")
    line_items: list[dict[str, Any]] | None = None
    allocations: list[dict[str, Any]] | None = None
    xero_updated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PrepaymentListResponse(BaseModel):
    """Response for listing prepayments."""

    prepayments: list[PrepaymentSchema]
    total: int
    limit: int
    offset: int


# -----------------------------------------------------------------------------
# Journals (System-Generated)
# -----------------------------------------------------------------------------


class JournalLineSchema(BaseModel):
    """A line in a journal entry."""

    journal_line_id: str | None = None
    account_id: str | None = None
    account_code: str | None = None
    account_name: str | None = None
    account_type: str | None = None
    description: str | None = None
    net_amount: Decimal = Field(default=Decimal("0.00"))
    gross_amount: Decimal = Field(default=Decimal("0.00"))
    tax_amount: Decimal = Field(default=Decimal("0.00"))
    tax_type: str | None = None
    tax_name: str | None = None


class JournalSchema(BaseModel):
    """Response for a synced Xero journal."""

    id: UUID
    connection_id: UUID
    xero_journal_id: str
    journal_number: int
    journal_date: datetime
    source_id: str | None = None
    source_type: XeroJournalSourceType
    reference: str | None = None
    created_date_utc: datetime | None = None
    xero_updated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JournalDetailSchema(JournalSchema):
    """Extended journal with line items."""

    journal_lines: list[JournalLineSchema] = Field(
        default_factory=list,
        description="Journal line items",
    )
    total_debits: Decimal = Field(default=Decimal("0.00"), description="Sum of debit amounts")
    total_credits: Decimal = Field(default=Decimal("0.00"), description="Sum of credit amounts")


class JournalListResponse(BaseModel):
    """Response for listing journals."""

    journals: list[JournalSchema]
    total: int
    limit: int
    offset: int


# -----------------------------------------------------------------------------
# Manual Journals
# -----------------------------------------------------------------------------


class ManualJournalLineSchema(BaseModel):
    """A line in a manual journal entry."""

    line_amount: Decimal = Field(default=Decimal("0.00"))
    account_id: str | None = None
    account_code: str | None = None
    account_name: str | None = None
    description: str | None = None
    tax_type: str | None = None
    tax_amount: Decimal | None = None
    is_blank: bool = False


class ManualJournalSchema(BaseModel):
    """Response for a synced Xero manual journal."""

    id: UUID
    connection_id: UUID
    xero_manual_journal_id: str
    narration: str | None = None
    status: XeroManualJournalStatus
    journal_date: datetime
    show_on_cash_basis_reports: bool = True
    url: str | None = None
    xero_updated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ManualJournalDetailSchema(ManualJournalSchema):
    """Extended manual journal with line items."""

    journal_lines: list[ManualJournalLineSchema] = Field(
        default_factory=list,
        description="Manual journal line items",
    )
    total_debits: Decimal = Field(default=Decimal("0.00"), description="Sum of positive amounts")
    total_credits: Decimal = Field(
        default=Decimal("0.00"), description="Sum of negative amounts (abs value)"
    )


class ManualJournalListResponse(BaseModel):
    """Response for listing manual journals."""

    manual_journals: list[ManualJournalSchema]
    total: int
    limit: int
    offset: int


# -----------------------------------------------------------------------------
# Transaction Sync Status
# -----------------------------------------------------------------------------


class TransactionSyncStatus(BaseModel):
    """Status of transaction syncs for a connection."""

    connection_id: UUID
    organization_name: str

    # Credit Notes
    credit_notes_count: int = 0
    last_credit_notes_sync_at: datetime | None = None

    # Payments
    payments_count: int = 0
    last_payments_sync_at: datetime | None = None

    # Overpayments
    overpayments_count: int = 0
    last_overpayments_sync_at: datetime | None = None

    # Prepayments
    prepayments_count: int = 0
    last_prepayments_sync_at: datetime | None = None

    # Journals
    journals_count: int = 0
    last_journals_sync_at: datetime | None = None
    latest_journal_number: int | None = None

    # Manual Journals
    manual_journals_count: int = 0
    last_manual_journals_sync_at: datetime | None = None

    sync_in_progress: bool = False


class EnhancedSyncStatus(BaseModel):
    """Enhanced sync status including all Spec 025 entity types.

    Provides a comprehensive view of sync status for fixed assets,
    purchase orders, repeating invoices, tracking categories, and quotes.
    """

    connection_id: UUID
    organization_name: str

    # Fixed Assets (requires assets scope)
    assets_count: int = 0
    asset_types_count: int = 0
    has_assets_scope: bool = False
    last_assets_sync_at: datetime | None = None

    # Purchase Orders
    purchase_orders_count: int = 0
    outstanding_purchase_orders: int = 0
    outstanding_purchase_orders_value: Decimal = Decimal("0.00")
    last_purchase_orders_sync_at: datetime | None = None

    # Repeating Invoices
    repeating_invoices_count: int = 0
    active_repeating_invoices: int = 0
    monthly_recurring_revenue: Decimal = Decimal("0.00")
    monthly_recurring_expense: Decimal = Decimal("0.00")
    last_repeating_invoices_sync_at: datetime | None = None

    # Tracking Categories
    tracking_categories_count: int = 0
    active_tracking_options: int = 0
    last_tracking_categories_sync_at: datetime | None = None

    # Quotes
    quotes_count: int = 0
    open_quotes_count: int = 0
    open_quotes_value: Decimal = Decimal("0.00")
    last_quotes_sync_at: datetime | None = None

    sync_in_progress: bool = False
    last_full_sync_at: datetime | None = None


# -----------------------------------------------------------------------------
# Asset Schemas (Spec 025)
# -----------------------------------------------------------------------------


class AssetTypeSchema(BaseModel):
    """Schema for asset type (depreciation category)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    connection_id: UUID
    xero_asset_type_id: str
    asset_type_name: str = Field(description="Name of the asset type")
    book_depreciation_method: str | None = Field(
        None, description="Book depreciation method (StraightLine, DiminishingValue100, etc.)"
    )
    book_depreciation_rate: Decimal | None = Field(
        None, description="Annual depreciation rate for book purposes (%)"
    )
    book_effective_life_years: int | None = Field(
        None, description="Effective life in years for book purposes"
    )
    tax_depreciation_method: str | None = Field(None, description="Tax depreciation method")
    tax_depreciation_rate: Decimal | None = Field(
        None, description="Annual depreciation rate for tax purposes (%)"
    )
    tax_effective_life_years: int | None = Field(
        None, description="Effective life in years for tax purposes"
    )
    asset_count: int = Field(0, description="Number of assets using this type")
    created_at: datetime
    updated_at: datetime


class AssetTypeListResponse(BaseModel):
    """Response for listing asset types."""

    asset_types: list[AssetTypeSchema]
    total: int


class AssetSchema(BaseModel):
    """Schema for fixed asset."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    connection_id: UUID
    xero_asset_id: str
    asset_name: str = Field(description="Name of the asset")
    asset_number: str | None = Field(None, description="Asset tracking number")
    purchase_date: datetime = Field(description="Date the asset was purchased")
    purchase_price: Decimal = Field(description="Original purchase price")
    status: str = Field(description="Asset status (Draft, Registered, Disposed)")
    book_value: Decimal = Field(description="Current book value after depreciation")
    serial_number: str | None = Field(None, description="Serial number")
    warranty_expiry: datetime | None = Field(None, description="Warranty expiry date")

    # Asset type reference
    asset_type_id: UUID | None = None
    asset_type_name: str | None = Field(None, description="Name of the asset type")

    # Book depreciation summary
    book_depreciation_method: str | None = None
    book_current_accum_depreciation: Decimal | None = Field(
        None, description="Accumulated book depreciation to date"
    )

    # Disposal info (if disposed)
    disposal_date: datetime | None = None
    disposal_price: Decimal | None = None

    created_at: datetime
    updated_at: datetime


class AssetDetailSchema(AssetSchema):
    """Extended asset schema with full depreciation details."""

    # Book depreciation details
    book_depreciation_rate: Decimal | None = Field(
        None, description="Annual book depreciation rate (%)"
    )
    book_effective_life_years: int | None = Field(
        None, description="Effective life for book purposes"
    )
    book_depreciation_start_date: datetime | None = None
    book_cost_limit: Decimal | None = None
    book_residual_value: Decimal | None = None
    book_prior_accum_depreciation: Decimal | None = None
    book_current_capital_gain: Decimal | None = None
    book_current_gain_loss: Decimal | None = None

    # Tax depreciation details
    tax_depreciation_method: str | None = None
    tax_depreciation_rate: Decimal | None = Field(
        None, description="Annual tax depreciation rate (%)"
    )
    tax_effective_life_years: int | None = Field(
        None, description="Effective life for tax purposes"
    )
    tax_depreciation_start_date: datetime | None = None
    tax_cost_limit: Decimal | None = None
    tax_residual_value: Decimal | None = None
    tax_prior_accum_depreciation: Decimal | None = None
    tax_current_accum_depreciation: Decimal | None = None
    tax_current_capital_gain: Decimal | None = None
    tax_current_gain_loss: Decimal | None = None


class AssetListResponse(BaseModel):
    """Response for listing assets with pagination."""

    assets: list[AssetSchema]
    total: int
    limit: int
    offset: int


class DepreciationSummary(BaseModel):
    """Summary of depreciation for a connection."""

    total_cost: Decimal = Field(description="Total purchase cost of all registered assets")
    total_book_value: Decimal = Field(description="Current total book value")
    total_accumulated_depreciation: Decimal = Field(
        description="Total accumulated depreciation (cost - book value)"
    )
    asset_count: int = Field(description="Number of registered assets")
    current_year_depreciation: Decimal | None = Field(
        None, description="Depreciation expense for current financial year"
    )


class InstantWriteOffEligibleAsset(BaseModel):
    """Asset eligible for instant asset write-off."""

    id: UUID
    asset_name: str
    asset_number: str | None
    purchase_date: datetime
    purchase_price: Decimal = Field(description="Amount eligible for immediate deduction")
    status: str
    asset_type_name: str | None = None


class InstantWriteOffSummary(BaseModel):
    """Summary of instant asset write-off eligibility."""

    is_eligible_business: bool = Field(
        description="Whether the business is eligible (turnover < threshold)"
    )
    ineligibility_reason: str | None = Field(
        None, description="Reason for ineligibility if not eligible"
    )
    write_off_threshold: Decimal = Field(description="Current instant asset write-off threshold")
    financial_year_start: datetime
    financial_year_end: datetime
    eligible_assets: list[InstantWriteOffEligibleAsset] = Field(
        default_factory=list, description="Assets qualifying for instant write-off"
    )
    total_eligible_amount: Decimal = Field(Decimal("0.00"), description="Total potential deduction")
    asset_count: int = Field(0, description="Number of eligible assets")


# =============================================================================
# Spec 025: Purchase Orders, Repeating Invoices, Tracking, Quotes
# =============================================================================


class PurchaseOrderSchema(BaseModel):
    """Purchase order synced from Xero."""

    id: UUID
    xero_purchase_order_id: str
    purchase_order_number: str | None = None
    contact_id: str | None = None
    contact_name: str | None = None
    reference: str | None = None
    date: date
    delivery_date: date | None = None
    status: str = Field(description="DRAFT, SUBMITTED, AUTHORISED, BILLED, DELETED")
    sub_total: Decimal
    total_tax: Decimal
    total: Decimal
    currency_code: str | None = None
    branding_theme_id: str | None = None
    expected_arrival_date: date | None = None
    delivery_address: str | None = None
    attention_to: str | None = None
    telephone: str | None = None
    delivery_instructions: str | None = None
    sent_to_contact: bool = False
    has_attachments: bool = False
    updated_date_utc: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderListResponse(BaseModel):
    """Response for listing purchase orders with pagination."""

    orders: list[PurchaseOrderSchema]
    total: int
    limit: int
    offset: int


class PurchaseOrderSummary(BaseModel):
    """Summary of outstanding purchase orders for cash flow."""

    outstanding_count: int = Field(description="Number of non-billed POs")
    outstanding_total: Decimal = Field(description="Total value of outstanding POs")
    by_status: dict[str, int] = Field(default_factory=dict, description="Count by status")
    upcoming_deliveries: list[dict] = Field(
        default_factory=list, description="POs with expected delivery in next 30 days"
    )


class RepeatingInvoiceSchema(BaseModel):
    """Repeating invoice template synced from Xero."""

    id: UUID
    xero_repeating_invoice_id: str
    invoice_type: str = Field(description="ACCPAY (bill) or ACCREC (invoice)")
    contact_id: str | None = None
    contact_name: str | None = None
    status: str = Field(description="DRAFT or AUTHORISED")
    schedule_unit: str = Field(description="WEEKLY, MONTHLY, YEARLY")
    schedule_period: int = Field(description="Number of units between invoices")
    start_date: date | None = None
    end_date: date | None = None
    next_scheduled_date: date | None = None
    reference: str | None = None
    branding_theme_id: str | None = None
    currency_code: str | None = None
    sub_total: Decimal
    total_tax: Decimal
    total: Decimal
    has_attachments: bool = False
    approved_for_sending: bool = False
    send_copy: bool = False
    mark_as_sent: bool = False
    include_pdf: bool = False
    updated_date_utc: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RepeatingInvoiceListResponse(BaseModel):
    """Response for listing repeating invoices with pagination."""

    invoices: list[RepeatingInvoiceSchema]
    total: int
    limit: int
    offset: int


class RecurringSummary(BaseModel):
    """Summary of recurring revenue/expenses from repeating invoices."""

    monthly_receivables: Decimal = Field(description="Estimated monthly receivables")
    monthly_payables: Decimal = Field(description="Estimated monthly payables")
    annual_receivables: Decimal = Field(description="Annualized receivables")
    annual_payables: Decimal = Field(description="Annualized payables")
    active_receivable_count: int
    active_payable_count: int


class TrackingCategorySchema(BaseModel):
    """Tracking category synced from Xero."""

    id: UUID
    xero_tracking_category_id: str
    name: str
    status: str = Field(description="ACTIVE or ARCHIVED")
    option_count: int = 0
    options: list[dict] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrackingCategoryListResponse(BaseModel):
    """Response for listing tracking categories."""

    categories: list[TrackingCategorySchema]
    total: int


class QuoteSchema(BaseModel):
    """Quote synced from Xero."""

    id: UUID
    xero_quote_id: str
    quote_number: str | None = None
    contact_id: str | None = None
    contact_name: str | None = None
    reference: str | None = None
    date: date
    expiry_date: date | None = None
    status: str = Field(description="DRAFT, SENT, DECLINED, ACCEPTED, INVOICED, DELETED")
    title: str | None = None
    summary: str | None = None
    sub_total: Decimal
    total_tax: Decimal
    total: Decimal
    total_discount: Decimal | None = None
    currency_code: str | None = None
    branding_theme_id: str | None = None
    updated_date_utc: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QuoteListResponse(BaseModel):
    """Response for listing quotes with pagination."""

    quotes: list[QuoteSchema]
    total: int
    limit: int
    offset: int


class QuotePipelineSummary(BaseModel):
    """Summary of quote pipeline for sales forecasting."""

    total_quotes: int
    total_value: Decimal
    by_status: dict[str, dict] = Field(
        default_factory=dict, description="Count and value by status"
    )
    conversion_rate: float | None = Field(None, description="% of quotes converted to invoices")
    average_quote_value: Decimal | None = None


# =============================================================================
# Bulk Import Schemas (Phase 035)
# =============================================================================


class BulkImportInitiateRequest(BaseModel):
    """Request to initiate a bulk import OAuth flow."""

    redirect_uri: str = Field(
        ...,
        description="Frontend URL to redirect back to after OAuth",
        examples=["http://localhost:3001/clients/import"],
    )


class BulkImportInitiateResponse(BaseModel):
    """Response with OAuth authorization URL for bulk import."""

    auth_url: str = Field(..., description="Xero OAuth authorization URL")
    state: str = Field(..., description="OAuth state token for verification")


class ImportOrganization(BaseModel):
    """A Xero organization discovered during bulk OAuth."""

    xero_tenant_id: str = Field(..., description="Xero organization identifier")
    organization_name: str = Field(..., description="Xero organization display name")
    already_connected: bool = Field(
        default=False,
        description="True if this org is already connected for this tenant",
    )
    existing_connection_id: UUID | None = Field(
        default=None,
        description="Existing connection ID if already connected",
    )
    match_status: str | None = Field(
        default=None,
        description="Auto-match result: matched, suggested, unmatched",
    )
    matched_client_name: str | None = Field(
        default=None,
        description="Name of matched existing client",
    )


class BulkImportCallbackResponse(BaseModel):
    """Response from processing a bulk import OAuth callback."""

    auth_event_id: str = Field(
        ..., description="Groups organizations from this authorization event"
    )
    organizations: list[ImportOrganization] = Field(
        ..., description="List of authorized organizations"
    )
    already_connected_count: int = Field(default=0, description="Number of orgs already connected")
    new_count: int = Field(default=0, description="Number of new orgs")
    plan_limit: int = Field(..., description="Maximum clients allowed on current subscription tier")
    current_client_count: int = Field(..., description="Current number of connected clients")
    available_slots: int = Field(..., description="How many more clients can be imported")


class ImportOrgSelection(BaseModel):
    """User's selection for a single organization in bulk import."""

    xero_tenant_id: str = Field(..., description="Xero organization identifier")
    organization_name: str = Field(
        default="",
        description="Xero organization display name",
    )
    selected: bool = Field(..., description="Whether to import this organization")
    connection_type: str = Field(
        default="client",
        description="Connection type: practice or client",
    )
    assigned_user_id: UUID | None = Field(
        default=None,
        description="Assigned team member UUID",
    )
    already_connected: bool = Field(
        default=False,
        description="Whether this org is already connected for this tenant",
    )


class BulkImportConfirmRequest(BaseModel):
    """Request to confirm selected organizations and start import."""

    auth_event_id: str = Field(..., description="Authorization event ID from callback")
    organizations: list[ImportOrgSelection] = Field(
        ..., description="Organization selections with configuration"
    )


class BulkImportJobResponse(BaseModel):
    """Summary of a bulk import job."""

    job_id: UUID = Field(..., description="Bulk import job ID")
    status: str = Field(..., description="Job status")
    total_organizations: int = Field(default=0, description="Total orgs in job")
    imported_count: int = Field(default=0, description="Successfully imported count")
    failed_count: int = Field(default=0, description="Failed import count")
    skipped_count: int = Field(default=0, description="Skipped org count")
    progress_percent: int = Field(default=0, description="Progress 0-100")
    created_at: datetime = Field(..., description="Job creation time")

    model_config = ConfigDict(from_attributes=True)


class BulkImportOrgStatus(BaseModel):
    """Status of a single organization within a bulk import job."""

    xero_tenant_id: str = Field(..., description="Xero organization identifier")
    organization_name: str = Field(..., description="Xero organization display name")
    status: str = Field(..., description="Org import status")
    connection_id: UUID | None = Field(default=None, description="Created connection ID")
    connection_type: str = Field(default="client", description="Connection type")
    assigned_user_id: UUID | None = Field(default=None, description="Assigned team member")
    error_message: str | None = Field(default=None, description="Error if failed")
    sync_started_at: datetime | None = Field(default=None, description="When sync started")
    sync_completed_at: datetime | None = Field(default=None, description="When sync completed")

    model_config = ConfigDict(from_attributes=True)


class BulkImportJobDetailResponse(BulkImportJobResponse):
    """Detailed bulk import job with per-organization status."""

    organizations: list[BulkImportOrgStatus] = Field(
        default_factory=list, description="Per-organization status details"
    )
    started_at: datetime | None = Field(default=None, description="When job started processing")
    completed_at: datetime | None = Field(default=None, description="When job completed")


class BulkImportJobListResponse(BaseModel):
    """Paginated list of bulk import jobs."""

    jobs: list[BulkImportJobResponse] = Field(
        default_factory=list, description="List of bulk import jobs"
    )
    total: int = Field(default=0, description="Total job count")
    limit: int = Field(default=20, description="Page size")
    offset: int = Field(default=0, description="Page offset")


# =============================================================================
# Progressive Sync Schemas (Spec 043)
# =============================================================================


class EntityProgressResponse(BaseModel):
    """Per-entity sync progress within a job."""

    model_config = ConfigDict(from_attributes=True)

    entity_type: str
    status: str
    records_processed: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_failed: int = 0
    error_message: str | None = None
    duration_ms: int | None = None


class PostSyncTaskResponse(BaseModel):
    """Post-sync preparation task status."""

    model_config = ConfigDict(from_attributes=True)

    task_type: str
    status: str
    sync_phase: int
    result_summary: dict[str, Any] | None = None


class SyncStatusResponse(BaseModel):
    """Enhanced sync status with phase and entity progress."""

    model_config = ConfigDict(from_attributes=True)

    job: XeroSyncJobResponse
    entities: list[EntityProgressResponse] = []
    phase: int | None = None
    total_phases: int = 3
    records_processed: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_failed: int = 0
    post_sync_tasks: list[PostSyncTaskResponse] = []


class MultiClientSyncRequest(BaseModel):
    """Request to sync all connected clients."""

    force_full: bool = False
    sync_type: str = "incremental"


class MultiClientQueuedConnection(BaseModel):
    """Detail of a connection that was queued for sync."""

    connection_id: UUID
    organization_name: str
    job_id: UUID


class MultiClientSkippedConnection(BaseModel):
    """Detail of a connection that was skipped during multi-client sync."""

    connection_id: UUID
    organization_name: str
    reason: str


class MultiClientSyncResponse(BaseModel):
    """Response from multi-client sync initiation."""

    batch_id: UUID
    total_connections: int
    jobs_queued: int
    jobs_skipped: int
    queued: list[MultiClientQueuedConnection] = []
    skipped: list[MultiClientSkippedConnection] = []


class MultiClientConnectionStatus(BaseModel):
    """Status of a single connection in a multi-client sync."""

    connection_id: UUID
    organization_name: str
    status: str
    records_processed: int = 0
    sync_phase: int | None = None
    last_sync_at: str | None = None


class MultiClientSyncStatusResponse(BaseModel):
    """Aggregate status of a multi-client sync operation."""

    total_connections: int
    syncing: int
    completed: int
    failed: int
    pending: int
    connections: list[MultiClientConnectionStatus] = []


# SSE Event schemas


class SyncStartedEvent(BaseModel):
    """SSE event: sync started."""

    job_id: UUID
    phase: int
    total_entities: int


class EntityProgressEvent(BaseModel):
    """SSE event: entity sync progress update."""

    entity_type: str
    status: str
    records_processed: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_failed: int = 0


class PhaseCompleteEvent(BaseModel):
    """SSE event: sync phase completed."""

    phase: int
    next_phase: int | None = None
    entities_completed: int
    records_processed: int


class SyncCompleteEvent(BaseModel):
    """SSE event: full sync completed."""

    job_id: UUID
    status: str
    records_processed: int
    records_created: int
    records_updated: int
    records_failed: int


class SyncFailedEvent(BaseModel):
    """SSE event: sync failed."""

    job_id: UUID
    error: str
    entity_type: str | None = None


class PostSyncProgressEvent(BaseModel):
    """SSE event: post-sync task progress."""

    task_type: str
    status: str
    result_summary: dict[str, Any] | None = None
