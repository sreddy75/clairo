# Implementation Plan: Xero Authentication Robustness & Reconnection UX

**Branch**: `059-xero-auth-reconnect` | **Date**: 2026-04-16 | **Spec**: [spec.md](./spec.md)

## Summary

Fix a token refresh race condition that causes erroneous `needs_reauth` state transitions multiple times per day for practices with multiple Xero connections. The root cause is that the Redis lock protecting token rotation is scoped per `connection_id`, but sibling connections (sharing the same OAuth grant) each hold their own lock and race to rotate the same refresh token — only one wins, the others get `invalid_grant`. Secondary fix: consolidate 5+ bypassed/unlocked token paths into a single guarded path. Tertiary: add a global re-auth notification so genuine re-auth needs are visible across all pages.

---

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, aioredis, React 18, shadcn/ui, TanStack Query
**Storage**: PostgreSQL 16 — **no schema changes**. `auth_event_id` already exists on `xero_connections` and serves as the grant group key.
**Testing**: pytest + pytest-asyncio, factory_boy, httpx; Jest + React Testing Library (frontend)
**Target Platform**: Linux / ECS Fargate (backend), Vercel (frontend)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Token refresh adds <100ms overhead to any sync operation; `/xero/status` endpoint responds in <50ms
**Constraints**: Redis outage MUST NOT block sync operations; zero erroneous `needs_reauth` transitions under concurrent load
**Scale/Scope**: Tenants with 1–20 Xero connections; Celery workers running concurrent syncs

---

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Modular monolith — all changes within `modules/integrations/xero/` | ✓ PASS | No new modules; changes are internal to the xero integration module |
| Repository pattern — no direct DB access outside repositories | ✓ PASS | All DB writes go through existing `XeroConnectionRepository` |
| Multi-tenancy — grant grouping scoped by `tenant_id` | ✓ PASS | Grant queries always filter by `tenant_id` |
| Domain exceptions in service layer, not HTTPException | ✓ PASS | New `XeroAuthRequiredError` extends domain exception base |
| Audit logging for auth events | ✓ PASS | `integration.xero.token_refreshed`, `reauth_initiated/succeeded/failed` defined in spec |
| No cross-module internal imports | ✓ PASS | Services in `data_service`, `report_service` etc. call `XeroConnectionService.ensure_valid_token()` via service interface |
| Tests: 80% unit coverage, 100% integration coverage for changed endpoints | REQUIRED | Concurrent refresh tests are critical gate for P1 |
| shadcn/ui only, CSS variable tokens, no hardcoded colors | REQUIRED | Frontend banner uses existing design system tokens |

**No constitution violations. No complexity tracking required.**

---

## Project Structure

### Documentation (this feature)

```text
specs/059-xero-auth-reconnect/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   └── xero-status.yaml ← OpenAPI for new /status endpoint
└── tasks.md             ← Phase 2 output (/speckit.tasks)
```

### Source Code

```text
backend/
├── app/
│   ├── modules/integrations/xero/
│   │   ├── models.py               ← no changes (auth_event_id already exists)
│   │   ├── connection_service.py   ← REWRITE lock + propagation logic
│   │   ├── data_service.py         ← REMOVE unlocked refresh path
│   │   ├── report_service.py       ← REMOVE direct refresh_tokens call
│   │   ├── payroll_service.py      ← REPLACE raw decrypt with ensure_valid_token
│   │   ├── xpm_service.py          ← REPLACE raw decrypt with ensure_valid_token
│   │   ├── router.py               ← ADD GET /status endpoint; fix raw decrypt in get_org_tax_rates
│   │   ├── oauth_service.py        ← SET auth_event_id from org in regular OAuth path (was only set in bulk import)
│   │   └── schemas.py              ← ADD XeroAuthStatusResponse schema
│   └── tasks/
│       └── xero_writeback.py       ← REPLACE inline refresh loop with ensure_valid_token
├── alembic/versions/
│   └── (no migration needed)
└── tests/
    ├── unit/modules/integrations/xero/
    │   ├── test_connection_service.py   ← concurrent refresh tests
    │   └── test_token_propagation.py
    └── integration/api/
        └── test_xero_status.py          ← /status endpoint tests

frontend/
└── src/
    ├── lib/
    │   └── xero-auth-context.tsx        ← NEW: global needs_reauth state
    ├── components/xero/
    │   └── XeroReauthBanner.tsx         ← NEW: persistent notification
    ├── app/
    │   ├── layout.tsx                   ← WRAP with XeroAuthProvider
    │   └── settings/integrations/xero/callback/page.tsx  ← extend return-to-origin
    └── types/
        └── xero.ts                      ← ADD XeroAuthStatus type
```

