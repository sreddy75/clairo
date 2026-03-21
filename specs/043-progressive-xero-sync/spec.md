# Feature Specification: Progressive Xero Data Sync

**Feature Branch**: `043-progressive-xero-sync`
**Created**: 2026-02-14
**Status**: Draft
**Input**: User description: "Progressive Xero Data Sync - Optimize the Xero data synchronization process for multi-client accounting practices."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Non-Blocking Background Sync (Priority: P1)

As an accountant, when I trigger a data sync for a client, I want the sync to run in the background so I can continue using the platform without waiting for it to complete.

**Why this priority**: This is the single biggest UX improvement. Currently the sync dialog blocks the user for minutes. Moving sync to a truly non-blocking background process removes the most painful friction point and allows accountants to stay productive.

**Independent Test**: Can be tested by triggering a sync, navigating to other pages, and confirming work continues uninterrupted. Delivers immediate value by eliminating wait time.

**Acceptance Scenarios**:

1. **Given** an accountant triggers a full sync for a client, **When** the sync starts, **Then** a brief confirmation toast appears ("Syncing data for Client X...") and the user is NOT blocked from navigating or working.
2. **Given** a sync is running in the background, **When** it completes, **Then** the user receives a non-intrusive notification (bell icon badge + toast) with a summary: "Client X sync complete — 2,517 records synced."
3. **Given** a sync fails due to a transient error (e.g., Xero rate limit), **When** the failure occurs, **Then** the system automatically retries up to 3 times before notifying the user of the failure with a clear error message and a "Retry" action.
4. **Given** a sync is running, **When** the user wants to check progress, **Then** they can view real-time progress from the notifications panel or the client's integration settings page.

---

### User Story 2 - Phased Initial Sync (Priority: P1)

As an accountant who just connected a new client's Xero account, I want to see essential client data (contacts, accounts, recent invoices) within seconds so I can start working immediately, while historical data loads in the background.

**Why this priority**: Equal to P1 because first impressions matter. When onboarding a new client, waiting minutes before seeing ANY data creates a poor experience. Phased sync delivers immediate usability by front-loading the most important data.

**Independent Test**: Can be tested by connecting a new Xero organisation and measuring time-to-first-data for essential entities vs. historical data. Delivers value by making the platform feel responsive from the first connection.

**Acceptance Scenarios**:

1. **Given** a new Xero organisation is connected, **When** the initial sync begins, **Then** essential data (Chart of Accounts, Contacts, and Invoices from the last 12 months) syncs first and becomes available within 30 seconds.
2. **Given** essential data has synced, **When** the user views the client dashboard, **Then** client cards, recent invoices, and account details are visible, with a subtle indicator showing "Syncing historical data..." for sections still loading.
3. **Given** historical data is still syncing, **When** the user navigates to a section that requires historical data (e.g., multi-year trend analysis), **Then** the system shows available data with a message: "Loading historical data — this section will update automatically when complete."
4. **Given** a phased sync is in progress, **When** Phase 1 (essential data) completes, **Then** the system immediately begins Phase 2 (recent history: bank transactions, payments, credit notes from last 12 months) without user intervention.
5. **Given** Phase 2 completes, **When** the system begins Phase 3 (full history), **Then** it syncs all remaining entity types and historical records older than 12 months.

---

### User Story 3 - Multi-Client Parallel Sync (Priority: P2)

As an accountant managing a practice with 100+ clients, I want to sync all my clients' data simultaneously so the entire practice is up-to-date without manually syncing each client one at a time.

**Why this priority**: Critical for practices with many clients, but depends on the background sync foundation (P1). Parallel sync with rate management is what makes the platform viable for real accounting practices.

**Independent Test**: Can be tested by triggering a "Sync All" action and observing multiple clients syncing concurrently with rate limit compliance. Delivers value by automating what would otherwise be hours of manual sync triggers.

**Acceptance Scenarios**:

1. **Given** an accountant has 50 connected clients, **When** they click "Sync All Clients," **Then** the system queues all clients and processes them in parallel (up to a configurable concurrency limit) while respecting Xero API rate limits.
2. **Given** multi-client sync is running, **When** the user views the dashboard, **Then** they see an aggregate progress indicator: "Syncing 12/50 clients..." with the ability to expand and see per-client status.
3. **Given** the Xero API rate limit is approached during multi-client sync, **When** the system detects fewer than 10 remaining API calls in the current minute, **Then** it pauses new requests and resumes automatically when the rate limit window resets, without failing any jobs.
4. **Given** one client's sync fails during a multi-client sync, **When** the failure occurs, **Then** other clients continue syncing unaffected, and the failed client is flagged with an error and "Retry" option.

