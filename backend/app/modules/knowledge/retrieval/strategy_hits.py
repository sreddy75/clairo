"""Two-pass retrieval helper for the tax_strategies namespace (Spec 060 T018a).

The hybrid retrieval pipeline returns candidates at the **chunk** level. For
tax strategies the caller actually wants candidates at the **parent** level
— multiple chunks of the same strategy should collapse to a single hit, and
the cross-encoder rerank should score against the full parent content
(implementation + explanation) rather than a chunk-sized slice.

This module implements:
    1. Dedupe by parent (tax_strategy_id), keeping the max-scored chunk.
    2. Batch-fetch live parent rows via TaxStrategyRepository.get_live_versions.
    3. Belt-and-braces SQL-side filter: exclude rows with
       status ∈ {superseded, archived} — defends against stale Pinecone
       metadata (FR-019, research §R11).
    4. Cross-encoder rerank on full parent content.

The helper returns a list of StrategyHit records in reranked order. Callers
(currently: tax_planning's _retrieve_tax_knowledge) use these to build the
`<strategy>` LLM envelope defined in architecture §9.5.

Compliance-knowledge chunks (no tax_strategy_id in payload) pass through
unchanged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.retrieval.hybrid_search import ScoredChunk
from app.modules.tax_strategies.repository import TaxStrategyRepository

if TYPE_CHECKING:
    from app.modules.knowledge.retrieval.reranker import CrossEncoderReranker
    from app.modules.tax_strategies.models import TaxStrategy

logger = logging.getLogger(__name__)


@dataclass
class StrategyHit:
    """A reranked tax strategy retrieval result, with full parent content."""

    strategy: TaxStrategy
    score: float
    best_chunk: ScoredChunk


# Status values excluded from retrieval per FR-019. Pinecone metadata
# is_superseded filter handles the happy path; this set handles the
# belt-and-braces SQL-side filter.
_EXCLUDED_STATUSES: frozenset[str] = frozenset({"superseded", "archived"})


async def dedupe_and_rerank_strategies(
    session: AsyncSession,
    chunks: list[ScoredChunk],
    query: str,
    reranker: CrossEncoderReranker | None = None,
    top_k: int = 8,
) -> list[StrategyHit]:
    """Run the two-pass retrieval: dedupe → parent-fetch → filter → rerank.

    Args:
        session: Async session for the parent-row batch fetch.
        chunks: Hybrid-search ScoredChunks. Non-strategy chunks are ignored.
        query: Original query string for the cross-encoder rerank.
        reranker: Optional cross-encoder. When None (e.g., local tests without
            the model loaded), hits are returned in max-chunk-score order.
        top_k: Maximum number of strategy hits to return.

    Returns:
        StrategyHit list in reranked order. Empty list when no strategy
        chunks are present in the input.
    """
    # Step 1: dedupe by parent strategy_id, keep max-score chunk per parent.
    best_by_parent: dict[str, ScoredChunk] = {}
    for chunk in chunks:
        payload = chunk.payload or {}
        strategy_id = payload.get("strategy_id")
        if not strategy_id:
            # Non-strategy chunk (e.g., compliance_knowledge) — ignore here;
            # the caller handles those separately.
            continue
        existing = best_by_parent.get(strategy_id)
        if existing is None or chunk.score > existing.score:
            best_by_parent[strategy_id] = chunk

    if not best_by_parent:
        return []

    # Step 2: batch-fetch live parent rows.
    repo = TaxStrategyRepository(session)
    strategy_ids = list(best_by_parent.keys())
    parents = await repo.get_live_versions(strategy_ids)
    parent_by_strategy_id = {p.strategy_id: p for p in parents}

    # Step 3: Build hits, filtering status ∈ {superseded, archived}.
    hits: list[StrategyHit] = []
    for strategy_id, best_chunk in best_by_parent.items():
        parent = parent_by_strategy_id.get(strategy_id)
        if parent is None:
            # Vector present but no live parent row (stale metadata).
            # Log and skip — FR-019 requires exclusion.
            logger.info(
                "strategy_hits.skip: vector metadata references %s but no "
                "live parent row exists (likely superseded or deleted)",
                strategy_id,
            )
            continue
        if parent.status in _EXCLUDED_STATUSES:
            logger.info(
                "strategy_hits.skip: parent %s has status=%s (SQL-side filter)",
                strategy_id,
                parent.status,
            )
            continue
        hits.append(StrategyHit(strategy=parent, score=best_chunk.score, best_chunk=best_chunk))

    if not hits:
        return []

    # Step 4: cross-encoder rerank on FULL parent content. We use the existing
    # CrossEncoderReranker (which operates on ScoredChunk inputs) by wrapping
    # each parent's full prose in a synthetic ScoredChunk whose `text` is the
    # composed parent content. The reranker returns chunks in reranked order
    # with updated scores; we map back to StrategyHit via strategy_id carried
    # in each synthetic chunk's payload.
    if reranker is None:
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]

    synthetic_candidates: list[ScoredChunk] = [
        ScoredChunk(
            chunk_id=h.strategy.strategy_id,  # use strategy_id as dedupe key
            score=h.score,
            text=_render_parent_for_rerank(h.strategy),
            payload={"strategy_id": h.strategy.strategy_id},
        )
        for h in hits
    ]
    try:
        reranked = reranker.rerank(
            query=query,
            candidates=synthetic_candidates,
            top_k=top_k,
        )
    except Exception:
        logger.exception("strategy_hits.rerank_failed: falling back to chunk-score order")
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]

    # Map reranked synthetic chunks back to StrategyHits.
    hit_by_id = {h.strategy.strategy_id: h for h in hits}
    result: list[StrategyHit] = []
    for rc in reranked:
        sid = (rc.payload or {}).get("strategy_id")
        if sid is None:
            continue
        source_hit = hit_by_id.get(sid)
        if source_hit is None:
            continue
        result.append(
            StrategyHit(
                strategy=source_hit.strategy,
                score=float(rc.score),
                best_chunk=source_hit.best_chunk,
            )
        )
    return result


def _render_parent_for_rerank(strategy: TaxStrategy) -> str:
    """Compose the full parent content passed to the reranker.

    Includes the name and category context so the reranker has the same
    signals as the LLM will see in the <strategy> envelope.
    """
    categories = ", ".join(strategy.categories) if strategy.categories else ""
    header = f"[{strategy.strategy_id}: {strategy.name} — Categories: {categories}]"
    return (
        f"{header}\n\n"
        f"Implementation advice:\n{strategy.implementation_text}\n\n"
        f"Strategy explanation:\n{strategy.explanation_text}"
    )
