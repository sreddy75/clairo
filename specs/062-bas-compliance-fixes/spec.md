# Feature Specification: BAS Compliance Fixes & Data Accuracy

**Feature Branch**: `062-bas-compliance-fixes`  
**Created**: 2026-04-24  
**Status**: Draft  
**Input**: User description: "Most critical issue: Clairo does not ask whether a client's BAS should be prepared on cash or accrual basis. Client in this session is registered on cash basis but Clairo loaded accrual figures — this produces a materially wrong BAS and incorrect GST reporting to the ATO. 10 bugs and gaps identified..."

## Background

BAS (Business Activity Statement) preparation is Clairo's core compliance function. A materially wrong BAS filed with the ATO exposes the accountant's practice to professional liability and the client to penalties. This spec addresses critical compliance gaps and a set of confirmed UX bugs observed during live BAS preparation sessions.

The issues were surfaced by Unni Ashok (Chartered Accountant & Director, Ashok Business Consulting Group) during a live trial on a real client (SCV Holdings Pty Ltd) on 18 April 2026.

The issues fall into four groups:
1. **Compliance-critical** — produce an incorrect BAS if unaddressed
2. **Data accuracy** — misleading or incorrect figures shown to users
3. **Navigation/state** — context lost during normal workflows
4. **Insights tab quality** — inaccurate or noisy advisory content

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Cash vs Accrual Basis Selection (Priority: P1)

An accountant opens a client's BAS preparation for the current quarter. Before any figures are loaded from Xero, the system prompts them to confirm whether this client's GST is reported on a **cash** or **accrual** basis. The accountant selects "Cash basis" for this client. Clairo then fetches and displays only receipts and payments within the quarter (cash basis), not invoices raised (accrual). The correct figures flow through to the BAS form fields (G1, G2, 1A, 1B).

**Why this priority**: Reporting GST on the wrong basis is a material ATO compliance error. A single incorrect BAS lodgement can trigger audits, penalties, and reputational harm for the practice. No other fix matters if the underlying figures are wrong.

**Independent Test**: Create a test client whose Xero invoices span two quarters (one raised in Q1, paid in Q2). Open BAS for Q2 in cash mode — only the Q2 payment should appear in G1. Open BAS for Q2 in accrual mode — the Q1 invoice should appear in G1. Both modes can be tested end-to-end without any other story being complete.

**Acceptance Scenarios**:

1. **Given** a client has no saved basis preference, **When** an accountant opens BAS preparation for any quarter, **Then** a modal or inline prompt asks "How does this client report GST?" with options: Cash basis / Accrual basis, before Xero data is fetched.
2. **Given** a client has a saved basis preference (cash or accrual), **When** an accountant opens BAS preparation, **Then** the preference is pre-selected but editable, and Xero data is fetched using the saved preference.
3. **Given** an accountant selects "Cash basis", **When** Clairo fetches Xero transactions, **Then** only receipts and payments with a payment date within the BAS quarter are included in turnover and GST calculations.
4. **Given** an accountant selects "Accrual basis", **When** Clairo fetches Xero transactions, **Then** invoices with an invoice date within the BAS quarter are included, regardless of payment date.
5. **Given** an accountant changes the basis preference for an existing period, **When** they confirm the change, **Then** all figures are recalculated and a warning is shown: "Changing the basis will reload all figures. Any manual adjustments will be lost."
6. **Given** the basis preference is saved, **When** the accountant returns to the same client in a future quarter, **Then** the previously saved preference is the default, clearly labelled so the accountant can confirm or override.

---

### User Story 2 — PAYGW (Wages) Population (Priority: P2)

An accountant is preparing a BAS for a client who pays wages. The PAYG Withholding section (W1/W2) should be automatically populated from the Xero payroll data for the quarter. Currently this field is blank and the accountant has no prompt to fill it.

**Why this priority**: PAYGW is a mandatory BAS obligation for wage-paying businesses. An unfilled W1/W2 results in an incorrect BAS. This is the same systemic gap as noted in the tax planning module.

**Independent Test**: Open BAS for a client with Xero payroll connected and wages recorded in the quarter. Verify W1 and W2 fields populate automatically. Can be tested in isolation without any other user story.

