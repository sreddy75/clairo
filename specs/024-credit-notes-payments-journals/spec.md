# Feature Specification: Credit Notes, Payments & Journals

**Feature Branch**: `024-credit-notes-payments-journals`
**Created**: 2026-01-01
**Status**: Draft
**Phase**: E (Data Intelligence)

## Overview

Sync Credit Notes, Payments, and Journals from Xero to complete the financial picture. Currently, Clairo only syncs invoices and bank transactions, missing critical data for accurate GST calculations, cash flow analysis, and audit trails.

**Why This Matters**:
- Credit Notes affect GST calculations but are currently missing
- Payments show when cash actually moved (vs invoice date)
- Journals provide complete audit trail for anomaly detection
- Gap analysis: We're missing ~30% of financial transaction data
- Foundation for accurate cash flow forecasting

**Disruption Level**: Medium - modifies existing GST calculations

---

## User Scenarios & Testing

### User Story 1 - View Credit Notes (Priority: P1)

As an accountant preparing BAS, I want to see all credit notes for a client so that I can ensure GST adjustments are correctly calculated.

**Why this priority**: Credit notes directly impact GST liability. Missing credit notes means incorrect BAS figures - a compliance risk.

**Independent Test**: Navigate to client → Transactions → Credit Notes tab → see all credit notes with GST amounts.

**Acceptance Scenarios**:

1. **Given** a client with credit notes in Xero, **When** I view the Credit Notes tab, **Then** I see all credit notes with date, contact, amount, GST, and status.

2. **Given** a credit note allocated to an invoice, **When** I view credit note details, **Then** I see which invoice(s) it's allocated against and remaining credit balance.

3. **Given** credit notes exist for the BAS period, **When** the GST calculation runs, **Then** credit note GST is subtracted from output GST (reducing liability).

---

### User Story 2 - GST Calculation with Credit Notes (Priority: P1)

As an accountant, I want credit notes automatically included in GST calculations so that the BAS worksheet shows accurate figures without manual adjustments.

**Why this priority**: This is the core compliance requirement - incorrect GST = ATO penalties.

**Independent Test**: Generate BAS worksheet → verify credit note GST reduces output GST total.

**Acceptance Scenarios**:

1. **Given** invoices with $10,000 GST and credit notes with $500 GST, **When** I generate BAS worksheet, **Then** output GST shows $9,500 (net of credit notes).

2. **Given** a credit note allocated to a prior period invoice, **When** generating BAS, **Then** the credit note GST is applied to the period the credit note was issued (not the original invoice period).

3. **Given** purchase credit notes (supplier refunds), **When** generating BAS, **Then** input GST is reduced by the credit note GST amount.

---

### User Story 3 - View Payment History (Priority: P1)

As an accountant, I want to see all payments made and received so that I can track actual cash flow versus invoiced amounts.

**Why this priority**: Cash flow is critical for business health. Invoices show what's owed; payments show what's been collected.

**Independent Test**: Navigate to client → Payments tab → see all payments with dates, amounts, and linked invoices.

**Acceptance Scenarios**:

1. **Given** a client with payments in Xero, **When** I view Payments, **Then** I see all payments with date, contact, amount, and payment method.

2. **Given** a payment linked to multiple invoices, **When** I view payment details, **Then** I see the allocation breakdown across invoices.

3. **Given** an overpayment exists, **When** viewing payment details, **Then** I see the overpayment amount and how it was applied (prepayment or credit).

---

### User Story 4 - Cash Flow Analysis (Priority: P2)

As an accountant, I want AI insights to use actual payment dates so that cash flow forecasts are based on real collection patterns.

**Why this priority**: Invoice dates don't reflect when cash arrives. Payment data enables accurate cash flow predictions.

**Independent Test**: AI chat about cash flow uses payment dates rather than invoice dates for analysis.

**Acceptance Scenarios**:

1. **Given** payment history exists, **When** AI analyzes cash flow, **Then** it references actual payment dates and average collection days.

2. **Given** recurring payments to a supplier, **When** AI forecasts cash needs, **Then** it predicts upcoming payments based on historical patterns.

3. **Given** a debtor with slow payment history, **When** AI generates collection insights, **Then** it highlights the average days-to-pay for that contact.

---

### User Story 5 - View Journals (Priority: P2)

As an accountant, I want to see journal entries so that I can trace the complete audit trail for any transaction.

**Why this priority**: Journals are the source of truth in accounting. They show exactly what was debited and credited.

**Independent Test**: Navigate to client → Journals tab → see journal entries with debits and credits.

**Acceptance Scenarios**:

1. **Given** a client with journal entries, **When** I view Journals, **Then** I see all journals with date, narration, and line items (account, debit, credit).

2. **Given** a system-generated journal (from invoice posting), **When** viewing journal details, **Then** I see the source transaction reference.

3. **Given** a manual journal, **When** viewing journal details, **Then** I see it's marked as user-created with the creator's name.

---

### User Story 6 - Manual Journals Sync (Priority: P2)

As an accountant, I want manual journal entries synced so that adjusting entries are included in the financial picture.

**Why this priority**: Manual journals are used for adjustments, accruals, and corrections. Missing them means incomplete data.

**Independent Test**: Manual journals created in Xero appear in Clairo within sync interval.

**Acceptance Scenarios**:

1. **Given** a manual journal in Xero, **When** sync runs, **Then** the journal appears in Clairo with all line items.

2. **Given** a manual journal marked as "Show in Reports", **When** viewing reports, **Then** the journal affects account balances.

3. **Given** a reversing journal, **When** viewing journals, **Then** both the original and reversal are shown with linkage.

---

### User Story 7 - Audit Trail Insights (Priority: P3)

As an accountant, I want AI to detect unusual journal patterns so that I can identify potential errors or fraud.

