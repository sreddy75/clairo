# Feature Specification: BAS Compliance Round 2 — Figures Accuracy & Field Usability

**Feature Branch**: `063-bas-compliance-xero-figures`  
**Created**: 2026-04-29  
**Status**: Draft

## Background

This spec addresses four confirmed bugs surfaced during continued live trial testing of the BAS preparation workflow (Spec 062 follow-up, retested 28 April 2026 by Unni Ashok, Ashok Business Consulting Group). Two are regressions from 062 fixes that partially landed; two are newly identified root causes.

All four bugs have the potential to produce an incorrect BAS if they remain in production:

| Bug | Severity | Impact |
|-----|----------|--------|
| W1/W2 lock-out after first save | High | PAYG Withholding cannot be entered or corrected |
| Unreconciled warning not triggering | High | Accountant proceeds on bad data without warning |
| BAS figures don't match Xero | Critical | Incorrect GST reported to ATO |
| BAS Excluded treated as uncoded | High | Payroll transactions surfaced as needing client input |

## User Scenarios & Testing *(mandatory)*

### User Story 1 — BAS Figures Match Xero Activity Statement (Priority: P1)

An accountant opens BAS preparation for Heart of Love for Q3 FY26, selects cash basis, and Clairo loads figures. They then download the Xero-generated activity statement for the same client and period. Every GST figure — G1 (total sales), G2, G10, G11, 1A (GST on sales), 1B (GST credits) — matches Xero's statement to the dollar. The accountant can lodge with confidence that Clairo and Xero are in agreement.

**Why this priority**: An accountant lodged a BAS using Clairo figures that differed from Xero. This is a critical compliance failure — the ATO receives an incorrect return and the practice is exposed to liability. No other bug fix matters until the underlying figures are trustworthy.

**Independent Test**: Use a test client whose Xero account has a known activity statement for a closed quarter (Q3 FY26). Select cash basis in Clairo. Compare G1, G10, G11, 1A, 1B line by line against the Xero statement PDF. Values must match within rounding tolerance (≤ $0.01).

**Acceptance Scenarios**:

1. **Given** a client is set to cash basis in Clairo, **When** BAS is calculated for a quarter, **Then** only transactions with a payment/receipt date within that quarter are included — not invoice dates.
2. **Given** a client is set to accrual basis, **When** BAS is calculated for a quarter, **Then** only transactions with an invoice/bill date within that quarter are included — consistent with Xero's accrual reporting.
3. **Given** the accountant selects Q3 FY26 (1 Jan – 31 Mar 2026), **When** Clairo fetches transactions, **Then** no transactions from outside that date window appear in the calculation, regardless of sync order or timezone.
4. **Given** a previously synced dataset, **When** the accountant clicks Recalculate, **Then** the new figures reflect the correct date-filtered, basis-filtered view and match the Xero activity statement for that period.
5. **Given** Clairo figures differ from a Xero statement, **When** the accountant views the BAS cross-check panel, **Then** discrepant fields are highlighted with the Clairo value and the Xero value shown side by side.

---

### User Story 2 — W1/W2 Fields Stay Editable After Save (Priority: P2)

An accountant enters total wages (W1) for a client who has no Xero payroll integration. After tabbing out of the W1 field, the save completes. The accountant then clicks the W2 field, enters the PAYG withheld amount, and tabs out — it saves. Both fields remain editable at all times. The accountant can go back and correct W1 without a page reload.

**Why this priority**: W1/W2 are mandatory BAS fields for any wage-paying business. If the fields lock after the first entry, the PAYG Withholding section cannot be completed without a page reload, making the workflow unusable for any client with wages.

**Independent Test**: Open BAS for any client without Xero payroll data. Enter a value in W1 and blur. Verify the field remains editable. Enter a value in W2. Verify both values persist after reload.

**Acceptance Scenarios**:

1. **Given** a client has no Xero payroll data, **When** the accountant opens the PAYG tab, **Then** W1 and W2 are blank editable number fields.
2. **Given** W1 is blank, **When** the accountant enters a value and blurs the field, **Then** the value is saved, a brief "Saved" indicator appears, and the W1 field remains editable with the entered value.
3. **Given** W1 has been saved, **When** the accountant clicks W2 and enters a value, **Then** the W2 field is editable (not read-only), the value saves on blur, and both W1 and W2 display their saved values.
4. **Given** both W1 and W2 have values, **When** the accountant changes W1 and blurs, **Then** the new W1 saves and W2 is unchanged.
5. **Given** the PAYG tab shows manual entry fields, **When** the page re-renders for any reason (query cache update, tab switch, recalculate), **Then** the manual entry fields are still shown and editable — not replaced by a locked read-only display.
6. **Given** a client has Xero payroll data (auto-populated W1/W2), **When** the accountant views the PAYG tab, **Then** the auto-populated values are shown with a "From Xero Payroll" label, and an override/edit affordance is available.

