# Feature Specification: BAS Workflow Tracker — Practice Management Layer

**Feature Branch**: `058-bas-workflow-tracker`  
**Created**: 2026-04-15  
**Status**: Draft  
**Input**: Gap analysis of Vik Dhawan's BAS workflow Excel + Unni & Vik huddle feedback (13 April 2026)

---

## Origin

Vik and Unni each manage ~280 BAS/IAS obligations per quarter using Excel spreadsheets. They've been alpha-testing Clairo but can't replace their Excel because the platform is built around individual client BAS preparation — it doesn't solve the practice-level management job of "which of my 280 clients are ready, who's handling what, and what's blocked."

The platform already has a sophisticated BAS processing engine (tax code classification, AI suggestions, Xero sync, lodgement workflow). What's missing is the "practice management" layer on top — the daily triage and team coordination that accountants do *before* they even open a single client's BAS.

**Key principle**: Solve the job, don't replicate the spreadsheet. Vik's Excel has 10 columns but only 3 represent genuinely missing capabilities. The rest are manual workarounds for things Clairo can auto-derive from data it already has.

**Success looks like**: Vik says "I can close my Excel spreadsheet."

---

## Problem

Australian accounting practices typically manage 100-300+ BAS obligations per quarter across their client base. The current platform provides deep per-client BAS preparation tools but no practice-wide view that supports:

