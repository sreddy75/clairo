# Feature Specification: BAS UX Polish & Xero Status Sync

**Feature Branch**: `056-bas-ux-xero-status`
**Created**: 2026-04-10
**Status**: Draft
**Input**: User description: "Remove Reject action, keep Dismiss, add per-transaction notes with optional Xero sync, read BAS status from Xero for state mismatch detection"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Remove Reject Action from Tax Code Suggestions (Priority: P1)

As an accountant reviewing tax code suggestions for a BAS session, I want the "Reject" button removed from the suggestion actions so that the interface is simpler and I only need to choose between Approve, Override, or Park it.

Currently there are four actions: Approve, Reject, Override, Dismiss. "Reject" and "Dismiss" are confusingly similar — both leave the transaction excluded. The "Reject" action is removed entirely, and the dismiss action is relabelled to "Park it" — meaning "I don't want to deal with this suggestion right now, park it for later." Parked items appear in a dedicated "Parked" section, where the accountant can later "Approve" them or move them "Back to Manual" (returning them to the pending/manual review state).

**Why this priority**: Simplifies the core review workflow and removes user confusion between two nearly identical negative actions. Every accountant using the tax code resolution flow encounters this friction.

**Independent Test**: Can be tested by opening any BAS session with tax code suggestions and verifying only three action buttons appear (Approve, Override, Park it) with no "Reject" option anywhere in the UI or API. Parked items should appear in a dedicated "Parked" section with "Approve" and "Back to Manual" actions.

**Acceptance Scenarios**:

1. **Given** a BAS session with pending tax code suggestions, **When** the accountant views the suggestion actions, **Then** only Approve, Override, and "Park it" buttons are shown — no Reject button exists.
2. **Given** existing suggestions that were previously rejected (status = "rejected"), **When** the accountant views the resolved section, **Then** those suggestions display as "Parked" and are treated identically to parked (dismissed) suggestions.
3. **Given** the API endpoint `/reject` for suggestions, **When** any client calls it, **Then** it still functions but internally maps to the dismiss/park action (backward compatibility for any in-flight requests during deployment).
4. **Given** a suggestion in the "Parked" section, **When** the accountant clicks "Approve", **Then** the suggestion is approved with the AI-suggested tax code.
5. **Given** a suggestion in the "Parked" section, **When** the accountant clicks "Back to Manual", **Then** the suggestion is returned to the pending state for manual review.

---

### User Story 2 - Per-Transaction Notes on Suggestions (Priority: P1)

As an accountant reviewing tax code suggestions, I want to add, view, and edit a free-text note on each transaction/suggestion so that I can record my reasoning, flag items for follow-up, or leave context for colleagues.

Notes are already partially supported in the system (agent transaction notes exist for classification requests). This extends the concept to the tax code suggestion flow. Notes are visible inline in the suggestion table row and can be added/edited without navigating away.

**Why this priority**: Accountants frequently need to annotate decisions for audit trail and team communication. This is the most-requested workflow improvement alongside removing Reject.

**Independent Test**: Can be tested by opening a BAS session, clicking a note icon on any suggestion row, typing a note, saving, and confirming it persists on page reload.

**Acceptance Scenarios**:

1. **Given** a tax code suggestion row (any status), **When** the accountant clicks the notes icon, **Then** an inline note editor appears where they can type and save a note. When dismissing, the note field doubles as the dismiss reason.
2. **Given** a suggestion with an existing note, **When** the accountant views the suggestion table, **Then** a visual indicator (icon) shows that a note exists, and the note text is visible on hover or click.
3. **Given** a saved note, **When** the accountant edits and saves the note again, **Then** the updated text replaces the previous note.
4. **Given** a suggestion with a note, **When** the BAS session is exported or audited, **Then** the note is included in the audit trail.

---

### User Story 3 - Sync Notes to Xero via History & Notes API (Priority: P2)

As an accountant, I want the option to push my transaction notes to Xero so that the context I add in Clairo is also visible in Xero's transaction history for my team members who work directly in Xero.

Xero's Accounting API provides a History & Notes endpoint that allows adding notes to bank transactions, invoices, and credit notes. When the accountant writes a note on a suggestion, they can optionally choose to sync it to Xero. The note appears in Xero's "History & Notes" tab for that transaction.

**Why this priority**: Nice-to-have that adds cross-platform value. Depends on User Story 2 (notes must exist before they can be synced). Not all accountants need this — some only work in Clairo.

**Independent Test**: Can be tested by adding a note to a suggestion, enabling Xero sync, and verifying the note appears in Xero's History & Notes for the corresponding transaction.

**Acceptance Scenarios**:

