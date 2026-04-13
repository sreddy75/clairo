# Feature Specification: BAS Transaction Grouping by Xero Reconciliation Status

**Feature Branch**: `057-bas-parked-reconciled`
**Created**: 2026-04-13
**Status**: Draft
**Input**: User description: "can we map all the xero unreconciled transaction in the BAS section as 'Parked' and all the other reconciled in a collapsable 'Reconciled' section"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unreconciled Transactions Auto-Parked (Priority: P1)

As an accountant viewing the BAS transaction list for a client, I want unreconciled Xero transactions to automatically appear in the "Parked" section so that I immediately know which transactions still need attention without manually triaging each one.

When a BAS session loads, each transaction's reconciliation status is read from Xero data. Transactions that Xero has not yet reconciled (not matched to a bank statement line) are automatically placed in the Parked state. The accountant can then act on each parked transaction — Approve, Override, or leave it Parked.

**Why this priority**: This is the core request. It eliminates manual triage — accountants currently have to scan the full transaction list to identify what needs work. Unreconciled = not yet matched in Xero = needs attention.

**Independent Test**: Can be tested by loading a BAS session for a client that has both reconciled and unreconciled transactions in Xero; verify that all unreconciled transactions appear in the "Parked" section on initial load, without any manual action.

**Acceptance Scenarios**:

1. **Given** a BAS session is loaded for a client with Xero data, **When** the transactions are displayed, **Then** all transactions whose Xero reconciliation status is "unreconciled" appear automatically in the "Parked" section.
2. **Given** a transaction is unreconciled at sync time and therefore auto-parked, **When** the accountant approves or overrides it, **Then** the transaction moves to the Approved/Overridden state and is no longer shown in the Parked section.
3. **Given** a transaction was auto-parked due to being unreconciled, **When** the accountant views it in the Parked section, **Then** a visible indicator (e.g., "Unreconciled in Xero") explains why it was parked — distinguishing auto-parked from manually parked items.
4. **Given** a BAS session was created before this feature shipped and already has manually parked items, **When** those items are displayed, **Then** they continue to appear in the Parked section with no change to their existing state.

---

### User Story 2 - Reconciled Transactions in Collapsible Section (Priority: P1)

As an accountant viewing the BAS transaction list, I want reconciled Xero transactions to appear in a collapsible "Reconciled" section that is collapsed by default so that my view is focused on work that needs attention and I can still access reconciled items when needed.

Reconciled transactions in Xero have been matched to bank statement lines. These are lower-priority for review — they already have tax codes in Xero and are likely correct. The collapsible section keeps them accessible without cluttering the primary workflow.

**Why this priority**: Equal priority to User Story 1 — both are needed together for the grouping to work. Without the collapsible Reconciled section, reconciled transactions have no home in the layout.

**Independent Test**: Can be tested by opening a BAS session with reconciled transactions and verifying they appear in a collapsed "Reconciled" section at the bottom of the page. Clicking to expand shows all reconciled items.

**Acceptance Scenarios**:

1. **Given** a BAS session with both reconciled and unreconciled transactions, **When** the page loads, **Then** a "Reconciled" section appears below the active transaction list, collapsed by default, showing a count of reconciled transactions.
2. **Given** the "Reconciled" section is collapsed, **When** the accountant clicks to expand it, **Then** all reconciled transactions are shown with their current tax codes and status.
3. **Given** the "Reconciled" section is expanded, **When** the accountant collapses it, **Then** it returns to the collapsed state and their scroll position in the main list is preserved.
4. **Given** a reconciled transaction has a tax code discrepancy detected by Clairo, **When** it appears in the Reconciled section, **Then** a warning indicator is shown on the section header (e.g., "Reconciled (47 — 2 need review)") so the accountant knows to check.
5. **Given** all transactions in the BAS session are reconciled, **When** the page loads, **Then** the Reconciled section is still shown (collapsed) with a message ("All transactions are reconciled in Xero") so the accountant understands the full state.

---

### User Story 3 - Refresh Reconciliation Status (Priority: P2)

