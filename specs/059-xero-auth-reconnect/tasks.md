# Tasks: Xero Authentication Robustness & Reconnection UX

**Input**: Design documents from `/specs/059-xero-auth-reconnect/`
**Branch**: `059-xero-auth-reconnect` (already created)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story this task belongs to (US1 = token refresh robustness, US2 = global notification, US3 = sync error clarity)

---

## Phase 0: Git Setup

Already on branch `059-xero-auth-reconnect`. No action needed.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Database migration and model changes that block all user stories.

**⚠️ CRITICAL**: Must be complete before any user story work begins — `oauth_grant_id` is required by the lock logic (US1) and the status query (US2).

- [x] T001 Write Alembic migration — NOT NEEDED: `auth_event_id` already exists on `xero_connections` and serves as the grant group key: add `oauth_grant_id UUID` to `xero_connections`, back-fill existing rows by grouping on `(tenant_id, DATE_TRUNC('minute', created_at))`, back-fill `token_expires_at = NOW() + INTERVAL '30 minutes'` where NULL — in `backend/alembic/versions/` (create new revision)
- [x] T002 Add `oauth_grant_id: Mapped[uuid.UUID]` field to `XeroConnection` model — NOT NEEDED: using existing `auth_event_id` field
- [x] T003 Run `uv run alembic upgrade head` — NOT NEEDED: no schema changes required

**Checkpoint**: Migration applied, model updated — user story work can begin.

---

## Phase 2: User Story 1 — Silent Token Refresh Never Triggers Re-Auth Erroneously (Priority: P1) 🎯 MVP

**Goal**: Fix the race condition. After this phase, concurrent syncs never produce erroneous `needs_reauth` transitions.

**Independent Test**: Run `test_concurrent_refresh_no_invalid_grant` — two sibling connections simultaneously hit the refresh window; assert exactly one Xero API call and zero `needs_reauth` transitions.

### Tests for User Story 1

- [x] T004 [P] [US1] Write concurrent refresh test: lock winner re-reads DB; if sibling already refreshed (tokens fresh), skip Xero call and return immediately — in `backend/tests/unit/modules/integrations/xero/test_connection_service.py`
- [x] T005 [P] [US1] Write Redis-unavailable test: Redis raises `ConnectionError`, assert refresh still succeeds via best-effort path without lock — in `backend/tests/unit/modules/integrations/xero/test_connection_service.py`
- [x] T006 [P] [US1] Write retry-before-reauth test: `invalid_grant` received but sibling already propagated fresh tokens into DB, assert no `needs_reauth` transition — in `backend/tests/unit/modules/integrations/xero/test_connection_service.py`
- [x] T007 [P] [US1] Write sibling propagation test: after refresh of one connection, all grant siblings (including needs_reauth) have updated tokens and status=ACTIVE — in `backend/tests/unit/modules/integrations/xero/test_connection_service.py`

### Implementation for User Story 1

- [x] T008 [US1] Update `oauth_service.handle_callback` to generate one `oauth_grant_id = uuid.uuid4()` and assign it to all connections created in the same callback in `backend/app/modules/integrations/xero/oauth_service.py`
- [x] T009 [US1] Rewrite `_refresh_with_lock` in `connection_service.py` to: (1) use lock key `xero_token_refresh:grant:{connection.oauth_grant_id}`, (2) after successful refresh query all connections with same `oauth_grant_id` + `tenant_id` and update all with new tokens, (3) on `invalid_grant` re-read DB and return fresh tokens if propagated by sibling, (4) catch `RedisError`/`ConnectionError` and fall back to best-effort refresh without lock — in `backend/app/modules/integrations/xero/connection_service.py`
- [x] T010 [US1] Remove the unlocked `refresh_tokens()` call in `data_service._get_connection_with_token` and replace with `await connection_service.ensure_valid_token(connection_id)`; remove duplicate token acquisition at sync start (keep only the per-pagination-loop `_ensure_valid_token` call) — in `backend/app/modules/integrations/xero/data_service.py`
- [x] T011 [P] [US1] Replace `refresh_tokens()` direct call in `report_service._get_connection_and_token` with `await connection_service.ensure_valid_token(connection_id)` — in `backend/app/modules/integrations/xero/report_service.py`
- [x] T012 [P] [US1] Replace raw `encryption.decrypt(connection.access_token)` in `payroll_service` with `await connection_service.ensure_valid_token(connection_id)` — in `backend/app/modules/integrations/xero/payroll_service.py`
- [x] T013 [P] [US1] Replace raw `encryption.decrypt(connection.access_token)` in `xpm_service` with `await connection_service.ensure_valid_token(connection_id)` — in `backend/app/modules/integrations/xero/xpm_service.py`
- [x] T014 [US1] Replace raw `encryption.decrypt(connection.access_token)` in `get_org_tax_rates` route with `await connection_service.ensure_valid_token(connection_id)`; catch `XeroAuthRequiredError` and raise `HTTPException(401)` instead of returning `{}` — in `backend/app/modules/bas/router.py`
- [x] T015 [US1] Remove bespoke inline token refresh loop in `xero_writeback` task; replace with `await connection_service.ensure_valid_token(connection_id)` before the writeback loop — in `backend/app/tasks/xero_writeback.py`
- [x] T016 [US1] Add `XeroAuthRequiredError` domain exception (if not already in exceptions.py) to `backend/app/modules/integrations/xero/exceptions.py`; ensure `connection_service.ensure_valid_token` raises it on genuine reauth-needed, and that existing router handlers convert it to `HTTP 401`

