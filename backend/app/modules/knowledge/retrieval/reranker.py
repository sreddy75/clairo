"""Cross-encoder re-ranking for improved retrieval precision.

After hybrid search returns ~30 candidates, the cross-encoder re-scores
each (query, candidate) pair to produce a more precise ranking.  The model
``cross-encoder/ms-marco-MiniLM-L-6-v2`` is small (~80 MB) and fast enough
to score 30 candidates in <100 ms.

The model is loaded lazily on first use and cached at module level so that
it is only loaded once per process.
"""

from __future__ import annotations

import logging
import math
import threading
from typing import Any

from app.modules.knowledge.retrieval import ScoredChunk

logger = logging.getLogger(__name__)

# Module-level model cache.  Keyed by model name so that (in theory)
# multiple models could coexist, though in practice we only use one.
_MODEL_CACHE: dict[str, Any] = {}
_MODEL_LOCK = threading.Lock()

_DEFAULT_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class CrossEncoderReranker:
    """Re-rank hybrid-search candidates using a cross-encoder model.

    The cross-encoder scores each ``(query, candidate_text)`` pair
    jointly, which is more accurate than independent bi-encoder
    embeddings at the cost of higher per-pair latency.  Because we
    only re-rank the top ~30 candidates the total latency stays
    under 100 ms.

    Args:
        model_name: HuggingFace model identifier for the cross-encoder.
            Defaults to ``cross-encoder/ms-marco-MiniLM-L-6-v2``.
    """

    def __init__(
        self,
        model_name: str = _DEFAULT_MODEL_NAME,
    ) -> None:
        self._model_name = model_name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rerank(
        self,
        query: str,
        candidates: list[ScoredChunk],
        top_k: int = 10,
    ) -> list[ScoredChunk]:
        """Re-rank candidates using the cross-encoder and return the top-k.

        For each candidate the text is extracted from ``candidate.text``
        or, as a fallback, from ``candidate.payload["text"]``.  The
        cross-encoder then scores every ``(query, text)`` pair.  Results
        are sorted by descending cross-encoder score and the top *top_k*
        are returned with their ``score`` field updated to the
        cross-encoder score.

        If the model fails to load, the original candidates are returned
        unchanged (graceful fallback to hybrid-search scores).

        Args:
            query: The user's search query.
            candidates: Scored chunks from hybrid search.
            top_k: Number of results to return after re-ranking.

        Returns:
            Up to *top_k* ``ScoredChunk`` objects sorted by cross-encoder
            score in descending order.
        """
        if not candidates:
            return []

        model = self._get_model()
        if model is None:
            # Model failed to load — fall back to existing scores.
            return candidates[:top_k]

        # Build (query, candidate_text) pairs and track which candidates
        # are scoreable (have non-empty text).
        pairs: list[list[str]] = []
        scoreable_indices: list[int] = []

        for idx, candidate in enumerate(candidates):
            text = self._extract_text(candidate)
            if not text:
                continue
            pairs.append([query, text])
            scoreable_indices.append(idx)

        if not pairs:
            return candidates[:top_k]

        # Score all pairs in one batch.
        try:
            raw_scores: list[float] = model.predict(pairs).tolist()
        except Exception:
            logger.exception("Cross-encoder scoring failed; returning candidates unchanged")
            return candidates[:top_k]

        # Normalize logit scores to 0-1 range via sigmoid (clamped to avoid overflow)
        normalized_scores = [1.0 / (1.0 + math.exp(-max(min(s, 500), -500))) for s in raw_scores]

        # Attach normalized cross-encoder scores to candidates.
        scored: list[ScoredChunk] = []
        for score, orig_idx in zip(normalized_scores, scoreable_indices, strict=True):
            candidate = candidates[orig_idx]
            scored.append(
                ScoredChunk(
                    chunk_id=candidate.chunk_id,
                    score=float(score),
                    text=candidate.text,
                    payload=candidate.payload,
                )
            )

        # Sort descending by cross-encoder score and return top_k.
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_model(self) -> Any | None:
        """Lazy-load the cross-encoder model with thread-safe caching.

        The ``sentence_transformers`` package is imported lazily so that
        the module can be imported even when the library is not installed
        (useful for lightweight test environments).

        Returns:
            The loaded ``CrossEncoder`` instance, or ``None`` if loading
            failed.
        """
        cached = _MODEL_CACHE.get(self._model_name)
        if cached is not None:
            return cached

        with _MODEL_LOCK:
            # Double-check after acquiring the lock.
            cached = _MODEL_CACHE.get(self._model_name)
            if cached is not None:
                return cached

            try:
                logger.info(
                    "Loading cross-encoder model '%s' (first use — may take a few seconds)...",
                    self._model_name,
                )
                from sentence_transformers import CrossEncoder

                model = CrossEncoder(self._model_name)
                _MODEL_CACHE[self._model_name] = model
                logger.info(
                    "Cross-encoder model '%s' loaded successfully.",
                    self._model_name,
                )
                return model
            except Exception:
                logger.exception(
                    "Failed to load cross-encoder model '%s'; "
                    "re-ranking will be skipped (falling back to hybrid-search scores).",
                    self._model_name,
                )
                return None

    @staticmethod
    def _extract_text(candidate: ScoredChunk) -> str:
        """Extract display text from a scored chunk.

        Prefers ``candidate.text``, falling back to
        ``candidate.payload["text"]``.

        Returns:
            The chunk text, or an empty string if unavailable.
        """
        if candidate.text:
            return candidate.text
        if candidate.payload:
            return candidate.payload.get("text", "")
        return ""