As an accountant working on a BAS session, I want to refresh the Xero reconciliation status during my session so that transactions reconciled in Xero after the last sync are reclassified immediately without waiting for the next scheduled sync.

Xero reconciliation happens continuously throughout the period as bank feeds are processed. An accountant may reconcile several transactions in Xero and then return to Clairo — a refresh lets them see the updated grouping without triggering a full Xero re-sync.

**Why this priority**: P2 because the scheduled sync already handles this eventually. The manual refresh is a convenience for accountants actively working across both Clairo and Xero simultaneously.

**Independent Test**: Can be tested by reconciling a transaction in Xero while a Clairo BAS session is open, clicking "Refresh reconciliation status", and verifying the transaction moves from the Parked section to the Reconciled section.

**Acceptance Scenarios**:

1. **Given** a BAS session is open and the accountant has reconciled additional transactions in Xero, **When** the accountant clicks "Refresh reconciliation status", **Then** the reconciliation status of all transactions is re-fetched from Xero and the sections are updated accordingly.
2. **Given** a transaction was auto-parked (unreconciled) and the accountant has now reconciled it in Xero, **When** the refresh completes, **Then** the transaction moves from the Parked section to the Reconciled section.
3. **Given** the refresh is triggered while the accountant has unsaved pending changes, **When** the refresh completes, **Then** the pending changes are preserved and not overwritten.
4. **Given** the Xero connection is expired or unavailable, **When** the accountant clicks refresh, **Then** a clear message is shown ("Unable to refresh — Xero connection unavailable") and the current grouping remains unchanged.

---

### Edge Cases

- What happens when a transaction has no Xero reconciliation data (e.g., manually entered transactions)? Transactions without a Xero reconciliation flag are treated as unreconciled and placed in the Parked section by default.
- What happens when an accountant manually parks a reconciled transaction? The manual park action takes precedence — the transaction moves to the Parked section regardless of Xero's reconciliation status.
- What happens when a reconciled transaction has no tax code? It appears in the Reconciled section with a warning indicator ("Missing tax code") so the accountant knows to review it.
- What happens when the BAS session has already been submitted/approved? The grouping display is read-only; no move actions are available.
- What happens when Xero has a very large number of reconciled transactions? The Reconciled section uses pagination or virtual scrolling — expanding the section does not render all items simultaneously. The count in the header is always exact.
- What happens when a transaction is reconciled between BAS session creation and when it is opened? The reconciliation status shown reflects the most recent Xero data available at session load time.
- What happens to manually parked items from the prior workflow (spec 056)? Auto-parked (unreconciled) and manually parked items co-exist in the same Parked section but are visually distinguishable by a label ("Unreconciled in Xero" vs no label for manually parked).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST read the Xero reconciliation status (`IsReconciled`) from Xero bank transaction data during BAS session load and persist it alongside each transaction record.
- **FR-002**: System MUST automatically place all transactions where `IsReconciled = false` into the Parked state when they are first added to a BAS session, unless the accountant has already acted on that transaction.
- **FR-003**: System MUST NOT override an accountant's manual action (Approve, Override, or explicit Park) with the auto-park logic — the accountant's action is the authoritative state.
- **FR-004**: System MUST display a visual label on auto-parked transactions ("Unreconciled in Xero") to distinguish them from manually parked items.
- **FR-005**: System MUST display all reconciled transactions in a collapsible "Reconciled" section that is collapsed by default on page load.
- **FR-006**: System MUST show the count of reconciled transactions in the section header when collapsed (e.g., "Reconciled (47)").
- **FR-007**: System MUST show a warning count in the Reconciled section header when any reconciled transaction has a detected tax code issue (e.g., "Reconciled (47 — 2 need review)").
- **FR-008**: System MUST preserve the collapsed/expanded state of the Reconciled section within the browser session (resets to collapsed on page reload).
- **FR-009**: System MUST provide a "Refresh reconciliation status" action that re-fetches Xero reconciliation data for all transactions in the current BAS session.
- **FR-010**: System MUST update the Parked and Reconciled sections after a successful refresh, moving transactions between sections if their reconciliation status has changed in Xero since the last sync.
- **FR-011**: System MUST preserve all accountant-made decisions (Approved, Overridden, manually Parked) when refreshing — only auto-parked transactions that have not been acted on may be automatically reclassified.
- **FR-012**: System MUST gracefully handle Xero unavailability during refresh — the current session state must remain intact and the accountant must be informed the refresh failed.
- **FR-013**: System MUST apply this grouping logic consistently for all BAS sessions, including sessions created before this feature is deployed (where existing manual actions are respected).

