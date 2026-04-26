"""AI-powered analyzer using Claude for intelligent insight generation.

This analyzer goes beyond rule-based checks to identify patterns and issues
that a human accountant would notice but that we haven't explicitly coded for.
"""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import func, select

from app.modules.insights.analyzers.base import BaseAnalyzer
from app.modules.insights.models import InsightCategory, InsightPriority
from app.modules.insights.schemas import InsightCreate, SuggestedAction

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.integrations.xero.models import XeroConnection

logger = logging.getLogger(__name__)


class AIAnalyzer(BaseAnalyzer):
    """AI-powered analyzer that uses Claude to identify issues.

    This analyzer:
    1. Gathers comprehensive financial data for a client
    2. Builds a rich context with transactions, trends, aging, etc.
    3. Sends to Claude with an Australian accountant persona
    4. Parses structured insights from the AI response

    Unlike rule-based analyzers, this can spot:
    - Unusual spending patterns
    - Seasonal anomalies compared to prior years
    - Industry-specific red flags
    - Relationships between disparate data points
    - Things that "just don't look right" to an experienced accountant
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self._anthropic_client = None

    @property
    def category(self) -> InsightCategory:
        """AI analyzer produces insights across all categories."""
        return InsightCategory.STRATEGIC  # Default, but AI can suggest any category

    async def analyze_client(
        self,
        tenant_id: UUID,
        client_id: UUID,
    ) -> list[InsightCreate]:
        """Analyze a client using AI.

        Args:
            tenant_id: The tenant ID.
            client_id: The XeroConnection ID to analyze.

        Returns:
            List of AI-generated insights.
        """
        # Get client info
        client = await self._get_client(client_id)
        if not client:
            logger.warning(f"Client {client_id} not found")
            return []

        # Gather comprehensive data
        context = await self._build_client_context(tenant_id, client)

        if not context:
            logger.info(f"No data available for client {client_id}")
            return []

        # Generate insights using Claude
        insights_data = await self._generate_ai_insights(client, context)

        # Convert to InsightCreate objects
        insights = []
        for insight_data in insights_data:
            try:
                insight = self._parse_ai_insight(insight_data, client, context)
                if insight:
                    insights.append(insight)
            except Exception as e:
                logger.error(f"Failed to parse AI insight: {e}")

        return insights

    async def _build_client_context(
        self,
        tenant_id: UUID,
        client: XeroConnection,
    ) -> dict[str, Any]:
        """Build comprehensive context for AI analysis.

        Gathers:
        - Client profile and basic info
        - Recent transactions summary
        - Invoice status and aging
        - Expense breakdown by category
        - Monthly trends
        - Quality scores
        - Any existing aggregations
        """
        from app.modules.integrations.xero.models import (
            XeroBankTransaction,
            XeroInvoice,
            XeroPayRun,
        )
        from app.modules.knowledge.aggregation_models import (
            ClientAIProfile,
            ClientAPAgingSummary,
            ClientARAgingSummary,
            ClientExpenseSummary,
            ClientGSTSummary,
            ClientMonthlyTrend,
        )
        from app.modules.quality.models import QualityScore

        context: dict[str, Any] = {
            "client_name": client.organization_name,
            "connection_id": str(client.id),
            "last_sync": client.last_full_sync_at.isoformat() if client.last_full_sync_at else None,
        }

        # Get profile if exists
        profile_result = await self.db.execute(
            select(ClientAIProfile).where(ClientAIProfile.connection_id == client.id)
        )
        profile = profile_result.scalar_one_or_none()
        if profile:
            context["profile"] = {
                "entity_type": profile.entity_type,
                "industry_code": profile.industry_code,
                "gst_registered": profile.gst_registered,
                "revenue_bracket": str(profile.revenue_bracket)
                if profile.revenue_bracket
                else None,
                "employee_count": profile.employee_count,
            }

        # Get recent transactions (last 90 days)
        ninety_days_ago = datetime.now(UTC) - timedelta(days=90)
        txn_result = await self.db.execute(
            select(
                XeroBankTransaction.transaction_type,
                func.count().label("count"),
                func.sum(XeroBankTransaction.total_amount).label("total"),
            )
            .where(
                XeroBankTransaction.connection_id == client.id,
                XeroBankTransaction.transaction_date >= ninety_days_ago,
            )
            .group_by(XeroBankTransaction.transaction_type)
        )
        transactions = txn_result.all()
        context["transactions_90d"] = [
            {"type": t.transaction_type, "count": t.count, "total": float(t.total or 0)}
            for t in transactions
        ]

        # If no bank transactions were found, note that this may simply be an invoice-based
        # business without a connected bank feed — not a "no activity" situation.
        # This prevents the AI from incorrectly flagging inactive clients when invoice/GST
        # data already shows significant revenue (e.g. $206K Q3 sales visible in BAS tab).
        if not context["transactions_90d"]:
            context["transactions_90d_note"] = (
                "No bank feed transactions found in the last 90 days. "
                "This is common for clients who use Xero for invoicing only and do not connect a bank feed. "
                "Do NOT treat this as 'no financial activity' — refer to invoices, GST summary, "
                "and monthly trends for actual financial activity."
            )

        # Get invoice summary
        invoice_result = await self.db.execute(
            select(
                XeroInvoice.invoice_type,
                XeroInvoice.status,
                func.count().label("count"),
                func.sum(XeroInvoice.total_amount).label("total"),
            )
            .where(XeroInvoice.connection_id == client.id)
            .group_by(XeroInvoice.invoice_type, XeroInvoice.status)
        )
        invoices = invoice_result.all()
        context["invoices"] = [
            {
                "type": i.invoice_type,
                "status": i.status,
                "count": i.count,
                "total": float(i.total or 0),
            }
            for i in invoices
        ]

        # Get AR aging
        ar_result = await self.db.execute(
            select(ClientARAgingSummary)
            .where(ClientARAgingSummary.connection_id == client.id)
            .order_by(ClientARAgingSummary.as_of_date.desc())
            .limit(1)
        )
        ar_aging = ar_result.scalar_one_or_none()
        if ar_aging:
            context["ar_aging"] = {
                "current": float(ar_aging.current_amount),
                "31_60_days": float(ar_aging.days_31_60),
                "61_90_days": float(ar_aging.days_61_90),
                "over_90_days": float(ar_aging.over_90_days),
                "total": float(ar_aging.total_outstanding),
                "top_debtors": ar_aging.top_debtors,
            }

        # Get AP aging
        ap_result = await self.db.execute(
            select(ClientAPAgingSummary)
            .where(ClientAPAgingSummary.connection_id == client.id)
            .order_by(ClientAPAgingSummary.as_of_date.desc())
            .limit(1)
        )
        ap_aging = ap_result.scalar_one_or_none()
        if ap_aging:
            context["ap_aging"] = {
                "current": float(ap_aging.current_amount),
                "31_60_days": float(ap_aging.days_31_60),
                "61_90_days": float(ap_aging.days_61_90),
                "over_90_days": float(ap_aging.over_90_days),
                "total": float(ap_aging.total_outstanding),
                "top_creditors": ap_aging.top_creditors,
            }

        # Get expense summary (current quarter)
        expense_result = await self.db.execute(
            select(ClientExpenseSummary)
            .where(
                ClientExpenseSummary.connection_id == client.id,
                ClientExpenseSummary.period_type == "quarter",
            )
            .order_by(ClientExpenseSummary.period_start.desc())
            .limit(1)
        )
        expense_summary = expense_result.scalar_one_or_none()
        if expense_summary:
            context["expenses_quarter"] = {
                "by_category": expense_summary.by_category,
                "total": float(expense_summary.total_expenses),
                "gst": float(expense_summary.total_gst),
                "transaction_count": expense_summary.transaction_count,
            }

        # Get GST summary
        gst_result = await self.db.execute(
            select(ClientGSTSummary)
            .where(
                ClientGSTSummary.connection_id == client.id,
                ClientGSTSummary.period_type == "quarter",
            )
            .order_by(ClientGSTSummary.period_start.desc())
            .limit(1)
        )
        gst_summary = gst_result.scalar_one_or_none()
        if gst_summary:
            context["gst_summary"] = {
                "period_start": gst_summary.period_start.isoformat(),
                "period_end": gst_summary.period_end.isoformat(),
                "gst_on_sales": float(gst_summary.gst_on_sales_1a),
                "gst_on_purchases": float(gst_summary.gst_on_purchases_1b),
                "net_gst": float(gst_summary.net_gst),
                "total_sales": float(gst_summary.total_sales),
                "total_purchases": float(gst_summary.total_purchases),
            }

        # Get monthly trends (last 6 months)
        trend_result = await self.db.execute(
            select(ClientMonthlyTrend)
            .where(ClientMonthlyTrend.connection_id == client.id)
            .order_by(ClientMonthlyTrend.year.desc(), ClientMonthlyTrend.month.desc())
            .limit(6)
        )
        trends = trend_result.scalars().all()
        if trends:
            context["monthly_trends"] = [
                {
                    "year": t.year,
                    "month": t.month,
                    "revenue": float(t.revenue),
                    "expenses": float(t.expenses),
                    "gross_profit": float(t.gross_profit),
                    "net_cashflow": float(t.net_cashflow),
                }
                for t in trends
            ]

        # Get quality score
        quality_result = await self.db.execute(
            select(QualityScore)
            .where(QualityScore.connection_id == client.id)
            .order_by(QualityScore.calculated_at.desc())
            .limit(1)
        )
        quality = quality_result.scalar_one_or_none()
        if quality:
            context["quality_score"] = {
                "overall": float(quality.overall_score),
                "reconciliation": float(quality.reconciliation_score),
                "categorization": float(quality.categorization_score),
                "freshness": float(quality.freshness_score),
                "completeness": float(quality.completeness_score),
            }

        # Get payroll summary
        payroll_result = await self.db.execute(
            select(
                func.count().label("pay_run_count"),
                func.sum(XeroPayRun.total_wages).label("total_wages"),
                func.sum(XeroPayRun.total_tax).label("total_tax"),
                func.sum(XeroPayRun.total_super).label("total_super"),
            ).where(
                XeroPayRun.connection_id == client.id,
                XeroPayRun.period_start >= ninety_days_ago,
            )
        )
        payroll = payroll_result.one_or_none()
        if payroll and payroll.pay_run_count:
            context["payroll_90d"] = {
                "pay_run_count": payroll.pay_run_count,
                "total_wages": float(payroll.total_wages or 0),
                "total_tax": float(payroll.total_tax or 0),
                "total_super": float(payroll.total_super or 0),
            }

        return context

    async def _generate_ai_insights(
        self,
        client: XeroConnection,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Send context to Claude and get structured insights.

        Args:
            client: The XeroConnection being analyzed.
            context: Comprehensive client data context.

        Returns:
            List of insight dictionaries from AI.
        """
        import anthropic

        from app.config import get_settings

        settings = get_settings()

        if not settings.anthropic.api_key.get_secret_value():
            logger.warning("Anthropic API key not configured, skipping AI analysis")
            return []

        # Build the prompt
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(client.organization_name, context)

        try:
            api_client = anthropic.Anthropic(api_key=settings.anthropic.api_key.get_secret_value())
            response = api_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            # Parse the JSON response
            response_text = response.content[0].text

            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            insights_data = json.loads(response_text)

            # Audit log AI analysis
            try:
                from app.core.audit import AuditService

                audit = AuditService(self.db)
                await audit.log_event(
                    event_type="ai.insights.analysis",
                    event_category="data",
                    action="create",
                    outcome="success",
                    metadata={
                        "model": "claude-sonnet-4-20250514",
                        "input_tokens": getattr(response.usage, "input_tokens", None),
                        "output_tokens": getattr(response.usage, "output_tokens", None),
                    },
                )
            except Exception:
                pass

            if isinstance(insights_data, dict) and "insights" in insights_data:
                return insights_data["insights"]
            elif isinstance(insights_data, list):
                return insights_data
            else:
                logger.warning(f"Unexpected AI response format: {type(insights_data)}")
                return []

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            return []
        except Exception as e:
            logger.error(f"AI insight generation failed: {e}")
            return []

    def _build_system_prompt(self) -> str:
        """Build the system prompt for Claude."""
        return """You are a senior Australian accountant with 15+ years of experience reviewing client financial data. You are helping an accounting practice identify issues and opportunities for their clients.

Your task is to analyze the financial data provided and identify insights that:
1. Indicate compliance risks (GST, BAS, superannuation, PAYG)
2. Suggest cash flow problems or opportunities
3. Highlight data quality issues that need attention
4. Spot unusual patterns that warrant investigation
5. Identify strategic opportunities for the client

CRITICAL RULES:
- Only generate insights if you see actual issues or opportunities in the data
- Each insight MUST be specific and actionable
- Write in third-person declarative style: "Revenue declined 12%" not "I notice revenue declined 12%"
- NEVER begin summary or detail text with "I ", "I've ", "It appears", "I notice", "I can see" or any first-person language
- Include specific numbers and percentages where relevant
- If a deadline applies, include it as an ISO date string
- Be conservative - only flag issues with at least medium confidence
- DO NOT generate insights about: BAS/IAS lodgement deadlines, GST registration thresholds, overdue receivables aging, or data quality scores — these are already covered by dedicated rule-based analyzers and creating them here causes duplicates
- DO NOT flag "no financial activity" or "no transactions" if invoice data, GST figures, or monthly trends show revenue — empty bank transactions means no bank feed, not a dormant business

You must respond with ONLY valid JSON in this exact format:
{
  "insights": [
    {
      "category": "compliance|quality|cash_flow|tax|strategic",
      "priority": "high|medium|low",
      "insight_type": "descriptive_snake_case_type",
      "title": "Brief descriptive title (max 60 chars)",
      "summary": "One or two sentences summarizing the issue",
      "detail": "Detailed explanation with specific numbers and context",
      "suggested_actions": [
        {"label": "Action button text", "url": null, "action": "action_type"}
      ],
      "action_deadline": "2025-01-28T00:00:00Z or null if no deadline",
      "confidence": 0.85
    }
  ]
}

If no significant insights are found, return: {"insights": []}

Categories explained:
- compliance: GST/BAS deadlines, super guarantee, PAYG withholding, ABN/TFN issues
- quality: Unreconciled transactions, uncoded items, data discrepancies
- cash_flow: AR/AP aging, overdue receivables, upcoming large payables
- tax: Deduction opportunities, tax planning windows, depreciation
- strategic: Business growth patterns, efficiency opportunities, benchmarking"""

    def _build_user_prompt(self, client_name: str, context: dict[str, Any]) -> str:
        """Build the user prompt with client context."""
        today = datetime.now(UTC).date()

        prompt = f"""Please analyze the following financial data for client "{client_name}" and identify any issues, risks, or opportunities.

Today's date: {today.isoformat()}
Current Australian financial year: FY{today.year if today.month >= 7 else today.year - 1}/{(today.year + 1) if today.month >= 7 else today.year}
Current BAS quarter: Q{((today.month - 1) // 3) + 1} (due approximately {self._get_next_bas_deadline(today)})

CLIENT DATA:
```json
{json.dumps(context, indent=2, default=str)}
```

Please identify:
1. Tax planning opportunities or compliance risks (super, PAYG — but NOT BAS deadlines or GST registration, those are handled separately)
2. Cash flow concerns (upcoming payables, revenue trends — but NOT overdue receivables aging, that is handled separately)
3. Unusual transaction patterns that warrant investigation
4. Strategic opportunities for the client
5. Any other issues an experienced accountant would flag

IMPORTANT: Do NOT generate insights about BAS lodgement deadlines, GST registration thresholds, overdue receivables/payables aging percentages, or data quality scores. These are covered by dedicated analyzers.

IMPORTANT: Do NOT generate "no financial activity", "no transactions recorded", or similar low-activity insights if invoice data, GST summary, or monthly revenue trends show activity. Empty bank transactions simply means the client uses invoice-based accounting without a bank feed — it does NOT indicate a dormant business.

Remember to respond with ONLY valid JSON."""

        return prompt

    def _get_next_bas_deadline(self, today: datetime.date) -> str:
        """Get the next BAS deadline date."""
        # BAS is due 28th of the month following quarter end
        # Q1 (Jul-Sep) due Oct 28, Q2 (Oct-Dec) due Feb 28, etc.
        month = today.month
        year = today.year

        if month <= 1 or (month == 2 and today.day <= 28):
            return f"28 February {year}"
        elif month <= 4 or (month == 5 and today.day <= 28):
            return f"28 May {year}"
        elif month <= 7 or (month == 8 and today.day <= 28):
            return f"28 August {year}"
        elif month <= 10 or (month == 11 and today.day <= 28):
            return f"28 November {year}"
        else:
            return f"28 February {year + 1}"

    def _parse_ai_insight(
        self,
        data: dict[str, Any],
        client: XeroConnection,
        client_context: dict[str, Any] | None = None,
    ) -> InsightCreate | None:
        """Parse AI response into InsightCreate.

        Args:
            data: Single insight dictionary from AI.
            client: The client this insight is for.
            client_context: The financial context used during analysis.

        Returns:
            InsightCreate or None if parsing fails.
        """
        # Strip first-person AI chat language from summary/detail
        _FIRST_PERSON_PREFIXES = (
            "I ",
            "I've ",
            "I've ",
            "I notice",
            "I see",
            "I can ",
            "It appears",
        )

        def _strip_first_person(text: str | None) -> str | None:
            if not text:
                return text
            stripped = text.strip()
            for prefix in _FIRST_PERSON_PREFIXES:
                if stripped.startswith(prefix):
                    # Return None so the insight is discarded rather than mangled
                    return None
            return text

        try:
            # Map category string to enum
            category_map = {
                "compliance": InsightCategory.COMPLIANCE,
                "quality": InsightCategory.QUALITY,
                "cash_flow": InsightCategory.CASH_FLOW,
                "tax": InsightCategory.TAX,
                "strategic": InsightCategory.STRATEGIC,
            }
            category = category_map.get(data.get("category", "").lower(), InsightCategory.STRATEGIC)

            # Map priority string to enum
            priority_map = {
                "high": InsightPriority.HIGH,
                "medium": InsightPriority.MEDIUM,
                "low": InsightPriority.LOW,
            }
            priority = priority_map.get(data.get("priority", "").lower(), InsightPriority.MEDIUM)

            # Parse suggested actions
            actions = []
            for action_data in data.get("suggested_actions", []):
                actions.append(
                    SuggestedAction(
                        label=action_data.get("label", "View Details"),
                        url=action_data.get("url") or f"/clients/{client.id}",
                        action=action_data.get("action"),
                    )
                )

            # Default action if none provided
            if not actions:
                actions = [
                    SuggestedAction(
                        label="View Client",
                        url=f"/clients/{client.id}",
                    )
                ]

            # Parse action deadline
            action_deadline = None
            if data.get("action_deadline"):
                with contextlib.suppress(ValueError, TypeError):
                    action_deadline = datetime.fromisoformat(
                        data["action_deadline"].replace("Z", "+00:00")
                    )

            # Calculate expiry (insight becomes stale after action deadline or 30 days)
            expires_at = None
            if action_deadline:
                expires_at = action_deadline + timedelta(days=7)
            else:
                expires_at = datetime.now(UTC) + timedelta(days=30)

            summary = _strip_first_person(data.get("summary", ""))
            if summary is None:
                logger.debug("Discarded AI insight with first-person summary language")
                return None
            detail = _strip_first_person(data.get("detail"))

            return InsightCreate(
                category=category,
                insight_type=data.get("insight_type", "ai_generated"),
                priority=priority,
                title=data.get("title", "AI-Generated Insight")[:255],
                summary=summary,
                detail=detail,
                suggested_actions=actions,
                related_url=f"/clients/{client.id}",
                expires_at=expires_at,
                action_deadline=action_deadline,
                confidence=self._calculate_confidence(client_context),
                data_snapshot=self._build_evidence_snapshot(client_context),
            )

        except Exception as e:
            logger.error(f"Failed to parse AI insight: {e}, data: {data}")
            return None

    def _build_evidence_snapshot(self, client_context: dict[str, Any] | None) -> dict[str, Any]:
        """Build evidence snapshot from the client context used during analysis.

        Args:
            client_context: The financial context dict built by _build_client_context().

        Returns:
            Trimmed snapshot dict suitable for JSONB storage.
        """
        from app.modules.insights.evidence import build_evidence_snapshot, trim_snapshot_to_size

        snapshot = build_evidence_snapshot(raw_context=client_context)
        return trim_snapshot_to_size(snapshot)

    def _calculate_confidence(self, client_context: dict[str, Any] | None) -> float:
        """Calculate meaningful confidence from data quality signals."""
        from app.modules.insights.evidence import build_evidence_snapshot, calculate_confidence

        snapshot = build_evidence_snapshot(raw_context=client_context)
        freshness = snapshot.data_freshness
        breakdown = calculate_confidence(
            snapshot=snapshot,
            data_freshness=freshness,
            knowledge_chunks_count=0,  # AI analyzer doesn't use RAG chunks
            perspectives_used=[],
        )
        return breakdown["overall"]
