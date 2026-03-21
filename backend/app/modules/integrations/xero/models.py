"""SQLAlchemy models for Xero integration.

This module defines:
- Enums: XeroConnectionStatus, XeroSyncType, XeroSyncStatus, XeroContactType,
         XeroInvoiceType, XeroInvoiceStatus, XeroBankTransactionType, XeroAccountClass
- Models: XeroConnection, XeroOAuthState, XeroSyncJob, XeroClient, XeroInvoice,
          XeroBankTransaction, XeroAccount

RLS (Row-Level Security):
- RLS is enforced on all tenant-scoped tables
- The `xero_oauth_states` table is NOT tenant-scoped (lookup by state token)
- RLS uses PostgreSQL session variable `app.current_tenant_id`
"""

import enum
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.auth.models import PracticeUser, Tenant
    from app.modules.insights.models import Insight
    from app.modules.quality.models import QualityIssue, QualityScore


# =============================================================================
# Enums
# =============================================================================


class XeroConnectionStatus(str, enum.Enum):
    """Status of a Xero connection.

    - ACTIVE: Connection is healthy, tokens are valid
    - NEEDS_REAUTH: Refresh failed, user must re-authorize
    - DISCONNECTED: User disconnected, tokens have been revoked
    """

    ACTIVE = "active"
    NEEDS_REAUTH = "needs_reauth"
    DISCONNECTED = "disconnected"

    def __str__(self) -> str:
        """Return the enum value as string."""
        return self.value


class XeroConnectionType(str, enum.Enum):
    """Type of Xero connection.

    - PRACTICE: The accounting practice's own Xero organization
    - CLIENT: A client business's Xero organization (managed by the practice)
    """

    PRACTICE = "practice"
    CLIENT = "client"

    def __str__(self) -> str:
        """Return the enum value as string."""
        return self.value


class XeroSyncType(str, enum.Enum):
    """Type of sync operation."""

    CONTACTS = "contacts"
    INVOICES = "invoices"
    BANK_TRANSACTIONS = "bank_transactions"
    ACCOUNTS = "accounts"
    EMPLOYEES = "employees"
    PAY_RUNS = "pay_runs"
    PAYROLL = "payroll"  # Combined employees + pay runs
    FULL = "full"

    def __str__(self) -> str:
        return self.value


class XeroSyncStatus(str, enum.Enum):
    """Status of a sync job."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    def __str__(self) -> str:
        return self.value


class XeroContactType(str, enum.Enum):
    """Type of Xero contact."""

    CUSTOMER = "customer"
    SUPPLIER = "supplier"
    BOTH = "both"

    def __str__(self) -> str:
        return self.value


class XeroInvoiceType(str, enum.Enum):
    """Type of Xero invoice."""

    ACCREC = "accrec"  # Accounts Receivable (sales)
    ACCPAY = "accpay"  # Accounts Payable (purchases)

    def __str__(self) -> str:
        return self.value


class XeroInvoiceStatus(str, enum.Enum):
    """Status of Xero invoice."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    AUTHORISED = "authorised"
    PAID = "paid"
    VOIDED = "voided"
    DELETED = "deleted"

    def __str__(self) -> str:
        return self.value


class XeroBankTransactionType(str, enum.Enum):
    """Type of bank transaction."""

    RECEIVE = "receive"
    SPEND = "spend"
    RECEIVE_OVERPAYMENT = "receive_overpayment"
    SPEND_OVERPAYMENT = "spend_overpayment"
    RECEIVE_PREPAYMENT = "receive_prepayment"
    SPEND_PREPAYMENT = "spend_prepayment"

    def __str__(self) -> str:
        return self.value


class XeroAccountClass(str, enum.Enum):
    """Classification of Xero account."""

    ASSET = "asset"
    EQUITY = "equity"
    EXPENSE = "expense"
    LIABILITY = "liability"
    REVENUE = "revenue"

    def __str__(self) -> str:
        return self.value


class XeroEmployeeStatus(str, enum.Enum):
    """Status of a Xero employee."""

    ACTIVE = "active"
    TERMINATED = "terminated"

    def __str__(self) -> str:
        return self.value


class XeroPayRunStatus(str, enum.Enum):
    """Status of a Xero pay run."""

    DRAFT = "draft"
    POSTED = "posted"

    def __str__(self) -> str:
        return self.value


# =============================================================================
# Credit Notes, Payments, Journals Enums (Spec 024)
# =============================================================================


class XeroCreditNoteType(str, enum.Enum):
    """Type of Xero credit note.

    Spec 024: Credit Notes, Payments & Journals
    """

    ACCPAYCREDIT = "accpaycredit"  # Accounts Payable Credit (from supplier)
    ACCRECCREDIT = "accreccredit"  # Accounts Receivable Credit (to customer)

    def __str__(self) -> str:
        return self.value


class XeroCreditNoteStatus(str, enum.Enum):
    """Status of Xero credit note.

    Spec 024: Credit Notes, Payments & Journals
    """

    DRAFT = "draft"
    SUBMITTED = "submitted"
    AUTHORISED = "authorised"
    PAID = "paid"
    VOIDED = "voided"

    def __str__(self) -> str:
        return self.value


class XeroPaymentType(str, enum.Enum):
    """Type of Xero payment.

    Spec 024: Credit Notes, Payments & Journals
    """

    ACCRECPAYMENT = "accrecpayment"  # Accounts Receivable Payment (customer pays us)
    ACCPAYPAYMENT = "accpaypayment"  # Accounts Payable Payment (we pay supplier)
    ARCREDITPAYMENT = "arcreditpayment"  # AR Credit Note refund
    APCREDITPAYMENT = "apcreditpayment"  # AP Credit Note refund
    ARPREPAYMENTPAYMENT = "arprepaymentpayment"  # AR Prepayment
    APPREPAYMENTPAYMENT = "apprepaymentpayment"  # AP Prepayment
    AROVERPAYMENTPAYMENT = "aroverpaymentpayment"  # AR Overpayment
    APOVERPAYMENTPAYMENT = "apoverpaymentpayment"  # AP Overpayment

    def __str__(self) -> str:
        return self.value


class XeroPaymentStatus(str, enum.Enum):
    """Status of Xero payment.

    Spec 024: Credit Notes, Payments & Journals
    """

    AUTHORISED = "authorised"
    DELETED = "deleted"

    def __str__(self) -> str:
        return self.value


class XeroOverpaymentStatus(str, enum.Enum):
    """Status of Xero overpayment.

    Spec 024: Credit Notes, Payments & Journals
    """

    AUTHORISED = "authorised"
    PAID = "paid"
    VOIDED = "voided"

    def __str__(self) -> str:
        return self.value


class XeroPrepaymentStatus(str, enum.Enum):
    """Status of Xero prepayment.

    Spec 024: Credit Notes, Payments & Journals
    """

    AUTHORISED = "authorised"
    PAID = "paid"
    VOIDED = "voided"

    def __str__(self) -> str:
        return self.value


class XeroJournalSourceType(str, enum.Enum):
    """Source type for Xero journals.

    Spec 024: Credit Notes, Payments & Journals
    """

    ACCREC = "accrec"  # Accounts Receivable Invoice
    ACCPAY = "accpay"  # Accounts Payable Bill
    CASHREC = "cashrec"  # Cash Received
    CASHPAID = "cashpaid"  # Cash Paid
    ACCPAYCREDIT = "accpaycredit"  # AP Credit Note
    ACCRECCREDIT = "accreccredit"  # AR Credit Note
    TRANSFER = "transfer"  # Bank Transfer
    MANJOURNAL = "manjournal"  # Manual Journal
    UNKNOWN = "unknown"  # Unrecognized source type

    @classmethod
    def _missing_(cls, value: object) -> "XeroJournalSourceType":
        return cls.UNKNOWN

    def __str__(self) -> str:
        return self.value


class XeroManualJournalStatus(str, enum.Enum):
    """Status of Xero manual journal.

    Spec 024: Credit Notes, Payments & Journals
    """

    DRAFT = "draft"
    POSTED = "posted"
    DELETED = "deleted"
    VOIDED = "voided"

    def __str__(self) -> str:
        return self.value


class XeroReportType(str, enum.Enum):
    """Types of reports available from Xero Reports API.

    Spec 023: Xero Reports API Integration
    """

    PROFIT_AND_LOSS = "profit_and_loss"
    BALANCE_SHEET = "balance_sheet"
    AGED_RECEIVABLES = "aged_receivables_by_contact"
    AGED_PAYABLES = "aged_payables_by_contact"
    TRIAL_BALANCE = "trial_balance"
    BANK_SUMMARY = "bank_summary"
    BUDGET_SUMMARY = "budget_summary"

    def __str__(self) -> str:
        return self.value

    @property
    def display_name(self) -> str:
        """Human-readable display name for the report type."""
        names = {
            "profit_and_loss": "Profit and Loss",
            "balance_sheet": "Balance Sheet",
            "aged_receivables_by_contact": "Aged Receivables",
            "aged_payables_by_contact": "Aged Payables",
            "trial_balance": "Trial Balance",
            "bank_summary": "Bank Summary",
            "budget_summary": "Budget Summary",
        }
        return names.get(self.value, self.value)


