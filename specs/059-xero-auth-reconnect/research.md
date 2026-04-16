# Research: Xero Authentication Robustness

**Phase**: 0 — Pre-design research
**Date**: 2026-04-16
**Method**: Full codebase analysis of `backend/app/modules/integrations/xero/`

All decisions below are based on reading the actual implementation. No NEEDS CLARIFICATION items remain.

---

## Decision 1: Grant Group Identification Strategy

**Question**: How do we identify which connections share the same OAuth grant (and thus the same refresh token), given we need this to scope the lock correctly?

**Decision**: Add an `oauth_grant_id UUID` column to `xero_connections`. All connections created from the same OAuth callback share the same `oauth_grant_id`.

**Rationale**:
- Comparing encrypted token blobs is unreliable (tokens rotate; after first refresh, blobs diverge even for siblings)
- A separate table (`xero_oauth_grants`) is over-engineered for this use case
- A column on the existing table is minimal and queryable with a simple index
- `oauth_grant_id` is set once at creation time and is immutable; it never changes even as tokens rotate

**Alternative considered**: Identify siblings by `tenant_id` + `created_at` proximity (same second = same bulk import).
**Rejected because**: Timing-based grouping is fragile — clock skew between workers, DB insert order, or a slow callback could split connections that belong to the same grant.

**Alternative considered**: Store a hash of the original refresh token as the group key.
**Rejected because**: The original token is rotated immediately after first use; we'd need to store the hash at OAuth callback time and the value becomes stale after the first refresh.

---

## Decision 2: Redis Lock Key Scope

**Question**: What should the lock key be?

**Decision**: `xero_token_refresh:grant:{oauth_grant_id}`

**Rationale**:
- Current key `xero_token_refresh:{connection_id}` allows siblings to hold separate locks simultaneously, causing the race
- Grant-scoped key ensures all siblings contend for the same lock
- One lock per grant = exactly one refresh per grant per rotation window

**Alternative considered**: Global lock per tenant (`xero_token_refresh:tenant:{tenant_id}`)
**Rejected because**: A tenant with 10 Xero connections would serialize all their syncs — including connections on different grants that don't share tokens. Too coarse.

---

## Decision 3: Sibling Propagation Scope

**Question**: After a successful refresh, which sibling connections get the new tokens?

**Decision**: ALL connections sharing the same `oauth_grant_id`, regardless of their current `status`.

**Rationale**:
- Current code only updates siblings already in `NEEDS_REAUTH`. Active siblings hold the now-invalidated refresh token and will fail on their next refresh.
- Propagating to all siblings is the correct behavior for rotating refresh tokens.
- The status of siblings should be set to `ACTIVE` if they were `NEEDS_REAUTH`, and their tokens updated if they were `ACTIVE`.

**Implementation**: After a successful refresh, query all connections with the same `oauth_grant_id`, and for each: update `access_token`, `refresh_token`, `token_expires_at`. Set status to `ACTIVE` if it was `NEEDS_REAUTH`.

---

## Decision 4: Retry-Before-Reauth on `invalid_grant`

**Question**: When `invalid_grant` is received, should we immediately mark `needs_reauth` or retry?

**Decision**: On `invalid_grant`, re-read the connection from DB once. If `token_expires_at > now`, a sibling already refreshed and propagated — use those tokens. Otherwise, mark `needs_reauth`.

**Rationale**:
- The race condition can cause `invalid_grant` even for a perfectly healthy OAuth grant
- Re-reading DB is cheap (one SELECT) and resolves the race in the common case
- This is the "check-then-act" pattern standard for distributed locking

**No sleep/retry loop**: We don't retry the Xero API call. We re-read DB once. If still stale, we give up. This keeps the logic simple and the error path fast.

---

## Decision 5: Redis Unavailability Handling

**Question**: If Redis is down, should we block or degrade gracefully?

**Decision**: Catch `RedisError` and `ConnectionError` at the lock-acquisition level. Log a warning and attempt a best-effort refresh without the lock. Accept the small concurrent-refresh risk.

**Rationale**:
- Current behavior: Redis down → lock raises → entire sync fails, even if token is valid
- Best-effort-without-lock is much better than total failure
- The race condition it re-introduces (sibling rotation race) is the same bug we're fixing; it's a known, bounded risk that only occurs during Redis outages
- Redis outages are rare; we should not let infrastructure failure cascade into Xero connectivity failures

