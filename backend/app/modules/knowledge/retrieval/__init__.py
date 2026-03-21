"""Enhanced retrieval pipeline for legal knowledge.

Components:
- hybrid_search: BM25 + semantic fusion
- reranker: Cross-encoder re-ranking
- query_router: Legal query classification
- query_expander: LLM-assisted query expansion
- citation_verifier: Post-generation citation verification
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScoredChunk:
    """A content chunk with a relevance score from retrieval or re-ranking.

    Used as the common interchange type between hybrid search, re-ranking,
    and downstream pipeline stages.
    """

    chunk_id: str
    score: float
    text: str | None = None
    payload: dict | None = field(default_factory=dict)


__all__ = ["ScoredChunk"]
