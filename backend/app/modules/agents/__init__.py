"""Multi-perspective AI agent system for Clairo.

This module provides intelligent query analysis using multiple perspectives:
- Compliance: ATO rules, GST, BAS requirements
- Quality: Data issues, reconciliation, coding errors
- Strategy: Tax optimization, business advice
- Insight: Trends, patterns, anomalies

The system uses a single LLM call with structured output for efficiency,
while providing attributed responses that show which perspective contributed
each insight.
"""

from app.modules.agents.audit import AgentAuditService
from app.modules.agents.orchestrator import MultiPerspectiveOrchestrator
from app.modules.agents.perspective_detector import PerspectiveDetector
from app.modules.agents.schemas import (
    AgentChatRequest,
    AgentChatResponse,
    EscalationStatus,
    OrchestratorResponse,
    Perspective,
    PerspectiveResult,
)
from app.modules.agents.settings import AgentSettings, agent_settings

__all__ = [
    "AgentAuditService",
    "AgentChatRequest",
    "AgentChatResponse",
    "AgentSettings",
    "EscalationStatus",
    "MultiPerspectiveOrchestrator",
    "OrchestratorResponse",
    "Perspective",
    "PerspectiveDetector",
    "PerspectiveResult",
    "agent_settings",
]
