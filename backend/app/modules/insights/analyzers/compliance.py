"""Compliance analyzer for detecting compliance-related insights.

Detects:
- GST threshold approaching (not registered, revenue > $65K)
- BAS deadline approaching (due < 7 days)
- Super guarantee due dates
"""

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.insights.analyzers.base import BaseAnalyzer
from app.modules.insights.models import InsightCategory, InsightPriority
from app.modules.insights.schemas import InsightCreate, SuggestedAction
from app.modules.knowledge.aggregation_models import (
    ClientAIProfile,
    ClientMonthlyTrend,
)

logger = logging.getLogger(__name__)

# GST threshold in Australia
GST_THRESHOLD = Decimal("75000")
GST_WARNING_THRESHOLD = Decimal("65000")  # Warn when approaching


class ComplianceAnalyzer(BaseAnalyzer):
    """Analyzer for compliance-related insights."""

    def __init__(self, db: AsyncSession):
        super().__init__(db)

    @property
    def category(self) -> InsightCategory:
        return InsightCategory.COMPLIANCE

    async def analyze_client(
        self,
        tenant_id: UUID,  # noqa: ARG002 - Required by interface
        client_id: UUID,
    ) -> list[InsightCreate]:
        """Analyze a client for compliance issues."""
        insights: list[InsightCreate] = []

        # Get client profile
        profile = await self._get_profile(client_id)
        if not profile:
            return insights

        # Check GST threshold
        gst_insight = await self._check_gst_threshold(client_id, profile)
        if gst_insight:
            insights.append(gst_insight)

        # Check BAS deadlines
        bas_insight = await self._check_bas_deadline(client_id)
        if bas_insight:
            insights.append(bas_insight)

        # Check super guarantee
        super_insight = self._check_super_guarantee(client_id, profile)
        if super_insight:
            insights.append(super_insight)

        return insights

    async def _get_profile(self, client_id: UUID) -> ClientAIProfile | None:
        """Get client AI profile."""
        result = await self.db.execute(
            select(ClientAIProfile).where(ClientAIProfile.connection_id == client_id)
        )
        return result.scalar_one_or_none()

    async def _check_gst_threshold(
        self,
        client_id: UUID,
        profile: ClientAIProfile,
    ) -> InsightCreate | None:
        """Check if client is approaching GST registration threshold."""
        # Skip if already registered (primary check via AI profile)
        if profile.gst_registered:
            return None

        # Secondary guard: if the client has a gst_reporting_basis set in Clairo,
        # they are already registered for GST — do not show the threshold insight.
        # ClientAIProfile.gst_registered may lag behind actual registration status.
        from sqlalchemy import select as _select

        from app.modules.clients.models import PracticeClient

        pc_result = await self.db.execute(
            _select(PracticeClient.gst_reporting_basis).where(
                PracticeClient.xero_connection_id == client_id
            )
        )
        row = pc_result.first()
        if row and row[0] is not None:
            return None

        # Get annual revenue from trends
        annual_revenue = await self._get_annual_revenue(client_id)
        if annual_revenue is None or annual_revenue < GST_WARNING_THRESHOLD:
            return None

        # Calculate months to threshold
        monthly_trend = await self._get_revenue_trend(client_id)
        months_to_threshold = None
        if monthly_trend and monthly_trend > 0:
            remaining = GST_THRESHOLD - annual_revenue
            months_to_threshold = int(remaining / monthly_trend) if monthly_trend > 0 else None

        # Determine priority
        if annual_revenue >= GST_THRESHOLD:
            priority = InsightPriority.HIGH
            title = "GST Registration Required"
            summary = (
                f"Revenue ${annual_revenue:,.0f} exceeds the mandatory GST registration "
                f"threshold of ${GST_THRESHOLD:,.0f}. Registration required within 21 days."
            )
        elif months_to_threshold and months_to_threshold <= 2:
            priority = InsightPriority.HIGH
            title = "GST Threshold Imminent"
            summary = (
                f"Revenue ${annual_revenue:,.0f}, projected to hit the ${GST_THRESHOLD:,.0f} "
                f"GST threshold in ~{months_to_threshold} months."
            )
        else:
            priority = InsightPriority.MEDIUM
            title = "GST Threshold Approaching"
            time_estimate = f" in ~{months_to_threshold} months" if months_to_threshold else ""
            summary = (
                f"Revenue ${annual_revenue:,.0f} has passed the ${GST_WARNING_THRESHOLD:,.0f} "
                f"early-warning level, approaching the ${GST_THRESHOLD:,.0f} threshold{time_estimate}."
            )

        return InsightCreate(
            category=InsightCategory.COMPLIANCE,
            insight_type="gst_threshold_approaching",
            priority=priority,
            title=title,
            summary=summary,
            detail=self._gst_detail(annual_revenue, monthly_trend, months_to_threshold),
            suggested_actions=[
                SuggestedAction(label="Review GST Options", url=f"/clients/{client_id}"),
                SuggestedAction(label="Discuss with Client", action="schedule_meeting"),
            ],
            related_url=f"/clients/{client_id}",
            confidence=0.85,
            data_snapshot={
                "annual_revenue": float(annual_revenue),
                "monthly_trend": float(monthly_trend) if monthly_trend else None,
                "months_to_threshold": months_to_threshold,
                "gst_registered": False,
                "threshold_gst_registration": float(GST_THRESHOLD),
                "threshold_gst_warning": float(GST_WARNING_THRESHOLD),
            },
        )

    def _gst_detail(
        self,
        revenue: Decimal,
        trend: Decimal | None,
        months: int | None,
    ) -> str:
        """Generate detailed GST threshold analysis."""
        detail = f"""## GST Registration Analysis

**Current Annual Revenue**: ${revenue:,.2f}
**GST Threshold**: $75,000

"""
        if trend:
            detail += f"**Monthly Revenue Trend**: ${trend:,.2f}/month\n"
        if months:
            detail += f"**Estimated Time to Threshold**: ~{months} months\n"

        detail += """
### Key Points

1. GST registration is **mandatory** when turnover exceeds $75,000 in a 12-month period
2. Must register **within 21 days** of reaching the threshold
3. Once registered, must charge GST on taxable sales

### Options to Discuss

- **Register now**: Allows claiming input tax credits on purchases
- **Wait until threshold**: Delay charging GST to customers
- **Review pricing strategy**: May need to adjust prices post-registration
"""
        return detail

    async def _check_bas_deadline(self, client_id: UUID) -> InsightCreate | None:
        """Check for upcoming BAS deadlines."""
        # Calculate current quarter BAS due date
        today = datetime.now(UTC).date()
        quarter = (today.month - 1) // 3 + 1
        year = today.year

        # BAS due dates: 28th of month after quarter end
        # Q1 (Jul-Sep) due 28 Oct, Q2 (Oct-Dec) due 28 Feb, etc.
        quarter_end_months = {1: 10, 2: 2, 3: 5, 4: 8}  # FY quarters
        due_month = quarter_end_months.get(quarter, 10)
        due_year = year if due_month > today.month else year + 1
        due_date = date(due_year, due_month, 28)

        days_until = (due_date - today).days

        if days_until > 14:
            return None  # Not urgent

        # Check if BAS exists for this period (would need BAS session check)
        # For now, just warn about the deadline

        if days_until <= 0:
            priority = InsightPriority.HIGH
            title = "BAS Overdue"
            summary = f"Q{quarter} BAS was due {due_date.strftime('%d %b %Y')}."
        elif days_until <= 7:
            priority = InsightPriority.HIGH
            title = f"BAS Due in {days_until} Days"
            summary = f"Q{quarter} BAS due {due_date.strftime('%d %b %Y')}. Prepare now."
        else:
            priority = InsightPriority.MEDIUM
            title = f"BAS Due in {days_until} Days"
            summary = f"Q{quarter} BAS due {due_date.strftime('%d %b %Y')}."

        return InsightCreate(
            category=InsightCategory.COMPLIANCE,
            insight_type="bas_deadline_approaching",
            priority=priority,
            title=title,
            summary=summary,
            suggested_actions=[
                SuggestedAction(label="Prepare BAS", url=f"/clients/{client_id}/bas"),
            ],
            related_url=f"/clients/{client_id}/bas",
            confidence=0.95,
            expires_at=datetime.combine(due_date + timedelta(days=7), datetime.min.time()).replace(
                tzinfo=UTC
            ),
            data_snapshot={
                "quarter": quarter,
                "year": year,
                "due_date": due_date.isoformat(),
                "days_until": days_until,
            },
        )

    def _check_super_guarantee(
        self,
        client_id: UUID,
        profile: ClientAIProfile,
    ) -> InsightCreate | None:
        """Check for super guarantee due dates."""
        if profile.employee_count == 0:
            return None

        # Super is due 28 days after quarter end
        today = datetime.now(UTC).date()
        quarter = (today.month - 1) // 3 + 1

        # Quarter end dates
        quarter_ends = {
            1: date(today.year, 3, 31),
            2: date(today.year, 6, 30),
            3: date(today.year, 9, 30),
            4: date(today.year, 12, 31),
        }

        # Find next relevant quarter end
        for q in range(quarter, 5):
            qe = quarter_ends.get(q)
            if qe and qe >= today:
                due_date = qe + timedelta(days=28)
                days_until = (due_date - today).days

                if days_until <= 14:
                    priority = InsightPriority.MEDIUM if days_until > 7 else InsightPriority.HIGH
                    return InsightCreate(
                        category=InsightCategory.COMPLIANCE,
                        insight_type="super_guarantee_due",
                        priority=priority,
                        title=f"Super Guarantee Due in {days_until} Days",
                        summary=f"Q{q} super for {profile.employee_count} employees due {due_date.strftime('%d %b')}.",
                        suggested_actions=[
                            SuggestedAction(
                                label="Review Payroll", url=f"/clients/{client_id}/payroll"
                            ),
                        ],
                        confidence=0.90,
                        data_snapshot={
                            "quarter": q,
                            "employee_count": profile.employee_count,
                            "due_date": due_date.isoformat(),
                        },
                    )
                break

        return None

    async def _get_annual_revenue(self, client_id: UUID) -> Decimal | None:
        """Get estimated annual revenue from monthly trends."""
        # Sum last 12 months of revenue
        today = datetime.now(UTC).date()
        twelve_months_ago = today - timedelta(days=365)
        start_year = twelve_months_ago.year
        start_month = twelve_months_ago.month

        # Compare using year/month integers, not date
        result = await self.db.execute(
            select(func.sum(ClientMonthlyTrend.revenue)).where(
                ClientMonthlyTrend.connection_id == client_id,
                (
                    (ClientMonthlyTrend.year > start_year)
                    | (
                        (ClientMonthlyTrend.year == start_year)
                        & (ClientMonthlyTrend.month >= start_month)
                    )
                ),
            )
        )
        total = result.scalar()
        return Decimal(str(total)) if total else None

    async def _get_revenue_trend(self, client_id: UUID) -> Decimal | None:
        """Get average monthly revenue trend."""
        today = datetime.now(UTC).date()
        three_months_ago = today - timedelta(days=90)
        start_year = three_months_ago.year
        start_month = three_months_ago.month

        # Compare using year/month integers, not date
        result = await self.db.execute(
            select(func.avg(ClientMonthlyTrend.revenue)).where(
                ClientMonthlyTrend.connection_id == client_id,
                (
                    (ClientMonthlyTrend.year > start_year)
                    | (
                        (ClientMonthlyTrend.year == start_year)
                        & (ClientMonthlyTrend.month >= start_month)
                    )
                ),
            )
        )
        avg = result.scalar()
        return Decimal(str(avg)) if avg else None