---

### User Story 4 - Incremental Sync (Priority: P2)

As an accountant, I want subsequent syncs after the initial full sync to be fast (seconds, not minutes) by only fetching records that changed since the last sync.

**Why this priority**: Incremental sync dramatically reduces ongoing sync times and API usage. It makes the daily sync and manual re-syncs feel instant. Depends on P1 infrastructure.

**Independent Test**: Can be tested by performing a full sync, making a change in Xero, then re-syncing and measuring that only changed records are fetched. Delivers value by making routine syncs near-instant.

**Acceptance Scenarios**:

1. **Given** a client has been fully synced previously, **When** the user triggers a sync, **Then** the system uses the last sync timestamp to fetch only records modified since then, completing in under 10 seconds for typical change volumes.
2. **Given** an incremental sync runs, **When** it completes, **Then** the notification shows "Updated 15 records" (not "Synced 2,517 records"), making it clear that only changes were processed.
3. **Given** an incremental sync is triggered, **When** the system detects data integrity concerns (e.g., missing expected records), **Then** it automatically escalates to a full sync for that entity type and logs the reason.
4. **Given** all entity types that support Xero's modified-since filtering, **When** an incremental sync runs, **Then** the modified-since header is sent for ALL supported entities (not just contacts, invoices, and bank transactions as currently implemented).

---

### User Story 5 - Real-Time Sync Progress (Priority: P3)

As an accountant watching a long-running sync, I want to see accurate, real-time progress updates (entity-by-entity, record counts) without having to refresh the page.

**Why this priority**: Enhances confidence and transparency during syncs but is not blocking. The current polling approach works but could be improved for a more responsive feel.

**Independent Test**: Can be tested by triggering a sync and observing that progress updates appear in real-time (sub-second latency) without page refreshes. Delivers value by building user confidence during long operations.

**Acceptance Scenarios**:

1. **Given** a sync is running, **When** an entity type completes syncing, **Then** the progress indicator updates within 1 second to show the completed entity and record counts.
2. **Given** a sync is running, **When** the user is on any page in the application, **Then** a persistent but non-intrusive indicator (e.g., sidebar badge, header icon) shows that a sync is active.
3. **Given** a sync completes, **When** the user is on the client's page, **Then** the data refreshes automatically without a manual page reload.

---

### User Story 6 - Xero Webhook-Driven Updates (Priority: P3)

As a practice using Clairo throughout the day, I want client data to stay current automatically when changes happen in Xero, without needing to manually trigger syncs.

**Why this priority**: This is the "icing on the cake" — true real-time data freshness. It reduces reliance on manual and scheduled syncs but requires Xero webhook infrastructure. Lower priority because scheduled + incremental syncs already provide good-enough freshness for most workflows.

**Independent Test**: Can be tested by making a change in Xero (e.g., creating an invoice) and verifying it appears in Clairo within minutes without any manual action. Delivers value by keeping data perpetually fresh.

**Acceptance Scenarios**:

1. **Given** the practice has configured Xero webhooks, **When** an invoice is created or updated in Xero, **Then** the system receives the webhook event and syncs the affected record within 2 minutes.
2. **Given** a webhook event is received, **When** it references an entity type that supports incremental sync, **Then** only the specific affected record is fetched (not a full entity sync).
3. **Given** webhook delivery fails (Xero retries), **When** a duplicate event is received, **Then** the system handles it idempotently without creating duplicate records.
4. **Given** a high volume of webhook events arrives simultaneously, **When** the system processes them, **Then** it batches related events (e.g., multiple invoice updates for the same client) into a single sync operation to avoid redundant API calls.

---

### User Story 7 - Post-Sync Data Preparation (Priority: P2)

As an accountant, after a client's data syncs, I want the platform to automatically prepare that data for use — calculating quality scores, BAS figures, AI insights, and trigger alerts — so I can immediately act on the results without any manual steps.

**Why this priority**: Synced data is only useful once it's been processed. Quality scores, BAS calculations, and AI insights are the core value of Clairo. Without post-sync preparation, the sync is just raw data. This must run automatically and progressively to complete the "sync-to-value" pipeline.

**Independent Test**: Can be tested by syncing a client and verifying that quality scores, BAS periods, and insights are generated automatically post-sync. Delivers value by making synced data actionable.

**Acceptance Scenarios**:

1. **Given** Phase 1 (essential data) of a sync completes, **When** the post-sync pipeline runs, **Then** a preliminary data quality score is calculated and displayed on the client card within 15 seconds.
2. **Given** the full sync completes (all phases), **When** the post-sync pipeline runs, **Then** the system calculates BAS period figures for the last 6 quarters, generates AI-powered insights, computes aggregations for the AI context, and evaluates threshold triggers.
3. **Given** post-sync preparation tasks are running, **When** the user accesses the client's dashboard, **Then** already-available data (from earlier phases) is accessible and a subtle indicator shows "Preparing insights..." for sections still processing.
4. **Given** post-sync preparation completes for a client, **When** new insights or alerts are generated, **Then** the user receives a notification summarising the results (e.g., "Client X: Quality score 87%, 3 new insights, 1 alert").
5. **Given** a post-sync task fails (e.g., insight generation errors), **When** the failure occurs, **Then** it does not prevent other post-sync tasks from completing, and the failed task is retried independently.

---

### Edge Cases

- What happens when a Xero connection's OAuth token expires mid-sync? The system should auto-refresh the token and resume without restarting the entire sync.
- What happens when Xero returns a 503 (service unavailable) during sync? The system should retry with exponential backoff and mark the entity as "partially synced" if retries are exhausted.
- What happens when the user disconnects a Xero organisation while a sync is in progress? The system should gracefully cancel the running sync and clean up the job status.
- What happens when two users trigger a sync for the same client simultaneously? The system should prevent duplicate syncs (already implemented — raise error for in-progress sync).
- What happens when the database is temporarily unavailable during a sync? The background task should retry with backoff, preserving progress already committed.
- What happens when a client has zero transactions (brand new Xero org)? Phase 1 should complete almost instantly and the user should see an appropriate empty state.
- What happens when Xero's rate limit headers are missing from a response? The system should fall back to conservative defaults (assume 50% of limits consumed).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST run all data syncs as background tasks that do not block the user interface.
- **FR-002**: System MUST divide initial syncs into at least two phases: essential data (Accounts, Contacts, recent Invoices) first, then everything else.
- **FR-003**: System MUST deliver essential data (Phase 1) for a newly connected client within 30 seconds of sync initiation.
- **FR-004**: System MUST support parallel syncing of multiple clients concurrently, with a configurable concurrency limit.
- **FR-005**: System MUST respect Xero API rate limits (60 calls/minute, 5000 calls/day) across all concurrent sync operations, with safety margins.
- **FR-006**: System MUST use Xero's `If-Modified-Since` header for ALL entity types that support it during incremental syncs (expanding beyond the current 3 entity types to all supported types).
- **FR-007**: System MUST track per-entity sync timestamps to enable granular incremental syncs (not just per-connection).
- **FR-008**: System MUST provide real-time progress updates to the frontend during active syncs, with per-entity status and record counts.
- **FR-009**: System MUST notify users when syncs complete or fail via the in-app notification system (bell icon + toast).
- **FR-010**: System MUST support a "Sync All Clients" action that queues and processes all connected clients.
- **FR-011**: System MUST handle sync failures gracefully — individual client failures must not affect other clients in a multi-client sync.
- **FR-012**: System MUST automatically retry failed syncs up to 3 times with exponential backoff before marking as failed.
- **FR-013**: System MUST show aggregate sync progress for multi-client operations (e.g., "12/50 clients synced").
- **FR-014**: System MUST show data freshness indicators on client pages — when data was last synced and whether it may be stale.
- **FR-015**: System MUST support Xero webhook events to trigger targeted, single-record syncs for supported entity types.
- **FR-016**: System MUST handle webhook events idempotently — processing the same event multiple times must not create duplicates.
- **FR-017**: System MUST batch webhook events for the same client within a short window to avoid redundant API calls.
- **FR-018**: System MUST allow users to cancel a running sync from the UI.
- **FR-019**: System MUST preserve sync progress if a sync is interrupted — resuming should not re-sync already-completed entity types.
- **FR-020**: System MUST auto-refresh expired Xero OAuth tokens during sync without restarting the sync.
- **FR-021**: System MUST trigger post-sync data preparation tasks after each sync phase completes, including: data quality scoring, BAS period calculation, AI context aggregation, proactive insight generation, and threshold trigger evaluation.
- **FR-022**: System MUST run post-sync preparation tasks progressively — basic quality scores and BAS readiness after Phase 1 (essential data), full insights and trigger evaluation after the complete sync finishes.
- **FR-023**: System MUST NOT block user access to already-synced data while post-sync preparation tasks are running.
- **FR-024**: System MUST notify the user when post-sync preparation completes (e.g., "Client X is ready — quality score: 87%, 3 new insights generated").

### Key Entities