class XeroReportSyncStatus(str, enum.Enum):
    """Status of a report sync operation.

    Spec 023: Xero Reports API Integration
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"  # e.g., budget not configured in Xero

    def __str__(self) -> str:
        return self.value


# -----------------------------------------------------------------------------
# Spec 025: Fixed Assets & Enhanced Analysis Enums
# -----------------------------------------------------------------------------


class XeroAssetStatus(str, enum.Enum):
    """Fixed asset status in Xero.

    Spec 025: Fixed Assets & Enhanced Analysis
    """

    DRAFT = "Draft"
    REGISTERED = "Registered"
    DISPOSED = "Disposed"

    def __str__(self) -> str:
        return self.value


class XeroDepreciationMethod(str, enum.Enum):
    """Depreciation calculation method.

    Spec 025: Fixed Assets & Enhanced Analysis
    """

    NO_DEPRECIATION = "NoDepreciation"
    STRAIGHT_LINE = "StraightLine"
    DIMINISHING_VALUE_100 = "DiminishingValue100"
    DIMINISHING_VALUE_150 = "DiminishingValue150"
    DIMINISHING_VALUE_200 = "DiminishingValue200"
    FULL_DEPRECIATION = "FullDepreciation"

    def __str__(self) -> str:
        return self.value


# Alias for backward compatibility with depreciation service
DepreciationMethod = XeroDepreciationMethod


class XeroAveragingMethod(str, enum.Enum):
    """Depreciation averaging method.

    Spec 025: Fixed Assets & Enhanced Analysis
    """

    FULL_MONTH = "FullMonth"
    ACTUAL_DAYS = "ActualDays"

    def __str__(self) -> str:
        return self.value


class XeroDepreciationCalculationMethod(str, enum.Enum):
    """How depreciation is calculated.

    Spec 025: Fixed Assets & Enhanced Analysis
    """

    RATE = "Rate"
    LIFE = "Life"
    NONE = "None"

    def __str__(self) -> str:
        return self.value


class XeroPurchaseOrderStatus(str, enum.Enum):
    """Purchase order status.

    Spec 025: Fixed Assets & Enhanced Analysis
    """

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    AUTHORISED = "AUTHORISED"
    BILLED = "BILLED"
    DELETED = "DELETED"

    def __str__(self) -> str:
        return self.value


class XeroRepeatingInvoiceStatus(str, enum.Enum):
    """Repeating invoice template status.

    Spec 025: Fixed Assets & Enhanced Analysis
    """

    DRAFT = "DRAFT"
    AUTHORISED = "AUTHORISED"

    def __str__(self) -> str:
        return self.value


class XeroScheduleUnit(str, enum.Enum):
    """Repeating invoice schedule unit.

    Spec 025: Fixed Assets & Enhanced Analysis
    """

    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"

    def __str__(self) -> str:
        return self.value


class XeroQuoteStatus(str, enum.Enum):
    """Quote status.

    Spec 025: Fixed Assets & Enhanced Analysis
    """

    DRAFT = "DRAFT"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    INVOICED = "INVOICED"

    def __str__(self) -> str:
        return self.value


class XeroTrackingCategoryStatus(str, enum.Enum):
    """Tracking category status.

    Spec 025: Fixed Assets & Enhanced Analysis
    """

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"

    def __str__(self) -> str:
        return self.value


# =============================================================================
# Helper Functions
# =============================================================================


def generate_oauth_state() -> str:
    """Generate a secure random OAuth state parameter.

    Uses secrets.token_urlsafe which is cryptographically secure.

    Returns:
        A 43-character URL-safe base64 token (32 bytes of entropy).
    """
    return secrets.token_urlsafe(32)


def generate_code_verifier() -> str:
    """Generate a PKCE code verifier.

    Per RFC 7636, the code verifier must be 43-128 characters,
    using only [A-Z], [a-z], [0-9], -, ., _, ~.

    Returns:
        A 43-character URL-safe base64 token.
    """
    return secrets.token_urlsafe(32)


def default_state_expiry() -> datetime:
    """Generate default expiry for OAuth state (10 minutes from now).

    Returns:
        A timezone-aware datetime 10 minutes in the future.
    """
    return datetime.now(UTC) + timedelta(minutes=10)


# =============================================================================
# Models
# =============================================================================


class XeroConnection(Base, TimestampMixin):
    """Xero organization connection entity.

    Represents a link between a Clairo tenant and a Xero organization.
    Stores OAuth tokens (encrypted) and rate limit tracking.

    This model is tenant-scoped with RLS enforced at the database level.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant (RLS enforced).
        xero_tenant_id: Xero's organization identifier.
        organization_name: Display name of the Xero organization.
        status: Current connection status (active, needs_reauth, disconnected).
        access_token: Encrypted OAuth access token.
        refresh_token: Encrypted OAuth refresh token.
        token_expires_at: When the access token expires.
        scopes: List of granted OAuth scopes.
        rate_limit_daily_remaining: Remaining daily API calls.
        rate_limit_minute_remaining: Remaining minute API calls.
        rate_limit_reset_at: When the minute limit resets.
        connected_by: Practice user who established the connection.
        connected_at: When the connection was established.
        last_used_at: When the connection was last used for an API call.
        last_contacts_sync_at: Last successful contacts sync timestamp.
        last_invoices_sync_at: Last successful invoices sync timestamp.
        last_transactions_sync_at: Last successful bank transactions sync timestamp.
        last_accounts_sync_at: Last successful accounts sync timestamp.
        last_full_sync_at: Last successful full sync timestamp.
        sync_in_progress: Whether a sync is currently in progress.
        created_at: When the record was created.
        updated_at: When the record was last modified.

    Relationships:
        tenant: The Clairo tenant this connection belongs to.
        connected_by_user: The practice user who connected.
    """

    __tablename__ = "xero_connections"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Tenant association (RLS enforced)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to tenant (RLS enforced)",
    )

    # Xero organization identity
    xero_tenant_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Xero organization identifier",
    )
    organization_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Display name of the Xero organization",
    )
    status: Mapped[XeroConnectionStatus] = mapped_column(
        Enum(
            XeroConnectionStatus,
            name="xero_connection_status",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=XeroConnectionStatus.ACTIVE,
        server_default="active",
        index=True,
        comment="Current connection status",
    )

    # Connection type (Phase 6b: Client Organization Authorization)
    connection_type: Mapped[XeroConnectionType] = mapped_column(
        Enum(
            XeroConnectionType,
            name="xero_connection_type",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=XeroConnectionType.PRACTICE,
        server_default="practice",
        index=True,
        comment="Whether this is the practice's own Xero or a client's Xero",
    )
    auth_event_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Groups connections from the same bulk authorization flow",
    )

    # Primary contact for this client business
    primary_contact_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Primary contact email for document requests and notifications",
    )

    # OAuth tokens (encrypted at application level)
    access_token: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Encrypted OAuth access token",
    )
    refresh_token: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Encrypted OAuth refresh token",
    )
    token_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When the access token expires",
    )
    scopes: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        comment="List of granted OAuth scopes",
    )

    # Rate limiting
    rate_limit_daily_remaining: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5000,
        server_default="5000",
        comment="Remaining daily API calls",
    )
    rate_limit_minute_remaining: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60,
        server_default="60",
        comment="Remaining minute API calls",
    )
    rate_limit_reset_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the minute limit resets",
    )

    # Connection audit
    connected_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Practice user who established the connection",
    )
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        comment="When the connection was established",
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the connection was last used",
    )

    # Sync tracking (added in 003_xero_sync migration)
    last_contacts_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful contacts sync timestamp",
    )
    last_invoices_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful invoices sync timestamp",
    )
    last_transactions_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful bank transactions sync timestamp",
    )
    last_accounts_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful accounts sync timestamp",
    )
    last_full_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful full sync timestamp",
    )
    sync_in_progress: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Whether a sync is currently in progress",
    )

    # Payroll tracking (added in 004_xero_payroll migration)
    has_payroll_access: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Whether payroll scopes were granted",
    )
    last_payroll_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful payroll sync timestamp",
    )
    last_employees_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful employees sync timestamp",
    )

    # Incremental sync timestamps (Spec 043: Progressive Sync)
    last_credit_notes_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful credit notes sync timestamp",
    )
    last_payments_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful payments sync timestamp",
    )
    last_overpayments_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful overpayments sync timestamp",
    )
    last_prepayments_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful prepayments sync timestamp",
    )
    last_journals_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful journals sync timestamp",
    )
    last_manual_journals_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful manual journals sync timestamp",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        lazy="joined",
    )
    connected_by_user: Mapped["PracticeUser | None"] = relationship(
        "PracticeUser",
        foreign_keys=[connected_by],
        lazy="joined",
    )

    # Quality scoring relationships
    quality_scores: Mapped[list["QualityScore"]] = relationship(
        "QualityScore",
        back_populates="connection",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    quality_issues: Mapped[list["QualityIssue"]] = relationship(
        "QualityIssue",
        back_populates="connection",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # Insight relationships
    insights: Mapped[list["Insight"]] = relationship(
        "Insight",
        back_populates="client",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # Report relationships (Spec 023)
    reports: Mapped[list["XeroReport"]] = relationship(
        "XeroReport",
        back_populates="connection",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # Table constraints
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "xero_tenant_id",
            name="uq_xero_connection_tenant_org",
        ),
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<XeroConnection(id={self.id}, org={self.organization_name}, status={self.status})>"

    @property
    def is_active(self) -> bool:
        """Check if connection is active and healthy."""
        return self.status == XeroConnectionStatus.ACTIVE

    @property
    def needs_refresh(self) -> bool:
        """Check if token needs refresh (expiring within 5 minutes)."""
        if not self.token_expires_at:
            return True
        threshold = datetime.now(UTC) + timedelta(minutes=5)
        return threshold >= self.token_expires_at

    @property
    def is_rate_limited(self) -> bool:
        """Check if currently rate limited (minute limit reached)."""
        return (self.rate_limit_minute_remaining or 0) <= 0

    @property
    def can_make_request(self) -> bool:
        """Check if a request can be made to Xero API."""
        return (
            self.is_active
            and not self.is_rate_limited
            and (self.rate_limit_daily_remaining or 0) > 0
        )


class XeroOAuthState(Base):
    """Temporary OAuth state storage.

    Stores state and PKCE code verifier during OAuth authorization flow.
    Records are cleaned up after use or expiry.

    This table is NOT tenant-scoped because the state token is used
    for lookup during the OAuth callback before tenant context is established.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant (for validation after lookup).
        user_id: Foreign key to the practice user initiating OAuth.
        state: CSRF protection token (unique).
        code_verifier: PKCE code verifier (kept secret).
        redirect_uri: Where to redirect after OAuth completion.
        expires_at: When the state expires.
        created_at: When the state was created.
        used_at: When the state was consumed (null if unused).

    Relationships:
        tenant: The Clairo tenant (for validation).
        user: The practice user who initiated OAuth.
    """

    __tablename__ = "xero_oauth_states"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Context (for validation after state lookup)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key to tenant (for validation)",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Practice user who initiated OAuth",
    )

    # OAuth state
    state: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        default=generate_oauth_state,
        comment="CSRF protection token",
    )
    code_verifier: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default=generate_code_verifier,
        comment="PKCE code verifier (secret)",
    )
    redirect_uri: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Redirect URI after OAuth completion",
    )

    # Client-specific OAuth (Phase 6b.3)
    xpm_client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xpm_clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="XPM client this OAuth is for (null for practice OAuth)",
    )
    connection_type: Mapped[XeroConnectionType] = mapped_column(
        Enum(
            XeroConnectionType,
            name="xero_connection_type",
            create_type=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=XeroConnectionType.PRACTICE,
        server_default="practice",
        comment="Whether this OAuth is for practice or client Xero org",
    )

    # Bulk import flag (Phase 035)
    is_bulk_import: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True for bulk import flows (multi-org OAuth)",
    )

    # Lifecycle
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=default_state_expiry,
        index=True,
        comment="When the state expires",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        comment="When the state was created",
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the state was consumed",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    user: Mapped["PracticeUser"] = relationship("PracticeUser", lazy="joined")
    xpm_client: Mapped["XpmClient | None"] = relationship(
        "XpmClient",
        lazy="joined",
        foreign_keys=[xpm_client_id],
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<XeroOAuthState(id={self.id}, valid={self.is_valid})>"

    @property
    def is_client_oauth(self) -> bool:
        """Check if this OAuth is for a client's Xero org."""
        return self.connection_type == XeroConnectionType.CLIENT

    @property
    def is_expired(self) -> bool:
        """Check if the state has expired."""
        return datetime.now(UTC) >= self.expires_at

    @property
    def is_used(self) -> bool:
        """Check if the state has been consumed."""
        return self.used_at is not None

    @property
    def is_valid(self) -> bool:
        """Check if the state can still be used."""
        return not self.is_expired and not self.is_used


