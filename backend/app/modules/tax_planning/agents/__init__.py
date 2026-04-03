"""Multi-agent tax planning pipeline.

Autonomous tax plan generation using 5 sequential agents:
1. Profiler — entity classification, eligibility, thresholds
2. Scanner — evaluate 15+ strategy categories with RAG citations
3. Modeller — model top strategies with real tax calculator
4. Advisor — generate accountant brief + client summary
5. Reviewer — verify numbers, citations, consistency
"""

from app.modules.tax_planning.agents.orchestrator import AnalysisPipelineOrchestrator

__all__ = ["AnalysisPipelineOrchestrator"]
