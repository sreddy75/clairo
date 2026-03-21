"""Context building service for client-aware AI chat.

Orchestrates context retrieval from aggregation tables and formats
it for injection into AI prompts.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.xero.models import (
    XeroAsset,
    XeroAssetStatus,
    XeroBankTransaction,
    XeroConnection,
    XeroCreditNote,
    XeroInvoice,
    XeroJournal,
    XeroManualJournal,
    XeroOverpayment,
    XeroPayment,
    XeroPrepayment,
    XeroPurchaseOrder,
    XeroQuote,
    XeroRepeatingInvoice,
    XeroReport,
    XeroReportType,
)
from app.modules.knowledge.aggregation_models import (
    ClientAPAgingSummary,
    ClientARAgingSummary,
    ClientComplianceSummary,
    ClientExpenseSummary,
    ClientGSTSummary,
    ClientMonthlyTrend,
    PeriodType,
)
from app.modules.knowledge.aggregation_repository import AggregationRepository
from app.modules.knowledge.intent_detector import QueryIntent, QueryIntentDetector
from app.modules.knowledge.token_budget import TokenBudgetManager

logger = logging.getLogger(__name__)


@dataclass
class ClientProfile:
    """Client profile data for AI context (Tier 1).

    Note: "Client" here refers to the Xero organization (XeroConnection),
    not individual contacts (XeroClient).
    """

    id: UUID  # This is the XeroConnection.id
    name: str  # XeroConnection.organization_name
    abn: str | None  # From aggregation profile if available
    entity_type: str | None
    industry_code: str | None
    gst_registered: bool
    revenue_bracket: str | None
    employee_count: int
    connection_id: UUID  # Same as id (for compatibility)
    last_sync_at: datetime | None


@dataclass
class ClientContext:
    """Complete client context for AI chat.

    Note: client_id here refers to XeroConnection.id (the organization),
    not XeroClient.id (contacts within the organization).
    """

    client_id: UUID  # XeroConnection.id
    profile: ClientProfile
    query_intent: QueryIntent
    summaries: dict[str, Any] = field(default_factory=dict)
    raw_data: list[dict[str, Any]] = field(default_factory=list)
    token_count: int = 0
    data_freshness: datetime | None = None


class ContextBuilderService:
    """Service for building client-aware AI context.

    Retrieves and formats financial data from aggregation tables
    based on query intent and token budget.
    """

    # Freshness threshold (24 hours)
    STALE_DATA_THRESHOLD = timedelta(hours=24)

    def __init__(self, db: AsyncSession):
        """Initialize with database session.

        Args:
            db: Async database session.
        """
        self.db = db
        self.repo = AggregationRepository(db)
        self.intent_detector = QueryIntentDetector()
        self.budget_manager = TokenBudgetManager()

    async def build_context(
        self,
        connection_id: UUID,
        query: str,
        conversation_history: list[str] | None = None,
        include_tier3: bool = False,
    ) -> ClientContext:
        """Build complete context for a client query.

        Args:
            connection_id: The XeroConnection ID (organization) to build context for.
            query: The user's query text.
            conversation_history: Optional conversation history for intent detection.
            include_tier3: Whether to include raw transaction details.

        Returns:
            ClientContext with profile, summaries, and optional raw data.
        """
        # Reset budget manager for new context
        self.budget_manager = TokenBudgetManager()

        # Detect query intent
        intent_match = self.intent_detector.detect(query, conversation_history)
        intent = intent_match.intent

        logger.info(
            f"Building context for organization {connection_id}, "
            f"intent={intent.value}, score={intent_match.score}, query='{query[:50]}...'"
        )

        # Build Tier 1: Profile (always included)
        profile = await self._get_tier1_profile(connection_id)

        # Initialize context
        context = ClientContext(
            client_id=connection_id,  # Still called client_id in the dataclass for API compatibility
            profile=profile,
            query_intent=intent,
            data_freshness=profile.last_sync_at,
        )

        # Build Tier 2: Intent-specific summaries
        summaries = await self._get_tier2_summaries(connection_id, intent)
        context.summaries = summaries

        # Build Tier 3: Raw data (if requested and drill-down detected)
        if include_tier3 or self.intent_detector.is_drill_down_request(query):
            raw_data = await self._get_tier3_details(connection_id, intent, query)
            context.raw_data = raw_data

        # Calculate total token count
        context.token_count = sum(
            self.budget_manager.get_usage_summary()["total"]["used"] for _ in [1]
        )

        return context

    async def _get_tier1_profile(self, connection_id: UUID) -> ClientProfile:
        """Get client profile data (Tier 1).

        Falls back to basic XeroConnection data if aggregated profile not available.

        Args:
            connection_id: The XeroConnection ID (organization).

        Returns:
            ClientProfile with available data.
        """
        # Get the XeroConnection (organization)
        result = await self.db.execute(
            select(XeroConnection).where(XeroConnection.id == connection_id)
        )
        connection = result.scalar_one_or_none()

        if not connection:
            raise ValueError(f"Organization {connection_id} not found")

        # Try to get aggregated profile (keyed by connection_id)
        ai_profile = await self.repo.get_profile_by_connection(connection_id)

        profile = ClientProfile(
            id=connection_id,
            name=connection.organization_name,
            abn=None,  # ABN not stored in connection or AI profile
            entity_type=ai_profile.entity_type if ai_profile else None,
            industry_code=ai_profile.industry_code if ai_profile else None,
            gst_registered=ai_profile.gst_registered if ai_profile else False,
            revenue_bracket=ai_profile.revenue_bracket.value
            if ai_profile and ai_profile.revenue_bracket
            else None,
            employee_count=ai_profile.employee_count if ai_profile else 0,
            connection_id=connection_id,
            last_sync_at=connection.last_full_sync_at,
        )

        # Record token usage
        profile_text = self._format_profile(profile)
        self.budget_manager.record_usage(profile_text, "tier1")

        return profile

    async def _get_tier2_summaries(
        self,
        connection_id: UUID,
        intent: QueryIntent,
    ) -> dict[str, Any]:
        """Get intent-specific financial summaries (Tier 2).

        Args:
            connection_id: The XeroConnection ID (organization).
            intent: The detected query intent.

        Returns:
            Dict of summary data keyed by summary type.
        """
        summaries: dict[str, Any] = {}

        if intent == QueryIntent.TAX_DEDUCTIONS:
            # Fetch expense summaries and monthly trends
            expense_summaries = await self.repo.get_expense_summaries(
                connection_id, PeriodType.QUARTER, limit=4
            )
            summaries["expenses"] = [self._format_expense_summary(s) for s in expense_summaries]

            trends = await self.repo.get_monthly_trends(connection_id, months=6)
            summaries["monthly_trends"] = [self._format_monthly_trend(t) for t in trends]

        elif intent == QueryIntent.CASH_FLOW:
            # Fetch AR/AP aging and monthly trends
            ar_aging = await self.repo.get_latest_ar_aging(connection_id)
            if ar_aging:
                summaries["ar_aging"] = self._format_ar_aging(ar_aging)

            ap_aging = await self.repo.get_latest_ap_aging(connection_id)
            if ap_aging:
                summaries["ap_aging"] = self._format_ap_aging(ap_aging)

            trends = await self.repo.get_monthly_trends(connection_id, months=6)
            summaries["monthly_trends"] = [self._format_monthly_trend(t) for t in trends]

        elif intent == QueryIntent.GST_BAS:
            # Fetch GST summaries for current and prior quarters
            gst_summaries = await self.repo.get_gst_summaries(
                connection_id, PeriodType.QUARTER, limit=4
            )
            summaries["gst"] = [self._format_gst_summary(s) for s in gst_summaries]
            logger.info(
                f"GST_BAS intent: fetched {len(gst_summaries)} GST summaries for connection {connection_id}"
            )

        elif intent == QueryIntent.COMPLIANCE:
            # Fetch compliance summaries
            compliance_summaries = await self.repo.get_compliance_summaries(
                connection_id, PeriodType.QUARTER, limit=4
            )
            summaries["compliance"] = [
                self._format_compliance_summary(s) for s in compliance_summaries
            ]

        else:  # GENERAL
            # Basic summaries only
            ar_aging = await self.repo.get_latest_ar_aging(connection_id)
            if ar_aging:
                summaries["ar_aging"] = self._format_ar_aging(ar_aging)

            trends = await self.repo.get_monthly_trends(connection_id, months=3)
            summaries["monthly_trends"] = [self._format_monthly_trend(t) for t in trends]

        # Record token usage
        summaries_text = str(summaries)
        self.budget_manager.record_usage(summaries_text, "tier2")

        return summaries

    async def _get_tier3_details(
        self,
        connection_id: UUID,
        intent: QueryIntent,
        query: str,
    ) -> list[dict[str, Any]]:
        """Get raw transaction details (Tier 3).

        Only fetches when drill-down is requested and respects token budget.

        Args:
            connection_id: The XeroConnection ID (organization).
            intent: The detected query intent.
            query: The user's query for context.

        Returns:
            List of raw transaction/invoice data.
        """
        raw_data: list[dict[str, Any]] = []

        # Check remaining budget
        remaining = self.budget_manager.remaining_budget("tier3")
        if remaining < 100:
            return raw_data

        # Fetch relevant raw data based on intent
        if intent in (QueryIntent.CASH_FLOW, QueryIntent.TAX_DEDUCTIONS):
            # Fetch recent invoices for this organization
            result = await self.db.execute(
                select(XeroInvoice)
                .where(XeroInvoice.connection_id == connection_id)
                .order_by(XeroInvoice.issue_date.desc())
                .limit(20)
            )
            invoices = result.scalars().all()

            for inv in invoices:
                inv_data = {
                    "type": "invoice",
                    "number": inv.invoice_number,
                    "invoice_type": inv.invoice_type.value if inv.invoice_type else None,
                    "status": inv.status.value if inv.status else None,
                    "issue_date": inv.issue_date.isoformat() if inv.issue_date else None,
                    "due_date": inv.due_date.isoformat() if inv.due_date else None,
                    "total": float(inv.total_amount) if inv.total_amount else 0,
                    "tax": float(inv.tax_amount) if inv.tax_amount else 0,
                }
                raw_data.append(inv_data)

                # Check budget
                if not self.budget_manager.fits_budget(str(raw_data), "tier3"):
                    raw_data.pop()
                    break

        elif intent == QueryIntent.GST_BAS:
            # Fetch recent bank transactions for GST analysis for this organization
            result = await self.db.execute(
                select(XeroBankTransaction)
                .where(XeroBankTransaction.connection_id == connection_id)
                .order_by(XeroBankTransaction.transaction_date.desc())
                .limit(30)
            )
            transactions = result.scalars().all()

            for txn in transactions:
                txn_data = {
                    "type": "transaction",
                    "reference": txn.reference,
                    "transaction_type": txn.transaction_type.value
                    if txn.transaction_type
                    else None,
                    "date": txn.transaction_date.isoformat() if txn.transaction_date else None,
                    "total": float(txn.total_amount) if txn.total_amount else 0,
                    "tax": float(txn.tax_amount) if txn.tax_amount else 0,
                }
                raw_data.append(txn_data)

                if not self.budget_manager.fits_budget(str(raw_data), "tier3"):
                    raw_data.pop()
                    break

        # Record usage
        self.budget_manager.record_usage(str(raw_data), "tier3")

        return raw_data

    def format_context_for_prompt(self, context: ClientContext) -> str:
        """Format client context for injection into AI prompt.

        Args:
            context: The built client context.

        Returns:
            Formatted string ready for prompt injection.
        """
        sections = []

        # Client Profile Section
        sections.append("## Client Information")
        sections.append(self._format_profile(context.profile))

        # Data Freshness Note
        if context.data_freshness:
            age = datetime.now(UTC) - context.data_freshness.replace(tzinfo=UTC)
            if age > self.STALE_DATA_THRESHOLD:
                sections.append(
                    f"\n⚠️ Data last synced: {context.data_freshness.strftime('%Y-%m-%d %H:%M')} "
                    f"({age.days} days ago - may be outdated)"
                )
            else:
                sections.append(
                    f"\nData last synced: {context.data_freshness.strftime('%Y-%m-%d %H:%M')}"
                )

        # Financial Summaries Section
        if context.summaries:
            sections.append("\n## Financial Summary")
            sections.append(self._format_summaries(context.summaries, context.query_intent))

        # Raw Data Section (if present)
        if context.raw_data:
            sections.append("\n## Transaction Details")
            sections.append(self._format_raw_data(context.raw_data))

        return "\n".join(sections)

    def _format_profile(self, profile: ClientProfile) -> str:
        """Format profile as text block."""
        lines = [
            f"- Name: {profile.name}",
        ]
        if profile.abn:
            lines.append(f"- ABN: {profile.abn}")
        if profile.gst_registered:
            lines.append("- GST Registered: Yes")
        if profile.revenue_bracket:
            lines.append(f"- Revenue Bracket: {profile.revenue_bracket}")
        if profile.employee_count > 0:
            lines.append(f"- Employees: {profile.employee_count}")
        if profile.entity_type:
            lines.append(f"- Entity Type: {profile.entity_type}")

        return "\n".join(lines)

    def _format_summaries(self, summaries: dict[str, Any], intent: QueryIntent) -> str:
        """Format summaries based on intent."""
        lines = []

        if "expenses" in summaries:
            lines.append("\n### Expense Summary")
            for exp in summaries["expenses"]:
                lines.append(f"- {exp['period']}: ${exp['total']:,.2f} (GST: ${exp['gst']:,.2f})")

        if "ar_aging" in summaries:
            ar = summaries["ar_aging"]
            lines.append("\n### Accounts Receivable Aging")
            lines.append(f"- Current: ${ar['current']:,.2f}")
            lines.append(f"- 31-60 days: ${ar['days_31_60']:,.2f}")
            lines.append(f"- 61-90 days: ${ar['days_61_90']:,.2f}")
            lines.append(f"- Over 90 days: ${ar['over_90']:,.2f}")
            lines.append(f"- **Total Outstanding: ${ar['total']:,.2f}**")
            if ar.get("top_debtors"):
                lines.append(
                    "- Top Debtors: "
                    + ", ".join(f"{d['name']} (${d['amount']:,.2f})" for d in ar["top_debtors"][:3])
                )

        if "ap_aging" in summaries:
            ap = summaries["ap_aging"]
            lines.append("\n### Accounts Payable Aging")
            lines.append(f"- Current: ${ap['current']:,.2f}")
            lines.append(f"- 31-60 days: ${ap['days_31_60']:,.2f}")
            lines.append(f"- 61-90 days: ${ap['days_61_90']:,.2f}")
            lines.append(f"- Over 90 days: ${ap['over_90']:,.2f}")
            lines.append(f"- **Total Payable: ${ap['total']:,.2f}**")

        if "gst" in summaries:
            lines.append("\n### GST Summary")
            for gst in summaries["gst"]:
                lines.append(f"- {gst['period']}:")
                lines.append(f"  - GST on Sales (1A): ${gst['gst_on_sales']:,.2f}")
                lines.append(f"  - GST on Purchases (1B): ${gst['gst_on_purchases']:,.2f}")
                lines.append(f"  - Net GST: ${gst['net_gst']:,.2f}")

        if "compliance" in summaries:
            lines.append("\n### Compliance Summary")
            for comp in summaries["compliance"]:
                lines.append(f"- {comp['period']}:")
                lines.append(f"  - Total Wages: ${comp['wages']:,.2f}")
                lines.append(f"  - PAYG Withheld: ${comp['payg']:,.2f}")
                lines.append(f"  - Superannuation: ${comp['super']:,.2f}")
                lines.append(f"  - Employees: {comp['employees']}")

        if "monthly_trends" in summaries:
            lines.append("\n### Monthly Trends")
            for trend in summaries["monthly_trends"]:
                lines.append(
                    f"- {trend['period']}: "
                    f"Revenue ${trend['revenue']:,.2f}, "
                    f"Expenses ${trend['expenses']:,.2f}, "
                    f"Profit ${trend['profit']:,.2f}"
                )

        return "\n".join(lines)

    def _format_raw_data(self, raw_data: list[dict[str, Any]]) -> str:
        """Format raw transaction data as markdown list."""
        lines = []
        for item in raw_data[:15]:  # Limit display
            if item["type"] == "invoice":
                lines.append(
                    f"- Invoice {item['number']}: {item['status']} - "
                    f"${item['total']:,.2f} (Due: {item['due_date']})"
                )
            elif item["type"] == "transaction":
                lines.append(
                    f"- {item['transaction_type']}: {item['reference']} - "
                    f"${item['total']:,.2f} ({item['date']})"
                )
        return "\n".join(lines)

    # =========================================================================
    # Summary Formatting Helpers
    # =========================================================================

    def _format_expense_summary(self, summary: ClientExpenseSummary) -> dict[str, Any]:
        """Format expense summary for context."""
        return {
            "period": f"{summary.period_start} to {summary.period_end}",
            "total": float(summary.total_expenses),
            "gst": float(summary.total_gst),
            "transaction_count": summary.transaction_count,
            "by_account": summary.by_account_code,
        }

    def _format_ar_aging(self, aging: ClientARAgingSummary) -> dict[str, Any]:
        """Format AR aging for context."""
        return {
            "as_of": aging.as_of_date.isoformat(),
            "current": float(aging.current_amount),
            "days_31_60": float(aging.days_31_60),
            "days_61_90": float(aging.days_61_90),
            "over_90": float(aging.over_90_days),
            "total": float(aging.total_outstanding),
            "top_debtors": aging.top_debtors,
        }

    def _format_ap_aging(self, aging: ClientAPAgingSummary) -> dict[str, Any]:
        """Format AP aging for context."""
        return {
            "as_of": aging.as_of_date.isoformat(),
            "current": float(aging.current_amount),
            "days_31_60": float(aging.days_31_60),
            "days_61_90": float(aging.days_61_90),
            "over_90": float(aging.over_90_days),
            "total": float(aging.total_outstanding),
            "top_creditors": aging.top_creditors,
        }

    def _format_gst_summary(self, summary: ClientGSTSummary) -> dict[str, Any]:
        """Format GST summary for context."""
        return {
            "period": f"{summary.period_start} to {summary.period_end}",
            "gst_on_sales": float(summary.gst_on_sales_1a),
            "gst_on_purchases": float(summary.gst_on_purchases_1b),
            "net_gst": float(summary.net_gst),
            "total_sales": float(summary.total_sales),
            "total_purchases": float(summary.total_purchases),
        }

    def _format_monthly_trend(self, trend: ClientMonthlyTrend) -> dict[str, Any]:
        """Format monthly trend for context."""
        return {
            "period": f"{trend.year}-{trend.month:02d}",
            "revenue": float(trend.revenue),
            "expenses": float(trend.expenses),
            "profit": float(trend.gross_profit),
            "cashflow": float(trend.net_cashflow),
        }

    def _format_compliance_summary(self, summary: ClientComplianceSummary) -> dict[str, Any]:
        """Format compliance summary for context."""
        return {
            "period": f"{summary.period_start} to {summary.period_end}",
            "wages": float(summary.total_wages),
            "payg": float(summary.total_payg_withheld),
            "super": float(summary.total_super),
            "employees": summary.employee_count,
            "contractor_payments": float(summary.contractor_payments),
            "contractors": summary.contractor_count,
        }

    def is_data_stale(self, context: ClientContext) -> bool:
        """Check if client data is stale.

        Args:
            context: The client context.

        Returns:
            True if data is older than threshold.
        """
        if not context.data_freshness:
            return True

        age = datetime.now(UTC) - context.data_freshness.replace(tzinfo=UTC)
        return age > self.STALE_DATA_THRESHOLD

    # =========================================================================
    # Multi-Perspective Context Building (for Spec 014)
    # =========================================================================

    async def build_perspective_context(
        self,
        connection_id: UUID,
        perspectives: list[str],
        query: str,
    ) -> dict[str, Any]:
        """Build context for multiple perspectives.

        Used by the multi-agent orchestrator to gather context relevant to
        each analysis perspective (Compliance, Quality, Strategy, Insight).

        Args:
            connection_id: The XeroConnection ID (organization).
            perspectives: List of perspective names to include.
            query: The user's query text.

        Returns:
            Dict with context keyed by perspective name.
        """
        from app.modules.agents.schemas import Perspective

        # Reset budget manager
        self.budget_manager = TokenBudgetManager()

        # Get profile first (always needed)
        profile = await self._get_tier1_profile(connection_id)

        context: dict[str, Any] = {
            "profile": self._format_profile(profile),
            "data_freshness": profile.last_sync_at,
            "perspectives": {},
        }

        # Build context for each perspective
        for perspective_name in perspectives:
            try:
                perspective = Perspective(perspective_name.lower())
                perspective_context = await self._get_perspective_context(
                    connection_id, perspective, query
                )
                context["perspectives"][perspective_name] = perspective_context
            except ValueError:
                logger.warning(f"Unknown perspective: {perspective_name}")
                continue

        return context

    async def _get_perspective_context(
        self,
        connection_id: UUID,
        perspective: "Perspective",
        query: str,
    ) -> dict[str, Any]:
        """Get context specific to a perspective.

        Args:
            connection_id: The XeroConnection ID.
            perspective: The perspective to get context for.
            query: The user's query.

        Returns:
            Dict with perspective-specific context.
        """
        from app.modules.agents.schemas import Perspective

        context: dict[str, Any] = {}

        if perspective == Perspective.COMPLIANCE:
            # For compliance, we mainly need GST status and compliance summaries
            gst_summaries = await self.repo.get_gst_summaries(
                connection_id, PeriodType.QUARTER, limit=4
            )
            context["gst_summaries"] = [self._format_gst_summary(s) for s in gst_summaries]

            compliance_summaries = await self.repo.get_compliance_summaries(
                connection_id, PeriodType.QUARTER, limit=2
            )
            context["compliance_summaries"] = [
                self._format_compliance_summary(s) for s in compliance_summaries
            ]

        elif perspective == Perspective.QUALITY:
            # For quality, we need data quality indicators
            context["quality_data"] = await self._get_quality_context(connection_id)

        elif perspective == Perspective.STRATEGY:
            # For strategy, we need trends, expense breakdown, and financial ratios
            trends = await self.repo.get_monthly_trends(connection_id, months=12)
            context["monthly_trends"] = [self._format_monthly_trend(t) for t in trends]

            expense_summaries = await self.repo.get_expense_summaries(
                connection_id, PeriodType.QUARTER, limit=4
            )
            context["expense_summaries"] = [
                self._format_expense_summary(s) for s in expense_summaries
            ]

            # Add financial report context for strategic analysis
            report_context = await self.get_client_report_context(connection_id)
            if report_context:
                context["report_context"] = report_context

            # Add extended data context (Spec 024/025: assets, POs, payments, etc.)
            extended_context = await self.get_client_extended_data_context(connection_id)
            if extended_context:
                context["extended_data"] = extended_context

        elif perspective == Perspective.INSIGHT:
            # For insight, we need all trends, aging data, and financial reports
            trends = await self.repo.get_monthly_trends(connection_id, months=12)
            context["monthly_trends"] = [self._format_monthly_trend(t) for t in trends]

            ar_aging = await self.repo.get_latest_ar_aging(connection_id)
            if ar_aging:
                context["ar_aging"] = self._format_ar_aging(ar_aging)

            ap_aging = await self.repo.get_latest_ap_aging(connection_id)
            if ap_aging:
                context["ap_aging"] = self._format_ap_aging(ap_aging)

            # Detect anomalies
            context["anomalies"] = self._detect_anomalies(trends)

            # Check thresholds
            gst_summaries = await self.repo.get_gst_summaries(
                connection_id, PeriodType.QUARTER, limit=4
            )
            context["threshold_alerts"] = self._check_thresholds(trends, gst_summaries)

            # Add financial report context for deeper insights
            report_context = await self.get_client_report_context(connection_id)
            if report_context:
                context["report_context"] = report_context

            # Add extended data context (Spec 024/025: assets, POs, payments, etc.)
            extended_context = await self.get_client_extended_data_context(connection_id)
            if extended_context:
                context["extended_data"] = extended_context

        return context

    async def _get_quality_context(self, connection_id: UUID) -> dict[str, Any]:
        """Get data quality context for a connection.

        Args:
            connection_id: The XeroConnection ID.

        Returns:
            Dict with quality indicators.
        """
        quality_data: dict[str, Any] = {
            "issues": [],
            "reconciliation_status": "unknown",
            "completeness": "unknown",
        }

        try:
            # Check for uncoded transactions (Ask My Accountant account)
            # This would integrate with quality scores from Spec 008
            from app.modules.quality.models import QualityIssue, QualityScore

            # Get latest quality score
            result = await self.db.execute(
                select(QualityScore)
                .where(QualityScore.connection_id == connection_id)
                .order_by(QualityScore.created_at.desc())
                .limit(1)
            )
            quality_score = result.scalar_one_or_none()

            if quality_score:
                quality_data["overall_score"] = quality_score.overall_score
                quality_data["completeness_score"] = quality_score.completeness_score
                quality_data["categorization_score"] = quality_score.categorization_score
                quality_data["reconciliation_score"] = quality_score.reconciliation_score

            # Get open issues
            result = await self.db.execute(
                select(QualityIssue)
                .where(
                    QualityIssue.connection_id == connection_id,
                    QualityIssue.is_dismissed == False,  # noqa: E712
                    QualityIssue.resolved_at.is_(None),
                )
                .order_by(QualityIssue.severity.desc())
                .limit(10)
            )
            issues = result.scalars().all()

            quality_data["issues"] = [
                {
                    "code": issue.issue_code,
                    "severity": issue.severity.value if issue.severity else "info",
                    "description": issue.description,
                    "affected_count": issue.affected_count,
                }
                for issue in issues
            ]

        except Exception as e:
            logger.warning(f"Error fetching quality context: {e}")

        return quality_data

    def _detect_anomalies(self, trends: list[ClientMonthlyTrend]) -> list[dict[str, Any]]:
        """Detect anomalies in monthly trends.

        Args:
            trends: List of monthly trend records.

        Returns:
            List of detected anomalies.
        """
        if len(trends) < 3:
            return []

        anomalies = []

        # Calculate averages
        revenues = [float(t.revenue) for t in trends]
        expenses = [float(t.expenses) for t in trends]

        avg_revenue = sum(revenues) / len(revenues) if revenues else 0
        avg_expense = sum(expenses) / len(expenses) if expenses else 0

        # Check for significant deviations (>50% from average)
        for trend in trends[-6:]:  # Check last 6 months
            revenue = float(trend.revenue)
            expense = float(trend.expenses)

            if avg_revenue > 0:
                if revenue > avg_revenue * 1.5:
                    anomalies.append(
                        {
                            "type": "revenue_spike",
                            "period": f"{trend.year}-{trend.month:02d}",
                            "value": revenue,
                            "average": avg_revenue,
                            "deviation_pct": ((revenue - avg_revenue) / avg_revenue) * 100,
                        }
                    )
                elif revenue < avg_revenue * 0.5:
                    anomalies.append(
                        {
                            "type": "revenue_drop",
                            "period": f"{trend.year}-{trend.month:02d}",
                            "value": revenue,
                            "average": avg_revenue,
                            "deviation_pct": ((avg_revenue - revenue) / avg_revenue) * 100,
                        }
                    )

            if avg_expense > 0 and expense > avg_expense * 1.5:
                anomalies.append(
                    {
                        "type": "expense_spike",
                        "period": f"{trend.year}-{trend.month:02d}",
                        "value": expense,
                        "average": avg_expense,
                        "deviation_pct": ((expense - avg_expense) / avg_expense) * 100,
                    }
                )

        return anomalies

    def _check_thresholds(
        self,
        trends: list[ClientMonthlyTrend],
        gst_summaries: list[ClientGSTSummary],
    ) -> list[dict[str, Any]]:
        """Check for compliance threshold alerts.

        Args:
            trends: Monthly trend data.
            gst_summaries: GST summary data.

        Returns:
            List of threshold alerts.
        """
        alerts = []

        # Calculate annual revenue from last 12 months of trends
        if trends:
            annual_revenue = sum(float(t.revenue) for t in trends[-12:])

            # GST threshold check ($75,000)
            if annual_revenue >= 65000 and annual_revenue < 75000:
                alerts.append(
                    {
                        "type": "gst_threshold_approaching",
                        "current": annual_revenue,
                        "threshold": 75000,
                        "message": f"Revenue (${annual_revenue:,.0f}) approaching GST threshold ($75,000)",
                    }
                )
            elif annual_revenue >= 75000:
                alerts.append(
                    {
                        "type": "gst_threshold_exceeded",
                        "current": annual_revenue,
                        "threshold": 75000,
                        "message": f"Revenue (${annual_revenue:,.0f}) exceeds GST threshold - registration required",
                    }
                )

        return alerts

    def format_perspective_context_for_prompt(
        self,
        perspective_context: dict[str, Any],
        perspective: str,
    ) -> str:
        """Format perspective-specific context for prompt.

        Args:
            perspective_context: Context data for the perspective.
            perspective: The perspective name.

        Returns:
            Formatted string for prompt injection.
        """
        lines = [f"### {perspective.title()} Context"]

        if perspective.lower() == "compliance":
            if "gst_summaries" in perspective_context:
                lines.append("\nGST Summary (last 4 quarters):")
                for gst in perspective_context["gst_summaries"]:
                    lines.append(
                        f"- {gst['period']}: Sales GST=${gst['gst_on_sales']:,.2f}, "
                        f"Purchases GST=${gst['gst_on_purchases']:,.2f}, "
                        f"Net=${gst['net_gst']:,.2f}"
                    )

        elif perspective.lower() == "quality":
            qd = perspective_context.get("quality_data", {})
            if "overall_score" in qd:
                lines.append(f"\nData Quality Score: {qd['overall_score']}/100")
            if qd.get("issues"):
                lines.append("\nOpen Issues:")
                for issue in qd["issues"][:5]:
                    lines.append(f"- [{issue['severity'].upper()}] {issue['description']}")

        elif perspective.lower() == "strategy":
            if "monthly_trends" in perspective_context:
                lines.append("\nRevenue Trend (last 6 months):")
                for trend in perspective_context["monthly_trends"][-6:]:
                    lines.append(
                        f"- {trend['period']}: Revenue=${trend['revenue']:,.2f}, "
                        f"Expenses=${trend['expenses']:,.2f}"
                    )

            # Report context for strategy perspective
            if perspective_context.get("report_context"):
                rc = perspective_context["report_context"]
                if rc.get("profit_and_loss"):
                    pl = rc["profit_and_loss"]
                    lines.append("\nProfit & Loss Summary:")
                    lines.append(f"- Total Income: ${pl.get('total_income', 0):,.2f}")
                    lines.append(f"- Gross Profit: ${pl.get('gross_profit', 0):,.2f}")
                    lines.append(f"- Net Profit: ${pl.get('net_profit', 0):,.2f}")
                    if pl.get("gross_margin_pct") is not None:
                        lines.append(f"- Gross Margin: {pl.get('gross_margin_pct', 0):.1f}%")
                    if pl.get("net_margin_pct") is not None:
                        lines.append(f"- Net Margin: {pl.get('net_margin_pct', 0):.1f}%")

                if rc.get("balance_sheet"):
                    bs = rc["balance_sheet"]
                    lines.append("\nBalance Sheet Summary:")
                    lines.append(f"- Total Assets: ${bs.get('total_assets', 0):,.2f}")
                    lines.append(f"- Equity: ${bs.get('equity', 0):,.2f}")
                    if bs.get("current_ratio") is not None:
                        lines.append(f"- Current Ratio: {bs.get('current_ratio', 0):.2f}")

            # Extended data context for strategy (Spec 024/025)
            if perspective_context.get("extended_data"):
                ed = perspective_context["extended_data"]
                self._format_extended_data_for_prompt(lines, ed)

        elif perspective.lower() == "insight":
            if perspective_context.get("anomalies"):
                lines.append("\nDetected Anomalies:")
                for anomaly in perspective_context["anomalies"]:
                    lines.append(
                        f"- {anomaly['type'].replace('_', ' ').title()} in {anomaly['period']}: "
                        f"{anomaly['deviation_pct']:.1f}% deviation from average"
                    )
            if perspective_context.get("threshold_alerts"):
                lines.append("\nThreshold Alerts:")
                for alert in perspective_context["threshold_alerts"]:
                    lines.append(f"- {alert['message']}")

            # Report context for insight perspective
            if perspective_context.get("report_context"):
                rc = perspective_context["report_context"]
                if rc.get("profit_and_loss"):
                    pl = rc["profit_and_loss"]
                    lines.append("\nProfit & Loss Summary:")
                    lines.append(f"- Total Income: ${pl.get('total_income', 0):,.2f}")
                    lines.append(f"- Gross Profit: ${pl.get('gross_profit', 0):,.2f}")
                    lines.append(f"- Net Profit: ${pl.get('net_profit', 0):,.2f}")
                    if pl.get("gross_margin_pct") is not None:
                        lines.append(f"- Gross Margin: {pl.get('gross_margin_pct', 0):.1f}%")
                    if pl.get("net_margin_pct") is not None:
                        lines.append(f"- Net Margin: {pl.get('net_margin_pct', 0):.1f}%")

                if rc.get("balance_sheet"):
                    bs = rc["balance_sheet"]
                    lines.append("\nBalance Sheet Summary:")
                    lines.append(f"- Total Assets: ${bs.get('total_assets', 0):,.2f}")
                    lines.append(f"- Total Liabilities: ${bs.get('total_liabilities', 0):,.2f}")
                    lines.append(f"- Equity: ${bs.get('equity', 0):,.2f}")
                    if bs.get("current_ratio") is not None:
                        lines.append(f"- Current Ratio: {bs.get('current_ratio', 0):.2f}")
                    if bs.get("debt_to_equity") is not None:
                        lines.append(f"- Debt/Equity: {bs.get('debt_to_equity', 0):.2f}")

                if rc.get("aged_receivables"):
                    ar = rc["aged_receivables"]
                    lines.append("\nAged Receivables Summary:")
                    lines.append(f"- Total Outstanding: ${ar.get('total', 0):,.2f}")
                    lines.append(f"- Overdue Amount: ${ar.get('overdue_total', 0):,.2f}")
                    if ar.get("overdue_pct") is not None:
                        lines.append(f"- Overdue %: {ar.get('overdue_pct', 0):.1f}%")
                    if ar.get("high_risk_contacts"):
                        lines.append(
                            "- High-Risk Contacts: "
                            + ", ".join(
                                f"{c['name']} (${c['amount']:,.2f})"
                                for c in ar["high_risk_contacts"][:3]
                            )
                        )

            # Extended data context for insight (Spec 024/025)
            if perspective_context.get("extended_data"):
                ed = perspective_context["extended_data"]
                self._format_extended_data_for_prompt(lines, ed)

        return "\n".join(lines)

    def _format_extended_data_for_prompt(
        self,
        lines: list[str],
        extended_data: dict[str, Any],
    ) -> None:
        """Format extended data (Spec 024/025) for prompt injection.

        Args:
            lines: List of lines to append to.
            extended_data: Extended data context dict.
        """
        # Fixed Assets
        if extended_data.get("fixed_assets"):
            fa = extended_data["fixed_assets"]
            lines.append("\nFixed Assets:")
            lines.append(f"- {fa.get('registered_count', 0)} registered assets")
            lines.append(f"- Total Book Value: ${fa.get('total_book_value', 0):,.2f}")
            lines.append(f"- Depreciation YTD: ${fa.get('total_depreciation_ytd', 0):,.2f}")
            if fa.get("insight"):
                lines.append(f"- Insight: {fa['insight']}")

        # Purchase Orders
        if extended_data.get("purchase_orders"):
            po = extended_data["purchase_orders"]
            if po.get("outstanding_count", 0) > 0:
                lines.append("\nPurchase Orders:")
                lines.append(
                    f"- Outstanding: {po.get('outstanding_count', 0)} POs worth ${po.get('outstanding_value', 0):,.2f}"
                )

        # Credit Notes
        if extended_data.get("credit_notes"):
            cn = extended_data["credit_notes"]
            if cn.get("insight"):
                lines.append(f"\nCredit Notes: {cn['insight']}")

        # Payments (last 90 days)
        if extended_data.get("payments"):
            pay = extended_data["payments"]
            lines.append("\nPayments (90 days):")
            lines.append(f"- Received: ${pay.get('payments_received_total', 0):,.2f}")
            lines.append(f"- Made: ${pay.get('payments_made_total', 0):,.2f}")
            lines.append(f"- Net Cash Flow: ${pay.get('net_cash_flow', 0):,.2f}")

        # Overpayments & Prepayments (available credits)
        available_credits = []
        if extended_data.get("overpayments"):
            op = extended_data["overpayments"]
            if op.get("total_available", 0) > 0:
                available_credits.append(f"Overpayments: ${op['total_available']:,.2f}")
        if extended_data.get("prepayments"):
            pp = extended_data["prepayments"]
            if pp.get("total_available", 0) > 0:
                available_credits.append(f"Prepayments: ${pp['total_available']:,.2f}")
        if available_credits:
            lines.append(f"\nAvailable Credits: {', '.join(available_credits)}")

        # Repeating Invoices (recurring revenue/expense)
        if extended_data.get("repeating_invoices"):
            ri = extended_data["repeating_invoices"]
            if ri.get("active_count", 0) > 0:
                lines.append("\nRecurring Revenue/Expense:")
                lines.append(f"- Annualized Revenue: ${ri.get('annualized_revenue', 0):,.2f}")
                lines.append(f"- Annualized Expense: ${ri.get('annualized_expense', 0):,.2f}")
                lines.append(f"- Net Recurring: ${ri.get('net_recurring', 0):,.2f}")

        # Quotes (sales pipeline)
        if extended_data.get("quotes"):
            qt = extended_data["quotes"]
            if qt.get("pending_count", 0) > 0:
                lines.append(
                    f"\nSales Pipeline: {qt['pending_count']} pending quotes worth ${qt.get('pending_value', 0):,.2f}"
                )

        # Journals (manual adjustments)
        if extended_data.get("journals"):
            jr = extended_data["journals"]
            if jr.get("manual_journals_count", 0) > 0:
                lines.append(
                    f"\nManual Journals: {jr['manual_journals_count']} entries in last 90 days - review for unusual adjustments"
                )

    # =========================================================================
    # Financial Report Context (Spec 023 - US6)
    # =========================================================================

    async def get_client_report_context(
        self,
        connection_id: UUID,
    ) -> dict[str, Any]:
        """Get client report context for AI enrichment.

        Fetches the latest cached reports (P&L, Balance Sheet, Aged Receivables)
        and extracts key metrics for AI context.

        Args:
            connection_id: The XeroConnection ID (organization).

        Returns:
            Dict with report summaries keyed by report type.
        """
        context: dict[str, Any] = {}

        # Fetch latest P&L report
        pl_report = await self._get_latest_report(connection_id, XeroReportType.PROFIT_AND_LOSS)
        if pl_report and pl_report.summary_data:
            context["profit_and_loss"] = {
                "period": pl_report.period_key,
                "revenue": pl_report.summary_data.get("revenue"),
                "total_income": pl_report.summary_data.get("total_income"),
                "cost_of_sales": pl_report.summary_data.get("cost_of_sales"),
                "gross_profit": pl_report.summary_data.get("gross_profit"),
                "operating_expenses": pl_report.summary_data.get("operating_expenses"),
                "net_profit": pl_report.summary_data.get("net_profit"),
                "gross_margin_pct": pl_report.summary_data.get("gross_margin_pct"),
                "net_margin_pct": pl_report.summary_data.get("net_margin_pct"),
                "expense_ratio_pct": pl_report.summary_data.get("expense_ratio_pct"),
                "fetched_at": pl_report.fetched_at.isoformat() if pl_report.fetched_at else None,
            }

        # Fetch latest Balance Sheet report
        bs_report = await self._get_latest_report(connection_id, XeroReportType.BALANCE_SHEET)
        if bs_report and bs_report.summary_data:
            context["balance_sheet"] = {
                "as_of_date": bs_report.period_key,
                "total_assets": bs_report.summary_data.get("total_assets"),
                "current_assets": bs_report.summary_data.get("current_assets"),
                "non_current_assets": bs_report.summary_data.get("non_current_assets"),
                "total_liabilities": bs_report.summary_data.get("total_liabilities"),
                "current_liabilities": bs_report.summary_data.get("current_liabilities"),
                "equity": bs_report.summary_data.get("equity"),
                "current_ratio": bs_report.summary_data.get("current_ratio"),
                "debt_to_equity": bs_report.summary_data.get("debt_to_equity"),
                "fetched_at": bs_report.fetched_at.isoformat() if bs_report.fetched_at else None,
            }

        # Fetch latest Aged Receivables report
        ar_report = await self._get_latest_report(connection_id, XeroReportType.AGED_RECEIVABLES)
        if ar_report and ar_report.summary_data:
            context["aged_receivables"] = {
                "as_of_date": ar_report.period_key,
                "total": ar_report.summary_data.get("total"),
                "current": ar_report.summary_data.get("current"),
                "overdue_30": ar_report.summary_data.get("overdue_30"),
                "overdue_60": ar_report.summary_data.get("overdue_60"),
                "overdue_90": ar_report.summary_data.get("overdue_90"),
                "overdue_90_plus": ar_report.summary_data.get("overdue_90_plus"),
                "overdue_total": ar_report.summary_data.get("overdue_total"),
                "overdue_pct": ar_report.summary_data.get("overdue_pct"),
                "high_risk_contacts": ar_report.summary_data.get("high_risk_contacts", []),
                "fetched_at": ar_report.fetched_at.isoformat() if ar_report.fetched_at else None,
            }

        # Fetch latest Aged Payables report
        ap_report = await self._get_latest_report(connection_id, XeroReportType.AGED_PAYABLES)
        if ap_report and ap_report.summary_data:
            context["aged_payables"] = {
                "as_of_date": ap_report.period_key,
                "total": ap_report.summary_data.get("total"),
                "current": ap_report.summary_data.get("current"),
                "overdue_total": ap_report.summary_data.get("overdue_total"),
                "overdue_pct": ap_report.summary_data.get("overdue_pct"),
                "fetched_at": ap_report.fetched_at.isoformat() if ap_report.fetched_at else None,
            }

        return context

    async def _get_latest_report(
        self,
        connection_id: UUID,
        report_type: XeroReportType,
    ) -> XeroReport | None:
        """Get the latest cached report of a given type.

        Args:
            connection_id: The XeroConnection ID.
            report_type: The type of report to fetch.

        Returns:
            The latest XeroReport or None if not found.
        """
        result = await self.db.execute(
            select(XeroReport)
            .where(
                XeroReport.connection_id == connection_id,
                XeroReport.report_type == report_type,
            )
            .order_by(XeroReport.fetched_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_client_extended_data_context(
        self,
        connection_id: UUID,
    ) -> dict[str, Any]:
        """Get extended client data context for AI enrichment (Spec 024/025 data).

        Fetches summaries of fixed assets, purchase orders, credit notes, payments,
        repeating invoices, overpayments, prepayments, journals, and quotes.

        Each query is individually guarded so a single table schema issue
        (e.g. missing column) does not prevent all other context from loading.

        Args:
            connection_id: The XeroConnection ID (organization).

        Returns:
            Dict with extended data summaries keyed by data type.
        """
        import logging

        logger = logging.getLogger(__name__)
        context: dict[str, Any] = {}

        fetchers: list[tuple[str, Any]] = [
            ("fixed_assets", self._get_fixed_assets_summary),
            ("purchase_orders", self._get_purchase_orders_summary),
            ("credit_notes", self._get_credit_notes_summary),
            ("payments", self._get_payments_summary),
            ("overpayments", self._get_overpayments_summary),
            ("prepayments", self._get_prepayments_summary),
            ("repeating_invoices", self._get_repeating_invoices_summary),
            ("quotes", self._get_quotes_summary),
            ("journals", self._get_journals_summary),
        ]

        for key, fetcher in fetchers:
            try:
                result = await fetcher(connection_id)
                if result:
                    context[key] = result
            except Exception as e:
                logger.warning("Failed to fetch %s context: %s", key, e)
                await self.db.rollback()

        return context

    async def _get_fixed_assets_summary(self, connection_id: UUID) -> dict[str, Any] | None:
        """Get fixed assets summary for AI context."""
        from decimal import Decimal

        # Get all assets for the connection
        result = await self.db.execute(
            select(XeroAsset).where(XeroAsset.connection_id == connection_id)
        )
        assets = list(result.scalars().all())

        if not assets:
            return None

        # Calculate summaries
        total_count = len(assets)
        registered = [a for a in assets if a.status == XeroAssetStatus.REGISTERED.value]
        disposed = [a for a in assets if a.status == XeroAssetStatus.DISPOSED.value]
        draft = [a for a in assets if a.status == XeroAssetStatus.DRAFT.value]

        total_purchase_price = sum((a.purchase_price or Decimal("0")) for a in registered)
        total_book_value = sum((a.book_value or Decimal("0")) for a in registered)
        total_depreciation_ytd = sum(
            (a.current_accum_depreciation or Decimal("0")) for a in registered
        )
        total_accumulated_depreciation = sum(
            (
                (a.prior_accum_depreciation or Decimal("0"))
                + (a.current_accum_depreciation or Decimal("0"))
            )
            for a in registered
        )

        # Instant write-off eligible (under $20,000 threshold for small business)
        write_off_threshold = Decimal("20000")
        current_fy_start = datetime(
            datetime.now().year if datetime.now().month >= 7 else datetime.now().year - 1, 7, 1
        ).date()
        write_off_eligible = [
            a
            for a in registered
            if (a.purchase_price or Decimal("0")) < write_off_threshold
            and a.purchase_date
            and a.purchase_date >= current_fy_start
        ]

        # Fully depreciated assets (potential replacement candidates)
        fully_depreciated = [
            a for a in registered if (a.book_value or Decimal("0")) <= Decimal("0")
        ]

        return {
            "total_count": total_count,
            "registered_count": len(registered),
            "disposed_count": len(disposed),
            "draft_count": len(draft),
            "total_purchase_price": float(total_purchase_price),
            "total_book_value": float(total_book_value),
            "total_depreciation_ytd": float(total_depreciation_ytd),
            "total_accumulated_depreciation": float(total_accumulated_depreciation),
            "write_off_eligible_count": len(write_off_eligible),
            "write_off_eligible_value": float(
                sum((a.purchase_price or Decimal("0")) for a in write_off_eligible)
            ),
            "fully_depreciated_count": len(fully_depreciated),
            "insight": self._generate_asset_insight(
                len(registered), total_book_value, len(write_off_eligible), len(fully_depreciated)
            ),
        }

    def _generate_asset_insight(
        self,
        registered_count: int,
        total_book_value: "Decimal",
        write_off_eligible: int,
        fully_depreciated: int,
    ) -> str:
        """Generate a brief insight about fixed assets."""
        insights = []
        if write_off_eligible > 0:
            insights.append(
                f"{write_off_eligible} asset(s) may qualify for instant asset write-off"
            )
        if fully_depreciated > 0:
            insights.append(
                f"{fully_depreciated} asset(s) fully depreciated - consider replacement planning"
            )
        if registered_count == 0:
            insights.append("No registered fixed assets on record")
        return (
            "; ".join(insights)
            if insights
            else f"{registered_count} registered assets worth ${total_book_value:,.2f} book value"
        )

    async def _get_purchase_orders_summary(self, connection_id: UUID) -> dict[str, Any] | None:
        """Get purchase orders summary for AI context."""
        from decimal import Decimal

        result = await self.db.execute(
            select(XeroPurchaseOrder).where(XeroPurchaseOrder.connection_id == connection_id)
        )
        orders = list(result.scalars().all())

        if not orders:
            return None

        # Group by status
        outstanding_statuses = {"DRAFT", "SUBMITTED", "AUTHORISED"}
        outstanding = [o for o in orders if o.status in outstanding_statuses]
        billed = [o for o in orders if o.status == "BILLED"]

        outstanding_total = sum((o.total or Decimal("0")) for o in outstanding)
        billed_total = sum((o.total or Decimal("0")) for o in billed)

        # Status breakdown
        by_status: dict[str, int] = {}
        for order in orders:
            by_status[order.status] = by_status.get(order.status, 0) + 1

        return {
            "total_count": len(orders),
            "outstanding_count": len(outstanding),
            "outstanding_value": float(outstanding_total),
            "billed_count": len(billed),
            "billed_value": float(billed_total),
            "by_status": by_status,
            "insight": f"{len(outstanding)} outstanding PO(s) worth ${outstanding_total:,.2f} affecting cash flow forecast"
            if outstanding
            else "No outstanding purchase orders",
        }

    async def _get_credit_notes_summary(self, connection_id: UUID) -> dict[str, Any] | None:
        """Get credit notes summary for AI context."""
        from decimal import Decimal

        result = await self.db.execute(
            select(XeroCreditNote).where(XeroCreditNote.connection_id == connection_id)
        )
        credit_notes = list(result.scalars().all())

        if not credit_notes:
            return None

        # Group by type (ACCPAYCREDIT = supplier credits, ACCRECCREDIT = customer credits)
        supplier_credits = [cn for cn in credit_notes if cn.credit_note_type == "ACCPAYCREDIT"]
        customer_credits = [cn for cn in credit_notes if cn.credit_note_type == "ACCRECCREDIT"]

        # Calculate available (not fully allocated)
        available_supplier = sum((cn.remaining_credit or Decimal("0")) for cn in supplier_credits)
        available_customer = sum((cn.remaining_credit or Decimal("0")) for cn in customer_credits)

        return {
            "total_count": len(credit_notes),
            "supplier_credit_count": len(supplier_credits),
            "supplier_credit_available": float(available_supplier),
            "customer_credit_count": len(customer_credits),
            "customer_credit_available": float(available_customer),
            "insight": self._generate_credit_note_insight(available_supplier, available_customer),
        }

    def _generate_credit_note_insight(
        self, supplier_available: "Decimal", customer_available: "Decimal"
    ) -> str:
        """Generate insight about credit notes."""
        insights = []
        if supplier_available > 0:
            insights.append(
                f"${supplier_available:,.2f} available supplier credits to apply to bills"
            )
        if customer_available > 0:
            insights.append(f"${customer_available:,.2f} customer credits outstanding")
        return "; ".join(insights) if insights else "No significant credit note balances"

    async def _get_payments_summary(self, connection_id: UUID) -> dict[str, Any] | None:
        """Get payments summary for AI context (last 90 days)."""
        from decimal import Decimal

        cutoff_date = datetime.now(UTC) - timedelta(days=90)

        result = await self.db.execute(
            select(XeroPayment).where(
                XeroPayment.connection_id == connection_id,
                XeroPayment.payment_date >= cutoff_date.date(),
            )
        )
        payments = list(result.scalars().all())

        if not payments:
            return None

        # Group by type
        received = [p for p in payments if p.payment_type in ("ACCRECPAYMENT", "ARCREDITPAYMENT")]
        made = [p for p in payments if p.payment_type in ("ACCPAYPAYMENT", "APCREDITPAYMENT")]

        received_total = sum((p.amount or Decimal("0")) for p in received)
        made_total = sum((p.amount or Decimal("0")) for p in made)

        return {
            "period": "last_90_days",
            "payments_received_count": len(received),
            "payments_received_total": float(received_total),
            "payments_made_count": len(made),
            "payments_made_total": float(made_total),
            "net_cash_flow": float(received_total - made_total),
            "insight": f"Net cash flow from payments: ${(received_total - made_total):,.2f} (received ${received_total:,.2f}, paid ${made_total:,.2f})",
        }

    async def _get_overpayments_summary(self, connection_id: UUID) -> dict[str, Any] | None:
        """Get overpayments summary for AI context."""
        from decimal import Decimal

        result = await self.db.execute(
            select(XeroOverpayment).where(XeroOverpayment.connection_id == connection_id)
        )
        overpayments = list(result.scalars().all())

        if not overpayments:
            return None

        # Only include those with remaining credit
        with_balance = [
            op for op in overpayments if (op.remaining_credit or Decimal("0")) > Decimal("0")
        ]

        if not with_balance:
            return None

        total_available = sum((op.remaining_credit or Decimal("0")) for op in with_balance)

        return {
            "count_with_balance": len(with_balance),
            "total_available": float(total_available),
            "insight": f"${total_available:,.2f} in overpayments available to allocate",
        }

    async def _get_prepayments_summary(self, connection_id: UUID) -> dict[str, Any] | None:
        """Get prepayments summary for AI context."""
        from decimal import Decimal

        result = await self.db.execute(
            select(XeroPrepayment).where(XeroPrepayment.connection_id == connection_id)
        )
        prepayments = list(result.scalars().all())

        if not prepayments:
            return None

        # Only include those with remaining credit
        with_balance = [
            pp for pp in prepayments if (pp.remaining_credit or Decimal("0")) > Decimal("0")
        ]

        if not with_balance:
            return None

        total_available = sum((pp.remaining_credit or Decimal("0")) for pp in with_balance)

        return {
            "count_with_balance": len(with_balance),
            "total_available": float(total_available),
            "insight": f"${total_available:,.2f} in prepayments available to allocate",
        }

    async def _get_repeating_invoices_summary(self, connection_id: UUID) -> dict[str, Any] | None:
        """Get repeating invoices summary for AI context (recurring revenue/expense)."""
        from decimal import Decimal

        result = await self.db.execute(
            select(XeroRepeatingInvoice).where(
                XeroRepeatingInvoice.connection_id == connection_id,
                XeroRepeatingInvoice.status == "ACTIVE",
            )
        )
        templates = list(result.scalars().all())

        if not templates:
            return None

        # Group by type
        sales = [t for t in templates if t.type == "ACCREC"]
        bills = [t for t in templates if t.type == "ACCPAY"]

        # Calculate annualized values (approximate based on schedule)
        def annualize(template: XeroRepeatingInvoice) -> Decimal:
            """Estimate annual value based on schedule."""
            total = template.total or Decimal("0")
            unit = template.schedule_unit or "MONTHLY"
            period = template.schedule_period or 1

            multipliers = {
                "WEEKLY": Decimal("52") / period,
                "MONTHLY": Decimal("12") / period,
                "YEARLY": Decimal("1") / period,
            }
            return total * multipliers.get(unit, Decimal("12"))

        annual_revenue = sum(annualize(t) for t in sales)
        annual_expense = sum(annualize(t) for t in bills)

        return {
            "active_count": len(templates),
            "sales_templates": len(sales),
            "bills_templates": len(bills),
            "annualized_revenue": float(annual_revenue),
            "annualized_expense": float(annual_expense),
            "net_recurring": float(annual_revenue - annual_expense),
            "insight": f"Recurring: ${annual_revenue:,.2f}/yr revenue, ${annual_expense:,.2f}/yr expenses (net ${(annual_revenue - annual_expense):,.2f}/yr)",
        }

    async def _get_quotes_summary(self, connection_id: UUID) -> dict[str, Any] | None:
        """Get quotes summary for AI context (sales pipeline)."""
        from decimal import Decimal

        result = await self.db.execute(
            select(XeroQuote).where(XeroQuote.connection_id == connection_id)
        )
        quotes = list(result.scalars().all())

        if not quotes:
            return None

        # Group by status
        pending_statuses = {"DRAFT", "SENT"}
        pending = [q for q in quotes if q.status in pending_statuses]
        accepted = [q for q in quotes if q.status == "ACCEPTED"]
        declined = [q for q in quotes if q.status == "DECLINED"]

        pending_value = sum((q.total or Decimal("0")) for q in pending)
        accepted_value = sum((q.total or Decimal("0")) for q in accepted)

        return {
            "total_count": len(quotes),
            "pending_count": len(pending),
            "pending_value": float(pending_value),
            "accepted_count": len(accepted),
            "accepted_value": float(accepted_value),
            "declined_count": len(declined),
            "insight": f"Sales pipeline: {len(pending)} pending quotes worth ${pending_value:,.2f}"
            if pending
            else "No pending quotes in pipeline",
        }

    async def _get_journals_summary(self, connection_id: UUID) -> dict[str, Any] | None:
        """Get journals summary for AI context (for anomaly awareness)."""
        # Get counts for last 90 days
        cutoff_date = datetime.now(UTC) - timedelta(days=90)

        # Auto journals count
        auto_result = await self.db.execute(
            select(func.count(XeroJournal.id)).where(
                XeroJournal.connection_id == connection_id,
                XeroJournal.journal_date >= cutoff_date.date(),
            )
        )
        auto_count = auto_result.scalar() or 0

        # Manual journals count
        manual_result = await self.db.execute(
            select(func.count(XeroManualJournal.id)).where(
                XeroManualJournal.connection_id == connection_id,
                XeroManualJournal.journal_date >= cutoff_date.date(),
            )
        )
        manual_count = manual_result.scalar() or 0

        if auto_count == 0 and manual_count == 0:
            return None

        return {
            "period": "last_90_days",
            "auto_journals_count": auto_count,
            "manual_journals_count": manual_count,
            "insight": f"{manual_count} manual journal(s) in last 90 days - review for unusual adjustments"
            if manual_count > 0
            else f"{auto_count} automated journal entries",
        }
