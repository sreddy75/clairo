# Data Model: Fixed Assets & Enhanced Analysis

**Feature**: 025-fixed-assets-enhanced-analysis
**Date**: 2026-01-01

---

## Entity Overview

| Entity | Description | Source |
|--------|-------------|--------|
| XeroAssetType | Asset category with default depreciation settings | Xero Assets API |
| XeroAsset | Fixed asset with depreciation details | Xero Assets API |
| XeroPurchaseOrder | Purchase order for future cash outflows | Xero Accounting API |
| XeroPurchaseOrderLine | Line items on purchase orders | Xero Accounting API |
| XeroRepeatingInvoice | Repeating invoice template | Xero Accounting API |
| XeroTrackingCategory | Tracking category (department/project) | Xero Accounting API |
| XeroTrackingOption | Options within tracking categories | Xero Accounting API |
| XeroQuote | Quote for potential revenue | Xero Accounting API |

---

## Enums

### AssetStatus

```python
class AssetStatus(str, enum.Enum):
    """Fixed asset status in Xero."""
    DRAFT = "Draft"
    REGISTERED = "Registered"
    DISPOSED = "Disposed"
```

### DepreciationMethod

```python
class DepreciationMethod(str, enum.Enum):
    """Depreciation calculation method."""
    NO_DEPRECIATION = "NoDepreciation"
    STRAIGHT_LINE = "StraightLine"
    DIMINISHING_VALUE_100 = "DiminishingValue100"
    DIMINISHING_VALUE_150 = "DiminishingValue150"
    DIMINISHING_VALUE_200 = "DiminishingValue200"
    FULL_DEPRECIATION = "FullDepreciation"
```

### AveragingMethod

```python
class AveragingMethod(str, enum.Enum):
    """Depreciation averaging method."""
    FULL_MONTH = "FullMonth"
    ACTUAL_DAYS = "ActualDays"
```

### DepreciationCalculationMethod

```python
class DepreciationCalculationMethod(str, enum.Enum):
    """How depreciation is calculated."""
    RATE = "Rate"
    LIFE = "Life"
    NONE = "None"
```

### PurchaseOrderStatus

```python
class PurchaseOrderStatus(str, enum.Enum):
    """Purchase order status."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    AUTHORISED = "AUTHORISED"
    BILLED = "BILLED"
    DELETED = "DELETED"
```

### RepeatingInvoiceStatus

```python
class RepeatingInvoiceStatus(str, enum.Enum):
    """Repeating invoice template status."""
    DRAFT = "DRAFT"
    AUTHORISED = "AUTHORISED"
```

### ScheduleUnit

```python
class ScheduleUnit(str, enum.Enum):
    """Repeating invoice schedule unit."""
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"
```

### QuoteStatus

```python
class QuoteStatus(str, enum.Enum):
    """Quote status."""
    DRAFT = "DRAFT"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    INVOICED = "INVOICED"
```

### TrackingCategoryStatus

```python
class TrackingCategoryStatus(str, enum.Enum):
    """Tracking category status."""
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"
```

---

## Entity Definitions

### XeroAssetType

Asset category with default depreciation settings.

```python
class XeroAssetType(TenantBase):
    """Asset type defining default depreciation behavior."""
    __tablename__ = "xero_asset_types"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[UUID] = mapped_column(ForeignKey("xero_connections.id"))
    xero_asset_type_id: Mapped[UUID] = mapped_column(unique=True)

    # Type details
    asset_type_name: Mapped[str] = mapped_column(String(255))

    # Account linkages
    fixed_asset_account_id: Mapped[UUID | None]
    depreciation_expense_account_id: Mapped[UUID | None]
    accumulated_depreciation_account_id: Mapped[UUID | None]

    # Default depreciation settings
    depreciation_method: Mapped[DepreciationMethod]
    averaging_method: Mapped[AveragingMethod]
    depreciation_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    effective_life_years: Mapped[int | None]
    calculation_method: Mapped[DepreciationCalculationMethod]

    # Metadata
    locks: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(onupdate=func.now())

    # Relationships
    connection: Mapped["XeroConnection"] = relationship(back_populates="asset_types")
    assets: Mapped[list["XeroAsset"]] = relationship(back_populates="asset_type")
```

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | UUID | No | Primary key |
| connection_id | UUID | No | FK to xero_connections |
| xero_asset_type_id | UUID | No | Xero's asset type ID |
| asset_type_name | String(255) | No | Name of the asset type |
| fixed_asset_account_id | UUID | Yes | Balance sheet account |
| depreciation_expense_account_id | UUID | Yes | P&L depreciation account |
| accumulated_depreciation_account_id | UUID | Yes | Accumulated depreciation account |
| depreciation_method | Enum | No | How depreciation is calculated |
| averaging_method | Enum | No | Month or actual days |
| depreciation_rate | Decimal(10,4) | Yes | Annual rate (%) |
| effective_life_years | Integer | Yes | Asset life in years |
| calculation_method | Enum | No | Rate or Life based |

