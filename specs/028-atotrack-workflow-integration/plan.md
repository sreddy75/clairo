# Implementation Plan: ATOtrack Workflow Integration

**Branch**: `028-atotrack-workflow-integration` | **Date**: 2026-01-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/028-atotrack-workflow-integration/spec.md`

## Summary

Integrate parsed ATO correspondence into the Clairo workflow system with automatic task creation, insight generation, deadline notifications, and a dedicated ATOtrack dashboard. This completes the ATOtrack feature set.

**Technical Approach**:
- Create ATOtrack submodule within email module
- Extend existing Task and Insight systems
- Add correspondence-specific notification triggers
- Build dedicated ATOtrack dashboard
- Implement AI response drafting using RAG

---

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Pydantic v2, Celery
**Storage**: PostgreSQL 16
**Testing**: pytest, pytest-asyncio
**Target Platform**: AWS ECS/Fargate (Sydney region)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Dashboard <2s, task creation <5s, AI draft <30s
**Constraints**: Leverage existing task/insight/notification systems
**Scale/Scope**: Up to 500 correspondence items/tenant

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **Modular Monolith** | ✅ PASS | ATOtrack submodule within email |
| **Repository Pattern** | ✅ PASS | Uses existing task/insight repos |
| **Multi-tenancy (RLS)** | ✅ PASS | All operations scoped by tenant |
| **Audit-First** | ✅ PASS | Audit events for workflow actions |
| **Type Hints** | ✅ PASS | Pydantic schemas throughout |
| **Test-First** | ✅ PASS | Test workflow rules and triggers |
| **API Conventions** | ✅ PASS | RESTful endpoints |
| **Integration Pattern** | ✅ PASS | Extends existing systems cleanly |

**No violations requiring justification.**

---

## Project Structure

### Documentation (this feature)

```text
specs/028-atotrack-workflow-integration/
├── plan.md              # This file
├── research.md          # Workflow integration research
├── data-model.md        # Entity extensions
├── quickstart.md        # Developer guide
├── contracts/           # OpenAPI specs
│   └── atotrack-api.yaml
└── tasks.md             # Implementation tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   └── modules/
│       └── email/
│           └── atotrack/                # NEW SUBMODULE
│               ├── __init__.py
│               ├── service.py           # ATOtrack orchestration
│               ├── task_rules.py        # Task creation rules
│               ├── insight_rules.py     # Insight generation rules
│               ├── notification_rules.py # Notification triggers
│               ├── response_drafter.py  # AI response drafting
│               ├── dashboard.py         # Dashboard aggregation
│               ├── router.py            # API endpoints
│               └── integrations/        # Practice management
│                   ├── __init__.py
│                   ├── karbon.py        # Karbon API client
│                   └── xpm.py           # XPM API client
│
└── tests/
    ├── unit/
    │   └── modules/
    │       └── email/
    │           └── atotrack/
    │               ├── test_task_rules.py
    │               ├── test_insight_rules.py
    │               └── test_response_drafter.py
    └── integration/
        └── api/
            └── test_atotrack.py

frontend/
└── src/
    ├── app/
    │   └── (protected)/
    │       └── atotrack/
    │           ├── page.tsx             # ATOtrack dashboard
    │           └── [id]/page.tsx        # Correspondence detail
    ├── components/
    │   └── atotrack/
    │       ├── SummaryCards.tsx
    │       ├── RequiresAttention.tsx
    │       ├── CorrespondenceRow.tsx
    │       ├── ResponseDrafter.tsx
    │       └── ResolveDialog.tsx
    └── lib/
        └── api/
            └── atotrack.ts
```

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      ATOTRACK WORKFLOW ARCHITECTURE                      │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │              PARSED CORRESPONDENCE (from Spec 027)                 │ │
│  └───────────────────────────────┬───────────────────────────────────┘ │
│                                  │                                      │
│                                  ▼                                      │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                    ATOTRACK SERVICE                                │ │
│  │                                                                    │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │ │
│  │  │    Task     │  │   Insight   │  │ Notification│               │ │
│  │  │    Rules    │  │    Rules    │  │   Rules     │               │ │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │ │
│  │         │                │                │                        │ │
│  │         ▼                ▼                ▼                        │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │ │
│  │  │   Tasks     │  │  Insights   │  │Notifications│               │ │
│  │  │   Module    │  │   Module    │  │   Module    │               │ │
│  │  │ (existing)  │  │ (existing)  │  │ (existing)  │               │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘               │ │
│  │                                                                    │ │
│  │  ┌─────────────────────────────────────────────────────────┐      │ │
│  │  │              RESPONSE DRAFTER                            │      │ │
│  │  │  - Claude API for drafting                               │      │ │
│  │  │  - RAG from knowledge base                               │      │ │
│  │  │  - Templates for common responses                        │      │ │
│  │  └─────────────────────────────────────────────────────────┘      │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│           ┌────────────────────┴────────────────────┐                  │
│           ▼                                          ▼                  │
│  ┌─────────────────────┐                ┌─────────────────────┐        │
│  │  ATOtrack Dashboard │                │  Practice Mgmt      │        │
│  │                     │                │  (Optional)         │        │
│  │  - Summary cards    │                │  - Karbon sync      │        │
│  │  - Requires attention│               │  - XPM sync         │        │
│  │  - Action buttons   │                │                     │        │
│  └─────────────────────┘                └─────────────────────┘        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Workflow Pipeline

```
ATOTRACK WORKFLOW PIPELINE
═══════════════════════════════════════════════════════════════════════════

