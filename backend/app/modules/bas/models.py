"""SQLAlchemy models for BAS preparation workflow.

This module defines:
- Enums: BASSessionStatus, BASAuditEventType
- Models: BASPeriod, BASSession, BASCalculation, BASAdjustment, BASAuditLog

RLS (Row-Level Security):
- RLS is enforced on all tenant-scoped tables
- RLS uses PostgreSQL session variable `app.current_tenant_id`
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.auth.models import PracticeUser, User
    from app.modules.integrations.xero.models import XeroConnection


# =============================================================================
# Enums
# =============================================================================


class BASSessionStatus(str, enum.Enum):
    """Status of a BAS preparation session.

    Workflow: DRAFT → IN_PROGRESS → READY_FOR_REVIEW → APPROVED → LODGED
    """

    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    LODGED = "lodged"

    def __str__(self) -> str:
        return self.value


class BASAuditEventType(str, enum.Enum):
    """Types of audit events for BAS sessions."""

    SESSION_CREATED = "session_created"
    SESSION_AUTO_CREATED = "session_auto_created"
    STATUS_CHANGED = "status_changed"
    CALCULATION_TRIGGERED = "calculation_triggered"
    ADJUSTMENT_ADDED = "adjustment_added"
    ADJUSTMENT_REMOVED = "adjustment_removed"
    SESSION_REVIEWED = "session_reviewed"
    SESSION_APPROVED = "session_approved"
    SESSION_LODGED = "session_lodged"

    # Lodgement events (Spec 011)
    LODGEMENT_RECORDED = "lodgement_recorded"
    LODGEMENT_UPDATED = "lodgement_updated"

    # Export events (Spec 011)
    EXPORT_PDF_LODGEMENT = "export_pdf_lodgement"
    EXPORT_EXCEL_LODGEMENT = "export_excel_lodgement"
    EXPORT_CSV = "export_csv"

    # Notification events (Spec 011)
    DEADLINE_NOTIFICATION_SENT = "deadline_notification_sent"

    # Tax code resolution events (Spec 046)
    TAX_CODE_SUGGESTIONS_GENERATED = "tax_code_suggestions_generated"
    TAX_CODE_SUGGESTION_APPROVED = "tax_code_suggestion_approved"
    TAX_CODE_SUGGESTION_REJECTED = "tax_code_suggestion_rejected"
    TAX_CODE_SUGGESTION_OVERRIDDEN = "tax_code_suggestion_overridden"
    TAX_CODE_TRANSACTION_DISMISSED = "tax_code_transaction_dismissed"
    TAX_CODE_BULK_APPROVED = "tax_code_bulk_approved"
    TAX_CODE_CONFLICT_DETECTED = "tax_code_conflict_detected"
    BAS_RECALCULATED_AFTER_RESOLUTION = "bas_recalculated_after_resolution"

    # Client classification events (Spec 047)
    CLASSIFICATION_REQUEST_CREATED = "classification_request_created"
    CLASSIFICATION_REQUEST_SENT = "classification_request_sent"
    CLASSIFICATION_REQUEST_SUBMITTED = "classification_request_submitted"
    CLASSIFICATION_REVIEWED = "classification_reviewed"
    CLASSIFICATION_AI_MAPPED = "classification_ai_mapped"

    def __str__(self) -> str:
        return self.value


class TaxCodeSuggestionSourceType(str, enum.Enum):
    """Source type for a tax code suggestion."""

    INVOICE = "invoice"
    BANK_TRANSACTION = "bank_transaction"
    CREDIT_NOTE = "credit_note"

    def __str__(self) -> str:
        return self.value


class TaxCodeOverrideWritebackStatus(str, enum.Enum):
    """Write-back sync status for a TaxCodeOverride (Spec 049)."""

    PENDING_SYNC = "pending_sync"
    SYNCED = "synced"
    SKIPPED = "skipped"
    FAILED = "failed"

    def __str__(self) -> str:
        return self.value


class TaxCodeSuggestionStatus(str, enum.Enum):
    """Resolution status of a tax code suggestion."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    OVERRIDDEN = "overridden"
    DISMISSED = "dismissed"

    def __str__(self) -> str:
        return self.value


class ConfidenceTier(str, enum.Enum):
    """Confidence tier for tax code suggestions."""

    ACCOUNT_DEFAULT = "account_default"
    CLIENT_HISTORY = "client_history"
    TENANT_HISTORY = "tenant_history"
    LLM_CLASSIFICATION = "llm_classification"
    MANUAL = "manual"

    def __str__(self) -> str:
        return self.value


