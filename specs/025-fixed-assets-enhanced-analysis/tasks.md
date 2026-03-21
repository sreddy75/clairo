# Implementation Tasks: Fixed Assets & Enhanced Analysis

**Feature**: 025-fixed-assets-enhanced-analysis
**Branch**: `025-fixed-assets-enhanced-analysis`
**Date**: 2026-01-01

---

## Task Summary

| Phase | Description | Task Count |
|-------|-------------|------------|
| Phase 1 | Setup | 5 |
| Phase 2 | Foundational (Models & Repositories) | 14 |
| Phase 3 | User Story 1 - View Fixed Assets Register | 8 |
| Phase 4 | User Story 2 - Instant Asset Write-Off Detection | 6 |
| Phase 5 | User Story 3 - Depreciation Planning Insights | 5 |
| Phase 6 | User Story 4 - Capital Expenditure Analysis | 4 |
| Phase 7 | User Story 5 - View Purchase Orders | 7 |
| Phase 8 | User Story 6 - View Repeating Invoices | 6 |
| Phase 9 | User Story 7 - Tracking Category Analysis | 5 |
| Phase 10 | User Story 8 - Quotes Pipeline | 6 |
| Phase 11 | Polish & Integration | 6 |
| **Total** | | **72** |

---

## Phase 1: Setup

- [X] T001 Create feature branch `025-fixed-assets-enhanced-analysis` from main
- [X] T002 [P] Create spec directory structure at `specs/025-fixed-assets-enhanced-analysis/`
- [X] T003 [P] Update OAuth scopes to include `assets` in `backend/app/modules/integrations/xero/oauth.py`
- [X] T004 [P] Review existing Xero sync infrastructure in `backend/app/modules/integrations/xero/`
- [X] T005 Verify Xero OAuth can request assets scope in testing

---

## Phase 2: Foundational (Models & Repositories)

### Database Models

- [X] T006 [P] Create asset enums (AssetStatus, DepreciationMethod, AveragingMethod) in `backend/app/modules/integrations/xero/models.py`
- [X] T007 [P] Create purchase order enums (PurchaseOrderStatus) in `backend/app/modules/integrations/xero/models.py`
- [X] T008 [P] Create repeating invoice enums (RepeatingInvoiceStatus, ScheduleUnit) in `backend/app/modules/integrations/xero/models.py`
- [X] T009 [P] Create quote enums (QuoteStatus) in `backend/app/modules/integrations/xero/models.py`
- [X] T010 Create XeroAssetType model in `backend/app/modules/integrations/xero/models.py`
- [X] T011 Create XeroAsset model in `backend/app/modules/integrations/xero/models.py`
- [X] T012 [P] Create XeroPurchaseOrder model in `backend/app/modules/integrations/xero/models.py`
- [X] T013 [P] Create XeroRepeatingInvoice model in `backend/app/modules/integrations/xero/models.py`
- [X] T014 [P] Create XeroTrackingCategory and XeroTrackingOption models in `backend/app/modules/integrations/xero/models.py`
- [X] T015 [P] Create XeroQuote model in `backend/app/modules/integrations/xero/models.py`
- [X] T016 Create Alembic migration for all new tables in `backend/alembic/versions/`
- [X] T017 Run and verify migration applies cleanly

### Repositories

- [X] T018 Create XeroAssetRepository in `backend/app/modules/integrations/xero/repository.py`
- [X] T019 Create XeroAssetTypeRepository in `backend/app/modules/integrations/xero/repository.py`

---

## Phase 3: User Story 1 - View Fixed Assets Register (P1)

**Goal**: Accountants can view all fixed assets for a client with depreciation status.

**Independent Test**: Navigate to client → Assets tab → see all fixed assets with purchase date, cost, book value, and status.

### Backend

