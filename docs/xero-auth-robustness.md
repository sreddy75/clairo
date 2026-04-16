# Xero Authentication Robustness & Reconnection UX

**Branch**: `059-xero-auth-reconnect`
**Date**: 2026-04-16
**Status**: Design / Pre-implementation

---

## 1. Problem Statement

Users are seeing Xero re-authentication prompts multiple times per day. This should only happen once every 60 days (when a refresh token genuinely expires from non-use) or when a user explicitly revokes access in Xero. The frequent prompts are caused by code-level race conditions in the token refresh mechanism, not by actual Xero session expiry.

---

## 2. How Xero OAuth Tokens Work

```
┌─────────────────────────────────────────────────────────────────┐
│                    Xero OAuth2 Token Lifecycle                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Access Token   ──── expires every 30 minutes                   │
│  Refresh Token  ──── expires after 60 days of non-use           │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  CRITICAL: Xero uses ROTATING refresh tokens             │   │
│  │                                                           │   │
│  │  Each time you use a refresh token to get a new          │   │
│  │  access token, Xero:                                      │   │
│  │    1. Issues a NEW refresh token                          │   │
│  │    2. Immediately INVALIDATES the old refresh token       │   │
│  │                                                           │   │
│  │  If two requests use the SAME refresh token at once,      │   │
│  │  one succeeds and one gets: invalid_grant               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Normal operation (no user interaction needed):                  │
│                                                                   │
│  t=0min    t=25min   t=30min  t=55min   t=60min                 │
│    │          │         │        │          │                    │
│  [Auth]  [check: ok] [expire] [refresh] [expire]               │
│                               ───────►                          │
│                            uses refresh token                   │
│                            gets new access + new refresh token  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Root Cause Analysis

### 3.1 Current Architecture

Clairo's Xero integration creates multiple `XeroConnection` records for a single OAuth grant. When an accountant connects Xero (bulk import), Clairo creates one connection per authorized org — all sharing the same initial `access_token` and `refresh_token`.

```
  Single OAuth Grant (one Xero login flow)
          │
          ├──► XeroConnection [id: A, org: "Smith & Co"]
          │       access_token: T1
          │       refresh_token: R1
          │
          ├──► XeroConnection [id: B, org: "Jones Pty Ltd"]
          │       access_token: T1
          │       refresh_token: R1
          │
          └──► XeroConnection [id: C, org: "Williams Trust"]
                  access_token: T1
                  refresh_token: R1
```

### 3.2 Failure Mode 1: Lock Scoped to Connection, Not Grant (Primary Cause)

The Redis lock that guards token refresh is keyed by `connection_id`. Siblings each have a different `connection_id` and therefore a different lock. Two sibling connections can simultaneously hold their own locks and both attempt to refresh the same `R1` refresh token.

```
  Sync Task for Connection A          Sync Task for Connection B
  ─────────────────────────          ─────────────────────────
  lock key: refresh:A                lock key: refresh:B
  acquire lock → SUCCESS             acquire lock → SUCCESS (different key!)
  read token: R1                     read token: R1
  POST /token (grant_type=refresh,   POST /token (grant_type=refresh,
    refresh_token=R1)                  refresh_token=R1)
        │                                    │
        ▼                                    ▼
  Xero: SUCCESS                      Xero: invalid_grant ✗
  new tokens: T2, R2                 (R1 was already rotated)
        │                                    │
        ▼                                    ▼
  save T2, R2 to DB                  mark Connection B → needs_reauth
  release lock                       release lock

  ─────────────────────────────────────────────────────────────────
  Result: Connection B needs re-auth even though R1 was valid.
  This happens every ~30 minutes when multiple syncs run concurrently.
```

### 3.3 Failure Mode 2: Broken Sibling Propagation

Even when one connection successfully refreshes, the sibling propagation logic only updates siblings that are already in `needs_reauth` state. Active siblings with the now-invalidated `R1` are left untouched:

```python
# Current code (connection_service.py ~301)
for sibling in siblings:
    if sibling.status == XeroConnectionStatus.NEEDS_REAUTH:  # ← only broken ones
        await self.connection_repo.update(sibling.id, new_tokens)

