# Data Model: ATOtrack Workflow Integration

**Spec**: 028-atotrack-workflow-integration
**Date**: 2026-01-01

---

## Entity Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ENTITY DIAGRAM                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐        ┌─────────────────┐                        │
│  │ ATOCorrespondence│ 1───1  │      Task       │                        │
│  │  (from Spec 027)│◄───────│   (existing)    │                        │
│  │                 │        │                 │                        │
│  │  + task_id      │        │ + source_type   │                        │
│  │  + insight_id   │        │ + source_id     │                        │
│  └────────┬────────┘        └─────────────────┘                        │
│           │                                                             │
│           │ 1:1                                                         │
│           ▼                                                             │
│  ┌─────────────────┐        ┌─────────────────┐                        │
│  │     Insight     │        │  Notification   │                        │
│  │   (existing)    │        │   (existing)    │                        │
│  │                 │        │                 │                        │
│  │ + source_type   │        │ + trigger_type  │                        │
│  │ + source_id     │        │ + source_id     │                        │
│  └─────────────────┘        └─────────────────┘                        │
│                                                                         │
│  NEW ENTITIES                                                           │
│  ┌─────────────────┐        ┌─────────────────┐                        │
│  │  ResponseDraft  │        │ PMIntegration   │                        │
│  │                 │        │                 │                        │
│  │ - correspondence│        │ - provider      │                        │
│  │ - draft_type    │        │ - credentials   │                        │
│  │ - content       │        │ - sync_enabled  │                        │
│  └─────────────────┘        └─────────────────┘                        │
│                                                                         │
│  ┌─────────────────┐        ┌─────────────────┐                        │
│  │ NotificationRule│        │  PMSyncRecord   │                        │
│  │                 │        │                 │                        │
│  │ - correspondence│        │ - correspondence│                        │
│  │ - trigger_days  │        │ - external_id   │                        │
│  │ - status        │        │ - sync_status   │                        │
│  └─────────────────┘        └─────────────────┘                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Entity Extensions

### ATOCorrespondence (Extended)

**Purpose**: Add workflow integration fields to existing correspondence model.

```python
# Additional fields for ATOCorrespondence (Spec 027)
class ATOCorrespondence(Base):
    # ... existing fields from Spec 027 ...

    # Workflow integration (NEW)
    task_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tasks.id"),
        nullable=True,
        index=True
    )
    insight_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("insights.id"),
        nullable=True,
        index=True
    )

    # Workflow flags
    workflow_processed: Mapped[bool] = mapped_column(default=False)
    workflow_processed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    task: Mapped["Task"] = relationship(back_populates="ato_correspondence")
    insight: Mapped["Insight"] = relationship(back_populates="ato_correspondence")
    response_drafts: Mapped[list["ResponseDraft"]] = relationship(back_populates="correspondence")
    notification_rules: Mapped[list["NotificationRule"]] = relationship(back_populates="correspondence")
    pm_sync_records: Mapped[list["PMSyncRecord"]] = relationship(back_populates="correspondence")
```

### Task (Extended)

**Purpose**: Add source tracking to existing task model.

```python
# Additional fields for Task module
class TaskSourceType(str, Enum):
    MANUAL = "manual"
    ATO_CORRESPONDENCE = "ato_correspondence"
    TRIGGER = "trigger"
    INSIGHT = "insight"

class Task(Base):
    # ... existing fields ...

    # Source tracking (NEW)
    source_type: Mapped[TaskSourceType] = mapped_column(
        default=TaskSourceType.MANUAL
    )
    source_id: Mapped[UUID | None] = mapped_column(nullable=True)

    # Relationships
    ato_correspondence: Mapped["ATOCorrespondence"] = relationship(
        back_populates="task",
        uselist=False
    )
```

### Insight (Extended)

**Purpose**: Add source tracking to existing insight model.

