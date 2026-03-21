"""Magic Zone Analyzer for high-value strategic insights.

The Magic Zone routes certain high-value triggers through the
Multi-Agent Orchestrator for cross-pillar analysis with OPTIONS format.

This provides strategic insights with multiple options, trade-offs,
and recommended actions for complex business decisions.
"""

import logging
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.modules.agents.orchestrator import MultiPerspectiveOrchestrator
from app.modules.agents.schemas import Perspective
from app.modules.insights.analyzers.base import BaseAnalyzer
from app.modules.insights.analyzers.magic_zone_types import (
    MagicZoneTrigger,
    MagicZoneTriggerType,
    RevenueTrend,
)
from app.modules.insights.models import Insight, InsightCategory, InsightPriority
from app.modules.insights.schemas import InsightCreate, SuggestedAction
from app.modules.knowledge.aggregation_models import (
    ClientAIProfile,
    ClientMonthlyTrend,
)

logger = logging.getLogger(__name__)


class MagicZoneTriggerDetector:
    """Detects high-value scenarios that should route to Magic Zone analysis.

    Magic Zone triggers are situations where multi-agent analysis provides
    significantly better insights than rule-based or single-agent analysis.
    """

    # GST threshold in Australia
    GST_THRESHOLD = Decimal("75000")
    GST_WARNING_THRESHOLD = Decimal("65000")

    # Revenue change threshold
    REVENUE_CHANGE_THRESHOLD = 0.30  # 30% change

    # EOFY planning window
    EOFY_WINDOW_START_MONTH = 5  # May
    EOFY_WINDOW_END_MONTH = 6  # June

    def __init__(self, db: AsyncSession):
        """Initialize the detector.

        Args:
            db: Database session for queries.
        """
        self.db = db

    async def detect_triggers(
        self,
        tenant_id: UUID,
        client_id: UUID,
    ) -> list[MagicZoneTrigger]:
        """Detect all Magic Zone triggers for a client.

        Args:
            tenant_id: The tenant ID.
            client_id: The client ID.

        Returns:
            List of detected MagicZoneTrigger objects.
        """
        triggers: list[MagicZoneTrigger] = []

        # Get client profile
        profile = await self._get_profile(client_id)
        if not profile:
            return triggers

        # Check each trigger type
        gst_trigger = await self._check_gst_threshold(tenant_id, client_id, profile)
        if gst_trigger:
            triggers.append(gst_trigger)

        eofy_trigger = self._check_eofy_window(tenant_id, client_id, profile)
        if eofy_trigger:
            triggers.append(eofy_trigger)

        revenue_trigger = await self._check_revenue_change(tenant_id, client_id)
        if revenue_trigger:
            triggers.append(revenue_trigger)

        return triggers

    async def _get_profile(self, client_id: UUID) -> ClientAIProfile | None:
        """Get client AI profile."""
        result = await self.db.execute(
            select(ClientAIProfile).where(ClientAIProfile.connection_id == client_id)
        )
        return result.scalar_one_or_none()

    async def _get_annual_revenue(self, client_id: UUID) -> Decimal | None:
        """Get estimated annual revenue from monthly trends (last 12 months)."""
        now = datetime.now(UTC)
        current_year = now.year
        current_month = now.month

        # Calculate 12 months ago
        if current_month == 12:
            start_year = current_year
            start_month = 1
        else:
            start_year = current_year - 1
            start_month = current_month + 1

        # Query: Get sum where (year > start_year) OR (year == start_year AND month >= start_month)
        result = await self.db.execute(
            select(func.sum(ClientMonthlyTrend.revenue)).where(
                ClientMonthlyTrend.connection_id == client_id,
                (
                    (ClientMonthlyTrend.year > start_year)
                    | (
                        (ClientMonthlyTrend.year == start_year)
                        & (ClientMonthlyTrend.month >= start_month)
                    )
                ),
            )
        )
        total = result.scalar()
        return Decimal(str(total)) if total else None

    async def _get_revenue_trend(self, client_id: UUID) -> tuple[Decimal | None, Decimal | None]:
        """Get current and previous year revenue for comparison.

        Returns:
            Tuple of (current_year_revenue, previous_year_revenue)
        """
        now = datetime.now(UTC)
        current_year = now.year

        # Current year revenue (this calendar year)
        result = await self.db.execute(
            select(func.sum(ClientMonthlyTrend.revenue)).where(
                ClientMonthlyTrend.connection_id == client_id,
                ClientMonthlyTrend.year == current_year,
            )
        )
        current = result.scalar()
        current_revenue = Decimal(str(current)) if current else None

        # Previous year revenue
        result = await self.db.execute(
            select(func.sum(ClientMonthlyTrend.revenue)).where(
                ClientMonthlyTrend.connection_id == client_id,
                ClientMonthlyTrend.year == current_year - 1,
            )
        )
        previous = result.scalar()
        previous_revenue = Decimal(str(previous)) if previous else None

        return current_revenue, previous_revenue

    async def _check_gst_threshold(
        self,
        tenant_id: UUID,
        client_id: UUID,
        profile: ClientAIProfile,
    ) -> MagicZoneTrigger | None:
        """Check if client is approaching GST threshold.

        The Magic Zone provides OPTIONS for:
        - Register now (claim input tax credits)
        - Wait until threshold (delay charging GST)
        - Strategic timing (if approaching threshold)
        """
        # TODO: Re-enable this check after testing
        # Skip if already registered
        # if profile.gst_registered:
        #     return None

        annual_revenue = await self._get_annual_revenue(client_id)
        if annual_revenue is None or annual_revenue < self.GST_WARNING_THRESHOLD:
            return None

        distance = self.GST_THRESHOLD - annual_revenue

        return MagicZoneTrigger(
            trigger_type=MagicZoneTriggerType.GST_THRESHOLD,
            client_id=client_id,
            tenant_id=tenant_id,
            title="GST Registration Decision Point",
            description=f"Revenue ${annual_revenue:,.0f} approaching $75K threshold",
            urgency="high" if annual_revenue >= self.GST_THRESHOLD else "medium",
            current_revenue=float(annual_revenue),
            distance_to_threshold=float(distance),
        )

    def _check_eofy_window(
        self,
        tenant_id: UUID,
        client_id: UUID,
        profile: ClientAIProfile,  # noqa: ARG002
    ) -> MagicZoneTrigger | None:
        """Check if we're in the EOFY planning window (May-June).

        The Magic Zone provides OPTIONS for:
        - Income deferral strategies
        - Expense acceleration
        - Super contribution timing
        - Asset purchases
        """
        now = datetime.now(UTC)

        if now.month not in (self.EOFY_WINDOW_START_MONTH, self.EOFY_WINDOW_END_MONTH):
            return None

        # Calculate days until EOFY (June 30)
        eofy = datetime(now.year, 6, 30, tzinfo=UTC)
        days_until = (eofy - now).days

        if days_until < 0:
            return None  # Past EOFY

        return MagicZoneTrigger(
            trigger_type=MagicZoneTriggerType.EOFY_PLANNING,
            client_id=client_id,
            tenant_id=tenant_id,
            title="End of Financial Year Planning",
            description=f"{days_until} days until EOFY - tax planning window",
            urgency="high" if days_until <= 14 else "medium",
            eofy_date=eofy,
            days_until_eofy=days_until,
        )

    async def _check_revenue_change(
        self,
        tenant_id: UUID,
        client_id: UUID,
    ) -> MagicZoneTrigger | None:
        """Check for significant revenue change (>30%).

        The Magic Zone provides OPTIONS for:
        - Cash flow management
        - Staffing decisions
        - Tax planning implications
        - Growth/contraction strategies
        """
        current_revenue, previous_revenue = await self._get_revenue_trend(client_id)

        if not current_revenue or not previous_revenue or previous_revenue == 0:
            return None

        change_percent = float((current_revenue - previous_revenue) / previous_revenue)

        if abs(change_percent) < self.REVENUE_CHANGE_THRESHOLD:
            return None

        trend = RevenueTrend(
            current_annual_revenue=float(current_revenue),
            previous_annual_revenue=float(previous_revenue),
            revenue_change_percent=change_percent * 100,
            trend_direction="up" if change_percent > 0 else "down",
        )

        direction = "increase" if change_percent > 0 else "decrease"

        return MagicZoneTrigger(
            trigger_type=MagicZoneTriggerType.REVENUE_CHANGE,
            client_id=client_id,
            tenant_id=tenant_id,
            title=f"Significant Revenue {direction.title()}",
            description=f"{abs(change_percent) * 100:.0f}% {direction} in annual revenue",
            urgency="medium",
            revenue_trend=trend,
        )


