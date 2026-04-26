"""Service layer for clients module.

CRITICAL: In Clairo, "client" = XeroConnection = one business = one BAS to lodge.
"""

from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.clients.repository import (
    ClientExclusionRepository,
    ClientNoteHistoryRepository,
    ClientsRepository,
    PracticeClientRepository,
)
from app.modules.clients.schemas import (
    BulkAssignResponse,
    ClientDetailResponse,
    ClientExclusionCreate,
    ClientExclusionResponse,
    ClientExclusionReversedResponse,
    ContactItem,
    ContactListResponse,
    EmployeeItem,
    EmployeeListResponse,
    EmployeeStatus,
    FinancialSummaryResponse,
    InvoiceItem,
    InvoiceListResponse,
    NoteHistoryEntry,
    NoteHistoryResponse,
    PayRunItem,
    PayRunListResponse,
    PayRunStatus,
    PracticeClientCreate,
    PracticeClientResponse,
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

        # Lodgement-window default: Australian BAS is due 28 days after quarter end.
        # If today falls within 28 days of the previous quarter's end, accountants are
        # most likely preparing that lodgement — default to the just-completed quarter.
        # Quarter end months: Q1→Sep, Q2→Dec, Q3→Mar, Q4→Jun
        quarter_end_month = {1: 9, 2: 12, 3: 3, 4: 6}
        prev_q = 4 if current_q == 1 else current_q - 1
        prev_fy = current_fy - 1 if current_q == 1 else current_fy
        # Calculate the end of the previous quarter
        prev_end_month = quarter_end_month[prev_q]
        from calendar import monthrange
        prev_end_year = prev_fy - 1 if prev_q in [1, 2] else prev_fy
        prev_end_day = monthrange(prev_end_year, prev_end_month)[1]
        prev_quarter_end = date(prev_end_year, prev_end_month, prev_end_day)
        days_since_prev_end = (today - prev_quarter_end).days
        if 0 <= days_since_prev_end <= 28:
            # Within lodgement window — default to the just-completed quarter
            current_q = prev_q
            current_fy = prev_fy

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
        self.practice_client_repo = PracticeClientRepository(db)
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
            # The clients list now uses PracticeClient.id as the URL param.
            # Resolve it to the actual XeroConnection.id and retry.
            practice_client = await self.practice_client_repo.get_by_id(connection_id, tenant_id)
            if practice_client and practice_client.xero_connection_id:
                connection_id = practice_client.xero_connection_id
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


# =============================================================================
# Practice Client Service (Spec 058)
# =============================================================================


class PracticeClientService:
    """Service for practice client management.

    Handles team assignment, exclusion, notes, and manual client creation.
    """

    def __init__(
        self, db: AsyncSession, actor_id: UUID | None = None, tenant_id: UUID | None = None
    ):
        self.db = db
        self.actor_id = actor_id
        self.tenant_id = tenant_id
        self.client_repo = PracticeClientRepository(db)
        self.exclusion_repo = ClientExclusionRepository(db)
        self.note_history_repo = ClientNoteHistoryRepository(db)

    async def _audit(
        self,
        event_type: str,
        resource_id: UUID,
        old_values: dict | None = None,
        new_values: dict | None = None,
    ) -> None:
        """Emit an audit event. Non-fatal if audit service is unavailable."""
        try:
            from app.core.audit import AuditService

            audit = AuditService(self.db)
            await audit.log_event(
                event_type=event_type,
                event_category="data_modification",
                resource_type="practice_client",
                resource_id=resource_id,
                action="update",
                outcome="success",
                tenant_id=self.tenant_id,
                actor_id=self.actor_id,
                old_values=old_values,
                new_values=new_values,
            )
        except Exception:
            pass  # Audit is non-blocking

    # ─── Helper ────────────────────────────────────────────────────────────

    def _to_response(self, client: "PracticeClient") -> PracticeClientResponse:
        notes_editor_name = None
        if client.notes_updated_by and hasattr(client, "notes_editor") and client.notes_editor:
            notes_editor_name = (
                getattr(client.notes_editor, "display_name", None) or client.notes_editor.email
            )

        return PracticeClientResponse(
            id=client.id,
            tenant_id=client.tenant_id,
            name=client.name,
            abn=client.abn,
            accounting_software=client.accounting_software,
            xero_connection_id=client.xero_connection_id,
            has_xero_connection=client.xero_connection_id is not None,
            assigned_user_id=client.assigned_user_id,
            assigned_user_name=client.assigned_user_name,
            notes=client.notes,
            notes_preview=client.notes_preview,
            notes_updated_at=client.notes_updated_at,
            notes_updated_by_name=notes_editor_name,
            manual_status=client.manual_status,
            gst_reporting_basis=client.gst_reporting_basis,
            gst_basis_updated_at=client.gst_basis_updated_at,
            gst_basis_updated_by=client.gst_basis_updated_by,
            created_at=client.created_at,
        )

    # ─── Assignment (US1) ──────────────────────────────────────────────────

    async def assign_client(
        self,
        client_id: UUID,
        assigned_user_id: UUID | None,
        tenant_id: UUID,
    ) -> PracticeClientResponse:
        old_client = await self.client_repo.get_by_id(client_id, tenant_id)
        old_assignee = (
            str(old_client.assigned_user_id) if old_client and old_client.assigned_user_id else None
        )
        client = await self.client_repo.update_assignment(
            client_id=client_id,
            tenant_id=tenant_id,
            assigned_user_id=assigned_user_id,
        )
        if client is None:
            raise NotFoundError(resource_type="PracticeClient", message="Client not found")
        await self._audit(
            "client.assigned",
            client_id,
            {"assigned_user_id": old_assignee},
            {"assigned_user_id": str(assigned_user_id) if assigned_user_id else None},
        )
        return self._to_response(client)

    async def bulk_assign_clients(
        self,
        client_ids: list[UUID],
        assigned_user_id: UUID | None,
        tenant_id: UUID,
    ) -> BulkAssignResponse:
        updated_count = await self.client_repo.bulk_update_assignment(
            client_ids=client_ids,
            assigned_user_id=assigned_user_id,
            tenant_id=tenant_id,
        )
        # Fetch updated clients for response
        clients = []
        for cid in client_ids:
            c = await self.client_repo.get_by_id(cid, tenant_id)
            if c:
                clients.append(self._to_response(c))
        return BulkAssignResponse(updated_count=updated_count, clients=clients)

    # ─── Exclusion (US2) ───────────────────────────────────────────────────

    async def exclude_client(
        self,
        client_id: UUID,
        data: ClientExclusionCreate,
        tenant_id: UUID,
        excluded_by: UUID,
    ) -> ClientExclusionResponse:
        # Check client exists
        client = await self.client_repo.get_by_id(client_id, tenant_id)
        if client is None:
            raise NotFoundError(resource_type="PracticeClient", message="Client not found")

        # Check not already excluded
        existing = await self.exclusion_repo.get_active_exclusion(
            client_id=client_id, quarter=data.quarter, fy_year=data.fy_year
        )
        if existing:
            raise ConflictError(
                message="Client is already excluded for this quarter",
                resource_type="ClientQuarterExclusion",
                conflict_field="client_id",
            )

        exclusion = await self.exclusion_repo.create_exclusion(
            tenant_id=tenant_id,
            client_id=client_id,
            quarter=data.quarter,
            fy_year=data.fy_year,
            excluded_by=excluded_by,
            reason=data.reason,
            reason_detail=data.reason_detail,
        )

        user_name = None
        if exclusion.excluded_by_user:
            user_name = (
                getattr(exclusion.excluded_by_user, "display_name", None)
                or exclusion.excluded_by_user.email
            )

        await self._audit(
            "client.exclusion.created",
            client_id,
            new_values={"quarter": data.quarter, "fy_year": data.fy_year, "reason": data.reason},
        )

        return ClientExclusionResponse(
            id=exclusion.id,
            client_id=exclusion.client_id,
            quarter=exclusion.quarter,
            fy_year=exclusion.fy_year,
            reason=exclusion.reason,
            reason_detail=exclusion.reason_detail,
            excluded_by_name=user_name,
            excluded_at=exclusion.excluded_at,
        )

    async def reverse_exclusion(
        self,
        client_id: UUID,
        exclusion_id: UUID,
        tenant_id: UUID,
        reversed_by: UUID,
    ) -> ClientExclusionReversedResponse:
        exclusion = await self.exclusion_repo.reverse_exclusion(
            exclusion_id=exclusion_id,
            tenant_id=tenant_id,
            reversed_by=reversed_by,
        )
        if exclusion is None:
            raise NotFoundError(
                resource_type="ClientQuarterExclusion", message="Exclusion not found"
            )

        user_name = None
        if exclusion.reversed_by_user:
            user_name = (
                getattr(exclusion.reversed_by_user, "display_name", None)
                or exclusion.reversed_by_user.email
            )

        await self._audit(
            "client.exclusion.reversed", client_id, new_values={"exclusion_id": str(exclusion_id)}
        )

        return ClientExclusionReversedResponse(
            id=exclusion.id,
            reversed_at=exclusion.reversed_at,  # type: ignore[arg-type]
            reversed_by_name=user_name,
        )

    # ─── Notes (US3) ──────────────────────────────────────────────────────

    async def update_notes(
        self,
        client_id: UUID,
        notes: str,
        tenant_id: UUID,
        updated_by: UUID,
    ) -> PracticeClientResponse:
        client = await self.client_repo.get_by_id(client_id, tenant_id)
        if client is None:
            raise NotFoundError(resource_type="PracticeClient", message="Client not found")

        # Save history entry before updating
        if client.notes:
            await self.note_history_repo.create_entry(
                tenant_id=tenant_id,
                client_id=client_id,
                note_text=client.notes,
                edited_by=updated_by,
            )

        client = await self.client_repo.update_notes(
            client_id=client_id,
            tenant_id=tenant_id,
            notes=notes,
            updated_by=updated_by,
        )
        await self._audit(
            "client.notes.updated", client_id, new_values={"notes_length": len(notes)}
        )
        return self._to_response(client)  # type: ignore[arg-type]

    async def get_note_history(
        self,
        client_id: UUID,
        tenant_id: UUID,
    ) -> NoteHistoryResponse:
        entries = await self.note_history_repo.get_history(client_id, tenant_id)
        history = []
        for entry in entries:
            editor_name = None
            if entry.editor:
                editor_name = getattr(entry.editor, "display_name", None) or entry.editor.email
            history.append(
                NoteHistoryEntry(
                    note_text=entry.note_text,
                    edited_by_name=editor_name,
                    edited_at=entry.edited_at,
                )
            )
        return NoteHistoryResponse(history=history)

    # ─── Manual Client (US4) ──────────────────────────────────────────────

    async def create_manual_client(
        self,
        data: PracticeClientCreate,
        tenant_id: UUID,
    ) -> PracticeClientResponse:
        client = await self.client_repo.create(
            tenant_id=tenant_id,
            name=data.name,
            abn=data.abn,
            accounting_software=data.accounting_software,
            assigned_user_id=data.assigned_user_id,
            notes=data.notes,
        )
        await self._audit(
            "client.created_manual",
            client.id,
            new_values={"name": data.name, "software": data.accounting_software},
        )
        return self._to_response(client)

    async def update_manual_status(
        self,
        client_id: UUID,
        status: str,
        tenant_id: UUID,
    ) -> PracticeClientResponse:
        client = await self.client_repo.update_manual_status(
            client_id=client_id,
            tenant_id=tenant_id,
            status=status,
        )
        if client is None:
            raise NotFoundError(resource_type="PracticeClient", message="Client not found")
        return self._to_response(client)

    async def set_gst_basis(
        self,
        client_id: UUID,
        basis: str,
        actor_id: UUID,
        tenant_id: UUID,
    ) -> PracticeClientResponse:
        """Set or update the GST reporting basis for a client (Spec 062).

        Emits BAS_GST_BASIS_SET on first save, BAS_GST_BASIS_CHANGED on subsequent
        changes. If a lodged BAS session exists for this client, also emits
        BAS_GST_BASIS_CHANGED_POST_LODGEMENT.
        """
        from app.modules.bas.audit_events import (
            BAS_GST_BASIS_CHANGED,
            BAS_GST_BASIS_CHANGED_POST_LODGEMENT,
            BAS_GST_BASIS_SET,
        )

        client = await self.client_repo.get_by_id(client_id, tenant_id)
        if client is None:
            raise NotFoundError(resource_type="PracticeClient", message="Client not found")

        old_basis = client.gst_reporting_basis
        event_type = BAS_GST_BASIS_SET if old_basis is None else BAS_GST_BASIS_CHANGED

        updated = await self.client_repo.update_gst_basis(
            client_id=client_id,
            tenant_id=tenant_id,
            basis=basis,
            updated_by=actor_id,
        )
        if updated is None:
            raise NotFoundError(resource_type="PracticeClient", message="Client not found")

        await self._audit(
            event_type,
            client_id,
            old_values={"gst_reporting_basis": old_basis},
            new_values={"gst_reporting_basis": basis},
        )

        # Check for lodged BAS sessions — emit post-lodgement event if any exist
        if old_basis is not None and old_basis != basis:
            try:
                from sqlalchemy import select

                from app.modules.bas.models import BASPeriod, BASSession

                # Find lodged sessions for this client's Xero connection
                if updated.xero_connection_id:
                    result = await self.db.execute(
                        select(BASSession)
                        .join(BASPeriod, BASSession.period_id == BASPeriod.id)
                        .where(
                            BASPeriod.connection_id == updated.xero_connection_id,
                            BASSession.lodged_at.isnot(None),
                        )
                        .limit(1)
                    )
                    if result.scalar_one_or_none() is not None:
                        await self._audit(
                            BAS_GST_BASIS_CHANGED_POST_LODGEMENT,
                            client_id,
                            old_values={"gst_reporting_basis": old_basis},
                            new_values={"gst_reporting_basis": basis},
                        )
            except Exception:
                pass  # Non-blocking

        return self._to_response(updated)