---

### User Story 3 — Unreconciled Warning Fires on Recalculate (Priority: P2)

An accountant clicks Recalculate for Awning Scape. Xero data shows 116 unreconciled transactions with a $9,100 balance discrepancy. Before BAS figures are shown, a warning dialog appears stating that the period contains unreconciled transactions and that figures may be incomplete. The accountant must explicitly choose to proceed or go back to reconcile in Xero first.

**Why this priority**: Without this warning, an accountant unknowingly prepares a BAS on incomplete bank data. 116 unreconciled transactions with a $9,100 discrepancy is a significant data quality problem that must be surfaced before the accountant can proceed.

**Independent Test**: Open BAS for a client with known unreconciled transactions. Trigger Recalculate. The warning must appear before figures are shown. Dismiss and re-calculate — warning must appear again unless the accountant explicitly chose "Proceed anyway."

**Acceptance Scenarios**:

1. **Given** a BAS session has unreconciled transactions in Xero for the selected period, **When** the accountant triggers Recalculate (not just session selection), **Then** the reconciliation check runs and a warning dialog appears before figures are displayed.
2. **Given** the unreconciled warning appears, **When** the accountant clicks "Dismiss — I'll reconcile in Xero first", **Then** the recalculation is cancelled and the previous (or no) figures remain visible.
3. **Given** the unreconciled warning appears, **When** the accountant clicks "Proceed anyway", **Then** calculation completes, the acknowledgement is remembered for the rest of the session, and a persistent inline banner reads "Warning: figures based on unreconciled data" with the transaction count and discrepancy amount visible.
4. **Given** the accountant has already clicked "Proceed anyway" in this session, **When** they trigger Recalculate again, **Then** the warning modal does NOT reappear — calculation proceeds directly and the inline banner remains.
5. **Given** the accountant has already clicked "Proceed anyway" in this session, **When** they navigate away and return to the same BAS session, **Then** the inline unreconciled banner is still visible.
5. **Given** all transactions for the period are reconciled, **When** the accountant triggers Recalculate, **Then** no warning appears and calculation proceeds immediately.
6. **Given** the reconciliation API call fails, **When** Recalculate is triggered, **Then** a non-blocking inline message explains reconciliation status could not be checked, and calculation is still allowed to proceed.

---

### User Story 4 — BAS Excluded Transactions Not Flagged as Uncoded (Priority: P3)

An accountant for OreScope opens the BAS uncoded transaction panel. Previously, 36 wage payment transactions (Wages Payable - Payroll, coded BAS Excluded in Xero) appeared in the uncoded list and were included in the count and in the "Request Client Input" queue. After this fix, those transactions do not appear in the uncoded list, the uncoded count is zero for wages transactions, and "Request Client Input" does not include BAS Excluded items.

**Why this priority**: Any practice with payroll clients is affected. Surfacing correctly-coded payroll transactions as uncoded erodes accountant trust, triggers unnecessary client communications, and inflates the uncoded transaction count used to assess BAS readiness.

**Independent Test**: Open BAS for a client with payroll transactions coded as BAS Excluded in Xero. Uncoded count must be zero for those transactions. Trigger "Request Client Input" — BAS Excluded items must not appear in the client-facing list.

**Acceptance Scenarios**:

1. **Given** a client has transactions coded with the BAS Excluded tax rate in Xero, **When** the BAS uncoded count is computed, **Then** BAS Excluded transactions are not included in the count.
2. **Given** a client has BAS Excluded transactions, **When** the uncoded transaction panel is opened, **Then** BAS Excluded transactions do not appear in the list — they are treated as intentionally coded, not as needing resolution.
3. **Given** a client has BAS Excluded transactions, **When** the accountant triggers "Request Client Input", **Then** BAS Excluded transactions are not included in the client-facing classification request.
4. **Given** a client has a mix of truly uncoded transactions (null tax code) and BAS Excluded transactions, **When** the uncoded panel is displayed, **Then** only transactions with no tax code assignment are shown; BAS Excluded transactions are absent.
5. **Given** a transaction has tax rate "BAS Excluded" applied in Xero, **When** Clairo syncs and processes that transaction, **Then** it is classified as intentionally excluded and flagged neither for AI suggestion nor for manual resolution.

---

### Edge Cases