```python
# Additional fields for Insight module
class InsightSourceType(str, Enum):
    ANALYSIS = "analysis"
    TRIGGER = "trigger"
    ATO_CORRESPONDENCE = "ato_correspondence"

class Insight(Base):
    # ... existing fields ...

    # Source tracking (NEW)
    source_type: Mapped[InsightSourceType] = mapped_column(
        default=InsightSourceType.ANALYSIS
    )
    source_id: Mapped[UUID | None] = mapped_column(nullable=True)

    # Relationships
    ato_correspondence: Mapped["ATOCorrespondence"] = relationship(
        back_populates="insight",
        uselist=False
    )
```

---

## New Entities

### 1. ResponseDraft

**Purpose**: Store AI-generated response drafts for correspondence.

```python
class ResponseDraftType(str, Enum):
    AUDIT_RESPONSE = "audit_response"
    REMISSION_REQUEST = "remission_request"
    PAYMENT_PLAN_REQUEST = "payment_plan_request"
    INFORMATION_RESPONSE = "information_response"
    GENERAL_RESPONSE = "general_response"


class ResponseDraftStatus(str, Enum):
    DRAFT = "draft"
    EDITED = "edited"
    SENT = "sent"
    DISCARDED = "discarded"


class ResponseDraft(Base):
    """AI-generated response drafts for ATO correspondence."""
    __tablename__ = "response_drafts"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Multi-tenancy
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)

    # Reference to correspondence
    correspondence_id: Mapped[UUID] = mapped_column(
        ForeignKey("ato_correspondence.id"),
        index=True
    )

    # Draft details
    draft_type: Mapped[ResponseDraftType] = mapped_column()
    status: Mapped[ResponseDraftStatus] = mapped_column(default=ResponseDraftStatus.DRAFT)

    # Content
    content: Mapped[str] = mapped_column(Text)
    edited_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI metadata
    model_used: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(50))
    rag_sources: Mapped[list] = mapped_column(JSONB, default=list)

    # User actions
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    edited_by_user_id: Mapped[UUID | None] = mapped_column(nullable=True)
    edited_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    tenant: Mapped["Tenant"] = relationship()
    correspondence: Mapped["ATOCorrespondence"] = relationship(back_populates="response_drafts")
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_user_id])
```

**Indexes**:
- `tenant_id` - Multi-tenancy
- `correspondence_id` - Lookup by correspondence

---

### 2. NotificationRule

**Purpose**: Track scheduled deadline notifications for correspondence.

```python
class NotificationRuleStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"  # User already resolved


class NotificationRule(Base):
    """Scheduled notifications for correspondence deadlines."""
    __tablename__ = "ato_notification_rules"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Multi-tenancy
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)

    # Reference to correspondence
    correspondence_id: Mapped[UUID] = mapped_column(
        ForeignKey("ato_correspondence.id"),
        index=True
    )

    # Trigger configuration
    days_before_due: Mapped[int] = mapped_column()  # 7, 3, 1, 0 (overdue)
    trigger_date: Mapped[date] = mapped_column(index=True)
    channels: Mapped[list] = mapped_column(JSONB)  # ["email", "push"]

    # Status
    status: Mapped[NotificationRuleStatus] = mapped_column(
        default=NotificationRuleStatus.PENDING
    )

    # Execution
    notification_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("notifications.id"),
        nullable=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    correspondence: Mapped["ATOCorrespondence"] = relationship(
        back_populates="notification_rules"
    )
    notification: Mapped["Notification"] = relationship()
```

**Indexes**:
- `tenant_id` - Multi-tenancy
- `correspondence_id` - Lookup by correspondence
- `trigger_date` - Query for notifications due today
- `(status, trigger_date)` - Query pending notifications

---

### 3. PMIntegration

**Purpose**: Store practice management system connections per tenant.

