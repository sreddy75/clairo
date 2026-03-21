"""Insight Engine module for proactive intelligence.

Provides:
- Proactive insight generation (system surfaces issues)
- Multi-client queries (cross-portfolio analysis)
- Workflow integration (AI assistance in BAS prep)
"""

from app.modules.insights.models import (
    Insight,
    InsightCategory,
    InsightPriority,
    InsightStatus,
)
from app.modules.insights.schemas import (
    InsightCreate,
    InsightDashboardResponse,
    InsightListResponse,
    InsightResponse,
)
from app.modules.insights.service import InsightService

__all__ = [
    "Insight",
    "InsightCategory",
    "InsightCreate",
    "InsightDashboardResponse",
    "InsightListResponse",
    "InsightPriority",
    "InsightResponse",
    "InsightService",
    "InsightStatus",
]
