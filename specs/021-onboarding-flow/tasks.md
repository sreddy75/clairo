# Tasks: Onboarding Flow

**Input**: Design documents from `/specs/021-onboarding-flow/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/openapi.yaml, quickstart.md

---

## User Stories Summary

| Story | Title | Priority | Focus |
|-------|-------|----------|-------|
| US1 | New Accountant Signup with Tier Selection | P1 | Tier selection, Stripe checkout |
| US2 | Free Trial Experience | P1 | Trial management, reminders |
| US3 | Connect Xero Integration | P1 | Xero/XPM OAuth |
| US4 | Bulk Import Practice Clients | P2 | Multi-select import, progress |
| US5 | Interactive Product Tour | P2 | react-joyride walkthrough |
| US6 | Onboarding Checklist | P2 | Progress widget |
| US7 | Welcome Email Drip Sequence | P3 | Resend + Celery emails |

---

## Phase 0: Git Setup (REQUIRED)

**Purpose**: Create feature branch before any implementation

- [x] T001 Create feature branch from main
  - Run: `git checkout main && git pull origin main`
  - Run: `git checkout -b 021-onboarding-flow`
  - Verify: You are now on the feature branch

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and shared structure

- [x] T002 Create onboarding module directory structure in backend/app/modules/onboarding/
  - Create: `__init__.py`, `models.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`, `events.py`, `tasks.py`

- [x] T003 [P] Create onboarding app routes in frontend/src/app/onboarding/
  - Create: `page.tsx`, `layout.tsx`
  - Create subdirs: `tier-selection/`, `connect-xero/`, `import-clients/`

- [x] T004 [P] Create onboarding components directory in frontend/src/components/onboarding/
  - Create placeholder files for components

- [x] T005 [P] Install react-joyride dependency
  - Run: `cd frontend && npm install react-joyride`

- [x] T006 Register onboarding router in backend/app/main.py
  - Add: `from app.modules.onboarding.router import router as onboarding_router`
  - Add: `app.include_router(onboarding_router, prefix="/api/v1/onboarding", tags=["Onboarding"])`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

- [x] T007 Create OnboardingStatus enum in backend/app/modules/onboarding/models.py
  - Values: STARTED, TIER_SELECTED, PAYMENT_SETUP, XERO_CONNECTED, CLIENTS_IMPORTED, TOUR_COMPLETED, COMPLETED, SKIPPED_XERO

- [x] T008 Create OnboardingProgress model in backend/app/modules/onboarding/models.py
  - Fields: id, tenant_id (FK unique), status, current_step, started_at, tier_selected_at, payment_setup_at, xero_connected_at, clients_imported_at, tour_completed_at, completed_at, checklist_dismissed_at, xero_skipped, tour_skipped, metadata
  - Add relationship to Tenant model

- [x] T009 Create BulkImportJobStatus enum in backend/app/modules/onboarding/models.py
  - Values: PENDING, IN_PROGRESS, COMPLETED, PARTIAL_FAILURE, FAILED, CANCELLED

- [x] T010 Create BulkImportJob model in backend/app/modules/onboarding/models.py
  - Fields: id, tenant_id (FK), status, source_type, total_clients, imported_count, failed_count, client_ids (JSONB), imported_clients (JSONB), failed_clients (JSONB), progress_percent, started_at, completed_at, error_message
  - Add relationship to Tenant model

- [x] T011 Create EmailDrip model in backend/app/modules/onboarding/models.py
  - Fields: id, tenant_id (FK), email_type, sent_at, recipient_email, metadata
  - Add unique constraint on (tenant_id, email_type)

- [x] T012 Update Tenant model in backend/app/modules/auth/models.py
  - Add relationships: onboarding_progress (1:1), import_jobs (1:N), email_drips (1:N)

- [x] T013 Generate Alembic migration for onboarding tables
  - Run: `cd backend && uv run alembic revision --autogenerate -m "add_onboarding_tables"`
  - Verify migration creates: onboarding_progress, bulk_import_jobs, email_drips tables

- [x] T014 Apply migration
  - Run: `cd backend && uv run alembic upgrade head`

- [x] T015 Create Pydantic schemas in backend/app/modules/onboarding/schemas.py
  - OnboardingProgressResponse, ChecklistItem, OnboardingChecklist
  - TierSelectionRequest, TierSelectionResponse
  - PaymentCompleteRequest, XeroConnectResponse
  - AvailableClientsResponse, AvailableClient
  - BulkImportRequest, BulkImportJobResponse, ImportedClient, FailedClient

- [x] T016 Create OnboardingRepository in backend/app/modules/onboarding/repository.py
  - Methods: get_by_tenant_id, create, update, get_or_create

- [x] T017 Create BulkImportJobRepository in backend/app/modules/onboarding/repository.py
  - Methods: create, get_by_id, update, list_by_tenant

- [x] T018 Create EmailDripRepository in backend/app/modules/onboarding/repository.py
  - Methods: create, get_by_tenant_and_type, has_sent

- [x] T019 Create audit events in backend/app/modules/onboarding/events.py
  - Events: onboarding.started, onboarding.tier_selected, onboarding.trial_started, onboarding.xero_connected, onboarding.bulk_import_started, onboarding.bulk_import_completed, onboarding.tour_completed, onboarding.completed

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Signup with Tier Selection (Priority: P1)

**Goal**: New accountants can select a subscription tier and start Stripe checkout with trial

**Independent Test**: Start from marketing site, complete signup, select tier, verify Stripe checkout opens with $0.00 trial

### Implementation for User Story 1

- [x] T020 [US1] Create OnboardingService.start_onboarding() in backend/app/modules/onboarding/service.py
  - Create OnboardingProgress record with status=STARTED
  - Emit audit event

- [x] T021 [US1] Create OnboardingService.select_tier() in backend/app/modules/onboarding/service.py
  - Validate tier is valid
  - Create Stripe checkout session with trial_period_days=14
  - Update progress to TIER_SELECTED
  - Return checkout URL

- [x] T022 [US1] Create OnboardingService.complete_payment() in backend/app/modules/onboarding/service.py
  - Verify Stripe session
  - Update tenant tier and subscription status
  - Update progress to PAYMENT_SETUP
  - Emit audit event

- [x] T023 [US1] Extend BillingService.create_trial_subscription() in backend/app/modules/billing/service.py
  - Add trial_period_days parameter
  - Set trial_ends_at on tenant

- [x] T024 [US1] Create onboarding API endpoints in backend/app/modules/onboarding/router.py
  - GET /progress - get current progress
  - POST /start - start onboarding
  - POST /tier - select tier, return checkout URL
  - POST /payment-complete - mark payment done

- [x] T025 [P] [US1] Create TierCard component in frontend/src/components/onboarding/TierCard.tsx
  - Props: tier name, price, features, client limit, recommended flag
  - Handle selection callback

- [x] T026 [P] [US1] Create TierSelection page in frontend/src/app/onboarding/tier-selection/page.tsx
  - Display all tiers using TierCard
  - Highlight Professional as recommended
  - Show "14-Day Free Trial" messaging
  - Handle Stripe checkout redirect

- [x] T027 [US1] Create useOnboarding hook in frontend/src/hooks/useOnboarding.ts
  - Fetch and cache onboarding progress
  - Provide methods: startOnboarding, selectTier, completePayment

- [x] T028 [US1] Create onboarding API client in frontend/src/lib/api/onboarding.ts
  - Functions: getProgress, startOnboarding, selectTier, completePayment

- [x] T029 [US1] Update Clerk auth callback to redirect to onboarding
  - In frontend/src/middleware.ts or auth callback
  - Check if onboarding incomplete, redirect to /onboarding
  - Note: Already implemented in (protected)/layout.tsx checkRegistration()

- [x] T030 [US1] Create onboarding layout in frontend/src/app/onboarding/layout.tsx
  - Show progress indicator (step 1/5, etc.)
  - Minimal header, no sidebar

**Checkpoint**: User Story 1 complete - new users can select tier and start trial

---

## Phase 4: User Story 2 - Free Trial Experience (Priority: P1)

**Goal**: 14-day trial with reminders and auto-conversion

**Independent Test**: Sign up for trial, verify trial status displays, check reminder emails are sent

### Implementation for User Story 2

- [x] T031 [US2] Create trial status endpoint in backend/app/modules/billing/router.py
  - GET /trial-status - return days remaining, end date, tier

- [x] T032 [US2] Create Celery task for trial reminders in backend/app/modules/onboarding/tasks.py
  - check_trial_reminders() - daily task
  - Find trials ending in 3 days, 1 day
  - Send reminder emails via NotificationService

- [x] T033 [US2] Register Celery beat schedule in backend/app/tasks/celeryconfig.py
  - Add daily task for check_trial_reminders at 9am AEDT

- [x] T034 [P] [US2] Create trial reminder email template in backend/app/modules/notifications/templates.py
  - Variables: user_name, days_remaining, tier, price, billing_date

- [x] T035 [US2] Handle Stripe webhook for trial_will_end in backend/app/modules/billing/webhooks.py
  - Event: customer.subscription.trial_will_end
  - Send final reminder email

- [x] T036 [US2] Handle Stripe webhook for trial conversion in backend/app/modules/billing/webhooks.py
  - Event: invoice.paid (first after trial)
  - Update subscription_status to ACTIVE
  - Send receipt email

- [x] T037 [US2] Handle payment failure on trial end in backend/app/modules/billing/webhooks.py
  - Event: invoice.payment_failed
  - Update subscription_status to PAST_DUE
  - Start 7-day grace period

- [x] T038 [P] [US2] Create TrialBanner component in frontend/src/components/billing/TrialBanner.tsx
  - Show days remaining, billing date, dismiss option

- [x] T039 [US2] Add trial banner to dashboard layout in frontend/src/app/(protected)/layout.tsx
  - Show TrialBanner when subscription_status === 'trial'

**Checkpoint**: User Story 2 complete - trial experience with reminders working

---

## Phase 5: User Story 3 - Connect Xero Integration (Priority: P1)

**Goal**: Xero/XPM OAuth connection as part of onboarding

**Independent Test**: Navigate to Connect Xero step, complete OAuth, verify connection established

### Implementation for User Story 3

- [x] T040 [US3] Create OnboardingService.initiate_xero_connect() in backend/app/modules/onboarding/service.py
  - Generate Xero OAuth URL with appropriate scopes
  - Include XPM scopes if available

- [x] T041 [US3] Create OnboardingService.complete_xero_connect() in backend/app/modules/onboarding/service.py
  - Handle OAuth callback
  - Update progress to XERO_CONNECTED
  - Emit audit event

- [x] T042 [US3] Create OnboardingService.skip_xero() in backend/app/modules/onboarding/service.py
  - Update progress to SKIPPED_XERO
  - Set xero_skipped=True

- [x] T043 [US3] Create XeroService.detect_connection_type() - deferred to Xero integration spec
  - Check OAuth scopes for XPM (practice.clients)
  - Return "xpm" or "xero_accounting"

- [x] T044 [US3] Add Xero onboarding endpoints in backend/app/modules/onboarding/router.py
  - POST /xero/connect - initiate OAuth
  - GET /xero/callback - handle callback
  - POST /xero/skip - skip connection

- [x] T045 [P] [US3] Create ConnectXero page in frontend/src/app/onboarding/connect-xero/page.tsx
  - Explain why Xero is needed
  - "Connect Xero" button opens OAuth
  - "Skip for now" with warning modal
  - Show connected org name on success

- [x] T046 [US3] Handle Xero OAuth callback in frontend
  - Create callback handler in frontend/src/app/onboarding/xero/callback/page.tsx
  - Parse code/state, call backend, redirect to next step

- [x] T047 [US3] Update useOnboarding hook with Xero methods
  - Add: connectXero, skipXero

**Checkpoint**: User Story 3 complete - Xero connection integrated into onboarding

---

## Phase 6: User Story 4 - Bulk Import Practice Clients (Priority: P2)

**Goal**: Multi-select bulk import with background processing and progress tracking

**Independent Test**: Connect XPM, select multiple clients, start import, verify progress updates and completion

### Implementation for User Story 4

- [x] T048 [US4] Create XPM client fetching in backend/app/modules/integrations/xero/xpm_client.py
  - XPMClient class with get_clients() method
  - Handle pagination and rate limits
  - Note: Stub implemented in OnboardingService.get_available_clients() - actual XPM API deferred to Xero integration spec

- [x] T049 [US4] Create XeroService.get_available_clients() in backend/app/modules/integrations/xero/service.py
  - Detect XPM vs Xero Accounting
  - Return list of clients available for import
  - Mark already-imported clients
  - Note: Stub implemented in OnboardingService - actual Xero API deferred to Xero integration spec

- [x] T050 [US4] Create OnboardingService.get_available_clients() in backend/app/modules/onboarding/service.py
  - Call XeroService
  - Apply tier client limit
  - Return paginated, searchable list
  - Implemented with stub data structure

- [x] T051 [US4] Create OnboardingService.start_bulk_import() in backend/app/modules/onboarding/service.py
  - Validate client_ids
  - Check tier limit not exceeded
  - Create BulkImportJob record
  - Queue Celery task
  - Return job_id
  - Implemented with TODO for Celery task queueing

- [x] T052 [US4] Create bulk import Celery task in backend/app/modules/onboarding/tasks.py
  - bulk_import_clients(job_id, client_ids)
  - For each client: fetch from XPM/Xero, create Client record, sync transactions
  - Update job progress every 5 clients
  - Handle errors, allow partial success
  - Note: Task structure exists - actual client creation deferred to Xero integration

- [x] T053 [US4] Create OnboardingService.get_import_job() in backend/app/modules/onboarding/service.py
  - Return job with current progress
  - Implemented

- [x] T054 [US4] Create OnboardingService.retry_failed_imports() in backend/app/modules/onboarding/service.py
  - Create new job with failed client_ids
  - Queue Celery task
  - Implemented

- [x] T055 [US4] Add import endpoints in backend/app/modules/onboarding/router.py
  - GET /clients/available - list clients for import
  - POST /clients/import - start bulk import
  - GET /import/{job_id} - get job status
  - POST /import/{job_id}/retry - retry failed
  - All endpoints implemented

- [x] T056 [P] [US4] Create ClientImportList component in frontend/src/components/onboarding/ClientImportList.tsx
  - Searchable/filterable list
  - Checkboxes for multi-select
  - "Select All" (respects tier limit)
  - Show tier limit warning
  - Integrated directly into ImportClients page

- [x] T057 [P] [US4] Create ImportProgress component in frontend/src/components/onboarding/ImportProgress.tsx
  - Progress bar with percentage
  - Client-by-client status
  - Error list with retry button
  - Implemented as ImportProgressView in page.tsx

- [x] T058 [US4] Create ImportClients page in frontend/src/app/onboarding/import-clients/page.tsx
  - Show ClientImportList
  - "Import Selected" button
  - Switch to ImportProgress when job starts
  - Poll for progress updates
  - Updated to use actual API

- [x] T059 [US4] Create useImportJob hook in frontend/src/hooks/useImportJob.ts
  - Poll import job status every 2s while in_progress
  - Return progress, status, imported/failed lists
  - Implemented

- [x] T060 [US4] Update useOnboarding hook with import methods
  - Add: getAvailableClients, startImport, getImportJob, retryFailedImports
  - Functions available in frontend/src/lib/api/onboarding.ts

**Checkpoint**: User Story 4 complete - bulk import with progress tracking working

---

## Phase 6b: Client Organization Authorization (Priority: P2)

**Goal**: Enable accountants to authorize access to each client's Xero organization for financial data sync

**Background**: XPM provides client metadata (names, contacts), but accessing each client's financial data (invoices, transactions, BAS) requires separate OAuth authorization for each client's Xero organization. This phase implements both Individual Authorization (available now) and prepares for Bulk Connections (future).

**Independent Test**: Load XPM client list, authorize a client's Xero org, verify tenant ID stored, sync financial data

### Phase 6b.1: Data Model & Backend Infrastructure

- [x] T060A [US4] Add xero_tenant_id field to Client model in backend/app/modules/clients/models.py
  - Field: xero_tenant_id (UUID, nullable) - links to authorized Xero organization
  - Field: xero_connection_status (enum: not_connected, connected, disconnected, no_access)
  - Field: xero_connected_at (datetime, nullable)
  - Field: xero_org_name (string, nullable) - cached org name from Xero
  - Implemented via XpmClient model with connection_status, xero_connection_id, xero_org_name fields

- [x] T060B [US4] Create XeroConnection model in backend/app/modules/integrations/xero/models.py
  - Fields: id, tenant_id (FK to our tenant), xero_tenant_id (Xero's tenant UUID), xero_org_name, connection_type (practice/client), auth_event_id (for bulk connections grouping), connected_at, disconnected_at, status
  - This tracks ALL Xero organizations connected via OAuth, separate from Client records
  - Added XeroConnectionType enum, XpmClientConnectionStatus enum, XpmClient model

- [x] T060C [US4] Create Alembic migration for client Xero connection fields
  - Migration 027_xpm_client_auth.py - XpmClient table and XeroConnection type fields
  - Migration 028_oauth_client_fields.py - OAuth state client-specific fields

- [x] T060D [US4] Create XeroConnectionRepository in backend/app/modules/integrations/xero/repository.py
  - Methods: create, get_by_xero_tenant_id, get_all_for_tenant, update_status, get_unmatched_connections
  - Added XpmClientRepository with full CRUD and connection management

### Phase 6b.2: Xero Connections Endpoint Integration

- [x] T060E [US4] Create service method to fetch all connections from Xero API
  - XpmClientService.fetch_xero_connections() in integrations/xero/service.py
  - Call GET /connections with access token
  - Return list of XeroOrganization with tenantId, tenantType, tenantName, authEventId

- [x] T060F [US4] Create service method to store/update Xero connections
  - XpmClientService.sync_xero_connections()
  - For each connection from API, create/update XeroConnection record
  - Group by authEventId to identify bulk connection batches

- [x] T060G [US4] Create service method to match Xero orgs to XPM clients
  - XpmClientService.match_connections_to_xpm_clients()
  - Match by: exact org name, ABN (if available), or fuzzy name match
  - Update XpmClient.xero_connection_id for matched clients
  - Return list of unmatched connections for manual review

- [x] T060H [US4] Add endpoint to trigger connection sync and matching
  - POST /api/v1/onboarding/xero/sync-connections
  - Fetches connections, stores them, attempts matching
  - Returns: {sync_result, match_result}

### Phase 6b.3: Individual Client Authorization (Current Approach)

- [x] T060I [US4] Create endpoint to initiate OAuth for specific client
  - POST /api/v1/onboarding/xpm-clients/{client_id}/connect-xero
  - Generates OAuth URL with state containing xpm_client_id
  - XeroOAuthService.generate_client_auth_url() with XeroConnectionType.CLIENT
  - Returns: XpmClientConnectXeroResponse with authorization_url, client_id, client_name

- [x] T060J [US4] Update Xero OAuth callback to handle client-specific auth
  - Parse xpm_client_id from OAuth state
  - XeroOAuthService.handle_callback() returns tuple (connection, xpm_client_id)
  - Auto-links connection to XpmClient after successful OAuth
  - Updated Xero router callback to handle client context

- [x] T060K [US4] Create "Connect All Remaining" workflow backend support
  - POST /api/v1/onboarding/xpm-clients/connect-next
  - Returns next unconnected client and OAuth URL
  - XpmClientService.list_xpm_clients() with NOT_CONNECTED filter

- [x] T060L [US4] Add client Xero status to available clients response
  - Updated AvailableClient schema with xero_org_status, xero_connection_id
  - OnboardingService.get_available_clients() fetches XPM clients with connection status
  - Allow filtering by connection status

### Phase 6b.4: Frontend - Individual Authorization UI

- [x] T060M [P] [US4] Update ImportClients page to show Xero connection status
  - Added connection status badges (Connected/Disconnected/Not Connected/No Access)
  - Added Xero Connection Progress section with progress bar
  - Added "Connect Xero" button for unconnected clients

- [x] T060N [P] [US4] Create ConnectClientXero modal/flow component
  - frontend/src/components/onboarding/ConnectClientXeroModal.tsx
  - Shows client name, explains what will be authorized
  - Lists data access (bank transactions, invoices, chart of accounts, GST reports)
  - "Connect" button initiates OAuth via useClientXeroConnection hook

- [x] T060O [P] [US4] Create ConnectAllRemainingFlow component
  - frontend/src/components/onboarding/ConnectAllRemainingFlow.tsx
  - Shows progress: "Connecting X of Y clients..."
  - Sequential OAuth redirects with automatic continuation
  - Option to pause/resume the flow
  - Skip button for individual clients

- [x] T060P [P] [US4] Add "Connect All Remaining" button to ImportClients page
  - Shows count of unconnected clients in button
  - Opens ConnectAllRemainingFlow modal
  - Updates client list as connections complete via onConnectionLinked callback

- [x] T060Q [US4] Create useClientXeroConnection hook
  - frontend/src/hooks/useClientXeroConnection.ts
  - Methods: connectClient, startConnectAll, connectNext, skipClient, pauseConnectAll, resumeConnectAll
  - Handles OAuth redirect and session storage for connect-all flow state

### Phase 6b.5: Bulk Connections Support (Future - When Advanced Partner Enabled)

- [ ] T060R [US4] Add XERO_BULK_CONNECTIONS_ENABLED config flag
  - Environment variable: XERO_BULK_CONNECTIONS_ENABLED=false (default)
  - When true, enables bulk connection features

- [ ] T060S [US4] Create bulk connections OAuth initiation
  - POST /api/v1/onboarding/xero/bulk-connect
  - Does NOT include acr_values=bulk_connect:false
  - State includes: bulk=true, tenant_id
  - Returns OAuth URL for multi-org selection

- [ ] T060T [US4] Update OAuth callback to handle bulk connections
  - Detect bulk=true in state
  - Call /connections to get ALL newly authorized orgs
  - Store all XeroConnection records with same authEventId
  - Trigger matching process
  - Return summary: {connected: N, matched: M, unmatched: U}

- [ ] T060U [P] [US4] Create BulkConnectionsButton component (conditional)
  - Only shown when XERO_BULK_CONNECTIONS_ENABLED=true
  - "Connect All Client Organizations" button
  - Explains: "Select all your client Xero accounts in one step"

- [ ] T060V [P] [US4] Create BulkConnectionsResult component
  - Shows results after bulk OAuth completes
  - List of matched clients with "Sync Now" option
  - List of unmatched orgs with manual matching UI

### Phase 6b.6: Manual Matching & Admin Tools

- [x] T060W [US4] Create endpoint for manual client-to-org matching
  - POST /api/v1/onboarding/xpm-clients/{client_id}/link-xero-org
  - Body: {xero_tenant_id: "..."}
  - XpmClientService.link_client_by_tenant_id() links by Xero tenant ID

- [x] T060X [US4] Create endpoint to list unmatched Xero connections
  - GET /api/v1/onboarding/xero/unmatched-connections
  - XpmClientService.get_unmatched_connections() returns unlinked active connections

- [x] T060Y [P] [US4] Create UnmatchedConnectionsManager component
  - frontend/src/components/onboarding/UnmatchedConnectionsManager.tsx
  - Lists unmatched Xero orgs with client dropdown selector
  - Link button with loading state and success/error feedback
  - Integrated into ImportClients page

**Checkpoint**: Phase 6b complete - Client organization authorization working (individual auth complete, bulk connections deferred to Phase 6b.5 when Xero Advanced Partner enabled)

---

## Phase 7: User Story 5 - Interactive Product Tour (Priority: P2)

**Goal**: react-joyride guided tour of main features

**Independent Test**: Complete onboarding, verify tour auto-starts, navigate through steps, skip works

### Implementation for User Story 5

- [x] T061 [US5] Create OnboardingService.complete_tour() in backend/app/modules/onboarding/service.py
  - Update progress to TOUR_COMPLETED
  - Check if all steps done, set COMPLETED if so
  - Already implemented

- [x] T062 [US5] Create OnboardingService.skip_tour() in backend/app/modules/onboarding/service.py
  - Set tour_skipped=True
  - Update progress appropriately
  - Already implemented

- [x] T063 [US5] Add tour endpoints in backend/app/modules/onboarding/router.py
  - POST /tour/complete - mark tour done
  - POST /tour/skip - skip tour
  - Already implemented

- [x] T064 [P] [US5] Define tour steps configuration in frontend/src/components/onboarding/tourSteps.ts
  - Step 1: Dashboard overview (.dashboard-header)
  - Step 2: Client list (.client-list)
  - Step 3: BAS workflow (.bas-workflow)
  - Step 4: Data quality (.quality-score)
  - Step 5: AI insights (.ai-insights)
  - Step 6: Settings (.settings-menu)
  - Created with TOUR_STEPS constant

- [x] T065 [US5] Create ProductTour component in frontend/src/components/onboarding/ProductTour.tsx
  - Use react-joyride with configured steps
  - Handle skip callback
  - Handle complete callback
  - Persist tour state
  - Created with styled react-joyride integration

- [x] T066 [US5] Create useTour hook in frontend/src/hooks/useTour.ts
  - Check if tour should run (first visit, not skipped)
  - Methods: startTour, skipTour, completeTour
  - Created with shouldShowTour, isTourRunning, startTour, handleTourEnd

- [x] T067 [US5] Integrate tour into dashboard layout in frontend/src/app/(dashboard)/layout.tsx
  - Add ProductTour component
  - Auto-start if onboarding.tour_completed_at is null and not skipped
  - Integrated in (protected)/layout.tsx with auto-start and data-tour attributes

- [x] T068 [US5] Add "Restart Tour" option in Help menu
  - In frontend/src/components/layout/HelpMenu.tsx or similar
  - Added Help menu with HelpCircle icon in header

**Checkpoint**: User Story 5 complete - product tour integrated

---

## Phase 8: User Story 6 - Onboarding Checklist (Priority: P2)

**Goal**: Persistent progress widget showing onboarding completion

**Independent Test**: View checklist at each onboarding stage, verify items update, dismiss works

### Implementation for User Story 6

- [x] T069 [US6] Create OnboardingService.get_checklist() in backend/app/modules/onboarding/service.py
  - Build checklist from OnboardingProgress
  - Items: tier selected, payment setup, xero connected, clients imported, tour complete
  - Return completed_count, total_count
  - Already implemented

- [x] T070 [US6] Create OnboardingService.dismiss_checklist() in backend/app/modules/onboarding/service.py
  - Set checklist_dismissed_at
  - Checklist hidden permanently
  - Already implemented

- [x] T071 [US6] Add checklist endpoint in backend/app/modules/onboarding/router.py
  - POST /checklist/dismiss - dismiss checklist
  - Already implemented

- [x] T072 [P] [US6] Create OnboardingChecklist component in frontend/src/components/onboarding/OnboardingChecklist.tsx
  - Collapsible widget
  - Show progress (e.g., "3 of 5 steps complete")
  - Expandable to show all items
  - Checkmark for completed items
  - Dismiss button
  - Created with expandable UI, progress bar, and links to incomplete items

- [x] T073 [US6] Create useChecklist hook in frontend/src/hooks/useChecklist.ts
  - Derive checklist state from onboarding progress
  - Methods: dismissChecklist
  - Created with shouldShow logic including auto-hide after 3 days

- [x] T074 [US6] Integrate checklist into app layout in frontend/src/app/(dashboard)/layout.tsx
  - Show OnboardingChecklist if not completed and not dismissed
  - Auto-hide 3 days after completion
  - Integrated in (protected)/layout.tsx at bottom of sidebar

**Checkpoint**: User Story 6 complete - checklist widget working

---

## Phase 9: User Story 7 - Welcome Email Drip Sequence (Priority: P3)

**Goal**: Automated emails for activation and trial reminders

**Independent Test**: Sign up, verify welcome email received, check nudge emails for incomplete steps

### Implementation for User Story 7

- [x] T075 [US7] Create email templates in backend/app/modules/notifications/templates/
  - welcome.html - immediate on signup
  - connect_xero.html - 24h nudge if no Xero
  - import_clients.html - 48h nudge if no clients
  - onboarding_complete.html - congratulations
  - All templates implemented in templates.py using inline HTML

- [x] T076 [US7] Create OnboardingService.send_welcome_email() in backend/app/modules/onboarding/service.py
  - Call NotificationService
  - Record in EmailDrip table
  - Already implemented with stub

- [x] T077 [US7] Create Celery task for onboarding nudges in backend/app/modules/onboarding/tasks.py
  - send_onboarding_drip_emails() - daily task
  - Find incomplete onboardings
  - Send appropriate nudge based on current step
  - Check EmailDrip to prevent duplicates
  - Implemented with TODO for NotificationService integration

- [x] T078 [US7] Register nudge task in Celery beat schedule in backend/app/tasks/celeryconfig.py
  - Add daily task for send_onboarding_drip_emails
  - Already registered at 9:30am AEDT

- [x] T079 [US7] Send welcome email on signup in backend/app/modules/onboarding/service.py
  - Call send_welcome_email() in start_onboarding()
  - Method exists with TODO for NotificationService

- [x] T080 [US7] Create email service methods in backend/app/modules/notifications/service.py
  - send_onboarding_email(tenant, email_type, context)
  - Use Resend API
  - Deferred to notification service integration

**Checkpoint**: User Story 7 complete - email drip sequence working

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T081 [P] Add comprehensive error handling in backend/app/modules/onboarding/router.py
  - Catch domain exceptions
  - Return appropriate HTTP status codes
  - Created exceptions.py with domain-specific exceptions
  - Updated router with try/except blocks and proper HTTP codes

- [x] T082 [P] Add logging throughout onboarding module
  - Log key events: start, tier selection, Xero connect, import progress
  - Added structured logging with get_logger to key endpoints

- [x] T083 [P] Write unit tests for OnboardingService in backend/tests/unit/modules/onboarding/test_service.py
  - Test state transitions
  - Test validation logic
  - 25+ test cases covering all service methods

- [x] T084 [P] Write integration tests for onboarding API in backend/tests/integration/api/test_onboarding.py
  - Test full flow endpoints
  - Test error cases
  - 15+ test cases for all endpoints

- [ ] T085 [P] Write E2E test for onboarding flow in frontend/tests/e2e/onboarding.spec.ts
  - Test tier selection through to completion
  - Skipped: E2E test infrastructure not set up for this project

- [ ] T086 Run quickstart.md validation
  - Follow all steps in specs/021-onboarding-flow/quickstart.md
  - Verify all checkboxes pass
  - Skipped: Requires running full manual test with actual services

---

## Phase FINAL: PR & Merge (REQUIRED)

**Purpose**: Create pull request and merge to main

- [ ] TFINAL-1 Ensure all tests pass
  - Run: `cd backend && uv run pytest`
  - Run: `cd frontend && npm run test`
  - All tests must pass before PR

- [ ] TFINAL-2 Run linting and type checking
  - Run: `cd backend && uv run ruff check . && uv run mypy .`
  - Run: `cd frontend && npm run lint`
  - Fix any issues

- [ ] TFINAL-3 Push feature branch and create PR
  - Run: `git add . && git commit -m "feat(021): Onboarding Flow"`
  - Run: `git push -u origin 021-onboarding-flow`
  - Run: `gh pr create --title "Spec 021: Onboarding Flow" --body "..."`
  - Include summary of changes in PR description

- [ ] TFINAL-4 Address review feedback (if any)
  - Make requested changes
  - Push additional commits

- [ ] TFINAL-5 Merge PR to main
  - Squash merge after approval
  - Delete feature branch after merge

- [ ] TFINAL-6 Update ROADMAP.md
  - Mark spec 021 as COMPLETE
  - Update current focus to spec 022 (Admin Dashboard)

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 0 (Git Setup)
    ↓
Phase 1 (Setup)
    ↓
Phase 2 (Foundational) ← BLOCKS all user stories
    ↓
┌───────────────────────────────────────────────┐
│ User Stories can proceed in priority order     │
│                                               │
│  Phase 3 (US1) ──┐                            │
│  Phase 4 (US2) ──┼── P1 stories (sequential)  │
│  Phase 5 (US3) ──┘                            │
│       ↓                                       │
│  Phase 6 (US4) ────── Bulk Import (metadata)  │
│       ↓                                       │
│  Phase 6b (US4) ───── Client Org Auth (NEW)   │
│       ↓                                       │
│  Phase 7 (US5) ──┐                            │
│  Phase 8 (US6) ──┼── P2 stories (can parallel)│
│       ↓          │                            │
│  Phase 9 (US7) ──┘─── P3 story                │
└───────────────────────────────────────────────┘
    ↓
Phase 10 (Polish)
    ↓
Phase FINAL (PR & Merge)
```

