"""Trigger execution engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.insights.models import Insight
from app.modules.triggers.evaluators.data_triggers import DataThresholdEvaluator
from app.modules.triggers.evaluators.event_triggers import EventTriggerEvaluator
from app.modules.triggers.evaluators.time_triggers import TimeScheduleEvaluator
from app.modules.triggers.models import Trigger, TriggerExecution, TriggerType
from app.modules.triggers.service import TriggerService


@dataclass
class InsightResult:
    """Result of insight generation for a single client."""

    client_id: UUID
    created: int = 0
    skipped: bool = False
    reason: str | None = None
    insight_ids: list[UUID] = field(default_factory=list)


@dataclass
class ExecutionResult:
    """Overall result of trigger execution."""

    success: bool
    clients_evaluated: int = 0
    insights_created: int = 0
    insights_deduplicated: int = 0
    client_results: list[InsightResult] = field(default_factory=list)
    error_message: str | None = None


class TriggerExecutor:
    """Executes triggers and generates insights.

    Implements the three-layer deduplication strategy:
    - Layer 3: Trigger-level throttle
    - Layer 1: Cross-trigger dedup
    - Layer 2: InsightGenerator dedup (built-in)
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.service = TriggerService(db)
        self.data_evaluator = DataThresholdEvaluator(db)
        self.time_evaluator = TimeScheduleEvaluator(db)
        self.event_evaluator = EventTriggerEvaluator(db)

    async def execute(
        self,
        trigger: Trigger,
        tenant_id: UUID,
        client_ids: list[UUID] | None = None,
    ) -> ExecutionResult:
        """Execute a trigger and generate insights.

        Args:
            trigger: The trigger to execute
            tenant_id: The tenant ID
            client_ids: Optional list of specific clients to evaluate.
                        If None, uses the evaluator to find matching clients.

        Returns:
            ExecutionResult with details of the execution.
        """
        # Create execution record
        execution = await self.service.create_execution(trigger, tenant_id)

        try:
            # Get clients to evaluate
            if client_ids is None:
                client_ids = await self._get_clients_for_trigger(trigger, tenant_id)

            result = ExecutionResult(success=True)
            client_id_strs: list[str] = []

            for client_id in client_ids:
                client_result = await self._execute_for_client(trigger, tenant_id, client_id)
                result.client_results.append(client_result)
                result.clients_evaluated += 1
                client_id_strs.append(str(client_id))

                if client_result.skipped:
                    result.insights_deduplicated += 1
                else:
                    result.insights_created += client_result.created

            # Complete execution record
            await self.service.complete_execution(
                execution,
                success=True,
                clients_evaluated=result.clients_evaluated,
                insights_created=result.insights_created,
                insights_deduplicated=result.insights_deduplicated,
                client_ids=client_id_strs,
            )

            # Update trigger last executed
            await self.service.mark_executed(trigger, success=True)

            return result

        except Exception as e:
            error_msg = str(e)
            result = ExecutionResult(
                success=False,
                error_message=error_msg,
            )

            # Complete execution with error
            await self.service.complete_execution(
                execution,
                success=False,
                clients_evaluated=0,
                insights_created=0,
                insights_deduplicated=0,
                client_ids=[],
                error_message=error_msg,
            )

            # Update trigger with failure
            await self.service.mark_executed(trigger, success=False, error=error_msg)

            return result

    async def _execute_for_client(
        self,
        trigger: Trigger,
        tenant_id: UUID,
        client_id: UUID,
    ) -> InsightResult:
        """Execute trigger for a single client.

        Implements the three-layer deduplication check.
        """
        result = InsightResult(client_id=client_id)

        # LAYER 3: Trigger-level throttle
        if await self._trigger_recently_fired(trigger, client_id):
            result.skipped = True
            result.reason = "trigger_throttle"
            return result

        # Process each target analyzer
        for analyzer in trigger.target_analyzers:
            # LAYER 1: Cross-trigger dedup
            if await self._similar_insight_exists(client_id, analyzer, hours=24):
                result.skipped = True
                result.reason = "cross_trigger_dedup"
                continue

            # Generate insights using InsightGenerator (has LAYER 2 built-in)
            insights = await self._generate_insights(tenant_id, client_id, analyzer, trigger.id)
            result.created += len(insights)
            result.insight_ids.extend([i.id for i in insights])

        if result.created > 0:
            result.skipped = False
            result.reason = None

        return result

    async def _get_clients_for_trigger(
        self,
        trigger: Trigger,
        tenant_id: UUID,
    ) -> list[UUID]:
        """Get clients to evaluate based on trigger type."""
        if trigger.trigger_type == TriggerType.DATA_THRESHOLD:
            return await self.data_evaluator.get_matching_clients(trigger, tenant_id)
        elif trigger.trigger_type == TriggerType.TIME_SCHEDULED:
            return await self.time_evaluator.get_matching_clients(trigger, tenant_id)
        elif trigger.trigger_type == TriggerType.EVENT_BASED:
            return await self.event_evaluator.get_matching_clients(trigger, tenant_id)
        return []

    async def _similar_insight_exists(
        self,
        client_id: UUID,
        category: str,
        hours: int = 24,
    ) -> bool:
        """Check if ANY trigger created similar insight recently (Layer 1)."""
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        result = await self.db.execute(
            select(Insight)
            .where(Insight.client_id == client_id)
            .where(Insight.category == category)
            .where(Insight.created_at > cutoff)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _trigger_recently_fired(
        self,
        trigger: Trigger,
        client_id: UUID,
    ) -> bool:
        """Check if this specific trigger fired for this client recently (Layer 3)."""
        if trigger.dedup_window_hours == 0:
            return False  # No throttle (e.g., new client welcome)

        cutoff = datetime.now(UTC) - timedelta(hours=trigger.dedup_window_hours)

        # Check trigger executions that included this client
        result = await self.db.execute(
            select(TriggerExecution)
            .where(TriggerExecution.trigger_id == trigger.id)
            .where(TriggerExecution.started_at > cutoff)
            .where(TriggerExecution.status == "success")
        )
        executions = result.scalars().all()

        # Check if any execution included this client
        client_id_str = str(client_id)
        for execution in executions:
            if client_id_str in execution.client_ids:
                return True

        return False

    async def _generate_insights(
        self,
        tenant_id: UUID,
        client_id: UUID,
        analyzer: str,
        trigger_id: UUID,
    ) -> list[Insight]:
        """Generate insights using the InsightGenerator.

        The InsightGenerator has its own Layer 2 deduplication built-in.
        """
        # Import here to avoid circular imports
        from app.modules.insights.generator import InsightGenerator

        generator = InsightGenerator(self.db)

        # Map analyzer name to generator method
        analyzer_map = {
            "cash_flow": generator._analyze_cash_flow,
            "quality": generator._analyze_data_quality,
            "compliance": generator._analyze_compliance,
        }

        if analyzer not in analyzer_map:
            return []

        # Call the specific analyzer
        analyze_fn = analyzer_map[analyzer]
        insights = await analyze_fn(tenant_id, client_id)

        # Mark insights as trigger-generated
        for insight in insights:
            insight.source = f"trigger:{trigger_id}"

        return insights
