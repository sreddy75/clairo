# Xero Tax Code Write-Back: API Research

**Date**: 2026-03-31
**Context**: Spec 046 (AI Tax Code Resolution) deferred Xero write-back to v2. This document captures the API research for implementing that write-back — syncing accountant-approved tax code mappings from Clairo back into Xero.

## Summary

The Xero Accounting API **supports updating TaxType on existing transactions** via POST endpoints for Bank Transactions, Invoices, and Credit Notes. Clairo already has the required OAuth scopes (`accounting.transactions` grants read/write). No scope changes needed today, though granular scope migration is required before September 2027.

---

## Endpoints

| Transaction Type | Endpoint | Method | Batch Limit |
|---|---|---|---|
| Bank Transactions | `POST /api.xro/2.0/BankTransactions` | Include `BankTransactionID` to update | ~50 per request |
| Invoices | `POST /api.xro/2.0/Invoices` | Include `InvoiceID` to update | ~50 per request |
| Credit Notes | `POST /api.xro/2.0/CreditNotes` | Include `CreditNoteID` to update | ~50 per request |

> **Xero's reversed HTTP conventions**: `PUT` creates new records, `POST` is "update or create" (upsert). If the payload includes an existing ID, it updates; if omitted, it creates.

---

## Request Formats

### Bank Transaction Update

```json
{
  "BankTransactions": [
    {
      "BankTransactionID": "existing-uuid",
      "Type": "SPEND",
      "Contact": { "ContactID": "contact-uuid" },
      "BankAccount": { "AccountID": "bank-account-uuid" },
      "LineItems": [
        {
          "LineItemID": "line-item-uuid",
          "Description": "Office supplies",
          "UnitAmount": 100.00,
          "AccountCode": "400",
          "TaxType": "INPUT",
          "Quantity": 1
        }
      ]
    }
  ]
}
```

### Invoice Update

```json
{
  "Invoices": [
    {
      "InvoiceID": "existing-invoice-uuid",
      "LineItems": [
        {
          "LineItemID": "existing-line-item-uuid",
          "Description": "Consulting services",
          "UnitAmount": 500.00,
          "AccountCode": "200",
          "TaxType": "OUTPUT",
          "Quantity": 1
        }
      ]
    }
  ]
}
```

### Query Parameters

- `summarizeErrors` (boolean, default false) — summarized vs individual validation errors
- `unitdp` (integer) — decimal places for unit amounts
- `idempotencyKey` — prevents duplicate processing

---

## Restrictions

### Reconciled Bank Transactions — CANNOT UPDATE

When `IsReconciled` is `true`, the API rejects modifications to financial fields (line items, amounts, TaxType). The transaction must be unreconciled first via the Xero UI.

### Invoice/Credit Note Status Restrictions

| Status | Can Update TaxType? | Notes |
|---|---|---|
| **DRAFT** | Yes | All fields modifiable |
| **SUBMITTED** | Yes | All fields modifiable |
| **AUTHORISED** | Limited | Restricted once payments/credit notes allocated. Varies by invoice type (ACCREC vs ACCPAY) |
| **PAID** | No | Cannot modify line items or TaxType |
| **VOIDED** | No | No updates possible |

### Lock Dates — API Cannot Bypass

Xero enforces two lock dates:
1. **Period lock date** — stops all users except advisers
2. **Adviser lock date** — stops ALL users including advisers

The API has no override mechanism. Transactions in locked periods will fail to update.

### Line Items Are REPLACED, Not Merged

**Critical**: When updating invoices/credit notes, you MUST include ALL existing line items in the payload. Any line items not included will be **deleted** by Xero.

Required workflow:
1. GET the full transaction (including all line items)
2. Modify only the TaxType on target line items
3. POST the complete line items array back

### TaxType Must Match Account Type

- `OUTPUT` (GST on Income) — only valid on revenue accounts
- `INPUT` (GST on Expenses) — only valid on expense accounts
- Invalid combinations return: `"The TaxType code 'OUTPUT' cannot be used with account code..."`

---

## Tax Types Reference Endpoint

```
GET /api.xro/2.0/TaxRates
```

Returns all tax rates configured for the organization. Always query this per-org rather than hardcoding — orgs may have custom rates.

### Common Australian Tax Types

| TaxType Code | Description | Rate |
|---|---|---|
| `OUTPUT` | GST on Income | 10% |
| `INPUT` | GST on Expenses | 10% |
| `EXEMPTOUTPUT` | GST-Free Income | 0% |
| `EXEMPTINPUT` | GST-Free Expenses | 0% |
| `INPUTTAXED` | Input Taxed (financial supplies) | 0% |
| `BASEXCLUDED` | BAS Excluded | 0% |
| `GSTONIMPORTS` | GST on Imported Goods | 10% |
| `CAPEXINPUT` | GST on Capital Expenses | 10% |
| `CAPEXOUTPUT` | GST on Capital Income | 10% |
| `NONE` | No Tax / Tax Exempt | 0% |