---

### XeroAsset

Fixed asset with depreciation tracking.

```python
class XeroAsset(TenantBase):
    """Fixed asset with depreciation details."""
    __tablename__ = "xero_assets"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[UUID] = mapped_column(ForeignKey("xero_connections.id"))
    xero_asset_id: Mapped[UUID] = mapped_column(unique=True)
    asset_type_id: Mapped[UUID | None] = mapped_column(ForeignKey("xero_asset_types.id"))

    # Asset identification
    asset_name: Mapped[str] = mapped_column(String(255))
    asset_number: Mapped[str | None] = mapped_column(String(50))
    serial_number: Mapped[str | None] = mapped_column(String(100))

    # Purchase details
    purchase_date: Mapped[date]
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    warranty_expiry_date: Mapped[date | None]

    # Disposal details
    disposal_date: Mapped[date | None]
    disposal_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))

    # Status
    status: Mapped[AssetStatus]

    # Depreciation settings (can override type defaults)
    depreciation_method: Mapped[DepreciationMethod | None]
    averaging_method: Mapped[AveragingMethod | None]
    depreciation_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    effective_life_years: Mapped[int | None]
    depreciation_start_date: Mapped[date | None]

    # Depreciation amounts
    cost_limit: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    residual_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    prior_accum_depreciation: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    current_accum_depreciation: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)

    # Calculated values
    book_value: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    current_capital_gain: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    current_gain_loss: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)

    # Control flags
    can_rollback: Mapped[bool] = mapped_column(default=False)
    is_delete_enabled: Mapped[bool] = mapped_column(default=False)

    # Metadata
    xero_updated_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(onupdate=func.now())

    # Relationships
    connection: Mapped["XeroConnection"] = relationship(back_populates="assets")
    asset_type: Mapped["XeroAssetType"] = relationship(back_populates="assets")
```

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | UUID | No | Primary key |
| connection_id | UUID | No | FK to xero_connections |
| xero_asset_id | UUID | No | Xero's asset ID |
| asset_type_id | UUID | Yes | FK to xero_asset_types |
| asset_name | String(255) | No | Asset name |
| asset_number | String(50) | Yes | Asset register number |
| serial_number | String(100) | Yes | Serial/model number |
| purchase_date | Date | No | Date asset was purchased |
| purchase_price | Decimal(15,2) | No | Original cost |
| warranty_expiry_date | Date | Yes | Warranty expiration |
| disposal_date | Date | Yes | Date disposed |
| disposal_price | Decimal(15,2) | Yes | Sale/disposal price |
| status | Enum | No | Draft/Registered/Disposed |
| book_value | Decimal(15,2) | No | Current book value |
| current_accum_depreciation | Decimal(15,2) | No | YTD depreciation |

---

### XeroPurchaseOrder

Purchase order for future cash outflows.

```python
class XeroPurchaseOrder(TenantBase):
    """Purchase order from Xero."""
    __tablename__ = "xero_purchase_orders"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[UUID] = mapped_column(ForeignKey("xero_connections.id"))
    xero_purchase_order_id: Mapped[UUID] = mapped_column(unique=True)
    contact_id: Mapped[UUID | None] = mapped_column(ForeignKey("xero_contacts.id"))

    # PO details
    purchase_order_number: Mapped[str | None] = mapped_column(String(50))
    reference: Mapped[str | None] = mapped_column(String(255))
    date: Mapped[date]
    delivery_date: Mapped[date | None]
    status: Mapped[PurchaseOrderStatus]

    # Amounts
    sub_total: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    total_tax: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    currency_code: Mapped[str] = mapped_column(String(3), default="AUD")
    currency_rate: Mapped[Decimal] = mapped_column(Numeric(15, 6), default=1)

    # Line items (JSONB for flexibility)
    line_items: Mapped[list] = mapped_column(JSONB, default=list)

    # Status flags
    sent_to_contact: Mapped[bool] = mapped_column(default=False)

    # Metadata
    xero_updated_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(onupdate=func.now())

    # Relationships
    connection: Mapped["XeroConnection"] = relationship(back_populates="purchase_orders")
    contact: Mapped["XeroContact"] = relationship()
```

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | UUID | No | Primary key |
| xero_purchase_order_id | UUID | No | Xero's PO ID |
| purchase_order_number | String(50) | Yes | PO number |
| date | Date | No | PO date |
| delivery_date | Date | Yes | Expected delivery |
| status | Enum | No | DRAFT/SUBMITTED/AUTHORISED/BILLED |
| total | Decimal(15,2) | No | Total amount |
| line_items | JSONB | No | Line item details |

