"""
BAS Review A2UI Generator

Generates A2UI components for BAS review with exception-focus approach.
Normal fields are collapsed while anomalies and exceptions are expanded
for quick review by accountants.
"""

import logging
from typing import Any
from uuid import UUID

from app.core.a2ui import (
    A2UIBuilder,
    A2UIMessage,
    DeviceContext,
    LayoutHint,
    Severity,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Variance Thresholds
# =============================================================================


class VarianceThresholds:
    """Thresholds for determining if a variance is significant."""

    # Percentage thresholds
    MINOR_PCT = 5.0  # 5% variance is minor
    MODERATE_PCT = 15.0  # 15% variance is moderate
    SIGNIFICANT_PCT = 30.0  # 30%+ variance is significant

    # Absolute dollar thresholds
    MINOR_ABS = 500  # $500 variance is minor
    MODERATE_ABS = 2000  # $2000 variance is moderate
    SIGNIFICANT_ABS = 5000  # $5000+ variance is significant


# =============================================================================
# BAS Field Categories
# =============================================================================


class BASFieldCategory:
    """Categories for BAS fields."""

    GST = "gst"
    PAYG = "payg"
    FUEL = "fuel"
    OTHER = "other"


BAS_FIELD_METADATA = {
    # GST Fields
    "1A": {"label": "GST on Sales (1A)", "category": BASFieldCategory.GST, "type": "liability"},
    "1B": {"label": "GST on Purchases (1B)", "category": BASFieldCategory.GST, "type": "credit"},
    "8A": {"label": "Total Sales (8A)", "category": BASFieldCategory.GST, "type": "info"},
    "8B": {"label": "Export Sales (8B)", "category": BASFieldCategory.GST, "type": "info"},
    "9": {"label": "Net GST Payable (9)", "category": BASFieldCategory.GST, "type": "liability"},
    # PAYG Fields
    "W1": {"label": "PAYG Withheld (W1)", "category": BASFieldCategory.PAYG, "type": "liability"},
    "W2": {
        "label": "Amounts Withheld (W2)",
        "category": BASFieldCategory.PAYG,
        "type": "liability",
    },
    # Fuel Tax Credits
    "7C": {"label": "Fuel Tax Credits (7C)", "category": BASFieldCategory.FUEL, "type": "credit"},
    "7D": {
        "label": "Fuel Tax Credit Adjustments (7D)",
        "category": BASFieldCategory.FUEL,
        "type": "credit",
    },
}


# =============================================================================
# Exception Detection
# =============================================================================


def detect_field_exception(
    field_name: str,
    current_value: float,
    prior_value: float | None,
    expected_value: float | None = None,
) -> dict[str, Any] | None:
    """
    Detect if a BAS field has an exception that needs attention.

    Args:
        field_name: BAS field code (e.g., "1A", "W1")
        current_value: Current period value
        prior_value: Prior period value (for variance analysis)
        expected_value: Expected value based on patterns (optional)

    Returns:
        Exception details if detected, None otherwise
    """
    exceptions = []
    severity = "normal"

    # Check variance against prior period
    if prior_value is not None and prior_value != 0:
        variance_pct = abs((current_value - prior_value) / prior_value) * 100
        variance_abs = abs(current_value - prior_value)

        if (
            variance_pct >= VarianceThresholds.SIGNIFICANT_PCT
            or variance_abs >= VarianceThresholds.SIGNIFICANT_ABS
        ):
            severity = "error"
            direction = "increased" if current_value > prior_value else "decreased"
            exceptions.append(
                {
                    "type": "variance",
                    "message": f"{direction.title()} by {variance_pct:.1f}% (${variance_abs:,.2f}) from prior period",
                    "variance_pct": variance_pct,
                    "variance_abs": variance_abs,
                }
            )
        elif (
            variance_pct >= VarianceThresholds.MODERATE_PCT
            or variance_abs >= VarianceThresholds.MODERATE_ABS
        ):
            severity = "warning" if severity == "normal" else severity
            direction = "increased" if current_value > prior_value else "decreased"
            exceptions.append(
                {
                    "type": "variance",
                    "message": f"{direction.title()} by {variance_pct:.1f}% (${variance_abs:,.2f}) from prior period",
                    "variance_pct": variance_pct,
                    "variance_abs": variance_abs,
                }
            )

    # Check for zero values that might be issues
    if current_value == 0 and prior_value and prior_value > 1000:
        if severity == "normal":
            severity = "warning"
        exceptions.append(
            {
                "type": "zero_value",
                "message": f"Value is $0 but was ${prior_value:,.2f} in prior period",
            }
        )

    # Check for negative values in liability fields
    field_meta = BAS_FIELD_METADATA.get(field_name, {})
    if field_meta.get("type") == "liability" and current_value < 0:
        severity = "warning" if severity == "normal" else severity
        exceptions.append(
            {
                "type": "negative_liability",
                "message": "Negative value in liability field - verify credits applied correctly",
            }
        )

    if not exceptions:
        return None

    return {
        "field": field_name,
        "current_value": current_value,
        "prior_value": prior_value,
        "severity": severity,
        "exceptions": exceptions,
    }


# =============================================================================
# BAS Review A2UI Generator
# =============================================================================


class BASReviewA2UIGenerator:
    """
    Generates A2UI components for BAS review with exception focus.

    The UI shows:
    - Summary cards for key totals
    - Exception alerts (expanded)
    - Normal fields (collapsed in accordion)
    - Variance chart for trends
    """

    def __init__(self, device_context: DeviceContext | None = None):
        self.device_context = device_context or DeviceContext(
            isMobile=False,
            isTablet=False,
        )

    def generate(
        self,
        session_id: UUID,
        calculation: dict[str, Any],
        variance_analysis: dict[str, Any] | None = None,
        prior_period: dict[str, Any] | None = None,
    ) -> A2UIMessage:
        """
        Generate A2UI message for BAS review.

        Args:
            session_id: BAS session ID
            calculation: Current period calculation results
            variance_analysis: Variance analysis results
            prior_period: Prior period values for comparison

        Returns:
            A2UIMessage with review components
        """
        builder = A2UIBuilder(self.device_context)
        builder.set_agent_id("bas-review")
        builder.set_layout(LayoutHint.STACK)

        # Detect exceptions
        exceptions = self._detect_all_exceptions(calculation, prior_period)

        # Add summary cards
        self._add_summary_cards(builder, calculation)

        # Add exception alerts (expanded, prominent)
        if exceptions:
            self._add_exception_alerts(builder, exceptions)
        else:
            builder.add_alert(
                title="No Exceptions Detected",
                description="All fields are within normal variance thresholds.",
                severity=Severity.SUCCESS,
            )

        # Add variance trend chart if available
        if variance_analysis:
            self._add_variance_chart(builder, variance_analysis)

        # Add field breakdown accordion (normal fields collapsed)
        self._add_field_accordion(builder, calculation, exceptions, prior_period)

        # Add action buttons
        self._add_review_actions(builder, session_id, bool(exceptions))

        return builder.build(
            fallback_text=f"BAS Review - {len(exceptions)} exceptions found"
            if exceptions
            else "BAS Review - No exceptions"
        )

    def _detect_all_exceptions(
        self,
        calculation: dict[str, Any],
        prior_period: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Detect exceptions across all BAS fields."""
        exceptions = []

        for field_name in BAS_FIELD_METADATA:
            current_value = calculation.get(field_name, 0)
            prior_value = prior_period.get(field_name) if prior_period else None

            exception = detect_field_exception(
                field_name=field_name,
                current_value=float(current_value) if current_value else 0,
                prior_value=float(prior_value) if prior_value else None,
            )

            if exception:
                exception["label"] = BAS_FIELD_METADATA[field_name]["label"]
                exceptions.append(exception)

        # Sort by severity (error first, then warning)
        severity_order = {"error": 0, "warning": 1, "info": 2}
        exceptions.sort(key=lambda x: severity_order.get(x["severity"], 3))

        return exceptions

    def _add_summary_cards(
        self,
        builder: A2UIBuilder,
        calculation: dict[str, Any],
    ) -> None:
        """Add summary stat cards for key BAS totals."""
        # GST Collected (1A)
        gst_collected = calculation.get("1A", 0)
        builder.add_stat_card(
            label="GST Collected (1A)",
            value=f"${float(gst_collected):,.2f}",
            icon="dollar-sign",
        )

        # GST Paid (1B)
        gst_paid = calculation.get("1B", 0)
        builder.add_stat_card(
            label="GST Paid (1B)",
            value=f"${float(gst_paid):,.2f}",
            icon="receipt",
        )

        # Net GST (9)
        net_gst = calculation.get("9", float(gst_collected) - float(gst_paid))
        builder.add_stat_card(
            label="Net GST Payable (9)",
            value=f"${float(net_gst):,.2f}",
            change_direction="up" if float(net_gst) > 0 else "down",
            icon="trending-up" if float(net_gst) > 0 else "trending-down",
        )

        # PAYG Withheld (W1) if present
        payg = calculation.get("W1", 0)
        if payg:
            builder.add_stat_card(
                label="PAYG Withheld (W1)",
                value=f"${float(payg):,.2f}",
                icon="user-check",
            )

    def _add_exception_alerts(
        self,
        builder: A2UIBuilder,
        exceptions: list[dict[str, Any]],
    ) -> None:
        """Add alert cards for each exception."""
        for exception in exceptions:
            severity = {
                "error": Severity.ERROR,
                "warning": Severity.WARNING,
                "info": Severity.INFO,
            }.get(exception["severity"], Severity.INFO)

            # Combine exception messages
            messages = [e["message"] for e in exception["exceptions"]]
            description = "; ".join(messages)

            # Add current vs prior values
            if exception.get("prior_value") is not None:
                description += f"\nCurrent: ${exception['current_value']:,.2f} | Prior: ${exception['prior_value']:,.2f}"

            builder.add_alert(
                title=f"{exception['label']} - Exception",
                description=description,
                severity=severity,
            )

    def _add_variance_chart(
        self,
        builder: A2UIBuilder,
        variance_analysis: dict[str, Any],
    ) -> None:
        """Add variance trend chart."""
        historical_data = variance_analysis.get("historical_data", [])

        if historical_data:
            builder.add_line_chart(
                data_key="varianceTrend",
                data=historical_data,
                title="GST Trend (Last 4 Quarters)",
                x_axis={"dataKey": "period"},
                y_axis={"format": "currency"},
                series=[
                    {
                        "dataKey": "gst_collected",
                        "name": "GST Collected",
                        "color": "hsl(142, 76%, 36%)",
                    },
                    {"dataKey": "gst_paid", "name": "GST Paid", "color": "hsl(0, 84%, 60%)"},
                    {"dataKey": "net_gst", "name": "Net GST", "color": "hsl(221, 83%, 53%)"},
                ],
            )

    def _add_field_accordion(
        self,
        builder: A2UIBuilder,
        calculation: dict[str, Any],
        exceptions: list[dict[str, Any]],
        prior_period: dict[str, Any] | None,
    ) -> None:
        """Add accordion with field details (exceptions open, normal closed)."""
        exception_fields = {e["field"] for e in exceptions}

        # Group fields by category
        gst_items = []
        payg_items = []
        other_items = []

        for field_name, meta in BAS_FIELD_METADATA.items():
            current_value = calculation.get(field_name, 0)
            prior_value = prior_period.get(field_name) if prior_period else None

            # Calculate variance
            variance_str = ""
            if prior_value and float(prior_value) != 0:
                variance_pct = (
                    (float(current_value) - float(prior_value)) / float(prior_value)
                ) * 100
                variance_str = f" ({variance_pct:+.1f}%)"

            item = {
                "id": field_name,
                "title": f"{meta['label']}: ${float(current_value):,.2f}{variance_str}",
                "content": f"Current: ${float(current_value):,.2f}",
                "hasException": field_name in exception_fields,
            }

            if prior_value is not None:
                item["content"] += f" | Prior: ${float(prior_value):,.2f}"

            if meta["category"] == BASFieldCategory.GST:
                gst_items.append(item)
            elif meta["category"] == BASFieldCategory.PAYG:
                payg_items.append(item)
            else:
                other_items.append(item)

        # Add accordions for each category
        # Exception fields are open by default
        default_open_gst = [i["id"] for i in gst_items if i.get("hasException")]
        default_open_payg = [i["id"] for i in payg_items if i.get("hasException")]

        if gst_items:
            builder.add_accordion(
                items=[
                    {"id": i["id"], "title": i["title"], "content": i["content"]} for i in gst_items
                ],
                default_open=default_open_gst or None,
            )

        if payg_items:
            builder.add_accordion(
                items=[
                    {"id": i["id"], "title": i["title"], "content": i["content"]}
                    for i in payg_items
                ],
                default_open=default_open_payg or None,
            )

    def _add_review_actions(
        self,
        builder: A2UIBuilder,
        session_id: UUID,
        has_exceptions: bool,
    ) -> None:
        """Add review action buttons."""
        from app.core.a2ui import ActionType

        if has_exceptions:
            builder.add_action_button(
                label="Review Exceptions",
                action_type=ActionType.NAVIGATE,
                target=f"/clients/bas/{session_id}/exceptions",
                variant="primary",
                icon="alert-circle",
            )
        else:
            builder.add_action_button(
                label="Approve BAS",
                action_type=ActionType.APPROVE,
                target=str(session_id),
                variant="primary",
                icon="check",
            )

        builder.add_action_button(
            label="Export Working Papers",
            action_type=ActionType.EXPORT,
            target=str(session_id),
            variant="secondary",
            icon="download",
        )


# =============================================================================
# Convenience Function
# =============================================================================


def generate_bas_review_ui(
    session_id: UUID,
    calculation: dict[str, Any],
    variance_analysis: dict[str, Any] | None = None,
    prior_period: dict[str, Any] | None = None,
    device_context: DeviceContext | None = None,
) -> A2UIMessage:
    """
    Generate BAS review A2UI message.

    Args:
        session_id: BAS session ID
        calculation: Current period calculation
        variance_analysis: Optional variance analysis
        prior_period: Optional prior period values
        device_context: Optional device context

    Returns:
        A2UIMessage for the BAS review
    """
    generator = BASReviewA2UIGenerator(device_context)
    return generator.generate(
        session_id=session_id,
        calculation=calculation,
        variance_analysis=variance_analysis,
        prior_period=prior_period,
    )
