"""Semantic text chunking for knowledge base content.

This module provides intelligent text chunking that:
- Respects semantic boundaries (paragraphs, sections, sentences)
- Maintains context with configurable overlap
- Handles HTML and plain text content
- Generates content hashes for deduplication

The chunker is optimized for Australian tax/compliance content where
preserving context is critical for accurate retrieval.
"""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Literal

from bs4 import BeautifulSoup, NavigableString, Tag


@dataclass
class Chunk:
    """A chunk of text with metadata."""

    text: str
    index: int
    start_char: int
    end_char: int
    content_hash: str
    metadata: dict = field(default_factory=dict)

    @property
    def token_estimate(self) -> int:
        """Estimate token count (~4 chars per token)."""
        return len(self.text) // 4


@dataclass
class ChunkerConfig:
    """Configuration for the semantic chunker."""

    # Target chunk size in characters
    chunk_size: int = 1500
    # Overlap between chunks for context continuity
    chunk_overlap: int = 200
    # Minimum chunk size (don't create tiny chunks)
    min_chunk_size: int = 100
    # Maximum chunk size (hard limit)
    max_chunk_size: int = 3000
    # Separators in order of preference (semantic importance)
    separators: list[str] = field(
        default_factory=lambda: [
            "\n\n\n",  # Multiple blank lines (section breaks)
            "\n\n",  # Paragraph breaks
            "\n",  # Line breaks
            ". ",  # Sentence breaks
            "? ",  # Question breaks
            "! ",  # Exclamation breaks
            "; ",  # Semicolon breaks
            ", ",  # Comma breaks
            " ",  # Word breaks
        ]
    )