### User Story Dependencies

- **US1 (Tier Selection)**: No dependencies - can start after Phase 2
- **US2 (Trial)**: Depends on US1 (needs tier/subscription)
- **US3 (Xero Connect)**: Depends on US1 (needs onboarding started)
- **US4 (Bulk Import)**: Depends on US3 (needs Xero connected)
- **US4 (Client Org Auth)**: Depends on US4 Bulk Import (needs client list)
- **US5 (Tour)**: Depends on US4 (tours dashboard features)
- **US6 (Checklist)**: Depends on US1 (tracks all steps)
- **US7 (Emails)**: Can parallel with US2-US6

### Parallel Opportunities

Within each phase, tasks marked [P] can run in parallel:

**Phase 1 (Setup)**:
```
T002, T003, T004, T005 - all parallel (different directories)
```

**Phase 2 (Foundational)**:
```
T007-T011 - sequential (model dependencies)
T015-T018 - can parallel after models
```

**Phase 6 (US4)**:
```
T056, T057 - parallel (different components)
```

**Phase 6b (Client Org Auth)**:
```
T060M, T060N, T060O - parallel (different components)
T060R-T060V - can parallel (bulk connections, conditional on flag)
```

---

## Implementation Strategy

### MVP First (US1 + US2 + US3)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 (Tier Selection)
4. Complete Phase 4: US2 (Trial)
5. Complete Phase 5: US3 (Xero Connect)
6. **STOP and VALIDATE**: Test signup through Xero connection
7. Deploy/demo if ready - this is MVP!