---

## Rate Limits

| Limit | Value |
|---|---|
| Per-minute (per org, per app) | 60 API calls/minute |
| Daily (per org, per app) | 5,000 API calls/day |
| Concurrent (per org, per app) | 5 simultaneous calls |
| App-wide per-minute | 10,000 calls/minute across all tenancies |
| Payload size | 3.5 MB max per POST |
| Batch size | ~50 elements per request (recommended) |

With 50 items per batch at 60 calls/minute = 3,000 transactions/minute theoretical max. But these calls are shared with sync operations.

Rate limit response: HTTP 429 with `Retry-After` header. Existing Celery retry infrastructure handles this.

---

## OAuth Scopes

### Current (Clairo already has these)

- `accounting.transactions` — grants read/write for bank transactions, invoices, credit notes, payments

### Granular Scopes (migration required before Sept 2027)

| Scope | Covers |
|---|---|
| `accounting.banktransactions` | Read + write for bank transactions |
| `accounting.invoices` | Read + write for invoices, credit notes, purchase orders, quotes |
| `accounting.payments` | Read + write for payments |
| `accounting.settings.read` | Read access to tax rates, accounts |

**Timeline**:
- March 2, 2026: New apps must use granular scopes
- April 2026: Xero assigns granular scopes to existing apps in developer portal
- September 2027: Broad scopes fully deprecated

---

## Codebase Readiness

### What exists

- `XeroClient` (`backend/app/modules/integrations/xero/client.py`) — 28 GET methods, zero write methods
- Rate limiter, token refresh, exponential backoff retry — all production-ready
- `XeroSyncJob` tracking, phased orchestration via Celery
- Webhook handler for incoming Xero change notifications

### What needs to be built

- `XeroClient.update_bank_transactions(transactions: list)` — POST to BankTransactions
- `XeroClient.update_invoices(invoices: list)` — POST to Invoices
- `XeroClient.update_credit_notes(credit_notes: list)` — POST to CreditNotes
- `XeroClient.get_tax_rates()` — GET TaxRates for validation
- Pre-flight check service: verify `IsReconciled`, invoice status, lock dates before attempting write
- Write-back Celery task with batching (50/request), rate limit awareness, idempotency keys
- Conflict resolution: handle cases where Xero rejects the update and surface to accountant

---

## Implementation Considerations

### Pre-flight Checks (per transaction)

1. **Bank transactions**: Check `IsReconciled` — if `true`, flag to user (cannot update via API)
2. **Invoices/credit notes**: Check `Status` — only DRAFT/SUBMITTED are safe
3. **Lock dates**: Query org settings (`GET /Organisation`), compare transaction date against lock dates
4. **TaxType validity**: Validate TaxType against account type before sending

### Write-back Flow

1. Accountant approves tax code mapping in Clairo
2. System batches approved mappings per transaction type
3. For each batch:
   a. GET current transaction state (all line items)
   b. Run pre-flight checks
   c. Modify TaxType on target line items only
   d. POST complete payload back with idempotency key
   e. Record success/failure per transaction
4. Surface failures to accountant with actionable context (e.g., "Transaction is reconciled — update in Xero directly")

### Sync Conflict Prevention

- After write-back, update local `TaxCodeOverride` record to mark as synced
- On next Xero sync, the incoming data should match (no conflict)
- If Xero webhook fires for the transaction we just updated, skip re-processing

---

## Sources

- [Xero Accounting API — Bank Transactions](https://developer.xero.com/documentation/api/accounting/banktransactions)
- [Xero Accounting API — Invoices](https://developer.xero.com/documentation/api/accounting/invoices)
- [Xero Accounting API — Credit Notes](https://developer.xero.com/documentation/api/accounting/creditnotes)
- [Xero Accounting API — Tax Rates](https://developer.xero.com/documentation/api/accounting/taxrates)
- [Xero OAuth2 Scopes](https://developer.xero.com/documentation/guides/oauth2/scopes/)
- [Xero API Rate Limits](https://developer.xero.com/documentation/guides/oauth2/limits/)
- [Xero Granular Scopes Announcement (Feb 2026)](https://devblog.xero.com/upcoming-changes-to-xero-accounting-api-scopes-705c5a9621a0)
- [Cannot Update Reconciled Bank Transaction (Forum)](https://developer.xero.com/community-forum-archive/discussion/14596824)
- [Line Item Replacement Behavior (Forum)](https://developer.xero.com/community-forum-archive/discussion/146270086)
- [Lock Dates in Xero](https://central.xero.com/s/article/Set-up-and-work-with-lock-dates)
- [Default Australian Tax Rates](https://central.xero.com/s/article/Default-tax-rates-AU)