**Acceptance Scenarios**:

1. **Given** a client has Xero payroll connected and wages paid in the BAS quarter, **When** BAS preparation loads, **Then** W1 (total salary/wages) and W2 (PAYG withheld) are auto-populated from payroll data.
2. **Given** W1/W2 fields are auto-populated, **When** the accountant reviews them, **Then** the source is labelled clearly (e.g., "From Xero Payroll — [date range]") and they are editable.
3. **Given** a client has no Xero payroll data for the quarter, **When** BAS loads, **Then** W1 and W2 fields are blank with a hint: "No payroll data found — enter manually if wages were paid."
4. **Given** a client's Xero payroll is not connected, **When** BAS loads, **Then** the W1/W2 section shows a "Connect Payroll" prompt or a manual entry fallback.

---

### User Story 3 — PAYG Instalment Manual Entry Tab (Priority: P3)

An accountant needs to record a client's PAYG instalment for the quarter. Currently no instalment fields are visible in the BAS workflow. The accountant must go outside Clairo to find this figure and has no structured way to enter it. Since Clairo has no ATO portal connection, instalment amounts cannot be auto-populated — manual entry is the immediate solution.

**Why this priority**: PAYG instalments appear on most small business BAS forms. Without this field the BAS cannot be considered complete within Clairo.

**Independent Test**: Navigate to BAS preparation for any client. A "PAYG Instalment" section must be visible and allow manual entry of instalment income (T7), instalment amount (T8), and instalment credit (T9). Can be tested without payroll or GST data.

**Acceptance Scenarios**:

1. **Given** an accountant is on the BAS preparation screen, **When** they select the PAYG Instalment section, **Then** they can enter T1 (instalment income) and T2 (instalment rate or amount) — the correct ATO field labels for quarterly BAS filers.
2. **Given** valid instalment figures are entered, **When** the BAS summary is generated, **Then** the instalment amount flows through to the total amount payable.
3. **Given** no instalment amount is entered, **When** the BAS is reviewed, **Then** the field shows zero with a clear label — not a blank that implies the data is missing.

---

### User Story 4 — Fix Misleading "Manual Required" Label (Priority: P4)

An accountant sees "57 Manual Required" in the transaction list. This label implies those transactions need manual bank reconciliation — but Xero shows 71 reconciled, 0 unreconciled. Those 57 transactions are fully reconciled; they simply have no tax code assigned. Reconciliation status and coding status are completely different things and must be shown as separate indicators.

**Why this priority**: This causes accountants to misdiagnose the problem and either look for the wrong fix or lose confidence in the data. It does not cause an incorrect BAS directly, but wastes time and erodes trust.

**Independent Test**: Open a client with uncoded but reconciled transactions. The BAS screen must show two distinct at-a-glance indicators: (a) reconciliation status ("All reconciled" or "N unreconciled") and (b) coding status ("N uncoded transactions"). The label "Manual Required" must not appear anywhere.

**Acceptance Scenarios**:

1. **Given** transactions exist with no tax code assigned, **When** the accountant views the transaction list, **Then** those transactions are labelled "Uncoded" (or "Needs tax code") and grouped under an "Uncoded Transactions" section.
2. **Given** transactions are uncoded, **When** the accountant views the count badge, **Then** it reads "N uncoded" (e.g., "57 uncoded"), never "Manual Required" or "Unreconciled".
3. **Given** transactions are uncoded, **When** the accountant clicks to action them, **Then** the prompt guides them to assign a tax code — not to reconcile against a bank statement.
4. **Given** the BAS screen loads, **When** the accountant scans the header/summary area, **Then** reconciliation status and coding status are visible as two separate indicators so both questions — "is the data reconciled?" and "are there uncoded transactions?" — are answerable at a glance.

---

### User Story 5 — Uncoded Transactions in Date Order (Priority: P5)

An accountant reviewing uncoded transactions expects them to appear in chronological order (oldest first) so they can work through them systematically. Currently the order is non-deterministic.

**Why this priority**: Date order is standard in all accounting tools and required for efficient review. Disorderly lists slow down BAS preparation.

**Independent Test**: Load a client with multiple uncoded transactions across different dates. Verify the list is sorted ascending by transaction date by default.

