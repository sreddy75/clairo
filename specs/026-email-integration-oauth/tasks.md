# Tasks: Email Integration & OAuth

**Input**: Design documents from `/specs/026-email-integration-oauth/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Test tasks included as this is a security-sensitive feature (OAuth tokens, encryption)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 0: Git Setup (REQUIRED)

**Purpose**: Create feature branch before any implementation

- [ ] T000 Create feature branch from main
  - Run: `git checkout main && git pull origin main`
  - Run: `git checkout -b feature/026-email-integration-oauth`
  - Verify: You are now on the feature branch

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Module structure and dependencies

- [ ] T001 Create email module structure in backend/app/modules/email/
  - Create __init__.py, models.py, schemas.py, repository.py, service.py, router.py
  - Create subdirectories: oauth/, sync/, ingest/
- [ ] T002 [P] Add dependencies to backend/pyproject.toml
  - Add: authlib, httpx (if not present), cryptography (if not present)
  - Run: `uv sync`
- [ ] T003 [P] Add environment variables to backend/app/config.py
  - Add: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
  - Add: MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, MICROSOFT_TENANT_ID
  - Add: EMAIL_TOKEN_ENCRYPTION_KEY, EMAIL_OAUTH_CALLBACK_URL
- [ ] T004 [P] Create frontend email components directory in frontend/src/components/email/
  - Create placeholder files for ConnectionCard.tsx, ConnectGmailButton.tsx, ConnectOutlookButton.tsx

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Create TokenEncryption utility in backend/app/modules/email/crypto.py
  - AES-256-GCM encryption/decryption
  - Key from EMAIL_TOKEN_ENCRYPTION_KEY environment variable
  - Base64 encoding for storage
- [ ] T006 [P] Create EmailProvider enum and ConnectionStatus enum in backend/app/modules/email/models.py
  - EmailProvider: GMAIL, OUTLOOK, FORWARDING
  - ConnectionStatus: PENDING, ACTIVE, EXPIRED, REVOKED, DISCONNECTED
- [ ] T007 Create EmailConnection model in backend/app/modules/email/models.py
  - Fields: id, tenant_id, provider, email_address, display_name
  - Encrypted token fields: access_token_encrypted, refresh_token_encrypted
  - Fields: token_expires_at, last_sync_at, sync_cursor, status, status_reason
  - Add relationship to tenant
- [ ] T008 [P] Create EmailSyncJob model in backend/app/modules/email/models.py
  - Fields: id, connection_id, tenant_id, job_type (INITIAL_BACKFILL/INCREMENTAL)
  - Fields: status (PENDING/RUNNING/COMPLETED/FAILED), emails_synced
  - Fields: started_at, completed_at, error_message
- [ ] T009 [P] Create RawEmail model in backend/app/modules/email/models.py
  - Fields: id, tenant_id, connection_id, provider_message_id
  - Fields: from_address, from_name, to_addresses, cc_addresses, subject, snippet
  - Fields: received_at, is_read, is_processed, body_text, body_html
  - Fields: raw_headers (JSONB), attachment_count
- [ ] T010 [P] Create EmailAttachment model in backend/app/modules/email/models.py
  - Fields: id, email_id, tenant_id, filename, content_type, size_bytes
  - Fields: storage_path, provider_attachment_id
- [ ] T011 Create Alembic migration for email tables
  - Run: `alembic revision --autogenerate -m "Add email integration tables"`
  - Include: email_connections, email_sync_jobs, raw_emails, email_attachments
  - Add indexes on tenant_id, connection_id, received_at
- [ ] T012 Create Pydantic schemas in backend/app/modules/email/schemas.py
  - OAuthAuthorizeResponse, OAuthCallbackRequest
  - EmailConnectionSummary, EmailConnectionDetail
  - SyncJobSummary, SyncStatus, SyncJobResponse
  - EmailSummary, EmailDetail, EmailListResponse
  - ForwardingConfig
- [ ] T013 Create EmailConnectionRepository in backend/app/modules/email/repository.py
  - CRUD for EmailConnection
  - get_by_tenant(), get_active_connections()
  - update_tokens(), update_sync_cursor(), mark_expired()
  - get_expiring_connections(expires_before)
- [ ] T014 [P] Create EmailRepository in backend/app/modules/email/repository.py
  - CRUD for RawEmail and EmailAttachment
  - get_emails_by_tenant() with pagination and filters
  - get_unread_count(), mark_as_read()
- [ ] T015 [P] Create EmailSyncJobRepository in backend/app/modules/email/repository.py
  - CRUD for EmailSyncJob
  - get_by_connection(), get_running_jobs()
  - mark_completed(), mark_failed()

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Connect Gmail Account (Priority: P1)

**Goal**: Enable accountants to connect their Gmail/Google Workspace account via OAuth

**Independent Test**: Click "Connect Gmail" → complete OAuth flow → see connection status as "Active"

### Tests for User Story 1

- [ ] T016 [P] [US1] Unit test for TokenEncryption in backend/tests/unit/modules/email/test_crypto.py
  - Test encrypt/decrypt roundtrip
  - Test different encryptions produce different output (nonce)
  - Test invalid key handling
- [ ] T017 [P] [US1] Unit test for GmailOAuthClient in backend/tests/unit/modules/email/test_oauth_gmail.py
  - Test get_authorization_url() generates correct URL
  - Test exchange_code() with mocked response
  - Test get_user_email() extracts email correctly
- [ ] T018 [P] [US1] Integration test for Gmail OAuth flow in backend/tests/integration/api/test_email_gmail_oauth.py
  - Test /email/oauth/gmail/authorize returns auth URL
  - Test callback with invalid state returns 400
  - Test callback with valid state creates connection

### Implementation for User Story 1

- [ ] T019 Create OAuth base interface in backend/app/modules/email/oauth/base.py
  - EmailOAuthProvider ABC with abstract methods
  - get_authorization_url(), exchange_code(), refresh_token(), get_user_email()
  - TokenData TypedDict
- [ ] T020 [US1] Create GmailOAuthClient in backend/app/modules/email/oauth/gmail.py
  - Implement EmailOAuthProvider for Gmail
  - Use authlib for OAuth flow
  - Scopes: gmail.readonly
  - access_type=offline, prompt=consent for refresh tokens
- [ ] T021 [US1] Create EmailService in backend/app/modules/email/service.py
  - get_authorization_url(provider, state)
  - complete_oauth_flow(provider, code, tenant_id)
  - list_connections(tenant_id)
  - disconnect(connection_id, tenant_id)
- [ ] T022 [US1] Create OAuth endpoints in backend/app/modules/email/router.py
  - GET /email/oauth/{provider}/authorize - initiate OAuth
  - GET /email/oauth/{provider}/callback - handle callback
  - Store state in Redis with 10-minute expiry
- [ ] T023 [US1] Register email router in backend/app/main.py
  - Import and include email router
  - Prefix: /api/v1
- [ ] T024 [P] [US1] Create frontend API client in frontend/src/lib/api/email.ts
  - initiateOAuth(provider)
  - listConnections()
  - disconnectConnection(id)
- [ ] T025 [US1] Create ConnectGmailButton in frontend/src/components/email/ConnectGmailButton.tsx
  - Call initiateOAuth('gmail')
  - Redirect to authorization_url
  - Loading state handling

**Checkpoint**: Gmail OAuth flow works end-to-end

---

## Phase 4: User Story 2 - Connect Microsoft 365 Account (Priority: P1)

**Goal**: Enable accountants to connect their Outlook/Microsoft 365 account via OAuth

**Independent Test**: Click "Connect Outlook" → complete Microsoft OAuth flow → see connection status as "Active"

### Tests for User Story 2

- [ ] T026 [P] [US2] Unit test for MicrosoftOAuthClient in backend/tests/unit/modules/email/test_oauth_microsoft.py
  - Test get_authorization_url() generates correct URL with tenant
  - Test exchange_code() with mocked response
  - Test get_user_email() extracts mail or userPrincipalName

### Implementation for User Story 2

- [ ] T027 [US2] Create MicrosoftOAuthClient in backend/app/modules/email/oauth/microsoft.py
  - Implement EmailOAuthProvider for Microsoft Graph
  - Tenant: common (multi-tenant)
  - Scopes: Mail.Read, Mail.ReadBasic, User.Read, offline_access
- [ ] T028 [US2] Update EmailService to support Microsoft OAuth in backend/app/modules/email/service.py
  - Add Microsoft client to get_authorization_url()
  - Handle Microsoft callback in complete_oauth_flow()
- [ ] T029 [US2] Create ConnectOutlookButton in frontend/src/components/email/ConnectOutlookButton.tsx
  - Call initiateOAuth('outlook')
  - Redirect to authorization_url
  - Loading state handling

**Checkpoint**: Microsoft OAuth flow works end-to-end

---

## Phase 5: User Story 3 - Initial Email Backfill (Priority: P1)

**Goal**: Import ATO emails from the last 12 months on first connection

**Independent Test**: After connecting email → see historical ATO emails appear in inbox within minutes

### Tests for User Story 3

- [ ] T030 [P] [US3] Unit test for GmailSyncService in backend/tests/unit/modules/email/test_gmail_sync.py
  - Test initial_backfill() with mocked Gmail API
  - Test ATO domain filtering (only @ato.gov.au)
  - Test email body extraction
- [ ] T031 [P] [US3] Unit test for MicrosoftSyncService in backend/tests/unit/modules/email/test_microsoft_sync.py
  - Test initial_backfill() with mocked Graph API
  - Test ATO domain filtering
  - Test delta token storage

### Implementation for User Story 3

- [ ] T032 [US3] Create ATO email filter constants in backend/app/modules/email/sync/__init__.py
  - ATO_DOMAINS list: @ato.gov.au, @notifications.ato.gov.au, @email.ato.gov.au, @online.ato.gov.au
  - Gmail query: `from:(@ato.gov.au OR @notifications.ato.gov.au) newer_than:365d`
  - Microsoft filter: `from/emailAddress/address contains 'ato.gov.au'`
- [ ] T033 [US3] Create GmailSyncService in backend/app/modules/email/sync/gmail_sync.py
  - initial_backfill(): Query last 12 months of ATO emails
  - Paginate with maxResults=100
  - Store emails and attachments
  - Record historyId for incremental sync
- [ ] T034 [US3] Create MicrosoftSyncService in backend/app/modules/email/sync/microsoft_sync.py
  - initial_backfill(): Query messages with ATO filter
  - Use $top=100 for pagination
  - Store emails and attachments
  - Record deltaToken for incremental sync
- [ ] T035 [US3] Create Celery task for initial sync in backend/app/modules/email/sync/scheduler.py
  - trigger_initial_sync(connection_id)
  - Create EmailSyncJob, run backfill, update status
- [ ] T036 [US3] Update EmailService to trigger initial sync on connection complete
  - After OAuth callback, queue initial sync task
  - Return connection with status PENDING until sync completes

**Checkpoint**: Initial backfill syncs historical ATO emails

---

## Phase 6: User Story 4 - Automatic Email Sync (Priority: P1)

**Goal**: New ATO emails captured automatically within 15 minutes

**Independent Test**: Receive new ATO email → appears in Clairo inbox within 15 minutes

### Tests for User Story 4

- [ ] T037 [P] [US4] Unit test for incremental sync in backend/tests/unit/modules/email/test_sync_service.py
  - Test incremental_sync() for Gmail (history API)
  - Test incremental_sync() for Microsoft (delta query)
  - Test sync cursor update

### Implementation for User Story 4

- [ ] T038 [US4] Add incremental_sync() to GmailSyncService in backend/app/modules/email/sync/gmail_sync.py
  - Use history API with startHistoryId
  - Filter messageAdded events
  - Store new ATO emails only
  - Update historyId cursor
- [ ] T039 [US4] Add incremental_sync() to MicrosoftSyncService in backend/app/modules/email/sync/microsoft_sync.py
  - Use delta query with deltaToken
  - Filter new messages only
  - Store new ATO emails
  - Update deltaToken cursor
- [ ] T040 [US4] Create Celery beat task for periodic sync in backend/app/modules/email/sync/scheduler.py
  - sync_all_email_connections(): Every 15 minutes
  - Get all ACTIVE connections
  - Run incremental sync for each
  - Update last_sync_at
- [ ] T041 [US4] Add Celery beat schedule to backend/app/celery_config.py
  - sync-email-connections: crontab(minute='*/15')
- [ ] T042 [US4] Create sync status endpoint in backend/app/modules/email/router.py
  - GET /email/connections/{connection_id}/sync/status
  - Return current job status, last sync time, email count
- [ ] T043 [P] [US4] Add sync status to frontend API client in frontend/src/lib/api/email.ts
  - getSyncStatus(connectionId)
  - triggerSync(connectionId, fullBackfill)

**Checkpoint**: Automatic 15-minute sync operational

---

## Phase 7: User Story 5 - Email Forwarding Fallback (Priority: P2)

**Goal**: Alternative email capture for organizations that can't use OAuth

**Independent Test**: Forward an ATO email to ingest address → email appears in Clairo inbox

### Implementation for User Story 5

- [ ] T044 [US5] Create ForwardingConfig model fields in backend/app/modules/email/models.py
  - Add to EmailConnection or separate ForwardingSetup table
  - forwarding_address: {tenant_slug}@ingest.clairo.ai
- [ ] T045 [US5] Create inbound email processor in backend/app/modules/email/ingest/forwarding.py
  - parse_forwarded_email(raw_email_data)
  - Extract original sender from X-Original-Sender or body
  - Validate sender is @ato.gov.au
  - Rate limit: 100 emails/hour per tenant
- [ ] T046 [US5] Create forwarding endpoints in backend/app/modules/email/router.py
  - GET /email/forwarding - get forwarding address
  - POST /email/forwarding - enable forwarding
  - POST /email/ingest (internal) - receive forwarded email
- [ ] T047 [P] [US5] Create ForwardingSetup component in frontend/src/components/email/ForwardingSetup.tsx
  - Display unique forwarding address
  - Show setup instructions for mail rules

**Checkpoint**: Email forwarding fallback works

---

## Phase 8: User Story 6 - Connection Management (Priority: P2)

**Goal**: Allow disconnect and reconnect of email accounts

**Independent Test**: View connected accounts → disconnect one → reconnect with different account

### Implementation for User Story 6

- [ ] T048 [US6] Add connection management endpoints in backend/app/modules/email/router.py
  - GET /email/connections - list all connections
  - GET /email/connections/{id} - get connection details
  - DELETE /email/connections/{id} - disconnect
  - POST /email/connections/{id}/reconnect - initiate re-auth
- [ ] T049 [US6] Update EmailService for connection management
  - disconnect(): Remove tokens, mark as DISCONNECTED
  - reconnect(): Generate new OAuth URL for existing connection
- [ ] T050 [US6] Create ConnectionCard component in frontend/src/components/email/ConnectionCard.tsx
  - Display email, provider, status, last sync time
  - Reconnect button for EXPIRED status
  - Disconnect button
- [ ] T051 [US6] Create email connections page in frontend/src/app/(protected)/settings/email-connections/page.tsx
  - List all connections using ConnectionCard
  - Connect Gmail and Connect Outlook buttons
  - Handle OAuth callback redirect

**Checkpoint**: Full connection management UI operational

---

## Phase 9: User Story 7 - Token Refresh (Priority: P1)

**Goal**: Automatic token refresh before expiry

**Independent Test**: Token expires → is automatically refreshed → sync continues without user action

### Tests for User Story 7

- [ ] T052 [P] [US7] Unit test for token refresh in backend/tests/unit/modules/email/test_token_refresh.py
  - Test Gmail token refresh
  - Test Microsoft token refresh
  - Test refresh failure marks connection EXPIRED

### Implementation for User Story 7

- [ ] T053 [US7] Add refresh_token() to GmailOAuthClient in backend/app/modules/email/oauth/gmail.py
  - Use grant_type=refresh_token
  - Return new access token and expiry
- [ ] T054 [US7] Add refresh_token() to MicrosoftOAuthClient in backend/app/modules/email/oauth/microsoft.py
  - Use grant_type=refresh_token
  - Handle refresh_token rotation (Microsoft returns new refresh token)
- [ ] T055 [US7] Create Celery beat task for token refresh in backend/app/modules/email/sync/scheduler.py
  - refresh_expiring_tokens(): Every 30 minutes
  - Get tokens expiring in next hour
  - Refresh and update encrypted tokens
  - Mark EXPIRED on refresh failure
- [ ] T056 [US7] Add Celery beat schedule for token refresh to backend/app/celery_config.py
  - refresh-expiring-tokens: crontab(minute='*/30')
- [ ] T057 [US7] Add connection expired notification in backend/app/modules/email/service.py
  - When marking EXPIRED, emit event for notification
  - Integrate with notifications module

**Checkpoint**: Token refresh runs proactively before expiry

---

## Phase 10: ATO Inbox UI

**Goal**: Display synced ATO emails in a dedicated inbox view

### Implementation

- [ ] T058 [P] Create email list endpoint in backend/app/modules/email/router.py
  - GET /email/inbox - list ATO emails with pagination
  - Filter by: connection_id, is_read, is_processed, date range
  - Return unread_count
- [ ] T059 Create email detail endpoint in backend/app/modules/email/router.py
  - GET /email/inbox/{email_id} - get email details
  - POST /email/inbox/{email_id}/mark-read - mark as read
  - GET /email/inbox/{email_id}/attachments/{attachment_id} - download
- [ ] T060 [P] Add email inbox to frontend API client in frontend/src/lib/api/email.ts
  - listEmails(filters, pagination)
  - getEmail(id), markAsRead(id), downloadAttachment(emailId, attachmentId)
- [ ] T061 Create EmailInbox page in frontend/src/app/(protected)/ato-inbox/page.tsx
  - List synced emails with filters
  - Show unread count badge
  - Pagination controls
- [ ] T062 [P] Create EmailRow component in frontend/src/components/email/EmailRow.tsx
  - Display: from, subject, date, read status
  - Attachment indicator
  - Click to view detail
- [ ] T063 Create EmailDetail modal/page in frontend/src/components/email/EmailDetail.tsx
  - Full email view with HTML/text toggle
  - Attachment download links
  - Mark as read on view

**Checkpoint**: ATO inbox UI fully functional

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T064 [P] Add audit events for email operations in backend/app/modules/email/service.py
  - email.connection.created, email.connection.revoked
  - email.connection.expired, email.sync.completed
  - email.received (for each new email)
- [ ] T065 [P] Add rate limiting to OAuth endpoints
  - Limit OAuth initiations per tenant
  - Limit sync triggers to prevent abuse
- [ ] T066 [P] Add error handling for OAuth failures in backend/app/modules/email/router.py
  - Handle provider errors (access_denied, invalid_grant)
  - User-friendly error messages
- [ ] T067 Add sync progress tracking in backend/app/modules/email/sync/scheduler.py
  - Emit progress events during long backfills
  - Store progress in EmailSyncJob
- [ ] T068 [P] Run quickstart.md validation
  - Verify all code snippets work
  - Test OAuth flows with real credentials
- [ ] T069 Code review and cleanup
  - Ensure consistent error handling
  - Add docstrings to all public methods
  - Remove debug logging

---

## Phase FINAL: PR & Merge (REQUIRED)

**Purpose**: Create pull request and merge to main

- [ ] TFINAL-1 Ensure all tests pass
  - Run: `uv run pytest backend/tests/unit/modules/email/ -v`
  - Run: `uv run pytest backend/tests/integration/api/test_email*.py -v`
  - All tests must pass before PR

- [ ] TFINAL-2 Run linting and type checking
  - Run: `uv run ruff check backend/app/modules/email/`
  - Run: `uv run mypy backend/app/modules/email/`
  - Run: `npm run lint` in frontend
  - Fix any issues

- [ ] TFINAL-3 Push feature branch and create PR
  - Run: `git push -u origin feature/026-email-integration-oauth`
  - Run: `gh pr create --title "Spec 026: Email Integration & OAuth" --body "..."`
  - Include summary of changes in PR description

- [ ] TFINAL-4 Address review feedback (if any)
  - Make requested changes
  - Push additional commits

- [ ] TFINAL-5 Merge PR to main
  - Squash merge after approval
  - Delete feature branch after merge

- [ ] TFINAL-6 Update ROADMAP.md
  - Mark spec 026 as COMPLETE
  - Update current focus to next spec

---

## Dependencies & Execution Order

### Phase Dependencies

- **Git Setup (Phase 0)**: MUST be done first
- **Setup (Phase 1)**: Depends on Phase 0
- **Foundational (Phase 2)**: Depends on Phase 1 - BLOCKS all user stories
- **User Stories (Phases 3-9)**: All depend on Phase 2 completion
  - US1 (Gmail OAuth): No dependencies
  - US2 (Microsoft OAuth): Shares OAuth base with US1
  - US3 (Initial Backfill): Depends on US1 or US2 for connection
  - US4 (Automatic Sync): Depends on US3 for sync infrastructure
  - US5 (Forwarding): Independent, can run in parallel
  - US6 (Management): Depends on US1/US2 for connections to manage
  - US7 (Token Refresh): Depends on US1/US2 for tokens to refresh
- **ATO Inbox UI (Phase 10)**: Depends on US3/US4 for emails to display
- **Polish (Phase 11)**: Depends on all user stories

### User Story Dependencies

```
US1 (Gmail) ──┬── US3 (Backfill) ── US4 (Auto Sync) ── Phase 10 (Inbox UI)
              │