class MagicZoneAnalyzer(BaseAnalyzer):
    """Analyzer that routes high-value insights through Multi-Agent Orchestrator.

    Unlike rule-based analyzers, the Magic Zone Analyzer:
    1. Detects trigger conditions (GST threshold, EOFY, revenue changes)
    2. Calls the Multi-Agent Orchestrator with options_format=True
    3. Parses the OPTIONS response into a rich insight with trade-offs

    Cost: ~$0.15 per insight (vs $0.05 for single-agent)
    Value: Strategic decisions with multiple options and recommendations
    """

    # Deduplication window for Magic Zone insights
    DEDUP_DAYS = 14

    def __init__(self, db: AsyncSession):
        """Initialize the Magic Zone analyzer.

        Args:
            db: Database session.
        """
        super().__init__(db)
        self.trigger_detector = MagicZoneTriggerDetector(db)
        self.orchestrator = MultiPerspectiveOrchestrator(db)

        # Check if Magic Zone is enabled
        settings = get_settings()
        self.enabled = getattr(settings, "enable_magic_zone_insights", True)

    @property
    def category(self) -> InsightCategory:
        """Magic Zone insights are strategic in nature."""
        return InsightCategory.STRATEGIC

    async def analyze_client(
        self,
        tenant_id: UUID,
        client_id: UUID,
    ) -> list[InsightCreate]:
        """Analyze a client for Magic Zone triggers.

        Args:
            tenant_id: The tenant ID.
            client_id: The client ID.

        Returns:
            List of InsightCreate objects for Magic Zone insights.
        """
        if not self.enabled:
            logger.debug("Magic Zone insights disabled")
            return []

        insights: list[InsightCreate] = []

        # Detect triggers
        triggers = await self.trigger_detector.detect_triggers(tenant_id, client_id)

        for trigger in triggers:
            # Check deduplication
            if not await self._should_generate(tenant_id, client_id, trigger):
                logger.debug(
                    f"Skipping Magic Zone trigger {trigger.trigger_type.value} - "
                    f"recent similar insight exists"
                )
                continue

            # Generate Magic Zone insight
            try:
                insight = await self._generate_magic_zone_insight(trigger)
                if insight:
                    insights.append(insight)
            except Exception as e:
                logger.error(
                    f"Magic Zone insight generation failed for {trigger.trigger_type.value}: {e}"
                )
                # Rollback to clear any failed transaction state so
                # subsequent triggers and _save_insights can still use the session
                await self.db.rollback()

        return insights

    async def _should_generate(
        self,
        tenant_id: UUID,
        client_id: UUID,
        trigger: MagicZoneTrigger,
    ) -> bool:
        """Check if we should generate a Magic Zone insight.

        Prevents duplicate insights for the same trigger type within
        the deduplication window.

        Args:
            tenant_id: The tenant ID.
            client_id: The client ID.
            trigger: The detected trigger.

        Returns:
            True if we should generate, False if duplicate exists.
        """
        insight_type = f"magic_zone_{trigger.trigger_type.value}"
        cutoff = datetime.now(UTC) - timedelta(days=self.DEDUP_DAYS)

        result = await self.db.execute(
            select(Insight)
            .where(
                Insight.tenant_id == tenant_id,
                Insight.client_id == client_id,
                Insight.insight_type == insight_type,
                Insight.generated_at >= cutoff,
            )
            .limit(1)
        )

        return result.scalar_one_or_none() is None

    async def _generate_magic_zone_insight(
        self,
        trigger: MagicZoneTrigger,
    ) -> InsightCreate | None:
        """Generate a Magic Zone insight using the Orchestrator.

        Args:
            trigger: The detected trigger.

        Returns:
            InsightCreate or None if generation fails.
        """
        logger.info(
            f"Generating Magic Zone insight for {trigger.trigger_type.value} "
            f"client={trigger.client_id}"
        )

        try:
            # Call orchestrator with OPTIONS format
            response = await self.orchestrator.process_query(
                query=trigger.orchestrator_query,
                tenant_id=trigger.tenant_id,
                user_id=trigger.tenant_id,  # Use tenant as user for automated insights
                connection_id=trigger.client_id,
                options_format=True,
            )

            # Build insight from response with evidence snapshot
            return self._build_insight(
                trigger,
                response.content,
                response.perspectives_used,
                raw_client_context=response.raw_client_context,
                raw_perspective_contexts=response.raw_perspective_contexts,
            )

        except Exception as e:
            logger.error(f"Orchestrator call failed: {e}")
            # Rollback to clear any failed transaction state from
            # the orchestrator's context builder DB queries
            await self.db.rollback()
            return None

    def _build_insight(
        self,
        trigger: MagicZoneTrigger,
        content: str,
        perspectives_used: list[Perspective],
        raw_client_context: Any | None = None,
        raw_perspective_contexts: dict[str, Any] | None = None,
    ) -> InsightCreate:
        """Build an InsightCreate from the orchestrator response.

        Args:
            trigger: The trigger that prompted this insight.
            content: The full OPTIONS response from orchestrator.
            perspectives_used: Which perspectives were used.
            raw_client_context: Raw client context from orchestrator for evidence.
            raw_perspective_contexts: Raw perspective contexts from orchestrator.

        Returns:
            InsightCreate object.
        """
        summary = self._extract_summary(content)
        options_count = self._count_options(content)
        actions = self._extract_actions(content, trigger)

        # Build evidence snapshot from orchestrator context if available
        snapshot = self._build_evidence_from_orchestrator(
            trigger, raw_client_context, raw_perspective_contexts, perspectives_used
        )

        return InsightCreate(
            category=InsightCategory.STRATEGIC,
            insight_type=f"magic_zone_{trigger.trigger_type.value}",
            priority=InsightPriority.HIGH if trigger.urgency == "high" else InsightPriority.MEDIUM,
            title=trigger.title,
            summary=summary,
            detail=content,
            suggested_actions=actions,
            related_url=f"/clients/{trigger.client_id}",
            confidence=self._calculate_confidence(snapshot, perspectives_used),
            data_snapshot=snapshot,
            # Magic Zone specific fields
            generation_type="magic_zone",
            agents_used=[p.value for p in perspectives_used],
            options_count=options_count,
        )

    def _extract_summary(self, content: str) -> str:
        """Extract a summary from the OPTIONS content.

        Takes the first paragraph or first ~200 chars as summary.

        Args:
            content: The full OPTIONS response.

        Returns:
            Summary string.
        """
        # Look for first paragraph
        paragraphs = content.strip().split("\n\n")

        for para in paragraphs:
            # Skip markdown headers
            if para.strip().startswith("#"):
                continue
            # Skip option headers
            if para.strip().startswith("### Option"):
                break

            clean = para.strip()
            if clean and len(clean) > 20:
                # Truncate if too long
                if len(clean) > 200:
                    return clean[:197] + "..."
                return clean

        # Fallback to first 200 chars
        return content[:200] + "..." if len(content) > 200 else content

    def _count_options(self, content: str) -> int:
        """Count the number of OPTIONS in the response.

        Args:
            content: The OPTIONS response.

        Returns:
            Number of options found.
        """
        # Look for "### Option X:" pattern
        pattern = r"###\s*Option\s+\d+"
        matches = re.findall(pattern, content, re.IGNORECASE)
        return len(matches)

    def _extract_actions(
        self,
        content: str,
        trigger: MagicZoneTrigger,
    ) -> list[SuggestedAction]:
        """Extract suggested actions from the OPTIONS content.

        Args:
            content: The OPTIONS response.
            trigger: The trigger context.

        Returns:
            List of SuggestedAction objects.
        """
        actions = []

        # Look for Action lines in OPTIONS
        pattern = r"\*\*Action:\*\*\s*(.+?)(?:\n|$)"
        matches = re.findall(pattern, content)

        for i, match in enumerate(matches[:3]):  # Max 3 actions
            action_text = match.strip()
            if action_text:
                actions.append(
                    SuggestedAction(
                        label=f"Option {i + 1}: {action_text[:40]}...",
                        url=f"/clients/{trigger.client_id}",
                    )
                )

        # Always add a "View Analysis" action
        actions.append(
            SuggestedAction(
                label="View Full Analysis",
                url=f"/clients/{trigger.client_id}",
            )
        )

        return actions

    def _build_snapshot(self, trigger: MagicZoneTrigger) -> dict[str, Any]:
        """Build a data snapshot for the insight.

        Args:
            trigger: The trigger with context data.

        Returns:
            Dictionary of snapshot data.
        """
        snapshot: dict[str, Any] = {
            "trigger_type": trigger.trigger_type.value,
            "urgency": trigger.urgency,
        }

        if trigger.revenue_trend:
            snapshot["revenue"] = {
                "current": trigger.revenue_trend.current_annual_revenue,
                "previous": trigger.revenue_trend.previous_annual_revenue,
                "change_percent": trigger.revenue_trend.revenue_change_percent,
                "direction": trigger.revenue_trend.trend_direction,
            }

        if trigger.current_revenue is not None:
            snapshot["current_revenue"] = trigger.current_revenue
            snapshot["gst_threshold"] = trigger.gst_threshold
            snapshot["distance_to_threshold"] = trigger.distance_to_threshold

        if trigger.days_until_eofy is not None:
            snapshot["days_until_eofy"] = trigger.days_until_eofy
            if trigger.eofy_date:
                snapshot["eofy_date"] = trigger.eofy_date.isoformat()

        return snapshot

    def _build_evidence_from_orchestrator(
        self,
        trigger: MagicZoneTrigger,
        raw_client_context: Any | None,
        raw_perspective_contexts: dict[str, Any] | None,
        perspectives_used: list[Perspective],
    ) -> dict[str, Any]:
        """Build evidence snapshot from orchestrator context.

        Falls back to trigger-based snapshot if orchestrator context unavailable.

        Args:
            trigger: The trigger with context data.
            raw_client_context: Raw client context from orchestrator.
            raw_perspective_contexts: Raw perspective contexts from orchestrator.
            perspectives_used: Which perspectives were used.

        Returns:
            Trimmed snapshot dict suitable for JSONB storage.
        """
        from app.modules.insights.evidence import build_evidence_snapshot, trim_snapshot_to_size

        if raw_client_context is not None:
            snapshot = build_evidence_snapshot(
                client_context=raw_client_context,
                perspective_contexts=raw_perspective_contexts,
            )
            snapshot.perspectives_used = [p.value for p in perspectives_used]
            return trim_snapshot_to_size(snapshot)

        # Fallback to trigger-based snapshot for backward compatibility
        return self._build_snapshot(trigger)

    def _calculate_confidence(
        self,
        snapshot: dict[str, Any],
        perspectives_used: list[Perspective],
    ) -> float:
        """Calculate meaningful confidence from data quality signals."""
        from app.modules.insights.evidence import DataSnapshotV1, calculate_confidence

        try:
            snap_model = DataSnapshotV1(**snapshot) if snapshot else None
        except Exception:
            snap_model = None

        freshness = snap_model.data_freshness if snap_model else None
        breakdown = calculate_confidence(
            snapshot=snap_model,
            data_freshness=freshness,
            knowledge_chunks_count=0,
            perspectives_used=[p.value for p in perspectives_used],
        )
        return breakdown["overall"]
