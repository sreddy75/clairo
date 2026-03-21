"""Pinecone vector database client wrapper.

This module provides an async-compatible client wrapper for Pinecone with
index management, vector operations, and search functionality.

Usage:
    from app.core.pinecone_service import PineconeService
    from app.config import get_settings

    settings = get_settings()
    pinecone = PineconeService(settings.pinecone)
    await pinecone.health_check()
"""

import asyncio
from dataclasses import dataclass
from functools import partial
from typing import Any
from uuid import UUID

from pinecone import Pinecone, ServerlessSpec

from app.config import PineconeSettings


@dataclass
class ScoredResult:
    """A search result with score and metadata (mimics Qdrant ScoredPoint)."""

    id: str
    score: float
    payload: dict[str, Any] | None = None


class PineconeService:
    """Pinecone client wrapper with index management and search.

    Note: Pinecone's Python client is synchronous, so we wrap calls
    with asyncio.to_thread for async compatibility.
    """

    # Pinecone serverless spec for index creation
    SERVERLESS_SPEC = ServerlessSpec(cloud="aws", region="us-east-1")

    def __init__(self, settings: PineconeSettings) -> None:
        """Initialize Pinecone client.

        Args:
            settings: Pinecone connection settings.
        """
        self._settings = settings
        self._client: Pinecone | None = None
        self._indexes: dict[str, Any] = {}

    @property
    def client(self) -> Pinecone:
        """Get or create the Pinecone client."""
        if self._client is None:
            api_key = self._settings.api_key.get_secret_value()
            if not api_key:
                raise ValueError("PINECONE_API_KEY is required")
            self._client = Pinecone(api_key=api_key)
        return self._client

    def _get_index(self, name: str) -> Any:
        """Get or create an index connection.

        Args:
            name: Index name.

        Returns:
            Pinecone Index object.
        """
        if name not in self._indexes:
            # Use index host if provided, otherwise use index name
            if self._settings.index_host:
                self._indexes[name] = self.client.Index(host=self._settings.index_host)
            else:
                self._indexes[name] = self.client.Index(name)
        return self._indexes[name]

    async def close(self) -> None:
        """Close the client connection (no-op for Pinecone)."""
        self._indexes.clear()
        self._client = None

    # =========================================================================
    # Health & Status
    # =========================================================================

    async def health_check(self) -> bool:
        """Check if Pinecone is reachable and healthy.

        Returns:
            True if healthy, False otherwise.
        """
        try:
            # List indexes to verify connection
            await asyncio.to_thread(self.client.list_indexes)
            return True
        except Exception:
            return False

    # =========================================================================
    # Index Management
    # =========================================================================

    async def index_exists(self, name: str) -> bool:
        """Check if an index exists.

        Args:
            name: Index name.

        Returns:
            True if index exists.
        """
        try:
            indexes = await asyncio.to_thread(self.client.list_indexes)
            return any(idx.name == name for idx in indexes)
        except Exception:
            return False

    async def create_index(
        self,
        name: str,
        dimension: int = 1024,
        metric: str = "cosine",
    ) -> bool:
        """Create an index if it doesn't exist.

        Args:
            name: Index name.
            dimension: Vector dimensions (default 1024 for voyage-3.5-lite).
            metric: Distance metric (cosine, euclidean, dotproduct).

        Returns:
            True if created, False if already exists.
        """
        if await self.index_exists(name):
            return False

        await asyncio.to_thread(
            self.client.create_index,
            name=name,
            dimension=dimension,
            metric=metric,
            spec=self.SERVERLESS_SPEC,
        )
        return True

    async def delete_index(self, name: str) -> bool:
        """Delete an index.

        Args:
            name: Index name.

        Returns:
            True if deleted, False if didn't exist.
        """
        if not await self.index_exists(name):
            return False

        await asyncio.to_thread(self.client.delete_index, name)
        # Clear cached index connection
        self._indexes.pop(name, None)
        return True

    async def get_index_info(self, name: str) -> dict[str, Any]:
        """Get index statistics and configuration.

        Args:
            name: Index name.

        Returns:
            Index info dict with vectors_count, status, etc.
        """
        index = self._get_index(name)
        stats = await asyncio.to_thread(index.describe_index_stats)
        return {
            "name": name,
            "vectors_count": stats.total_vector_count,
            "dimension": stats.dimension,
            "namespaces": dict(stats.namespaces) if stats.namespaces else {},
        }

    async def list_indexes(self) -> list[str]:
        """List all index names.

        Returns:
            List of index names.
        """
        indexes = await asyncio.to_thread(self.client.list_indexes)
        return [idx.name for idx in indexes]

    # =========================================================================
    # Vector Operations
    # =========================================================================

    async def upsert_vectors(
        self,
        index_name: str,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
        namespace: str = "",
    ) -> None:
        """Upsert vectors with metadata.

        Args:
            index_name: Index name.
            ids: Vector IDs (UUIDs as strings).
            vectors: Embedding vectors.
            payloads: Metadata dicts for each vector.
            namespace: Optional namespace for organizing vectors.
        """
        index = self._get_index(index_name)

        # Build records for upsert
        records = [
            {"id": id_, "values": vec, "metadata": payload}
            for id_, vec, payload in zip(ids, vectors, payloads, strict=True)
        ]

        # Pinecone recommends batching in groups of 100
        batch_size = 100
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            await asyncio.to_thread(partial(index.upsert, vectors=batch, namespace=namespace))

    async def delete_vectors(
        self,
        index_name: str,
        ids: list[str],
        namespace: str = "",
    ) -> None:
        """Delete vectors by ID.

        Args:
            index_name: Index name.
            ids: List of vector IDs to delete.
            namespace: Optional namespace.
        """
        index = self._get_index(index_name)
        await asyncio.to_thread(partial(index.delete, ids=ids, namespace=namespace))

    async def fetch_vectors(
        self,
        index_name: str,
        ids: list[str],
        namespace: str = "",
    ) -> dict[str, Any]:
        """Retrieve vectors by ID.

        Args:
            index_name: Index name.
            ids: List of vector IDs to retrieve.
            namespace: Optional namespace.

        Returns:
            Dict mapping ID to vector data.
        """
        index = self._get_index(index_name)
        result = await asyncio.to_thread(partial(index.fetch, ids=ids, namespace=namespace))
        return result.vectors

    # =========================================================================
    # Search
    # =========================================================================

    async def search(
        self,
        index_name: str,
        query_vector: list[float],
        namespace: str = "",
        filter: dict[str, Any] | None = None,
        limit: int = 10,
        include_metadata: bool = True,
    ) -> list[ScoredResult]:
        """Vector similarity search with optional filtering.

        Args:
            index_name: Index name.
            query_vector: Query embedding vector.
            namespace: Optional namespace to search in.
            filter: Optional metadata filter dict.
            limit: Maximum results to return.
            include_metadata: Include metadata in results.

        Returns:
            List of ScoredResult sorted by score descending.
        """
        index = self._get_index(index_name)

        result = await asyncio.to_thread(
            partial(
                index.query,
                vector=query_vector,
                namespace=namespace,
                filter=filter,
                top_k=limit,
                include_metadata=include_metadata,
            )
        )

        return [
            ScoredResult(
                id=match.id,
                score=match.score,
                payload=dict(match.metadata) if match.metadata else None,
            )
            for match in result.matches
        ]

    async def search_multi_namespace(
        self,
        index_name: str,
        namespaces: list[str],
        query_vector: list[float],
        filters: dict[str, dict[str, Any]] | None = None,
        limit_per_namespace: int = 5,
        total_limit: int | None = None,
        score_threshold: float | None = None,
    ) -> list[ScoredResult]:
        """Search multiple namespaces in parallel.

        In Pinecone, we use namespaces instead of multiple indexes
        (more cost-effective for serverless).

        Args:
            index_name: Index name.
            namespaces: List of namespaces to search.
            query_vector: Query embedding vector.
            filters: Optional dict mapping namespace to filter.
            limit_per_namespace: Max results per namespace.
            total_limit: Max total results (after merging).
            score_threshold: Minimum similarity score.

        Returns:
            Merged and sorted list of ScoredResult.
        """
        # Search all namespaces in parallel
        tasks = [
            self.search(
                index_name=index_name,
                query_vector=query_vector,
                namespace=ns,
                filter=filters.get(ns) if filters else None,
                limit=limit_per_namespace,
                include_metadata=True,
            )
            for ns in namespaces
        ]

        results = await asyncio.gather(*tasks)

        # Flatten and add namespace info to payload
        all_results: list[ScoredResult] = []
        for ns, points in zip(namespaces, results, strict=True):
            for point in points:
                # Apply score threshold if specified
                if score_threshold and point.score < score_threshold:
                    continue
                # Add namespace to payload for identification
                if point.payload:
                    point.payload["_collection"] = ns
                else:
                    point.payload = {"_collection": ns}
                all_results.append(point)

        # Sort by score descending
        all_results.sort(key=lambda p: p.score, reverse=True)

        # Apply total limit
        if total_limit:
            all_results = all_results[:total_limit]

        return all_results

    # =========================================================================
    # Filter Builders (convenience methods)
    # =========================================================================

    @staticmethod
    def build_filter(
        must: dict[str, Any] | None = None,
        must_not: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a Pinecone filter from conditions.

        Pinecone uses a simpler filter syntax than Qdrant.

        Args:
            must: Conditions that must match (AND).
            must_not: Conditions that must not match.

        Returns:
            Pinecone filter dict.
        """
        filter_dict: dict[str, Any] = {}

        if must:
            filter_dict.update(must)

        if must_not:
            for key, value in must_not.items():
                filter_dict[key] = {"$ne": value}

        return filter_dict if filter_dict else {}

    @staticmethod
    def match_value(field: str, value: str | int | bool) -> dict[str, Any]:
        """Create exact match condition.

        Args:
            field: Metadata field name.
            value: Value to match.

        Returns:
            Filter condition dict.
        """
        return {field: {"$eq": value}}

    @staticmethod
    def match_any(field: str, values: list[str]) -> dict[str, Any]:
        """Create match-any condition (value in list).

        Args:
            field: Metadata field name.
            values: List of values to match any.

        Returns:
            Filter condition dict.
        """
        return {field: {"$in": values}}


# Type alias for UUID to string conversion
def uuid_to_str(uuid: UUID) -> str:
    """Convert UUID to string for Pinecone vector ID."""
    return str(uuid)
