"""Query intent detection for client context selection.

Detects the intent of user queries to determine which
financial summaries to include in AI context.
"""

import re
from dataclasses import dataclass
from enum import Enum


class QueryIntent(str, Enum):
    """Types of financial queries for context selection."""

    TAX_DEDUCTIONS = "tax_deductions"
    CASH_FLOW = "cash_flow"
    GST_BAS = "gst_bas"
    COMPLIANCE = "compliance"
    GENERAL = "general"


@dataclass
class IntentMatch:
    """Result of intent detection with confidence score."""

    intent: QueryIntent
    score: float
    matched_keywords: list[str]


# Keyword patterns for each intent category
INTENT_PATTERNS: dict[QueryIntent, list[str]] = {
    QueryIntent.TAX_DEDUCTIONS: [
        r"\btax\b",
        r"\bdeduct",
        r"\bexpense",
        r"\bclaim",
        r"\bwrite[\s-]?off",
        r"\bdepreciat",
        r"\basset",
        r"\bmotor\s+vehicle",
        r"\bcar\s+expense",
        r"\btravel\s+expense",
        r"\bhome\s+office",
        r"\bwork[\s-]?from[\s-]?home",
        r"\bequipment",
        r"\bsubscription",
        r"\bsoftware",
        r"\bprofessional\s+development",
        r"\btraining",
        r"\bfringe\s+benefit",
        r"\bfbt\b",
        r"\bato\b",
        r"\btaxable\b",
    ],
    QueryIntent.CASH_FLOW: [
        r"\bcash\b",
        r"\bcashflow",
        r"\bpayment",
        r"\bpay\s+me",
        r"\bowing",
        r"\bowed",
        r"\boverdue",
        r"\baged\s+receivable",
        r"\baged\s+payable",
        r"\breceivable",
        r"\bpayable",
        r"\bar\b",
        r"\bap\b",
        r"\bdebtor",
        r"\bcreditor",
        r"\binvoice",
        r"\bbill",
        r"\bunpaid",
        r"\boutstanding",
        r"\bcollect",
        r"\bchase",
        r"\bfollow[\s-]?up",
        r"\bdue\s+date",
        r"\bbalance",
    ],
    QueryIntent.GST_BAS: [
        r"\bgst\b",
        r"\bbas\b",
        r"\bquarter",
        r"\bactivity\s+statement",
        r"\b1a\b",
        r"\b1b\b",
        r"\bg1\b",
        r"\bg2\b",
        r"\bg3\b",
        r"\bg10\b",
        r"\bg11\b",
        r"\blodge",
        r"\blodgement",
        r"\brefund",
        r"\bpayable\s+to\s+ato",
        r"\bato\s+payment",
        r"\bgst\s+on\s+sale",
        r"\bgst\s+on\s+purchase",
        r"\binput\s+tax",
        r"\boutput\s+tax",
        r"\btax\s+code",
        r"\bgst[\s-]?free",
        r"\bno\s+gst",
        r"\binclusive",
        r"\bexclusive",
    ],
    QueryIntent.COMPLIANCE: [
        r"\bpayroll\b",
        r"\bwage",
        r"\bsalary",
        r"\bsuper\b",
        r"\bsuperannuation",
        r"\bpayg\b",
        r"\bwithholding",
        r"\bcontractor",
        r"\bemployee",
        r"\bstaff",
        r"\bstp\b",
        r"\bsingle\s+touch",
        r"\bleave",
        r"\bannual\s+leave",
        r"\bsick\s+leave",
        r"\bworkcover",
        r"\bworkers\s+comp",
        r"\bsuperannuation\s+guarantee",
        r"\bsgc\b",
        r"\bsgg\b",
        r"\btpd\b",
        r"\bpension",
        r"\bretirement",
        r"\btax\s+file\s+number",
        r"\btfn\b",
        r"\babn\b.*contractor",
    ],
}


class QueryIntentDetector:
    """Detects the intent of financial queries.

    Uses keyword pattern matching with scoring to determine
    which financial context is most relevant to a query.
    """

    def __init__(self) -> None:
        """Initialize the intent detector with compiled patterns."""
        self._compiled_patterns: dict[QueryIntent, list[re.Pattern[str]]] = {}
        for intent, patterns in INTENT_PATTERNS.items():
            self._compiled_patterns[intent] = [re.compile(p, re.IGNORECASE) for p in patterns]

    def detect(
        self,
        query: str,
        conversation_history: list[str] | None = None,
    ) -> IntentMatch:
        """Detect the intent of a query.

        Args:
            query: The user's question or query text.
            conversation_history: Optional list of previous messages
                for context-aware detection.

        Returns:
            IntentMatch with the detected intent, score, and matched keywords.
        """
        # Score each intent based on keyword matches
        intent_scores: dict[QueryIntent, tuple[float, list[str]]] = {}

        # Analyze current query
        for intent, patterns in self._compiled_patterns.items():
            matches = []
            for pattern in patterns:
                found = pattern.findall(query)
                if found:
                    matches.extend(found)

            # Base score from current query
            score = len(matches) * 1.0
            intent_scores[intent] = (score, matches)

        # Boost score from conversation history
        if conversation_history:
            history_text = " ".join(conversation_history[-3:])  # Last 3 messages
            for intent, patterns in self._compiled_patterns.items():
                history_matches = []
                for pattern in patterns:
                    found = pattern.findall(history_text)
                    if found:
                        history_matches.extend(found)

                # Add 30% weight to history matches
                current_score, current_matches = intent_scores[intent]
                history_boost = len(history_matches) * 0.3
                intent_scores[intent] = (
                    current_score + history_boost,
                    current_matches,
                )

        # Find the highest scoring intent
        best_intent = QueryIntent.GENERAL
        best_score = 0.0
        best_matches: list[str] = []

        for intent, (score, matches) in intent_scores.items():
            if score > best_score:
                best_score = score
                best_intent = intent
                best_matches = matches

        # Default to GENERAL if no significant matches
        if best_score < 0.5:
            best_intent = QueryIntent.GENERAL
            best_matches = []

        return IntentMatch(
            intent=best_intent,
            score=best_score,
            matched_keywords=list(set(best_matches)),
        )

    def is_drill_down_request(self, query: str) -> bool:
        """Check if the query is requesting detailed data.

        Args:
            query: The user's question.

        Returns:
            True if the query requests specific transaction/invoice details.
        """
        drill_down_patterns = [
            r"\bshow\s+me",
            r"\blist\b",
            r"\bdetail",
            r"\bspecific",
            r"\bbreakdown",
            r"\bitemiz",
            r"\bline\s+item",
            r"\beach\s+",
            r"\bevery\s+",
            r"\ball\s+the\s+",
            r"\btransaction",
            r"\bwhat\s+invoices?",
            r"\bwhich\s+bills?",
        ]

        for pattern in drill_down_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return True

        return False