**Checkpoint**: All T004–T007 tests pass. Run `uv run pytest backend/tests/unit/modules/integrations/xero/` — zero failures. Concurrent refresh no longer produces `needs_reauth`.

---

## Phase 3: User Story 2 — Genuine Re-Auth Is Surfaced Everywhere (Priority: P2)

**Goal**: When re-auth is genuinely needed, a persistent notification appears on every page with a working one-click reconnect that returns the user to their originating page.

**Independent Test**: Set a Xero connection to `needs_reauth` in DB. Navigate to `/clients`, `/bas`, and `/dashboard`. Assert the banner is visible on all three with the org name and a working reconnect button. After reconnecting, assert banner is gone.

### Tests for User Story 2

- [ ] T017 [P] [US2] Write integration test for `GET /api/v1/integrations/xero/status`: returns `needs_reauth` list when connections are in that state, empty list when all active — in `backend/tests/integration/api/test_xero_status.py`
- [ ] T018 [P] [US2] Write unit test for `XeroReauthBanner`: renders org names from `needsReauth` prop, hides when array is empty — in `frontend/src/components/xero/__tests__/XeroReauthBanner.test.tsx`

### Implementation for User Story 2

- [ ] T019 [US2] Add `XeroAuthStatusResponse` and `XeroConnectionSummary` Pydantic schemas to `backend/app/modules/integrations/xero/schemas.py`
- [ ] T020 [US2] Add `GET /status` endpoint to `backend/app/modules/integrations/xero/router.py` — queries `connection_repo.list_by_tenant`, filters for `needs_reauth`, returns `XeroAuthStatusResponse`
- [ ] T021 [US2] Create `frontend/src/lib/xero-auth-context.tsx`: React context + `XeroAuthProvider` component that polls `GET /api/v1/integrations/xero/status` with TanStack Query (`staleTime: 60_000`), exposes `{ needsReauth, isChecking, refetch }` — only active for practice-user authenticated sessions (not portal)
- [ ] T022 [US2] Create `frontend/src/components/xero/XeroReauthBanner.tsx`: persistent non-blocking banner (fixed bottom or top), lists affected org names, single "Reconnect" button that stores `window.location.href` to `sessionStorage('xero_reauth_return_to')` and initiates Xero OAuth flow via existing `XeroConnectButton` logic
- [ ] T023 [US2] Wrap authenticated layout with `XeroAuthProvider` and render `<XeroReauthBanner />` in `frontend/src/app/(dashboard)/layout.tsx` (or equivalent authenticated root layout)
- [ ] T024 [US2] Extend `frontend/src/app/settings/integrations/xero/callback/page.tsx` to read `sessionStorage.getItem('xero_reauth_return_to')` for all reconnect flows (it currently only handles Tax Planning; extend the return URL to cover all pages) and remove the Tax Planning-specific `xero_reauth_return_to` logic from `TaxPlanningWorkspace.tsx`
- [ ] T025 [US2] Add TypeScript type `XeroAuthStatus` matching the OpenAPI contract to `frontend/src/types/xero.ts`

**Checkpoint**: `T017` integration test passes. Banner visible on all pages when `needs_reauth` connection exists. Reconnect returns user to origin page.

---

## Phase 4: User Story 3 — Sync Operations Fail Gracefully on Auth Error (Priority: P3)

**Goal**: Any sync operation that encounters `needs_reauth` shows a specific, actionable error — not a generic one. Raw-decrypt paths that currently return silent empty results are fixed.

**Independent Test**: With a connection in `needs_reauth`, trigger a manual Xero sync and a BAS tax rates fetch. Assert both show a specific "Xero reconnection required" error with a reconnect link — not a generic error and not an empty result.

### Tests for User Story 3

- [ ] T026 [P] [US3] Write test: sync task encounters `XeroAuthRequiredError`, Celery task marks job as failed with specific error message containing org name — in `backend/tests/unit/tasks/test_xero_sync.py`
- [ ] T027 [P] [US3] Write test: BAS `get_org_tax_rates` with `needs_reauth` connection returns `HTTP 401` with `{ error: "xero_reauth_required", org_name: "..." }` body — in `backend/tests/integration/api/test_bas_xero.py`

