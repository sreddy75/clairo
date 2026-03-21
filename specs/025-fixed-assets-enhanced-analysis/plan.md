# Implementation Plan: Fixed Assets & Enhanced Analysis

**Branch**: `025-fixed-assets-enhanced-analysis` | **Date**: 2026-01-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/025-fixed-assets-enhanced-analysis/spec.md`

## Summary

Integrate Xero Assets API for fixed asset tracking, depreciation schedules, and disposal data. Additionally sync Purchase Orders, Quotes, Repeating Invoices, and Tracking Categories. Enable AI-powered instant asset write-off detection and depreciation planning insights.

**Technical Approach**:
- Add new OAuth scope: `assets` for Assets API access
- Add new models: `XeroAsset`, `XeroAssetType`, `XeroPurchaseOrder`, `XeroRepeatingInvoice`, `XeroTrackingCategory`, `XeroQuote`
- Extend `XeroClient` with methods for Assets API and additional Accounting API endpoints
- Create instant write-off detection service
- Add depreciation analysis for AI agents
- Create capital expenditure insights

---

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Pydantic v2, httpx, Celery
**Storage**: PostgreSQL 16 with proper foreign keys to existing Xero tables
**Testing**: pytest, pytest-asyncio, httpx for API testing
**Target Platform**: AWS ECS/Fargate (Sydney region)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Sync assets within existing sync window, write-off detection <100ms
**Constraints**: Xero rate limit 60 req/min, ATO 7-year data retention
**Scale/Scope**: Up to 1,000 assets, 5,000 purchase orders per client

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **Modular Monolith** | ✅ PASS | Extends existing `integrations/xero/` module |
| **Repository Pattern** | ✅ PASS | New repositories for each entity type |
| **Multi-tenancy (RLS)** | ✅ PASS | All new tables include `tenant_id` |
| **Audit-First** | ✅ PASS | Audit events for sync and tax recommendations |
| **Type Hints** | ✅ PASS | Pydantic schemas, typed functions |
| **Test-First** | ✅ PASS | Contract tests for Xero API, unit tests for write-off logic |
| **API Conventions** | ✅ PASS | RESTful endpoints under existing paths |
| **External Integration Pattern** | ✅ PASS | Rate limiting, error handling per constitution |

**No violations requiring justification.**

---

## Project Structure

### Documentation (this feature)

```text
specs/025-fixed-assets-enhanced-analysis/
├── plan.md              # This file
├── research.md          # Xero API research
├── data-model.md        # Entity definitions
├── quickstart.md        # Developer guide
├── contracts/           # OpenAPI specs
│   └── assets-api.yaml
└── tasks.md             # Implementation tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   └── modules/
│       └── integrations/
│           └── xero/
│               ├── client.py           # + Asset, PO, Quote, Repeating Invoice methods
│               ├── models.py           # + XeroAsset, XeroAssetType, XeroPurchaseOrder, etc.
│               ├── repository.py       # + Asset, PO, Quote repositories
│               ├── service.py          # + Sync methods for new entities
│               ├── schemas.py          # + Asset, PO, Quote schemas
│               ├── router.py           # + Asset, PO endpoints
│               └── write_off.py        # NEW: Instant write-off detection
│       └── agents/
│           └── tools/
│               ├── depreciation.py     # NEW: Depreciation analysis tool
│               └── capex.py            # NEW: Capital expenditure tool
│
└── tests/
    ├── unit/
    │   └── modules/
    │       └── integrations/
    │           └── xero/
    │               ├── test_asset_service.py
    │               ├── test_write_off_detection.py
    │               └── test_depreciation.py
    ├── integration/
    │   └── api/
    │       ├── test_assets.py
    │       ├── test_purchase_orders.py
    │       └── test_repeating_invoices.py
    └── contract/
        └── adapters/
            └── test_xero_assets_api.py

frontend/
└── src/
    ├── app/
    │   └── (protected)/
    │       └── clients/
    │           └── [id]/
    │               ├── assets/
    │               │   └── page.tsx
    │               ├── purchase-orders/
    │               │   └── page.tsx
    │               └── repeating-invoices/
    │                   └── page.tsx
    ├── components/
    │   └── assets/
    │       ├── AssetsList.tsx
    │       ├── AssetDetail.tsx
    │       ├── DepreciationSummary.tsx
    │       ├── InstantWriteOffBanner.tsx
    │       ├── PurchaseOrdersList.tsx
    │       └── RepeatingInvoicesList.tsx
    └── lib/
        └── api/
            └── assets.ts
```

**Structure Decision**: Extends existing `integrations/xero/` module and adds new asset-related pages to frontend.

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         XERO DATA FLOW                                   │
│                                                                         │
│  Xero Assets API              Xero Accounting API                       │
│  ┌─────────────┐             ┌─────────────────────────────────────┐   │
│  │   Assets    │             │ PurchaseOrders │ Quotes │ Repeating │   │
│  │ AssetTypes  │             │ TrackingCategories                   │   │
│  │  Settings   │             └─────────────────────────────────────┘   │
│  └──────┬──────┘                              │                        │
│         │                                     │                        │
│         └─────────────────┬───────────────────┘                        │
│                           ▼                                            │
│                   ┌─────────────────┐                                  │
│                   │   XeroClient    │                                  │
│                   │ (API methods)   │                                  │
│                   └────────┬────────┘                                  │
│                            │                                           │
│                            ▼                                           │
│                   ┌─────────────────┐                                  │
│                   │ XeroSyncService │                                  │
│                   │ (orchestration) │                                  │
│                   └────────┬────────┘                                  │
│                            │                                           │
│     ┌──────────────────────┼──────────────────────┐                   │
│     ▼                      ▼                      ▼                   │
│  ┌─────────┐         ┌─────────────┐        ┌─────────────┐          │
│  │ Asset   │         │ PurchaseOrder│        │ Repeating  │          │
│  │ Repo    │         │ Repository  │        │ Invoice Repo│          │
│  └────┬────┘         └──────┬──────┘        └──────┬──────┘          │
│       │                     │                      │                  │
│       └─────────────────────┴──────────────────────┘                  │
│                             │                                         │
│                             ▼                                         │
│                     ┌─────────────────┐                               │
│                     │   PostgreSQL    │                               │
│                     └─────────────────┘                               │
└─────────────────────────────────────────────────────────────────────────┘
```