1. **Given** a suggestion note, **When** the accountant saves it with the "Sync to Xero" option enabled, **Then** the note is pushed to Xero's History & Notes endpoint for the corresponding transaction on a fire-and-forget basis.
2. **Given** a Xero sync attempt fails (network error, auth expired), **Then** the failure is logged but no persistent error state is stored — the user is not blocked or alerted.
3. **Given** a suggestion for a transaction type that does not support Xero History & Notes, **When** the user tries to enable sync, **Then** the sync option is hidden or disabled with an explanation.

---

### User Story 4 - Xero BAS Cross-Check on Tab Load (Priority: P2)

As an accountant opening the BAS tab for a client, I want to see whether a BAS report exists in Xero for the same period, and if so, see a quick comparison of Xero's key BAS figures against Clairo's calculated figures so I can spot discrepancies before lodging.

When the BAS tab loads, Clairo fetches the BAS report from Xero for the matching period. If a report exists, a compact info panel shows:
- **That a BAS report exists in Xero** for this period (this alone is useful — it tells the accountant the period has been touched in Xero).
- **Key figure comparison**: Xero's 1A (GST on sales) vs Clairo's 1A, Xero's 1B (GST on purchases) vs Clairo's 1B, and net GST — so the accountant can eyeball whether numbers align.

**Note**: Xero's API does not expose a BAS "lodgement status" or "filed/draft" flag. The report endpoint returns dollar amounts only. This feature shows what Xero has, not whether it's been lodged.

**Why this priority**: Gives accountants a quick sanity check against Xero's data without switching apps. However, it's P2 because it adds a Xero API call on tab load and the comparison is informational only — it doesn't block any workflow.

**Independent Test**: Can be tested by opening the BAS tab for a client that has a BAS report in Xero for the same period, and verifying the cross-check panel appears with Xero's figures alongside Clairo's.

**Acceptance Scenarios**:

1. **Given** a BAS session in Clairo with a calculation, **When** the BAS tab loads and Xero has a BAS report for the same period, **Then** an info panel shows "Xero BAS data found for this period" with a side-by-side of key figures (1A, 1B, net GST).
2. **Given** a BAS session in Clairo, **When** the BAS tab loads and Xero has no BAS report for the period, **Then** the info panel shows "No BAS report found in Xero for this period" (neutral, not a warning).
3. **Given** the Xero figures differ materially from Clairo's figures (e.g., more than $1 difference on any key field), **When** the cross-check panel is displayed, **Then** differing values are highlighted in amber so the accountant notices them.
4. **Given** a Xero API call fails (auth expired, rate limited, timeout), **When** the BAS tab loads, **Then** the BAS tab loads normally without the cross-check panel, and a subtle message notes that Xero data could not be fetched.
5. **Given** the cross-check panel is displayed, **When** the accountant clicks "Dismiss", **Then** the panel is hidden for this session until the page is reloaded.

---

### Edge Cases

- What happens when a suggestion was rejected before this change? Existing "rejected" status records are treated as "parked" in the UI. The database column retains the original value for audit purposes; the display layer maps both to "Parked."
- What happens when an accountant tries to add a very long note? Notes are limited to 2,000 characters. The UI shows a character counter and prevents submission beyond the limit.
- What happens when Xero History & Notes has a different character limit? Xero's History & Notes `Details` field is limited to 450 characters. If the Clairo note exceeds this, only the first 447 characters are synced to Xero with a "..." suffix.
- What happens when the Xero connection is disconnected? The Xero sync option and BAS status check are hidden. Notes still work locally.
- What happens when multiple BAS periods exist for the same quarter? The cross-check compares based on the period start/end dates, not session names.
- What happens when Xero doesn't have a BAS report for the period? The panel shows "No BAS report found in Xero for this period" — neutral, not a warning.
- What happens when Clairo has no calculation yet? The cross-check panel shows Xero's figures only, with a note that Clairo hasn't calculated yet so no comparison is possible.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST remove the "Reject" action from all tax code suggestion interfaces (suggestion cards, suggestion tables, bulk actions).
- **FR-002**: System MUST treat existing "rejected" status suggestions identically to "dismissed" in all display contexts.
- **FR-003**: System MUST provide a note field on each tax code suggestion that supports free-text input up to 2,000 characters.
- **FR-004**: System MUST display a visual indicator on suggestion rows that have notes attached.
- **FR-005**: System MUST persist notes with the suggestion record. Any tenant user with BAS session access can create or edit any note; the audit trail captures the acting user.
- **FR-006**: System MUST include suggestion notes in the BAS session audit trail.
- **FR-007**: System MUST provide an optional "Sync to Xero" toggle when saving a note, for suggestions linked to transaction types that support Xero's History & Notes API.
- **FR-008**: System MUST push the note text to Xero's History & Notes endpoint on a fire-and-forget basis when sync is enabled, truncating to 450 characters if necessary. No persistent sync status is tracked (no `note_xero_sync_status` column).
- **FR-009**: System MUST provide a "Parked" section showing all parked (dismissed) suggestions, with "Approve" and "Back to Manual" (unpark) actions on each item.
- **FR-010**: System MUST fetch the BAS report from Xero for the matching period when the BAS tab loads for a client.
- **FR-011**: System MUST display a cross-check info panel showing whether a Xero BAS report exists for the period, and if so, show key figures (1A GST on sales, 1B GST on purchases, net GST) side-by-side with Clairo's calculated values.
- **FR-012**: System MUST highlight values that differ materially (more than $1) between Xero and Clairo.
- **FR-013**: System MUST gracefully handle Xero API failures without blocking the BAS tab from loading.
- **FR-014**: System MUST allow the cross-check panel to be dismissed for the current browser session.

