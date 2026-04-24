"""Insight generator that orchestrates all analyzers.

The InsightGenerator is the main entry point for generating insights.
It runs all analyzers and handles deduplication, storage, and notifications.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.insights.analyzers.ai_analyzer import AIAnalyzer
from app.modules.insights.analyzers.cashflow import CashFlowAnalyzer
from app.modules.insights.analyzers.compliance import ComplianceAnalyzer
from app.modules.insights.analyzers.magic_zone import MagicZoneAnalyzer
from app.modules.insights.analyzers.quality import QualityAnalyzer
from app.modules.insights.dedup import InsightDedupService
from app.modules.insights.service import InsightService
from app.modules.integrations.xero.models import XeroConnection

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.pinecone_service import PineconeService
    from app.core.voyage import VoyageService
    from app.modules.insights.analyzers.base import BaseAnalyzer
    from app.modules.insights.models import Insight
    from app.modules.insights.schemas import InsightCreate

logger = logging.getLogger(__name__)

# Minimum confidence to keep an insight at HIGH/URGENT priority.
# Insights below this threshold are downgraded to MEDIUM so low-quality
# AI guesses don't pollute the urgent triage bucket.
URGENT_CONFIDENCE_THRESHOLD = 0.70


class InsightGenerator:
    """Orchestrates insight generation across all analyzers.

    Usage:
        generator = InsightGenerator(db)
        insights = await generator.generate_for_tenant(tenant_id)
        # or for a single client:
        insights = await generator.generate_for_client(tenant_id, client_id)

        # With semantic dedup (recommended):
        generator = InsightGenerator(db, pinecone=pinecone, voyage=voyage)
    """

    def __init__(
        self,
        db: AsyncSession,
        pinecone: PineconeService | None = None,
        voyage: VoyageService | None = None,
    ):
        """Initialize the generator with database session.

        Args:
            db: Async database session.
            pinecone: Optional Pinecone service for semantic dedup.
            voyage: Optional Voyage service for semantic dedup.
        """
        self.db = db
        self.service = InsightService(db)

        # Semantic dedup service (None if Pinecone/Voyage not provided)
        self._dedup: InsightDedupService | None = None
        if pinecone and voyage:
            self._dedup = InsightDedupService(pinecone, voyage, db)

        # Initialize all analyzers
        # Rule-based analyzers run first for deterministic checks
        # AI analyzer runs after for intelligent pattern detection
        # Magic Zone runs last for high-value strategic insights
        self.analyzers: list[BaseAnalyzer] = [
            ComplianceAnalyzer(db),
            QualityAnalyzer(db),
            CashFlowAnalyzer(db),
            AIAnalyzer(db),  # AI-powered analysis
            MagicZoneAnalyzer(db),  # Multi-agent strategic insights
        ]

    async def generate_for_client(
        self,
        tenant_id: UUID,
        client_id: UUID,
        source: str = "manual",
    ) -> list[Insight]:
        """Generate insights for a single client.

        Runs all analyzers for the specified client and saves
        any new insights (after deduplication).

        Args:
            tenant_id: The tenant ID.
            client_id: The client (XeroConnection) ID.
            source: Source of generation (manual, scheduled, post_sync).

        Returns:
            List of newly created Insight objects.
        """
        logger.info(f"Generating insights for client {client_id}")

        # Expire any past-due insights before generating new ones
        expired_count, expired_ids = await self.service.expire_old_insights(tenant_id)
        if expired_count:
            logger.info(f"Expired {expired_count} past-due insights for tenant {tenant_id}")
            # Remove dedup vectors for expired insights
            if self._dedup and expired_ids:
                await self._dedup.remove_insights_batch(expired_ids)

        all_insight_creates: list[InsightCreate] = []

        # Track topics covered by rule-based analyzers so the AI doesn't duplicate them.
        # Keywords are normalized (underscores removed) so "cash_flow" matches "cashflow".
        _TOPIC_KEYWORDS = [
            "bas",
            "gst",
            "overdue",
            "receivable",
            "payable",
            "aging",
            "quality",
            "reconcil",
            "freshness",
            "cashflow",
            "draft",
            "invoice",
            "expense",
        ]
        rule_based_topics: set[str] = set()

        # Run each analyzer
        for analyzer in self.analyzers:
            try:
                insights = await analyzer.analyze_client(tenant_id, client_id)
                is_ai = analyzer.__class__.__name__ in ("AIAnalyzer", "MagicZoneAnalyzer")
                if is_ai and rule_based_topics:
                    # Filter out AI insights that overlap with rule-based topics.
                    # Normalize by stripping underscores so "cash_flow" == "cashflow".
                    before = len(insights)
                    insights = [
                        i
                        for i in insights
                        if not any(
                            kw in i.insight_type.lower().replace("_", "")
                            for kw in rule_based_topics
                        )
                    ]
                    dropped = before - len(insights)
                    if dropped:
                        logger.debug(f"Dropped {dropped} AI insights overlapping rule-based topics")
                else:
                    # Collect topic keywords from rule-based analyzers
                    for i in insights:
                        normalized_type = i.insight_type.lower().replace("_", "")
                        for kw in _TOPIC_KEYWORDS:
                            if kw in normalized_type:
                                rule_based_topics.add(kw)

                all_insight_creates.extend(insights)
                logger.debug(
                    f"Analyzer {analyzer.__class__.__name__} found {len(insights)} insights"
                )
            except Exception as e:
                logger.error(
                    f"Analyzer {analyzer.__class__.__name__} failed for client {client_id}: {e}"
                )
                # Rollback to clear any failed transaction state so
                # subsequent analyzers and _save_insights can still use the session
                await self.db.rollback()

        # T045: Confidence threshold routing — downgrade high-priority low-confidence insights
        from app.modules.insights.models import InsightPriority  # noqa: PLC0415 (lazy import ok)
        for ic in all_insight_creates:
            if ic.priority == InsightPriority.HIGH and ic.confidence < URGENT_CONFIDENCE_THRESHOLD:
                ic.priority = InsightPriority.MEDIUM

        # T046: Type-level deduplication — keep highest-confidence instance per (insight_type)
        seen: dict[str, int] = {}  # insight_type -> index in all_insight_creates
        deduped: list[InsightCreate] = []
        for ic in all_insight_creates:
            key = ic.insight_type
            if key in seen:
                existing_idx = seen[key]
                if ic.confidence > deduped[existing_idx].confidence:
                    deduped[existing_idx] = ic
            else:
                seen[key] = len(deduped)
                deduped.append(ic)
        if len(deduped) < len(all_insight_creates):
            logger.debug(
                f"Deduped {len(all_insight_creates) - len(deduped)} duplicate insight(s) by type"
            )
        all_insight_creates = deduped

        # Save insights (with deduplication)
        saved_insights = await self._save_insights(
            tenant_id=tenant_id,
            client_id=client_id,
            insight_creates=all_insight_creates,
            source=source,
        )

        logger.info(
            f"Generated {len(saved_insights)} new insights for client {client_id} "
            f"(from {len(all_insight_creates)} candidates)"
        )

        return saved_insights

    async def generate_for_tenant(
        self,
        tenant_id: UUID,
        source: str = "scheduled",
    ) -> list[Insight]:
        """Generate insights for all clients in a tenant.

        Args:
            tenant_id: The tenant ID.
            source: Source of generation.

        Returns:
            List of all newly created Insight objects.
        """
        logger.info(f"Generating insights for tenant {tenant_id}")

        # Get all active clients
        clients = await self._get_active_clients(tenant_id)
        logger.info(f"Found {len(clients)} active clients")

        all_insights: list[Insight] = []

        for client in clients:
            try:
                client_insights = await self.generate_for_client(
                    tenant_id=tenant_id,
                    client_id=client.id,
                    source=source,
                )
                all_insights.extend(client_insights)
            except Exception as e:
                logger.error(f"Failed to generate insights for client {client.id}: {e}")

        logger.info(f"Generated {len(all_insights)} total insights for tenant {tenant_id}")

        return all_insights

    async def _get_active_clients(self, tenant_id: UUID) -> list[XeroConnection]:
        """Get all active Xero connections for a tenant."""
        result = await self.db.execute(
            select(XeroConnection).where(
                XeroConnection.tenant_id == tenant_id,
                XeroConnection.status == "active",
            )
        )
        return list(result.scalars().all())

    async def _save_insights(
        self,
        tenant_id: UUID,
        client_id: UUID,
        insight_creates: list[InsightCreate],
        source: str,
    ) -> list[Insight]:
        """Save insights with deduplication.

        Uses a two-pass dedup strategy:
        1. Exact match on insight_type (cheap, handles rule-based analyzers).
        2. Semantic search via Pinecone/Voyage (catches AI-generated duplicates
           with varying titles/types).

        When a semantic duplicate is found the existing insight is updated
        in-place rather than creating a new row.

        Args:
            tenant_id: The tenant ID.
            client_id: The client ID.
            insight_creates: List of InsightCreate objects to save.
            source: Source of generation.

        Returns:
            List of newly created or updated Insight objects.
        """
        from datetime import UTC, datetime

        saved: list[Insight] = []

        for insight_data in insight_creates:
            try:
                # Pass 1: exact insight_type match (fast, works for rule-based)
                existing = await self.service.find_similar(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    insight_type=insight_data.insight_type,
                    days=7,
                )

                if existing:
                    logger.debug(
                        f"Exact-match dedup: skipping {insight_data.insight_type} "
                        f"for client {client_id}"
                    )
                    continue

                # Pass 2: semantic dedup via Pinecone/Voyage
                if self._dedup and client_id:
                    semantic_match = await self._dedup.find_duplicate(
                        title=insight_data.title,
                        summary=insight_data.summary,
                        client_id=client_id,
                        tenant_id=tenant_id,
                    )

                    if semantic_match:
                        # Update the existing insight in-place
                        logger.info(
                            f"Semantic dedup: updating existing insight "
                            f"{semantic_match.id} with new content from "
                            f"'{insight_data.title}'"
                        )
                        semantic_match.title = insight_data.title
                        semantic_match.summary = insight_data.summary
                        semantic_match.detail = insight_data.detail
                        semantic_match.suggested_actions = [
                            a.model_dump() for a in insight_data.suggested_actions
                        ]
                        semantic_match.confidence = insight_data.confidence
                        semantic_match.generated_at = datetime.now(UTC)

                        await self.db.flush()

                        # Refresh the embedding to match updated content
                        await self._dedup.update_insight_vector(semantic_match)

                        saved.append(semantic_match)
                        continue

                # No duplicate found — create new insight
                insight = await self.service.create(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    data=insight_data,
                    source=source,
                )
                saved.append(insight)

                # Index the new insight for future dedup
                if self._dedup:
                    await self._dedup.index_insight(insight)

                # Create notification for high priority insights
                if insight_data.priority.value == "high":
                    await self._create_notification(insight)
            except Exception as e:
                logger.error(
                    f"Failed to save insight {insight_data.insight_type} "
                    f"for client {client_id}: {e}"
                )
                await self.db.rollback()

        return saved

    async def _create_notification(self, insight: Insight) -> None:
        """Create a notification for a high-priority insight.

        Note: The current notification model requires a user_id which we don't
        have in the insight generation context. For now, we skip notification
        creation. In the future, this could broadcast to all users in the tenant
        or use a dedicated notification queue.

        Args:
            insight: The insight to create a notification for.
        """
        # TODO: Implement when notification system supports tenant-wide broadcasts
        # The notification model requires user_id which is not available in insight context
        logger.debug(
            f"Skipping notification for insight {insight.id} - "
            "notification system requires user_id (not available in insight context)"
        )