**Acceptance Scenarios**:

1. **Given** a client has uncoded transactions, **When** the accountant views the list, **Then** transactions are sorted by date descending (most recent first) by default.
2. **Given** the date-sorted list, **When** the accountant clicks a column header, **Then** they can re-sort by amount, description, or date.

---

### User Story 6 — Cent-Level Precision in Transaction Amounts (Priority: P6)

An accountant or business owner reviewing transactions sees amounts rounded to whole dollars (e.g., $1,234), but bank statements show cents (e.g., $1,234.56). This causes reconciliation confusion and looks like a data error.

**Why this priority**: Rounding introduces apparent discrepancies between Clairo figures and bank statements. This erodes accountant trust and prompts unnecessary investigation.

**Independent Test**: Load any client with Xero transaction data. Transaction amounts must display two decimal places throughout the BAS workflow and transaction list.

**Acceptance Scenarios**:

1. **Given** a transaction has a value with cents (e.g., $1,234.56), **When** it appears in the transaction list, **Then** it is displayed as "$1,234.56" — never "$1,235" or "$1,234".
2. **Given** BAS form fields are populated (G1, 1A, 1B, etc.), **When** the accountant reviews them, **Then** values display with cent precision unless the ATO field specification requires whole-dollar rounding (in which case the rounding rule is shown to the user).

---

### User Story 7 — Quarter Context Preserved Across Tabs (Priority: P7)

An accountant selects the March quarter for BAS preparation, switches to the Insights tab, and sees April data — a different quarter. The quarter selection does not persist across tabs. The selected BAS period must be the active context across all tabs — BAS, Insights, and Dashboard.

**Why this priority**: Quarter context is foundational. Every figure on the screen must relate to the same period. Losing it causes confusion about what the accountant is reviewing.

**Independent Test**: Select March quarter on BAS tab. Switch to Insights tab — must show March data. Switch to Dashboard — must show March data. Switch back to BAS tab — must still show March quarter selected.

**Acceptance Scenarios**:

1. **Given** an accountant has selected a quarter on the BAS tab, **When** they switch to the Insights tab or Dashboard, **Then** all tabs display data scoped to the same selected quarter.
2. **Given** an accountant is on the Insights tab or Dashboard, **When** they switch back to the BAS tab, **Then** the previously selected quarter is still active.
3. **Given** no quarter has been explicitly selected, **When** the accountant opens any tab, **Then** the current/most recent quarter is selected by default and clearly displayed on every tab.
4. **Given** data from outside the selected period is shown (e.g., year-to-date context), **When** it appears on any tab, **Then** it is clearly labelled as outside the BAS period.

---

### User Story 8 — Insights Tab Accuracy & Quality (Priority: P8)

An accountant opens the Insights tab alongside BAS preparation to review advisory content before sending it to the client. Currently: the "overdue" figure is wrong; a GST registration insight appears for already-registered clients; insight cards use AI chat language ("it appears that…") instead of professional advisory language; low-confidence items are flagged as urgent; and some insights are duplicated. There is also no way to see the calculation behind a figure.

**Why this priority**: The vision of sending Insights alongside BAS lodgement as an advisory summary is strong and worth investing in — but only if the insights are accurate and professionally worded. Inaccurate or noisy insights undermine accountant confidence and cannot be sent to clients.

**Independent Test**: Open Insights tab for a client who is GST-registered and has no overdue lodgements. The GST registration insight must not appear. Overdue count must match ATO portal. No insight should be labelled "urgent" unless its confidence level is high. No insight should appear more than once. Each insight must display a "How was this calculated?" breakdown.

**Acceptance Scenarios**:

