"""Insight analyzers for different categories.

Each analyzer is responsible for detecting insights in a specific category:
- ComplianceAnalyzer: GST thresholds, BAS deadlines, super obligations
- QualityAnalyzer: Unreconciled transactions, coding issues
- CashFlowAnalyzer: AR/AP aging, cash flow warnings
- AIAnalyzer: AI-powered analysis using Claude to find issues we haven't coded for
- JournalAnomalyAnalyzer: Unusual journal patterns (Spec 024)
"""

from app.modules.insights.analyzers.ai_analyzer import AIAnalyzer
from app.modules.insights.analyzers.base import BaseAnalyzer
from app.modules.insights.analyzers.cashflow import CashFlowAnalyzer
from app.modules.insights.analyzers.compliance import ComplianceAnalyzer
from app.modules.insights.analyzers.journal_anomaly import JournalAnomalyAnalyzer
from app.modules.insights.analyzers.quality import QualityAnalyzer

__all__ = [
    "AIAnalyzer",
    "BaseAnalyzer",
    "CashFlowAnalyzer",
    "ComplianceAnalyzer",
    "JournalAnomalyAnalyzer",
    "QualityAnalyzer",
]