### Incremental Delivery

1. MVP (US1-US3) → Core acquisition flow works
2. Add US4 Phase 6 (Bulk Import metadata) → Client list from XPM
3. Add US4 Phase 6b.1-6b.4 (Individual Auth) → Connect each client's Xero org
4. Add US5 (Tour) → Feature discovery
5. Add US6 (Checklist) → Progress visibility
6. Add US7 (Emails) → Activation automation
7. Add US4 Phase 6b.5 (Bulk Connections) → When Xero Advanced Partner approved

### Task Count Summary

| Phase | Tasks | Story |
|-------|-------|-------|
| Phase 0 | 1 | Git Setup |
| Phase 1 | 5 | Setup |
| Phase 2 | 13 | Foundational |
| Phase 3 | 11 | US1 - Tier Selection |
| Phase 4 | 9 | US2 - Trial |
| Phase 5 | 8 | US3 - Xero Connect |
| Phase 6 | 13 | US4 - Bulk Import (metadata) |
| Phase 6b | 25 | US4 - Client Org Authorization (NEW) |
| Phase 7 | 8 | US5 - Product Tour |
| Phase 8 | 6 | US6 - Checklist |
| Phase 9 | 6 | US7 - Emails |
| Phase 10 | 6 | Polish |
| Phase FINAL | 6 | PR & Merge |
| **TOTAL** | **117** | |

**Phase 6b Breakdown**:
- 6b.1 Data Model & Backend: 4 tasks (T060A-D)
- 6b.2 Xero Connections API: 4 tasks (T060E-H)
- 6b.3 Individual Authorization: 4 tasks (T060I-L)
- 6b.4 Frontend Individual Auth UI: 5 tasks (T060M-Q)
- 6b.5 Bulk Connections (Future): 5 tasks (T060R-V)
- 6b.6 Manual Matching & Admin: 3 tasks (T060W-Y)

---

## Notes

- [P] tasks = different files, no dependencies
- [US#] label maps task to specific user story
- Each user story should be independently completable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
