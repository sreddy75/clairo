# Feature Specification: Xero Tax Code Write-Back

**Feature Branch**: `049-xero-taxcode-sync`
**Created**: 2026-03-30
**Status**: Draft
**Input**: After the client reviews tax_code_suggestions and they are approved by the tax agent, the approved tax codes need to be synced back to Xero.

## Context & Background

This feature is the second part of the AI Tax Code Resolution workflow introduced in spec `046-ai-tax-code-resolution`. Spec 046 deliberately deferred Xero write-back to a future version, noting: *"Xero write-back is explicitly deferred to a future version (v2). For v1, all tax code changes are applied locally only."*

The existing workflow (046) produces `TaxCodeSuggestion` and `TaxCodeOverride` records. When an accountant approves a suggestion, the override is stored locally in Clairo but the source transaction in Xero still carries the original (incorrect) tax code. This means:
- The BAS figures are correct in Clairo but Xero is out of sync
- Future Xero syncs could re-introduce the old (incorrect) tax codes
- The accountant's practice does not benefit from the corrections in Xero for non-BAS purposes (e.g., Xero reporting, client bookkeeping view)

This feature closes that gap by writing the approved tax codes back to Xero, making Xero the source of truth once again.

This spec also refines the client-facing review workflow introduced in spec `047-client-transaction-classification`, adding two changes to the client portal and two to the agent side that are required for the full loop to function correctly before write-back occurs.

### Xero API Writeback — Technical Analysis

**Authentication**: The `accounting.transactions` OAuth scope is already requested during Xero connection setup. This scope covers both read and write access to invoices, bank transactions, and credit notes. **No re-authorization or scope change is required.**

**Xero write endpoints**:
- Invoices: `POST /Invoices/{InvoiceID}` with updated `LineItems` array containing `TaxType`
- Bank Transactions: `POST /BankTransactions/{BankTransactionID}` with updated `LineItems`
- Credit Notes: `POST /CreditNotes/{CreditNoteID}` with updated `LineItems`

**Critical constraint — full document required**: Xero requires the full line items array to be sent on update (not a partial patch). The system must reconstruct the full document with only the target line item(s) modified.

**Editability constraints** (transactions that cannot be updated in Xero):
- `VOIDED` or `DELETED` invoices/credit notes — Xero rejects all edits
- `PAID` invoices where a payment has been fully applied and the period is locked
- `AUTHORISED` invoices with payments or credit notes already allocated — Xero rejects line item modification
- Transactions falling within Xero's locked accounting period (set by the practice in Xero)
- Bank transactions where `IsReconciled` is `true` — Xero rejects financial field changes

**Rate limits**: 60 API calls per minute and 5,000 per day per connected Xero organisation. Writing back one invoice = one API call, regardless of how many line items changed on that invoice. The system should batch changes per-document (not per-line-item) and queue writes to respect rate limits.

---

## Clarifications

### Session 2026-03-31

- Q: Should there be a hard cap on how many times an agent can send a transaction back to the client? → A: Unlimited — no system-enforced cap; agent can send back as many times as needed and can override directly at any point.
- Q: Does a send-back reuse the existing ClassificationRequest/link, or create a new one? → A: New ClassificationRequest with a new single-use magic link each time — required by security (single-use links). Original link is never reused. Each round has its own request linked via `parent_request_id`.
- Q: Can the client save progress on "I don't know" without a description and return later? → A: No save-and-return feature exists and none will be added. Client must complete all answers in one session. All save/restore references removed from spec.
- Q: Which term is canonical for the practice-side user — "tax agent" or "accountant"? → A: "Tax agent" is canonical in all requirements and user stories (ATO official term). "Accountant" is used only in client-facing UI copy (e.g., "Your accountant says:").
- Q: How should the tax agent be notified when a client responds to a returned item after the tax agent has already overridden it? → A: In-app indicator only (badge/flag on the overridden item in the review screen). No email. Client response is recorded in audit trail regardless.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Sync Approved Tax Codes to Xero (Priority: P1)

After approving tax code suggestions for a BAS session, the tax agent initiates a "Sync to Xero" action. The system writes all approved tax codes back to the corresponding invoices, bank transactions, and credit notes in Xero. The tax agent sees a clear progress report showing which items synced successfully.

**Why this priority**: This is the core feature. Without it, Xero remains out of sync and future re-syncs can silently undo the tax agent's approved corrections.

**Independent Test**: Can be fully tested by approving tax code suggestions in a BAS session, triggering sync to Xero, and verifying via the Xero UI (or API) that the targeted invoices and transactions now carry the corrected tax type.

**Acceptance Scenarios**:

1. **Given** a BAS session where several tax code suggestions have been approved, **When** the tax agent clicks "Sync to Xero", **Then** the system writes the corrected tax type back to each source document in Xero (invoice, bank transaction, or credit note) and the sync completes with a summary showing counts of successful, failed, and skipped items.
2. **Given** a BAS session where all suggestions are still in "pending" state (none approved), **When** the tax agent attempts to trigger sync, **Then** the system informs them that there is nothing to sync (zero approved overrides exist).
3. **Given** a sync that completes successfully, **When** a Xero re-sync is performed, **Then** the incoming data from Xero now reflects the corrected tax codes, and no new conflicts are detected for the synced items.
4. **Given** the system is constructing an update for an invoice with three line items where only line item index 1 needs a tax code change, **When** it sends the update to Xero, **Then** line items 0 and 2 are unchanged and only line item 1 has its TaxType updated.

