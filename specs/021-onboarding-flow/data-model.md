# Data Model: Onboarding Flow

**Feature**: 021-onboarding-flow
**Date**: 2025-12-31
**Status**: Complete

---

## Overview

This document defines the database models required for the onboarding flow feature. All models follow the Clairo constitution (multi-tenancy, audit, repository pattern).

---

## Entity Relationship Diagram

```
┌─────────────────┐       ┌──────────────────────┐
│     Tenant      │───────│  OnboardingProgress  │
│  (auth module)  │  1:1  │                      │
└─────────────────┘       └──────────────────────┘
        │                           │
        │                           │ 1:N
        │                           ▼
        │                 ┌──────────────────────┐
        │                 │   BulkImportJob      │
        │                 └──────────────────────┘
        │
        │ 1:N
        ▼
┌─────────────────┐
│   EmailDrip     │
│                 │
└─────────────────┘
```

---

## New Models

### 1. OnboardingProgress

Tracks each tenant's progress through the onboarding flow.

**Table**: `onboarding_progress`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | UUID | No | Primary key |
| `tenant_id` | UUID | No | FK to tenants.id (unique) |
| `status` | Enum | No | Current onboarding state |
| `current_step` | String | No | Current step identifier |
| `started_at` | Timestamp | No | When onboarding began |
| `tier_selected_at` | Timestamp | Yes | When tier was chosen |
| `payment_setup_at` | Timestamp | Yes | When Stripe checkout completed |
| `xero_connected_at` | Timestamp | Yes | When Xero OAuth completed |
| `clients_imported_at` | Timestamp | Yes | When first client imported |
| `tour_completed_at` | Timestamp | Yes | When product tour finished |
| `completed_at` | Timestamp | Yes | When all steps done |
| `checklist_dismissed_at` | Timestamp | Yes | When user dismissed checklist |
| `xero_skipped` | Boolean | No | Whether user skipped Xero connection |
| `tour_skipped` | Boolean | No | Whether user skipped product tour |
| `metadata` | JSONB | No | Additional tracking data |
| `created_at` | Timestamp | No | Record creation time |
| `updated_at` | Timestamp | No | Last update time |

**Indexes**:
- `idx_onboarding_progress_tenant_id` (unique)
- `idx_onboarding_progress_status`

**Constraints**:
- `tenant_id` is unique (one progress record per tenant)
- FK to `tenants.id` with CASCADE delete

**Enum: OnboardingStatus**
```python
class OnboardingStatus(str, Enum):
    STARTED = "started"
    TIER_SELECTED = "tier_selected"
    PAYMENT_SETUP = "payment_setup"
    XERO_CONNECTED = "xero_connected"
    CLIENTS_IMPORTED = "clients_imported"
    TOUR_COMPLETED = "tour_completed"
    COMPLETED = "completed"
    SKIPPED_XERO = "skipped_xero"  # Alternative path
```

**SQLAlchemy Model**:
```python
class OnboardingProgress(Base, TimestampMixin):
    __tablename__ = "onboarding_progress"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[OnboardingStatus] = mapped_column(
        Enum(OnboardingStatus, name="onboarding_status"),
        nullable=False,
        default=OnboardingStatus.STARTED,
        index=True,
    )
    current_step: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="tier_selection",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    tier_selected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    payment_setup_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    xero_connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    clients_imported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    tour_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    checklist_dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    xero_skipped: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    tour_skipped: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="onboarding_progress")
```

---

### 2. BulkImportJob

Tracks bulk client import jobs with progress.

**Table**: `bulk_import_jobs`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | UUID | No | Primary key |
| `tenant_id` | UUID | No | FK to tenants.id |
| `status` | Enum | No | Job status |
| `source_type` | String | No | "xpm" or "xero_accounting" |
| `total_clients` | Integer | No | Total clients to import |
| `imported_count` | Integer | No | Successfully imported |
| `failed_count` | Integer | No | Failed imports |
| `client_ids` | JSONB | No | List of XPM/Xero client IDs to import |
| `imported_clients` | JSONB | No | List of imported client IDs with details |
| `failed_clients` | JSONB | No | List of failed clients with error details |
| `progress_percent` | Integer | No | Current progress (0-100) |
| `started_at` | Timestamp | No | Job start time |
| `completed_at` | Timestamp | Yes | Job completion time |
| `error_message` | Text | Yes | Overall error if job failed |
| `created_at` | Timestamp | No | Record creation |
| `updated_at` | Timestamp | No | Last update |

**Indexes**:
- `idx_bulk_import_jobs_tenant_id`
- `idx_bulk_import_jobs_status`
- `idx_bulk_import_jobs_created_at`

**Enum: BulkImportJobStatus**
```python
class BulkImportJobStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

**SQLAlchemy Model**:
```python
class BulkImportJob(Base, TimestampMixin):
    __tablename__ = "bulk_import_jobs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[BulkImportJobStatus] = mapped_column(
        Enum(BulkImportJobStatus, name="bulk_import_job_status"),
        nullable=False,
        default=BulkImportJobStatus.PENDING,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    total_clients: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    imported_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    failed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    client_ids: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    imported_clients: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    failed_clients: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    progress_percent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="import_jobs")

    # Computed property
    @property
    def is_complete(self) -> bool:
        return self.status in (
            BulkImportJobStatus.COMPLETED,
            BulkImportJobStatus.PARTIAL_FAILURE,
            BulkImportJobStatus.FAILED,
        )
