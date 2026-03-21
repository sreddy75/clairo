# Quickstart: Fixed Assets & Enhanced Analysis

**Feature**: 025-fixed-assets-enhanced-analysis
**Date**: 2026-01-01

This guide helps developers implement the fixed assets and enhanced analysis feature.

---

## Prerequisites

1. **Xero OAuth Connection**: Client must have valid Xero connection with `assets` scope
2. **Existing Sync Infrastructure**: Invoice sync working (Spec 004)
3. **Database Migrations**: Run before starting implementation

---

## OAuth Scope Update

The Assets API requires a separate OAuth scope. Update the OAuth flow:

```python
# backend/app/modules/integrations/xero/oauth.py

XERO_SCOPES = [
    "openid",
    "profile",
    "email",
    "accounting.transactions",
    "accounting.contacts",
    "accounting.settings",
    "assets",  # NEW: Required for Assets API
    "offline_access",
]
```

---

## Quick Implementation Guide

### Step 1: Add Database Models

```python
# backend/app/modules/integrations/xero/models.py

from sqlalchemy import Column, String, Numeric, DateTime, Date, ForeignKey, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

class AssetStatus(str, enum.Enum):
    DRAFT = "Draft"
    REGISTERED = "Registered"
    DISPOSED = "Disposed"

class DepreciationMethod(str, enum.Enum):
    NO_DEPRECIATION = "NoDepreciation"
    STRAIGHT_LINE = "StraightLine"
    DIMINISHING_VALUE_100 = "DiminishingValue100"
    DIMINISHING_VALUE_150 = "DiminishingValue150"
    DIMINISHING_VALUE_200 = "DiminishingValue200"
    FULL_DEPRECIATION = "FullDepreciation"

class XeroAsset(TenantBase):
    __tablename__ = "xero_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("xero_connections.id"))
    xero_asset_id = Column(UUID(as_uuid=True), unique=True)
    asset_type_id = Column(UUID(as_uuid=True), ForeignKey("xero_asset_types.id"))

    asset_name = Column(String(255), nullable=False)
    asset_number = Column(String(50))
    purchase_date = Column(Date, nullable=False)
    purchase_price = Column(Numeric(15, 2), nullable=False)
    status = Column(String(20), nullable=False)

    # Depreciation
    depreciation_method = Column(String(50))
    depreciation_rate = Column(Numeric(10, 4))
    book_value = Column(Numeric(15, 2), nullable=False)
    current_accum_depreciation = Column(Numeric(15, 2), default=0)

    # Disposal
    disposal_date = Column(Date)
    disposal_price = Column(Numeric(15, 2))

    # Relationships
    connection = relationship("XeroConnection", back_populates="assets")
    asset_type = relationship("XeroAssetType", back_populates="assets")
```

### Step 2: Extend XeroClient for Assets API

```python
# backend/app/modules/integrations/xero/client.py

class XeroClient:
    ASSETS_BASE_URL = "https://api.xero.com/assets.xro/1.0"

    async def get_assets(
        self,
        access_token: str,
        tenant_id: str,
        status: str | None = None,
        page: int = 1,
    ) -> dict:
        """Fetch fixed assets from Xero Assets API."""
        headers = self._auth_headers(access_token, tenant_id)

        params = {"page": page, "pageSize": 200}
        if status:
            params["status"] = status

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.ASSETS_BASE_URL}/Assets",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def get_asset_types(
        self,
        access_token: str,
        tenant_id: str,
    ) -> dict:
        """Fetch asset types from Xero Assets API."""
        headers = self._auth_headers(access_token, tenant_id)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.ASSETS_BASE_URL}/AssetTypes",
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    async def get_purchase_orders(
        self,
        access_token: str,
        tenant_id: str,
        modified_since: datetime | None = None,
        status: str | None = None,
        page: int = 1,
    ) -> dict:
        """Fetch purchase orders from Xero Accounting API."""
        headers = self._auth_headers(access_token, tenant_id)
        if modified_since:
            headers["If-Modified-Since"] = modified_since.strftime("%Y-%m-%dT%H:%M:%S")

        params = {"page": page}
        if status:
            params["Status"] = status

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/PurchaseOrders",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def get_repeating_invoices(
        self,
        access_token: str,
        tenant_id: str,
    ) -> dict:
        """Fetch repeating invoice templates."""
        headers = self._auth_headers(access_token, tenant_id)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/RepeatingInvoices",
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    async def get_tracking_categories(
        self,
        access_token: str,
        tenant_id: str,
    ) -> dict:
        """Fetch tracking categories with options."""
        headers = self._auth_headers(access_token, tenant_id)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/TrackingCategories",
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    async def get_quotes(
        self,
        access_token: str,
        tenant_id: str,
        modified_since: datetime | None = None,
        status: str | None = None,
        page: int = 1,
    ) -> dict:
        """Fetch quotes from Xero."""
        headers = self._auth_headers(access_token, tenant_id)
        if modified_since:
            headers["If-Modified-Since"] = modified_since.strftime("%Y-%m-%dT%H:%M:%S")

        params = {"page": page}
        if status:
            params["Status"] = status

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/Quotes",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()
```