class SemanticChunker:
    """Semantic text chunker for knowledge base content.

    Splits text into chunks while respecting semantic boundaries.
    Uses a recursive splitting strategy that tries increasingly
    fine-grained separators until chunks are small enough.
    """

    def __init__(self, config: ChunkerConfig | None = None) -> None:
        """Initialize the chunker.

        Args:
            config: Chunker configuration. Uses defaults if not provided.
        """
        self.config = config or ChunkerConfig()

    def chunk_text(
        self,
        text: str,
        metadata: dict | None = None,
    ) -> list[Chunk]:
        """Chunk plain text into semantic units.

        Args:
            text: Text to chunk.
            metadata: Optional metadata to attach to each chunk.

        Returns:
            List of Chunk objects.
        """
        if not text or not text.strip():
            return []

        # Clean and normalize text
        text = self._normalize_text(text)

        # Split into chunks
        raw_chunks = self._recursive_split(text, self.config.separators)

        # Merge small chunks and add overlap
        merged_chunks = self._merge_small_chunks(raw_chunks)
        overlapped_chunks = self._add_overlap(merged_chunks)

        # Build Chunk objects with metadata
        chunks: list[Chunk] = []
        char_offset = 0

        for i, chunk_text in enumerate(overlapped_chunks):
            if not chunk_text.strip():
                continue

            content_hash = self._hash_content(chunk_text)

            chunk = Chunk(
                text=chunk_text.strip(),
                index=i,
                start_char=char_offset,
                end_char=char_offset + len(chunk_text),
                content_hash=content_hash,
                metadata=metadata.copy() if metadata else {},
            )
            chunks.append(chunk)
            char_offset += len(chunk_text)

        return chunks

    def chunk_html(
        self,
        html: str,
        metadata: dict | None = None,
        preserve_structure: bool = True,
    ) -> list[Chunk]:
        """Chunk HTML content, extracting and preserving semantic structure.

        Args:
            html: HTML content to chunk.
            metadata: Optional metadata to attach to each chunk.
            preserve_structure: Keep headings with their content.

        Returns:
            List of Chunk objects.
        """
        if not html or not html.strip():
            return []

        soup = BeautifulSoup(html, "lxml")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        if preserve_structure:
            # Extract structured sections
            sections = self._extract_sections(soup)
            all_chunks: list[Chunk] = []

            for section in sections:
                section_chunks = self.chunk_text(section["text"], metadata)
                # Add section title to metadata if present
                if section.get("title"):
                    for chunk in section_chunks:
                        chunk.metadata["section_title"] = section["title"]
                all_chunks.extend(section_chunks)

            # Reindex chunks
            for i, chunk in enumerate(all_chunks):
                chunk.index = i

            return all_chunks
        else:
            # Simple text extraction
            text = soup.get_text(separator="\n", strip=True)
            return self.chunk_text(text, metadata)

    def chunk_structured_content(
        self,
        content: dict,
        content_type: Literal["ruling", "legislation", "guide"] = "guide",
        metadata: dict | None = None,
    ) -> list[Chunk]:
        """Chunk pre-structured content like rulings or legislation.

        Args:
            content: Dict with 'title', 'sections' (list of dicts with 'heading', 'text').
            content_type: Type of content for specialized handling.
            metadata: Optional metadata to attach to each chunk.

        Returns:
            List of Chunk objects.
        """
        all_chunks: list[Chunk] = []
        base_metadata = metadata.copy() if metadata else {}

        # Add title as first chunk if present
        if content.get("title"):
            base_metadata["is_title"] = True

        # Process each section
        for section in content.get("sections", []):
            section_metadata = base_metadata.copy()

            # Add section heading to metadata
            if section.get("heading"):
                section_metadata["section_heading"] = section["heading"]

            # For rulings, include the heading in the chunk text for context
            if content_type == "ruling" and section.get("heading"):
                section_text = f"{section['heading']}\n\n{section.get('text', '')}"
            else:
                section_text = section.get("text", "")

            section_chunks = self.chunk_text(section_text, section_metadata)
            all_chunks.extend(section_chunks)

        # Reindex
        for i, chunk in enumerate(all_chunks):
            chunk.index = i

        return all_chunks

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent chunking.

        Args:
            text: Raw text.

        Returns:
            Normalized text.
        """
        # Replace various whitespace with standard space
        text = re.sub(r"[\t\r\f\v]+", " ", text)
        # Normalize multiple spaces (but preserve newlines)
        text = re.sub(r" +", " ", text)
        # Normalize multiple newlines to max 3
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        # Strip lines
        lines = [line.strip() for line in text.split("\n")]
        return "\n".join(lines)

    def _recursive_split(
        self,
        text: str,
        separators: list[str],
    ) -> list[str]:
        """Recursively split text using separators.

        Tries each separator in order until chunks are small enough.

        Args:
            text: Text to split.
            separators: List of separators to try.

        Returns:
            List of text chunks.
        """
        if len(text) <= self.config.chunk_size:
            return [text] if text.strip() else []

        if not separators:
            # No more separators, force split at chunk_size
            return self._force_split(text)

        separator = separators[0]
        remaining_separators = separators[1:]

        # Split by current separator
        parts = text.split(separator)

        # If only one part, try next separator
        if len(parts) == 1:
            return self._recursive_split(text, remaining_separators)

        # Process parts
        chunks: list[str] = []
        current_chunk = ""

        for part in parts:
            # Would adding this part exceed chunk size?
            potential_chunk = current_chunk + separator + part if current_chunk else part

            if len(potential_chunk) <= self.config.chunk_size:
                current_chunk = potential_chunk
            else:
                # Save current chunk if not empty
                if current_chunk.strip():
                    chunks.append(current_chunk)

                # Check if part itself needs splitting
                if len(part) > self.config.chunk_size:
                    # Recursively split with remaining separators
                    sub_chunks = self._recursive_split(part, remaining_separators)
                    chunks.extend(sub_chunks)
                    current_chunk = ""
                else:
                    current_chunk = part

        # Don't forget the last chunk
        if current_chunk.strip():
            chunks.append(current_chunk)

        return chunks

    def _force_split(self, text: str) -> list[str]:
        """Force split text at chunk_size boundaries.

        Used as last resort when no separators work.

        Args:
            text: Text to split.

        Returns:
            List of chunks.
        """
        chunks: list[str] = []
        for i in range(0, len(text), self.config.chunk_size):
            chunk = text[i : i + self.config.chunk_size]
            if chunk.strip():
                chunks.append(chunk)
        return chunks

    def _merge_small_chunks(self, chunks: list[str]) -> list[str]:
        """Merge chunks that are too small.

        Args:
            chunks: List of text chunks.

        Returns:
            List of merged chunks.
        """
        if not chunks:
            return []

        merged: list[str] = []
        current = ""

        for chunk in chunks:
            if not chunk.strip():
                continue

            if not current:
                current = chunk
            elif len(current) + len(chunk) + 1 <= self.config.max_chunk_size:
                # Can merge
                if len(current) < self.config.min_chunk_size:
                    current = current + "\n\n" + chunk
                else:
                    merged.append(current)
                    current = chunk
            else:
                merged.append(current)
                current = chunk

        if current.strip():
            merged.append(current)

        return merged

    def _add_overlap(self, chunks: list[str]) -> list[str]:
        """Add overlap between chunks for context continuity.

        Args:
            chunks: List of text chunks.

        Returns:
            List of chunks with overlap.
        """
        if len(chunks) <= 1 or self.config.chunk_overlap == 0:
            return chunks

        overlapped: list[str] = []

        for i, chunk in enumerate(chunks):
            if i == 0:
                # First chunk: no prefix overlap
                overlapped.append(chunk)
            else:
                # Add overlap from previous chunk
                prev_chunk = chunks[i - 1]
                overlap_text = self._get_overlap_text(prev_chunk)

                if overlap_text:
                    overlapped.append(f"...{overlap_text}\n\n{chunk}")
                else:
                    overlapped.append(chunk)

        return overlapped

    def _get_overlap_text(self, text: str) -> str:
        """Get the overlap text from end of a chunk.

        Tries to find a clean break point.

        Args:
            text: Text to get overlap from.

        Returns:
            Overlap text.
        """
        if len(text) <= self.config.chunk_overlap:
            return text

        overlap = text[-self.config.chunk_overlap :]

        # Try to find a clean break point
        for sep in [". ", "? ", "! ", "\n", ", ", " "]:
            idx = overlap.find(sep)
            if idx != -1:
                return overlap[idx + len(sep) :].strip()

        return overlap.strip()

    def _extract_sections(self, soup: BeautifulSoup) -> list[dict]:
        """Extract sections from HTML based on headings.

        Args:
            soup: BeautifulSoup object.

        Returns:
            List of dicts with 'title' and 'text' keys.
        """
        sections: list[dict] = []
        current_section: dict = {"title": None, "text": ""}

        # Find all heading tags
        heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}

        def process_element(element: Tag | NavigableString) -> None:
            nonlocal current_section

            if isinstance(element, NavigableString):
                text = str(element).strip()
                if text:
                    current_section["text"] += text + " "
            elif isinstance(element, Tag):
                if element.name in heading_tags:
                    # Save current section if it has content
                    if current_section["text"].strip():
                        sections.append(current_section)
                    # Start new section
                    current_section = {
                        "title": element.get_text(strip=True),
                        "text": "",
                    }
                elif element.name in ["p", "div", "li", "td"]:
                    text = element.get_text(separator=" ", strip=True)
                    if text:
                        current_section["text"] += text + "\n\n"
                else:
                    # Recursively process children
                    for child in element.children:
                        process_element(child)

        # Process body or main content
        body = soup.find("body") or soup.find("main") or soup
        if isinstance(body, Tag):
            for child in body.children:
                process_element(child)

        # Don't forget the last section
        if current_section["text"].strip():
            sections.append(current_section)

        return sections

    def _hash_content(self, text: str) -> str:
        """Generate SHA-256 hash of content for deduplication.

        Args:
            text: Text to hash.

        Returns:
            Hex digest of hash.
        """
        # Normalize for hashing (ignore whitespace differences)
        normalized = " ".join(text.split())
        return hashlib.sha256(normalized.encode()).hexdigest()


# =============================================================================
# Convenience Functions
# =============================================================================


def chunk_text(
    text: str,
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
    metadata: dict | None = None,
) -> list[Chunk]:
    """Convenience function to chunk text with default settings.

    Args:
        text: Text to chunk.
        chunk_size: Target chunk size.
        chunk_overlap: Overlap between chunks.
        metadata: Optional metadata.

    Returns:
        List of Chunk objects.
    """
    config = ChunkerConfig(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunker = SemanticChunker(config)
    return chunker.chunk_text(text, metadata)


def chunk_html(
    html: str,
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
    metadata: dict | None = None,
) -> list[Chunk]:
    """Convenience function to chunk HTML with default settings.

    Args:
        html: HTML to chunk.
        chunk_size: Target chunk size.
        chunk_overlap: Overlap between chunks.
        metadata: Optional metadata.

    Returns:
        List of Chunk objects.
    """
    config = ChunkerConfig(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunker = SemanticChunker(config)
    return chunker.chunk_html(html, metadata)
