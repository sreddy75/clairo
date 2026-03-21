"""Payment-based tools for AI agents.

Spec 024: Credit Notes, Payments & Journals - User Story 4

Provides tools for AI agents to analyze payment data for cash flow insights.
These tools are designed to be used with LangChain/LangGraph agents.
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.context.cash_flow import CashFlowContextBuilder
from app.modules.integrations.xero.service import PaymentAnalysisService


async def get_cash_flow_summary_tool(
    session: AsyncSession,
    connection_id: UUID,
    months: int = 12,
) -> str:
    """Get cash flow summary for a client.

    Tool for AI agents to retrieve cash flow summary data.

    Args:
        session: Database session.
        connection_id: The Xero connection ID.
        months: Number of months of history to analyze.

    Returns:
        JSON string with cash flow summary.
    """
    context_builder = CashFlowContextBuilder(session)
    context = await context_builder.build_context(
        connection_id=connection_id,
        period_months=months,
    )

    return json.dumps(context, indent=2)


async def get_contact_payment_behavior_tool(
    session: AsyncSession,
    connection_id: UUID,
    xero_contact_id: str,
    months: int = 12,
) -> str:
    """Get payment behavior analysis for a specific contact.

    Tool for AI agents to analyze how quickly a contact pays.

    Args:
        session: Database session.
        connection_id: The Xero connection ID.
        xero_contact_id: The Xero contact ID.
        months: Number of months of history to analyze.

    Returns:
        JSON string with contact payment behavior analysis.
    """
    context_builder = CashFlowContextBuilder(session)
    context = await context_builder.build_contact_context(
        connection_id=connection_id,
        xero_contact_id=xero_contact_id,
        period_months=months,
    )

    return json.dumps(context, indent=2)


async def get_payment_patterns_tool(
    session: AsyncSession,
    connection_id: UUID,
    months: int = 12,
) -> str:
    """Identify recurring payment patterns.

    Tool for AI agents to identify regular payments, common amounts,
    and payment schedules.

    Args:
        session: Database session.
        connection_id: The Xero connection ID.
        months: Number of months of history to analyze.

    Returns:
        JSON string with payment pattern analysis.
    """
    payment_service = PaymentAnalysisService(session)

    date_to = datetime.now(UTC)
    date_from = date_to - timedelta(days=months * 30)

    patterns = await payment_service.identify_payment_patterns(
        connection_id=connection_id,
        date_from=date_from,
        date_to=date_to,
    )

    result = {
        "type": "payment_pattern_analysis",
        "period": {
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
            "months": months,
        },
        "patterns": patterns,
        "insights": _generate_pattern_insights(patterns),
    }

    return json.dumps(result, indent=2)


def _generate_pattern_insights(patterns: dict[str, Any]) -> list[str]:
    """Generate insights from payment patterns.

    Args:
        patterns: Payment pattern data.

    Returns:
        List of insight strings.
    """
    insights = []

    recurring = patterns.get("recurring_amounts", [])
    if recurring:
        # Summarize recurring payments
        total_recurring = sum(r["amount"] * r["occurrences"] for r in recurring)
        insights.append(
            f"Identified {len(recurring)} recurring payment amounts "
            f"totaling ${total_recurring:,.2f} over the period."
        )

        # Highlight largest recurring
        if recurring[0]["occurrences"] >= 5:
            insights.append(
                f"Most common recurring payment: ${recurring[0]['amount']:,.2f} "
                f"({recurring[0]['occurrences']} times)."
            )

    common_days = patterns.get("common_days_of_month", [])
    if common_days and common_days[0]["occurrences"] >= 3:
        top_days = [str(d["day"]) for d in common_days[:3]]
        insights.append(
            f"Payments most commonly occur on days: {', '.join(top_days)} of the month."
        )

    avg_interval = patterns.get("average_days_between_payments")
    if avg_interval is not None:
        if avg_interval <= 7:
            insights.append("High payment velocity - payments received almost weekly.")
        elif avg_interval <= 14:
            insights.append("Regular payment flow - payments received bi-weekly on average.")
        elif avg_interval <= 30:
            insights.append("Standard monthly payment cycle observed.")
        else:
            insights.append(
                f"Infrequent payments - average of {avg_interval:.0f} days between payments."
            )

    return insights


# Tool definitions for LangChain/LangGraph integration
PAYMENT_TOOLS = [
    {
        "name": "get_cash_flow_summary",
        "description": (
            "Analyze cash flow for a client including total payments, "
            "average days to collect receivables, and payment patterns. "
            "Use when asked about cash flow, payment timing, or collection efficiency."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "connection_id": {
                    "type": "string",
                    "description": "The Xero connection ID (UUID)",
                },
                "months": {
                    "type": "integer",
                    "description": "Number of months of history to analyze (default 12)",
                    "default": 12,
                },
            },
            "required": ["connection_id"],
        },
    },
    {
        "name": "get_contact_payment_behavior",
        "description": (
            "Analyze payment behavior for a specific customer or supplier. "
            "Shows how quickly they pay, their payment risk level, and patterns. "
            "Use when asked about a specific contact's payment history."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "connection_id": {
                    "type": "string",
                    "description": "The Xero connection ID (UUID)",
                },
                "xero_contact_id": {
                    "type": "string",
                    "description": "The Xero contact ID",
                },
                "months": {
                    "type": "integer",
                    "description": "Number of months of history to analyze (default 12)",
                    "default": 12,
                },
            },
            "required": ["connection_id", "xero_contact_id"],
        },
    },
    {
        "name": "get_payment_patterns",
        "description": (
            "Identify recurring payment patterns including regular amounts, "
            "common payment days, and payment frequency. "
            "Use when looking for subscription revenue or regular payment schedules."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "connection_id": {
                    "type": "string",
                    "description": "The Xero connection ID (UUID)",
                },
                "months": {
                    "type": "integer",
                    "description": "Number of months of history to analyze (default 12)",
                    "default": 12,
                },
            },
            "required": ["connection_id"],
        },
    },
]
