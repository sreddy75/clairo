# Data Model: Credit Notes, Payments & Journals

**Feature**: 024-credit-notes-payments-journals
**Date**: 2026-01-01

---

## Entity Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ENTITY RELATIONSHIPS                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  XeroConnection (existing)                                              │
│       │                                                                 │
│       ├──► XeroInvoice (existing)                                       │
│       │        │                                                        │
│       │        ├───────► XeroCreditNote                                 │
│       │        │              │                                         │
│       │        │              └──► XeroCreditNoteAllocation             │
│       │        │                                                        │
│       │        └───────► XeroPayment                                    │
│       │                                                                 │
│       ├──► XeroOverpayment ───► XeroOverpaymentAllocation              │
│       │                                                                 │
│       ├──► XeroPrepayment ───► XeroPrepaymentAllocation                │
│       │                                                                 │
│       ├──► XeroJournal ───► XeroJournalLine                            │
│       │                                                                 │
│       └──► XeroManualJournal ───► XeroManualJournalLine                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Enums

### XeroCreditNoteType

```python
class XeroCreditNoteType(str, enum.Enum):
    """Credit note types in Xero."""

    ACCPAYCREDIT = "ACCPAYCREDIT"    # Accounts Payable (from supplier)
    ACCRECCREDIT = "ACCRECCREDIT"    # Accounts Receivable (to customer)
```

### XeroCreditNoteStatus

```python
class XeroCreditNoteStatus(str, enum.Enum):
    """Credit note status in Xero."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    AUTHORISED = "AUTHORISED"
    PAID = "PAID"          # Fully allocated
    VOIDED = "VOIDED"
```

### XeroPaymentType

```python
class XeroPaymentType(str, enum.Enum):
    """Payment types in Xero."""

    ACCRECPAYMENT = "ACCRECPAYMENT"       # Customer pays us
    ACCPAYPAYMENT = "ACCPAYPAYMENT"       # We pay supplier
    ARCREDITPAYMENT = "ARCREDITPAYMENT"   # AR Credit Note refund
    APCREDITPAYMENT = "APCREDITPAYMENT"   # AP Credit Note refund
    ABORECPAYMENT = "ABORECPAYMENT"       # AR Overpayment
    ABOPAYMENT = "ABOPAYMENT"             # AP Overpayment
    ARPREPAYMENTPAYMENT = "ARPREPAYMENTPAYMENT"  # AR Prepayment
    APPREPAYMENTPAYMENT = "APPREPAYMENTPAYMENT"  # AP Prepayment
```

### XeroPaymentStatus

```python
class XeroPaymentStatus(str, enum.Enum):
    """Payment status in Xero."""

    AUTHORISED = "AUTHORISED"
    DELETED = "DELETED"
```

### XeroJournalSourceType

```python
class XeroJournalSourceType(str, enum.Enum):
    """Journal source types in Xero."""

    ACCREC = "ACCREC"           # AR Invoice
    ACCPAY = "ACCPAY"           # AP Bill
    CASHREC = "CASHREC"         # Cash Received
    CASHPAID = "CASHPAID"       # Cash Paid
    ACCPAYCREDIT = "ACCPAYCREDIT"  # AP Credit Note
    ACCRECCREDIT = "ACCRECCREDIT"  # AR Credit Note
    TRANSFER = "TRANSFER"       # Bank Transfer
    MANJOURNAL = "MANJOURNAL"   # Manual Journal
```

### XeroManualJournalStatus

```python
class XeroManualJournalStatus(str, enum.Enum):
    """Manual journal status in Xero."""

    DRAFT = "DRAFT"
    POSTED = "POSTED"
    DELETED = "DELETED"
    VOIDED = "VOIDED"
```

---

## Entities

### XeroCreditNote

