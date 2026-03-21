# Data Model: Usage Tracking & Limits

**Date**: 2025-12-31
**Feature**: 020-usage-tracking

---

## Entity Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              TENANT                                      │
│  (Extended from Spec 019)                                               │
├─────────────────────────────────────────────────────────────────────────┤
│  + ai_queries_month: int        # AI queries this billing period        │
│  + documents_month: int         # Documents processed this period       │
│  + usage_month_reset: date      # When monthly counters were reset      │
└─────────────────────────────────────────────────────────────────────────┘
         │ 1
         │
         │ ∞
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         USAGE_SNAPSHOT                                   │
│  Point-in-time record of tenant usage metrics                           │
├─────────────────────────────────────────────────────────────────────────┤
│  id: UUID (PK)                                                          │
│  tenant_id: UUID (FK → tenants.id)                                      │
│  captured_at: timestamp                                                  │
│  client_count: int                                                       │
│  ai_queries_count: int                                                   │
│  documents_count: int                                                    │
│  tier: varchar(20)                                                       │
│  client_limit: int | null                                               │
│  created_at: timestamp                                                   │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                          USAGE_ALERT                                     │
│  Record of alerts sent to prevent duplicates                            │
├─────────────────────────────────────────────────────────────────────────┤
│  id: UUID (PK)                                                          │
│  tenant_id: UUID (FK → tenants.id)                                      │
│  alert_type: varchar(20)            # 'threshold_80', 'threshold_90'    │
│  billing_period: varchar(7)         # 'YYYY-MM'                         │
│  threshold_percentage: int          # 80 or 90                          │
│  client_count_at_alert: int         # Count when alert triggered        │
│  client_limit_at_alert: int         # Limit when alert triggered        │
│  recipient_email: varchar(255)                                          │
│  sent_at: timestamp                                                      │
│  created_at: timestamp                                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Entity Details

### 1. Tenant (Extension)

**New columns added to existing `tenants` table**:

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `ai_queries_month` | INTEGER | NO | 0 | AI chat completions this billing period |
| `documents_month` | INTEGER | NO | 0 | Documents processed this billing period |
| `usage_month_reset` | DATE | YES | NULL | Date when monthly counters were last reset |

**Validation Rules**:
- `ai_queries_month` >= 0
- `documents_month` >= 0

**Notes**:
- Existing `client_count` field continues to be used
- Monthly counters reset on 1st of each month via background job

---

### 2. UsageSnapshot

**Purpose**: Historical record of usage for trend analysis and reporting.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | uuid_generate_v4() | Primary key |
| `tenant_id` | UUID | NO | - | Foreign key to tenants |
| `captured_at` | TIMESTAMPTZ | NO | NOW() | When snapshot was taken |
| `client_count` | INTEGER | NO | - | Number of active clients |
| `ai_queries_count` | INTEGER | NO | - | AI queries in period |
| `documents_count` | INTEGER | NO | - | Documents processed in period |
| `tier` | VARCHAR(20) | NO | - | Tier at time of snapshot |
| `client_limit` | INTEGER | YES | - | Client limit (null = unlimited) |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Record creation time |

**Indexes**:
- `idx_usage_snapshots_tenant_id` on `tenant_id`
- `idx_usage_snapshots_captured_at` on `captured_at`
- `idx_usage_snapshots_tenant_period` on `(tenant_id, captured_at)` - composite for queries

**Constraints**:
- FK: `tenant_id` REFERENCES `tenants(id)` ON DELETE CASCADE
- CHECK: `client_count >= 0`
- CHECK: `ai_queries_count >= 0`
- CHECK: `documents_count >= 0`

---

### 3. UsageAlert

**Purpose**: Track sent alerts to prevent duplicate notifications.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | uuid_generate_v4() | Primary key |
| `tenant_id` | UUID | NO | - | Foreign key to tenants |
| `alert_type` | VARCHAR(20) | NO | - | 'threshold_80', 'threshold_90', 'limit_reached' |
| `billing_period` | VARCHAR(7) | NO | - | Format: 'YYYY-MM' |
| `threshold_percentage` | INTEGER | NO | - | 80, 90, or 100 |
| `client_count_at_alert` | INTEGER | NO | - | Count when triggered |
| `client_limit_at_alert` | INTEGER | NO | - | Limit when triggered |
| `recipient_email` | VARCHAR(255) | NO | - | Email address notified |
| `sent_at` | TIMESTAMPTZ | NO | NOW() | When email was sent |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Record creation time |

**Indexes**:
- `idx_usage_alerts_tenant_id` on `tenant_id`
- `idx_usage_alerts_dedup` on `(tenant_id, alert_type, billing_period)` - for deduplication queries
- UNIQUE: `(tenant_id, alert_type, billing_period)` - enforce one alert per type per period

**Constraints**:
- FK: `tenant_id` REFERENCES `tenants(id)` ON DELETE CASCADE
- CHECK: `alert_type IN ('threshold_80', 'threshold_90', 'limit_reached')`
- CHECK: `threshold_percentage IN (80, 90, 100)`
- UNIQUE: `(tenant_id, alert_type, billing_period)`

