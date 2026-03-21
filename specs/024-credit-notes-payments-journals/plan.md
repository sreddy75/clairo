# Implementation Plan: Credit Notes, Payments & Journals

**Branch**: `024-credit-notes-payments-journals` | **Date**: 2026-01-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/024-credit-notes-payments-journals/spec.md`

## Summary

Extend the Xero integration to sync Credit Notes, Payments (including Overpayments/Prepayments), and Journals (both system-generated and manual). This completes the financial transaction picture and enables accurate GST calculations that account for credit adjustments.

**Technical Approach**:
- Add new models: `XeroCreditNote`, `XeroPayment`, `XeroOverpayment`, `XeroPrepayment`, `XeroJournal`, `XeroManualJournal`
- Extend `XeroClient` with methods for each endpoint
- Extend `XeroSyncService` to include new transaction types
- Modify GST calculation to include credit note adjustments
- Add payment-based cash flow context for AI agents

---

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Pydantic v2, httpx, Celery
**Storage**: PostgreSQL 16 with proper foreign keys to existing Xero tables
**Testing**: pytest, pytest-asyncio, httpx for API testing
**Target Platform**: AWS ECS/Fargate (Sydney region)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Sync additional entities within existing sync window, GST calc <100ms
**Constraints**: Xero rate limit 60 req/min, ATO 7-year data retention
**Scale/Scope**: Up to 10,000 credit notes/payments per client

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **Modular Monolith** | ✅ PASS | Extends existing `integrations/xero/` module |
| **Repository Pattern** | ✅ PASS | New repositories for each entity type |
| **Multi-tenancy (RLS)** | ✅ PASS | All new tables include `tenant_id` |
| **Audit-First** | ✅ PASS | Audit events for sync and GST calculations |
| **Type Hints** | ✅ PASS | Pydantic schemas, typed functions |
| **Test-First** | ✅ PASS | Contract tests for Xero API, integration tests |
| **API Conventions** | ✅ PASS | RESTful endpoints under existing paths |
| **External Integration Pattern** | ✅ PASS | Rate limiting, error handling per constitution |

**No violations requiring justification.**

---

## Project Structure

### Documentation (this feature)

```text
specs/024-credit-notes-payments-journals/
├── plan.md              # This file
├── research.md          # Xero API research
├── data-model.md        # Entity definitions
├── quickstart.md        # Developer guide
├── contracts/           # OpenAPI specs
│   └── transactions-api.yaml
└── tasks.md             # Implementation tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   └── modules/
│       └── integrations/
│           └── xero/
│               ├── client.py           # + Credit Note, Payment, Journal methods
│               ├── models.py           # + XeroCreditNote, XeroPayment, XeroJournal, etc.
│               ├── repository.py       # + CreditNote, Payment, Journal repositories
│               ├── service.py          # + Sync methods for new entities
│               ├── schemas.py          # + Credit Note, Payment, Journal schemas
│               ├── router.py           # + Transaction endpoints
│               └── transformers.py     # + Transaction transformers
│       └── bas/
│           └── calculator.py           # Modified: Include credit notes in GST
│
└── tests/
    ├── unit/
    │   └── modules/
    │       └── integrations/
    │           └── xero/
    │               ├── test_credit_note_service.py
    │               ├── test_payment_service.py
    │               └── test_journal_service.py
    │       └── bas/
    │           └── test_gst_calculator.py  # Credit note adjustment tests
    ├── integration/
    │   └── api/
    │       ├── test_credit_notes.py
    │       ├── test_payments.py
    │       └── test_journals.py
    └── contract/
        └── adapters/
            └── test_xero_transactions_api.py

frontend/
└── src/
    ├── app/
    │   └── (protected)/
    │       └── clients/
    │           └── [id]/
    │               └── transactions/
    │                   ├── credit-notes/
    │                   │   └── page.tsx
    │                   ├── payments/
    │                   │   └── page.tsx
    │                   └── journals/
    │                       └── page.tsx
    ├── components/
    │   └── transactions/
    │       ├── CreditNotesList.tsx
    │       ├── CreditNoteDetail.tsx
    │       ├── PaymentsList.tsx
    │       ├── PaymentDetail.tsx
    │       ├── JournalsList.tsx
    │       └── JournalDetail.tsx
    └── lib/
        └── api/
            └── transactions.ts
