"""Repository for Xero payroll data operations.

Handles database operations for:
- XeroEmployee: Employee records synced from Xero Payroll
- XeroPayRun: Pay run records with PAYG withholding data
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.xero.models import (
    XeroEmployee,
    XeroEmployeeStatus,
    XeroPayRun,
    XeroPayRunStatus,
)


class XeroPayrollRepository:
    """Repository for Xero payroll data operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # =========================================================================
    # Employee Operations
    # =========================================================================

    async def upsert_employee(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        xero_employee_id: str,
        first_name: str | None,
        last_name: str | None,
        email: str | None,
        status: XeroEmployeeStatus,
        start_date: datetime | None,
        termination_date: datetime | None,
        job_title: str | None,
        xero_updated_at: datetime | None,
    ) -> XeroEmployee:
        """Upsert an employee record."""
        # Check for existing
        stmt = select(XeroEmployee).where(
            XeroEmployee.connection_id == connection_id,
            XeroEmployee.xero_employee_id == xero_employee_id,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            existing.first_name = first_name
            existing.last_name = last_name
            existing.email = email
            existing.status = status
            existing.start_date = start_date
            existing.termination_date = termination_date
            existing.job_title = job_title
            existing.xero_updated_at = xero_updated_at
            await self.session.flush()
            return existing

        # Create new
        employee = XeroEmployee(
            tenant_id=tenant_id,
            connection_id=connection_id,
            xero_employee_id=xero_employee_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            status=status,
            start_date=start_date,
            termination_date=termination_date,
            job_title=job_title,
            xero_updated_at=xero_updated_at,
        )
        self.session.add(employee)
        await self.session.flush()
        return employee

    async def get_employees(
        self,
        connection_id: UUID,
        status: XeroEmployeeStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[XeroEmployee], int]:
        """Get employees for a connection with optional status filter."""
        # Base query
        base_query = select(XeroEmployee).where(XeroEmployee.connection_id == connection_id)

        if status:
            base_query = base_query.where(XeroEmployee.status == status)

        # Count query
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        # Data query with pagination
        data_query = (
            base_query.order_by(XeroEmployee.last_name, XeroEmployee.first_name)
            .offset(offset)
            .limit(limit)
        )

        result = await self.session.execute(data_query)
        employees = list(result.scalars().all())

        return employees, total

    async def get_employee_count(self, connection_id: UUID) -> int:
        """Get count of active employees for a connection."""
        stmt = select(func.count()).where(
            XeroEmployee.connection_id == connection_id,
            XeroEmployee.status == XeroEmployeeStatus.ACTIVE,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # =========================================================================
    # Pay Run Operations
    # =========================================================================

    async def upsert_pay_run(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        xero_pay_run_id: str,
        payroll_calendar_id: str | None,
        pay_run_status: XeroPayRunStatus,
        period_start: datetime,
        period_end: datetime,
        payment_date: datetime,
        total_wages: Decimal,
        total_tax: Decimal,
        total_super: Decimal,
        total_deductions: Decimal,
        total_reimbursements: Decimal,
        total_net_pay: Decimal,
        employee_count: int,
        xero_updated_at: datetime | None,
    ) -> XeroPayRun:
        """Upsert a pay run record."""
        # Check for existing
        stmt = select(XeroPayRun).where(
            XeroPayRun.connection_id == connection_id,
            XeroPayRun.xero_pay_run_id == xero_pay_run_id,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            existing.payroll_calendar_id = payroll_calendar_id
            existing.pay_run_status = pay_run_status
            existing.period_start = period_start
            existing.period_end = period_end
            existing.payment_date = payment_date
            existing.total_wages = total_wages
            existing.total_tax = total_tax
            existing.total_super = total_super
            existing.total_deductions = total_deductions
            existing.total_reimbursements = total_reimbursements
            existing.total_net_pay = total_net_pay
            existing.employee_count = employee_count
            existing.xero_updated_at = xero_updated_at
            await self.session.flush()
            return existing

        # Create new
        pay_run = XeroPayRun(
            tenant_id=tenant_id,
            connection_id=connection_id,
            xero_pay_run_id=xero_pay_run_id,
            payroll_calendar_id=payroll_calendar_id,
            pay_run_status=pay_run_status,
            period_start=period_start,
            period_end=period_end,
            payment_date=payment_date,
            total_wages=total_wages,
            total_tax=total_tax,
            total_super=total_super,
            total_deductions=total_deductions,
            total_reimbursements=total_reimbursements,
            total_net_pay=total_net_pay,
            employee_count=employee_count,
            xero_updated_at=xero_updated_at,
        )
        self.session.add(pay_run)
        await self.session.flush()
        return pay_run

    async def get_pay_runs(
        self,
        connection_id: UUID,
        status: XeroPayRunStatus | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[XeroPayRun], int]:
        """Get pay runs for a connection with optional filters."""
        # Base query
        base_query = select(XeroPayRun).where(XeroPayRun.connection_id == connection_id)

        if status:
            base_query = base_query.where(XeroPayRun.pay_run_status == status)

        if from_date:
            base_query = base_query.where(XeroPayRun.payment_date >= from_date)

        if to_date:
            base_query = base_query.where(XeroPayRun.payment_date <= to_date)

        # Count query
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        # Data query with pagination
        data_query = base_query.order_by(XeroPayRun.payment_date.desc()).offset(offset).limit(limit)

        result = await self.session.execute(data_query)
        pay_runs = list(result.scalars().all())

        return pay_runs, total

    async def get_payroll_summary(
        self,
        connection_id: UUID,
        from_date: date,
        to_date: date,
    ) -> dict:
        """Get aggregated payroll data for a date range (for BAS).

        Returns totals for:
        - W1: Total wages (sum of total_wages from posted pay runs)
        - W2/4: Total tax withheld (sum of total_tax from posted pay runs)
        - Total super
        - Pay run count
        """
        stmt = select(
            func.coalesce(func.sum(XeroPayRun.total_wages), 0).label("total_wages"),
            func.coalesce(func.sum(XeroPayRun.total_tax), 0).label("total_tax"),
            func.coalesce(func.sum(XeroPayRun.total_super), 0).label("total_super"),
            func.count().label("pay_run_count"),
        ).where(
            XeroPayRun.connection_id == connection_id,
            XeroPayRun.pay_run_status == XeroPayRunStatus.POSTED,
            XeroPayRun.payment_date >= from_date,
            XeroPayRun.payment_date <= to_date,
        )

        result = await self.session.execute(stmt)
        row = result.one()

        return {
            "total_wages": Decimal(str(row.total_wages)),
            "total_tax_withheld": Decimal(str(row.total_tax)),
            "total_super": Decimal(str(row.total_super)),
            "pay_run_count": row.pay_run_count,
        }
