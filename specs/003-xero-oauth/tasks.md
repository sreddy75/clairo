# Tasks: Xero OAuth & Connection Management

**Spec**: 003-xero-oauth | **Date**: 2025-12-28
**Input**: Design documents from `/specs/003-xero-oauth/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md

**Tests**: Included - TDD approach with tests written before implementation where appropriate.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

---

## Phase 0: Git Setup (COMPLETE)

**Purpose**: Create feature branch before any implementation

- [x] T000 Create feature branch from main
  - Run: `git checkout main && git pull origin main`
  - Run: `git checkout -b feature/003-xero-oauth`
  - _Completed: Branch created_

---

## Phase 1: Setup (COMPLETE)

**Purpose**: Configuration and project structure for xero module

- [x] T001 [P] Add Xero configuration settings to `backend/app/config.py`
  - Add `XeroSettings` class with: `client_id`, `client_secret`, `redirect_uri`, `scopes`, `authorization_url`, `token_url`, `connections_url`, `revocation_url`
  - Add `TokenEncryptionSettings` class with: `key` (base64 encoded 32-byte key)
  - Update `Settings` class to include `xero: XeroSettings` and `token_encryption: TokenEncryptionSettings`
  - _Requirements: FR-001, FR-003_

- [x] T002 [P] Create xero module directory structure
  - Create `backend/app/modules/integrations/__init__.py`
  - Create `backend/app/modules/integrations/xero/__init__.py`
  - Create placeholder files: `router.py`, `service.py`, `repository.py`, `models.py`, `schemas.py`, `oauth.py`, `client.py`, `rate_limiter.py`, `encryption.py`, `audit_events.py`
  - _Requirements: Constitution - Modular Monolith Architecture_

- [x] T003 [P] Create test directory structure for xero module
  - Create `backend/tests/unit/modules/integrations/__init__.py`
  - Create `backend/tests/unit/modules/integrations/xero/__init__.py`
  - Create placeholder test files: `test_oauth.py`, `test_encryption.py`, `test_rate_limiter.py`, `test_service.py`
  - Create `backend/tests/integration/api/test_xero_endpoints.py`
  - Create `backend/tests/factories/xero.py`
  - _Requirements: Constitution - 80% Unit Test Coverage_

- [x] T004 [P] Add cryptography dependency to `backend/pyproject.toml`
  - Add `cryptography = "^42"` to dependencies
  - Run `uv sync` to install
  - _Requirements: NFR-004_

---

## Phase 2: Foundational (COMPLETE)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

### 2.1 Data Models and Enums

- [x] T005 Create enum definitions in `backend/app/modules/integrations/xero/models.py`
  - Implement `XeroConnectionStatus` enum (ACTIVE, NEEDS_REAUTH, DISCONNECTED)
  - _Requirements: Key Entities_

- [x] T006 Create `XeroConnection` SQLAlchemy model in `backend/app/modules/integrations/xero/models.py`
  - Implement all fields per data-model.md: id, tenant_id, xero_tenant_id, organization_name, status, access_token, refresh_token, token_expires_at, scopes, rate_limit fields, connected_by, timestamps
  - Add computed properties: `is_active`, `needs_refresh`, `is_rate_limited`
  - _Requirements: FR-003, FR-006, Key Entities - XeroConnection_

- [x] T007 Create `XeroOAuthState` SQLAlchemy model in `backend/app/modules/integrations/xero/models.py`
  - Implement fields: id, tenant_id, user_id, state, code_verifier, redirect_uri, expires_at, created_at, used_at
  - Add computed properties: `is_expired`, `is_used`, `is_valid`
  - _Requirements: FR-014, Key Entities - XeroOAuthState_

- [x] T008 [P] Write unit tests for models in `backend/tests/unit/modules/integrations/xero/test_models.py`
  - Test enum values and string representations
  - Test computed properties (is_active, needs_refresh, is_rate_limited)
  - Test state validity computation
  - _Requirements: Constitution - 80% Unit Test Coverage_

### 2.2 Pydantic Schemas

- [x] T009 Create Pydantic schemas in `backend/app/modules/integrations/xero/schemas.py`
  - Request schemas: `XeroConnectRequest`, `XeroCallbackRequest`, `XeroDisconnectRequest`
  - Response schemas: `XeroConnectionResponse`, `XeroConnectionSummary`, `XeroAuthUrlResponse`, `XeroConnectionListResponse`
  - Internal schemas: `TokenResponse`, `XeroOrganization`
  - _Requirements: Constitution - Pydantic for Schemas_

### 2.3 Database Migration

- [x] T010 Create Alembic migration `backend/alembic/versions/003_xero_oauth.py`
  - Create enum: `xero_connection_status`
  - Create `xero_connections` table with all columns and indexes
  - Create `xero_oauth_states` table with all columns and indexes
  - Enable RLS on `xero_connections` table
  - Create RLS policy: `tenant_isolation_xero_connections`
  - Include proper downgrade function
  - _Requirements: FR-006, FR-007_

- [x] T011 Write integration test for RLS policies in `backend/tests/integration/test_xero_rls.py`
  - Test tenant isolation on xero_connections table
  - Test cross-tenant access returns empty
  - _Requirements: FR-007, User Story 4_

### 2.4 Core Utilities

- [x] T012 Create token encryption utility in `backend/app/modules/integrations/xero/encryption.py`
  - Implement `TokenEncryption` class with AES-256-GCM
  - Methods: `encrypt(plaintext: str) -> str`, `decrypt(encrypted: str) -> str`
  - Use unique nonce per encryption
  - _Requirements: FR-003, NFR-004_

- [x] T013 [P] Write unit tests for encryption in `backend/tests/unit/modules/integrations/xero/test_encryption.py`
  - Test encrypt/decrypt round-trip
  - Test different inputs (short, long, special chars)
  - Test invalid key handling
  - Test tampered ciphertext detection
  - _Requirements: NFR-004_

- [x] T014 [P] Define audit events in `backend/app/modules/integrations/xero/audit_events.py`
  - Define `XERO_AUDIT_EVENTS` dictionary with all event types
  - Events: `integration.xero.oauth_started`, `integration.xero.connected`, `integration.xero.disconnected`, `integration.xero.token_refreshed`, `integration.xero.token_refresh_failed`, `integration.xero.rate_limited`, `integration.xero.authorization_required`
  - _Requirements: FR-013, Audit Events_

### 2.5 Test Factories

- [x] T015 Create test factories in `backend/tests/factories/xero.py`
  - Implement `XeroConnectionFactory` with factory_boy
  - Implement `XeroOAuthStateFactory` with factory_boy
  - Add async SQLAlchemy support
  - _Requirements: Testing Strategy_

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Connect Xero Organization (COMPLETE)

**Goal**: Enable users to connect their Xero organizations via OAuth 2.0 with PKCE

**Independent Test**: User can click "Connect Xero", complete OAuth flow, see connected organization

### Tests for User Story 1

- [x] T016 [P] [US1] Write unit tests for PKCE generation in `backend/tests/unit/modules/integrations/xero/test_oauth.py`
  - Test code_verifier generation (43-128 chars, URL-safe)
  - Test code_challenge computation (SHA256 + base64url)
  - Test state generation (32 bytes, URL-safe)
  - _Requirements: FR-001_

- [x] T017 [P] [US1] Write unit tests for XeroOAuthService in `backend/tests/unit/modules/integrations/xero/test_service.py`
  - Test `generate_auth_url()` creates correct URL with PKCE params
  - Test `generate_auth_url()` stores state with code_verifier
  - Test `handle_callback()` validates state
  - Test `handle_callback()` exchanges code for tokens
  - Test `handle_callback()` encrypts and stores tokens
  - _Requirements: User Story 1 - Acceptance Scenarios_

- [x] T018 [US1] Write integration tests for OAuth endpoints in `backend/tests/integration/api/test_xero_endpoints.py`
  - Test GET `/api/v1/integrations/xero/auth-url` returns valid URL
  - Test GET `/api/v1/integrations/xero/callback` with valid state creates connection
  - Test GET `/api/v1/integrations/xero/callback` with invalid state returns error
  - Test GET `/api/v1/integrations/xero/callback` with expired state returns error
  - _Requirements: User Story 1 - Acceptance Scenarios 1, 4_

### Implementation for User Story 1

- [x] T019 [US1] Create XeroClient in `backend/app/modules/integrations/xero/client.py`
  - Implement `__init__` with XeroSettings and httpx.AsyncClient
  - Implement `exchange_code()` - exchanges authorization code for tokens
  - Implement `get_connections()` - fetches authorized Xero organizations
  - Handle HTTP errors and timeouts
  - _Requirements: FR-001, FR-005_

- [x] T020 [US1] Create XeroOAuthStateRepository in `backend/app/modules/integrations/xero/repository.py`
  - Implement `create()` method
  - Implement `get_by_state()` method
  - Implement `mark_as_used()` method
  - Implement `cleanup_expired()` method
  - _Requirements: FR-014_

- [x] T021 [US1] Create XeroConnectionRepository in `backend/app/modules/integrations/xero/repository.py`
  - Implement `create()` method
  - Implement `get_by_id()` method
  - Implement `get_by_xero_tenant_id()` method
  - Implement `list_by_tenant()` method
  - Implement `update()` method
  - _Requirements: Constitution - Repository Pattern_

- [x] T022 [US1] Create OAuth utilities in `backend/app/modules/integrations/xero/oauth.py`
  - Implement `generate_code_verifier()` function
  - Implement `generate_code_challenge()` function
  - Implement `generate_state()` function
  - Implement `build_authorization_url()` function
  - _Requirements: FR-001_

- [x] T023 [US1] Create XeroOAuthService in `backend/app/modules/integrations/xero/service.py`
  - Implement `generate_auth_url()` - creates OAuth URL with PKCE
  - Implement `handle_callback()` - validates state, exchanges code, creates connection
  - Inject dependencies: XeroClient, repositories, encryption, audit
  - _Requirements: User Story 1 - All Acceptance Scenarios_

- [x] T024 [US1] Create OAuth router endpoints in `backend/app/modules/integrations/xero/router.py`
  - GET `/api/v1/integrations/xero/auth-url` - generate OAuth URL
  - GET `/api/v1/integrations/xero/callback` - handle OAuth callback
  - _Requirements: API Endpoints Design_

- [x] T025 [US1] Register xero router in `backend/app/main.py`
  - Import and include xero router with prefix `/api/v1`
  - _Requirements: Constitution - Modular Monolith_

- [x] T026 [US1] Add audit logging to OAuth flow
  - Log `integration.xero.oauth_started` when auth URL generated
  - Log `integration.xero.connected` on successful connection
  - _Requirements: FR-013, Audit Events_

### Frontend Implementation for User Story 1

- [x] T027 [P] [US1] Create Xero API client in `frontend/src/lib/api/integrations.ts`
  - Function: `getXeroAuthUrl(redirectUri: string)`
  - Function: `handleXeroCallback(code: string, state: string)`
  - Function: `listXeroConnections()`
  - _Requirements: Vertical Slice_

- [x] T028 [US1] Create XeroConnectButton component in `frontend/src/components/integrations/XeroConnectButton.tsx`
  - Button triggers OAuth flow
  - Shows loading state during redirect
  - _Requirements: FR-011_

- [x] T029 [US1] Create OAuth callback page in `frontend/src/app/(protected)/settings/integrations/xero/callback/page.tsx`
  - Extract code and state from URL params
  - Send to backend callback endpoint
  - Show success/error message
  - Redirect to connections page on success
  - _Requirements: User Story 1 - Acceptance Scenario 2_

- [x] T030 [US1] Create integrations list page in `frontend/src/app/(protected)/settings/integrations/page.tsx`
  - Show Xero integration card
  - Link to Xero connections page
  - Future: placeholder for MYOB
  - _Requirements: FR-011_

**Checkpoint**: User Story 1 complete - users can connect Xero organizations

---

## Phase 4: User Story 2 - View and Manage Connections (COMPLETE)

**Goal**: Users can view connected organizations and disconnect when needed

**Independent Test**: User can see list of connections with status, can disconnect

### Tests for User Story 2

- [x] T031 [P] [US2] Write unit tests for XeroConnectionService in `backend/tests/unit/modules/integrations/xero/test_service.py`
  - Test `list_connections()` returns tenant's connections
  - Test `get_connection()` returns single connection
  - Test `disconnect()` updates status and revokes tokens
  - _Requirements: User Story 2 - Acceptance Scenarios_

- [x] T032 [US2] Write integration tests for connection endpoints in `backend/tests/integration/api/test_xero_endpoints.py`
  - Test GET `/api/v1/integrations/xero/connections` lists connections
  - Test GET `/api/v1/integrations/xero/connections/{id}` returns connection
  - Test DELETE `/api/v1/integrations/xero/connections/{id}` disconnects
  - Test cross-tenant access returns 404
  - _Requirements: User Story 2 - Acceptance Scenarios_

### Implementation for User Story 2

- [x] T033 [US2] Add revoke_token method to XeroClient in `backend/app/modules/integrations/xero/client.py`
  - Implement `revoke_token()` - revokes token at Xero
  - Handle errors gracefully (still mark as disconnected)
  - _Requirements: FR-015_

- [x] T034 [US2] Create XeroConnectionService in `backend/app/modules/integrations/xero/service.py`
  - Implement `list_connections()` with pagination
  - Implement `get_connection()` with decryption
  - Implement `disconnect()` with token revocation
  - Inject dependencies: repositories, client, encryption, audit
  - _Requirements: User Story 2 - All Acceptance Scenarios_

- [x] T035 [US2] Create connection management endpoints in `backend/app/modules/integrations/xero/router.py`
  - GET `/api/v1/integrations/xero/connections` - list connections
  - GET `/api/v1/integrations/xero/connections/{id}` - get connection details
  - DELETE `/api/v1/integrations/xero/connections/{id}` - disconnect (Admin only)
  - _Requirements: API Endpoints Design_

- [x] T036 [US2] Add audit logging for connection management
  - Log `integration.xero.disconnected` on disconnect
  - Include disconnected_by, reason in audit data
  - _Requirements: FR-013_

### Frontend Implementation for User Story 2

- [x] T037 [P] [US2] Create ConnectionStatusBadge component in `frontend/src/components/integrations/ConnectionStatusBadge.tsx`
  - Show status: Active (green), Needs Re-auth (orange), Disconnected (gray)
  - _Requirements: FR-012_

- [x] T038 [US2] Create XeroConnectionCard component in `frontend/src/components/integrations/XeroConnectionCard.tsx`
  - Show organization name, status badge, connected date
  - Disconnect button (with confirmation dialog)
  - Re-connect button if needs_reauth
  - _Requirements: FR-011, FR-012_

- [x] T039 [US2] Create Xero connections page in `frontend/src/app/(protected)/settings/integrations/xero/page.tsx`
  - List connected organizations using XeroConnectionCard
  - Connect button if no connections
  - Empty state with call-to-action
  - _Requirements: User Story 2 - Acceptance Scenario 4_

- [x] T040 [US2] Add disconnect API function in `frontend/src/lib/api/integrations.ts`
  - Function: `disconnectXero(connectionId: string, reason?: string)`
  - _Requirements: FR-011_

**Checkpoint**: User Story 2 complete - users can view and manage connections

---

## Phase 5: User Story 3 - Automatic Token Refresh (COMPLETE)

**Goal**: System automatically refreshes tokens before expiry

**Independent Test**: Token refresh occurs automatically without user intervention

### Tests for User Story 3

- [x] T041 [P] [US3] Write unit tests for token refresh in `backend/tests/unit/modules/integrations/xero/test_service.py`
  - Test `refresh_tokens()` gets new tokens before expiry
  - Test `refresh_tokens()` updates stored tokens (rotating)
  - Test `refresh_tokens()` handles refresh failure
  - Test retry logic with same token on network error
  - _Requirements: User Story 3 - Acceptance Scenarios_

- [x] T042 [US3] Write integration tests for token refresh in `backend/tests/integration/api/test_xero_endpoints.py`
  - Test POST `/api/v1/integrations/xero/connections/{id}/refresh` works
  - Test automatic refresh when accessing with near-expired token
  - _Requirements: FR-004, FR-005_

### Implementation for User Story 3

- [x] T043 [US3] Add refresh_token method to XeroClient in `backend/app/modules/integrations/xero/client.py`
  - Implement `refresh_token()` - exchanges refresh token for new tokens
  - Handle rotating tokens (new refresh token each time)
  - Implement retry logic with exponential backoff
  - _Requirements: FR-004, FR-005, NFR-001_

- [x] T044 [US3] Add token refresh to XeroConnectionService in `backend/app/modules/integrations/xero/service.py`
  - Implement `refresh_tokens()` method
  - Implement `ensure_valid_token()` helper - refreshes if needed before API calls
  - Handle `invalid_grant` error - mark as needs_reauth
  - Handle retry window (30 min) for network failures
  - _Requirements: User Story 3 - All Acceptance Scenarios_

- [x] T045 [US3] Create token refresh endpoint in `backend/app/modules/integrations/xero/router.py`
  - POST `/api/v1/integrations/xero/connections/{id}/refresh` - manual refresh (Admin)
  - _Requirements: API Endpoints Design_

- [x] T046 [US3] Add audit logging for token refresh
  - Log `integration.xero.token_refreshed` on success
  - Log `integration.xero.token_refresh_failed` on failure
  - Log `integration.xero.authorization_required` when needs re-auth
  - _Requirements: FR-013_

**Checkpoint**: User Story 3 complete - tokens refresh automatically

---

## Phase 6: User Story 4 - Multi-Tenant Connection Isolation (COMPLETE)

**Goal**: Connections are isolated per tenant via RLS

**Independent Test**: Tenant A cannot see Tenant B's connections

### Tests for User Story 4

- [x] T047 [US4] Write integration tests for tenant isolation in `backend/tests/integration/api/test_xero_tenant_isolation.py`
  - Test Tenant A's connections are invisible to Tenant B
  - Test API returns 404 (not 403) for cross-tenant access
  - Test multiple users in same tenant can see connections
  - _Requirements: User Story 4 - All Acceptance Scenarios_

### Implementation for User Story 4

- [x] T048 [US4] Verify RLS policies in migration are correct
  - Review `tenant_isolation_xero_connections` policy
  - Ensure policy uses `current_setting('app.current_tenant_id')`
  - _Requirements: FR-007_

- [x] T049 [US4] Add integration test for RLS bypass attempts
  - Test direct SQL without tenant context returns empty
  - Test API with forged tenant_id in body uses JWT tenant_id
  - _Requirements: FR-007_

**Checkpoint**: User Story 4 complete - tenant isolation verified

---

## Phase 7: User Story 5 - Rate Limit Handling (COMPLETE)

**Goal**: System handles Xero API rate limits gracefully

**Independent Test**: System respects rate limits and backs off appropriately

### Tests for User Story 5

- [x] T050 [P] [US5] Write unit tests for rate limiter in `backend/tests/unit/modules/integrations/xero/test_rate_limiter.py`
  - Test `update_from_headers()` parses X-*Limit-Remaining headers
  - Test `can_make_request()` returns false when limit reached
  - Test `get_wait_time()` calculates correct wait time
  - Test exponential backoff calculation
  - _Requirements: User Story 5 - Acceptance Scenarios_

- [x] T051 [US5] Write integration tests for rate limit handling in `backend/tests/integration/api/test_xero_rate_limits.py`
  - Test system pauses when limit approached
  - Test system waits Retry-After seconds on 429
  - _Requirements: FR-008, FR-009, FR-010_

### Implementation for User Story 5

- [x] T052 [US5] Create XeroRateLimiter in `backend/app/modules/integrations/xero/rate_limiter.py`
  - Implement `update_from_headers()` - parses rate limit headers
  - Implement `can_make_request()` - checks if request allowed
  - Implement `get_wait_time()` - returns seconds to wait
  - Implement `record_rate_limit_hit()` - handles 429 with Retry-After
  - _Requirements: FR-008, FR-009, FR-010_

- [x] T053 [US5] Integrate rate limiter with XeroClient
  - Check rate limits before making requests
  - Update limits from response headers
  - Handle 429 responses with backoff
  - _Requirements: FR-008, FR-009, FR-010_

- [x] T054 [US5] Update XeroConnectionRepository to persist rate limits
  - Save rate limit state to database
  - Load rate limit state on connection retrieval
  - _Requirements: NFR-005_

- [x] T055 [US5] Add audit logging for rate limit events
  - Log `integration.xero.rate_limited` when 429 received
  - Include endpoint, retry_after in audit data
  - _Requirements: FR-013_

**Checkpoint**: User Story 5 complete - rate limits handled gracefully

---

## Phase 8: User Story 6 - Connection Security and Audit (COMPLETE)

**Goal**: All connection activities are logged for compliance

**Independent Test**: Audit log shows all connection events

### Tests for User Story 6

- [x] T056 [US6] Write integration tests for audit logging in `backend/tests/integration/api/test_xero_audit.py`
  - Test connect creates audit event with correct data
  - Test disconnect creates audit event
  - Test token refresh creates audit event
  - Test failed refresh creates audit event
  - _Requirements: User Story 6 - All Acceptance Scenarios_

### Implementation for User Story 6

- [x] T057 [US6] Verify all audit logging is implemented
  - Review all service methods log appropriate events
  - Verify audit data includes required fields
  - _Requirements: FR-013, Audit Implementation Requirements_

- [x] T058 [US6] Add security event logging
  - Log `integration.xero.oauth_state_mismatch` on CSRF detection
  - Include IP (masked to /24) in security events
  - _Requirements: FR-014, Audit Events_

**Checkpoint**: User Story 6 complete - audit logging verified

---

## Phase 9: Polish & Cross-Cutting Concerns (COMPLETE)

**Purpose**: Improvements that affect multiple user stories

- [x] T059 [P] Add error handling middleware for xero exceptions
  - Handle `XeroOAuthError` -> 400 response
  - Handle `XeroConnectionNotFoundError` -> 404 response
  - Handle `XeroRateLimitError` -> 429 response
  - _Requirements: Error Handling_

- [x] T060 [P] Add OpenAPI documentation for xero endpoints
  - Add response schemas to all endpoints
  - Add security requirements (Bearer token)
  - Add example requests/responses
  - _Requirements: API Documentation_

- [x] T061 Code cleanup and refactoring
  - Ensure consistent error messages
  - Remove any duplicate code
  - Verify all type hints are complete
  - _Requirements: Constitution - Type Hints Everywhere_

- [x] T062 [P] Update frontend settings navigation
  - Add "Integrations" link to sidebar
  - Update protected layout if needed
  - _Requirements: Vertical Slice_

---

## Phase FINAL: PR & Merge

**Purpose**: Create pull request and merge to main

- [x] TFINAL-1 Ensure all tests pass
  - Run: `cd backend && uv run pytest`
  - All tests must pass before PR

- [x] TFINAL-2 Run linting and type checking
  - Run: `cd backend && uv run ruff check && uv run mypy`
  - Run: `cd frontend && npm run lint`
  - Fix any issues

- [x] TFINAL-3 Push feature branch and create PR
  - Run: `git push -u origin feature/003-xero-oauth`
  - Run: `gh pr create --title "Spec 003: Xero OAuth & Connection Management" --body "..."`
  - Include summary of changes in PR description

- [x] TFINAL-4 Address review feedback (if any)
  - Make requested changes
  - Push additional commits

- [x] TFINAL-5 Merge PR to main
  - Squash merge after approval
  - Delete feature branch after merge

- [x] TFINAL-6 Update ROADMAP.md
  - Mark spec 003 as COMPLETE
  - Update current focus to spec 004

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 0 (Git Setup) ────────────────────────────────────────┐
                                                             │
Phase 1 (Setup) ────────────────────────────────────────────┤
    ├── T001, T002, T003, T004 (all parallel)               │
                                                             │
Phase 2 (Foundational) ─────────────────────────────────────┤
    ├── T005 -> T006, T007 (model dependencies)             │
    ├── T008, T013, T014 (parallel - tests)                 │
    ├── T009 (schemas - after models)                       │
    ├── T010, T011 (migration & RLS tests)                  │
    ├── T012 (encryption utility)                           │
    └── T015 (factories - after models)                     │
                                                             │
              ┌──────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│  User Stories can proceed in order after Phase 2            │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │   US1    │  │   US2    │  │   US3    │                  │
│  │ Connect  │──│ View/Mgmt│──│ Refresh  │                  │
│  │ (P1)     │  │ (P1)     │  │ (P1)     │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
│       │             │             │                         │
│       └─────────────┴─────────────┘                         │
│                     │                                       │
│                     ▼                                       │
│  ┌──────────────────────────────────────────┐              │
│  │  US4 (Isolation) + US5 (Rate) + US6 (Audit)│             │
│  │  (P2 - can run in parallel)               │              │
│  └──────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
              Phase 9 (Polish) & Phase FINAL (PR)
```

### Critical Path

1. **Phase 1**: Setup (all parallel)
2. **Phase 2**: Foundational - BLOCKS all user stories
3. **US1**: Connect flow (P1) - enables testing
4. **US2**: View/Manage (P1) - depends on US1 for connections to exist
5. **US3**: Token refresh (P1) - independent after US1
6. **US4-US6**: Can run in parallel after US1-US3
7. **Phase 9-FINAL**: After all user stories

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Connect)
4. Complete Phase 4: User Story 2 (View/Manage)
5. **STOP and VALIDATE**: Test connect/disconnect flow independently
6. Deploy/demo if ready - basic Xero connection working

### Incremental Delivery

1. Setup + Foundational -> Foundation ready
2. Add US1 -> Test independently -> Users can connect Xero
3. Add US2 -> Test independently -> Users can view/disconnect
4. Add US3 -> Test independently -> Token refresh automatic
5. Add US4-US6 -> Full feature set with security
6. Polish phase -> Production ready

---

## Notes

- [P] tasks = different files, no dependencies
- [USn] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All file paths are relative to repository root
