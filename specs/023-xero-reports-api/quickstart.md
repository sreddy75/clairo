# Quickstart: Xero Reports API Integration

**Feature**: 023-xero-reports-api
**Date**: 2026-01-01

---

## Overview

This guide helps developers get started with implementing Xero Reports API integration. The feature adds support for fetching and caching Xero financial reports (P&L, Balance Sheet, Aged reports, etc.) to enhance AI agent capabilities and provide accountants with pre-calculated financial data.

---

## Prerequisites

Before starting:

1. **Existing Xero Integration** - Specs 003 and 004 must be complete
2. **PostgreSQL 16+** - JSONB support required
3. **Celery** - For background sync jobs
4. **Dev Environment** - Backend running with valid Xero test connection

```bash
# Verify prerequisites
cd /Users/suren/KR8IT/projects/Personal/BAS/backend

# Check existing Xero module
ls -la app/modules/integrations/xero/

# Verify database connection
uv run alembic current
```

---

## Step 1: Database Migration

Create and run the migration for new tables:

```bash
# Generate migration (after adding models)
uv run alembic revision --autogenerate -m "Add Xero Reports tables"

# Apply migration
uv run alembic upgrade head

# Verify tables created
uv run python -c "
from app.database import engine
from sqlalchemy import inspect
inspector = inspect(engine)
print('Tables:', inspector.get_table_names())
"
```

**Expected Tables**:
- `xero_reports`
- `xero_report_sync_jobs`

---

## Step 2: Add XeroClient Report Methods

Extend `backend/app/modules/integrations/xero/client.py`:

```python
# Add to XeroClient class

async def get_profit_and_loss(
    self,
    access_token: str,
    tenant_id: str,
    from_date: date,
    to_date: date,
    periods: int = 1,
    timeframe: str = "MONTH",
    standard_layout: bool = True,
) -> tuple[dict[str, Any], RateLimitState]:
    """Fetch Profit and Loss report from Xero.

    Args:
        access_token: Valid Xero access token.
        tenant_id: Xero tenant ID.
        from_date: Report period start.
        to_date: Report period end.
        periods: Number of comparison periods.
        timeframe: MONTH, QUARTER, or YEAR.
        standard_layout: Use standard chart of accounts layout.

    Returns:
        Tuple of (report dict, rate_limit_state).
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Xero-Tenant-Id": tenant_id,
        "Accept": "application/json",
    }

    # CRITICAL: date parameter needed for per-period amounts
    params = {
        "date": from_date.isoformat(),
        "fromDate": from_date.isoformat(),
        "toDate": to_date.isoformat(),
        "periods": periods,
        "timeframe": timeframe,
        "standardLayout": str(standard_layout).lower(),
    }

    response = await self.client.get(
        f"{self.settings.api_url}/Reports/ProfitAndLoss",
        headers=headers,
        params=params,
    )

    self._check_response(response)

    data = response.json()
    rate_limit = self._extract_rate_limit_state(response.headers)

    reports = data.get("Reports", [])
    return reports[0] if reports else {}, rate_limit


async def get_balance_sheet(
    self,
    access_token: str,
    tenant_id: str,
    as_of_date: date,
    periods: int = 1,
    timeframe: str = "MONTH",
) -> tuple[dict[str, Any], RateLimitState]:
    """Fetch Balance Sheet report from Xero."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Xero-Tenant-Id": tenant_id,
        "Accept": "application/json",
    }

    params = {
        "date": as_of_date.isoformat(),
        "periods": periods,
        "timeframe": timeframe,
    }

    response = await self.client.get(
        f"{self.settings.api_url}/Reports/BalanceSheet",
        headers=headers,
        params=params,
    )

    self._check_response(response)

    data = response.json()
    rate_limit = self._extract_rate_limit_state(response.headers)

    reports = data.get("Reports", [])
    return reports[0] if reports else {}, rate_limit


async def get_aged_receivables(
    self,
    access_token: str,
    tenant_id: str,
    as_of_date: date,
) -> tuple[dict[str, Any], RateLimitState]:
    """Fetch Aged Receivables by Contact report."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Xero-Tenant-Id": tenant_id,
        "Accept": "application/json",
    }

    params = {"date": as_of_date.isoformat()}

    response = await self.client.get(
        f"{self.settings.api_url}/Reports/AgedReceivablesByContact",
        headers=headers,
        params=params,
    )

    self._check_response(response)

    data = response.json()
    rate_limit = self._extract_rate_limit_state(response.headers)

    reports = data.get("Reports", [])
    return reports[0] if reports else {}, rate_limit
```

