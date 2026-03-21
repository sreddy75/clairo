"""Service layer for clients module.

CRITICAL: In Clairo, "client" = XeroConnection = one business = one BAS to lodge.
"""

from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.repository import ClientsRepository
from app.modules.clients.schemas import (
    ClientDetailResponse,
    ContactItem,
    ContactListResponse,
    EmployeeItem,
    EmployeeListResponse,
    EmployeeStatus,
    FinancialSummaryResponse,
    InvoiceItem,
    InvoiceListResponse,
    PayRunItem,
    PayRunListResponse,
    PayRunStatus,
    TransactionItem,
    TransactionListResponse,
)
from app.modules.integrations.xero.payroll_repository import XeroPayrollRepository
from app.modules.quality.repository import QualityRepository


def get_quarter_dates(
    quarter: int | None = None, fy_year: int | None = None
) -> tuple[date, date, str, int, int]:
    """Calculate quarter start/end dates for Australian financial year.

    Australian FY: July-June
    Q1: Jul-Sep, Q2: Oct-Dec, Q3: Jan-Mar, Q4: Apr-Jun

    Returns: (quarter_start, quarter_end, quarter_label, quarter, fy_year)
    """
    from datetime import UTC, datetime

    today = datetime.now(UTC).date()

    # Determine current quarter if not specified
    if quarter is None or fy_year is None:
        month = today.month
        year = today.year

        if month >= 7:  # Jul-Dec
            current_fy = year + 1
            current_q = 1 if month <= 9 else 2
        else:  # Jan-Jun
            current_fy = year
            current_q = 3 if month <= 3 else 4

        quarter = quarter or current_q
        fy_year = fy_year or current_fy

    # Calculate quarter dates
    quarter_months = {
        1: (7, 9),  # Jul-Sep
        2: (10, 12),  # Oct-Dec
        3: (1, 3),  # Jan-Mar
        4: (4, 6),  # Apr-Jun
    }

    start_month, end_month = quarter_months[quarter]

    # Determine calendar year for start/end
    if quarter in [1, 2]:  # Jul-Dec
        start_year = fy_year - 1
        end_year = fy_year - 1
    else:  # Jan-Jun
        start_year = fy_year
        end_year = fy_year

    # Handle December (31 days) vs other months
    if end_month == 12:
        end_day = 31
    elif end_month in [4, 6, 9]:
        end_day = 30
    else:
        end_day = 31

    quarter_start = date(start_year, start_month, 1)
    quarter_end = date(end_year, end_month, end_day)
    quarter_label = f"Q{quarter} FY{str(fy_year)[-2:]}"

    return quarter_start, quarter_end, quarter_label, quarter, fy_year