1. **Given** a client has overdue accounts receivable, **When** the overdue receivables insight appears, **Then** the figure matches the actual overdue AR balance from Xero (e.g., one invoice at $5,114 overdue — not 81% of all outstanding). Overdue receivables and total outstanding receivables are distinct figures and must not be conflated.
2. **Given** a client is already registered for GST (detectable from their ABN/client profile), **When** insights are generated, **Then** no "Consider GST registration" insight is shown.
3. **Given** an insight is generated by AI, **When** it appears in the Insights tab, **Then** it is written in professional advisory language (e.g., "Revenue declined 12% this quarter vs the same period last year") — not conversational chat language (e.g., "I notice there's a misunderstanding in your question"). Insight generation and chat response must use distinct generation paths.
4. **Given** an insight has a confidence score below 70%, **When** it is displayed, **Then** it is placed in the "For Review" section — never in "Urgent".
5. **Given** multiple insights are generated, **When** the Insights tab renders, **Then** each unique insight appears exactly once — no duplicates, even if wording differs slightly.
6. **Given** an insight shows a calculated figure, **When** the accountant clicks "How was this calculated?", **Then** a breakdown panel shows the data points and formula used to arrive at the figure (e.g., cash flow of -$11,802/month must show the income and expense figures used).

---

### User Story 9 — Request Client Input: Label & Ordering Fixes (Priority: P9)

An accountant uses the "Request Client Input" workflow to send uncoded transactions to the business owner for clarification. Currently the client receives a list with the same misleading labels and disordered dates that the accountant sees — "Manual Required" and non-chronological ordering. The concept is sound; the execution needs the same corrections applied to the accountant view.

**Why this priority**: Sending a client a list labelled "Manual Required" for transactions that are already reconciled is confusing and unprofessional. The ordering fix is equally important for the client to work through transactions systematically.

**Independent Test**: Trigger a Request Client Input for a client with uncoded transactions. The client-facing view must show "Uncoded" (or "Needs tax code") labels and transactions sorted date descending — consistent with what the accountant sees after this spec's fixes.

**Acceptance Scenarios**:

1. **Given** an accountant sends uncoded transactions to a client via Request Client Input, **When** the client views the request, **Then** transactions are labelled "Needs tax code" (or equivalent plain-language label appropriate for a non-accountant) — never "Manual Required" or "Unreconciled".
2. **Given** the client views the transaction request, **When** the list renders, **Then** transactions are sorted by date descending (most recent first) by default.
3. **Given** the client has responded to a request, **When** the accountant reviews the responses, **Then** the response view uses the same corrected labels and ordering.

---

### User Story 10 — Load Error with Working Refresh (Priority: P10)


An accountant opens BAS for a specific client and encounters an error during data load. The refresh button is visible but non-functional (clicking it does nothing). The accountant must close the tab and re-navigate to retry.

**Why this priority**: A non-functional error recovery path is a blocking UX defect. Accountants under time pressure will abandon the workflow.

**Independent Test**: Simulate a Xero data fetch failure (e.g., by temporarily disconnecting the integration). An error state must appear. Clicking the "Refresh" or "Retry" button must re-attempt the data fetch and either succeed or show an updated error message.

**Acceptance Scenarios**:

1. **Given** a data load error occurs, **When** the error state is displayed, **Then** a "Retry" button is visible and functional.
2. **Given** the accountant clicks "Retry", **When** the retry succeeds, **Then** the page loads normally.
3. **Given** the accountant clicks "Retry", **When** the retry also fails, **Then** the error message updates (e.g., "Still unable to load — Xero may be unavailable. Try again in a few minutes.") and the button remains active.

---

### User Story 11 — Unreconciled Data Warning (Priority: P11)

An accountant opens BAS for a client whose Xero data includes unreconciled transactions. Currently, Clairo fetches and displays those figures without any indication that they are based on unreconciled data. The accountant may prepare and lodge a BAS on incomplete figures.

**Why this priority**: Unreconciled figures are preliminary. A BAS prepared on unreconciled data may need to be amended — which is costly and damages the practice's ATO standing.

**Independent Test**: Connect a client whose Xero account has a non-zero count of unreconciled bank statement lines. Open BAS preparation. A warning banner must appear before figures are shown.

**Acceptance Scenarios**:

1. **Given** a client's Xero account has unreconciled transactions for the selected period, **When** BAS preparation loads, **Then** a prominent warning is displayed before showing any BAS figures: "Xero transactions for this period are not fully reconciled — BAS figures may be incomplete or inaccurate." with two explicit options: "Proceed anyway" and "Go back and reconcile first."
2. **Given** the accountant selects "Proceed anyway", **When** BAS figures are displayed, **Then** a persistent banner remains on screen: "Warning: based on unreconciled data as at [date]."
3. **Given** the accountant selects "Go back and reconcile first", **When** they confirm, **Then** they are returned to the client overview without BAS figures being shown.
4. **Given** a client's Xero account is fully reconciled for the selected period, **When** BAS preparation loads, **Then** no warning is shown and figures are displayed directly.

