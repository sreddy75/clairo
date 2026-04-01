# Spec 047: Client Transaction Classification

## Origin

First domain validation session (2026-03-15). Vik (accountant) and Unni (tax agent) tested Spec 046 (AI Tax Code Resolution) and identified a critical workflow gap:

> When the platform surfaces unresolved transactions during BAS prep, it's the **client** (business owner) who knows what the transaction was for — not the accountant. The accountant needs the client to classify it, and needs an **audit trail** proving the client made the claim. If ATO audits, the accountant must show it was the client who asserted the nature of the transaction.

This is not a nice-to-have. It's a compliance requirement for the accountant's professional protection.

## Problem

1. Spec 046 surfaces unresolved transactions and suggests tax codes via AI — but assumes the **accountant** resolves them
2. In reality, the accountant often **cannot** classify a transaction because they don't know what the client spent money on
3. Currently there is no way to get the client's input from within the platform
4. Without a recorded audit trail of the client's classification, the accountant carries the liability risk

## Solution

A lightweight client-facing flow where the business owner classifies their own transactions in **plain English** — never seeing tax codes. The AI then maps their description to the correct BAS tax code. The accountant reviews, approves or overrides, and the full chain is recorded as an audit trail.

### Key Principle: Clients speak English, not tax codes

The client never sees "GST on Expenses" or "BAS Excluded." They see:
- Their transaction (date, amount, bank description)
- A question: "What was this for?"
- Smart categories in plain English + free text option

The AI handles the translation to tax codes. The accountant handles the approval.

## User Stories

### US-1: Accountant requests client classification
**As an** accountant preparing BAS
**I want to** send my client a request to classify their unresolved transactions
**So that** I get their input without phone calls or emails, with a recorded audit trail

### US-2: Client classifies transactions
**As a** business owner
**I want to** quickly tell my accountant what each flagged transaction was for
**So that** my BAS is prepared correctly without back-and-forth

### US-3: AI maps client descriptions to tax codes
**As the** system
**I want to** translate the client's plain-English description into the correct BAS tax code
**So that** the client doesn't need to understand tax codes

### US-4: Accountant reviews client classifications
**As an** accountant
**I want to** see what the client said alongside the AI's suggested tax code
**So that** I can approve correct classifications and override incorrect ones

### US-6: System auto-flags transactions needing receipts
**As an** accountant
**I want** the system to automatically flag transactions that require a supporting invoice or receipt
**So that** I don't have to manually tag each one, and the client knows what evidence to provide

### US-5: Audit trail records the full chain
**As an** accountant
**I want** every classification to record: who said what, when, and what was approved
**So that** I have ATO-ready evidence if the client is audited

## Functional Requirements

### Accountant Side (BAS Prep)

**FR-1**: From the BAS preparation screen, when unresolved transactions exist, the accountant can click "Request Client Input" to initiate a classification request.

**FR-2**: The accountant can select which unresolved transactions to include in the request (all, or a filtered subset). The accountant can also manually flag specific transactions as "receipt required" before sending.

**FR-3**: The accountant can add a message to the client (e.g., "Please classify these before Friday").

**FR-4**: The system looks up the client's email from `XeroClient.email` (synced from Xero). If the client has no email on file, the accountant is prompted to enter one manually (with option to save it to the contact record). The system then generates a magic link and sends the client an email via Resend using the existing portal email infrastructure.

**FR-5**: The BAS prep screen shows the status of the request: Sent, Viewed, In Progress, Completed.

**FR-6**: When the client submits their classifications, the accountant receives a notification (in-app + email).

**FR-7**: The accountant reviews client classifications inline within the existing `TaxCodeResolutionPanel` (no separate review screen). When a classification request exists, a "Client Said" column is added to the suggestion table showing the client's input (category, free-text description, or "Personal expense" / "Needs help" flags) alongside the AI-suggested tax code and approve/override controls. A compact summary line ("N classified by client · N reviewed") replaces the standalone `ClassificationReview` component. This eliminates duplicate display of the same transactions across separate tables.

### Client Side (Magic Link Flow)

**FR-8**: The client receives an email with a secure, time-limited link (7-day expiry). No account creation required.

**FR-9**: Clicking the link authenticates the client via the existing portal magic link system and lands them on a transaction classification page.

**FR-10**: The client sees a list of transactions, each showing:
- Date
- Amount
- Bank/payee description
- Any existing AI suggestion as a hint (in plain English, not tax code)
- A "receipt needed" flag with reason, if auto-flagged or manually flagged by accountant

