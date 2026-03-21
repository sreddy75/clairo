"""Hybrid search combining BM25 keyword and Pinecone semantic retrieval.

Uses Reciprocal Rank Fusion (RRF) to merge dense (Pinecone vector) and
sparse (BM25 keyword) search results into a single ranked list.

The hybrid approach improves recall on both exact-match queries (e.g.,
section references, ruling numbers) via BM25, and conceptual/semantic
queries via dense embeddings.

Usage:
    from app.modules.knowledge.retrieval.hybrid_search import HybridSearchEngine

    engine = HybridSearchEngine(session, pinecone, voyage)
    results = await engine.hybrid_search(
        query="What are the Div 7A rules?",
        collection="compliance_knowledge",
        limit=30,
        semantic_weight=0.6,
    )
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from rank_bm25 import BM25Okapi
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pinecone_service import PineconeService, ScoredResult
from app.core.voyage import VoyageService
from app.modules.knowledge.collections import INDEX_NAME, get_namespace_with_env
from app.modules.knowledge.repository import BM25IndexRepository

logger = logging.getLogger(__name__)

# Standard English stopwords for BM25 tokenisation
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "do",
        "for",
        "from",
        "had",
        "has",
        "have",
        "he",
        "her",
        "him",
        "his",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "me",
        "my",
        "no",
        "not",
        "of",
        "on",
        "or",
        "our",
        "own",
        "she",
        "so",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "too",
        "up",
        "us",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
    }
)

# Regex pattern for tokenisation: split on non-alphanumeric characters
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@dataclass
class ScoredChunk:
    """A search result with a fused relevance score.

    Attributes:
        chunk_id: UUID string identifying the content chunk.
        score: Fused relevance score (higher is better).
        text: Chunk text content, if available from metadata.
        payload: Full Pinecone metadata dict.
    """

    chunk_id: str
    score: float
    text: str | None = None
    payload: dict[str, Any] | None = field(default=None, repr=False)


class HybridSearchEngine:
    """Hybrid search engine combining BM25 keyword and Pinecone semantic search.

    Retrieves candidates from both dense and sparse indexes, then merges
    results using weighted Reciprocal Rank Fusion (RRF).

    Args:
        session: Async SQLAlchemy session for BM25 index lookups.
        pinecone: Pinecone vector search service.
        voyage: Voyage AI embedding service for query vectorisation.
    """

    def __init__(
        self,
        session: AsyncSession,
        pinecone: PineconeService,
        voyage: VoyageService,
    ) -> None:
        self._session = session
        self._pinecone = pinecone
        self._voyage = voyage
        self._bm25_repo = BM25IndexRepository(session)

        # In-memory cache of BM25 indexes keyed by collection name.
        # Persists for the lifetime of this engine instance.
        self._bm25_cache: dict[str, tuple[BM25Okapi, list[str]]] = {}

    # =========================================================================
    # Public API
    # =========================================================================

    async def hybrid_search(
        self,
        query: str,
        collection: str,
        limit: int = 30,
        semantic_weight: float = 0.6,
        pinecone_filter: dict[str, Any] | None = None,
        namespaces: list[str] | None = None,
    ) -> list[ScoredChunk]:
        """Run hybrid search combining semantic and BM25 retrieval.

        Steps:
            1. Embed the query via VoyageService.
            2. Semantic search via Pinecone (top ``limit * 2`` candidates).
            3. BM25 keyword search against the DB-backed token index.
            4. Merge results with weighted Reciprocal Rank Fusion.
            5. Return the top ``limit`` results sorted by fused score.

        Args:
            query: Natural-language search query.
            collection: Base collection/namespace name (e.g. ``"compliance_knowledge"``).
            limit: Maximum number of results to return.
            semantic_weight: Weight for the semantic (dense) component.
                The BM25 (sparse) component weight is ``1 - semantic_weight``.
            pinecone_filter: Optional Pinecone metadata filter dict passed
                directly to the vector search.
            namespaces: Optional list of base namespace names to search.
                When ``None``, the ``collection`` value is used as a single
                namespace.

        Returns:
            Ranked list of :class:`ScoredChunk` sorted by descending fused
            relevance score, capped at ``limit`` items.
        """
        candidate_count = limit * 2

        # Step 1: Embed the query
        query_vector = await self._voyage.embed_query(query)

        # Step 2: Semantic search via Pinecone
        semantic_results = await self._semantic_search(
            query_vector=query_vector,
            collection=collection,
            limit=candidate_count,
            pinecone_filter=pinecone_filter,
            namespaces=namespaces,
        )

        # Step 3: BM25 keyword search
        bm25_results = await self._bm25_search(
            query=query,
            collection=collection,
            limit=candidate_count,
        )

        # Step 4 + 5: Reciprocal Rank Fusion and truncation
        fused = self._reciprocal_rank_fusion(
            semantic_results=semantic_results,
            bm25_results=bm25_results,
            semantic_weight=semantic_weight,
        )

        # Step 5b: Enrich BM25-only results that lack Pinecone metadata.
        # BM25 results use DB UUIDs as chunk_id while Pinecone uses vector IDs,
        # so we look up qdrant_point_id from the DB, then fetch from Pinecone.
        bm25_only = [c for c in fused[: limit * 2] if c.payload is None]
        if bm25_only:
            try:
                from uuid import UUID as _UUID

                from sqlalchemy import select as _select

                from app.modules.knowledge.models import ContentChunk

                db_uuids = [_UUID(c.chunk_id) for c in bm25_only]
                result_rows = await self._session.execute(
                    _select(
                        ContentChunk.id,
                        ContentChunk.qdrant_point_id,
                        ContentChunk.title,
                        ContentChunk.source_url,
                        ContentChunk.source_type,
                        ContentChunk.section_ref,
                        ContentChunk.content_type,
                        ContentChunk.natural_key,
                    ).where(ContentChunk.id.in_(db_uuids))
                )
                db_rows = {str(r.id): r for r in result_rows.all()}

                # Fetch text from Pinecone using the real vector IDs
                vector_ids = [
                    db_rows[c.chunk_id].qdrant_point_id
                    for c in bm25_only
                    if c.chunk_id in db_rows and db_rows[c.chunk_id].qdrant_point_id
                ]
                pinecone_text: dict[str, str] = {}
                if vector_ids:
                    namespace = get_namespace_with_env(collection)
                    fetched = await self._pinecone.fetch_vectors(
                        index_name=INDEX_NAME,
                        ids=vector_ids,
                        namespace=namespace,
                    )
                    if fetched:
                        for vid, vec_data in fetched.items():
                            md = (
                                vec_data.get("metadata", {})
                                if isinstance(vec_data, dict)
                                else getattr(vec_data, "metadata", {})
                            )
                            pinecone_text[vid] = md.get("text", "")

                # Populate metadata on BM25-only results
                for chunk in bm25_only:
                    row = db_rows.get(chunk.chunk_id)
                    if not row:
                        continue
                    text = pinecone_text.get(row.qdrant_point_id, "")
                    chunk.text = text
                    chunk.payload = {
                        "chunk_id": chunk.chunk_id,
                        "title": row.title or "",
                        "source_url": row.source_url or "",
                        "source_type": row.source_type or "",
                        "section_ref": row.section_ref or "",
                        "content_type": row.content_type or "",
                        "natural_key": row.natural_key or "",
                        "text": text,
                    }

                logger.debug(
                    "Enriched %d BM25-only results with DB+Pinecone metadata",
                    len(bm25_only),
                )
            except Exception:
                logger.warning(
                    "Failed to enrich BM25-only results; they will lack metadata",
                    exc_info=True,
                )

        result = fused[:limit]

        logger.info(
            "Hybrid search complete: query=%r collection=%s "
            "semantic=%d bm25=%d fused=%d returned=%d",
            query[:80],
            collection,
            len(semantic_results),
            len(bm25_results),
            len(fused),
            len(result),
        )

        return result

    # =========================================================================
    # Semantic (Dense) Search
    # =========================================================================

    async def _semantic_search(
        self,
        query_vector: list[float],
        collection: str,
        limit: int,
        pinecone_filter: dict[str, Any] | None,
        namespaces: list[str] | None,
    ) -> list[ScoredResult]:
        """Run semantic vector search against Pinecone.

        Args:
            query_vector: Embedded query vector.
            collection: Base collection name (used as namespace if *namespaces* is None).
            limit: Maximum results to retrieve.
            pinecone_filter: Optional metadata filter dict.
            namespaces: Optional list of base namespace names to search.

        Returns:
            Ranked list of Pinecone ``ScoredResult`` objects.
        """
        if namespaces:
            # Search across multiple namespaces
            target_namespaces = [get_namespace_with_env(ns) for ns in namespaces]
            results = await self._pinecone.search_multi_namespace(
                index_name=INDEX_NAME,
                namespaces=target_namespaces,
                query_vector=query_vector,
                limit_per_namespace=max(2, limit // len(target_namespaces)),
                total_limit=limit,
            )
        else:
            # Single-namespace search
            namespace = get_namespace_with_env(collection)
            results = await self._pinecone.search(
                index_name=INDEX_NAME,
                query_vector=query_vector,
                namespace=namespace,
                filter=pinecone_filter,
                limit=limit,
                include_metadata=True,
            )

        return results

    # =========================================================================
    # BM25 (Sparse) Search
    # =========================================================================

    async def _bm25_search(
        self,
        query: str,
        collection: str,
        limit: int,
    ) -> list[tuple[str, float]]:
        """Run BM25 keyword search against the DB-backed token index.

        Args:
            query: Natural-language search query.
            collection: Collection name used to look up BM25 entries.
            limit: Maximum results to return.

        Returns:
            List of ``(chunk_id_str, bm25_score)`` tuples sorted by
            descending BM25 score.
        """
        bm25_index, chunk_ids = await self._get_bm25_index(collection)
        if bm25_index is None or not chunk_ids:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores = bm25_index.get_scores(query_tokens)

        # Pair each score with its chunk_id, then take top-N by score
        scored_pairs = [(chunk_ids[i], float(score)) for i, score in enumerate(scores) if score > 0]
        scored_pairs.sort(key=lambda pair: pair[1], reverse=True)

        return scored_pairs[:limit]

    async def _get_bm25_index(
        self,
        collection: str,
    ) -> tuple[BM25Okapi | None, list[str]]:
        """Load or retrieve cached BM25 index for a collection.

        On first call per collection, all ``BM25IndexEntry`` rows for the
        collection are fetched from the database, and a ``BM25Okapi`` scorer
        is built from the stored token lists. The result is cached in memory
        for the lifetime of this engine instance.

        Args:
            collection: Collection name to index.

        Returns:
            Tuple of ``(BM25Okapi scorer, list of chunk_id strings)``
            matching the corpus order. Returns ``(None, [])`` if the
            collection has no BM25 entries.
        """
        if collection in self._bm25_cache:
            return self._bm25_cache[collection]

        entries = await self._bm25_repo.get_by_collection(collection)
        if not entries:
            logger.debug("No BM25 entries found for collection=%s", collection)
            self._bm25_cache[collection] = (None, [])
            return None, []

        # Build the corpus from stored token lists
        corpus: list[list[str]] = []
        chunk_ids: list[str] = []
        for entry in entries:
            tokens = entry.tokens if entry.tokens else []
            corpus.append(tokens)
            chunk_ids.append(str(entry.chunk_id))

        bm25 = BM25Okapi(corpus)
        self._bm25_cache[collection] = (bm25, chunk_ids)

        logger.info(
            "Built BM25 index for collection=%s with %d entries",
            collection,
            len(chunk_ids),
        )

        return bm25, chunk_ids

    # =========================================================================
    # Reciprocal Rank Fusion
    # =========================================================================

    @staticmethod
    def _reciprocal_rank_fusion(
        semantic_results: list[ScoredResult],
        bm25_results: list[tuple[str, float]],
        semantic_weight: float,
        k: int = 60,
    ) -> list[ScoredChunk]:
        """Merge semantic and BM25 results using weighted Reciprocal Rank Fusion.

        RRF score for each result list is ``1 / (k + rank)`` where *rank*
        starts at 1 for the top result. The final score is a weighted
        combination:

            ``final = semantic_weight * rrf_semantic + (1 - semantic_weight) * rrf_bm25``

        Args:
            semantic_results: Ranked Pinecone search results.
            bm25_results: Ranked BM25 results as ``(chunk_id, score)`` tuples.
            semantic_weight: Weight for the semantic RRF component (0-1).
            k: RRF constant (standard default 60).

        Returns:
            Combined list of :class:`ScoredChunk` sorted by descending
            fused score.
        """
        bm25_weight = 1.0 - semantic_weight

        # Accumulate RRF contributions per chunk_id
        # Stores: {chunk_id: {"semantic_rrf": float, "bm25_rrf": float,
        #                     "text": str|None, "payload": dict|None}}
        rrf_map: dict[str, dict[str, Any]] = {}

        # -- Semantic contributions --
        for rank, result in enumerate(semantic_results, start=1):
            chunk_id = result.id
            rrf_score = 1.0 / (k + rank)

            if chunk_id not in rrf_map:
                rrf_map[chunk_id] = {
                    "semantic_rrf": 0.0,
                    "bm25_rrf": 0.0,
                    "text": None,
                    "payload": None,
                }

            rrf_map[chunk_id]["semantic_rrf"] += rrf_score

            # Capture metadata from the Pinecone result
            if result.payload:
                rrf_map[chunk_id]["payload"] = result.payload
                rrf_map[chunk_id]["text"] = result.payload.get("text")

        # -- BM25 contributions --
        for rank, (chunk_id, _bm25_score) in enumerate(bm25_results, start=1):
            rrf_score = 1.0 / (k + rank)

            if chunk_id not in rrf_map:
                rrf_map[chunk_id] = {
                    "semantic_rrf": 0.0,
                    "bm25_rrf": 0.0,
                    "text": None,
                    "payload": None,
                }

            rrf_map[chunk_id]["bm25_rrf"] += rrf_score

        # -- Compute fused scores --
        fused_chunks: list[ScoredChunk] = []
        for chunk_id, data in rrf_map.items():
            fused_score = semantic_weight * data["semantic_rrf"] + bm25_weight * data["bm25_rrf"]
            fused_chunks.append(
                ScoredChunk(
                    chunk_id=chunk_id,
                    score=fused_score,
                    text=data["text"],
                    payload=data["payload"],
                )
            )

        # Sort descending by fused score
        fused_chunks.sort(key=lambda c: c.score, reverse=True)

        return fused_chunks


# =============================================================================
# Module-level helpers
# =============================================================================


def _tokenize(text: str) -> list[str]:
    """Tokenize text for BM25 scoring.

    Lowercases the input, splits on non-alphanumeric boundaries, and
    removes standard English stopwords.

    Args:
        text: Raw text to tokenize.

    Returns:
        List of normalised, non-stopword tokens.
    """
    lowered = text.lower()
    tokens = _TOKEN_PATTERN.findall(lowered)
    return [t for t in tokens if t not in _STOPWORDS]