- [X] T020 [US1] Add get_assets method to XeroClient in `backend/app/modules/integrations/xero/client.py`
- [X] T021 [US1] Add get_asset_types method to XeroClient in `backend/app/modules/integrations/xero/client.py`
- [X] T022 [US1] Create AssetSchema and AssetDetailSchema in `backend/app/modules/integrations/xero/schemas.py`
- [X] T023 [US1] Add sync_asset_types method to XeroSyncService in `backend/app/modules/integrations/xero/service.py`
- [X] T024 [US1] Add sync_assets method to XeroSyncService in `backend/app/modules/integrations/xero/service.py`
- [X] T025 [US1] Create assets API endpoints (list, detail) in `backend/app/modules/integrations/xero/router.py`

### Frontend

- [X] T026 [P] [US1] Create AssetsList component in `frontend/src/components/assets/AssetsList.tsx`
- [X] T027 [US1] Create assets page in `frontend/src/app/(protected)/clients/[id]/assets/page.tsx`

---

## Phase 4: User Story 2 - Instant Asset Write-Off Detection (P1)

**Goal**: AI identifies assets qualifying for instant asset write-off.

**Independent Test**: AI identifies assets under $20,000 purchased in current FY as eligible for instant write-off.

### Backend

- [X] T028 [US2] Create InstantWriteOffService in `backend/app/modules/integrations/xero/write_off.py`
- [X] T029 [US2] Add write-off threshold configuration in `backend/app/config.py`
- [X] T030 [US2] Create instant write-off API endpoint in `backend/app/modules/integrations/xero/router.py`
- [X] T031 [US2] Add write-off detection to AI agent tools in `backend/app/modules/agents/tools/asset_tools.py`

### Frontend

- [X] T032 [P] [US2] Create InstantWriteOffBanner component in `frontend/src/components/assets/InstantWriteOffBanner.tsx`
- [X] T033 [US2] Integrate write-off banner into assets page

---

## Phase 5: User Story 3 - Depreciation Planning Insights (P1)

**Goal**: See current year depreciation totals for tax planning.

**Independent Test**: View depreciation summary showing current year depreciation by asset type.

### Backend

- [X] T034 [US3] Create DepreciationService in `backend/app/modules/integrations/xero/depreciation.py`
- [X] T035 [US3] Create depreciation summary API endpoint in `backend/app/modules/integrations/xero/router.py`
- [X] T036 [US3] Add depreciation tool for AI agents in `backend/app/modules/agents/tools/asset_tools.py`

### Frontend

- [X] T037 [P] [US3] Create DepreciationSummary component in `frontend/src/components/assets/DepreciationSummary.tsx`
- [X] T038 [US3] Add depreciation summary to assets page

---

## Phase 6: User Story 4 - Capital Expenditure Analysis (P2)

**Goal**: AI identifies capital expenditure patterns and replacement needs.

**Independent Test**: AI provides insights on asset purchase patterns and upcoming replacement needs.

### Backend

- [X] T039 [US4] Add get_assets_by_purchase_date_range method to XeroAssetRepository
- [X] T040 [US4] Create CapexAnalysisService in `backend/app/modules/integrations/xero/capex.py`
- [X] T041 [US4] Add capex analysis API endpoints in `backend/app/modules/integrations/xero/router.py`
- [X] T042 [US4] Add fully-depreciated asset detection to capex service

---

## Phase 7: User Story 5 - View Purchase Orders (P2)

**Goal**: See outstanding purchase orders for cash flow forecasting.

**Independent Test**: View purchase orders tab showing outstanding orders with expected delivery dates.

### Backend

- [X] T043 [US5] Add get_purchase_orders method to XeroClient in `backend/app/modules/integrations/xero/client.py`
- [X] T044 [US5] Create XeroPurchaseOrderRepository in `backend/app/modules/integrations/xero/repository.py`
- [X] T045 [US5] Create PurchaseOrderSchema in `backend/app/modules/integrations/xero/schemas.py`
- [X] T046 [US5] Add sync_purchase_orders method to XeroSyncService in `backend/app/modules/integrations/xero/service.py`
- [X] T047 [US5] Create purchase orders API endpoints in `backend/app/modules/integrations/xero/router.py`

