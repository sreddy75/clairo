"""Audit logging service for the agents module.

This module handles logging agent queries and escalations for compliance
and analytics purposes. Query content is NOT stored for privacy - only
hashes and metadata.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.models import AgentEscalation, AgentQuery
from app.modules.agents.orchestrator import MultiPerspectiveOrchestrator
from app.modules.agents.schemas import EscalationStatus, OrchestratorResponse

logger = logging.getLogger(__name__)


class AgentAuditService:
    """Service for auditing agent queries and managing escalations.

    Responsibilities:
    - Log query metadata (NOT content) for compliance
    - Create and manage escalation records
    - Provide escalation statistics
    """

    def __init__(self, db: AsyncSession):
        """Initialize the audit service.

        Args:
            db: Database session.
        """
        self.db = db

    async def log_query(
        self,
        query: str,
        tenant_id: UUID,
        user_id: UUID,
        response: OrchestratorResponse,
        connection_id: UUID | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> AgentQuery:
        """Log a query to the audit table.

        Note: The actual query text is NOT stored - only a hash for
        deduplication and analytics.

        Args:
            query: The original query text (will be hashed, not stored).
            tenant_id: Tenant ID for the query.
            user_id: User who made the query.
            response: The orchestrator response.
            connection_id: Optional client connection ID.
            extra_data: Additional metadata to store.

        Returns:
            The created AgentQuery record.
        """
        query_hash = MultiPerspectiveOrchestrator.hash_query(query)

        agent_query = AgentQuery(
            correlation_id=response.correlation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            connection_id=connection_id,
            query_hash=query_hash,
            perspectives_used=[p.value for p in response.perspectives_used],
            confidence=response.confidence,
            escalation_required=response.escalation_required,
            escalation_reason=response.escalation_reason,
            processing_time_ms=response.processing_time_ms,
            token_usage=response.token_usage,
            extra_data=extra_data,
        )

        self.db.add(agent_query)
        await self.db.flush()

        logger.info(
            f"Logged agent query correlation_id={response.correlation_id}, "
            f"tenant_id={tenant_id}, escalation={response.escalation_required}"
        )

        return agent_query

    async def create_escalation(
        self,
        query: str,
        query_record: AgentQuery,
        response: OrchestratorResponse,
        tenant_id: UUID,
    ) -> AgentEscalation:
        """Create an escalation record for human review.

        Unlike the audit table, escalations DO store the query text
        since it needs to be reviewed by an accountant.

        Args:
            query: The original query text.
            query_record: The associated AgentQuery record.
            response: The orchestrator response.
            tenant_id: Tenant ID.

        Returns:
            The created AgentEscalation record.
        """
        escalation = AgentEscalation(
            query_id=query_record.id,
            tenant_id=tenant_id,
            reason=response.escalation_reason or "Low confidence",
            confidence=response.confidence,
            status=EscalationStatus.PENDING.value,
            query_text=query,
            perspectives_used=[p.value for p in response.perspectives_used],
            partial_response=response.content,
        )

        self.db.add(escalation)
        await self.db.flush()

        logger.info(
            f"Created escalation for query correlation_id={response.correlation_id}, "
            f"reason={response.escalation_reason}"
        )

        return escalation

    async def get_escalation(
        self,
        escalation_id: UUID,
        tenant_id: UUID,
    ) -> AgentEscalation | None:
        """Get an escalation by ID.

        Args:
            escalation_id: The escalation ID.
            tenant_id: Tenant ID for access control.

        Returns:
            The escalation record or None if not found.
        """
        result = await self.db.execute(
            select(AgentEscalation).where(
                AgentEscalation.id == escalation_id,
                AgentEscalation.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_escalations(
        self,
        tenant_id: UUID,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[AgentEscalation]:
        """List escalations for a tenant.

        Args:
            tenant_id: Tenant ID.
            status: Optional status filter.
            limit: Maximum records to return.
            offset: Records to skip.

        Returns:
            List of escalation records.
        """
        query = select(AgentEscalation).where(AgentEscalation.tenant_id == tenant_id)

        if status:
            query = query.where(AgentEscalation.status == status)

        query = query.order_by(AgentEscalation.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def resolve_escalation(
        self,
        escalation_id: UUID,
        tenant_id: UUID,
        resolved_by: UUID,
        resolution_notes: str,
        accountant_response: str | None = None,
        feedback_useful: bool | None = None,
    ) -> AgentEscalation | None:
        """Resolve an escalation.

        Args:
            escalation_id: The escalation ID.
            tenant_id: Tenant ID for access control.
            resolved_by: User ID of the resolver.
            resolution_notes: Notes explaining the resolution.
            accountant_response: Optional accountant's answer to the query.
            feedback_useful: Optional feedback on agent's analysis.

        Returns:
            The updated escalation record or None if not found.
        """
        escalation = await self.get_escalation(escalation_id, tenant_id)
        if not escalation:
            return None

        escalation.status = EscalationStatus.RESOLVED.value
        escalation.resolved_by = resolved_by
        escalation.resolved_at = datetime.now(UTC)
        escalation.resolution_notes = resolution_notes
        escalation.accountant_response = accountant_response
        escalation.feedback_useful = feedback_useful

        await self.db.flush()

        logger.info(f"Resolved escalation id={escalation_id}, resolved_by={resolved_by}")

        return escalation

    async def dismiss_escalation(
        self,
        escalation_id: UUID,
        tenant_id: UUID,
        dismissed_by: UUID,
        reason: str,
    ) -> AgentEscalation | None:
        """Dismiss an escalation without full resolution.

        Args:
            escalation_id: The escalation ID.
            tenant_id: Tenant ID for access control.
            dismissed_by: User ID of the dismisser.
            reason: Reason for dismissal.

        Returns:
            The updated escalation record or None if not found.
        """
        escalation = await self.get_escalation(escalation_id, tenant_id)
        if not escalation:
            return None

        escalation.status = EscalationStatus.DISMISSED.value
        escalation.resolved_by = dismissed_by
        escalation.resolved_at = datetime.now(UTC)
        escalation.resolution_notes = f"Dismissed: {reason}"

        await self.db.flush()

        logger.info(
            f"Dismissed escalation id={escalation_id}, dismissed_by={dismissed_by}, reason={reason}"
        )

        return escalation

    async def get_escalation_stats(
        self,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Get escalation statistics for a tenant.

        Args:
            tenant_id: Tenant ID.

        Returns:
            Dictionary with escalation statistics.
        """
        # Count pending escalations
        pending_result = await self.db.execute(
            select(func.count(AgentEscalation.id)).where(
                AgentEscalation.tenant_id == tenant_id,
                AgentEscalation.status == EscalationStatus.PENDING.value,
            )
        )
        pending_count = pending_result.scalar() or 0

        # Count resolved today
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        resolved_result = await self.db.execute(
            select(func.count(AgentEscalation.id)).where(
                AgentEscalation.tenant_id == tenant_id,
                AgentEscalation.status == EscalationStatus.RESOLVED.value,
                AgentEscalation.resolved_at >= today_start,
            )
        )
        resolved_today = resolved_result.scalar() or 0

        # Average confidence of pending escalations
        avg_result = await self.db.execute(
            select(func.avg(AgentEscalation.confidence)).where(
                AgentEscalation.tenant_id == tenant_id,
                AgentEscalation.status == EscalationStatus.PENDING.value,
            )
        )
        average_confidence = avg_result.scalar() or 0.0

        # Top escalation reasons
        reasons_result = await self.db.execute(
            select(
                AgentEscalation.reason,
                func.count(AgentEscalation.id).label("count"),
            )
            .where(AgentEscalation.tenant_id == tenant_id)
            .group_by(AgentEscalation.reason)
            .order_by(func.count(AgentEscalation.id).desc())
            .limit(5)
        )
        top_reasons = [{"reason": row[0], "count": row[1]} for row in reasons_result.all()]

        return {
            "pending_count": pending_count,
            "resolved_today": resolved_today,
            "average_confidence": float(average_confidence),
            "top_reasons": top_reasons,
        }

    async def get_query_by_correlation_id(
        self,
        correlation_id: UUID,
        tenant_id: UUID,
    ) -> AgentQuery | None:
        """Get a query record by correlation ID.

        Args:
            correlation_id: The correlation ID.
            tenant_id: Tenant ID for access control.

        Returns:
            The query record or None if not found.
        """
        result = await self.db.execute(
            select(AgentQuery).where(
                AgentQuery.correlation_id == correlation_id,
                AgentQuery.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()
