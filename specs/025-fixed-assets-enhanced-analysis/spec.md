# Feature Specification: Fixed Assets & Enhanced Analysis

**Feature Branch**: `025-fixed-assets-enhanced-analysis`
**Created**: 2026-01-01
**Status**: Draft
**Phase**: E (Data Intelligence)

## Overview

Integrate the Xero Assets API to sync fixed assets, depreciation schedules, and disposal data. Additionally, sync Purchase Orders, Quotes, Repeating Invoices, and Tracking Categories to complete the financial picture and enable enhanced AI analysis.

**Why This Matters**:
- Fixed assets represent significant capital investment requiring proper tracking
- Instant Asset Write-Off detection helps clients maximize tax deductions ($20,000 threshold until June 2026)
- Depreciation data affects tax planning and cash flow forecasting
- Purchase Orders show committed future cash outflows
- Repeating Invoices enable accurate recurring revenue/expense prediction
- Tracking Categories allow project/department-level profitability analysis

**Disruption Level**: Low (additive)

---

## User Scenarios & Testing

### User Story 1 - View Fixed Assets Register (Priority: P1)

As an accountant, I want to see all fixed assets for a client so that I can review their asset register and depreciation status.

**Why this priority**: Assets represent significant capital. Accountants need visibility into client asset registers.

**Independent Test**: Navigate to client → Assets tab → see all fixed assets with purchase date, cost, book value, and depreciation status.

**Acceptance Scenarios**:

1. **Given** a client with fixed assets in Xero, **When** I view the Assets tab, **Then** I see all assets with name, purchase date, cost, book value, and status.

2. **Given** a registered asset, **When** I view asset details, **Then** I see depreciation method, rate, accumulated depreciation, and current book value.

3. **Given** a disposed asset, **When** I view asset details, **Then** I see disposal date, disposal price, and capital gain/loss.

---

### User Story 2 - Instant Asset Write-Off Detection (Priority: P1)

As an accountant, I want AI to identify assets qualifying for instant asset write-off so that I can advise clients on tax optimization opportunities.

**Why this priority**: $20,000 instant write-off threshold (until June 2026) is a key tax planning opportunity. Missing qualifying assets means lost deductions.

**Independent Test**: AI identifies assets under $20,000 purchased in current FY as eligible for instant write-off.

**Acceptance Scenarios**:

1. **Given** assets purchased under $20,000 in current FY, **When** AI analyzes assets, **Then** it flags them as qualifying for instant write-off with total potential deduction.

2. **Given** a small business client (turnover <$10M), **When** viewing asset insights, **Then** I see "3 assets qualify for instant write-off ($12,400 total deduction)".

3. **Given** an asset just over the $20,000 threshold, **When** AI provides advice, **Then** it suggests considering if asset could be split or if a lower-cost alternative exists.

---

### User Story 3 - Depreciation Planning Insights (Priority: P1)

As an accountant, I want to see current year depreciation totals so that I can advise clients on their tax position.

**Why this priority**: Depreciation is a significant tax deduction. Accurate forecasting helps with tax planning.

**Independent Test**: View depreciation summary showing current year depreciation by asset type.

**Acceptance Scenarios**:

1. **Given** assets with scheduled depreciation, **When** I view depreciation summary, **Then** I see total current year depreciation as a tax deduction amount.

2. **Given** assets using different depreciation methods (straight-line, diminishing value), **When** I view summary, **Then** depreciation is correctly calculated per method.

3. **Given** AI advisory mode, **When** discussing tax planning, **Then** AI includes "Current year depreciation: $8,200 tax deduction" in context.

---

### User Story 4 - Capital Expenditure Analysis (Priority: P2)

As an accountant, I want AI to identify capital expenditure patterns so that I can advise on asset replacement and budget planning.

**Why this priority**: Understanding capex patterns helps with cash flow planning and replacement timing.

**Independent Test**: AI provides insights on asset purchase patterns and upcoming replacement needs.

**Acceptance Scenarios**:

1. **Given** historical asset purchase data, **When** AI analyzes patterns, **Then** it identifies typical capex timing (e.g., "Client typically purchases equipment in Q4").

2. **Given** fully depreciated assets, **When** AI generates insights, **Then** it suggests "Asset X fully depreciated - consider replacement planning".

