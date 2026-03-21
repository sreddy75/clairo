# Implementation Tasks: Credit Notes, Payments & Journals

**Feature**: 024-credit-notes-payments-journals
**Branch**: `024-credit-notes-payments-journals`
**Date**: 2026-01-01

---

## Task Summary

| Phase | Description | Task Count |
|-------|-------------|------------|
| Phase 1 | Setup | 4 |
| Phase 2 | Foundational (Models & Repositories) | 12 |
| Phase 3 | User Story 1 - View Credit Notes | 8 |
| Phase 4 | User Story 2 - GST Calculation with Credit Notes | 6 |
| Phase 5 | User Story 3 - View Payment History | 8 |
| Phase 6 | User Story 4 - Cash Flow Analysis | 4 |
| Phase 7 | User Story 5 - View Journals | 8 |
| Phase 8 | User Story 6 - Manual Journals Sync | 6 |
| Phase 9 | User Story 7 - Audit Trail Insights | 4 |
| Phase 10 | Polish & Integration | 6 |
| **Total** | | **66** |

---

## Phase 1: Setup

- [X] T001 Create feature branch `024-credit-notes-payments-journals` from main
- [X] T002 [P] Create spec directory structure at `specs/024-credit-notes-payments-journals/`
- [X] T003 [P] Review existing Xero sync infrastructure in `backend/app/modules/integrations/xero/`
- [X] T004 Verify Xero OAuth scopes include credit notes, payments, journals access

---

## Phase 2: Foundational (Models & Repositories)

### Database Models

- [X] T005 [P] Create credit note enums (CreditNoteType, CreditNoteStatus) in `backend/app/modules/integrations/xero/models.py`
- [X] T006 [P] Create payment enums (PaymentType, PaymentStatus) in `backend/app/modules/integrations/xero/models.py`
- [X] T007 [P] Create journal enums (JournalSourceType, ManualJournalStatus) in `backend/app/modules/integrations/xero/models.py`
- [X] T008 Create XeroCreditNote model in `backend/app/modules/integrations/xero/models.py`
- [X] T009 Create XeroCreditNoteAllocation model in `backend/app/modules/integrations/xero/models.py`
- [X] T010 [P] Create XeroPayment model in `backend/app/modules/integrations/xero/models.py`
- [X] T011 [P] Create XeroOverpayment and XeroPrepayment models in `backend/app/modules/integrations/xero/models.py`
- [X] T012 [P] Create XeroJournal and XeroJournalLine models in `backend/app/modules/integrations/xero/models.py`
- [X] T013 [P] Create XeroManualJournal and XeroManualJournalLine models in `backend/app/modules/integrations/xero/models.py`
- [X] T014 Create Alembic migration for all new tables in `backend/alembic/versions/`
- [X] T015 Run and verify migration applies cleanly

### Repositories

- [X] T016 Create XeroCreditNoteRepository in `backend/app/modules/integrations/xero/repository.py`

---

## Phase 3: User Story 1 - View Credit Notes (P1)

**Goal**: Accountants can view all credit notes for a client with GST amounts.

**Independent Test**: Navigate to client → Transactions → Credit Notes tab → see all credit notes with date, contact, amount, GST, and status.

### Backend

- [X] T017 [US1] Add get_credit_notes method to XeroClient in `backend/app/modules/integrations/xero/client.py`
- [X] T018 [US1] Add get_credit_note_allocations method to XeroClient in `backend/app/modules/integrations/xero/client.py`
- [X] T019 [US1] Create CreditNoteSchema and CreditNoteDetailSchema in `backend/app/modules/integrations/xero/schemas.py`
- [X] T020 [US1] Add sync_credit_notes method to XeroSyncService in `backend/app/modules/integrations/xero/service.py`
- [X] T021 [US1] Create credit notes API endpoints (list, detail) in `backend/app/modules/integrations/xero/router.py`

### Frontend

- [X] T022 [P] [US1] Create CreditNotesList component (integrated into client page)
- [X] T023 [P] [US1] Create CreditNoteDetail component (integrated into client page)
- [X] T024 [US1] Create credit notes tab in `frontend/src/app/(protected)/clients/[id]/page.tsx`

---

## Phase 4: User Story 2 - GST Calculation with Credit Notes (P1)

**Goal**: Credit notes automatically reduce GST liability in BAS calculations.

**Independent Test**: Generate BAS worksheet → verify credit note GST reduces output GST total.

### Backend

- [X] T025 [US2] Add get_credit_notes_by_period method to XeroCreditNoteRepository in `backend/app/modules/integrations/xero/repository.py`
- [X] T026 [US2] Update GSTCalculator to include credit note adjustments in `backend/app/modules/bas/calculator.py`
- [X] T027 [US2] Add credit_note_gst fields to GSTCalculation schema in `backend/app/modules/bas/schemas.py`
- [X] T028 [US2] Add audit event for gst.calculated with credit note adjustment in `backend/app/modules/bas/service.py`

