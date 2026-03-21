# Implementation Plan: Progressive Xero Data Sync

**Branch**: `043-progressive-xero-sync` | **Date**: 2026-02-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/043-progressive-xero-sync/spec.md`

## Summary

Transform the Xero data sync from a blocking, sequential single-task operation into a non-blocking, phased background process. The current sync blocks users for 2-5 minutes while syncing 2,500+ records across 16+ entity types in a single Celery task with one DB session. The new architecture:

1. **Phases the initial sync** — essential data (accounts, contacts, recent invoices) in <30s, then historical data in background
2. **Parallelizes entity syncs** — each entity type runs as a separate Celery task with isolated DB sessions
3. **Provides real-time progress** via Server-Sent Events backed by Redis pub/sub
4. **Expands incremental sync** from 3 entity types to 9 using If-Modified-Since
5. **Supports multi-client parallel sync** with Xero API rate limit management
6. **Tracks post-sync pipeline** — quality scoring, BAS calculation, insights, triggers

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Celery + Redis, Pydantic v2, Next.js 14, shadcn/ui, TanStack Query
**Storage**: PostgreSQL 16 (new tables: `xero_sync_entity_progress`, `post_sync_tasks`, `xero_webhook_events`; extend `xero_sync_jobs`, `xero_connections`)
**Testing**: pytest + pytest-asyncio (backend), Playwright (E2E)
**Target Platform**: Docker (Linux containers), macOS development
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Phase 1 essential data in <30s, incremental sync <10s, SSE updates <1s latency
**Constraints**: Xero API rate limits (60 calls/min, 5000 calls/day per connection), 4 Celery worker processes
**Scale/Scope**: 25-250 clients per tenant, 16+ entity types per client, ~2,500 records per client

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Modular monolith architecture | PASS | All changes within `modules/integrations/xero/` and `tasks/`. No new modules created. |
| Repository pattern for DB access | PASS | New models get repositories following existing pattern (e.g., `XeroSyncEntityProgressRepository`). |
| Multi-tenancy (tenant_id + RLS) | PASS | All new tables include `tenant_id` with RLS policies. |
| Audit-first | PASS | Sync start/complete/fail events already audited. New entity-level events added. |
| Module boundaries | PASS | Cross-module calls use service layer (e.g., `QualityService`, `BASService` via Celery task dispatch). |
| Type hints everywhere | PASS | All new code fully typed. |
| Domain exceptions (not HTTPException) | PASS | Existing pattern followed — `XeroSyncInProgressError`, `XeroRateLimitExceededError`. |
| Testing coverage (80% unit, 100% endpoints) | PASS | New endpoints get integration tests. Sync orchestration gets unit tests. |

**Post-Phase 1 Re-check**: PASS. SSE endpoint uses standard FastAPI `StreamingResponse` — no WebSocket infrastructure needed. Redis pub/sub uses existing Redis connection from Celery broker. No new external dependencies introduced.

## Project Structure

### Documentation (this feature)

```text
specs/043-progressive-xero-sync/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 research and decisions
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Phase 1 developer quickstart
├── contracts/           # Phase 1 API contracts
│   └── api.yaml
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Phase 2 task list (created by /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── modules/integrations/xero/
│   │   ├── models.py                # Extend: XeroSyncJob, new: XeroSyncEntityProgress, PostSyncTask, XeroWebhookEvent
│   │   ├── repository.py            # Extend: new repos for new models
│   │   ├── schemas.py               # Extend: SSE events, entity progress, multi-client sync schemas
│   │   ├── service.py               # Extend: start_phased_sync(), start_multi_client_sync()
│   │   ├── router.py                # Extend: SSE stream, multi-client sync, webhook endpoints
│   │   ├── sync_progress.py         # NEW: Redis pub/sub for sync progress events
│   │   └── webhook_handler.py       # NEW: Xero webhook verification + event processing (Phase 3)
│   │
│   └── tasks/
│       ├── xero.py                  # REFACTOR: Phased sync orchestration, per-entity tasks
│       └── scheduler.py             # Extend: Use incremental sync, multi-client awareness
│
├── alembic/versions/
│   └── YYYYMMDD_*_progressive_sync_tables.py  # Migration
│
└── tests/
    ├── unit/modules/integrations/xero/
    │   ├── test_sync_progress.py    # Redis pub/sub tests
    │   └── test_phased_sync.py      # Orchestration unit tests
    └── integration/api/
        └── test_sync_endpoints.py   # SSE, multi-client sync endpoint tests

frontend/
├── src/
│   ├── hooks/
│   │   └── useSyncProgress.ts       # NEW: EventSource hook for SSE
│   ├── lib/
│   │   └── xero-sync.ts             # Extend: SSE helpers, multi-client API
│   └── components/integrations/xero/
│       ├── SyncProgressDialog.tsx    # REFACTOR: SSE-powered, non-blocking
│       ├── SyncStatusDisplay.tsx     # Extend: data freshness indicator
│       ├── SyncNotificationBadge.tsx # NEW: Active sync count badge
│       └── MultiClientSyncButton.tsx # NEW: "Sync All" with progress
```

**Structure Decision**: Web application structure following existing Clairo modular monolith pattern. All backend changes within the existing `modules/integrations/xero/` module and `tasks/` package. Frontend changes extend existing sync components.

## Complexity Tracking

No constitution violations. All changes follow existing patterns:
- Repository pattern for new models
- Celery tasks for background processing
- Redis for pub/sub (already the Celery broker)
- FastAPI StreamingResponse for SSE (built-in, no new dependency)

## Phase 0 Artifacts

- [research.md](./research.md) — 8 design decisions with rationale and alternatives

## Phase 1 Artifacts

- [data-model.md](./data-model.md) — 3 new entities, 2 modified entities, state transitions
- [contracts/api.yaml](./contracts/api.yaml) — 6 endpoints (2 modified, 4 new), 7 schema definitions
- [quickstart.md](./quickstart.md) — Development overview, architecture diagram, file manifest

## Implementation Priority

| Priority | User Story | Scope |
|----------|-----------|-------|
| **P1** | Non-blocking background sync | Refactor sync to background, toast notifications, non-blocking UI |
| **P1** | Phased initial sync | 3-phase sync orchestration, progressive data availability |
| **P2** | Incremental sync expansion | Add IMS to 6 more entity types, per-entity timestamps |
| **P2** | Multi-client parallel sync | "Sync All" endpoint, rate-limit-aware queuing, aggregate progress |
| **P2** | Post-sync data preparation | Track post-sync pipeline, progressive preparation after each phase |
| **P3** | Real-time SSE progress | Redis pub/sub → SSE stream → frontend EventSource |
| **P3** | Xero webhooks | Webhook receiver, HMAC verification, event batching |

## Key Risks

| Risk | Mitigation |
|------|-----------|
| Celery chord/chain complexity | Start with simple sequential phases; upgrade to parallel groups within phases incrementally |
| Redis pub/sub message loss | Progress events are ephemeral — frontend can always fall back to polling `/sync/status` |
| Rate limit exhaustion during multi-client sync | Global rate limiter across all connections, configurable concurrency cap |
| Xero webhook delivery unreliability | Webhooks supplement scheduled + manual sync, never replace them |
| Migration on production data | All new columns nullable, new tables additive — zero downtime migration |
