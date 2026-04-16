# Data Model: Xero Authentication Robustness

**Feature**: 059-xero-auth-reconnect
**Date**: 2026-04-16
**Updated**: 2026-04-16 (post-implementation discovery)

---

## Schema Changes

**None.** No migration required.

### Discovery During Implementation

`auth_event_id STRING(50)` already exists on `xero_connections` (with an index) and serves exactly the role we planned for `oauth_grant_id`. It is populated by Xero's API — the `/connections` endpoint returns `authEventId` on each org object, grouping all orgs authorized in the same OAuth session.

The column was already being set during the bulk import flow (`bulk_import_service.py`). The gap was in the regular OAuth path (`oauth_service._upsert_connection`), which was not passing `org.auth_event_id` through to the repository create call. That single line was added as part of this feature.

---

## Entity: `XeroConnection` (unchanged)

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | No change |
| `tenant_id` | UUID FK | No change |
| `auth_event_id` | String(50), nullable, indexed | **Grant group key** — shared across all connections from same OAuth callback. Set by Xero API (`authEventId` field). Now also set in regular OAuth path. |
| `organization_name` | Text | No change |
| `xero_tenant_id` | Text | No change |
| `access_token` | Text (encrypted) | No change |
| `refresh_token` | Text (encrypted) | No change |
| `token_expires_at` | TimestampTZ | No change |
| `status` | Enum | `active` / `needs_reauth` / `disconnected` — no change |
| `scopes` | Text[] | No change |

---

## No New Tables

All behavioral changes are in service layer logic. The grant-group concept is captured by the existing `auth_event_id` column.

---

## State Transitions: `XeroConnection.status`

The state machine is unchanged. What changes is when and why transitions occur:

```
                   ┌─────────────────────────────────────────┐
                   │                                           │
                   ▼                                           │
            ┌────────────┐      successful                    │
  OAuth ──► │   ACTIVE   │ ─── background ──► still ACTIVE   │
  callback  │            │     token refresh  (no user action)│
            └─────┬──────┘                                    │
                  │                                           │
                  │ genuine invalid_grant                     │
                  │ (refresh token expired/revoked,           │
                  │  NOT a race condition — race is now fixed) │
                  ▼                                           │
          ┌──────────────┐   user completes                  │
          │ NEEDS_REAUTH  │ ── OAuth flow ─────────────────────┘
          └──────────────┘
                  │
                  │ user disconnects
                  ▼
          ┌──────────────┐
          │ DISCONNECTED  │
          └──────────────┘
```

**Key change**: `ACTIVE → NEEDS_REAUTH` transitions now only occur when the refresh token has genuinely expired (60 days non-use) or been explicitly revoked. Race-condition-induced transitions are eliminated.

---

## Grant Group Query Pattern

Used by `connection_service.py` to propagate tokens after a refresh:

```sql
-- Get all connections in the same grant group
SELECT * FROM xero_connections
WHERE auth_event_id = :auth_event_id
  AND tenant_id = :tenant_id
  AND status != 'disconnected';
```

Connections without an `auth_event_id` (created before bulk import flow was added, or single-connection tenants) are treated as single-member grant groups — their lock key falls back to `xero_token_refresh:event:{connection_id}`.
