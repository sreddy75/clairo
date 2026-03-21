"""Journal analysis tools for AI agents.

Spec 024: Credit Notes, Payments & Journals - User Story 7

Provides tools for AI agents to analyze journal entries for audit insights.
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.analysis.journal_anomaly import JournalAnomalyDetector


async def get_journal_anomalies_tool(
    session: AsyncSession,
    connection_id: UUID,
    months: int = 12,
) -> str:
    """Detect anomalies in journal entries.

    Tool for AI agents to identify unusual journal patterns
    that may require review.

    Args:
        session: Database session.
        connection_id: The Xero connection ID.
        months: Number of months of history to analyze.

    Returns:
        JSON string with anomaly analysis.
    """
    detector = JournalAnomalyDetector(session)

    date_to = datetime.now(UTC)
    date_from = date_to - timedelta(days=months * 30)

    summary = await detector.get_anomaly_summary(
        connection_id=connection_id,
        date_from=date_from,
        date_to=date_to,
    )

    result = {
        "type": "journal_anomaly_analysis",
        "period": {
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
            "months": months,
        },
        "summary": summary,
        "insights": _generate_anomaly_insights(summary),
    }

    return json.dumps(result, indent=2)


async def get_audit_risk_score_tool(
    session: AsyncSession,
    connection_id: UUID,
    months: int = 12,
) -> str:
    """Calculate audit risk score based on journal patterns.

    Tool for AI agents to assess overall audit risk.

    Args:
        session: Database session.
        connection_id: The Xero connection ID.
        months: Number of months of history to analyze.

    Returns:
        JSON string with risk score and breakdown.
    """
    detector = JournalAnomalyDetector(session)

    date_to = datetime.now(UTC)
    date_from = date_to - timedelta(days=months * 30)

    summary = await detector.get_anomaly_summary(
        connection_id=connection_id,
        date_from=date_from,
        date_to=date_to,
    )

    # Calculate risk score
    risk_score = _calculate_risk_score(summary)

    result = {
        "type": "audit_risk_assessment",
        "period": {
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
            "months": months,
        },
        "risk_score": risk_score,
        "breakdown": {
            "anomaly_count": summary["total_anomalies"],
            "critical_issues": summary["critical_count"],
            "high_issues": summary["high_count"],
            "amount_flagged": summary["total_amount_flagged"],
        },
        "recommendations": _generate_risk_recommendations(risk_score, summary),
    }

    return json.dumps(result, indent=2)


def _calculate_risk_score(summary: dict[str, Any]) -> dict[str, Any]:
    """Calculate risk score from anomaly summary.

    Args:
        summary: Anomaly summary data.

    Returns:
        Risk score with level and numeric value.
    """
    # Base score
    score = 0

    # Add points for anomalies
    score += summary.get("critical_count", 0) * 25
    score += summary.get("high_count", 0) * 15
    score += summary.get("by_severity", {}).get("medium", 0) * 5
    score += summary.get("by_severity", {}).get("low", 0) * 1

    # Cap at 100
    score = min(score, 100)

    # Determine level
    if score >= 75:
        level = "high"
        description = "Significant audit risk - immediate review recommended"
    elif score >= 50:
        level = "elevated"
        description = "Elevated audit risk - review within 30 days"
    elif score >= 25:
        level = "moderate"
        description = "Moderate audit risk - routine review advised"
    else:
        level = "low"
        description = "Low audit risk - standard monitoring sufficient"

    return {
        "score": score,
        "level": level,
        "description": description,
    }


def _generate_anomaly_insights(summary: dict[str, Any]) -> list[str]:
    """Generate insights from anomaly analysis.

    Args:
        summary: Anomaly summary data.

    Returns:
        List of insight strings.
    """
    insights = []

    total = summary.get("total_anomalies", 0)
    if total == 0:
        insights.append("No journal anomalies detected in the review period.")
        return insights

    insights.append(f"Identified {total} journal entries requiring attention.")

    # Critical/high findings
    critical = summary.get("critical_count", 0)
    high = summary.get("high_count", 0)
    if critical > 0:
        insights.append(f"URGENT: {critical} critical issue(s) require immediate review.")
    if high > 0:
        insights.append(f"{high} high-priority issue(s) should be reviewed soon.")

    # Type-specific insights
    by_type = summary.get("by_type", {})
    if by_type.get("large_amount", 0) > 0:
        insights.append(f"Found {by_type['large_amount']} large amount entries above threshold.")
    if by_type.get("weekend_entry", 0) > 0:
        insights.append(f"Found {by_type['weekend_entry']} journal entries on weekends.")
    if by_type.get("round_number", 0) > 0:
        insights.append(
            f"Found {by_type['round_number']} round number entries that may need verification."
        )
    if by_type.get("manual_override", 0) > 0:
        insights.append(
            f"Found {by_type['manual_override']} manual journal entries requiring authorization check."
        )

    # Total amount flagged
    amount = summary.get("total_amount_flagged", 0)
    if amount > 0:
        insights.append(f"Total value of flagged transactions: ${amount:,.2f}")

    return insights


def _generate_risk_recommendations(
    risk_score: dict[str, Any],
    summary: dict[str, Any],
) -> list[str]:
    """Generate recommendations based on risk score.

    Args:
        risk_score: Calculated risk score.
        summary: Anomaly summary data.

    Returns:
        List of recommendation strings.
    """
    recommendations = []
    level = risk_score.get("level", "low")

    if level == "high":
        recommendations.append(
            "Schedule immediate review of all critical and high-priority findings."
        )
        recommendations.append(
            "Consider engaging external audit support for independent verification."
        )
    elif level == "elevated":
        recommendations.append("Schedule review of high-priority findings within the next 30 days.")
        recommendations.append("Implement additional controls for manual journal entries.")
    elif level == "moderate":
        recommendations.append("Include flagged items in next routine audit review.")
    else:
        recommendations.append("Continue standard monitoring procedures.")

    # Specific recommendations based on anomaly types
    by_type = summary.get("by_type", {})
    if by_type.get("weekend_entry", 0) >= 5:
        recommendations.append(
            "Review policy on weekend transactions and ensure proper authorization."
        )
    if by_type.get("manual_override", 0) >= 10:
        recommendations.append(
            "High volume of manual journals - consider implementing dual authorization."
        )
    if by_type.get("round_number", 0) >= 5:
        recommendations.append("Verify round number entries have supporting documentation.")

    return recommendations


# Tool definitions for LangChain/LangGraph integration
JOURNAL_ANALYSIS_TOOLS = [
    {
        "name": "get_journal_anomalies",
        "description": (
            "Analyze journal entries to detect anomalies that may indicate errors "
            "or require audit attention. Identifies large amounts, weekend entries, "
            "round numbers, and manual overrides. Use when asked about audit risk, "
            "unusual transactions, or journal review."
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
        "name": "get_audit_risk_score",
        "description": (
            "Calculate an overall audit risk score based on journal patterns. "
            "Returns a score from 0-100 with risk level (low/moderate/elevated/high) "
            "and specific recommendations. Use when asked about audit health or risk."
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