---

### User Story 2 — Handle Non-Editable Transactions Gracefully (Priority: P1)

During writeback, some transactions may be locked in Xero (voided, paid with locked period, or within the practice's locked accounting date). The system detects these before attempting to write and reports them clearly so the tax agent can take action in Xero directly.

**Why this priority**: Attempting to write to locked transactions will always fail. Surfacing these upfront (rather than silent failures) is essential for the tax agent to trust the sync process.

**Independent Test**: Can be tested by attempting a write-back on an invoice that is VOIDED in Xero and verifying the item is reported as "skipped — locked or voided" without causing the overall sync job to fail.

**Acceptance Scenarios**:

1. **Given** a batch of items to write back where one invoice is VOIDED in Xero, **When** the sync runs, **Then** that item is marked "skipped — not editable in Xero" and all other eligible items continue to be written.
2. **Given** a transaction that falls within Xero's locked accounting period, **When** the sync attempts to write to it, **Then** Xero returns an error, the system catches it, marks that item "skipped — period locked", and does not retry it.
3. **Given** the sync completes with some skipped items, **When** the tax agent views the sync result, **Then** they see each skipped item listed with its specific reason (voided, paid/locked, period-locked) and clear guidance that they must correct these directly in Xero.
4. **Given** an item was skipped because the period was locked, **When** the tax agent later unlocks the period in Xero and re-runs the sync for the same session, **Then** that item is retried and succeeds.

---

### User Story 3 — Sync Progress and Status Visibility (Priority: P2)

Writeback involves multiple sequential API calls and may take tens of seconds for large BAS sessions. The tax agent can see real-time progress during the sync and review a detailed outcome report afterwards.

**Why this priority**: For sessions with many excluded transactions, the sync could take 30-60 seconds. Without feedback the tax agent would not know if the operation is running or hung.

**Independent Test**: Can be tested by triggering a sync with 20+ items and verifying progress counts update during execution without requiring a page refresh.

**Acceptance Scenarios**:

1. **Given** a sync is in progress, **When** the tax agent watches the Resolved table, **Then** each approved/overridden row shows an inline "Syncing…" badge in its status column — no separate progress panel.
2. **Given** the sync completes, **When** the tax agent views the Resolved table, **Then** each row shows its final per-row Xero status badge (green "Xero ✓", amber "⚠ Skipped — [reason]", or red "Xero ✗"); a compact one-line retry row appears below the table if any items failed.
3. **Given** the sync has completed, **When** the tax agent navigates away and returns to the BAS session, **Then** each row still shows its Xero status badge and the retry row remains visible if failures exist.
4. **Given** a sync fails mid-way due to an unexpected error (e.g., token expiry), **When** the tax agent views the result, **Then** they see which items succeeded before the failure and which remain unsynced, with an option to retry.

---

### User Story 4 — Partial Retry for Failed Items (Priority: P2)

After a sync where some items failed, the tax agent can retry only the failed items without re-attempting items that already succeeded.

**Why this priority**: Retrying all items (including already-successful ones) would be redundant API calls and risks modifying Xero data unnecessarily. Targeted retry is the correct behaviour.

**Independent Test**: Can be tested by causing a deliberate failure for one item in a multi-item sync, then re-running sync and verifying only the previously failed item is retried.

**Acceptance Scenarios**:

1. **Given** a sync where 8 items succeeded and 2 failed, **When** the tax agent clicks "Retry Failed Items", **Then** only the 2 failed items are attempted — the 8 already-synced items are not touched.
2. **Given** all items in a session have been successfully synced, **When** the tax agent clicks "Sync to Xero" again, **Then** the system skips all already-synced items and reports "0 items to sync — all approved codes are already in Xero".
3. **Given** an item was previously synced successfully, **Then** it is never overwritten in a subsequent sync unless a new approval has been made in Clairo that differs from what was written.

---

### User Story 5 — Audit Trail for Xero Write-Backs (Priority: P1)

Every write to Xero is recorded in Clairo's audit log, capturing who triggered the sync, what was written, what Xero returned, and whether the write succeeded. This record satisfies ATO requirements for demonstrating that BAS figures can be traced back to source data in Xero.

**Why this priority**: ATO compliance requires a tamper-evident audit trail for all changes to BAS source data. Writing to Xero is a change to the underlying financial records.

**Independent Test**: Can be tested by triggering a sync and verifying the audit log contains an entry per document written, with before/after tax types, Xero document reference, user, and timestamp.

**Acceptance Scenarios**:

1. **Given** a sync that completes successfully, **When** the tax agent views the audit trail for the BAS session, **Then** an entry exists for each document written to Xero, showing: Xero document reference, document type, line item index, original tax type (before), new tax type (after), Clairo user who triggered the sync, and timestamp.
2. **Given** an item that was skipped (not editable), **When** the tax agent views the audit trail, **Then** the skip is recorded with the reason, so there is a clear explanation of why that document was not updated.
3. **Given** the sync was triggered by one tax agent but the suggestions were approved by a different one, **When** the audit trail is reviewed, **Then** both users are recorded: the approver (captured in the existing TaxCodeSuggestion record) and the sync initiator.

---

---

### User Story 6 — Client Must Describe "I Don't Know" Transactions (Priority: P1)

When a client selects "I don't know — ask my accountant" for a transaction in the portal, they are required to add a description explaining what they do know (e.g., the payee, the approximate purpose, anything they recall). This prevents the tax agent from receiving blank "I don't know" items with no context to work from.

**Why this priority**: A bare "I don't know" is as useless as no response. Even partial context — "I think it was for the work car" — allows the tax agent to make a judgement or ask a targeted follow-up. This is a direct requirement from the tax agents.

**Independent Test**: Can be tested by selecting "I don't know" on the client portal without entering a description and verifying the form prevents submission, showing a validation message on that item.

**Acceptance Scenarios**:

1. **Given** a client has selected "I don't know" for a transaction, **When** they attempt to move to the next item or submit, **Then** a validation message appears requiring them to add a description before proceeding.
2. **Given** a client has selected "I don't know" and entered a description, **When** they submit, **Then** the submission is accepted and the description is visible to the tax agent in their review screen.
3. **Given** a client selects any other category (not "I don't know"), **Then** the description field remains optional.

---

### User Story 7 — Client Must Answer Every Transaction Before Submitting (Priority: P1)

The client cannot submit the classification request while any transaction remains unanswered. Every transaction in the request must have at least a category selection (or "I don't know" with description) before the submit button becomes active.

**Why this priority**: Spec 047 allowed partial submissions, but this creates an incomplete audit trail and leaves the tax agent with unresolved items that delay BAS finalisation. The request is deliberately short (tax agent selects which transactions to send), so requiring a full response is reasonable.

**Independent Test**: Can be tested by loading a request with 5 transactions, answering only 4, and verifying the submit button is disabled and a counter shows "1 transaction still needs your answer".

**Acceptance Scenarios**:

1. **Given** a classification request with 8 transactions, **When** the client has answered 7 but not 8, **Then** the "Submit" button is disabled and the interface clearly indicates which transaction(s) remain unanswered.
2. **Given** a client has answered all transactions, **When** they press Submit, **Then** the submission proceeds immediately without additional prompts.
3. **Given** the client closes the portal mid-way without submitting, **When** they reopen the link, **Then** they must start again — there is no save-and-return. The link remains valid until expiry but progress is not persisted.

---

### User Story 8 — Agent Adds a Note When Sending Classification Request (Priority: P2)

When the tax agent creates a classification request and sends it to the client, they can add a per-transaction note for individual items (in addition to the existing global message). Per-transaction notes appear next to each transaction on the client's portal page to give context or guidance.

**Why this priority**: The agent often knows something about a transaction that would help the client respond correctly (e.g., "This was around the time you mentioned buying equipment"). Without this, the agent has no way to guide the client except a generic cover message.

**Independent Test**: Can be tested by an agent adding a note on a specific transaction before sending the request, then verifying the note appears next to that transaction on the client portal.

**Acceptance Scenarios**:

1. **Given** the agent is building a classification request, **When** they view the list of transactions to be sent, **Then** each transaction has an optional note field where the agent can type context for the client.
2. **Given** the agent has typed a note on a transaction, **When** the client opens the portal, **Then** the note appears visibly next to that transaction (e.g., "Your accountant says: This was charged to your business card on 14 Feb").
3. **Given** a transaction with no agent note, **When** the client views it, **Then** no note section is shown for that transaction (clean layout).
4. **Given** the agent leaves the global message field empty but fills per-transaction notes, **Then** only the per-transaction notes are shown; no empty global message banner is displayed.

---

### User Story 9 — Agent Sends "I Don't Know" Items Back to Client With Guidance (Priority: P1)

When the agent reviews the client's classification responses and sees items marked "I don't know", they can add a targeted comment to those specific items and send them back to the client for a further round of review. The system creates a new classification request (containing only the returned items) with a new single-use magic link. The client receives an email with the new link and responds via a fresh portal session.

**Why this priority**: "I don't know" items that reach the agent unresolved block BAS finalisation. The agent needs a structured way to send back targeted questions rather than making phone calls or sending generic emails.

**Independent Test**: Can be tested by having a client submit "I don't know" for a transaction, then having the agent add a comment and send it back. Verify the client receives a new email with a new magic link, and the portal session for that link shows only the returned item with the agent's comment.

**Acceptance Scenarios**:

1. **Given** the agent's review screen shows items where the client responded "I don't know", **When** the agent adds a comment to one of those items and clicks "Send Back to Client", **Then** the system creates a new `ClassificationRequest` for the returned items, generates a new single-use magic link, sends the client an email, and the client's new portal session shows only the returned items with the agent's comment visible.
2. **Given** a returned item, **When** the client views it, **Then** they see: their original response ("I don't know — [their description]"), and the agent's new comment below it, followed by the response field for them to answer again.
3. **Given** the client submits a revised response on a returned item, **When** the agent reviews again, **Then** the original "I don't know" response, the agent's comment, and the new client response are all visible in sequence (showing the conversation thread).
4. **Given** the agent decides an "I don't know" item does not need client input, **When** they override it with a tax code directly, **Then** the item is resolved and does not appear in any send-back to the client.
5. **Given** multiple "I don't know" items exist, **When** the agent reviews them, **Then** they can select a subset to send back (not forced to send all at once).

---

### User Story 10 — View and Assign Tax Codes per Line Item on Split Bank Transactions (Priority: P1)

Bank transactions in Xero can contain multiple line items (referred to as "splits"), each with its own amount, account code, and tax type. When a bank transaction has more than one line item, the tax agent must be able to see each individual split in the review UI and assign a separate tax code to each one. Without this, a sync would overwrite all line items with the same code, corrupting the multi-split structure.

**Why this priority**: Transactions with existing splits are already in Xero with distinct tax codes per split. Treating them as a single-code entity and syncing a single override destroys that distinction. This is a data integrity issue, not a convenience feature.

**Independent Test**: Can be tested by syncing a Xero bank transaction that has 3 line items with different amounts. Verify the review UI shows all 3 line items with their respective amounts and current tax types, and that the agent can set a different override code for each.

**Acceptance Scenarios**:

1. **Given** a bank transaction with 3 line items, **When** the tax agent views it in the tax code review screen, **Then** all 3 line items are visible individually with their amounts, descriptions, and current tax types — not collapsed into a single combined row.
2. **Given** a bank transaction with 3 line items, **When** the tax agent sets a tax code override for line item index 1, **Then** only that line item's tax type is changed at sync time — line items 0 and 2 retain their original tax types.
3. **Given** a bank transaction with a single line item, **When** the tax agent views it, **Then** no line item expansion is shown — the existing single-code assignment UI is used unchanged.
4. **Given** a multi-line bank transaction where the AI has suggested a tax code for the whole transaction, **When** the tax agent reviews it, **Then** the AI suggestion is shown as a starting point for each line item, and the agent can accept or override it independently per line item.

---

### User Story 11 — Create and Edit Splits on Bank Transactions (Priority: P2)

When a bank transaction has a single line item, the tax agent can split it into multiple line items — each with a specified amount and tax code. This allows a single transaction (e.g., a $1,200 supplier payment) to be correctly categorised across different tax treatments (e.g., $1,000 G11 for goods + $200 BASEXCLUDED for an insurance component). The system enforces that split amounts always sum to the original transaction total.

**Why this priority**: This is required when a single Xero bank transaction covers expenses with different GST treatments. Without this, the accountant must manually split the transaction in Xero first — removing a key workflow efficiency and requiring a round-trip outside Clairo.

**Independent Test**: Can be tested by splitting a single-line bank transaction of $1,200 into two splits ($800 G11, $400 BASEXCLUDED), syncing to Xero, and verifying the resulting Xero bank transaction has 2 line items with the correct amounts and tax types.

**Acceptance Scenarios**:

1. **Given** a single-line bank transaction, **When** the tax agent clicks "Add Split", **Then** a second line item row appears with an amount field (defaulting to the remainder needed to balance) and a tax code selector.
2. **Given** the tax agent has added splits, **When** the sum of split amounts does not equal the original transaction total, **Then** a validation message is shown and the agent cannot save or sync until the amounts balance.
3. **Given** the tax agent has created valid splits that sum to the original amount, **When** they sync to Xero, **Then** Xero's bank transaction is updated with the specified line items carrying the correct amounts and tax types.
4. **Given** a bank transaction with existing splits in Xero, **When** the tax agent edits a split amount, **Then** the amounts-must-balance validation applies to the full updated set of line items.
5. **Given** the tax agent removes a split, leaving only one line item, **Then** the single-line item view is restored and the amounts-must-balance constraint is automatically satisfied.

---

### Edge Cases

- There is no save-and-return feature on the client portal. The client must complete all answers in a single session before submitting.
- Each send-back always creates a new `ClassificationRequest` with a new single-use magic link, so expired-link issues on the original request are not relevant to the send-back flow.
- What happens if the client submits a revised response on a returned item but the tax agent has already overridden it in the meantime? The client's new response is recorded in the audit trail; the override takes precedence. The tax agent sees an in-app indicator (badge/flag) on the overridden item in their review screen indicating the client responded after the override — no email is sent.
- How many rounds of send-back are permitted? Unlimited — no system cap. The agent may send back any number of times and can override directly at any point.
- What happens when the same invoice appears in two different BAS sessions (period overlap), and both have approved overrides? The system should write the most recently approved override and flag to the tax agent that a conflict existed.
- What if Xero's current line items differ from the local snapshot used to reconstruct the update (Xero was modified since last sync)? The system should detect the mismatch, skip the item, mark it as "conflict — Xero data has changed since last sync", and prompt the tax agent to re-sync from Xero first.
- What happens when the Xero OAuth token expires mid-sync? The system should refresh the token automatically and continue; if refresh fails, it marks all remaining items as "failed — authentication error" and records the failure.
- What if the same line item has multiple approved overrides (edge case from session duplication)? The system should use only the most recently approved override.
- What happens when a credit note line item needs correction but the credit note is fully applied against an invoice? Xero may reject the edit. The system should treat this as a "not editable" skip with a specific reason.
- What if an invoice has 50 line items but only one needs a tax code change? The system reconstructs all 50 in the update payload to avoid inadvertently clearing the others, then sends one API call.
- What if a bank transaction has `IsReconciled=true` and also has multiple line items? → The whole transaction is skipped as "not editable — reconciled"; no individual line items are modified.
- What if the tax agent defines splits on a single-line transaction but the transaction becomes reconciled in Xero before the sync runs? → The pre-flight check (FR-005) will detect `IsReconciled=true`, skip the document, and mark it "not editable — reconciled after split was defined".
- What if the tax agent creates a split line item with an amount of zero or a negative amount? → This is invalid; the system must reject zero or negative split amounts before allowing save or sync.
- What if the agent defines splits but the local `line_items` snapshot has drifted from Xero (FR-013 conflict) at sync time? → The system skips the document and marks it "conflict — Xero data has changed since last sync", preserving the agent's split definition so they can retry after re-syncing from Xero.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide an explicit "Sync to Xero" action on the BAS session screen, visible only when there are approved (unsynced) tax code overrides.
- **FR-002**: System MUST collect all approved TaxCodeOverride records for the BAS session that have not yet been successfully written to Xero.
- **FR-003**: System MUST group overrides by source document (invoice, bank transaction, or credit note), so multiple changed line items on the same document are written in a single Xero API call.
- **FR-004**: System MUST reconstruct the full line items payload for each document, applying tax type changes only to the specific line items referenced by the approved overrides, leaving all other line items unchanged.
- **FR-005**: System MUST check editability before writing: skip documents that are VOIDED, DELETED, have `IsReconciled=true` (bank transactions), are AUTHORISED with allocated payments/credit notes, or fall within a locked Xero accounting period — record the specific reason for each skip.
- **FR-005a**: Before queuing writes, system MUST fetch the organisation's tax rates via `GET /TaxRates` and validate that each approved override's `override_tax_type` is a recognised TaxType code for the connected Xero organisation. Custom tax rates differ per organisation — never hardcode valid codes.
- **FR-005b**: System MUST pass an `idempotencyKey` (the `XeroWritebackItem.id`) as a header on each Xero write call to prevent duplicate writes if the Celery task is retried.
- **FR-006**: System MUST write the corrected tax type to Xero for each eligible document and record whether the write succeeded or failed.
- **FR-007**: System MUST update the local Xero entity (XeroInvoice / XeroBankTransaction / XeroCreditNote) line_items field after a successful write, so local data reflects the new Xero state.
- **FR-008**: System MUST mark each TaxCodeOverride record as "synced" (no longer active as a local divergence) after a successful write to Xero.
- **FR-009**: System MUST NOT attempt to re-sync items that have already been successfully written to Xero in a previous sync run for this session.
- **FR-010**: System MUST display real-time progress to the tax agent during the sync operation.
- **FR-011**: System MUST present a detailed post-sync summary: success count, skip count (with reasons), failure count, and total duration.
- **FR-012**: System MUST allow the tax agent to retry only previously failed items, without re-attempting successfully synced items.
- **FR-013**: System MUST detect when Xero's current line items differ from the local snapshot, and skip rather than blindly overwrite with stale data.
- **FR-014**: System MUST record all write attempts in the BAS audit trail (success, skip, and failure) with full context.
- **FR-015**: System MUST respect Xero's rate limits (60 calls/minute per organisation) by queuing document updates and applying backoff when a 429 response is received.
- **FR-016**: System MUST handle OAuth token expiry during a sync by refreshing automatically; if refresh fails, abort the remaining items and report the authentication failure clearly.
- **FR-017**: System MUST scope all write-back operations to the correct Xero connection (tenant_id + connection_id), preventing cross-tenant data leakage.
- **FR-018**: System MUST NOT allow a sync to be triggered on a BAS session that has not yet reached "ready_for_review" or later status.

### Client Portal Workflow Refinements *(extends Spec 047)*

- **FR-019**: When a client selects "I don't know" for a transaction, the description field for that item MUST become mandatory before the item can be considered answered.
- **FR-020**: The client portal submit button MUST remain disabled until every transaction in the request has been answered (any category selection, "I don't know" with description, or "Personal — not business").
- **FR-021**: The portal MUST display a live counter showing how many transactions remain unanswered, updating as the client answers items.
- **FR-022**: There is no save-and-return functionality. The client must complete and submit all answers in one session. The magic link remains valid for 7 days but in-progress answers are not persisted between sessions.
- **FR-023**: The client portal MUST allow the client to change a previously given answer within the same session before submitting.

### Agent Workflow Refinements *(extends Spec 047)*

- **FR-024**: When the agent creates a classification request, they MUST be able to add a per-transaction note (optional) to any transaction being sent, in addition to the global request message.
- **FR-025**: Per-transaction tax agent notes MUST be displayed next to the relevant transaction on the client portal, clearly attributed as coming from "your accountant" (client-facing label).
- **FR-026**: The tax agent's review screen MUST allow them to select one or more "I don't know" items and trigger a "Send Back to Client" action with a mandatory comment for each returned item.
- **FR-027**: When items are sent back to the client, the system MUST create a new `ClassificationRequest` scoped to only the returned items, generate a new single-use magic link, and deliver it to the client via email. Each send-back round has its own request and link — the original link is not reused.
- **FR-028**: The portal MUST display the full response thread for returned items: client's original "I don't know" response, tax agent's comment (displayed as "Your accountant says:"), and the new response field — in chronological order.
- **FR-029**: The tax agent MUST be able to override a "I don't know" item with a direct tax code selection at any time, without being required to send it back to the client.
- **FR-030**: There is no system-enforced limit on send-back rounds per transaction. The tax agent may send an item back to the client as many times as needed and retains the ability to override directly at any time.
- **FR-031**: If the client submits a response on a returned item after the tax agent has already overridden it, the system MUST record the client's response in the audit trail and display an in-app indicator (badge/flag) on that item in the tax agent's review screen. No email notification is sent for this event.

### Bank Transaction Line Item & Split Management

- **FR-032**: For bank transactions with more than one line item, the tax code review UI MUST display each line item individually, showing its `LineAmount`, current `TaxType`, and `Description` (if present). Single-line-item transactions continue to use the existing single-code override UI unchanged.
- **FR-033**: Each displayed line item MUST have its own independent tax code selector. Overriding a single line item creates a `TaxCodeOverride` record scoped to that `line_item_index`; other line items are not affected.
- **FR-034**: The tax agent MUST be able to split a single-line bank transaction into multiple line items by specifying, for each new split: `LineAmount` (required) and `TaxType` (required). `Description` and `AccountCode` default to the original line item's values if not provided.
- **FR-035**: When splits are defined, the system MUST validate that the sum of all split `LineAmount` values equals the original transaction's total amount before allowing save or sync. Transactions with unbalanced splits cannot be included in a writeback job.
- **FR-036**: The tax agent MUST be able to: add a new split, remove a split (auto-restoring single-line view when one item remains), and edit the amount, tax code, or description of any split — at any time before the sync is triggered.
- **FR-037**: When the write-back processes a bank transaction where the tax agent has defined new splits, the system MUST send a `LineItems` array to Xero reflecting the full new split structure (not merely patching `TaxType` on the original single line item). This is an amendment to FR-004 for the split-creation case.
- **FR-038**: Splits created in Clairo that have not yet been synced to Xero MUST be visually distinguished from confirmed Xero line items (e.g., a "pending" indicator). Once successfully synced, they are shown as confirmed line items with the standard Xero status badge.

### Key Entities

- **XeroWritebackJob**: Represents a single "Sync to Xero" invocation. Tracks the triggering user, session, connection, start/end times, overall status (pending, in_progress, completed, failed), item counts (total, succeeded, skipped, failed), and links to per-item results.
- **XeroWritebackItem**: One item within a writeback job, corresponding to a single Xero document (invoice, bank transaction, or credit note). Captures the document type, Xero document ID, the list of line item indexes being changed, the before/after tax types, sync status, and error detail if applicable.
- **TaxCodeOverride** (from 046): Gains a `writeback_status` field: `pending_sync`, `synced`, `skipped`, `failed`. When a write succeeds, this is set to `synced` and `is_active` is set to false (Xero is now the source of truth).
- **AgentTransactionNote** (new): A per-transaction note added by the tax agent when creating or reviewing a classification request. Stores the note text, which transaction it applies to, and whether it was written on initial send or as a send-back comment.
- **ClientClassificationRound** (extends 047): Tracks each round of client review for a transaction. Round 1 = initial `ClassificationRequest`. Round 2+ = each new `ClassificationRequest` created by a send-back. Stores the round number, agent comment (if any), client response, source request ID, and timestamps.
- **ClassificationRequest** (from 047): Each send-back creates a new `ClassificationRequest`. Gains a `parent_request_id` (nullable FK to the originating request) and `round_number` to link the chain of send-backs for a given BAS session.

---

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [x] **Data Modification Events**: This feature writes tax type changes to financial documents in Xero (invoices, bank transactions, credit notes) — direct modification of BAS source data.
- [x] **Integration Events**: This feature pushes data to Xero via API — every write to an external system must be logged.
- [x] **Compliance Events**: Tax codes directly determine how transactions appear in the BAS lodgement. Changing them in Xero affects the official books of the client business.

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| `xero.taxcode.writeback_initiated` | Tax agent clicks "Sync to Xero" | Session ID, connection ID, user ID, count of items queued, timestamp | 7 years | None |
| `xero.taxcode.writeback_item_success` | Xero API returns success for a document | Session ID, document type, Xero document ID, line item index, original tax type, new tax type, user ID, timestamp | 7 years | None |
| `xero.taxcode.writeback_item_skipped` | Item pre-screened as not editable | Session ID, document type, Xero document ID, skip reason (voided / period-locked / data-mismatch), user ID, timestamp | 7 years | None |
| `xero.taxcode.writeback_item_failed` | Xero API returns error for a document | Session ID, document type, Xero document ID, HTTP status code, Xero error message, user ID, timestamp | 7 years | None |
| `xero.taxcode.writeback_completed` | All items in the job have been processed | Session ID, job ID, total items, succeeded, skipped, failed, duration, user ID, timestamp | 7 years | None |
| `xero.taxcode.writeback_retry_initiated` | Tax agent triggers retry for failed items | Session ID, job ID, count of items being retried, user ID, timestamp | 7 years | None |
| `classification.items_sent_back` | Tax agent sends "I don't know" items back to client | Request ID, transaction IDs returned, tax agent comment per item, tax agent user ID, round number, timestamp | 7 years | None |
| `classification.client_answered_round` | Client submits a revised response on a returned item | Request ID, transaction ID, round number, client response, timestamp | 7 years | None |

### Compliance Considerations

- **ATO Requirements**: This feature changes tax codes on the source financial records that form the basis of the BAS lodgement. The audit trail must be sufficient to answer the question: "Who changed this tax code, when, and why was the change justified?" The "why" is captured by linking back to the TaxCodeSuggestion and its approval record from spec 046.
- **Data Retention**: All writeback records must be retained for 7 years, aligned with ATO document retention requirements. Since these records explain changes to BAS source data, they must survive even after the Xero connection is disconnected.
- **Access Logging**: Write-back audit logs must be viewable by the same users who can access the BAS session (the tax agent who owns the session and the practice manager). Clients (business owners) do NOT have access to writeback audit logs.
- **Professional Judgement**: The ATO requires tax agents to exercise professional judgement over their client's tax affairs. The design enforces this by requiring explicit human approval of each tax code change (via the 046 workflow) before any write to Xero can occur. Automated or bulk writes without tax agent approval are prohibited.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Tax agents can sync all approved tax codes for a standard quarterly BAS session (up to 50 approved overrides) to Xero within 2 minutes, end-to-end.
- **SC-002**: At least 90% of sync attempts for editable documents succeed on the first try (measured as success rate excluding pre-screened skips).
- **SC-003**: All non-editable documents (voided, locked period) are detected before attempting a write, resulting in zero unexpected API errors from known-locked documents.
- **SC-004**: After a successful sync, a subsequent Xero re-sync detects zero new conflicts for the items that were written back (Xero and Clairo are in agreement).
- **SC-005**: 100% of write operations (success, skip, failure) are recorded in the audit trail with no gaps.
- **SC-006**: Tax agents can identify which items failed and why within 10 seconds of the sync completing, without needing to contact support.
- **SC-007**: A partial sync failure (e.g., 2 items fail, 8 succeed) does not cause the tax agent to re-do the full sync — only the failed items need to be retried.
- **SC-008**: Clients are not able to submit a classification request with any unanswered transaction — the submit action is gated and validated client-side and server-side.
- **SC-009**: "I don't know" submissions without a description are rejected before submission — zero "I don't know" items reach the agent review screen without at least a text context.
- **SC-010**: Agents can send "I don't know" items back to the client and receive a revised response within the same portal session lifecycle without any manual workaround (email, phone, or external tool).
- **SC-011**: Tax agents can view individual line items on any bank transaction that already has multiple splits, without needing to navigate to Xero.
- **SC-012**: After syncing agent-defined splits to Xero, a subsequent Xero re-sync shows zero conflicts for those transactions — the local `line_items` snapshot matches Xero exactly.

---

## Assumptions

- The `accounting.transactions` OAuth scope already requested during Xero connection covers write access to invoices, bank transactions, and credit notes. No re-authorization is needed for this feature. **Note**: Xero will deprecate broad scopes in September 2027 — migration to granular scopes (`accounting.banktransactions`, `accounting.invoices`, `accounting.payments`, `accounting.settings.read`) is required before that date but is out of scope for this feature.
- Bank transactions with `IsReconciled=true` are treated as not editable. The field `IsReconciled` (not `IsLocked`) is the correct Xero API field to check.
- Xero's API uses `POST /Invoices/{id}` (not `PUT`) to update existing invoices and the same pattern applies to bank transactions and credit notes.
- When reconstructing a full document payload for the Xero update, the system will use the locally stored `line_items` JSONB as the base (from the last sync), applying only the tax type change before sending. This is safe as long as the local snapshot is current.
- A pre-flight check against the Xero API (fetching the current document to detect if Xero has changed since last sync) is required before each write to avoid inadvertently overwriting changes made directly in Xero after the last sync.
- Xero will return the document's `locked` or `voided` state in the same GET response used for the pre-flight check, allowing editability to be determined before attempting the write.
- Rate limit management can reuse the existing `RateLimitState` infrastructure already built in the Xero client module.
- The writeback is always tax agent-initiated (explicit button click). There is no automatic writeback on approval.
- Bank transactions with status `AUTHORISED` (not yet reconciled, i.e. `IsReconciled=false`) can have their line item tax types updated.
- Credit note line items follow the same update pattern as invoice line items.
- The "mandatory description on I don't know" and "all questions required before submit" rules are enforced client-side for UX and server-side for integrity.
- Each agent send-back creates a new `ClassificationRequest` with its own single-use magic link. Magic link reuse is never required — security is maintained by design.
- Per-transaction agent notes are stored separately from the global request message; both can coexist on the same request.
- `TaxCodeOverride` already carries a `line_item_index` field (from spec 046). Multiple `TaxCodeOverride` records targeting different `line_item_index` values on the same bank transaction are valid and supported by the existing write-back pipeline.
- Split structure is stored by extending `TaxCodeOverride` rather than adding a new table. The extension adds: `suggestion_id` made nullable (agent-created splits have no AI suggestion); `line_amount` (nullable decimal — null = keep existing Xero amount); `line_description` (nullable text — null = keep existing); `line_account_code` (nullable text — null = keep existing); `is_new_split` boolean (false = override an existing line item at that index, true = insert a new line item at that index in the reconstructed payload).
- `apply_overrides_to_line_items` in the write-back pipeline handles two modes: (1) override existing — patch `TaxType` and any non-null amount/description/account_code on the existing line item; (2) new split — insert a new entry into the reconstructed `LineItems` array at the specified index.
- Split management (FR-032–FR-038) applies to bank transactions only. Invoice and credit note line items are managed by the accountant directly in Xero and are treated as read-only structure in Clairo.

---

## Out of Scope

- Automatic write-back on approval — the write to Xero must always be an explicit tax agent action, not triggered automatically when a suggestion is approved.
- Writing back changes made to transactions that were not part of the tax code resolution workflow (this feature only writes TaxCodeOverride records, not arbitrary Xero edits).
- Writing back any field other than TaxType, except when the tax agent has explicitly defined splits on a bank transaction (in which case `LineAmount` and optionally `Description`/`AccountCode` per split are also written). All other fields on invoice and credit note line items remain read-only.
- Correcting Xero account code assignments (except as an optional field when the agent explicitly defines splits on a bank transaction).
- Split management on invoices or credit notes — applies to bank transactions only.
- Bulk writeback across multiple BAS sessions at once — each sync is scoped to a single BAS session.
- Syncing corrections back to MYOB or other accounting platforms.
- ATO lodgement — BAS lodgement remains manual and is outside scope.
- SMS or push notification for send-back alerts — email only (consistent with initial request delivery).
- In-app chat or real-time messaging between agent and client — the send-back is asynchronous (email notification + portal).
- Allowing the client to initiate contact with the agent from the portal (one direction only: agent → client send-back).

---

## Reliability Fixes (2026-04-06)

Four UX and reliability issues discovered during implementation were resolved in a follow-up session. These refine the original design without changing any scope.

### Fix 1 — Org-Specific Tax Type Validation in Override Dropdown

**Problem**: The override dropdown in `TaxCodeSuggestionCard` showed a hardcoded list of 11 tax type codes. Xero organisations may not have all codes enabled; selecting an unavailable code would be silently skipped at sync time with `invalid_tax_type`.

**Resolution**: Added `GET /api/v1/clients/{connection_id}/xero/tax-rates` endpoint in `backend/app/modules/bas/router.py`. On first open of the override dropdown, the frontend fetches the org's active Xero tax rates and populates the list from Xero's `GET /TaxRates` response filtered to `status=ACTIVE`. Falls back to the hardcoded `VALID_TAX_TYPES` list if the fetch fails. Added `fetchOrgTaxTypes()` in `frontend/src/lib/bas.ts`.

### Fix 2 — Apply & Recalculate Button Clarity

**Problem**: Users were unclear when "Apply & Recalculate" was required vs. when syncing was sufficient.

**Resolution**: Added a `title` tooltip to the button: *"Updates BAS figures (G1, 1A, G11, 1B) to reflect your approved tax codes. Run this before submitting to the ATO."* Also added context-sensitive left-panel text: when all items are resolved and recalculation is pending, shows "All resolved — recalculate BAS figures before lodgement" instead of "0 pending". Apply & Recalculate is now purely a BAS figure update step — it is NOT required before syncing to Xero (Fix 4 removed that dependency).

### Fix 3 — Inline Sync Status in Resolved Table

**Problem**: `WritebackProgressPanel` and `WritebackResultsSummary` appeared as separate cards above/below the Resolved table that would pop in and disappear, disconnected from the rows they described.

**Resolution**: Removed both components from the accordion layout. Polling logic moved inline into `TaxCodeResolutionPanel` (silent useEffect, no visual block). During sync: each approved/overridden row shows a `Syncing…` amber badge in its status column. After sync: per-row Xero status badges (`Xero ✓` / `⚠ Skipped` / `Xero ✗`) remain. Failed items: a compact one-line retry row appears below the table only when `failed_count > 0`. `WritebackProgressPanel` and `WritebackResultsSummary` components are no longer rendered.

### Fix 4 — TaxCodeOverride Created Immediately on Approve/Override (Root Bug Fix)

**Problem**: `TaxCodeOverride` records were only created in `apply_and_recalculate()`. If the tax agent synced to Xero before running Apply & Recalculate, `_get_pending_overrides()` found nothing because no overrides existed yet. This also caused `approved_unsynced_count` to read 0 immediately after an approval.

**Resolution**: `approve_suggestion()`, `override_suggestion()`, and `bulk_approve_suggestions()` in `tax_code_service.py` now create a `TaxCodeOverride` with `writeback_status=pending_sync` immediately on action, using the `get_active_override()` / `create_override()` repository pattern. `apply_and_recalculate()` retains its existing guard (`if not existing: create`) so it still works correctly but is no longer the sole creator of override records. `apply_and_recalculate` is now a pure BAS figure recalculation step — override lifecycle is fully decoupled from it.

### Fix 5 — Frontend Stale Session / Accordion Reliability

**Problem**: Several frontend state issues prevented the Sync button from appearing after an approve/override action:
1. `selectedSession.approved_unsynced_count` was stale because the useEffect that sets `selectedSession` had a `!selectedSession` guard — it only ran at mount, never re-synced from the refreshed `sessions` array after `fetchSessions()`.
2. `WritebackProgressPanel` calling `fetchSessionDetail` restored `completedWritebackJob` from a previous sync, and `!completedWritebackJob` in the Sync button condition permanently hid the button for any session that had been synced before.
3. The Resolved accordion used an uncontrolled `defaultValue` computed at mount — it never included `'resolved'` for fresh sessions, so the Sync button inside it was hidden behind a collapsed section.
4. `fetchSessions()` called `setIsLoading(true)` on every invocation, causing the entire `BASTab` to unmount `TaxCodeResolutionPanel` and flicker each time a background refresh occurred (after approve, after sync completion).

**Resolution**:
- useEffect in `BASTab` now re-syncs `selectedSession` from the refreshed `sessions` array on every `sessions` state change (removed `!selectedSession` guard).
- Sync button condition changed to `!activeWritebackJobId && approvedUnsyncedCount > 0` — `completedWritebackJob` no longer blocks it.
- Accordion switched to controlled `value={openSections}` with `useState(['high', 'review', 'manual', 'resolved'])` initial state; `useEffect` also auto-opens `'resolved'` reactively when sync state changes.
- `fetchSessions()` now only shows the full-page loading spinner on the initial load (`hasLoadedSessionsRef`). Subsequent background calls run silently, keeping `TaxCodeResolutionPanel` mounted.
