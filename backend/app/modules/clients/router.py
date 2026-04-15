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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.database import get_db
from app.modules.auth.models import PracticeUser
from app.modules.auth.permissions import Permission, require_permission
from app.modules.clients.schemas import (
    BulkAssignResponse,
    ClientDetailResponse,
    ClientExclusionCreate,
    ClientExclusionResponse,
    ClientExclusionReversedResponse,
    ContactListResponse,
    EmployeeListResponse,
    FinancialSummaryResponse,
    InvoiceListResponse,
    ManualStatusUpdate,
    NoteHistoryResponse,
    PayRunListResponse,
    PracticeClientAssignRequest,
    PracticeClientBulkAssignRequest,
    PracticeClientCreate,
    PracticeClientNotesUpdate,
    PracticeClientResponse,
    TransactionListResponse,
)
from app.modules.clients.service import ClientsService, PracticeClientService
from app.modules.dashboard.schemas import ClientPortfolioResponse
from app.modules.dashboard.service import DashboardService

router = APIRouter(prefix="/clients", tags=["Clients"])


# =============================================================================
# Practice Client Management Endpoints (Spec 058)
# =============================================================================


@router.post(
    "/manual",
    response_model=PracticeClientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create non-Xero client",
)
async def create_manual_client(
    request: PracticeClientCreate,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> PracticeClientResponse:
    """Create a manually-added client (QuickBooks, MYOB, email-based, etc.)."""
    service = PracticeClientService(db)
    return await service.create_manual_client(
        data=request,
        tenant_id=current_user.tenant_id,
    )


@router.patch(
    "/{client_id}/assign",
    response_model=PracticeClientResponse,
    summary="Assign team member to client",
)
async def assign_client(
    client_id: UUID,
    request: PracticeClientAssignRequest,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> PracticeClientResponse:
    """Assign or reassign a team member to a client."""
    service = PracticeClientService(db)
    try:
        return await service.assign_client(
            client_id=client_id,
            assigned_user_id=request.assigned_user_id,
            tenant_id=current_user.tenant_id,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Client not found")


@router.post(
    "/bulk-assign",
    response_model=BulkAssignResponse,
    summary="Bulk assign team member",
)
async def bulk_assign_clients(
    request: PracticeClientBulkAssignRequest,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> BulkAssignResponse:
    """Assign a team member to multiple clients at once."""
    service = PracticeClientService(db)
    return await service.bulk_assign_clients(
        client_ids=request.client_ids,
        assigned_user_id=request.assigned_user_id,
        tenant_id=current_user.tenant_id,
    )


@router.patch(
    "/{client_id}/notes",
    response_model=PracticeClientResponse,
    summary="Update persistent client notes",
)
async def update_client_notes(
    client_id: UUID,
    request: PracticeClientNotesUpdate,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> PracticeClientResponse:
    """Update persistent notes for a client."""
    service = PracticeClientService(db)
    try:
        return await service.update_notes(
            client_id=client_id,
            notes=request.notes,
            tenant_id=current_user.tenant_id,
            updated_by=current_user.id,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Client not found")


@router.get(
    "/{client_id}/notes/history",
    response_model=NoteHistoryResponse,
    summary="Get note change history",
)
async def get_note_history(
    client_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    db: AsyncSession = Depends(get_db),
) -> NoteHistoryResponse:
    """Get change history for a client's persistent notes."""
    service = PracticeClientService(db)
    return await service.get_note_history(
        client_id=client_id,
        tenant_id=current_user.tenant_id,
    )


@router.post(
    "/{client_id}/exclusions",
    response_model=ClientExclusionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Exclude client from quarter",
)
async def exclude_client(
    client_id: UUID,
    request: ClientExclusionCreate,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> ClientExclusionResponse:
    """Exclude a client from BAS obligations for a specific quarter."""
    service = PracticeClientService(db)
    try:
        return await service.exclude_client(
            client_id=client_id,
            data=request,
            tenant_id=current_user.tenant_id,
            excluded_by=current_user.id,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Client not found")
    except ConflictError:
        raise HTTPException(status_code=409, detail="Client already excluded for this quarter")


@router.delete(
    "/{client_id}/exclusions/{exclusion_id}",
    response_model=ClientExclusionReversedResponse,
    summary="Reverse client exclusion",
)
async def reverse_exclusion(
    client_id: UUID,
    exclusion_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> ClientExclusionReversedResponse:
    """Reverse a client's quarter exclusion."""
    service = PracticeClientService(db)
    try:
        return await service.reverse_exclusion(
            client_id=client_id,
            exclusion_id=exclusion_id,
            tenant_id=current_user.tenant_id,
            reversed_by=current_user.id,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Exclusion not found")


@router.patch(
    "/{client_id}/manual-status",
    response_model=PracticeClientResponse,
    summary="Update BAS status for non-Xero client",
)
async def update_manual_status(
    client_id: UUID,
    request: ManualStatusUpdate,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> PracticeClientResponse:
    """Update BAS status for a non-Xero client (manual progression)."""
    service = PracticeClientService(db)
    try:
        return await service.update_manual_status(
            client_id=client_id,
            status=request.manual_status,
            tenant_id=current_user.tenant_id,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Client not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=ClientPortfolioResponse)
async def list_clients(
    quarter: int | None = Query(None, ge=1, le=4, description="BAS quarter (1-4)"),
    fy_year: int | None = Query(None, ge=2020, le=2100, description="Financial year"),
    status: str | None = Query(
        None,
        description="Filter by BAS status: ready, needs_review, no_activity, missing_data",
    ),
    search: str | None = Query(None, description="Search by client name"),
    sort_by: str = Query(
        "organization_name",
        description="Sort by: organization_name, total_sales, total_purchases, net_gst, activity_count",
    ),
    sort_order: str = Query("asc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(25, ge=1, le=100, description="Items per page"),
    assigned_user_id: UUID | None = Query(None, description="Filter by assigned team member"),
    show_excluded: bool = Query(False, description="Show excluded clients instead of active"),
    software: str | None = Query(None, description="Filter by accounting software type"),
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    db: AsyncSession = Depends(get_db),
) -> ClientPortfolioResponse:
    """List all practice clients for the tenant.

    Each client represents one business the practice manages.
    Includes Xero-connected and manually-added clients.
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
        assigned_user_id=assigned_user_id,
        show_excluded=show_excluded,
        software=software,
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