### Key Entities

- **SuggestionNote**: A free-text annotation on a tax code suggestion. Contains note text, author, and timestamps. One note per suggestion (upsert model). When dismissing a suggestion, the note field serves as the dismiss reason — replacing the separate `dismissal_reason` field.
- **Xero BAS Report Snapshot**: Key BAS figures (1A, 1B, net GST) fetched from Xero's BAS report for a given period. Used for cross-check comparison only — not persisted long-term.

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [ ] **Authentication Events**: No — no auth changes.
- [x] **Data Access Events**: No sensitive data read (no TFN/bank details).
- [x] **Data Modification Events**: Yes — notes are created/edited on financial data suggestions; reject status is remapped.
- [x] **Integration Events**: Yes — notes synced to Xero; BAS status fetched from Xero.
- [x] **Compliance Events**: Yes — BAS status mismatch detection directly affects compliance workflow.

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| suggestion.note_created | Note saved on a suggestion | suggestion_id, note_text, author_id, synced_to_xero | 7 years | None |
| suggestion.note_updated | Note edited | suggestion_id, old_text, new_text, author_id | 7 years | None |
| suggestion.note_xero_synced | Note push attempted to Xero (fire-and-forget) | suggestion_id, xero_transaction_id, success | 7 years | None |
| bas.xero_crosscheck | BAS tab loaded with Xero comparison | session_id, xero_report_found, figures_match, xero_1a, xero_1b, clairo_1a, clairo_1b | 7 years | None |

### Compliance Considerations

- **ATO Requirements**: Notes provide additional audit trail evidence for tax code decisions, supporting ATO review requirements. The BAS status mismatch detection helps prevent compliance errors.
- **Data Retention**: Notes follow standard 7-year ATO retention. Xero sync is a copy — Clairo retains the authoritative record.
- **Access Logging**: Notes and mismatch events are visible to all users with access to the BAS session within the tenant.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Accountants can review and act on tax code suggestions using only three actions (Approve, Override, Park it) — the Reject option is no longer present anywhere in the workflow. Parked items appear in a dedicated "Parked" section with "Approve" and "Back to Manual" actions.
- **SC-002**: Accountants can add a note to any suggestion in under 5 seconds without navigating away from the review screen.
- **SC-003**: Notes synced to Xero are dispatched to Xero's History & Notes endpoint on a fire-and-forget basis when saving.
- **SC-004**: Xero BAS cross-check panel is displayed within 3 seconds of the BAS tab loading, without delaying the rest of the tab content.
- **SC-005**: Material differences (>$1) between Xero and Clairo BAS figures are visually highlighted so the accountant notices them at a glance.

## Clarifications

### Session 2026-04-10

- Q: Can any tenant user edit another accountant's note, or only the original author? → A: Any tenant user with BAS access can edit any note.
- Q: Should the existing dismiss reason field be merged into the new notes feature? → A: Yes, merge them. Dismissing uses the note field as the reason — one field, not two.

## Assumptions

- Xero's History & Notes API supports BankTransactions, Invoices, and CreditNotes — the three source types used by tax code suggestions.
- Xero does NOT expose a BAS lodgement/filing status. The `GET /Reports/BAS` endpoint returns financial data (amounts per BAS label) only. The cross-check shows whether a report exists and compares key figures — it does not indicate lodgement status.
- The `rejected` status enum value is retained in the database for backward compatibility; no data migration is needed.
- Notes are per-suggestion, not per-transaction — if a transaction has multiple line items with separate suggestions, each gets its own note.