- **Team coordination**: Who is responsible for which clients? (Currently, assignment happens during client import but doesn't persist beyond that step.)
- **Portfolio triage**: Which clients need BAS this quarter and which don't? (Currently, every active client appears in the dashboard regardless of whether they need a BAS — dormant entities, externally-lodged clients, and GST-cancelled businesses all clutter the working list.)
- **Tribal knowledge**: What does a team member need to know before opening a specific client's BAS? (Currently, per-session notes exist but reset each quarter. Persistent client-level instructions like "client does the bookkeeping" or "monthly BAS" have nowhere to live.)
- **Complete visibility**: What about the ~40% of clients not on Xero? (Currently, only Xero-connected clients appear. QuickBooks, MYOB, and email-based clients are invisible.)
- **Accurate readiness signals**: The dashboard shows clients as "Ready" even when they have dozens of unreconciled bank transactions.

Without these capabilities, accountants maintain a parallel Excel spreadsheet — defeating the purpose of the platform.

---

## User Scenarios & Testing

### User Story 1 — Team Assignment (Priority: P1)

As a practice owner, I need to assign each client to a team member so we know who is responsible for whose BAS. My team is 4 people and each handles a subset of ~280 clients. The allocation is the most-used column in my daily triage.

**Why this priority**: Without team assignment, multi-person practices cannot divide work. This is the single biggest gap blocking Vik from replacing his Excel. Every other feature adds value on top of this one.

**Independent Test**: Can be fully tested by assigning team members to clients and filtering the dashboard by assignee. Delivers immediate value by enabling "My clients" as the default working view for each team member.

**Acceptance Scenarios**:

1. **Given** a practice with 4 team members and 50 clients, **When** the practice owner assigns 15 clients to team member "Pawan", **Then** those 15 clients show "Pawan" in the assigned-to column on the dashboard.

2. **Given** a team member logs in (non-admin role), **When** they view the dashboard, **Then** it defaults to showing only their assigned clients ("My Clients" filter).

3. **Given** a practice owner viewing the dashboard, **When** they select the "All" filter, **Then** they see all clients regardless of assignment, with each client's assignee visible.

4. **Given** a client currently assigned to "Aarti", **When** the practice owner reassigns that client to "Anil", **Then** the dashboard immediately reflects the new assignment and the client appears under Anil's "My Clients" view.

5. **Given** 10 clients selected on the dashboard, **When** the practice owner uses bulk reassignment to assign all 10 to "Pawan", **Then** all 10 clients update their assignee simultaneously.

6. **Given** a new client imported via the existing bulk import flow with a team member selected, **When** the import completes, **Then** the assignment persists on the client record and appears on the dashboard.

7. **Given** a client with no team member assigned, **When** viewed on the dashboard, **Then** the assigned-to column shows "Unassigned" and the client appears under the "Unassigned" filter option.

---

### User Story 2 — Client Exclusion per Quarter (Priority: P1)

As an accountant, I need to mark clients as "not required" for a specific quarter so they don't clutter my working list. The reasons vary — GST registration cancelled, entity is dormant, a separate bookkeeper handles lodgement, or the client has left the practice.

**Why this priority**: Without exclusion, every active client appears in every quarter's view. For a practice with 280 clients where perhaps 30-40 don't need BAS in a given quarter, this creates significant noise that slows down daily triage. Combined with team assignment, these two features form the minimum viable practice management layer.

**Independent Test**: Can be tested by marking clients as excluded for a quarter and verifying they disappear from the active working list and summary totals.

**Acceptance Scenarios**:

1. **Given** a client that is dormant, **When** the accountant marks that client as "not required" for Q3 FY2026, **Then** the client no longer appears in the default dashboard view for Q3 and does not count toward summary card totals (portfolio health, ready to lodge, etc.).

2. **Given** a client excluded for Q3 FY2026, **When** the accountant switches to viewing Q4 FY2026, **Then** that client reappears as a normal active client (exclusion is per-quarter, not permanent).

3. **Given** a client excluded for a quarter, **When** the accountant filters for "Excluded" clients, **Then** the client appears in a dedicated excluded list with the reason shown.

4. **Given** a client that was excluded by mistake, **When** the accountant reverses the exclusion, **Then** the client immediately reappears in the active working list and counts toward summary totals.

5. **Given** an exclusion action, **When** the accountant marks a client as excluded, **Then** the system prompts for an optional reason (dormant, lodged externally, GST cancelled, left practice, other with free text).

6. **Given** the dashboard summary cards, **When** 5 clients are excluded for the quarter, **Then** the total client count and status distribution only reflect the non-excluded clients.

---

### User Story 3 — Persistent Client Notes (Priority: P2)

As a team member, when I open a client's BAS session, I need to see persistent notes about how this client works — who does the bookkeeping, what software they use, any special instructions. This is tribal knowledge that currently lives in the practice owner's head or in the Excel spreadsheet.

**Why this priority**: Critical for team efficiency but not a blocker for practice-level triage (the P1 stories). Notes reduce the back-and-forth between team members and the practice owner when preparing BAS. Existing per-session notes handle quarter-specific context; these notes handle client-level context that carries across quarters.

**Independent Test**: Can be tested by adding a note to a client, closing the session, starting a new quarter's BAS, and verifying the note persists and is prominently displayed.

**Acceptance Scenarios**:

1. **Given** a client record, **When** a team member adds a persistent note like "Client does the bookkeeping, usually sends on the last day", **Then** that note is saved on the client record (not the session) and visible to all practice users.

2. **Given** a client with a persistent note, **When** any team member opens that client's BAS session for any quarter, **Then** the persistent note is prominently displayed as the first contextual information they see — before session-specific details.

3. **Given** a client note last edited by "Aarti" on 15 March 2026, **When** viewing the note, **Then** the system shows who last edited it and when.

4. **Given** a client with both a persistent note and a session-specific note, **When** viewing the BAS session, **Then** both notes are visible and clearly distinguished — the persistent note is labeled as a standing instruction and the session note as quarter-specific context.

5. **Given** a client with a persistent note, **When** the note is updated, **Then** the previous content is not lost (a history of changes is maintained for audit purposes).

---

### User Story 4 — Non-Xero Client Visibility (Priority: P2)

As a practice owner, I manage 280 clients but only ~60% are on Xero. I need to see ALL my clients in one place, even if the platform can't pull data for the non-Xero ones. If only the Xero slice is visible, I still need my Excel for the rest.

**Why this priority**: Important for completeness but delivers less functional depth than the P1 stories — non-Xero clients can only be manually tracked (no auto-derived readiness, no AI suggestions, no sync). The value is in having a single source of truth for the full client list so nothing falls through the cracks.

**Independent Test**: Can be tested by adding non-Xero clients manually and verifying they appear alongside Xero clients on the dashboard with appropriate visual indicators.

**Acceptance Scenarios**:

1. **Given** the dashboard, **When** an accountant adds a client manually (not via Xero connection), **Then** the client appears in the dashboard client table alongside Xero-connected clients.

2. **Given** a manually-added client with accounting software set to "QuickBooks", **When** viewing the dashboard, **Then** the client shows a clear indicator of its software type and that it is not connected for auto-sync.

3. **Given** a non-Xero client, **When** viewing its detail page, **Then** the system shows that BAS status can only be manually progressed (no auto-derived readiness) and team members can manually move it through status stages.

4. **Given** the dashboard with a mix of Xero and non-Xero clients, **When** applying the team member filter, **Then** both Xero and non-Xero clients are included in the filtered results.

5. **Given** a manual client creation form, **When** the accountant creates a new client, **Then** they can specify the client name, ABN (optional), accounting software type (QuickBooks, MYOB, email-based, other), and optionally assign a team member.

6. **Given** a non-Xero client that later connects to Xero, **When** the Xero connection is established, **Then** the client record is linked to the Xero connection and auto-derived features (sync, readiness, AI suggestions) become available.

---

### User Story 5 — Smarter Readiness Signals (Priority: P2)

As an accountant, I need the dashboard to accurately reflect which clients are truly ready for BAS preparation. Currently, a client can show as "Ready" even when it has 50 unreconciled bank transactions — which means I open the client, discover the mess, and waste time triaging.

**Why this priority**: Valuable improvement to an existing feature but not a structural gap like team assignment or exclusion. The current readiness signal is functional for practices with well-maintained Xero books. This refinement matters most for practices with clients who have messy data.

**Independent Test**: Can be tested by checking that a client with many unreconciled transactions does not appear as "Ready" on the dashboard, and that the reconciliation count is visible as a data point.

**Acceptance Scenarios**:

1. **Given** a client with 20 unreconciled bank transactions and otherwise complete data, **When** the dashboard derives readiness status, **Then** the client shows as "Needs Review" (not "Ready").

2. **Given** a client with 3 unreconciled bank transactions (below the threshold), **When** the dashboard derives readiness status, **Then** the client can still show as "Ready" if all other readiness criteria are met.

3. **Given** the dashboard client table, **When** viewing a client row, **Then** the unreconciled transaction count is visible as a data point (similar to how quality score is shown today).

4. **Given** the "Attention Needed" insight cards on the dashboard, **When** a client has a high count of unreconciled transactions, **Then** an attention card highlights this client with the specific count.

5. **Given** a practice with varying data quality across clients, **When** the default reconciliation threshold is applied (more than 5 unreconciled transactions triggers "Needs Review"), **Then** the threshold behaves as a sensible default that the practice can accept without configuration.

---

### Edge Cases

- **Team member removed from practice**: Clients assigned to a removed team member become "Unassigned" and the practice owner is notified of orphaned assignments.
- **Quarter boundary for exclusions**: Exclusions do not carry forward — each quarter starts with a clean slate unless the accountant re-excludes.
- **Bulk import with existing clients**: If a client already exists (matched by ABN or Xero org ID) during bulk import, the assignment updates the existing client, not creates a duplicate.
- **Non-Xero client with same ABN as Xero client**: If a manually-added client is later connected to Xero, the system merges the records rather than creating a duplicate. Matching is by ABN first, then by name similarity.
- **Concurrent exclusion edits**: Two users excluding/including the same client for the same quarter simultaneously — last write wins, with both actions logged.
- **Empty practice**: A new practice with zero clients sees an empty dashboard with clear calls-to-action for adding clients (via Xero connection or manual entry).
- **Reconciliation data freshness**: Unreconciled count is only as fresh as the last Xero sync. If sync is stale (>24h), the reconciliation signal is treated as potentially outdated and flagged accordingly.
- **Non-Xero client readiness**: Non-Xero clients cannot have auto-derived readiness. Their status is manually managed and does not show misleading auto-derived signals.
- **Notes with special characters or excessive length**: Persistent notes support rich text basics (line breaks, bullet points) and have a reasonable maximum length to prevent misuse as a document store.

---

## Requirements

### Functional Requirements — Team Assignment

- **FR-001**: System MUST allow practice owners and accountants to assign a team member to any client.
- **FR-002**: System MUST display the assigned team member on the dashboard client table as a visible column.
- **FR-003**: System MUST provide a "My Clients" filter on the dashboard that shows only clients assigned to the currently logged-in user. This MUST be the default view for non-admin users.
- **FR-004**: System MUST provide an "Unassigned" filter option to show clients with no team member assigned.
- **FR-005**: System MUST support bulk reassignment — selecting multiple clients and assigning them to a team member in a single action.
- **FR-006**: System MUST carry team member assignments from the bulk import flow through to the persistent client record. Assignments set during import MUST NOT be lost after import completes.
- **FR-007**: System MUST allow reassignment of clients via the client detail view and from the dashboard table directly (inline dropdown or quick action).

### Functional Requirements — Client Exclusion

- **FR-008**: System MUST allow accountants to mark a client as "not required" for a specific quarter.
- **FR-009**: Exclusion MUST be per-quarter — a client excluded for Q3 FY2026 MUST appear as active in Q4 FY2026.
- **FR-010**: Excluded clients MUST NOT appear in the default dashboard working list for that quarter.
- **FR-011**: Excluded clients MUST NOT count toward summary card totals (portfolio health, status distribution, ready to lodge count).
- **FR-012**: System MUST allow filtering to see excluded clients and their exclusion reasons.
- **FR-013**: Exclusion MUST be reversible — an accountant can un-exclude a client for a quarter at any time.
- **FR-014**: System SHOULD capture an optional reason for exclusion (dormant, lodged externally, GST cancelled, left practice, other with free text).

### Functional Requirements — Persistent Client Notes

- **FR-015**: System MUST provide a persistent notes field on the client record that carries across all quarters and sessions.
- **FR-016**: Persistent notes MUST be prominently displayed when a team member opens a client's BAS session — visible before session-specific details.
- **FR-017**: System MUST track who last edited a persistent note and when.
- **FR-018**: Persistent notes MUST coexist with existing session-specific notes. Both MUST be visible and clearly distinguished in the BAS session view.
- **FR-019**: System SHOULD maintain a change history for persistent notes (previous versions recoverable for audit purposes).

### Functional Requirements — Non-Xero Client Visibility

- **FR-020**: System MUST provide a way to add clients manually (not via Xero connection) with at minimum: name, ABN (optional), and accounting software type.
- **FR-021**: System MUST support the following accounting software types: Xero, QuickBooks, MYOB, email-based, other, unknown.
- **FR-022**: Non-Xero clients MUST appear on the dashboard alongside Xero-connected clients with a clear visual indicator of their connection status.
- **FR-023**: Non-Xero clients MUST support all practice management features: team assignment, exclusion, persistent notes.
- **FR-024**: Non-Xero clients MUST support manual BAS status progression (manual override of workflow stages) since auto-derived readiness is not available.
- **FR-025**: System SHOULD detect when a manually-added client matches an incoming Xero connection (by ABN) and offer to link them rather than creating a duplicate.

### Functional Requirements — Smarter Readiness Signals

- **FR-026**: System MUST include unreconciled bank transaction count in the readiness status derivation.
- **FR-027**: System MUST show clients with a significant number of unreconciled transactions (default threshold: more than 5) as "Needs Review" rather than "Ready", regardless of other readiness criteria.
- **FR-028**: System MUST display unreconciled transaction count as a visible data point on the dashboard client table.
- **FR-029**: System SHOULD surface clients with high unreconciled counts in the "Attention Needed" insight cards on the dashboard.

---

### Key Entities

- **Client** (extended): The core client record for the practice. Gains team member assignment (persistent), persistent notes, and accounting software type. Serves as the anchor for both Xero-connected and manually-added clients. Belongs to a tenant. Has one optional Xero connection.
- **Client Quarter Exclusion**: A per-quarter record linking a client to a specific quarter with an exclusion status and optional reason. Allows the same client to be excluded in one quarter and active in the next. Belongs to a tenant.
- **Practice User** (existing): Team members within the practice with roles (admin, accountant, staff). Referenced by client assignment.
- **Client Note History**: A record of changes to persistent client notes, capturing who changed what and when. Supports audit requirements for compliance.

---

## Auditing & Compliance Checklist

### Audit Events Required

- [ ] **Authentication Events**: No — this feature does not change authentication or authorization.
- [ ] **Data Access Events**: No — no new sensitive data types introduced (no TFN, no bank details).
- [x] **Data Modification Events**: Yes — team assignment changes, exclusion status changes, client note edits, manual client creation.
- [ ] **Integration Events**: No — no new external system integrations.
- [x] **Compliance Events**: Yes — exclusion of a client from BAS obligations for a quarter has compliance implications (ensures it was a deliberate decision, not an oversight).

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| client.assigned | Team member assignment changed | Client ID, previous assignee, new assignee, changed by | 7 years | None |
| client.exclusion.created | Client excluded for a quarter | Client ID, quarter, reason, excluded by | 7 years | None |
| client.exclusion.reversed | Client exclusion reversed | Client ID, quarter, reversed by, original reason | 7 years | None |
| client.notes.updated | Persistent note edited | Client ID, previous note content, new note content, edited by | 7 years | None |
| client.created_manual | Non-Xero client added manually | Client ID, name, ABN, software type, created by | 7 years | None |
| client.merged | Manual client linked to Xero connection | Client ID, Xero connection ID, matched by (ABN/name), merged by | 7 years | None |

### Compliance Considerations

- **ATO Requirements**: Client exclusion from BAS obligations must be auditable — the ATO may ask why a client did not lodge. The exclusion reason and timestamp provide the audit trail.
- **Data Retention**: Standard 7-year retention for all events. No extended retention needed.
- **Access Logging**: All practice users within the tenant can view audit logs for their clients. No cross-tenant access.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: An accountant managing 280 clients can identify and open their personally assigned clients within 10 seconds of logging in (via "My Clients" default filter).
- **SC-002**: Excluding clients that don't need BAS reduces the active working list by the expected proportion (e.g., if 40 of 280 clients are excluded, the dashboard shows ~240 active clients with accurate summary totals).
- **SC-003**: A team member opening a client's BAS session sees persistent client instructions without needing to ask the practice owner — reducing internal "how do I handle this client?" queries.
- **SC-004**: The dashboard shows 100% of the practice's clients (both Xero-connected and non-Xero) — no clients exist only in a spreadsheet.
- **SC-005**: Zero clients are falsely shown as "Ready" when they have more than 5 unreconciled bank transactions.
- **SC-006**: The practice owner can state "I no longer need my BAS workflow Excel spreadsheet" for daily triage and team coordination.

---

## Assumptions

- **Assignment is primarily permanent**: Team member assignment lives on the client record (not per-quarter). Vik's allocation is mostly stable with rare overrides. Per-quarter assignment overrides can be a future enhancement if needed.
- **Non-Xero clients are added manually**: Since we are not building QuickBooks/MYOB integrations, non-Xero clients enter via a manual "add client" form. CSV import for bulk addition of non-Xero clients is a potential future enhancement but not in this scope.
- **Reconciliation threshold is a sensible default**: The default of >5 unreconciled transactions is based on the brief's suggestion. This is not configurable in this scope but can be made configurable later.
- **PracticeUser identity display**: Team members are displayed by their name (from the identity provider) or email as a fallback. No new "display name" field is added in this scope.
- **Existing dashboard structure is preserved**: The new features extend the existing dashboard (new columns, new filters, new summary data) rather than replacing it with a fundamentally different design.