### Instant Write-Off Detection Flow

```
INSTANT ASSET WRITE-OFF DETECTION
═══════════════════════════════════════════════════════════════════════════

Input: Client assets synced from Xero
       ↓
┌──────────────────────────────────────────────────────────────────────────┐
│                         ELIGIBILITY CHECKS                               │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. Small Business Check                                                 │
│     └── Aggregated turnover < $10,000,000                               │
│                                                                          │
│  2. Asset Cost Threshold                                                 │
│     └── Purchase price < $20,000 (GST-exclusive if registered)          │
│                                                                          │
│  3. Date Range Check                                                     │
│     └── First used/installed: 1 July 2025 - 30 June 2026               │
│                                                                          │
│  4. Asset Status Check                                                   │
│     └── Status = DRAFT or REGISTERED                                    │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
       ↓
Output: List of qualifying assets with total potential deduction

Example Result:
┌──────────────────────────────────────────────────────────────────────────┐
│  INSTANT WRITE-OFF OPPORTUNITIES                                         │
│                                                                          │
│  ✓ MacBook Pro (purchased 15 Oct 2025)      $3,500                      │
│  ✓ Office Furniture (purchased 20 Nov 2025) $4,200                      │
│  ✓ Printer/Scanner (purchased 5 Dec 2025)   $1,800                      │
│                                             ───────                      │
│  Total Potential Deduction:                 $9,500                      │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Entity Relationships

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       ENTITY RELATIONSHIPS                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  XeroConnection (existing)                                              │
│       │                                                                 │
│       ├──► XeroAssetType ◄───────────────────────────┐                 │
│       │        │                                      │                 │
│       │        └──► XeroAsset                         │ (type ref)     │
│       │                                               │                 │
│       ├──► XeroPurchaseOrder ───► XeroPurchaseOrderLine               │
│       │                                                                 │
│       ├──► XeroRepeatingInvoice ───► XeroRepeatingInvoiceLine         │
│       │                                                                 │
│       ├──► XeroTrackingCategory ───► XeroTrackingOption               │
│       │                                                                 │
│       └──► XeroQuote ───► XeroQuoteLine                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Asset Sync Flow

```
1. XeroSyncService.sync_assets(connection_id)
   │
   ▼
2. Check OAuth scopes include "assets"
   │
   ├──► If missing: Skip asset sync, log warning
   │
   ▼
3. XeroClient.get_asset_types(access_token, tenant_id)
   │
   ▼
4. Upsert asset types to database
   │
   ▼
5. XeroClient.get_assets(access_token, tenant_id, status_filter)
   │
   ├──► Page through results (Xero returns 200 per page)
   │
   ▼
6. For each asset:
   │
   ├──► Parse depreciation settings
   ├──► Calculate book value from depreciation details
   ├──► Link to asset type
   │
   └──► Upsert to database via XeroAssetRepository
   │
   ▼
7. Run instant write-off detection
   │
   ▼
8. Update sync job status
```

### Purchase Order Sync Flow

```
1. XeroSyncService.sync_purchase_orders(connection_id)
   │
   ▼
2. XeroClient.get_purchase_orders(access_token, tenant_id, modified_since)
   │
   ▼
3. For each purchase order:
   │
   ├──► Parse line items with tracking
   ├──► Link to contact (vendor)
   │
   └──► Upsert to database via XeroPurchaseOrderRepository
   │
   ▼
4. Update sync job status
```

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Assets API scope | Separate OAuth scope | Xero requires `assets` scope separately from accounting |
| Depreciation storage | Store book depreciation details | Tax depreciation may differ; store book values from Xero |
| Write-off threshold | Configurable by FY | ATO changes threshold yearly; must be updatable |
| Asset status filter | Sync all statuses | Need disposed assets for gain/loss analysis |
| Purchase order lines | Store as JSONB | Flexible structure, tracking categories vary |

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Assets scope not authorized | Graceful degradation; skip assets sync if scope missing |
| Depreciation calculation mismatch | Use Xero's calculated values, don't recalculate |
| Large asset registers | Pagination, batch processing |
| Write-off threshold changes | Store threshold in config, update annually |
| Missing aggregated turnover | Prompt user to enter turnover for write-off eligibility |

---

## Dependencies

### Internal Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Spec 003: Xero OAuth | ✅ Complete | Need to add assets scope request |
| Spec 004: Xero Data Sync | ✅ Complete | Sync patterns established |
| Spec 023: Xero Reports | ✅ Complete | P&L context for depreciation |
| Spec 024: Credit Notes/Payments | ✅ Complete | Complete transaction picture |

### External Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| Xero Assets API | v1 | Asset data source |
| Xero Accounting API | v2 | PO, Quote, Repeating Invoice source |
| PostgreSQL | 16+ | Storage |
| Celery | 5.x | Background sync |

---

## Phase References

- **Phase 0**: See [research.md](./research.md) for Xero API research
- **Phase 1**: See [data-model.md](./data-model.md) for entity definitions
- **Phase 1**: See [contracts/assets-api.yaml](./contracts/assets-api.yaml) for API specs
- **Phase 1**: See [quickstart.md](./quickstart.md) for developer guide