---

## Decision 6: Consolidating Token Access Paths

**Question**: Which services need to be refactored to use `ensure_valid_token`?

**Decision**: All of them. Identified 7 bypassed paths:

| Service / File | Current Issue | Fix |
|----------------|---------------|-----|
| `data_service._get_connection_with_token` | Calls `refresh_tokens()` directly (no lock) | Use `ensure_valid_token()` |
| `data_service._ensure_valid_token` (loop) | Already uses `ensure_valid_token` — but duplicates the start-of-sync call | Keep, remove duplicate unlocked call at sync start |
| `report_service._get_connection_and_token` | Calls `refresh_tokens()` directly (no lock) | Use `ensure_valid_token()` |
| `payroll_service` (line 82) | Raw `encryption.decrypt(access_token)` — no expiry check | Use `ensure_valid_token()` |
| `xpm_service` (line 94) | Raw `encryption.decrypt(access_token)` — no expiry check | Use `ensure_valid_token()` |
| `bas/router` `get_org_tax_rates` (line 1937) | Raw decrypt, silent 401 returns `{}` | Use `ensure_valid_token()`, raise on auth failure |
| `xero_writeback` task (lines 122-171) | Bespoke inline refresh, no lock | Use `ensure_valid_token()` |

---

## Decision 7: New API Endpoint

**Question**: Does the frontend need a new endpoint to check `needs_reauth` status?

**Decision**: Yes — add `GET /api/v1/integrations/xero/status`. The existing connections list endpoint returns too much data (full connection objects) to be polled on every page navigation.

**Response shape**:
```json
{
  "needs_reauth": [
    { "connection_id": "uuid", "org_name": "Smith & Co" }
  ],
  "total_connections": 3,
  "active_connections": 2
}
```

**Rationale**: Lightweight summary that the frontend can poll cheaply. Only `needs_reauth` connections are returned in detail — that's all the banner needs to display org names.

---

## Decision 8: Frontend Polling Strategy

**Question**: How often should the frontend check for `needs_reauth`?

**Decision**: TanStack Query with `staleTime: 60_000` (1 minute). The query runs:
- On initial authenticated page load
- On window focus (standard TanStack Query behavior)
- On navigation (via `router.events` listener or `usePathname` change trigger)

**Not used**: WebSocket push, long-polling, or server-sent events.

**Rationale**: `needs_reauth` is not time-critical. Detecting it within 1 minute of the state change is sufficient. WebSockets would add infrastructure complexity for minimal benefit.

---

## Decision 9: `token_expires_at = None` Guard

**Question**: How to handle existing connections that have `token_expires_at = None`?

**Decision**: In `needs_refresh`, if `token_expires_at` is `None`, treat as needs-refresh (current behavior). But also: in `ensure_valid_token`, after a successful refresh, assert that `token_expires_at` is set before returning. Add a DB-level default (`DEFAULT NOW() + INTERVAL '30 minutes'`) as a safety net.

**No separate migration needed**: The `oauth_grant_id` migration can include a default for `token_expires_at` on rows where it's `NULL`.

---

## Decision 10: Back-fill Strategy for `oauth_grant_id`

**Question**: How do we assign `oauth_grant_id` to existing `xero_connections` rows?

**Decision**: Group by `tenant_id` + `created_at` truncated to minute. Connections created within the same minute for the same tenant are assumed to be from the same OAuth callback (bulk import creates all connections atomically).

**SQL**:
```sql
WITH grouped AS (
    SELECT
        id,
        gen_random_uuid() OVER (
            PARTITION BY tenant_id, DATE_TRUNC('minute', created_at)
        ) AS grant_id
    FROM xero_connections
    WHERE oauth_grant_id IS NULL
)
UPDATE xero_connections xc
SET oauth_grant_id = g.grant_id
FROM grouped g
WHERE xc.id = g.id;
```

**Edge cases**:
- Single connection per tenant per minute → gets its own UUID (correct: single-member grant group)
- Connections created at different times but from the same grant (e.g., added one-by-one) → each gets its own UUID. This is slightly incorrect for edge cases but acceptable: they'll behave as independent connections with independent locks, which is safe (no shared token to race over at that point since each was added via its own OAuth flow)
