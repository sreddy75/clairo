"""Unit tests for StrategyChunker (Spec 060 T019)."""

from __future__ import annotations

import re

import pytest

from app.modules.knowledge.chunkers.strategy import (
    StrategyChunker,
    StrategyChunkerInput,
)


_DEFAULT_KEYWORDS: list[str] = ["concessional", "catch-up super", "carry forward"]
_SENTINEL: list[str] = []  # placeholder for keyword override default


def _clr_012_input(
    *,
    implementation_text: str = (
        "1. Confirm the employee's concessional cap for the FY.\n"
        "2. Determine any unused carry-forward cap amounts."
    ),
    explanation_text: str = (
        "Concessional super contributions are taxed at 15% inside super "
        "rather than at the employee's marginal rate."
    ),
    keywords: list[str] | None = None,
) -> StrategyChunkerInput:
    # Explicit None → default keyword set; explicit empty list → no keywords.
    resolved_keywords = list(_DEFAULT_KEYWORDS) if keywords is None else keywords
    return StrategyChunkerInput(
        strategy_id="CLR-012",
        name="Concessional super contributions",
        primary_category="Recommendations",
        implementation_text=implementation_text,
        explanation_text=explanation_text,
        keywords=resolved_keywords,
    )


def test_produces_exactly_two_chunks_for_typical_input() -> None:
    chunker = StrategyChunker()
    chunks = chunker.chunk_strategy(_clr_012_input())
    assert len(chunks) == 2
    assert chunks[0].metadata["chunk_section"] == "implementation"
    assert chunks[1].metadata["chunk_section"] == "explanation"


def test_context_header_format_matches_arch_spec() -> None:
    """Architecture §7.2: `[CLR-XXX: Name — Category: Y]`."""
    chunker = StrategyChunker()
    chunks = chunker.chunk_strategy(_clr_012_input())
    for chunk in chunks:
        header = chunk.metadata["context_header"]
        assert re.match(
            r"^\[CLR-012: Concessional super contributions — Category: Recommendations\]$",
            header,
        ), header
        # Header must also be the first line of the chunk text body.
        assert chunk.text.startswith(header)


def test_every_chunk_ends_with_keywords_line_when_keywords_provided() -> None:
    chunker = StrategyChunker()
    chunks = chunker.chunk_strategy(_clr_012_input())
    for chunk in chunks:
        last_line = chunk.text.rstrip().splitlines()[-1]
        assert last_line.startswith("Keywords: ")
        assert last_line.endswith(".")


def test_no_keywords_tail_when_keywords_empty() -> None:
    chunker = StrategyChunker()
    chunks = chunker.chunk_strategy(_clr_012_input(keywords=[]))
    for chunk in chunks:
        assert "Keywords:" not in chunk.text


def test_empty_section_is_skipped_not_chunked() -> None:
    """Stub strategies have blank sections; chunker must not emit zero-body
    chunks for them (publish task is expected to gate on status anyway,
    but defense in depth matters)."""
    chunker = StrategyChunker()
    chunks = chunker.chunk_strategy(_clr_012_input(implementation_text="   "))
    assert len(chunks) == 1
    assert chunks[0].metadata["chunk_section"] == "explanation"


def test_long_explanation_splits_at_paragraph_boundary() -> None:
    """Architecture §7.3: when a section exceeds the chunk budget, split at
    paragraph boundaries; each split piece carries the same context header."""
    # Construct an explanation whose total budget exceeds 500 tokens but
    # whose individual paragraphs are smaller.
    long_paragraph = " ".join(["concessional super contributions detail."] * 60)
    # Token estimate = len(text) // 4; ~2000 chars per paragraph → ~500 tokens.
    # Three such paragraphs force at least 2 splits.
    explanation = "\n\n".join([long_paragraph, long_paragraph, long_paragraph])

    chunker = StrategyChunker()
    chunks = chunker.chunk_strategy(_clr_012_input(explanation_text=explanation))
    explanation_chunks = [
        c for c in chunks if c.metadata["chunk_section"] == "explanation"
    ]
    assert len(explanation_chunks) >= 2, (
        f"Expected ≥2 explanation chunks for long input, got {len(explanation_chunks)}"
    )
    # Every split piece must carry the same context header.
    headers = {c.metadata["context_header"] for c in explanation_chunks}
    assert len(headers) == 1


def test_chunk_metadata_carries_strategy_identity() -> None:
    chunker = StrategyChunker()
    chunks = chunker.chunk_strategy(_clr_012_input())
    for chunk in chunks:
        assert chunk.metadata["strategy_id"] == "CLR-012"
        assert chunk.metadata["strategy_name"] == "Concessional super contributions"
        assert chunk.metadata["primary_category"] == "Recommendations"
        assert chunk.topic_tags == ["Recommendations"]


def test_chunk_generic_chunk_method_is_not_supported() -> None:
    """The generic chunk(raw_content, metadata) signature isn't meaningful
    for two-section strategies — it must raise so callers use chunk_strategy.
    """
    chunker = StrategyChunker()
    with pytest.raises(NotImplementedError):
        chunker.chunk("some text")