---

## Phase 0: Research

**All unknowns resolved via codebase analysis (2026-04-16). See `research.md` for decisions.**

Key decisions made:
1. Grant group identified by `auth_event_id` (existing column, already populated by bulk import) — no new column needed. Regular OAuth path updated to also set `auth_event_id` from `org.auth_event_id` (Xero API returns `authEventId` on the org object).
2. Lock key: `xero_token_refresh:event:{auth_event_id}` (fallback to `connection_id` when `auth_event_id` is None)
3. Sibling propagation: update ALL connections in grant group after refresh, regardless of status
4. Retry-before-reauth: on `invalid_grant`, re-read DB once before marking `needs_reauth`
5. Redis fallback: best-effort refresh without lock on `RedisError` / `ConnectionError`
6. No new endpoint for global status beyond simple `GET /status` returning `needs_reauth` list
7. Frontend polling: on page load + navigation (TanStack Query with `staleTime: 60_000`)

---

## Phase 1: Design & Contracts

### Data Model Changes

See `data-model.md` for full entity definitions.

**No schema changes.** `auth_event_id STRING(50)` already exists on `xero_connections` with an index. It is populated by Xero's API (the `authEventId` field on the org object from `/connections`) and was already being set during bulk import. The regular OAuth path (`oauth_service._upsert_connection`) was not setting it — that gap is now closed.

All fixes are behavioral (lock key scope, propagation logic, service consolidation).

### API Contracts

See `contracts/xero-status.yaml` for OpenAPI definition.

**New endpoint**: `GET /api/v1/integrations/xero/status`
```
Response 200:
{
  "needs_reauth": [
    { "connection_id": "uuid", "org_name": "Smith & Co" }
  ],
  "total_connections": 3,
  "active_connections": 2
}
```

**No other API changes.** The reconnect flow reuses the existing `POST /connect` and `GET /callback` endpoints unchanged.

### Connection Service: Revised `ensure_valid_token` Contract

```python
async def ensure_valid_token(self, connection_id: UUID) -> str:
    """
    Returns a valid, decrypted Xero access token for the given connection.

    Behavior:
    - If token is valid (>5min remaining): return immediately, no lock
    - If token needs refresh: acquire grant-scoped Redis lock, refresh once,
      propagate to all grant siblings, release lock, return new token
    - On invalid_grant: re-read DB (sibling may have already refreshed);
      if fresh tokens found, return them; else raise XeroAuthRequiredError
    - On Redis unavailable: attempt best-effort refresh without lock, log warning
    - On any other refresh failure: raise XeroAuthRequiredError

    Raises:
        XeroAuthRequiredError: Connection needs user re-authorization
        XeroConnectionNotFoundError: Connection does not exist
    """
```

### Frontend: XeroAuthProvider Contract

```typescript
interface XeroAuthContextValue {
  needsReauth: Array<{ connectionId: string; orgName: string }>;
  isChecking: boolean;
  refetch: () => void;
}

// Polls GET /api/v1/integrations/xero/status
// staleTime: 60s (re-check on navigation, not every render)
// Only active on authenticated practice-user pages (not portal)
```
