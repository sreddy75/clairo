# Feature Specification: Bulk Client Import via Multi-Org Xero OAuth

**Feature Branch**: `035-bulk-client-import`
**Created**: 2026-02-08
**Status**: Draft
**Input**: User description: "Bulk Client Import via Multi-Org Xero OAuth"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bulk Connect Xero Client Organizations (Priority: P1)

As an accountant at a practice managing 50+ clients, I want to connect all my clients' Xero organizations in a single OAuth flow so that I don't have to repeat the authorization process individually for each client.

Currently, I must go through the full Xero OAuth login, select one organization, wait for it to connect, then repeat for every single client. With 100+ clients, this takes hours and is impractical. I want to click "Import Clients from Xero" once, authorize access to all my client organizations in Xero's consent screen, and have them all appear in Clairo ready for sync.

**Why this priority**: This is the core problem being solved. Without multi-org OAuth support, the entire feature has no value. A practice cannot realistically onboard at scale with the current one-at-a-time approach.

**Independent Test**: Can be fully tested by an accountant clicking "Import Clients from Xero", completing a single Xero login, selecting multiple organizations, and seeing all selected organizations appear as new connections in Clairo.

**Acceptance Scenarios**:

1. **Given** an accountant with access to 15 Xero client organizations, **When** they click "Import Clients from Xero" and complete the Xero OAuth login selecting all 15 orgs, **Then** the system creates connection records for all 15 organizations and displays them in a confirmation screen.

2. **Given** an accountant who already has 5 clients connected in Clairo, **When** they complete a bulk import flow that includes those 5 plus 10 new orgs, **Then** the system identifies the 5 existing connections (skips creating duplicates) and creates only the 10 new ones, clearly labeling which are new and which were already connected.

3. **Given** an accountant on the Starter plan (25 client limit) who already has 20 clients, **When** they attempt to bulk import 10 new organizations, **Then** the system warns that only 5 can be added within their plan limit and allows them to select which 5 to import.

4. **Given** an accountant completing the OAuth flow, **When** Xero returns the list of authorized organizations, **Then** the system groups connections by the authorization event and only presents newly authorized organizations for configuration (not previously connected ones).

---

### User Story 2 - Configure Imported Clients Before Sync (Priority: P2)

As an accountant who has just authorized multiple Xero organizations, I want to review and configure each imported client before syncing begins so that I can assign team members, set the correct connection type, and exclude any organizations I don't want to manage in Clairo.

After the OAuth flow returns multiple organizations, I need a configuration screen where I can see all newly authorized orgs, select/deselect which ones to import, assign a team member to each, and mark whether each is a "client" or my "practice" organization.

