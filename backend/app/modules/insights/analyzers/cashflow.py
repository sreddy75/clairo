"""Cash flow analyzer for detecting cash flow insights.

Detects:
- Overdue receivables spike (AR aging > 30 days)
- Cash flow warnings (negative trend)
- Large outstanding payables
"""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.insights.analyzers.base import BaseAnalyzer
from app.modules.insights.models import InsightCategory, InsightPriority
from app.modules.insights.schemas import InsightCreate, SuggestedAction
from app.modules.knowledge.aggregation_models import (
    ClientAPAgingSummary,
    ClientARAgingSummary,
    ClientMonthlyTrend,
)

logger = logging.getLogger(__name__)

# Thresholds
AR_OVERDUE_WARNING_PERCENT = 30  # Warn if >30% is overdue
AR_OVERDUE_CRITICAL_PERCENT = 50  # Critical if >50% is overdue
AP_CONCENTRATION_WARNING = Decimal("10000")  # Warn if large AP due soon


class CashFlowAnalyzer(BaseAnalyzer):
    """Analyzer for cash flow insights."""

    def __init__(self, db: AsyncSession):
        super().__init__(db)

    @property
    def category(self) -> InsightCategory:
        return InsightCategory.CASH_FLOW

    async def analyze_client(
        self,
        tenant_id: UUID,  # noqa: ARG002 - Required by interface
        client_id: UUID,
    ) -> list[InsightCreate]:
        """Analyze a client for cash flow issues."""
        insights: list[InsightCreate] = []

        # Check AR aging
        ar_insight = await self._check_ar_aging(client_id)
        if ar_insight:
            insights.append(ar_insight)

        # Check AP aging
        ap_insight = await self._check_ap_aging(client_id)
        if ap_insight:
            insights.append(ap_insight)

        # Check cash flow trend
        trend_insight = await self._check_cash_flow_trend(client_id)
        if trend_insight:
            insights.append(trend_insight)

        return insights

    async def _get_ar_aging(self, client_id: UUID) -> ClientARAgingSummary | None:
        """Get the latest AR aging summary."""
        result = await self.db.execute(
            select(ClientARAgingSummary)
            .where(ClientARAgingSummary.connection_id == client_id)
            .order_by(ClientARAgingSummary.as_of_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_ap_aging(self, client_id: UUID) -> ClientAPAgingSummary | None:
        """Get the latest AP aging summary."""
        result = await self.db.execute(
            select(ClientAPAgingSummary)
            .where(ClientAPAgingSummary.connection_id == client_id)
            .order_by(ClientAPAgingSummary.as_of_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_monthly_trends(
        self, client_id: UUID, months: int = 3
    ) -> list[ClientMonthlyTrend]:
        """Get recent monthly trends."""
        # Calculate cutoff year/month
        now = datetime.now(UTC)
        cutoff_year = now.year
        cutoff_month = now.month - months
        if cutoff_month <= 0:
            cutoff_year -= 1
            cutoff_month += 12

        result = await self.db.execute(
            select(ClientMonthlyTrend)
            .where(
                ClientMonthlyTrend.connection_id == client_id,
                # Filter by year and month
                (
                    (ClientMonthlyTrend.year > cutoff_year)
                    | (
                        (ClientMonthlyTrend.year == cutoff_year)
                        & (ClientMonthlyTrend.month >= cutoff_month)
                    )
                ),
            )
            .order_by(ClientMonthlyTrend.year.desc(), ClientMonthlyTrend.month.desc())
            .limit(months)
        )
        return list(result.scalars().all())

    async def _check_ar_aging(self, client_id: UUID) -> InsightCreate | None:
        """Check for problematic AR aging."""
        ar = await self._get_ar_aging(client_id)
        if not ar:
            return None

        # Use total_outstanding from the model or calculate from parts
        total_ar = ar.total_outstanding or Decimal(0)

        if total_ar <= 0:
            return None

        # Calculate overdue amount (>30 days)
        overdue = (
            (ar.days_31_60 or Decimal(0))
            + (ar.days_61_90 or Decimal(0))
            + (ar.over_90_days or Decimal(0))
        )

        overdue_percent = (overdue / total_ar * 100) if total_ar > 0 else 0

        if overdue_percent < AR_OVERDUE_WARNING_PERCENT:
            return None

        if overdue_percent >= AR_OVERDUE_CRITICAL_PERCENT:
            priority = InsightPriority.HIGH
            title = "Critical: High Overdue Receivables"
            summary = (
                f"${overdue:,.0f} ({overdue_percent:.0f}%) of receivables overdue >30 days — "
                f"exceeds the {AR_OVERDUE_CRITICAL_PERCENT}% critical threshold."
            )
        else:
            priority = InsightPriority.MEDIUM
            title = "Overdue Receivables Rising"
            summary = (
                f"${overdue:,.0f} ({overdue_percent:.0f}%) of receivables overdue >30 days — "
                f"exceeds the {AR_OVERDUE_WARNING_PERCENT}% warning threshold."
            )

        return InsightCreate(
            category=InsightCategory.CASH_FLOW,
            insight_type="overdue_receivables",
            priority=priority,
            title=title,
            summary=summary,
            detail=self._ar_detail(ar, total_ar, overdue, overdue_percent),
            suggested_actions=[
                SuggestedAction(
                    label="Review Receivables", url=f"/clients/{client_id}/receivables"
                ),
                SuggestedAction(label="Send Reminders", action="send_ar_reminders"),
            ],
            related_url=f"/clients/{client_id}/receivables",
            confidence=0.90,
            data_snapshot={
                "total_ar": float(total_ar),
                "overdue_amount": float(overdue),
                "overdue_percent": float(overdue_percent),
                "days_over_90": float(ar.over_90_days or 0),
                "threshold_warning_pct": AR_OVERDUE_WARNING_PERCENT,
                "threshold_critical_pct": AR_OVERDUE_CRITICAL_PERCENT,
            },
        )

    def _ar_detail(
        self,
        ar: ClientARAgingSummary,
        total: Decimal,
        overdue: Decimal,
        overdue_pct: float,
    ) -> str:
        """Generate detailed AR analysis."""
        return f"""## Accounts Receivable Analysis

- **Total Outstanding**: ${total:,.2f}
- **Overdue (>30 days)**: ${overdue:,.2f} ({overdue_pct:.1f}%)

### Aging Breakdown

| Bucket | Amount | % of Total |
|--------|--------|------------|
| Current | ${ar.current_amount or 0:,.2f} | {((ar.current_amount or 0) / total * 100) if total else 0:.1f}% |
| 31-60 days | ${ar.days_31_60 or 0:,.2f} | {((ar.days_31_60 or 0) / total * 100) if total else 0:.1f}% |
| 61-90 days | ${ar.days_61_90 or 0:,.2f} | {((ar.days_61_90 or 0) / total * 100) if total else 0:.1f}% |
| Over 90 days | ${ar.over_90_days or 0:,.2f} | {((ar.over_90_days or 0) / total * 100) if total else 0:.1f}% |

### Recommended Actions

1. Review customers with balances >90 days
2. Send payment reminders for 30+ day balances
3. Consider offering early payment discounts
4. Evaluate credit policies for high-risk customers
"""

    async def _check_ap_aging(self, client_id: UUID) -> InsightCreate | None:
        """Check for large upcoming payables."""
        ap = await self._get_ap_aging(client_id)
        if not ap:
            return None

        # Check for large amounts due soon (current = not yet due)
        due_soon = ap.current_amount or Decimal(0)

        if due_soon < AP_CONCENTRATION_WARNING:
            return None

        return InsightCreate(
            category=InsightCategory.CASH_FLOW,
            insight_type="large_payables_due",
            priority=InsightPriority.MEDIUM,
            title=f"${due_soon:,.0f} Payables Due Soon",
            summary="Large payables due soon. Plan cash accordingly.",
            suggested_actions=[
                SuggestedAction(label="Review Payables", url=f"/clients/{client_id}/payables"),
            ],
            confidence=0.85,
            data_snapshot={
                "due_soon": float(due_soon),
                "current": float(ap.current_amount or 0),
                "total": float(ap.total_outstanding or 0),
            },
        )

    async def _check_cash_flow_trend(self, client_id: UUID) -> InsightCreate | None:
        """Check for negative cash flow trends."""
        trends = await self._get_monthly_trends(client_id, months=3)

        if len(trends) < 2:
            return None

        # Calculate net cash flow for each month
        cash_flows = []
        for t in trends:
            net = (t.revenue or Decimal(0)) - (t.expenses or Decimal(0))
            cash_flows.append(net)

        # Check if trending negative
        negative_months = sum(1 for cf in cash_flows if cf < 0)

        if negative_months < 2:
            return None

        avg_negative = sum(cf for cf in cash_flows if cf < 0) / negative_months

        return InsightCreate(
            category=InsightCategory.CASH_FLOW,
            insight_type="negative_cash_flow_trend",
            priority=InsightPriority.HIGH if negative_months >= 3 else InsightPriority.MEDIUM,
            title="Negative Cash Flow Trend",
            summary=(
                f"{negative_months} of last 3 months show negative cash flow "
                f"(avg ${avg_negative:,.0f}/month). Alert triggers at 2+ consecutive negative months."
            ),
            detail=self._cashflow_detail(trends, cash_flows),
            suggested_actions=[
                SuggestedAction(label="Review Expenses", url=f"/clients/{client_id}/expenses"),
                SuggestedAction(label="Cash Flow Forecast", action="generate_forecast"),
            ],
            confidence=0.80,
            data_snapshot={
                "negative_months": negative_months,
                "avg_negative": float(avg_negative),
                "cash_flows": [float(cf) for cf in cash_flows],
            },
        )

    def _cashflow_detail(
        self,
        trends: list[ClientMonthlyTrend],
        cash_flows: list[Decimal],
    ) -> str:
        """Generate detailed cash flow analysis."""
        import calendar

        detail = """## Cash Flow Analysis

### Monthly Breakdown

| Month | Revenue | Expenses | Net Cash Flow |
|-------|---------|----------|---------------|
"""
        for t, cf in zip(trends, cash_flows, strict=False):
            status = "🔴" if cf < 0 else "🟢"
            month_name = calendar.month_abbr[t.month]
            detail += f"| {month_name} {t.year} | ${t.revenue or 0:,.0f} | ${t.expenses or 0:,.0f} | {status} ${cf:,.0f} |\n"

        detail += """
### Recommendations

1. Review major expense categories for reduction opportunities
2. Accelerate receivables collection
3. Negotiate extended payment terms with suppliers
4. Consider short-term financing if needed
"""
        return detail
