"""Type definitions for Magic Zone Analyzer.

The Magic Zone routes high-value insights through the Multi-Agent
Orchestrator for cross-pillar analysis with OPTIONS format.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID


class MagicZoneTriggerType(str, Enum):
    """Types of triggers that route to Magic Zone analysis.

    These represent high-value scenarios where multi-agent
    analysis provides significantly better insights.
    """

    # GST threshold approaching - strategic decision point
    GST_THRESHOLD = "gst_threshold"

    # End of financial year planning window (May-June)
    EOFY_PLANNING = "eofy_planning"

    # Significant revenue change (>30%)
    REVENUE_CHANGE = "revenue_change"


@dataclass
class RevenueTrend:
    """Revenue trend analysis data.

    Captures current revenue metrics and changes for
    threshold and trend-based triggers.
    """

    current_annual_revenue: float
    previous_annual_revenue: float | None = None
    revenue_change_percent: float | None = None
    months_of_data: int = 0
    trend_direction: str = "stable"  # "up", "down", "stable"
    projected_annual_revenue: float | None = None


@dataclass
class MagicZoneTrigger:
    """A trigger that qualifies for Magic Zone analysis.

    Contains all context needed for the Multi-Agent Orchestrator
    to generate a comprehensive OPTIONS-format insight.
    """

    trigger_type: MagicZoneTriggerType
    client_id: UUID
    tenant_id: UUID

    # Trigger-specific context
    title: str
    description: str
    urgency: str = "medium"  # "high", "medium", "low"

    # Revenue data (if applicable)
    revenue_trend: RevenueTrend | None = None

    # EOFY context (if applicable)
    eofy_date: datetime | None = None
    days_until_eofy: int | None = None

    # GST context (if applicable)
    current_revenue: float | None = None
    gst_threshold: float = 75000.0
    distance_to_threshold: float | None = None

    # Query for orchestrator
    orchestrator_query: str = ""

    # Perspectives to use (defaults to all for Magic Zone)
    perspectives: list[str] = field(
        default_factory=lambda: ["compliance", "quality", "strategy", "insight"]
    )

    def __post_init__(self) -> None:
        """Build orchestrator query if not provided."""
        if not self.orchestrator_query:
            self.orchestrator_query = self._build_query()

    def _build_query(self) -> str:
        """Build the query to send to the orchestrator."""
        if self.trigger_type == MagicZoneTriggerType.GST_THRESHOLD:
            return self._build_gst_query()
        elif self.trigger_type == MagicZoneTriggerType.EOFY_PLANNING:
            return self._build_eofy_query()
        elif self.trigger_type == MagicZoneTriggerType.REVENUE_CHANGE:
            return self._build_revenue_change_query()
        return self.description

    def _build_gst_query(self) -> str:
        """Build query for GST threshold trigger."""
        revenue = self.current_revenue or 0
        distance = self.distance_to_threshold or (75000 - revenue)
        return (
            f"This client has annual revenue of ${revenue:,.0f}, which is ${distance:,.0f} "
            f"away from the $75,000 GST registration threshold. "
            f"What are the strategic options for managing GST registration timing? "
            f"Consider the pros and cons of voluntary early registration vs waiting."
        )

    def _build_eofy_query(self) -> str:
        """Build query for EOFY planning trigger."""
        days = self.days_until_eofy or 30
        return (
            f"End of financial year is in {days} days. "
            f"What tax planning opportunities should this client consider before EOFY? "
            f"Include options for timing income/expenses, super contributions, "
            f"asset purchases, and any compliance deadlines."
        )

    def _build_revenue_change_query(self) -> str:
        """Build query for revenue change trigger."""
        if self.revenue_trend:
            change = self.revenue_trend.revenue_change_percent or 0
            direction = "increase" if change > 0 else "decrease"
            return (
                f"This client has experienced a {abs(change):.0f}% revenue {direction}. "
                f"Current annual revenue: ${self.revenue_trend.current_annual_revenue:,.0f}. "
                f"What strategic options should the client consider to respond to this change? "
                f"Include implications for cash flow, staffing, tax planning, and growth strategy."
            )
        return self.description
