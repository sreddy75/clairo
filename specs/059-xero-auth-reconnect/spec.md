# Feature Specification: Xero Authentication Robustness & Reconnection UX

**Feature Branch**: `059-xero-auth-reconnect`
**Created**: 2026-04-16
**Status**: Draft

## Background & Context

Clairo connects to Xero via OAuth2 with PKCE. Access tokens expire every 30 minutes and are meant to be renewed automatically using refresh tokens — users should never see this. Refresh tokens themselves expire after 60 days of inactivity or if the user revokes access in Xero.

**The problem**: Users are seeing re-authentication prompts multiple times per day. This should not be happening. Investigation reveals the root cause is a combination of:

1. **Rotating refresh tokens + broken lock scope**: Xero issues a new refresh token on every refresh and immediately invalidates the old one. The existing Redis lock is scoped per `connection_id`, but multiple connections can share the same OAuth grant (from bulk import). When two connections from the same grant simultaneously hit the refresh window, each holds its own lock and both try to refresh the same token — one wins, one gets `invalid_grant` and marks itself `needs_reauth`.

2. **Broken sibling propagation**: After a successful refresh, only siblings already in `needs_reauth` get the new tokens. Active siblings (holding the now-invalidated refresh token) are left to fail on their next call — they then each fail in turn, cascade-marking multiple connections `needs_reauth`.

3. **Multiple unlocked refresh paths**: `data_service`, `report_service`, `payroll_service`, `xpm_service`, and the writeback task all call `refresh_tokens` directly, bypassing the Redis lock entirely. These race with each other and with the lock-guarded path.

4. **`data_service` races with itself**: A single sync task calls unlocked `refresh_tokens` at the start, then calls locked `ensure_valid_token` in every pagination loop — both can fire on the same token within a single task run.

5. **Raw decrypt paths with no expiry check**: `payroll_service`, `xpm_service`, and one BAS router route decrypt and use access tokens directly with no refresh check — they silently 401 when the token has expired.

6. **Redis unavailability causes sync failure**: If Redis is down, `lock.acquire()` raises and the entire sync operation fails, even if the token is perfectly valid.

The secondary problem is a UX gap: when re-auth is genuinely needed (refresh token expired after 60 days of inactivity), there is no global notification — users only see the prompt on the Settings page or Tax Planning workspace, not anywhere else in the app.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Silent Token Refresh Never Triggers Re-Auth Erroneously (Priority: P1)

An accountant uses Clairo daily. Multiple syncs run throughout the day (scheduled and manual). Access tokens expire every 30 minutes. The accountant should never be asked to re-authenticate Xero unless their refresh token has genuinely expired (60 days of non-use) or they explicitly revoked access in Xero.

Today: re-auth prompts appear multiple times per day due to concurrent refresh races. After this fix: zero erroneous re-auth prompts.

**Why this priority**: This is the root cause of the reported issue and affects every user who does frequent Xero syncs. Everything else is secondary to stopping the false re-auth storms.

**Independent Test**: Simulate concurrent sync tasks for a tenant with 2+ Xero connections sharing the same OAuth grant. Run them simultaneously 20 times. Confirm zero `invalid_grant` errors and zero `needs_reauth` state transitions.

**Acceptance Scenarios**:

1. **Given** a tenant has multiple Xero connections sharing the same OAuth grant, **When** two sync tasks execute simultaneously and both connections are within the 5-minute token refresh window, **Then** exactly one refresh occurs, the new tokens are propagated to all connections, and neither connection is marked `needs_reauth`.

2. **Given** a refresh is in progress, **When** another task tries to use the same connection's token and cannot acquire the lock within 15 seconds, **Then** it waits for the refresh to complete and uses the fresh token — it does not proceed with a stale token.

3. **Given** Redis is temporarily unavailable, **When** a sync task needs to refresh a token, **Then** the task attempts a best-effort refresh without the lock (accepting the small race risk) rather than failing the entire sync operation.

4. **Given** a successful token refresh occurs for one connection, **When** sibling connections share the same OAuth grant, **Then** all siblings (regardless of current status) are updated with the new access and refresh tokens atomically.

5. **Given** `data_service`, `report_service`, `payroll_service`, `xpm_service`, and the writeback task all need a valid token, **When** they acquire the token, **Then** they all go through a single consistent path that checks expiry and refreshes with lock protection — no raw decrypts.

---

### User Story 2 — Genuine Re-Auth Is Surfaced Everywhere (Priority: P2)

When re-auth is genuinely required (refresh token expired after 60+ days), the accountant should see a clear, persistent notification from anywhere in the app — not just on the Settings page or Tax Planning workspace. The notification should name the affected org, allow reconnection in one click, and return them to where they were.