# Active siblings still have R1. Next time they refresh → invalid_grant → needs_reauth
```

### 3.4 Failure Mode 3: Multiple Unlocked Refresh Paths

Five separate code paths refresh tokens without going through the Redis lock:

```
  ┌─────────────────────────────────────────────────────────────┐
  │              Code Paths That Access Xero Tokens              │
  ├─────────────────────────────────────────────────────────────┤
  │                                                               │
  │  ✓ ensure_valid_token()          ← Redis lock protected      │
  │      └─► _refresh_with_lock()                                │
  │                                                               │
  │  ✗ data_service._get_connection_with_token()                 │
  │       └─► refresh_tokens() directly  ← NO LOCK               │
  │                                                               │
  │  ✗ report_service._get_connection_and_token()                │
  │       └─► refresh_tokens() directly  ← NO LOCK               │
  │                                                               │
  │  ✗ payroll_service (line 82)                                 │
  │       └─► encryption.decrypt(access_token)  ← NO EXPIRY CHECK│
  │                                                               │
  │  ✗ xpm_service (line 94)                                     │
  │       └─► encryption.decrypt(access_token)  ← NO EXPIRY CHECK│
  │                                                               │
  │  ✗ bas/router (line 1937)                                    │
  │       └─► encryption.decrypt(access_token)  ← NO EXPIRY CHECK│
  │           returns {} on 401, silent failure                   │
  │                                                               │
  │  ✗ xero_writeback task (lines 122-171)                       │
  │       └─► inline refresh loop  ← NO LOCK, bespoke logic      │
  │                                                               │
  └─────────────────────────────────────────────────────────────┘
```

The `data_service` also races with itself: it calls the unlocked path at sync start, then calls the locked path inside every pagination loop — both can fire within a single task run.

### 3.5 Failure Mode 4: Blocking-Timeout Returns Stale Token

When a waiter cannot acquire the lock within 15 seconds, it reads whatever token is currently in the database and proceeds. If the holder is still mid-HTTP-call to Xero's token endpoint, the database has not yet been updated — the waiter gets the old (now-invalidated) token and proceeds to make API calls that return 401.

```
  Holder: acquiring lock ─────────────────────────────────────► save new tokens
  Waiter: waiting 15s ─────────────────► timeout → read DB → stale token → 401
                          │
                  15s timeout fires here,
                  before holder writes new tokens
```

### 3.6 Failure Mode 5: Redis Unavailability Fails Entire Sync

If Redis is down, `lock.acquire()` raises an exception that propagates all the way out of `ensure_valid_token`, failing the sync operation — even if the access token is perfectly valid and doesn't need refreshing.

### 3.7 Failure Mode 6: Missing `token_expires_at`

If `token_expires_at` is `None` (can happen if not set during initial OAuth), `needs_refresh` returns `True` unconditionally. Every call attempts a refresh, multiplying the chances of concurrent rotation.

```python
# models.py ~879
@property
def needs_refresh(self) -> bool:
    if not self.token_expires_at:
        return True  # ← triggers refresh on every single call
    threshold = datetime.now(UTC) + timedelta(minutes=5)
    return threshold >= self.token_expires_at
```

---

## 4. Solution Design

### 4.1 Overview

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                        Solution Components                       │
  ├─────────────────────────────────────────────────────────────────┤
  │                                                                   │
  │  P1 ─ Token Refresh Robustness (backend)                        │
  │    ├── Lock scoped to OAuth grant, not connection_id            │
  │    ├── Propagate tokens to ALL siblings after refresh           │
  │    ├── Retry-before-reauth on invalid_grant                     │
  │    ├── Single token path for all services                       │
  │    └── Redis fallback for lock acquisition failure              │
  │                                                                   │
  │  P2 ─ Global Re-Auth Notification (frontend + API)              │
  │    ├── Global needs_reauth state via existing connections API   │
  │    ├── Persistent banner/popup on all authenticated pages       │
  │    └── Return-to-origin after OAuth flow                        │
  │                                                                   │
  │  P3 ─ Sync Error Clarity (backend)                              │
  │    ├── Raw-decrypt paths upgraded to route through             │
  │    │   ensure_valid_token                                        │
  │    └── Typed exceptions for auth failures → specific UI errors  │
  │                                                                   │
  └─────────────────────────────────────────────────────────────────┘
```

### 4.2 Fix 1: OAuth Grant-Scoped Lock

The lock key changes from per-connection to per-OAuth-grant. All connections that share the same refresh token contend for the same lock.

