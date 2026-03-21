"""LLM-assisted query expansion for improved retrieval recall.

For CONCEPTUAL, PROCEDURAL, SCENARIO, and CASE_LAW queries, the query
expander generates additional search variants that include relevant
section numbers, legal terms, and synonyms.  This improves recall for
vague or colloquial queries that would otherwise miss precise
legislative language.

Two expansion strategies are applied in sequence:

1. **Synonym expansion** (always, no LLM) -- expands abbreviations and
   alternative terms from a curated legal synonym table.
2. **LLM expansion** (best-effort) -- uses Claude to generate 2-3
   alternative query formulations with specific section numbers, act
   names, and legal terminology.

For SECTION_LOOKUP and RULING_LOOKUP queries the original query is
returned unchanged because these are already precise references.

On any error (API failure, timeout, missing key) the expander degrades
gracefully and returns only the original query.
"""

from __future__ import annotations

import asyncio
import logging
import re

from app.modules.knowledge.retrieval.query_router import QueryType

logger = logging.getLogger(__name__)

# =============================================================================
# Legal Synonym Table
# =============================================================================
#
# Each entry maps a canonical term to its alternative forms.  During
# expansion, if the query contains *any* term in a group, the other
# terms are appended in parentheses to the query string.  This is
# bidirectional: "GST" expands to "(Goods and Services Tax, GST Act
# 1999)" and vice-versa.

LEGAL_SYNONYM_TABLE: dict[str, list[str]] = {
    "GST": ["Goods and Services Tax", "GST Act 1999"],
    "Div 7A": ["Division 7A", "deemed dividend", "ITAA 1936 Part III"],
    "CGT": ["capital gains tax", "ITAA 1997 Part 3-1"],
    "FBT": ["fringe benefits tax", "FBTAA 1986"],
    "SMSF": ["self-managed superannuation fund", "SIS Act"],
    "PAYG": ["pay as you go", "withholding"],
    "TFN": ["tax file number"],
    "ABN": ["Australian Business Number"],
    "BAS": ["business activity statement"],
    "IAS": ["instalment activity statement"],
}

# Pre-compile patterns for each synonym group.  For every group we
# build a regex for each term so that matching is case-insensitive and
# word-boundary aware.  The compiled patterns are stored as a list of
# ``(pattern, group_key)`` tuples for linear scanning.
_SYNONYM_PATTERNS: list[tuple[re.Pattern[str], str]] = []

for _key, _alternatives in LEGAL_SYNONYM_TABLE.items():
    _all_terms = [_key, *_alternatives]
    for _term in _all_terms:
        _pattern = re.compile(r"\b" + re.escape(_term) + r"\b", re.IGNORECASE)
        _SYNONYM_PATTERNS.append((_pattern, _key))

# Query types that benefit from expansion (non-precise queries).
_EXPANDABLE_QUERY_TYPES: frozenset[QueryType] = frozenset(
    {
        QueryType.CONCEPTUAL,
        QueryType.PROCEDURAL,
        QueryType.SCENARIO,
        QueryType.CASE_LAW,
    }
)

# LLM configuration
_LLM_MODEL = "claude-haiku-4-5-20251001"
_LLM_TIMEOUT_SECONDS = 5
_LLM_MAX_TOKENS = 256

_LLM_SYSTEM_PROMPT = (
    "You are an Australian tax law search assistant. Generate 2-3 "
    "alternative search queries that would help find relevant "
    "legislation, rulings, and case law for the given question. "
    "Include specific section numbers, act names, and legal "
    "terminology where possible. Return ONLY the queries, one per line."
)


# =============================================================================
# QueryExpander
# =============================================================================