---

### Edge Cases

- What if a client's basis preference changes mid-year (e.g., ATO approves a switch from cash to accrual)? The system must support changing the preference with a clear audit record of when it changed and who changed it.
- What if the accountant changes the basis for an already-lodged period? The system must show an elevated warning ("this period is lodged — changing basis requires an amended BAS") but permit the change; the audit log must record that the change was made post-lodgement.
- What if Xero payroll data is partially reconciled — e.g., some pay runs are finalised and some are draft? Only finalised pay runs should populate W1/W2; a note should indicate if draft runs exist.
- What if the same transaction appears to qualify under both cash and accrual rules for the same period (e.g., invoice raised and paid in the same quarter)? It should appear once regardless of basis.
- What if an insight's source data is stale (e.g., Xero sync is 3 days old)? The insight card must display the data-as-of date.
- What if the BAS form fields require whole-dollar amounts for lodgement? Clairo must display cents for review but round correctly at the point of generating the lodgement file, with a clear rounding summary.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST prompt the accountant to select a GST reporting basis (cash or accrual) before loading Xero transaction data for a BAS period.
- **FR-002**: The system MUST persist the GST reporting basis preference per client, so subsequent quarters default to the saved preference.
- **FR-003**: The system MUST fetch and calculate BAS figures using only transactions that fall within the selected quarter under the chosen basis (payment date for cash; invoice date for accrual).
- **FR-004**: The system MUST allow the accountant to change the basis preference for an already-loaded period, with a confirmation warning that figures will be recalculated and manual adjustments will be discarded. If the period has already been lodged, the system MUST display an additional elevated warning: "This period has been lodged with the ATO. Changing the basis will require you to lodge an amended BAS." The accountant may still proceed after confirming both warnings.
- **FR-005**: The system MUST auto-populate W1 (gross wages) and W2 (PAYG withheld) from Xero payroll data for the BAS quarter when payroll data is available.
- **FR-006**: The system MUST provide a manual entry fallback for W1/W2 when Xero payroll is not connected or has no data for the quarter.
- **FR-007**: The system MUST provide a PAYG Instalment section in the BAS workflow for all clients, supporting T1 (instalment income) and T2 (instalment rate or amount) entry — the correct ATO field labels for quarterly BAS filers. The section is always visible regardless of whether the client is enrolled in PAYG instalments — accountants leave it blank if not applicable.
- **FR-008**: The system MUST label transactions with no tax code as "Uncoded" (or "Needs tax code") — never "Manual Required" or "Unreconciled" — throughout the BAS workflow. The BAS screen MUST display reconciliation status and coding status as two separate indicators so both are visible at a glance.
- **FR-009**: The system MUST display uncoded transactions sorted by date descending (most recent first) by default, with the ability for the accountant to re-sort by amount, description, or date.
- **FR-010**: The system MUST display all transaction amounts with cent-level precision (two decimal places) throughout the BAS workflow and transaction list.
- **FR-011**: The system MUST preserve the selected BAS quarter as the active context across all tabs — BAS, Insights, and Dashboard — within a session.
- **FR-012**: The system MUST scope all Insights tab and Dashboard content to the quarter selected on the BAS tab (or the current/most recent quarter if no explicit selection has been made). Data displayed outside the selected period must be clearly labelled as such.
- **FR-013**: The system MUST suppress insights that are not relevant to the client's current situation (e.g., a "register for GST" insight must not appear for a client already registered for GST).
- **FR-014**: Insight cards MUST use professional advisory language, not conversational AI language.
- **FR-015**: Insights with a confidence score below 70% MUST NOT appear in the "Urgent" section; they MUST appear in the "For Review" section. Insights are never suppressed on confidence grounds alone — all generated insights are shown, routed to the appropriate section based on their score.
- **FR-016**: The system MUST deduplicate insights before rendering — no insight may appear more than once in the same Insights tab view.
- **FR-017**: Each insight that displays a calculated figure MUST offer a "How was this calculated?" breakdown showing the source data and formula.
- **FR-018**: The overdue receivables figure displayed in insights MUST reflect the actual overdue AR balance from Xero — invoices past their due date — not total outstanding receivables. These are distinct figures and must not be conflated.
- **FR-018b**: The overdue lodgement count displayed in insights MUST be derived from Clairo's own lodgement records (lodgements with a due date in the past and no recorded lodgement date). The accountant MUST be able to manually mark a lodgement as overdue or clear an overdue flag if the ATO status differs from Clairo's records.
- **FR-019**: The "Retry" button on the BAS load error screen MUST re-trigger the Xero data fetch, and must update the error message if the retry also fails. The error state must describe what went wrong and offer a suggested next step — a non-functional button with no error detail is not acceptable.
- **FR-020**: The system MUST display a blocking warning when a client's Xero data includes unreconciled transactions for the selected period, before showing any BAS figures. The warning MUST offer two explicit options: "Proceed anyway" and "Go back and reconcile first." If the accountant proceeds, a persistent banner must remain on screen for the duration of the session.
- **FR-022**: The Request Client Input workflow MUST apply the same label and ordering corrections as the accountant view: transactions sent to clients must be labelled "Needs tax code" (plain language, not "Manual Required") and sorted date descending by default.
- **FR-021**: The system MUST allow the accountant to optionally include an Insights summary when sending the BAS lodgement confirmation to the client. The accountant decides per client whether to include it. The summary must present the quarter's key insights in professional advisory language suitable for a business owner to read. The delivery format (inline email section, PDF attachment, or magic link to a web page) is accountant-selectable.