**Why this priority**: Once the robustness fix eliminates false re-auth storms, genuine re-auth needs to be handled gracefully. Currently the notification is only in two places.

**Independent Test**: Set a Xero connection to `needs_reauth` in the DB. Navigate to BAS tracker, client page, and dashboard. Confirm the reconnect notification appears on all three pages with the org name and a working reconnect action that returns the user to the originating page.

**Acceptance Scenarios**:

1. **Given** any Xero connection is in `needs_reauth` state, **When** an authenticated practice user (accountant) navigates to any page in the application, **Then** a persistent, non-blocking notification is visible identifying the affected Xero org by name with a reconnect action.

2. **Given** the notification is visible, **When** the accountant clicks reconnect, **Then** they complete the Xero OAuth flow and are returned to the exact page they were on when they initiated reconnection.

3. **Given** reconnection completes successfully, **When** the user returns to the app, **Then** the notification is no longer shown.

4. **Given** multiple connections are in `needs_reauth`, **Then** the notification lists all affected org names.

---

### User Story 3 — Sync Operations Fail Gracefully on Auth Error (Priority: P3)

When a sync operation fails because a connection genuinely needs re-auth (after the robustness fix, this should be rare), the error shown to the user must be specific and actionable — not a generic "something went wrong".

**Why this priority**: Defense-in-depth. Even with the robustness fix, edge cases can still produce genuine auth failures.

**Acceptance Scenarios**:

1. **Given** a Xero sync is triggered and the connection is in `needs_reauth`, **When** the sync attempts to fetch data, **Then** the error message explicitly states Xero reconnection is required and includes a direct reconnect action.

2. **Given** a raw-decrypt code path (payroll, XPM, BAS tax rates) encounters an expired token, **When** it gets a 401 from Xero, **Then** it marks the connection `needs_reauth` and surfaces a specific reconnect prompt rather than returning an empty result silently.

---

### Edge Cases

- What if Redis is down during a refresh? Attempt refresh without lock; log a warning. Accept the small race risk — it is better than failing the sync entirely.
- What if two tasks simultaneously acquire the lock for the same OAuth grant (different shards/workers) due to Redis split-brain? After a successful refresh, always re-read from DB before returning; the second writer will detect the token already changed and abort rather than double-rotate.
- What if a sibling connection propagation write fails (DB error)? Log and alert but do not fail the primary connection's refresh. The sibling will attempt its own refresh on next call and encounter `invalid_grant` — this should now trigger a retry-then-propagate loop rather than immediate `needs_reauth`.
- What if reconnection completes but the callback associates the new grant with a different Xero org than was previously connected? Show the new org name clearly and let the accountant decide whether to proceed or reconnect again.
- What if the OAuth state token (10-minute expiry) expires before the user completes the consent screen? Callback fails gracefully, user lands on Settings with "authorization expired" message and a retry button.

---

## Requirements *(mandatory)*

### Functional Requirements

**Token Refresh Robustness (P1)**

- **FR-001**: The refresh lock key MUST be scoped to the OAuth grant (shared across all connections that share the same original `refresh_token`), not per `connection_id`. All connections sharing a grant must contend for the same lock.
- **FR-002**: After any successful token refresh, the system MUST propagate the new access and refresh tokens to ALL connections sharing the same OAuth grant, regardless of their current status.
- **FR-003**: Before marking a connection `needs_reauth` on `invalid_grant`, the system MUST re-read the connection from the database — a sibling may have already refreshed and propagated fresh tokens. If fresh tokens are now present, use them without raising.
- **FR-004**: All code paths that need a Xero access token MUST go through the single `ensure_valid_token` path with lock protection. Direct `refresh_tokens` calls and raw `access_token` decrypts in `data_service`, `report_service`, `payroll_service`, `xpm_service`, and the writeback task MUST be removed.
- **FR-005**: If the Redis lock cannot be acquired (Redis unavailable), the system MUST attempt a best-effort token refresh without the lock and log a warning, rather than failing the operation entirely.
- **FR-006**: The `_get_connection_with_token` and `_ensure_valid_token` duplication within `data_service` MUST be consolidated — a single token acquisition call at the start of each sync, refreshed if still near-expiry mid-pagination.
- **FR-007**: `token_expires_at` MUST always be set when storing new tokens. If it is `None` on an existing connection, treat it as immediately expired and refresh — do not trigger infinite refresh loops.

**Global Re-Auth Notification (P2)**

