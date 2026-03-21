# Quickstart: Progressive Xero Data Sync

**Feature**: 043-progressive-xero-sync
**Date**: 2026-02-14

## Overview

This feature transforms the Xero data sync from a blocking, sequential operation into a non-blocking, phased background process with real-time progress updates, multi-client parallel sync, and expanded incremental sync support.

## Key Changes

### Backend

1. **Phased sync orchestration** — `run_sync` refactored from single monolithic task to Celery chain of phases. Each phase dispatches entity sync tasks in parallel using Celery groups.

2. **Per-entity Celery tasks** — Each entity type syncs in its own Celery task with isolated DB session. Failure in one entity doesn't cascade to others.

3. **SSE endpoint** — New `GET /api/v1/xero/connections/{id}/sync/stream` provides real-time progress via Server-Sent Events. Backend publishes events to Redis pub/sub, SSE endpoint subscribes and streams to client.

4. **Expanded If-Modified-Since** — 6 additional entity types now support incremental sync: credit notes, payments, overpayments, prepayments, journals, manual journals.

5. **Multi-client sync** — New `POST /api/v1/xero/sync/all` endpoint queues sync for all active connections with rate-limit-aware scheduling.

6. **Post-sync pipeline tracking** — New `PostSyncTask` model tracks execution of downstream tasks (quality score, BAS calc, aggregation, insights, triggers).

7. **Webhook receiver** (Phase 3) — New endpoint for Xero webhook events with HMAC verification and event batching.

### Frontend

1. **Non-blocking sync** — Sync triggers a background job and shows a toast notification. User is not blocked.

2. **SSE-powered progress** — `useEventSource` hook subscribes to SSE stream for real-time per-entity progress updates.

3. **Sync notification badges** — Bell icon shows active sync count. Toast on completion with summary.

4. **Multi-client sync dashboard** — "Sync All" button with aggregate progress indicator on clients page.

5. **Data freshness indicators** — Client cards show "last synced X ago" with stale data warnings.

## Architecture

```
User triggers sync
       │
       ▼
  POST /sync → 202 Accepted
       │
       ▼
  Celery: run_phased_sync (orchestrator)
       │
       ├── Phase 1 (Essential): group(accounts, contacts, recent_invoices)
       │     │
       │     ├── on_complete → post_sync_phase1(quality_score)
       │     └── Redis pub/sub → SSE stream → Frontend
       │
       ├── Phase 2 (Recent): group(bank_txns, payments, credit_notes, ...)
       │     │
       │     ├── on_complete → post_sync_phase2(bas_calc, aggregation)
       │     └── Redis pub/sub → SSE stream → Frontend
       │
       └── Phase 3 (Full): group(purchase_orders, quotes, historical, ...)
             │
             ├── on_complete → post_sync_phase3(insights, triggers)
             └── Redis pub/sub → SSE stream → Frontend
```

## Files to Modify/Create

### Backend — Modify

| File | Change |
|------|--------|
| `backend/app/modules/integrations/xero/models.py` | Add `XeroSyncEntityProgress`, `PostSyncTask`, `XeroWebhookEvent` models. Extend `XeroSyncJob` with phase fields. |
| `backend/app/modules/integrations/xero/repository.py` | Add repos for new models. |
| `backend/app/modules/integrations/xero/schemas.py` | Add SSE event schemas, entity progress schemas, multi-client sync schemas. |
| `backend/app/modules/integrations/xero/service.py` | Add `start_phased_sync()`, `start_multi_client_sync()`. Update `start_sync()` to use phased approach. |
| `backend/app/modules/integrations/xero/router.py` | Add SSE stream endpoint, multi-client sync endpoints, webhook endpoint. |
| `backend/app/tasks/xero.py` | Refactor `run_sync` to phased chain. Add per-entity tasks with Redis pub/sub progress. |
| `backend/app/tasks/scheduler.py` | Update `sync_all_stale_connections` to use incremental sync. |

### Backend — Create

| File | Purpose |
|------|---------|
| `backend/app/modules/integrations/xero/sync_progress.py` | Redis pub/sub publisher/subscriber for sync progress events. |
| `backend/app/modules/integrations/xero/webhook_handler.py` | Xero webhook verification and event processing. |
| Alembic migration | Add new columns and tables. |

### Frontend — Modify

| File | Change |
|------|--------|
| `frontend/src/lib/xero-sync.ts` | Add SSE connection helpers, multi-client sync API functions. |
| `frontend/src/components/integrations/xero/SyncProgressDialog.tsx` | Replace polling with SSE subscription. Make non-blocking (close dialog, sync continues). |
| `frontend/src/components/integrations/xero/SyncStatusDisplay.tsx` | Add data freshness indicator. |

### Frontend — Create

| File | Purpose |
|------|---------|
| `frontend/src/hooks/useSyncProgress.ts` | Hook wrapping EventSource for SSE sync progress. |
| `frontend/src/components/integrations/xero/SyncNotificationBadge.tsx` | Bell icon badge showing active syncs. |
| `frontend/src/components/integrations/xero/MultiClientSyncButton.tsx` | "Sync All" button with aggregate progress. |

## Development Order

1. **Database migration** — New tables and columns
2. **Per-entity task refactoring** — Break monolithic `run_sync` into per-entity tasks
3. **Phased sync orchestration** — Celery chain of grouped entity tasks
4. **Redis pub/sub progress** — Publish progress events from entity tasks
5. **SSE endpoint** — Backend SSE stream consuming Redis pub/sub
6. **Frontend SSE hook** — `useSyncProgress` consuming SSE stream
7. **Non-blocking UI** — Toast-based sync notifications, close dialog
8. **Expanded IMS** — Add If-Modified-Since to 6 more entity types
9. **Multi-client sync** — "Sync All" endpoint and UI
10. **Post-sync pipeline tracking** — Track downstream task execution
11. **Webhook receiver** (Phase 3) — Xero webhook infrastructure

## Running Locally

```bash
# Start all services
docker-compose up -d

# Run migration
docker exec clairo-backend alembic upgrade head

# Restart workers to pick up new tasks
docker restart clairo-celery-worker

# Test SSE endpoint (requires auth token)
curl -N -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/xero/connections/$CONN_ID/sync/stream
```