**Grant identification**: Query all connections in the tenant with the same `refresh_token` value (after decryption hash, or by adding an `oauth_grant_id` column). The simplest approach is a `oauth_grant_id` UUID on `XeroConnection`, set to the same value for all connections created from the same OAuth callback.

```
  BEFORE (broken):                    AFTER (fixed):

  Connection A ─► lock: refresh:A     Connection A ─┐
  Connection B ─► lock: refresh:B     Connection B ─┼─► lock: refresh:grant:<GRANT_ID>
  Connection C ─► lock: refresh:C     Connection C ─┘
  (3 independent locks)               (1 shared lock)
```

**Revised `_refresh_with_lock` flow**:

```
  acquire lock: xero_token_refresh:grant:<oauth_grant_id>
       │
       ├── acquired → re-read ALL connections in this grant group
       │                  │
       │              any still needs_refresh?
       │                  ├── YES → call Xero refresh endpoint once
       │                  │             │
       │                  │         update ALL connections in group
       │                  │         with new access_token + refresh_token
       │                  │             │
       │                  │         return fresh connection
       │                  │
       │                  └── NO (another holder already refreshed)
       │                          return connection with fresh tokens from DB
       │
       └── not acquired (timeout) → re-read DB → wait for holder's write
                                      if still stale: best-effort refresh
                                      (accept race risk, log warning)
```

### 4.3 Fix 2: Propagate to ALL Siblings

After every successful refresh, update all connections in the grant group regardless of their current status:

```
  BEFORE:                              AFTER:

  for sibling in siblings:             for sibling in grant_group:
      if sibling.status ==                 await repo.update(sibling.id,
         NEEDS_REAUTH:                         new_tokens + status=ACTIVE)
          update(sibling)

  (skips ACTIVE siblings              (all siblings get fresh tokens,
   with stale tokens)                  even ACTIVE ones)
```

### 4.4 Fix 3: Retry Before Marking `needs_reauth`

On `invalid_grant`, before giving up and marking the connection `needs_reauth`, re-read from the database. A sibling may have already refreshed and propagated the new tokens:

```
  invalid_grant received
       │
       ▼
  re-read connection from DB
       │
       ├── token_expires_at > now? (fresh tokens propagated by sibling)
       │       └── YES → use these tokens, return success
       │
       └── NO (still stale) → mark needs_reauth, raise exception
```

### 4.5 Fix 4: Single Token Path for All Services

All services are refactored to call `ensure_valid_token` via `XeroConnectionService`. No direct calls to `refresh_tokens` or raw `encryption.decrypt(access_token)`:

```
  ALL callers
      │
      ▼
  connection_service.ensure_valid_token(connection_id)
      │
      ├── token valid → return decrypted access_token
      │
      └── needs_refresh → _refresh_with_lock(grant_id)
              │
              ├── refresh success → return new access_token
              │
              └── refresh failed → raise XeroAuthRequiredError
                      │
                      ▼
              caller shows specific reconnect prompt
```

**Services to migrate**:

| Service | Current | Fix |
|---------|---------|-----|
| `data_service._get_connection_with_token` | `refresh_tokens()` direct | `ensure_valid_token()` |
| `data_service._ensure_valid_token` (loop) | `ensure_valid_token()` ✓ | Keep, remove start-of-sync duplicate |
| `report_service._get_connection_and_token` | `refresh_tokens()` direct | `ensure_valid_token()` |
| `payroll_service` | raw decrypt, no check | `ensure_valid_token()` |
| `xpm_service` | raw decrypt, no check | `ensure_valid_token()` |
| `bas/router` get_org_tax_rates | raw decrypt, silent 401 | `ensure_valid_token()` |
| `xero_writeback` task | bespoke inline refresh, no lock | `ensure_valid_token()` |

### 4.6 Fix 5: Redis Fallback

```python
async def _refresh_with_lock(self, grant_id: str) -> XeroConnection:
    try:
        redis = aioredis.from_url(self.settings.redis.url)
        lock = redis.lock(f"xero_token_refresh:grant:{grant_id}", timeout=30, blocking_timeout=15)
        acquired = await lock.acquire(blocking=True)
        # ... normal lock path
    except (ConnectionError, TimeoutError, RedisError) as e:
        logger.warning("Redis unavailable for token refresh lock, attempting without lock", error=str(e))
        return await self._refresh_without_lock(connection_id)
        # best-effort: small race risk accepted, much better than total failure
```

### 4.7 Fix 6: Ensure `token_expires_at` Is Always Set

