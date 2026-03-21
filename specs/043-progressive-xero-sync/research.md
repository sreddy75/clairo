# Research: Progressive Xero Data Sync

**Feature**: 043-progressive-xero-sync
**Date**: 2026-02-14

## Current Architecture Analysis

### Sync Orchestration (`backend/app/tasks/xero.py`)

- **`run_sync`**: Single Celery task orchestrates all entity syncing **sequentially** in one task
- Entity sync order for FULL sync:
  1. Accounts (no If-Modified-Since)
  2. Contacts (supports IMS)
  3. Invoices (supports IMS)
  4. Bank Transactions (supports IMS)
  5. Credit Notes, Payments, Overpayments, Prepayments, Journals, Manual Journals
  6. Purchase Orders, Repeating Invoices, Tracking Categories, Quotes (no IMS)
  7. Payroll (if scope permits)
  8. Asset Types + Assets (if scope permits)
  9. Organisation Profile
- Post-sync triggers fire only after ALL entities complete: quality score, BAS calc, aggregation, insights, triggers
- Single DB session for the entire task — one failure poisons the transaction

### Rate Limiter (`backend/app/modules/integrations/xero/rate_limiter.py`)

- Tracks `rate_limit_daily_remaining` (5000/day) and `rate_limit_minute_remaining` (60/min) on `XeroConnection` model
- `rate_limit_reset_at` tracks when minute bucket resets
- Rate limit headers parsed from Xero API responses and stored on connection
- Rate limiter is connection-scoped (not tenant-scoped) — each Xero org has its own limits
- No cross-connection rate limit coordination

### If-Modified-Since Usage

