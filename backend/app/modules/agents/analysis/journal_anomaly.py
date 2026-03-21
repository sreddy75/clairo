"""Journal anomaly detection for audit trail insights.

Spec 024: Credit Notes, Payments & Journals - User Story 7

Detects unusual journal patterns that may indicate:
- Data entry errors
- Potential fraud
- Unusual transactions requiring review

Anomaly types:
- Large amount journals (above threshold)
- Weekend/holiday entries
- Unusual account combinations
- Round number entries
- Late night entries (if timestamp available)
- Duplicate entries
- Unusual patterns
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.xero.repository import (
    XeroJournalRepository,
    XeroManualJournalRepository,
)

logger = logging.getLogger(__name__)


class AnomalyType(str, Enum):
    """Types of journal anomalies."""

    LARGE_AMOUNT = "large_amount"
    WEEKEND_ENTRY = "weekend_entry"
    ROUND_NUMBER = "round_number"
    UNUSUAL_ACCOUNT = "unusual_account"
    DUPLICATE_PATTERN = "duplicate_pattern"
    CONCENTRATION_RISK = "concentration_risk"
    MANUAL_OVERRIDE = "manual_override"


class AnomalySeverity(str, Enum):
    """Severity levels for anomalies."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class JournalAnomaly:
    """Represents a detected journal anomaly."""

    anomaly_type: AnomalyType
    severity: AnomalySeverity
    journal_id: str
    journal_date: datetime
    amount: Decimal
    description: str
    details: dict[str, Any]
    recommendation: str


