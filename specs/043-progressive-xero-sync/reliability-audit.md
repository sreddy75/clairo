# Xero Sync Pipeline — Reliability Audit & Redesign

**Date**: 2026-02-21
**Status**: CRITICAL — Production sync pipeline has multiple confirmed bugs causing stuck jobs and data staleness
**Environment**: Railway (ephemeral containers), Redis broker, PostgreSQL 16 with RLS

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Architecture](#2-current-architecture)
3. [Confirmed Bugs](#3-confirmed-bugs)
4. [Additional Failure Modes](#4-additional-failure-modes)
5. [Root Cause Patterns](#5-root-cause-patterns)
6. [Proposed Architecture](#6-proposed-architecture)
7. [Implementation Plan](#7-implementation-plan)
8. [Monitoring & Observability](#8-monitoring--observability)
9. [Testing Strategy](#9-testing-strategy)

---

## 1. Executive Summary

The Xero data sync pipeline is the **critical data ingestion path** for the entire Clairo platform. Every downstream feature — quality scoring, BAS calculations, AI insights, advisory triggers, client dashboards — depends on fresh, complete data from Xero. When syncs fail silently or get stuck, the entire platform degrades.

**Current state**: The pipeline has **8 confirmed bugs** ranging from CRITICAL to MEDIUM severity. The most severe (missing scheduler arguments) means **all scheduled syncs have been failing since the progressive sync feature was deployed**. Combined with the lack of stale job cleanup, connections that fail once are **permanently blocked** from future scheduled syncs.

### Impact Assessment

| Area | Impact |
|------|--------|
| **Data Freshness** | Xero data becomes stale after 24h; quality scores, BAS calculations, and insights are based on outdated data |
| **User Experience** | Dashboard shows stale data; sync buttons may appear stuck; no clear error feedback |
| **AI Features** | Insights, triggers, and advisory recommendations based on stale data lose credibility |
| **Compliance** | BAS calculations may use outdated transaction data, creating compliance risk |
| **Revenue** | Platform value proposition degrades when data isn't fresh; retention risk |

### Bug Summary

| # | Bug | Severity | Status |
|---|-----|----------|--------|
| 1 | Scheduler missing `connection_id` and `tenant_id` in `run_phased_sync.delay()` | **CRITICAL** | Confirmed |
| 2 | Worker pool deadlock — orchestrator blocks worker waiting for child tasks | **HIGH** | Confirmed |
| 3 | `SET LOCAL` tenant context lost after every `session.commit()` | **HIGH** | Confirmed |
| 4 | No periodic stale job cleanup — stuck jobs block future syncs forever | **HIGH** | Confirmed |
| 5 | New DB engine created per task — connection pool leak | **MEDIUM** | Confirmed |
| 6 | `task_acks_late` + orchestrator = duplicate work on worker crash | **HIGH** | Confirmed |
| 7 | `asyncio.run()` per task compounds engine/connection leak | **MEDIUM** | Confirmed |
| 8 | Scheduler queries bypass RLS (no tenant context set) | **LOW-MEDIUM** | Confirmed |

---

## 2. Current Architecture

### Sync Flow (Progressive 3-Phase System)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TRIGGER SOURCES                              │
│  User (API) │ Scheduler (02:00 UTC daily) │ Webhook │ Bulk Import  │
└──────┬──────┴─────────────┬────────────────┴────┬────┴──────────────┘
       │                    │                     │
       ▼                    ▼                     ▼
┌──────────────┐  ┌──────────────────┐  ┌─────────────────────┐
│ initiate_    │  │ sync_all_stale_  │  │ process_webhook_    │
│ sync()       │  │ connections()    │  │ events()            │
│ (service.py) │  │ (scheduler.py)   │  │ (xero.py)           │
└──────┬───────┘  └────────┬─────────┘  └──────────┬──────────┘
       │                   │                       │
       ▼                   ▼                       ▼
┌──────────────────────────────────────────────────────────────┐
│                    run_phased_sync                            │
│                 (Celery orchestrator task)                    │
│                                                              │
│  BLOCKS A WORKER for entire duration (~5-90 minutes)         │
│                                                              │
│  Phase 1: group([accounts, contacts, invoices])              │
│     └─► group_result.get(timeout=1800) ◄── BLOCKING WAIT    │
│  Phase 2: group([bank_txns, payments, credit_notes,          │
│                  overpayments, prepayments])                  │
│     └─► group_result.get(timeout=1800) ◄── BLOCKING WAIT    │
│     └─► Post-sync: quality_score, bas_calc, aggregation      │
│  Phase 3: group([journals, manual_journals, POs,             │
│                  repeating_invoices, tracking, quotes])       │
│     └─► group_result.get(timeout=1800) ◄── BLOCKING WAIT    │
│     └─► Post-sync: insights, triggers                        │
│  Payroll sync (inline, if access)                            │
│  Org profile sync (inline, if full)                          │
│  Finalize job                                                │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                      sync_entity                             │
│               (Celery worker task, 30/m rate)                │
│                                                              │
│  1. Create async session + engine (NEW per call)             │
│  2. SET LOCAL tenant context                                 │
│  3. Update entity progress → commit (tenant context LOST)    │
│  4. Call XeroDataService.sync_<entity>()                     │
│  5. Update entity progress → commit                          │
│  6. Update connection timestamp → commit                     │
│  7. Close session (engine NOT disposed)                      │
└──────────────────────────────────────────────────────────────┘
```

### Key Configuration

| Setting | Value | File:Line |
|---------|-------|-----------|
| `worker_concurrency` | 4 | `celery_app.py:54` |
| `task_time_limit` | 3600s (1h) | `celery_app.py:38` |
| `task_soft_time_limit` | 3300s (55m) | `celery_app.py:39` |
| `task_acks_late` | True | `celery_app.py:40` |
| `task_reject_on_worker_lost` | True | `celery_app.py:41` |
| `phase_timeout_seconds` | 1800s (30m) | `config.py:403` |
| `sync_entity rate_limit` | 30/m | `xero.py:1373` |
| `beat_scheduler` | PersistentScheduler | `celery_app.py:60` |
| `result_expires` | 3600s | `celery_app.py:50` |

### Database Tables (Sync-Specific)

| Table | Purpose | RLS Policy |
|-------|---------|------------|
| `xero_connections` | OAuth tokens, rate limits, per-entity timestamps | `NULLIF(current_setting(..., true), '')::uuid` (safe) |
| `xero_sync_jobs` | Job lifecycle, phase tracking | `NULLIF(current_setting(..., true), '')::uuid` (safe) |
| `xero_sync_entity_progress` | Per-entity status within job | `current_setting(...)::uuid` (**NO missing_ok**) |
| `post_sync_tasks` | Downstream task tracking | `current_setting(...)::uuid` (**NO missing_ok**) |
| `xero_webhook_events` | Webhook deduplication, batching | `current_setting(...)::uuid` (**NO missing_ok**) |

---

## 3. Confirmed Bugs

### Bug 1: Scheduler Missing Required Task Arguments

**Severity**: CRITICAL
**Files**: `scheduler.py:135-138`, `scheduler.py:236-239`

The daily scheduler dispatches `run_phased_sync` without the required `connection_id` and `tenant_id` parameters:

```python
# scheduler.py:135-138 — BROKEN
run_phased_sync.delay(
    job_id=str(job.id),
    sync_type="full",        # ← connection_id MISSING
    force_full=needs_full,   # ← tenant_id MISSING
)
```

The task signature requires these as positional args with no defaults:

```python
# xero.py:1685-1692
def run_phased_sync(
    self: Task,
    job_id: str,
    connection_id: str,   # REQUIRED, no default
    tenant_id: str,        # REQUIRED, no default
    sync_type: str = "full",
    force_full: bool = False,
)
```

Compare with the correct dispatch in the service layer:

```python
# service.py:2464-2472 — CORRECT
self.celery_app.send_task("app.tasks.xero.run_phased_sync", kwargs={
    "job_id": str(job.id),
    "connection_id": str(connection.id),     # ✓
    "tenant_id": str(connection.tenant_id),  # ✓
    "sync_type": sync_type.value,
    "force_full": force_full,
})
```

**Impact**: Every scheduled sync (daily 02:00 UTC) fails with `TypeError`. The job was already created as PENDING in the DB *before* `.delay()` is called (line 128), so the job stays PENDING forever. The next scheduler run sees this PENDING job and skips the connection (line 120-125). **Result: connections become permanently stuck after the first scheduled sync attempt.**

**Fix**: Pass `connection_id` and `tenant_id` to both `.delay()` calls.

---

### Bug 2: Worker Pool Deadlock

**Severity**: HIGH
**Files**: `celery_app.py:54`, `xero.py:1908-1912`

With `worker_concurrency=4`, the orchestrator (`run_phased_sync`) blocks a worker on `group_result.get()`:

```python
# xero.py:1908-1912
with allow_join_result():
    phase_results = group_result.get(
        timeout=settings.xero.phase_timeout_seconds,  # 1800s
        propagate=False,
    )
```

**Deadlock analysis**:

| Concurrent Syncs | Workers as Orchestrators | Workers for Entity Tasks | Phase 2 Entities | Status |
|------------------|--------------------------|--------------------------|------------------|--------|
| 1 | 1 blocked | 3 available | 5 needed | Slow (2 queued) |
| 2 | 2 blocked | 2 available | 10 needed | Very slow |
| 3 | 3 blocked | 1 available | 15 needed | Near-deadlock |
| **4+** | **4 blocked** | **0 available** | 20+ needed | **COMPLETE DEADLOCK** |

The scheduler dispatches ALL stale connections at once (line 110-145), so 4+ stale connections = guaranteed deadlock. With `task_time_limit=3600s`, the deadlocked workers are killed after 1 hour, leaving jobs stuck as `in_progress`.

**Fix**: Replace `group_result.get()` blocking pattern with Celery `chord()` callbacks.

---

### Bug 3: `SET LOCAL` Tenant Context Lost After Commit

**Severity**: HIGH
**Files**: `xero.py:77`, `xero.py:1768-1784`, `xero.py:1445-1469`

`SET LOCAL` is transaction-scoped in PostgreSQL. Every `session.commit()` ends the transaction and clears the setting:

```python
# xero.py:77
await session.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_id}'"))
```

**In `_run_phased_sync_async`**:
- Line 1768: `_set_tenant_context()` — sets context
- Line 1784: `session.commit()` — **context LOST**
- Lines 1872, 1880, 1975, 2122: More commits without re-setting context

**In `_sync_entity_async`**:
- Line 1445: `_set_tenant_context()` — sets context
- Line 1469: `session.commit()` — **context LOST**
- Line 1512: `sync_method(**kwargs)` — XeroDataService queries DB without RLS context
- Lines 1538, 1562: More commits without re-setting context

**RLS policy inconsistency makes this worse**:

The new progressive sync tables (migration `b12cfec71461`) use `current_setting('app.current_tenant_id')::uuid` **without `missing_ok=true`**. When the setting is empty after commit, this casts `''::uuid` which throws a PostgreSQL error:

```sql
-- New tables (xero_sync_entity_progress, post_sync_tasks, xero_webhook_events):
-- CRASHES when tenant context is unset
USING (tenant_id = current_setting('app.current_tenant_id')::uuid)

-- Old tables (xero_connections, xero_sync_jobs, xero_clients, etc.):
-- Returns NULL → silently filters all rows
USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
```

**Impact**: If the DB role enforces RLS, queries on new tables crash after any commit. Queries on old tables silently return zero rows.

**Fix**: Use `SET` (session-scoped, persists across transactions) instead of `SET LOCAL`, or re-set context before every DB operation after a commit.

---

### Bug 4: No Periodic Stale Job Cleanup

**Severity**: HIGH
**Files**: `service.py:2393-2401`, `celery_app.py:102-193`

The only stale job auto-expire logic is inline in `initiate_sync()`, triggered only when a user manually requests a new sync:

```python
# service.py:2393-2401
stale_threshold = datetime.now(UTC) - timedelta(minutes=30)
if existing_job.created_at.replace(tzinfo=UTC) < stale_threshold:
    await self.job_repo.update_status(
        existing_job.id, XeroSyncStatus.FAILED,
        error_message="Auto-expired: job stale for over 30 minutes",
    )
```

There is **no beat schedule entry** for periodic cleanup. No cleanup task exists anywhere in the codebase.

**Permanent stuck-job cascade**:
1. Worker dies or scheduler bug creates a PENDING job
2. Job stays PENDING/IN_PROGRESS forever (no cleanup)
3. Daily scheduler sees existing active job → skips connection (line 120-125)
4. Connection never syncs again until someone manually triggers a sync
5. With Bug 1, this happens to every connection after its first scheduled sync attempt

**Fix**: Add a periodic beat task that expires jobs stuck in PENDING/IN_PROGRESS for >30 minutes.

---

### Bug 5: New Database Engine Created Per Task

**Severity**: MEDIUM
**Files**: `xero.py:60-65`, `scheduler.py:23-31`

```python
# xero.py:60-65
async def _get_async_session() -> AsyncSession:
    settings = get_settings()
    engine = create_async_engine(settings.database.url, echo=False)  # NEW engine every call
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return async_session()
```

Each task invocation creates a brand new `create_async_engine()` with its own connection pool (default `pool_size=5`). During a phased sync: 1 orchestrator + 14 entity tasks = **15 engines = 75 potential DB connections per sync**. Engines are never `dispose()`d — only `session.close()` is called.

**Impact on Railway**: With limited PostgreSQL `max_connections` (typically 20-100 on shared plans), multiple concurrent syncs can exhaust the connection pool, causing `too many connections` errors.

**Fix**: Use a module-level engine singleton with `NullPool` (since each task runs `asyncio.run()` which creates/destroys the event loop).

---

### Bug 6: `task_acks_late` + Orchestrator = Duplicate Work on Crash

**Severity**: HIGH
**Files**: `celery_app.py:40-41`, `xero.py:1867-1912`

```python
# celery_app.py:40-41
task_acks_late=True,
task_reject_on_worker_lost=True,
```

When a worker dies during `group_result.get()`:
1. The orchestrator task is **requeued** (task_reject_on_worker_lost)
2. Child `sync_entity` tasks may have already completed or still be running
3. The requeued orchestrator restarts from scratch:
   - Sets job back to IN_PROGRESS (line 1783)
   - Calls `bulk_create_for_job()` (line 1867) to create entity progress records
   - **CRASH**: Hits unique constraint `uq_xero_sync_entity_progress_job_entity` because records already exist from the first run

There is **no idempotency guard** in the orchestrator — it doesn't check which phases/entities have already completed.

**Fix**: Make the orchestrator idempotent — check existing entity progress records before creating new ones, and skip completed entities.

---

### Bug 7: `asyncio.run()` Compounds Engine/Connection Leak

**Severity**: MEDIUM
**Files**: `xero.py:1720`, `xero.py:1407`, and all task entry points

Every Celery task uses `asyncio.run()` which creates a new event loop and closes it when done. The async engine's connection pool is tied to the event loop that created it. When the loop closes, pool connections become orphaned. This compounds Bug 5's connection leak.

**Fix**: Addressed by the same engine singleton fix as Bug 5 (use `NullPool`).

---

### Bug 8: Scheduler Queries Bypass RLS

**Severity**: LOW-MEDIUM
**Files**: `scheduler.py:82-99`

The `_sync_stale()` function queries `XeroConnection` and `XeroSyncJob` without calling `_set_tenant_context()`. If RLS is enforced on the DB role, these queries return no results and the scheduler finds zero stale connections.

**Impact**: If RLS is enforced, the scheduler silently does nothing. If RLS is not enforced (DB role is table owner/superuser), the scheduler sees all tenants' data, which is acceptable for a system-level scheduler.

**Fix**: Either ensure the scheduler's DB role bypasses RLS (preferred for system tasks), or query without RLS and set context per-connection when dispatching.

---

## 4. Additional Failure Modes

### 4.1 OAuth Token Refresh Race Condition (HIGH)

**Files**: `service.py:636-714`, `service.py:801-814`, `client.py:139`

When multiple `sync_entity` tasks run in parallel for the same connection, each calls `_ensure_valid_token()` independently at every pagination loop iteration (service.py:889). Xero uses **single-use rotating refresh tokens** (noted at client.py:139) — when you refresh, the old refresh token is invalidated by Xero.

**Race scenario** (Phase 1: 3 tasks, Phase 2: 5 tasks in parallel):
1. Token expires during Phase 1 (Xero tokens last 30 minutes, syncs take 10+ minutes)
2. All 3 tasks see `connection.needs_refresh=True` (model property at line 880-885, true when token expires within 5 minutes)
3. Task A reads `refresh_token_1` from DB, calls Xero OAuth, gets `access_token_2` + `refresh_token_2`, stores in DB. Xero invalidates `refresh_token_1`.
4. Task B reads `refresh_token_1` from DB (from its own stale session), calls Xero OAuth with the **invalidated** token.
5. Xero returns `invalid_grant`. Task B's error handler (service.py:668-673) marks connection as `NEEDS_REAUTH`.
6. **All concurrent and future tasks for this connection now fail.** User must manually re-authorize.

There is **NO locking mechanism** — no Redis lock, no database advisory lock, no `SELECT FOR UPDATE`. Each `sync_entity` task creates its own separate DB session via `_get_async_session()`, so they can't share a session-level lock.

**Fix**: Implement distributed locking for token refresh (Redis lock with connection_id as key), or pre-refresh the token in the orchestrator before dispatching entity tasks.

### 4.2 Rate Limiter Not Shared Across Concurrent Tasks (LOW-MEDIUM)

**Files**: `rate_limiter.py:49-164`, `service.py:816-858`

The `XeroRateLimiter` is a stateless in-memory utility. Each `sync_entity` task creates its own `XeroDataService` (xero.py:1496) with its own rate limiter. Rate limit values are stored on `XeroConnection` model columns but each task reads/writes them independently:

1. Task A reads `minute_remaining=10`, makes API calls, writes `minute_remaining=5`
2. Task B reads `minute_remaining=10` (before A's commit), makes API calls, writes `minute_remaining=5`
3. **Actual** remaining: 0. DB says 5. Next requests will get 429s.

**Mitigating factor**: Xero's actual rate limiting is server-side. The local tracking is advisory. The `MINUTE_SAFETY_MARGIN=5` (rate_limiter.py:70) helps but is insufficient with 3-5 concurrent tasks. When we exceed the limit, Xero returns 429 and the task retries with backoff — so this degrades performance but doesn't cause data loss.

**Fix**: Use Redis-based rate limiting with atomic `DECR` + `EXPIRE` shared across all workers.

### 4.3 Celery Beat PersistentScheduler on Railway (HIGH)

**Files**: `celery_app.py:60`

```python
beat_scheduler="celery.beat:PersistentScheduler"
```

`PersistentScheduler` writes schedule state to a `celerybeat-schedule` file on the local filesystem. Railway containers are **ephemeral** — this file is lost on every deploy or restart. The beat schedule has **15+ periodic tasks** (celery_app.py:102-193).

**Impact on every deploy**:
- Beat loses track of when tasks last ran
- All periodic tasks fire immediately because beat thinks they're overdue
- **Thundering herd**: `sync_all_stale_connections`, `check_lodgement_deadlines`, `ingest_knowledge_weekly`, `generate_insights_daily`, and ALL other periodic tasks trigger simultaneously
- Combined with Bug 2 (worker deadlock), the thundering herd of sync tasks deadlocks the worker pool

**Specific deploy timing risks**:
- Deploy at 1:55am UTC → container restarts at 2:05am → daily sync job **missed entirely**
- Deploy at 2:01am UTC → sync fires before deploy AND after restart with no schedule state → **double execution**

**Fix**: Use `redbeat` (`RedBeatSchedulerEntry`) to store schedule in Redis. RedBeat also supports distributed locking so multiple beat instances don't double-fire.

```python
celery_app.conf.update(
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=celery_settings.broker_url,
)
```

### 4.4 Redis Pub/Sub Failures Are Silent (LOW)

**Files**: `sync_progress.py:57-67`

Redis pub/sub failures in `_publish()` are caught and logged but don't affect the sync. This is correct for non-critical progress events. The frontend SSE stream will miss updates (degraded UX but not data loss).

**However**: If the Celery **broker** (also Redis) goes down, all in-flight tasks fail. With `task_acks_late=True`, tasks are requeued when the broker recovers — but any task mid-execution will be re-executed, potentially causing duplicate syncs.

### 4.5 No Heartbeat or Liveness Detection for Running Jobs (MEDIUM)

There is no mechanism to detect if a job in `in_progress` is actually still running vs. its worker silently died. If a Railway container is killed (OOM, deploy, health check failure), the task may not be properly cleaned up. The only backstop is Celery's `task_time_limit=3600s`, which kills the worker process — but this only works if the worker is still running.

**Fix**: Implement a heartbeat mechanism — running tasks periodically update a `last_heartbeat_at` timestamp. A cleanup task checks for jobs whose heartbeat is stale (>15 minutes).

### 4.6 Webhook Processing Issues (HIGH)

**Files**: `xero.py:2787-2988`

Multiple issues in `process_webhook_events`:

**a) No RLS context for initial query** (xero.py:2832-2844): `webhook_repo.get_all_pending()` queries `xero_webhook_events` without calling `_set_tenant_context`. This table's RLS policy uses `current_setting('app.current_tenant_id')::uuid` **without `missing_ok`** — so the query will **crash** if RLS is enforced.

**b) Events marked processed before dispatch** (xero.py:2900-2908): Events are marked as `processed` and committed at line 2905 **BEFORE** the `sync_entity` task is dispatched at line 2908. If the Celery `send_task` call fails (e.g., broker down), events are permanently lost — marked as processed but no sync runs.

**c) No active sync check**: Creates new sync jobs (line 2879-2885) without checking if a sync is already in progress for that connection. Two concurrent syncs for the same connection causes token refresh races (4.1) and rate limit overshooting (4.2).

**Fix**: Dispatch task first, then mark events as processed. Check for active sync jobs before creating new ones. Add RLS bypass for system-level queries.

### 4.7 Bulk Import Task Issues (MEDIUM-HIGH)

**Files**: `xero.py:2464-2779`

Multiple issues in `run_bulk_xero_import`:

**a) Blocking `time.sleep(2)` at line 2689**: Synchronous sleep in an `asyncio.run()` context blocks the event loop. Should be `await asyncio.sleep(2)`.

**b) SET LOCAL lost after commits**: Same as Bug 3. `_set_tenant_context` called once at line 2524, but `session.commit()` at lines 2539, 2558, 2573, 2586, 2602, 2651, 2686 all clear it.

**c) No idempotency**: If worker dies mid-bulk-import and task is requeued, the requeued task re-processes ALL orgs including already-completed ones.

**d) Long-running single task**: Processes ALL orgs sequentially. 50 orgs at 2+ minutes each = 100+ minutes. May exceed `task_time_limit=3600s` for large imports.

**e) No sync job conflict check**: Creates sync jobs without checking if one already exists (line 2596-2602), unlike `initiate_sync` which checks.

### 4.8 TOCTOU Race: Concurrent Sync Protection (MEDIUM)

**Files**: `service.py:2390-2403`, `scheduler.py:113-125`

Between checking for an existing job and creating a new one, there's a time-of-check-time-of-use window. If a user clicks "Sync" at almost the same time the scheduler runs, both paths create jobs and dispatch syncs. Two full phased syncs running concurrently for the same connection share the same OAuth token (amplifying 4.1), consume rate limits 2x as fast, and dispatch duplicate post-sync tasks.

**Fix**: Use database advisory locks or `SELECT ... FOR UPDATE` when creating sync jobs.

### 4.9 Database Connection Drop During Sync (MEDIUM)

If PostgreSQL drops during a sync, the error handler in `_run_phased_sync_async` (xero.py:2198-2206) tries to update the job status to FAILED **using the same broken session**. This second DB operation also fails silently. The job stays stuck in `IN_PROGRESS` permanently.

Similarly in `_sync_entity_async` (xero.py:1627-1662), the error handler's DB update fails on the broken session.

The engine-per-task pattern (Bug 5) means there's no connection pooling with keep-alive or health checks (`pool_pre_ping=False` by default).

**Fix**: Create a fresh session in error handlers, or use the stale job cleanup task as a backstop. Enable `pool_pre_ping=True` on the engine.

### 4.10 Potential UnboundLocalError in Finally Blocks (LOW)

**Files**: `xero.py:1674-1676`, `xero.py:2235-2237`

If `_get_async_session()` raises (DB connection refused, DNS failure), `session` is never assigned. The `finally` block will raise `UnboundLocalError` on `await session.close()`. Same risk for `publisher`.

**Fix**: Initialize `session = None` and `publisher = None` before the try block, and check for None in finally.

---

## 5. Root Cause Patterns

Five systemic patterns underlie all the bugs:

### Pattern 1: Synchronous Orchestration in Async Workers

The `run_phased_sync` orchestrator blocks a worker to coordinate child tasks via `group_result.get()`. This is fundamentally at odds with Celery's concurrent worker model. **Every blocked orchestrator reduces the available worker pool by 25%** (with 4 workers).

### Pattern 2: Transaction-Scoped State in Long-Running Processes

Using `SET LOCAL` (transaction-scoped) for tenant context in tasks that make multiple commits creates a fragile state management pattern. Any commit invalidates the context, and the code doesn't re-establish it.

### Pattern 3: No Resource Lifecycle Management

Database engines, connections, and event loops are created per-task but never properly disposed. In a constrained Railway environment, this leads to resource exhaustion.

### Pattern 4: No Self-Healing Mechanisms

There's no periodic cleanup, no heartbeat detection, no automatic recovery from stuck states. The system relies entirely on human intervention to recover from failures.

### Pattern 5: Missing Integration Testing of Task Dispatch

The scheduler bug (missing args) would have been caught by any integration test that actually dispatched the task. The fact that it shipped suggests task dispatch paths aren't covered by tests.

---

## 6. Proposed Architecture

### 6.1 Replace Blocking Orchestrator with Chord/Callback Pattern

**Current**: `run_phased_sync` blocks a worker waiting for child tasks via `group_result.get()`.
**Proposed**: Use Celery `chord()` with phase callbacks that chain to the next phase. The orchestrator uses `self.replace()` to release its worker immediately.

#### Architecture

```
┌──────────────────────┐
│ start_phased_sync()  │ ← Lightweight task, creates job, pre-refreshes token
│ (uses self.replace)  │    then replaces itself with the Phase 1 chord
└────────┬─────────────┘    Worker is FREED immediately
         │
         ▼
┌──────────────────────────────────────┐
│ chord(                               │
│   group([                            │
│     sync_entity("accounts"),         │
│     sync_entity("contacts"),         │
│     sync_entity("invoices"),         │
│   ]),                                │
│   on_phase_complete.s(job_id, 1)     │  ← Callback fires when ALL complete
│ )                                    │
└──────────────────────────────────────┘
         │
         ▼  (callback fires automatically — uses only 1 worker briefly)
┌──────────────────────────────────────┐
│ on_phase_complete(results, job_id, 1)│
│   - Aggregate phase 1 results        │
│   - Dispatch post-sync tasks         │
│   - Dispatch phase 2 chord           │
└──────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│ chord(                               │
│   group([                            │
│     sync_entity("bank_transactions"),│
│     sync_entity("payments"),         │
│     sync_entity("credit_notes"),     │
│     sync_entity("overpayments"),     │
│     sync_entity("prepayments"),      │
│   ]),                                │
│   on_phase_complete.s(job_id, 2)     │
│ )                                    │
└──────────────────────────────────────┘
         │
         ▼  ... Phase 3 chord ...
         │
         ▼
┌──────────────────────────────────────┐
│ finalize_sync(job_id)                │
│   - Payroll sync (inline)            │
│   - Org profile sync (inline)        │
│   - Set final job status             │
│   - Publish sync_complete event      │
│   - Emit audit event                 │
└──────────────────────────────────────┘
```

#### Code Pattern

```python
from celery import chord

@celery_app.task(bind=True, name="app.tasks.xero.start_phased_sync")
def start_phased_sync(self, job_id, connection_id, tenant_id, sync_type="full", force_full=False):
    """Lightweight orchestrator that replaces itself with a chord workflow.

    Uses self.replace() to free the worker immediately.
    The chord callback pattern chains phases automatically.
    """
    import asyncio
    # 1. Update job status to IN_PROGRESS
    # 2. Pre-refresh token if needed (prevents race in child tasks)
    # 3. Create entity progress records for phase 1
    asyncio.run(_init_phased_sync(job_id, connection_id, tenant_id, force_full))

    # 4. Build phase 1 chord and replace this task with it
    phase_1_entities = SYNC_PHASES[1]
    workflow = chord(
        [sync_entity.s(
            job_id=job_id, entity_type=e, connection_id=connection_id,
            tenant_id=tenant_id, force_full=force_full,
        ) for e in phase_1_entities],
        on_phase_complete.s(job_id=job_id, phase=1, connection_id=connection_id,
                            tenant_id=tenant_id, sync_type=sync_type, force_full=force_full),
    )
    raise self.replace(workflow)  # Worker is freed!


@celery_app.task(bind=True, name="app.tasks.xero.on_phase_complete")
def on_phase_complete(self, phase_results, job_id, phase, connection_id, tenant_id,
                      sync_type="full", force_full=False):
    """Chord callback: aggregate results, dispatch next phase or finalize."""
    import asyncio

    # 1. Aggregate results from completed phase
    # 2. Update job progress in DB
    # 3. Dispatch post-sync tasks for this phase
    asyncio.run(_process_phase_results(phase_results, job_id, phase, connection_id, tenant_id))

    next_phase = phase + 1
    if next_phase <= TOTAL_SYNC_PHASES:
        # Create entity progress records for next phase and dispatch chord
        asyncio.run(_init_phase(job_id, tenant_id, next_phase))
        phase_entities = SYNC_PHASES[next_phase]
        workflow = chord(
            [sync_entity.s(
                job_id=job_id, entity_type=e, connection_id=connection_id,
                tenant_id=tenant_id, force_full=force_full,
            ) for e in phase_entities],
            on_phase_complete.s(job_id=job_id, phase=next_phase, connection_id=connection_id,
                                tenant_id=tenant_id, sync_type=sync_type, force_full=force_full),
        )
        raise self.replace(workflow)
    else:
        # All phases done — finalize
        asyncio.run(_finalize_sync(job_id, connection_id, tenant_id, sync_type))
```

#### Alternative: Polling Pattern (Most Resilient Fallback)

If chord reliability is a concern with the Redis backend, a polling pattern can be used as a fallback:

```python
@celery_app.task(bind=True, max_retries=None)
def monitor_sync_phase(self, job_id, phase):
    """Polls DB for entity completion, dispatches next phase when ready."""
    progress = db.get_entity_progress_for_phase(job_id, phase)
    if all(p.status in ('completed', 'failed') for p in progress):
        dispatch_next_phase_or_finalize(job_id, phase)
        return
    # Re-check in 10 seconds
    raise self.retry(countdown=10)
```

#### Benefits

- **Zero workers blocked** as orchestrators — all 4 workers available for entity tasks
- No `allow_join_result()` hack needed
- Natural error propagation via chord error callbacks (`link_error`)
- **No deadlock possible** regardless of concurrent sync count
- `self.replace()` means the orchestrator worker is freed immediately
- With Redis backend, chord synchronization uses an atomic counter (efficient)

### 6.2 Fix Tenant Context Management

**Key insight from research**: `SET LOCAL` IS the correct choice for multi-tenant safety (it auto-reverts on rollback, preventing tenant context leaking to the next task via connection pooling). The problem is that the current code only sets it once and doesn't re-set it after commits.

**Two-pronged fix**:

#### A) Tenant-Aware Session Wrapper

Create a session wrapper that automatically re-establishes `SET LOCAL` at the start of each transaction:

```python
class TenantAwareSession:
    """Wraps AsyncSession to auto-set RLS context on each transaction."""

    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self._session = session
        self._tenant_id = tenant_id

    async def _ensure_tenant_context(self):
        """Set tenant context for the current transaction."""
        await self._session.execute(
            text(f"SET LOCAL app.current_tenant_id = '{self._tenant_id}'")
        )

    async def commit(self):
        """Commit and re-establish tenant context for next transaction."""
        await self._session.commit()
        await self._ensure_tenant_context()

    async def __aenter__(self):
        await self._ensure_tenant_context()
        return self

    async def __aexit__(self, *args):
        await self._session.close()

    # Delegate all other methods to the underlying session
    def __getattr__(self, name):
        return getattr(self._session, name)
```

Usage in tasks:

```python
async def _sync_entity_async(task, job_id, entity_type, connection_id, tenant_id, ...):
    session = await _get_async_session()
    async with TenantAwareSession(session, tenant_id) as tsession:
        # Every commit automatically re-sets SET LOCAL
        progress_repo = XeroSyncEntityProgressRepository(tsession)
        await progress_repo.update_status(...)
        await tsession.commit()  # Tenant context is re-set automatically

        data_service = XeroDataService(tsession, settings)
        result = await data_service.sync_contacts(...)  # RLS context is active
```

#### B) Fix RLS Policies on New Tables

Add `missing_ok=true` and `NULLIF` for consistency with older tables. New Alembic migration:

```sql
-- Fix: add missing_ok and NULLIF for consistency
-- xero_sync_entity_progress, post_sync_tasks, xero_webhook_events
DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};
CREATE POLICY {table}_tenant_isolation ON {table}
USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
```

**Why NOT `SET` (session-scoped)**: Using `SET` (without `LOCAL`) persists across transactions. If a Celery worker reuses the same DB connection for a different tenant's task, the stale tenant_id leaks. `SET LOCAL` auto-reverts on rollback/commit, making it safe for connection pooling. The tradeoff is needing to re-set after commits, which the `TenantAwareSession` wrapper handles automatically.

### 6.3 Module-Level Engine with NullPool + Worker Init

```python
# xero.py — module-level singleton, initialized after worker fork
from sqlalchemy.pool import NullPool
from celery.signals import worker_process_init

_engine = None
_session_factory = None

@worker_process_init.connect
def _init_db_engine(**kwargs):
    """Initialize DB engine after Celery worker forks.

    Using worker_process_init ensures each forked worker process gets its
    own engine instance, avoiding sharing across forks (which causes issues).
    NullPool is used because each task runs asyncio.run() with a fresh event
    loop — connection pools are tied to event loops, so pooling would cause
    orphaned connections.
    """
    global _engine, _session_factory
    settings = get_settings()
    _engine = create_async_engine(
        settings.database.url,
        echo=False,
        poolclass=NullPool,
        pool_pre_ping=True,  # Detect stale connections before use
    )
    _session_factory = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def _get_async_session() -> AsyncSession:
    """Create an async database session for tasks.

    Uses the worker-level engine singleton instead of creating a new engine
    per call. Falls back to creating a new engine if called outside a worker
    (e.g., in tests).
    """
    global _engine, _session_factory
    if _session_factory is None:
        # Fallback for non-worker contexts (tests, scripts)
        settings = get_settings()
        _engine = create_async_engine(
            settings.database.url, echo=False, poolclass=NullPool, pool_pre_ping=True,
        )
        _session_factory = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    return _session_factory()
```

**Why `NullPool`**: Each Celery task runs `asyncio.run()` which creates a new event loop. Connection pools are tied to event loops. `NullPool` avoids pooling entirely — each task gets a fresh connection that's properly closed when the session closes. This prevents the orphaned connection leak.

**Why `worker_process_init`**: Celery's prefork model creates child processes. `worker_process_init` fires in each child after fork, ensuring the engine is created in the correct process (not inherited from the parent). This is the SQLAlchemy-recommended pattern for Celery workers.

**Why `pool_pre_ping=True`**: Detects stale database connections before use, preventing errors after Railway PostgreSQL restarts or brief network interruptions.

### 6.4 Stale Job Cleanup Beat Task

```python
# Add to celery_app.py beat_schedule:
"cleanup-stale-sync-jobs": {
    "task": "app.tasks.scheduler.cleanup_stale_sync_jobs",
    "schedule": crontab(minute="*/15"),  # Every 15 minutes
    "options": {"queue": celery_settings.task_default_queue},
},
```

```python
# scheduler.py — new task
STALE_JOB_THRESHOLD_MINUTES = 45  # Jobs older than 45 min are stale

@celery_app.task(name="app.tasks.scheduler.cleanup_stale_sync_jobs", bind=True)
def cleanup_stale_sync_jobs(self) -> dict:
    """Expire sync jobs stuck in PENDING or IN_PROGRESS for too long."""
    import asyncio

    async def _cleanup():
        session = await _get_async_session()
        try:
            threshold = datetime.now(UTC) - timedelta(minutes=STALE_JOB_THRESHOLD_MINUTES)
            result = await session.execute(
                text("""
                    UPDATE xero_sync_jobs
                    SET status = 'failed',
                        error_message = 'Auto-expired: job stale for over 45 minutes',
                        completed_at = NOW()
                    WHERE status IN ('pending', 'in_progress')
                    AND created_at < :threshold
                    RETURNING id
                """).bindparams(threshold=threshold)
            )
            expired_ids = [str(row[0]) for row in result.fetchall()]
            await session.commit()

            return {
                "expired_count": len(expired_ids),
                "expired_job_ids": expired_ids,
                "checked_at": datetime.now(UTC).isoformat(),
            }
        finally:
            await session.close()

    return asyncio.run(_cleanup())
```

### 6.5 Idempotent Orchestrator

Make `start_sync` and `on_phase_complete` idempotent so they can safely re-run after worker crashes:

```python
async def _get_or_create_entity_progress(progress_repo, job_id, tenant_id, entity_types):
    """Create entity progress records only if they don't already exist."""
    existing = await progress_repo.get_by_job_id(job_id)
    existing_types = {ep.entity_type for ep in existing}
    new_types = [et for et in entity_types if et not in existing_types]
    if new_types:
        await progress_repo.bulk_create_for_job(job_id, tenant_id, new_types)
    return existing
```

### 6.6 Distributed Token Refresh Lock

```python
import redis.asyncio as redis

async def ensure_valid_token_with_lock(
    session: AsyncSession,
    connection_id: UUID,
    encryption: TokenEncryption,
    settings: Settings,
) -> str:
    """Refresh token with distributed lock to prevent races."""
    r = redis.from_url(settings.redis.url)
    lock_key = f"xero_token_refresh:{connection_id}"

    try:
        async with r.lock(lock_key, timeout=30, blocking_timeout=10):
            # Re-read connection inside lock (may have been refreshed by another task)
            conn_repo = XeroConnectionRepository(session)
            connection = await conn_repo.get_by_id(connection_id)

            if connection.needs_refresh:
                # Perform refresh
                conn_service = XeroConnectionService(session, settings)
                connection = await conn_service.refresh_tokens(connection_id)

            return encryption.decrypt(connection.access_token)
    finally:
        await r.close()
```

### 6.7 Redis-Based Rate Limiting

Replace the in-memory rate limiter with Redis atomic operations for coordination across workers:

```python
async def check_and_decrement_rate_limit(
    redis_client: redis.Redis,
    xero_tenant_id: str,
) -> bool:
    """Atomically check and decrement rate limit counter.

    Uses Redis DECR with TTL for minute-level rate limiting.
    """
    key = f"xero_rate_limit:{xero_tenant_id}:minute"
    pipe = redis_client.pipeline()
    pipe.decr(key)
    pipe.ttl(key)
    results = await pipe.execute()

    current = results[0]
    ttl = results[1]

    # Initialize on first use (60 requests per minute)
    if ttl == -1:
        await redis_client.expire(key, 60)

    if current < 0:
        # Over limit — revert and signal caller to wait
        await redis_client.incr(key)
        return False

    return True
```

### 6.8 Fix Scheduler Dispatch

```python
# scheduler.py:135-139 — FIXED
run_phased_sync.delay(
    job_id=str(job.id),
    connection_id=str(connection.id),    # ← ADD
    tenant_id=str(connection.tenant_id), # ← ADD
    sync_type="full",
    force_full=needs_full,
)
```

### 6.9 Switch to RedBeat for Beat Scheduler

```python
# celery_app.py — replace PersistentScheduler
celery_app.conf.update(
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=celery_settings.broker_url,
)
```

This stores the beat schedule in Redis instead of the filesystem, surviving Railway container restarts.

---

## 7. Implementation Plan

### Priority 1 — Critical Fixes (deploy ASAP)

These can be deployed immediately with minimal risk. **Unblocks all scheduled syncs.**

| # | Fix | Effort | Risk | Files |
|---|-----|--------|------|-------|
| P1.1 | Fix scheduler missing `connection_id`/`tenant_id` args | 5 min | Very Low | `scheduler.py:135-138`, `scheduler.py:236-239` |
| P1.2 | Add stale job cleanup beat task (every 15 min) | 30 min | Low | `scheduler.py`, `celery_app.py` |
| P1.3 | Create `TenantAwareSession` wrapper, replace `_set_tenant_context` | 1 hour | Low | `xero.py` (new helper + update all task functions) |
| P1.4 | Fix RLS policies on new tables (add `missing_ok=true`) | 20 min | Low | New Alembic migration |
| P1.5 | Initialize `session=None`/`publisher=None` before try blocks | 10 min | Very Low | `xero.py:1441-1444`, `xero.py:1756-1758` |

**Estimated time**: 2-3 hours including testing

### Priority 2 — High-Impact Architecture Fixes (next sprint)

These eliminate the deadlock and resource exhaustion issues. **Makes syncs actually reliable.**

| # | Fix | Effort | Risk | Files |
|---|-----|--------|------|-------|
| P2.1 | Replace blocking orchestrator with `chord` + `self.replace()` pattern | 4-6 hours | Medium | `xero.py` (major refactor of `run_phased_sync`) |
| P2.2 | Module-level engine with `NullPool` + `worker_process_init` | 30 min | Low | `xero.py`, `scheduler.py` |
| P2.3 | Make orchestrator idempotent (check existing progress before creating) | 1-2 hours | Low | `xero.py` |
| P2.4 | Distributed token refresh lock (Redis lock per connection_id) | 1-2 hours | Low | `service.py` |
| P2.5 | Pre-refresh token in orchestrator before dispatching entity tasks | 30 min | Very Low | `xero.py` (new `start_phased_sync`) |
| P2.6 | Fix webhook event dispatch ordering (dispatch before marking processed) | 30 min | Low | `xero.py:2900-2908` |

**Estimated time**: 1-2 days including testing

### Priority 3 — Hardening (following sprint)

These improve resilience and observability for production-grade reliability.

| # | Fix | Effort | Risk | Files |
|---|-----|--------|------|-------|
| P3.1 | Switch to RedBeat scheduler (Redis-backed beat) | 1 hour | Low | `celery_app.py`, `requirements.txt` |
| P3.2 | Redis-based rate limiting (atomic `DECR`/`EXPIRE`) | 2-3 hours | Low | `rate_limiter.py`, `service.py` |
| P3.3 | Job heartbeat mechanism + liveness detector | 2-3 hours | Low | New model field, cleanup task |
| P3.4 | Webhook-during-sync protection (check active jobs) | 1-2 hours | Low | `xero.py` webhook task |
| P3.5 | TOCTOU sync protection (advisory lock on job creation) | 1-2 hours | Low | `service.py`, `scheduler.py` |
| P3.6 | Fix bulk import issues (`asyncio.sleep`, idempotency, context) | 2-3 hours | Low | `xero.py` bulk import task |
| P3.7 | Monitoring health endpoint + structured logging | 2-3 hours | Low | `router.py`, all task files |
| P3.8 | Fresh session in error handlers (for DB drop recovery) | 1 hour | Low | `xero.py` error paths |

**Estimated time**: 2-3 days including testing

### Deployment Order

```
Deploy 1 (Priority 1) — Unblocks scheduled syncs
  └── P1.1 + P1.2 + P1.3 + P1.4 + P1.5
  └── Run: manually trigger sync for each connection to verify
  └── Monitor: check that 02:00 UTC scheduler succeeds next day

Deploy 2 (Priority 2) — Eliminates deadlock and races
  └── P2.1 + P2.2 + P2.3 + P2.4 + P2.5 + P2.6
  └── Run: trigger concurrent syncs for 4+ connections
  └── Monitor: verify no worker deadlocks, no stuck jobs

Deploy 3 (Priority 3) — Production hardening
  └── P3.1 through P3.8
  └── Run: chaos tests (kill worker mid-sync, Redis disconnect)
  └── Monitor: health endpoint, alerting thresholds
```

---

## 8. Monitoring & Observability

### 8.1 Key Metrics to Track

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| Jobs stuck in PENDING > 30 min | DB query on `xero_sync_jobs` | Any count > 0 |
| Jobs stuck in IN_PROGRESS > 60 min | DB query on `xero_sync_jobs` | Any count > 0 |
| Sync job failure rate | `xero_sync_jobs` status=failed / total | > 20% in 24h |
| Average sync duration | `xero_sync_jobs` completed_at - started_at | > 30 minutes |
| Entity sync failure rate | `xero_sync_entity_progress` | > 10% per entity type |
| Stale connections (> 48h since sync) | `xero_connections.last_full_sync_at` | Any count > 0 |
| Celery worker queue depth | Redis `LLEN` on queue | > 50 tasks |
| PostgreSQL active connections | `pg_stat_activity` | > 80% of max_connections |
| Redis memory usage | `INFO memory` | > 80% of max |
| Token refresh failures | Logs / error counts | Any in 1h |

### 8.2 Health Check Endpoint

Add a `/integrations/xero/health/sync` endpoint that returns:

```json
{
  "status": "degraded",
  "checks": {
    "stuck_jobs": {"count": 2, "oldest_minutes": 47, "status": "fail"},
    "stale_connections": {"count": 1, "oldest_hours": 52, "status": "warn"},
    "worker_queue_depth": {"value": 3, "status": "ok"},
    "db_connections": {"active": 12, "max": 100, "status": "ok"},
    "last_successful_sync": {"minutes_ago": 15, "status": "ok"}
  }
}
```

### 8.3 Structured Logging

Ensure all sync tasks emit structured log entries with consistent fields:

```python
logger.info("sync_event", extra={
    "event": "entity_sync_completed",
    "job_id": str(job_id),
    "connection_id": str(connection_id),
    "tenant_id": str(tenant_id),
    "entity_type": entity_type,
    "duration_ms": duration_ms,
    "records_processed": result.records_processed,
    "records_created": result.records_created,
    "phase": phase_num,
})
```

Railway logs can then be filtered/aggregated on these fields for dashboards.

---

## 9. Testing Strategy

### 9.1 Unit Tests (Priority 1 fixes)

| Test | What it verifies |
|------|------------------|
| `test_scheduler_passes_all_required_args` | `run_phased_sync.delay()` receives connection_id and tenant_id |
| `test_stale_job_cleanup_expires_old_jobs` | Jobs older than threshold are marked FAILED |
| `test_stale_job_cleanup_ignores_recent_jobs` | Jobs within threshold are not touched |
| `test_tenant_context_survives_commit` | RLS context is maintained after session.commit() |
| `test_rls_policy_handles_missing_tenant` | New table RLS doesn't crash when tenant is unset |

### 9.2 Integration Tests (Priority 2)

| Test | What it verifies |
|------|------------------|
| `test_chord_phase_execution` | Phase 1 entities complete → phase 2 dispatches automatically |
| `test_chord_error_handling` | Entity failure in a phase doesn't crash the entire sync |
| `test_concurrent_syncs_no_deadlock` | 4+ concurrent syncs complete within timeout |
| `test_idempotent_orchestrator_rerun` | Restarted orchestrator picks up where it left off |
| `test_token_refresh_lock_prevents_race` | Only one task refreshes the token under concurrent access |

### 9.3 Chaos Tests (Priority 3)

| Test | What it verifies |
|------|------------------|
| `test_worker_kill_during_sync` | Job eventually reaches terminal state after worker death |
| `test_redis_disconnect_during_sync` | Sync completes even if Redis pub/sub fails |
| `test_db_disconnect_during_entity_sync` | Entity is marked FAILED, job continues with other entities |
| `test_xero_429_during_parallel_entities` | Rate-limited entities retry without breaking the phase |

### 9.4 Smoke Tests for Railway

Run after every deploy:

```bash
# 1. Trigger a sync for a test connection
curl -X POST /api/integrations/xero/sync \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"connection_id": "$TEST_CONN_ID"}'

# 2. Poll status until complete or timeout (5 minutes)
# 3. Verify job status is COMPLETED
# 4. Verify entity progress records exist for all 14 entity types
# 5. Verify no stuck jobs in DB
```

---

## Appendix A: File Reference

| File | Lines | Purpose |
|------|-------|---------|
| `backend/app/tasks/xero.py` | ~2988 | Celery task orchestration |
| `backend/app/tasks/scheduler.py` | ~267 | Periodic sync scheduling |
| `backend/app/tasks/celery_app.py` | ~194 | Celery configuration + beat schedule |
| `backend/app/tasks/reports.py` | ~360 | Report sync tasks |
| `backend/app/modules/integrations/xero/service.py` | ~5706 | Business logic |
| `backend/app/modules/integrations/xero/repository.py` | ~4507 | Database access |
| `backend/app/modules/integrations/xero/models.py` | ~4571 | SQLAlchemy models |
| `backend/app/modules/integrations/xero/router.py` | ~4792 | API endpoints |
| `backend/app/modules/integrations/xero/client.py` | ~1704 | Xero HTTP client |
| `backend/app/modules/integrations/xero/rate_limiter.py` | ~231 | Rate limit tracking |
| `backend/app/modules/integrations/xero/sync_progress.py` | ~262 | Redis pub/sub progress |
| `backend/app/modules/integrations/xero/webhook_handler.py` | ~295 | Webhook processing |
| `backend/app/modules/integrations/xero/encryption.py` | ~144 | Token encryption |
| `backend/app/config.py` | - | Settings (XeroSettings, CelerySettings) |

## Appendix B: Xero API Constraints

| Constraint | Value | Impact |
|------------|-------|--------|
| Rate limit (per org/min) | 60 requests | Parallel entity syncs must coordinate |
| Rate limit (per org/day) | 5,000 requests | Large orgs with many entities risk hitting daily limit |
| Refresh token lifetime | Single-use | Cannot be used concurrently by multiple tasks |
| Access token lifetime | 30 minutes | Must refresh during long syncs |
| Webhook delivery | At-least-once | Must deduplicate events |
| API timeout | 30 seconds | Large responses (e.g., invoices) may time out |
