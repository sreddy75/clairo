# Research: Fixed Assets & Enhanced Analysis

**Feature**: 025-fixed-assets-enhanced-analysis
**Date**: 2026-01-01
**Status**: Complete

---

## Research Tasks

### 1. Xero Assets API

**Decision**: Use Xero Assets API v1 for fixed asset data

**Base URL**: `https://api.xero.com/assets.xro/1.0`

**OAuth Scope Required**: `assets` (read-write) or `assets.read` (read-only)

**Endpoints**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/Assets` | GET | List all fixed assets (paginated, 200 per page) |
| `/Assets` | POST | Create a new draft asset |
| `/Assets/{id}` | GET | Get single asset with full details |
| `/AssetTypes` | GET | List asset types with depreciation settings |
| `/AssetTypes` | POST | Create new asset type |
| `/Settings` | GET | Get asset register settings |

**Asset Structure**:
```json
{
  "assetId": "uuid",
  "assetName": "MacBook Pro 16\"",
  "assetNumber": "FA-001",
  "assetTypeId": "uuid",
  "purchaseDate": "2025-10-15",
  "purchasePrice": 3500.00,
  "disposalDate": null,
  "disposalPrice": null,
  "assetStatus": "Registered",
  "warrantyExpiryDate": "2028-10-15",
  "serialNumber": "C02XY1234567",
  "bookDepreciationSetting": {
    "depreciationMethod": "StraightLine",
    "averagingMethod": "FullMonth",
    "depreciationRate": 20.0,
    "effectiveLifeYears": 5,
    "depreciationCalculationMethod": "Rate",
    "depreciableObjectId": "uuid",
    "depreciableObjectType": "Asset"
  },
  "bookDepreciationDetail": {
    "currentCapitalGain": 0,
    "currentGainLoss": 0,
    "depreciationStartDate": "2025-10-01",
    "costLimit": 0,
    "residualValue": 0,
    "priorAccumDepreciationAmount": 0,
    "currentAccumDepreciationAmount": 233.33
  },
  "canRollback": true,
  "accountingBookValue": 3266.67,
  "isDeleteEnabledForDate": false
}
```

**Asset Status Values**:
- `Draft`: Asset created but not registered for depreciation
- `Registered`: Active asset being depreciated
- `Disposed`: Asset sold or written off

**Depreciation Methods**:
| Method | Description |
|--------|-------------|
| `NoDepreciation` | Not depreciating (e.g., land) |
| `StraightLine` | Equal annual depreciation |
| `DiminishingValue100` | 100% diminishing value |
| `DiminishingValue150` | 150% diminishing value |
| `DiminishingValue200` | 200% diminishing value (prime cost) |
| `FullDepreciation` | Fully depreciated immediately |

**Averaging Methods**:
- `FullMonth`: Depreciation starts from first of month
- `ActualDays`: Depreciation calculated on actual days

**Calculation Methods**:
- `Rate`: Depreciation calculated using rate percentage
- `Life`: Depreciation calculated using effective life in years
- `None`: No calculation (for NoDepreciation method)

**Rationale**: Assets API provides comprehensive fixed asset data including depreciation settings and book values. Required for accurate asset tracking and write-off detection.

---

### 2. Asset Type Structure

**Decision**: Sync asset types to provide default depreciation settings

**AssetType Structure**:
```json
{
  "assetTypeId": "uuid",
  "assetTypeName": "Computer Equipment",
  "fixedAssetAccountId": "uuid",
  "depreciationExpenseAccountId": "uuid",
  "accumulatedDepreciationAccountId": "uuid",
  "bookDepreciationSetting": {
    "depreciationMethod": "DiminishingValue200",
    "averagingMethod": "FullMonth",
    "depreciationRate": 40.0,
    "effectiveLifeYears": 4,
    "depreciationCalculationMethod": "Rate"
  },
  "locks": 0
}
```

**Account Linkages**:
- `fixedAssetAccountId`: Balance sheet account for asset cost
- `depreciationExpenseAccountId`: P&L account for depreciation expense
- `accumulatedDepreciationAccountId`: Balance sheet contra account

**Rationale**: Asset types define default depreciation behavior. Syncing types enables validation and type-based analysis.

---

### 3. Purchase Orders API

**Decision**: Use Xero Accounting API for purchase orders

**Endpoints**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/PurchaseOrders` | GET | List purchase orders (paginated) |
| `/PurchaseOrders/{id}` | GET | Get single purchase order |
| `/PurchaseOrders/{id}/History` | GET | Get PO history |