### Frontend

- [X] T048 [P] [US5] Create PurchaseOrdersList component in `frontend/src/components/assets/PurchaseOrdersList.tsx`
- [X] T049 [US5] Create purchase orders page in `frontend/src/app/(protected)/clients/[id]/purchase-orders/page.tsx`

---

## Phase 8: User Story 6 - View Repeating Invoices (P2)

**Goal**: See repeating invoice templates for recurring revenue/expense forecasting.

**Independent Test**: View repeating invoices showing schedule, next date, and annualized amount.

### Backend

- [X] T050 [US6] Add get_repeating_invoices method to XeroClient in `backend/app/modules/integrations/xero/client.py`
- [X] T051 [US6] Create XeroRepeatingInvoiceRepository in `backend/app/modules/integrations/xero/repository.py`
- [X] T052 [US6] Create RepeatingInvoiceSchema in `backend/app/modules/integrations/xero/schemas.py`
- [X] T053 [US6] Add sync_repeating_invoices method to XeroSyncService in `backend/app/modules/integrations/xero/service.py`
- [X] T054 [US6] Create repeating invoices API endpoints with recurring summary in `backend/app/modules/integrations/xero/router.py`

### Frontend

- [X] T055 [US6] Create RepeatingInvoicesList component in `frontend/src/components/assets/RepeatingInvoicesList.tsx`

---

## Phase 9: User Story 7 - Tracking Category Analysis (P3)

**Goal**: Analyze profitability by tracking category (project/department).

**Independent Test**: View profitability breakdown by tracking category.

### Backend

- [X] T056 [US7] Add get_tracking_categories method to XeroClient in `backend/app/modules/integrations/xero/client.py`
- [X] T057 [US7] Create XeroTrackingCategoryRepository in `backend/app/modules/integrations/xero/repository.py`
- [X] T058 [US7] Add sync_tracking_categories method to XeroSyncService in `backend/app/modules/integrations/xero/service.py`
- [X] T059 [US7] Create tracking categories API endpoint in `backend/app/modules/integrations/xero/router.py`
- [X] T060 [US7] Add tracking-based analysis tool for AI agents in `backend/app/modules/agents/tools/asset_tools.py`

---

## Phase 10: User Story 8 - Quotes Pipeline (P3)

**Goal**: See outstanding quotes for revenue pipeline analysis.

**Independent Test**: View quotes showing status, value, and conversion rates.

### Backend

- [X] T061 [US8] Add get_quotes method to XeroClient in `backend/app/modules/integrations/xero/client.py`
- [X] T062 [US8] Create XeroQuoteRepository in `backend/app/modules/integrations/xero/repository.py`
- [X] T063 [US8] Create QuoteSchema in `backend/app/modules/integrations/xero/schemas.py`
- [X] T064 [US8] Add sync_quotes method to XeroSyncService in `backend/app/modules/integrations/xero/service.py`
- [X] T065 [US8] Create quotes API endpoints with pipeline summary in `backend/app/modules/integrations/xero/router.py`
- [X] T066 [US8] Add conversion rate calculation to quote pipeline summary

---

## Phase 11: Polish & Integration

### Sync Integration

- [X] T067 Add assets sync to full sync orchestration (if assets scope authorized)
- [X] T068 Create enhanced sync status endpoint including all new entities

### Frontend Integration

- [X] T069 [P] Add assets API client methods in `frontend/src/lib/api/assets.ts`
- [X] T070 Add assets navigation to client layout in `frontend/src/app/(protected)/clients/[id]/layout.tsx`

### Documentation & PR

- [X] T071 Update API documentation with new endpoints
- [X] T072 Create pull request with comprehensive description

---

## Dependencies

