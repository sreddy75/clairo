# Data Model: ATO Correspondence Parsing

**Spec**: 027-ato-correspondence-parsing
**Date**: 2026-01-01

---

## Entity Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ENTITY DIAGRAM                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐        ┌─────────────────┐                        │
│  │    RawEmail     │ 1───1  │ ATOCorrespondence│                        │
│  │  (from Spec 026)│◄───────│                 │                        │
│  └─────────────────┘        │ - notice_type   │                        │
│                             │ - due_date      │                        │
│                             │ - amount        │                        │
│                             │ - confidence    │                        │
│                             └────────┬────────┘                        │
│                                      │                                  │
│                                      │ N:1 (optional)                   │
│                                      ▼                                  │
│                             ┌─────────────────┐                        │
│                             │     Client      │                        │
│                             │  (existing)     │                        │
│                             └─────────────────┘                        │
│                                                                         │
│  ┌─────────────────┐        ┌─────────────────┐                        │
│  │ ATOCorrespondence│ 1───1  │   TriageItem    │                        │
│  │ (unmatched)     │◄───────│                 │                        │
│  └─────────────────┘        │ - suggested_id  │                        │
│                             │ - action        │                        │
│                             └─────────────────┘                        │
│                                                                         │
│  QDRANT (Vector Store)                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Collection: ato_correspondence_{tenant_id}                      │   │
│  │  - correspondence_id (UUID)                                      │   │
│  │  - embedding (1536 dimensions)                                   │   │
│  │  - metadata (notice_type, client_id, received_at)               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Entities

### 1. ATOCorrespondence

**Purpose**: Stores parsed and structured ATO email data.

```python
class ATONoticeType(str, Enum):
    """Classification of ATO notice types."""
    # Activity Statements
    ACTIVITY_STATEMENT_REMINDER = "activity_statement_reminder"
    ACTIVITY_STATEMENT_CONFIRMATION = "activity_statement_confirmation"
    ACTIVITY_STATEMENT_AMENDMENT = "activity_statement_amendment"

    # Compliance
    AUDIT_NOTICE = "audit_notice"
    AUDIT_OUTCOME = "audit_outcome"
    INFORMATION_REQUEST = "information_request"

    # Debt & Penalties
    PENALTY_NOTICE = "penalty_notice"
    DEBT_NOTICE = "debt_notice"
    PAYMENT_REMINDER = "payment_reminder"
    PAYMENT_PLAN = "payment_plan"

    # Running Balance
    RUNNING_BALANCE_ACCOUNT = "running_balance_account"
    CREDIT_NOTICE = "credit_notice"

    # Tax Returns
    TAX_RETURN_REMINDER = "tax_return_reminder"
    TAX_ASSESSMENT = "tax_assessment"
    TAX_AMENDMENT = "tax_amendment"

    # Obligations
    SUPERANNUATION_NOTICE = "superannuation_notice"
    PAYG_WITHHOLDING = "payg_withholding"
    FBT_NOTICE = "fringe_benefits_tax"

    # Other
    REGISTRATION = "registration"
    GENERAL = "general"
    UNKNOWN = "unknown"


class CorrespondenceStatus(str, Enum):
    """Processing status of correspondence."""
    NEW = "new"                # Just parsed, not reviewed
    REVIEWED = "reviewed"      # Accountant has viewed
    ACTIONED = "actioned"      # Task created or action taken
    RESOLVED = "resolved"      # Complete, no further action
    IGNORED = "ignored"        # Marked as not relevant


class MatchType(str, Enum):
    """How the client was matched."""
    ABN_EXACT = "abn_exact"
    TFN_EXACT = "tfn_exact"
    NAME_FUZZY = "name_fuzzy"
    MANUAL = "manual"
    NONE = "none"


class ATOCorrespondence(Base):
    """Parsed ATO email correspondence."""
    __tablename__ = "ato_correspondence"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Multi-tenancy
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)

    # Source email reference
    raw_email_id: Mapped[UUID] = mapped_column(
        ForeignKey("raw_emails.id"),
        unique=True,
        index=True
    )

    # Client matching (optional - may be in triage)
    client_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clients.id"),
        nullable=True,
        index=True
    )
    match_type: Mapped[MatchType] = mapped_column(default=MatchType.NONE)
    match_confidence: Mapped[float] = mapped_column(default=0.0)  # 0-100

    # Email metadata (denormalized for quick access)
    subject: Mapped[str] = mapped_column(String(500))
    from_address: Mapped[str] = mapped_column(String(255))
    received_at: Mapped[datetime] = mapped_column(index=True)

    # Parsed fields
    notice_type: Mapped[ATONoticeType] = mapped_column(index=True)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    due_date: Mapped[date | None] = mapped_column(nullable=True, index=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    required_action: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI parsing metadata
    parsed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    parsing_confidence: Mapped[float] = mapped_column(default=0.0)  # 0-100
    parsing_model: Mapped[str] = mapped_column(String(100))  # e.g., "claude-3-5-sonnet-20241022"
    raw_parsed_json: Mapped[dict] = mapped_column(JSONB, default=dict)  # Full Claude response

    # Vector store reference
    vector_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Workflow status
    status: Mapped[CorrespondenceStatus] = mapped_column(
        default=CorrespondenceStatus.NEW,
        index=True
    )

    # Future integration (Spec 028)
    task_id: Mapped[UUID | None] = mapped_column(nullable=True)
    insight_id: Mapped[UUID | None] = mapped_column(nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="ato_correspondence")
    raw_email: Mapped["RawEmail"] = relationship(back_populates="correspondence")
    client: Mapped["Client"] = relationship(back_populates="ato_correspondence")
    triage_item: Mapped["TriageItem"] = relationship(
        back_populates="correspondence",
        uselist=False
    )
```