- A client has W1 entered manually but later connects Xero payroll — the Xero payroll data must take precedence and be clearly labelled, with the manual value preserved as a fallback visible to the accountant.
- A quarter spans two financial years (e.g., Jun/Jul split) — date filtering must use the exact BAS period start/end dates, not inferred FY boundaries.
- Unreconciled count is 0 but balance discrepancy is non-zero — any non-zero discrepancy triggers the unreconciled warning. If the discrepancy is less than $1.00, the warning message must note "This may be a rounding difference" alongside the exact discrepancy amount. If $1.00 or greater, the standard "figures may be incomplete or inaccurate" message applies.
- BAS Excluded transactions that also have a split with a taxable component — only the BAS Excluded split component should be excluded from the uncoded count; the taxable split must still be evaluated.
- Cash basis sync: transactions paid in a prior quarter but invoiced in the current quarter — must only appear in the quarter the payment date falls within.
- W1 is entered as zero by the accountant explicitly — this must save as 0 and not be treated as "no payroll data", so the field must not revert to blank.

## Requirements *(mandatory)*

### Functional Requirements

**W1/W2 Field Usability**

- **FR-001**: The W1 and W2 manual entry fields MUST remain editable at all times once displayed, regardless of save state or cache updates.
- **FR-002**: The PAYG tab MUST display manual entry fields (W1, W2) when the client has no Xero payroll data, and MUST NOT replace those fields with a read-only display when either field contains a value entered manually.
- **FR-003**: The condition for switching between "Xero payroll auto-populated" and "manual entry" MUST be based on whether Xero payroll data was detected — not on whether W1 > 0. A non-zero W1 from manual entry must not cause the tab to switch to the locked display.
- **FR-004**: After a successful W1 or W2 save, the UI MUST show a transient "Saved" confirmation (≤ 2 seconds) and the field MUST retain focus or return to an editable state.
- **FR-005**: W1 and W2 values MUST persist across tab switches within the same BAS session.

**Unreconciled Warning**

- **FR-006**: The reconciliation check MUST run when the accountant triggers Recalculate, not only on session selection.
- **FR-007**: The unreconciled warning MUST display both the count of unreconciled transactions and the exact dollar amount of the balance discrepancy. If the discrepancy is greater than $0 but less than $1.00, the warning MUST additionally display the note "This may be a rounding difference" to prevent unnecessary alarm.
- **FR-008**: The reconciliation check MUST query the reconciliation status for the exact period dates of the selected BAS session (start_date to end_date), not a cached or approximate range.
- **FR-009**: If the reconciliation API is unavailable, the system MUST allow calculation to proceed with a non-blocking inline notice rather than silently suppressing all warnings.

**BAS Figures Accuracy (Cash Basis)**

- **FR-010**: When a client is set to cash basis, the transaction fetch MUST filter exclusively on payment date (receipts) or payment date (bills) falling within the BAS period — invoice dates MUST NOT be used.
- **FR-011**: When a client is set to accrual basis, the transaction fetch MUST filter on invoice/bill date within the BAS period.
- **FR-012**: The BAS cross-check panel MUST fetch official period figures from Xero's BAS Reports API and display them side by side against Clairo's calculated figures for G1, G10, G11, 1A, and 1B, with discrepant fields visually highlighted.
- **FR-012a**: The cross-check API call MUST be retried up to 2 times (3 attempts total) with a short delay on transient failures (network error, 5xx response) before giving up. Note: rate-limit (429) handling already exists via the Xero rate limiter and must be respected.
- **FR-012b**: If the Xero Reports API call fails after all retries, the cross-check panel MUST display a clear inline message — e.g., "Could not connect to Xero — cross-check unavailable. Try again or verify Xero connection." — rather than showing stale or empty data silently.
- **FR-013**: The system MUST root-cause and document whether the Heart of Love figure discrepancy is caused by: (a) incorrect date filtering, (b) incorrect basis filtering, (c) a period/sync mismatch, or (d) another identified cause — and fix the identified cause.

**BAS Excluded Filtering**

- **FR-014**: Transactions with a Xero tax rate of "BAS Excluded" MUST be excluded from the uncoded transaction count in all contexts: the BAS dashboard count, the uncoded panel list, and the "Request Client Input" selection.
- **FR-015**: The BAS Excluded filter MUST apply consistently across all code paths that compute the uncoded count — including the primary detection pipeline, the session summary, and any batch/background recomputation.
- **FR-016**: "Request Client Input" MUST NOT include any transaction coded BAS Excluded, regardless of account name or description.

### Key Entities

