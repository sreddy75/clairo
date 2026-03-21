"""Structure-aware chunker for ATO rulings.

Parses ATO ruling text (from the ATO Legal Database) into structured chunks
based on the natural section boundaries: Ruling, Explanation, Examples,
Date of Effect, and Appendix.

Rulings have known structural patterns but inconsistent formatting across
different ruling types (TR, GSTR, TD, PCG, etc.). This chunker handles
the common variations defensively with fallback to paragraph splitting.
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

# Section heading patterns (case-insensitive).
# Order matters: more specific patterns first to avoid false matches.
_SECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ruling",
        re.compile(
            r"^\s*(?:\d+\.\s+)?"
            r"(?:Ruling|What this Ruling is about|Ruling with [Ee]xplanation)",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        "explanation",
        re.compile(
            r"^\s*(?:\d+\.\s+)?"
            r"(?:Explanation|Detailed [Cc]ontents [Ll]ist)",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        "example",
        re.compile(
            r"^\s*(?:\d+\.\s+)?(?:Examples?(?:\s+\d+)?)\s*$",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        "date_of_effect",
        re.compile(
            r"^\s*(?:\d+\.\s+)?Date\s+of\s+[Ee]ffect",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        "appendix",
        re.compile(
            r"^\s*(?:\d+\.\s+)?Appendix",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
]

# Pattern for numbered paragraphs in explanation sections (e.g., "15.", "16.")
_NUMBERED_PARA_PATTERN = re.compile(r"^(\d+)\.\s", re.MULTILINE)

# Pattern for numbered examples (e.g., "Example 1", "Example 2")
_EXAMPLE_SPLIT_PATTERN = re.compile(
    r"(?:^|\n)\s*Example\s+(\d+)",
    re.IGNORECASE,
)

# Mapping from ruling type prefix to default topic tags
_PREFIX_TOPIC_MAP: dict[str, list[str]] = {
    "TR": ["income_tax"],
    "TXR": ["income_tax"],
    "TD": ["income_tax"],
    "TXD": ["income_tax"],
    "GSTR": ["gst"],
    "GST": ["gst"],
    "GSTD": ["gst"],
    "CR": ["class_ruling"],
    "CLR": ["class_ruling"],
    "PCG": ["practical_compliance"],
    "TPA": ["practical_compliance"],
    "SRB": ["superannuation", "smsf"],
    "SGR": ["superannuation", "smsf"],
    "PS LA": ["ato_practice"],
    "SAV": ["ato_practice"],
    "AID": ["interpretive_decision"],
}


def _infer_topic_tags_from_prefix(ruling_type_prefix: str | None) -> list[str]:
    """Derive topic tags from the ruling type prefix.

    Args:
        ruling_type_prefix: Prefix like 'TR', 'GSTR', 'PCG', etc.

    Returns:
        List of topic tag strings, empty if prefix is unrecognised.
    """
    if not ruling_type_prefix:
        return []
    # Normalise: strip whitespace, uppercase
    prefix = ruling_type_prefix.strip().upper()
    # Try exact match first, then with spaces removed
    if prefix in _PREFIX_TOPIC_MAP:
        return list(_PREFIX_TOPIC_MAP[prefix])
    normalised = prefix.replace(" ", "")
    for key, tags in _PREFIX_TOPIC_MAP.items():
        if key.replace(" ", "") == normalised:
            return list(tags)
    return []


class RulingChunker(BaseStructuredChunker):
    """Chunker for ATO rulings (TR, GSTR, TD, PCG, etc.).

    Parses ruling text into structural sections and produces one or more
    ``ChunkResult`` per section, preserving the ruling number as a prefix
    and extracting cross-references and topic tags.
    """

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def chunk(
        self,
        raw_content: str,
        metadata: dict | None = None,
    ) -> list[ChunkResult]:
        """Chunk an ATO ruling into structured pieces.

        Args:
            raw_content: Full ruling text (plain text, not HTML).
            metadata: Expected keys: ``ruling_number``, ``ruling_type_prefix``,
                ``topic_tags`` (optional).

        Returns:
            List of ``ChunkResult`` objects.
        """
        metadata = metadata or {}
        ruling_number: str = metadata.get("ruling_number", "Unknown Ruling")
        ruling_type_prefix: str | None = metadata.get("ruling_type_prefix")
        topic_tags: list[str] = metadata.get("topic_tags") or _infer_topic_tags_from_prefix(
            ruling_type_prefix,
        )

        sections = self._parse_sections(raw_content)

        if not sections:
            # Fallback: treat entire content as a single ruling chunk
            logger.warning(
                "Could not parse sections from ruling %s; falling back to single chunk.",
                ruling_number,
            )
            return [
                self._make_chunk(
                    text=raw_content,
                    content_type="ruling",
                    ruling_number=ruling_number,
                    topic_tags=topic_tags,
                    metadata=metadata,
                ),
            ]

        chunks: list[ChunkResult] = []

        for section_name, section_text in sections.items():
            if not section_text.strip():
                continue

            section_chunks = self._chunk_section(
                section_name=section_name,
                section_text=section_text,
                ruling_number=ruling_number,
                topic_tags=topic_tags,
                metadata=metadata,
            )
            chunks.extend(section_chunks)

        return chunks

    # ------------------------------------------------------------------
    # Section parsing
    # ------------------------------------------------------------------

    def _parse_sections(self, text: str) -> dict[str, str]:
        """Split ruling text into named sections.

        Uses regex matching against known ATO ruling headings. Handles
        variations in case, numbering, and formatting.

        Args:
            text: Full ruling text.

        Returns:
            Ordered dict mapping section name to content text.
        """
        # Find all heading matches with their positions
        matches: list[tuple[int, str]] = []
        for section_name, pattern in _SECTION_PATTERNS:
            for m in pattern.finditer(text):
                matches.append((m.start(), section_name))

        if not matches:
            return {}

        # Sort by position in text
        matches.sort(key=lambda x: x[0])

        # Deduplicate: if the same section name appears multiple times,
        # only keep the first occurrence (unless it is "example" which may
        # legitimately repeat as sub-headings inside the examples section).
        seen: set[str] = set()
        deduped: list[tuple[int, str]] = []
        for pos, name in matches:
            if name == "example" and "example" in seen:
                # Skip duplicate example headings - they will be captured
                # inside the first examples section body.
                continue
            if name not in seen:
                seen.add(name)
                deduped.append((pos, name))
        matches = deduped

        # Extract section bodies
        sections: dict[str, str] = {}
        for i, (start_pos, section_name) in enumerate(matches):
            # Content starts after the heading line
            heading_end = text.find("\n", start_pos)
            if heading_end == -1:
                heading_end = start_pos
            content_start = heading_end + 1

            # Content ends at the start of the next section
            content_end = matches[i + 1][0] if i + 1 < len(matches) else len(text)

            body = text[content_start:content_end].strip()
            sections[section_name] = body

        return sections

    # ------------------------------------------------------------------
    # Per-section chunking strategies
    # ------------------------------------------------------------------

    def _chunk_section(
        self,
        section_name: str,
        section_text: str,
        ruling_number: str,
        topic_tags: list[str],
        metadata: dict,
    ) -> list[ChunkResult]:
        """Dispatch to the appropriate chunking strategy for a section.

        Args:
            section_name: One of 'ruling', 'explanation', 'example',
                'date_of_effect', 'appendix'.
            section_text: Body text of that section.
            ruling_number: E.g. "TR 2024/1".
            topic_tags: Tags to attach to every chunk.
            metadata: Original metadata dict.

        Returns:
            List of ``ChunkResult`` for this section.
        """
        # Map section name to content_type and splitting strategy
        if section_name == "ruling":
            return [
                self._make_chunk(
                    text=section_text,
                    content_type="ruling",
                    ruling_number=ruling_number,
                    topic_tags=topic_tags,
                    metadata=metadata,
                    section_label="Ruling",
                ),
            ]

        if section_name == "explanation":
            parts = self._split_explanation(section_text)
            return [
                self._make_chunk(
                    text=part,
                    content_type="explanation",
                    ruling_number=ruling_number,
                    topic_tags=topic_tags,
                    metadata=metadata,
                    section_label="Explanation",
                )
                for part in parts
            ]

        if section_name == "example":
            parts = self._split_examples(section_text)
            return [
                self._make_chunk(
                    text=part,
                    content_type="example",
                    ruling_number=ruling_number,
                    topic_tags=topic_tags,
                    metadata=metadata,
                    section_label="Example",
                )
                for part in parts
            ]

        if section_name == "date_of_effect":
            return [
                self._make_chunk(
                    text=section_text,
                    content_type="date_of_effect",
                    ruling_number=ruling_number,
                    topic_tags=topic_tags,
                    metadata=metadata,
                    section_label="Date of Effect",
                ),
            ]

        if section_name == "appendix":
            parts = self._split_at_boundary(section_text)
            return [
                self._make_chunk(
                    text=part,
                    content_type="appendix",
                    ruling_number=ruling_number,
                    topic_tags=topic_tags,
                    metadata=metadata,
                    section_label="Appendix",
                )
                for part in parts
            ]

        # Unknown section - treat as generic paragraph split
        logger.debug("Unknown section '%s' in ruling %s", section_name, ruling_number)
        parts = self._split_at_boundary(section_text)
        return [
            self._make_chunk(
                text=part,
                content_type="ruling",
                ruling_number=ruling_number,
                topic_tags=topic_tags,
                metadata=metadata,
                section_label=section_name.replace("_", " ").title(),
            )
            for part in parts
        ]

    # ------------------------------------------------------------------
    # Explanation splitting
    # ------------------------------------------------------------------

    def _split_explanation(self, text: str) -> list[str]:
        """Split explanation text at numbered paragraph boundaries.

        Paragraphs beginning with ``15.``, ``16.`` etc. each become one
        chunk.  Very short consecutive paragraphs (< 64 tokens) are
        grouped together.  Very long paragraphs (> 512 tokens) are
        further split using ``_split_at_boundary``.

        Args:
            text: Explanation section body.

        Returns:
            List of text chunks.
        """
        # Find positions of all numbered paragraphs
        para_positions: list[int] = [m.start() for m in _NUMBERED_PARA_PATTERN.finditer(text)]

        if not para_positions:
            # No numbered paragraphs - fall back to boundary split
            return self._split_at_boundary(text)

        # Extract raw paragraph groups
        raw_parts: list[str] = []
        for i, start in enumerate(para_positions):
            end = para_positions[i + 1] if i + 1 < len(para_positions) else len(text)
            part = text[start:end].strip()
            if part:
                raw_parts.append(part)

        # Include any preamble text before the first numbered paragraph
        preamble = text[: para_positions[0]].strip()
        if preamble:
            raw_parts.insert(0, preamble)

        if not raw_parts:
            return self._split_at_boundary(text)

        # Group short paragraphs and split long ones
        min_tokens = 64
        max_tokens = 512
        chunks: list[str] = []
        current = ""

        for part in raw_parts:
            token_est = len(part) // 4
            if token_est > max_tokens:
                # Flush current buffer first
                if current:
                    chunks.append(current)
                    current = ""
                # Split this large paragraph using boundary splitter
                chunks.extend(
                    self._split_at_boundary(part, max_tokens=max_tokens, min_tokens=min_tokens)
                )
            else:
                combined = f"{current}\n\n{part}".strip() if current else part
                combined_tokens = len(combined) // 4
                if combined_tokens > max_tokens and current:
                    # Adding this part would exceed max - flush current
                    chunks.append(current)
                    current = part
                elif len(current) // 4 >= min_tokens and token_est >= min_tokens:
                    # Both parts are individually large enough - keep separate
                    chunks.append(current)
                    current = part
                else:
                    # Group short paragraphs together
                    current = combined

        if current:
            chunks.append(current)

        return chunks

    # ------------------------------------------------------------------
    # Example splitting
    # ------------------------------------------------------------------

    def _split_examples(self, text: str) -> list[str]:
        """Split examples section into individual example chunks.

        Handles both numbered examples (``Example 1``, ``Example 2``) and
        a single unnumbered example.

        Args:
            text: Examples section body.

        Returns:
            List of text chunks, one per example.
        """
        split_positions = list(_EXAMPLE_SPLIT_PATTERN.finditer(text))

        if not split_positions:
            # Single example or no recognisable example headings
            stripped = text.strip()
            if stripped:
                return [stripped]
            return []

        parts: list[str] = []

        # Any preamble text before the first "Example N" heading
        preamble = text[: split_positions[0].start()].strip()
        if preamble:
            parts.append(preamble)

        for i, match in enumerate(split_positions):
            start = match.start()
            end = split_positions[i + 1].start() if i + 1 < len(split_positions) else len(text)
            part = text[start:end].strip()
            if part:
                parts.append(part)

        return parts if parts else [text.strip()]

    # ------------------------------------------------------------------
    # Chunk construction helper
    # ------------------------------------------------------------------

    def _make_chunk(
        self,
        text: str,
        content_type: str,
        ruling_number: str,
        topic_tags: list[str],
        metadata: dict,
        section_label: str | None = None,
    ) -> ChunkResult:
        """Build a ``ChunkResult`` with standard ruling enrichments.

        Every chunk is prefixed with the ruling number and section label
        so that the chunk is self-describing even outside the original
        document context.

        Args:
            text: Chunk body text.
            content_type: One of 'ruling', 'explanation', 'example',
                'date_of_effect', 'appendix'.
            ruling_number: E.g. "TR 2024/1".
            topic_tags: Tags to assign.
            metadata: Original metadata dict for pass-through.
            section_label: Human-readable section name for the prefix.

        Returns:
            ``ChunkResult`` instance.
        """
        # Build prefix
        label = section_label or content_type.replace("_", " ").title()
        prefixed_text = f"{ruling_number} - {label}\n\n{text}"

        # Extract cross-references
        section_refs = extract_section_references(text)
        ruling_refs = extract_ruling_references(text)
        cross_refs = list(set(section_refs + ruling_refs))

        return ChunkResult(
            text=prefixed_text,
            content_type=content_type,
            section_ref=ruling_number,
            cross_references=cross_refs,
            defined_terms_used=[],  # Populated downstream by definitions matcher
            topic_tags=list(topic_tags),
            metadata=metadata,
        )


# Register this chunker for the "ruling" content type
register_chunker("ruling", RulingChunker)