class XeroSyncJob(Base, TimestampMixin):
    """Sync job tracking entity.

    Tracks the execution of a sync operation from Xero.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection.
        sync_type: Type of sync (contacts, invoices, etc.).
        status: Current status of the sync job.
        started_at: When the sync started.
        completed_at: When the sync completed.
        records_processed: Total records processed.
        records_created: Records created during sync.
        records_updated: Records updated during sync.
        records_failed: Records that failed to sync.
        error_message: Error message if sync failed.
        progress_details: Detailed progress information (JSONB).
    """

    __tablename__ = "xero_sync_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sync_type: Mapped[XeroSyncType] = mapped_column(
        Enum(
            XeroSyncType,
            name="xero_sync_type",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    status: Mapped[XeroSyncStatus] = mapped_column(
        Enum(
            XeroSyncStatus,
            name="xero_sync_status",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=XeroSyncStatus.PENDING,
        server_default="pending",
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    records_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    records_created: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    records_updated: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    records_failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    progress_details: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Phased sync fields (Spec 043: Progressive Sync)
    sync_phase: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Current sync phase (1, 2, or 3). Null for legacy full syncs.",
    )
    parent_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_sync_jobs.id", ondelete="CASCADE"),
        nullable=True,
        comment="Links phase jobs to a parent orchestration job",
    )
    triggered_by: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="user",
        server_default="user",
        comment="What triggered this sync: user, schedule, webhook, system",
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the job was cancelled",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")
    parent_job: Mapped["XeroSyncJob | None"] = relationship(
        "XeroSyncJob",
        remote_side="XeroSyncJob.id",
        lazy="select",
    )
    entity_progress: Mapped[list["XeroSyncEntityProgress"]] = relationship(
        "XeroSyncEntityProgress",
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="select",
    )
    post_sync_tasks: Mapped[list["PostSyncTask"]] = relationship(
        "PostSyncTask",
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (Index("ix_xero_sync_jobs_connection_status", "connection_id", "status"),)

    def __repr__(self) -> str:
        return f"<XeroSyncJob(id={self.id}, type={self.sync_type}, status={self.status})>"

    @property
    def is_running(self) -> bool:
        """Check if sync is currently running."""
        return self.status in (XeroSyncStatus.PENDING, XeroSyncStatus.IN_PROGRESS)

    @property
    def is_finished(self) -> bool:
        """Check if sync has finished (success or failure)."""
        return self.status in (
            XeroSyncStatus.COMPLETED,
            XeroSyncStatus.FAILED,
            XeroSyncStatus.CANCELLED,
        )


class XeroClient(Base, TimestampMixin):
    """Synced Xero contact entity.

    Represents a contact synced from Xero as a Clairo client.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection.
        xero_contact_id: Xero's contact identifier.
        name: Contact name.
        email: Contact email.
        contact_number: Contact phone number.
        abn: Validated 11-digit ABN.
        contact_type: Type of contact (customer, supplier, both).
        is_active: Whether the contact is active.
        addresses: JSONB of contact addresses.
        phones: JSONB of contact phone numbers.
        xero_updated_at: When the contact was last updated in Xero.
    """

    __tablename__ = "xero_clients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    xero_contact_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    contact_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    abn: Mapped[str | None] = mapped_column(
        String(11),
        nullable=True,
        comment="Validated 11-digit ABN",
    )
    contact_type: Mapped[XeroContactType] = mapped_column(
        Enum(
            XeroContactType,
            name="xero_contact_type",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=XeroContactType.CUSTOMER,
        server_default="customer",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    addresses: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    phones: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    xero_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "xero_contact_id",
            name="uq_xero_client_connection_contact",
        ),
        Index("ix_xero_clients_tenant_name", "tenant_id", "name"),
    )

    def __repr__(self) -> str:
        return f"<XeroClient(id={self.id}, name={self.name})>"