3. **Given** warranty expiry data, **When** viewing asset details, **Then** upcoming warranty expirations are highlighted.

---

### User Story 5 - View Purchase Orders (Priority: P2)

As an accountant, I want to see outstanding purchase orders so that I can understand committed future cash outflows.

**Why this priority**: POs represent future cash obligations. Critical for cash flow forecasting.

**Independent Test**: View purchase orders tab showing outstanding orders with expected delivery dates.

**Acceptance Scenarios**:

1. **Given** a client with purchase orders in Xero, **When** I view Purchase Orders tab, **Then** I see all POs with status, vendor, amount, and expected delivery.

2. **Given** outstanding POs totaling $50,000, **When** AI forecasts cash flow, **Then** it includes these as committed outflows.

3. **Given** a PO with received status, **When** syncing data, **Then** the received quantity and date are tracked.

---

### User Story 6 - View Repeating Invoices (Priority: P2)

As an accountant, I want to see repeating invoice templates so that I can understand recurring revenue and expenses.

**Why this priority**: Repeating invoices represent predictable cash flows. Essential for revenue/expense forecasting.

**Independent Test**: View repeating invoices showing schedule, next date, and annualized amount.

**Acceptance Scenarios**:

1. **Given** repeating invoice templates in Xero, **When** I view Repeating Invoices tab, **Then** I see all templates with frequency, next date, and amount.

2. **Given** monthly recurring revenue of $5,000, **When** AI forecasts, **Then** it predicts "$60,000 annualized recurring revenue".

3. **Given** scheduled repeating expenses, **When** viewing cash flow, **Then** upcoming automated invoices are included in forecasts.

---

### User Story 7 - Tracking Category Analysis (Priority: P3)

As an accountant, I want to analyze profitability by tracking category (project/department) so that I can provide business insights.

**Why this priority**: Tracking categories enable segment-level analysis not possible from aggregate numbers.

**Independent Test**: View profitability breakdown by tracking category.

**Acceptance Scenarios**:

1. **Given** tracking categories configured in Xero, **When** I view category analysis, **Then** I see revenue, expenses, and profit per category.

2. **Given** project-level tracking, **When** AI analyzes, **Then** it identifies most and least profitable projects.

3. **Given** department-level tracking, **When** viewing insights, **Then** departmental cost trends are highlighted.

---

### User Story 8 - Quotes Pipeline (Priority: P3)

As an accountant, I want to see outstanding quotes so that I can understand potential revenue pipeline.

**Why this priority**: Quotes represent potential future revenue. Useful for forecasting and conversion analysis.

**Independent Test**: View quotes showing status, value, and conversion rates.

**Acceptance Scenarios**:

1. **Given** quotes in Xero, **When** I view Quotes tab, **Then** I see all quotes with status, client, amount, and expiry date.

2. **Given** historical quote data, **When** AI analyzes, **Then** it calculates quote-to-invoice conversion rate.

3. **Given** quotes expiring soon, **When** viewing quotes, **Then** expiring quotes are highlighted for follow-up.

---

### Edge Cases

- What happens when an asset is disposed mid-depreciation cycle?
  → Sync disposal data, calculate final depreciation and gain/loss

- How are pooled assets handled?
  → Assets in pools are synced with pool reference; depreciation is at pool level

- What if depreciation hasn't been run in Xero?
  → Display warning that depreciation may be stale; show last run date

- How are different depreciation methods compared?
  → Store both book and tax depreciation settings if different

- What about assets with no depreciation (land)?
  → Assets with "NoDepreciation" method display as "Not Depreciating"

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST sync Fixed Assets from Xero Assets API
- **FR-002**: System MUST sync Asset Types with depreciation settings
- **FR-003**: System MUST track book value and accumulated depreciation
- **FR-004**: System MUST identify instant asset write-off qualifying assets
- **FR-005**: System MUST calculate current year depreciation totals
- **FR-006**: System MUST sync Purchase Orders with line items
- **FR-007**: System MUST sync Repeating Invoice templates
- **FR-008**: System MUST sync Tracking Categories
- **FR-009**: System SHOULD sync Quotes for pipeline analysis
- **FR-010**: System MUST track disposed assets with gain/loss
- **FR-011**: System MUST support different depreciation methods
- **FR-012**: System SHOULD detect fully depreciated assets