class LodgementMethod(str, enum.Enum):
    """Method used to lodge BAS with the ATO.

    Spec 011: Interim Lodgement
    """

    ATO_PORTAL = "ATO_PORTAL"
    XERO = "XERO"
    OTHER = "OTHER"

    def __str__(self) -> str:
        return self.value


# =============================================================================
# Models
# =============================================================================


class BASPeriod(Base, TimestampMixin):
    """A BAS reporting period for a client.

    Represents a quarter (or month for monthly reporters) for which a BAS
    can be prepared. Periods are created on-demand when a user starts
    BAS preparation.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant (RLS enforced).
        connection_id: Foreign key to the Xero connection.
        period_type: 'quarterly' or 'monthly'.
        quarter: Quarter number (1-4) for quarterly periods.
        month: Month number (1-12) for monthly periods.
        fy_year: Financial year (e.g., 2025 for FY2024-25).
        start_date: Start date of the period.
        end_date: End date of the period.
        due_date: ATO lodgement deadline.
    """

    __tablename__ = "bas_periods"

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

    # Period identification
    period_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="quarterly",
        comment="'quarterly' or 'monthly'",
    )
    quarter: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Quarter 1-4 for quarterly periods",
    )
    month: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Month 1-12 for monthly periods",
    )
    fy_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Financial year (e.g., 2025 for FY2024-25)",
    )

    # Period dates
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    due_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="ATO lodgement deadline",
    )

    # Relationships
    connection: Mapped["XeroConnection"] = relationship(
        "XeroConnection",
        lazy="joined",
    )
    session: Mapped["BASSession | None"] = relationship(
        "BASSession",
        back_populates="period",
        uselist=False,
        lazy="joined",
    )

    __table_args__ = (
        # Only one period per connection per quarter
        UniqueConstraint(
            "connection_id",
            "fy_year",
            "quarter",
            name="uq_bas_period_connection_quarter",
        ),
        # Quarter must be 1-4 or NULL
        CheckConstraint(
            "quarter IS NULL OR (quarter >= 1 AND quarter <= 4)",
            name="ck_bas_period_quarter_range",
        ),
        # Month must be 1-12 or NULL
        CheckConstraint(
            "month IS NULL OR (month >= 1 AND month <= 12)",
            name="ck_bas_period_month_range",
        ),
        # Must have either quarter or month, not both
        CheckConstraint(
            "(quarter IS NOT NULL AND month IS NULL) OR (quarter IS NULL AND month IS NOT NULL)",
            name="ck_bas_period_quarter_xor_month",
        ),
    )

    def __repr__(self) -> str:
        if self.quarter:
            return f"<BASPeriod Q{self.quarter} FY{self.fy_year} for {self.connection_id}>"
        return f"<BASPeriod M{self.month} FY{self.fy_year} for {self.connection_id}>"

    @property
    def display_name(self) -> str:
        """Human-readable period name."""
        if self.quarter:
            return f"Q{self.quarter} FY{self.fy_year}"
        return f"Month {self.month} FY{self.fy_year}"