**FR-11**: For each transaction, the client can:
- Select from **plain-English smart categories** (see Category Taxonomy below)
- Type a free-text description if no category fits
- Mark as "Personal / Not business" (important — removes from BAS)
- Mark as "I don't know — ask my accountant"
- Attach a receipt/invoice when flagged (uses existing portal document upload)

**FR-12**: The client can save progress and return later (within the link expiry window).

### Auto-Flagging: Receipt / Invoice Required

**FR-20**: The system automatically flags transactions that require a supporting document (invoice or receipt) based on the following rules, evaluated in order:

| Rule | Condition | Why |
|------|-----------|-----|
| **ATO tax invoice rule** | Expense transaction > $82.50 where the client's category implies GST credits | ATO requires a valid tax invoice to claim GST input credits on purchases over $82.50. This is law, not a judgment call. |
| **Capital / asset purchases** | Client selects "Computer & IT equipment" or "Tools & equipment" | Instant asset write-off claims need evidence of purchase |
| **Entertainment** | Client selects "Meals & entertainment" | FBT implications, 50% deductibility rules require documentation |
| **Subcontractor payments** | Client selects "Subcontractor payment" | TPAR reporting requires ABN + invoice |
| **Vague bank description** | Bank description is cryptic: fewer than 5 meaningful characters, or matches patterns like "TRANSFER", "PAYMENT", "DIRECT DEBIT", "ATM", "EFT" | No paper trail without a receipt when the description alone doesn't explain the transaction |

**FR-21**: Transactions flagged for a receipt show a clear visual indicator to the client: "Please attach a receipt or invoice" with the reason (e.g., "Required for GST credit claims over $82.50"). The flag is informational — the client can still submit without attaching a document, but unattached flagged items are highlighted in the accountant's review.

**FR-22**: The accountant can manually flag additional transactions for receipt upload when creating the classification request (override). These manual flags are in addition to the auto-flags, not a replacement.

**FR-23**: The receipt flag status is recorded in the audit trail: whether a receipt was requested (auto or manual), whether the client attached one, and the document ID if attached.

**FR-13**: The client submits when done. Partial submissions are accepted (not all transactions must be classified).

### AI Tax Code Mapping

**FR-14**: When the client submits, the system takes each client description and maps it to a BAS tax code using the Spec 046 suggestion engine (LLM tier), with the client's description as additional context.

**FR-15**: The AI suggestion includes a confidence score. Low-confidence mappings (<0.7) are flagged for accountant attention.

**FR-16**: The mapping uses the client's description + transaction data (amount, account, payee) + any category selection to produce the tax code suggestion.

### Audit Trail

**FR-17**: Every client classification is recorded with:
- `classified_by`: client identifier (portal session / connection ID)
- `classified_at`: timestamp
- `client_description`: what the client said (free text or category)
- `client_category`: the plain-English category selected (if any)
- `ai_suggested_code`: the tax code the AI mapped to
- `ai_confidence`: confidence score
- `accountant_action`: approved / overridden
- `accountant_user_id`: who approved
- `approved_at`: timestamp
- `final_tax_code`: what was actually applied
- `override_reason`: if overridden, why
- `receipt_required`: whether a receipt was flagged (auto or manual)
- `receipt_flag_reason`: why the receipt was flagged (e.g., "GST credit > $82.50")
- `receipt_attached`: whether the client uploaded a document
- `receipt_document_id`: link to the uploaded document (if any)

**FR-18**: The audit trail is queryable per client, per BAS period, and exportable as a compliance report.

**FR-19**: The audit record is immutable once created. Overrides create new records, they don't modify existing ones.

## Category Taxonomy (Plain English)

These are the categories the client sees. They map to groups of BAS tax codes, not 1:1.

### Business Expense Categories
| Client Sees | Maps To (typical) | Notes |
|------------|-------------------|-------|
| Office supplies & stationery | GST on Expenses | |
| Computer & IT equipment | GST on Expenses | May trigger instant asset write-off |
| Tools & equipment | GST on Expenses | May trigger instant asset write-off |
| Travel & transport | GST on Expenses / GST Free | Depends on type |
| Fuel & vehicle expenses | GST on Expenses | |
| Meals & entertainment | GST on Expenses (50% for entertainment) | Special FBT rules |
| Advertising & marketing | GST on Expenses | |
| Professional services (legal, accounting) | GST on Expenses | |
| Insurance | GST Free / Input Taxed | Depends on type |
| Rent & property | GST on Expenses / Input Taxed | Depends on property type |
| Phone & internet | GST on Expenses | |
| Subscriptions & software | GST on Expenses / GST Free | Overseas = GST Free |
| Stock & inventory | GST on Expenses | |
| Subcontractor payment | GST on Expenses | May need TPAR reporting |
| Bank fees & charges | GST Free (Input Taxed) | Financial supplies |
| Government fees & charges | GST Free | |
| Training & education | GST on Expenses / GST Free | Depends on provider |
| Donations & gifts | GST Free | |

