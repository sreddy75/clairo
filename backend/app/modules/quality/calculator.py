"""Quality score calculators for each dimension.

This module contains the calculators for computing quality scores
across the five dimensions:
- Data Freshness (20%)
- Reconciliation (30%)
- Categorization (20%)
- Completeness (15%)
- PAYG Readiness (15%)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.xero.models import (
    XeroBankTransaction,
    XeroClient,
    XeroConnection,
    XeroEmployee,
    XeroInvoice,
    XeroPayRun,
)

# =============================================================================
# Constants
# =============================================================================

DIMENSION_WEIGHTS = {
    "freshness": Decimal("0.20"),  # 20%
    "reconciliation": Decimal("0.30"),  # 30%
    "categorization": Decimal("0.20"),  # 20%
    "completeness": Decimal("0.15"),  # 15%
    "payg_readiness": Decimal("0.15"),  # 15%
}

# Freshness thresholds
FRESHNESS_THRESHOLDS = {
    24: Decimal("100"),  # < 24 hours: 100%
    48: Decimal("75"),  # < 48 hours: 75%
    168: Decimal("50"),  # < 7 days (168 hours): 50%
    720: Decimal("25"),  # < 30 days (720 hours): 25%
}


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class CalculationResult:
    """Result of a dimension calculation."""

    score: Decimal
    details: str
    raw_data: dict[str, Any] | None = None

    @property
    def is_applicable(self) -> bool:
        """Check if this dimension is applicable (not N/A)."""
        return True


@dataclass
class PaygCalculationResult(CalculationResult):
    """Result for PAYG dimension (can be N/A)."""

    applicable: bool = True

    @property
    def is_applicable(self) -> bool:
        return self.applicable


# =============================================================================
# Base Calculator
# =============================================================================


class DimensionCalculator(ABC):
    """Base class for dimension calculators."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of this dimension."""
        ...

    @property
    def weight(self) -> Decimal:
        """Weight of this dimension."""
        return DIMENSION_WEIGHTS.get(self.name, Decimal("0"))

    @abstractmethod
    async def calculate(
        self,
        connection: XeroConnection,
        quarter_start: datetime,
        quarter_end: datetime,
    ) -> CalculationResult:
        """Calculate the score for this dimension.

        Args:
            connection: The Xero connection to score.
            quarter_start: Start of the BAS quarter.
            quarter_end: End of the BAS quarter.

        Returns:
            CalculationResult with score (0-100), details, and optional raw data.
        """
        ...


# =============================================================================
# Freshness Calculator
# =============================================================================


class FreshnessCalculator(DimensionCalculator):
    """Calculate data freshness based on last sync timestamp."""

    @property
    def name(self) -> str:
        return "freshness"

    async def calculate(
        self,
        connection: XeroConnection,
        quarter_start: datetime,  # noqa: ARG002
        quarter_end: datetime,  # noqa: ARG002
    ) -> CalculationResult:
        """Score based on how recently data was synced."""
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
            return CalculationResult(
                score=Decimal("0"),
                details="Data has never been synced",
                raw_data={"last_sync": None, "hours_ago": None},
            )

        # Calculate hours since last sync
        now = datetime.now(UTC)
        hours_ago = (now - last_sync).total_seconds() / 3600

        # Determine score based on thresholds
        score = Decimal("0")
        details = ""

        for threshold_hours, threshold_score in sorted(FRESHNESS_THRESHOLDS.items()):
            if hours_ago < threshold_hours:
                score = threshold_score
                if threshold_hours == 24:
                    details = f"Data synced {int(hours_ago)} hours ago (within 24h)"
                elif threshold_hours == 48:
                    details = f"Data synced {int(hours_ago)} hours ago (within 48h)"
                elif threshold_hours == 168:
                    details = f"Data synced {int(hours_ago / 24)} days ago (within 7 days)"
                else:
                    details = f"Data synced {int(hours_ago / 24)} days ago (within 30 days)"
                break
        else:
            details = f"Data synced {int(hours_ago / 24)} days ago (>30 days old)"

        return CalculationResult(
            score=score,
            details=details,
            raw_data={"last_sync": last_sync.isoformat(), "hours_ago": hours_ago},
        )


# =============================================================================
# Reconciliation Calculator
# =============================================================================