- **BASCalculation**: Holds W1 (`w1_total_wages`), W2 (`w2_amount_withheld`), `payg_source_label` (null = manual entry, non-null = Xero payroll auto-populated), `unreconciled_count`, `unreconciled_amount`, `gst_basis_used`
- **ReconciliationStatus**: Returned by the reconciliation check endpoint — holds `unreconciled_count`, `total_transactions`, `balance_discrepancy`, `as_of` timestamp
- **XeroTransaction**: Has `payment_date`, `invoice_date`, `tax_type` (includes "BASEXCLUDED"), `is_reconciled`, `show_on_cash_basis`
- **TaxCodeSuggestion**: Represents an uncoded transaction needing resolution — must never be created for BASEXCLUDED transactions

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [x] **Data Access Events**: Reads BAS figures (GST, PAYG) — any discrepancy between Clairo and Xero must be traceable
- [x] **Data Modification Events**: W1/W2 manual entry modifies BAS calculation — must be audited
- [x] **Integration Events**: Cash basis filter change affects which Xero transactions appear in BAS figures
- [x] **Compliance Events**: Figures accuracy directly affects BAS lodgements; unreconciled warnings gate the proceed decision

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| `bas.payg.manual_updated` | Accountant saves W1 or W2 manually | session_id, calculation_id, before/after W1, before/after W2, accountant user_id | 7 years | None |
| `bas.reconciliation.warning_shown` | Unreconciled warning displayed | session_id, unreconciled_count, balance_discrepancy, as_of, period dates | 7 years | None |
| `bas.reconciliation.proceed_anyway` | Accountant clicks "Proceed anyway" | session_id, unreconciled_count, balance_discrepancy, accountant user_id | 7 years | None |
| `bas.figures.cross_check_discrepancy` | Cross-check panel detects Xero mismatch | session_id, fields with discrepancy, Clairo values, Xero values, basis_used | 7 years | None |

### Compliance Considerations

- **ATO Requirements**: If a BAS is lodged with incorrect figures due to a cash/accrual basis bug, the practice and client may face ATO penalties. Any fix must be verified against the ATO's own activity statement for the affected client/period before being considered complete.
- **Data Retention**: All PAYG manual entries and reconciliation warning overrides are retained for 7 years per standard ATO audit trail requirements.
- **Access Logging**: Audit logs for W1/W2 changes and reconciliation overrides must be accessible to tenant admins for their own clients only.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Clairo BAS figures for any client/quarter match the equivalent Xero-generated activity statement within $0.01 for all GST fields (G1, G10, G11, 1A, 1B) — verified against Heart of Love Q3 FY26 as the acceptance case.
- **SC-002**: An accountant can enter, save, correct, and re-save W1 and W2 within a single BAS session without a page reload.
- **SC-003**: The unreconciled warning modal fires on every Recalculate where `unreconciled_count > 0` or `balance_discrepancy ≠ 0`, except when the accountant has already clicked "Proceed anyway" in the current session (in which case calculation proceeds silently and the inline banner remains) — verified against Awning Scape with 116 unreconciled and $9,100 discrepancy.
- **SC-004**: Zero BAS Excluded transactions appear in the uncoded count, uncoded panel, or "Request Client Input" queue for any client — verified against OreScope whose 36 wage transactions (Wages Payable - Payroll) are correctly coded BAS Excluded.
- **SC-005**: The root cause of the Heart of Love figure discrepancy is identified, documented, and fixed — confirmed by a side-by-side Clairo vs Xero reconciliation showing zero discrepancy for that client/period after the fix.
- **SC-006**: No regression in T1/T2 (PAYG Instalment) field editability — those fields must continue to behave as they do today after the W1/W2 fix is applied.

## Clarifications

### Session 2026-04-29

- Q: If the accountant already clicked "Proceed anyway" in the current session, does a subsequent Recalculate re-show the warning modal? → A: No — "Proceed anyway" is sticky for the session. Subsequent Recalculates skip the modal and proceed directly; the inline banner remains visible.
- Q: What is the balance discrepancy threshold for triggering the unreconciled warning? → A: Any non-zero discrepancy triggers the warning ($0 threshold). If discrepancy is < $1.00, the warning must include "This may be a rounding difference" alongside the exact amount. $1.00+ shows the standard incomplete-data message.
- Q: Where do the Xero figures in the BAS cross-check panel come from? → A: Xero's BAS Reports API (`GET /Reports/BAS`). Retry up to 2 times on transient failure; on final failure show "Could not connect to Xero — cross-check unavailable" inline. Existing rate-limit (429) handling applies. Note: no general HTTP retry logic exists today in the Xero client — this must be added for this call.

## Assumptions

- The `payg_source_label` field on `BASCalculation` (or equivalent backend flag) reliably distinguishes Xero-auto-populated W1/W2 from manually entered W1/W2. If this field does not exist, a `payg_data_source` enum (`xero_payroll` | `manual`) must be added.
- "BAS Excluded" in Xero corresponds to the tax type string `"BASEXCLUDED"` in the Xero API response — no other strings map to this concept.
- The unreconciled count and balance discrepancy figures come from the existing `/reconciliation-status` endpoint; the fix is in when and how the frontend invokes it (on Recalculate, not just session selection).
- The Heart of Love discrepancy will be root-caused by inspecting which transactions are included vs excluded compared to the Xero BAS Reports API response. The cross-check panel calls `GET /Reports/BAS` directly — this is a new Xero API call not previously used in the codebase. The Xero client's existing rate-limiter applies; a 2-retry wrapper for transient errors must be added.
