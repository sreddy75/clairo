"""
A2UI Generator for Agent Responses

Analyzes query intent and response data to generate rich UI components
alongside text responses.
"""

import re
from typing import Any

from app.core.a2ui import (
    A2UIBuilder,
    A2UIMessage,
    DeviceContext,
    LayoutHint,
    Severity,
)

from .schemas import Perspective, PerspectiveResult

# =============================================================================
# Query Intent Detection
# =============================================================================

# Patterns that indicate financial/numeric queries
FINANCIAL_PATTERNS = [
    r"\bgst\s*(liability|payable|collected|amount)\b",
    r"\b(total|sum|amount)\s*(sales|purchases|expenses|revenue)\b",
    r"\b(calculate|compute|show)\s*(gst|tax|bas)\b",
    r"\boverdue\s*(invoices?|receivables?|debtors?)\b",
    r"\baging\s*(report|summary|breakdown)\b",
    r"\bcash\s*flow\b",
    r"\bprofit\s*(and\s*loss|margin)\b",
    r"\bbalance\s*sheet\b",
    r"\bexpense\s*(breakdown|categories|summary)\b",
]

# Patterns that indicate compliance/issue queries
COMPLIANCE_PATTERNS = [
    r"\bcompliance\s*(issues?|check|status)\b",
    r"\b(any|what)\s*(issues?|problems?|errors?)\b",
    r"\bpayg\s*(withheld|withholding)\b",
    r"\bsuper(annuation)?\s*(contributions?|guarantee)\b",
    r"\blodgement\s*(due|deadline|status)\b",
    r"\b(missing|incomplete)\s*(data|records?|transactions?)\b",
]

# Patterns that indicate list/table queries
LIST_PATTERNS = [
    r"\b(show|list|display)\s*(all|the)\b",
    r"\btop\s*\d+\b",
    r"\blargest\s*(expenses?|transactions?|invoices?)\b",
    r"\boverdue\s*(invoices?|receivables?)\b",
    r"\bwho\s*(owes?|are)\b",
]

# Patterns that indicate trend/chart queries
TREND_PATTERNS = [
    r"\btrend\b",
    r"\bover\s*(time|the\s*(past|last))\b",
    r"\b(monthly|quarterly|yearly)\s*(breakdown|summary)\b",
    r"\bcompare\b",
    r"\bgrowth\b",
]


def detect_query_intent(query: str) -> dict[str, bool]:
    """Detect the intent of a query to determine appropriate A2UI components."""
    query_lower = query.lower()
    return {
        "is_financial": any(re.search(p, query_lower) for p in FINANCIAL_PATTERNS),
        "is_compliance": any(re.search(p, query_lower) for p in COMPLIANCE_PATTERNS),
        "is_list": any(re.search(p, query_lower) for p in LIST_PATTERNS),
        "is_trend": any(re.search(p, query_lower) for p in TREND_PATTERNS),
    }


# =============================================================================
# Data Extraction from Response
# =============================================================================


def extract_currency_values(text: str) -> list[dict[str, Any]]:
    """Extract currency values from response text."""
    # Match patterns like $1,234.56 or $1234
    pattern = r"\$[\d,]+(?:\.\d{2})?"
    matches = re.findall(pattern, text)

    values = []
    for match in matches:
        # Clean and convert to float
        clean_value = match.replace("$", "").replace(",", "")
        try:
            values.append(
                {
                    "raw": match,
                    "value": float(clean_value),
                }
            )
        except ValueError:
            continue
    return values


def extract_percentages(text: str) -> list[dict[str, Any]]:
    """Extract percentage values from response text."""
    pattern = r"(\d+(?:\.\d+)?)\s*%"
    matches = re.findall(pattern, text)

    return [{"value": float(m), "raw": f"{m}%"} for m in matches]


def extract_counts(text: str) -> list[dict[str, Any]]:
    """Extract count values (e.g., '5 invoices', '3 clients')."""
    pattern = r"(\d+)\s+(invoices?|clients?|transactions?|items?|issues?|errors?)"
    matches = re.findall(pattern, text.lower())

    return [{"count": int(m[0]), "type": m[1]} for m in matches]