**Why this priority**: Configuration before sync prevents wasted resources (syncing orgs the accountant doesn't want) and ensures proper assignment of team members from the start, avoiding cleanup work later.

**Independent Test**: Can be tested by completing a bulk OAuth flow and verifying the configuration screen appears with all authorized organizations, allows selection/deselection, team member assignment, and connection type tagging before triggering sync.

**Acceptance Scenarios**:

1. **Given** an accountant who just authorized 20 Xero organizations, **When** the configuration screen loads, **Then** all 20 organizations are listed with their names, each with a checkbox (default: selected), a team member dropdown, and a connection type selector (practice/client, default: client).

2. **Given** the configuration screen showing 20 organizations, **When** the accountant deselects 3 organizations and clicks "Import Selected", **Then** only the 17 selected organizations proceed to connection creation and sync, and the 3 deselected orgs are not connected.

3. **Given** the configuration screen, **When** the accountant assigns "Jane Smith" as the team member for 10 clients and "Mark Lee" for the remaining 7, **Then** each created connection records the assigned team member for future reference.

4. **Given** the configuration screen showing organizations that are already connected, **When** the accountant views the list, **Then** already-connected organizations are visually distinguished (greyed out or labeled "Already Connected") and cannot be re-imported.

---

### User Story 3 - Monitor Bulk Sync Progress (Priority: P3)

As an accountant who has initiated a bulk import of 50 client organizations, I want to see real-time progress of the initial data sync for each organization so that I know which clients are ready to work with and which are still loading.

After clicking "Import Selected" on the configuration screen, syncing begins in the background. I need a progress dashboard that shows overall completion (e.g., "23 of 50 synced"), per-organization status (pending, syncing, completed, failed), and any errors so I can take action on failures.

**Why this priority**: Without progress visibility, accountants have no idea when their clients are ready. For large imports, the sync can take 30+ minutes. A progress dashboard builds confidence and allows the accountant to start working with completed clients while others are still syncing.

**Independent Test**: Can be tested by initiating a bulk import of multiple organizations and verifying the progress dashboard displays real-time status updates, shows per-org completion states, and surfaces error details for any failed syncs.

**Acceptance Scenarios**:

1. **Given** a bulk import of 30 organizations has been initiated, **When** the accountant views the bulk import progress screen, **Then** they see an overall progress bar ("12 of 30 complete"), a list of each organization with its current status (pending/syncing/completed/failed), and an estimated time remaining.

2. **Given** 3 organizations fail to sync due to rate limiting or token errors, **When** the accountant views the progress screen, **Then** failed organizations show an error summary and a "Retry" button to re-attempt the sync.

3. **Given** all organizations have completed syncing, **When** the accountant views the progress screen, **Then** they see a completion summary with counts (e.g., "28 successful, 2 failed") and a link to navigate to the Clients list.

4. **Given** a bulk sync is in progress, **When** the accountant navigates away from the progress screen and returns later, **Then** the progress screen still reflects the current real-time status of all syncs.

---

### User Story 4 - Auto-Match Imported Orgs to Existing Practice Clients (Priority: P4)

As an accountant who has already set up client records in Clairo (via Xero Practice Manager or manual entry), I want newly imported Xero organizations to automatically match to my existing client records so that I don't have to manually link each one.

When bulk importing organizations, if the practice already has client records (from XPM or manual creation), the system should attempt to match each imported Xero organization to an existing client by name. Matched clients are automatically linked; unmatched ones are presented for manual linking or creation as new clients.

**Why this priority**: Auto-matching reduces manual effort for practices that have already set up their client list. However, it's an optimization — the feature is fully usable without it (orgs can always be manually linked later).

**Independent Test**: Can be tested by having existing client records with known names, bulk importing Xero organizations with matching names, and verifying the system automatically links matching pairs and presents unmatched items for review.

**Acceptance Scenarios**:

1. **Given** 5 existing client records with names matching 5 of the 20 newly imported Xero organizations (exact name match), **When** the bulk import completes, **Then** those 5 organizations are automatically linked to their matching client records with a "Matched" label.

2. **Given** 3 imported organizations with no name match to existing clients, **When** the auto-matching runs, **Then** those 3 are listed as "Unmatched" with options to either link to an existing client manually or create a new client record.

3. **Given** an imported organization named "KR8 IT Pty Ltd" and an existing client named "KR8 IT", **When** auto-matching runs, **Then** the system suggests this as a potential match (fuzzy matching) and presents it for the accountant to confirm or reject.

---

### Edge Cases

- What happens when the accountant's Xero login has access to 0 organizations? The system displays a helpful message explaining that no organizations were found and suggests checking Xero permissions.
- What happens when the Xero OAuth flow is cancelled by the user mid-way? The system handles the cancelled/denied callback gracefully and returns the user to the import screen with no partial state.
- What happens when the same accountant initiates two bulk import flows simultaneously? The system prevents concurrent bulk import jobs for the same tenant, showing a message that an import is already in progress.
- What happens when a Xero token expires during a long-running bulk sync? The system automatically refreshes the token (existing behavior) and retries the failed request. If refresh fails, the individual org sync is marked as failed with a "re-authentication required" message.
- What happens when the practice's subscription tier limit is reached mid-import? The system stops importing new connections once the limit is reached, marks remaining orgs as "skipped (plan limit reached)", and suggests upgrading.
- What happens when an organization is disconnected from Xero after being imported but before sync completes? The system marks the connection as "disconnected" and shows the status in the progress dashboard.
- What happens when two organizations have the same name? The system creates separate connections for each (identified by unique Xero tenant ID) and labels them clearly so the accountant can distinguish them.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST process all authorized organizations returned from a Xero OAuth flow, not just the first one.
- **FR-002**: System MUST identify which organizations are newly authorized in the current flow versus previously connected, using the authorization event identifier.
- **FR-003**: System MUST share the same encrypted access and refresh tokens across all connections created from a single OAuth flow (Xero uses one token set per user session, not per org).
- **FR-004**: System MUST present a post-authorization configuration screen listing all newly authorized organizations with selection controls, team member assignment, and connection type options.
- **FR-005**: System MUST allow the accountant to select which organizations to import (default: all selected) and skip the rest.
- **FR-006**: System MUST enforce the tenant's subscription tier client limit during bulk import, preventing imports that would exceed the limit.
- **FR-007**: System MUST display a warning when the accountant's organization count exceeds the uncertified app limit (25 orgs), explaining that a maximum of 25 can be connected simultaneously.
- **FR-008**: System MUST queue initial data sync for each imported organization as a background job, staggered to respect rate limits.
- **FR-009**: System MUST limit concurrent organization syncs to a maximum of 10 at a time to stay within global rate limits.
- **FR-010**: System MUST provide a bulk import progress dashboard showing overall completion, per-organization status (pending, syncing, completed, failed), and error details.
- **FR-011**: System MUST allow the accountant to retry failed syncs from the progress dashboard.
- **FR-012**: System MUST prevent duplicate connections — if an organization is already connected for the tenant, it should be identified and skipped during import.
- **FR-013**: System MUST maintain backward compatibility with the existing single-organization connection flow (the current "Connect Xero" for individual clients continues to work unchanged).
- **FR-014**: System MUST attempt to auto-match imported organizations to existing client records by name (exact match first, then fuzzy matching).
- **FR-015**: System MUST present unmatched organizations for manual linking or new client record creation.
- **FR-016**: System MUST track bulk import jobs with metadata including: initiating user, timestamp, total organizations, import counts (success/failed/skipped), and per-organization results.
- **FR-017**: System MUST prevent concurrent bulk import jobs for the same tenant.
- **FR-018**: System MUST provide a "Import Clients from Xero" entry point accessible from the Clients page.

### Key Entities

- **Bulk Import Job**: Tracks a single bulk import operation. Key attributes: initiating user, creation time, status (in_progress, completed, failed, cancelled), total organization count, imported count, failed count, skipped count, per-organization results with individual statuses and error messages.
- **Xero Connection**: Represents an authorized link between the tenant and a Xero organization. Shares tokens with other connections from the same OAuth flow (identified by authorization event ID). Key attributes: organization name, Xero tenant ID, connection type (practice/client), assigned team member, sync status, authorization event ID.
- **Import Organization Entry**: An individual organization within a bulk import job. Key attributes: Xero tenant ID, organization name, import status (pending, importing, completed, failed, skipped), error message if failed, linked client record if auto-matched.

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [x] **Authentication Events**: This feature involves OAuth authorization with Xero, granting access to multiple client financial data sets.
- [x] **Data Access Events**: Bulk import triggers sync of client financial data (invoices, transactions, bank accounts).
- [x] **Data Modification Events**: Creates multiple Xero connection records and potentially new client records.
- [x] **Integration Events**: Syncs financial data from multiple Xero organizations simultaneously.
- [ ] **Compliance Events**: Does not directly affect BAS lodgements (sync populates data used later for BAS).

### Audit Implementation Requirements

| Event Type                          | Trigger                                          | Data Captured                                                                 | Retention | Sensitive Data                      |
| ----------------------------------- | ------------------------------------------------ | ----------------------------------------------------------------------------- | --------- | ----------------------------------- |
| integration.xero.bulk_import.start  | Accountant initiates bulk import                 | User ID, tenant ID, total org count, selected org names                       | 7 years   | None                                |
| integration.xero.oauth.multi_org    | OAuth callback processes multiple organizations  | User ID, tenant ID, auth event ID, org count, org names                       | 7 years   | Access tokens masked                |
| integration.xero.connection.created | New Xero connection created during bulk import   | Connection ID, tenant ID, org name, Xero tenant ID, connection type           | 7 years   | None                                |
| integration.xero.bulk_import.complete | Bulk import job finishes                       | Job ID, total/imported/failed/skipped counts, duration, per-org result summary | 7 years   | None                                |
| integration.xero.bulk_sync.start   | Background sync initiated for an imported org    | Connection ID, org name, sync type                                            | 7 years   | None                                |
| integration.xero.bulk_sync.fail    | Sync fails for an individual organization        | Connection ID, org name, error type, error message                            | 7 years   | API error details may be truncated  |

### Compliance Considerations

- **ATO Requirements**: Bulk import itself does not affect BAS compliance directly, but the audit trail must record which client data sets were imported, when, and by whom, to maintain a complete chain of custody for financial data used in BAS preparation.
- **Data Retention**: Standard 7-year retention for all audit events related to financial data access and import operations.
- **Access Logging**: Practice administrators and the accountant who initiated the import should be able to view bulk import audit logs. Individual connection audit events follow existing per-client access controls.

## Assumptions

- Xero's OAuth consent screen allows users to select multiple organizations in a single flow (confirmed by Xero API documentation — this is standard behavior for all apps).
- Uncertified apps are limited to 25 concurrent organization connections. This limit will be documented to users; certification and Bulk Connections feature are future enhancements.
- A single access/refresh token pair works for all organizations authorized in one OAuth flow. API calls target specific orgs via the Xero-Tenant-Id header.
- The existing rate limiter handles per-org limits (60/min, 5000/day). The bulk sync orchestrator needs to additionally enforce the app-wide 10,000 calls/minute limit.
- Team member assignment during import uses the existing practice user/team model. If no team members exist, the assigning accountant is the default.
- Fuzzy name matching for auto-matching uses simple string similarity (e.g., normalized comparison, removing common suffixes like "Pty Ltd"). Advanced NLP-based matching is out of scope.
- The existing BulkImportJob model in the onboarding module can be extended or reused for tracking bulk Xero imports.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An accountant can connect 25 client organizations in a single session in under 5 minutes (excluding sync time), compared to the current ~2 minutes per client (50+ minutes total).
- **SC-002**: 95% of bulk import flows complete without errors when importing 10 or fewer organizations.
- **SC-003**: The bulk sync progress dashboard reflects real-time status within 5 seconds of any individual organization sync completing or failing.
- **SC-004**: Auto-matching correctly links at least 80% of imported organizations that have exact name matches to existing client records.
- **SC-005**: No duplicate connections are created when re-running a bulk import that includes already-connected organizations.
- **SC-006**: The system respects all rate limits during bulk sync — no 429 (Too Many Requests) errors propagate to the user.
- **SC-007**: Accountants can begin working with individual clients as soon as their sync completes, without waiting for the entire bulk import to finish.