### Step 3: Instant Write-Off Detection Service

```python
# backend/app/modules/integrations/xero/write_off.py

from decimal import Decimal
from datetime import date
from dataclasses import dataclass

@dataclass
class InstantWriteOffResult:
    eligible: bool
    reason: str | None
    financial_year: str
    threshold: Decimal
    qualifying_assets: list
    total_deduction: Decimal

# Configurable thresholds by financial year
WRITE_OFF_THRESHOLDS = {
    "2023-24": Decimal("20000"),
    "2024-25": Decimal("20000"),
    "2025-26": Decimal("20000"),
    "2026-27": Decimal("1000"),  # Returns to $1000 unless extended
}

TURNOVER_LIMIT = Decimal("10000000")  # $10M

class InstantWriteOffService:
    def __init__(self, asset_repo: XeroAssetRepository):
        self.asset_repo = asset_repo

    async def detect_eligible_assets(
        self,
        client_id: UUID,
        financial_year: str = "2025-26",
    ) -> InstantWriteOffResult:
        """Identify assets qualifying for instant asset write-off."""

        # Get client details
        client = await self.client_repo.get(client_id)

        # Check turnover eligibility
        if client.aggregated_turnover and client.aggregated_turnover >= TURNOVER_LIMIT:
            return InstantWriteOffResult(
                eligible=False,
                reason=f"Aggregated turnover (${client.aggregated_turnover:,.0f}) exceeds $10M threshold",
                financial_year=financial_year,
                threshold=WRITE_OFF_THRESHOLDS.get(financial_year, Decimal("1000")),
                qualifying_assets=[],
                total_deduction=Decimal("0"),
            )

        # Get threshold
        threshold = WRITE_OFF_THRESHOLDS.get(financial_year, Decimal("1000"))

        # Get FY date range
        fy_year = int(financial_year[:4])
        fy_start = date(fy_year, 7, 1)
        fy_end = date(fy_year + 1, 6, 30)

        # Get assets purchased in FY
        assets = await self.asset_repo.get_by_purchase_date_range(
            client_id, fy_start, fy_end
        )

        qualifying_assets = []
        total_deduction = Decimal("0")

        for asset in assets:
            # Skip disposed assets
            if asset.status == AssetStatus.DISPOSED:
                continue

            # Calculate GST-exclusive cost
            cost = asset.purchase_price
            if client.is_gst_registered:
                cost = cost / Decimal("1.10")

            # Check threshold
            if cost < threshold:
                qualifying_assets.append({
                    "asset_id": asset.id,
                    "asset_name": asset.asset_name,
                    "purchase_date": asset.purchase_date,
                    "cost": cost,
                })
                total_deduction += cost

        return InstantWriteOffResult(
            eligible=True,
            reason=None,
            financial_year=financial_year,
            threshold=threshold,
            qualifying_assets=qualifying_assets,
            total_deduction=total_deduction,
        )
```

### Step 4: Depreciation Summary Service

