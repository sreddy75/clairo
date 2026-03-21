"""Idempotent document ingestion manager for the knowledge base.

Wraps document-level idempotency logic so that repeated ingestion of the
same content is safe and efficient. Uses natural keys and document hashes
to decide whether to skip, replace, or insert documents.

All DB operations happen within the caller's transaction (session).
Pinecone upserts use deterministic vector IDs, making them inherently
idempotent on retry.
"""

from __future__ import annotations

import hashlib
import logging
import re
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pinecone_service import PineconeService
from app.modules.knowledge.chunkers.base import ChunkResult
from app.modules.knowledge.models import ContentChunk
from app.modules.knowledge.repository import BM25IndexRepository, ContentChunkRepository

logger = logging.getLogger(__name__)


class IngestDecision(str, Enum):
    """Decision for whether to ingest a document."""

    SKIP = "skip"
    REPLACE = "replace"
    INSERT = "insert"


class IngestionManager:
    """Manages idempotent document ingestion into Pinecone and PostgreSQL.

    Uses natural keys (e.g. ``legislation:C1936A00027:s109D``) and document
    hashes (SHA-256 of raw content) to decide whether a document should be
    skipped, replaced, or inserted fresh.
    """

    def __init__(
        self,
        session: AsyncSession,
        pinecone: PineconeService,
        index_name: str,
        namespace: str,
    ) -> None:
        self._session = session
        self._pinecone = pinecone
        self._index_name = index_name
        self._namespace = namespace
        self._chunk_repo = ContentChunkRepository(session)
        self._bm25_repo = BM25IndexRepository(session)

    # ------------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------------

    async def should_ingest(self, natural_key: str, document_hash: str) -> IngestDecision:
        """Determine whether a document needs ingestion.

        Args:
            natural_key: Stable identifier for the document.
            document_hash: SHA-256 hash of the full raw content.

        Returns:
            INSERT if the document is new, SKIP if unchanged, REPLACE if
            the content has changed.
        """
        existing_chunks = await self._chunk_repo.get_by_natural_key(natural_key)
        if not existing_chunks:
            return IngestDecision.INSERT

        # Compare document hash from first existing chunk
        if existing_chunks[0].document_hash == document_hash:
            return IngestDecision.SKIP

        return IngestDecision.REPLACE

    # ------------------------------------------------------------------
    # Insert
    # ------------------------------------------------------------------

    async def insert_document(
        self,
        natural_key: str,
        document_hash: str,
        chunks: list[ChunkResult],
        vectors: list[list[float]],
        source_id: UUID,
        collection_name: str,
        source_url: str,
        title: str,
        source_type: str,
        metadata: dict | None = None,
    ) -> list[ContentChunk]:
        """Insert a new document's chunks and vectors.

        Args:
            natural_key: Stable identifier for the document.
            document_hash: SHA-256 of the full raw content.
            chunks: Chunked content from a structured chunker.
            vectors: Embedding vectors corresponding to each chunk.
            source_id: FK to knowledge_sources.
            collection_name: Pinecone namespace / collection name.
            source_url: Origin URL of the document.
            title: Document title.
            source_type: E.g. ``legislation``, ``ruling``, ``case_law``.
            metadata: Optional extra metadata to merge into each chunk.

        Returns:
            List of created ContentChunk ORM objects.
        """
        return await self._insert_chunks_and_vectors(
            natural_key=natural_key,
            document_hash=document_hash,
            chunks=chunks,
            vectors=vectors,
            source_id=source_id,
            collection_name=collection_name,
            source_url=source_url,
            title=title,
            source_type=source_type,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Replace
    # ------------------------------------------------------------------

    async def replace_document(
        self,
        natural_key: str,
        new_chunks: list[ChunkResult],
        new_vectors: list[list[float]],
        source_id: UUID,
        collection_name: str,
        source_url: str,
        title: str,
        source_type: str,
        document_hash: str,
        metadata: dict | None = None,
    ) -> list[ContentChunk]:
        """Atomically replace an existing document's chunks and vectors.

        Deletes old Pinecone vectors and DB rows, then inserts new ones.
        The caller is responsible for committing the session.

        Args:
            natural_key: Stable identifier for the document.
            new_chunks: Replacement chunked content.
            new_vectors: Replacement embedding vectors.
            source_id: FK to knowledge_sources.
            collection_name: Pinecone namespace / collection name.
            source_url: Origin URL of the document.
            title: Document title.
            source_type: E.g. ``legislation``, ``ruling``, ``case_law``.
            document_hash: SHA-256 of the new raw content.
            metadata: Optional extra metadata to merge into each chunk.

        Returns:
            List of newly created ContentChunk ORM objects.
        """
        # Collect old Pinecone vector IDs before deleting DB rows
        old_chunks = await self._chunk_repo.get_by_natural_key(natural_key)
        old_vector_ids = [c.qdrant_point_id for c in old_chunks if c.qdrant_point_id]

        # Delete old vectors from Pinecone
        if old_vector_ids:
            await self._pinecone.delete_vectors(
                index_name=self._index_name,
                ids=old_vector_ids,
                namespace=self._namespace,
            )
            logger.info(
                "Deleted %d old Pinecone vectors for natural_key=%s",
                len(old_vector_ids),
                natural_key,
            )

        # Delete old DB rows (cascades to BM25 entries)
        deleted_count = await self._chunk_repo.delete_by_natural_key(natural_key)
        logger.info(
            "Deleted %d old DB chunks for natural_key=%s",
            deleted_count,
            natural_key,
        )

        # Insert replacement chunks and vectors
        return await self._insert_chunks_and_vectors(
            natural_key=natural_key,
            document_hash=document_hash,
            chunks=new_chunks,
            vectors=new_vectors,
            source_id=source_id,
            collection_name=collection_name,
            source_url=source_url,
            title=title,
            source_type=source_type,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _insert_chunks_and_vectors(
        self,
        natural_key: str,
        document_hash: str,
        chunks: list[ChunkResult],
        vectors: list[list[float]],
        source_id: UUID,
        collection_name: str,
        source_url: str,
        title: str,
        source_type: str,
        metadata: dict | None = None,
    ) -> list[ContentChunk]:
        """Create ContentChunk rows and upsert vectors to Pinecone.

        Generates deterministic Pinecone vector IDs of the form
        ``{source_type}:{natural_key}:{chunk_index}`` so that repeated
        upserts are safe.

        Args:
            natural_key: Stable identifier for the document.
            document_hash: SHA-256 of the full raw content.
            chunks: Chunked content from a structured chunker.
            vectors: Embedding vectors, one per chunk.
            source_id: FK to knowledge_sources.
            collection_name: Pinecone namespace / collection name.
            source_url: Origin URL of the document.
            title: Document title.
            source_type: E.g. ``legislation``, ``ruling``, ``case_law``.
            metadata: Optional extra metadata dict merged into each chunk.

        Returns:
            List of created ContentChunk ORM objects.
        """
        extra = metadata or {}
        pinecone_ids: list[str] = []
        pinecone_payloads: list[dict] = []
        db_chunks: list[ContentChunk] = []

        for idx, (chunk, _vector) in enumerate(zip(chunks, vectors, strict=True)):
            # Deterministic vector ID for idempotent upserts
            vector_id = f"{source_type}:{natural_key}:{idx}"
            chunk_uuid = uuid4()

            db_chunk = ContentChunk(
                id=chunk_uuid,
                source_id=source_id,
                qdrant_point_id=vector_id,
                collection_name=collection_name,
                content_hash=chunk.content_hash,
                source_url=source_url,
                title=title,
                source_type=source_type,
                # Spec 045 structured metadata
                content_type=chunk.content_type,
                section_ref=chunk.section_ref,
                cross_references=chunk.cross_references or None,
                defined_terms_used=chunk.defined_terms_used or None,
                topic_tags=chunk.topic_tags or None,
                natural_key=natural_key,
                document_hash=document_hash,
                # Merge any extra metadata fields
                **{
                    k: v
                    for k, v in extra.items()
                    if hasattr(ContentChunk, k)
                    and k
                    not in {
                        "id",
                        "source_id",
                        "qdrant_point_id",
                        "collection_name",
                        "content_hash",
                        "source_url",
                        "title",
                        "source_type",
                        "content_type",
                        "section_ref",
                        "cross_references",
                        "defined_terms_used",
                        "topic_tags",
                        "natural_key",
                        "document_hash",
                        "created_at",
                        "updated_at",
                    }
                },
            )
            await self._chunk_repo.create(db_chunk)
            db_chunks.append(db_chunk)

            # Build Pinecone payload (filter out None values)
            # Truncate text to stay under Pinecone's 40KB metadata limit
            MAX_TEXT_BYTES = 30_000
            chunk_text = chunk.text
            if len(chunk_text.encode("utf-8")) > MAX_TEXT_BYTES:
                chunk_text = chunk_text[: MAX_TEXT_BYTES // 4]  # conservative truncation
                logger.warning(
                    "Truncated text for vector %s (original too large for Pinecone metadata)",
                    f"{source_type}:{natural_key}:{idx}",
                )
            payload: dict = {
                "chunk_id": str(chunk_uuid),
                "source_id": str(source_id),
                "source_url": source_url,
                "title": title,
                "source_type": source_type,
                "content_type": chunk.content_type,
                "section_ref": chunk.section_ref,
                "natural_key": natural_key,
                "document_hash": document_hash,
                "text": chunk_text,
                "_collection": collection_name,
            }
            if chunk.topic_tags:
                payload["topic_tags"] = chunk.topic_tags
            if chunk.cross_references:
                payload["cross_references"] = chunk.cross_references
            # Merge caller-supplied metadata into Pinecone payload
            for k, v in extra.items():
                if v is not None and k not in payload:
                    # Convert date/datetime to ISO string for Pinecone
                    payload[k] = v.isoformat() if hasattr(v, "isoformat") else v
            # Strip any remaining None values
            payload = {k: v for k, v in payload.items() if v is not None}

            pinecone_ids.append(vector_id)
            pinecone_payloads.append(payload)

        # Batch upsert to Pinecone (service handles batching in groups of 100)
        if pinecone_ids:
            await self._pinecone.upsert_vectors(
                index_name=self._index_name,
                ids=pinecone_ids,
                vectors=vectors,
                payloads=pinecone_payloads,
                namespace=self._namespace,
            )
            logger.info(
                "Upserted %d vectors for natural_key=%s",
                len(pinecone_ids),
                natural_key,
            )

        # Create BM25 index entries for hybrid search
        for db_chunk, payload in zip(db_chunks, pinecone_payloads, strict=True):
            text = payload.get("text", "")
            if not text:
                continue
            tokens = re.findall(r"\w+", text.lower())
            section_refs = re.findall(
                r"(?:s(?:ection)?\s*\d+[\w-]*|"
                r"[Dd]iv(?:ision)?\s*\d+[\w]*|"
                r"[Pp]art\s+\d+[\w-]*)",
                text,
            )
            section_refs = list({ref.strip().lower() for ref in section_refs})
            await self._bm25_repo.upsert(
                chunk_id=db_chunk.id,
                collection_name=collection_name,
                tokens=tokens,
                section_refs=section_refs,
            )
        logger.info(
            "Created %d BM25 entries for natural_key=%s",
            len(db_chunks),
            natural_key,
        )

        return db_chunks

    # ------------------------------------------------------------------
    # Static utilities
    # ------------------------------------------------------------------

    @staticmethod
    def build_natural_key(source_type: str, identifier: str) -> str:
        """Build a stable natural key for a document.

        Key format by source type:
        - legislation: ``legislation:{act_id}:{section_ref}``
        - ruling: ``ruling:{ruling_number}``
        - case_law: ``case_law:{case_citation}``
        - other: ``other:{sha256(source_url)}``

        Args:
            source_type: One of ``legislation``, ``ruling``, ``case_law``,
                or any other string.
            identifier: Type-specific identifier. For legislation pass
                ``{act_id}:{section_ref}``, for rulings the ruling number,
                for case law the citation, and for other types the source URL.

        Returns:
            Deterministic natural key string.
        """
        if source_type == "legislation":
            # identifier should already be "{act_id}:{section_ref}"
            return f"legislation:{identifier}"
        elif source_type == "ruling":
            return f"ruling:{identifier}"
        elif source_type == "case_law":
            return f"case_law:{identifier}"
        else:
            url_hash = hashlib.sha256(identifier.encode()).hexdigest()
            return f"other:{url_hash}"

    @staticmethod
    def compute_document_hash(content: str) -> str:
        """Compute SHA-256 hash of the full raw content string."""
        return hashlib.sha256(content.encode()).hexdigest()