**Indexes**:
- `tenant_id` - Multi-tenancy filtering
- `raw_email_id` - Unique constraint, lookup by source
- `client_id` - Filter by client
- `notice_type` - Filter by type
- `due_date` - Order by urgency
- `status` - Filter by workflow status
- `(tenant_id, received_at)` - Composite for timeline queries
- `(tenant_id, client_id, received_at)` - Client correspondence history

---

### 2. TriageItem

**Purpose**: Queue of correspondence needing manual client assignment.

```python
class TriageAction(str, Enum):
    """Action taken on triage item."""
    PENDING = "pending"
    ASSIGNED = "assigned"     # Client manually assigned
    IGNORED = "ignored"       # Not relevant
    DUPLICATE = "duplicate"   # Duplicate of another item


class TriageItem(Base):
    """Item in triage queue for manual review."""
    __tablename__ = "triage_items"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Multi-tenancy
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)

    # Reference to unmatched correspondence
    correspondence_id: Mapped[UUID] = mapped_column(
        ForeignKey("ato_correspondence.id"),
        unique=True,
        index=True
    )

    # Matching info
    extracted_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    identifier_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # abn, tfn, name

    # Suggestions from fuzzy matching
    suggested_client_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clients.id"),
        nullable=True
    )
    suggested_confidence: Mapped[float | None] = mapped_column(nullable=True)

    # Triage status
    action: Mapped[TriageAction] = mapped_column(
        default=TriageAction.PENDING,
        index=True
    )

    # Resolution
    resolved_by_user_id: Mapped[UUID | None] = mapped_column(nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship()
    correspondence: Mapped["ATOCorrespondence"] = relationship(back_populates="triage_item")
    suggested_client: Mapped["Client"] = relationship()
```

**Indexes**:
- `tenant_id` - Multi-tenancy
- `correspondence_id` - Unique lookup
- `action` - Filter by triage status
- `(tenant_id, action, created_at)` - Queue ordering

---

### 3. ParsingJob