---

## Step 3: Add Repository

Create `XeroReportRepository` following existing patterns:

```python
# backend/app/modules/integrations/xero/repository.py (add to existing file)

class XeroReportRepository:
    """Repository for XeroReport entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, report_id: UUID) -> XeroReport | None:
        """Get report by ID."""
        stmt = select(XeroReport).where(XeroReport.id == report_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_cached_report(
        self,
        connection_id: UUID,
        report_type: XeroReportType,
        period_key: str,
    ) -> XeroReport | None:
        """Get cached report if exists and not expired."""
        stmt = (
            select(XeroReport)
            .where(
                XeroReport.connection_id == connection_id,
                XeroReport.report_type == report_type,
                XeroReport.period_key == period_key,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_report(
        self,
        connection_id: UUID,
        tenant_id: UUID,
        report_type: XeroReportType,
        period_key: str,
        report_data: dict,
        summary_data: dict,
        cache_ttl_hours: int = 1,
    ) -> XeroReport:
        """Insert or update a report."""
        now = datetime.now(UTC)
        cache_expires = now + timedelta(hours=cache_ttl_hours)

        existing = await self.get_cached_report(connection_id, report_type, period_key)

        if existing:
            existing.rows_data = report_data.get("Rows", [])
            existing.summary_data = summary_data
            existing.fetched_at = now
            existing.cache_expires_at = cache_expires
            existing.xero_updated_at = self._parse_xero_date(report_data.get("UpdatedDateUTC"))
            return existing

        report = XeroReport(
            tenant_id=tenant_id,
            connection_id=connection_id,
            report_type=report_type,
            period_key=period_key,
            report_name=report_data.get("ReportName", report_type.value),
            report_titles=report_data.get("ReportTitles", []),
            rows_data=report_data.get("Rows", []),
            summary_data=summary_data,
            fetched_at=now,
            cache_expires_at=cache_expires,
        )
        self.session.add(report)
        return report

    def _parse_xero_date(self, xero_date: str | None) -> datetime | None:
        """Parse Xero's /Date(1234567890000)/ format."""
        if not xero_date:
            return None
        match = re.search(r"/Date\((\d+)\)/", xero_date)
        if match:
            timestamp_ms = int(match.group(1))
            return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
        return None
```

---

## Step 4: Add Service Layer

```python
# backend/app/modules/integrations/xero/service.py (add XeroReportService)

class XeroReportService:
    """Service for fetching and managing Xero reports."""

    def __init__(
        self,
        session: AsyncSession,
        xero_client: XeroClient,
        connection_service: XeroConnectionService,
    ):
        self.session = session
        self.xero_client = xero_client
        self.connection_service = connection_service
        self.report_repo = XeroReportRepository(session)

    async def get_report(
        self,
        client_id: UUID,
        report_type: XeroReportType,
        period_key: str | None = None,
        force_refresh: bool = False,
    ) -> XeroReport:
        """Get a report, fetching from Xero if stale or not cached."""
        connection = await self.connection_service.get_active_connection(client_id)
        if not connection:
            raise XeroConnectionNotFoundError(client_id)

        # Default period key
        if not period_key:
            period_key = self._default_period_key(report_type)

        # Check cache
        if not force_refresh:
            cached = await self.report_repo.get_cached_report(
                connection.id, report_type, period_key
            )
            if cached and cached.cache_expires_at > datetime.now(UTC):
                return cached

        # Fetch from Xero
        report_data = await self._fetch_from_xero(connection, report_type, period_key)

        # Extract summary
        summary = self._extract_summary(report_type, report_data)

        # Upsert to cache
        return await self.report_repo.upsert_report(
            connection_id=connection.id,
            tenant_id=connection.tenant_id,
            report_type=report_type,
            period_key=period_key,
            report_data=report_data,
            summary_data=summary,
            cache_ttl_hours=self._get_cache_ttl(report_type),
        )

    async def _fetch_from_xero(
        self,
        connection: XeroConnection,
        report_type: XeroReportType,
        period_key: str,
    ) -> dict:
        """Fetch report data from Xero API."""
        access_token = await self.connection_service.get_valid_token(connection)

        async with self.xero_client as client:
            if report_type == XeroReportType.PROFIT_AND_LOSS:
                from_date, to_date = self._parse_period_dates(period_key)
                data, _ = await client.get_profit_and_loss(
                    access_token, connection.xero_tenant_id, from_date, to_date
                )
            elif report_type == XeroReportType.BALANCE_SHEET:
                as_of = self._parse_as_of_date(period_key)
                data, _ = await client.get_balance_sheet(
                    access_token, connection.xero_tenant_id, as_of
                )
            elif report_type == XeroReportType.AGED_RECEIVABLES:
                as_of = self._parse_as_of_date(period_key)
                data, _ = await client.get_aged_receivables(
                    access_token, connection.xero_tenant_id, as_of
                )
            # ... add other report types

        return data

    def _extract_summary(self, report_type: XeroReportType, data: dict) -> dict:
        """Extract key metrics from report for quick access."""
        # Implementation depends on report type
        # See transformers.py for full implementation
        return {}

    def _get_cache_ttl(self, report_type: XeroReportType) -> int:
        """Get cache TTL in hours for report type."""
        ttls = {
            XeroReportType.PROFIT_AND_LOSS: 1,
            XeroReportType.BALANCE_SHEET: 1,
            XeroReportType.AGED_RECEIVABLES: 4,
            XeroReportType.AGED_PAYABLES: 4,
            XeroReportType.TRIAL_BALANCE: 1,
            XeroReportType.BANK_SUMMARY: 4,
            XeroReportType.BUDGET_SUMMARY: 24,
        }
        return ttls.get(report_type, 1)
```