### Income Categories
| Client Sees | Maps To (typical) |
|------------|-------------------|
| Sale of goods | GST on Income |
| Service income | GST on Income |
| Rental income | GST on Income / Input Taxed |
| Interest received | GST Free (Input Taxed) |
| Government grant | GST Free |

### Special Categories
| Client Sees | Effect |
|------------|--------|
| Personal expense — not business | Excluded from BAS entirely |
| I don't know — my accountant can decide | Flagged for accountant, no AI mapping |
| Other (please describe) | Free text → AI mapping |

**Note**: The AI uses the category + transaction context to determine the exact tax code. The categories are guidance for the client, not a rigid 1:1 mapping.

## Client Contact Data

The client's email is already available from Xero sync:

| Field | Source | Model |
|-------|--------|-------|
| `email` | `Xero Contact.EmailAddress` | `XeroClient.email` (String, nullable) |
| `contact_number` | First phone from `Xero Contact.Phones` | `XeroClient.contact_number` (String, nullable) |
| `phones` | Full phone array | `XeroClient.phones` (JSONB, nullable) |

**Email is the primary delivery channel.** The `XeroClient.email` field is populated during contact sync from Xero's `EmailAddress` field. Most business contacts in Xero have an email address.

**Missing email handling**: If `XeroClient.email` is null, the UI prompts the accountant to enter the client's email manually. The manually-entered email is stored on the classification request (not written back to Xero) so it's available for future requests.

**Future**: SMS delivery via `contact_number` / `phones[type=MOBILE]` is out of scope for this spec but the data is there when needed.

## Infrastructure Reuse

This feature is intentionally built on top of existing systems:

| Component | Source | What We Reuse |
|-----------|--------|---------------|
| Magic link auth | Spec 030 (Portal) | `MagicLinkService`, `PortalSession`, `CurrentPortalClient` dependency |
| Portal frontend | Spec 030 | Layout, verify flow, `portalApi` client, PWA service worker |
| Email templates | Spec 030 | `PortalEmailTemplates` pattern, Resend integration |
| Tax code suggestions | Spec 046 | `TaxCodeSuggestion` model, LLM suggestion tier, confidence scoring |
| Document upload | Spec 030 | `PortalDocument` model, upload endpoints |
| Audit events | Spec 046 | `BASAuditEventType` pattern, audit logging |

### New Components Needed

| Component | Description |
|-----------|-------------|
| `ClassificationRequest` model | Links BAS period + client + selected transactions |
| `ClientClassification` model | Per-transaction: client description, category, AI mapping, accountant action |
| Classification request API (accountant) | Create request, check status, review/approve |
| Classification submission API (client) | Get transactions, submit classifications |
| Email template | "Your accountant needs you to classify transactions" |
| Frontend: accountant request flow | Button in BAS prep, status indicator, review screen |
| Frontend: client classification page | `/portal/classify/[request_id]` |

## Non-Functional Requirements

**NFR-1**: Client page must load in <3 seconds on mobile (most business owners will open on their phone).

**NFR-2**: Magic link must expire after 7 days (configurable per tenant).

**NFR-3**: Client classification page must work offline (PWA) — save progress locally, sync when online.

**NFR-4**: All client-submitted data is tenant-isolated (existing RLS).

**NFR-5**: Maximum 200 transactions per classification request (UX limit — beyond this, split into batches).

## Out of Scope (for this spec)

- Full business owner portal dashboard (Spec 030 broader scope)
- Xero write-back of tax codes (deferred in Spec 046)
- Automated reminders for unresponded requests (use existing portal reminder templates later)
- SMS/WhatsApp delivery of magic link (email only for now)
- Multi-language support

## Success Metrics

- Client response rate >60% within 48 hours of receiving the link
- Average time to classify 10 transactions <5 minutes
- Accountant override rate <20% (AI mapping accuracy from client descriptions)
- 100% of classifications have complete audit trail
- Vik and Unni confirm the audit trail meets their ATO compliance needs

## Dependencies

- Spec 046 (AI Tax Code Resolution) — COMPLETE
- Spec 030 (Portal infrastructure) — COMPLETE (backend + frontend + auth)
- Resend email service — COMPLETE (not yet wired to portal invitations)