```python
# backend/app/modules/integrations/xero/depreciation.py

from decimal import Decimal
from dataclasses import dataclass

@dataclass
class DepreciationSummary:
    financial_year: str
    total_depreciation: Decimal
    by_asset_type: list[dict]
    by_method: list[dict]

class DepreciationService:
    def __init__(self, asset_repo: XeroAssetRepository):
        self.asset_repo = asset_repo

    async def get_depreciation_summary(
        self,
        client_id: UUID,
        financial_year: str = "2025-26",
    ) -> DepreciationSummary:
        """Calculate depreciation summary for the financial year."""

        # Get all registered assets
        assets = await self.asset_repo.get_by_status(
            client_id, AssetStatus.REGISTERED
        )

        total_depreciation = Decimal("0")
        by_asset_type: dict[str, Decimal] = {}
        by_method: dict[str, Decimal] = {}

        for asset in assets:
            depreciation = asset.current_accum_depreciation

            total_depreciation += depreciation

            # By asset type
            type_name = asset.asset_type.asset_type_name if asset.asset_type else "Uncategorized"
            by_asset_type[type_name] = by_asset_type.get(type_name, Decimal("0")) + depreciation

            # By method
            method = asset.depreciation_method or "Unknown"
            by_method[method] = by_method.get(method, Decimal("0")) + depreciation

        return DepreciationSummary(
            financial_year=financial_year,
            total_depreciation=total_depreciation,
            by_asset_type=[
                {"asset_type_name": name, "depreciation_amount": amount, "asset_count": 0}
                for name, amount in by_asset_type.items()
            ],
            by_method=[
                {"method": method, "depreciation_amount": amount}
                for method, amount in by_method.items()
            ],
        )
```

---

## Test Scenarios

### Instant Write-Off Detection

```python
# tests/unit/modules/integrations/xero/test_write_off_detection.py

async def test_eligible_small_business():
    """Small business with qualifying assets should get write-off recommendations."""
    service = InstantWriteOffService(...)

    result = await service.detect_eligible_assets(
        client_id=client_id,
        financial_year="2025-26",
    )

    assert result.eligible is True
    assert result.threshold == Decimal("20000")
    assert len(result.qualifying_assets) == 3
    assert result.total_deduction == Decimal("9500")


async def test_ineligible_large_business():
    """Business over $10M turnover should not be eligible."""
    # Setup client with $15M turnover
    service = InstantWriteOffService(...)

    result = await service.detect_eligible_assets(
        client_id=large_client_id,
        financial_year="2025-26",
    )

    assert result.eligible is False
    assert "exceeds $10M" in result.reason


async def test_asset_over_threshold():
    """Asset costing $25,000 should not qualify."""
    service = InstantWriteOffService(...)

    result = await service.detect_eligible_assets(
        client_id=client_id,
        financial_year="2025-26",
    )

    # Asset over $20k should not be in qualifying list
    asset_costs = [a["cost"] for a in result.qualifying_assets]
    assert all(cost < Decimal("20000") for cost in asset_costs)


async def test_gst_exclusive_calculation():
    """Cost should be calculated GST-exclusive for registered businesses."""
    # Asset costs $21,000 inc GST = $19,090.91 ex GST
    # Should qualify as under $20,000 threshold
    service = InstantWriteOffService(...)

    result = await service.detect_eligible_assets(
        client_id=gst_registered_client_id,
        financial_year="2025-26",
    )

    # The $21,000 inc GST asset should qualify
    assert len(result.qualifying_assets) == 1
    assert result.qualifying_assets[0]["cost"] < Decimal("20000")
```

### Depreciation Summary

```python
async def test_depreciation_summary():
    """Should calculate total depreciation correctly."""
    service = DepreciationService(...)

    result = await service.get_depreciation_summary(
        client_id=client_id,
        financial_year="2025-26",
    )

    assert result.total_depreciation == Decimal("8200")
    assert len(result.by_asset_type) > 0
    assert len(result.by_method) > 0
```

---

## API Usage Examples

### List Fixed Assets

```bash
# Get all assets
curl -X GET "http://localhost:8000/api/v1/clients/{client_id}/assets" \
  -H "Authorization: Bearer {token}"

# Filter by status
curl -X GET "http://localhost:8000/api/v1/clients/{client_id}/assets?status=Registered" \
  -H "Authorization: Bearer {token}"
```