**Purchase Order Structure**:
```json
{
  "PurchaseOrderID": "uuid",
  "PurchaseOrderNumber": "PO-001",
  "Date": "2025-12-01",
  "DeliveryDate": "2025-12-15",
  "Reference": "Office supplies order",
  "Status": "AUTHORISED",
  "Contact": {
    "ContactID": "uuid",
    "Name": "Office Supplies Co"
  },
  "LineItems": [
    {
      "Description": "Printer paper",
      "Quantity": 10,
      "UnitAmount": 25.00,
      "LineAmount": 250.00,
      "AccountCode": "400",
      "TaxType": "INPUT2",
      "Tracking": [
        {
          "Name": "Department",
          "Option": "Marketing"
        }
      ]
    }
  ],
  "SubTotal": 250.00,
  "TotalTax": 25.00,
  "Total": 275.00,
  "CurrencyCode": "AUD",
  "SentToContact": true,
  "UpdatedDateUTC": "/Date(1234567890000)/"
}
```

**PO Status Values**:
- `DRAFT`: Not yet sent
- `SUBMITTED`: Sent to supplier
- `AUTHORISED`: Approved
- `BILLED`: Converted to bill
- `DELETED`: Cancelled

**Rationale**: Purchase orders represent committed future cash outflows. Essential for cash flow forecasting.

---

### 4. Repeating Invoices API

**Decision**: Sync repeating invoice templates for recurring revenue/expense prediction

**Endpoints**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/RepeatingInvoices` | GET | List repeating invoice templates |
| `/RepeatingInvoices/{id}` | GET | Get single template |

**Repeating Invoice Structure**:
```json
{
  "RepeatingInvoiceID": "uuid",
  "Type": "ACCREC",
  "Contact": {
    "ContactID": "uuid",
    "Name": "Monthly Client"
  },
  "Schedule": {
    "Period": 1,
    "Unit": "MONTHLY",
    "DueDate": 20,
    "DueDateType": "DAYSAFTERBILLDATE",
    "StartDate": "2025-01-01",
    "NextScheduledDate": "2026-02-01",
    "EndDate": null
  },
  "LineItems": [...],
  "SubTotal": 5000.00,
  "TotalTax": 500.00,
  "Total": 5500.00,
  "Status": "AUTHORISED",
  "CurrencyCode": "AUD"
}
```

**Schedule Units**:
- `WEEKLY`
- `MONTHLY`
- `YEARLY`

**Status Values**:
- `DRAFT`: Not active
- `AUTHORISED`: Active, will generate invoices

**Rationale**: Repeating invoices represent predictable recurring revenue and expenses. Critical for financial forecasting.

---

### 5. Tracking Categories API

**Decision**: Sync tracking categories for segment-level analysis

**Endpoints**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/TrackingCategories` | GET | List tracking categories with options |
| `/TrackingCategories/{id}` | GET | Get single category |

**Tracking Category Structure**:
```json
{
  "TrackingCategoryID": "uuid",
  "Name": "Department",
  "Status": "ACTIVE",
  "Options": [
    {
      "TrackingOptionID": "uuid",
      "Name": "Marketing",
      "Status": "ACTIVE"
    },
    {
      "TrackingOptionID": "uuid",
      "Name": "Sales",
      "Status": "ACTIVE"
    }
  ]
}
```

**Common Uses**:
- Department tracking (cost centers)
- Project tracking (job costing)
- Location tracking (multi-site)

**Rationale**: Tracking categories enable segment-level profitability analysis beyond aggregate numbers.

---

### 6. Quotes API

**Decision**: Sync quotes for revenue pipeline analysis

