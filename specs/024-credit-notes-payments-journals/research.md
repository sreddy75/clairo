# Research: Credit Notes, Payments & Journals

**Feature**: 024-credit-notes-payments-journals
**Date**: 2026-01-01
**Status**: Complete

---

## Research Tasks

### 1. Xero Credit Notes API

**Decision**: Use Xero Accounting API v2.0 CreditNotes endpoints

**Endpoints**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/CreditNotes` | GET | List all credit notes (paginated) |
| `/CreditNotes/{CreditNoteID}` | GET | Get single credit note with full details |
| `/CreditNotes/{CreditNoteID}/Allocations` | GET | Get allocations for credit note |

**Credit Note Structure**:
```json
{
  "CreditNoteID": "uuid",
  "CreditNoteNumber": "CN-0001",
  "Type": "ACCPAYCREDIT | ACCRECCREDIT",
  "Contact": { "ContactID": "uuid", "Name": "..." },
  "Date": "2025-12-15",
  "DueDate": "2025-01-15",
  "Status": "DRAFT | SUBMITTED | AUTHORISED | PAID | VOIDED",
  "LineAmountTypes": "Exclusive | Inclusive | NoTax",
  "SubTotal": 1000.00,
  "TotalTax": 100.00,
  "Total": 1100.00,
  "CurrencyCode": "AUD",
  "CurrencyRate": 1.0,
  "LineItems": [...],
  "Allocations": [
    {
      "AllocationID": "uuid",
      "Invoice": { "InvoiceID": "uuid", "InvoiceNumber": "INV-001" },
      "Amount": 500.00,
      "Date": "2025-12-20"
    }
  ],
  "RemainingCredit": 600.00,
  "UpdatedDateUTC": "/Date(1234567890000)/"
}
```

**Credit Note Types**:
- `ACCPAYCREDIT`: Accounts Payable Credit Note (from supplier)
- `ACCRECCREDIT`: Accounts Receivable Credit Note (to customer)

**Status Values**:
- `DRAFT`: Not yet approved
- `SUBMITTED`: Awaiting approval
- `AUTHORISED`: Approved, can be allocated
- `PAID`: Fully allocated
- `VOIDED`: Cancelled

**Rationale**: Credit notes are essential for accurate GST calculations. Missing credit notes results in overstated GST liability.

---

### 2. Xero Payments API

**Decision**: Use Xero Accounting API v2.0 Payments endpoints

**Endpoints**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/Payments` | GET | List all payments (paginated) |
| `/Payments/{PaymentID}` | GET | Get single payment with details |

**Payment Structure**:
```json
{
  "PaymentID": "uuid",
  "Date": "2025-12-15",
  "Amount": 1500.00,
  "CurrencyRate": 1.0,
  "PaymentType": "ACCRECPAYMENT | ACCPAYPAYMENT | ...",
  "Status": "AUTHORISED | DELETED",
  "Reference": "Payment ref",
  "IsReconciled": true,
  "Account": {
    "AccountID": "uuid",
    "Code": "090",
    "Name": "Bank Account"
  },
  "Invoice": {
    "InvoiceID": "uuid",
    "InvoiceNumber": "INV-001",
    "Type": "ACCREC | ACCPAY"
  },
  "CreditNote": {
    "CreditNoteID": "uuid",
    "CreditNoteNumber": "CN-001"
  },
  "Prepayment": { ... },
  "Overpayment": { ... },
  "UpdatedDateUTC": "/Date(1234567890000)/"
}
```

**Payment Types**:
- `ACCRECPAYMENT`: Accounts Receivable Payment (customer pays us)
- `ACCPAYPAYMENT`: Accounts Payable Payment (we pay supplier)
- `ARCREDITPAYMENT`: AR Credit Note refund
- `APCREDITPAYMENT`: AP Credit Note refund
- `ABORECPAYMENT`: AR Overpayment
- `ABOPAYMENT`: AP Overpayment
- `ARPREPAYMENTPAYMENT`: AR Prepayment
- `APPREPAYMENTPAYMENT`: AP Prepayment

**Rationale**: Payments show actual cash movement, essential for cash flow analysis.

---

### 3. Xero Overpayments & Prepayments API

**Decision**: Sync overpayments and prepayments separately

**Overpayment Endpoints**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/Overpayments` | GET | List overpayments |
| `/Overpayments/{OverpaymentID}` | GET | Get single overpayment |
| `/Overpayments/{OverpaymentID}/Allocations` | GET | Get allocations |

**Prepayment Endpoints**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/Prepayments` | GET | List prepayments |
| `/Prepayments/{PrepaymentID}` | GET | Get single prepayment |
| `/Prepayments/{PrepaymentID}/Allocations` | GET | Get allocations |

**Key Difference**:
- **Overpayment**: Customer pays more than invoice amount
- **Prepayment**: Payment received before invoice is created

**Rationale**: Both affect cash flow and need separate tracking for accurate reconciliation.

---

### 4. Xero Journals API

**Decision**: Sync both automatic journals and manual journals

