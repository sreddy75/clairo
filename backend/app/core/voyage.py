"""Voyage AI embedding service.

This module provides a service for generating text embeddings using Voyage AI's
models. Optimized for RAG retrieval with batch processing and retry logic.

Usage:
    from app.core.voyage import VoyageService
    from app.config import get_settings

    settings = get_settings()
    voyage = VoyageService(settings.voyage)

    # Single text
    vector = await voyage.embed_text("Hello world")

    # Query (optimized for retrieval)
    query_vector = await voyage.embed_query("What is GST?")

    # Batch
    vectors = await voyage.embed_batch(["text1", "text2", ...])
"""

import asyncio
import logging
from typing import ClassVar, Literal

import voyageai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import VoyageSettings

logger = logging.getLogger(__name__)


class VoyageEmbeddingError(Exception):
    """Error during Voyage AI embedding operation."""

    pass


class VoyageService:
    """Voyage AI embedding service with batching and retry logic.

    Voyage AI provides high-quality embeddings optimized for RAG retrieval.
    The service handles:
    - Single text embedding
    - Query embedding (different input_type for better retrieval)
    - Batch embedding with automatic chunking
    - Retry with exponential backoff on failures
    """

    # Model constants (dimensions per model)
    SUPPORTED_MODELS: ClassVar[dict[str, int]] = {
        "voyage-3.5-lite": 1024,  # Default output dimensions
        "voyage-3-large": 1024,
        "voyage-3": 1024,
    }

    def __init__(self, settings: VoyageSettings) -> None:
        """Initialize Voyage service.

        Args:
            settings: Voyage AI configuration settings.

        Raises:
            ValueError: If API key is not configured.
        """
        api_key = settings.api_key.get_secret_value()
        if not api_key:
            raise ValueError(
                "Voyage API key not configured. Set VOYAGE_API_KEY environment variable."
            )

        self._settings = settings
        self._client = voyageai.Client(api_key=api_key)
        self._async_client = voyageai.AsyncClient(api_key=api_key)

        # Validate model
        if settings.model not in self.SUPPORTED_MODELS:
            logger.warning(f"Unknown model {settings.model}, expected dimensions may be wrong")

    @property
    def model(self) -> str:
        """Get the configured embedding model name."""
        return self._settings.model

    @property
    def dimensions(self) -> int:
        """Get the vector dimensions for the configured model."""
        return self._settings.dimensions

    @property
    def batch_size(self) -> int:
        """Get the maximum batch size for embedding requests."""
        return self._settings.batch_size

    # =========================================================================
    # Core Embedding Methods
    # =========================================================================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((voyageai.error.RateLimitError, ConnectionError)),
        reraise=True,
    )
    async def embed_text(
        self,
        text: str,
        input_type: Literal["document", "query"] = "document",
    ) -> list[float]:
        """Embed a single text.

        Args:
            text: Text to embed.
            input_type: Type of text - "document" for content, "query" for search.

        Returns:
            Embedding vector (list of floats).

        Raises:
            VoyageEmbeddingError: On API error after retries.
        """
        try:
            result = await self._async_client.embed(
                texts=[text],
                model=self.model,
                input_type=input_type,
            )
            return result.embeddings[0]
        except voyageai.error.InvalidRequestError as e:
            raise VoyageEmbeddingError(f"Invalid request: {e}") from e
        except Exception as e:
            raise VoyageEmbeddingError(f"Embedding failed: {e}") from e

    async def embed_query(self, query: str) -> list[float]:
        """Embed a search query (optimized for retrieval).

        Uses input_type="query" which is optimized for finding similar documents.

        Args:
            query: Search query text.

        Returns:
            Query embedding vector.
        """
        return await self.embed_text(query, input_type="query")

    async def embed_document(self, text: str) -> list[float]:
        """Embed document content.

        Uses input_type="document" which is optimized for document storage.

        Args:
            text: Document text to embed.

        Returns:
            Document embedding vector.
        """
        return await self.embed_text(text, input_type="document")

    # =========================================================================
    # Batch Embedding
    # =========================================================================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((voyageai.error.RateLimitError, ConnectionError)),
        reraise=True,
    )
    async def _embed_batch_chunk(
        self,
        texts: list[str],
        input_type: Literal["document", "query"] = "document",
    ) -> list[list[float]]:
        """Embed a batch of texts (internal, handles single API call).

        Args:
            texts: Texts to embed (must be <= batch_size).
            input_type: Type of texts.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        try:
            result = await self._async_client.embed(
                texts=texts,
                model=self.model,
                input_type=input_type,
            )
            return result.embeddings
        except voyageai.error.InvalidRequestError as e:
            raise VoyageEmbeddingError(f"Invalid request: {e}") from e
        except Exception as e:
            raise VoyageEmbeddingError(f"Batch embedding failed: {e}") from e

    async def embed_batch(
        self,
        texts: list[str],
        input_type: Literal["document", "query"] = "document",
        parallel: bool = True,
    ) -> list[list[float]]:
        """Embed multiple texts with automatic batching.

        Automatically splits texts into batches of batch_size and processes
        them. Can process batches in parallel or sequentially.

        Args:
            texts: List of texts to embed.
            input_type: Type of texts - "document" for content, "query" for search.
            parallel: Process batches in parallel (faster) or sequential (rate-limit safe).

        Returns:
            List of embedding vectors in same order as input texts.

        Raises:
            VoyageEmbeddingError: On API error after retries.
        """
        if not texts:
            return []

        # Split into batches
        batches: list[list[str]] = []
        for i in range(0, len(texts), self.batch_size):
            batches.append(texts[i : i + self.batch_size])

        logger.info(
            f"Embedding {len(texts)} texts in {len(batches)} batches "
            f"(batch_size={self.batch_size}, parallel={parallel})"
        )

        if parallel and len(batches) > 1:
            # Process all batches in parallel
            tasks = [self._embed_batch_chunk(batch, input_type) for batch in batches]
            results = await asyncio.gather(*tasks)
        else:
            # Process batches sequentially (safer for rate limits)
            results = []
            for batch in batches:
                result = await self._embed_batch_chunk(batch, input_type)
                results.append(result)

        # Flatten results
        all_embeddings: list[list[float]] = []
        for batch_result in results:
            all_embeddings.extend(batch_result)

        return all_embeddings

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def health_check(self) -> bool:
        """Check if Voyage AI service is reachable.

        Returns:
            True if healthy (can embed a test text).
        """
        try:
            await self.embed_text("health check", input_type="document")
            return True
        except Exception as e:
            logger.warning(f"Voyage health check failed: {e}")
            return False

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text (rough approximation).

        Voyage uses its own tokenizer, but ~4 chars per token is a
        reasonable approximation for English text.

        Args:
            text: Text to estimate.

        Returns:
            Estimated token count.
        """
        # Rough approximation: ~4 characters per token
        return len(text) // 4

    def estimate_batch_cost(self, texts: list[str]) -> dict[str, float]:
        """Estimate cost for embedding a batch of texts.

        Args:
            texts: List of texts to embed.

        Returns:
            Dict with estimated tokens and cost (USD).
        """
        total_tokens = sum(self.estimate_tokens(t) for t in texts)

        # Voyage-3.5-lite pricing: $0.02 per 1M tokens (as of research)
        cost_per_million = 0.02
        estimated_cost = (total_tokens / 1_000_000) * cost_per_million

        return {
            "texts_count": len(texts),
            "estimated_tokens": total_tokens,
            "estimated_cost_usd": round(estimated_cost, 6),
            "model": self.model,
        }
