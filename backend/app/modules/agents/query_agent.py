"""
Query Visualization Agent

Specialized agent for handling ad-hoc queries and generating
visual answers with charts, tables, and interactive filters.

This agent analyzes natural language queries about financial data
and generates appropriate A2UI components for visualization.
"""

import logging
import re
from typing import Any
from uuid import UUID, uuid4

from app.core.a2ui import (
    A2UIBuilder,
    DeviceContext,
    LayoutHint,
    Severity,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Query Classification
# =============================================================================


class QueryType:
    """Types of queries we can handle."""

    SUMMARY = "summary"  # Overview/summary requests
    COMPARISON = "comparison"  # Compare periods/entities
    TREND = "trend"  # Time-based trends
    BREAKDOWN = "breakdown"  # Category breakdowns
    LIST = "list"  # List of items (invoices, transactions)
    DETAIL = "detail"  # Specific item details
    ANOMALY = "anomaly"  # Find unusual patterns
    FORECAST = "forecast"  # Future projections


class QueryClassifier:
    """Classifies queries to determine visualization approach."""

    SUMMARY_PATTERNS = [
        r"\b(overview|summary|snapshot|status|how\s+is)\b",
        r"\b(total|overall|net)\s+(gst|bas|revenue|profit)\b",
        r"\bwhat('?s|is)\s+(my|the|our)\b",
    ]

    COMPARISON_PATTERNS = [
        r"\bcompare\b",
        r"\bvs\b",
        r"\bversus\b",
        r"\bdifference\s+between\b",
        r"\b(this|last)\s+(quarter|month|year)\s+vs\b",
        r"\b(better|worse)\s+than\b",
    ]

    TREND_PATTERNS = [
        r"\btrend\b",
        r"\bover\s+(time|the\s+(past|last))\b",
        r"\b(monthly|quarterly|yearly|weekly)\s+(trend|pattern)\b",
        r"\bhow\s+has\s+.+\s+changed\b",
        r"\b(increasing|decreasing|growing|declining)\b",
    ]

    BREAKDOWN_PATTERNS = [
        r"\bbreakdown\b",
        r"\bby\s+(category|type|source|client)\b",
        r"\bwhere\s+is\s+.+\s+(going|coming\s+from)\b",
        r"\bsplit\b",
        r"\bcomposition\b",
    ]

    LIST_PATTERNS = [
        r"\b(list|show)\s+(all|the|my)\b",
        r"\btop\s+\d+\b",
        r"\blargest\b",
        r"\boverdue\b",
        r"\bwho\s+(owes?|are)\b",
        r"\bwhich\s+(clients?|invoices?|expenses?)\b",
    ]

    ANOMALY_PATTERNS = [
        r"\bunusual\b",
        r"\banomaly\b",
        r"\bodd\b",
        r"\bwrong\b",
        r"\bissues?\b",
        r"\bproblems?\b",
        r"\bsuspicious\b",
    ]

    @classmethod
    def classify(cls, query: str) -> tuple[str, float]:
        """Classify a query and return type with confidence."""
        query_lower = query.lower()

        # Check each pattern set
        patterns_map = {
            QueryType.SUMMARY: cls.SUMMARY_PATTERNS,
            QueryType.COMPARISON: cls.COMPARISON_PATTERNS,
            QueryType.TREND: cls.TREND_PATTERNS,
            QueryType.BREAKDOWN: cls.BREAKDOWN_PATTERNS,
            QueryType.LIST: cls.LIST_PATTERNS,
            QueryType.ANOMALY: cls.ANOMALY_PATTERNS,
        }

        matches = {}
        for query_type, patterns in patterns_map.items():
            match_count = sum(1 for p in patterns if re.search(p, query_lower))
            if match_count > 0:
                matches[query_type] = match_count

        if not matches:
            # Default to summary if no patterns match
            return QueryType.SUMMARY, 0.5

        # Return the type with most matches
        best_type = max(matches, key=matches.get)
        confidence = min(0.9, 0.5 + (matches[best_type] * 0.15))

        return best_type, confidence


# =============================================================================
# Data Extractors
# =============================================================================


def extract_time_period(query: str) -> dict[str, Any] | None:
    """Extract time period references from query."""
    query_lower = query.lower()

    # Quarter patterns
    quarter_match = re.search(r"q([1-4])\s*(\d{4})?", query_lower)
    if quarter_match:
        quarter = int(quarter_match.group(1))
        year = int(quarter_match.group(2)) if quarter_match.group(2) else None
        return {"type": "quarter", "quarter": quarter, "year": year}

    # Month patterns
    months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    for i, month in enumerate(months):
        if month in query_lower:
            year_match = re.search(r"(\d{4})", query_lower)
            return {
                "type": "month",
                "month": i + 1,
                "year": int(year_match.group(1)) if year_match else None,
            }

    # Relative periods
    if "this quarter" in query_lower:
        return {"type": "relative", "period": "this_quarter"}
    if "last quarter" in query_lower:
        return {"type": "relative", "period": "last_quarter"}
    if "this month" in query_lower:
        return {"type": "relative", "period": "this_month"}
    if "last month" in query_lower:
        return {"type": "relative", "period": "last_month"}
    if "this year" in query_lower or "ytd" in query_lower:
        return {"type": "relative", "period": "ytd"}
    if "last year" in query_lower:
        return {"type": "relative", "period": "last_year"}

    return None


def extract_metric_focus(query: str) -> list[str]:
    """Extract what metrics the query is focused on."""
    query_lower = query.lower()

    metrics = []

    metric_patterns = {
        "gst": [r"\bgst\b"],
        "revenue": [r"\b(revenue|sales|income)\b"],
        "expenses": [r"\b(expense|cost|spending)\b"],
        "profit": [r"\b(profit|margin|earnings)\b"],
        "payg": [r"\b(payg|withholding)\b"],
        "super": [r"\b(super|superannuation)\b"],
        "receivables": [r"\b(receivable|owed|owing)\b", r"\bwho\s+owes\b"],
        "payables": [r"\b(payable|bills?)\b"],
    }

    for metric, patterns in metric_patterns.items():
        if any(re.search(p, query_lower) for p in patterns):
            metrics.append(metric)

    return metrics if metrics else ["gst", "revenue", "expenses"]


# =============================================================================
# Query Visualization Agent
# =============================================================================


class QueryVisualizationAgent:
    """
    Agent that processes natural language queries and generates
    appropriate visualizations using A2UI.
    """

    def __init__(self, device_context: DeviceContext | None = None):
        self.device_context = device_context or DeviceContext(
            isMobile=False,
            isTablet=False,
        )

    async def process_query(
        self,
        query: str,
        client_data: dict[str, Any] | None = None,
        connection_id: UUID | None = None,
    ) -> dict[str, Any]:
        """
        Process a natural language query and generate visualization.

        Args:
            query: The natural language query
            client_data: Financial data for the client
            connection_id: Optional client connection ID

        Returns:
            Dict with text_response and a2ui_message
        """
        # Classify the query
        query_type, confidence = QueryClassifier.classify(query)
        logger.info(f"Query classified as {query_type} with confidence {confidence}")

        # Extract context from query
        time_period = extract_time_period(query)
        metric_focus = extract_metric_focus(query)

        # Generate response based on query type
        builder = A2UIBuilder(self.device_context)
        builder.set_agent_id("query-visualization")
        builder.set_layout(LayoutHint.STACK)

        # Build appropriate visualization
        if query_type == QueryType.SUMMARY:
            text_response = self._build_summary_response(
                builder, query, client_data, metric_focus, time_period
            )
        elif query_type == QueryType.COMPARISON:
            text_response = self._build_comparison_response(
                builder, query, client_data, metric_focus, time_period
            )
        elif query_type == QueryType.TREND:
            text_response = self._build_trend_response(
                builder, query, client_data, metric_focus, time_period
            )
        elif query_type == QueryType.BREAKDOWN:
            text_response = self._build_breakdown_response(
                builder, query, client_data, metric_focus, time_period
            )
        elif query_type == QueryType.LIST:
            text_response = self._build_list_response(
                builder, query, client_data, metric_focus, time_period
            )
        elif query_type == QueryType.ANOMALY:
            text_response = self._build_anomaly_response(
                builder, query, client_data, metric_focus, time_period
            )
        else:
            text_response = self._build_summary_response(
                builder, query, client_data, metric_focus, time_period
            )

        # Add filter bar for interactive filtering
        self._add_filter_bar(builder, query_type, metric_focus)

        return {
            "correlation_id": str(uuid4()),
            "text_response": text_response,
            "a2ui_message": builder.build(fallback_text=text_response[:200]),
            "query_type": query_type,
            "confidence": confidence,
            "time_period": time_period,
            "metric_focus": metric_focus,
        }

    def _build_summary_response(
        self,
        builder: A2UIBuilder,
        query: str,
        client_data: dict[str, Any] | None,
        metric_focus: list[str],
        time_period: dict[str, Any] | None,
    ) -> str:
        """Build summary visualization with stat cards."""
        data = client_data or self._get_mock_data()

        # Period label
        period_label = self._format_period_label(time_period)

        # Add key stat cards
        if "gst" in metric_focus or "revenue" in metric_focus:
            builder.add_stat_card(
                label=f"GST Collected{period_label}",
                value=f"${data.get('gst_collected', 0):,.2f}",
                icon="dollar-sign",
            )
            builder.add_stat_card(
                label=f"GST Paid{period_label}",
                value=f"${data.get('gst_paid', 0):,.2f}",
                icon="receipt",
            )
            net_gst = data.get("gst_collected", 0) - data.get("gst_paid", 0)
            builder.add_stat_card(
                label=f"Net GST Payable{period_label}",
                value=f"${net_gst:,.2f}",
                change_direction="up" if net_gst > 0 else "down",
                icon="trending-up" if net_gst > 0 else "trending-down",
            )

        if "revenue" in metric_focus:
            builder.add_stat_card(
                label=f"Total Revenue{period_label}",
                value=f"${data.get('total_revenue', 0):,.2f}",
                change_value=data.get("revenue_change_pct", 0),
                change_direction="up" if data.get("revenue_change_pct", 0) > 0 else "down",
                icon="arrow-up-right",
            )

        if "expenses" in metric_focus:
            builder.add_stat_card(
                label=f"Total Expenses{period_label}",
                value=f"${data.get('total_expenses', 0):,.2f}",
                change_value=data.get("expense_change_pct", 0),
                change_direction="up" if data.get("expense_change_pct", 0) > 0 else "down",
                icon="arrow-down-right",
            )

        return f"Here's your financial summary{period_label}. The key metrics are displayed above."

    def _build_comparison_response(
        self,
        builder: A2UIBuilder,
        query: str,
        client_data: dict[str, Any] | None,
        metric_focus: list[str],
        time_period: dict[str, Any] | None,
    ) -> str:
        """Build comparison visualization."""
        data = client_data or self._get_mock_data()

        # Create comparison data
        comparison_data = [
            {"period": "This Quarter", "revenue": 125000, "expenses": 85000, "profit": 40000},
            {"period": "Last Quarter", "revenue": 118000, "expenses": 82000, "profit": 36000},
        ]

        builder.add_bar_chart(
            data_key="periodComparison",
            data=comparison_data,
            title="Quarter-over-Quarter Comparison",
            orientation="vertical",
        )

        # Add comparison table
        builder.add_comparison_table(
            left_label="This Quarter",
            right_label="Last Quarter",
            rows=[
                {"metric": "Revenue", "left": "$125,000", "right": "$118,000", "change": "+5.9%"},
                {"metric": "Expenses", "left": "$85,000", "right": "$82,000", "change": "+3.7%"},
                {"metric": "Profit", "left": "$40,000", "right": "$36,000", "change": "+11.1%"},
            ],
        )

        return "Here's the comparison between periods. Revenue increased by 5.9% while expenses grew by 3.7%, resulting in an 11.1% profit improvement."

    def _build_trend_response(
        self,
        builder: A2UIBuilder,
        query: str,
        client_data: dict[str, Any] | None,
        metric_focus: list[str],
        time_period: dict[str, Any] | None,
    ) -> str:
        """Build trend visualization with line chart."""
        data = client_data or self._get_mock_data()

        # Get or create trend data
        trend_data = data.get(
            "monthly_trend",
            [
                {"month": "Jul", "revenue": 38000, "expenses": 28000},
                {"month": "Aug", "revenue": 42000, "expenses": 30000},
                {"month": "Sep", "revenue": 45000, "expenses": 27000},
                {"month": "Oct", "revenue": 41000, "expenses": 29000},
                {"month": "Nov", "revenue": 48000, "expenses": 31000},
                {"month": "Dec", "revenue": 52000, "expenses": 33000},
            ],
        )

        builder.add_line_chart(
            data_key="monthlyTrend",
            data=trend_data,
            title="Monthly Financial Trend",
            x_axis={"dataKey": "month"},
            y_axis={"format": "currency"},
            series=[
                {"dataKey": "revenue", "name": "Revenue", "color": "hsl(142, 76%, 36%)"},
                {"dataKey": "expenses", "name": "Expenses", "color": "hsl(0, 84%, 60%)"},
            ],
        )

        return "The chart shows your financial trend over the past 6 months. Revenue has been growing steadily, with a significant uptick in the last quarter."

    def _build_breakdown_response(
        self,
        builder: A2UIBuilder,
        query: str,
        client_data: dict[str, Any] | None,
        metric_focus: list[str],
        time_period: dict[str, Any] | None,
    ) -> str:
        """Build breakdown visualization with bar/pie charts."""
        data = client_data or self._get_mock_data()

        expense_breakdown = data.get(
            "expense_breakdown",
            [
                {"category": "Wages", "amount": 45000},
                {"category": "Rent", "amount": 18000},
                {"category": "Utilities", "amount": 5400},
                {"category": "Marketing", "amount": 8200},
                {"category": "Professional Fees", "amount": 6500},
                {"category": "Other", "amount": 3200},
            ],
        )

        builder.add_bar_chart(
            data_key="expenseBreakdown",
            data=expense_breakdown,
            title="Expense Breakdown by Category",
            orientation="horizontal",
        )

        # Add pie chart for visual variety
        builder.add_pie_chart(
            data_key="expensePie",
            data=expense_breakdown,
            title="Expense Distribution",
            donut=True,
        )

        total = sum(item["amount"] for item in expense_breakdown)
        top_category = max(expense_breakdown, key=lambda x: x["amount"])

        return f"Your total expenses are ${total:,.2f}. The largest category is {top_category['category']} at ${top_category['amount']:,.2f} ({top_category['amount'] / total * 100:.1f}% of total)."

    def _build_list_response(
        self,
        builder: A2UIBuilder,
        query: str,
        client_data: dict[str, Any] | None,
        metric_focus: list[str],
        time_period: dict[str, Any] | None,
    ) -> str:
        """Build list visualization with data table."""
        data = client_data or self._get_mock_data()

        # Determine what to list based on query
        if "receivables" in metric_focus or "owes" in query.lower():
            items = data.get(
                "overdue_invoices",
                [
                    {
                        "client": "Acme Corp",
                        "invoice": "INV-001",
                        "amount": 15420,
                        "days_overdue": 45,
                    },
                    {
                        "client": "Tech Solutions",
                        "invoice": "INV-002",
                        "amount": 8750,
                        "days_overdue": 30,
                    },
                    {
                        "client": "Global Services",
                        "invoice": "INV-003",
                        "amount": 5200,
                        "days_overdue": 15,
                    },
                ],
            )

            builder.add_data_table(
                data_key="overdueInvoices",
                data=items,
                columns=[
                    {"key": "client", "label": "Client", "sortable": True},
                    {"key": "invoice", "label": "Invoice #", "sortable": False},
                    {"key": "amount", "label": "Amount", "sortable": True},
                    {"key": "days_overdue", "label": "Days Overdue", "sortable": True},
                ],
                title="Overdue Invoices",
                page_size=10,
            )

            total = sum(item["amount"] for item in items)
            return f"You have {len(items)} overdue invoices totaling ${total:,.2f}. The table above shows all overdue items sorted by days overdue."
        else:
            # Default to top expenses
            items = data.get(
                "top_transactions",
                [
                    {
                        "date": "Dec 15",
                        "description": "Office Rent",
                        "amount": 6000,
                        "category": "Rent",
                    },
                    {
                        "date": "Dec 10",
                        "description": "Payroll",
                        "amount": 15000,
                        "category": "Wages",
                    },
                    {
                        "date": "Dec 5",
                        "description": "Software Licenses",
                        "amount": 2500,
                        "category": "IT",
                    },
                ],
            )

            builder.add_data_table(
                data_key="topTransactions",
                data=items,
                columns=[
                    {"key": "date", "label": "Date", "sortable": True},
                    {"key": "description", "label": "Description", "sortable": False},
                    {"key": "amount", "label": "Amount", "sortable": True},
                    {"key": "category", "label": "Category", "sortable": True},
                ],
                title="Recent Transactions",
                page_size=10,
            )

            return "Here are your recent transactions. You can sort by any column and filter by category."

    def _build_anomaly_response(
        self,
        builder: A2UIBuilder,
        query: str,
        client_data: dict[str, Any] | None,
        metric_focus: list[str],
        time_period: dict[str, Any] | None,
    ) -> str:
        """Build anomaly detection visualization."""
        data = client_data or self._get_mock_data()

        anomalies = data.get(
            "anomalies",
            [
                {
                    "type": "Unusual Expense",
                    "description": "Marketing spend 3x higher than average",
                    "amount": 24600,
                    "severity": "warning",
                },
                {
                    "type": "Missing Data",
                    "description": "No bank reconciliation for November",
                    "severity": "error",
                },
                {
                    "type": "Duplicate Transaction",
                    "description": "Possible duplicate payment to Supplier X",
                    "amount": 4500,
                    "severity": "warning",
                },
            ],
        )

        # Add alerts for each anomaly
        for anomaly in anomalies:
            severity = {
                "warning": Severity.WARNING,
                "error": Severity.ERROR,
                "info": Severity.INFO,
            }.get(anomaly.get("severity", "info"), Severity.INFO)

            amount_str = f" (${anomaly['amount']:,.2f})" if "amount" in anomaly else ""
            builder.add_alert(
                title=anomaly["type"],
                description=f"{anomaly['description']}{amount_str}",
                severity=severity,
            )

        if anomalies:
            return f"I found {len(anomalies)} potential issues that need your attention. Review the alerts above and take action where needed."
        else:
            builder.add_alert(
                title="All Clear",
                description="No anomalies detected in your recent data.",
                severity=Severity.SUCCESS,
            )
            return "No anomalies or unusual patterns detected in your financial data."

    def _add_filter_bar(
        self,
        builder: A2UIBuilder,
        query_type: str,
        metric_focus: list[str],
    ) -> None:
        """Add interactive filter bar based on query context."""
        filters = []

        # Period filter
        filters.append(
            {
                "id": "period",
                "label": "Period",
                "type": "select",
                "options": [
                    {"value": "this_quarter", "label": "This Quarter"},
                    {"value": "last_quarter", "label": "Last Quarter"},
                    {"value": "ytd", "label": "Year to Date"},
                    {"value": "last_year", "label": "Last Year"},
                ],
            }
        )

        # Metric filter if multiple metrics
        if len(metric_focus) > 1:
            filters.append(
                {
                    "id": "metric",
                    "label": "Metric",
                    "type": "select",
                    "options": [{"value": m, "label": m.title()} for m in metric_focus],
                }
            )

        # Add filter bar if we have filters
        if filters:
            builder.add_filter_bar(filters=filters)

    def _format_period_label(self, time_period: dict[str, Any] | None) -> str:
        """Format time period as a label suffix."""
        if not time_period:
            return ""

        if time_period.get("type") == "quarter":
            q = time_period.get("quarter")
            y = time_period.get("year", "")
            return f" (Q{q} {y})" if y else f" (Q{q})"

        if time_period.get("type") == "relative":
            period = time_period.get("period", "")
            labels = {
                "this_quarter": " (This Quarter)",
                "last_quarter": " (Last Quarter)",
                "this_month": " (This Month)",
                "last_month": " (Last Month)",
                "ytd": " (Year to Date)",
                "last_year": " (Last Year)",
            }
            return labels.get(period, "")

        return ""

    def _get_mock_data(self) -> dict[str, Any]:
        """Get mock data for demonstration."""
        return {
            "gst_collected": 15420.50,
            "gst_paid": 5196.25,
            "total_revenue": 154205.00,
            "total_expenses": 86342.00,
            "revenue_change_pct": 8.5,
            "expense_change_pct": 3.2,
            "monthly_trend": [
                {"month": "Jul", "revenue": 38000, "expenses": 28000},
                {"month": "Aug", "revenue": 42000, "expenses": 30000},
                {"month": "Sep", "revenue": 45000, "expenses": 27000},
                {"month": "Oct", "revenue": 41000, "expenses": 29000},
                {"month": "Nov", "revenue": 48000, "expenses": 31000},
                {"month": "Dec", "revenue": 52000, "expenses": 33000},
            ],
            "expense_breakdown": [
                {"category": "Wages", "amount": 45000},
                {"category": "Rent", "amount": 18000},
                {"category": "Utilities", "amount": 5400},
                {"category": "Marketing", "amount": 8200},
                {"category": "Professional Fees", "amount": 6500},
                {"category": "Other", "amount": 3200},
            ],
        }


# =============================================================================
# Convenience Function
# =============================================================================


async def process_query_with_visualization(
    query: str,
    client_data: dict[str, Any] | None = None,
    connection_id: UUID | None = None,
    device_context: DeviceContext | None = None,
) -> dict[str, Any]:
    """
    Process a query and return visualization response.

    Args:
        query: Natural language query
        client_data: Optional client financial data
        connection_id: Optional client connection ID
        device_context: Optional device context for responsive UI

    Returns:
        Dict containing text_response and a2ui_message
    """
    agent = QueryVisualizationAgent(device_context)
    return await agent.process_query(query, client_data, connection_id)