```

**Structure Decision**: Extends existing `integrations/xero/` module and adds new transaction pages to frontend.

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           XERO DATA FLOW                                 │
│                                                                         │
│  Xero API                                                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│  │ CreditNotes │ │  Payments   │ │  Journals   │ │ManualJournals│       │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘       │
│         │               │               │               │               │
│         └───────────────┴───────────────┴───────────────┘               │
│                                   │                                     │
│                                   ▼                                     │
│                         ┌─────────────────┐                             │
│                         │   XeroClient    │                             │
│                         │ (API methods)   │                             │
│                         └────────┬────────┘                             │
│                                  │                                      │
│                                  ▼                                      │
│                         ┌─────────────────┐                             │
│                         │ XeroSyncService │                             │
│                         │ (orchestration) │                             │
│                         └────────┬────────┘                             │
│                                  │                                      │
│         ┌────────────────────────┼────────────────────────┐            │
│         ▼                        ▼                        ▼            │
│  ┌─────────────┐         ┌─────────────┐         ┌─────────────┐       │
│  │ CreditNote  │         │  Payment    │         │  Journal    │       │
│  │ Repository  │         │ Repository  │         │ Repository  │       │
│  └──────┬──────┘         └──────┬──────┘         └──────┬──────┘       │
│         │                       │                       │              │
│         └───────────────────────┴───────────────────────┘              │
│                                 │                                      │
│                                 ▼                                      │
│                         ┌─────────────────┐                            │
│                         │   PostgreSQL    │                            │
│                         └─────────────────┘                            │
└─────────────────────────────────────────────────────────────────────────┘
```

### GST Calculation Flow

```
GST CALCULATION WITH CREDIT NOTES
═══════════════════════════════════════════════════════════════════════════

CURRENT (Incomplete)
────────────────────
Sales Invoices GST:     $10,000
Bills GST:              -$3,000
                        ───────
Net GST Payable:        $7,000

AFTER (With Credit Notes)
─────────────────────────
Sales Invoices GST:     $10,000
Sales Credit Notes:     -$500      ← NEW: Reduces output GST
                        ───────
Net Output GST:         $9,500

Bills GST:              $3,000
Purchase Credit Notes:  -$200      ← NEW: Reduces input GST
                        ───────
Net Input GST:          $2,800

                        ───────
Net GST Payable:        $6,700     (vs incorrect $7,000)
```

### Entity Relationships

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       ENTITY RELATIONSHIPS                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  XeroConnection (existing)                                              │
│       │                                                                 │
│       ├──► XeroInvoice (existing)                                       │
│       │        │                                                        │
│       │        ├──► XeroCreditNote ───► XeroCreditNoteAllocation        │
│       │        │         │                                              │
│       │        └──► XeroPayment ───────► XeroPaymentAllocation          │
│       │                                                                 │
│       ├──► XeroOverpayment ───► XeroOverpaymentAllocation              │
│       │                                                                 │
│       ├──► XeroPrepayment ───► XeroPrepaymentAllocation                │
│       │                                                                 │
│       ├──► XeroJournal ───► XeroJournalLine                            │
│       │                                                                 │
│       └──► XeroManualJournal ───► XeroManualJournalLine                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Credit Note Sync Flow

```
1. XeroSyncService.sync_credit_notes(connection_id)
   │
   ▼
2. XeroClient.get_credit_notes(access_token, tenant_id, modified_since)
   │
   ▼
3. For each credit note:
   │
   ├──► Parse credit note data
   │
   ├──► Fetch allocations: XeroClient.get_credit_note_allocations(credit_note_id)
   │
   └──► Upsert to database via XeroCreditNoteRepository
   │
   ▼
4. Update sync job status
```

### Payment Sync Flow

```
1. XeroSyncService.sync_payments(connection_id)
   │
   ▼
2. XeroClient.get_payments(access_token, tenant_id, modified_since)
   │
   ▼
3. For each payment:
   │
   ├──► Parse payment data
   │
   ├──► Link to invoice/bill if present
   │
   └──► Upsert to database via XeroPaymentRepository
   │
   ▼
4. Also sync: Overpayments, Prepayments (separate endpoints)
```

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Credit Note GST timing | Apply to period of credit note issue | ATO rules require GST adjustment in period credit note issued |
| Payment allocations | Store full allocation details | Enables accurate cash flow per invoice |
| Journal storage | Store all journal lines | Provides complete audit trail |
| Overpayment handling | Separate model with allocations | Different behavior from regular payments |
| Sync order | After invoices, before reports | Credit notes reference invoices; reports need complete data |

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| GST calculation regression | Extensive unit tests for GST calc, integration tests with real data |
| Sync performance impact | Parallel sync of new entities, pagination for large datasets |
| Credit note allocation complexity | Store raw allocation data, compute on read |
| Multi-currency credit notes | Store both original and base currency amounts |
| Voided transaction handling | Soft delete with status tracking, recalculate GST |

---

## Dependencies

### Internal Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Spec 003: Xero OAuth | ✅ Complete | Connection management exists |
| Spec 004: Xero Data Sync | ✅ Complete | Sync patterns established |
| Spec 007: BAS Calculation | ✅ Complete | Will be modified |
| Spec 023: Xero Reports | ✅ Complete | Report context available |

### External Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| Xero Accounting API | v2 | Data source |
| PostgreSQL | 16+ | Storage |
| Celery | 5.x | Background sync |

---

## Phase References

- **Phase 0**: See [research.md](./research.md) for Xero API research
- **Phase 1**: See [data-model.md](./data-model.md) for entity definitions
- **Phase 1**: See [contracts/transactions-api.yaml](./contracts/transactions-api.yaml) for API specs
- **Phase 1**: See [quickstart.md](./quickstart.md) for developer guide
