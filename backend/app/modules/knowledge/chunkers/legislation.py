"""Legislation chunker for Australian tax legislation sections.

Produces structured chunks from raw legislation section text,
suitable for RAG retrieval. Handles operative provisions, definitions,
and examples with cross-reference and defined-term extraction.
"""

from __future__ import annotations

import re

from app.modules.knowledge.chunkers import register_chunker
from app.modules.knowledge.chunkers.base import (
    BaseStructuredChunker,
    ChunkResult,
    extract_ruling_references,
    extract_section_references,
)

# Common defined terms in Australian tax law used for matching against chunk text.
# This list covers the most frequently referenced terms across income tax, GST,
# superannuation, FBT, and general tax administration legislation.
COMMON_DEFINED_TERMS: list[str] = [
    "CGT asset",
    "CGT event",
    "capital gain",
    "capital loss",
    "net capital gain",
    "capital proceeds",
    "cost base",
    "reduced cost base",
    "assessable income",
    "taxable income",
    "ordinary income",
    "statutory income",
    "exempt income",
    "non-assessable non-exempt income",
    "deductible",
    "general deduction",
    "GST",
    "goods and services tax",
    "input tax credit",
    "taxable supply",
    "GST-free supply",
    "input taxed supply",
    "entity",
    "associate",
    "connected entity",
    "small business entity",
    "trust",
    "trustee",
    "beneficiary",
    "partnership",
    "company",
    "dividend",
    "frankable distribution",
    "franking credit",
    "fringe benefit",
    "reportable fringe benefit",
    "superannuation fund",
    "complying superannuation fund",
    "financial year",
    "income year",
    "base year",
    "private company",
    "shareholder",
    "distributable surplus",
    "arm's length",
    "market value",
    "fair market value",
    "withholding tax",
    "resident",
    "non-resident",
    "permanent establishment",
    "depreciating asset",
    "effective life",
    "instant asset write-off",
    "small business CGT concession",
    "aggregated turnover",
    "Commissioner",
    "tax offset",
]

# Pre-compiled patterns for matching defined terms (case-insensitive).
# Each entry is (term, compiled regex).
_DEFINED_TERM_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (term, re.compile(re.escape(term), re.IGNORECASE)) for term in COMMON_DEFINED_TERMS
]

# Patterns that indicate a definition section.
_DEFINITION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bmeans\b", re.IGNORECASE),
    re.compile(r"\bhas the meaning\b", re.IGNORECASE),
    re.compile(r"\bis defined\b", re.IGNORECASE),
    re.compile(r"\bhas the same meaning\b", re.IGNORECASE),
]

# Patterns that indicate an example block.
_EXAMPLE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^Example\b", re.IGNORECASE),
    re.compile(r"^For example\b", re.IGNORECASE),
]


class LegislationChunker(BaseStructuredChunker):
    """Chunker for Australian legislation sections.

    Produces chunks at section level (256-512 tokens), splitting at
    subsection boundaries for long sections. Each chunk is prefixed
    with the section number and heading, classified by content type,
    and enriched with cross-references and defined-term annotations.
    """

    def chunk(
        self,
        raw_content: str,
        metadata: dict | None = None,
    ) -> list[ChunkResult]:
        """Chunk legislation section text into structured pieces.

        Args:
            raw_content: Raw text of the legislation section.
            metadata: Expected keys: section_ref, act_short_name, part,
                      division, subdivision, topic_tags. All optional
                      but recommended.

        Returns:
            List of ChunkResult objects, one per chunk.
        """
        if not raw_content or not raw_content.strip():
            return []

        metadata = metadata or {}

        section_ref = metadata.get("section_ref")
        act_short_name = metadata.get("act_short_name", "")
        heading = metadata.get("heading", "")
        topic_tags = list(metadata.get("topic_tags", []))

        # Build section prefix for each chunk, e.g.:
        # "Section 109D - Amounts treated as dividends"
        prefix = self._build_prefix(section_ref, heading, act_short_name)

        # Determine whether the section fits in a single chunk.
        token_estimate = len(raw_content.strip()) // 4
        if token_estimate <= 512:
            # Single chunk for the entire section.
            text = f"{prefix}\n\n{raw_content.strip()}" if prefix else raw_content.strip()
            content_type = self._classify_content_type(raw_content.strip(), metadata)
            cross_refs = extract_section_references(raw_content) + extract_ruling_references(
                raw_content
            )
            defined_terms = self._find_defined_terms(raw_content)

            return [
                ChunkResult(
                    text=text,
                    content_type=content_type,
                    section_ref=section_ref,
                    cross_references=cross_refs,
                    defined_terms_used=defined_terms,
                    topic_tags=topic_tags,
                    metadata=metadata,
                ),
            ]

        # Section is too long -- split at subsection boundaries.
        segments = self._split_at_boundary(raw_content.strip(), max_tokens=512, min_tokens=64)

        results: list[ChunkResult] = []
        for segment in segments:
            text = f"{prefix}\n\n{segment}" if prefix else segment
            content_type = self._classify_content_type(segment, metadata)
            cross_refs = extract_section_references(segment) + extract_ruling_references(segment)
            defined_terms = self._find_defined_terms(segment)

            results.append(
                ChunkResult(
                    text=text,
                    content_type=content_type,
                    section_ref=section_ref,
                    cross_references=cross_refs,
                    defined_terms_used=defined_terms,
                    topic_tags=topic_tags,
                    metadata=metadata,
                ),
            )

        return results

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    @staticmethod
    def _build_prefix(
        section_ref: str | None,
        heading: str,
        act_short_name: str,
    ) -> str:
        """Build a human-readable prefix such as 'Section 109D - Amounts treated as dividends'.

        Returns empty string if insufficient information is available.
        """
        parts: list[str] = []
        if section_ref:
            parts.append(f"Section {section_ref}")
        if heading:
            parts.append(heading)

        prefix = " - ".join(parts) if parts else ""

        if prefix and act_short_name:
            prefix = f"{prefix} ({act_short_name})"

        return prefix

    @staticmethod
    def _classify_content_type(text: str, metadata: dict) -> str:
        """Classify a text segment as definition, example, or operative provision.

        Args:
            text: The chunk text to classify.
            metadata: Section metadata; 'division' key checked for
                      definitions divisions.

        Returns:
            One of "definition", "example", or "operative_provision".
        """
        # Check for example patterns first (higher specificity).
        stripped = text.strip()
        for pattern in _EXAMPLE_PATTERNS:
            if pattern.search(stripped[:50]):  # Check only the start of the text.
                return "example"

        # Check for definition patterns in the first paragraph.
        first_para = stripped.split("\n\n")[0] if "\n\n" in stripped else stripped
        division = str(metadata.get("division", "")).lower()
        is_definitions_division = "definition" in division

        if is_definitions_division:
            for pattern in _DEFINITION_PATTERNS:
                if pattern.search(first_para):
                    return "definition"

        # Default to operative provision.
        return "operative_provision"

    @staticmethod
    def _find_defined_terms(text: str) -> list[str]:
        """Find COMMON_DEFINED_TERMS that appear in the text.

        Performs case-insensitive matching.

        Returns:
            Sorted, deduplicated list of matched term names
            (in their canonical capitalisation from the constant).
        """
        found: list[str] = []
        for term, pattern in _DEFINED_TERM_PATTERNS:
            if pattern.search(text):
                found.append(term)
        return sorted(set(found))


# Register the chunker so it can be looked up by content_type.
register_chunker("legislation", LegislationChunker)
