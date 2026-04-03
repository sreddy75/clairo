"""Analysis Pipeline Orchestrator.

Chains the 5 agents sequentially:
  Profiler → Scanner → Modeller → Advisor → Reviewer

Reports progress after each stage. Saves results to the database.
"""

import logging
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


class AnalysisPipelineOrchestrator:
    """Coordinates the multi-agent tax planning pipeline."""

    async def run(
        self,
        plan_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        on_progress: Any = None,
    ) -> UUID:
        """Execute the full analysis pipeline.

        Args:
            plan_id: The tax plan to analyse.
            tenant_id: Tenant for multi-tenancy.
            user_id: User who triggered the generation.
            on_progress: Optional callback(stage, stage_number, message).

        Returns:
            The analysis_id of the completed TaxPlanAnalysis.
        """
        raise NotImplementedError("AnalysisPipelineOrchestrator.run() not yet implemented")