**Purpose**: Track bulk parsing jobs and retries.

```python
class ParsingJobStatus(str, Enum):
    """Status of a parsing job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some emails failed


class ParsingJob(Base):
    """Tracking for email parsing jobs."""
    __tablename__ = "parsing_jobs"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Multi-tenancy
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)

    # Job info
    job_type: Mapped[str] = mapped_column(String(50))  # "single", "batch", "backfill"
    status: Mapped[ParsingJobStatus] = mapped_column(default=ParsingJobStatus.PENDING)

    # Progress tracking
    total_emails: Mapped[int] = mapped_column(default=0)
    processed_emails: Mapped[int] = mapped_column(default=0)
    successful_parses: Mapped[int] = mapped_column(default=0)
    failed_parses: Mapped[int] = mapped_column(default=0)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Error tracking
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

---

### 4. CorrespondenceCorrection

**Purpose**: Track manual corrections for audit and learning.

```python
class CorrespondenceCorrection(Base):
    """Record of manual corrections to parsed data."""
    __tablename__ = "correspondence_corrections"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Multi-tenancy
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)

    # Reference
    correspondence_id: Mapped[UUID] = mapped_column(
        ForeignKey("ato_correspondence.id"),
        index=True
    )

    # Correction details
    field_name: Mapped[str] = mapped_column(String(100))  # e.g., "notice_type", "due_date"
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str] = mapped_column(Text)

    # Who made the correction
    corrected_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    correspondence: Mapped["ATOCorrespondence"] = relationship()
    corrected_by: Mapped["User"] = relationship()
```

---

## Qdrant Vector Storage

### Collection Schema

```python
# Collection per tenant for data isolation
COLLECTION_NAME_PATTERN = "ato_correspondence_{tenant_id}"

# Vector configuration
VECTOR_CONFIG = VectorParams(
    size=1536,  # OpenAI text-embedding-3-small
    distance=Distance.COSINE,
)

# Point structure
class QdrantPoint:
    id: str  # correspondence_id as string
    vector: list[float]  # 1536-dimension embedding
    payload: {
        "correspondence_id": str,
        "notice_type": str,
        "client_id": str | None,
        "subject": str,
        "received_at": str,  # ISO format
        "due_date": str | None,
        "has_amount": bool,
    }
```

### Search Filters

```python
# Filter by notice type
notice_type_filter = FieldCondition(
    key="notice_type",
    match=MatchValue(value="penalty_notice"),
)

# Filter by client
client_filter = FieldCondition(
    key="client_id",
    match=MatchValue(value="client-uuid"),
)

# Filter by date range
date_range_filter = FieldCondition(
    key="received_at",
    range=DatetimeRange(
        gte="2025-01-01T00:00:00Z",
        lte="2025-12-31T23:59:59Z",
    ),
)

# Combine filters
combined_filter = Filter(
    must=[notice_type_filter, client_filter],
)
```

---

## Database Migrations

### Migration: Add ATO Correspondence Tables

```python
# alembic/versions/xxx_add_ato_correspondence.py