class BASSession(Base, TimestampMixin):
    """A BAS preparation session for a specific period.

    Tracks the workflow state and calculation results for preparing
    a client's BAS. Only one session per period is allowed.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant (RLS enforced).
        period_id: Foreign key to the BAS period.
        status: Current workflow status.
        created_by: User who created the session.
        last_modified_by: User who last modified the session.
        approved_by: User who approved the session.
        approved_at: Timestamp of approval.
        gst_calculated_at: When GST was last calculated.
        payg_calculated_at: When PAYG was last calculated.
        internal_notes: Internal notes for the session.
    """

    __tablename__ = "bas_sessions"

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
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bas_periods.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Status tracking (stored as VARCHAR for flexibility)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        server_default="draft",
        index=True,
    )

    # User tracking
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    last_modified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Calculation timestamps
    gst_calculated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    payg_calculated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Notes
    internal_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Auto-creation tracking
    auto_created: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True if session was auto-created by system",
    )

    # Review tracking (for auto-created sessions)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who reviewed auto-created session",
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When session was reviewed",
    )

    # Lodgement tracking (Spec 011)
    lodged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when BAS was marked as lodged",
    )
    lodged_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who recorded the lodgement",
    )
    lodgement_method: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Lodgement method: ATO_PORTAL, XERO, OTHER",
    )
    lodgement_method_description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Description for OTHER lodgement method",
    )
    ato_reference_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="ATO lodgement reference number",
    )
    lodgement_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes about the lodgement",
    )

    # Optimistic locking (Spec 011)
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        comment="Version for optimistic locking",
    )

    # GST basis snapshot (Spec 062) — immutable after lodgement
    gst_basis_used: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="Snapshot of GST basis used at calculation time ('cash' or 'accrual')",
    )

    # Relationships
    period: Mapped["BASPeriod"] = relationship(
        "BASPeriod",
        back_populates="session",
        lazy="joined",
    )
    reviewed_by_user: Mapped["PracticeUser | None"] = relationship(
        "PracticeUser",
        foreign_keys=[reviewed_by],
        lazy="joined",
    )
    lodged_by_user: Mapped["PracticeUser | None"] = relationship(
        "PracticeUser",
        foreign_keys=[lodged_by],
        lazy="joined",
    )
    calculation: Mapped["BASCalculation | None"] = relationship(
        "BASCalculation",
        back_populates="session",
        uselist=False,
        lazy="joined",
    )
    adjustments: Mapped[list["BASAdjustment"]] = relationship(
        "BASAdjustment",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    created_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by],
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<BASSession {self.id} status={self.status}>"

    @property
    def status_enum(self) -> BASSessionStatus:
        """Get status as enum."""
        return BASSessionStatus(self.status)

    @property
    def is_editable(self) -> bool:
        """Check if session can be edited."""
        return self.status in (
            BASSessionStatus.DRAFT.value,
            BASSessionStatus.IN_PROGRESS.value,
        )

    @property
    def can_approve(self) -> bool:
        """Check if session can be approved."""
        return self.status == BASSessionStatus.READY_FOR_REVIEW.value

    @property
    def can_record_lodgement(self) -> bool:
        """Check if lodgement can be recorded for this session."""
        return self.status == BASSessionStatus.APPROVED.value

    @property
    def is_lodged(self) -> bool:
        """Check if session has been lodged."""
        return self.lodged_at is not None or self.status == BASSessionStatus.LODGED.value

    # Optimistic locking configuration
    __mapper_args__ = {
        "version_id_col": version,
    }