**Journals Endpoint** (System-generated):

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/Journals` | GET | List all journals (paginated) |
| `/Journals/{JournalID}` | GET | Get single journal |

**Note**: Journals endpoint requires Advanced tier and security assessment approval.

**Journal Structure**:
```json
{
  "JournalID": "uuid",
  "JournalDate": "2025-12-15",
  "JournalNumber": 12345,
  "Reference": "INV-001",
  "SourceID": "uuid",
  "SourceType": "ACCREC | ACCPAY | CASHREC | CASHPAID | ...",
  "JournalLines": [
    {
      "JournalLineID": "uuid",
      "AccountID": "uuid",
      "AccountCode": "200",
      "AccountType": "REVENUE",
      "AccountName": "Sales",
      "Description": "Sale of goods",
      "NetAmount": 1000.00,
      "GrossAmount": 1100.00,
      "TaxAmount": 100.00,
      "TaxType": "OUTPUT2",
      "TaxName": "GST on Income"
    }
  ],
  "CreatedDateUTC": "/Date(1234567890000)/"
}
```

**Source Types**:
- `ACCREC`: Accounts Receivable Invoice
- `ACCPAY`: Accounts Payable Bill
- `CASHREC`: Cash Received
- `CASHPAID`: Cash Paid
- `ACCPAYCREDIT`: AP Credit Note
- `ACCRECCREDIT`: AR Credit Note
- `TRANSFER`: Bank Transfer
- `MANJOURNAL`: Manual Journal

---

### 5. Manual Journals API

**Decision**: Sync manual journals for adjusting entries

**Endpoints**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ManualJournals` | GET | List manual journals |
| `/ManualJournals/{ManualJournalID}` | GET | Get single manual journal |

**Manual Journal Structure**:
```json
{
  "ManualJournalID": "uuid",
  "Date": "2025-12-31",
  "Status": "DRAFT | POSTED | DELETED | VOIDED",
  "Narration": "Year-end accrual adjustment",
  "ShowOnCashBasisReports": true,
  "LineAmountTypes": "NoTax",
  "JournalLines": [
    {
      "LineAmount": 500.00,
      "AccountCode": "200",
      "Description": "Accrued revenue",
      "TaxType": "NONE"
    },
    {
      "LineAmount": -500.00,
      "AccountCode": "320",
      "Description": "Accrued revenue contra"
    }
  ],
  "UpdatedDateUTC": "/Date(1234567890000)/"
}
```

**Rationale**: Manual journals contain adjustments, accruals, and corrections that affect the complete financial picture.

---

### 6. GST Calculation with Credit Notes

**Decision**: Adjust GST calculation to include credit notes

**Current Formula (Incomplete)**:
```python
output_gst = sum(invoice.gst for invoice in sales_invoices)
input_gst = sum(bill.gst for bill in purchase_bills)
net_gst = output_gst - input_gst
```

**Updated Formula (Complete)**:
```python
# Output GST (what we owe)
sales_invoice_gst = sum(inv.gst for inv in sales_invoices)
sales_credit_note_gst = sum(cn.gst for cn in sales_credit_notes)
output_gst = sales_invoice_gst - sales_credit_note_gst

# Input GST (what we can claim)
purchase_bill_gst = sum(bill.gst for bill in purchase_bills)
purchase_credit_note_gst = sum(cn.gst for cn in purchase_credit_notes)
input_gst = purchase_bill_gst - purchase_credit_note_gst

# Net GST payable
net_gst = output_gst - input_gst
```

**Credit Note GST Timing**:
- Credit notes apply to the BAS period in which they are **issued** (not the original invoice period)
- Example: Invoice in Oct, Credit Note in Nov → Credit Note GST affects Nov BAS

**Rationale**: ATO requires credit note adjustments in the period the credit note is issued.

---

### 7. Sync Strategy

**Decision**: Incremental sync with modified-since parameter

**Sync Order**:
1. Invoices (existing) - must sync first
2. Credit Notes - reference invoices
3. Payments - reference invoices, credit notes
4. Overpayments/Prepayments - standalone
5. Journals - after all source transactions
6. Manual Journals - after system journals

**Rate Limiting**:
- 60 requests/minute
- Credit Notes, Payments each ~1 request per 100 items
- Journals may require 2-3 requests per sync (pagination)

**Incremental Sync**:
```
If-Modified-Since: {last_sync_timestamp}
```

**Rationale**: Incremental sync minimizes API calls while keeping data current.

---

### 8. Voided/Deleted Transaction Handling

**Decision**: Soft delete with status tracking

**Approach**:
1. On sync, detect status change to `VOIDED` or `DELETED`
2. Update local record status (don't hard delete)
3. Recalculate GST for affected periods
4. Flag for reconciliation review

**Audit Trail**:
- Keep full history of status changes
- Record who/when transaction was voided
- Store original values before void

**Rationale**: ATO requires audit trail; soft delete preserves history while excluding from calculations.

---

## Summary of Decisions

| Area | Decision |
|------|----------|
| Credit Notes | Sync with full allocations, store GST for BAS |
| Payments | Sync all types including overpayments/prepayments |
| Journals | Sync system journals for audit trail |
| Manual Journals | Sync for adjusting entries |
| GST Calculation | Subtract credit note GST from totals |
| GST Timing | Apply to period of credit note issue |
| Sync Strategy | Incremental with modified-since |
| Voided Handling | Soft delete, recalculate GST |

---

## Sources

- [Xero Accounting API - Credit Notes](https://developer.xero.com/documentation/api/accounting/creditnotes)
- [Xero Accounting API - Payments](https://developer.xero.com/documentation/api/accounting/payments)
- [Xero Accounting API - Types and Codes](https://developer.xero.com/documentation/api/accounting/types)
- [Xero API Directory - GetKnit](https://www.getknit.dev/blog/xero-api-directory)
- [Xero Node SDK Documentation](https://xeroapi.github.io/xero-node/accounting/index.html)
