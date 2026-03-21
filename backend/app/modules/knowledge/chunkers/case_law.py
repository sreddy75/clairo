"""Structure-aware chunker for Australian case law.

Splits court decisions into semantic sections (headnote, reasoning,
orders) and produces structured chunks preserving court and citation
metadata.  Handles varying case formats defensively -- if the expected
structure cannot be detected, the chunker falls back to paragraph
boundary splitting.

Registered as the ``"case_law"`` chunker in the chunker registry.
"""

from __future__ import annotations

import logging
import re

from app.modules.knowledge.chunkers import register_chunker
from app.modules.knowledge.chunkers.base import (
    BaseStructuredChunker,
    ChunkResult,
    extract_ruling_references,
    extract_section_references,
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Section detection patterns
# --------------------------------------------------------------------------

# Pattern for the headnote / catchwords section.
# Variations: "HEADNOTE", "Catchwords", "CATCHWORDS", "Summary"
_HEADNOTE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*(?:HEAD\s*NOTE|HEADNOTE|Headnote)", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*(?:CATCHWORDS|Catchwords)", re.IGNORECASE | re.MULTILINE),
    re.compile(
        r"^\s*(?:SUMMARY|Summary)(?:\s+OF\s+(?:DECISION|JUDGMENT))?", re.IGNORECASE | re.MULTILINE
    ),
]

# Pattern for the reasoning / judgment section.
# Variations: "REASONS FOR JUDGMENT", "JUDGMENT", "THE COURT:", "REASONS"
_REASONING_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*REASONS?\s+FOR\s+(?:JUDGMENT|DECISION)", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*(?:THE\s+COURT|JUDGMENT)\s*:", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*REASONS?\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*CONSIDERATION\s*$", re.IGNORECASE | re.MULTILINE),
]

# Pattern for the orders section.
# Variations: "ORDERS", "ORDER", "THE COURT ORDERS", "THE ORDERS OF THE COURT ARE"
_ORDERS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*(?:THE\s+)?(?:COURT\s+)?ORDERS?\s*:?\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(
        r"^\s*(?:THE\s+)?ORDERS?\s+(?:OF\s+THE\s+(?:COURT|TRIBUNAL))", re.IGNORECASE | re.MULTILINE
    ),
    re.compile(r"^\s*(?:I\s+ORDER|IT\s+IS\s+ORDERED)\s+THAT", re.IGNORECASE | re.MULTILINE),
]

# Pattern for numbered paragraphs (e.g., "1.", "2.", "[1]", "[2]").
_NUMBERED_PARA_PATTERN = re.compile(
    r"^(?:\[(\d+)\]|(\d+)\.)\s",
    re.MULTILINE,
)