---

## Migration Script

```sql
-- Migration: 025_usage_tracking

-- 1. Extend tenants table
ALTER TABLE tenants
ADD COLUMN ai_queries_month INTEGER NOT NULL DEFAULT 0,
ADD COLUMN documents_month INTEGER NOT NULL DEFAULT 0,
ADD COLUMN usage_month_reset DATE;

-- 2. Create usage_snapshots table
CREATE TABLE usage_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    client_count INTEGER NOT NULL CHECK (client_count >= 0),
    ai_queries_count INTEGER NOT NULL CHECK (ai_queries_count >= 0),
    documents_count INTEGER NOT NULL CHECK (documents_count >= 0),
    tier VARCHAR(20) NOT NULL,
    client_limit INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_usage_snapshots_tenant_id ON usage_snapshots(tenant_id);
CREATE INDEX idx_usage_snapshots_captured_at ON usage_snapshots(captured_at);
CREATE INDEX idx_usage_snapshots_tenant_period ON usage_snapshots(tenant_id, captured_at);

-- 3. Create usage_alerts table
CREATE TABLE usage_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    alert_type VARCHAR(20) NOT NULL CHECK (alert_type IN ('threshold_80', 'threshold_90', 'limit_reached')),
    billing_period VARCHAR(7) NOT NULL,
    threshold_percentage INTEGER NOT NULL CHECK (threshold_percentage IN (80, 90, 100)),
    client_count_at_alert INTEGER NOT NULL,
    client_limit_at_alert INTEGER NOT NULL,
    recipient_email VARCHAR(255) NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (tenant_id, alert_type, billing_period)
);

CREATE INDEX idx_usage_alerts_tenant_id ON usage_alerts(tenant_id);
CREATE INDEX idx_usage_alerts_dedup ON usage_alerts(tenant_id, alert_type, billing_period);
```

---

## SQLAlchemy Models

### UsageSnapshot Model

```python
class UsageSnapshot(Base, TimestampMixin):
    """Point-in-time usage snapshot for historical tracking."""

    __tablename__ = "usage_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    client_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_queries_count: Mapped[int] = mapped_column(Integer, nullable=False)
    documents_count: Mapped[int] = mapped_column(Integer, nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    client_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="usage_snapshots")
```

### UsageAlert Model

```python
class UsageAlertType(str, enum.Enum):
    """Types of usage alerts."""
    THRESHOLD_80 = "threshold_80"
    THRESHOLD_90 = "threshold_90"
    LIMIT_REACHED = "limit_reached"


class UsageAlert(Base, TimestampMixin):
    """Record of usage alerts sent to tenants."""

    __tablename__ = "usage_alerts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "alert_type", "billing_period", name="uq_usage_alert_dedup"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    alert_type: Mapped[UsageAlertType] = mapped_column(Enum(UsageAlertType), nullable=False)
    billing_period: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    threshold_percentage: Mapped[int] = mapped_column(Integer, nullable=False)
    client_count_at_alert: Mapped[int] = mapped_column(Integer, nullable=False)
    client_limit_at_alert: Mapped[int] = mapped_column(Integer, nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="usage_alerts")
```

---

## Pydantic Schemas

```python
class UsageMetrics(BaseModel):
    """Extended usage metrics including all tracked metrics."""
    client_count: int
    client_limit: int | None
    client_percentage: float | None
    ai_queries_month: int
    documents_month: int
    is_at_limit: bool
    is_approaching_limit: bool
    threshold_warning: str | None  # "80%" or "90%" if applicable


class UsageSnapshotResponse(BaseModel):
    """Usage snapshot for API response."""
    id: UUID
    captured_at: datetime
    client_count: int
    ai_queries_count: int
    documents_count: int
    tier: str
    client_limit: int | None


class UsageHistoryResponse(BaseModel):
    """Historical usage data for charting."""
    snapshots: list[UsageSnapshotResponse]
    period_start: datetime
    period_end: datetime


class UsageAlertResponse(BaseModel):
    """Usage alert record for API response."""
    id: UUID
    alert_type: str
    billing_period: str
    threshold_percentage: int
    sent_at: datetime


class AdminUsageStats(BaseModel):
    """Aggregate usage statistics for admin dashboard."""
    total_tenants: int
    total_clients: int
    average_clients_per_tenant: float
    tenants_at_limit: int
    tenants_approaching_limit: int
    tenants_by_tier: dict[str, int]


class UpsellOpportunity(BaseModel):
    """Tenant approaching limit - potential upsell."""
    tenant_id: UUID
    tenant_name: str
    owner_email: str
    current_tier: str
    client_count: int
    client_limit: int
    percentage_used: float
```

---

## Relationships Summary

| From | To | Relationship | Description |
|------|----|--------------|-------------|
| UsageSnapshot | Tenant | Many-to-One | Each snapshot belongs to one tenant |
| UsageAlert | Tenant | Many-to-One | Each alert belongs to one tenant |
| Tenant | UsageSnapshot | One-to-Many | Tenant has many snapshots |
| Tenant | UsageAlert | One-to-Many | Tenant has many alerts |