class XeroInvoice(Base, TimestampMixin):
    """Synced Xero invoice entity.

    Represents an invoice synced from Xero.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection.
        client_id: Foreign key to the synced client (if exists).
        xero_invoice_id: Xero's invoice identifier.
        xero_contact_id: Xero's contact identifier for reference.
        invoice_number: Invoice number.
        invoice_type: Type (ACCREC or ACCPAY).
        status: Invoice status.
        issue_date: Invoice issue date.
        due_date: Invoice due date.
        subtotal: Subtotal amount.
        tax_amount: Tax amount.
        total_amount: Total amount.
        currency: Currency code.
        line_items: JSONB of line items with BAS-relevant data.
        xero_updated_at: When the invoice was last updated in Xero.
    """

    __tablename__ = "xero_invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    xero_invoice_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    xero_contact_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Stored for reference even if client not synced",
    )
    invoice_number: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    invoice_type: Mapped[XeroInvoiceType] = mapped_column(
        Enum(
            XeroInvoiceType,
            name="xero_invoice_type",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    status: Mapped[XeroInvoiceStatus] = mapped_column(
        Enum(
            XeroInvoiceStatus,
            name="xero_invoice_status",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    issue_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    due_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="AUD",
        server_default="AUD",
    )
    line_items: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Line items with account_code, tax_type, amounts",
    )
    xero_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")
    client: Mapped["XeroClient | None"] = relationship("XeroClient", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "xero_invoice_id",
            name="uq_xero_invoice_connection_invoice",
        ),
        Index("ix_xero_invoices_tenant_date", "tenant_id", "issue_date"),
        Index("ix_xero_invoices_tenant_type", "tenant_id", "invoice_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<XeroInvoice(id={self.id}, number={self.invoice_number}, type={self.invoice_type})>"
        )


class XeroBankTransaction(Base, TimestampMixin):
    """Synced Xero bank transaction entity.

    Represents a bank transaction synced from Xero.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection.
        client_id: Foreign key to the synced client (if contact present).
        xero_transaction_id: Xero's transaction identifier.
        xero_contact_id: Xero's contact identifier.
        xero_bank_account_id: Xero's bank account identifier.
        transaction_type: Type of transaction.
        status: Transaction status.
        transaction_date: Transaction date.
        reference: Transaction reference.
        subtotal: Subtotal amount.
        tax_amount: Tax amount.
        total_amount: Total amount.
        line_items: JSONB of line items with GST data.
        xero_updated_at: When the transaction was last updated in Xero.
    """

    __tablename__ = "xero_bank_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    xero_transaction_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    xero_contact_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    xero_bank_account_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    transaction_type: Mapped[XeroBankTransactionType] = mapped_column(
        Enum(
            XeroBankTransactionType,
            name="xero_bank_transaction_type",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    line_items: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    xero_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")
    client: Mapped["XeroClient | None"] = relationship("XeroClient", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "xero_transaction_id",
            name="uq_xero_transaction_connection_txn",
        ),
        Index("ix_xero_transactions_tenant_date", "tenant_id", "transaction_date"),
    )

    def __repr__(self) -> str:
        return f"<XeroBankTransaction(id={self.id}, type={self.transaction_type})>"


class XeroAccount(Base, TimestampMixin):
    """Synced Xero chart of accounts entity.

    Represents an account synced from Xero's chart of accounts.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection.
        xero_account_id: Xero's account identifier.
        account_code: Account code.
        account_name: Account name.
        account_type: Account type (e.g., BANK, CURRENT, FIXED).
        account_class: Account class (asset, liability, etc.).
        default_tax_type: Default tax type for this account.
        is_active: Whether the account is active.
        reporting_code: BAS reporting code for mapping.
        is_bas_relevant: Whether relevant to BAS calculations.
    """

    __tablename__ = "xero_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    xero_account_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    account_code: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )
    account_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    account_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    account_class: Mapped[XeroAccountClass | None] = mapped_column(
        Enum(
            XeroAccountClass,
            name="xero_account_class",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=True,
    )
    default_tax_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    reporting_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="BAS reporting code for mapping",
    )
    is_bas_relevant: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True if relevant to BAS calculations",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "xero_account_id",
            name="uq_xero_account_connection_account",
        ),
        Index("ix_xero_accounts_tenant_code", "tenant_id", "account_code"),
    )

    def __repr__(self) -> str:
        return f"<XeroAccount(id={self.id}, code={self.account_code}, name={self.account_name})>"


class XeroEmployee(Base, TimestampMixin):
    """Synced Xero employee entity.

    Represents an employee synced from Xero Payroll API.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection.
        xero_employee_id: Xero's employee identifier.
        first_name: Employee first name.
        last_name: Employee last name.
        email: Employee email.
        status: Employee status (active, terminated).
        start_date: Employment start date.
        termination_date: Employment termination date.
        job_title: Employee job title.
        xero_updated_at: When the employee was last updated in Xero.
    """

    __tablename__ = "xero_employees"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    xero_employee_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    first_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    last_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    status: Mapped[XeroEmployeeStatus] = mapped_column(
        Enum(
            XeroEmployeeStatus,
            name="xero_employee_status",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=XeroEmployeeStatus.ACTIVE,
        server_default="active",
    )
    start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    termination_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    job_title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    xero_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "xero_employee_id",
            name="uq_xero_employee_connection_employee",
        ),
        Index("ix_xero_employees_tenant_status", "tenant_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<XeroEmployee(id={self.id}, name={self.first_name} {self.last_name})>"

    @property
    def full_name(self) -> str:
        """Get employee full name."""
        parts = [p for p in [self.first_name, self.last_name] if p]
        return " ".join(parts) or "Unknown"

    @property
    def is_active(self) -> bool:
        """Check if employee is active."""
        return self.status == XeroEmployeeStatus.ACTIVE


class XeroPayRun(Base, TimestampMixin):
    """Synced Xero pay run entity.

    Represents a pay run synced from Xero Payroll API.
    Contains aggregated totals for BAS PAYG withholding calculations.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection.
        xero_pay_run_id: Xero's pay run identifier.
        payroll_calendar_id: Xero payroll calendar identifier.
        pay_run_status: Pay run status (draft, posted).
        period_start: Pay period start date.
        period_end: Pay period end date.
        payment_date: Payment date.
        total_wages: Total wages paid (BAS W1).
        total_tax: Total PAYG tax withheld (BAS W2/4).
        total_super: Total superannuation.
        total_deductions: Total deductions.
        total_reimbursements: Total reimbursements.
        total_net_pay: Total net pay.
        employee_count: Number of employees in pay run.
        xero_updated_at: When the pay run was last updated in Xero.
    """

    __tablename__ = "xero_pay_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    xero_pay_run_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    payroll_calendar_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    pay_run_status: Mapped[XeroPayRunStatus] = mapped_column(
        Enum(
            XeroPayRunStatus,
            name="xero_pay_run_status",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=XeroPayRunStatus.DRAFT,
        server_default="draft",
    )
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    payment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    # Financial totals for BAS
    total_wages: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
        comment="Total wages paid (BAS W1)",
    )
    total_tax: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
        comment="Total PAYG tax withheld (BAS W2/4)",
    )
    total_super: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
        comment="Total superannuation",
    )
    total_deductions: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    total_reimbursements: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    total_net_pay: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    employee_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    xero_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "xero_pay_run_id",
            name="uq_xero_pay_run_connection_payrun",
        ),
        Index("ix_xero_pay_runs_tenant_payment_date", "tenant_id", "payment_date"),
        Index("ix_xero_pay_runs_connection_period", "connection_id", "period_start", "period_end"),
    )

    def __repr__(self) -> str:
        return f"<XeroPayRun(id={self.id}, period={self.period_start}-{self.period_end}, status={self.pay_run_status})>"

    @property
    def is_posted(self) -> bool:
        """Check if pay run is posted."""
        return self.pay_run_status == XeroPayRunStatus.POSTED


# =============================================================================
# XPM Client Model (Phase 6b: Client Organization Authorization)
# =============================================================================


class XpmClientConnectionStatus(str, enum.Enum):
    """Status of an XPM client's Xero organization connection.

    - NOT_CONNECTED: Client exists in XPM but Xero org not authorized
    - CONNECTED: Client's Xero org is authorized and linked
    - DISCONNECTED: Previously connected but access revoked
    - NO_ACCESS: Accountant doesn't have user access to client's Xero org
    """

    NOT_CONNECTED = "not_connected"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    NO_ACCESS = "no_access"

    def __str__(self) -> str:
        return self.value


