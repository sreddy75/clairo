"""Xero reports service — fetches, caches, and transforms P&L, Balance Sheet, Aged AR/AP, Trial Balance, and Bank Summary."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.modules.integrations.xero.client import XeroClient
from app.modules.integrations.xero.encryption import TokenEncryption
from app.modules.integrations.xero.models import XeroConnection, XeroConnectionStatus
from app.modules.integrations.xero.repository import XeroConnectionRepository
from app.modules.integrations.xero.transformers import (
    AgedPayablesTransformer,
    AgedReceivablesTransformer,
    BalanceSheetTransformer,
    BankSummaryTransformer,
    ProfitAndLossTransformer,
    TrialBalanceTransformer,
    XeroReportTransformer,
)

logger = logging.getLogger(__name__)


class XeroReportService:
    """Service for managing Xero financial reports.

    Handles fetching, caching, and transforming reports from Xero's
    Reports API including Profit & Loss, Balance Sheet, Aged Receivables,
    Aged Payables, Trial Balance, Bank Summary, and Budget Summary.
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        """Initialize XeroReportService.

        Args:
            session: Database session.
            settings: Application settings.
        """
        from app.core.audit import AuditService
        from app.modules.integrations.xero.repository import (
            XeroReportRepository,
            XeroReportSyncJobRepository,
        )

        self.session = session
        self.settings = settings
        self.report_repo = XeroReportRepository(session)
        self.sync_job_repo = XeroReportSyncJobRepository(session)
        self.connection_repo = XeroConnectionRepository(session)
        self.encryption = TokenEncryption(settings.token_encryption.key.get_secret_value())
        self.audit_service = AuditService(session)
        self.logger = logging.getLogger(__name__)

    async def _get_connection_and_token(self, connection_id: UUID) -> tuple[XeroConnection, str]:
        """Get connection and ensure valid access token.

        Args:
            connection_id: The connection ID.

        Returns:
            Tuple of (connection, decrypted_access_token).

        Raises:
            XeroConnectionNotFoundExc: If connection not found.
            XeroConnectionInactiveError: If connection not active.
        """
        connection = await self.connection_repo.get_by_id(connection_id)
        if connection is None:
            raise XeroConnectionNotFoundExc(connection_id)

        if connection.status != XeroConnectionStatus.ACTIVE:
            raise XeroConnectionInactiveError(str(connection_id))

        # Refresh if needed
        if connection.needs_refresh:
            self.logger.info(
                f"Token needs refresh for connection {connection_id}, "
                f"expires_at={connection.token_expires_at}"
            )
            conn_service = XeroConnectionService(self.session, self.settings)
            connection = await conn_service.refresh_tokens(connection_id)
            self.logger.info(f"Token refreshed successfully for connection {connection_id}")

        access_token = self.encryption.decrypt(connection.access_token)
        return connection, access_token

    async def get_report(
        self,
        connection_id: UUID,
        report_type: str,
        period_key: str,
        force_refresh: bool = False,
        to_date_override: str | None = None,
    ) -> dict[str, Any]:
        """Get a report, from cache if available or fetch from Xero.

        Args:
            connection_id: The Xero connection ID.
            report_type: Type of report (e.g., 'profit_and_loss').
            period_key: Period identifier (e.g., '2025-FY', '2025-12').
            force_refresh: If True, bypass cache and fetch fresh data.
            to_date_override: Optional ISO date string to cap the report
                to_date (e.g. reconciliation date). When set, the cache
                key is adjusted so different caps get separate entries.

        Returns:
            Report data dict with summary and rows.

        Raises:
            XeroConnectionNotFoundError: If connection not found.
            XeroConnectionInactiveError: If connection is inactive.
        """
        from app.modules.integrations.xero.models import XeroReportType

        # Convert string to enum
        try:
            report_type_enum = XeroReportType(report_type)
        except ValueError as e:
            raise ValueError(f"Invalid report type: {report_type}") from e

        # Handle aged reports specially - compute from synced invoice data
        # Xero's aged report APIs require contactId which isn't practical
        if report_type_enum == XeroReportType.AGED_RECEIVABLES:
            self.logger.info(
                "Computing aged receivables from synced invoices",
                extra={
                    "connection_id": str(connection_id),
                    "report_type": report_type,
                    "period_key": period_key,
                },
            )
            await self._log_report_access(
                connection_id=connection_id,
                report_type=report_type,
                period_key=period_key,
                source="computed",
            )
            return await self._compute_aged_receivables(connection_id)

        if report_type_enum == XeroReportType.AGED_PAYABLES:
            self.logger.info(
                "Computing aged payables from synced bills",
                extra={
                    "connection_id": str(connection_id),
                    "report_type": report_type,
                    "period_key": period_key,
                },
            )
            await self._log_report_access(
                connection_id=connection_id,
                report_type=report_type,
                period_key=period_key,
                source="computed",
            )
            return await self._compute_aged_payables(connection_id)

        # When to_date is overridden, use a composite cache key so
        # different caps (e.g. different reconciliation dates) get
        # separate cache entries.
        cache_period_key = (
            f"{period_key}__to_{to_date_override}" if to_date_override else period_key
        )

        # Check cache first (unless forcing refresh)
        if not force_refresh:
            cached = await self.report_repo.get_cached_report(
                connection_id=connection_id,
                report_type=report_type_enum,
                period_key=cache_period_key,
                include_expired=False,
            )
            if cached:
                self.logger.info(
                    "Returning cached report",
                    extra={
                        "connection_id": str(connection_id),
                        "report_type": report_type,
                        "period_key": cache_period_key,
                    },
                )
                # Log audit event for report access
                await self._log_report_access(
                    connection_id=connection_id,
                    report_type=report_type,
                    period_key=cache_period_key,
                    source="cache",
                )
                return self._report_to_dict(cached)

        # Fetch from Xero
        return await self._fetch_and_cache_report(
            connection_id=connection_id,
            report_type=report_type_enum,
            period_key=period_key,
            to_date_override=to_date_override,
            cache_period_key=cache_period_key,
        )

    async def list_report_statuses(
        self,
        connection_id: UUID,
    ) -> list[dict[str, Any]]:
        """List available report types with their sync status.

        Args:
            connection_id: The Xero connection ID.

        Returns:
            List of report status dicts.
        """
        from app.modules.integrations.xero.models import XeroReportType

        # Get connection to verify it exists and is active
        connection = await self.connection_repo.get_by_id(connection_id)
        if not connection:
            raise XeroConnectionNotFoundExc(connection_id)

        statuses = []

        for report_type in XeroReportType:
            # Get any active sync job for this report type
            active_job = await self.sync_job_repo.get_active_for_connection(
                connection_id=connection_id,
                report_type=report_type,
            )

            # Get cached reports for this type
            reports, _ = await self.report_repo.get_reports_by_connection(
                connection_id=connection_id,
                report_type=report_type,
                include_expired=True,
                limit=10,
            )

            # Find most recent valid cached report
            last_synced_at = None
            is_stale = True
            periods_available = []

            for report in reports:
                periods_available.append(report.period_key)
                if report.fetched_at:
                    if last_synced_at is None or report.fetched_at > last_synced_at:
                        last_synced_at = report.fetched_at
                if report.cache_expires_at and report.cache_expires_at > datetime.now(UTC):
                    is_stale = False

            statuses.append(
                {
                    "report_type": report_type.value,
                    "display_name": XeroReportTransformer.get_display_name(report_type.value),
                    "is_available": True,
                    "last_synced_at": last_synced_at,
                    "is_stale": is_stale and len(reports) > 0,
                    "sync_status": active_job.status.value if active_job else None,
                    "periods_available": periods_available,
                }
            )

        return statuses

    async def refresh_report(
        self,
        connection_id: UUID,
        report_type: str,
        period_key: str,
        user_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Request a refresh of a specific report.

        Enforces throttling (max 1 refresh per 5 minutes per report type).

        Args:
            connection_id: The Xero connection ID.
            report_type: Type of report to refresh.
            period_key: Period to refresh.
            user_id: User requesting the refresh.

        Returns:
            Report data if immediately available, or pending status.

        Raises:
            XeroRateLimitExceededError: If refresh throttle exceeded.
        """
        from app.modules.integrations.xero.models import XeroReportType

        try:
            report_type_enum = XeroReportType(report_type)
        except ValueError as e:
            raise ValueError(f"Invalid report type: {report_type}") from e

        # Handle aged reports specially - compute from synced invoice data
        # Xero's aged report APIs require contactId which isn't practical
        if report_type_enum == XeroReportType.AGED_RECEIVABLES:
            self.logger.info(
                "Computing aged receivables from synced invoices (refresh)",
                extra={
                    "connection_id": str(connection_id),
                    "report_type": report_type,
                },
            )
            return await self._compute_aged_receivables(connection_id)

        if report_type_enum == XeroReportType.AGED_PAYABLES:
            self.logger.info(
                "Computing aged payables from synced bills (refresh)",
                extra={
                    "connection_id": str(connection_id),
                    "report_type": report_type,
                },
            )
            return await self._compute_aged_payables(connection_id)

        # Check throttle (1 minute between refresh requests)
        recent_job = await self.sync_job_repo.get_recent_by_report_type(
            connection_id=connection_id,
            report_type=report_type_enum,
            minutes=1,
        )

        if recent_job:
            seconds_remaining = 60 - int(
                (datetime.now(UTC) - recent_job.created_at).total_seconds()
            )
            if seconds_remaining > 0:
                raise XeroRateLimitExceededError(
                    wait_seconds=seconds_remaining,
                    limit_type="refresh",
                )

        # Fetch fresh data
        return await self._fetch_and_cache_report(
            connection_id=connection_id,
            report_type=report_type_enum,
            period_key=period_key,
            triggered_by="on_demand",
            user_id=user_id,
        )

    async def sync_all_reports(
        self,
        connection_id: UUID,
        report_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Sync all (or specified) report types for a connection.

        Used for scheduled batch sync operations.

        Args:
            connection_id: The Xero connection ID.
            report_types: Optional list of report types to sync.

        Returns:
            Summary of sync results.
        """
        from app.modules.integrations.xero.models import XeroReportType

        # Get connection
        connection = await self.connection_repo.get_by_id(connection_id)
        if not connection:
            raise XeroConnectionNotFoundExc(connection_id)

        # Determine report types to sync
        # Exclude aged reports - they are computed from synced invoices, not fetched from API
        excluded_types = {XeroReportType.AGED_RECEIVABLES, XeroReportType.AGED_PAYABLES}
        types_to_sync = []
        if report_types:
            for rt in report_types:
                try:
                    report_type_enum = XeroReportType(rt)
                    if report_type_enum not in excluded_types:
                        types_to_sync.append(report_type_enum)
                    else:
                        self.logger.info(f"Skipping {rt} - computed from synced invoices")
                except ValueError:
                    self.logger.warning(f"Ignoring invalid report type: {rt}")
        else:
            types_to_sync = [rt for rt in XeroReportType if rt not in excluded_types]

        results = {
            "connection_id": str(connection_id),
            "reports_synced": 0,
            "reports_failed": 0,
            "errors": [],
        }

        # Generate current period key
        now = datetime.now(UTC)
        current_period = f"{now.year}-{now.month:02d}"

        for report_type in types_to_sync:
            try:
                await self._fetch_and_cache_report(
                    connection_id=connection_id,
                    report_type=report_type,
                    period_key=current_period,
                    triggered_by="scheduled",
                )
                results["reports_synced"] += 1
            except Exception as e:
                self.logger.error(
                    f"Failed to sync {report_type.value}: {e}",
                    exc_info=True,
                )
                results["reports_failed"] += 1
                results["errors"].append(
                    {
                        "report_type": report_type.value,
                        "error": str(e),
                    }
                )

        return results

    async def _fetch_and_cache_report(
        self,
        connection_id: UUID,
        report_type: XeroReportType,
        period_key: str,
        triggered_by: str = "on_demand",
        user_id: UUID | None = None,
        to_date_override: str | None = None,
        cache_period_key: str | None = None,
    ) -> dict[str, Any]:
        """Fetch a report from Xero and cache it.

        Args:
            connection_id: The Xero connection ID.
            report_type: Type of report to fetch.
            period_key: Period identifier.
            triggered_by: How the sync was triggered.
            user_id: User who triggered the sync.
            to_date_override: Optional ISO date to cap the report to_date.
            cache_period_key: Period key to use for cache storage (includes
                override suffix when to_date_override is set).

        Returns:
            Report data dict.
        """
        from app.modules.integrations.xero.models import (
            XeroReportSyncStatus,
        )

        # Get connection with valid token (refreshes if needed)
        connection, access_token = await self._get_connection_and_token(connection_id)

        # Create sync job
        job = await self.sync_job_repo.create(
            tenant_id=connection.tenant_id,
            connection_id=connection_id,
            report_type=report_type,
            triggered_by=triggered_by,
            user_id=user_id,
        )

        try:
            # Update job status to in_progress
            await self.sync_job_repo.update_status(
                job_id=job.id,
                status=XeroReportSyncStatus.IN_PROGRESS,
            )

            # Parse period key to get date range
            from_date, to_date = self._parse_period_key(period_key)
            if to_date_override:
                to_date = to_date_override

            # Fetch report from Xero based on type
            async with XeroClient(self.settings.xero) as client:
                xero_response, rate_limit = await self._call_xero_report_api(
                    client=client,
                    access_token=access_token,
                    tenant_id=connection.xero_tenant_id,
                    report_type=report_type,
                    from_date=from_date,
                    to_date=to_date,
                )

            # Update rate limits on connection
            await self.connection_repo.update(
                connection_id,
                XeroConnectionUpdate(
                    rate_limit_minute_remaining=rate_limit.minute_remaining,
                    rate_limit_daily_remaining=rate_limit.daily_remaining,
                    last_used_at=datetime.now(UTC),
                ),
            )

            # Extract metadata and rows
            metadata = XeroReportTransformer.extract_report_metadata(xero_response)
            rows = XeroReportTransformer.extract_rows(xero_response)
            rows_count = XeroReportTransformer.count_data_rows(rows)

            # Extract summary using appropriate transformer
            summary_data = self._extract_summary(report_type, rows)

            # Calculate cache expiry
            cache_ttl = self._get_cache_ttl(report_type, period_key)
            cache_expires_at = datetime.now(UTC) + cache_ttl

            # Determine if current period
            is_current = self._is_current_period(period_key)

            # Upsert report
            report_data = {
                "id": job.id,  # Use job ID as report ID for now
                "tenant_id": connection.tenant_id,
                "connection_id": connection_id,
                "report_type": report_type,
                "period_key": cache_period_key or period_key,
                "xero_report_id": metadata.get("xero_report_id"),
                "report_name": metadata.get("report_name", report_type.value),
                "report_titles": metadata.get("report_titles", []),
                "xero_updated_at": metadata.get("xero_updated_at"),
                "rows_data": {"rows": rows},
                "summary_data": summary_data,
                "fetched_at": datetime.now(UTC),
                "cache_expires_at": cache_expires_at,
                "is_current_period": is_current,
                "parameters": {},
            }

            report, _ = await self.report_repo.upsert_report(report_data)

            # Update job as completed
            await self.sync_job_repo.update_status(
                job_id=job.id,
                status=XeroReportSyncStatus.COMPLETED,
                report_id=report.id,
                rows_fetched=rows_count,
            )

            # Log audit event for report fetch from Xero
            await self._log_report_access(
                connection_id=connection_id,
                report_type=report_type.value,
                period_key=cache_period_key or period_key,
                source="xero_api",
            )

            return self._report_to_dict(report)

        except Exception as e:
            # Update job as failed
            await self.sync_job_repo.update_status(
                job_id=job.id,
                status=XeroReportSyncStatus.FAILED,
                error_code="FETCH_ERROR",
                error_message=str(e)[:500],
            )
            raise

    def _get_cache_ttl(self, report_type: XeroReportType, period_key: str) -> timedelta:
        """Get cache TTL for a report type and period.

        Args:
            report_type: Type of report.
            period_key: Period identifier.

        Returns:
            Cache TTL as timedelta.
        """
        from app.modules.integrations.xero.models import XeroReportType

        is_current = self._is_current_period(period_key)

        # Historical periods have indefinite cache (1 year)
        if not is_current:
            return timedelta(days=365)

        # Current period TTLs by report type
        ttls = {
            XeroReportType.PROFIT_AND_LOSS: timedelta(hours=1),
            XeroReportType.BALANCE_SHEET: timedelta(hours=1),
            XeroReportType.AGED_RECEIVABLES: timedelta(hours=4),
            XeroReportType.AGED_PAYABLES: timedelta(hours=4),
            XeroReportType.TRIAL_BALANCE: timedelta(hours=1),
            XeroReportType.BANK_SUMMARY: timedelta(hours=4),
            XeroReportType.BUDGET_SUMMARY: timedelta(hours=24),
        }

        return ttls.get(report_type, timedelta(hours=1))

    def _is_current_period(self, period_key: str) -> bool:
        """Check if a period key represents the current period.

        Args:
            period_key: Period identifier.

        Returns:
            True if current period, False otherwise.
        """
        now = datetime.now(UTC)

        # Handle financial year (YYYY-FY)
        if period_key.endswith("-FY"):
            year = int(period_key.split("-")[0])
            # Australian FY runs July to June
            if now.month >= 7:
                return year == now.year
            return year == now.year - 1

        # Handle quarter (YYYY-QN)
        if "-Q" in period_key:
            parts = period_key.split("-Q")
            year = int(parts[0])
            quarter = int(parts[1])
            current_quarter = (now.month - 1) // 3 + 1
            return year == now.year and quarter == current_quarter

        # Handle month (YYYY-MM)
        if len(period_key) == 7:  # YYYY-MM
            year_month = f"{now.year}-{now.month:02d}"
            return period_key == year_month

        # Handle date (YYYY-MM-DD) - current if today or future
        if len(period_key) == 10:  # YYYY-MM-DD
            try:
                period_date = datetime.strptime(period_key, "%Y-%m-%d")
                return period_date.date() >= now.date()
            except ValueError:
                return True

        return True  # Default to current

    def _report_to_dict(self, report: XeroReport) -> dict[str, Any]:
        """Convert a XeroReport model to a response dict.

        Args:
            report: XeroReport model instance.

        Returns:
            Response dict.
        """
        return {
            "id": str(report.id),
            "report_type": report.report_type.value,
            "report_name": report.report_name,
            "report_titles": report.report_titles,
            "period_key": report.period_key,
            "period_start": report.period_start,
            "period_end": report.period_end,
            "as_of_date": report.as_of_date,
            "summary": report.summary_data,
            "rows": report.rows_data.get("rows", []),
            "fetched_at": report.fetched_at,
            "cache_expires_at": report.cache_expires_at,
            "is_current_period": report.is_current_period,
            "is_stale": report.cache_expires_at < datetime.now(UTC),
        }

    def _parse_period_key(self, period_key: str) -> tuple[str | None, str | None]:
        """Parse a period key into from_date and to_date strings.

        Args:
            period_key: Period identifier (e.g., '2025-FY', '2025-12', '2025-Q1').

        Returns:
            Tuple of (from_date, to_date) in YYYY-MM-DD format.
        """
        now = datetime.now(UTC)

        # Handle "current" keyword
        if period_key == "current":
            # Current month
            first_day = date(now.year, now.month, 1)
            if now.month == 12:
                last_day = date(now.year + 1, 1, 1) - timedelta(days=1)
            else:
                last_day = date(now.year, now.month + 1, 1) - timedelta(days=1)
            return first_day.isoformat(), last_day.isoformat()

        # Handle financial year (YYYY-FY) - Australian FY runs July to June
        if period_key.endswith("-FY"):
            fy_year = int(period_key.split("-")[0])
            from_date = date(fy_year, 7, 1)  # July 1
            to_date = date(fy_year + 1, 6, 30)  # June 30
            return from_date.isoformat(), to_date.isoformat()

        # Handle quarter (YYYY-QN)
        if "-Q" in period_key:
            parts = period_key.split("-Q")
            year = int(parts[0])
            quarter = int(parts[1])
            # Q1 = Jan-Mar, Q2 = Apr-Jun, Q3 = Jul-Sep, Q4 = Oct-Dec
            quarter_months = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}
            start_month, end_month = quarter_months[quarter]
            from_date = date(year, start_month, 1)
            if end_month == 12:
                to_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                to_date = date(year, end_month + 1, 1) - timedelta(days=1)
            return from_date.isoformat(), to_date.isoformat()

        # Handle month (YYYY-MM)
        if len(period_key) == 7:
            year, month = period_key.split("-")
            year_int = int(year)
            month_int = int(month)
            from_date = date(year_int, month_int, 1)
            if month_int == 12:
                to_date = date(year_int + 1, 1, 1) - timedelta(days=1)
            else:
                to_date = date(year_int, month_int + 1, 1) - timedelta(days=1)
            return from_date.isoformat(), to_date.isoformat()

        # Handle specific date (YYYY-MM-DD) - use as both from and to
        if len(period_key) == 10:
            return period_key, period_key

        # Default: return None to let API use defaults
        return None, None

    # =========================================================================
    # Bank Data Methods (Spec 049 — FR-015 to FR-018)
    # =========================================================================

    async def get_bank_balances(
        self,
        connection_id: UUID,
    ) -> list[dict[str, Any]]:
        """Get per-account bank balances from the Bank Summary report.

        Uses the existing report cache pipeline. Returns per-account
        opening/closing balances from the most recent Bank Summary.

        Args:
            connection_id: The Xero connection ID.

        Returns:
            List of per-account balance dicts.
        """
        from app.modules.integrations.xero.transformers import BankSummaryTransformer

        report_data = await self.get_report(
            connection_id=connection_id,
            report_type="bank_summary",
            period_key="current",
        )
        rows_data = report_data.get("rows", [])
        if not rows_data:
            return []
        return BankSummaryTransformer.extract_per_account_summary(rows_data)

    async def get_last_reconciliation_date(
        self,
        connection_id: UUID,
    ) -> date | None:
        """Derive the last bank reconciliation date from synced transactions.

        Queries the most recent reconciled bank transaction date across
        all bank accounts for the given connection.

        Args:
            connection_id: The Xero connection ID.

        Returns:
            The date of the most recent reconciled transaction, or None.
        """
        from sqlalchemy import func, select

        from app.modules.integrations.xero.models import XeroBankTransaction

        result = await self.session.execute(
            select(func.max(XeroBankTransaction.transaction_date)).where(
                XeroBankTransaction.connection_id == connection_id,
                XeroBankTransaction.is_reconciled.is_(True),
            )
        )
        max_date = result.scalar_one_or_none()
        if max_date is None:
            return None
        return max_date.date() if hasattr(max_date, "date") else max_date

    async def _call_xero_report_api(
        self,
        client: XeroClient,
        access_token: str,
        tenant_id: str,
        report_type: XeroReportType,
        from_date: str | None,
        to_date: str | None,
    ) -> tuple[dict[str, Any], RateLimitState]:
        """Call the appropriate Xero Reports API based on report type.

        Args:
            client: XeroClient instance.
            access_token: Valid Xero access token.
            tenant_id: Xero tenant/organization ID.
            report_type: Type of report to fetch.
            from_date: Start date for the report period.
            to_date: End date for the report period.

        Returns:
            Tuple of (Xero API response dict, rate limit state).
        """
        from app.modules.integrations.xero.models import XeroReportType

        if report_type == XeroReportType.PROFIT_AND_LOSS:
            return await client.get_profit_and_loss(
                access_token=access_token,
                tenant_id=tenant_id,
                from_date=from_date,
                to_date=to_date,
            )
        elif report_type == XeroReportType.BALANCE_SHEET:
            return await client.get_balance_sheet(
                access_token=access_token,
                tenant_id=tenant_id,
                as_of_date=to_date,  # Balance sheet is point-in-time
            )
        elif report_type == XeroReportType.AGED_RECEIVABLES:
            return await client.get_aged_receivables(
                access_token=access_token,
                tenant_id=tenant_id,
                as_of_date=to_date,
            )
        elif report_type == XeroReportType.AGED_PAYABLES:
            return await client.get_aged_payables(
                access_token=access_token,
                tenant_id=tenant_id,
                as_of_date=to_date,
            )
        elif report_type == XeroReportType.TRIAL_BALANCE:
            return await client.get_trial_balance(
                access_token=access_token,
                tenant_id=tenant_id,
                as_of_date=to_date,
            )
        elif report_type == XeroReportType.BANK_SUMMARY:
            return await client.get_bank_summary(
                access_token=access_token,
                tenant_id=tenant_id,
                from_date=from_date,
                to_date=to_date,
            )
        elif report_type == XeroReportType.BUDGET_SUMMARY:
            return await client.get_budget_summary(
                access_token=access_token,
                tenant_id=tenant_id,
            )
        else:
            raise ValueError(f"Unsupported report type: {report_type}")

    def _extract_summary(
        self,
        report_type: XeroReportType,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Extract summary data from report rows using appropriate transformer.

        Args:
            report_type: Type of report.
            rows: Report rows from Xero API.

        Returns:
            Summary dict with extracted metrics.
        """
        from app.modules.integrations.xero.models import XeroReportType

        if report_type == XeroReportType.PROFIT_AND_LOSS:
            return ProfitAndLossTransformer.extract_profit_and_loss_summary(rows)
        elif report_type == XeroReportType.BALANCE_SHEET:
            return BalanceSheetTransformer.extract_balance_sheet_summary(rows)
        elif report_type == XeroReportType.AGED_RECEIVABLES:
            return AgedReceivablesTransformer.extract_aged_receivables_summary(rows)
        elif report_type == XeroReportType.AGED_PAYABLES:
            return AgedPayablesTransformer.extract_aged_payables_summary(rows)
        elif report_type == XeroReportType.TRIAL_BALANCE:
            return TrialBalanceTransformer.extract_trial_balance_summary(rows)
        elif report_type == XeroReportType.BANK_SUMMARY:
            return BankSummaryTransformer.extract_bank_summary_summary(rows)
        else:
            # For Budget Summary or unknown types, return empty summary
            return {}

    async def _log_report_access(
        self,
        connection_id: UUID,
        report_type: str,
        period_key: str,
        source: str = "api",
        outcome: str = "success",
    ) -> None:
        """Log an audit event for report access.

        Args:
            connection_id: The Xero connection ID.
            report_type: Type of report accessed.
            period_key: Period of the report.
            source: Where the report came from (cache, api).
            outcome: Whether access was successful.
        """
        from app.core.tenant_context import TenantContext

        try:
            # Get tenant context
            tenant_id = TenantContext.get_current_tenant_id()

            await self.audit_service.log_event(
                event_type=f"xero.report.{report_type}.accessed",
                event_category="integration",
                resource_type="xero_report",
                resource_id=connection_id,
                action="read",
                outcome=outcome,
                tenant_id=tenant_id,
                new_values={
                    "report_type": report_type,
                    "period_key": period_key,
                    "source": source,
                },
            )
        except Exception as e:
            # Don't fail the main request if audit logging fails
            self.logger.warning(
                f"Failed to log audit event: {e}",
                extra={
                    "connection_id": str(connection_id),
                    "report_type": report_type,
                },
            )

    # =========================================================================
    # Computed Aged Reports (from synced invoices)
    # =========================================================================

    async def _compute_aged_receivables(
        self,
        connection_id: UUID,
        as_of_date: date | None = None,
    ) -> dict[str, Any]:
        """Compute aged receivables from synced ACCREC invoices.

        Args:
            connection_id: The Xero connection ID.
            as_of_date: Date to calculate aging from. Defaults to today.

        Returns:
            Report data dict with summary and rows.
        """
        from sqlalchemy import and_, select

        from app.modules.integrations.xero.models import (
            XeroClient,
            XeroInvoice,
            XeroInvoiceStatus,
            XeroInvoiceType,
        )

        if as_of_date is None:
            as_of_date = date.today()

        # Query unpaid receivables (ACCREC + AUTHORISED status)
        query = select(XeroInvoice).where(
            and_(
                XeroInvoice.connection_id == connection_id,
                XeroInvoice.invoice_type == XeroInvoiceType.ACCREC,
                XeroInvoice.status == XeroInvoiceStatus.AUTHORISED,
            )
        )
        result = await self.session.execute(query)
        invoices = result.scalars().all()

        # Get contact names for display
        contact_ids = list({inv.xero_contact_id for inv in invoices if inv.xero_contact_id})
        contact_names: dict[str, str] = {}
        if contact_ids:
            contact_query = select(XeroClient.xero_contact_id, XeroClient.name).where(
                and_(
                    XeroClient.connection_id == connection_id,
                    XeroClient.xero_contact_id.in_(contact_ids),
                )
            )
            contact_result = await self.session.execute(contact_query)
            contact_names = {row[0]: row[1] for row in contact_result.fetchall()}

        # Calculate aging buckets
        current = Decimal("0.00")
        overdue_30 = Decimal("0.00")
        overdue_60 = Decimal("0.00")
        overdue_90 = Decimal("0.00")
        overdue_90_plus = Decimal("0.00")

        # Track high-risk contacts (contacts with most overdue)
        contact_totals: dict[str, dict] = {}

        rows = []
        for inv in invoices:
            amount = inv.total_amount or Decimal("0.00")
            due_date = inv.due_date.date() if inv.due_date else inv.issue_date.date()
            days_overdue = (as_of_date - due_date).days

            # Assign to bucket
            if days_overdue <= 0:
                current += amount
                bucket = "Current"
            elif days_overdue <= 30:
                overdue_30 += amount
                bucket = "1-30 Days"
            elif days_overdue <= 60:
                overdue_60 += amount
                bucket = "31-60 Days"
            elif days_overdue <= 90:
                overdue_90 += amount
                bucket = "61-90 Days"
            else:
                overdue_90_plus += amount
                bucket = "90+ Days"

            # Track by contact for high-risk list
            contact_id = inv.xero_contact_id or "Unknown"
            contact_name = contact_names.get(contact_id, contact_id)
            if contact_id not in contact_totals:
                contact_totals[contact_id] = {
                    "name": contact_name,
                    "total": Decimal("0.00"),
                    "overdue": Decimal("0.00"),
                }
            contact_totals[contact_id]["total"] += amount
            if days_overdue > 0:
                contact_totals[contact_id]["overdue"] += amount

            # Add row for display
            rows.append(
                {
                    "row_type": "Row",
                    "cells": [
                        {"value": inv.invoice_number or inv.xero_invoice_id, "attributes": []},
                        {"value": contact_name, "attributes": []},
                        {"value": str(due_date), "attributes": []},
                        {"value": f"${float(amount):,.2f}", "attributes": []},
                        {"value": bucket, "attributes": []},
                    ],
                }
            )

        total = current + overdue_30 + overdue_60 + overdue_90 + overdue_90_plus
        overdue_total = overdue_30 + overdue_60 + overdue_90 + overdue_90_plus
        overdue_pct = float(overdue_total / total * 100) if total > 0 else 0.0

        # Get top 5 high-risk contacts (most overdue)
        high_risk = sorted(
            [
                {"name": c["name"], "amount": float(c["overdue"])}
                for c in contact_totals.values()
                if c["overdue"] > 0
            ],
            key=lambda x: x["amount"],
            reverse=True,
        )[:5]

        summary = {
            "total": float(total),
            "current": float(current),
            "overdue_30": float(overdue_30),
            "overdue_60": float(overdue_60),
            "overdue_90": float(overdue_90),
            "overdue_90_plus": float(overdue_90_plus),
            "overdue_total": float(overdue_total),
            "overdue_pct": round(overdue_pct, 1),
            "high_risk_contacts": high_risk,
        }

        # Add header row
        header_row = {
            "row_type": "Header",
            "cells": [
                {"value": "Invoice", "attributes": []},
                {"value": "Contact", "attributes": []},
                {"value": "Due Date", "attributes": []},
                {"value": "Amount", "attributes": []},
                {"value": "Aging", "attributes": []},
            ],
        }

        import uuid as uuid_module

        return {
            "id": str(uuid_module.uuid4()),
            "report_type": "aged_receivables_by_contact",
            "report_name": "Aged Receivables",
            "report_titles": [f"As of {as_of_date}"],
            "period_key": str(as_of_date),
            "period_start": None,
            "period_end": str(as_of_date),
            "as_of_date": str(as_of_date),
            "summary": summary,
            "rows": [header_row] + rows,
            "fetched_at": datetime.now(UTC).isoformat(),
            "cache_expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "is_current_period": True,
            "is_stale": False,
        }

    async def _compute_aged_payables(
        self,
        connection_id: UUID,
        as_of_date: date | None = None,
    ) -> dict[str, Any]:
        """Compute aged payables from synced ACCPAY invoices.

        Args:
            connection_id: The Xero connection ID.
            as_of_date: Date to calculate aging from. Defaults to today.

        Returns:
            Report data dict with summary and rows.
        """
        from sqlalchemy import and_, select

        from app.modules.integrations.xero.models import (
            XeroClient,
            XeroInvoice,
            XeroInvoiceStatus,
            XeroInvoiceType,
        )

        if as_of_date is None:
            as_of_date = date.today()

        # Query unpaid payables (ACCPAY + AUTHORISED status)
        query = select(XeroInvoice).where(
            and_(
                XeroInvoice.connection_id == connection_id,
                XeroInvoice.invoice_type == XeroInvoiceType.ACCPAY,
                XeroInvoice.status == XeroInvoiceStatus.AUTHORISED,
            )
        )
        result = await self.session.execute(query)
        invoices = result.scalars().all()

        # Get contact names for display
        contact_ids = list({inv.xero_contact_id for inv in invoices if inv.xero_contact_id})
        contact_names: dict[str, str] = {}
        if contact_ids:
            contact_query = select(XeroClient.xero_contact_id, XeroClient.name).where(
                and_(
                    XeroClient.connection_id == connection_id,
                    XeroClient.xero_contact_id.in_(contact_ids),
                )
            )
            contact_result = await self.session.execute(contact_query)
            contact_names = {row[0]: row[1] for row in contact_result.fetchall()}

        # Calculate aging buckets
        current = Decimal("0.00")
        overdue_30 = Decimal("0.00")
        overdue_60 = Decimal("0.00")
        overdue_90 = Decimal("0.00")
        overdue_90_plus = Decimal("0.00")

        rows = []
        for inv in invoices:
            amount = inv.total_amount or Decimal("0.00")
            due_date = inv.due_date.date() if inv.due_date else inv.issue_date.date()
            days_overdue = (as_of_date - due_date).days

            # Assign to bucket
            if days_overdue <= 0:
                current += amount
                bucket = "Current"
            elif days_overdue <= 30:
                overdue_30 += amount
                bucket = "1-30 Days"
            elif days_overdue <= 60:
                overdue_60 += amount
                bucket = "31-60 Days"
            elif days_overdue <= 90:
                overdue_90 += amount
                bucket = "61-90 Days"
            else:
                overdue_90_plus += amount
                bucket = "90+ Days"

            # Add row for display
            contact_name = contact_names.get(inv.xero_contact_id, inv.xero_contact_id or "Unknown")
            rows.append(
                {
                    "row_type": "Row",
                    "cells": [
                        {"value": inv.invoice_number or inv.xero_invoice_id, "attributes": []},
                        {"value": contact_name, "attributes": []},
                        {"value": str(due_date), "attributes": []},
                        {"value": f"${float(amount):,.2f}", "attributes": []},
                        {"value": bucket, "attributes": []},
                    ],
                }
            )

        total = current + overdue_30 + overdue_60 + overdue_90 + overdue_90_plus
        overdue_total = overdue_30 + overdue_60 + overdue_90 + overdue_90_plus

        summary = {
            "total": float(total),
            "current": float(current),
            "overdue_30": float(overdue_30),
            "overdue_60": float(overdue_60),
            "overdue_90": float(overdue_90),
            "overdue_90_plus": float(overdue_90_plus),
            "overdue_total": float(overdue_total),
        }

        # Add header row
        header_row = {
            "row_type": "Header",
            "cells": [
                {"value": "Invoice", "attributes": []},
                {"value": "Supplier", "attributes": []},
                {"value": "Due Date", "attributes": []},
                {"value": "Amount", "attributes": []},
                {"value": "Aging", "attributes": []},
            ],
        }

        import uuid as uuid_module

        return {
            "id": str(uuid_module.uuid4()),
            "report_type": "aged_payables_by_contact",
            "report_name": "Aged Payables",
            "report_titles": [f"As of {as_of_date}"],
            "period_key": str(as_of_date),
            "period_start": None,
            "period_end": str(as_of_date),
            "as_of_date": str(as_of_date),
            "summary": summary,
            "rows": [header_row] + rows,
            "fetched_at": datetime.now(UTC).isoformat(),
            "cache_expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "is_current_period": True,
            "is_stale": False,
        }