def upgrade():
    # Create notice type enum
    op.execute("""
        CREATE TYPE ato_notice_type AS ENUM (
            'activity_statement_reminder',
            'activity_statement_confirmation',
            'activity_statement_amendment',
            'audit_notice',
            'audit_outcome',
            'information_request',
            'penalty_notice',
            'debt_notice',
            'payment_reminder',
            'payment_plan',
            'running_balance_account',
            'credit_notice',
            'tax_return_reminder',
            'tax_assessment',
            'tax_amendment',
            'superannuation_notice',
            'payg_withholding',
            'fringe_benefits_tax',
            'registration',
            'general',
            'unknown'
        )
    """)

    # Create correspondence status enum
    op.execute("""
        CREATE TYPE correspondence_status AS ENUM (
            'new', 'reviewed', 'actioned', 'resolved', 'ignored'
        )
    """)

    # Create match type enum
    op.execute("""
        CREATE TYPE match_type AS ENUM (
            'abn_exact', 'tfn_exact', 'name_fuzzy', 'manual', 'none'
        )
    """)

    # Create ato_correspondence table
    op.create_table(
        'ato_correspondence',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('raw_email_id', sa.UUID(), sa.ForeignKey('raw_emails.id'), unique=True),
        sa.Column('client_id', sa.UUID(), sa.ForeignKey('clients.id'), nullable=True),
        sa.Column('match_type', sa.Enum('match_type'), default='none'),
        sa.Column('match_confidence', sa.Float(), default=0.0),
        sa.Column('subject', sa.String(500), nullable=False),
        sa.Column('from_address', sa.String(255), nullable=False),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('notice_type', sa.Enum('ato_notice_type'), nullable=False),
        sa.Column('reference_number', sa.String(100), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('required_action', sa.Text(), nullable=True),
        sa.Column('parsed_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('parsing_confidence', sa.Float(), default=0.0),
        sa.Column('parsing_model', sa.String(100), nullable=False),
        sa.Column('raw_parsed_json', sa.JSON(), default={}),
        sa.Column('vector_id', sa.String(100), nullable=True),
        sa.Column('status', sa.Enum('correspondence_status'), default='new'),
        sa.Column('task_id', sa.UUID(), nullable=True),
        sa.Column('insight_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Add indexes
    op.create_index('ix_ato_correspondence_tenant_id', 'ato_correspondence', ['tenant_id'])
    op.create_index('ix_ato_correspondence_client_id', 'ato_correspondence', ['client_id'])
    op.create_index('ix_ato_correspondence_notice_type', 'ato_correspondence', ['notice_type'])
    op.create_index('ix_ato_correspondence_due_date', 'ato_correspondence', ['due_date'])
    op.create_index('ix_ato_correspondence_status', 'ato_correspondence', ['status'])
    op.create_index(
        'ix_ato_correspondence_tenant_received',
        'ato_correspondence',
        ['tenant_id', 'received_at']
    )

    # Create triage_items table
    op.create_table(
        'triage_items',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('correspondence_id', sa.UUID(), sa.ForeignKey('ato_correspondence.id'), unique=True),
        sa.Column('extracted_identifier', sa.String(255), nullable=True),
        sa.Column('identifier_type', sa.String(50), nullable=True),
        sa.Column('suggested_client_id', sa.UUID(), sa.ForeignKey('clients.id'), nullable=True),
        sa.Column('suggested_confidence', sa.Float(), nullable=True),
        sa.Column('action', sa.String(50), default='pending'),
        sa.Column('resolved_by_user_id', sa.UUID(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Enable RLS
    op.execute("ALTER TABLE ato_correspondence ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE triage_items ENABLE ROW LEVEL SECURITY")


def downgrade():
    op.drop_table('triage_items')
    op.drop_table('ato_correspondence')
    op.execute("DROP TYPE correspondence_status")
    op.execute("DROP TYPE match_type")
    op.execute("DROP TYPE ato_notice_type")
```

---

## Data Validation Rules

### ATOCorrespondence

| Field | Validation |
|-------|------------|
| `notice_type` | Must be valid enum value |
| `reference_number` | Optional, max 100 chars |
| `due_date` | Must be valid date if present |
| `amount` | Must be positive if present |
| `parsing_confidence` | 0-100 range |
| `match_confidence` | 0-100 range |

### Business Rules

1. **One correspondence per email**: `raw_email_id` is unique
2. **Triage if low confidence**: Create TriageItem if `match_confidence < 80`
3. **Status transitions**:
   - NEW → REVIEWED (on view)
   - REVIEWED → ACTIONED (on task creation)
   - ACTIONED → RESOLVED (on completion)
   - Any → IGNORED (user action)
4. **Client required for non-triage**: If not in triage, `client_id` should be set