---

### XeroRepeatingInvoice

Repeating invoice template for recurring revenue/expense.

```python
class XeroRepeatingInvoice(TenantBase):
    """Repeating invoice template from Xero."""
    __tablename__ = "xero_repeating_invoices"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[UUID] = mapped_column(ForeignKey("xero_connections.id"))
    xero_repeating_invoice_id: Mapped[UUID] = mapped_column(unique=True)
    contact_id: Mapped[UUID | None] = mapped_column(ForeignKey("xero_contacts.id"))

    # Type (ACCREC = sales, ACCPAY = bills)
    type: Mapped[str] = mapped_column(String(20))
    reference: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[RepeatingInvoiceStatus]

    # Schedule
    schedule_period: Mapped[int] = mapped_column(default=1)
    schedule_unit: Mapped[ScheduleUnit]
    schedule_due_date: Mapped[int | None]  # Days after invoice date
    schedule_due_date_type: Mapped[str | None] = mapped_column(String(50))
    schedule_start_date: Mapped[date | None]
    schedule_next_date: Mapped[date | None]
    schedule_end_date: Mapped[date | None]

    # Amounts
    sub_total: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    total_tax: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    currency_code: Mapped[str] = mapped_column(String(3), default="AUD")

    # Line items
    line_items: Mapped[list] = mapped_column(JSONB, default=list)

    # Metadata
    xero_updated_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(onupdate=func.now())

    # Relationships
    connection: Mapped["XeroConnection"] = relationship(back_populates="repeating_invoices")
    contact: Mapped["XeroContact"] = relationship()
```

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | UUID | No | Primary key |
| xero_repeating_invoice_id | UUID | No | Xero's template ID |
| type | String(20) | No | ACCREC (sales) or ACCPAY (bills) |
| status | Enum | No | DRAFT/AUTHORISED |
| schedule_unit | Enum | No | WEEKLY/MONTHLY/YEARLY |
| schedule_next_date | Date | Yes | Next scheduled date |
| total | Decimal(15,2) | No | Amount per occurrence |

---

### XeroTrackingCategory

Tracking category for segment analysis.

```python
class XeroTrackingCategory(TenantBase):
    """Tracking category from Xero."""
    __tablename__ = "xero_tracking_categories"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[UUID] = mapped_column(ForeignKey("xero_connections.id"))
    xero_tracking_category_id: Mapped[UUID] = mapped_column(unique=True)

    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[TrackingCategoryStatus]

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(onupdate=func.now())

    # Relationships
    connection: Mapped["XeroConnection"] = relationship(back_populates="tracking_categories")
    options: Mapped[list["XeroTrackingOption"]] = relationship(back_populates="category")
```

### XeroTrackingOption

```python
class XeroTrackingOption(TenantBase):
    """Option within a tracking category."""
    __tablename__ = "xero_tracking_options"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    category_id: Mapped[UUID] = mapped_column(ForeignKey("xero_tracking_categories.id"))
    xero_tracking_option_id: Mapped[UUID] = mapped_column(unique=True)

    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[TrackingCategoryStatus]

    # Relationships
    category: Mapped["XeroTrackingCategory"] = relationship(back_populates="options")
```

---

### XeroQuote

Quote for potential revenue.

```python
class XeroQuote(TenantBase):
    """Quote from Xero."""
    __tablename__ = "xero_quotes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[UUID] = mapped_column(ForeignKey("xero_connections.id"))
    xero_quote_id: Mapped[UUID] = mapped_column(unique=True)
    contact_id: Mapped[UUID | None] = mapped_column(ForeignKey("xero_contacts.id"))

    # Quote details
    quote_number: Mapped[str | None] = mapped_column(String(50))
    reference: Mapped[str | None] = mapped_column(String(255))
    date: Mapped[date]
    expiry_date: Mapped[date | None]
    status: Mapped[QuoteStatus]

    # Amounts
    sub_total: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    total_tax: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    currency_code: Mapped[str] = mapped_column(String(3), default="AUD")

    # Line items
    line_items: Mapped[list] = mapped_column(JSONB, default=list)

    # Metadata
    xero_updated_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(onupdate=func.now())

    # Relationships
    connection: Mapped["XeroConnection"] = relationship(back_populates="quotes")
    contact: Mapped["XeroContact"] = relationship()
```

