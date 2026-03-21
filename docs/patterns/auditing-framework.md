# Pattern: Auditing Framework

**Pattern Type:** Cross-Cutting Concern
**Status:** Reference Implementation
**Created:** 2025-12-28
**Last Updated:** 2025-12-28

---

> **Note:** This document serves as a **reference pattern** for implementing auditing across Clairo.
> For the authoritative auditing requirements, see:
> - Constitution Section X: "Auditing & Compliance (NON-NEGOTIABLE - FIRST-CLASS CONCERN)"
> - Architecture Document Section 14.4: "Auditing Framework"

---

## 1. Executive Summary

This pattern defines the auditing framework for Clairo - a comprehensive, immutable audit trail system designed to meet ATO compliance requirements and build user confidence. Given the sensitive nature of BAS lodgments and tax advisory services, auditing is a first-class architectural concern that must be baked into every layer of the platform.

### 1.1 Why Auditing is Critical

1. **ATO Compliance**: The ATO requires businesses to keep records for 5 years (7 years for some records). Clairo must demonstrate complete traceability of all data and calculations.

2. **Professional Liability**: Accountants need defensible records showing exactly what data was available and what advice was generated at any point in time.

3. **User Trust**: Clients and accountants must have confidence that the platform maintains integrity and can prove its actions.

4. **Dispute Resolution**: When discrepancies arise with the ATO, detailed audit trails are essential for investigation and resolution.

---

## 2. Audit Requirements

### 2.1 ATO Record-Keeping Requirements

| Record Type | Retention Period | Source |
|-------------|------------------|--------|
| BAS lodgment records | 5 years | Taxation Administration Act 1953 |
| GST records | 5 years | GST Act 1999 |
| PAYG records | 5 years | PAYG legislation |
| Capital gains records | 5 years after CGT event | Income Tax Assessment Act |
| Depreciation records | Life of asset + 5 years | ATO guidelines |
| Superannuation records | 5 years | SIS regulations |

### 2.2 Audit Event Categories

#### 2.2.1 Authentication & Access Events
- User login/logout (success and failure)
- Password changes and resets
- MFA enrollment and verification
- Session management (creation, expiry, revocation)
- API key creation and usage
- OAuth token grants and revocations

#### 2.2.2 Data Access Events
- Financial data views (who viewed what, when)
- Report generation and downloads
- Data exports
- Search queries on sensitive data
- API data retrievals

#### 2.2.3 Data Modification Events
- All CRUD operations on financial entities
- BAS calculation changes
- Manual adjustments with justifications
- Bulk data imports
- Data corrections and amendments

#### 2.2.4 Integration Events
- Xero/MYOB sync operations (start, complete, errors)
- Data mapping changes
- API connection establishment
- Third-party data retrievals
- Webhook receipts

#### 2.2.5 Compliance Events
- BAS preparation milestones
- BAS lodgment submissions
- ATO portal interactions
- Compliance check results
- Amendment lodgments

#### 2.2.6 Administrative Events
- User provisioning and deprovisioning
- Role and permission changes
- Tenant configuration changes
- System configuration changes
- Feature flag modifications

---

## 3. Technical Architecture

### 3.1 Audit Log Schema