1. CORRESPONDENCE PARSED (Event: correspondence.parsed)
   │
   ▼
2. APPLY TASK RULES
   ├── Match notice type → task template
   ├── Calculate due date from notice or default
   ├── Set priority based on notice type
   ├── Create task linked to correspondence
   └── Update correspondence.task_id
   │
   ▼
3. APPLY INSIGHT RULES
   ├── Check if notice type generates insight
   ├── Set severity based on notice type + amount
   ├── Create insight linked to correspondence
   └── Update correspondence.insight_id
   │
   ▼
4. SCHEDULE NOTIFICATIONS
   ├── Register deadline notifications:
   │   - 7 days before
   │   - 3 days before
   │   - 1 day before
   │   - Overdue (daily)
   └── Store notification schedule
   │
   ▼
5. OPTIONAL: SYNC TO PRACTICE MANAGEMENT
   ├── If Karbon connected → create Karbon task
   └── If XPM connected → create XPM job

RESOLUTION FLOW
═══════════════════════════════════════════════════════════════════════════

1. USER MARKS RESOLVED
   │
   ▼
2. UPDATE CORRESPONDENCE
   └── status = RESOLVED
   │
   ▼
3. COMPLETE LINKED TASK
   └── task.status = COMPLETED
   │
   ▼
4. DISMISS LINKED INSIGHT
   └── insight.status = DISMISSED
   │
   ▼
5. CANCEL PENDING NOTIFICATIONS
   └── Remove scheduled deadline reminders
```

### Dashboard Data Flow

```
DASHBOARD AGGREGATION
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│                         GET /atotrack/dashboard                          │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  QUERY: ATOCorrespondence WHERE tenant_id = ? AND status != RESOLVED    │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  AGGREGATIONS:                                                           │
│  ├── overdue_count: WHERE due_date < today AND status != RESOLVED       │
│  ├── due_soon_count: WHERE due_date BETWEEN today AND today+7           │
│  ├── handled_count: WHERE status = RESOLVED                             │
│  ├── triage_count: WHERE needs_triage = true                            │
│  └── requires_attention: ORDER BY urgency, due_date LIMIT 10            │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  RESPONSE: DashboardData                                                 │
│  {                                                                       │
│    summary: { overdue: 3, due_soon: 5, handled: 12, triage: 2 },        │
│    requires_attention: [ ... top 10 items sorted by urgency ... ],       │
│    recent_resolved: [ ... last 5 resolved items ... ]                    │
│  }                                                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Task Integration | Extend existing Task module | Reuse proven task infrastructure |
| Insight Integration | Extend existing Insight module | Unified insight experience |
| Notification System | Use existing triggers module | Consistent notification delivery |
| Response Drafting | Claude + RAG | Best quality for professional correspondence |
| Dashboard | Dedicated ATOtrack page | Focused experience for ATO matters |
| PM Integration | Optional, async | Core value in Clairo, PM sync is bonus |

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Task duplication | Check for existing task by correspondence_id |
| Notification spam | Respect user preferences, aggregate alerts |
| AI draft quality | Human review required, provide templates |
| PM sync failures | Async with retry, don't block core workflow |
| Performance | Aggregate queries, cache dashboard data |

---

## Dependencies

### Internal Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Spec 027 (ATO Parsing) | Required | Provides parsed correspondence |
| Tasks module | Required | Task creation infrastructure |
| Insights module | Required | Insight generation |
| Notifications module | Required | Email/push delivery |
| Triggers module | Required | Deadline scheduling |

### External Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| anthropic | 0.35+ | AI response drafting |
| Karbon API | v1 | Practice management sync |
| XPM API | v1 | Practice management sync |

---

## Phase References

- **Phase 0**: See [research.md](./research.md) for workflow research
- **Phase 1**: See [data-model.md](./data-model.md) for entity extensions
- **Phase 1**: See [contracts/atotrack-api.yaml](./contracts/atotrack-api.yaml) for API specs
- **Phase 1**: See [quickstart.md](./quickstart.md) for developer guide
