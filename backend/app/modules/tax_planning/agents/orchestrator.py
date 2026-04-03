"""Analysis Pipeline Orchestrator.

Chains the 5 agents sequentially:
  Profiler → Scanner → Modeller → Advisor → Reviewer

Reports progress after each stage. Saves results to the database.
"""

import logging
import time
from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.modules.tax_planning.agents.advisor import AdvisorAgent
from app.modules.tax_planning.agents.modeller import ScenarioModellerAgent
from app.modules.tax_planning.agents.profiler import ProfilerAgent
from app.modules.tax_planning.agents.reviewer import ReviewerAgent
from app.modules.tax_planning.agents.scanner import StrategyScannerAgent
from app.modules.tax_planning.models import AnalysisStatus
from app.modules.tax_planning.repository import (
    AnalysisRepository,
    ImplementationItemRepository,
    TaxPlanRepository,
    TaxRateConfigRepository,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, int, str], Any]


class AnalysisPipelineOrchestrator:
    """Coordinates the multi-agent tax planning pipeline."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.analysis_repo = AnalysisRepository(session)
        self.plan_repo = TaxPlanRepository(session)
        self.rate_repo = TaxRateConfigRepository(session)
        self.item_repo = ImplementationItemRepository(session)

    async def run(
        self,
        plan_id: UUID,
        tenant_id: UUID,
        analysis_id: UUID,
        on_progress: ProgressCallback | None = None,
    ) -> UUID:
        """Execute the full analysis pipeline.

        Args:
            plan_id: The tax plan to analyse.
            tenant_id: Tenant for multi-tenancy.
            analysis_id: Pre-created TaxPlanAnalysis record ID.
            on_progress: Optional callback(stage_name, stage_number, message).

        Returns:
            The analysis_id of the completed TaxPlanAnalysis.
        """
        start_time = time.time()
        api_key = self.settings.anthropic.api_key.get_secret_value()

        # Load plan and rate configs
        plan = await self.plan_repo.get_by_id(plan_id, tenant_id)
        if not plan or not plan.financials_data:
            raise ValueError(f"Plan {plan_id} not found or has no financials")

        rates = await self.rate_repo.get_rates_for_year(plan.financial_year)
        rate_configs = {r.rate_type: r.rates_data for r in rates}
        rate_configs["_financial_year"] = plan.financial_year

        analysis = await self.analysis_repo.get_by_id(analysis_id, tenant_id)
        if not analysis:
            raise ValueError(f"Analysis {analysis_id} not found")

        token_usage: dict[str, Any] = {}

        def _progress(stage: str, num: int, msg: str) -> None:
            if on_progress:
                on_progress(stage, num, msg)

        try:
            # Stage 1: Profile
            _progress("profiling", 1, "Analysing client profile...")
            profiler = ProfilerAgent(api_key=api_key)
            client_profile = await profiler.run(
                financials_data=plan.financials_data,
                entity_type=plan.entity_type,
                financial_year=plan.financial_year,
            )
            await self.analysis_repo.update(analysis, {"client_profile": client_profile})
            await self.session.commit()

            # Stage 2: Scan strategies
            _progress("scanning", 2, "Evaluating tax strategies...")
            scanner = StrategyScannerAgent(api_key=api_key)

            # RAG retrieval for compliance citations
            knowledge_chunks = await self._retrieve_knowledge(plan.entity_type)

            strategies = await scanner.run(
                client_profile=client_profile,
                financials_data=plan.financials_data,
                tax_position=plan.tax_position,
                knowledge_chunks=knowledge_chunks,
            )
            await self.analysis_repo.update(analysis, {"strategies_evaluated": strategies})
            await self.session.commit()

            # Stage 3: Model scenarios
            _progress("modelling", 3, "Modelling top strategies...")
            modeller = ScenarioModellerAgent(api_key=api_key)
            scenarios, combined = await modeller.run(
                strategies=strategies,
                financials_data=plan.financials_data,
                entity_type=plan.entity_type,
                rate_configs=rate_configs,
            )
            await self.analysis_repo.update(
                analysis,
                {"recommended_scenarios": scenarios, "combined_strategy": combined},
            )
            await self.session.commit()

            # Stage 4: Generate documents
            _progress("writing", 4, "Writing accountant brief...")
            advisor = AdvisorAgent(api_key=api_key)
            brief, summary = await advisor.run(
                client_profile=client_profile,
                scenarios=scenarios,
                combined_strategy=combined,
                strategies_evaluated=strategies,
                financials_data=plan.financials_data,
                financial_year=plan.financial_year,
            )
            await self.analysis_repo.update(
                analysis,
                {"accountant_brief": brief, "client_summary": summary},
            )
            await self.session.commit()

            # Stage 5: Quality review
            _progress("reviewing", 5, "Verifying calculations and citations...")
            reviewer = ReviewerAgent(api_key=api_key)
            review_result, review_passed = await reviewer.run(
                client_profile=client_profile,
                strategies_evaluated=strategies,
                recommended_scenarios=scenarios,
                combined_strategy=combined,
                accountant_brief=brief,
                client_summary=summary,
                financials_data=plan.financials_data,
                entity_type=plan.entity_type,
                rate_configs=rate_configs,
            )

            # Generate implementation items from recommended scenarios
            items = self._build_implementation_items(
                scenarios,
                tenant_id,
                analysis_id,
                plan.financial_year,
            )
            if items:
                await self.item_repo.create_batch(items)

            # Finalize
            elapsed_ms = int((time.time() - start_time) * 1000)
            await self.analysis_repo.update(
                analysis,
                {
                    "review_result": review_result,
                    "review_passed": review_passed,
                    "status": AnalysisStatus.DRAFT.value,
                    "generation_time_ms": elapsed_ms,
                    "token_usage": token_usage,
                },
            )
            await self.session.commit()

            logger.info(
                "Pipeline completed for plan %s in %dms: %d strategies, %d scenarios, review=%s",
                plan_id,
                elapsed_ms,
                len(strategies),
                len(scenarios),
                review_passed,
            )

            return analysis_id

        except Exception:
            # Mark analysis as failed
            try:
                await self.session.rollback()
                analysis = await self.analysis_repo.get_by_id(analysis_id, tenant_id)
                if analysis:
                    analysis.status = "failed"
                    await self.session.commit()
            except Exception:
                pass
            raise

    async def _retrieve_knowledge(self, entity_type: str) -> list[dict[str, Any]]:
        """Retrieve tax knowledge chunks for strategy citations."""
        try:
            from app.modules.knowledge.pinecone_service import PineconeService
            from app.modules.knowledge.service import KnowledgeSearchRequest, KnowledgeService
            from app.modules.knowledge.voyage_service import VoyageService

            pinecone = PineconeService(self.settings)
            voyage = VoyageService(self.settings)
            knowledge_service = KnowledgeService(
                self.session,
                pinecone,
                voyage,
            )
            entity_filters = {
                "company": ["company"],
                "individual": ["sole_trader", "individual"],
                "trust": ["trust"],
                "partnership": ["partnership"],
            }.get(entity_type, [])

            request = KnowledgeSearchRequest(
                query=f"tax planning strategies for {entity_type} EOFY",
                entity_types=entity_filters,
                exclude_superseded=True,
                limit=12,
            )
            results = await knowledge_service.search_knowledge(request)
            return [
                {
                    "title": r.get("title", ""),
                    "ruling_number": r.get("ruling_number"),
                    "section_ref": r.get("section_ref"),
                    "text": r.get("text", ""),
                    "relevance_score": r.get("relevance_score", 0),
                }
                for r in results
            ]
        except Exception:
            logger.warning("RAG retrieval failed, proceeding without knowledge", exc_info=True)
            return []

    @staticmethod
    def _build_implementation_items(
        scenarios: list[dict[str, Any]],
        tenant_id: UUID,
        analysis_id: UUID,
        financial_year: str,
    ) -> list[dict[str, Any]]:
        """Build implementation checklist items from recommended scenarios."""
        items = []
        fy_end_year = int(financial_year.split("-")[0]) + 1
        eofy = f"{fy_end_year}-06-30"

        for i, scenario in enumerate(scenarios):
            saving = scenario.get("impact", {}).get("change", {}).get("tax_saving", 0)
            items.append(
                {
                    "tenant_id": tenant_id,
                    "analysis_id": analysis_id,
                    "sort_order": i,
                    "title": scenario.get("scenario_title", f"Strategy {i + 1}"),
                    "description": scenario.get("description", ""),
                    "strategy_ref": scenario.get("strategy_id", ""),
                    "deadline": eofy,
                    "estimated_saving": saving if saving > 0 else None,
                    "risk_rating": scenario.get("risk_rating", "moderate"),
                    "compliance_notes": scenario.get("compliance_notes", ""),
                    "client_visible": True,
                    "status": "pending",
                }
            )

        return items
