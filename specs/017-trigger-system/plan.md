# Implementation Plan: Trigger System

**Branch**: `feature/017-trigger-system` | **Date**: 2025-12-31 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/017-trigger-system/spec.md`

## Summary

Implement an event/time-based trigger system that proactively generates insights without manual intervention. The system supports three trigger types: data-change triggers (threshold crossings), time-based triggers (scheduled runs), and event-based triggers (business events). Built on the existing Celery infrastructure with PostgreSQL for trigger configuration and execution tracking.

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: FastAPI, Celery, SQLAlchemy 2.0, Redis
**Storage**: PostgreSQL (trigger configs, execution history)
**Testing**: pytest with pytest-asyncio
**Target Platform**: Linux server (Docker)
**Project Type**: Web application (backend focus, minimal frontend)
**Performance Goals**: Triggers fire within 30 seconds of event, <1% failure rate
**Constraints**: Must integrate with existing insight generation pipeline
**Scale/Scope**: ~100 clients per tenant, ~10 triggers per tenant

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Modular Monolith | ✅ Pass | New `triggers` module under `app/modules/` |
| Repository Pattern | ✅ Pass | TriggerRepository for DB access |
| Multi-Tenancy | ✅ Pass | All triggers tenant-scoped |
| Testing Strategy | ✅ Pass | Unit + integration tests for trigger logic |
| Audit Logging | ✅ Pass | All trigger executions logged |
| Code Quality | ✅ Pass | Type hints, Pydantic schemas |

## Project Structure

### Documentation (this feature)

```text
specs/017-trigger-system/
├── spec.md              # User stories and requirements
├── plan.md              # This file
└── tasks.md             # Implementation tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── modules/
│   │   └── triggers/                    # NEW MODULE
│   │       ├── __init__.py
│   │       ├── models.py                # Trigger, TriggerExecution models
│   │       ├── schemas.py               # Pydantic schemas
│   │       ├── service.py               # TriggerService
│   │       ├── router.py                # API endpoints
│   │       ├── evaluators/              # Trigger condition evaluators
│   │       │   ├── __init__.py
│   │       │   ├── base.py              # Base evaluator interface
│   │       │   ├── data_triggers.py     # Threshold-based evaluators
│   │       │   ├── time_triggers.py     # Schedule-based evaluators
│   │       │   └── event_triggers.py    # Event-based evaluators
│   │       └── executor.py              # Trigger execution engine
│   │
│   └── tasks/
│       └── trigger_tasks.py             # Celery tasks for triggers
│
├── alembic/
│   └── versions/
│       └── 021_triggers.py              # Migration for trigger tables
│
└── tests/
    ├── unit/
    │   └── modules/
    │       └── triggers/
    │           ├── test_service.py
    │           └── test_evaluators.py
    └── integration/
        └── api/
            └── test_triggers.py
```

## Architecture Design

### Trigger Types

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TRIGGER SYSTEM                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  DATA TRIGGERS              TIME TRIGGERS          EVENT TRIGGERS   │
│  ─────────────              ─────────────          ──────────────   │
│  • Revenue threshold        • Daily at 6am         • New client     │
│  • Cash flow alert          • Weekly summary       • BAS lodged     │
│  • Data quality drop        • BAS deadline -14d    • Action due     │
│  • AR/AP aging spike        • Quarterly review     • Sync complete  │
│                                                                      │
│  Triggered by:              Triggered by:          Triggered by:    │
│  Post-sync evaluation       Celery Beat schedule   Event bus/signal │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      TRIGGER EXECUTOR                                │
├─────────────────────────────────────────────────────────────────────┤
│  1. Evaluate trigger conditions                                      │
│  2. Check deduplication window (7 days default)                     │
│  3. Generate insights via InsightGenerator                          │
│  4. Record execution in TriggerExecution table                      │
│  5. Emit audit event                                                │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Model

```python
# Trigger Types Enum
class TriggerType(str, Enum):
    DATA_THRESHOLD = "data_threshold"    # Fires when metric crosses threshold
    TIME_SCHEDULED = "time_scheduled"    # Fires on cron schedule
    EVENT_BASED = "event_based"          # Fires on business event

# Trigger Status Enum
class TriggerStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"  # Auto-disabled after repeated failures

# Trigger Model
class Trigger(Base):
    id: UUID
    tenant_id: UUID
    name: str                           # "GST Threshold Alert"
    description: str | None
    trigger_type: TriggerType

    # Configuration (JSON)
    config: dict                        # Type-specific config
    # DATA_THRESHOLD: {"metric": "revenue_ytd", "operator": "gt", "threshold": 75000}
    # TIME_SCHEDULED: {"cron": "0 6 * * *", "timezone": "Australia/Sydney"}
    # EVENT_BASED: {"event": "xero_sync_complete", "conditions": {...}}

    # Target analyzer(s) to run
    target_analyzers: list[str]         # ["cash_flow", "compliance"]

    # Deduplication
    dedup_window_hours: int = 168       # 7 days default

    # Status
    status: TriggerStatus
    last_executed_at: datetime | None
    last_error: str | None
    consecutive_failures: int = 0

    # Audit
    created_at: datetime
    updated_at: datetime