### Key Entities

- **Client GST Basis**: Persisted preference (cash or accrual) per client, editable by the accountant, with a history of changes for audit purposes.
- **BAS Period Session State**: The selected quarter, chosen GST basis, and active tab — maintained across tab switches within the same BAS preparation session.
- **Insight Confidence Score**: A numeric score (0–100) attached to each generated insight, used to route it to the correct section (Urgent vs For Review) and to determine whether to show it at all.
- **Insight Source Breakdown**: The data points and calculation steps that produced a displayed insight figure, surfaced in the "How was this calculated?" panel.

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [x] **Authentication Events**: No new auth changes.
- [x] **Data Access Events**: Yes — BAS figures are sensitive financial data; loading them must be logged.
- [x] **Data Modification Events**: Yes — saving the GST basis preference and any manual W1/W2/T1/T2 entries are modifications to business-critical data.
- [x] **Integration Events**: Yes — changing the basis triggers a new Xero data fetch, which is an integration event.
- [x] **Compliance Events**: Yes — the GST basis directly determines what is reported to the ATO; the chosen basis must be captured in the audit record for every BAS period.

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| `bas.gst_basis.set` | Accountant saves or changes GST basis preference | client_id, period, old_basis, new_basis, changed_by | 10 years | None |
| `bas.period.loaded` | BAS period data is fetched from Xero | client_id, period, basis_used, transaction_count, fetched_at | 7 years | None |
| `bas.paygw.manual_entry` | Accountant manually enters W1 or W2 | client_id, period, field, old_value, new_value, entered_by | 10 years | None |
| `bas.payg_instalment.entry` | Accountant enters T1 or T2 instalment | client_id, period, mode (T1/T2), amount, entered_by | 10 years | None |
| `bas.data_refresh.retry` | Accountant clicks Retry after load failure | client_id, period, attempt_number, outcome | 5 years | None |

### Compliance Considerations