### Tests

- [X] T029 [P] [US2] Write unit tests for GST calculation with credit notes in `backend/tests/unit/modules/bas/test_gst_calculator.py`
- [X] T030 [US2] Write integration test for BAS worksheet generation in `backend/tests/integration/api/test_bas_worksheet.py`

---

## Phase 5: User Story 3 - View Payment History (P1)

**Goal**: Accountants can see all payments made and received with invoice linkage.

**Independent Test**: Navigate to client → Payments tab → see all payments with dates, amounts, and linked invoices.

### Backend

- [X] T031 [US3] Add get_payments method to XeroClient in `backend/app/modules/integrations/xero/client.py`
- [X] T032 [US3] Create XeroPaymentRepository in `backend/app/modules/integrations/xero/repository.py`
- [X] T033 [US3] Create PaymentSchema and PaymentDetailSchema in `backend/app/modules/integrations/xero/schemas.py`
- [X] T034 [US3] Add sync_payments method to XeroSyncService in `backend/app/modules/integrations/xero/service.py`
- [X] T035 [US3] Create payments API endpoints (list, detail) in `backend/app/modules/integrations/xero/router.py`

### Frontend

- [X] T036 [P] [US3] Create PaymentsList component (integrated into client page)
- [X] T037 [P] [US3] Create PaymentDetail component (integrated into client page)
- [X] T038 [US3] Create payments tab in `frontend/src/app/(protected)/clients/[id]/page.tsx`

---

## Phase 6: User Story 4 - Cash Flow Analysis (P2)

**Goal**: AI insights use actual payment dates for cash flow analysis.

**Independent Test**: AI chat about cash flow uses payment dates rather than invoice dates for analysis.

### Backend

- [X] T039 [US4] Add get_payments_by_contact method to XeroPaymentRepository in `backend/app/modules/integrations/xero/repository.py`
- [X] T040 [US4] Add calculate_average_days_to_pay method to PaymentAnalysisService in `backend/app/modules/integrations/xero/service.py`
- [X] T041 [US4] Create cash flow context builder for AI agents in `backend/app/modules/agents/context/cash_flow.py`
- [X] T042 [US4] Add payment-based tools to AI agent toolkit in `backend/app/modules/agents/tools/`

---

## Phase 7: User Story 5 - View Journals (P2)

**Goal**: Accountants can see journal entries with debits and credits for audit trail.

**Independent Test**: Navigate to client → Journals tab → see journal entries with debits and credits.

### Backend

- [X] T043 [US5] Add get_journals method to XeroClient in `backend/app/modules/integrations/xero/client.py`
- [X] T044 [US5] Create XeroJournalRepository in `backend/app/modules/integrations/xero/repository.py`
- [X] T045 [US5] Create JournalSchema and JournalDetailSchema in `backend/app/modules/integrations/xero/schemas.py`
- [X] T046 [US5] Add sync_journals method to XeroSyncService in `backend/app/modules/integrations/xero/service.py`
- [X] T047 [US5] Create journals API endpoints (list, detail) in `backend/app/modules/integrations/xero/router.py`

### Frontend

- [X] T048 [P] [US5] Create JournalsList component (integrated into client page)
- [X] T049 [P] [US5] Create JournalDetail component (integrated into client page)
- [X] T050 [US5] Create journals tab in `frontend/src/app/(protected)/clients/[id]/page.tsx`

---

## Phase 8: User Story 6 - Manual Journals Sync (P2)

**Goal**: Manual journal entries are synced for complete financial picture.

**Independent Test**: Manual journals created in Xero appear in Clairo within sync interval.

### Backend

- [X] T051 [US6] Add get_manual_journals method to XeroClient in `backend/app/modules/integrations/xero/client.py`
- [X] T052 [US6] Create XeroManualJournalRepository in `backend/app/modules/integrations/xero/repository.py`
- [X] T053 [US6] Create ManualJournalSchema and ManualJournalDetailSchema in `backend/app/modules/integrations/xero/schemas.py`
- [X] T054 [US6] Add sync_manual_journals method to XeroSyncService in `backend/app/modules/integrations/xero/service.py`
- [X] T055 [US6] Create manual journals API endpoints in `backend/app/modules/integrations/xero/router.py`
- [X] T056 [US6] Add manual journals to journals list view with type indicator

---

## Phase 9: User Story 7 - Audit Trail Insights (P3)

**Goal**: AI detects unusual journal patterns for potential errors or fraud.

**Independent Test**: AI identifies and alerts on unusual journal patterns.

### Backend

