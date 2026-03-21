# Feature Specification: Onboarding Flow

**Feature Branch**: `feature/021-onboarding-flow`
**Created**: 2025-12-31
**Status**: Draft
**Input**: Onboarding Flow - Guide new accountants from signup through to first value. Flow: Clerk signup → Tier selection → Stripe checkout with 14-day free trial option → Connect Xero → Import first client → Interactive product tour → Dashboard ready. Includes onboarding checklist to track setup completion, welcome email drip sequence for activation.

---

## Overview

This feature creates a guided onboarding experience that takes new accountants from initial signup to their first moment of value (seeing their first client's BAS data). The flow minimizes friction while ensuring users complete key setup steps that lead to successful adoption.

**Key Value**: Reduce time-to-value from signup to first BAS insight, increase activation rates, and ensure new users understand the platform's capabilities.

**Dependencies**: Builds on Spec 019 (Subscription & Feature Gating) for tier selection and Stripe checkout, and Spec 003/004 (Xero OAuth and Data Sync) for connecting accounting data.

---

## User Scenarios & Testing

### User Story 1 - New Accountant Signup with Tier Selection (Priority: P1)

A new accountant discovers Clairo and wants to start using it for their practice. They complete signup, choose an appropriate subscription tier for their practice size, and complete payment to gain immediate access.

**Why this priority**: This is the primary acquisition funnel. Without a smooth signup flow, no users enter the platform.

**Independent Test**: Can be fully tested by starting from the marketing site, completing signup, selecting a tier, and verifying successful account creation with correct tier assignment.

**Acceptance Scenarios**:

1. **Given** a new visitor on the Clairo marketing site, **When** they click "Start Free Trial", **Then** they are directed to the Clerk signup page with email/Google/Microsoft options

2. **Given** a user has completed Clerk signup, **When** they are authenticated, **Then** they are automatically redirected to the tier selection page (not the main dashboard)

3. **Given** a user is on the tier selection page, **When** they view the options, **Then** they see all tiers (Starter $99, Professional $299, Growth $599) with clear feature comparison and client limits

4. **Given** a user is viewing tier options, **When** they select any tier, **Then** the "Start 14-Day Free Trial" button is prominently displayed with text indicating no charge until trial ends

5. **Given** a user selects Professional tier and clicks "Start Free Trial", **When** Stripe checkout loads, **Then** they see "$0.00 due today" with future billing date shown (14 days from now)

6. **Given** a user completes Stripe checkout, **When** payment method is saved successfully, **Then** they are redirected to the "Connect Xero" step (not dashboard)

---

### User Story 2 - Free Trial Experience (Priority: P1)

Accountants can try Clairo for 14 days without being charged. During the trial, they have full access to their chosen tier's features. They receive reminders before the trial ends and can easily convert to paid or cancel.

**Why this priority**: Free trials significantly reduce signup friction and are industry standard for B2B SaaS. Critical for acquisition.

**Independent Test**: Can be tested by signing up for a trial, verifying no charge occurs, checking trial status displays correctly, and receiving trial ending notifications.

**Acceptance Scenarios**:

1. **Given** a user has started a 14-day free trial, **When** they view their billing page, **Then** they see "Free Trial - 12 days remaining" with the tier they selected and the date billing will begin

2. **Given** a user is on day 11 of their trial (3 days remaining), **When** the system runs daily checks, **Then** they receive an email: "Your Clairo trial ends in 3 days - your saved payment method will be charged $299"

3. **Given** a user is on their last trial day, **When** they log in, **Then** they see an in-app banner: "Your trial ends tomorrow. Your card ending in 4242 will be charged $299.00"

4. **Given** a trial has ended, **When** the user's payment method is charged successfully, **Then** their subscription converts to "active" status and they receive a receipt email

5. **Given** a trial has ended and payment fails, **When** the charge is declined, **Then** their subscription enters "past_due" status, they receive a notification, and a 7-day grace period begins

6. **Given** a user wants to cancel during their trial, **When** they access billing settings and click "Cancel Trial", **Then** they can cancel without being charged and lose access at trial end

---

### User Story 3 - Connect Xero Integration (Priority: P1)

After completing signup and payment setup, the accountant connects their Xero account to begin syncing practice and client data. This is a required step before they can use most platform features.

**Why this priority**: Without Xero connection, there's no data and no value. This is the critical "activation" step.

**Independent Test**: Can be tested by navigating to the Connect Xero step, completing OAuth flow, and verifying the connection is established.

**Acceptance Scenarios**:

1. **Given** a user has completed Stripe checkout, **When** they land on the Connect Xero page, **Then** they see a clear explanation of why Xero connection is needed and what data will be synced

2. **Given** a user clicks "Connect Xero", **When** Xero OAuth popup opens, **Then** they can authorize Clairo access to their Xero organization

3. **Given** OAuth completes successfully, **When** user returns to Clairo, **Then** they see a success message with their connected Xero organization name and are automatically moved to the next step

4. **Given** OAuth fails or is cancelled, **When** user returns to Clairo, **Then** they see an error message with a "Try Again" button and option to skip for now

5. **Given** a user chooses to skip Xero connection, **When** they click "Skip for now", **Then** they are warned that most features require Xero and can proceed to the product tour with limited functionality

---

### User Story 4 - Bulk Import Practice Clients (Priority: P2)

After connecting Xero, the accountant imports their practice clients from Xero Practice Manager (XPM). Accounting firms typically have many clients on their books (often 50-200+), so the import experience must support bulk selection. Each client's associated contacts (customers, suppliers) are automatically imported as entities within that client.

**Why this priority**: Client import is the "aha moment" - seeing real data makes the platform real. Bulk import is essential because accountants won't adopt a tool that requires importing 100+ clients one-by-one.

**Independent Test**: Can be tested by connecting XPM, selecting multiple clients from the list, and verifying all selected clients are imported with their associated data.

**Acceptance Scenarios**:

1. **Given** Xero is connected, **When** user lands on the Import Clients step, **Then** they see a loading state while the system fetches their XPM client list (typically 10-30 seconds)

2. **Given** XPM clients are loaded, **When** user views the import screen, **Then** they see:
   - A searchable/filterable list of their practice clients from XPM
   - Checkbox next to each client for multi-select
   - "Select All" option at the top
   - Client count indicator (e.g., "147 clients found")
   - Their tier's client limit displayed (e.g., "Your plan allows 100 clients")

3. **Given** a user has a Starter tier (25 client limit) with 50 XPM clients, **When** they click "Select All", **Then** only the first 25 clients are selected and they see a message: "Your Starter plan allows 25 clients. Upgrade to Professional for up to 100 clients." with an upgrade prompt

4. **Given** a user selects 15 clients and clicks "Import Selected", **When** the import begins, **Then** they see:
   - A progress indicator showing import status (e.g., "Importing 3 of 15 clients...")
   - Each client's status updates as it completes (syncing contacts, invoices, transactions)
   - Import runs in background so user can proceed to next step while it finishes

5. **Given** import is in progress, **When** all selected clients are imported, **Then** user sees a summary: "Successfully imported 15 clients. 2,340 transactions synced. Average data quality score: 78%"

6. **Given** some client imports fail (e.g., Xero API error), **When** the batch completes, **Then** user sees partial success message with option to retry failed imports: "Imported 13 of 15 clients. 2 clients encountered errors - click to retry"

7. **Given** a user has imported at least one client, **When** they click "Continue", **Then** they are taken to the Product Tour step (import can continue in background)

8. **Given** user only has Xero Accounting (not XPM), **When** they view the import screen, **Then** they see their Xero organization's contacts that can be imported as clients, with the same bulk selection UX

9. **Given** no XPM clients or Xero contacts are found, **When** user views the import screen, **Then** they see a helpful message explaining they need clients in Xero/XPM first, with option to skip and add later

**Bulk Connections Scenarios (When Advanced Partner tier enabled)**:

10. **Given** Bulk Connections is enabled for our app, **When** accountant clicks "Connect All Client Organizations", **Then** they are redirected to Xero OAuth with multi-select checkboxes for ALL organizations they have access to

11. **Given** accountant is on Xero's organization selection screen, **When** they select 150 client organizations and click "Allow Access", **Then** they return to Clairo and the system retrieves all 150 tenant IDs from `/connections` endpoint

12. **Given** bulk authorization completes, **When** system processes the connections, **Then** each client record is linked to its corresponding Xero tenant ID and data sync can begin for all clients

**Individual Authorization Scenarios (Current approach)**:

13. **Given** XPM clients are loaded with metadata, **When** user views a client without Xero connection, **Then** they see a "Connect Xero" button next to that client's name

14. **Given** user clicks "Connect Xero" for a specific client, **When** Xero OAuth opens, **Then** the accountant authorizes access to that client's Xero organization only

15. **Given** a client's Xero is authorized, **When** user returns to the import screen, **Then** that client shows "Connected" badge and data sync begins automatically

16. **Given** user has 50 clients to connect, **When** they click "Connect All Remaining", **Then** a streamlined workflow opens that guides them through authorizing each client sequentially with minimal clicks

**Note on Xero Integration Architecture**:

There are TWO levels of authorization required for full functionality:

**Level 1 - Practice Authorization (Accountant's own accounts)**:
- **Xero Practice Manager (XPM)**: Provides client list, jobs, and practice management data
- **Accountant's Xero Accounting**: The practice's own bookkeeping

**Level 2 - Client Organization Authorization (Each client's Xero)**:
- Each client business has its OWN Xero organization with financial data
- To access a client's invoices, transactions, and BAS data, that specific Xero organization must be authorized
- This is where bulk authorization becomes critical for practices with 200+ clients

**Authorization Approaches**:

| Approach | Availability | How It Works |
|----------|--------------|--------------|
| **Bulk Connections** | Requires Xero Advanced Partner tier | Single OAuth flow where accountant selects ALL client orgs at once using checkboxes. Returns multiple tenant IDs. |
| **Individual Authorization** | Available now | Each client org authorized separately. Can be streamlined with a "Connect Next Client" workflow. |

**Current Implementation Strategy**:
1. **Phase 1 (Now)**: Support individual authorization with streamlined UX
   - Show client list from XPM (metadata only)
   - For each client, show "Connect Xero" button
   - Track which clients have authorized Xero access
   - Provide "Connect All Remaining" workflow that loops through

2. **Phase 2 (After Advanced Partner approval)**: Enable Bulk Connections
   - Single OAuth redirects to Xero with multi-select UI
   - Accountant checks all client organizations
   - All authorized at once, system retrieves all tenant IDs

**Important Distinctions**:
- **XPM Client Record**: Metadata (name, ABN, contact) - available after XPM connection
- **Xero Organization Access**: Financial data (transactions, invoices, BAS) - requires each client org to be authorized
- **Contact vs Client**: Contacts (customers, suppliers) are entities *within* a client's Xero organization

---

### User Story 5 - Interactive Product Tour (Priority: P2)

A new user receives a guided tour of the main platform features, highlighting key capabilities and helping them understand how to navigate. The tour can be skipped but is shown once by default.

**Why this priority**: Product tours improve feature discovery and reduce support questions. Important for activation but user has already received value by this point.

**Independent Test**: Can be tested by completing onboarding steps and verifying the tour launches, steps can be navigated, and completion is tracked.

**Acceptance Scenarios**:

1. **Given** a user completes the Import Client step, **When** they reach the dashboard, **Then** an interactive tour overlay automatically begins highlighting the first feature

2. **Given** the tour is active, **When** user views each step, **Then** they see a tooltip explaining the feature with a "Next" button to continue (approximately 5-7 steps covering: Dashboard overview, Client list, BAS workflow, Data quality, AI insights, Settings)

3. **Given** the tour is in progress, **When** user clicks "Skip Tour", **Then** the tour closes immediately and doesn't show again

4. **Given** the tour completes all steps, **When** user finishes the last step, **Then** they see a completion message: "You're all set! Start by reviewing your client's data quality score"

5. **Given** a user skipped or completed the tour previously, **When** they log in again, **Then** the tour does not auto-start (but can be restarted from Help menu)

---

### User Story 6 - Onboarding Checklist (Priority: P2)

A persistent checklist shows new users their onboarding progress and remaining setup steps. This encourages completion of all setup tasks and provides a sense of accomplishment.

**Why this priority**: Checklists drive completion rates. Visible progress motivates users to finish setup. Supports activation goals.

**Independent Test**: Can be tested by observing checklist state after each onboarding action and verifying items are marked complete appropriately.

**Acceptance Scenarios**:

1. **Given** a new user has just completed signup, **When** they view any page, **Then** they see an onboarding checklist widget showing their progress (e.g., "2 of 5 steps complete")

2. **Given** the checklist is visible, **When** user expands it, **Then** they see all steps: [ ] Choose subscription tier, [ ] Connect Xero, [ ] Import clients, [ ] Complete product tour, [ ] Review client data quality

3. **Given** a user completes the Xero connection step, **When** the checklist refreshes, **Then** the "Connect Xero" item shows as completed with a checkmark

4. **Given** all checklist items are complete, **When** user views the checklist, **Then** they see a congratulations message and the checklist collapses/hides after 3 days

5. **Given** a user has incomplete checklist items after 7 days, **When** they log in, **Then** the checklist remains visible as a reminder until complete or dismissed

6. **Given** a user clicks "Dismiss checklist", **When** they confirm, **Then** the checklist hides permanently (but progress is still tracked)

---

### User Story 7 - Welcome Email Drip Sequence (Priority: P3)

New users receive a series of helpful emails over their first 14 days (trial period) that guide them through setup, highlight key features, and encourage activation.

**Why this priority**: Email drips improve activation rates but are less critical than in-app experience. Can be implemented after core flow works.

**Independent Test**: Can be tested by signing up and verifying emails are received at expected intervals with correct personalization.

**Acceptance Scenarios**:

1. **Given** a user completes signup, **When** their account is created, **Then** they receive a welcome email within 5 minutes: "Welcome to Clairo, [Name]! Here's how to get started..."

2. **Given** a user signed up but hasn't connected Xero after 24 hours, **When** the automation runs, **Then** they receive a reminder email: "Connect Xero to unlock Clairo's full potential"

3. **Given** a user connected Xero but hasn't imported a client after 48 hours, **When** the automation runs, **Then** they receive an email: "Import your first client to see AI-powered insights"

4. **Given** a user is on day 7 of their trial, **When** the automation runs, **Then** they receive a mid-trial email highlighting features they haven't used yet

5. **Given** a user is on day 12 of their trial, **When** the automation runs, **Then** they receive a trial ending reminder with success stories from other accountants

6. **Given** a user completes all onboarding steps, **When** checklist is 100% complete, **Then** they receive a congratulations email with tips for ongoing usage

---

### Edge Cases

- What happens if a user starts signup but abandons before completing Stripe checkout?
  - User record is created with tier but subscription_status="incomplete". After 24 hours, they receive a recovery email. After 7 days with no completion, record is marked abandoned.

- What happens if Xero OAuth token expires during initial sync?
  - User sees an error message with "Reconnect Xero" button. Onboarding can resume from where it left off after reconnection.

- What happens if a user has multiple Xero organizations?
  - After OAuth, user is shown a list of their Xero organizations and can select which one to connect to Clairo.

- What happens if a user tries to import more clients than their trial tier allows during onboarding?
  - They are limited to their tier's client limit (e.g., 25 for Starter) and shown an upgrade prompt for more clients.

- What happens if the user's browser blocks the Xero OAuth popup?
  - The system detects popup block and shows instructions to allow popups, with a fallback "Open in new tab" link.

- What happens if the accountant has both XPM and multiple Xero organizations?
  - After XPM OAuth, the system displays the XPM client list. Each XPM client may have their own Xero organization which is connected when that client is imported.

- What happens if the accountant doesn't have user access to a client's Xero organization?
  - That client shows "No Xero Access" status. The accountant must first be added as a user in the client's Xero org before they can authorize it. System provides guidance on how to request access.

- What happens if an XPM client record cannot be matched to a connected Xero organization?
  - System stores the Xero org connection but shows it as "Unmatched". Admin can manually link the Xero org to an XPM client, or system attempts fuzzy matching by organization name/ABN.

- What happens when Bulk Connections OAuth returns 200+ tenant IDs?
  - System stores all tenant IDs, then processes them in batches. For each tenant, it attempts to match to existing XPM client records by organization name or ABN. Unmatched orgs are stored for manual review.

- What happens if an accountant has Bulk Connections enabled but wants to authorize just one client?
  - System provides both options: "Connect All Organizations" (bulk) and "Connect This Client Only" (individual). Individual auth uses `acr_values=bulk_connect:false` to disable multi-select.

- What happens if a client's Xero access is revoked after initial setup?
  - System detects auth failure on next sync attempt, marks client as "Disconnected", and notifies accountant to re-authorize that specific client.

- What happens if bulk import is interrupted (e.g., user closes browser)?
  - Import continues in background via Celery. User sees import progress when they return, with completed/pending status for each client.

- What happens if XPM rate limits are hit during bulk import of 100+ clients?
  - Import job implements exponential backoff and continues automatically. User sees "Import paused - resuming shortly" status. Progress is preserved.

---

## Requirements

### Functional Requirements

**Signup & Tier Selection**:
- **FR-001**: System MUST redirect newly authenticated users to onboarding flow (not dashboard) if onboarding is incomplete
- **FR-002**: System MUST display tier selection page with all available tiers after Clerk authentication
- **FR-003**: System MUST show client limits, feature lists, and pricing for each tier on selection page
- **FR-004**: System MUST highlight the recommended tier (Professional) with visual emphasis
- **FR-005**: System MUST offer 14-day free trial for all tiers

**Trial Management**:
- **FR-006**: System MUST create Stripe subscription with trial_period_days=14 for new signups
- **FR-007**: System MUST not charge payment method until trial period ends
- **FR-008**: System MUST send trial ending reminders at 3 days and 1 day before expiration
- **FR-009**: System MUST automatically convert trial to paid subscription if payment succeeds
- **FR-010**: System MUST enter grace period if payment fails at trial end
- **FR-011**: System MUST allow users to cancel trial without charge before it ends

**Xero Connection**:
- **FR-012**: System MUST guide users to connect Xero after completing payment setup
- **FR-013**: System MUST handle Xero OAuth flow with proper error handling
- **FR-014**: System MUST allow users to skip Xero connection with a warning about limited functionality
- **FR-015**: System MUST show Xero organization name after successful connection

**Client Import & Authorization**:
- **FR-016**: System MUST detect whether user has Xero Practice Manager (XPM) or only Xero Accounting
- **FR-017**: System MUST fetch and display practice clients from XPM if available, otherwise display Xero Accounting contacts
- **FR-018**: System MUST provide searchable/filterable list of available clients for import
- **FR-019**: System MUST support multi-select with checkboxes for bulk client selection
- **FR-020**: System MUST provide "Select All" option that respects tier client limits
- **FR-021**: System MUST display user's tier client limit alongside selection (e.g., "Your plan allows 100 clients")
- **FR-022**: System MUST show upgrade prompt when user attempts to select more clients than tier allows
- **FR-023**: System MUST initiate bulk import as background process when user clicks "Import Selected"
- **FR-024**: System MUST show real-time import progress (e.g., "Importing 3 of 15 clients...")
- **FR-025**: System MUST allow user to proceed to next onboarding step while import continues in background
- **FR-026**: System MUST display import summary on completion (clients imported, transactions synced, any errors)
- **FR-027**: System MUST provide retry option for any failed client imports
- **FR-028**: System MUST automatically sync each imported client's contacts, invoices, and transactions

**Client Organization Authorization (Two-Level Auth)**:
- **FR-029A**: System MUST distinguish between XPM client metadata and Xero organization financial data access
- **FR-029B**: System MUST track which clients have authorized Xero organization access vs only have metadata
- **FR-029C**: System MUST display "Connect Xero" button for clients without authorized organization access
- **FR-029D**: System MUST support individual client authorization via OAuth flow for each client's Xero organization
- **FR-029E**: System MUST provide "Connect All Remaining" workflow that guides accountant through sequential client authorizations
- **FR-029F**: System MUST retrieve and store all connected tenant IDs from Xero `/connections` endpoint after OAuth
- **FR-029G**: System MUST match connected Xero tenant IDs to XPM client records where possible

**Bulk Connections (When Advanced Partner Tier Enabled)**:
- **FR-029H**: System SHOULD support Xero Bulk Connections when enabled by Xero partnership
- **FR-029I**: When Bulk Connections enabled, System MUST allow single OAuth flow to authorize multiple organizations
- **FR-029J**: When Bulk Connections enabled, System MUST NOT include `acr_values=bulk_connect:false` in OAuth URL
- **FR-029K**: System MUST provide configuration flag to enable/disable Bulk Connections feature

**Product Tour**:
- **FR-030**: System MUST launch interactive product tour on first dashboard visit
- **FR-031**: System MUST allow users to skip tour at any point
- **FR-032**: System MUST track tour completion status
- **FR-033**: System MUST allow users to restart tour from Help menu

**Onboarding Checklist**:
- **FR-034**: System MUST display onboarding checklist widget for incomplete users
- **FR-035**: System MUST track completion status of each onboarding step
- **FR-036**: System MUST update checklist in real-time as steps complete
- **FR-037**: System MUST allow users to dismiss checklist permanently
- **FR-038**: System MUST hide checklist automatically 3 days after all items complete

**Welcome Emails**:
- **FR-039**: System MUST send welcome email within 5 minutes of signup
- **FR-040**: System MUST send reminder emails based on incomplete onboarding steps
- **FR-041**: System MUST send trial reminder emails at day 12 (2 days before end)
- **FR-042**: System MUST personalize emails with user name and account status
- **FR-043**: System MUST respect email opt-out preferences

### Key Entities

- **OnboardingProgress**: Tracks each tenant's progress through onboarding steps (tier_selected, xero_connected, clients_imported, tour_completed, checklist_dismissed), with timestamps for each milestone
- **OnboardingStep**: Enumeration of onboarding steps with ordering and requirements
- **BulkImportJob**: Tracks bulk client import jobs with status (pending, in_progress, completed, partial_failure), total clients selected, clients imported successfully, clients failed, and error details
- **EmailDrip**: Tracks which automated emails have been sent to each user, preventing duplicates and enabling analytics

---

## Auditing & Compliance Checklist

### Audit Events Required

- [x] **Authentication Events**: User signup and tier selection involves account creation
- [ ] **Data Access Events**: No sensitive data read during onboarding
- [x] **Data Modification Events**: Tenant record created, tier assigned, subscription created
- [x] **Integration Events**: Xero OAuth connection established, initial sync triggered
- [ ] **Compliance Events**: No BAS lodgement or compliance actions during onboarding

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| onboarding.started | User begins onboarding | tenant_id, timestamp | 7 years | None |
| onboarding.tier_selected | User selects subscription tier | tenant_id, tier, trial_start | 7 years | None |
| onboarding.trial_started | Stripe trial subscription created | tenant_id, stripe_subscription_id | 7 years | None |
| onboarding.xero_connected | Xero OAuth completed | tenant_id, xero_org_id | 7 years | None |
| onboarding.bulk_import_started | Bulk import job initiated | tenant_id, job_id, client_count | 7 years | None |
| onboarding.bulk_import_completed | Bulk import job finished | tenant_id, job_id, success_count, fail_count | 7 years | None |
| onboarding.tour_completed | Product tour finished | tenant_id, timestamp | 7 years | None |
| onboarding.completed | All onboarding steps done | tenant_id, duration_hours | 7 years | None |

### Compliance Considerations

- **ATO Requirements**: Onboarding events are not directly ATO-relevant but are useful for customer success and support audits
- **Data Retention**: Standard 7-year retention for business records
- **Access Logging**: Support and customer success teams may view onboarding progress for assistance

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: New users complete signup (Clerk + tier + payment method) in under 5 minutes
- **SC-002**: At least 70% of signups proceed to connect Xero within the same session
- **SC-003**: At least 60% of users who connect Xero import at least one client in their first session
- **SC-004**: Average time from signup to first client data visible is under 15 minutes
- **SC-005**: At least 50% of new users complete the full onboarding checklist within 7 days
- **SC-006**: Trial-to-paid conversion rate is at least 25% for users who complete onboarding
- **SC-007**: Trial-to-paid conversion rate is at least 5% for users who don't complete onboarding
- **SC-008**: Welcome email open rate is at least 60%
- **SC-009**: Product tour completion rate is at least 40% (of those who start it)
- **SC-010**: Support tickets related to "getting started" decrease by 50% compared to no-onboarding baseline

---

## Assumptions

The following reasonable defaults were assumed based on industry standards and context:

1. **Trial Length**: 14 days is industry standard for B2B SaaS and aligns with monthly billing cycle
2. **Email Timing**: Welcome email immediate, reminders based on incomplete actions, trial warnings at 3 and 1 day
3. **Tour Length**: 5-7 steps covering major features is optimal for engagement without fatigue
4. **Checklist Behavior**: Auto-hide after 3 days of completion, permanent dismiss option available
5. **Skip Options**: All steps allow skip (with warnings) to avoid frustrating users who want to explore independently
6. **Recovery Flows**: Abandoned signups receive recovery emails; users can resume from any incomplete step