- **FR-008**: The application MUST check for any `needs_reauth` connections on each page load and expose this as a global UI state available to all authenticated pages.
- **FR-009**: A persistent, non-blocking notification MUST appear on all authenticated pages when any connection is in `needs_reauth`, naming the affected Xero organization(s).
- **FR-010**: The notification MUST include a one-click reconnect action that records the current page URL and initiates the Xero OAuth flow.
- **FR-011**: After successful OAuth callback, the user MUST be returned to the stored origin URL. If no origin URL is stored, fall back to Settings/Integrations.
- **FR-012**: The notification MUST disappear after successful reconnection without requiring a full page reload (within one polling cycle or navigation).

**Sync Error Clarity (P3)**

- **FR-013**: Any sync or data operation that encounters a `needs_reauth` connection MUST surface a specific, user-readable error identifying the org and linking to the reconnect flow — not a generic error.
- **FR-014**: Raw-decrypt paths that currently return empty results on 401 MUST instead mark the connection `needs_reauth` and raise a typed exception that the caller can handle specifically.

### Key Entities

- **XeroConnection**: Existing entity. `status`, `access_token`, `refresh_token`, `token_expires_at`, `organization_name`, `tenant_id`. No schema changes needed for the robustness fix.
- **OAuth Grant Group**: A logical grouping concept (not a new DB table) — all `XeroConnection` records that share the same original OAuth authorization. Identified by shared `refresh_token` value at time of token rotation, or by a new `oauth_grant_id` column if added.

---

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [x] **Authentication Events**: Token refresh and re-authorization are credential lifecycle events.
- [ ] **Data Access Events**: No new sensitive data access.
- [ ] **Data Modification Events**: No BAS/financial data modified.
- [x] **Integration Events**: Token refresh and re-auth affect which credentials are active for Xero syncs.
- [ ] **Compliance Events**: Does not directly affect BAS lodgement status.

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| `integration.xero.token_refreshed` | Successful background token refresh | tenant_id, connection_id, org_name, grant_group_id, siblings_updated count | 7 years | Tokens never logged |
| `integration.xero.refresh_failed` | `invalid_grant` or HTTP error during refresh | tenant_id, connection_id, org_name, error_reason, retry_attempted | 7 years | None |
| `integration.xero.reauth_initiated` | User clicks reconnect | tenant_id, user_id, connection_id, org_name, originating_page | 7 years | None |
| `integration.xero.reauth_succeeded` | OAuth callback completes | tenant_id, user_id, connection_id, org_name, previous_status | 7 years | None |
| `integration.xero.reauth_failed` | Callback fails (invalid state, expired, etc.) | tenant_id, user_id, error_reason | 7 years | None |

### Compliance Considerations

- **ATO Requirements**: Credential lifecycle events (token refresh, re-auth) must be auditable to verify data integrity of synced financial records — if a sync produced incorrect data, the audit trail proves which token was active.
- **Data Retention**: Standard 7-year ATO retention.
- **Access Logging**: Audit logs visible to practice admins only.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero erroneous `needs_reauth` state transitions during normal operation (concurrent syncs, daily use) — re-auth is only required when a refresh token genuinely expires or is revoked.
- **SC-002**: Concurrent sync tasks for a tenant with multiple Xero connections complete without any `invalid_grant` errors in 100% of test runs.
- **SC-003**: A genuine `needs_reauth` condition is visible to the accountant from any page in the application, not only from Settings or Tax Planning.
- **SC-004**: After completing reconnection, the accountant is returned to their originating page in 100% of successful reconnect flows.
- **SC-005**: The token refresh mechanism is a single code path — there are zero direct `refresh_tokens` calls or raw `access_token` decrypts outside of `ensure_valid_token`.
- **SC-006**: Redis unavailability does not cause sync task failure when the access token is still valid.

---

## Assumptions

- **Xero cannot pre-select org on re-auth**: Xero's consent screen is controlled by Xero. When genuine re-auth is needed, users will see the org selection screen. If they have an active Xero session, Xero may streamline it — this is outside Clairo's control.
- **OAuth grant grouping without schema change**: Initially, siblings can be identified by querying connections with the same `tenant_id` that were created from the same bulk import. A new `oauth_grant_id` column would make this more robust but is deferred unless the tenant-level grouping proves insufficient.
- **Return-to-origin via session storage**: The post-reconnect return URL will be stored in browser session storage (consistent with the existing `xero_reauth_return_to` pattern), not in the database.
- **Notification polling**: The global `needs_reauth` check will run on page load and navigation. No WebSocket push is needed — polling on navigation is sufficient.
- **Business owners excluded**: The global notification is only relevant for practice users (accountants). Business owners in the client portal do not manage Xero connections.