```python
class XeroCreditNote(Base, TimestampMixin):
    """Credit note synced from Xero.

    Credit notes reduce amounts owed:
    - ACCRECCREDIT: Reduces what customer owes us (sales credit)
    - ACCPAYCREDIT: Reduces what we owe supplier (purchase credit)

    GST on credit notes must be included in BAS calculations.
    """

    __tablename__ = "xero_credit_notes"

    # Primary Key
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Multi-tenancy
    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Xero Connection
    connection_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Xero identifiers
    xero_credit_note_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    credit_note_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Type and status
    credit_note_type: Mapped[XeroCreditNoteType] = mapped_column(
        SQLAlchemyEnum(XeroCreditNoteType),
        nullable=False,
    )
    status: Mapped[XeroCreditNoteStatus] = mapped_column(
        SQLAlchemyEnum(XeroCreditNoteStatus),
        nullable=False,
    )

    # Contact
    contact_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_clients.id", ondelete="SET NULL"),
        nullable=True,
    )
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Dates
    date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Amounts
    sub_total: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    total_tax: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    remaining_credit: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    # Currency
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="AUD")
    currency_rate: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False, default=1.0)

    # Line items (JSONB for flexibility)
    line_items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Xero metadata
    xero_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    allocations: Mapped[list["XeroCreditNoteAllocation"]] = relationship(
        "XeroCreditNoteAllocation",
        back_populates="credit_note",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("ix_xero_credit_notes_connection_date", "connection_id", "date"),
        Index("ix_xero_credit_notes_tenant_type", "tenant_id", "credit_note_type"),
    )
```

### XeroCreditNoteAllocation

```python
class XeroCreditNoteAllocation(Base, TimestampMixin):
    """Allocation of credit note to invoice/bill."""

    __tablename__ = "xero_credit_note_allocations"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    credit_note_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_credit_notes.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Xero allocation ID
    xero_allocation_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Target invoice
    invoice_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_invoices.id", ondelete="SET NULL"),
        nullable=True,
    )
    xero_invoice_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Allocation details
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    allocation_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Relationships
    credit_note: Mapped["XeroCreditNote"] = relationship(
        "XeroCreditNote",
        back_populates="allocations",
    )
```

---

### XeroPayment

```python
class XeroPayment(Base, TimestampMixin):
    """Payment synced from Xero.

    Tracks actual cash movement, linked to invoices/bills/credit notes.
    Used for cash flow analysis and reconciliation.
    """

    __tablename__ = "xero_payments"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Multi-tenancy
    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Xero Connection
    connection_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Xero identifiers
    xero_payment_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Type and status
    payment_type: Mapped[XeroPaymentType] = mapped_column(
        SQLAlchemyEnum(XeroPaymentType),
        nullable=False,
    )
    status: Mapped[XeroPaymentStatus] = mapped_column(
        SQLAlchemyEnum(XeroPaymentStatus),
        nullable=False,
    )

    # Payment details
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_reconciled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Currency
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="AUD")
    currency_rate: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False, default=1.0)

    # Bank account
    account_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    account_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Linked transaction (one of these will be set)
    invoice_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_invoices.id", ondelete="SET NULL"),
        nullable=True,
    )
    credit_note_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_credit_notes.id", ondelete="SET NULL"),
        nullable=True,
    )
    overpayment_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    prepayment_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Xero references (store IDs for linking)
    xero_invoice_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    xero_credit_note_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Xero metadata
    xero_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Indexes
    __table_args__ = (
        Index("ix_xero_payments_connection_date", "connection_id", "payment_date"),
        Index("ix_xero_payments_invoice", "invoice_id"),
    )
```

---

### XeroOverpayment

```python
class XeroOverpayment(Base, TimestampMixin):
    """Overpayment synced from Xero.

    Created when customer pays more than invoice amount.
    Can be allocated to future invoices.
    """

    __tablename__ = "xero_overpayments"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    tenant_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("xero_connections.id"), nullable=False)

    xero_overpayment_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Type: RECEIVE-OVERPAYMENT or SPEND-OVERPAYMENT
    overpayment_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)

    # Contact
    contact_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Amounts
    date: Mapped[date] = mapped_column(Date, nullable=False)
    sub_total: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    total_tax: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    remaining_credit: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="AUD")

    # Line items and allocations
    line_items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    allocations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    xero_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

---

### XeroPrepayment

```python
class XeroPrepayment(Base, TimestampMixin):
    """Prepayment synced from Xero.

    Payment received before invoice is created.
    Allocated when invoice is generated.
    """

    __tablename__ = "xero_prepayments"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    tenant_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("xero_connections.id"), nullable=False)

    xero_prepayment_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Type: RECEIVE-PREPAYMENT or SPEND-PREPAYMENT
    prepayment_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)

    # Contact
    contact_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Amounts
    date: Mapped[date] = mapped_column(Date, nullable=False)
    sub_total: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    total_tax: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    remaining_credit: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="AUD")

    # Line items and allocations
    line_items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    allocations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    xero_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

