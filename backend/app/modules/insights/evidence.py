"""Evidence extraction and data snapshot building for insight traceability.

Provides structured evidence extraction from financial context data,
snapshot building for audit trails, and size management utilities.

The hybrid evidence approach:
- Backend extracts structured evidence from known financial context
- AI is instructed to include inline citations for readability
- Frontend renders evidence exclusively from structured backend data
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Maximum snapshot size in bytes (50KB per clarification)
MAX_SNAPSHOT_SIZE_BYTES = 50 * 1024


class EvidenceItem(BaseModel):
    """A single structured data point extracted from financial context."""

    source: str = Field(..., max_length=100, description="Data source name")
    period: str = Field(..., max_length=50, description="Reporting period or as-of date")
    metric: str = Field(..., max_length=100, description="Metric label")
    value: str = Field(..., max_length=100, description="Formatted value")
    category: Literal["financial", "aging", "gst", "quality", "trend"] = Field(
        ..., description="Evidence category"
    )


class DataSnapshotV1(BaseModel):
    """Structured capture of financial context at time of AI analysis.

    Stored in the insight's data_snapshot JSONB column.
    Bounded to 50KB maximum per snapshot.
    """

    version: str = "1.0"
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data_freshness: datetime | None = None
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    profile: dict[str, Any] | None = None
    financial_summary: dict[str, Any] | None = None
    aging_summary: dict[str, Any] | None = None
    gst_summary: dict[str, Any] | None = None
    monthly_trends: list[dict[str, Any]] | None = None
    quality_scores: dict[str, Any] | None = None
    perspectives_used: list[str] = Field(default_factory=list)
    ai_analysis: bool = True
    generated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


def _format_currency(value: float | int | None) -> str:
    """Format a numeric value as AUD currency string."""
    if value is None:
        return "N/A"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:,.1f}M"
    if abs(value) >= 1_000:
        return f"${value:,.0f}"
    return f"${value:,.2f}"


def _format_percentage(value: float | int | None) -> str:
    """Format a numeric value as percentage string."""
    if value is None:
        return "N/A"
    return f"{value:.1f}%"


def _format_ratio(value: float | int | None) -> str:
    """Format a numeric value as a ratio."""
    if value is None:
        return "N/A"
    return f"{value:.2f}"


def _extract_evidence_from_profile(
    profile: dict[str, Any],
) -> list[EvidenceItem]:
    """Extract evidence items from client profile data."""
    items: list[EvidenceItem] = []

    if profile.get("revenue_bracket"):
        items.append(
            EvidenceItem(
                source="Client Profile",
                period="Current",
                metric="Revenue Bracket",
                value=str(profile["revenue_bracket"]),
                category="financial",
            )
        )

    if profile.get("entity_type"):
        items.append(
            EvidenceItem(
                source="Client Profile",
                period="Current",
                metric="Entity Type",
                value=str(profile["entity_type"]),
                category="financial",
            )
        )

    return items


def _extract_evidence_from_report_context(
    report_context: dict[str, Any],
) -> tuple[list[EvidenceItem], dict[str, Any]]:
    """Extract evidence items and financial summary from report context.

    Report context contains P&L, Balance Sheet, Aged Receivables, etc.
    """
    items: list[EvidenceItem] = []
    financial_summary: dict[str, Any] = {}

    # Profit & Loss
    pnl = report_context.get("profit_and_loss")
    if pnl and isinstance(pnl, dict):
        report_name = pnl.get("report_name", "Profit & Loss")
        period = pnl.get("report_date", "Current Period")

        rows = pnl.get("rows", [])
        for row in rows:
            title = row.get("title", "")
            cells = row.get("cells", [])
            if cells and title:
                val = cells[0].get("value")
                if val is not None:
                    try:
                        numeric_val = float(str(val).replace(",", "").replace("$", ""))
                        formatted = _format_currency(numeric_val)

                        if "revenue" in title.lower() or "income" in title.lower():
                            items.append(
                                EvidenceItem(
                                    source=report_name,
                                    period=period,
                                    metric=title,
                                    value=formatted,
                                    category="financial",
                                )
                            )
                            financial_summary["revenue"] = numeric_val
                        elif "expense" in title.lower() or "cost" in title.lower():
                            items.append(
                                EvidenceItem(
                                    source=report_name,
                                    period=period,
                                    metric=title,
                                    value=formatted,
                                    category="financial",
                                )
                            )
                            financial_summary["expenses"] = numeric_val
                        elif "net" in title.lower() and "profit" in title.lower():
                            items.append(
                                EvidenceItem(
                                    source=report_name,
                                    period=period,
                                    metric=title,
                                    value=formatted,
                                    category="financial",
                                )
                            )
                            financial_summary["net_profit"] = numeric_val
                    except (ValueError, TypeError):
                        pass

    # Balance Sheet
    bs = report_context.get("balance_sheet")
    if bs and isinstance(bs, dict):
        report_name = bs.get("report_name", "Balance Sheet")
        period = bs.get("report_date", "Current Period")

        rows = bs.get("rows", [])
        total_current_assets = None
        total_current_liabilities = None

        for row in rows:
            title = row.get("title", "")
            cells = row.get("cells", [])
            if cells and title:
                val = cells[0].get("value")
                if val is not None:
                    try:
                        numeric_val = float(str(val).replace(",", "").replace("$", ""))
                        title_lower = title.lower()

                        if "current asset" in title_lower and "total" in title_lower:
                            total_current_assets = numeric_val
                        elif "current liabilit" in title_lower and "total" in title_lower:
                            total_current_liabilities = numeric_val

                        if "total assets" in title_lower or "total equity" in title_lower:
                            items.append(
                                EvidenceItem(
                                    source=report_name,
                                    period=period,
                                    metric=title,
                                    value=_format_currency(numeric_val),
                                    category="financial",
                                )
                            )
                    except (ValueError, TypeError):
                        pass

        if total_current_assets and total_current_liabilities and total_current_liabilities != 0:
            ratio = total_current_assets / total_current_liabilities
            financial_summary["current_ratio"] = round(ratio, 2)
            items.append(
                EvidenceItem(
                    source=report_name,
                    period=period,
                    metric="Current Ratio",
                    value=_format_ratio(ratio),
                    category="financial",
                )
            )

    # Aged Receivables
    ar = report_context.get("aged_receivables")
    if ar and isinstance(ar, dict):
        report_name = ar.get("report_name", "Aged Receivables")
        period = ar.get("report_date", "Current")

        rows = ar.get("rows", [])
        for row in rows:
            title = row.get("title", "")
            if "total" in title.lower():
                cells = row.get("cells", [])
                if cells:
                    val = cells[0].get("value")
                    if val is not None:
                        try:
                            numeric_val = float(str(val).replace(",", "").replace("$", ""))
                            items.append(
                                EvidenceItem(
                                    source=report_name,
                                    period=period,
                                    metric="Total Outstanding",
                                    value=_format_currency(numeric_val),
                                    category="aging",
                                )
                            )
                        except (ValueError, TypeError):
                            pass

    # Aged Payables
    ap = report_context.get("aged_payables")
    if ap and isinstance(ap, dict):
        report_name = ap.get("report_name", "Aged Payables")
        period = ap.get("report_date", "Current")

        rows = ap.get("rows", [])
        for row in rows:
            title = row.get("title", "")
            if "total" in title.lower():
                cells = row.get("cells", [])
                if cells:
                    val = cells[0].get("value")
                    if val is not None:
                        try:
                            numeric_val = float(str(val).replace(",", "").replace("$", ""))
                            items.append(
                                EvidenceItem(
                                    source=report_name,
                                    period=period,
                                    metric="Total Outstanding",
                                    value=_format_currency(numeric_val),
                                    category="aging",
                                )
                            )
                        except (ValueError, TypeError):
                            pass

    return items, financial_summary


def _extract_evidence_from_aging(
    aging_data: dict[str, Any],
    source_name: str,
) -> tuple[list[EvidenceItem], dict[str, Any]]:
    """Extract evidence from AR/AP aging summary data."""
    items: list[EvidenceItem] = []
    summary: dict[str, Any] = {}
    period = aging_data.get("as_of_date", aging_data.get("period", "Current"))

    total = aging_data.get("total", aging_data.get("total_outstanding"))
    overdue = aging_data.get("overdue", aging_data.get("total_overdue"))

    if total is not None:
        items.append(
            EvidenceItem(
                source=source_name,
                period=str(period),
                metric="Total Outstanding",
                value=_format_currency(total),
                category="aging",
            )
        )
        key_prefix = "ar" if "receivable" in source_name.lower() else "ap"
        summary[f"{key_prefix}_total"] = total

    if overdue is not None:
        items.append(
            EvidenceItem(
                source=source_name,
                period=str(period),
                metric="Total Overdue",
                value=_format_currency(overdue),
                category="aging",
            )
        )
        key_prefix = "ar" if "receivable" in source_name.lower() else "ap"
        summary[f"{key_prefix}_overdue"] = overdue

        if total and total > 0:
            pct = (overdue / total) * 100
            summary[f"{key_prefix}_overdue_pct"] = round(pct, 1)
            items.append(
                EvidenceItem(
                    source=source_name,
                    period=str(period),
                    metric="Overdue Percentage",
                    value=_format_percentage(pct),
                    category="aging",
                )
            )

    return items, summary


def _extract_evidence_from_gst(
    gst_summaries: list[dict[str, Any]],
) -> tuple[list[EvidenceItem], dict[str, Any]]:
    """Extract evidence from GST summary data."""
    items: list[EvidenceItem] = []
    summary: dict[str, Any] = {}

    if not gst_summaries:
        return items, summary

    # Use the most recent GST summary
    latest = gst_summaries[0]
    period = latest.get("period", latest.get("quarter", "Current Quarter"))

    collected = latest.get("gst_collected", latest.get("collected"))
    paid = latest.get("gst_paid", latest.get("paid"))
    net = latest.get("net_gst", latest.get("net_position"))

    if collected is not None:
        items.append(
            EvidenceItem(
                source="GST Summary",
                period=str(period),
                metric="GST Collected",
                value=_format_currency(collected),
                category="gst",
            )
        )
        summary["collected"] = collected

    if paid is not None:
        items.append(
            EvidenceItem(
                source="GST Summary",
                period=str(period),
                metric="GST Paid",
                value=_format_currency(paid),
                category="gst",
            )
        )
        summary["paid"] = paid

    if net is not None:
        items.append(
            EvidenceItem(
                source="GST Summary",
                period=str(period),
                metric="Net GST Position",
                value=_format_currency(net),
                category="gst",
            )
        )
        summary["net_position"] = net

    return items, summary


def _extract_evidence_from_trends(
    trends: list[dict[str, Any]],
) -> list[EvidenceItem]:
    """Extract evidence from monthly trend data."""
    items: list[EvidenceItem] = []

    if not trends or len(trends) < 2:
        return items

    # Latest month revenue trend
    latest = trends[0]
    previous = trends[1] if len(trends) > 1 else None

    period = latest.get("month", latest.get("period", "Latest Month"))
    revenue = latest.get("revenue", latest.get("total_revenue"))

    if revenue is not None:
        items.append(
            EvidenceItem(
                source="Monthly Trends",
                period=str(period),
                metric="Revenue",
                value=_format_currency(revenue),
                category="trend",
            )
        )

    # Revenue direction
    if previous and revenue is not None:
        prev_revenue = previous.get("revenue", previous.get("total_revenue"))
        if prev_revenue is not None and prev_revenue != 0:
            change_pct = ((revenue - prev_revenue) / abs(prev_revenue)) * 100
            direction = "up" if change_pct > 0 else "down"
            items.append(
                EvidenceItem(
                    source="Monthly Trends",
                    period=str(period),
                    metric=f"Revenue Trend ({direction})",
                    value=_format_percentage(abs(change_pct)),
                    category="trend",
                )
            )

    # Expenses trend
    expenses = latest.get("expenses", latest.get("total_expenses"))
    if expenses is not None:
        items.append(
            EvidenceItem(
                source="Monthly Trends",
                period=str(period),
                metric="Expenses",
                value=_format_currency(expenses),
                category="trend",
            )
        )

    return items


def _extract_evidence_from_quality(
    quality_data: dict[str, Any],
) -> tuple[list[EvidenceItem], dict[str, Any]]:
    """Extract evidence from quality score data."""
    items: list[EvidenceItem] = []
    summary: dict[str, Any] = {}

    score = quality_data.get("overall_score", quality_data.get("score"))
    if score is not None:
        items.append(
            EvidenceItem(
                source="Data Quality Score",
                period="Current",
                metric="Overall Score",
                value=f"{score}/100"
                if isinstance(score, int | float) and score > 1
                else _format_percentage(score * 100 if score <= 1 else score),
                category="quality",
            )
        )
        summary["overall_score"] = score

    dimensions = quality_data.get("dimensions", quality_data.get("breakdown", {}))
    if isinstance(dimensions, dict):
        summary["dimensions"] = dimensions
        for dim_name, dim_value in dimensions.items():
            if isinstance(dim_value, int | float):
                items.append(
                    EvidenceItem(
                        source="Data Quality Score",
                        period="Current",
                        metric=dim_name.replace("_", " ").title(),
                        value=f"{dim_value}/100"
                        if dim_value > 1
                        else _format_percentage(dim_value * 100),
                        category="quality",
                    )
                )

    return items, summary


def build_evidence_snapshot(
    client_context: Any | None = None,
    perspective_contexts: dict[str, Any] | None = None,
    raw_context: dict[str, Any] | None = None,
) -> DataSnapshotV1:
    """Build a structured evidence snapshot from financial context.

    Accepts context from either the orchestrator flow (client_context +
    perspective_contexts) or the AI analyzer flow (raw_context dict).

    Args:
        client_context: ClientContext dataclass from context_builder.
        perspective_contexts: Dict of perspective-specific context from orchestrator.
        raw_context: Raw context dict from AI analyzer's _build_client_context().

    Returns:
        DataSnapshotV1 with extracted evidence items and summary data.
    """
    evidence_items: list[EvidenceItem] = []
    profile_data: dict[str, Any] | None = None
    financial_summary: dict[str, Any] = {}
    aging_summary: dict[str, Any] = {}
    gst_summary_data: dict[str, Any] = {}
    monthly_trends_data: list[dict[str, Any]] | None = None
    quality_scores_data: dict[str, Any] | None = None
    data_freshness: datetime | None = None
    perspectives_used: list[str] = []

    # === Extract from orchestrator flow (client_context + perspective_contexts) ===
    if client_context is not None:
        # ClientContext dataclass
        profile = getattr(client_context, "profile", None)
        if profile:
            profile_data = {
                "name": getattr(profile, "name", None),
                "entity_type": getattr(profile, "entity_type", None),
                "industry": getattr(profile, "industry_code", None),
                "gst_registered": getattr(profile, "gst_registered", None),
                "revenue_bracket": getattr(profile, "revenue_bracket", None),
            }
            evidence_items.extend(_extract_evidence_from_profile(profile_data))

        data_freshness = getattr(client_context, "data_freshness", None)

    if perspective_contexts:
        # Multi-perspective context from orchestrator
        multi_context = perspective_contexts
        if "profile" in multi_context and not profile_data:
            profile_data = multi_context["profile"]
            if isinstance(profile_data, dict):
                evidence_items.extend(_extract_evidence_from_profile(profile_data))

        if "data_freshness" in multi_context and not data_freshness:
            data_freshness = multi_context.get("data_freshness")

        persp = multi_context.get("perspectives", {})
        perspectives_used = list(persp.keys())

        # Strategy perspective: has report_context, monthly_trends, expenses
        strategy = persp.get("strategy", {})
        if isinstance(strategy, dict):
            report_ctx = strategy.get("report_context", {})
            if report_ctx:
                report_evidence, fin_summary = _extract_evidence_from_report_context(report_ctx)
                evidence_items.extend(report_evidence)
                financial_summary.update(fin_summary)

            trends = strategy.get("monthly_trends", [])
            if trends:
                monthly_trends_data = trends[:6]  # Keep last 6 months
                evidence_items.extend(_extract_evidence_from_trends(trends))

        # Insight perspective: has AR/AP aging, trends, report context
        insight = persp.get("insight", {})
        if isinstance(insight, dict):
            ar = insight.get("ar_aging")
            if ar:
                ar_evidence, ar_summary = _extract_evidence_from_aging(ar, "AR Aging Summary")
                evidence_items.extend(ar_evidence)
                aging_summary.update(ar_summary)

            ap = insight.get("ap_aging")
            if ap:
                ap_evidence, ap_summary = _extract_evidence_from_aging(ap, "AP Aging Summary")
                evidence_items.extend(ap_evidence)
                aging_summary.update(ap_summary)

            # Report context from insight perspective if not already captured
            if not financial_summary:
                report_ctx = insight.get("report_context", {})
                if report_ctx:
                    report_evidence, fin_summary = _extract_evidence_from_report_context(report_ctx)
                    evidence_items.extend(report_evidence)
                    financial_summary.update(fin_summary)

            if not monthly_trends_data:
                trends = insight.get("monthly_trends", [])
                if trends:
                    monthly_trends_data = trends[:6]
                    evidence_items.extend(_extract_evidence_from_trends(trends))

        # Compliance perspective: GST summaries
        compliance = persp.get("compliance", {})
        if isinstance(compliance, dict):
            gst = compliance.get("gst_summaries", [])
            if gst:
                gst_evidence, gst_sum = _extract_evidence_from_gst(gst)
                evidence_items.extend(gst_evidence)
                gst_summary_data.update(gst_sum)

        # Quality perspective
        quality = persp.get("quality", {})
        if isinstance(quality, dict):
            quality_data = quality.get("quality_data", quality)
            quality_evidence, quality_sum = _extract_evidence_from_quality(quality_data)
            evidence_items.extend(quality_evidence)
            if quality_sum:
                quality_scores_data = quality_sum

    # === Extract from AI analyzer flow (raw_context dict) ===
    if raw_context and isinstance(raw_context, dict):
        # AI analyzer builds a flat dict with various keys
        if not profile_data:
            profile_info = raw_context.get("profile", raw_context.get("client_profile", {}))
            if profile_info:
                profile_data = profile_info if isinstance(profile_info, dict) else {}

        # AR aging
        ar = raw_context.get("ar_aging", raw_context.get("accounts_receivable", {}))
        if ar and isinstance(ar, dict):
            ar_evidence, ar_sum = _extract_evidence_from_aging(ar, "AR Aging Summary")
            evidence_items.extend(ar_evidence)
            aging_summary.update(ar_sum)

        # AP aging
        ap = raw_context.get("ap_aging", raw_context.get("accounts_payable", {}))
        if ap and isinstance(ap, dict):
            ap_evidence, ap_sum = _extract_evidence_from_aging(ap, "AP Aging Summary")
            evidence_items.extend(ap_evidence)
            aging_summary.update(ap_sum)

        # GST
        gst = raw_context.get("gst_data", raw_context.get("gst_summaries", []))
        if isinstance(gst, list) and gst:
            gst_evidence, gst_sum = _extract_evidence_from_gst(gst)
            evidence_items.extend(gst_evidence)
            gst_summary_data.update(gst_sum)
        elif isinstance(gst, dict) and gst:
            gst_evidence, gst_sum = _extract_evidence_from_gst([gst])
            evidence_items.extend(gst_evidence)
            gst_summary_data.update(gst_sum)

        # Trends
        trends = raw_context.get("trends", raw_context.get("monthly_trends", []))
        if trends and isinstance(trends, list):
            monthly_trends_data = trends[:6]
            evidence_items.extend(_extract_evidence_from_trends(trends))

        # Quality scores
        quality = raw_context.get("quality_scores", raw_context.get("quality", {}))
        if quality and isinstance(quality, dict):
            q_evidence, q_sum = _extract_evidence_from_quality(quality)
            evidence_items.extend(q_evidence)
            if q_sum:
                quality_scores_data = q_sum

        # Data freshness
        freshness = raw_context.get("data_freshness", raw_context.get("last_sync_at"))
        if freshness and not data_freshness:
            if isinstance(freshness, datetime):
                data_freshness = freshness
            elif isinstance(freshness, str):
                import contextlib

                with contextlib.suppress(ValueError, TypeError):
                    data_freshness = datetime.fromisoformat(freshness)

    # Deduplicate evidence items by (source, metric) pair
    seen: set[tuple[str, str]] = set()
    unique_items: list[EvidenceItem] = []
    for item in evidence_items:
        key = (item.source, item.metric)
        if key not in seen:
            seen.add(key)
            unique_items.append(item)

    snapshot = DataSnapshotV1(
        data_freshness=data_freshness,
        evidence_items=unique_items,
        profile=profile_data,
        financial_summary=financial_summary if financial_summary else None,
        aging_summary=aging_summary if aging_summary else None,
        gst_summary=gst_summary_data if gst_summary_data else None,
        monthly_trends=monthly_trends_data,
        quality_scores=quality_scores_data,
        perspectives_used=perspectives_used,
    )

    return snapshot


# Total available perspectives in the system
TOTAL_PERSPECTIVES = 4  # compliance, quality, strategy, insight


class ConfidenceBreakdown(TypedDict):
    """Breakdown of confidence score factors."""

    overall: float
    data_completeness: float
    data_freshness: float
    knowledge_match: float
    perspective_coverage: float


def calculate_confidence(
    snapshot: DataSnapshotV1 | None = None,
    data_freshness: datetime | None = None,
    knowledge_chunks_count: int = 0,
    perspectives_used: list[str] | None = None,
) -> ConfidenceBreakdown:
    """Calculate a meaningful confidence score from data quality signals.

    Factors:
    - data_completeness (40%): How many snapshot sections are non-null
    - data_freshness (25%): 1.0 if synced today, decays to 0.3 at 30 days, floors at 0.1
    - knowledge_match (20%): Based on RAG chunk count
    - perspective_coverage (15%): Perspectives used / total available

    Returns:
        ConfidenceBreakdown with overall and per-factor scores (all 0-1).
    """
    # --- Data completeness ---
    if snapshot:
        sections = [
            snapshot.profile,
            snapshot.financial_summary,
            snapshot.aging_summary,
            snapshot.gst_summary,
            snapshot.monthly_trends,
            snapshot.quality_scores,
        ]
        non_null = sum(1 for s in sections if s is not None)
        completeness = non_null / len(sections)
    else:
        completeness = 0.1

    # --- Data freshness ---
    if data_freshness:
        now = datetime.now(UTC)
        if hasattr(data_freshness, "tzinfo") and data_freshness.tzinfo is None:
            data_freshness = data_freshness.replace(tzinfo=UTC)
        days_old = (now - data_freshness).total_seconds() / 86400
        if days_old <= 0:
            freshness = 1.0
        elif days_old >= 30:
            freshness = 0.1
        else:
            # Linear decay from 1.0 to 0.3 over 30 days, then floor at 0.1
            freshness = max(0.1, 1.0 - (days_old / 30) * 0.7)
    else:
        freshness = 0.3  # Unknown freshness

    # --- Knowledge match ---
    if knowledge_chunks_count >= 4:
        knowledge = 0.9
    elif knowledge_chunks_count >= 1:
        knowledge = 0.6
    else:
        knowledge = 0.3

    # --- Perspective coverage ---
    n_perspectives = len(perspectives_used) if perspectives_used else 0
    coverage = n_perspectives / TOTAL_PERSPECTIVES if TOTAL_PERSPECTIVES > 0 else 0.0

    # --- Weighted overall ---
    overall = completeness * 0.40 + freshness * 0.25 + knowledge * 0.20 + coverage * 0.15

    return ConfidenceBreakdown(
        overall=round(overall, 3),
        data_completeness=round(completeness, 3),
        data_freshness=round(freshness, 3),
        knowledge_match=round(knowledge, 3),
        perspective_coverage=round(coverage, 3),
    )


def trim_snapshot_to_size(
    snapshot: DataSnapshotV1,
    max_size_bytes: int = MAX_SNAPSHOT_SIZE_BYTES,
) -> dict[str, Any]:
    """Trim a snapshot to fit within the size limit.

    Trim priority (lowest priority removed first):
    1. Remove extended_data
    2. Truncate monthly_trends to last 3 months
    3. Remove raw_data
    4. Core summaries (profile, financial, aging, gst, quality) always preserved

    Args:
        snapshot: The DataSnapshotV1 model to trim.
        max_size_bytes: Maximum size in bytes (default 50KB).

    Returns:
        Dict suitable for JSONB storage, trimmed to fit size limit.
    """
    data = snapshot.model_dump(mode="json")

    # Remove any extended_data if present
    data.pop("extended_data", None)
    data.pop("raw_data", None)

    serialized = json.dumps(data, default=str)
    if len(serialized.encode("utf-8")) <= max_size_bytes:
        return data

    # Step 2: Truncate monthly_trends to 3 months
    if data.get("monthly_trends") and len(data["monthly_trends"]) > 3:
        data["monthly_trends"] = data["monthly_trends"][:3]

    serialized = json.dumps(data, default=str)
    if len(serialized.encode("utf-8")) <= max_size_bytes:
        return data

    # Step 3: Remove monthly_trends entirely
    data["monthly_trends"] = None

    serialized = json.dumps(data, default=str)
    if len(serialized.encode("utf-8")) <= max_size_bytes:
        return data

    # Step 4: Trim evidence items to top 10
    if data.get("evidence_items") and len(data["evidence_items"]) > 10:
        data["evidence_items"] = data["evidence_items"][:10]

    serialized = json.dumps(data, default=str)
    if len(serialized.encode("utf-8")) <= max_size_bytes:
        return data

    # Step 5: Remove quality_scores
    data["quality_scores"] = None

    logger.warning(
        f"Snapshot still exceeds {max_size_bytes} bytes after trimming. "
        f"Final size: {len(json.dumps(data, default=str).encode('utf-8'))} bytes"
    )

    return data
