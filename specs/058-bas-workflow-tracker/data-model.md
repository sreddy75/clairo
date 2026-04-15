# Data Model: 058-bas-workflow-tracker

**Branch**: `058-bas-workflow-tracker`  
**Date**: 2026-04-15

---

## New Tables

### `practice_clients`

The universal practice management entity. One record per client the practice manages, regardless of accounting software. Replaces `xero_connections` as the driving table for dashboard queries.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | gen_random_uuid() | PK |
| `tenant_id` | UUID | NO | — | FK → tenants.id |
| `name` | VARCHAR(255) | NO | — | Client business name |
| `abn` | VARCHAR(11) | YES | NULL | Australian Business Number (11 digits) |
| `accounting_software` | VARCHAR(20) | NO | 'unknown' | Enum: xero, quickbooks, myob, email, other, unknown |
| `xero_connection_id` | UUID | YES | NULL | FK → xero_connections.id (UNIQUE). NULL for non-Xero clients |
| `assigned_user_id` | UUID | YES | NULL | FK → practice_users.id. Team member responsible |
| `notes` | TEXT | YES | NULL | Persistent client notes (carries across quarters) |
| `notes_updated_at` | TIMESTAMPTZ | YES | NULL | When notes were last edited |
| `notes_updated_by` | UUID | YES | NULL | FK → practice_users.id. Who last edited notes |
| `manual_status` | VARCHAR(20) | YES | NULL | For non-Xero clients: not_started, in_progress, completed, lodged |
| `created_at` | TIMESTAMPTZ | NO | now() | Record creation |
| `updated_at` | TIMESTAMPTZ | NO | now() | Last modification |

**Indexes**:
- `ix_practice_clients_tenant_id` ON (tenant_id)
- `ix_practice_clients_assigned_user_id` ON (assigned_user_id) — filter by team member
- `ix_practice_clients_xero_connection_id` ON (xero_connection_id) UNIQUE WHERE xero_connection_id IS NOT NULL — lookup by connection
- `ix_practice_clients_tenant_software` ON (tenant_id, accounting_software) — filter by software type
- `ix_practice_clients_tenant_name` ON (tenant_id, name) — search

**Constraints**:
- FK `tenant_id` → `tenants.id` ON DELETE CASCADE
- FK `xero_connection_id` → `xero_connections.id` ON DELETE SET NULL
- FK `assigned_user_id` → `practice_users.id` ON DELETE SET NULL (orphan → unassigned)
- FK `notes_updated_by` → `practice_users.id` ON DELETE SET NULL
- CHECK `accounting_software` IN ('xero', 'quickbooks', 'myob', 'email', 'other', 'unknown')
- CHECK `manual_status` IN ('not_started', 'in_progress', 'completed', 'lodged') OR NULL

**RLS Policy**: `tenant_id = current_setting('app.current_tenant_id')::uuid`

---

### `client_quarter_exclusions`

Per-quarter exclusion records. Presence of a row means the client is excluded for that quarter.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | gen_random_uuid() | PK |
| `tenant_id` | UUID | NO | — | FK → tenants.id |
| `client_id` | UUID | NO | — | FK → practice_clients.id |
| `quarter` | SMALLINT | NO | — | Quarter number (1-4) |
| `fy_year` | VARCHAR(7) | NO | — | Financial year (e.g., '2025-26') |
| `reason` | VARCHAR(30) | YES | NULL | Enum: dormant, lodged_externally, gst_cancelled, left_practice, other |
| `reason_detail` | TEXT | YES | NULL | Free text detail (when reason = 'other') |
| `excluded_by` | UUID | NO | — | FK → practice_users.id |
| `excluded_at` | TIMESTAMPTZ | NO | now() | When exclusion was created |
| `reversed_at` | TIMESTAMPTZ | YES | NULL | When exclusion was reversed (soft delete) |
| `reversed_by` | UUID | YES | NULL | FK → practice_users.id |