### Get Instant Write-Off Analysis

```bash
curl -X GET "http://localhost:8000/api/v1/clients/{client_id}/assets/instant-write-off?financial_year=2025-26" \
  -H "Authorization: Bearer {token}"

# Response:
{
  "eligible": true,
  "financial_year": "2025-26",
  "threshold": 20000.00,
  "qualifying_assets": [
    {
      "asset_id": "...",
      "asset_name": "MacBook Pro",
      "purchase_date": "2025-10-15",
      "cost": 3181.82
    },
    {
      "asset_id": "...",
      "asset_name": "Office Furniture",
      "purchase_date": "2025-11-20",
      "cost": 3818.18
    }
  ],
  "total_deduction": 7000.00
}
```

### Get Depreciation Summary

```bash
curl -X GET "http://localhost:8000/api/v1/clients/{client_id}/assets/depreciation-summary?financial_year=2025-26" \
  -H "Authorization: Bearer {token}"

# Response:
{
  "financial_year": "2025-26",
  "total_depreciation": 8200.00,
  "by_asset_type": [
    {
      "asset_type_name": "Computer Equipment",
      "depreciation_amount": 5500.00,
      "asset_count": 8
    },
    {
      "asset_type_name": "Office Furniture",
      "depreciation_amount": 2700.00,
      "asset_count": 12
    }
  ],
  "by_method": [
    {
      "method": "DiminishingValue200",
      "depreciation_amount": 5500.00
    },
    {
      "method": "StraightLine",
      "depreciation_amount": 2700.00
    }
  ]
}
```

### List Purchase Orders

```bash
# Get outstanding POs
curl -X GET "http://localhost:8000/api/v1/clients/{client_id}/purchase-orders?status=AUTHORISED" \
  -H "Authorization: Bearer {token}"
```

### Get Recurring Summary

```bash
curl -X GET "http://localhost:8000/api/v1/clients/{client_id}/repeating-invoices/summary" \
  -H "Authorization: Bearer {token}"

# Response:
{
  "recurring_revenue": 60000.00,
  "recurring_expenses": 24000.00,
  "net_recurring": 36000.00,
  "by_schedule": [
    {
      "unit": "MONTHLY",
      "revenue_count": 5,
      "revenue_total": 5000.00,
      "expense_count": 2,
      "expense_total": 2000.00
    }
  ]
}
```

---

## Implementation Checklist

### Backend

- [ ] Update OAuth scopes to include `assets`
- [ ] Add asset models and enums
- [ ] Add purchase order, repeating invoice, quote models
- [ ] Add tracking category models
- [ ] Create Alembic migration
- [ ] Add XeroClient methods for Assets API
- [ ] Add XeroClient methods for PO, RI, Quotes
- [ ] Create repositories for each entity
- [ ] Add sync service methods
- [ ] Create instant write-off detection service
- [ ] Create depreciation summary service
- [ ] Add API endpoints
- [ ] Write unit tests
- [ ] Write integration tests

### Frontend

- [ ] Create AssetsList component
- [ ] Create AssetDetail component
- [ ] Create InstantWriteOffBanner component
- [ ] Create DepreciationSummary component
- [ ] Create PurchaseOrdersList component
- [ ] Create RepeatingInvoicesList component
- [ ] Add asset pages to client view
- [ ] Add AI agent tools for depreciation/capex

---

## Key Implementation Notes

1. **OAuth Scope**: The `assets` scope must be requested separately. Handle cases where scope is not authorized gracefully.

2. **API Rate Limits**: Assets API has its own rate limit (60/min) separate from Accounting API. Track separately.

3. **Depreciation Values**: Use Xero's calculated depreciation values. Do not recalculate locally.

4. **Write-Off Threshold**: Store threshold in config. Update when ATO changes rules (typically in federal budget).

5. **Turnover Data**: If client's aggregated turnover is not known, prompt user to enter it for write-off eligibility check.

6. **Financial Year**: Australia's FY runs July 1 - June 30. Format as "2025-26" for FY starting July 2025.

---

*End of Quickstart Guide*
