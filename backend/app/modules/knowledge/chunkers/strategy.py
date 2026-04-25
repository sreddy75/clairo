"""Chunker for tax strategy parent documents (Spec 060 T026).

Produces exactly two retrievable child chunks per strategy:
    1. Implementation (from TaxStrategy.implementation_text)
    2. Explanation (from TaxStrategy.explanation_text)

Each chunk is prefixed with a context header carrying the Clairo
identifier, name, and primary category, and suffixed with a Keywords
line — the two levers that make semantic retrieval match on strategy
name / category (via the header in the embedding) and BM25 match on
accountant shorthand (via keywords in the body). See architecture §7.

When a section's text exceeds the chunk budget, it splits at paragraph
boundaries via BaseStructuredChunker._split_at_boundary, with each split
piece carrying the same context header.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.knowledge.chunkers.base import BaseStructuredChunker, ChunkResult

# Chunk budget for the body (excluding the prepended context header).
# 500 tokens ≈ architecture §7.3 target ceiling; 200 is the soft lower
# bound below which we avoid splitting further.
_MAX_BODY_TOKENS = 500


@dataclass
class StrategyChunkerInput:
    """Input bundle for StrategyChunker.chunk().

    We don't pass a raw_content string because tax strategies have two
    distinct sections (implementation + explanation) that must emit as
    separate chunks. Using a typed input keeps the contract explicit.
    """

    strategy_id: str
    name: str
    primary_category: str
    implementation_text: str
    explanation_text: str
    keywords: list[str]


class StrategyChunker(BaseStructuredChunker):
    """Parent-child chunker for tax strategies.

    Usage:
        chunker = StrategyChunker()
        chunks = chunker.chunk_strategy(
            StrategyChunkerInput(
                strategy_id="CLR-241",
                name="Change PSI to PSB",
                primary_category="Business",
                implementation_text="...",
                explanation_text="...",
                keywords=["PSI", "PSB", "80% rule", ...],
            )
        )
        # Returns [impl_chunk_1, ..., impl_chunk_n, expl_chunk_1, ..., expl_chunk_m]
    """

    # BaseStructuredChunker requires chunk(raw_content, metadata) — we
    # satisfy the signature but the real entry point is chunk_strategy().
    def chunk(self, raw_content: str, metadata: dict | None = None) -> list[ChunkResult]:
        raise NotImplementedError(
            "Use StrategyChunker.chunk_strategy(StrategyChunkerInput) — "
            "tax strategies have structured input that doesn't fit the "
            "generic raw_content + metadata signature."
        )

    def chunk_strategy(self, data: StrategyChunkerInput) -> list[ChunkResult]:
        """Produce chunks for both sections of a tax strategy.

        Returns one or more chunks per section (one each in the typical
        case; more when a section exceeds _MAX_BODY_TOKENS and splits at
        paragraph boundaries).
        """
        results: list[ChunkResult] = []
        keyword_tail = self._format_keyword_tail(data.keywords)
        context_header = self._format_context_header(
            data.strategy_id, data.name, data.primary_category
        )

        for section_label, section_text in (
            ("implementation", data.implementation_text),
            ("explanation", data.explanation_text),
        ):
            text = (section_text or "").strip()
            if not text:
                # Skip empty sections — a stub strategy will have blank
                # implementation/explanation and must not produce zero-body
                # chunks. Caller (publish task) should gate on status to
                # avoid chunking stubs.
                continue

            bodies = self._split_at_boundary(text, max_tokens=_MAX_BODY_TOKENS)
            for body in bodies:
                composed = self._compose_chunk_text(
                    context_header=context_header,
                    section_label=section_label,
                    body=body,
                    keyword_tail=keyword_tail,
                )
                results.append(
                    ChunkResult(
                        text=composed,
                        content_type="tax_strategy",
                        section_ref=data.strategy_id,  # reuse section_ref slot
                        topic_tags=[data.primary_category],
                        metadata={
                            "strategy_id": data.strategy_id,
                            "strategy_name": data.name,
                            "chunk_section": section_label,
                            "context_header": context_header,
                            "keywords": list(data.keywords),
                            "primary_category": data.primary_category,
                        },
                    )
                )
        return results

    @staticmethod
    def _format_context_header(strategy_id: str, name: str, primary_category: str) -> str:
        """Produce `[CLR-XXX: Name — Category: Y]` per architecture §7.2."""
        return f"[{strategy_id}: {name} — Category: {primary_category}]"

    @staticmethod
    def _format_keyword_tail(keywords: list[str]) -> str:
        """Produce the `Keywords: ...` tail line for BM25.

        Empty keyword list returns an empty string (caller omits the tail).
        """
        cleaned = [k.strip() for k in keywords if k and k.strip()]
        if not cleaned:
            return ""
        return "Keywords: " + ", ".join(cleaned) + "."

    @staticmethod
    def _compose_chunk_text(
        *,
        context_header: str,
        section_label: str,
        body: str,
        keyword_tail: str,
    ) -> str:
        """Assemble the final chunk text from header + body + keywords."""
        section_header = (
            "Implementation advice:"
            if section_label == "implementation"
            else "Strategy explanation:"
        )
        parts = [context_header, section_header, body.strip()]
        if keyword_tail:
            parts.append(keyword_tail)
        return "\n\n".join(parts)