class ClientsService:
    """Service for client business operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = ClientsRepository(db)
        self.payroll_repo = XeroPayrollRepository(db)
        self.quality_repo = QualityRepository(db)

    async def get_client_detail(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        quarter: int | None = None,
        fy_year: int | None = None,
    ) -> ClientDetailResponse | None:
        """Get detailed view of a client business."""
        quarter_start, quarter_end, quarter_label, q, fy = get_quarter_dates(quarter, fy_year)

        data = await self.repository.get_connection_with_financials(
            tenant_id=tenant_id,
            connection_id=connection_id,
            quarter_start=quarter_start,
            quarter_end=quarter_end,
        )

        if not data:
            return None

        # Get payroll data if connection has payroll access
        payroll_data = await self._get_payroll_summary(
            connection_id=connection_id,
            quarter_start=quarter_start,
            quarter_end=quarter_end,
            has_payroll=data.get("has_payroll_access", False),
            last_payroll_sync_at=data.get("last_payroll_sync_at"),
        )

        # Get quality data
        quality_data = await self.quality_repo.get_quality_scores_for_connections(
            connection_ids=[connection_id],
            quarter=q,
            fy_year=fy,
        )
        quality_info = quality_data.get(connection_id, {})

        return ClientDetailResponse(
            id=data["id"],
            organization_name=data["organization_name"],
            xero_tenant_id=data["xero_tenant_id"],
            status=data["status"],
            last_full_sync_at=data["last_full_sync_at"],
            bas_status=data["bas_status"],
            contact_email=data.get("contact_email"),
            total_sales=data["total_sales"],
            total_purchases=data["total_purchases"],
            gst_collected=data["gst_collected"],
            gst_paid=data["gst_paid"],
            net_gst=data["net_gst"],
            invoice_count=data["invoice_count"],
            transaction_count=data["transaction_count"],
            contact_count=data["contact_count"],
            quarter_label=quarter_label,
            quarter=q,
            fy_year=fy,
            has_payroll=payroll_data["has_payroll"],  # type: ignore[arg-type]
            total_wages=payroll_data["total_wages"],  # type: ignore[arg-type]
            total_tax_withheld=payroll_data["total_tax_withheld"],  # type: ignore[arg-type]
            total_super=payroll_data["total_super"],  # type: ignore[arg-type]
            pay_run_count=payroll_data["pay_run_count"],  # type: ignore[arg-type]
            employee_count=payroll_data["employee_count"],  # type: ignore[arg-type]
            last_payroll_sync_at=payroll_data["last_payroll_sync_at"],  # type: ignore[arg-type]
            quality_score=quality_info.get("overall_score"),
            critical_issues=quality_info.get("critical_issues", 0),
        )

    async def get_financial_summary(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        quarter: int | None = None,
        fy_year: int | None = None,
    ) -> FinancialSummaryResponse | None:
        """Get financial summary for a client business."""
        quarter_start, quarter_end, quarter_label, q, fy = get_quarter_dates(quarter, fy_year)

        data = await self.repository.get_connection_with_financials(
            tenant_id=tenant_id,
            connection_id=connection_id,
            quarter_start=quarter_start,
            quarter_end=quarter_end,
        )

        if not data:
            return None

        # Get payroll data if connection has payroll access
        payroll_data = await self._get_payroll_summary(
            connection_id=connection_id,
            quarter_start=quarter_start,
            quarter_end=quarter_end,
            has_payroll=data.get("has_payroll_access", False),
            last_payroll_sync_at=data.get("last_payroll_sync_at"),
        )

        return FinancialSummaryResponse(
            quarter_label=quarter_label,
            quarter=q,
            fy_year=fy,
            total_sales=data["total_sales"],
            total_purchases=data["total_purchases"],
            gst_collected=data["gst_collected"],
            gst_paid=data["gst_paid"],
            net_gst=data["net_gst"],
            invoice_count=data["invoice_count"],
            transaction_count=data["transaction_count"],
            has_payroll=payroll_data["has_payroll"],  # type: ignore[arg-type]
            total_wages=payroll_data["total_wages"],  # type: ignore[arg-type]
            total_tax_withheld=payroll_data["total_tax_withheld"],  # type: ignore[arg-type]
            total_super=payroll_data["total_super"],  # type: ignore[arg-type]
            pay_run_count=payroll_data["pay_run_count"],  # type: ignore[arg-type]
            employee_count=payroll_data["employee_count"],  # type: ignore[arg-type]
        )

    async def _get_payroll_summary(
        self,
        connection_id: UUID,
        quarter_start: date,
        quarter_end: date,
        has_payroll: bool,
        last_payroll_sync_at: date | None,
    ) -> dict[str, object]:
        """Get payroll summary data for a connection."""
        from decimal import Decimal

        if not has_payroll:
            return {
                "has_payroll": False,
                "total_wages": Decimal("0.00"),
                "total_tax_withheld": Decimal("0.00"),
                "total_super": Decimal("0.00"),
                "pay_run_count": 0,
                "employee_count": 0,
                "last_payroll_sync_at": None,
            }

        # Get aggregated payroll data
        summary = await self.payroll_repo.get_payroll_summary(
            connection_id=connection_id,
            from_date=quarter_start,
            to_date=quarter_end,
        )

        # Get active employee count
        employee_count = await self.payroll_repo.get_employee_count(connection_id)

        return {
            "has_payroll": True,
            "total_wages": summary["total_wages"],
            "total_tax_withheld": summary["total_tax_withheld"],
            "total_super": summary["total_super"],
            "pay_run_count": summary["pay_run_count"],
            "employee_count": employee_count,
            "last_payroll_sync_at": last_payroll_sync_at,
        }

    async def list_contacts(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        contact_type: str | None = None,
        search: str | None = None,
        page: int = 1,
        limit: int = 25,
    ) -> ContactListResponse | None:
        """List contacts for a client business."""
        # Verify connection belongs to tenant
        connection = await self.repository.get_connection(tenant_id, connection_id)
        if not connection:
            return None

        offset = (page - 1) * limit
        contacts_data, total = await self.repository.list_contacts(
            connection_id=connection_id,
            contact_type=contact_type,
            search=search,
            limit=limit,
            offset=offset,
        )

        contacts = [ContactItem(**c) for c in contacts_data]

        return ContactListResponse(
            contacts=contacts,
            total=total,
            page=page,
            limit=limit,
        )

    async def list_invoices(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        invoice_type: str | None = None,
        status: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        sort_by: str = "issue_date",
        sort_order: str = "desc",
        page: int = 1,
        limit: int = 20,
    ) -> InvoiceListResponse | None:
        """List invoices for a client business.

        Note: Unlike financial summaries, invoice listings show ALL invoices
        unless date filters are explicitly provided. This allows the tabs to
        display all historical data while the quarter dropdown controls
        financial calculations.
        """
        # Verify connection belongs to tenant
        connection = await self.repository.get_connection(tenant_id, connection_id)
        if not connection:
            return None

        # No default date filtering - show all invoices unless dates specified
        offset = (page - 1) * limit
        invoices_data, total = await self.repository.list_invoices(
            connection_id=connection_id,
            invoice_type=invoice_type,
            status=status,
            from_date=from_date,
            to_date=to_date,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )

        invoices = [InvoiceItem(**i) for i in invoices_data]

        return InvoiceListResponse(
            invoices=invoices,
            total=total,
            page=page,
            limit=limit,
        )

    async def list_transactions(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        transaction_type: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        sort_by: str = "transaction_date",
        sort_order: str = "desc",
        page: int = 1,
        limit: int = 20,
    ) -> TransactionListResponse | None:
        """List bank transactions for a client business.

        Note: Unlike financial summaries, transaction listings show ALL
        transactions unless date filters are explicitly provided. This allows
        the tabs to display all historical data while the quarter dropdown
        controls financial calculations.
        """
        # Verify connection belongs to tenant
        connection = await self.repository.get_connection(tenant_id, connection_id)
        if not connection:
            return None

        # No default date filtering - show all transactions unless dates specified
        offset = (page - 1) * limit
        transactions_data, total = await self.repository.list_transactions(
            connection_id=connection_id,
            transaction_type=transaction_type,
            from_date=from_date,
            to_date=to_date,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )

        transactions = [TransactionItem(**t) for t in transactions_data]

        return TransactionListResponse(
            transactions=transactions,
            total=total,
            page=page,
            limit=limit,
        )

    async def list_employees(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        status: str | None = None,
        page: int = 1,
        limit: int = 25,
    ) -> EmployeeListResponse | None:
        """List employees for a client business."""
        from app.modules.integrations.xero.models import XeroEmployeeStatus

        # Verify connection belongs to tenant
        connection = await self.repository.get_connection(tenant_id, connection_id)
        if not connection:
            return None

        # Parse status filter
        status_enum = None
        if status:
            status_upper = status.upper()
            if status_upper == "ACTIVE":
                status_enum = XeroEmployeeStatus.ACTIVE
            elif status_upper == "TERMINATED":
                status_enum = XeroEmployeeStatus.TERMINATED

        offset = (page - 1) * limit
        employees, total = await self.payroll_repo.get_employees(
            connection_id=connection_id,
            status=status_enum,
            limit=limit,
            offset=offset,
        )

        # Transform to response items
        employee_items = []
        for emp in employees:
            employee_items.append(
                EmployeeItem(
                    id=emp.id,
                    xero_employee_id=emp.xero_employee_id,
                    first_name=emp.first_name,
                    last_name=emp.last_name,
                    full_name=emp.full_name,
                    email=emp.email,
                    status=EmployeeStatus(emp.status.value),
                    start_date=emp.start_date,
                    termination_date=emp.termination_date,
                    job_title=emp.job_title,
                )
            )

        return EmployeeListResponse(
            employees=employee_items,
            total=total,
            page=page,
            limit=limit,
        )

    async def list_pay_runs(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        status: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> PayRunListResponse | None:
        """List pay runs for a client business."""
        from app.modules.integrations.xero.models import XeroPayRunStatus

        # Verify connection belongs to tenant
        connection = await self.repository.get_connection(tenant_id, connection_id)
        if not connection:
            return None

        # Default to current quarter if no dates specified
        if from_date is None and to_date is None:
            quarter_start, quarter_end, _, _, _ = get_quarter_dates()
            from_date = quarter_start
            to_date = quarter_end

        # Parse status filter
        status_enum = None
        if status:
            status_upper = status.upper()
            if status_upper == "POSTED":
                status_enum = XeroPayRunStatus.POSTED
            elif status_upper == "DRAFT":
                status_enum = XeroPayRunStatus.DRAFT

        offset = (page - 1) * limit
        pay_runs, total = await self.payroll_repo.get_pay_runs(
            connection_id=connection_id,
            status=status_enum,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )

        # Transform to response items
        pay_run_items = []
        for pr in pay_runs:
            pay_run_items.append(
                PayRunItem(
                    id=pr.id,
                    xero_pay_run_id=pr.xero_pay_run_id,
                    status=PayRunStatus(pr.pay_run_status.value),
                    period_start=pr.period_start,
                    period_end=pr.period_end,
                    payment_date=pr.payment_date,
                    total_wages=pr.total_wages,
                    total_tax=pr.total_tax,
                    total_super=pr.total_super,
                    total_net_pay=pr.total_net_pay,
                    employee_count=pr.employee_count,
                )
            )

        return PayRunListResponse(
            pay_runs=pay_run_items,
            total=total,
            page=page,
            limit=limit,
        )