---

### XeroJournal

```python
class XeroJournal(Base, TimestampMixin):
    """System-generated journal entry from Xero.

    Every transaction in Xero creates a journal entry.
    Provides complete audit trail of all debits and credits.
    """

    __tablename__ = "xero_journals"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    tenant_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("xero_connections.id"), nullable=False)

    xero_journal_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    journal_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Journal details
    journal_date: Mapped[date] = mapped_column(Date, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Source transaction
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[XeroJournalSourceType | None] = mapped_column(
        SQLAlchemyEnum(XeroJournalSourceType),
        nullable=True,
    )

    # Xero metadata
    created_date_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    lines: Mapped[list["XeroJournalLine"]] = relationship(
        "XeroJournalLine",
        back_populates="journal",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_xero_journals_connection_date", "connection_id", "journal_date"),
        Index("ix_xero_journals_source", "source_id", "source_type"),
    )
```

### XeroJournalLine

```python
class XeroJournalLine(Base):
    """Individual line in a journal entry."""

    __tablename__ = "xero_journal_lines"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    journal_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_journals.id", ondelete="CASCADE"),
        nullable=False,
    )

    xero_journal_line_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Account
    account_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    account_code: Mapped[str] = mapped_column(String(50), nullable=False)
    account_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Amounts
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)

    # Tax
    tax_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tax_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    journal: Mapped["XeroJournal"] = relationship("XeroJournal", back_populates="lines")
```

---

### XeroManualJournal

```python
class XeroManualJournal(Base, TimestampMixin):
    """Manual journal entry from Xero.

    User-created journal for adjustments, accruals, corrections.
    """

    __tablename__ = "xero_manual_journals"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    tenant_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("xero_connections.id"), nullable=False)

    xero_manual_journal_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Status
    status: Mapped[XeroManualJournalStatus] = mapped_column(
        SQLAlchemyEnum(XeroManualJournalStatus),
        nullable=False,
    )

    # Journal details
    date: Mapped[date] = mapped_column(Date, nullable=False)
    narration: Mapped[str | None] = mapped_column(Text, nullable=True)
    show_on_cash_basis_reports: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Line amount type
    line_amount_types: Mapped[str] = mapped_column(String(50), nullable=False, default="NoTax")

    # Xero metadata
    xero_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    lines: Mapped[list["XeroManualJournalLine"]] = relationship(
        "XeroManualJournalLine",
        back_populates="manual_journal",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_xero_manual_journals_connection_date", "connection_id", "date"),
    )
```

### XeroManualJournalLine

```python
class XeroManualJournalLine(Base):
    """Individual line in a manual journal."""

    __tablename__ = "xero_manual_journal_lines"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    manual_journal_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_manual_journals.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Account
    account_code: Mapped[str] = mapped_column(String(50), nullable=False)

    # Amount (positive = debit, negative = credit)
    line_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Tax
    tax_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)

    # Relationships
    manual_journal: Mapped["XeroManualJournal"] = relationship(
        "XeroManualJournal",
        back_populates="lines",
    )
```

---

## Migration

### Alembic Migration