class QueryExpander:
    """Expand search queries with legal synonyms and LLM-generated variants.

    Args:
        anthropic_api_key: Anthropic API key for LLM expansion.  If
            ``None``, the key is loaded from application settings.  If
            the key is unavailable, only synonym expansion is applied.
    """

    def __init__(self, anthropic_api_key: str | None = None) -> None:
        self._api_key = anthropic_api_key
        if self._api_key is None:
            self._api_key = self._load_api_key_from_settings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def expand_query(self, query: str, query_type: QueryType) -> list[str]:
        """Expand a query into multiple search variants.

        For precise query types (``SECTION_LOOKUP``, ``RULING_LOOKUP``)
        the original query is returned unchanged.  For all other types
        the query is first expanded with legal synonyms and then
        (best-effort) with LLM-generated variants.

        Args:
            query: The user's original search query.
            query_type: Classified query type from the query router.

        Returns:
            A list of query strings starting with the original query
            followed by any expanded variants.
        """
        if query_type not in _EXPANDABLE_QUERY_TYPES:
            return [query]

        try:
            # Step 1: Always apply synonym expansion (fast, no LLM)
            synonym_expanded = self._expand_with_synonyms(query)

            # Step 2: Best-effort LLM expansion
            llm_variants = await self._expand_with_llm(synonym_expanded, query_type.value)

            # Combine: original first, then LLM variants
            result = [query]
            for variant in llm_variants:
                # Avoid duplicating the original query
                if variant.strip().lower() != query.strip().lower():
                    result.append(variant)

            return result

        except Exception:
            logger.exception("Query expansion failed; returning original query")
            return [query]

    # ------------------------------------------------------------------
    # Synonym Expansion
    # ------------------------------------------------------------------

    def _expand_with_synonyms(self, query: str) -> str:
        """Expand abbreviations and alternative terms using the synonym table.

        Scans the query for known legal terms and appends their
        alternative forms in parentheses.  Each synonym group is
        expanded at most once even if multiple terms from the same
        group appear in the query.

        Args:
            query: Original query text.

        Returns:
            The query with synonym expansions appended.
        """
        matched_groups: set[str] = set()
        expansions: list[str] = []

        for pattern, group_key in _SYNONYM_PATTERNS:
            if group_key in matched_groups:
                continue
            if pattern.search(query):
                matched_groups.add(group_key)
                # Collect all terms in the group except the one(s) already
                # present in the query.
                all_terms = [group_key, *LEGAL_SYNONYM_TABLE[group_key]]
                extra_terms = [
                    t
                    for t in all_terms
                    if not re.search(r"\b" + re.escape(t) + r"\b", query, re.IGNORECASE)
                ]
                if extra_terms:
                    expansions.append("(" + ", ".join(extra_terms) + ")")

        if not expansions:
            return query

        return query + " " + " ".join(expansions)

    # ------------------------------------------------------------------
    # LLM Expansion
    # ------------------------------------------------------------------

    async def _expand_with_llm(self, query: str, query_type: str) -> list[str]:
        """Generate query variants using Claude.

        Calls Claude (claude-haiku-4-5-20251001) with a system prompt
        instructing it to produce 2-3 alternative search queries with
        specific legal terminology.

        Args:
            query: The (possibly synonym-expanded) query text.
            query_type: String value of the ``QueryType`` enum for
                context in the prompt.

        Returns:
            List of expanded query strings (NOT including the original).
            Returns an empty list on any failure.
        """
        if not self._api_key:
            logger.debug("No Anthropic API key configured; skipping LLM query expansion")
            return []

        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=self._api_key)

            response = await asyncio.wait_for(
                client.messages.create(
                    model=_LLM_MODEL,
                    max_tokens=_LLM_MAX_TOKENS,
                    system=_LLM_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": query}],
                ),
                timeout=_LLM_TIMEOUT_SECONDS,
            )

            # Parse response: extract text, split by newline
            raw_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    raw_text += block.text

            variants = [line.strip() for line in raw_text.strip().splitlines() if line.strip()]

            # Remove any numbering prefixes (e.g., "1. ", "- ")
            cleaned: list[str] = []
            for variant in variants:
                cleaned_variant = re.sub(r"^\d+[\.\)]\s*", "", variant)
                cleaned_variant = re.sub(r"^[-*]\s*", "", cleaned_variant)
                cleaned_variant = cleaned_variant.strip()
                if cleaned_variant:
                    cleaned.append(cleaned_variant)

            logger.debug(
                "LLM query expansion produced %d variants for query type '%s'",
                len(cleaned),
                query_type,
            )
            return cleaned

        except TimeoutError:
            logger.warning(
                "LLM query expansion timed out after %ds",
                _LLM_TIMEOUT_SECONDS,
            )
            return []
        except Exception:
            logger.exception("LLM query expansion failed")
            return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_api_key_from_settings() -> str | None:
        """Attempt to load the Anthropic API key from application settings.

        Returns:
            The API key string, or ``None`` if not configured.
        """
        try:
            from app.config import get_settings

            settings = get_settings()
            key = settings.anthropic.api_key.get_secret_value()
            return key if key else None
        except Exception:
            logger.debug(
                "Could not load Anthropic API key from settings; "
                "LLM query expansion will be disabled"
            )
            return None