### Key Entities

- **Transaction Reconciliation Status**: A flag on each Xero bank transaction indicating whether it has been matched to a bank statement line in Xero. Source: Xero `BankTransaction.IsReconciled`. Drives initial grouping at session load time and after a manual refresh.
- **Auto-Parked Transaction**: A transaction placed in the Parked state automatically because it was unreconciled in Xero at session load or refresh time, and has not yet been acted on by the accountant. Can be reclassified by a refresh if Xero status changes.
- **Reconciled Section**: A collapsible UI grouping within the BAS transaction view containing all transactions reconciled in Xero that have not been manually moved by the accountant. Collapsed by default; shows count and warning indicators in its header.

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [ ] **Authentication Events**: No — no auth changes.
- [ ] **Data Access Events**: No sensitive data read (no TFN/bank details beyond existing BAS data).
- [x] **Data Modification Events**: Yes — auto-parked state is written on transaction records; refresh changes grouping state.
- [x] **Integration Events**: Yes — reconciliation status is fetched from Xero; refresh action calls Xero API.
- [x] **Compliance Events**: Yes — transaction grouping directly affects which transactions receive tax code attention before BAS lodgement.

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| transaction.auto_parked | Transaction placed in Parked state at BAS session load due to Xero unreconciled status | session_id, transaction_id, reason="auto_parked_unreconciled" | 7 years | None |
| transaction.reconciliation_refreshed | Accountant triggers a reconciliation status refresh | session_id, transactions_reclassified_count, refresh_source="manual" | 7 years | None |
| transaction.moved_to_reconciled | Transaction moves from Parked to Reconciled after a refresh | session_id, transaction_id, previous_state="auto_parked" | 7 years | None |

### Compliance Considerations

- **ATO Requirements**: Ensuring unreconciled transactions receive explicit accountant attention (via the Parked state) before BAS lodgement strengthens the audit trail — unreconciled transactions are surfaced, not buried.
- **Data Retention**: Reconciliation status and auto-park events follow the standard 7-year ATO retention.
- **Access Logging**: Auto-park events are visible to all users with access to the BAS session within the tenant.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All unreconciled Xero transactions appear in the Parked section automatically on BAS session load — zero manual triage required to identify them.
- **SC-002**: The Reconciled section is visible and collapsed by default within 2 seconds of the BAS page loading, without blocking the display of active (unreconciled) transactions.
- **SC-003**: Accountants can expand the Reconciled section and locate any specific reconciled transaction without a full page reload.
- **SC-004**: After a reconciliation status refresh, reclassified transactions move between sections within 5 seconds and all prior accountant decisions are preserved intact.
- **SC-005**: Accountants can distinguish auto-parked (unreconciled) transactions from manually parked transactions at a glance without opening the transaction detail.

## Assumptions

- Xero's `BankTransaction.IsReconciled` field is already available in the synced Xero data stored in Clairo, or can be added to the Xero sync without a structural change to the sync architecture. Surfacing this field is in scope if it is not currently captured.
- The "Parked" concept aligns with the Parked state introduced in spec 056 (dismissed/parked tax code suggestions). Auto-parked transactions co-exist with manually parked items in the same Parked section.
- Reconciliation status applies to `BankTransaction` records only. Invoices and credit notes are not reconciled/unreconciled in the Xero sense and are excluded from auto-park logic.
- The collapsible Reconciled section replaces the current flat/mixed display of reconciled transactions in the BAS transaction list.
- Auto-park applies only on first encounter (session load or refresh for items with no prior accountant action) — once an accountant has acted on a transaction, the auto-park logic does not re-apply to that transaction.