---

## Database Indexes

```sql
-- Asset lookups
CREATE INDEX idx_xero_assets_connection ON xero_assets(connection_id);
CREATE INDEX idx_xero_assets_status ON xero_assets(status);
CREATE INDEX idx_xero_assets_purchase_date ON xero_assets(purchase_date);
CREATE INDEX idx_xero_assets_type ON xero_assets(asset_type_id);

-- Asset type lookups
CREATE INDEX idx_xero_asset_types_connection ON xero_asset_types(connection_id);

-- Purchase order lookups
CREATE INDEX idx_xero_purchase_orders_connection ON xero_purchase_orders(connection_id);
CREATE INDEX idx_xero_purchase_orders_status ON xero_purchase_orders(status);
CREATE INDEX idx_xero_purchase_orders_date ON xero_purchase_orders(date);

-- Repeating invoice lookups
CREATE INDEX idx_xero_repeating_invoices_connection ON xero_repeating_invoices(connection_id);
CREATE INDEX idx_xero_repeating_invoices_next_date ON xero_repeating_invoices(schedule_next_date);

-- Tracking category lookups
CREATE INDEX idx_xero_tracking_categories_connection ON xero_tracking_categories(connection_id);

-- Quote lookups
CREATE INDEX idx_xero_quotes_connection ON xero_quotes(connection_id);
CREATE INDEX idx_xero_quotes_status ON xero_quotes(status);
CREATE INDEX idx_xero_quotes_expiry ON xero_quotes(expiry_date);
```

---

## Migration Template

