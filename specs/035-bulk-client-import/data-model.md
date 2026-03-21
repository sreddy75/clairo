# Data Model: Bulk Client Import via Multi-Org Xero OAuth

**Feature**: 035-bulk-client-import
**Date**: 2026-02-08

## Entity Changes

### Modified: XeroConnection

**Table**: `xero_connections` (existing)

No schema changes required. Existing fields used:

| Field | Usage in Bulk Import |
|-------|---------------------|
| `auth_event_id` (String(50), nullable) | Groups connections from the same bulk OAuth flow |
| `connection_type` (Enum: practice/client) | Set to CLIENT for all bulk-imported orgs (unless user marks one as PRACTICE) |
| `access_token` (Text, encrypted) | Shared token from single OAuth flow, stored per-connection |
| `refresh_token` (Text, encrypted) | Shared token from single OAuth flow, stored per-connection |
| `status` (Enum) | Set to ACTIVE on creation |

### Modified: XeroOAuthState

**Table**: `xero_oauth_states` (existing)

New field:

| Field | Type | Purpose |
|-------|------|---------|
| `is_bulk_import` | Boolean, default False | Distinguishes bulk import flows from single-org flows |

### Reused: BulkImportJob

**Table**: `bulk_import_jobs` (existing, in onboarding module)

No schema changes. Reused with `source_type = "xero_bulk_oauth"`.

Existing fields used:

| Field | Usage |
|-------|-------|
| `source_type` | Set to `"xero_bulk_oauth"` |
| `total_clients` | Count of selected organizations |
| `imported_count` | Incremented as each org sync completes |
| `failed_count` | Incremented on org sync failure |
| `progress_percent` | Calculated as `(imported + failed) / total * 100` |
| `client_ids` | JSONB array of Xero tenant IDs selected for import |
| `imported_clients` | JSONB array of `{xero_tenant_id, org_name, connection_id}` |
| `failed_clients` | JSONB array of `{xero_tenant_id, org_name, error}` |
| `status` | PENDING → IN_PROGRESS → COMPLETED/PARTIAL_FAILURE/FAILED |

### New: BulkImportOrganization

**Table**: `bulk_import_organizations`

Tracks individual organization status within a bulk import job.

| Field | Type | Constraints | Purpose |
|-------|------|-------------|---------|
| `id` | UUID | PK | Unique identifier |
| `tenant_id` | UUID | FK → tenants.id, NOT NULL | RLS tenant scoping |
| `bulk_import_job_id` | UUID | FK → bulk_import_jobs.id, NOT NULL | Parent job reference |
| `xero_tenant_id` | String(50) | NOT NULL | Xero organization identifier |
| `organization_name` | String(255) | NOT NULL | Xero organization display name |
| `status` | String(20) | NOT NULL, default "pending" | pending, importing, syncing, completed, failed, skipped |
| `connection_id` | UUID | FK → xero_connections.id, nullable | Created connection (set after import) |
| `connection_type` | String(20) | NOT NULL, default "client" | practice or client |
| `assigned_user_id` | UUID | FK → practice_users.id, nullable | Assigned team member |
| `already_connected` | Boolean | NOT NULL, default False | True if org was already connected |
| `selected_for_import` | Boolean | NOT NULL, default True | User's selection on config screen |
| `match_status` | String(20) | nullable | matched, suggested, unmatched |
| `matched_client_name` | String(255) | nullable | Name of matched XPM/existing client |
| `error_message` | Text | nullable | Error details if failed |
| `sync_started_at` | DateTime(tz) | nullable | When sync was dispatched |
| `sync_completed_at` | DateTime(tz) | nullable | When sync finished |
| `created_at` | DateTime(tz) | NOT NULL, default now() | Record creation time |
| `updated_at` | DateTime(tz) | NOT NULL, default now() | Last update time |

**Indexes**:
- `ix_bulk_import_orgs_job` on `bulk_import_job_id`
- `ix_bulk_import_orgs_tenant` on `tenant_id`
- `ix_bulk_import_orgs_xero_tenant` on `xero_tenant_id`

**Relationships**:
- `bulk_import_job` → BulkImportJob (many-to-one)
- `connection` → XeroConnection (many-to-one, nullable)

## Entity Relationship Summary

```
Tenant (1) ─── (N) BulkImportJob
                      │
                      └── (N) BulkImportOrganization ──── (0..1) XeroConnection
                                                                       │
                                                              Uses shared tokens
                                                              from same auth_event_id
```

## State Transitions

### BulkImportJob Status

```
PENDING ──(worker picks up)──> IN_PROGRESS ──(all orgs done)──> COMPLETED
                                    │                               │
                                    └──(some failed)────> PARTIAL_FAILURE
                                    │
                                    └──(all failed)─────> FAILED
                                    │
                          (user cancels)──> CANCELLED
```

### BulkImportOrganization Status

```
pending ──(job starts)──> importing ──(connection created)──> syncing ──(sync done)──> completed
                              │                                  │
                              └──(error)─────> failed            └──(sync error)──> failed

pending ──(user deselected)──> skipped
pending ──(already connected)──> skipped (already_connected=true)
pending ──(plan limit)──> skipped (error_message="Plan limit reached")
```

## Migration Notes

- Add `is_bulk_import` column to `xero_oauth_states` (ALTER TABLE, default False)
- Create `bulk_import_organizations` table
- No changes to `xero_connections` or `bulk_import_jobs` tables