OAuth callback and every token storage write must always set `token_expires_at`. Add a database check: if `None`, treat as expired and refresh once to populate the field.

---

## 5. Schema Change: `oauth_grant_id`

Add `oauth_grant_id: UUID` to `XeroConnection`. All connections created from the same OAuth callback share the same `oauth_grant_id`.

```sql
ALTER TABLE xero_connections
  ADD COLUMN oauth_grant_id UUID;

-- Back-fill: group existing connections by tenant + approximate creation time
-- (connections created within same bulk-import callback window share a grant)
-- This requires a one-time migration script.

CREATE INDEX ix_xero_connections_grant_id ON xero_connections (oauth_grant_id);
```

**Migration strategy for existing rows**: Group connections by `tenant_id` that share identical initial `refresh_token` values (compare encrypted blobs — same blob = same original token). Assign the same `oauth_grant_id` UUID to each group. For any connections where this cannot be determined, assign each its own unique `oauth_grant_id` (they become single-member grant groups, no siblings).

---

## 6. Global Re-Auth Notification (P2)

### 6.1 Backend: Connections Status Endpoint

The existing `GET /api/v1/integrations/xero/connections` endpoint already returns connection status. The frontend needs to include `needs_reauth` connections in a global state check.

No new endpoint required — add a lightweight `GET /api/v1/integrations/xero/status` that returns just the summary:

```json
{
  "needs_reauth": [
    { "connection_id": "...", "org_name": "Smith & Co" },
    { "connection_id": "...", "org_name": "Jones Pty Ltd" }
  ]
}
```

### 6.2 Frontend: Global Auth State

```
  App Layout (authenticated pages)
       │
       ▼
  XeroAuthProvider (React context)
       │
       ├── polls GET /xero/status on page load + navigation
       │
       ├── exposes: { needsReauth: Connection[] }
       │
       └── renders: <XeroReauthBanner /> when needsReauth.length > 0


  XeroReauthBanner
       │
       ├── position: fixed bottom bar or top banner (non-blocking)
       │
       ├── content: "Xero reconnection needed: Smith & Co, Jones Pty Ltd"
       │             [Reconnect] button
       │
       └── on [Reconnect] click:
               save current URL to sessionStorage
               initiate OAuth flow for first needs_reauth connection
               (user reconnects one at a time if multiple)
```

### 6.3 Return-to-Origin Flow

```
  User on /clients/abc/bas-tracker
       │
       └── clicks Reconnect in banner
               │
               ▼
       sessionStorage.setItem('xero_reauth_return_to', '/clients/abc/bas-tracker')
               │
               ▼
       POST /api/v1/integrations/xero/connect → { auth_url, state }
               │
               ▼
       window.location.href = auth_url (Xero consent screen)
               │
               ▼
       Xero redirects to /settings/integrations/xero/callback?code=...&state=...
               │
               ▼
       GET /api/v1/integrations/xero/callback (backend exchanges code → tokens)
               │
               ▼
       callback page reads sessionStorage.getItem('xero_reauth_return_to')
               │
               ├── URL found → router.push('/clients/abc/bas-tracker')
               │
               └── no URL → router.push('/settings/integrations')
```

---

## 7. Complete Fixed Token Refresh Flow

```
  Sync task starts for Connection A (grant: G1)
       │
       ▼
  connection_service.ensure_valid_token(connection_id=A)
       │
       ├── token valid (>5min remaining) → return access_token ──► done
       │
       └── needs_refresh (≤5min remaining)
               │
               ▼
       _refresh_with_lock(grant_id=G1)
               │
               ├── try acquire Redis lock: xero_token_refresh:grant:G1
               │         │
               │         ├── ACQUIRED
               │         │       │
               │         │       ▼
               │         │   re-read ALL connections in grant G1 from DB
               │         │       │
               │         │       ├── still needs_refresh?
               │         │       │       │
               │         │       │       └── YES: call Xero /token endpoint
               │         │       │                     │
               │         │       │                 SUCCESS: new T2, R2
               │         │       │                     │
               │         │       │                 update ALL grant-G1 connections:
               │         │       │                   access_token = T2
               │         │       │                   refresh_token = R2
               │         │       │                   token_expires_at = now+30min
               │         │       │                   status = ACTIVE
               │         │       │                     │
               │         │       │                 release lock
               │         │       │                 return fresh connection ──► done
               │         │       │
               │         │       │                 FAILURE (invalid_grant):
               │         │       │                     │
               │         │       │                 re-read DB (sibling may have refreshed)
               │         │       │                     │
               │         │       │                 ├── tokens fresh? → use them ──► done
               │         │       │                 └── still stale:
               │         │       │                     mark needs_reauth
               │         │       │                     release lock
               │         │       │                     raise XeroAuthRequiredError
               │         │       │
               │         │       └── NO longer needs_refresh (sibling refreshed while waiting):
               │         │               release lock
               │         │               return fresh connection ──► done
               │         │
               │         ├── TIMEOUT (15s, holder still working)
               │         │       re-read DB → return whatever is there
               │         │       (may be stale — caller will get 401 → retry or surface error)
               │         │
               │         └── Redis UNAVAILABLE
               │                 log warning
               │                 best-effort refresh without lock
               │                 (accept race risk)
               │
               └── lock infrastructure failure propagates as warning, not hard failure
```