- **ATO Requirements**: The GST reporting basis (cash vs accrual) is a registered characteristic of the business with the ATO. Any change to the basis used for a specific period must be auditable to demonstrate that the correct basis was applied at lodgement time.
- **Data Retention**: BAS-related audit events must be retained for 10 years (ATO compliance period for potential audits).
- **Access Logging**: Audit logs for BAS events must be accessible to the practice principal and to any accountant with admin-level access to the practice. They must not be accessible to business owners (portal users).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero BAS lodgements prepared using the wrong GST basis — the system must enforce basis selection before displaying any figures.
- **SC-002**: 100% of clients with Xero payroll connected have W1/W2 auto-populated for any quarter where payroll data exists.
- **SC-003**: The "Uncoded" label replaces all instances of "Manual Required" across the BAS workflow within this feature.
- **SC-004**: Transaction amounts display cents in 100% of instances across the BAS workflow and transaction list.
- **SC-005**: Quarter selection is preserved without loss in 100% of tab-switch events (BAS ↔ Insights) within a session.
- **SC-006**: Zero relevance errors on Insights tab — e.g., no "register for GST" insight for an already-registered client — in manual testing across 5 representative client profiles.
- **SC-007**: Zero duplicate insights rendered in the same Insights tab view.
- **SC-008**: All insights in the "Urgent" section have a confidence score ≥ 70%.
- **SC-009**: The "Retry" button on the error screen successfully re-triggers a data fetch in 100% of attempts where the underlying error has resolved.
- **SC-010**: A blocking warning with explicit "Proceed" / "Go back" options appears on BAS load for 100% of clients with one or more unreconciled Xero transactions for the selected period.
- **SC-011**: Quarter context is preserved across BAS, Insights, and Dashboard tabs — not just BAS ↔ Insights.
- **SC-012**: An accountant can generate and send an Insights summary report alongside a BAS lodgement confirmation without leaving Clairo.

## Clarifications

### Session 2026-04-24

- Q: Should the system allow changing the GST basis after a BAS has been lodged for that period? → A: Yes — warn with an elevated message ("This period is lodged. Changing basis requires an amended BAS.") but permit the change. The accountant must confirm two sequential warnings.
- Q: When should the PAYG Instalment (T1/T2) section be visible in the BAS workflow? → A: Always visible for all clients regardless of enrolment status; accountants leave it blank if not applicable.
- Q: For insights below 70% confidence, should they appear in "For Review" or be suppressed entirely? → A: Always show in "For Review" — no insight is suppressed on confidence grounds alone; all insights are visible, routed by score.
- Q: Do any of these fixes apply to the business owner view? → A: Yes — all applicable fixes extend to the business owner view (accessed via magic link email). Display fixes (cents precision, "Uncoded" label, quarter context in Insights, insight quality) apply to both accountant and business owner views. Edit-only features (GST basis selection, PAYGW entry, PAYG instalment entry) are accountant-only as the business owner view is read-only.
- Q: Where should the overdue lodgement count in Insights be sourced from? → A: Clairo's own lodgement records, with a manual override — accountant can mark a lodgement as overdue or clear the flag if ATO status differs from Clairo's records.
- Q: How should the Insights summary be delivered to clients alongside the BAS lodgement confirmation? → A: Accountant's choice per client — they decide whether to include it and in what format (inline email, PDF attachment, or magic link to web page).
- Q: Are clients quarterly BAS filers or monthly IAS filers (determines T1/T2 vs T7/T8/T9 field labels)? → A: Quarterly BAS filers — correct labels are T1 (instalment income) and T2 (instalment rate or amount).
- Q: Should the Request Client Input workflow (client-facing labels and ordering) be fixed in this spec? → A: Yes — apply the same label ("Needs tax code") and date descending ordering fixes to the client-facing flow for consistency.

## Assumptions

- The Xero API supports filtering transactions by payment date (cash basis) or invoice date (accrual basis) — this is confirmed by the Xero API design.
- Xero payroll data is accessible via the same Xero OAuth connection already in use; no additional OAuth scope is required (assumption — verify during planning).
- The GST basis preference is a new field on the existing client record — no new table is required, but a schema migration will be needed.
- The confidence score for insights already exists in the data model (based on the Insights tab design being described as "working well"); this spec updates the routing rules, not the scoring mechanism.
- "Whole-dollar rounding" for ATO lodgement files is handled at export time, not at the display layer — this spec addresses only the display layer.
- The BAS quarter selector state is currently managed client-side; the fix for tab-switching context loss is a frontend-only state management change.
- Business owners access their view via magic link email (no separate portal app). Display fixes in this spec (cents precision, transaction labels, Insights quality, quarter context) apply to the business owner's magic-link view as well as the accountant UI. Edit-only features (GST basis selection, PAYGW/PAYG instalment entry) are accountant-only.