```python
class PMProvider(str, Enum):
    KARBON = "karbon"
    XPM = "xpm"


class PMIntegration(Base):
    """Practice management system integrations."""
    __tablename__ = "pm_integrations"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Multi-tenancy
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        unique=True  # One integration per tenant (for now)
    )

    # Provider
    provider: Mapped[PMProvider] = mapped_column()

    # OAuth credentials (encrypted)
    access_token_encrypted: Mapped[str] = mapped_column(Text)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Configuration
    sync_enabled: Mapped[bool] = mapped_column(default=True)
    default_assignee: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Status
    last_sync_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_count: Mapped[int] = mapped_column(default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship()
    sync_records: Mapped[list["PMSyncRecord"]] = relationship(back_populates="integration")
```

---

### 4. PMSyncRecord

**Purpose**: Track individual sync operations to practice management.

```python
class SyncStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class PMSyncRecord(Base):
    """Individual sync records to practice management."""
    __tablename__ = "pm_sync_records"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Multi-tenancy
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)

    # References
    integration_id: Mapped[UUID] = mapped_column(
        ForeignKey("pm_integrations.id"),
        index=True
    )
    correspondence_id: Mapped[UUID] = mapped_column(
        ForeignKey("ato_correspondence.id"),
        index=True
    )
    task_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tasks.id"),
        nullable=True
    )

    # Sync details
    sync_type: Mapped[str] = mapped_column(String(50))  # "create_task", "update_task", "complete_task"
    status: Mapped[SyncStatus] = mapped_column(default=SyncStatus.PENDING)

    # External reference
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Result
    request_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Retry tracking
    attempt_count: Mapped[int] = mapped_column(default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    synced_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    integration: Mapped["PMIntegration"] = relationship(back_populates="sync_records")
    correspondence: Mapped["ATOCorrespondence"] = relationship(back_populates="pm_sync_records")
    task: Mapped["Task"] = relationship()
```

**Indexes**:
- `tenant_id` - Multi-tenancy
- `integration_id` - Lookup by integration
- `correspondence_id` - Lookup by correspondence
- `(status, next_retry_at)` - Query for retryable syncs

---

## Database Migrations

### Migration: Add ATOtrack Workflow Tables