US2 (Microsoft)┘

US5 (Forwarding) - Independent

US6 (Management) - Depends on US1/US2

US7 (Token Refresh) - Depends on US1/US2
```

### Parallel Opportunities

**Phase 2 (Foundational):**
```
T006 (Enums) ─┬─ T007 (EmailConnection)
              ├─ T008 (EmailSyncJob)    } All in parallel
              ├─ T009 (RawEmail)        } (different models)
              └─ T010 (EmailAttachment)

T013 (ConnectionRepo) ─┬─ T014 (EmailRepo)     } In parallel
                       └─ T015 (SyncJobRepo)   } (different repos)
```

**Phase 3 (Gmail OAuth):**
```
T016 (Crypto tests) ─┬─ T017 (OAuth tests)  } In parallel
                     └─ T018 (Integration)  } (different test files)
```

**User Stories in Parallel (with sufficient team):**
```
After Phase 2:
  Developer A: US1 (Gmail) → US3 (Backfill)
  Developer B: US2 (Microsoft) → US4 (Auto Sync)
  Developer C: US5 (Forwarding) + US6 (Management)
```

---

## Implementation Strategy

### MVP First (Gmail OAuth + Initial Sync)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (Gmail OAuth)
4. Complete Phase 5: User Story 3 (Initial Backfill)
5. **STOP and VALIDATE**: Gmail connects and syncs ATO emails
6. Deploy/demo if ready - this is the core value

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add Gmail OAuth (US1) → Test → First connection type (MVP!)
3. Add Microsoft OAuth (US2) → Test → Second connection type
4. Add Initial Backfill (US3) → Test → Historical emails visible
5. Add Automatic Sync (US4) → Test → Real-time capture
6. Add Token Refresh (US7) → Test → Long-term reliability
7. Add Management UI (US6) → Test → User control
8. Add Forwarding (US5) → Test → Fallback option
9. Add Inbox UI (Phase 10) → Test → Complete experience

---

## Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| 0 | 1 | Git setup |
| 1 | 4 | Module structure |
| 2 | 11 | Models, repos, schemas |
| 3 | 10 | Gmail OAuth (P1) |
| 4 | 4 | Microsoft OAuth (P1) |
| 5 | 7 | Initial Backfill (P1) |
| 6 | 8 | Automatic Sync (P1) |
| 7 | 4 | Forwarding Fallback (P2) |
| 8 | 4 | Connection Management (P2) |
| 9 | 6 | Token Refresh (P1) |
| 10 | 6 | ATO Inbox UI |
| 11 | 6 | Polish |
| FINAL | 6 | PR & Merge |

**Total Tasks**: 77
**P1 Stories**: 5 (Gmail, Microsoft, Backfill, Auto Sync, Token Refresh)
**P2 Stories**: 2 (Forwarding, Management)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- OAuth credentials must be configured in Google Cloud Console and Azure Portal
- Token encryption key must be 32 bytes base64-encoded
- All tokens are encrypted at rest (AES-256-GCM)
- Only @ato.gov.au emails are synced (privacy by design)
- Celery beat required for automatic sync and token refresh