```sql
CREATE TABLE audit_logs (
    -- Immutable identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL UNIQUE,  -- Idempotency key

    -- Temporal data (immutable once written)
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Actor identification
    actor_type VARCHAR(50) NOT NULL,  -- 'user', 'system', 'api_key', 'integration'
    actor_id UUID,
    actor_email VARCHAR(255),
    actor_ip_address INET,
    actor_user_agent TEXT,

    -- Multi-tenancy
    tenant_id UUID NOT NULL,

    -- Event classification
    event_category VARCHAR(50) NOT NULL,  -- auth, data_access, data_modify, etc.
    event_type VARCHAR(100) NOT NULL,     -- specific event name
    event_severity VARCHAR(20) NOT NULL DEFAULT 'info',  -- debug, info, warning, error, critical

    -- Resource identification
    resource_type VARCHAR(100),
    resource_id UUID,
    resource_name VARCHAR(255),

    -- Event data
    action VARCHAR(50) NOT NULL,  -- create, read, update, delete, execute
    outcome VARCHAR(20) NOT NULL, -- success, failure, partial

    -- Detailed payload (JSONB for flexibility)
    old_values JSONB,  -- Previous state for modifications
    new_values JSONB,  -- New state for modifications
    metadata JSONB,    -- Additional context

    -- Integrity verification
    checksum VARCHAR(64) NOT NULL,  -- SHA-256 of event data
    previous_checksum VARCHAR(64),  -- Chain to previous event (blockchain-style)

    -- Indexing support
    search_vector TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('english',
            COALESCE(event_type, '') || ' ' ||
            COALESCE(resource_name, '') || ' ' ||
            COALESCE(actor_email, '')
        )
    ) STORED
);

-- Indexes for common query patterns
CREATE INDEX idx_audit_tenant_time ON audit_logs (tenant_id, occurred_at DESC);
CREATE INDEX idx_audit_actor ON audit_logs (actor_id, occurred_at DESC);
CREATE INDEX idx_audit_resource ON audit_logs (resource_type, resource_id, occurred_at DESC);
CREATE INDEX idx_audit_category ON audit_logs (event_category, occurred_at DESC);
CREATE INDEX idx_audit_search ON audit_logs USING GIN (search_vector);

-- Prevent modifications (append-only)
CREATE RULE audit_logs_no_update AS ON UPDATE TO audit_logs DO INSTEAD NOTHING;
CREATE RULE audit_logs_no_delete AS ON DELETE TO audit_logs DO INSTEAD NOTHING;
```

### 3.2 Audit Chain Integrity

Each audit event is cryptographically linked to its predecessor, creating a tamper-evident chain:

```python
from hashlib import sha256
import json

def calculate_event_checksum(event: AuditEvent, previous_checksum: str | None) -> str:
    """Calculate SHA-256 checksum for audit event integrity."""
    data = {
        "event_id": str(event.event_id),
        "occurred_at": event.occurred_at.isoformat(),
        "tenant_id": str(event.tenant_id),
        "actor_id": str(event.actor_id) if event.actor_id else None,
        "event_type": event.event_type,
        "resource_type": event.resource_type,
        "resource_id": str(event.resource_id) if event.resource_id else None,
        "action": event.action,
        "outcome": event.outcome,
        "old_values": event.old_values,
        "new_values": event.new_values,
        "previous_checksum": previous_checksum,
    }
    canonical = json.dumps(data, sort_keys=True, default=str)
    return sha256(canonical.encode()).hexdigest()
```

### 3.3 Audit Service Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Application Layer                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────────┐│
│  │ API      │ │ Services │ │ Tasks    │ │ Integrations         ││
│  │ Endpoints│ │          │ │ (Celery) │ │ (Xero/MYOB)          ││
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────────┬───────────┘│
│       │            │            │                   │            │
│       └────────────┴────────────┴───────────────────┘            │
│                              │                                    │
│                    ┌─────────▼─────────┐                         │
│                    │   Audit Context   │  ← Request-scoped       │
│                    │   (contextvars)   │    actor/tenant info    │
│                    └─────────┬─────────┘                         │
└──────────────────────────────┼───────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   AuditService      │
                    │   - log_event()     │
                    │   - query_logs()    │
                    │   - verify_chain()  │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼─────┐ ┌───────▼───────┐ ┌─────▼─────┐
    │ PostgreSQL    │ │ Event Bus     │ │ Async     │
    │ (Primary)     │ │ (Real-time)   │ │ Archive   │
    │               │ │               │ │ (S3/MinIO)│
    └───────────────┘ └───────────────┘ └───────────┘
