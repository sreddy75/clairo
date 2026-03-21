# Data Model: Progressive Xero Data Sync

**Feature**: 043-progressive-xero-sync
**Date**: 2026-02-14

## Modified Entities

### XeroConnection (existing — extend)

Add new `last_*_sync_at` columns for entities that support `If-Modified-Since` but aren't currently tracked:

| Field | Type | Notes |
|-------|------|-------|
| `last_credit_notes_sync_at` | `DateTime(tz)` | Nullable. New. |
| `last_payments_sync_at` | `DateTime(tz)` | Nullable. New. |
| `last_overpayments_sync_at` | `DateTime(tz)` | Nullable. New. |
| `last_prepayments_sync_at` | `DateTime(tz)` | Nullable. New. |
| `last_journals_sync_at` | `DateTime(tz)` | Nullable. New. |
| `last_manual_journals_sync_at` | `DateTime(tz)` | Nullable. New. |

**Existing fields retained**: `last_contacts_sync_at`, `last_invoices_sync_at`, `last_transactions_sync_at`, `last_accounts_sync_at`, `last_full_sync_at`, `last_payroll_sync_at`, `last_employees_sync_at`, `rate_limit_*` fields.

### XeroSyncJob (existing — extend)

Add phase tracking and enhanced metadata:

| Field | Type | Notes |
|-------|------|-------|
| `sync_phase` | `Integer` | Nullable. 1, 2, or 3. Null for legacy full syncs. |
| `parent_job_id` | `UUID (FK → xero_sync_jobs.id)` | Nullable. Links phase jobs to a parent orchestration job. |
| `triggered_by` | `String(20)` | Default `'user'`. Values: `user`, `schedule`, `webhook`, `system`. |
| `cancelled_at` | `DateTime(tz)` | Nullable. When the job was cancelled. |

**Existing fields retained**: `id`, `tenant_id`, `connection_id`, `sync_type`, `status`, `records_processed`, `records_created`, `records_updated`, `records_failed`, `progress_details` (JSONB), `error_message`, `started_at`, `completed_at`, `created_at`, `updated_at`.

## New Entities

### XeroSyncEntityProgress

Tracks per-entity sync status within a job. Replaces the current `progress_details` JSONB approach with a proper relational model for query-ability.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | `UUID` | PK | |
| `tenant_id` | `UUID (FK → tenants.id)` | NOT NULL | RLS |
| `job_id` | `UUID (FK → xero_sync_jobs.id)` | NOT NULL | Parent job |
| `entity_type` | `String(50)` | NOT NULL | e.g., `contacts`, `invoices`, `bank_transactions` |
| `status` | `Enum` | NOT NULL, default `pending` | `pending`, `in_progress`, `completed`, `failed`, `skipped` |
| `records_processed` | `Integer` | Default 0 | |
| `records_created` | `Integer` | Default 0 | |
| `records_updated` | `Integer` | Default 0 | |
| `records_failed` | `Integer` | Default 0 | |
| `error_message` | `Text` | Nullable | |
| `modified_since` | `DateTime(tz)` | Nullable | IMS timestamp used for this entity |
| `started_at` | `DateTime(tz)` | Nullable | |
| `completed_at` | `DateTime(tz)` | Nullable | |
| `duration_ms` | `Integer` | Nullable | Elapsed time in milliseconds |
| `created_at` | `DateTime(tz)` | Default `now()` | |
| `updated_at` | `DateTime(tz)` | Default `now()` | |

**Indexes**: `(job_id)`, `(tenant_id)`, `(job_id, entity_type)` UNIQUE.

### XeroWebhookEvent (for Phase 3 — P3)

Records incoming Xero webhook events for processing and deduplication.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | `UUID` | PK | |
| `tenant_id` | `UUID (FK → tenants.id)` | NOT NULL | RLS |
| `connection_id` | `UUID (FK → xero_connections.id)` | NOT NULL | |
| `webhook_key` | `String(255)` | NOT NULL, UNIQUE | Xero event key for deduplication |
| `event_type` | `String(100)` | NOT NULL | e.g., `CREATE`, `UPDATE` |
| `event_category` | `String(50)` | NOT NULL | e.g., `INVOICE`, `CONTACT` |
| `resource_id` | `String(50)` | NOT NULL | Xero entity ID affected |
| `status` | `Enum` | NOT NULL, default `pending` | `pending`, `processing`, `completed`, `failed` |
| `batch_id` | `UUID` | Nullable | Groups events batched together |
| `processed_at` | `DateTime(tz)` | Nullable | |
| `error_message` | `Text` | Nullable | |
| `raw_payload` | `JSONB` | Nullable | Original webhook payload |
| `created_at` | `DateTime(tz)` | Default `now()` | |

**Indexes**: `(webhook_key)` UNIQUE, `(connection_id, status)`, `(tenant_id)`, `(batch_id)`.

### PostSyncTask

Tracks execution of post-sync data preparation tasks.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | `UUID` | PK | |
| `tenant_id` | `UUID (FK → tenants.id)` | NOT NULL | RLS |
| `job_id` | `UUID (FK → xero_sync_jobs.id)` | NOT NULL | Triggering sync job |
| `connection_id` | `UUID (FK → xero_connections.id)` | NOT NULL | |
| `task_type` | `String(50)` | NOT NULL | `quality_score`, `bas_calculation`, `aggregation`, `insights`, `triggers` |
| `status` | `Enum` | NOT NULL, default `pending` | `pending`, `in_progress`, `completed`, `failed` |
| `sync_phase` | `Integer` | NOT NULL | Which sync phase triggered this (1, 2, 3) |
| `started_at` | `DateTime(tz)` | Nullable | |
| `completed_at` | `DateTime(tz)` | Nullable | |
| `error_message` | `Text` | Nullable | |
| `result_summary` | `JSONB` | Nullable | e.g., `{"quality_score": 87, "issues_found": 3}` |
| `created_at` | `DateTime(tz)` | Default `now()` | |
| `updated_at` | `DateTime(tz)` | Default `now()` | |

**Indexes**: `(job_id)`, `(connection_id, task_type)`, `(tenant_id)`.

## State Transitions

### Sync Job States

```
pending → in_progress → completed
                      → failed
                      → cancelled (user cancelled)
```

### Sync Entity Progress States

```
pending → in_progress → completed
                      → failed
                      → skipped (entity not applicable)
```

### Sync Phases (Initial Sync)

```
Phase 1 (Essential) → Phase 2 (Recent) → Phase 3 (Full History)
     ↓                      ↓                     ↓
  Post-sync P1          Post-sync P2          Post-sync P3
  (quality score,       (BAS calc,            (full insights,
   basic readiness)      aggregation)          trigger evaluation)
```

## Entity Relationships

```
XeroSyncJob (1) ──→ (N) XeroSyncEntityProgress
XeroSyncJob (1) ──→ (N) PostSyncTask
XeroSyncJob (parent) ──→ (N) XeroSyncJob (phase children)
XeroConnection (1) ──→ (N) XeroSyncJob
XeroConnection (1) ──→ (N) XeroWebhookEvent
```

## Migration Notes

- Add 6 new `last_*_sync_at` columns to `xero_connections` — all nullable, no default
- Add `sync_phase`, `parent_job_id`, `triggered_by`, `cancelled_at` columns to `xero_sync_jobs`
- Create new `xero_sync_entity_progress` table
- Create new `post_sync_tasks` table
- Create new `xero_webhook_events` table (can defer to Phase 3)
- All new tables must include `tenant_id` with RLS policy
- Preserve existing `progress_details` JSONB on sync jobs for backward compatibility