# =============================================================================
# A2UI Generation
# =============================================================================


class AgentA2UIGenerator:
    """Generates A2UI components based on query and response analysis."""

    def __init__(self, device_context: DeviceContext | None = None):
        self.device_context = device_context or DeviceContext(
            isMobile=False,
            isTablet=False,
        )

    def generate(
        self,
        query: str,
        content: str,
        perspectives_used: list[Perspective],
        perspective_results: list[PerspectiveResult],
        client_data: dict[str, Any] | None = None,
        confidence: float = 0.0,
        escalation_required: bool = False,
        escalation_reason: str | None = None,
    ) -> A2UIMessage | None:
        """Generate A2UI message based on query and response analysis.

        Returns None if no rich UI is appropriate for this response.
        """
        builder = A2UIBuilder(self.device_context)
        builder.set_agent_id("knowledge-assistant")
        builder.set_layout(LayoutHint.STACK)

        intent = detect_query_intent(query)
        has_components = False

        # Add escalation banner if needed
        if escalation_required:
            builder.add_alert(
                title="Professional Review Recommended",
                description=escalation_reason or "This query may require professional judgment.",
                severity=Severity.WARNING,
            )
            has_components = True

        # Add confidence indicator for low confidence
        if confidence < 0.7 and confidence > 0:
            builder.add_alert(
                title="Lower Confidence Response",
                description=f"Confidence: {confidence * 100:.0f}%. Consider verifying with primary sources.",
                severity=Severity.INFO,
            )
            has_components = True

        # Generate components based on query intent and available data
        if client_data:
            has_components = (
                self._add_client_components(builder, intent, content, client_data) or has_components
            )

        # Add perspective-specific components
        for result in perspective_results:
            if result.perspective == Perspective.COMPLIANCE:
                has_components = (
                    self._add_compliance_components(builder, result.content) or has_components
                )
            elif result.perspective == Perspective.INSIGHT:
                has_components = (
                    self._add_insight_components(builder, result.content, client_data)
                    or has_components
                )

        # Only return A2UI if we have meaningful components
        if not has_components:
            return None

        return builder.build(fallback_text=content[:200])

    def _add_client_components(
        self,
        builder: A2UIBuilder,
        intent: dict[str, bool],
        content: str,
        client_data: dict[str, Any],
    ) -> bool:
        """Add client-specific A2UI components."""
        added = False

        # Extract financial metrics from client data
        gst_collected = client_data.get("gst_collected", 0)
        gst_paid = client_data.get("gst_paid", 0)
        gst_period = client_data.get("gst_period", "")
        total_sales = client_data.get("total_sales", 0)
        total_purchases = client_data.get("total_purchases", 0)
        net_gst = gst_collected - gst_paid

        # Add stat cards for financial queries
        if intent["is_financial"] and (gst_collected or gst_paid or total_sales):
            # GST stat cards
            if gst_collected or gst_paid:
                period_suffix = f" ({gst_period})" if gst_period else ""
                builder.add_stat_card(
                    label=f"GST Collected (1A){period_suffix}",
                    value=f"${gst_collected:,.2f}",
                    icon="dollar-sign",
                )
                builder.add_stat_card(
                    label=f"GST Paid (1B){period_suffix}",
                    value=f"${gst_paid:,.2f}",
                    icon="receipt",
                )
                builder.add_stat_card(
                    label=f"Net GST Payable{period_suffix}",
                    value=f"${net_gst:,.2f}",
                    change_direction="up" if net_gst > 0 else "down",
                    icon="trending-up" if net_gst > 0 else "trending-down",
                )
                added = True

            # Sales/purchases breakdown
            if total_sales or total_purchases:
                builder.add_stat_card(
                    label="Total Sales",
                    value=f"${total_sales:,.2f}",
                    icon="arrow-up-right",
                )
                builder.add_stat_card(
                    label="Total Purchases",
                    value=f"${total_purchases:,.2f}",
                    icon="arrow-down-right",
                )
                added = True

        # Add expense breakdown chart if available
        expense_breakdown = client_data.get("expense_breakdown", [])
        if intent["is_financial"] and expense_breakdown:
            builder.add_bar_chart(
                data_key="expenseBreakdown",
                data=expense_breakdown,
                title="Expense Breakdown",
                orientation="horizontal",
            )
            added = True

        # Add overdue invoices table if available
        overdue_invoices = client_data.get("overdue_invoices", [])
        if intent["is_list"] and overdue_invoices:
            builder.add_data_table(
                data_key="overdueInvoices",
                data=overdue_invoices[:10],  # Limit to 10 rows
                columns=[
                    {"key": "contact_name", "label": "Customer", "sortable": True},
                    {"key": "invoice_number", "label": "Invoice #", "sortable": False},
                    {"key": "amount_due", "label": "Amount Due", "sortable": True},
                    {"key": "days_overdue", "label": "Days Overdue", "sortable": True},
                ],
                page_size=5,
            )
            added = True

        # Add trend chart if available
        monthly_data = client_data.get("monthly_summary", [])
        if intent["is_trend"] and monthly_data:
            builder.add_line_chart(
                data_key="monthlyTrend",
                data=monthly_data,
                title="Monthly Financial Trend",
                x_axis={"dataKey": "month"},
                y_axis={"format": "currency"},
                series=[
                    {"dataKey": "revenue", "name": "Revenue", "color": "hsl(142, 76%, 36%)"},
                    {"dataKey": "expenses", "name": "Expenses", "color": "hsl(0, 84%, 60%)"},
                    {"dataKey": "profit", "name": "Profit", "color": "hsl(221, 83%, 53%)"},
                ],
            )
            added = True

        return added

    def _add_compliance_components(
        self,
        builder: A2UIBuilder,
        content: str,
    ) -> bool:
        """Add compliance-related A2UI components."""
        added = False

        # Check for compliance issues mentioned in content
        issues = []

        if "missing" in content.lower():
            issues.append(("Missing Data", "Some records may be incomplete.", Severity.WARNING))
        if "overdue" in content.lower():
            issues.append(
                ("Overdue Items", "There are overdue lodgements or payments.", Severity.ERROR)
            )
        if "compliant" in content.lower() and "non" not in content.lower():
            issues.append(("Compliance Status", "Records appear compliant.", Severity.SUCCESS))

        for title, desc, severity in issues:
            builder.add_alert(
                title=title,
                description=desc,
                severity=severity,
            )
            added = True

        return added

    def _add_insight_components(
        self,
        builder: A2UIBuilder,
        content: str,
        client_data: dict[str, Any] | None,
    ) -> bool:
        """Add insight-related A2UI components."""
        added = False

        # Extract any percentages or growth metrics from content
        percentages = extract_percentages(content)

        for pct in percentages[:3]:  # Limit to 3 stat cards
            # Try to find context around the percentage
            value = pct["value"]
            if value > 0:
                builder.add_stat_card(
                    label="Growth/Change",
                    value=f"{value:.1f}%",
                    change_value=value,
                    change_direction="up" if value > 0 else "down",
                )
                added = True

        return added


def generate_agent_a2ui(
    query: str,
    content: str,
    perspectives_used: list[Perspective],
    perspective_results: list[PerspectiveResult],
    client_data: dict[str, Any] | None = None,
    confidence: float = 0.0,
    escalation_required: bool = False,
    escalation_reason: str | None = None,
    device_context: DeviceContext | None = None,
) -> A2UIMessage | None:
    """Convenience function to generate agent A2UI."""
    generator = AgentA2UIGenerator(device_context)
    return generator.generate(
        query=query,
        content=content,
        perspectives_used=perspectives_used,
        perspective_results=perspective_results,
        client_data=client_data,
        confidence=confidence,
        escalation_required=escalation_required,
        escalation_reason=escalation_reason,
    )