class XpmClient(Base, TimestampMixin):
    """XPM Practice Client entity.

    Represents a client business from Xero Practice Manager (XPM).
    This is the accountant's practice client - a business they manage BAS for.

    Each XPM client may have their own Xero organization with financial data.
    The `xero_connection_id` links to the authorized Xero organization when connected.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the Clairo tenant (the accounting practice).
        xpm_client_id: XPM's unique client identifier.
        xero_connection_id: FK to XeroConnection when client's Xero is authorized.
        name: Client business name.
        abn: Australian Business Number (11 digits).
        email: Primary contact email.
        phone: Primary contact phone.
        address: Business address (JSONB).
        contact_person: Primary contact name.
        xero_org_name: Cached Xero organization name (for matching).
        connection_status: Status of Xero organization connection.
        xero_connected_at: When client's Xero org was authorized.
        xpm_updated_at: Last update timestamp from XPM.
        extra_data: Additional XPM metadata (JSONB).
    """

    __tablename__ = "xpm_clients"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Tenant association (the accounting practice)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to Clairo tenant (the accounting practice)",
    )

    # XPM identity
    xpm_client_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="XPM's unique client identifier",
    )

    # Link to authorized Xero organization (nullable until connected)
    xero_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="FK to XeroConnection when client's Xero org is authorized",
    )

    # Client business details
    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
        comment="Client business name",
    )
    abn: Mapped[str | None] = mapped_column(
        String(11),
        nullable=True,
        index=True,
        comment="Australian Business Number (11 digits)",
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Primary contact email",
    )
    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Primary contact phone",
    )
    address: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Business address",
    )
    contact_person: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Primary contact name",
    )

    # Xero organization matching
    xero_org_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Cached Xero organization name (for matching)",
    )
    connection_status: Mapped[XpmClientConnectionStatus] = mapped_column(
        Enum(
            XpmClientConnectionStatus,
            name="xpm_client_connection_status",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=XpmClientConnectionStatus.NOT_CONNECTED,
        server_default="not_connected",
        index=True,
        comment="Status of Xero organization connection",
    )
    xero_connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When client's Xero org was authorized",
    )

    # XPM sync tracking
    xpm_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last update timestamp from XPM",
    )

    # Extra metadata from XPM
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional XPM metadata",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    xero_connection: Mapped["XeroConnection | None"] = relationship(
        "XeroConnection",
        lazy="joined",
        foreign_keys=[xero_connection_id],
    )

    # Table constraints
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "xpm_client_id",
            name="uq_xpm_client_tenant_xpm_id",
        ),
        Index("ix_xpm_clients_tenant_name", "tenant_id", "name"),
        Index("ix_xpm_clients_tenant_abn", "tenant_id", "abn"),
        Index("ix_xpm_clients_tenant_status", "tenant_id", "connection_status"),
    )

    def __repr__(self) -> str:
        return f"<XpmClient(id={self.id}, name={self.name}, status={self.connection_status})>"

    @property
    def is_connected(self) -> bool:
        """Check if client's Xero org is connected."""
        return self.connection_status == XpmClientConnectionStatus.CONNECTED

    @property
    def needs_authorization(self) -> bool:
        """Check if client needs Xero authorization."""
        return self.connection_status in (
            XpmClientConnectionStatus.NOT_CONNECTED,
            XpmClientConnectionStatus.DISCONNECTED,
        )


# =============================================================================
# Xero Reports Models (Spec 023)
# =============================================================================


class XeroReport(Base, TimestampMixin):
    """Cached Xero report data.

    Spec 023: Xero Reports API Integration

    Reports are fetched from Xero and cached locally for:
    - Fast retrieval without API calls
    - AI agent context enrichment
    - Historical trend analysis
    - ATO compliance (7-year retention)

    Each report is uniquely identified by:
    - connection_id (which client)
    - report_type (P&L, Balance Sheet, etc.)
    - period_key (e.g., "2025-FY", "2025-12", "2025-12-31")
    """

    __tablename__ = "xero_reports"

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Multi-tenancy
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Report identification
    report_type: Mapped[XeroReportType] = mapped_column(
        Enum(
            XeroReportType,
            name="xeroreporttype",
            create_constraint=True,
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
    )

    # Period identification (composite with report_type for uniqueness)
    period_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Period identifier: '2025-FY', '2025-Q4', '2025-12', '2025-12-31'",
    )
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    as_of_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="For point-in-time reports (Balance Sheet, Aged)",
    )

    # Report metadata from Xero
    xero_report_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    report_name: Mapped[str] = mapped_column(String(255), nullable=False)
    report_titles: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    xero_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When Xero last updated this report",
    )

    # Raw report data (flexible structure)
    rows_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Full Rows array from Xero response",
    )

    # Extracted summary fields (for quick queries)
    summary_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Extracted key metrics: revenue, net_profit, current_ratio, etc.",
    )

    # Sync metadata
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    cache_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When this cached data should be considered stale",
    )
    is_current_period: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="True if period includes today (affects cache TTL)",
    )

    # Report parameters used (for cache key matching)
    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Query params used: timeframe, periods, standardLayout, etc.",
    )

    # Relationships
    connection: Mapped["XeroConnection"] = relationship(
        "XeroConnection",
        back_populates="reports",
        lazy="joined",
    )

    # Constraints
    __table_args__ = (
        # Unique report per connection/type/period
        UniqueConstraint(
            "connection_id",
            "report_type",
            "period_key",
            name="uq_xero_reports_connection_type_period",
        ),
        # Index for common queries
        Index(
            "ix_xero_reports_tenant_type",
            "tenant_id",
            "report_type",
        ),
        Index(
            "ix_xero_reports_cache_expires",
            "cache_expires_at",
        ),
    )

    def __repr__(self) -> str:
        return f"<XeroReport(id={self.id}, type={self.report_type}, period={self.period_key})>"

    @property
    def is_fresh(self) -> bool:
        """Check if cached data is still fresh."""
        return datetime.now(UTC) < self.cache_expires_at

    @property
    def is_stale(self) -> bool:
        """Check if cached data is stale and should be refreshed."""
        return not self.is_fresh


class XeroReportSyncJob(Base, TimestampMixin):
    """Tracks individual report sync operations.

    Spec 023: Xero Reports API Integration

    Used for:
    - Audit trail of all sync attempts
    - Retry logic for failed syncs
    - Performance monitoring (duration, error rates)
    """

    __tablename__ = "xero_report_sync_jobs"

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Multi-tenancy
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Job details
    report_type: Mapped[XeroReportType] = mapped_column(
        Enum(
            XeroReportType,
            name="xeroreporttype",
            create_constraint=False,
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
    )
    status: Mapped[XeroReportSyncStatus] = mapped_column(
        Enum(
            XeroReportSyncStatus,
            name="xeroreportsyncstatus",
            create_constraint=True,
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
        default=XeroReportSyncStatus.PENDING,
    )

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Total sync duration in milliseconds",
    )

    # Results
    rows_fetched: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of rows in fetched report",
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_reports.id", ondelete="SET NULL"),
        nullable=True,
        comment="Resulting report record if successful",
    )

    # Error handling
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Request context
    triggered_by: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="scheduled",
        comment="'scheduled', 'on_demand', 'retry'",
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="User who triggered on-demand sync",
    )

    # Constraints
    __table_args__ = (
        Index(
            "ix_xero_report_sync_jobs_status",
            "status",
            "next_retry_at",
        ),
    )

    def __repr__(self) -> str:
        return f"<XeroReportSyncJob(id={self.id}, type={self.report_type}, status={self.status})>"


# =============================================================================
# Credit Notes, Payments, Journals Models (Spec 024)
# =============================================================================


class XeroCreditNote(Base, TimestampMixin):
    """Synced Xero credit note entity.

    Spec 024: Credit Notes, Payments & Journals

    Credit notes reduce amounts owed:
    - ACCRECCREDIT: Customer credit (reduces AR)
    - ACCPAYCREDIT: Supplier credit (reduces AP)

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection.
        xero_credit_note_id: Xero's credit note identifier.
        credit_note_number: Credit note number.
        credit_note_type: Type (ACCRECCREDIT or ACCPAYCREDIT).
        xero_contact_id: Xero contact identifier.
        status: Credit note status.
        issue_date: Credit note issue date.
        due_date: Credit note due date.
        subtotal: Subtotal amount.
        tax_amount: Tax amount.
        total_amount: Total amount.
        remaining_credit: Unallocated credit amount.
        currency: Currency code.
        currency_rate: Exchange rate.
        line_items: JSONB of line items.
        xero_updated_at: When the credit note was last updated in Xero.
    """

    __tablename__ = "xero_credit_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    xero_credit_note_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    credit_note_number: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    credit_note_type: Mapped[XeroCreditNoteType] = mapped_column(
        Enum(
            XeroCreditNoteType,
            name="xero_credit_note_type",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    xero_contact_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Xero contact ID for reference",
    )
    status: Mapped[XeroCreditNoteStatus] = mapped_column(
        Enum(
            XeroCreditNoteStatus,
            name="xero_credit_note_status",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    issue_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    due_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    line_amount_types: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Exclusive, Inclusive, or NoTax",
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    remaining_credit: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
        comment="Unallocated credit remaining",
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="AUD",
        server_default="AUD",
    )
    currency_rate: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6),
        nullable=False,
        default=Decimal("1.0"),
        server_default="1.0",
    )
    line_items: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Line items with account_code, tax_type, amounts",
    )
    xero_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")
    allocations: Mapped[list["XeroCreditNoteAllocation"]] = relationship(
        "XeroCreditNoteAllocation",
        back_populates="credit_note",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "xero_credit_note_id",
            name="uq_xero_credit_note_connection_cn",
        ),
        Index("ix_xero_credit_notes_tenant_date", "tenant_id", "issue_date"),
        Index("ix_xero_credit_notes_tenant_type", "tenant_id", "credit_note_type"),
        Index("ix_xero_credit_notes_tenant_status", "tenant_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<XeroCreditNote(id={self.id}, number={self.credit_note_number}, type={self.credit_note_type})>"

    @property
    def is_sales_credit(self) -> bool:
        """Check if this is a sales credit note (to customer)."""
        return self.credit_note_type == XeroCreditNoteType.ACCRECCREDIT

    @property
    def is_purchase_credit(self) -> bool:
        """Check if this is a purchase credit note (from supplier)."""
        return self.credit_note_type == XeroCreditNoteType.ACCPAYCREDIT

    @property
    def is_fully_allocated(self) -> bool:
        """Check if credit note is fully allocated."""
        return self.remaining_credit <= Decimal("0.00")


class XeroCreditNoteAllocation(Base, TimestampMixin):
    """Xero credit note allocation entity.

    Spec 024: Credit Notes, Payments & Journals

    Represents how a credit note is applied to invoices.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant (RLS enforced).
        credit_note_id: Foreign key to the credit note.
        xero_allocation_id: Xero's allocation identifier (if provided).
        xero_invoice_id: Xero invoice this credit is allocated to.
        amount: Amount allocated.
        allocation_date: Date of allocation.
    """

    __tablename__ = "xero_credit_note_allocations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    credit_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_credit_notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    xero_allocation_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    xero_invoice_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Xero invoice ID this credit is allocated to",
    )
    invoice_number: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Invoice number for display",
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    allocation_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    credit_note: Mapped["XeroCreditNote"] = relationship(
        "XeroCreditNote",
        back_populates="allocations",
        lazy="joined",
    )

    __table_args__ = (
        Index("ix_xero_cn_alloc_credit_note", "credit_note_id"),
        Index("ix_xero_cn_alloc_invoice", "xero_invoice_id"),
    )

    def __repr__(self) -> str:
        return f"<XeroCreditNoteAllocation(id={self.id}, amount={self.amount})>"


