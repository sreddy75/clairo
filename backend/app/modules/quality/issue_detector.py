"""Quality issue detector for identifying data problems.

This module detects specific quality issues in synced data
and generates QualityIssue records for each problem found.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.xero.models import (
    XeroBankTransaction,
    XeroConnection,
    XeroEmployee,
    XeroInvoice,
    XeroPayRun,
)
from app.modules.quality.models import IssueCode, IssueSeverity

# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class DetectedIssue:
    """A detected quality issue."""

    code: IssueCode
    severity: IssueSeverity
    title: str
    description: str
    affected_entity_type: str | None = None
    affected_count: int = 0
    affected_ids: list[str] = field(default_factory=list)
    suggested_action: str | None = None


# =============================================================================
# Issue Titles and Descriptions
# =============================================================================

ISSUE_DEFINITIONS: dict[IssueCode, dict[str, Any]] = {
    IssueCode.STALE_DATA: {
        "severity": IssueSeverity.WARNING,
        "title": "Data sync overdue",
        "description": "Data has not been synced in over 24 hours",
        "suggested_action": "Sync data from Xero to get the latest updates",
    },
    IssueCode.STALE_DATA_CRITICAL: {
        "severity": IssueSeverity.CRITICAL,
        "title": "Data severely outdated",
        "description": "Data has not been synced in over 7 days",
        "suggested_action": "Sync data from Xero immediately to ensure accuracy",
    },
    IssueCode.UNRECONCILED_TXN: {
        "severity": IssueSeverity.WARNING,
        "title": "Unreconciled transactions",
        "description": "Bank transactions are not reconciled",
        "entity_type": "bank_transaction",
        "suggested_action": "Reconcile transactions in Xero before BAS preparation",
    },
    IssueCode.MISSING_GST_CODE: {
        "severity": IssueSeverity.WARNING,
        "title": "Missing GST codes",
        "description": "Items are missing GST classification",
        "entity_type": "mixed",  # invoices and transactions
        "suggested_action": "Add GST codes to all invoices and transactions",
    },
    IssueCode.INVALID_GST_CODE: {
        "severity": IssueSeverity.ERROR,
        "title": "Invalid GST codes",
        "description": "Items have invalid or unknown GST codes",
        "entity_type": "mixed",
        "suggested_action": "Correct the GST codes on flagged items",
    },
    IssueCode.NO_INVOICES: {
        "severity": IssueSeverity.INFO,
        "title": "No invoices for quarter",
        "description": "No sales or purchase invoices found for this quarter",
        "suggested_action": "Verify that all invoices are entered in Xero",
    },
    IssueCode.NO_TRANSACTIONS: {
        "severity": IssueSeverity.INFO,
        "title": "No transactions for quarter",
        "description": "No bank transactions found for this quarter",
        "suggested_action": "Verify that bank feeds are connected and up to date",
    },
    IssueCode.MISSING_PAYROLL: {
        "severity": IssueSeverity.WARNING,
        "title": "Payroll data missing",
        "description": "Payroll is enabled but no data has been synced",
        "suggested_action": "Sync payroll data from Xero Payroll",
    },
    IssueCode.INCOMPLETE_PAYROLL: {
        "severity": IssueSeverity.WARNING,
        "title": "Incomplete payroll data",
        "description": "Employees exist but no pay runs found for the quarter",
        "entity_type": "employee",
        "suggested_action": "Ensure pay runs are processed and synced",
    },
}


# =============================================================================
# Issue Detector
# =============================================================================


class IssueDetector:
    """Detects quality issues in synced Xero data."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.now = datetime.now(UTC)

    async def detect_all(
        self,
        connection: XeroConnection,
        quarter_start: datetime,
        quarter_end: datetime,
    ) -> list[DetectedIssue]:
        """Detect all quality issues for a connection.

        Args:
            connection: The Xero connection to analyze.
            quarter_start: Start of the BAS quarter.
            quarter_end: End of the BAS quarter.

        Returns:
            List of detected issues.
        """
        issues: list[DetectedIssue] = []

        # Data freshness issues
        freshness_issues = await self._detect_freshness_issues(connection)
        issues.extend(freshness_issues)

        # Reconciliation issues
        reconciliation_issues = await self._detect_reconciliation_issues(
            connection, quarter_start, quarter_end
        )
        issues.extend(reconciliation_issues)

        # Categorization issues
        categorization_issues = await self._detect_categorization_issues(
            connection, quarter_start, quarter_end
        )
        issues.extend(categorization_issues)

        # Completeness issues
        completeness_issues = await self._detect_completeness_issues(
            connection, quarter_start, quarter_end
        )
        issues.extend(completeness_issues)

        # PAYG issues
        if connection.has_payroll_access:
            payg_issues = await self._detect_payg_issues(connection, quarter_start, quarter_end)
            issues.extend(payg_issues)

        return issues

    # =========================================================================
    # Freshness Issues
    # =========================================================================

    async def _detect_freshness_issues(
        self,
        connection: XeroConnection,
    ) -> list[DetectedIssue]:
        """Detect data freshness issues."""
        issues: list[DetectedIssue] = []
        # Use the most recent timestamp available. During a phased sync,
        # last_full_sync_at is only set after ALL phases complete, but
        # quality_score runs as a Phase 2 post-sync task before that.
        # Per-entity timestamps are updated as each entity completes,
        # so they may be more recent than last_full_sync_at.
        all_timestamps = [
            connection.last_full_sync_at,
            connection.last_transactions_sync_at,
            connection.last_invoices_sync_at,
            connection.last_contacts_sync_at,
            connection.last_accounts_sync_at,
        ]
        valid = [ts for ts in all_timestamps if ts is not None]
        last_sync = max(valid) if valid else None

        if last_sync is None:
            # Never synced - critical
            issues.append(
                self._create_issue(
                    IssueCode.STALE_DATA_CRITICAL,
                    description="Data has never been synced from Xero",
                )
            )
            return issues

        hours_ago = (self.now - last_sync).total_seconds() / 3600

        if hours_ago >= 168:  # 7 days
            issues.append(
                self._create_issue(
                    IssueCode.STALE_DATA_CRITICAL,
                    description=f"Data last synced {int(hours_ago / 24)} days ago",
                )
            )
        elif hours_ago >= 24:
            issues.append(
                self._create_issue(
                    IssueCode.STALE_DATA,
                    description=f"Data last synced {int(hours_ago)} hours ago",
                )
            )

        return issues

    # =========================================================================
    # Reconciliation Issues
    # =========================================================================

    async def _detect_reconciliation_issues(
        self,
        connection: XeroConnection,
        quarter_start: datetime,
        quarter_end: datetime,
    ) -> list[DetectedIssue]:
        """Detect pending (non-authorised) transaction issues.

        Note: Xero API doesn't provide direct reconciliation status.
        We treat non-AUTHORISED transactions as 'pending review'.
        """
        issues: list[DetectedIssue] = []

        # Find transactions that are not AUTHORISED (pending review)
        query = (
            select(XeroBankTransaction.id)
            .where(
                XeroBankTransaction.connection_id == connection.id,
                XeroBankTransaction.transaction_date >= quarter_start,
                XeroBankTransaction.transaction_date <= quarter_end,
                XeroBankTransaction.status != "AUTHORISED",
            )
            .limit(1000)
        )  # Limit to prevent memory issues

        result = await self.session.execute(query)
        pending_ids = [str(row[0]) for row in result.fetchall()]

        if pending_ids:
            issues.append(
                self._create_issue(
                    IssueCode.UNRECONCILED_TXN,
                    affected_count=len(pending_ids),
                    affected_ids=pending_ids[:100],  # Store max 100 IDs
                    description=f"{len(pending_ids)} bank transactions pending review",
                )
            )

        return issues

    # =========================================================================
    # Categorization Issues
    # =========================================================================

    async def _detect_categorization_issues(
        self,
        connection: XeroConnection,
        quarter_start: datetime,
        quarter_end: datetime,
    ) -> list[DetectedIssue]:
        """Detect missing GST code issues.

        Since line_items is JSONB, we use line_items IS NULL as a proxy
        for missing categorization.
        """
        issues: list[DetectedIssue] = []

        # Find invoices without line_items (uncategorized)
        invoice_query = (
            select(XeroInvoice.id)
            .where(
                XeroInvoice.connection_id == connection.id,
                XeroInvoice.issue_date >= quarter_start,
                XeroInvoice.issue_date <= quarter_end,
                XeroInvoice.line_items.is_(None),
            )
            .limit(500)
        )

        invoice_result = await self.session.execute(invoice_query)
        missing_invoice_ids = [str(row[0]) for row in invoice_result.fetchall()]

        # Find transactions without line_items (uncategorized)
        txn_query = (
            select(XeroBankTransaction.id)
            .where(
                XeroBankTransaction.connection_id == connection.id,
                XeroBankTransaction.transaction_date >= quarter_start,
                XeroBankTransaction.transaction_date <= quarter_end,
                XeroBankTransaction.line_items.is_(None),
            )
            .limit(500)
        )

        txn_result = await self.session.execute(txn_query)
        missing_txn_ids = [str(row[0]) for row in txn_result.fetchall()]

        total_missing = len(missing_invoice_ids) + len(missing_txn_ids)

        if total_missing > 0:
            issues.append(
                self._create_issue(
                    IssueCode.MISSING_GST_CODE,
                    affected_count=total_missing,
                    affected_ids=missing_invoice_ids[:50] + missing_txn_ids[:50],
                    description=f"{total_missing} items missing tax codes ({len(missing_invoice_ids)} invoices, {len(missing_txn_ids)} transactions)",
                )
            )

        return issues

    # =========================================================================
    # Completeness Issues
    # =========================================================================

    async def _detect_completeness_issues(
        self,
        connection: XeroConnection,
        quarter_start: datetime,
        quarter_end: datetime,
    ) -> list[DetectedIssue]:
        """Detect missing data issues."""
        issues: list[DetectedIssue] = []

        # Check for invoices in quarter
        invoices_count = await self.session.scalar(
            select(func.count())
            .select_from(XeroInvoice)
            .where(
                XeroInvoice.connection_id == connection.id,
                XeroInvoice.issue_date >= quarter_start,
                XeroInvoice.issue_date <= quarter_end,
            )
        )

        if not invoices_count:
            issues.append(self._create_issue(IssueCode.NO_INVOICES))

        # Check for transactions in quarter
        txn_count = await self.session.scalar(
            select(func.count())
            .select_from(XeroBankTransaction)
            .where(
                XeroBankTransaction.connection_id == connection.id,
                XeroBankTransaction.transaction_date >= quarter_start,
                XeroBankTransaction.transaction_date <= quarter_end,
            )
        )

        if not txn_count:
            issues.append(self._create_issue(IssueCode.NO_TRANSACTIONS))

        return issues

    # =========================================================================
    # PAYG Issues
    # =========================================================================

    async def _detect_payg_issues(
        self,
        connection: XeroConnection,
        quarter_start: datetime,
        quarter_end: datetime,
    ) -> list[DetectedIssue]:
        """Detect payroll-related issues."""
        issues: list[DetectedIssue] = []

        # Check for employees
        employees_count = await self.session.scalar(
            select(func.count())
            .select_from(XeroEmployee)
            .where(XeroEmployee.connection_id == connection.id)
        )

        # Check for pay runs in quarter
        pay_runs_count = await self.session.scalar(
            select(func.count())
            .select_from(XeroPayRun)
            .where(
                XeroPayRun.connection_id == connection.id,
                XeroPayRun.payment_date >= quarter_start,
                XeroPayRun.payment_date <= quarter_end,
            )
        )

        employees = employees_count or 0
        pay_runs = pay_runs_count or 0

        if employees == 0 and pay_runs == 0:
            issues.append(
                self._create_issue(
                    IssueCode.MISSING_PAYROLL,
                    description="Payroll is enabled but no employees or pay runs have been synced",
                )
            )
        elif employees > 0 and pay_runs == 0:
            issues.append(
                self._create_issue(
                    IssueCode.INCOMPLETE_PAYROLL,
                    affected_count=employees,
                    description=f"{employees} employees found but no pay runs for the quarter",
                )
            )

        return issues

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _create_issue(
        self,
        code: IssueCode,
        description: str | None = None,
        affected_count: int = 0,
        affected_ids: list[str] | None = None,
    ) -> DetectedIssue:
        """Create a DetectedIssue from a code."""
        definition = ISSUE_DEFINITIONS[code]

        return DetectedIssue(
            code=code,
            severity=definition["severity"],
            title=definition["title"],
            description=description or definition["description"],
            affected_entity_type=definition.get("entity_type"),
            affected_count=affected_count,
            affected_ids=affected_ids or [],
            suggested_action=definition.get("suggested_action"),
        )