- **Currently supported**: Contacts (`last_contacts_sync_at`), Invoices (`last_invoices_sync_at`), Bank Transactions (`last_transactions_sync_at`)
- **Not supported but could be**: Credit Notes, Payments, Overpayments, Prepayments, Journals, Manual Journals (Xero API supports IMS for these)
- **Cannot support IMS**: Accounts, Purchase Orders, Repeating Invoices, Tracking Categories, Quotes, Assets (Xero doesn't provide IMS)
- Timestamps stored as `last_*_sync_at` on `XeroConnection` model

### Frontend Progress

- **Polling-based**: Frontend polls `GET /api/v1/xero/connections/{id}/sync/status` at intervals
- **SyncProgressDialog** (`frontend/src/components/integrations/xero/SyncProgressDialog.tsx`): Modal that blocks UI while showing per-entity progress
- **SyncStatusDisplay**: Shows sync status on client cards (syncing, stale, last synced)
- **SyncHistoryView**: Paginated table of past sync jobs
- No WebSocket or SSE infrastructure exists

### Post-Sync Pipeline

Currently triggered inline at end of `run_sync` task via `task.delay()`:
1. `calculate_quality_score.delay()` — Spec 009
2. `calculate_bas_periods.delay()` — Spec 010
3. `compute_aggregations.delay()` — Spec 013
4. `generate_insights_for_connection.delay()` — Spec 016
5. `evaluate_data_triggers.delay()` — Spec 017
6. Usage alert check (inline, not a separate task)

### Scheduled Sync

- `sync_all_stale_connections` runs daily at 2am UTC (12pm AEST)
- Checks for connections with `last_full_sync_at` older than 24 hours
- Creates sync jobs and dispatches `run_sync.delay()` for each
- Sequential processing — no parallelism

### Webhook Infrastructure

- **None exists**. No webhook endpoints, no event processing, no Xero webhook verification.
- Xero webhooks require: endpoint registration, HMAC-SHA256 signature verification, intent-to-receive validation

---

## Design Decisions

### Decision 1: SSE over WebSocket for real-time progress

**Decision**: Use Server-Sent Events (SSE) for real-time sync progress
**Rationale**:
- SSE is simpler (unidirectional server→client, standard HTTP)
- No need for bidirectional communication (client doesn't send data during sync)
- Native browser support via `EventSource`
- Works through proxies and load balancers without special configuration
- FastAPI supports SSE via `StreamingResponse` with `text/event-stream`
**Alternatives considered**:
- WebSocket: Overkill for unidirectional progress. Requires connection upgrade, more complex error handling, harder to debug
- Long polling: Already in use. Higher latency, more server load from repeated connections

### Decision 2: Celery chord/chain for phased sync

**Decision**: Use Celery `chain` to compose phased sync (Phase 1 → Phase 2 → Phase 3 → Post-sync)
**Rationale**:
- Celery chains provide natural sequential phase execution
- Each phase is a group of parallel entity sync tasks
- Using `chord` within each phase allows parallel entity syncs with a callback
- Fits existing Celery infrastructure — no new dependencies
- Progress tracking via Redis pub/sub between tasks
**Alternatives considered**:
- Single monolithic task (current): Can't parallelize entities within a phase. Single DB session failure cascades
- Separate independent tasks with no orchestration: Harder to track overall progress, no phase ordering
- Celery canvas (chain of groups): Same as chosen approach — chain + group is the canvas pattern

### Decision 3: Redis pub/sub for progress broadcasting

**Decision**: Use Redis pub/sub to broadcast sync progress events, consumed by SSE endpoint
**Rationale**:
- Redis already in the stack (Celery broker)
- Pub/sub is fire-and-forget — no persistence needed for progress events
- Multiple SSE connections can subscribe to the same channel
- Celery tasks already have Redis access
- Low latency (<10ms)
**Alternatives considered**:
- Database polling: Higher latency (already in use), more DB load
- Redis Streams: More complex, persistence not needed for ephemeral progress events
- Dedicated message broker (RabbitMQ): New dependency, unnecessary

### Decision 4: Per-entity Celery tasks (not all entities in one task)

**Decision**: Refactor sync to dispatch separate Celery tasks per entity type, grouped by phase
**Rationale**:
- Isolated failure handling — one entity's failure doesn't poison others
- Each entity task has its own DB session — no transaction cascade
- Parallel execution within phases using Celery groups
- Individual retry per entity (e.g., contacts rate-limited, invoices continue)
- Progress updates per entity via Redis pub/sub
**Alternatives considered**:
- Keep single task, just add phases: Still has the transaction cascade problem. Can't parallelize.
- Thread-based parallelism within single task: Celery tasks should not spawn threads. SQLAlchemy sessions are not thread-safe.

### Decision 5: Expand If-Modified-Since to all supported entities

**Decision**: Add IMS tracking for Credit Notes, Payments, Overpayments, Prepayments, Journals, Manual Journals
**Rationale**:
- Xero API supports `If-Modified-Since` header for these entities
- Currently only 3 of 9+ eligible entities use it
- Adds `last_*_sync_at` columns to `XeroConnection` for each new entity
- Dramatically reduces incremental sync time and API calls
**Alternatives considered**:
- Keep current 3 only: Misses easy optimization for 6 more entity types
- Per-entity tracking table: Adds complexity — columns on XeroConnection is simpler and consistent with current pattern

### Decision 6: Defer webhooks to Phase 3 (P3)

**Decision**: Implement webhooks as a separate, lower-priority phase after background sync and incremental sync are solid
**Rationale**:
- Background sync + incremental sync solve 90% of the freshness problem
- Webhooks require Xero developer portal configuration per app
- Webhook verification (HMAC-SHA256) and intent-to-receive validation add complexity
- Scheduled daily sync + fast incremental sync is "good enough" for most practices
- Webhooks add value but aren't blocking
**Alternatives considered**:
- Build webhooks first: Higher risk, lower ROI. Webhook delivery isn't guaranteed — still need polling as fallback

### Decision 7: Phase definitions for initial sync

**Decision**: Three phases based on data criticality
- **Phase 1 (Essential)**: Accounts + Contacts + recent Invoices (last 12 months)
- **Phase 2 (Recent History)**: Bank Transactions, Payments, Credit Notes, Prepayments, Overpayments (last 12 months)
- **Phase 3 (Full History)**: All remaining entities + historical data older than 12 months

**Rationale**:
- Phase 1 gives accountants what they need to start working within 30 seconds
- Phase 2 completes the financial picture for BAS preparation
- Phase 3 fills in historical data for trend analysis and insights
- Each phase triggers progressive post-sync preparation

### Decision 8: Stale job auto-expiry (already implemented)

**Decision**: Auto-expire sync jobs stuck as `in_progress` for >30 minutes
**Rationale**: Already implemented in this branch. Prevents stuck jobs from permanently blocking new syncs.
**Implementation**: Check in `start_sync()` — if existing active job is older than 30 minutes, mark it as failed and allow new sync.