```
T001 ──► T002, T003, T004, T005
         │
         ▼
T006-T019 (Phase 2: Foundational)
         │
         ├──► T020-T027 (US1: Fixed Assets) ◄── Core feature
         │         │
         │         ├──► T028-T033 (US2: Write-Off) ◄── depends on US1
         │         │
         │         ├──► T034-T038 (US3: Depreciation) ◄── depends on US1
         │         │
         │         └──► T039-T042 (US4: CapEx) ◄── depends on US1
         │
         ├──► T043-T049 (US5: Purchase Orders) ◄── independent of US1
         │
         ├──► T050-T055 (US6: Repeating Invoices) ◄── independent
         │
         ├──► T056-T060 (US7: Tracking Categories) ◄── independent
         │
         └──► T061-T066 (US8: Quotes) ◄── independent
                   │
                   ▼
         T067-T072 (Phase 11: Polish)
```

---

## Parallel Execution Opportunities

### Phase 2 Parallelization

```
Group A (Enums):      T006, T007, T008, T009 [parallel]
Group B (Models):     T010, T011, T012, T013, T014, T015 [parallel after Group A]
Group C (Migration):  T016, T017 [sequential after Group B]
Group D (Repos):      T018, T019 [after migration]
```

### User Story Parallelization

After Phase 2 completes:
- **US1** (Assets) must complete first (core feature)
- **US2** (Write-Off), **US3** (Depreciation), **US4** (CapEx) depend on US1
- **US5** (Purchase Orders), **US6** (Repeating Invoices), **US7** (Tracking), **US8** (Quotes) can run in parallel with US2-4

### Frontend Parallelization

Within each user story:
- List components can be developed in parallel
- Page components depend on list components

---

## Implementation Strategy

### MVP Scope (Recommended First Delivery)

1. **Phase 1**: Setup (OAuth scope)
2. **Phase 2**: Foundational models (assets and asset types only)
3. **Phase 3**: US1 - Fixed Assets Register
4. **Phase 4**: US2 - Instant Write-Off Detection

**MVP Deliverable**: Accountants can view fixed assets and see instant write-off recommendations for tax planning.

### Incremental Delivery

1. **Increment 1** (MVP): Assets + Write-Off Detection
2. **Increment 2**: Depreciation + CapEx Analysis
3. **Increment 3**: Purchase Orders + Repeating Invoices
4. **Increment 4**: Tracking Categories + Quotes

---

## Acceptance Criteria Checklist

### User Story 1 - View Fixed Assets
- [ ] Assets list shows name, number, purchase date, cost, book value, status
- [ ] Asset detail shows depreciation method, rate, accumulated depreciation
- [ ] Disposed assets show disposal date, price, gain/loss
- [ ] Filtering by status and asset type works

### User Story 2 - Instant Write-Off
- [ ] Eligible small businesses see qualifying assets
- [ ] Large businesses (>$10M turnover) see ineligibility reason
- [ ] Threshold correctly applies GST-exclusive for registered businesses
- [ ] Total potential deduction calculated correctly

### User Story 3 - Depreciation Insights
- [ ] Total current year depreciation shown
- [ ] Breakdown by asset type available
- [ ] Breakdown by depreciation method available
- [ ] AI can reference depreciation in tax planning

### User Story 4 - CapEx Analysis
- [ ] Historical purchase patterns identified
- [ ] Fully depreciated assets flagged for replacement
- [ ] Warranty expiry dates highlighted

### User Story 5 - Purchase Orders
- [ ] PO list shows number, vendor, date, delivery date, status, total
- [ ] Outstanding POs shown for cash flow planning
- [ ] PO detail shows line items with tracking

### User Story 6 - Repeating Invoices
- [ ] Template list shows contact, schedule, next date, amount
- [ ] Annualized revenue/expense calculated
- [ ] Type filter (sales vs bills) works

### User Story 7 - Tracking Categories
- [ ] Categories list with all options shown
- [ ] Category-based analysis available

### User Story 8 - Quotes
- [ ] Quote list shows number, client, date, expiry, status, total
- [ ] Pipeline summary with totals by status
- [ ] Conversion rate calculated
- [ ] Expiring quotes highlighted

---

*End of Tasks Document*