**Why this priority**: Unusual journals (large round amounts, unusual accounts, weekend entries) may indicate issues.

**Independent Test**: AI identifies and alerts on unusual journal patterns.

**Acceptance Scenarios**:

1. **Given** a journal with an unusually large amount, **When** AI analyzes transactions, **Then** it flags it for review with context.

2. **Given** multiple journals to the same account in quick succession, **When** AI runs anomaly detection, **Then** it highlights the pattern.

3. **Given** a journal to an account not typically used, **When** AI analyzes, **Then** it suggests reviewing the entry.

---

### Edge Cases

- What happens when a credit note is voided after sync?
  → Sync detects voided status, update local record, recalculate GST

- How are credit notes in foreign currency handled?
  → Store in original currency plus base currency equivalent using Xero's rate

- What if a payment is deleted in Xero?
  → Soft delete locally, maintain audit trail, flag for reconciliation review

- How are prepayments (payments before invoice) handled?
  → Create prepayment record, allocate when invoice is created

- What about payments split across multiple accounts?
  → Store allocation details per account from Xero

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST sync Credit Notes from Xero with full allocation details
- **FR-002**: System MUST sync Payments (received and made) with invoice/bill linkage
- **FR-003**: System MUST sync Journals (system-generated) for audit trail
- **FR-004**: System MUST sync Manual Journals (user-created) with line items
- **FR-005**: System MUST include credit note GST in BAS calculations
- **FR-006**: System MUST track payment allocations across invoices
- **FR-007**: System MUST distinguish between overpayments and prepayments
- **FR-008**: System MUST link journals to their source transactions
- **FR-009**: System SHOULD detect unusual journal patterns for AI insights
- **FR-010**: System MUST handle voided/deleted transactions gracefully
- **FR-011**: System MUST support multi-currency credit notes and payments

### Key Entities

- **XeroCreditNote**: Credit note with allocations, GST, status
- **XeroPayment**: Payment with invoice/bill allocations
- **XeroOverpayment**: Overpayment with allocation tracking
- **XeroPrepayment**: Prepayment before invoice creation
- **XeroJournal**: System-generated journal entry
- **XeroManualJournal**: User-created adjusting entry
- **XeroJournalLine**: Individual debit/credit line

### Non-Functional Requirements

- **NFR-001**: Credit Note/Payment sync MUST complete within existing sync window
- **NFR-002**: Journal queries MUST respond in <500ms
- **NFR-003**: All transaction data MUST be retained for 7 years (ATO compliance)
- **NFR-004**: Credit note impact on GST must be calculated in <100ms

---

## Auditing & Compliance Checklist

### Audit Events Required

- [x] **Data Access Events**: Yes - viewing credit notes, payments, journals is sensitive
- [x] **Data Modification Events**: Yes - syncing financial transaction data
- [x] **Integration Events**: Yes - Xero API calls for data fetching
- [x] **Compliance Events**: Yes - credit notes affect GST calculations

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| `credit_note.synced` | Credit note sync | client_id, credit_note_id, amount | 7 years | None |
| `payment.synced` | Payment sync | client_id, payment_id, amount | 7 years | None |
| `journal.synced` | Journal sync | client_id, journal_id, type | 7 years | None |
| `gst.calculated` | BAS worksheet generation | client_id, period, gross_gst, net_gst, credit_note_adjustment | 7 years | None |
| `credit_note.viewed` | User views credit note | user_id, client_id, credit_note_id | 5 years | None |

### Compliance Considerations

- **ATO Requirements**: All GST-affecting transactions must be retained 7 years
- **Credit Note Rules**: Credit notes must be allocated to same BAS period as issued
- **Audit Trail**: Journals provide the authoritative record for all transactions

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of credit notes synced within 24 hours of creation in Xero
- **SC-002**: GST calculations include credit notes with >99.9% accuracy
- **SC-003**: Payment data available for cash flow analysis on all clients
- **SC-004**: Journal-based audit trail complete for all synced transactions
- **SC-005**: Unusual journal detection identifies >80% of anomalies flagged by auditors

---

## Technical Notes (for Plan phase)

### Xero API Endpoints

```
GET /CreditNotes
GET /CreditNotes/{CreditNoteID}
GET /CreditNotes/{CreditNoteID}/Allocations

GET /Payments
GET /Payments/{PaymentID}

GET /Overpayments
GET /Overpayments/{OverpaymentID}/Allocations

GET /Prepayments
GET /Prepayments/{PrepaymentID}/Allocations

GET /Journals
GET /Journals/{JournalID}

GET /ManualJournals
GET /ManualJournals/{ManualJournalID}
```

### Key Relationships

```
Invoice ──────────────────────────────────► XeroInvoice (existing)
   │                                              │
   │ allocated by                                 │ paid by
   ▼                                              ▼
CreditNote ──────────────────────────────► XeroCreditNote
   │                                              │
   │                                              │ posted as
   │                                              ▼
   └─────────────────────────────────────► XeroJournal
```

### GST Calculation Update

```python
# Current (incomplete)
output_gst = sum(invoice.gst for invoice in invoices)

# After (complete)
output_gst = (
    sum(invoice.gst for invoice in invoices)
    - sum(credit_note.gst for credit_note in sales_credit_notes)
)

input_gst = (
    sum(bill.gst for bill in bills)
    - sum(credit_note.gst for credit_note in purchase_credit_notes)
)
```

---

## Dependencies

- **Spec 003 (Xero OAuth)**: Required - valid Xero connection ✓
- **Spec 004 (Xero Data Sync)**: Required - sync infrastructure ✓
- **Spec 023 (Xero Reports API)**: Required - report data for context ✓
- **Spec 007 (BAS Calculation)**: Modified - add credit note adjustment
