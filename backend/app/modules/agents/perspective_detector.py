"""Perspective detection for multi-agent queries.

This module determines which perspectives (Compliance, Quality, Strategy, Insight)
are relevant for a given query using LLM-based classification.
"""

import json
import logging
from dataclasses import dataclass

import anthropic

from app.config import get_settings
from app.modules.agents.schemas import Perspective
from app.modules.knowledge.context_builder import ClientContext

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """Result of perspective detection."""

    perspectives: list[Perspective]
    reasoning: str
    confidence: float


# Perspective descriptions for the LLM prompt
PERSPECTIVE_DESCRIPTIONS = {
    "compliance": (
        "ATO rules, GST registration/reporting, BAS requirements, PAYG withholding, "
        "superannuation obligations, tax deadlines, deduction eligibility, instant asset "
        "write-off rules, depreciation rules, and regulatory compliance."
    ),
    "quality": (
        "Data quality issues: uncoded transactions, reconciliation status, duplicate entries, "
        "missing information, GST coding errors, data completeness for BAS lodgement."
    ),
    "strategy": (
        "Business overview, financial health assessment, tax optimization strategies, "
        "cash flow planning, asset management, purchase orders, quotes pipeline, "
        "recurring revenue/expense analysis, growth planning, and business advice."
    ),
    "insight": (
        "Financial trends and patterns, revenue projections, threshold monitoring, "
        "anomaly detection, comparative analysis, risk identification, and data-driven observations."
    ),
}

CLASSIFICATION_PROMPT = """You are a query classifier for an Australian accounting AI assistant.

Given a user query, determine which analysis perspectives are relevant. Choose 1-3 perspectives.

## Available Perspectives

1. **compliance**: {compliance}

2. **quality**: {quality}

3. **strategy**: {strategy}

4. **insight**: {insight}

## Classification Rules

- Most queries need 1-2 perspectives
- Use "strategy" for business overviews, financial health, assets, cash flow, planning questions
- Use "insight" for trend analysis, anomaly detection, data observations
- Use "compliance" for tax rules, ATO requirements, BAS, GST, deductions
- Use "quality" for data issues, errors, reconciliation problems
- General "tell me about" or "overview" queries → strategy + insight
- Asset/depreciation questions → strategy + compliance
- "What's wrong" or "check" queries → quality + compliance

## Response Format

Return ONLY valid JSON (no markdown):
{{"perspectives": ["perspective1", "perspective2"], "reasoning": "brief explanation"}}

## Query

{query}""".format(**PERSPECTIVE_DESCRIPTIONS, query="{query}")


class PerspectiveDetector:
    """Detects which perspectives are relevant for a query using LLM classification."""

    def __init__(
        self,
        default_perspectives: list[Perspective] | None = None,
        use_llm: bool = True,
    ):
        """Initialize the detector.

        Args:
            default_perspectives: Fallback perspectives if detection fails.
            use_llm: Whether to use LLM for classification (can disable for testing).
        """
        self.default_perspectives = default_perspectives or [
            Perspective.STRATEGY,
            Perspective.INSIGHT,
        ]
        self.use_llm = use_llm
        self._client: anthropic.Anthropic | None = None

    @property
    def client(self) -> anthropic.Anthropic:
        """Lazy-load Anthropic client."""
        if self._client is None:
            settings = get_settings()
            api_key = settings.anthropic.api_key.get_secret_value()
            self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    def detect(
        self,
        query: str,
        client_context: ClientContext | None = None,
    ) -> DetectionResult:
        """Detect relevant perspectives for a query using LLM.

        Args:
            query: The user's question
            client_context: Optional client context (for future use)

        Returns:
            DetectionResult with perspectives, reasoning, and confidence
        """
        if not self.use_llm:
            return self._fallback_detect(query)

        try:
            return self._llm_detect(query)
        except Exception as e:
            logger.warning(f"LLM perspective detection failed: {e}, using fallback")
            return self._fallback_detect(query)

    def _llm_detect(self, query: str) -> DetectionResult:
        """Use Claude Haiku for fast, intelligent perspective classification."""
        prompt = CLASSIFICATION_PROMPT.format(query=query)

        response = self.client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse the response
        content = response.content[0].text.strip()

        # Handle potential markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        try:
            result = json.loads(content)
            perspectives = [
                Perspective(p.lower())
                for p in result.get("perspectives", [])
                if p.lower() in [e.value for e in Perspective]
            ]
            reasoning = result.get("reasoning", "LLM classification")

            if not perspectives:
                perspectives = self.default_perspectives

            return DetectionResult(
                perspectives=perspectives[:3],  # Max 3 perspectives
                reasoning=reasoning,
                confidence=0.9,
            )

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response: {content}, error: {e}")
            return self._fallback_detect(query)

    def _fallback_detect(self, query: str) -> DetectionResult:
        """Simple fallback detection when LLM is unavailable."""
        query_lower = query.lower()
        perspectives = []

        # Simple keyword-based fallback
        if any(
            kw in query_lower
            for kw in ["gst", "bas", "tax", "ato", "deduct", "claim", "compliance"]
        ):
            perspectives.append(Perspective.COMPLIANCE)

        if any(
            kw in query_lower for kw in ["error", "issue", "wrong", "reconcil", "quality", "check"]
        ):
            perspectives.append(Perspective.QUALITY)

        if any(
            kw in query_lower
            for kw in ["overview", "strategic", "health", "asset", "cash flow", "advice", "plan"]
        ):
            perspectives.append(Perspective.STRATEGY)

        if any(
            kw in query_lower for kw in ["trend", "insight", "anomal", "pattern", "why", "analys"]
        ):
            perspectives.append(Perspective.INSIGHT)

        # Default to Strategy + Insight for general queries
        if not perspectives:
            perspectives = self.default_perspectives

        return DetectionResult(
            perspectives=perspectives[:3],
            reasoning="Fallback keyword matching",
            confidence=0.6,
        )

    def get_perspective_description(self, perspective: Perspective) -> str:
        """Get a description of what a perspective analyzes."""
        return PERSPECTIVE_DESCRIPTIONS.get(perspective.value, "")