**Indexes**:
- `uix_client_quarter_exclusion` UNIQUE ON (client_id, quarter, fy_year) WHERE reversed_at IS NULL — one active exclusion per client per quarter
- `ix_exclusions_tenant_quarter` ON (tenant_id, quarter, fy_year) — dashboard filter

**Constraints**:
- FK `tenant_id` → `tenants.id` ON DELETE CASCADE
- FK `client_id` → `practice_clients.id` ON DELETE CASCADE
- FK `excluded_by` → `practice_users.id` ON DELETE RESTRICT
- FK `reversed_by` → `practice_users.id` ON DELETE SET NULL
- CHECK `quarter` BETWEEN 1 AND 4

**RLS Policy**: `tenant_id = current_setting('app.current_tenant_id')::uuid`

---

### `client_note_history`

Append-only audit trail for persistent note changes.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | gen_random_uuid() | PK |
| `tenant_id` | UUID | NO | — | FK → tenants.id |
| `client_id` | UUID | NO | — | FK → practice_clients.id |
| `note_text` | TEXT | NO | — | Snapshot of note content at time of change |
| `edited_by` | UUID | NO | — | FK → practice_users.id |
| `edited_at` | TIMESTAMPTZ | NO | now() | When this version was saved |

**Indexes**:
- `ix_note_history_client` ON (client_id, edited_at DESC) — show history for a client

**Constraints**:
- FK `tenant_id` → `tenants.id` ON DELETE CASCADE
- FK `client_id` → `practice_clients.id` ON DELETE CASCADE
- FK `edited_by` → `practice_users.id` ON DELETE RESTRICT
- Immutable: CREATE RULE no_update, no_delete (same pattern as audit_logs)

**RLS Policy**: `tenant_id = current_setting('app.current_tenant_id')::uuid`

---

## Modified Tables

### `practice_users` (add column)

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `display_name` | VARCHAR(100) | YES | NULL | Cached from Clerk. Falls back to email when NULL |

---

## Entity Relationships

```
tenants
  └── practice_clients (1:N via tenant_id)
        ├── xero_connections (1:1 optional via xero_connection_id)
        │     ├── xero_invoices (1:N)
        │     ├── xero_bank_transactions (1:N)
        │     └── bas_periods → bas_sessions (1:N)
        ├── client_quarter_exclusions (1:N via client_id)
        ├── client_note_history (1:N via client_id)
        └── practice_users (N:1 via assigned_user_id)
```

---

## Migration Strategy

### Migration 1: Create tables

1. Create `practice_clients` table
2. Create `client_quarter_exclusions` table
3. Create `client_note_history` table
4. Add `display_name` column to `practice_users`
5. Create all indexes and constraints

### Migration 2: Backfill existing data

For every `xero_connection` WHERE `status IN ('active', 'needs_reauth')`:
```sql
INSERT INTO practice_clients (tenant_id, name, accounting_software, xero_connection_id, created_at, updated_at)
SELECT
  xc.tenant_id,
  xc.organization_name,
  'xero',
  xc.id,
  xc.created_at,
  now()
FROM xero_connections xc
WHERE xc.status IN ('active', 'needs_reauth')
  AND NOT EXISTS (
    SELECT 1 FROM practice_clients pc WHERE pc.xero_connection_id = xc.id
  );
```

Also backfill `assigned_user_id` from `bulk_import_organizations` where available:
```sql
UPDATE practice_clients pc
SET assigned_user_id = bio.assigned_user_id
FROM bulk_import_organizations bio
JOIN xero_connections xc ON xc.id = pc.xero_connection_id
WHERE bio.xero_tenant_id = xc.xero_tenant_id
  AND bio.assigned_user_id IS NOT NULL
  AND pc.assigned_user_id IS NULL;
```

---

## State Transitions

### Client Quarter Exclusion

```
[Active] --exclude--> [Excluded] (row created)
[Excluded] --reverse--> [Active] (reversed_at set, row soft-deleted)
```

### Manual BAS Status (non-Xero clients only)

```
[not_started] --> [in_progress] --> [completed] --> [lodged]
```

Transitions are manual (accountant-driven), no auto-derivation.
