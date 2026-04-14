"""Payment analysis service — analytics for AI agent context (days to pay, cash flow, recurring patterns)."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .repository import XeroInvoiceRepository, XeroPaymentRepository

logger = logging.getLogger(__name__)


class PaymentAnalysisService:
    """Service for payment analysis and cash flow insights.

    Spec 024: Credit Notes, Payments & Journals - User Story 4
    Provides payment analytics for AI agent context.

    Attributes:
        session: SQLAlchemy async session.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the payment analysis service.

        Args:
            session: SQLAlchemy async session.
        """
        self.session = session
        self.payment_repo = XeroPaymentRepository(session)
        self.invoice_repo = XeroInvoiceRepository(session)

    async def calculate_average_days_to_pay(
        self,
        connection_id: UUID,
        xero_contact_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        """Calculate average days to pay for invoices.

        For each paid invoice, calculates the number of days between
        invoice issue date and payment date. Returns aggregate statistics.

        Args:
            connection_id: The Xero connection ID.
            xero_contact_id: Optional contact to filter by.
            date_from: Optional start date filter.
            date_to: Optional end date filter.

        Returns:
            Dictionary with:
            - average_days: Average days to pay
            - median_days: Median days to pay
            - min_days: Minimum days to pay
            - max_days: Maximum days to pay
            - sample_size: Number of invoices analyzed
            - payment_patterns: List of (invoice_date, payment_date, days) tuples
        """
        # Get paid invoices with payments
        invoices, _ = await self.invoice_repo.list_by_connection(
            connection_id=connection_id,
            xero_contact_id=xero_contact_id,
            status="PAID",
            date_from=date_from.date() if date_from else None,
            date_to=date_to.date() if date_to else None,
            limit=500,  # Reasonable limit for analysis
        )

        if not invoices:
            return {
                "average_days": None,
                "median_days": None,
                "min_days": None,
                "max_days": None,
                "sample_size": 0,
                "payment_patterns": [],
            }

        # Calculate days to pay for each invoice
        days_list: list[int] = []
        payment_patterns: list[dict[str, Any]] = []

        for invoice in invoices:
            if invoice.fully_paid_on_date and invoice.issue_date:
                days = (invoice.fully_paid_on_date - invoice.issue_date).days
                if days >= 0:  # Only include valid positive values
                    days_list.append(days)
                    payment_patterns.append(
                        {
                            "invoice_date": invoice.issue_date.isoformat(),
                            "payment_date": invoice.fully_paid_on_date.isoformat(),
                            "days_to_pay": days,
                            "amount": float(invoice.total_amount),
                        }
                    )

        if not days_list:
            return {
                "average_days": None,
                "median_days": None,
                "min_days": None,
                "max_days": None,
                "sample_size": 0,
                "payment_patterns": [],
            }

        # Calculate statistics
        sorted_days = sorted(days_list)
        average_days = sum(days_list) / len(days_list)
        median_days = sorted_days[len(sorted_days) // 2]

        return {
            "average_days": round(average_days, 1),
            "median_days": median_days,
            "min_days": min(days_list),
            "max_days": max(days_list),
            "sample_size": len(days_list),
            "payment_patterns": payment_patterns[:20],  # Return top 20 for context
        }

    async def get_cash_flow_summary(
        self,
        connection_id: UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        """Get cash flow summary for a connection.

        Analyzes incoming and outgoing payments to provide
        cash flow insights for AI agents.

        Args:
            connection_id: The Xero connection ID.
            date_from: Optional start date filter.
            date_to: Optional end date filter.

        Returns:
            Dictionary with cash flow summary data.
        """
        # Get payment statistics
        payment_stats = await self.payment_repo.get_payment_stats_by_connection(
            connection_id=connection_id,
            date_from=date_from,
            date_to=date_to,
        )

        # Get average days to pay for receivables
        receivables_analysis = await self.calculate_average_days_to_pay(
            connection_id=connection_id,
            date_from=date_from,
            date_to=date_to,
        )

        return {
            "period": {
                "from": date_from.isoformat() if date_from else None,
                "to": date_to.isoformat() if date_to else None,
            },
            "payments": {
                "total_count": payment_stats["payment_count"],
                "total_amount": float(payment_stats["total_amount"]),
                "average_amount": float(payment_stats["average_amount"]),
                "earliest": payment_stats["earliest_payment"].isoformat()
                if payment_stats["earliest_payment"]
                else None,
                "latest": payment_stats["latest_payment"].isoformat()
                if payment_stats["latest_payment"]
                else None,
            },
            "receivables": {
                "average_days_to_collect": receivables_analysis["average_days"],
                "median_days_to_collect": receivables_analysis["median_days"],
                "sample_size": receivables_analysis["sample_size"],
            },
        }

    async def identify_payment_patterns(
        self,
        connection_id: UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        """Identify recurring payment patterns.

        Analyzes payment history to identify:
        - Regular payment schedules
        - Common payment amounts
        - Seasonal patterns

        Args:
            connection_id: The Xero connection ID.
            date_from: Optional start date filter.
            date_to: Optional end date filter.

        Returns:
            Dictionary with identified payment patterns.
        """
        payments, _ = await self.payment_repo.list_by_connection(
            connection_id=connection_id,
            date_from=date_from,
            date_to=date_to,
            limit=200,
        )

        if not payments:
            return {
                "recurring_amounts": [],
                "payment_frequency": None,
                "common_days_of_month": [],
            }

        # Analyze payment amounts for recurring patterns
        amount_counts: dict[Decimal, int] = {}
        day_of_month_counts: dict[int, int] = {}

        for payment in payments:
            # Round amount to nearest dollar for pattern matching
            rounded_amount = round(payment.amount)
            amount_counts[rounded_amount] = amount_counts.get(rounded_amount, 0) + 1

            # Track day of month
            day = payment.payment_date.day
            day_of_month_counts[day] = day_of_month_counts.get(day, 0) + 1

        # Find recurring amounts (appear 3+ times)
        recurring_amounts = [
            {"amount": float(amount), "occurrences": count}
            for amount, count in sorted(amount_counts.items(), key=lambda x: x[1], reverse=True)
            if count >= 3
        ][:10]  # Top 10

        # Find common days of month
        common_days = [
            {"day": day, "occurrences": count}
            for day, count in sorted(day_of_month_counts.items(), key=lambda x: x[1], reverse=True)
        ][:5]  # Top 5

        # Calculate average payment frequency
        if len(payments) >= 2:
            dates = sorted([p.payment_date for p in payments])
            intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
            avg_interval = sum(intervals) / len(intervals) if intervals else None
        else:
            avg_interval = None

        return {
            "recurring_amounts": recurring_amounts,
            "average_days_between_payments": round(avg_interval, 1) if avg_interval else None,
            "common_days_of_month": common_days,
            "total_payments_analyzed": len(payments),
        }
