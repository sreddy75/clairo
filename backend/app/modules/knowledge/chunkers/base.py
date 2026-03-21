"""Base class for structure-aware chunkers."""

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ChunkResult:
    """Result of chunking a piece of content."""

    text: str
    content_type: str  # "operative_provision", "definition", "example", "ruling", "explanation", "headnote", "reasoning", "orders"
    section_ref: str | None = None  # "s109D ITAA 1936", "TR 2024/1 para 15"
    cross_references: list[str] = field(default_factory=list)  # ["s104-5", "Div 115"]
    defined_terms_used: list[str] = field(default_factory=list)  # ["CGT asset", "capital proceed"]
    topic_tags: list[str] = field(default_factory=list)  # ["CGT", "disposal"]
    metadata: dict = field(default_factory=dict)  # Additional metadata

    @property
    def content_hash(self) -> str:
        """SHA-256 hash of normalised text."""
        normalized = " ".join(self.text.split())
        return hashlib.sha256(normalized.encode()).hexdigest()

    @property
    def token_estimate(self) -> int:
        """Rough token count estimate."""
        return len(self.text) // 4


# Common regex patterns for Australian legal references
SECTION_REF_PATTERN = re.compile(
    r"""
    (?:
        [Ss](?:ection|ec\.?|)\s*(\d+[\w\-]*) |   # section 109D, s109D, sec 109D
        [Dd]iv(?:ision)?\s*(\d+[\w\-]*) |          # Division 7A, Div 7A
        [Pp]art\s*(\d+[\w\-]*)                      # Part 3-1
    )
    """,
    re.VERBOSE,
)

RULING_REF_PATTERN = re.compile(
    r"""
    (?:
        (T[RD]|GSTR?D?|PCG|CR|PR|PS\s*LA|SGR|SRB)\s*(\d{4})/(\d+) |  # TR 2024/1
        (IT|TD)\s*(\d+)                                                  # IT 2167
    )
    """,
    re.VERBOSE,
)


def extract_section_references(text: str) -> list[str]:
    """Extract legislation section references from text."""
    refs = []
    for match in SECTION_REF_PATTERN.finditer(text):
        ref = match.group(0).strip()
        refs.append(ref)
    return list(set(refs))


def extract_ruling_references(text: str) -> list[str]:
    """Extract ATO ruling references from text."""
    refs = []
    for match in RULING_REF_PATTERN.finditer(text):
        ref = match.group(0).strip()
        refs.append(ref)
    return list(set(refs))


class BaseStructuredChunker(ABC):
    """Abstract base class for structure-aware chunkers.

    Subclasses implement content-type-specific chunking that preserves
    the natural structure of legal documents.
    """

    @abstractmethod
    def chunk(self, raw_content: str, metadata: dict | None = None) -> list[ChunkResult]:
        """Chunk raw content into structured pieces.

        Args:
            raw_content: The raw text or HTML content to chunk.
            metadata: Additional metadata from the scraper (e.g., act_id, ruling_number).

        Returns:
            List of ChunkResult objects.
        """
        ...

    def _split_at_boundary(
        self,
        text: str,
        max_tokens: int = 512,
        min_tokens: int = 64,
    ) -> list[str]:
        """Split text at paragraph boundaries, respecting token limits.

        Never splits mid-paragraph.
        """
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: list[str] = []
        current = ""

        for para in paragraphs:
            combined = f"{current}\n\n{para}".strip() if current else para
            if len(combined) // 4 > max_tokens and current:
                chunks.append(current)
                current = para
            else:
                current = combined

        if current:
            chunks.append(current)

        return chunks