class XeroPayment(Base, TimestampMixin):
    """Synced Xero payment entity.

    Spec 024: Credit Notes, Payments & Journals

    Represents a payment against an invoice or credit note.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection.
        xero_payment_id: Xero's payment identifier.
        payment_type: Type of payment.
        status: Payment status.
        payment_date: Date of payment.
        amount: Payment amount.
        currency_rate: Exchange rate.
        reference: Payment reference.
        is_reconciled: Whether payment is reconciled.
        xero_invoice_id: Associated invoice ID (if applicable).
        xero_credit_note_id: Associated credit note ID (if applicable).
        xero_account_id: Bank account ID.
        xero_updated_at: When the payment was last updated in Xero.
    """

    __tablename__ = "xero_payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    xero_payment_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    payment_type: Mapped[XeroPaymentType] = mapped_column(
        Enum(
            XeroPaymentType,
            name="xero_payment_type",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    status: Mapped[XeroPaymentStatus] = mapped_column(
        Enum(
            XeroPaymentStatus,
            name="xero_payment_status",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    payment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    currency_rate: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6),
        nullable=False,
        default=Decimal("1.0"),
        server_default="1.0",
    )
    reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    is_reconciled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    xero_invoice_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Xero invoice ID this payment applies to",
    )
    xero_credit_note_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Xero credit note ID this payment applies to",
    )
    xero_account_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Xero bank account ID",
    )
    account_code: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="Bank account code for display",
    )
    xero_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "xero_payment_id",
            name="uq_xero_payment_connection_payment",
        ),
        Index("ix_xero_payments_tenant_date", "tenant_id", "payment_date"),
        Index("ix_xero_payments_tenant_type", "tenant_id", "payment_type"),
    )

    def __repr__(self) -> str:
        return f"<XeroPayment(id={self.id}, type={self.payment_type}, amount={self.amount})>"


class XeroOverpayment(Base, TimestampMixin):
    """Synced Xero overpayment entity.

    Spec 024: Credit Notes, Payments & Journals

    An overpayment occurs when a customer pays more than the invoice amount.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection.
        xero_overpayment_id: Xero's overpayment identifier.
        overpayment_type: Type (RECEIVE-OVERPAYMENT or SPEND-OVERPAYMENT).
        xero_contact_id: Xero contact identifier.
        status: Overpayment status.
        overpayment_date: Date of overpayment.
        subtotal: Subtotal amount.
        tax_amount: Tax amount.
        total_amount: Total amount.
        remaining_credit: Unallocated amount.
        currency: Currency code.
        line_items: JSONB of line items.
        xero_updated_at: When the overpayment was last updated in Xero.
    """

    __tablename__ = "xero_overpayments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    xero_overpayment_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    overpayment_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="RECEIVE-OVERPAYMENT or SPEND-OVERPAYMENT",
    )
    xero_contact_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    status: Mapped[XeroOverpaymentStatus] = mapped_column(
        Enum(
            XeroOverpaymentStatus,
            name="xero_overpayment_status",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    overpayment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    remaining_credit: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="AUD",
        server_default="AUD",
    )
    line_items: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    xero_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "xero_overpayment_id",
            name="uq_xero_overpayment_connection_op",
        ),
        Index("ix_xero_overpayments_tenant_date", "tenant_id", "overpayment_date"),
    )

    def __repr__(self) -> str:
        return f"<XeroOverpayment(id={self.id}, type={self.overpayment_type}, total={self.total_amount})>"


class XeroPrepayment(Base, TimestampMixin):
    """Synced Xero prepayment entity.

    Spec 024: Credit Notes, Payments & Journals

    A prepayment is a payment received before an invoice is created.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection.
        xero_prepayment_id: Xero's prepayment identifier.
        prepayment_type: Type (RECEIVE-PREPAYMENT or SPEND-PREPAYMENT).
        xero_contact_id: Xero contact identifier.
        status: Prepayment status.
        prepayment_date: Date of prepayment.
        subtotal: Subtotal amount.
        tax_amount: Tax amount.
        total_amount: Total amount.
        remaining_credit: Unallocated amount.
        currency: Currency code.
        line_items: JSONB of line items.
        xero_updated_at: When the prepayment was last updated in Xero.
    """

    __tablename__ = "xero_prepayments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    xero_prepayment_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    prepayment_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="RECEIVE-PREPAYMENT or SPEND-PREPAYMENT",
    )
    xero_contact_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    status: Mapped[XeroPrepaymentStatus] = mapped_column(
        Enum(
            XeroPrepaymentStatus,
            name="xero_prepayment_status",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    prepayment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    remaining_credit: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="AUD",
        server_default="AUD",
    )
    line_items: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    xero_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "xero_prepayment_id",
            name="uq_xero_prepayment_connection_pp",
        ),
        Index("ix_xero_prepayments_tenant_date", "tenant_id", "prepayment_date"),
    )

    def __repr__(self) -> str:
        return f"<XeroPrepayment(id={self.id}, type={self.prepayment_type}, total={self.total_amount})>"


class XeroJournal(Base, TimestampMixin):
    """Synced Xero journal entity.

    Spec 024: Credit Notes, Payments & Journals

    System-generated journals from Xero's double-entry accounting.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection.
        xero_journal_id: Xero's journal identifier.
        journal_number: Sequential journal number.
        journal_date: Date of journal.
        source_id: ID of source transaction (invoice, payment, etc.).
        source_type: Type of source transaction.
        reference: Journal reference.
        journal_lines: JSONB of journal line entries.
        xero_created_at: When the journal was created in Xero.
    """

    __tablename__ = "xero_journals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    xero_journal_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    journal_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    journal_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    source_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="ID of source transaction",
    )
    source_type: Mapped[XeroJournalSourceType | None] = mapped_column(
        Enum(
            XeroJournalSourceType,
            name="xero_journal_source_type",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=True,
    )
    reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    journal_lines: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Journal line entries with account, debit/credit amounts",
    )
    xero_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "xero_journal_id",
            name="uq_xero_journal_connection_journal",
        ),
        Index("ix_xero_journals_tenant_date", "tenant_id", "journal_date"),
        Index("ix_xero_journals_source", "source_id", "source_type"),
        Index("ix_xero_journals_number", "connection_id", "journal_number"),
    )

    def __repr__(self) -> str:
        return (
            f"<XeroJournal(id={self.id}, number={self.journal_number}, source={self.source_type})>"
        )