### Implementation for User Story 3

- [ ] T028 [US3] Update Celery sync task error handling in `backend/app/tasks/xero.py` to catch `XeroAuthRequiredError` and store a structured error message on the sync job record (`{ "error": "xero_reauth_required", "org_name": "...", "connection_id": "..." }`) instead of a generic exception message
- [ ] T029 [US3] Update `bas/router.py` `get_org_tax_rates` route (already partly fixed in T014) to return a structured `ErrorResponse` with `code: "XERO_REAUTH_REQUIRED"` and `org_name` when `XeroAuthRequiredError` is raised, consistent with the `ErrorResponse` schema in the OpenAPI contract
- [ ] T030 [US3] Update frontend sync error display components to check for `code === "XERO_REAUTH_REQUIRED"` and render a specific inline message with a reconnect link rather than a generic error — update `frontend/src/components/xero/SyncStatusBadge.tsx` (or equivalent sync error display component)

**Checkpoint**: `T026` and `T027` tests pass. Sync errors display specific reconnect-required messages.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T031 [P] Add audit event logging to `connection_service.py`: emit `integration.xero.token_refreshed` on successful refresh and `integration.xero.refresh_failed` on failure using `audit_event()` from `app.core.audit`
- [ ] T032 [P] Add audit event logging for re-auth flows: emit `integration.xero.reauth_initiated` in the `/connect` route when initiated from a `needs_reauth` context, `integration.xero.reauth_succeeded` / `reauth_failed` in the `/callback` route — in `backend/app/modules/integrations/xero/router.py`
- [ ] T033 [P] Update `docs/xero-auth-robustness.md` to reflect any implementation deviations from the design (expected to be minor)
- [ ] T034 Run full validation: `cd backend && uv run ruff check . && uv run pytest && cd ../frontend && npm run lint && npx tsc --noEmit`

---

## Phase FINAL: PR & Merge

- [ ] TFINAL-1 Ensure all tests pass: `cd backend && uv run pytest` — all green
- [ ] TFINAL-2 Run linting and type checking: `cd backend && uv run ruff check . && cd ../frontend && npx tsc --noEmit`
- [ ] TFINAL-3 Push branch and create PR: `git push -u origin 059-xero-auth-reconnect` then `gh pr create --title "fix: Xero token refresh race condition + global reauth notification" --body "..."`
- [ ] TFINAL-4 Address review feedback
- [ ] TFINAL-5 Squash merge to main, delete branch
- [ ] TFINAL-6 Update `specs/ROADMAP.md` — mark 059 as COMPLETE

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Must complete first — `oauth_grant_id` column is required by all subsequent phases
- **Phase 2 (US1)**: Depends on Phase 1. The core fix — must ship before US2/US3 as it eliminates most re-auth occurrences
- **Phase 3 (US2)**: Depends on Phase 1. Can run in parallel with US1 after Phase 1 is complete (different files — backend status endpoint + all frontend work)
- **Phase 4 (US3)**: Depends on US1 being complete (uses `XeroAuthRequiredError` defined in US1). T028–T030 are sequential within US3
- **Phase 5 (Polish)**: Depends on all user stories complete

### Within User Story 1

- T004–T007 (tests): write first, verify they FAIL before implementation
- T008 (oauth_service): independent, can run in parallel with T009
- T009 (connection_service rewrite): core change, must complete before T010–T015
- T010–T015: can run in parallel after T009 (different files)
- T016 (exceptions): can run in parallel with T009

### Parallel Opportunities After Phase 1

```bash
# US1 backend + US2 backend + US2 frontend can all proceed in parallel:
# Developer A: T008-T016 (connection service + service consolidation)
# Developer B: T019-T020 (backend status endpoint)
# Developer C: T021-T025 (frontend context + banner + callback)
```

---

## Implementation Strategy

### MVP: User Story 1 Only (stops the daily re-auth storms)

1. Complete Phase 1 (migration)
2. Complete Phase 2 (US1 — lock fix + token path consolidation)
3. **STOP and VALIDATE**: Run concurrent refresh test 20 times — zero `needs_reauth` transitions
4. Deploy — the most impactful fix ships first

### Full Delivery

1. Phase 1 → Phase 2 (US1) → validate → deploy
2. Phase 3 (US2) → validate → deploy (banner visible everywhere)
3. Phase 4 (US3) → validate → deploy (better error messages)
4. Phase 5 (Polish) → PR → merge

---

## Task Count Summary

| Phase | Tasks | Parallelizable |
|-------|-------|----------------|
| Phase 1: Setup | 3 | 0 |
| Phase 2: US1 (P1) | 13 | 8 |
| Phase 3: US2 (P2) | 9 | 3 |
| Phase 4: US3 (P3) | 5 | 2 |
| Phase 5: Polish | 4 | 3 |
| Final | 6 | 0 |
| **Total** | **40** | **16** |