class BASCalculation(Base, TimestampMixin):
    """Cached BAS calculation results for a session.

    Stores the calculated GST and PAYG fields. Only one calculation
    per session (upserted on recalculation).

    GST Fields (G-fields):
        g1_total_sales: Total sales including GST
        g2_export_sales: Export sales (GST-free)
        g3_gst_free_sales: Other GST-free sales
        g10_capital_purchases: Capital purchases
        g11_non_capital_purchases: Non-capital purchases
        field_1a_gst_on_sales: GST collected on sales
        field_1b_gst_on_purchases: GST paid on purchases

    PAYG Fields:
        w1_total_wages: Total salary/wages (gross)
        w2_amount_withheld: PAYG tax withheld

    Summary Fields:
        gst_payable: Net GST (1A - 1B)
        total_payable: Total amount payable (GST + PAYG)
    """

    __tablename__ = "bas_calculations"

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
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bas_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # GST G-fields
    g1_total_sales: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        comment="Total sales including GST",
    )
    g2_export_sales: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        comment="Export sales (GST-free)",
    )
    g3_gst_free_sales: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        comment="Other GST-free sales",
    )
    g10_capital_purchases: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        comment="Capital purchases",
    )
    g11_non_capital_purchases: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        comment="Non-capital purchases",
    )

    # GST calculated fields
    field_1a_gst_on_sales: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        comment="GST collected on sales",
    )
    field_1b_gst_on_purchases: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        comment="GST paid on purchases",
    )

    # PAYG fields
    w1_total_wages: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        comment="Total salary/wages (BAS W1)",
    )
    w2_amount_withheld: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        comment="PAYG tax withheld (BAS W2)",
    )

    # PAYG Instalment fields (Spec 062) — manual entry for quarterly BAS filers
    t1_instalment_income: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Instalment income (T1) — manual entry",
    )
    t2_instalment_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 5),
        nullable=True,
        comment="Instalment rate (T2) — manual entry (e.g. 0.04 = 4%)",
    )

    # Summary fields
    gst_payable: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        comment="Net GST (1A - 1B), negative = refund",
    )
    total_payable: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
        comment="Total amount payable (GST + PAYG)",
    )

    # Calculation metadata
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    calculation_duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Calculation duration in milliseconds",
    )
    transaction_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Number of bank transactions processed",
    )
    invoice_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Number of invoices processed",
    )
    pay_run_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Number of pay runs processed",
    )

    # Relationships
    session: Mapped["BASSession"] = relationship(
        "BASSession",
        back_populates="calculation",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<BASCalculation session={self.session_id} GST={self.gst_payable}>"

    @property
    def net_gst(self) -> Decimal:
        """Net GST amount (alias for gst_payable)."""
        return self.gst_payable

    @property
    def is_refund(self) -> bool:
        """True if GST is a refund (1B > 1A)."""
        return self.gst_payable < 0


class BASAdjustment(Base, TimestampMixin):
    """A manual adjustment to a BAS calculation field.

    Allows accountants to record adjustments to calculated figures
    with a mandatory reason for audit purposes.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant (RLS enforced).
        session_id: Foreign key to the BAS session.
        field_name: Name of the field being adjusted.
        adjustment_amount: Amount to add (positive) or subtract (negative).
        reason: Mandatory reason for the adjustment.
        reference: Optional reference (invoice number, etc.).
        created_by: User who created the adjustment.
    """

    __tablename__ = "bas_adjustments"

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
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bas_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Adjustment details
    field_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Field being adjusted (e.g., 'g1_total_sales', 'field_1a')",
    )
    adjustment_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Amount to add (positive) or subtract (negative)",
    )
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Mandatory reason for the adjustment",
    )
    reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Optional reference (invoice number, etc.)",
    )

    # User tracking
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )

    # Relationships
    session: Mapped["BASSession"] = relationship(
        "BASSession",
        back_populates="adjustments",
        lazy="joined",
    )
    created_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by],
        lazy="joined",
    )

    # Valid field names for adjustments
    VALID_FIELDS: ClassVar[set[str]] = {
        "g1_total_sales",
        "g2_export_sales",
        "g3_gst_free_sales",
        "g10_capital_purchases",
        "g11_non_capital_purchases",
        "field_1a_gst_on_sales",
        "field_1b_gst_on_purchases",
        "w1_total_wages",
        "w2_amount_withheld",
    }

    __table_args__ = (
        CheckConstraint(
            f"field_name IN ({', '.join(repr(f) for f in VALID_FIELDS)})",
            name="ck_bas_adjustment_field_name",
        ),
    )

    def __repr__(self) -> str:
        return f"<BASAdjustment {self.field_name}={self.adjustment_amount}>"