class XeroManualJournal(Base, TimestampMixin):
    """Synced Xero manual journal entity.

    Spec 024: Credit Notes, Payments & Journals

    Manual journals are user-created adjusting entries.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection.
        xero_manual_journal_id: Xero's manual journal identifier.
        narration: Journal description/narration.
        status: Manual journal status.
        journal_date: Date of journal.
        line_amount_types: How tax is handled on lines.
        show_on_cash_basis: Whether to show on cash basis reports.
        journal_lines: JSONB of journal line entries.
        xero_updated_at: When the manual journal was last updated in Xero.
    """

    __tablename__ = "xero_manual_journals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    xero_manual_journal_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    narration: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Journal description/reason",
    )
    status: Mapped[XeroManualJournalStatus] = mapped_column(
        Enum(
            XeroManualJournalStatus,
            name="xero_manual_journal_status",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    journal_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    line_amount_types: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="NoTax, Exclusive, or Inclusive",
    )
    show_on_cash_basis: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="Whether to show on cash basis reports",
    )
    journal_lines: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Journal line entries with account, amounts, tax",
    )
    xero_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "xero_manual_journal_id",
            name="uq_xero_manual_journal_connection_mj",
        ),
        Index("ix_xero_manual_journals_tenant_date", "tenant_id", "journal_date"),
        Index("ix_xero_manual_journals_tenant_status", "tenant_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<XeroManualJournal(id={self.id}, narration={self.narration[:30] if self.narration else 'None'}...)>"

    @property
    def is_posted(self) -> bool:
        """Check if the manual journal is posted."""
        return self.status == XeroManualJournalStatus.POSTED


# =============================================================================
# Spec 025: Fixed Assets & Enhanced Analysis Models
# =============================================================================


class XeroAssetType(Base, TimestampMixin):
    """Asset type defining default depreciation behavior.

    Spec 025: Fixed Assets & Enhanced Analysis
    """

    __tablename__ = "xero_asset_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    xero_asset_type_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Xero's asset type ID",
    )
    asset_type_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Name of the asset type",
    )
    fixed_asset_account_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Balance sheet account ID",
    )
    depreciation_expense_account_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="P&L depreciation expense account ID",
    )
    accumulated_depreciation_account_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Accumulated depreciation account ID",
    )
    depreciation_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Depreciation method",
    )
    averaging_method: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Averaging method (FullMonth or ActualDays)",
    )
    depreciation_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="Annual depreciation rate (%)",
    )
    effective_life_years: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Effective life in years",
    )
    calculation_method: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="Rate",
        comment="How depreciation is calculated (Rate/Life)",
    )
    locks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of locked periods",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")
    assets: Mapped[list["XeroAsset"]] = relationship("XeroAsset", back_populates="asset_type")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "xero_asset_type_id",
            name="uq_xero_asset_type_connection_type",
        ),
        Index("ix_xero_asset_types_tenant", "tenant_id"),
        Index("ix_xero_asset_types_connection", "connection_id"),
    )

    def __repr__(self) -> str:
        return f"<XeroAssetType(id={self.id}, name={self.asset_type_name})>"


class XeroAsset(Base, TimestampMixin):
    """Fixed asset with depreciation details.

    Spec 025: Fixed Assets & Enhanced Analysis
    """

    __tablename__ = "xero_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    xero_asset_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Xero's asset ID",
    )
    asset_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_asset_types.id", ondelete="SET NULL"),
        nullable=True,
    )
    asset_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Asset name",
    )
    asset_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Asset register number",
    )
    serial_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Serial/model number",
    )
    purchase_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Date asset was purchased",
    )
    purchase_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Original cost",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Draft/Registered/Disposed",
    )
    book_value: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Current book value",
    )
    warranty_expiry: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Warranty expiration date",
    )
    # Book depreciation
    book_depreciation_method: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        comment="Book depreciation method",
    )
    book_depreciation_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="Book depreciation rate (%)",
    )
    book_effective_life_years: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Book effective life in years",
    )
    book_current_capital_gain: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Book capital gain on disposal",
    )
    book_current_gain_loss: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Book gain/loss on disposal",
    )
    book_depreciation_start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Date book depreciation started",
    )
    book_cost_limit: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Book cost limit for depreciation",
    )
    book_residual_value: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Book residual value at end of life",
    )
    book_prior_accum_depreciation: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Book depreciation from prior years",
    )
    book_current_accum_depreciation: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Book current year accumulated depreciation",
    )
    # Tax depreciation
    tax_depreciation_method: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        comment="Tax depreciation method",
    )
    tax_depreciation_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="Tax depreciation rate (%)",
    )
    tax_effective_life_years: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Tax effective life in years",
    )
    tax_current_capital_gain: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Tax capital gain on disposal",
    )
    tax_current_gain_loss: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Tax gain/loss on disposal",
    )
    tax_depreciation_start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Date tax depreciation started",
    )
    tax_cost_limit: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Tax cost limit for depreciation",
    )
    tax_residual_value: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Tax residual value at end of life",
    )
    tax_prior_accum_depreciation: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Tax depreciation from prior years",
    )
    tax_current_accum_depreciation: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Tax current year accumulated depreciation",
    )
    # Disposal
    disposal_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Date disposed",
    )
    disposal_price: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Sale/disposal price",
    )
    is_billed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")
    asset_type: Mapped["XeroAssetType | None"] = relationship(
        "XeroAssetType", back_populates="assets"
    )

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "xero_asset_id",
            name="uq_xero_asset_connection_asset",
        ),
        Index("ix_xero_assets_tenant", "tenant_id"),
        Index("ix_xero_assets_connection", "connection_id"),
        Index("ix_xero_assets_status", "status"),
        Index("ix_xero_assets_purchase_date", "purchase_date"),
        Index("ix_xero_assets_type", "asset_type_id"),
    )

    def __repr__(self) -> str:
        return f"<XeroAsset(id={self.id}, name={self.asset_name}, status={self.status})>"

    @property
    def total_depreciation(self) -> Decimal:
        """Calculate total accumulated depreciation (book)."""
        return (self.book_prior_accum_depreciation or Decimal(0)) + (
            self.book_current_accum_depreciation or Decimal(0)
        )

    @property
    def is_fully_depreciated(self) -> bool:
        """Check if asset is fully depreciated."""
        return self.book_value <= (self.book_residual_value or Decimal(0))

    # Compatibility properties for depreciation service
    @property
    def asset_type_name(self) -> str | None:
        """Get asset type name from related asset_type."""
        return self.asset_type.asset_type_name if self.asset_type else None

    @property
    def book_depreciation_this_year(self) -> Decimal:
        """Alias for book_current_accum_depreciation (current year depreciation)."""
        return self.book_current_accum_depreciation or Decimal(0)

    @property
    def book_accumulated_depreciation(self) -> Decimal:
        """Total accumulated depreciation (prior + current year)."""
        return (self.book_prior_accum_depreciation or Decimal(0)) + (
            self.book_current_accum_depreciation or Decimal(0)
        )

    @property
    def book_depreciation_effective_life_years(self) -> int | None:
        """Get effective life years, falling back to asset type default."""
        if self.book_effective_life_years is not None:
            return self.book_effective_life_years
        if self.asset_type:
            return self.asset_type.effective_life_years
        return None

    @property
    def tax_depreciation_this_year(self) -> Decimal:
        """Tax depreciation this year."""
        return self.tax_current_accum_depreciation or Decimal(0)

    @property
    def tax_accumulated_depreciation(self) -> Decimal:
        """Tax accumulated depreciation (prior + current year)."""
        return (self.tax_prior_accum_depreciation or Decimal(0)) + (
            self.tax_current_accum_depreciation or Decimal(0)
        )


class XeroPurchaseOrder(Base, TimestampMixin):
    """Purchase order from Xero.

    Spec 025: Fixed Assets & Enhanced Analysis
    """

    __tablename__ = "xero_purchase_orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    xero_purchase_order_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Xero's PO ID",
    )
    contact_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Xero contact ID (vendor)",
    )
    contact_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Vendor name (denormalized)",
    )
    purchase_order_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="PO number",
    )
    reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="PO date",
    )
    delivery_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Expected delivery date",
    )
    expected_arrival_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Expected arrival date from Xero",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="DRAFT/SUBMITTED/AUTHORISED/BILLED/DELETED",
    )
    sub_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
    )
    total_tax: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
    )
    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="AUD",
    )
    currency_rate: Mapped[Decimal] = mapped_column(
        Numeric(15, 6),
        nullable=False,
        default=1,
    )
    line_items: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Line item details with tracking",
    )
    sent_to_contact: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    xero_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "xero_purchase_order_id",
            name="uq_xero_purchase_order_connection_po",
        ),
        Index("ix_xero_purchase_orders_tenant", "tenant_id"),
        Index("ix_xero_purchase_orders_connection", "connection_id"),
        Index("ix_xero_purchase_orders_status", "status"),
        Index("ix_xero_purchase_orders_date", "date"),
    )

    def __repr__(self) -> str:
        return f"<XeroPurchaseOrder(id={self.id}, number={self.purchase_order_number}, status={self.status})>"

    @property
    def is_outstanding(self) -> bool:
        """Check if PO is still outstanding (not billed or deleted)."""
        return self.status in ("DRAFT", "SUBMITTED", "AUTHORISED")


