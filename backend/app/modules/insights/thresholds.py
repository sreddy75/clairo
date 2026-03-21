"""Threshold registry for platform-wide transparency.

Defines the rules and bands used for all computed scores, severity
classifications, and trigger conditions across the platform.
Exposed via API so the frontend can render tooltip explanations.
"""

from pydantic import BaseModel


class ThresholdBand(BaseModel):
    """A single band within a threshold rule."""

    label: str
    color: str
    condition: str


class ThresholdRule(BaseModel):
    """A threshold rule with display metadata and bands."""

    metric_key: str
    display_name: str
    description: str
    rules: list[ThresholdBand]


class ThresholdRegistryResponse(BaseModel):
    """API response containing all platform threshold rules."""

    thresholds: list[ThresholdRule]


THRESHOLD_REGISTRY: list[ThresholdRule] = [
    ThresholdRule(
        metric_key="quality_score",
        display_name="Data Quality Score",
        description="Weighted composite of four dimensions: Freshness (20%), Reconciliation (30%), Completeness (25%), Timeliness (25%). Reconciliation is a proxy for authorisation status.",
        rules=[
            ThresholdBand(label="Good", color="green", condition="Score >= 70%"),
            ThresholdBand(label="Fair", color="yellow", condition="Score 40-69%"),
            ThresholdBand(label="Poor", color="red", condition="Score < 40%"),
        ],
    ),
    ThresholdRule(
        metric_key="bas_variance_severity",
        display_name="BAS Variance Severity",
        description="How significant a variance is between current and prior BAS periods.",
        rules=[
            ThresholdBand(
                label="Critical", color="red", condition=">50% change or >$10,000 absolute"
            ),
            ThresholdBand(
                label="Warning", color="yellow", condition=">20% change or >$5,000 absolute"
            ),
            ThresholdBand(label="Normal", color="gray", condition="Any other change"),
        ],
    ),
    ThresholdRule(
        metric_key="balance_sheet_current_ratio",
        display_name="Current Ratio (Liquidity)",
        description="Current Assets / Current Liabilities. Measures short-term ability to pay obligations. Benchmark: 1.5-2.0.",
        rules=[
            ThresholdBand(label="Healthy", color="green", condition="Ratio >= 1.5"),
            ThresholdBand(label="Warning", color="yellow", condition="Ratio 1.0-1.49"),
            ThresholdBand(label="Danger", color="red", condition="Ratio < 1.0"),
        ],
    ),
    ThresholdRule(
        metric_key="balance_sheet_debt_equity",
        display_name="Debt-to-Equity Ratio",
        description="Total Liabilities / Total Equity. Measures financial leverage and risk.",
        rules=[
            ThresholdBand(label="Low Risk", color="green", condition="Ratio <= 1.0"),
            ThresholdBand(label="Moderate", color="yellow", condition="Ratio 1.01-2.0"),
            ThresholdBand(label="High Risk", color="red", condition="Ratio > 2.0"),
        ],
    ),
    ThresholdRule(
        metric_key="ar_risk",
        display_name="Accounts Receivable Risk",
        description="Percentage of total receivables that are overdue (past payment terms).",
        rules=[
            ThresholdBand(label="Low Risk", color="green", condition="Overdue <= 15%"),
            ThresholdBand(label="Medium Risk", color="yellow", condition="Overdue 15-30%"),
            ThresholdBand(label="High Risk", color="red", condition="Overdue > 30%"),
        ],
    ),
    ThresholdRule(
        metric_key="gst_registration_threshold",
        display_name="GST Registration Threshold",
        description="Mandatory GST registration required when annual turnover reaches $75,000.",
        rules=[
            ThresholdBand(
                label="Registered / Below",
                color="green",
                condition="Revenue < $65,000 or already registered",
            ),
            ThresholdBand(label="Approaching", color="yellow", condition="Revenue $65,000-$74,999"),
            ThresholdBand(
                label="Must Register",
                color="red",
                condition="Revenue >= $75,000 and not registered",
            ),
        ],
    ),
    ThresholdRule(
        metric_key="cash_flow_trend",
        display_name="Cash Flow Trend Alert",
        description="Monitors consecutive months of negative net cash flow.",
        rules=[
            ThresholdBand(
                label="Healthy", color="green", condition="< 2 consecutive negative months"
            ),
            ThresholdBand(label="Watch", color="yellow", condition="2 consecutive negative months"),
            ThresholdBand(label="Alert", color="red", condition="3+ consecutive negative months"),
        ],
    ),
    ThresholdRule(
        metric_key="data_staleness",
        display_name="Data Staleness",
        description="Time since last successful Xero data sync.",
        rules=[
            ThresholdBand(label="Fresh", color="green", condition="Synced within 7 days"),
            ThresholdBand(label="Stale", color="yellow", condition="Synced 7-14 days ago"),
            ThresholdBand(label="Very Stale", color="red", condition="Synced > 14 days ago"),
        ],
    ),
]
