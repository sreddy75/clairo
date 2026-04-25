"""Insight service for CRUD operations and business logic."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.insights.models import Insight, InsightStatus
from app.modules.insights.schemas import (
    ClientReference,
    InsightCreate,
    InsightDashboardResponse,
    InsightListResponse,
    InsightResponse,
    InsightStats,
    MultiClientQueryResponse,
)

logger = logging.getLogger(__name__)


class InsightService:
    """Service for managing insights."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        tenant_id: UUID,
        client_id: UUID | None,
        data: InsightCreate,
        source: str,
    ) -> Insight:
        """Create a new insight."""
        insight = Insight(
            tenant_id=tenant_id,
            client_id=client_id,
            category=data.category.value,
            insight_type=data.insight_type,
            priority=data.priority.value,
            title=data.title,
            summary=data.summary,
            detail=data.detail,
            suggested_actions=[a.model_dump() for a in data.suggested_actions],
            related_url=data.related_url,
            expires_at=data.expires_at,
            action_deadline=data.action_deadline,
            confidence=data.confidence,
            data_snapshot=data.data_snapshot,
            generation_source=source,
            status=InsightStatus.NEW.value,
            # Magic Zone fields
            generation_type=data.generation_type,
            agents_used=data.agents_used,
            options_count=data.options_count,
        )
        self.db.add(insight)
        await self.db.flush()
        return insight

    async def get_by_id(
        self,
        insight_id: UUID,
        tenant_id: UUID,
    ) -> Insight | None:
        """Get a single insight by ID."""
        result = await self.db.execute(
            select(Insight)
            .options(selectinload(Insight.client))
            .where(
                Insight.id == insight_id,
                Insight.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        tenant_id: UUID,
        status: list[str] | None = None,
        priority: list[str] | None = None,
        category: list[str] | None = None,
        client_id: UUID | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> InsightListResponse:
        """List insights with filtering."""
        query = (
            select(Insight)
            .options(selectinload(Insight.client))
            .where(Insight.tenant_id == tenant_id)
        )

        # Apply filters
        if status:
            query = query.where(Insight.status.in_(status))
        else:
            # By default, exclude dismissed and expired
            query = query.where(
                Insight.status.notin_([InsightStatus.DISMISSED.value, InsightStatus.EXPIRED.value])
            )

        if priority:
            query = query.where(Insight.priority.in_(priority))

        if category:
            query = query.where(Insight.category.in_(category))

        if client_id:
            query = query.where(Insight.client_id == client_id)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting and pagination
        query = (
            query.order_by(
                # Priority order: high first
                func.array_position(
                    ["high", "medium", "low"],
                    Insight.priority,
                ),
                Insight.generated_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)
        insights = result.scalars().all()

        return InsightListResponse(
            insights=[self._to_response(i) for i in insights],
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(insights)) < total,
        )

    async def get_dashboard(
        self,
        tenant_id: UUID,
        top_count: int = 5,
    ) -> InsightDashboardResponse:
        """Get dashboard summary with top insights and stats."""
        # Get top insights (new and high priority first)
        top_query = (
            select(Insight)
            .options(selectinload(Insight.client))
            .where(
                Insight.tenant_id == tenant_id,
                Insight.status.notin_([InsightStatus.DISMISSED.value, InsightStatus.EXPIRED.value]),
            )
            .order_by(
                # New first, then by priority
                Insight.status == InsightStatus.NEW.value,
                func.array_position(["high", "medium", "low"], Insight.priority),
                Insight.generated_at.desc(),
            )
            .limit(top_count)
        )
        top_result = await self.db.execute(top_query)
        top_insights = top_result.scalars().all()

        # Get stats
        stats = await self._get_stats(tenant_id)

        # Count new (unviewed)
        new_count_result = await self.db.execute(
            select(func.count()).where(
                Insight.tenant_id == tenant_id,
                Insight.status == InsightStatus.NEW.value,
            )
        )
        new_count = new_count_result.scalar() or 0

        return InsightDashboardResponse(
            top_insights=[self._to_response(i) for i in top_insights],
            stats=stats,
            new_count=new_count,
        )

    async def _get_stats(self, tenant_id: UUID) -> InsightStats:
        """Get insight statistics.

        Performance: Queries are optimized with proper indexes on tenant_id, status,
        priority, and category. Consider Redis caching if load increases significantly.
        """
        base_query = select(Insight).where(
            Insight.tenant_id == tenant_id,
            Insight.status.notin_([InsightStatus.DISMISSED.value, InsightStatus.EXPIRED.value]),
        )

        # Total count
        total_result = await self.db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = total_result.scalar() or 0

        # By priority
        priority_result = await self.db.execute(
            select(Insight.priority, func.count())
            .where(
                Insight.tenant_id == tenant_id,
                Insight.status.notin_([InsightStatus.DISMISSED.value, InsightStatus.EXPIRED.value]),
            )
            .group_by(Insight.priority)
        )
        by_priority = {row[0]: row[1] for row in priority_result.all()}

        # By category
        category_result = await self.db.execute(
            select(Insight.category, func.count())
            .where(
                Insight.tenant_id == tenant_id,
                Insight.status.notin_([InsightStatus.DISMISSED.value, InsightStatus.EXPIRED.value]),
            )
            .group_by(Insight.category)
        )
        by_category = {row[0]: row[1] for row in category_result.all()}

        # By status
        status_result = await self.db.execute(
            select(Insight.status, func.count())
            .where(Insight.tenant_id == tenant_id)
            .group_by(Insight.status)
        )
        by_status = {row[0]: row[1] for row in status_result.all()}

        # New this week
        week_ago = datetime.now(UTC) - timedelta(days=7)
        new_week_result = await self.db.execute(
            select(func.count()).where(
                Insight.tenant_id == tenant_id,
                Insight.generated_at >= week_ago,
            )
        )
        new_this_week = new_week_result.scalar() or 0

        return InsightStats(
            total=total,
            by_priority=by_priority,
            by_category=by_category,
            by_status=by_status,
            new_this_week=new_this_week,
        )

    async def mark_viewed(
        self,
        insight_id: UUID,
        tenant_id: UUID,
    ) -> Insight | None:
        """Mark an insight as viewed."""
        insight = await self.get_by_id(insight_id, tenant_id)
        if not insight:
            return None

        if insight.status == InsightStatus.NEW.value:
            insight.status = InsightStatus.VIEWED.value
        insight.viewed_at = datetime.now(UTC)
        await self.db.flush()
        return insight

    async def mark_actioned(
        self,
        insight_id: UUID,
        tenant_id: UUID,
        notes: str | None = None,  # noqa: ARG002 - Reserved for future use
    ) -> Insight | None:
        """Mark an insight as actioned."""
        insight = await self.get_by_id(insight_id, tenant_id)
        if not insight:
            return None

        insight.status = InsightStatus.ACTIONED.value
        insight.actioned_at = datetime.now(UTC)
        if insight.viewed_at is None:
            insight.viewed_at = datetime.now(UTC)
        await self.db.flush()
        return insight

    async def dismiss(
        self,
        insight_id: UUID,
        tenant_id: UUID,
        notes: str | None = None,  # noqa: ARG002 - Reserved for future use
    ) -> Insight | None:
        """Dismiss an insight."""
        insight = await self.get_by_id(insight_id, tenant_id)
        if not insight:
            return None

        insight.status = InsightStatus.DISMISSED.value
        insight.dismissed_at = datetime.now(UTC)
        await self.db.flush()
        return insight

    async def find_similar(
        self,
        tenant_id: UUID,
        client_id: UUID | None,
        insight_type: str,
        days: int = 7,
    ) -> Insight | None:
        """Find a recent insight with the same type for deduplication.

        Performs exact match on insight_type. This is the fast-path for
        rule-based analyzers with deterministic type strings.

        Semantic dedup for AI-generated insights (varying titles/types)
        is handled separately by InsightDedupService via Pinecone/Voyage.
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        filters = [
            Insight.tenant_id == tenant_id,
            Insight.insight_type == insight_type,
            Insight.generated_at >= cutoff,
            Insight.status.notin_([InsightStatus.DISMISSED.value, InsightStatus.EXPIRED.value]),
        ]

        if client_id:
            filters.append(Insight.client_id == client_id)
        else:
            filters.append(Insight.client_id.is_(None))

        result = await self.db.execute(select(Insight).where(*filters).limit(1))
        return result.scalar_one_or_none()

    async def get_insights_summary(
        self,
        tenant_id: UUID,
        client_id: UUID,
        top_n: int = 5,
    ) -> tuple[str, str]:
        """Fetch top N insights for a client and format as HTML + plain-text summary.

        Ordered by priority (high first), then confidence (descending).
        Returns (html_section, text_section) for email embedding.
        Used by FR-021: include insights in lodgement confirmation email.
        """
        priority_order = func.array_position(
            ["high", "medium", "low"],
            Insight.priority,
        )
        stmt = (
            select(Insight)
            .where(
                Insight.tenant_id == tenant_id,
                Insight.client_id == client_id,
                Insight.status.notin_([InsightStatus.DISMISSED.value, InsightStatus.EXPIRED.value]),
            )
            .order_by(
                priority_order.asc(),
                Insight.confidence.desc().nulls_last(),
            )
            .limit(top_n)
        )
        result = await self.db.execute(stmt)
        insights = result.scalars().all()

        if not insights:
            return "", ""

        # HTML section
        rows_html = "\n".join(
            f'<li style="margin: 0 0 6px 0; font-size: 14px; color: #374151;">'
            f"<strong>{i.title}</strong> — {i.summary}</li>"
            for i in insights
        )
        html = (
            '<table role="presentation" cellspacing="0" cellpadding="0" border="0" '
            'style="background-color: #f0fdf4; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">'
            "<tr><td>"
            '<p style="color: #065f46; font-size: 14px; font-weight: 600; margin: 0 0 10px 0;">'
            "This Quarter in Numbers</p>"
            f'<ul style="margin: 0; padding: 0 0 0 18px;">{rows_html}</ul>'
            "</td></tr></table>"
        )

        # Plain-text section
        rows_text = "\n".join(f"- {i.title}: {i.summary}" for i in insights)
        text = f"This Quarter in Numbers:\n{rows_text}"

        return html, text

    async def expire_old_insights(self, tenant_id: UUID | None = None) -> tuple[int, list[UUID]]:
        """Mark insights past their expiry date as expired.

        Returns:
            Tuple of (count of expired insights, list of expired insight IDs).
        """
        from sqlalchemy import update

        query = (
            update(Insight)
            .where(
                Insight.expires_at.isnot(None),
                Insight.expires_at < datetime.now(UTC),
                Insight.status.notin_(
                    [
                        InsightStatus.EXPIRED.value,
                        InsightStatus.DISMISSED.value,
                        InsightStatus.ACTIONED.value,
                    ]
                ),
            )
            .values(status=InsightStatus.EXPIRED.value)
            .returning(Insight.id)
        )

        if tenant_id:
            query = query.where(Insight.tenant_id == tenant_id)

        result = await self.db.execute(query)
        expired_ids = [row[0] for row in result.fetchall()]
        return len(expired_ids), expired_ids

    def _to_response(self, insight: Insight) -> InsightResponse:
        """Convert model to response schema."""
        from app.modules.insights.schemas import SuggestedAction

        # Build client URL for navigation
        client_url = None
        client_name = None
        if insight.client:
            client_name = insight.client.organization_name
            client_url = f"/clients/{insight.client_id}"

        return InsightResponse(
            id=insight.id,
            tenant_id=insight.tenant_id,
            client_id=insight.client_id,
            category=insight.category,
            insight_type=insight.insight_type,
            priority=insight.priority,
            title=insight.title,
            summary=insight.summary,
            detail=insight.detail,
            suggested_actions=[
                SuggestedAction.model_validate(a) for a in (insight.suggested_actions or [])
            ],
            related_url=insight.related_url,
            status=insight.status,
            generated_at=insight.generated_at,
            expires_at=insight.expires_at,
            action_deadline=insight.action_deadline,
            viewed_at=insight.viewed_at,
            actioned_at=insight.actioned_at,
            generation_source=insight.generation_source,
            confidence=insight.confidence,
            generation_type=insight.generation_type or "rule_based",
            agents_used=insight.agents_used,
            options_count=insight.options_count,
            data_snapshot=insight.data_snapshot,
            client_name=client_name,
            client_url=client_url,
        )

    async def query_multi_client(
        self,
        tenant_id: UUID,
        query: str,
        include_inactive: bool = False,
    ) -> MultiClientQueryResponse:
        """Query insights across all clients using AI.

        Gathers all active insights and uses Claude to analyze them
        and answer the user's question.

        Args:
            tenant_id: The tenant ID.
            query: Natural language query from the user.
            include_inactive: Whether to include dismissed/expired insights.

        Returns:
            AI-generated response with client references.
        """
        import anthropic

        from app.config import get_settings

        settings = get_settings()

        # Get all relevant insights
        status_filter = (
            None
            if include_inactive
            else [
                InsightStatus.NEW.value,
                InsightStatus.VIEWED.value,
                InsightStatus.ACTIONED.value,
            ]
        )

        insights_response = await self.list(
            tenant_id=tenant_id,
            status=status_filter,
            limit=100,  # Get more insights for comprehensive context
        )

        insights = insights_response.insights

        if not insights:
            return MultiClientQueryResponse(
                response="No insights are currently available for your clients. "
                "Insights are generated automatically after data syncs. "
                "Please ensure your client data is synced and check back later.",
                clients_referenced=[],
                perspectives_used=[],
                confidence=0.5,
                insights_included=0,
            )

        # Build context from insights
        insights_context = self._build_insights_context(insights)

        # Build the prompt
        system_prompt = """You are an AI assistant for accountants using Clairo,
an Australian accounting practice management platform. You have access to
proactive insights about their clients that highlight issues needing attention.

Analyze the insights provided and answer the user's question. Be specific about
which clients are mentioned. Use Australian accounting terminology.

Format your response clearly, with specific client names when relevant.
If the query cannot be answered from the available insights, say so clearly."""

        user_prompt = f"""Here are the current insights for this practice:

{insights_context}

User question: {query}

Please analyze the insights and provide a helpful response."""

        # Call Claude API
        try:
            client = anthropic.Anthropic(api_key=settings.anthropic.api_key.get_secret_value())
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            ai_response = response.content[0].text

            # Audit log AI query
            try:
                from app.core.audit import AuditService

                audit = AuditService(self.session)
                await audit.log_event(
                    event_type="ai.insights.summary",
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

        except Exception as e:
            logger.error(f"AI query failed: {e}")
            return MultiClientQueryResponse(
                response=f"Unable to process query: {e!s}",
                clients_referenced=[],
                perspectives_used=[],
                confidence=0.0,
                insights_included=len(insights),
            )

        # Extract referenced clients from insights
        clients_referenced = self._extract_clients_from_insights(insights, ai_response)

        # Identify perspectives used
        perspectives = list({i.category for i in insights})

        return MultiClientQueryResponse(
            response=ai_response,
            clients_referenced=clients_referenced,
            perspectives_used=perspectives,
            confidence=0.85,
            insights_included=len(insights),
        )

    def _build_insights_context(self, insights: list[InsightResponse]) -> str:
        """Build a text context from insights for the AI."""
        context_parts = []

        for i, insight in enumerate(insights, 1):
            client_name = insight.client_name or "Practice-wide"
            context_parts.append(
                f"{i}. [{insight.priority.upper()}] {insight.title}\n"
                f"   Client: {client_name}\n"
                f"   Category: {insight.category}\n"
                f"   Summary: {insight.summary}\n"
            )

        return "\n".join(context_parts)

    def _extract_clients_from_insights(
        self,
        insights: list[InsightResponse],
        ai_response: str,
    ) -> list[ClientReference]:
        """Extract clients mentioned in the AI response."""
        # Group insights by client
        client_insights: dict[UUID, dict] = {}

        for insight in insights:
            if not insight.client_id or not insight.client_name:
                continue

            # Check if client is mentioned in the response
            if insight.client_name.lower() not in ai_response.lower():
                continue

            if insight.client_id not in client_insights:
                client_insights[insight.client_id] = {
                    "name": insight.client_name,
                    "issues": [],
                }

            client_insights[insight.client_id]["issues"].append(insight.title)

        return [
            ClientReference(
                id=client_id,
                name=data["name"],
                issues=data["issues"][:5],  # Limit to 5 issues per client
            )
            for client_id, data in client_insights.items()
        ]
