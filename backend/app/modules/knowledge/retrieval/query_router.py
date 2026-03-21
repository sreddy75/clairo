"""Legal query classification and routing for hybrid search.

Classifies incoming tax questions into query types and determines
the optimal retrieval strategy (fusion weights + Pinecone metadata
filters). This drives the hybrid search parameters.

Query classification is pure regex/keyword matching -- no LLM calls --
so it executes in sub-millisecond time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

# =============================================================================
# Query Type Classification
# =============================================================================


class QueryType(str, Enum):
    """Types of legal/tax queries for retrieval strategy selection."""

    SECTION_LOOKUP = "section_lookup"
    RULING_LOOKUP = "ruling_lookup"
    CONCEPTUAL = "conceptual"
    PROCEDURAL = "procedural"
    SCENARIO = "scenario"
    CASE_LAW = "case_law"


@dataclass
class QueryClassification:
    """Result of query classification with retrieval parameters.

    Attributes:
        query_type: Detected query type.
        confidence: Classification confidence score (0-1).
        pinecone_filter: Metadata filter dict to pass to Pinecone, or None.
        fusion_weights: Tuple of (semantic_weight, keyword_weight) for
            Reciprocal Rank Fusion between dense and sparse retrieval.
        extracted_refs: Section or ruling references found in the query text.
        domain_detected: Tax domain slug if automatically detected, or None.
    """

    query_type: QueryType
    confidence: float
    pinecone_filter: dict | None
    fusion_weights: tuple[float, float]
    extracted_refs: list[str] = field(default_factory=list)
    domain_detected: str | None = None


# =============================================================================
# Compiled Regex Patterns (module-level for performance)
# =============================================================================

# Section reference patterns
_SECTION_REF_PATTERNS: list[re.Pattern[str]] = [
    # "s109D", "s104-10", "s23AG", "s100A"
    re.compile(r"\bs(\d+[A-Za-z]*(?:-\d+[A-Za-z]*)*)\b", re.IGNORECASE),
    # "section 109D", "section 104-10"
    re.compile(r"\bsection\s+(\d+[A-Za-z]*(?:-\d+[A-Za-z]*)*)\b", re.IGNORECASE),
    # "Div 7A", "Division 7A", "Div 104", "Division 104"
    re.compile(r"\bDiv(?:ision)?\s+(\d+[A-Za-z]*)\b", re.IGNORECASE),
    # "Part 3-1", "Part III"
    re.compile(r"\bPart\s+(\d+(?:-\d+)?|[IVX]+)\b", re.IGNORECASE),
]

# Ruling reference patterns
_RULING_REF_PATTERNS: list[re.Pattern[str]] = [
    # "TR 2024/1", "TR2024/1"
    re.compile(r"\bTR\s*(\d{4}/?\d+)\b", re.IGNORECASE),
    # "GSTR 2000/1", "GSTR2000/1", "GSTD 2000/1"
    re.compile(r"\bGSTR?\s*(\d{4}/?\d+)\b", re.IGNORECASE),
    # "TD 2024/1"
    re.compile(r"\bTD\s*(\d{4}/?\d+)\b", re.IGNORECASE),
    # "PCG 2024/1"
    re.compile(r"\bPCG\s*(\d{4}/?\d+)\b", re.IGNORECASE),
    # "CR 2024/1"
    re.compile(r"\bCR\s*(\d{4}/?\d+)\b", re.IGNORECASE),
]

# Full ruling number extraction (includes prefix)
_RULING_FULL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(TR\s*\d{4}/?\d+)\b", re.IGNORECASE),
    re.compile(r"\b(GSTR?\s*\d{4}/?\d+)\b", re.IGNORECASE),
    re.compile(r"\b(TD\s*\d{4}/?\d+)\b", re.IGNORECASE),
    re.compile(r"\b(PCG\s*\d{4}/?\d+)\b", re.IGNORECASE),
    re.compile(r"\b(CR\s*\d{4}/?\d+)\b", re.IGNORECASE),
]

# Case law keyword pattern
_CASE_LAW_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:court|case|tribunal|decision|judgment|judgement|appeal|AAT|FCA|HCA"
    r"|FCAFC|AATA|Federal\s+Court|High\s+Court)\b",
    re.IGNORECASE,
)

# Procedural query patterns
_PROCEDURAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bhow\s+to\b", re.IGNORECASE),
    re.compile(r"\bhow\s+do\s+I\b", re.IGNORECASE),
    re.compile(r"\bsteps?\s+to\b", re.IGNORECASE),
    re.compile(r"\bprocess\s+for\b", re.IGNORECASE),
    re.compile(r"\bregister\s+for\b", re.IGNORECASE),
    re.compile(r"\blodge\b", re.IGNORECASE),
    re.compile(r"\bapply\s+for\b", re.IGNORECASE),
    re.compile(r"\bwhen\s+do\s+I\s+need\s+to\b", re.IGNORECASE),
]

# Scenario query patterns
_SCENARIO_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bmy\s+client\b", re.IGNORECASE),
    re.compile(r"\ba\s+company\s+with\b", re.IGNORECASE),
    re.compile(r"\bif\s+a\s+business\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+if\b", re.IGNORECASE),
    re.compile(r"\bscenario\b", re.IGNORECASE),
    re.compile(r"\bin\s+the\s+case\s+where\b", re.IGNORECASE),
    re.compile(r"\bassume\b", re.IGNORECASE),
]

# =============================================================================
# Domain Detection Mapping
# =============================================================================

# Maps domain slug to topic tags for keyword matching and Pinecone filtering.
DOMAIN_TOPIC_TAGS: dict[str, list[str]] = {
    "gst": ["gst", "goods_and_services_tax"],
    "division_7a": ["division_7a", "deemed_dividend"],
    "cgt": ["cgt", "capital_gains"],
    "smsf": ["smsf", "superannuation"],
    "fbt": ["fbt", "fringe_benefits"],
    "trusts": ["trusts", "trust_distributions"],
    "payg": ["payg", "pay_as_you_go"],
    "international": ["international_tax", "transfer_pricing"],
    "deductions": ["deductions", "work_related"],
}

# Compiled domain keyword patterns (built once at module load)
_DOMAIN_PATTERNS: dict[str, list[re.Pattern[str]]] = {}
for _slug, _tags in DOMAIN_TOPIC_TAGS.items():
    _DOMAIN_PATTERNS[_slug] = [
        re.compile(r"\b" + re.escape(tag) + r"\b", re.IGNORECASE) for tag in _tags
    ]
# Add common keyword aliases that also map to domains
_DOMAIN_ALIAS_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "gst": [
        re.compile(r"\bgst\b", re.IGNORECASE),
        re.compile(r"\bgoods\s+and\s+services\s+tax\b", re.IGNORECASE),
        re.compile(r"\binput\s+tax\s+credit\b", re.IGNORECASE),
        re.compile(r"\btaxable\s+supply\b", re.IGNORECASE),
    ],
    "division_7a": [
        re.compile(r"\bdiv(?:ision)?\s*7\s*a\b", re.IGNORECASE),
        re.compile(r"\bdeemed\s+dividend\b", re.IGNORECASE),
        re.compile(r"\bshareholder\s+loan\b", re.IGNORECASE),
        re.compile(r"\bs109[A-Z]?\b", re.IGNORECASE),
    ],
    "cgt": [
        re.compile(r"\bcgt\b", re.IGNORECASE),
        re.compile(r"\bcapital\s+gains?\b", re.IGNORECASE),
        re.compile(r"\bcost\s+base\b", re.IGNORECASE),
        re.compile(r"\bcgt\s+event\b", re.IGNORECASE),
        re.compile(r"\bcgt\s+discount\b", re.IGNORECASE),
    ],
    "smsf": [
        re.compile(r"\bsmsf\b", re.IGNORECASE),
        re.compile(r"\bself[\s-]managed\s+super\b", re.IGNORECASE),
        re.compile(r"\bsuperannuation\b", re.IGNORECASE),
        re.compile(r"\bcontribution\s+cap\b", re.IGNORECASE),
    ],
    "fbt": [
        re.compile(r"\bfbt\b", re.IGNORECASE),
        re.compile(r"\bfringe\s+benefits?\b", re.IGNORECASE),
        re.compile(r"\bcar\s+benefits?\b", re.IGNORECASE),
        re.compile(r"\bentertainment\s+benefits?\b", re.IGNORECASE),
    ],
    "trusts": [
        re.compile(r"\btrust\s+distribution\b", re.IGNORECASE),
        re.compile(r"\bfamily\s+trust\b", re.IGNORECASE),
        re.compile(r"\bstreaming\b", re.IGNORECASE),
        re.compile(r"\bs100A\b", re.IGNORECASE),
        re.compile(r"\bsection\s+100A\b", re.IGNORECASE),
    ],
    "payg": [
        re.compile(r"\bpayg\b", re.IGNORECASE),
        re.compile(r"\bpay\s+as\s+you\s+go\b", re.IGNORECASE),
        re.compile(r"\bwithholding\b", re.IGNORECASE),
        re.compile(r"\bsuper\s+guarantee\b", re.IGNORECASE),
    ],
    "international": [
        re.compile(r"\binternational\s+tax\b", re.IGNORECASE),
        re.compile(r"\btransfer\s+pricing\b", re.IGNORECASE),
        re.compile(r"\bthin\s+cap\b", re.IGNORECASE),
        re.compile(r"\bforeign\s+income\b", re.IGNORECASE),
        re.compile(r"\btax\s+treaty\b", re.IGNORECASE),
    ],
    "deductions": [
        re.compile(r"\bwork[\s-]related\s+expense\b", re.IGNORECASE),
        re.compile(r"\binstant\s+asset\b", re.IGNORECASE),
        re.compile(r"\bwrite[\s-]?off\b", re.IGNORECASE),
        re.compile(r"\bdepreciation\b", re.IGNORECASE),
        re.compile(r"\bhome\s+office\b", re.IGNORECASE),
    ],
}


# =============================================================================
# Query Router
# =============================================================================


class QueryRouter:
    """Classifies incoming tax queries and determines retrieval strategy.

    The router applies regex patterns to detect query type, extracts
    section/ruling references, detects tax domains, and returns a
    QueryClassification with the optimal fusion weights and Pinecone
    metadata filters for the hybrid search pipeline.

    This is a pure CPU operation with no I/O -- classification is
    sub-millisecond.
    """

    def classify(self, query: str, domain: str | None = None) -> QueryClassification:
        """Classify a query and determine retrieval parameters.

        Args:
            query: The user's tax question or search text.
            domain: Optional domain slug (e.g., "gst") to scope retrieval.
                If provided, adds topic_tags filter to the Pinecone query.

        Returns:
            QueryClassification with query type, confidence, Pinecone
            filter, fusion weights, extracted refs, and detected domain.
        """
        extracted_refs = self._extract_references(query)
        detected_domain = domain or self._detect_domain(query)

        # Classify in priority order: SECTION_LOOKUP > RULING_LOOKUP >
        # CASE_LAW > PROCEDURAL > SCENARIO > CONCEPTUAL (default)
        classification = self._classify_query_type(query)

        # Apply domain scoping filter if domain is set
        if detected_domain and detected_domain in DOMAIN_TOPIC_TAGS:
            domain_tags = DOMAIN_TOPIC_TAGS[detected_domain]
            domain_filter = {"topic_tags": {"$in": domain_tags}}
            if classification.pinecone_filter is not None:
                classification.pinecone_filter = {
                    "$and": [classification.pinecone_filter, domain_filter]
                }
            else:
                classification.pinecone_filter = domain_filter

        classification.extracted_refs = extracted_refs
        classification.domain_detected = detected_domain

        return classification

    def _classify_query_type(self, query: str) -> QueryClassification:
        """Apply classification rules in priority order.

        Priority (highest first):
            1. SECTION_LOOKUP -- query references a specific legislation section
            2. RULING_LOOKUP  -- query references a specific ruling number
            3. CASE_LAW       -- query mentions courts/cases/tribunals
            4. PROCEDURAL     -- query asks "how to" do something
            5. SCENARIO       -- query describes a client/business scenario
            6. CONCEPTUAL     -- default fallback

        Args:
            query: Raw query text.

        Returns:
            QueryClassification for the matched type.
        """
        # --- SECTION_LOOKUP (highest priority) ---
        section_refs = self._find_section_refs(query)
        if section_refs:
            first_ref = section_refs[0]
            # Confidence based on how specific the reference is
            confidence = min(0.95, 0.7 + 0.1 * len(section_refs))
            pinecone_filter: dict = {
                "$and": [
                    {"section_ref": {"$eq": first_ref}},
                    {"is_superseded": {"$ne": True}},
                ]
            }
            return QueryClassification(
                query_type=QueryType.SECTION_LOOKUP,
                confidence=confidence,
                pinecone_filter=pinecone_filter,
                fusion_weights=(0.2, 0.8),
            )

        # --- RULING_LOOKUP ---
        ruling_refs = self._find_ruling_refs(query)
        if ruling_refs:
            first_ref = ruling_refs[0]
            confidence = min(0.95, 0.75 + 0.1 * len(ruling_refs))
            pinecone_filter = {
                "$and": [
                    {"ruling_number": {"$eq": first_ref}},
                    {"is_superseded": {"$ne": True}},
                ]
            }
            return QueryClassification(
                query_type=QueryType.RULING_LOOKUP,
                confidence=confidence,
                pinecone_filter=pinecone_filter,
                fusion_weights=(0.2, 0.8),
            )

        # --- CASE_LAW ---
        case_matches = _CASE_LAW_PATTERN.findall(query)
        if case_matches:
            confidence = min(0.9, 0.5 + 0.1 * len(case_matches))
            pinecone_filter = {"source_type": {"$eq": "case_law"}}
            return QueryClassification(
                query_type=QueryType.CASE_LAW,
                confidence=confidence,
                pinecone_filter=pinecone_filter,
                fusion_weights=(0.5, 0.5),
            )

        # --- PROCEDURAL ---
        procedural_count = sum(1 for p in _PROCEDURAL_PATTERNS if p.search(query))
        if procedural_count > 0:
            confidence = min(0.9, 0.5 + 0.15 * procedural_count)
            pinecone_filter = {
                "$and": [
                    {"source_type": {"$in": ["ato_guide", "ato_ruling"]}},
                    {"is_superseded": {"$ne": True}},
                ]
            }
            return QueryClassification(
                query_type=QueryType.PROCEDURAL,
                confidence=confidence,
                pinecone_filter=pinecone_filter,
                fusion_weights=(0.5, 0.5),
            )

        # --- SCENARIO ---
        scenario_count = sum(1 for p in _SCENARIO_PATTERNS if p.search(query))
        if scenario_count > 0:
            confidence = min(0.9, 0.5 + 0.15 * scenario_count)
            pinecone_filter = {"is_superseded": {"$ne": True}}
            return QueryClassification(
                query_type=QueryType.SCENARIO,
                confidence=confidence,
                pinecone_filter=pinecone_filter,
                fusion_weights=(0.6, 0.4),
            )

        # --- CONCEPTUAL (default fallback) ---
        return QueryClassification(
            query_type=QueryType.CONCEPTUAL,
            confidence=0.5,
            pinecone_filter={"is_superseded": {"$ne": True}},
            fusion_weights=(0.7, 0.3),
        )

    # -------------------------------------------------------------------------
    # Reference Extraction
    # -------------------------------------------------------------------------

    def _extract_references(self, query: str) -> list[str]:
        """Extract all section and ruling references from a query.

        Uses regex to find references like "s109D", "section 104-10",
        "Div 7A", "TR 2024/1", "GSTR 2000/1", normalises formatting,
        and returns a deduplicated list.

        Args:
            query: Raw query text.

        Returns:
            List of normalised references found in the query.
        """
        refs: list[str] = []

        # Section references
        section_refs = self._find_section_refs(query)
        refs.extend(section_refs)

        # Ruling references
        ruling_refs = self._find_ruling_refs(query)
        refs.extend(ruling_refs)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_refs: list[str] = []
        for ref in refs:
            normalised = ref.strip().lower()
            if normalised not in seen:
                seen.add(normalised)
                unique_refs.append(ref)

        return unique_refs

    def _find_section_refs(self, query: str) -> list[str]:
        """Find and normalise legislation section references.

        Patterns matched:
            - s109D, s104-10, s23AG
            - section 109D, section 104-10
            - Div 7A, Division 104
            - Part 3-1

        Args:
            query: Raw query text.

        Returns:
            List of normalised section reference strings.
        """
        refs: list[str] = []

        for pattern in _SECTION_REF_PATTERNS:
            for match in pattern.finditer(query):
                full_match = match.group(0).strip()
                ref_number = match.group(1).strip()

                # Normalise the reference
                lower_full = full_match.lower()
                if lower_full.startswith("s") and not lower_full.startswith("section"):
                    # "s109D" -> "s109D"
                    refs.append(f"s{ref_number}")
                elif lower_full.startswith("section"):
                    # "section 109D" -> "s109D"
                    refs.append(f"s{ref_number}")
                elif lower_full.startswith("div"):
                    # "Div 7A" or "Division 104" -> "Div 7A" / "Div 104"
                    refs.append(f"Div {ref_number}")
                elif lower_full.startswith("part"):
                    # "Part 3-1" -> "Part 3-1"
                    refs.append(f"Part {ref_number}")

        return refs

    def _find_ruling_refs(self, query: str) -> list[str]:
        """Find and normalise ruling number references.

        Patterns matched:
            - TR 2024/1, TR2024/1
            - GSTR 2000/1, GSTD 2000/1
            - TD 2024/1, PCG 2024/1, CR 2024/1

        The result is normalised to include a space between the prefix
        and the number, with a slash separator (e.g., "TR 2024/1").

        Args:
            query: Raw query text.

        Returns:
            List of normalised ruling reference strings.
        """
        refs: list[str] = []

        for pattern in _RULING_FULL_PATTERNS:
            for match in pattern.finditer(query):
                raw = match.group(1).strip()
                # Normalise: ensure space between prefix and number,
                # and slash between year and sequence
                normalised = re.sub(r"([A-Za-z]+)\s*(\d{4}/?)", r"\1 \2", raw)
                # Ensure slash present
                if "/" not in normalised:
                    # Insert slash before final digit group after year
                    normalised = re.sub(r"(\d{4})(\d+)", r"\1/\2", normalised)
                # Uppercase prefix
                parts = normalised.split(" ", 1)
                if len(parts) == 2:
                    normalised = f"{parts[0].upper()} {parts[1]}"
                refs.append(normalised)

        return refs

    # -------------------------------------------------------------------------
    # Domain Detection
    # -------------------------------------------------------------------------

    def _detect_domain(self, query: str) -> str | None:
        """Detect the tax domain from query keywords.

        Performs simple keyword matching against domain topic tags and
        common aliases. Returns the domain slug with the highest match
        count, or None if no confident match is found.

        Args:
            query: Raw query text.

        Returns:
            Domain slug string (e.g., "gst", "cgt") or None.
        """
        domain_scores: dict[str, int] = {}

        # Check compiled topic tag patterns
        for slug, patterns in _DOMAIN_PATTERNS.items():
            score = sum(1 for p in patterns if p.search(query))
            if score > 0:
                domain_scores[slug] = domain_scores.get(slug, 0) + score

        # Check alias patterns for broader coverage
        for slug, patterns in _DOMAIN_ALIAS_PATTERNS.items():
            score = sum(1 for p in patterns if p.search(query))
            if score > 0:
                domain_scores[slug] = domain_scores.get(slug, 0) + score

        if not domain_scores:
            return None

        # Return the domain with the highest score
        best_domain = max(domain_scores, key=lambda k: domain_scores[k])
        return best_domain