- **Sync Job**: Represents a single sync operation for one client connection. Tracks status (pending, in_progress, completed, failed, cancelled), phase (1/2/3), per-entity progress, record counts, and timing. One-to-many with Sync Entity Progress.
- **Sync Entity Progress**: Tracks sync status for each individual entity type within a job. Records entity name, status, records processed/created/updated/failed, last modified-since timestamp used, and duration.
- **Sync Queue**: Manages the ordering and priority of pending sync jobs across all clients. Supports priority levels (user-triggered > scheduled > webhook-triggered), concurrency control, and rate limit awareness.
- **Webhook Event**: Records incoming Xero webhook events. Tracks event type, affected entity, tenant/connection reference, processing status, and deduplication key.
- **Sync Schedule**: Defines per-client sync preferences — frequency, preferred time window, entity types to include/exclude. Enables practices to customise sync behaviour per client.
- **Post-Sync Pipeline**: Orchestrates downstream data preparation tasks after sync completion. Tracks which preparation steps have run (quality scoring, BAS calculation, AI aggregation, insight generation, trigger evaluation), their status, and results. Runs progressively — partial preparation after Phase 1, full preparation after complete sync.

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [ ] **Authentication Events**: Does this feature involve user authentication or authorization changes?
- [x] **Data Access Events**: Does this feature read sensitive data (TFN, bank details, BAS figures)?
- [x] **Data Modification Events**: Does this feature create, update, or delete business-critical data?
- [x] **Integration Events**: Does this feature sync with external systems (Xero, MYOB, ATO)?
- [ ] **Compliance Events**: Does this feature affect BAS lodgements or compliance status?

### Audit Implementation Requirements

| Event Type                        | Trigger                          | Data Captured                                                       | Retention | Sensitive Data         |
| --------------------------------- | -------------------------------- | ------------------------------------------------------------------- | --------- | ---------------------- |
| integration.xero.sync.started     | Sync job begins                  | Job ID, connection ID, sync type, phase, triggered by (user/system) | 7 years   | None                   |
| integration.xero.sync.completed   | Sync job completes               | Job ID, records processed/created/updated/failed, duration, phases  | 7 years   | None                   |
| integration.xero.sync.failed      | Sync job fails after all retries | Job ID, error message, entity that failed, retry count              | 7 years   | None                   |
| integration.xero.webhook.received | Xero webhook event received      | Event type, affected entity, connection ID, event key               | 7 years   | None                   |
| integration.xero.data.modified    | Client financial data changed    | Entity type, record count, connection ID, modification type         | 7 years   | Mask financial amounts |

### Compliance Considerations

- **ATO Requirements**: All data sync operations must be auditable to demonstrate data provenance — when financial data was sourced from Xero, what changed, and who triggered the sync.
- **Data Retention**: Sync job records and audit events retained for 7 years per standard ATO compliance requirements.
- **Access Logging**: Practice administrators and accountants with integration management permissions can view sync logs. Tenant-level Row-Level Security ensures data isolation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can continue working in the platform immediately after triggering a sync — zero UI blocking time (down from 2-5 minutes currently).
- **SC-002**: Essential client data (contacts, accounts, recent invoices) is visible within 30 seconds of connecting a new Xero organisation.
- **SC-003**: Incremental syncs for a typical client (with fewer than 100 changed records) complete in under 10 seconds.
- **SC-004**: A practice with 100 connected clients can sync all clients within 30 minutes using parallel background processing.
- **SC-005**: The system stays within Xero's API rate limits (60/min, 5000/day) at all times, with zero rate-limit-induced failures visible to users.
- **SC-006**: 95% of sync notifications are delivered to users within 2 seconds of sync completion.
- **SC-007**: Webhook-triggered updates appear in the platform within 2 minutes of the change occurring in Xero.
- **SC-008**: Failed syncs are automatically retried, with 90% of transient failures resolved without user intervention.

## Assumptions

- Xero's API continues to support the `If-Modified-Since` header for the entity types currently documented.
- Xero's webhook delivery is reliable enough for near-real-time updates (with scheduled syncs as a safety net).
- The existing Celery + Redis infrastructure can handle the increased task volume from parallel multi-client syncing.
- Practices typically have 25-250 connected clients (per subscription tiers), which bounds the maximum concurrency requirements.
- The existing sync job model can be extended (rather than replaced) to support phased sync tracking.

## Dependencies

- Existing Xero integration module (authentication, API client, data transformers, repositories).
- Existing Celery + Redis task queue infrastructure.
- Existing in-app notification system (bell icon, toast notifications).
- Xero Developer Portal webhook configuration (requires app-level setup).
