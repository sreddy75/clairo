"""Service for syncing payroll data from Xero.

Handles:
- Employee sync from Xero Payroll API
- Pay run sync with PAYG withholding data
- Payroll summary calculations for BAS
"""

import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.modules.integrations.xero.client import XeroClient
from app.modules.integrations.xero.connection_service import XeroConnectionService
from app.modules.integrations.xero.encryption import TokenEncryption
from app.modules.integrations.xero.models import (
    XeroConnection,
    XeroConnectionStatus,
    XeroEmployeeStatus,
    XeroPayRunStatus,
)
from app.modules.integrations.xero.payroll_repository import XeroPayrollRepository
from app.modules.integrations.xero.repository import XeroConnectionRepository
from app.modules.integrations.xero.schemas import XeroConnectionUpdate

logger = logging.getLogger(__name__)


class XeroPayrollSyncError(Exception):
    """Error during payroll sync."""

    pass


class XeroPayrollService:
    """Service for syncing and querying Xero payroll data."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.encryption = TokenEncryption(settings.token_encryption.key.get_secret_value())
        self.connection_repo = XeroConnectionRepository(session)
        self.payroll_repo = XeroPayrollRepository(session)

    async def sync_payroll(
        self,
        connection_id: UUID,
    ) -> dict[str, Any]:
        """Sync all payroll data for a connection.

        Args:
            connection_id: The connection to sync.

        Returns:
            Dict with sync results (employees_synced, pay_runs_synced, etc.)

        Raises:
            XeroPayrollSyncError: If sync fails.
        """
        # Get connection
        connection = await self.connection_repo.get_by_id(connection_id)
        if not connection:
            raise XeroPayrollSyncError(f"Connection {connection_id} not found")

        if connection.status == XeroConnectionStatus.NEEDS_REAUTH:
            from app.modules.integrations.xero.exceptions import XeroAuthRequiredError
            raise XeroAuthRequiredError(connection_id, org_name=connection.organization_name or "")

        if connection.status != XeroConnectionStatus.ACTIVE:
            raise XeroPayrollSyncError(f"Connection {connection_id} is not active")

        if not connection.has_payroll_access:
            logger.info(f"Connection {connection_id} does not have payroll access, skipping")
            return {
                "status": "skipped",
                "reason": "no_payroll_access",
                "employees_synced": 0,
                "pay_runs_synced": 0,
            }

        # Get access token via ensure_valid_token (handles expiry + grant-scoped lock)
        conn_service = XeroConnectionService(self.session, self.settings)
        access_token = await conn_service.ensure_valid_token(connection_id)

        # Sync employees
        employees_synced = await self._sync_employees(connection, access_token)

        # Sync pay runs
        pay_runs_synced = await self._sync_pay_runs(connection, access_token)

        # Update sync timestamps
        await self.connection_repo.update(
            connection_id=connection_id,
            data=XeroConnectionUpdate(
                last_payroll_sync_at=datetime.now(UTC),
                last_employees_sync_at=datetime.now(UTC),
            ),
        )

        await self.session.commit()

        return {
            "status": "complete",
            "employees_synced": employees_synced,
            "pay_runs_synced": pay_runs_synced,
        }

    async def _sync_employees(
        self,
        connection: XeroConnection,
        access_token: str,
    ) -> int:
        """Sync employees from Xero Payroll API."""
        total_synced = 0
        page = 1

        async with XeroClient(self.settings.xero) as client:
            while True:
                try:
                    employees, has_more, _ = await client.get_employees(
                        access_token=access_token,
                        tenant_id=connection.xero_tenant_id,
                        page=page,
                        modified_since=connection.last_employees_sync_at,
                    )
                except Exception as e:
                    logger.error(f"Error fetching employees page {page}: {e}")
                    break

                for emp_data in employees:
                    await self._upsert_employee(connection, emp_data)
                    total_synced += 1

                if not has_more:
                    break

                page += 1

        logger.info(f"Synced {total_synced} employees for connection {connection.id}")
        return total_synced

    async def _upsert_employee(
        self,
        connection: XeroConnection,
        data: dict[str, Any],
    ) -> None:
        """Transform and upsert a single employee."""
        # Xero Payroll AU API uses camelCase field names
        # Parse status
        status_str = data.get("status", data.get("Status", "ACTIVE")).upper()
        status = (
            XeroEmployeeStatus.TERMINATED
            if status_str == "TERMINATED"
            else XeroEmployeeStatus.ACTIVE
        )

        # Parse dates (handle both camelCase and TitleCase)
        start_date = self._parse_xero_date(data.get("startDate") or data.get("StartDate"))
        termination_date = self._parse_xero_date(data.get("endDate") or data.get("TerminationDate"))
        updated_at = self._parse_xero_datetime(
            data.get("updatedDateUTC") or data.get("UpdatedDateUTC")
        )

        await self.payroll_repo.upsert_employee(
            tenant_id=connection.tenant_id,
            connection_id=connection.id,
            xero_employee_id=data.get("employeeID") or data.get("EmployeeID", ""),
            first_name=data.get("firstName") or data.get("FirstName"),
            last_name=data.get("lastName") or data.get("LastName"),
            email=data.get("email") or data.get("Email"),
            status=status,
            start_date=start_date,
            termination_date=termination_date,
            job_title=data.get("jobTitle") or data.get("JobTitle"),
            xero_updated_at=updated_at,
        )

    async def _sync_pay_runs(
        self,
        connection: XeroConnection,
        access_token: str,
    ) -> int:
        """Sync pay runs from Xero Payroll API."""
        total_synced = 0
        page = 1

        async with XeroClient(self.settings.xero) as client:
            while True:
                try:
                    # Fetch pay runs (both draft and posted for visibility)
                    pay_runs, has_more, _ = await client.get_pay_runs(
                        access_token=access_token,
                        tenant_id=connection.xero_tenant_id,
                        page=page,
                    )
                except Exception as e:
                    logger.error(f"Error fetching pay runs page {page}: {e}")
                    break

                for pr_data in pay_runs:
                    # For each pay run, get details to get totals
                    try:
                        detailed_pr, _ = await client.get_pay_run_details(
                            access_token=access_token,
                            tenant_id=connection.xero_tenant_id,
                            pay_run_id=pr_data.get("PayRunID", ""),
                        )
                        if detailed_pr:
                            await self._upsert_pay_run(connection, detailed_pr)
                            total_synced += 1
                    except Exception as e:
                        logger.error(f"Error fetching pay run details: {e}")
                        continue

                if not has_more:
                    break

                page += 1

        logger.info(f"Synced {total_synced} pay runs for connection {connection.id}")
        return total_synced

    async def _upsert_pay_run(
        self,
        connection: XeroConnection,
        data: dict[str, Any],
    ) -> None:
        """Transform and upsert a single pay run."""
        # Parse status
        status_str = data.get("PayRunStatus", "DRAFT").upper()
        status = XeroPayRunStatus.POSTED if status_str == "POSTED" else XeroPayRunStatus.DRAFT

        # Parse dates
        period_start = self._parse_xero_date(data.get("PayRunPeriodStartDate"))
        period_end = self._parse_xero_date(data.get("PayRunPeriodEndDate"))
        payment_date = self._parse_xero_date(data.get("PaymentDate"))
        updated_at = self._parse_xero_datetime(data.get("UpdatedDateUTC"))

        if not period_start or not period_end or not payment_date:
            logger.warning(f"Pay run missing required dates: {data.get('PayRunID')}")
            return

        # Calculate totals from payslips
        payslips = data.get("Payslips", [])
        total_wages = Decimal("0")
        total_tax = Decimal("0")
        total_super = Decimal("0")
        total_deductions = Decimal("0")
        total_reimbursements = Decimal("0")
        total_net_pay = Decimal("0")

        for slip in payslips:
            total_wages += Decimal(str(slip.get("Wages", 0)))
            total_tax += Decimal(str(slip.get("Tax", 0)))
            total_super += Decimal(str(slip.get("Super", 0)))
            total_deductions += Decimal(str(slip.get("Deductions", 0)))
            total_reimbursements += Decimal(str(slip.get("Reimbursements", 0)))
            total_net_pay += Decimal(str(slip.get("NetPay", 0)))

        await self.payroll_repo.upsert_pay_run(
            tenant_id=connection.tenant_id,
            connection_id=connection.id,
            xero_pay_run_id=data.get("PayRunID", ""),
            payroll_calendar_id=data.get("PayrollCalendarID"),
            pay_run_status=status,
            period_start=period_start,
            period_end=period_end,
            payment_date=payment_date,
            total_wages=total_wages,
            total_tax=total_tax,
            total_super=total_super,
            total_deductions=total_deductions,
            total_reimbursements=total_reimbursements,
            total_net_pay=total_net_pay,
            employee_count=len(payslips),
            xero_updated_at=updated_at,
        )

    def _parse_xero_date(self, date_str: str | None) -> datetime | None:
        """Parse Xero date string to datetime."""
        if not date_str:
            return None

        # Xero dates are in format "/Date(timestamp)/" or ISO format
        if date_str.startswith("/Date("):
            # Extract timestamp
            try:
                timestamp_str = date_str.replace("/Date(", "").replace(")/", "")
                # Handle timezone offset if present
                if "+" in timestamp_str:
                    timestamp_str = timestamp_str.split("+")[0]
                elif "-" in timestamp_str and timestamp_str.count("-") > 1:
                    timestamp_str = timestamp_str.rsplit("-", 1)[0]
                timestamp = int(timestamp_str) / 1000
                return datetime.fromtimestamp(timestamp, tz=UTC)
            except (ValueError, TypeError):
                return None

        # Try ISO format
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    def _parse_xero_datetime(self, dt_str: str | None) -> datetime | None:
        """Parse Xero datetime string."""
        return self._parse_xero_date(dt_str)

    # =========================================================================
    # Query Methods
    # =========================================================================

    async def get_payroll_summary(
        self,
        connection_id: UUID,
        from_date: date,
        to_date: date,
    ) -> dict[str, Any]:
        """Get payroll summary for a date range.

        Returns aggregated data for BAS fields:
        - W1: Total wages
        - W2/4: Total tax withheld
        - Total super
        - Pay run count
        - Employee count
        """
        # Get connection to check payroll access
        connection = await self.connection_repo.get_by_id(connection_id)
        if not connection:
            return self._empty_payroll_summary()

        if not connection.has_payroll_access:
            return self._empty_payroll_summary()

        # Get aggregated data from pay runs
        summary = await self.payroll_repo.get_payroll_summary(
            connection_id=connection_id,
            from_date=from_date,
            to_date=to_date,
        )

        # Get employee count
        employee_count = await self.payroll_repo.get_employee_count(connection_id)

        return {
            "has_payroll": True,
            "total_wages": summary["total_wages"],
            "total_tax_withheld": summary["total_tax_withheld"],
            "total_super": summary["total_super"],
            "pay_run_count": summary["pay_run_count"],
            "employee_count": employee_count,
            "last_payroll_sync_at": connection.last_payroll_sync_at,
        }

    def _empty_payroll_summary(self) -> dict[str, Any]:
        """Return empty payroll summary for connections without payroll."""
        return {
            "has_payroll": False,
            "total_wages": Decimal("0"),
            "total_tax_withheld": Decimal("0"),
            "total_super": Decimal("0"),
            "pay_run_count": 0,
            "employee_count": 0,
            "last_payroll_sync_at": None,
        }

    async def get_employees(
        self,
        connection_id: UUID,
        status: str | None = None,
        page: int = 1,
        limit: int = 25,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get employees for a connection."""
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

        # Transform to dict
        result = []
        for emp in employees:
            result.append(
                {
                    "id": str(emp.id),
                    "xero_employee_id": emp.xero_employee_id,
                    "first_name": emp.first_name,
                    "last_name": emp.last_name,
                    "full_name": emp.full_name,
                    "email": emp.email,
                    "status": emp.status.value,
                    "start_date": emp.start_date.isoformat() if emp.start_date else None,
                    "termination_date": emp.termination_date.isoformat()
                    if emp.termination_date
                    else None,
                    "job_title": emp.job_title,
                }
            )

        return result, total

    async def get_pay_runs(
        self,
        connection_id: UUID,
        status: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get pay runs for a connection."""
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

        # Transform to dict
        result = []
        for pr in pay_runs:
            result.append(
                {
                    "id": str(pr.id),
                    "xero_pay_run_id": pr.xero_pay_run_id,
                    "status": pr.pay_run_status.value,
                    "period_start": pr.period_start.isoformat() if pr.period_start else None,
                    "period_end": pr.period_end.isoformat() if pr.period_end else None,
                    "payment_date": pr.payment_date.isoformat() if pr.payment_date else None,
                    "total_wages": float(pr.total_wages),
                    "total_tax": float(pr.total_tax),
                    "total_super": float(pr.total_super),
                    "total_net_pay": float(pr.total_net_pay),
                    "employee_count": pr.employee_count,
                }
            )

        return result, total