**Endpoints**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/Quotes` | GET | List quotes (paginated) |
| `/Quotes/{id}` | GET | Get single quote |

**Quote Structure**:
```json
{
  "QuoteID": "uuid",
  "QuoteNumber": "QU-001",
  "Reference": "Website redesign proposal",
  "Contact": {
    "ContactID": "uuid",
    "Name": "Potential Client"
  },
  "Date": "2025-12-01",
  "ExpiryDate": "2025-12-31",
  "Status": "SENT",
  "LineItems": [...],
  "SubTotal": 15000.00,
  "TotalTax": 1500.00,
  "Total": 16500.00,
  "CurrencyCode": "AUD"
}
```

**Quote Status Values**:
- `DRAFT`: Not yet sent
- `SENT`: Sent to customer
- `ACCEPTED`: Customer accepted
- `DECLINED`: Customer declined
- `INVOICED`: Converted to invoice

**Rationale**: Quotes represent potential future revenue. Useful for pipeline analysis and conversion tracking.

---

### 7. Instant Asset Write-Off Rules (Australia)

**Decision**: Implement ATO instant asset write-off detection

**Current Rules (2025-2026)**:

| Parameter | Value |
|-----------|-------|
| Threshold | $20,000 (GST-exclusive if registered) |
| Eligibility Period | 1 July 2025 - 30 June 2026 |
| Turnover Limit | < $10,000,000 aggregated turnover |
| Asset Types | New and second-hand depreciating assets |

**Calculation Logic**:
```python
def calculate_instant_write_off_eligibility(
    assets: list[XeroAsset],
    client: Client,
    financial_year: str = "2025-26"
) -> InstantWriteOffResult:
    """
    Identify assets qualifying for instant asset write-off.
    """
    # Check eligibility
    if client.aggregated_turnover >= Decimal("10000000"):
        return InstantWriteOffResult(
            eligible=False,
            reason="Turnover exceeds $10M threshold"
        )

    # Get threshold for financial year
    thresholds = {
        "2023-24": Decimal("20000"),
        "2024-25": Decimal("20000"),
        "2025-26": Decimal("20000"),
    }
    threshold = thresholds.get(financial_year, Decimal("1000"))

    # Date range for FY
    fy_start = date(int(financial_year[:4]), 7, 1)
    fy_end = date(int(financial_year[:4]) + 1, 6, 30)

    qualifying_assets = []
    total_deduction = Decimal("0")

    for asset in assets:
        # Check purchase date in eligible period
        if not (fy_start <= asset.purchase_date <= fy_end):
            continue

        # Check asset status
        if asset.status == "Disposed":
            continue

        # Calculate GST-exclusive cost
        cost = asset.purchase_price
        if client.is_gst_registered:
            cost = cost / Decimal("1.10")

        # Check threshold
        if cost < threshold:
            qualifying_assets.append(asset)
            total_deduction += cost

    return InstantWriteOffResult(
        eligible=True,
        qualifying_assets=qualifying_assets,
        total_deduction=total_deduction,
        threshold=threshold,
        financial_year=financial_year
    )
```

**Important Notes**:
- Threshold returns to $1,000 on 1 July 2026 unless extended
- "First used or installed ready for use" is the key date
- Per-asset basis (can write off multiple assets under threshold)

**Rationale**: Instant write-off is a significant tax planning opportunity. Detection helps accountants advise clients on deductions.

---

### 8. Sync Strategy

**Decision**: Sequential sync with dependencies

**Sync Order**:
1. Asset Types (required for asset type reference)
2. Assets (references asset types)
3. Tracking Categories (standalone)
4. Purchase Orders (can reference tracking)
5. Repeating Invoices (can reference tracking)
6. Quotes (standalone)

**Rate Limiting**:
- Assets API: 60 requests/minute (separate from Accounting API)
- Accounting API: 60 requests/minute (shared across endpoints)
- Use 1-second delay between paginated calls

**Incremental Sync**:
- Assets API supports `modifiedAfter` parameter
- PurchaseOrders support `If-Modified-Since` header
- Quotes support `If-Modified-Since` header

**Rationale**: Sequential sync ensures dependencies are available. Rate limiting prevents API throttling.

---

## Summary of Decisions

| Area | Decision |
|------|----------|
| Assets API | Use Xero Assets API v1 with assets scope |
| Depreciation | Store Xero-calculated values, don't recalculate |
| Write-Off Detection | Check turnover, threshold, date range, status |
| Purchase Orders | Sync for cash flow forecasting |
| Repeating Invoices | Sync for recurring revenue/expense prediction |
| Tracking Categories | Sync for segment analysis |
| Quotes | Sync for pipeline analysis |
| Sync Strategy | Sequential with dependencies, incremental |

---

## Sources

- [Xero Assets API Overview](https://developer.xero.com/documentation/api/assets/overview)
- [Xero Assets API Assets](https://developer.xero.com/documentation/api/assets/assets)
- [Xero Assets API Types](https://developer.xero.com/documentation/api/assets/types)
- [Xero OpenAPI Specification](https://github.com/XeroAPI/Xero-OpenAPI/blob/master/xero_assets.yaml)
- [Xero Purchase Orders API](https://developer.xero.com/documentation/api/accounting/purchaseorders)
- [Xero Repeating Invoices API](https://developer.xero.com/documentation/api/accounting/repeatinginvoices)
- [ATO Instant Asset Write-Off](https://www.ato.gov.au/about-ato/new-legislation/in-detail/businesses/small-business-support-20000-dollar-instant-asset-write-off)
- [ATO Simpler Depreciation Rules](https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/depreciation-and-capital-expenses-and-allowances/simpler-depreciation-for-small-business)