```

---

### 3. EmailDrip

Tracks sent onboarding emails to prevent duplicates.

**Table**: `email_drips`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | UUID | No | Primary key |
| `tenant_id` | UUID | No | FK to tenants.id |
| `email_type` | String | No | Email template identifier |
| `sent_at` | Timestamp | No | When email was sent |
| `recipient_email` | String | No | Recipient email address |
| `metadata` | JSONB | No | Additional context |
| `created_at` | Timestamp | No | Record creation |

**Indexes**:
- `idx_email_drips_tenant_id`
- `idx_email_drips_email_type`

**Constraints**:
- Unique constraint on `(tenant_id, email_type)` - one email type per tenant

**Email Types**:
```python
class EmailDripType(str, Enum):
    WELCOME = "welcome"
    CONNECT_XERO = "connect_xero"
    IMPORT_CLIENTS = "import_clients"
    TRIAL_MIDPOINT = "trial_midpoint"
    TRIAL_ENDING = "trial_ending"
    TRIAL_ENDED = "trial_ended"
    ONBOARDING_COMPLETE = "onboarding_complete"
```

**SQLAlchemy Model**:
```python
class EmailDrip(Base):
    __tablename__ = "email_drips"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    recipient_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "email_type", name="uq_email_drip_tenant_type"),
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="email_drips")
```

---

## Extended Models (Existing)

### Tenant (auth module)

Add relationship to new models:

```python
# In app/modules/auth/models.py - Tenant class
# Add these relationships:

onboarding_progress: Mapped["OnboardingProgress"] = relationship(
    back_populates="tenant",
    uselist=False,  # 1:1 relationship
)
import_jobs: Mapped[list["BulkImportJob"]] = relationship(
    back_populates="tenant",
)
email_drips: Mapped[list["EmailDrip"]] = relationship(
    back_populates="tenant",
)
```

### Tenant - Trial Fields

Already exists from Spec 019/020:
- `tier: SubscriptionTier`
- `subscription_status: SubscriptionStatus`
- `trial_ends_at: datetime | None`

---

## Migration

**Alembic migration file**: `migrations/versions/xxx_add_onboarding_tables.py`

```python
def upgrade():
    # Create onboarding_status enum
    op.execute("""
        CREATE TYPE onboarding_status AS ENUM (
            'started', 'tier_selected', 'payment_setup',
            'xero_connected', 'clients_imported',
            'tour_completed', 'completed', 'skipped_xero'
        )
    """)

    # Create bulk_import_job_status enum
    op.execute("""
        CREATE TYPE bulk_import_job_status AS ENUM (
            'pending', 'in_progress', 'completed',
            'partial_failure', 'failed', 'cancelled'
        )
    """)

    # Create onboarding_progress table
    op.create_table(
        'onboarding_progress',
        sa.Column('id', postgresql.UUID(as_uuid=True), ...),
        # ... all columns
    )

    # Create bulk_import_jobs table
    op.create_table(
        'bulk_import_jobs',
        # ... all columns
    )

    # Create email_drips table
    op.create_table(
        'email_drips',
        # ... all columns
    )

    # Create indexes
    op.create_index(...)


def downgrade():
    op.drop_table('email_drips')
    op.drop_table('bulk_import_jobs')
    op.drop_table('onboarding_progress')
    op.execute("DROP TYPE bulk_import_job_status")
    op.execute("DROP TYPE onboarding_status")
```

---

## Validation Rules

### OnboardingProgress

| Field | Rule |
|-------|------|
| `status` | Valid OnboardingStatus enum |
| `current_step` | One of: tier_selection, connect_xero, import_clients, product_tour, complete |
| `metadata` | Valid JSON object |

### BulkImportJob

| Field | Rule |
|-------|------|
| `source_type` | One of: "xpm", "xero_accounting" |
| `total_clients` | >= 0 |
| `imported_count` | >= 0, <= total_clients |
| `failed_count` | >= 0, <= total_clients |
| `progress_percent` | 0-100 |
| `client_ids` | Array of valid UUIDs/strings |

### EmailDrip

| Field | Rule |
|-------|------|
| `email_type` | Valid EmailDripType |
| `recipient_email` | Valid email format |

---

## State Transitions

### OnboardingProgress State Machine

```
STARTED
    ↓ (select tier)
TIER_SELECTED
    ↓ (complete Stripe checkout)
PAYMENT_SETUP
    ↓ (connect Xero)          ↘ (skip Xero)
XERO_CONNECTED              SKIPPED_XERO
    ↓ (import clients)         ↓
CLIENTS_IMPORTED  ←───────────┘
    ↓ (complete tour)
TOUR_COMPLETED
    ↓ (automatic after tour)
COMPLETED
```

### BulkImportJob State Machine

```
PENDING
    ↓ (Celery picks up)
IN_PROGRESS
    ↓ (all succeed)    ↘ (some fail)    ↘ (all fail/error)
COMPLETED         PARTIAL_FAILURE      FAILED
                        ↓ (user clicks retry)
                    PENDING (new job)
```