class BASAuditLog(Base):
    """Audit log for BAS session events.

    Tracks all significant events on BAS sessions for compliance purposes.
    This includes session creation, status changes, calculations, and approvals.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant (RLS enforced).
        session_id: Foreign key to the BAS session.
        event_type: Type of event (from BASAuditEventType).
        event_description: Human-readable description of the event.
        from_status: Previous status (for status changes).
        to_status: New status (for status changes).
        performed_by: User who performed the action (NULL for system).
        performed_by_name: Cached name of the user.
        is_system_action: True if action was performed by the system.
        event_metadata: Additional event-specific data.
        ip_address: IP address of the user (if available).
        created_at: Timestamp of the event.
    """

    __tablename__ = "bas_audit_log"

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
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bas_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Event details
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of audit event",
    )
    event_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Human-readable event description",
    )

    # Status tracking
    from_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Previous status (for status changes)",
    )
    to_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="New status (for status changes)",
    )

    # User tracking
    performed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who performed the action (NULL for system)",
    )
    performed_by_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Cached name of the user",
    )
    is_system_action: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True if action was performed by system",
    )

    # Additional context
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional event-specific data",
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of the user",
    )

    # Timestamp (not using TimestampMixin - audit logs are immutable)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Relationships
    session: Mapped["BASSession"] = relationship(
        "BASSession",
        lazy="joined",
    )
    performed_by_user: Mapped["PracticeUser | None"] = relationship(
        "PracticeUser",
        foreign_keys=[performed_by],
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<BASAuditLog {self.event_type} session={self.session_id}>"


# =============================================================================
# Tax Code Resolution Models (Spec 046)
# =============================================================================


class TaxCodeSuggestion(Base, TimestampMixin):
    """AI-generated tax code suggestion for an excluded transaction line item.

    Spec 046: AI Tax Code Resolution for BAS Preparation.
    Stores suggestions, accountant resolutions, and denormalized transaction
    context for display. Scoped to a BAS session.
    """

    __tablename__ = "tax_code_suggestions"

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
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bas_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Source transaction reference
    source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    line_item_index: Mapped[int] = mapped_column(Integer, nullable=False)
    line_item_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Xero LineItemID for reference",
    )

    # Tax code data
    original_tax_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Tax type from Xero (e.g. NONE, BASEXCLUDED)",
    )
    suggested_tax_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="AI-suggested tax type",
    )
    applied_tax_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Actually applied tax type (may differ from suggestion)",
    )

    # Confidence
    confidence_score: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2),
        nullable=True,
        comment="0.00-1.00 confidence",
    )
    confidence_tier: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    suggestion_basis: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable explanation of suggestion",
    )

    # Resolution
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    dismissal_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason if dismissed (soft-deprecated — use note_text for new records)",
    )

    # Xero reconciliation grouping (Spec 057)
    is_reconciled: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        default=None,
        comment="Mirrors XeroBankTransaction.is_reconciled. NULL for invoices/credit notes.",
    )
    auto_park_reason: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        default=None,
        comment="'unreconciled_in_xero' when system auto-parked; NULL for manual park or non-auto-parked.",
    )

    # Per-suggestion note (Spec 056)
    note_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Free-text note (max 2000 chars, enforced in app layer)",
    )
    note_updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    note_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # Denormalized transaction context (snapshot at detection time)
    account_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    line_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    transaction_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Relationships
    session: Mapped["BASSession"] = relationship("BASSession", lazy="joined")
    resolved_by_user: Mapped["PracticeUser | None"] = relationship(
        "PracticeUser",
        foreign_keys=[resolved_by],
        lazy="joined",
    )
    note_updated_by_user: Mapped["PracticeUser | None"] = relationship(
        "PracticeUser",
        foreign_keys=[note_updated_by],
        lazy="joined",
    )

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "source_type",
            "source_id",
            "line_item_index",
            name="uq_tax_code_suggestion_session_source_line",
        ),
        Index("ix_tax_code_suggestions_source", "source_type", "source_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<TaxCodeSuggestion {self.source_type}:{self.source_id}"
            f" line={self.line_item_index} status={self.status}>"
        )


class TaxCodeOverride(Base, TimestampMixin):
    """Locally applied tax code that differs from Xero.

    Spec 046: Tracks overrides to enable conflict detection on re-sync.
    The Xero JSONB is never mutated — overrides are applied during BAS
    calculation by overlaying on top of Xero data.
    """

    __tablename__ = "tax_code_overrides"

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

    # Source reference
    source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    line_item_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Override data
    original_tax_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Tax type from Xero at time of override",
    )
    override_tax_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Tax type applied by accountant",
    )

    # Who and when
    applied_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=False,
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Link to suggestion
    suggestion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_code_suggestions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Lifecycle
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    conflict_detected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    xero_new_tax_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Xero's new value when conflict detected",
    )
    conflict_resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Write-back status (Spec 049)
    writeback_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TaxCodeOverrideWritebackStatus.PENDING_SYNC.value,
        server_default=TaxCodeOverrideWritebackStatus.PENDING_SYNC.value,
        comment="Xero write-back sync state: pending_sync | synced | skipped | failed",
    )

    # Split management (Spec 049 line-items extension)
    line_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Override LineAmount. Null = keep existing Xero amount. Required when is_new_split=True.",
    )
    line_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Override Description. Null = keep existing.",
    )
    line_account_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Override AccountCode. Null = keep existing.",
    )
    is_new_split: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True = insert new line item at line_item_index; False = patch existing.",
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True = remove this original line item from the Xero payload. Only meaningful when is_new_split=False.",
    )

    # Relationships
    suggestion: Mapped["TaxCodeSuggestion | None"] = relationship(
        "TaxCodeSuggestion",
        lazy="joined",
    )
    applied_by_user: Mapped["PracticeUser | None"] = relationship(
        "PracticeUser",
        foreign_keys=[applied_by],
        lazy="joined",
    )

    __table_args__ = (
        Index(
            "uq_tax_code_override_active",
            "connection_id",
            "source_type",
            "source_id",
            "line_item_index",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<TaxCodeOverride {self.source_type}:{self.source_id}"
            f" line={self.line_item_index} active={self.is_active}>"
        )