- [X] T057 [US7] Create JournalAnomalyDetector service in `backend/app/modules/agents/analysis/journal_anomaly.py`
- [X] T058 [US7] Add unusual journal detection rules (large amounts, unusual accounts, weekend entries)
- [X] T059 [US7] Create journal analysis tool for AI agents in `backend/app/modules/agents/tools/journal_analysis.py`
- [X] T060 [US7] Add anomaly alerts to insights system in `backend/app/modules/insights/`

---

## Phase 10: Polish & Integration

### Sync Integration

- [X] T061 Add transactions sync to full sync orchestration in `backend/app/tasks/xero.py`
- [X] T062 Create transactions sync status endpoint in `backend/app/modules/integrations/xero/router.py`

### Frontend Integration

- [X] T063 [P] Add transactions API client methods in `frontend/src/lib/api/transactions.ts`
- [X] T064 Add transactions tabs to client detail page in `frontend/src/app/(protected)/clients/[id]/page.tsx`

### Documentation & PR

- [X] T065 Update API documentation with new endpoints
- [X] T066 Create pull request with comprehensive description

---

## Dependencies

```
T001 ──► T002, T003, T004
         │
         ▼
T005-T016 (Phase 2: Foundational)
         │
         ├──► T017-T024 (US1: Credit Notes)
         │         │
         │         ▼
         ├──► T025-T030 (US2: GST Calculation) ◄── depends on US1
         │
         ├──► T031-T038 (US3: Payments) ◄── independent of US1/US2
         │         │
         │         ▼
         ├──► T039-T042 (US4: Cash Flow) ◄── depends on US3
         │
         ├──► T043-T050 (US5: Journals) ◄── independent
         │         │
         │         ▼
         ├──► T051-T056 (US6: Manual Journals) ◄── depends on US5
         │         │
         │         ▼
         └──► T057-T060 (US7: Audit Insights) ◄── depends on US5/US6
                   │
                   ▼
         T061-T066 (Phase 10: Polish)
```

---

## Parallel Execution Opportunities

### Phase 2 Parallelization

```
Group A (Enums):      T005, T006, T007 [parallel]
Group B (Models):     T008, T009, T010, T011, T012, T013 [parallel after Group A]
Group C (Migration):  T014, T015 [sequential after Group B]
Group D (Repo):       T016 [after migration]
```

### User Story Parallelization

After Phase 2 completes:
- **US1** (Credit Notes) and **US3** (Payments) and **US5** (Journals) can run in parallel
- **US2** (GST Calc) depends on US1 completion
- **US4** (Cash Flow) depends on US3 completion
- **US6** (Manual Journals) depends on US5 completion
- **US7** (Audit Insights) depends on US5 and US6 completion

### Frontend Parallelization

Within each user story:
- List component and Detail component can be developed in parallel
- Page component depends on both list and detail components

---

## Implementation Strategy

### MVP Scope (Recommended First Delivery)

1. **Phase 1**: Setup
2. **Phase 2**: Foundational models only (T005-T016)
3. **Phase 3**: US1 - Credit Notes view (T017-T024)
4. **Phase 4**: US2 - GST calculation with credit notes (T025-T030)

**MVP Deliverable**: Accountants can view credit notes and see accurate GST calculations that include credit note adjustments.

### Incremental Delivery

1. **Increment 1** (MVP): Credit Notes + GST Calculation
2. **Increment 2**: Payments + Cash Flow Analysis
3. **Increment 3**: Journals + Manual Journals
4. **Increment 4**: Audit Trail Insights + Polish

---

## Acceptance Criteria Checklist

### User Story 1 - View Credit Notes
- [X] Credit notes list shows date, contact, amount, GST, status
- [X] Credit note detail shows allocations and remaining credit
- [X] Filtering by type, status, date range works

### User Story 2 - GST Calculation
- [X] Output GST is reduced by sales credit note GST
- [X] Input GST is reduced by purchase credit note GST
- [X] Credit note applies to period when issued (not original invoice period)

### User Story 3 - Payment History
- [X] Payments list shows date, contact, amount, payment method
- [X] Payment detail shows allocation across invoices
- [X] Overpayments are clearly indicated

### User Story 4 - Cash Flow Analysis
- [X] AI uses payment dates for cash flow analysis
- [X] Average days-to-pay calculated per contact
- [X] Recurring payment patterns identified

### User Story 5 - Journals
- [X] Journals list shows date, narration, total debits/credits
- [X] Journal detail shows all line items with accounts
- [X] Source transaction reference shown

### User Story 6 - Manual Journals
- [X] Manual journals sync from Xero
- [X] Manual journals marked as user-created
- [X] Show on cash basis reports flag respected

### User Story 7 - Audit Insights
- [X] Unusually large journals flagged
- [X] Multiple journals to same account detected
- [X] Weekend entries highlighted

---

*End of Tasks Document*