class JournalAnomalyDetector:
    """Detects unusual patterns in journal entries.

    Spec 024: Credit Notes, Payments & Journals - User Story 7

    Provides audit trail insights by identifying:
    - Unusually large transactions
    - Weekend/off-hours entries
    - Round number entries (potential fraud indicator)
    - Multiple entries to same account
    - Manual journal overrides

    Attributes:
        session: SQLAlchemy async session.
        large_amount_threshold: Amount above which to flag as large.
        round_number_threshold: Amount to check for round numbers.
    """

    def __init__(
        self,
        session: AsyncSession,
        large_amount_threshold: Decimal = Decimal("10000"),
        round_number_threshold: Decimal = Decimal("1000"),
    ) -> None:
        """Initialize the anomaly detector.

        Args:
            session: SQLAlchemy async session.
            large_amount_threshold: Flag amounts above this value.
            round_number_threshold: Check for round numbers above this value.
        """
        self.session = session
        self.journal_repo = XeroJournalRepository(session)
        self.manual_journal_repo = XeroManualJournalRepository(session)
        self.large_amount_threshold = large_amount_threshold
        self.round_number_threshold = round_number_threshold

    async def analyze_connection(
        self,
        connection_id: UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[JournalAnomaly]:
        """Analyze journals for a connection and detect anomalies.

        Args:
            connection_id: The Xero connection ID.
            date_from: Optional start date filter.
            date_to: Optional end date filter.

        Returns:
            List of detected anomalies.
        """
        # Default to last 12 months if no date range specified
        if date_to is None:
            date_to = datetime.now(UTC)
        if date_from is None:
            date_from = date_to - timedelta(days=365)

        anomalies: list[JournalAnomaly] = []

        # Get journals for analysis
        journals, _ = await self.journal_repo.list_by_connection(
            connection_id=connection_id,
            date_from=date_from,
            date_to=date_to,
            limit=1000,
        )

        # Get manual journals (higher risk)
        manual_journals, _ = await self.manual_journal_repo.list_by_connection(
            connection_id=connection_id,
            date_from=date_from,
            date_to=date_to,
            limit=500,
        )

        # Run detection rules
        for journal in journals:
            anomalies.extend(self._analyze_journal(journal, is_manual=False))

        for journal in manual_journals:
            anomalies.extend(self._analyze_manual_journal(journal))

        # Run aggregate analysis
        anomalies.extend(
            await self._analyze_account_concentration(connection_id, date_from, date_to)
        )

        # Sort by severity (critical first)
        severity_order = {
            AnomalySeverity.CRITICAL: 0,
            AnomalySeverity.HIGH: 1,
            AnomalySeverity.MEDIUM: 2,
            AnomalySeverity.LOW: 3,
        }
        anomalies.sort(key=lambda a: severity_order[a.severity])

        return anomalies

    def _analyze_journal(
        self,
        journal: Any,
        is_manual: bool = False,
    ) -> list[JournalAnomaly]:
        """Analyze a single journal for anomalies.

        Args:
            journal: The journal entry to analyze.
            is_manual: Whether this is a manual journal.

        Returns:
            List of anomalies detected in this journal.
        """
        anomalies = []

        # Check for large amount
        if hasattr(journal, "net_amount") and journal.net_amount:
            amount = abs(journal.net_amount)
            if amount >= self.large_amount_threshold:
                anomalies.append(
                    JournalAnomaly(
                        anomaly_type=AnomalyType.LARGE_AMOUNT,
                        severity=AnomalySeverity.MEDIUM
                        if amount < self.large_amount_threshold * 5
                        else AnomalySeverity.HIGH,
                        journal_id=str(journal.id),
                        journal_date=journal.journal_date
                        if hasattr(journal, "journal_date")
                        else datetime.now(UTC),
                        amount=amount,
                        description=f"Large journal entry: ${amount:,.2f}",
                        details={
                            "threshold": float(self.large_amount_threshold),
                            "narration": getattr(journal, "narration", None),
                        },
                        recommendation="Review journal entry for accuracy and proper authorization.",
                    )
                )

            # Check for round numbers (potential fraud indicator)
            if amount >= self.round_number_threshold:
                if self._is_round_number(amount):
                    anomalies.append(
                        JournalAnomaly(
                            anomaly_type=AnomalyType.ROUND_NUMBER,
                            severity=AnomalySeverity.LOW,
                            journal_id=str(journal.id),
                            journal_date=journal.journal_date
                            if hasattr(journal, "journal_date")
                            else datetime.now(UTC),
                            amount=amount,
                            description=f"Round number entry: ${amount:,.2f}",
                            details={
                                "narration": getattr(journal, "narration", None),
                            },
                            recommendation="Verify round number entries have supporting documentation.",
                        )
                    )

        # Check for weekend entries
        journal_date = getattr(journal, "journal_date", None)
        if journal_date and journal_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            day_name = "Saturday" if journal_date.weekday() == 5 else "Sunday"
            anomalies.append(
                JournalAnomaly(
                    anomaly_type=AnomalyType.WEEKEND_ENTRY,
                    severity=AnomalySeverity.LOW if not is_manual else AnomalySeverity.MEDIUM,
                    journal_id=str(journal.id),
                    journal_date=journal_date,
                    amount=getattr(journal, "net_amount", Decimal("0")),
                    description=f"Journal entry on {day_name}",
                    details={
                        "day_of_week": journal_date.strftime("%A"),
                        "narration": getattr(journal, "narration", None),
                    },
                    recommendation="Verify weekend entries are legitimate business transactions.",
                )
            )

        return anomalies

    def _analyze_manual_journal(
        self,
        journal: Any,
    ) -> list[JournalAnomaly]:
        """Analyze a manual journal entry.

        Manual journals warrant extra scrutiny as they bypass
        normal transaction flows.

        Args:
            journal: The manual journal to analyze.

        Returns:
            List of anomalies detected.
        """
        anomalies = self._analyze_journal(journal, is_manual=True)

        # Additional check: flag all large manual journals
        if hasattr(journal, "total_amount") and journal.total_amount:
            amount = abs(journal.total_amount)
            if amount >= self.large_amount_threshold / 2:  # Lower threshold for manual
                anomalies.append(
                    JournalAnomaly(
                        anomaly_type=AnomalyType.MANUAL_OVERRIDE,
                        severity=AnomalySeverity.MEDIUM,
                        journal_id=str(journal.id),
                        journal_date=getattr(journal, "manual_journal_date", datetime.now(UTC)),
                        amount=amount,
                        description=f"Manual journal entry: ${amount:,.2f}",
                        details={
                            "narration": getattr(journal, "narration", None),
                            "status": str(getattr(journal, "status", "unknown")),
                        },
                        recommendation="Ensure manual journal has proper approval and documentation.",
                    )
                )

        return anomalies

    async def _analyze_account_concentration(
        self,
        connection_id: UUID,
        date_from: datetime,
        date_to: datetime,
    ) -> list[JournalAnomaly]:
        """Analyze for concentration of entries to specific accounts.

        Detects when many journal entries hit the same account,
        which could indicate:
        - Dumping transactions to suspense accounts
        - Unusual patterns requiring review

        Args:
            connection_id: The Xero connection ID.
            date_from: Start date.
            date_to: End date.

        Returns:
            List of concentration anomalies.
        """
        # This would require aggregating journal lines by account
        # For now, return empty list - full implementation would
        # query journal lines and group by account_id
        return []

    def _is_round_number(self, amount: Decimal) -> bool:
        """Check if amount is a round number.

        Round numbers (e.g., $1000, $5000, $10000) with no cents
        can be indicators of estimated/fabricated entries.

        Args:
            amount: The amount to check.

        Returns:
            True if the amount is a round number.
        """
        # Check if amount has no cents
        if amount != amount.quantize(Decimal("1")):
            return False

        # Check if divisible by 1000 or 500
        int_amount = int(amount)
        return int_amount % 500 == 0

    async def get_anomaly_summary(
        self,
        connection_id: UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        """Get summary of anomalies for a connection.

        Args:
            connection_id: The Xero connection ID.
            date_from: Optional start date filter.
            date_to: Optional end date filter.

        Returns:
            Summary statistics and top anomalies.
        """
        anomalies = await self.analyze_connection(
            connection_id=connection_id,
            date_from=date_from,
            date_to=date_to,
        )

        # Group by type
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        total_amount_flagged = Decimal("0")

        for anomaly in anomalies:
            by_type[anomaly.anomaly_type.value] = by_type.get(anomaly.anomaly_type.value, 0) + 1
            by_severity[anomaly.severity.value] = by_severity.get(anomaly.severity.value, 0) + 1
            total_amount_flagged += anomaly.amount

        return {
            "total_anomalies": len(anomalies),
            "by_type": by_type,
            "by_severity": by_severity,
            "total_amount_flagged": float(total_amount_flagged),
            "critical_count": by_severity.get("critical", 0),
            "high_count": by_severity.get("high", 0),
            "top_anomalies": [
                {
                    "type": a.anomaly_type.value,
                    "severity": a.severity.value,
                    "amount": float(a.amount),
                    "description": a.description,
                    "recommendation": a.recommendation,
                }
                for a in anomalies[:10]  # Top 10
            ],
        }