class ReconciliationCalculator(DimensionCalculator):
    """Calculate reconciliation score based on bank transactions.

    Note: Xero API doesn't provide direct reconciliation status for bank transactions.
    We use 'AUTHORISED' status as a proxy for transactions that have been reviewed.
    """

    @property
    def name(self) -> str:
        return "reconciliation"

    async def calculate(
        self,
        connection: XeroConnection,
        quarter_start: datetime,
        quarter_end: datetime,
    ) -> CalculationResult:
        """Score based on percentage of authorised bank transactions.

        Since Xero doesn't expose reconciliation status directly, we treat
        AUTHORISED transactions as "processed" for scoring purposes.
        """
        # Query bank transactions for the quarter
        # Count total and those with AUTHORISED status (meaning reviewed/approved)
        query = select(
            func.count().label("total"),
            func.count().filter(XeroBankTransaction.status == "AUTHORISED").label("authorised"),
        ).where(
            XeroBankTransaction.connection_id == connection.id,
            XeroBankTransaction.transaction_date >= quarter_start,
            XeroBankTransaction.transaction_date <= quarter_end,
        )

        result = await self.session.execute(query)
        row = result.one()
        total = row.total or 0
        authorised = row.authorised or 0

        # If no transactions, score is 100% (nothing to reconcile)
        if total == 0:
            return CalculationResult(
                score=Decimal("100"),
                details="No bank transactions in quarter",
                raw_data={"total": 0, "authorised": 0, "pending": 0},
            )

        # Calculate percentage
        score = Decimal(str((authorised / total) * 100)).quantize(Decimal("0.01"))
        pending = total - authorised

        if score >= 100:
            details = f"All {total} transactions authorised"
        else:
            details = f"{authorised} of {total} transactions authorised ({pending} pending)"

        return CalculationResult(
            score=score,
            details=details,
            raw_data={"total": total, "authorised": authorised, "pending": pending},
        )


# =============================================================================
# Categorization Calculator
# =============================================================================


class CategorizationCalculator(DimensionCalculator):
    """Calculate categorization score based on tax information.

    Uses tax_amount > 0 as indicator that items have been properly categorized
    with GST codes, since detailed line item tax types are stored in JSONB.
    """

    @property
    def name(self) -> str:
        return "categorization"

    async def calculate(
        self,
        connection: XeroConnection,
        quarter_start: datetime,
        quarter_end: datetime,
    ) -> CalculationResult:
        """Score based on percentage of items with tax information.

        Since line_items is JSONB, we use a simpler heuristic:
        items with tax_amount > 0 or non-null line_items are considered categorized.
        """
        # Count invoices - those with tax_amount or line_items are considered categorized
        invoice_query = select(
            func.count().label("total"),
            func.count()
            .filter((XeroInvoice.tax_amount != 0) | (XeroInvoice.line_items.isnot(None)))
            .label("categorized"),
        ).where(
            XeroInvoice.connection_id == connection.id,
            XeroInvoice.issue_date >= quarter_start,
            XeroInvoice.issue_date <= quarter_end,
        )

        invoice_result = await self.session.execute(invoice_query)
        invoice_row = invoice_result.one()

        # Count bank transactions - those with line_items are considered categorized
        txn_query = select(
            func.count().label("total"),
            func.count().filter(XeroBankTransaction.line_items.isnot(None)).label("categorized"),
        ).where(
            XeroBankTransaction.connection_id == connection.id,
            XeroBankTransaction.transaction_date >= quarter_start,
            XeroBankTransaction.transaction_date <= quarter_end,
        )

        txn_result = await self.session.execute(txn_query)
        txn_row = txn_result.one()

        # Combine totals
        total = (invoice_row.total or 0) + (txn_row.total or 0)
        categorized = (invoice_row.categorized or 0) + (txn_row.categorized or 0)

        # If no items, score is 100%
        if total == 0:
            return CalculationResult(
                score=Decimal("100"),
                details="No invoices or transactions in quarter",
                raw_data={
                    "invoices_total": 0,
                    "invoices_categorized": 0,
                    "transactions_total": 0,
                    "transactions_categorized": 0,
                },
            )

        # Calculate percentage
        score = Decimal(str((categorized / total) * 100)).quantize(Decimal("0.01"))
        uncategorized = total - categorized

        if score >= 100:
            details = f"All {total} items have tax codes"
        else:
            details = f"{categorized} of {total} items have tax codes ({uncategorized} missing)"

        return CalculationResult(
            score=score,
            details=details,
            raw_data={
                "invoices_total": invoice_row.total or 0,
                "invoices_categorized": invoice_row.categorized or 0,
                "transactions_total": txn_row.total or 0,
                "transactions_categorized": txn_row.categorized or 0,
            },
        )


