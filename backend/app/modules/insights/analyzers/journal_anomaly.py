"""Journal anomaly analyzer for insights system.

Spec 024: Credit Notes, Payments & Journals - User Story 7

Integrates journal anomaly detection with the insights system
to generate alerts for unusual journal patterns.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.modules.agents.analysis.journal_anomaly import (
    JournalAnomalyDetector,
)
from app.modules.insights.analyzers.base import BaseAnalyzer
from app.modules.insights.models import InsightCategory, InsightPriority
from app.modules.insights.schemas import InsightCreate, SuggestedAction

logger = logging.getLogger(__name__)


class JournalAnomalyAnalyzer(BaseAnalyzer):
    """Analyzer that detects unusual journal patterns.

    Generates insights for:
    - Large amount journal entries
    - Weekend/off-hours entries
    - Round number entries
    - Manual journal overrides
    - Concentration of entries to specific accounts

    These insights help accountants identify potential
    errors or fraud requiring investigation.
    """

    @property
    def category(self) -> InsightCategory:
        """Return the compliance category for audit-related insights."""
        return InsightCategory.COMPLIANCE

    async def analyze_client(
        self,
        tenant_id: UUID,
        client_id: UUID,
    ) -> list[InsightCreate]:
        """Analyze journal entries for a client.

        Args:
            tenant_id: The tenant ID.
            client_id: The XeroConnection ID to analyze.

        Returns:
            List of InsightCreate objects for detected anomalies.
        """
        insights: list[InsightCreate] = []

        try:
            # Analyze last 3 months for recent anomalies
            detector = JournalAnomalyDetector(self.db)
            date_to = datetime.now(UTC)
            date_from = date_to - timedelta(days=90)

            summary = await detector.get_anomaly_summary(
                connection_id=client_id,
                date_from=date_from,
                date_to=date_to,
            )

            # Generate insights based on findings
            if summary["total_anomalies"] > 0:
                # Create a summary insight
                priority = self._determine_priority(summary)
                insights.append(
                    InsightCreate(
                        category=InsightCategory.COMPLIANCE,
                        insight_type="journal_anomaly_summary",
                        priority=priority,
                        title=self._generate_title(summary),
                        summary=self._generate_summary(summary),
                        detail=self._generate_detail(summary),
                        suggested_actions=self._generate_actions(summary),
                        expires_at=datetime.now(UTC) + timedelta(days=30),
                        confidence=0.85,
                        data_snapshot={
                            "total_anomalies": summary["total_anomalies"],
                            "critical_count": summary["critical_count"],
                            "high_count": summary["high_count"],
                            "amount_flagged": summary["total_amount_flagged"],
                            "by_type": summary["by_type"],
                            "analyzed_period": {
                                "from": date_from.isoformat(),
                                "to": date_to.isoformat(),
                            },
                        },
                    )
                )

                # Create specific high-priority insights for critical items
                for anomaly in summary.get("top_anomalies", [])[:3]:
                    if anomaly["severity"] in ("critical", "high"):
                        insights.append(
                            InsightCreate(
                                category=InsightCategory.COMPLIANCE,
                                insight_type=f"journal_anomaly_{anomaly['type']}",
                                priority=InsightPriority.HIGH
                                if anomaly["severity"] == "critical"
                                else InsightPriority.MEDIUM,
                                title=f"Audit Alert: {anomaly['description']}",
                                summary=anomaly["description"],
                                detail=anomaly["recommendation"],
                                suggested_actions=[
                                    SuggestedAction(
                                        action_type="review",
                                        label="Review Transaction",
                                        description="Examine the flagged journal entry for accuracy.",
                                    ),
                                    SuggestedAction(
                                        action_type="document",
                                        label="Document Finding",
                                        description="Record the investigation outcome in the audit file.",
                                    ),
                                ],
                                expires_at=datetime.now(UTC) + timedelta(days=14),
                                confidence=0.9,
                                data_snapshot=anomaly,
                            )
                        )

        except Exception as e:
            logger.error(f"Journal anomaly analysis failed for client {client_id}: {e}")

        return insights

    def _determine_priority(self, summary: dict) -> InsightPriority:
        """Determine insight priority from anomaly summary."""
        if summary["critical_count"] > 0:
            return InsightPriority.HIGH
        if summary["high_count"] > 0:
            return InsightPriority.MEDIUM
        return InsightPriority.LOW

    def _generate_title(self, summary: dict) -> str:
        """Generate insight title."""
        total = summary["total_anomalies"]
        if summary["critical_count"] > 0:
            return f"Critical: {total} Journal Entries Require Immediate Review"
        if summary["high_count"] > 0:
            return f"Attention: {total} Journal Entries Flagged for Review"
        return f"Info: {total} Journal Entries Have Minor Flags"

    def _generate_summary(self, summary: dict) -> str:
        """Generate insight summary."""
        parts = []
        parts.append(
            f"Detected {summary['total_anomalies']} journal entries "
            f"with potential issues over the last 90 days."
        )

        if summary["critical_count"] > 0:
            parts.append(
                f"{summary['critical_count']} critical issue(s) require immediate attention."
            )
        if summary["high_count"] > 0:
            parts.append(f"{summary['high_count']} high-priority item(s) should be reviewed.")

        amount = summary["total_amount_flagged"]
        if amount > 0:
            parts.append(f"Total value of flagged transactions: ${amount:,.2f}.")

        return " ".join(parts)

    def _generate_detail(self, summary: dict) -> str:
        """Generate detailed insight description."""
        lines = ["### Journal Anomaly Analysis Results\n"]

        by_type = summary.get("by_type", {})
        if by_type:
            lines.append("**Issues by Type:**")
            for type_name, count in by_type.items():
                readable_name = type_name.replace("_", " ").title()
                lines.append(f"- {readable_name}: {count}")

        lines.append("\n**Top Findings:**")
        for anomaly in summary.get("top_anomalies", [])[:5]:
            lines.append(f"- [{anomaly['severity'].upper()}] {anomaly['description']}")

        return "\n".join(lines)

    def _generate_actions(self, summary: dict) -> list[SuggestedAction]:
        """Generate suggested actions based on findings."""
        actions = []

        if summary["critical_count"] > 0 or summary["high_count"] > 0:
            actions.append(
                SuggestedAction(
                    action_type="review",
                    label="Review Critical Items",
                    description="Examine high-priority journal entries immediately.",
                )
            )

        if summary.get("by_type", {}).get("manual_override", 0) > 0:
            actions.append(
                SuggestedAction(
                    action_type="verify",
                    label="Verify Manual Journals",
                    description="Confirm all manual journals have proper authorization.",
                )
            )

        if summary.get("by_type", {}).get("weekend_entry", 0) > 0:
            actions.append(
                SuggestedAction(
                    action_type="investigate",
                    label="Review Weekend Entries",
                    description="Verify weekend journal entries are legitimate.",
                )
            )

        actions.append(
            SuggestedAction(
                action_type="document",
                label="Document Review",
                description="Record findings in the audit working papers.",
            )
        )

        return actions