```python
"""Add Credit Notes, Payments, Journals tables.

Revision ID: 024_credit_notes_payments
Create Date: 2026-01-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "024_credit_notes_payments"
down_revision = "023_xero_reports"


def upgrade() -> None:
    # Create enums
    op.execute("CREATE TYPE xerocreditnotetype AS ENUM ('ACCPAYCREDIT', 'ACCRECCREDIT')")
    op.execute("CREATE TYPE xerocreditnotestatus AS ENUM ('DRAFT', 'SUBMITTED', 'AUTHORISED', 'PAID', 'VOIDED')")
    op.execute("CREATE TYPE xeropaymenttype AS ENUM ('ACCRECPAYMENT', 'ACCPAYPAYMENT', 'ARCREDITPAYMENT', 'APCREDITPAYMENT', 'ABORECPAYMENT', 'ABOPAYMENT', 'ARPREPAYMENTPAYMENT', 'APPREPAYMENTPAYMENT')")
    op.execute("CREATE TYPE xeropaymentstatus AS ENUM ('AUTHORISED', 'DELETED')")
    op.execute("CREATE TYPE xerojournalsourcetype AS ENUM ('ACCREC', 'ACCPAY', 'CASHREC', 'CASHPAID', 'ACCPAYCREDIT', 'ACCRECCREDIT', 'TRANSFER', 'MANJOURNAL')")
    op.execute("CREATE TYPE xeromanualjournalstatus AS ENUM ('DRAFT', 'POSTED', 'DELETED', 'VOIDED')")

    # Create xero_credit_notes table
    op.create_table(
        "xero_credit_notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", UUID(as_uuid=True), nullable=False),
        sa.Column("xero_credit_note_id", sa.String(255), nullable=False, unique=True),
        sa.Column("credit_note_number", sa.String(100), nullable=True),
        sa.Column("credit_note_type", sa.Enum("xerocreditnotetype", create_type=False), nullable=False),
        sa.Column("status", sa.Enum("xerocreditnotestatus", create_type=False), nullable=False),
        sa.Column("contact_id", UUID(as_uuid=True), nullable=True),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("sub_total", sa.Numeric(15, 2), nullable=False),
        sa.Column("total_tax", sa.Numeric(15, 2), nullable=False),
        sa.Column("total", sa.Numeric(15, 2), nullable=False),
        sa.Column("remaining_credit", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="AUD"),
        sa.Column("currency_rate", sa.Numeric(15, 6), nullable=False, server_default="1.0"),
        sa.Column("line_items", JSONB, nullable=False, server_default="[]"),
        sa.Column("xero_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["xero_connections.id"], ondelete="CASCADE"),
    )

    # Create remaining tables (credit_note_allocations, payments, overpayments, prepayments, journals, etc.)
    # ... (similar pattern for each table)


def downgrade() -> None:
    op.drop_table("xero_manual_journal_lines")
    op.drop_table("xero_manual_journals")
    op.drop_table("xero_journal_lines")
    op.drop_table("xero_journals")
    op.drop_table("xero_prepayments")
    op.drop_table("xero_overpayments")
    op.drop_table("xero_payments")
    op.drop_table("xero_credit_note_allocations")
    op.drop_table("xero_credit_notes")

    op.execute("DROP TYPE xeromanualjournalstatus")
    op.execute("DROP TYPE xerojournalsourcetype")
    op.execute("DROP TYPE xeropaymentstatus")
    op.execute("DROP TYPE xeropaymenttype")
    op.execute("DROP TYPE xerocreditnotestatus")
    op.execute("DROP TYPE xerocreditnotetype")
```

---

## Validation Rules

### XeroCreditNote

| Field | Rule |
|-------|------|
| `total_tax` | Must match sum of line item tax amounts |
| `total` | Must equal `sub_total + total_tax` |
| `remaining_credit` | Must be >= 0 and <= `total` |

### XeroPayment

| Field | Rule |
|-------|------|
| `amount` | Must be > 0 |
| Linked transaction | At least one of invoice_id, credit_note_id, overpayment_id, prepayment_id |

### XeroJournal

| Field | Rule |
|-------|------|
| Journal lines | Sum of debits must equal sum of credits |

---

## State Transitions

### XeroCreditNote Status

```
DRAFT ──────► SUBMITTED ──────► AUTHORISED ──────► PAID
                                     │
                                     └──────► VOIDED
```

### XeroPayment Status

```
AUTHORISED ──────► DELETED
```

### XeroManualJournal Status

```
DRAFT ──────► POSTED ──────► VOIDED
                │
                └──────► DELETED
```