# =============================================================================
# Completeness Calculator
# =============================================================================


class CompletenessCalculator(DimensionCalculator):
    """Calculate completeness score based on presence of data."""

    @property
    def name(self) -> str:
        return "completeness"

    async def calculate(
        self,
        connection: XeroConnection,
        quarter_start: datetime,
        quarter_end: datetime,
    ) -> CalculationResult:
        """Score based on presence of accounts, contacts, and activity."""
        checks = {}

        # Check for accounts (Chart of Accounts synced)
        from app.modules.integrations.xero.models import XeroAccount

        accounts_count = await self.session.scalar(
            select(func.count())
            .select_from(XeroAccount)
            .where(XeroAccount.connection_id == connection.id)
        )
        checks["has_accounts"] = (accounts_count or 0) > 0

        # Check for contacts synced
        contacts_count = await self.session.scalar(
            select(func.count())
            .select_from(XeroClient)
            .where(XeroClient.connection_id == connection.id)
        )
        checks["has_contacts"] = (contacts_count or 0) > 0

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
        checks["has_invoices"] = (invoices_count or 0) > 0

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
        checks["has_transactions"] = (txn_count or 0) > 0

        # Calculate score: 25% for each check
        passed = sum(1 for v in checks.values() if v)
        score = Decimal(str((passed / 4) * 100)).quantize(Decimal("0.01"))

        # Build details
        missing = [k.replace("has_", "").replace("_", " ") for k, v in checks.items() if not v]
        details = "All data types present" if not missing else f"Missing: {', '.join(missing)}"

        return CalculationResult(
            score=score,
            details=details,
            raw_data={
                "accounts": accounts_count or 0,
                "contacts": contacts_count or 0,
                "invoices": invoices_count or 0,
                "transactions": txn_count or 0,
            },
        )


# =============================================================================
# PAYG Readiness Calculator
# =============================================================================


class PaygReadinessCalculator(DimensionCalculator):
    """Calculate PAYG readiness based on payroll data."""

    @property
    def name(self) -> str:
        return "payg_readiness"

    async def calculate(
        self,
        connection: XeroConnection,
        quarter_start: datetime,
        quarter_end: datetime,
    ) -> PaygCalculationResult:
        """Score based on payroll data completeness."""
        # If payroll not enabled, this dimension is N/A
        if not connection.has_payroll_access:
            return PaygCalculationResult(
                score=Decimal("100"),  # Doesn't count against score
                details="Payroll not enabled for this connection",
                applicable=False,
                raw_data={"has_payroll_access": False},
            )

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

        # Scoring logic
        if pay_runs > 0:
            score = Decimal("100")
            details = f"{pay_runs} pay runs found for quarter"
        elif employees > 0:
            score = Decimal("50")
            details = f"{employees} employees found but no pay runs in quarter"
        else:
            score = Decimal("0")
            details = "Payroll enabled but no employees or pay runs synced"

        return PaygCalculationResult(
            score=score,
            details=details,
            applicable=True,
            raw_data={
                "has_payroll_access": True,
                "employees": employees,
                "pay_runs": pay_runs,
            },
        )


# =============================================================================
# Score Aggregator
# =============================================================================


class QualityScoreAggregator:
    """Aggregates dimension scores into overall quality score."""

    def __init__(self):
        self.dimension_results: dict[str, CalculationResult] = {}

    def add_result(self, dimension: str, result: CalculationResult) -> None:
        """Add a dimension result."""
        self.dimension_results[dimension] = result

    def calculate_overall_score(self) -> Decimal:
        """Calculate weighted overall score.

        If PAYG dimension is N/A, redistributes its weight proportionally.
        """
        total_weight = Decimal("0")
        weighted_sum = Decimal("0")

        for dimension, result in self.dimension_results.items():
            weight = DIMENSION_WEIGHTS.get(dimension, Decimal("0"))

            # Skip N/A dimensions
            if not result.is_applicable:
                continue

            total_weight += weight
            weighted_sum += result.score * weight

        if total_weight == 0:
            return Decimal("0")

        # Normalize to account for skipped dimensions
        overall = (weighted_sum / total_weight).quantize(Decimal("0.01"))
        return min(overall, Decimal("100"))  # Cap at 100

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all dimension scores."""
        return {
            dimension: {
                "score": float(result.score),
                "weight": float(DIMENSION_WEIGHTS.get(dimension, 0)),
                "details": result.details,
                "applicable": result.is_applicable,
            }
            for dimension, result in self.dimension_results.items()
        }