# Trigger Execution Model
class TriggerExecution(Base):
    id: UUID
    trigger_id: UUID
    tenant_id: UUID

    # Execution details
    started_at: datetime
    completed_at: datetime | None
    status: str                         # "success", "failed", "partial"

    # Results
    clients_evaluated: int
    insights_created: int
    insights_deduplicated: int          # Skipped due to dedup

    # Error tracking
    error_message: str | None
    error_details: dict | None          # Stack trace, context

    # Metrics
    duration_ms: int | None
```

### Deduplication Strategy (CRITICAL)

Multiple triggers can fire for the same client simultaneously or in quick succession. To prevent duplicate insights, we implement a **two-layer deduplication strategy**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DEDUPLICATION LAYERS                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  LAYER 1: Cross-Trigger Dedup (NEW - in TriggerExecutor)            │
│  ─────────────────────────────────────────────────────────          │
│  Before calling InsightGenerator, check if ANY trigger already      │
│  created a similar insight for this client recently.                │
│                                                                      │
│  Query: SELECT FROM insights WHERE                                  │
│         client_id = ? AND                                           │
│         category = ? AND                                            │
│         created_at > NOW() - INTERVAL '24 hours'                    │
│                                                                      │
│  Purpose: Prevents different triggers from creating same insight    │
│  Window: 24 hours (short, for cross-trigger coordination)           │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  LAYER 2: Insight-Level Dedup (EXISTING - in InsightGenerator)      │
│  ─────────────────────────────────────────────────────────          │
│  InsightGenerator checks for duplicate insights before creation.    │
│                                                                      │
│  Query: SELECT FROM insights WHERE                                  │
│         client_id = ? AND                                           │
│         title = ? AND  (or content hash)                            │
│         created_at > NOW() - INTERVAL '7 days'                      │
│                                                                      │
│  Purpose: Prevents exact duplicate insights                         │
│  Window: 7 days (longer, for content-based dedup)                   │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  LAYER 3: Trigger-Level Throttle (NEW - per trigger)                │
│  ─────────────────────────────────────────────────────              │
│  Each trigger has dedup_window_hours to prevent spam.               │
│                                                                      │
│  Check: Has THIS trigger created insights for THIS client           │
│         within its configured window?                               │
│                                                                      │
│  Purpose: Prevents same trigger from firing too frequently          │
│  Window: Configurable per trigger (24h - 168h typically)            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### Deduplication Flow

```python
class TriggerExecutor:
    async def execute_for_client(
        self,
        trigger: Trigger,
        client_id: UUID,
        analyzer: str
    ) -> InsightResult:

        # LAYER 3: Trigger-level throttle
        if await self._trigger_recently_fired(trigger, client_id):
            return InsightResult(skipped=True, reason="trigger_throttle")

        # LAYER 1: Cross-trigger dedup (before calling generator)
        if await self._similar_insight_exists(client_id, analyzer, hours=24):
            return InsightResult(skipped=True, reason="cross_trigger_dedup")

        # Call InsightGenerator (which has its own LAYER 2 dedup)
        insights = await self.insight_generator.generate(
            client_id=client_id,
            analyzers=[analyzer],
            source=f"trigger:{trigger.id}"
        )

        # Record execution
        await self._record_execution(trigger, client_id, insights)

        return InsightResult(created=len(insights))

    async def _similar_insight_exists(
        self,
        client_id: UUID,
        category: str,
        hours: int = 24
    ) -> bool:
        """Check if ANY trigger created similar insight recently."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        result = await self.db.execute(
            select(Insight)
            .where(Insight.client_id == client_id)
            .where(Insight.category == category)
            .where(Insight.created_at > cutoff)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _trigger_recently_fired(
        self,
        trigger: Trigger,
        client_id: UUID
    ) -> bool:
        """Check if this specific trigger fired for this client recently."""
        if trigger.dedup_window_hours == 0:
            return False  # No throttle (e.g., new client welcome)

        cutoff = datetime.utcnow() - timedelta(hours=trigger.dedup_window_hours)
        result = await self.db.execute(
            select(TriggerExecution)
            .where(TriggerExecution.trigger_id == trigger.id)
            .where(TriggerExecution.client_ids.contains([str(client_id)]))
            .where(TriggerExecution.started_at > cutoff)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
```

#### Example Scenario

```
Timeline for Client A:

6:00 AM - Daily Scheduled Trigger fires
          → Layer 3: Not throttled (first run today)
          → Layer 1: No recent insights for "cash_flow"
          → Creates "Cash Flow Warning" insight ✓

10:00 AM - Xero Sync completes, Data Trigger evaluates
          → Layer 3: Not throttled (different trigger)
          → Layer 1: "cash_flow" insight exists from 6am ← BLOCKED
          → Skipped (cross-trigger dedup)

10:05 AM - Another Xero Sync (retry), Data Trigger evaluates again
          → Layer 3: Not throttled (dedup_window is 72h, only 5min passed)
          → Layer 1: "cash_flow" insight exists from 6am ← BLOCKED
          → Skipped (cross-trigger dedup)

Next Day 6:00 AM - Daily Scheduled Trigger fires again
          → Layer 3: Not throttled (>24h since last)
          → Layer 1: Previous insight is >24h old, not blocking
          → Layer 2 (InsightGenerator): Checks 7-day window for exact duplicate
          → If situation unchanged, likely creates new insight ✓
```

### Integration Points

```
┌─────────────────────────────────────────────────────────────────────┐
│                    INTEGRATION ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  EXISTING SYSTEMS                    TRIGGER SYSTEM                 │
│  ────────────────                    ──────────────                 │
│                                                                      │
│  Xero Sync Task ──────────────────► Post-Sync Data Trigger          │
│  (after sync completes)              Evaluator                       │
│                                                                      │
│  Celery Beat ─────────────────────► Time-Based Trigger              │
│  (cron schedules)                    Scheduler                       │
│                                                                      │
│  BAS Lodgement ───────────────────► Event Trigger                   │
│  Action Items                        Handler                         │
│                                                                      │
│  InsightGenerator ◄───────────────── Trigger Executor               │
│  (existing)                          (calls existing generator)      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### API Endpoints

```
# Trigger Management (Admin)
GET    /api/v1/triggers              # List all triggers for tenant
POST   /api/v1/triggers              # Create custom trigger
GET    /api/v1/triggers/{id}         # Get trigger details
PATCH  /api/v1/triggers/{id}         # Update trigger config
DELETE /api/v1/triggers/{id}         # Delete trigger

# Trigger Actions
POST   /api/v1/triggers/{id}/enable  # Enable trigger
POST   /api/v1/triggers/{id}/disable # Disable trigger
POST   /api/v1/triggers/{id}/test    # Test trigger (dry run)

# Execution History
GET    /api/v1/triggers/executions   # List recent executions
GET    /api/v1/triggers/{id}/executions # Executions for specific trigger
```

### Default Triggers (Seeded)

```python
DEFAULT_TRIGGERS = [
    # Data Triggers
    {
        "name": "GST Threshold Alert",
        "trigger_type": "data_threshold",
        "config": {"metric": "revenue_ytd", "operator": "gte", "threshold": 75000},
        "target_analyzers": ["compliance"],
        "dedup_window_hours": 168,
    },
    {
        "name": "Cash Flow Warning",
        "trigger_type": "data_threshold",
        "config": {"metric": "ar_overdue_total", "operator": "gte", "threshold": 20000},
        "target_analyzers": ["cash_flow"],
        "dedup_window_hours": 72,
    },
    {
        "name": "Data Quality Alert",
        "trigger_type": "data_threshold",
        "config": {"metric": "unreconciled_count", "operator": "gte", "threshold": 10},
        "target_analyzers": ["quality"],
        "dedup_window_hours": 24,
    },

    # Time Triggers
    {
        "name": "Daily Insight Generation",
        "trigger_type": "time_scheduled",
        "config": {"cron": "0 6 * * *", "timezone": "Australia/Sydney"},
        "target_analyzers": ["cash_flow", "quality", "compliance"],
        "dedup_window_hours": 24,
    },
    {
        "name": "BAS Deadline Reminder",
        "trigger_type": "time_scheduled",
        "config": {"cron": "0 9 * * *", "days_before_deadline": 14},
        "target_analyzers": ["compliance"],
        "dedup_window_hours": 168,
    },

    # Event Triggers
    {
        "name": "New Client Welcome",
        "trigger_type": "event_based",
        "config": {"event": "xero_connection_created"},
        "target_analyzers": ["cash_flow", "quality", "compliance"],
        "dedup_window_hours": 0,  # Always run for new clients
    },
    {
        "name": "Post-Lodgement Review",
        "trigger_type": "event_based",
        "config": {"event": "bas_lodged"},
        "target_analyzers": ["compliance"],
        "dedup_window_hours": 0,
    },
]
```

## Complexity Tracking

> No constitution violations - design follows established patterns.

## Implementation Notes

### Celery Integration

```python
# trigger_tasks.py

@celery_app.task
def evaluate_data_triggers(tenant_id: str, client_id: str):
    """Called after Xero sync completes for a client."""
    ...

@celery_app.task
def execute_scheduled_trigger(trigger_id: str):
    """Called by Celery Beat for time-based triggers."""
    ...

@celery_app.task
def handle_business_event(event_type: str, payload: dict):
    """Called when business events occur."""
    ...
```

### Celery Beat Schedule

```python
# Add to celery config
CELERY_BEAT_SCHEDULE = {
    "daily-insight-generation": {
        "task": "app.tasks.trigger_tasks.run_time_triggers",
        "schedule": crontab(hour=6, minute=0),  # 6am daily
    },
    "check-bas-deadlines": {
        "task": "app.tasks.trigger_tasks.check_deadline_triggers",
        "schedule": crontab(hour=9, minute=0),  # 9am daily
    },
}
```

### Error Handling

- Triggers auto-disable after 3 consecutive failures
- Failed executions logged with full context
- Partial success tracked (some clients processed before failure)
- Retry with exponential backoff for transient failures