### Key Entities

- **XeroAsset**: Fixed asset with depreciation settings
- **XeroAssetType**: Asset category with default depreciation
- **XeroPurchaseOrder**: Purchase order with line items
- **XeroRepeatingInvoice**: Repeating invoice template
- **XeroTrackingCategory**: Tracking category (project/department)
- **XeroTrackingOption**: Options within tracking categories
- **XeroQuote**: Quote with line items and status

### Non-Functional Requirements

- **NFR-001**: Asset sync MUST complete within existing sync window
- **NFR-002**: Instant write-off detection MUST run in <100ms
- **NFR-003**: All asset data MUST be retained for 7 years (ATO compliance)
- **NFR-004**: Depreciation calculations MUST match Xero's calculations

---

## Auditing & Compliance Checklist

### Audit Events Required

- [x] **Data Access Events**: Yes - viewing asset financial data is sensitive
- [x] **Data Modification Events**: Yes - syncing asset data
- [x] **Integration Events**: Yes - Xero Assets API calls
- [x] **Compliance Events**: Yes - instant write-off recommendations affect tax

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| `asset.synced` | Asset sync | client_id, asset_id, book_value | 7 years | None |
| `asset.viewed` | User views asset | user_id, client_id, asset_id | 5 years | None |
| `depreciation.calculated` | Depreciation summary | client_id, period, total | 7 years | None |
| `write_off.detected` | Instant write-off analysis | client_id, asset_ids, total | 7 years | None |
| `purchase_order.synced` | PO sync | client_id, po_id, amount | 7 years | None |

### Compliance Considerations

- **ATO Instant Write-Off**: $20,000 threshold for small businesses (<$10M turnover)
- **Depreciation Methods**: Must support ATO-approved methods
- **Record Keeping**: Asset records retained 7 years from disposal

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of fixed assets synced within 24 hours of creation/update
- **SC-002**: Instant write-off detection accuracy >99%
- **SC-003**: Depreciation totals match Xero calculations exactly
- **SC-004**: Purchase orders visible for cash flow forecasting
- **SC-005**: Repeating invoices used in revenue/expense predictions
- **SC-006**: Tracking category analysis available for segmented insights

---

## Technical Notes (for Plan phase)

### Xero API Endpoints

```
Assets API (requires assets scope):
GET /Assets
GET /Assets/{id}
POST /Assets
GET /AssetTypes
POST /AssetTypes
GET /Settings

Accounting API (existing scopes):
GET /PurchaseOrders
GET /PurchaseOrders/{id}
GET /Quotes
GET /Quotes/{id}
GET /RepeatingInvoices
GET /TrackingCategories
```

### Asset Status Values

```
DRAFT: Asset created but not registered
REGISTERED: Active asset being depreciated
DISPOSED: Asset sold or written off
```

### Depreciation Methods

```
NoDepreciation: Not depreciating (e.g., land)
StraightLine: Equal annual depreciation
DiminishingValue100: 100% diminishing value
DiminishingValue150: 150% diminishing value
DiminishingValue200: 200% diminishing value (prime cost)
FullDepreciation: Fully depreciated immediately
```

### Instant Write-Off Logic

```python
def is_eligible_for_instant_write_off(asset: XeroAsset, client: Client) -> bool:
    """Check if asset qualifies for instant write-off."""
    # Small business check
    if client.aggregated_turnover >= 10_000_000:
        return False

    # Threshold check (GST-exclusive for GST-registered)
    threshold = Decimal("20000.00")
    cost = asset.purchase_price
    if client.is_gst_registered:
        cost = cost / Decimal("1.10")  # Remove GST

    if cost >= threshold:
        return False

    # Date check (1 July 2025 - 30 June 2026)
    eligible_start = date(2025, 7, 1)
    eligible_end = date(2026, 6, 30)

    if not (eligible_start <= asset.purchase_date <= eligible_end):
        return False

    return True
```

---

## Dependencies

- **Spec 003 (Xero OAuth)**: Required - valid Xero connection with assets scope
- **Spec 004 (Xero Data Sync)**: Required - sync infrastructure
- **Spec 023 (Xero Reports)**: Optional - for enhanced financial context
- **Spec 024 (Credit Notes/Payments)**: Optional - for complete transaction picture
