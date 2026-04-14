"""Xero client data service — read-only queries for client businesses, invoices, transactions, and financial summaries."""

from __future__ import annotations

import logging
from datetime import date, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.xero.exceptions import XeroClientNotFoundError
from app.modules.integrations.xero.repository import (
    XeroBankTransactionRepository,
    XeroClientRepository,
    XeroConnectionRepository,
    XeroInvoiceRepository,
)
from app.modules.integrations.xero.schemas import (
    AvailableQuartersResponse,
    ClientFinancialSummaryResponse,
    QuarterInfo,
    XeroBankTransactionListResponse,
    XeroBankTransactionResponse,
    XeroClientDetailResponse,
    XeroClientListResponse,
    XeroClientResponse,
    XeroInvoiceListResponse,
    XeroInvoiceResponse,
)
from app.modules.integrations.xero.utils import (
    format_quarter,
    get_available_quarters,
    get_current_quarter,
    get_quarter_dates,
)

logger = logging.getLogger(__name__)


class XeroClientService:
    """Service for viewing client data and financial summaries.

    Provides read-only operations for:
    - Listing clients with filtering and pagination
    - Getting client details with connection metadata
    - Retrieving client invoices and transactions
    - Calculating BAS quarter financial summaries
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize client service.

        Args:
            session: Database session.
        """
        self.session = session
        self.client_repo = XeroClientRepository(session)
        self.invoice_repo = XeroInvoiceRepository(session)
        self.transaction_repo = XeroBankTransactionRepository(session)
        self.connection_repo = XeroConnectionRepository(session)

    async def list_clients(
        self,
        search: str | None = None,
        contact_type: str | None = None,
        is_active: bool | None = None,
        sort_by: Literal[name, contact_type, created_at] = "name",
        sort_order: Literal[asc, desc] = "asc",
        limit: int = 25,
        offset: int = 0,
    ) -> XeroClientListResponse:
        """List all clients for the current tenant.

        Args:
            search: Optional search term for name/email.
            contact_type: Filter by contact type (CUSTOMER, SUPPLIER, etc.).
            is_active: Filter by active status.
            sort_by: Field to sort by.
            sort_order: Sort direction.
            limit: Maximum results to return.
            offset: Number of results to skip.

        Returns:
            XeroClientListResponse with clients and pagination info.
        """
        clients, total = await self.client_repo.list_all_for_tenant(
            search=search,
            contact_type=contact_type,
            is_active=is_active,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )

        return XeroClientListResponse(
            clients=[XeroClientResponse.model_validate(c) for c in clients],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_client_detail(self, client_id: UUID) -> XeroClientDetailResponse:
        """Get detailed client information with connection metadata.

        Args:
            client_id: The client ID.

        Returns:
            XeroClientDetailResponse with full client details.

        Raises:
            XeroClientNotFoundError: If client not found.
        """
        client = await self.client_repo.get_by_id(client_id)
        if client is None:
            raise XeroClientNotFoundError(client_id)

        # Get connection for metadata
        connection = await self.connection_repo.get_by_id(client.connection_id)

        return XeroClientDetailResponse(
            id=client.id,
            connection_id=client.connection_id,
            xero_contact_id=client.xero_contact_id,
            name=client.name,
            email=client.email,
            contact_number=client.contact_number,
            abn=client.abn,
            contact_type=client.contact_type,
            is_active=client.is_active,
            addresses=client.addresses,
            phones=client.phones,
            xero_updated_at=client.xero_updated_at,
            created_at=client.created_at,
            updated_at=client.updated_at,
            organization_name=connection.organization_name if connection else "Unknown",
            connection_status=connection.status if connection else None,
            last_synced_at=connection.last_contacts_sync_at if connection else None,
        )

    async def get_client_invoices(
        self,
        client_id: UUID,
        from_date: date | None = None,
        to_date: date | None = None,
        status: str | None = None,
        invoice_type: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> XeroInvoiceListResponse:
        """Get invoices for a specific client.

        Args:
            client_id: The client ID.
            from_date: Filter invoices from this date.
            to_date: Filter invoices to this date.
            status: Filter by invoice status.
            invoice_type: Filter by invoice type (ACCREC, ACCPAY).
            limit: Maximum results to return.
            offset: Number of results to skip.

        Returns:
            XeroInvoiceListResponse with invoices and pagination info.

        Raises:
            XeroClientNotFoundError: If client not found.
        """
        # Verify client exists
        client = await self.client_repo.get_by_id(client_id)
        if client is None:
            raise XeroClientNotFoundError(client_id)

        invoices, total = await self.invoice_repo.list_by_client(
            client_id=client_id,
            from_date=from_date,
            to_date=to_date,
            status=status,
            invoice_type=invoice_type,
            limit=limit,
            offset=offset,
        )

        return XeroInvoiceListResponse(
            invoices=[XeroInvoiceResponse.model_validate(inv) for inv in invoices],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_client_transactions(
        self,
        client_id: UUID,
        from_date: date | None = None,
        to_date: date | None = None,
        transaction_type: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> XeroBankTransactionListResponse:
        """Get bank transactions for a specific client.

        Args:
            client_id: The client ID.
            from_date: Filter transactions from this date.
            to_date: Filter transactions to this date.
            transaction_type: Filter by transaction type.
            limit: Maximum results to return.
            offset: Number of results to skip.

        Returns:
            XeroBankTransactionListResponse with transactions and pagination info.

        Raises:
            XeroClientNotFoundError: If client not found.
        """
        # Verify client exists
        client = await self.client_repo.get_by_id(client_id)
        if client is None:
            raise XeroClientNotFoundError(client_id)

        transactions, total = await self.transaction_repo.list_by_client(
            client_id=client_id,
            from_date=from_date,
            to_date=to_date,
            transaction_type=transaction_type,
            limit=limit,
            offset=offset,
        )

        return XeroBankTransactionListResponse(
            transactions=[XeroBankTransactionResponse.model_validate(tx) for tx in transactions],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_client_financial_summary(
        self,
        client_id: UUID,
        quarter: int,
        fy_year: int,
    ) -> ClientFinancialSummaryResponse:
        """Calculate financial summary for a client in a specific quarter.

        Args:
            client_id: The client ID.
            quarter: Quarter number (1-4).
            fy_year: Financial year (e.g., 2025 for FY25).

        Returns:
            ClientFinancialSummaryResponse with BAS-relevant totals.

        Raises:
            XeroClientNotFoundError: If client not found.
            ValueError: If quarter is invalid.
        """
        # Verify client exists
        client = await self.client_repo.get_by_id(client_id)
        if client is None:
            raise XeroClientNotFoundError(client_id)

        # Get quarter date range
        start_date, end_date = get_quarter_dates(quarter, fy_year)

        # Calculate invoice summary
        invoice_summary = await self.invoice_repo.calculate_summary(
            client_id=client_id,
            from_date=start_date,
            to_date=end_date,
        )

        # Get transaction count for the period
        transaction_count = await self.transaction_repo.count_by_client_and_date_range(
            client_id=client_id,
            from_date=start_date,
            to_date=end_date,
        )

        # Calculate total invoice count from sales + purchases
        invoice_count = (
            invoice_summary["sales_invoice_count"] + invoice_summary["purchase_invoice_count"]
        )

        return ClientFinancialSummaryResponse(
            client_id=client_id,
            quarter=quarter,
            fy_year=fy_year,
            quarter_label=format_quarter(quarter, fy_year),
            total_sales=invoice_summary["total_sales"],
            gst_collected=invoice_summary["gst_collected"],
            total_purchases=invoice_summary["total_purchases"],
            gst_paid=invoice_summary["gst_paid"],
            invoice_count=invoice_count,
            transaction_count=transaction_count,
            net_gst=invoice_summary["gst_collected"] - invoice_summary["gst_paid"],
        )

    def get_available_quarters(
        self,
        num_previous: int = 4,
        include_next: bool = True,
    ) -> AvailableQuartersResponse:
        """Get list of available quarters for selection.

        Args:
            num_previous: Number of previous quarters to include.
            include_next: Whether to include next quarter if near end of current.

        Returns:
            AvailableQuartersResponse with quarters list and current quarter.
        """
        quarters = get_available_quarters(
            num_previous=num_previous,
            include_next=include_next,
        )
        current_q, current_fy = get_current_quarter()

        quarter_infos = []
        for q, fy in quarters:
            start, end = get_quarter_dates(q, fy)
            quarter_infos.append(
                QuarterInfo(
                    quarter=q,
                    fy_year=fy,
                    label=format_quarter(q, fy),
                    start_date=datetime.combine(start, datetime.min.time()),
                    end_date=datetime.combine(end, datetime.max.time()),
                )
            )

        # Build current quarter info
        current_start, current_end = get_quarter_dates(current_q, current_fy)
        current_info = QuarterInfo(
            quarter=current_q,
            fy_year=current_fy,
            label=format_quarter(current_q, current_fy),
            start_date=datetime.combine(current_start, datetime.min.time()),
            end_date=datetime.combine(current_end, datetime.max.time()),
        )

        return AvailableQuartersResponse(
            quarters=quarter_infos,
            current=current_info,
        )