---

## 8. Files to Change

### Backend

| File | Change |
|------|--------|
| `modules/integrations/xero/models.py` | Add `oauth_grant_id` column to `XeroConnection`; fix `needs_refresh` for `None` expiry |
| `modules/integrations/xero/connection_service.py` | Change lock key to grant-scoped; propagate tokens to all siblings; retry-before-reauth; Redis fallback |
| `modules/integrations/xero/data_service.py` | Remove `_get_connection_with_token` unlocked refresh; consolidate to `ensure_valid_token` |
| `modules/integrations/xero/report_service.py` | Replace `refresh_tokens` direct call with `ensure_valid_token` |
| `modules/integrations/xero/payroll_service.py` | Replace raw decrypt with `ensure_valid_token` |
| `modules/integrations/xero/xpm_service.py` | Replace raw decrypt with `ensure_valid_token` |
| `modules/integrations/xero/router.py` | Fix `get_org_tax_rates` raw decrypt; add `GET /status` endpoint |
| `modules/integrations/xero/oauth_service.py` | Set `oauth_grant_id` on all connections created from same callback |
| `tasks/xero_writeback.py` | Replace inline refresh loop with `ensure_valid_token` |
| `alembic/versions/` | Migration: add `oauth_grant_id`, back-fill existing rows |

### Frontend

| File | Change |
|------|--------|
| `app/layout.tsx` (or root auth layout) | Wrap with `XeroAuthProvider` |
| `lib/xero-auth-context.tsx` (new) | React context: polls `/xero/status`, exposes `needsReauth` |
| `components/xero/XeroReauthBanner.tsx` (new) | Persistent non-blocking notification with reconnect action |
| `app/settings/integrations/xero/callback/page.tsx` | Already handles return-to-origin for Tax Planning; extend to all pages |

---

## 9. What Is Not Changing

- The OAuth2 PKCE flow itself — no changes to how initial authorization works
- Token encryption (AES-256-GCM) — unchanged
- The `XeroConnectionStatus` enum — `needs_reauth` remains the signal for genuine re-auth
- Xero's consent screen — org selection is controlled by Xero; we cannot skip it for genuine re-auth

---

## 10. Testing Strategy

### Robustness Tests (P1)

1. **Concurrent refresh test**: Create a tenant with 3 connections sharing one grant. Simultaneously fire `ensure_valid_token` on all three from separate async tasks. Assert: exactly one Xero refresh call, all three connections have the new tokens, zero `needs_reauth` transitions.

2. **`invalid_grant` retry test**: Mock Xero to return `invalid_grant` for the first call, then succeed on the second (simulating sibling already refreshed). Assert: no `needs_reauth`, fresh tokens used.

3. **Redis-down test**: Take Redis offline. Trigger `ensure_valid_token` with a near-expired token. Assert: refresh succeeds (best-effort, no lock), sync completes, warning logged.

4. **Sibling propagation test**: Refresh one connection. Assert all siblings in the grant group have updated tokens regardless of their prior status.

5. **Single code path test**: Assert no test or production code calls `refresh_tokens()` directly or `encryption.decrypt(access_token)` outside of `ensure_valid_token`.

### Re-Auth UX Tests (P2)

1. Set a connection to `needs_reauth`. Navigate to BAS tracker. Assert banner visible with org name.
2. Click reconnect from BAS tracker. Complete OAuth. Assert return to BAS tracker URL.
3. Reconnect successfully. Assert banner no longer shown.
