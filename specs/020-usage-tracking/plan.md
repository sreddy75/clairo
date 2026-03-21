# Implementation Plan: Usage Tracking & Limits

**Branch**: `feature/020-usage-tracking` | **Date**: 2025-12-31 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/020-usage-tracking/spec.md`

---

## Summary

Extend Spec 019's billing infrastructure to add comprehensive usage tracking, limit enforcement with user-friendly errors, threshold-based email alerts, and usage analytics. The foundation (client count, tier limits) exists; this spec adds visibility, proactive alerts, and historical tracking.

**Key deliverables**:
1. Usage dashboard showing clients/AI queries/documents vs limits
2. Client limit enforcement with upgrade prompts
3. Email alerts at 80% and 90% thresholds
4. Usage history for trend analysis
5. Admin analytics for upsell identification

---

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Next.js 14, React, Tailwind CSS
**Storage**: PostgreSQL 16 (new tables: usage_snapshots, usage_alerts)
**Testing**: pytest, vitest
**Target Platform**: Web (desktop and mobile responsive)
**Project Type**: Web application (monorepo with backend/ and frontend/)
**Performance Goals**: Dashboard loads < 2 seconds, real-time client count updates within 1 minute
**Constraints**: Email alerts sent within 5 minutes of threshold crossing
**Scale/Scope**: 100s of tenants, 1000s of clients, monthly usage snapshots

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Modular Monolith Architecture | ✅ PASS | Extends existing billing module |
| Repository Pattern | ✅ PASS | New repositories for usage entities |
| Multi-tenancy (tenant_id isolation) | ✅ PASS | All usage data scoped to tenant |
| Pydantic for all schemas | ✅ PASS | New schemas for usage metrics |
| Type hints everywhere | ✅ PASS | Will follow existing patterns |
| Test-first development | ✅ PASS | Unit + integration tests |
| Auditing (first-class concern) | ✅ PASS | Audit events defined in spec |

**No violations to justify.**

---

## Project Structure

### Documentation (this feature)

```text
specs/020-usage-tracking/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── usage-api.yaml   # OpenAPI spec for usage endpoints
├── checklists/
│   └── requirements.md  # Specification checklist
└── tasks.md             # Phase 2 output (from /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── modules/
│   │   ├── billing/              # Extend existing module
│   │   │   ├── models.py         # Add UsageSnapshot, UsageAlert
│   │   │   ├── schemas.py        # Add usage dashboard schemas
│   │   │   ├── repository.py     # Add usage repositories
│   │   │   ├── service.py        # Extend with alert/tracking logic
│   │   │   ├── router.py         # Add usage endpoints
│   │   │   └── usage_alerts.py   # NEW: Usage alert logic (uses EmailService)
│   │   └── notifications/        # Existing module
│   │       ├── email_service.py  # EXTEND: Add usage alert methods
│   │       └── templates.py      # EXTEND: Add usage alert templates
├── alembic/versions/
│   └── 025_usage_tracking.py     # Migration for new tables
└── tests/
    ├── unit/modules/billing/
    │   ├── test_usage_service.py
    │   └── test_alerts.py
    └── integration/api/
        └── test_usage_endpoints.py

frontend/
├── src/
│   ├── app/(protected)/settings/billing/
│   │   └── page.tsx              # Extend with usage dashboard
│   ├── components/billing/
│   │   ├── UsageDashboard.tsx    # NEW: Main usage component
│   │   ├── UsageProgressBar.tsx  # NEW: Visual progress bar
│   │   ├── UsageHistory.tsx      # NEW: Historical chart
│   │   └── UsageAlert.tsx        # NEW: In-app alert banner
│   ├── hooks/
│   │   └── useUsage.ts           # NEW: Usage data hook
│   └── lib/api/
│       └── billing.ts            # Extend with usage endpoints
└── src/__tests__/
    └── components/billing/
        └── UsageDashboard.test.tsx
```

**Structure Decision**: Extend existing billing module rather than create new module. Usage tracking is closely tied to billing/subscription infrastructure from Spec 019.

---

## Implementation Approach

### Phase 1: Backend Foundation (P1 - Dashboard Data)
1. Create UsageSnapshot and UsageAlert models
2. Add usage tracking repositories
3. Extend BillingService with enhanced usage methods
4. Create API endpoints for usage data

### Phase 2: Frontend Dashboard (P1 - Visualization)
1. Create UsageDashboard component
2. Add UsageProgressBar with color coding
3. Integrate into billing settings page
4. Add useUsage hook

### Phase 3: Limit Enforcement (P1 - Core Business Logic)
1. Hook client creation to check limits
2. Return upgrade prompts on limit reached
3. Handle Xero sync edge cases

### Phase 4: Email Alerts (P2 - Proactive Notifications)
1. Create email alert service
2. Add threshold detection logic
3. Implement alert deduplication (once per threshold per period)
4. Add in-app alert banners

### Phase 5: Usage History (P3 - Analytics)
1. Add daily snapshot background job
2. Create history API endpoint
3. Add UsageHistory chart component

### Phase 6: Admin Analytics (P3 - Business Intelligence)
1. Create admin usage analytics endpoints
2. Add aggregate statistics queries
3. Implement upsell opportunity identification

---

## Key Design Decisions

### 1. Client Count Source
**Decision**: Count active XeroConnections per tenant where `status != 'disconnected'`
**Rationale**: Already implemented in Spec 019, consistent with existing logic
**Alternative rejected**: Separate client table - would duplicate data

### 2. Alert Deduplication Strategy
**Decision**: Store sent alerts in UsageAlert table, check before sending
**Rationale**: Prevents alert fatigue, allows reset per billing period
**Alternative rejected**: In-memory tracking - would reset on restart

### 3. Usage Snapshot Frequency
**Decision**: Daily snapshots, aggregated to monthly for display
**Rationale**: Balance between granularity and storage, sufficient for trend analysis
**Alternative rejected**: Hourly snapshots - excessive storage, minimal value

### 4. Email vs Push Notifications
**Decision**: Email only (as specified in scope)
**Rationale**: Simpler implementation, email infrastructure exists
**Alternative rejected**: Push notifications - out of scope, can add later

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Email delivery failures | Medium | Low | Log failures, retry logic, manual check in admin |
| Client count drift | Low | Medium | Sync count on login, background reconciliation |
| Performance on large tenant base | Low | Medium | Indexes on tenant_id, pagination for admin views |
| Alert spam if thresholds crossed repeatedly | Medium | Medium | Deduplication in UsageAlert table |

---

## Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Spec 019 (Billing module) | ✅ Complete | Tier infrastructure exists |
| XeroConnection model | ✅ Exists | For client counting |
| Email infrastructure | ✅ Exists | Resend EmailService in notifications module |
| Background job system | ✅ Exists | Celery + Redis configured |

---

## Estimated Effort

| Phase | Effort | Dependencies |
|-------|--------|--------------|
| Backend Foundation | 4 hours | None |
| Frontend Dashboard | 4 hours | Backend Foundation |
| Limit Enforcement | 2 hours | Backend Foundation |
| Email Alerts | 3 hours | Backend Foundation |
| Usage History | 3 hours | Backend Foundation |
| Admin Analytics | 4 hours | Backend Foundation |
| Testing & Polish | 4 hours | All phases |
| **Total** | **~3 days** | Sequential |
