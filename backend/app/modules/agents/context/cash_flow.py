"""Cash flow context builder for AI agents.

Spec 024: Credit Notes, Payments & Journals - User Story 4

Provides cash flow context to AI agents for analysis and insights.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.xero.service import PaymentAnalysisService


class CashFlowContextBuilder:
    """Build cash flow context for AI agents.

    Aggregates payment and invoice data to provide AI agents with
    cash flow insights for analysis and recommendations.

    Attributes:
        session: SQLAlchemy async session.
        payment_service: Payment analysis service.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the context builder.

        Args:
            session: SQLAlchemy async session.
        """
        self.session = session
        self.payment_service = PaymentAnalysisService(session)

    async def build_context(
        self,
        connection_id: UUID,
        period_months: int = 12,
    ) -> dict[str, Any]:
        """Build cash flow context for AI agents.

        Compiles comprehensive cash flow data including:
        - Payment statistics
        - Average days to collect receivables
        - Payment patterns
        - Trend indicators

        Args:
            connection_id: The Xero connection ID.
            period_months: Number of months of history to analyze.

        Returns:
            Dictionary with structured cash flow context.
        """
        # Calculate date range
        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(days=period_months * 30)

        # Get cash flow summary
        cash_flow_summary = await self.payment_service.get_cash_flow_summary(
            connection_id=connection_id,
            date_from=date_from,
            date_to=date_to,
        )

        # Get payment patterns
        payment_patterns = await self.payment_service.identify_payment_patterns(
            connection_id=connection_id,
            date_from=date_from,
            date_to=date_to,
        )

        # Get days to pay analysis
        days_to_pay = await self.payment_service.calculate_average_days_to_pay(
            connection_id=connection_id,
            date_from=date_from,
            date_to=date_to,
        )

        # Build context structure for AI
        context = {
            "type": "cash_flow_analysis",
            "period": {
                "from": date_from.isoformat(),
                "to": date_to.isoformat(),
                "months": period_months,
            },
            "summary": {
                "total_payments": cash_flow_summary["payments"]["total_count"],
                "total_payment_amount": cash_flow_summary["payments"]["total_amount"],
                "average_payment_amount": cash_flow_summary["payments"]["average_amount"],
            },
            "receivables": {
                "average_days_to_collect": cash_flow_summary["receivables"][
                    "average_days_to_collect"
                ],
                "median_days_to_collect": cash_flow_summary["receivables"][
                    "median_days_to_collect"
                ],
                "sample_size": cash_flow_summary["receivables"]["sample_size"],
            },
            "payment_patterns": {
                "recurring_amounts": payment_patterns["recurring_amounts"],
                "average_days_between_payments": payment_patterns["average_days_between_payments"],
                "common_payment_days": payment_patterns["common_days_of_month"],
            },
            "days_to_pay_analysis": {
                "average": days_to_pay["average_days"],
                "median": days_to_pay["median_days"],
                "range": {
                    "min": days_to_pay["min_days"],
                    "max": days_to_pay["max_days"],
                },
                "sample_size": days_to_pay["sample_size"],
            },
            "insights": self._generate_insights(
                cash_flow_summary,
                payment_patterns,
                days_to_pay,
            ),
        }

        return context

    def _generate_insights(
        self,
        cash_flow: dict[str, Any],
        patterns: dict[str, Any],
        days_to_pay: dict[str, Any],
    ) -> list[str]:
        """Generate insights from cash flow data.

        Analyzes the data to provide human-readable insights
        that AI agents can use or expand upon.

        Args:
            cash_flow: Cash flow summary data.
            patterns: Payment pattern data.
            days_to_pay: Days to pay analysis data.

        Returns:
            List of insight strings.
        """
        insights = []

        # Days to collect insight
        avg_days = cash_flow["receivables"]["average_days_to_collect"]
        if avg_days is not None:
            if avg_days > 45:
                insights.append(
                    f"Average collection time is {avg_days:.0f} days, which is longer than "
                    "the typical 30-day payment terms. Consider reviewing credit policies."
                )
            elif avg_days < 20:
                insights.append(
                    f"Excellent collection efficiency with an average of {avg_days:.0f} days "
                    "to receive payment."
                )

        # Payment frequency insight
        avg_interval = patterns.get("average_days_between_payments")
        if avg_interval is not None:
            if avg_interval <= 7:
                insights.append(
                    "Payments are received frequently, averaging less than a week apart."
                )
            elif avg_interval > 30:
                insights.append(
                    f"Payments are infrequent, averaging {avg_interval:.0f} days between payments."
                )

        # Recurring payment insight
        recurring = patterns.get("recurring_amounts", [])
        if recurring and len(recurring) >= 3:
            insights.append(
                f"Identified {len(recurring)} recurring payment amounts, suggesting "
                "regular customers or subscription-based revenue."
            )

        # Common payment day insight
        common_days = patterns.get("common_days_of_month", [])
        if common_days:
            top_day = common_days[0]
            if top_day["occurrences"] >= 5:
                insights.append(
                    f"Payments commonly occur on day {top_day['day']} of the month "
                    f"({top_day['occurrences']} occurrences)."
                )

        return insights

    async def build_contact_context(
        self,
        connection_id: UUID,
        xero_contact_id: str,
        period_months: int = 12,
    ) -> dict[str, Any]:
        """Build cash flow context for a specific contact.

        Provides contact-specific payment behavior analysis.

        Args:
            connection_id: The Xero connection ID.
            xero_contact_id: The Xero contact ID.
            period_months: Number of months of history to analyze.

        Returns:
            Dictionary with contact-specific cash flow context.
        """
        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(days=period_months * 30)

        # Get days to pay for this specific contact
        days_to_pay = await self.payment_service.calculate_average_days_to_pay(
            connection_id=connection_id,
            xero_contact_id=xero_contact_id,
            date_from=date_from,
            date_to=date_to,
        )

        context = {
            "type": "contact_payment_analysis",
            "contact_id": xero_contact_id,
            "period": {
                "from": date_from.isoformat(),
                "to": date_to.isoformat(),
                "months": period_months,
            },
            "payment_behavior": {
                "average_days_to_pay": days_to_pay["average_days"],
                "median_days_to_pay": days_to_pay["median_days"],
                "fastest_payment": days_to_pay["min_days"],
                "slowest_payment": days_to_pay["max_days"],
                "invoices_analyzed": days_to_pay["sample_size"],
            },
            "risk_assessment": self._assess_payment_risk(days_to_pay),
        }

        return context

    def _assess_payment_risk(
        self,
        days_to_pay: dict[str, Any],
    ) -> dict[str, Any]:
        """Assess payment risk based on days to pay.

        Args:
            days_to_pay: Days to pay analysis data.

        Returns:
            Risk assessment dictionary.
        """
        avg_days = days_to_pay.get("average_days")
        sample_size = days_to_pay.get("sample_size", 0)

        if sample_size < 3:
            return {
                "level": "unknown",
                "reason": "Insufficient payment history for assessment",
                "confidence": "low",
            }

        if avg_days is None:
            return {
                "level": "unknown",
                "reason": "No payment data available",
                "confidence": "low",
            }

        if avg_days <= 30:
            return {
                "level": "low",
                "reason": "Consistently pays within standard terms",
                "confidence": "high" if sample_size >= 10 else "medium",
            }
        elif avg_days <= 45:
            return {
                "level": "medium",
                "reason": "Occasionally pays past standard terms",
                "confidence": "high" if sample_size >= 10 else "medium",
            }
        elif avg_days <= 60:
            return {
                "level": "elevated",
                "reason": "Regularly exceeds payment terms",
                "confidence": "high" if sample_size >= 10 else "medium",
            }
        else:
            return {
                "level": "high",
                "reason": f"Average payment takes {avg_days:.0f} days",
                "confidence": "high" if sample_size >= 10 else "medium",
            }
