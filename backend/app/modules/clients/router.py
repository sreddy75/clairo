"""API endpoints for clients module.

CRITICAL: In Clairo, "client" = XeroConnection = one business = one BAS to lodge.
This module provides endpoints for viewing individual client businesses.

Endpoints:
- GET /api/v1/clients - List all client businesses (uses dashboard logic)
- GET /api/v1/clients/{id} - Get client business detail
- GET /api/v1/clients/{id}/contacts - List contacts for a business
- GET /api/v1/clients/{id}/invoices - List invoices for a business
- GET /api/v1/clients/{id}/transactions - List transactions for a business
- GET /api/v1/clients/{id}/summary - Get financial summary
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.models import PracticeUser
from app.modules.auth.permissions import Permission, require_permission
from app.modules.clients.schemas import (
    ClientDetailResponse,
    ContactListResponse,
    EmployeeListResponse,
    FinancialSummaryResponse,
    InvoiceListResponse,
    PayRunListResponse,
    TransactionListResponse,
)
from app.modules.clients.service import ClientsService
from app.modules.dashboard.schemas import ClientPortfolioResponse
from app.modules.dashboard.service import DashboardService

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.get("", response_model=ClientPortfolioResponse)
async def list_clients(
    quarter: int | None = Query(None, ge=1, le=4, description="BAS quarter (1-4)"),
    fy_year: int | None = Query(None, ge=2020, le=2100, description="Financial year"),
    status: str | None = Query(
        None,
        description="Filter by BAS status: ready, needs_review, no_activity, missing_data",
    ),
    search: str | None = Query(None, description="Search by organization name"),
    sort_by: str = Query(
        "organization_name",
        description="Sort by: organization_name, total_sales, total_purchases, net_gst, activity_count",
    ),
    sort_order: str = Query("asc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(25, ge=1, le=100, description="Items per page"),
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    db: AsyncSession = Depends(get_db),
) -> ClientPortfolioResponse:
    """List all client businesses (XeroConnections) for the tenant.

    Each client business represents one Xero organization = one BAS to lodge.
    Reuses the dashboard service for consistent data.
    """
    service = DashboardService(db)
    return await service.get_client_portfolio(
        tenant_id=current_user.tenant_id,
        quarter=quarter,
        fy_year=fy_year,
        status=status,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        limit=limit,
    )


@router.get("/{connection_id}", response_model=ClientDetailResponse)
async def get_client_detail(
    connection_id: UUID,
    quarter: int | None = Query(None, ge=1, le=4, description="BAS quarter (1-4)"),
    fy_year: int | None = Query(None, ge=2020, le=2100, description="Financial year"),
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    db: AsyncSession = Depends(get_db),
) -> ClientDetailResponse:
    """Get detailed view of a single client business (XeroConnection).

    Returns the business details along with financial summary for the specified quarter.
    """
    service = ClientsService(db)
    result = await service.get_client_detail(
        tenant_id=current_user.tenant_id,
        connection_id=connection_id,
        quarter=quarter,
        fy_year=fy_year,
    )

    if not result:
        raise HTTPException(status_code=404, detail="Client not found")

    return result


@router.get("/{connection_id}/summary", response_model=FinancialSummaryResponse)
async def get_client_summary(
    connection_id: UUID,
    quarter: int | None = Query(None, ge=1, le=4, description="BAS quarter (1-4)"),
    fy_year: int | None = Query(None, ge=2020, le=2100, description="Financial year"),
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    db: AsyncSession = Depends(get_db),
) -> FinancialSummaryResponse:
    """Get financial summary for a client business.

    Returns aggregated financial data for the specified BAS quarter.
    """
    service = ClientsService(db)
    result = await service.get_financial_summary(
        tenant_id=current_user.tenant_id,
        connection_id=connection_id,
        quarter=quarter,
        fy_year=fy_year,
    )

    if not result:
        raise HTTPException(status_code=404, detail="Client not found")

    return result


@router.get("/{connection_id}/contacts", response_model=ContactListResponse)
async def list_client_contacts(
    connection_id: UUID,
    contact_type: str | None = Query(None, description="Filter by: customer, supplier, both"),
    search: str | None = Query(None, description="Search by name or ABN"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(25, ge=1, le=100, description="Items per page"),
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    db: AsyncSession = Depends(get_db),
) -> ContactListResponse:
    """List contacts (customers/suppliers) for a client business.

    These are XeroClient records - the customers and suppliers of the business.
    """
    service = ClientsService(db)
    result = await service.list_contacts(
        tenant_id=current_user.tenant_id,
        connection_id=connection_id,
        contact_type=contact_type,
        search=search,
        page=page,
        limit=limit,
    )

    if not result:
        raise HTTPException(status_code=404, detail="Client not found")

    return result


@router.get("/{connection_id}/invoices", response_model=InvoiceListResponse)
async def list_client_invoices(
    connection_id: UUID,
    invoice_type: str | None = Query(
        None, description="Filter by: accrec (sales), accpay (purchases)"
    ),
    status: str | None = Query(
        None, description="Filter by: draft, submitted, authorised, paid, voided"
    ),
    from_date: date | None = Query(None, description="Start date filter (optional)"),
    to_date: date | None = Query(None, description="End date filter (optional)"),
    sort_by: str = Query("issue_date", description="Sort by: issue_date, due_date, total_amount"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    db: AsyncSession = Depends(get_db),
) -> InvoiceListResponse:
    """List invoices for a client business.

    Returns invoices (sales and purchases) for the connection.
    Shows all invoices unless date filters are explicitly provided.
    """
    service = ClientsService(db)
    result = await service.list_invoices(
        tenant_id=current_user.tenant_id,
        connection_id=connection_id,
        invoice_type=invoice_type,
        status=status,
        from_date=from_date,
        to_date=to_date,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        limit=limit,
    )

    if not result:
        raise HTTPException(status_code=404, detail="Client not found")

    return result


@router.get("/{connection_id}/transactions", response_model=TransactionListResponse)
async def list_client_transactions(
    connection_id: UUID,
    transaction_type: str | None = Query(None, description="Filter by: receive, spend"),
    from_date: date | None = Query(None, description="Start date filter (optional)"),
    to_date: date | None = Query(None, description="End date filter (optional)"),
    sort_by: str = Query("transaction_date", description="Sort by: transaction_date, total_amount"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    db: AsyncSession = Depends(get_db),
) -> TransactionListResponse:
    """List bank transactions for a client business.

    Returns bank transactions for the connection.
    Shows all transactions unless date filters are explicitly provided.
    """
    service = ClientsService(db)
    result = await service.list_transactions(
        tenant_id=current_user.tenant_id,
        connection_id=connection_id,
        transaction_type=transaction_type,
        from_date=from_date,
        to_date=to_date,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        limit=limit,
    )

    if not result:
        raise HTTPException(status_code=404, detail="Client not found")

    return result


@router.get("/{connection_id}/employees", response_model=EmployeeListResponse)
async def list_client_employees(
    connection_id: UUID,
    status: str | None = Query(None, description="Filter by: active, terminated"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(25, ge=1, le=100, description="Items per page"),
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    db: AsyncSession = Depends(get_db),
) -> EmployeeListResponse:
    """List employees for a client business (from Xero Payroll).

    Returns employees synced from Xero Payroll API.
    Only available for connections with payroll access.
    """
    service = ClientsService(db)
    result = await service.list_employees(
        tenant_id=current_user.tenant_id,
        connection_id=connection_id,
        status=status,
        page=page,
        limit=limit,
    )

    if not result:
        raise HTTPException(status_code=404, detail="Client not found")

    return result


@router.get("/{connection_id}/pay-runs", response_model=PayRunListResponse)
async def list_client_pay_runs(
    connection_id: UUID,
    status: str | None = Query(None, description="Filter by: draft, posted"),
    from_date: date | None = Query(None, description="Start date (defaults to quarter start)"),
    to_date: date | None = Query(None, description="End date (defaults to quarter end)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    db: AsyncSession = Depends(get_db),
) -> PayRunListResponse:
    """List pay runs for a client business (from Xero Payroll).

    Returns pay runs synced from Xero Payroll API with PAYG withholding totals.
    Defaults to current quarter if no date range specified.
    """
    service = ClientsService(db)
    result = await service.list_pay_runs(
        tenant_id=current_user.tenant_id,
        connection_id=connection_id,
        status=status,
        from_date=from_date,
        to_date=to_date,
        page=page,
        limit=limit,
    )

    if not result:
        raise HTTPException(status_code=404, detail="Client not found")

    return result