```python
"""Add fixed assets and enhanced analysis tables.

Revision ID: xxx
Create Date: 2026-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

def upgrade() -> None:
    # Asset types
    op.create_table(
        "xero_asset_types",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", UUID(as_uuid=True), sa.ForeignKey("xero_connections.id")),
        sa.Column("xero_asset_type_id", UUID(as_uuid=True), unique=True),
        sa.Column("asset_type_name", sa.String(255), nullable=False),
        sa.Column("fixed_asset_account_id", UUID(as_uuid=True)),
        sa.Column("depreciation_expense_account_id", UUID(as_uuid=True)),
        sa.Column("accumulated_depreciation_account_id", UUID(as_uuid=True)),
        sa.Column("depreciation_method", sa.String(50), nullable=False),
        sa.Column("averaging_method", sa.String(20), nullable=False),
        sa.Column("depreciation_rate", sa.Numeric(10, 4)),
        sa.Column("effective_life_years", sa.Integer),
        sa.Column("calculation_method", sa.String(20), nullable=False),
        sa.Column("locks", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Assets
    op.create_table(
        "xero_assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", UUID(as_uuid=True), sa.ForeignKey("xero_connections.id")),
        sa.Column("xero_asset_id", UUID(as_uuid=True), unique=True),
        sa.Column("asset_type_id", UUID(as_uuid=True), sa.ForeignKey("xero_asset_types.id")),
        sa.Column("asset_name", sa.String(255), nullable=False),
        sa.Column("asset_number", sa.String(50)),
        sa.Column("serial_number", sa.String(100)),
        sa.Column("purchase_date", sa.Date, nullable=False),
        sa.Column("purchase_price", sa.Numeric(15, 2), nullable=False),
        sa.Column("warranty_expiry_date", sa.Date),
        sa.Column("disposal_date", sa.Date),
        sa.Column("disposal_price", sa.Numeric(15, 2)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("depreciation_method", sa.String(50)),
        sa.Column("averaging_method", sa.String(20)),
        sa.Column("depreciation_rate", sa.Numeric(10, 4)),
        sa.Column("effective_life_years", sa.Integer),
        sa.Column("depreciation_start_date", sa.Date),
        sa.Column("cost_limit", sa.Numeric(15, 2), default=0),
        sa.Column("residual_value", sa.Numeric(15, 2), default=0),
        sa.Column("prior_accum_depreciation", sa.Numeric(15, 2), default=0),
        sa.Column("current_accum_depreciation", sa.Numeric(15, 2), default=0),
        sa.Column("book_value", sa.Numeric(15, 2), nullable=False),
        sa.Column("current_capital_gain", sa.Numeric(15, 2), default=0),
        sa.Column("current_gain_loss", sa.Numeric(15, 2), default=0),
        sa.Column("can_rollback", sa.Boolean, default=False),
        sa.Column("is_delete_enabled", sa.Boolean, default=False),
        sa.Column("xero_updated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Purchase orders
    op.create_table(
        "xero_purchase_orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", UUID(as_uuid=True), sa.ForeignKey("xero_connections.id")),
        sa.Column("xero_purchase_order_id", UUID(as_uuid=True), unique=True),
        sa.Column("contact_id", UUID(as_uuid=True), sa.ForeignKey("xero_contacts.id")),
        sa.Column("purchase_order_number", sa.String(50)),
        sa.Column("reference", sa.String(255)),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("delivery_date", sa.Date),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("sub_total", sa.Numeric(15, 2), default=0),
        sa.Column("total_tax", sa.Numeric(15, 2), default=0),
        sa.Column("total", sa.Numeric(15, 2), default=0),
        sa.Column("currency_code", sa.String(3), default="AUD"),
        sa.Column("currency_rate", sa.Numeric(15, 6), default=1),
        sa.Column("line_items", JSONB, default=[]),
        sa.Column("sent_to_contact", sa.Boolean, default=False),
        sa.Column("xero_updated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Repeating invoices
    op.create_table(
        "xero_repeating_invoices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", UUID(as_uuid=True), sa.ForeignKey("xero_connections.id")),
        sa.Column("xero_repeating_invoice_id", UUID(as_uuid=True), unique=True),
        sa.Column("contact_id", UUID(as_uuid=True), sa.ForeignKey("xero_contacts.id")),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("reference", sa.String(255)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("schedule_period", sa.Integer, default=1),
        sa.Column("schedule_unit", sa.String(20), nullable=False),
        sa.Column("schedule_due_date", sa.Integer),
        sa.Column("schedule_due_date_type", sa.String(50)),
        sa.Column("schedule_start_date", sa.Date),
        sa.Column("schedule_next_date", sa.Date),
        sa.Column("schedule_end_date", sa.Date),
        sa.Column("sub_total", sa.Numeric(15, 2), default=0),
        sa.Column("total_tax", sa.Numeric(15, 2), default=0),
        sa.Column("total", sa.Numeric(15, 2), default=0),
        sa.Column("currency_code", sa.String(3), default="AUD"),
        sa.Column("line_items", JSONB, default=[]),
        sa.Column("xero_updated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Tracking categories
    op.create_table(
        "xero_tracking_categories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", UUID(as_uuid=True), sa.ForeignKey("xero_connections.id")),
        sa.Column("xero_tracking_category_id", UUID(as_uuid=True), unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Tracking options
    op.create_table(
        "xero_tracking_options",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", UUID(as_uuid=True), sa.ForeignKey("xero_tracking_categories.id")),
        sa.Column("xero_tracking_option_id", UUID(as_uuid=True), unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
    )

    # Quotes
    op.create_table(
        "xero_quotes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", UUID(as_uuid=True), sa.ForeignKey("xero_connections.id")),
        sa.Column("xero_quote_id", UUID(as_uuid=True), unique=True),
        sa.Column("contact_id", UUID(as_uuid=True), sa.ForeignKey("xero_contacts.id")),
        sa.Column("quote_number", sa.String(50)),
        sa.Column("reference", sa.String(255)),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("expiry_date", sa.Date),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("sub_total", sa.Numeric(15, 2), default=0),
        sa.Column("total_tax", sa.Numeric(15, 2), default=0),
        sa.Column("total", sa.Numeric(15, 2), default=0),
        sa.Column("currency_code", sa.String(3), default="AUD"),
        sa.Column("line_items", JSONB, default=[]),
        sa.Column("xero_updated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Create indexes
    op.create_index("idx_xero_assets_connection", "xero_assets", ["connection_id"])
    op.create_index("idx_xero_assets_status", "xero_assets", ["status"])
    op.create_index("idx_xero_assets_purchase_date", "xero_assets", ["purchase_date"])
    op.create_index("idx_xero_purchase_orders_connection", "xero_purchase_orders", ["connection_id"])
    op.create_index("idx_xero_purchase_orders_status", "xero_purchase_orders", ["status"])
    op.create_index("idx_xero_repeating_invoices_connection", "xero_repeating_invoices", ["connection_id"])
    op.create_index("idx_xero_quotes_connection", "xero_quotes", ["connection_id"])
    op.create_index("idx_xero_quotes_status", "xero_quotes", ["status"])


def downgrade() -> None:
    op.drop_table("xero_quotes")
    op.drop_table("xero_tracking_options")
    op.drop_table("xero_tracking_categories")
    op.drop_table("xero_repeating_invoices")
    op.drop_table("xero_purchase_orders")
    op.drop_table("xero_assets")
    op.drop_table("xero_asset_types")
```

---

*End of Data Model Document*