---

## Step 5: Add Router Endpoints

```python
# backend/app/modules/integrations/xero/router.py (add endpoints)

@router.get("/clients/{client_id}/reports")
async def list_reports(
    client_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReportListResponse:
    """List available report types for a client."""
    # Verify access to client
    client = await get_client_or_404(session, client_id, current_user.tenant_id)

    # Get report statuses
    reports = await report_service.list_report_statuses(client.id)

    return ReportListResponse(client_id=client_id, reports=reports)


@router.get("/clients/{client_id}/reports/{report_type}")
async def get_report(
    client_id: UUID,
    report_type: str,
    period: str | None = None,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReportResponse:
    """Get a specific report for the client."""
    # Map URL path to enum
    report_type_enum = XeroReportType(report_type.replace("-", "_"))

    report = await report_service.get_report(
        client_id=client_id,
        report_type=report_type_enum,
        period_key=period,
    )

    return ReportResponse.from_model(report)


@router.post("/clients/{client_id}/reports/{report_type}/refresh")
async def refresh_report(
    client_id: UUID,
    report_type: str,
    request: RefreshReportRequest | None = None,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReportResponse:
    """Force refresh a report from Xero."""
    # Check rate limit
    await rate_limiter.check_refresh_allowed(client_id, report_type)

    report_type_enum = XeroReportType(report_type.replace("-", "_"))

    report = await report_service.get_report(
        client_id=client_id,
        report_type=report_type_enum,
        period_key=request.period if request else None,
        force_refresh=True,
    )

    return ReportResponse.from_model(report)
```

---

## Step 6: Add Celery Task for Nightly Sync

```python
# backend/app/tasks/reports.py

from celery import shared_task
from app.modules.integrations.xero.service import XeroReportService

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def sync_reports_for_connection(self, connection_id: str) -> dict:
    """Sync all reports for a single Xero connection.

    Called by nightly batch job for each active connection.
    """
    import asyncio
    from app.database import async_session_maker

    async def _sync():
        async with async_session_maker() as session:
            service = XeroReportService(session, ...)

            results = {}
            for report_type in XeroReportType:
                try:
                    await service.get_report(
                        connection_id=UUID(connection_id),
                        report_type=report_type,
                        force_refresh=True,
                    )
                    results[report_type.value] = "success"
                except Exception as e:
                    results[report_type.value] = f"failed: {str(e)}"

            await session.commit()
            return results

    return asyncio.run(_sync())


@shared_task
def nightly_report_sync() -> dict:
    """Nightly job to sync reports for all active connections.

    Scheduled via Celery Beat at 2 AM AEST.
    """
    from app.modules.integrations.xero.repository import XeroConnectionRepository

    # Get all active connections
    connections = XeroConnectionRepository.get_active_connections()

    # Queue sync for each
    for conn in connections:
        sync_reports_for_connection.delay(str(conn.id))

    return {"queued": len(connections)}
```

---

## Step 7: Frontend Integration

Add report components to the client detail page:

```typescript
// frontend/src/lib/api/reports.ts

import { apiClient } from './client';

export interface ReportSummary {
  report_type: string;
  display_name: string;
  available: boolean;
  last_synced_at: string | null;
  cache_status: 'fresh' | 'stale' | 'expired' | 'not_synced';
}

export interface Report {
  id: string;
  client_id: string;
  report_type: string;
  report_name: string;
  period_key: string;
  fetched_at: string;
  is_fresh: boolean;
  summary: Record<string, unknown>;
  rows: ReportRow[];
}

export async function listReports(clientId: string): Promise<ReportSummary[]> {
  const response = await apiClient.get(`/clients/${clientId}/reports`);
  return response.data.reports;
}

export async function getReport(
  clientId: string,
  reportType: string,
  period?: string
): Promise<Report> {
  const params = period ? { period } : {};
  const response = await apiClient.get(
    `/clients/${clientId}/reports/${reportType}`,
    { params }
  );
  return response.data;
}

export async function refreshReport(
  clientId: string,
  reportType: string
): Promise<Report> {
  const response = await apiClient.post(
    `/clients/${clientId}/reports/${reportType}/refresh`
  );
  return response.data;
}
```

---

## Testing

### Unit Test Example

```python
# backend/tests/unit/modules/integrations/xero/test_report_service.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.modules.integrations.xero.service import XeroReportService

@pytest.fixture
def mock_xero_client():
    client = MagicMock()
    client.get_profit_and_loss = AsyncMock(return_value=({
        "ReportName": "Profit and Loss",
        "Rows": [{"RowType": "Header", "Cells": []}],
    }, MagicMock()))
    return client

@pytest.mark.asyncio
async def test_get_report_fetches_from_xero_when_not_cached(
    mock_xero_client,
    mock_session,
    mock_connection,
):
    service = XeroReportService(mock_session, mock_xero_client, ...)

    report = await service.get_report(
        client_id=mock_connection.client_id,
        report_type=XeroReportType.PROFIT_AND_LOSS,
    )

    assert report.report_type == XeroReportType.PROFIT_AND_LOSS
    mock_xero_client.get_profit_and_loss.assert_called_once()
```

### Contract Test Example

```python
# backend/tests/contract/adapters/test_xero_reports_api.py

import pytest
import httpx
from datetime import date

@pytest.mark.contract
async def test_xero_profit_and_loss_endpoint():
    """Verify Xero P&L endpoint contract."""
    # Use recorded response or live API with test org
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.xero.com/api.xro/2.0/Reports/ProfitAndLoss",
            headers={
                "Authorization": f"Bearer {TEST_TOKEN}",
                "Xero-Tenant-Id": TEST_TENANT,
            },
            params={"fromDate": "2025-01-01", "toDate": "2025-12-31"},
        )

    assert response.status_code == 200
    data = response.json()

    # Verify contract
    assert "Reports" in data
    assert len(data["Reports"]) > 0
    report = data["Reports"][0]
    assert "ReportName" in report
    assert "Rows" in report
```

---

## Common Issues

### 1. Rate Limit Exceeded

```python
# Error: XeroRateLimitError: Rate limit exceeded
# Solution: Check rate limit state before making requests

async def fetch_with_rate_limit(connection_id: UUID):
    state = await rate_limiter.get_state(connection_id)
    if state.minute_remaining < 5:
        raise TooManyRequestsError("Rate limit too low, try again later")
    # ... proceed with fetch
```

### 2. Empty Report Data

```python
# Issue: Report returns empty Rows array
# Cause: No transactions in the requested period

if not report_data.get("Rows"):
    return EmptyReportResponse(
        message="No data available for this period",
        period=period_key,
    )
```

### 3. Token Expiry During Sync

```python
# Issue: XeroAuthError mid-sync
# Solution: Refresh token before each batch

async def sync_with_token_refresh(connection: XeroConnection):
    try:
        token = await connection_service.get_valid_token(connection)
    except TokenExpiredError:
        await connection_service.refresh_connection(connection)
        token = await connection_service.get_valid_token(connection)
    # ... continue with sync
```

---

## Next Steps

1. Run tests: `uv run pytest tests/unit/modules/integrations/xero/test_report_*.py`
2. Test with real Xero org using demo company
3. Add remaining report types (Aged Payables, Trial Balance, etc.)
4. Integrate with AI agents (update context providers)
5. Add frontend components for report display

---

## Reference Documentation

- [Xero Accounting API Reports](https://developer.xero.com/documentation/api/accounting/reports)
- [Spec 023 - Feature Spec](./spec.md)
- [Plan Document](./plan.md)
- [Data Model](./data-model.md)
- [API Contract](./contracts/reports-api.yaml)