class CaseLawChunker(BaseStructuredChunker):
    """Chunker for Australian court decisions.

    Splits case text into headnote, reasoning, and orders sections,
    then produces chunks preserving court and citation metadata on
    every chunk.

    Expected metadata keys (all optional):

    - ``case_citation``: e.g. ``"[2010] HCA 10"``
    - ``court``: e.g. ``"HCA"``
    - ``topic_tags``: list of tags
    """

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def chunk(
        self,
        raw_content: str,
        metadata: dict | None = None,
    ) -> list[ChunkResult]:
        """Chunk case text into structured pieces.

        Args:
            raw_content: Full text of the court decision.
            metadata: Case metadata (citation, court, topic_tags).

        Returns:
            List of ChunkResult objects.
        """
        if not raw_content or not raw_content.strip():
            return []

        metadata = metadata or {}
        case_citation: str = metadata.get("case_citation", "Unknown Case")
        court: str | None = metadata.get("court")
        topic_tags: list[str] = list(metadata.get("topic_tags", []))

        # Parse the case into sections.
        sections = self._parse_case_sections(raw_content)

        chunks: list[ChunkResult] = []

        # Headnote: single high-priority chunk.
        if sections.get("headnote"):
            chunks.append(
                self._make_chunk(
                    text=sections["headnote"],
                    content_type="headnote",
                    case_citation=case_citation,
                    court=court,
                    topic_tags=topic_tags,
                    section_label="Headnote",
                    metadata=metadata,
                )
            )

        # Reasoning: split by numbered paragraphs or boundary.
        if sections.get("reasoning"):
            reasoning_chunks = self._chunk_reasoning(
                sections["reasoning"],
                case_citation=case_citation,
                court=court,
                topic_tags=topic_tags,
                metadata=metadata,
            )
            chunks.extend(reasoning_chunks)

        # Orders: single chunk.
        if sections.get("orders"):
            chunks.append(
                self._make_chunk(
                    text=sections["orders"],
                    content_type="orders",
                    case_citation=case_citation,
                    court=court,
                    topic_tags=topic_tags,
                    section_label="Orders",
                    metadata=metadata,
                )
            )

        # Fallback: if no sections detected, treat entire content as reasoning.
        if not chunks:
            logger.warning(
                "Could not parse case sections for %s; falling back to paragraph splitting.",
                case_citation,
            )
            parts = self._split_at_boundary(raw_content.strip())
            for part in parts:
                chunks.append(
                    self._make_chunk(
                        text=part,
                        content_type="reasoning",
                        case_citation=case_citation,
                        court=court,
                        topic_tags=topic_tags,
                        section_label="Reasoning",
                        metadata=metadata,
                    )
                )

        return chunks

    # ------------------------------------------------------------------
    # Section parsing
    # ------------------------------------------------------------------

    def _parse_case_sections(self, text: str) -> dict[str, str]:
        """Split case text into headnote, reasoning, and orders sections.

        Uses regex patterns to locate section boundaries.  Handles
        varying formats defensively -- missing sections are simply
        omitted from the result.

        Args:
            text: Full case text.

        Returns:
            Dict mapping section name to body text.  Possible keys:
            ``"headnote"``, ``"reasoning"``, ``"orders"``.
        """
        # Find all section boundaries.
        boundaries: list[tuple[int, str]] = []

        for pattern in _HEADNOTE_PATTERNS:
            match = pattern.search(text)
            if match:
                boundaries.append((match.start(), "headnote"))
                break

        for pattern in _REASONING_PATTERNS:
            match = pattern.search(text)
            if match:
                boundaries.append((match.start(), "reasoning"))
                break

        for pattern in _ORDERS_PATTERNS:
            # Orders pattern should match near the end of the document.
            # Search from the last third of the text to avoid false matches.
            search_start = len(text) // 2
            match = pattern.search(text, pos=search_start)
            if match:
                boundaries.append((match.start(), "orders"))
                break
            # Fallback: search from the beginning
            match = pattern.search(text)
            if match:
                boundaries.append((match.start(), "orders"))
                break

        if not boundaries:
            return {}

        # Sort by position
        boundaries.sort(key=lambda x: x[0])

        # Extract section bodies
        sections: dict[str, str] = {}

        for i, (start_pos, section_name) in enumerate(boundaries):
            # Skip past the heading line
            heading_end = text.find("\n", start_pos)
            if heading_end == -1:
                heading_end = start_pos
            content_start = heading_end + 1

            # Content ends at the next boundary
            content_end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)

            body = text[content_start:content_end].strip()
            if body:
                sections[section_name] = body

        return sections

    # ------------------------------------------------------------------
    # Reasoning chunking
    # ------------------------------------------------------------------

    def _chunk_reasoning(
        self,
        text: str,
        case_citation: str,
        court: str | None,
        topic_tags: list[str],
        metadata: dict,
    ) -> list[ChunkResult]:
        """Chunk the reasoning section by numbered paragraphs.

        Numbered paragraphs (e.g. [1], [2], or 1., 2.) are grouped
        to respect token limits.  Very long paragraphs are further
        split using ``_split_at_boundary``.

        Args:
            text: Reasoning section body.
            case_citation: Case citation for metadata.
            court: Court abbreviation.
            topic_tags: Topic tags.
            metadata: Full metadata dict.

        Returns:
            List of ChunkResult objects.
        """
        # Find numbered paragraph positions
        para_positions: list[int] = [m.start() for m in _NUMBERED_PARA_PATTERN.finditer(text)]

        if not para_positions:
            # No numbered paragraphs -- fall back to boundary splitting
            parts = self._split_at_boundary(text)
            return [
                self._make_chunk(
                    text=part,
                    content_type="reasoning",
                    case_citation=case_citation,
                    court=court,
                    topic_tags=topic_tags,
                    section_label="Reasoning",
                    metadata=metadata,
                )
                for part in parts
            ]

        # Extract raw paragraph groups
        raw_parts: list[str] = []

        # Include any preamble before first numbered paragraph
        preamble = text[: para_positions[0]].strip()
        if preamble:
            raw_parts.append(preamble)

        for i, start in enumerate(para_positions):
            end = para_positions[i + 1] if i + 1 < len(para_positions) else len(text)
            part = text[start:end].strip()
            if part:
                raw_parts.append(part)

        if not raw_parts:
            parts = self._split_at_boundary(text)
            return [
                self._make_chunk(
                    text=part,
                    content_type="reasoning",
                    case_citation=case_citation,
                    court=court,
                    topic_tags=topic_tags,
                    section_label="Reasoning",
                    metadata=metadata,
                )
                for part in parts
            ]

        # Group small paragraphs and split large ones
        max_tokens = 512
        min_tokens = 64
        chunks: list[str] = []
        current = ""

        for part in raw_parts:
            token_est = len(part) // 4
            if token_est > max_tokens:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.extend(
                    self._split_at_boundary(part, max_tokens=max_tokens, min_tokens=min_tokens)
                )
            else:
                combined = f"{current}\n\n{part}".strip() if current else part
                combined_tokens = len(combined) // 4
                if combined_tokens > max_tokens and current:
                    chunks.append(current)
                    current = part
                else:
                    current = combined

        if current:
            chunks.append(current)

        return [
            self._make_chunk(
                text=chunk_text,
                content_type="reasoning",
                case_citation=case_citation,
                court=court,
                topic_tags=topic_tags,
                section_label="Reasoning",
                metadata=metadata,
            )
            for chunk_text in chunks
        ]

    # ------------------------------------------------------------------
    # Chunk construction helper
    # ------------------------------------------------------------------

    @staticmethod
    def _make_chunk(
        text: str,
        content_type: str,
        case_citation: str,
        court: str | None,
        topic_tags: list[str],
        section_label: str,
        metadata: dict,
    ) -> ChunkResult:
        """Build a ChunkResult with case law metadata.

        Every chunk is prefixed with the case citation and section label
        so that the chunk is self-describing.

        Args:
            text: Chunk body text.
            content_type: One of "headnote", "reasoning", "orders".
            case_citation: Case citation string.
            court: Court abbreviation (HCA, FCA, etc.).
            topic_tags: Topic tags to assign.
            section_label: Human-readable section name for the prefix.
            metadata: Original metadata dict.

        Returns:
            ChunkResult instance.
        """
        # Build prefix
        prefixed_text = f"{case_citation} - {section_label}\n\n{text}"

        # Extract cross-references to legislation and rulings
        section_refs = extract_section_references(text)
        ruling_refs = extract_ruling_references(text)
        cross_refs = list(set(section_refs + ruling_refs))

        # Include court and citation in chunk metadata
        chunk_metadata = dict(metadata)
        chunk_metadata["court"] = court
        chunk_metadata["case_citation"] = case_citation

        return ChunkResult(
            text=prefixed_text,
            content_type=content_type,
            section_ref=case_citation,
            cross_references=cross_refs,
            defined_terms_used=[],  # Populated downstream
            topic_tags=list(topic_tags),
            metadata=chunk_metadata,
        )


# Register this chunker for the "case_law" content type
register_chunker("case_law", CaseLawChunker)