```

### 3.4 Audit Context Management

```python
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

@dataclass
class AuditContext:
    """Request-scoped audit context."""
    tenant_id: UUID
    actor_type: str  # 'user', 'system', 'api_key', 'integration'
    actor_id: UUID | None
    actor_email: str | None
    ip_address: str | None
    user_agent: str | None
    request_id: str | None
    correlation_id: str | None  # For tracing across services

# Context variable for current request
_audit_context: ContextVar[AuditContext | None] = ContextVar('audit_context', default=None)

def get_audit_context() -> AuditContext:
    """Get current audit context or raise error."""
    ctx = _audit_context.get()
    if ctx is None:
        raise RuntimeError("Audit context not initialized")
    return ctx

def set_audit_context(context: AuditContext) -> None:
    """Set audit context for current request."""
    _audit_context.set(context)
```

---

## 4. Implementation Patterns

### 4.1 Decorator-Based Auditing

```python
from functools import wraps
from typing import Callable, TypeVar, ParamSpec

P = ParamSpec('P')
R = TypeVar('R')

def audited(
    event_type: str,
    resource_type: str | None = None,
    capture_result: bool = False,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to automatically audit function calls."""
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            context = get_audit_context()

            # Capture "before" state if applicable
            old_values = await _capture_before_state(args, kwargs, resource_type)

            try:
                result = await func(*args, **kwargs)

                await audit_service.log_event(
                    event_type=event_type,
                    resource_type=resource_type,
                    action=_infer_action(event_type),
                    outcome="success",
                    old_values=old_values,
                    new_values=result if capture_result else None,
                )

                return result

            except Exception as e:
                await audit_service.log_event(
                    event_type=event_type,
                    resource_type=resource_type,
                    action=_infer_action(event_type),
                    outcome="failure",
                    old_values=old_values,
                    metadata={"error": str(e), "error_type": type(e).__name__},
                )
                raise

        return wrapper
    return decorator

# Usage example
class BASService:
    @audited("bas.calculation.updated", resource_type="bas_period", capture_result=True)
    async def update_bas_calculation(
        self,
        period_id: UUID,
        adjustments: dict
    ) -> BASCalculation:
        # Business logic here
        ...
```

### 4.2 Model-Level Auditing (SQLAlchemy Events)

```python
from sqlalchemy import event
from sqlalchemy.orm import Session

class AuditableMixin:
    """Mixin for models that require automatic audit logging."""

    __audit_enabled__ = True
    __audit_fields__: set[str] = set()  # Empty = all fields
    __audit_exclude__: set[str] = {"updated_at"}  # Fields to exclude

@event.listens_for(Session, "before_flush")
def audit_changes(session: Session, flush_context, instances):
    """Capture all changes for auditing before flush."""
    for obj in session.new:
        if hasattr(obj, '__audit_enabled__') and obj.__audit_enabled__:
            _queue_audit_event(obj, "create", old_values=None, new_values=_get_values(obj))

    for obj in session.dirty:
        if hasattr(obj, '__audit_enabled__') and obj.__audit_enabled__:
            old = _get_history(obj)
            new = _get_values(obj)
            if old != new:  # Only audit if actually changed
                _queue_audit_event(obj, "update", old_values=old, new_values=new)

    for obj in session.deleted:
        if hasattr(obj, '__audit_enabled__') and obj.__audit_enabled__:
            _queue_audit_event(obj, "delete", old_values=_get_values(obj), new_values=None)
```

### 4.3 Sensitive Data Handling

```python
from enum import Enum

class SensitivityLevel(Enum):
    PUBLIC = "public"           # Can be logged in full
    INTERNAL = "internal"       # Logged but not exported
    CONFIDENTIAL = "confidential"  # Masked in logs
    RESTRICTED = "restricted"   # Only presence logged, no values

FIELD_SENSITIVITY = {
    "tax_file_number": SensitivityLevel.RESTRICTED,
    "bank_account_number": SensitivityLevel.CONFIDENTIAL,
    "email": SensitivityLevel.INTERNAL,
    "business_name": SensitivityLevel.PUBLIC,
}

def mask_sensitive_data(data: dict, context: str = "log") -> dict:
    """Mask sensitive fields based on context and sensitivity level."""
    masked = {}
    for key, value in data.items():
        sensitivity = FIELD_SENSITIVITY.get(key, SensitivityLevel.INTERNAL)

        if sensitivity == SensitivityLevel.RESTRICTED:
            masked[key] = "[RESTRICTED]"
        elif sensitivity == SensitivityLevel.CONFIDENTIAL:
            masked[key] = _partial_mask(value)
        else:
            masked[key] = value

    return masked

def _partial_mask(value: str) -> str:
    """Show first and last 2 characters only."""
    if not value or len(value) < 6:
        return "****"
    return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"
```

---

## 5. Query & Reporting

### 5.1 Audit Query API

```python
@dataclass
class AuditQuery:
    """Query parameters for audit log search."""
    tenant_id: UUID

    # Time range (required for performance)
    from_date: datetime
    to_date: datetime

    # Filters
    actor_id: UUID | None = None
    event_categories: list[str] | None = None
    event_types: list[str] | None = None
    resource_type: str | None = None
    resource_id: UUID | None = None
    outcome: str | None = None
    severity: list[str] | None = None

    # Full-text search
    search_text: str | None = None

    # Pagination
    limit: int = 100
    offset: int = 0

    # Sorting
    order_by: str = "occurred_at"
    order_direction: str = "desc"

class AuditQueryService:
    async def search(self, query: AuditQuery) -> AuditSearchResult:
        """Search audit logs with filters."""
        ...

    async def get_activity_summary(
        self,
        tenant_id: UUID,
        from_date: datetime,
        to_date: datetime
    ) -> ActivitySummary:
        """Get aggregated activity summary."""
        ...

    async def get_resource_history(
        self,
        tenant_id: UUID,
        resource_type: str,
        resource_id: UUID
    ) -> list[AuditEvent]:
        """Get complete history for a resource."""
        ...

    async def export_for_compliance(
        self,
        tenant_id: UUID,
        from_date: datetime,
        to_date: datetime,
        format: str = "csv"
    ) -> bytes:
        """Export audit logs for ATO compliance."""
        ...
```

### 5.2 Pre-built Compliance Reports

| Report | Purpose | Frequency |
|--------|---------|-----------|
| User Access Report | Who accessed what data | Monthly |
| Data Modification Report | All changes to financial data | As needed |
| BAS Activity Report | All BAS-related actions | Per BAS period |
| Integration Sync Report | Xero/MYOB sync history | Weekly |
| Security Events Report | Auth failures, permission changes | Daily |
| Chain Integrity Report | Verify audit log integrity | Weekly |

---

## 6. Retention & Archival

### 6.1 Retention Policy

```python
RETENTION_POLICIES = {
    "auth": {
        "hot_storage_days": 90,      # PostgreSQL
        "warm_storage_days": 365,     # Compressed in PostgreSQL
        "cold_storage_years": 7,      # S3/MinIO archive
    },
    "data_access": {
        "hot_storage_days": 30,
        "warm_storage_days": 180,
        "cold_storage_years": 5,
    },
    "data_modify": {
        "hot_storage_days": 365,
        "warm_storage_days": 365 * 2,
        "cold_storage_years": 7,
    },
    "compliance": {
        "hot_storage_days": 365 * 2,
        "warm_storage_days": 365 * 5,
        "cold_storage_years": 10,     # Extra retention for compliance
    },
}
```

### 6.2 Archival Process

```python
class AuditArchivalService:
    async def archive_old_events(self):
        """Move old events to cold storage (daily job)."""
        for category, policy in RETENTION_POLICIES.items():
            # Move from PostgreSQL to compressed archive
            cutoff = datetime.now() - timedelta(days=policy["hot_storage_days"])

            events = await self._get_events_before(category, cutoff)

            if events:
                # Write to MinIO/S3 in Parquet format
                archive_path = self._generate_archive_path(category, cutoff)
                await self._write_parquet(events, archive_path)

                # Verify archive integrity
                await self._verify_archive(archive_path, events)

                # Only delete after successful archive
                await self._delete_archived_events(events)

    async def restore_from_archive(
        self,
        tenant_id: UUID,
        from_date: datetime,
        to_date: datetime
    ) -> list[AuditEvent]:
        """Restore archived events for compliance queries."""
        ...
```

---

## 7. Integration with Existing Architecture

### 7.1 Middleware Integration

```python
from starlette.middleware.base import BaseHTTPMiddleware

class AuditMiddleware(BaseHTTPMiddleware):
    """Initialize audit context for each request."""

    async def dispatch(self, request: Request, call_next):
        # Extract actor information
        user = getattr(request.state, "user", None)

        context = AuditContext(
            tenant_id=_get_tenant_id(request),
            actor_type="user" if user else "anonymous",
            actor_id=user.sub if user else None,
            actor_email=user.email if user else None,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            request_id=request.headers.get("x-request-id", str(uuid4())),
            correlation_id=request.headers.get("x-correlation-id"),
        )

        set_audit_context(context)

        try:
            response = await call_next(request)
            return response
        finally:
            # Log request completion
            await audit_service.log_event(
                event_type="http.request.completed",
                metadata={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                }
            )
```

### 7.2 Event Bus Integration

```python
from app.core.events import event_bus, DomainEvent

# Subscribe audit service to all domain events
@event_bus.subscribe("*")  # Wildcard subscription
async def audit_domain_event(event: DomainEvent):
    """Automatically audit all domain events."""
    await audit_service.log_event(
        event_type=f"domain.{event.event_type}",
        event_category="domain_event",
        resource_type=event.aggregate_type,
        resource_id=UUID(event.aggregate_id) if event.aggregate_id else None,
        action="execute",
        outcome="success",
        new_values=event.payload,
    )
```

---

## 8. Security Considerations

### 8.1 Access Control for Audit Logs

- **Read Access**: Only users with `audit:read` permission
- **Export Access**: Only users with `audit:export` permission
- **No Write Access**: Audit logs are append-only via system
- **No Delete Access**: Cannot be deleted (except by retention policy)

### 8.2 Integrity Protection

1. **Checksum Chain**: Each event linked to previous
2. **Database Rules**: PostgreSQL rules prevent UPDATE/DELETE
3. **Regular Verification**: Weekly integrity checks
4. **Immutable Archives**: Write-once storage for cold archives

### 8.3 Privacy Compliance

- Sensitive data masked in logs
- TFN and bank details never stored in plain text
- GDPR/Privacy Act compliant data handling
- Audit of audit log access (meta-auditing)

---

## 9. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Audit coverage | 100% of critical events | Event type checklist |
| Chain integrity | 100% valid | Weekly verification job |
| Query latency (hot) | < 500ms p95 | Application metrics |
| Query latency (warm) | < 5s p95 | Application metrics |
| Archive restore time | < 1 hour | Tested quarterly |
| Retention compliance | 100% | Automated policy checks |

---

## 10. Implementation Phases

### Phase 1: Core Infrastructure
- Audit log table and indexes
- AuditService with basic logging
- Audit context middleware
- Basic query API

### Phase 2: Automatic Auditing
- Decorator-based auditing
- Model-level change tracking
- Event bus integration
- Sensitive data masking

### Phase 3: Compliance Features
- Compliance reports
- Export functionality
- Chain integrity verification
- Archival process

### Phase 4: Advanced Features
- Real-time audit streaming
- Anomaly detection
- Advanced search
- Dashboard visualizations