class XeroRepeatingInvoice(Base, TimestampMixin):
    """Repeating invoice template from Xero.

    Spec 025: Fixed Assets & Enhanced Analysis
    """

    __tablename__ = "xero_repeating_invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    xero_repeating_invoice_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Xero's repeating invoice ID",
    )
    contact_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Xero contact ID",
    )
    contact_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Contact name (denormalized)",
    )
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="ACCREC (sales) or ACCPAY (bills)",
    )
    reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="DRAFT or AUTHORISED",
    )
    schedule_period: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Number of schedule units between invoices",
    )
    schedule_unit: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="WEEKLY/MONTHLY/YEARLY",
    )
    schedule_due_date: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Days after invoice date for due date",
    )
    schedule_due_date_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    schedule_start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    schedule_next_scheduled_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Next scheduled invoice date",
    )
    schedule_end_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    sub_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
    )
    total_tax: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
    )
    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="AUD",
    )
    line_items: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "xero_repeating_invoice_id",
            name="uq_xero_repeating_invoice_connection_ri",
        ),
        Index("ix_xero_repeating_invoices_tenant", "tenant_id"),
        Index("ix_xero_repeating_invoices_connection", "connection_id"),
        Index("ix_xero_repeating_invoices_next_date", "schedule_next_scheduled_date"),
        Index("ix_xero_repeating_invoices_type", "type"),
    )

    def __repr__(self) -> str:
        return f"<XeroRepeatingInvoice(id={self.id}, type={self.type}, total={self.total})>"

    @property
    def is_sales(self) -> bool:
        """Check if this is a sales (ACCREC) repeating invoice."""
        return self.type == "ACCREC"

    @property
    def is_bill(self) -> bool:
        """Check if this is a bill (ACCPAY) repeating invoice."""
        return self.type == "ACCPAY"

    @property
    def annualized_amount(self) -> Decimal:
        """Calculate annualized amount based on schedule."""
        if self.schedule_unit == "WEEKLY":
            return self.total * 52 // self.schedule_period
        elif self.schedule_unit == "MONTHLY":
            return self.total * 12 // self.schedule_period
        elif self.schedule_unit == "YEARLY":
            return self.total // self.schedule_period
        return self.total


class XeroTrackingCategory(Base, TimestampMixin):
    """Tracking category from Xero.

    Spec 025: Fixed Assets & Enhanced Analysis
    """

    __tablename__ = "xero_tracking_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    xero_tracking_category_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Xero's tracking category ID",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="ACTIVE/ARCHIVED/DELETED",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")
    options: Mapped[list["XeroTrackingOption"]] = relationship(
        "XeroTrackingOption",
        back_populates="category",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "xero_tracking_category_id",
            name="uq_xero_tracking_category_connection_tc",
        ),
        Index("ix_xero_tracking_categories_tenant", "tenant_id"),
        Index("ix_xero_tracking_categories_connection", "connection_id"),
    )

    def __repr__(self) -> str:
        return f"<XeroTrackingCategory(id={self.id}, name={self.name})>"


class XeroTrackingOption(Base, TimestampMixin):
    """Option within a tracking category.

    Spec 025: Fixed Assets & Enhanced Analysis
    """

    __tablename__ = "xero_tracking_options"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_tracking_categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    xero_tracking_option_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Xero's tracking option ID",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="ACTIVE/ARCHIVED/DELETED",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    category: Mapped["XeroTrackingCategory"] = relationship(
        "XeroTrackingCategory",
        back_populates="options",
    )

    __table_args__ = (
        UniqueConstraint(
            "category_id",
            "xero_tracking_option_id",
            name="uq_xero_tracking_option_category_to",
        ),
        Index("ix_xero_tracking_options_tenant", "tenant_id"),
        Index("ix_xero_tracking_options_category", "category_id"),
    )

    def __repr__(self) -> str:
        return f"<XeroTrackingOption(id={self.id}, name={self.name})>"


class XeroQuote(Base, TimestampMixin):
    """Quote from Xero.

    Spec 025: Fixed Assets & Enhanced Analysis
    """

    __tablename__ = "xero_quotes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    xero_quote_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Xero's quote ID",
    )
    contact_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Xero contact ID",
    )
    contact_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Client name (denormalized)",
    )
    quote_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Quote number",
    )
    reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Quote date",
    )
    expiry_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Quote expiry date",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="DRAFT/SENT/ACCEPTED/DECLINED/INVOICED",
    )
    sub_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
    )
    total_tax: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
    )
    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="AUD",
    )
    line_items: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "xero_quote_id",
            name="uq_xero_quote_connection_quote",
        ),
        Index("ix_xero_quotes_tenant", "tenant_id"),
        Index("ix_xero_quotes_connection", "connection_id"),
        Index("ix_xero_quotes_status", "status"),
        Index("ix_xero_quotes_expiry", "expiry_date"),
    )

    def __repr__(self) -> str:
        return f"<XeroQuote(id={self.id}, number={self.quote_number}, status={self.status})>"

    @property
    def is_open(self) -> bool:
        """Check if quote is still open (DRAFT or SENT)."""
        return self.status in ("DRAFT", "SENT")

    @property
    def is_won(self) -> bool:
        """Check if quote was won (ACCEPTED or INVOICED)."""
        return self.status in ("ACCEPTED", "INVOICED")

    @property
    def is_expired(self) -> bool:
        """Check if quote has expired."""
        if self.expiry_date is None:
            return False
        return self.expiry_date < date.today() and self.is_open


# =============================================================================
# Progressive Sync Models (Spec 043)
# =============================================================================


class XeroSyncEntityProgressStatus(str, enum.Enum):
    """Status of an individual entity sync within a job."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

    def __str__(self) -> str:
        return self.value


class XeroSyncEntityProgress(Base, TimestampMixin):
    """Per-entity sync progress within a sync job.

    Tracks sync status for each individual entity type (contacts, invoices, etc.)
    within a parent sync job. Replaces the progress_details JSONB approach with
    a proper relational model for query-ability.
    """

    __tablename__ = "xero_sync_entity_progress"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_sync_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Entity type: contacts, invoices, bank_transactions, etc.",
    )
    status: Mapped[XeroSyncEntityProgressStatus] = mapped_column(
        Enum(
            XeroSyncEntityProgressStatus,
            name="xero_sync_entity_progress_status",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=XeroSyncEntityProgressStatus.PENDING,
        server_default="pending",
    )
    records_processed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    records_created: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    records_updated: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    records_failed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    modified_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="If-Modified-Since timestamp used for this entity",
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Elapsed time in milliseconds",
    )

    # Relationships
    job: Mapped["XeroSyncJob"] = relationship("XeroSyncJob", back_populates="entity_progress")

    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "entity_type",
            name="uq_xero_sync_entity_progress_job_entity",
        ),
        Index("ix_xero_sync_entity_progress_tenant", "tenant_id"),
        Index("ix_xero_sync_entity_progress_job", "job_id"),
    )

    def __repr__(self) -> str:
        return f"<XeroSyncEntityProgress(entity={self.entity_type}, status={self.status})>"


class PostSyncTaskStatus(str, enum.Enum):
    """Status of a post-sync preparation task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

    def __str__(self) -> str:
        return self.value


class PostSyncTask(Base, TimestampMixin):
    """Tracks execution of post-sync data preparation tasks.

    After each sync phase completes, downstream tasks are dispatched:
    - Phase 1: quality_score
    - Phase 2: bas_calculation, aggregation
    - Phase 3: insights, triggers
    """

    __tablename__ = "post_sync_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_sync_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Task type: quality_score, bas_calculation, aggregation, insights, triggers",
    )
    status: Mapped[PostSyncTaskStatus] = mapped_column(
        Enum(
            PostSyncTaskStatus,
            name="post_sync_task_status",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=PostSyncTaskStatus.PENDING,
        server_default="pending",
    )
    sync_phase: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Which sync phase triggered this task (1, 2, or 3)",
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='e.g., {"quality_score": 87, "issues_found": 3}',
    )

    # Relationships
    job: Mapped["XeroSyncJob"] = relationship("XeroSyncJob", back_populates="post_sync_tasks")
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        Index("ix_post_sync_tasks_job", "job_id"),
        Index("ix_post_sync_tasks_connection_type", "connection_id", "task_type"),
        Index("ix_post_sync_tasks_tenant", "tenant_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<PostSyncTask(type={self.task_type}, phase={self.sync_phase}, status={self.status})>"
        )


class XeroWebhookEventStatus(str, enum.Enum):
    """Status of a webhook event."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

    def __str__(self) -> str:
        return self.value


class XeroWebhookEvent(Base):
    """Records incoming Xero webhook events for processing and deduplication.

    Xero webhooks deliver event notifications when data changes.
    Events are stored, deduplicated by webhook_key, and batched for processing.
    """

    __tablename__ = "xero_webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    webhook_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        comment="Xero event key for deduplication",
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="e.g., CREATE, UPDATE",
    )
    event_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="e.g., INVOICE, CONTACT",
    )
    resource_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Xero entity ID affected",
    )
    status: Mapped[XeroWebhookEventStatus] = mapped_column(
        Enum(
            XeroWebhookEventStatus,
            name="xero_webhook_event_status",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=XeroWebhookEventStatus.PENDING,
        server_default="pending",
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Groups events batched together for processing",
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Original webhook payload",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationships
    connection: Mapped["XeroConnection"] = relationship("XeroConnection", lazy="joined")

    __table_args__ = (
        Index(
            "ix_xero_webhook_events_connection_status",
            "connection_id",
            "status",
        ),
        Index("ix_xero_webhook_events_tenant", "tenant_id"),
        Index("ix_xero_webhook_events_batch", "batch_id"),
    )