```python
# alembic/versions/xxx_add_atotrack_workflow.py

def upgrade():
    # Add columns to ato_correspondence
    op.add_column(
        'ato_correspondence',
        sa.Column('task_id', sa.UUID(), sa.ForeignKey('tasks.id'), nullable=True)
    )
    op.add_column(
        'ato_correspondence',
        sa.Column('insight_id', sa.UUID(), sa.ForeignKey('insights.id'), nullable=True)
    )
    op.add_column(
        'ato_correspondence',
        sa.Column('workflow_processed', sa.Boolean(), default=False)
    )
    op.add_column(
        'ato_correspondence',
        sa.Column('workflow_processed_at', sa.DateTime(), nullable=True)
    )
    op.create_index('ix_ato_correspondence_task_id', 'ato_correspondence', ['task_id'])
    op.create_index('ix_ato_correspondence_insight_id', 'ato_correspondence', ['insight_id'])

    # Add source columns to tasks
    op.add_column(
        'tasks',
        sa.Column('source_type', sa.String(50), default='manual')
    )
    op.add_column(
        'tasks',
        sa.Column('source_id', sa.UUID(), nullable=True)
    )

    # Add source columns to insights
    op.add_column(
        'insights',
        sa.Column('source_type', sa.String(50), default='analysis')
    )
    op.add_column(
        'insights',
        sa.Column('source_id', sa.UUID(), nullable=True)
    )

    # Create response_drafts table
    op.create_table(
        'response_drafts',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('correspondence_id', sa.UUID(), sa.ForeignKey('ato_correspondence.id'), nullable=False),
        sa.Column('draft_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), default='draft'),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('edited_content', sa.Text(), nullable=True),
        sa.Column('model_used', sa.String(100), nullable=False),
        sa.Column('prompt_version', sa.String(50), nullable=False),
        sa.Column('rag_sources', sa.JSON(), default=[]),
        sa.Column('created_by_user_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('edited_by_user_id', sa.UUID(), nullable=True),
        sa.Column('edited_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
    )
    op.create_index('ix_response_drafts_tenant_id', 'response_drafts', ['tenant_id'])
    op.create_index('ix_response_drafts_correspondence_id', 'response_drafts', ['correspondence_id'])

    # Create ato_notification_rules table
    op.create_table(
        'ato_notification_rules',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('correspondence_id', sa.UUID(), sa.ForeignKey('ato_correspondence.id'), nullable=False),
        sa.Column('days_before_due', sa.Integer(), nullable=False),
        sa.Column('trigger_date', sa.Date(), nullable=False),
        sa.Column('channels', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('notification_id', sa.UUID(), sa.ForeignKey('notifications.id'), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
    )
    op.create_index('ix_ato_notification_rules_tenant_id', 'ato_notification_rules', ['tenant_id'])
    op.create_index('ix_ato_notification_rules_trigger_date', 'ato_notification_rules', ['trigger_date'])

    # Create pm_integrations table
    op.create_table(
        'pm_integrations',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id'), unique=True, nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('access_token_encrypted', sa.Text(), nullable=False),
        sa.Column('refresh_token_encrypted', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(), nullable=True),
        sa.Column('sync_enabled', sa.Boolean(), default=True),
        sa.Column('default_assignee', sa.String(255), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('last_sync_status', sa.String(50), nullable=True),
        sa.Column('error_count', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now()),
    )

    # Create pm_sync_records table
    op.create_table(
        'pm_sync_records',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('integration_id', sa.UUID(), sa.ForeignKey('pm_integrations.id'), nullable=False),
        sa.Column('correspondence_id', sa.UUID(), sa.ForeignKey('ato_correspondence.id'), nullable=False),
        sa.Column('task_id', sa.UUID(), sa.ForeignKey('tasks.id'), nullable=True),
        sa.Column('sync_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('external_id', sa.String(255), nullable=True),
        sa.Column('external_url', sa.String(500), nullable=True),
        sa.Column('request_payload', sa.JSON(), nullable=True),
        sa.Column('response_payload', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('attempt_count', sa.Integer(), default=0),
        sa.Column('next_retry_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('synced_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_pm_sync_records_tenant_id', 'pm_sync_records', ['tenant_id'])
    op.create_index('ix_pm_sync_records_status', 'pm_sync_records', ['status'])

    # Enable RLS
    op.execute("ALTER TABLE response_drafts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ato_notification_rules ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE pm_integrations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE pm_sync_records ENABLE ROW LEVEL SECURITY")


def downgrade():
    op.drop_table('pm_sync_records')
    op.drop_table('pm_integrations')
    op.drop_table('ato_notification_rules')
    op.drop_table('response_drafts')

    op.drop_column('insights', 'source_id')
    op.drop_column('insights', 'source_type')
    op.drop_column('tasks', 'source_id')
    op.drop_column('tasks', 'source_type')

    op.drop_column('ato_correspondence', 'workflow_processed_at')
    op.drop_column('ato_correspondence', 'workflow_processed')
    op.drop_column('ato_correspondence', 'insight_id')
    op.drop_column('ato_correspondence', 'task_id')
```

---

## Data Validation Rules

### ResponseDraft

| Field | Validation |
|-------|------------|
| `draft_type` | Must be valid enum value |
| `content` | Required, non-empty |
| `model_used` | Required, max 100 chars |

### NotificationRule

| Field | Validation |
|-------|------------|
| `days_before_due` | Must be 0, 1, 3, or 7 |
| `trigger_date` | Must be valid date |
| `channels` | Must contain only "email" and/or "push" |

### PMIntegration

| Field | Validation |
|-------|------------|
| `provider` | Must be "karbon" or "xpm" |
| `access_token_encrypted` | Required, encrypted |

### Business Rules

1. **One task per correspondence**: `task_id` must be unique across correspondence
2. **One insight per correspondence**: `insight_id` must be unique across correspondence
3. **Cancel notifications on resolve**: When correspondence resolved, cancel pending notifications
4. **Complete task on resolve**: When correspondence resolved, complete linked task
5. **Retry limit for PM sync**: Max 3 attempts, then mark failed
