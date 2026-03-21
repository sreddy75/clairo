"""Repository for knowledge base database operations.

Provides CRUD operations for KnowledgeSource, ContentChunk, IngestionJob,
ChatConversation/ChatMessage, LegislationSection, ContentCrossReference,
TaxDomain, BM25IndexEntry, and ScraperCircuitBreakerState.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.knowledge.models import (
    BM25IndexEntry,
    ChatConversation,
    ChatMessage,
    ContentChunk,
    ContentCrossReference,
    IngestionJob,
    KnowledgeSource,
    LegislationSection,
    ScraperCircuitBreakerState,
    TaxDomain,
)


class KnowledgeSourceRepository:
    """Repository for KnowledgeSource operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, source: KnowledgeSource) -> KnowledgeSource:
        """Create a new knowledge source."""
        self.session.add(source)
        await self.session.flush()
        return source

    async def get_by_id(self, source_id: UUID) -> KnowledgeSource | None:
        """Get source by ID."""
        return await self.session.get(KnowledgeSource, source_id)

    async def get_by_name(self, name: str) -> KnowledgeSource | None:
        """Get source by name."""
        result = await self.session.execute(
            select(KnowledgeSource).where(KnowledgeSource.name == name)
        )
        return result.scalar_one_or_none()

    async def get_all(self, active_only: bool = True) -> Sequence[KnowledgeSource]:
        """Get all knowledge sources."""
        query = select(KnowledgeSource)
        if active_only:
            query = query.where(KnowledgeSource.is_active.is_(True))
        query = query.order_by(KnowledgeSource.name)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_collection(self, collection_name: str) -> Sequence[KnowledgeSource]:
        """Get all sources for a specific collection."""
        result = await self.session.execute(
            select(KnowledgeSource)
            .where(KnowledgeSource.collection_name == collection_name)
            .where(KnowledgeSource.is_active.is_(True))
            .order_by(KnowledgeSource.name)
        )
        return result.scalars().all()

    async def update_last_scraped(
        self, source_id: UUID, scraped_at: datetime, error: str | None = None
    ) -> None:
        """Update last scraped timestamp and error."""
        await self.session.execute(
            update(KnowledgeSource)
            .where(KnowledgeSource.id == source_id)
            .values(
                last_scraped_at=scraped_at,
                last_error=error,
                updated_at=datetime.now(tz=UTC),
            )
        )

    async def delete(self, source_id: UUID) -> bool:
        """Delete a knowledge source."""
        source = await self.get_by_id(source_id)
        if source:
            await self.session.delete(source)
            return True
        return False


class ContentChunkRepository:
    """Repository for ContentChunk operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, chunk: ContentChunk) -> ContentChunk:
        """Create a new content chunk."""
        self.session.add(chunk)
        await self.session.flush()
        return chunk

    async def create_many(self, chunks: list[ContentChunk]) -> list[ContentChunk]:
        """Create multiple content chunks."""
        self.session.add_all(chunks)
        await self.session.flush()
        return chunks

    async def get_by_id(self, chunk_id: UUID) -> ContentChunk | None:
        """Get chunk by ID."""
        return await self.session.get(ContentChunk, chunk_id)

    async def get_by_qdrant_id(self, qdrant_point_id: str) -> ContentChunk | None:
        """Get chunk by Qdrant point ID."""
        result = await self.session.execute(
            select(ContentChunk).where(ContentChunk.qdrant_point_id == qdrant_point_id)
        )
        return result.scalar_one_or_none()

    async def get_by_hash(self, content_hash: str) -> ContentChunk | None:
        """Get chunk by content hash (for deduplication).

        Uses first() instead of scalar_one_or_none() to handle the case
        where duplicate hashes exist from parallel ingestion.
        """
        result = await self.session.execute(
            select(ContentChunk).where(ContentChunk.content_hash == content_hash)
        )
        return result.scalars().first()

    async def get_by_source(
        self,
        source_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ContentChunk]:
        """Get chunks for a specific source."""
        result = await self.session.execute(
            select(ContentChunk)
            .where(ContentChunk.source_id == source_id)
            .order_by(ContentChunk.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def get_by_collection(
        self,
        collection_name: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ContentChunk]:
        """Get chunks for a specific collection."""
        result = await self.session.execute(
            select(ContentChunk)
            .where(ContentChunk.collection_name == collection_name)
            .order_by(ContentChunk.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def get_by_ruling_number(self, ruling_number: str) -> ContentChunk | None:
        """Get chunk by ruling number."""
        result = await self.session.execute(
            select(ContentChunk).where(ContentChunk.ruling_number == ruling_number)
        )
        return result.scalar_one_or_none()

    async def count_by_source(self, source_id: UUID) -> int:
        """Count chunks for a source."""
        result = await self.session.execute(
            select(func.count(ContentChunk.id)).where(ContentChunk.source_id == source_id)
        )
        return result.scalar_one()

    async def count_by_collection(self, collection_name: str) -> int:
        """Count chunks in a collection."""
        result = await self.session.execute(
            select(func.count(ContentChunk.id)).where(
                ContentChunk.collection_name == collection_name
            )
        )
        return result.scalar_one()

    async def mark_superseded(
        self,
        chunk_id: UUID,
        superseded_by: str | None = None,
    ) -> None:
        """Mark a chunk as superseded."""
        await self.session.execute(
            update(ContentChunk)
            .where(ContentChunk.id == chunk_id)
            .values(
                is_superseded=True,
                superseded_by=superseded_by,
                updated_at=datetime.now(tz=UTC),
            )
        )

    async def delete_by_source(self, source_id: UUID) -> int:
        """Delete all chunks for a source. Returns count deleted."""
        # Get count first
        count_result = await self.session.execute(
            select(func.count(ContentChunk.id)).where(ContentChunk.source_id == source_id)
        )
        count = count_result.scalar_one()

        # Delete
        await self.session.execute(delete(ContentChunk).where(ContentChunk.source_id == source_id))

        return count

    async def get_by_section_ref(self, section_ref: str) -> Sequence[ContentChunk]:
        """Get chunks matching a section reference."""
        result = await self.session.execute(
            select(ContentChunk)
            .where(ContentChunk.section_ref == section_ref)
            .order_by(ContentChunk.created_at.desc())
        )
        return result.scalars().all()

    async def get_by_natural_key(self, natural_key: str) -> Sequence[ContentChunk]:
        """Get all chunks for a document by its natural key."""
        result = await self.session.execute(
            select(ContentChunk)
            .where(ContentChunk.natural_key == natural_key)
            .order_by(ContentChunk.created_at.asc())
        )
        return result.scalars().all()

    async def get_by_document_hash(self, document_hash: str) -> ContentChunk | None:
        """Check if a document with this hash exists."""
        result = await self.session.execute(
            select(ContentChunk).where(ContentChunk.document_hash == document_hash).limit(1)
        )
        return result.scalars().first()

    async def browse_by_collection(
        self,
        collection_name: str,
        page: int = 1,
        page_size: int = 20,
        source_type: str | None = None,
        search: str | None = None,
    ) -> tuple[Sequence[ContentChunk], int]:
        """Browse content chunks in a collection with filtering and pagination.

        Args:
            collection_name: Collection/namespace name to filter by.
            page: Page number (1-based).
            page_size: Number of items per page.
            source_type: Optional source_type filter.
            search: Optional ILIKE search on title.

        Returns:
            Tuple of (chunks, total_count).
        """
        base_filter = ContentChunk.collection_name == collection_name
        conditions = [base_filter]

        if source_type:
            conditions.append(ContentChunk.source_type == source_type)
        if search:
            conditions.append(ContentChunk.title.ilike(f"%{search}%"))

        # Get total count
        count_query = select(func.count(ContentChunk.id)).where(*conditions)
        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one()

        # Get paginated results
        offset = (page - 1) * page_size
        data_query = (
            select(ContentChunk)
            .where(*conditions)
            .order_by(ContentChunk.created_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        data_result = await self.session.execute(data_query)
        chunks = data_result.scalars().all()

        return chunks, total

    async def source_type_counts_by_collection(
        self,
        collection_name: str,
    ) -> dict[str, int]:
        """Get count of chunks per source_type in a collection.

        Returns:
            Dict mapping source_type to chunk count.
        """
        result = await self.session.execute(
            select(ContentChunk.source_type, func.count(ContentChunk.id))
            .where(ContentChunk.collection_name == collection_name)
            .group_by(ContentChunk.source_type)
        )
        return {row[0]: row[1] for row in result.all()}

    async def delete_by_natural_key(self, natural_key: str) -> int:
        """Delete all chunks for a document by natural key. Returns count deleted."""
        count_result = await self.session.execute(
            select(func.count(ContentChunk.id)).where(ContentChunk.natural_key == natural_key)
        )
        count = count_result.scalar_one()
        if count > 0:
            await self.session.execute(
                delete(ContentChunk).where(ContentChunk.natural_key == natural_key)
            )
        return count


class IngestionJobRepository:
    """Repository for IngestionJob operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, job: IngestionJob) -> IngestionJob:
        """Create a new ingestion job."""
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_by_id(self, job_id: UUID, with_source: bool = False) -> IngestionJob | None:
        """Get job by ID."""
        query = select(IngestionJob).where(IngestionJob.id == job_id)
        if with_source:
            query = query.options(selectinload(IngestionJob.source))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_source(
        self,
        source_id: UUID,
        limit: int = 20,
        status: str | None = None,
    ) -> Sequence[IngestionJob]:
        """Get jobs for a specific source."""
        query = (
            select(IngestionJob)
            .where(IngestionJob.source_id == source_id)
            .order_by(IngestionJob.created_at.desc())
            .limit(limit)
        )
        if status:
            query = query.where(IngestionJob.status == status)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_recent(
        self,
        limit: int = 20,
        status: str | None = None,
        with_source: bool = True,
    ) -> Sequence[IngestionJob]:
        """Get recent jobs across all sources."""
        query = select(IngestionJob).order_by(IngestionJob.created_at.desc()).limit(limit)
        if status:
            query = query.where(IngestionJob.status == status)
        if with_source:
            query = query.options(selectinload(IngestionJob.source))
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_running(self) -> Sequence[IngestionJob]:
        """Get all currently running jobs."""
        result = await self.session.execute(
            select(IngestionJob)
            .where(IngestionJob.status == "running")
            .options(selectinload(IngestionJob.source))
        )
        return result.scalars().all()

    async def update_status(
        self,
        job_id: UUID,
        status: str,
        **kwargs: int | datetime | list | None,
    ) -> None:
        """Update job status and optional fields."""
        values = {"status": status, **kwargs}
        await self.session.execute(
            update(IngestionJob).where(IngestionJob.id == job_id).values(**values)
        )

    async def start_job(self, job_id: UUID) -> None:
        """Mark job as started."""
        await self.update_status(
            job_id,
            status="running",
            started_at=datetime.now(tz=UTC),
        )

    async def complete_job(
        self,
        job_id: UUID,
        items_processed: int,
        items_added: int,
        items_updated: int,
        items_skipped: int,
        items_failed: int = 0,
        tokens_used: int = 0,
        errors: list | None = None,
    ) -> None:
        """Mark job as completed with statistics."""
        await self.update_status(
            job_id,
            status="completed",
            completed_at=datetime.now(tz=UTC),
            items_processed=items_processed,
            items_added=items_added,
            items_updated=items_updated,
            items_skipped=items_skipped,
            items_failed=items_failed,
            tokens_used=tokens_used,
            errors=errors or [],
        )

    async def fail_job(self, job_id: UUID, errors: list) -> None:
        """Mark job as failed."""
        await self.update_status(
            job_id,
            status="failed",
            completed_at=datetime.now(tz=UTC),
            errors=errors,
        )

    async def delete(self, job_id: UUID) -> bool:
        """Delete an ingestion job."""
        job = await self.get_by_id(job_id)
        if job:
            await self.session.delete(job)
            return True
        return False

    async def update_job_checkpoint(
        self,
        job_id: UUID,
        completed_item: str | None = None,
        failed_item: dict | None = None,
    ) -> None:
        """Append to completed/failed items for checkpoint tracking."""
        job = await self.get_by_id(job_id)
        if not job:
            return

        if completed_item:
            items = list(job.completed_items or [])
            items.append(completed_item)
            await self.session.execute(
                update(IngestionJob).where(IngestionJob.id == job_id).values(completed_items=items)
            )

        if failed_item:
            items = list(job.failed_items or [])
            items.append(failed_item)
            await self.session.execute(
                update(IngestionJob).where(IngestionJob.id == job_id).values(failed_items=items)
            )

    async def get_job_completed_items(self, job_id: UUID) -> set[str]:
        """Get set of completed item keys for resume."""
        job = await self.get_by_id(job_id)
        if not job or not job.completed_items:
            return set()
        return set(job.completed_items)


class LegislationSectionRepository:
    """Repository for LegislationSection operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_section_ref(
        self, section_ref: str, act_id: str | None = None
    ) -> LegislationSection | None:
        """Get section by reference, optionally scoped to act."""
        query = select(LegislationSection).where(
            LegislationSection.section_ref == section_ref,
            LegislationSection.is_current.is_(True),
        )
        if act_id:
            query = query.where(LegislationSection.act_id == act_id)
        result = await self.session.execute(query)
        return result.scalars().first()

    async def upsert(self, data: dict) -> LegislationSection:
        """Insert or update a legislation section."""
        existing = await self.get_by_section_ref(data["section_ref"], data.get("act_id"))
        if existing:
            for key, value in data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            await self.session.flush()
            return existing
        section = LegislationSection(**data)
        self.session.add(section)
        await self.session.flush()
        return section

    async def get_by_act(self, act_id: str) -> Sequence[LegislationSection]:
        """Get all sections for an act."""
        result = await self.session.execute(
            select(LegislationSection)
            .where(LegislationSection.act_id == act_id, LegislationSection.is_current.is_(True))
            .order_by(LegislationSection.section_ref)
        )
        return result.scalars().all()


class ContentCrossReferenceRepository:
    """Repository for ContentCrossReference operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: dict) -> ContentCrossReference:
        """Create a cross-reference."""
        ref = ContentCrossReference(**data)
        self.session.add(ref)
        await self.session.flush()
        return ref

    async def get_by_source_chunk(self, chunk_id: UUID) -> Sequence[ContentCrossReference]:
        """Get all cross-references from a chunk."""
        result = await self.session.execute(
            select(ContentCrossReference).where(ContentCrossReference.source_chunk_id == chunk_id)
        )
        return result.scalars().all()

    async def get_by_target_ref(self, target_section_ref: str) -> Sequence[ContentCrossReference]:
        """Get all cross-references pointing to a section."""
        result = await self.session.execute(
            select(ContentCrossReference).where(
                ContentCrossReference.target_section_ref == target_section_ref
            )
        )
        return result.scalars().all()


class TaxDomainRepository:
    """Repository for TaxDomain operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self) -> Sequence[TaxDomain]:
        """Get all active tax domains ordered by display_order."""
        result = await self.session.execute(
            select(TaxDomain).where(TaxDomain.is_active.is_(True)).order_by(TaxDomain.display_order)
        )
        return result.scalars().all()

    async def get_by_slug(self, slug: str) -> TaxDomain | None:
        """Get a domain by slug."""
        result = await self.session.execute(select(TaxDomain).where(TaxDomain.slug == slug))
        return result.scalar_one_or_none()


class BM25IndexRepository:
    """Repository for BM25IndexEntry operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_collection(self, collection_name: str) -> Sequence[BM25IndexEntry]:
        """Get all BM25 entries for a collection."""
        result = await self.session.execute(
            select(BM25IndexEntry).where(BM25IndexEntry.collection_name == collection_name)
        )
        return result.scalars().all()

    async def upsert(
        self, chunk_id: UUID, collection_name: str, tokens: list, section_refs: list
    ) -> BM25IndexEntry:
        """Insert or update a BM25 index entry."""
        result = await self.session.execute(
            select(BM25IndexEntry).where(BM25IndexEntry.chunk_id == chunk_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.tokens = tokens
            existing.section_refs = section_refs
            await self.session.flush()
            return existing
        entry = BM25IndexEntry(
            chunk_id=chunk_id,
            collection_name=collection_name,
            tokens=tokens,
            section_refs=section_refs,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def delete_by_chunk(self, chunk_id: UUID) -> None:
        """Delete BM25 entry for a chunk."""
        await self.session.execute(
            delete(BM25IndexEntry).where(BM25IndexEntry.chunk_id == chunk_id)
        )


class CircuitBreakerRepository:
    """Repository for ScraperCircuitBreakerState operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_host(self, source_host: str) -> ScraperCircuitBreakerState | None:
        """Get circuit breaker state for a host."""
        result = await self.session.execute(
            select(ScraperCircuitBreakerState).where(
                ScraperCircuitBreakerState.source_host == source_host
            )
        )
        return result.scalar_one_or_none()

    async def upsert(self, source_host: str, **kwargs: Any) -> ScraperCircuitBreakerState:
        """Insert or update circuit breaker state."""
        existing = await self.get_by_host(source_host)
        if existing:
            for key, value in kwargs.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            await self.session.flush()
            return existing
        state = ScraperCircuitBreakerState(source_host=source_host, **kwargs)
        self.session.add(state)
        await self.session.flush()
        return state


class FreshnessReportRepository:
    """Repository for content freshness reporting."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_freshness_report(self) -> list[dict]:
        """Get aggregated freshness report per source."""
        result = await self.session.execute(
            select(
                KnowledgeSource.source_type,
                KnowledgeSource.name,
                KnowledgeSource.last_scraped_at,
                func.count(ContentChunk.id).label("chunk_count"),
                KnowledgeSource.last_error,
            )
            .outerjoin(ContentChunk, ContentChunk.source_id == KnowledgeSource.id)
            .where(KnowledgeSource.is_active.is_(True))
            .group_by(
                KnowledgeSource.source_type,
                KnowledgeSource.name,
                KnowledgeSource.last_scraped_at,
                KnowledgeSource.last_error,
            )
        )
        rows = result.all()
        report = []
        for row in rows:
            source_type, name, last_scraped, chunk_count, last_error = row
            if last_error:
                status = "error"
            elif last_scraped is None:
                status = "never_ingested"
            else:
                from datetime import timedelta

                age = datetime.now(tz=UTC) - last_scraped
                if age < timedelta(days=7):
                    status = "fresh"
                else:
                    status = "stale"
            report.append(
                {
                    "source_type": source_type,
                    "source_name": name,
                    "last_ingested_at": last_scraped.isoformat() if last_scraped else None,
                    "chunk_count": chunk_count,
                    "error_count": 1 if last_error else 0,
                    "freshness_status": status,
                }
            )
        return report


class ChatConversationRepository:
    """Repository for ChatConversation operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: str,
        title: str = "New Conversation",
        client_id: UUID | None = None,
    ) -> ChatConversation:
        """Create a new conversation.

        Args:
            user_id: Clerk user ID.
            title: Conversation title.
            client_id: Optional client ID for client-context chat.
        """
        conversation = ChatConversation(
            user_id=user_id,
            title=title,
            client_id=client_id,
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def get_by_id(
        self, conversation_id: UUID, with_messages: bool = False
    ) -> ChatConversation | None:
        """Get conversation by ID."""
        query = select(ChatConversation).where(ChatConversation.id == conversation_id)
        if with_messages:
            query = query.options(selectinload(ChatConversation.messages))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        client_id: UUID | None = None,
        general_only: bool = False,
    ) -> Sequence[ChatConversation]:
        """Get conversations for a user, ordered by most recent.

        Args:
            user_id: Clerk user ID.
            limit: Max conversations to return.
            offset: Pagination offset.
            client_id: Filter to specific client (optional).
            general_only: If True, only return conversations without a client.
        """
        query = select(ChatConversation).where(ChatConversation.user_id == user_id)

        if client_id:
            query = query.where(ChatConversation.client_id == client_id)
        elif general_only:
            query = query.where(ChatConversation.client_id.is_(None))

        query = query.order_by(ChatConversation.updated_at.desc()).limit(limit).offset(offset)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_user_with_clients(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[tuple[ChatConversation, str | None]]:
        """Get conversations for a user with client names.

        Returns tuples of (conversation, client_name).
        """
        from app.modules.integrations.xero.models import XeroClient

        query = (
            select(ChatConversation, XeroClient.name)
            .outerjoin(XeroClient, ChatConversation.client_id == XeroClient.id)
            .where(ChatConversation.user_id == user_id)
            .order_by(ChatConversation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return list(result.all())

    async def get_user_clients(
        self,
        user_id: str,
    ) -> list[tuple[UUID, str, int]]:
        """Get distinct clients that a user has conversations with.

        Returns tuples of (client_id, client_name, conversation_count).
        """
        from app.modules.integrations.xero.models import XeroClient

        query = (
            select(
                ChatConversation.client_id,
                XeroClient.name,
                func.count(ChatConversation.id).label("count"),
            )
            .join(XeroClient, ChatConversation.client_id == XeroClient.id)
            .where(
                ChatConversation.user_id == user_id,
                ChatConversation.client_id.isnot(None),
            )
            .group_by(ChatConversation.client_id, XeroClient.name)
            .order_by(func.max(ChatConversation.updated_at).desc())
        )
        result = await self.session.execute(query)
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def update_title(self, conversation_id: UUID, title: str) -> None:
        """Update conversation title."""
        await self.session.execute(
            update(ChatConversation)
            .where(ChatConversation.id == conversation_id)
            .values(title=title, updated_at=datetime.now(tz=UTC))
        )

    async def touch(self, conversation_id: UUID) -> None:
        """Update the updated_at timestamp."""
        await self.session.execute(
            update(ChatConversation)
            .where(ChatConversation.id == conversation_id)
            .values(updated_at=datetime.now(tz=UTC))
        )

    async def delete(self, conversation_id: UUID) -> bool:
        """Delete a conversation and all its messages."""
        conversation = await self.get_by_id(conversation_id)
        if conversation:
            await self.session.delete(conversation)
            return True
        return False

    async def count_by_user(self, user_id: str) -> int:
        """Count conversations for a user."""
        result = await self.session.execute(
            select(func.count(ChatConversation.id)).where(ChatConversation.user_id == user_id)
        )
        return result.scalar_one()


class ChatMessageRepository:
    """Repository for ChatMessage operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        citations: list[dict] | None = None,
        metadata: dict | None = None,
    ) -> ChatMessage:
        """Create a new message.

        Args:
            conversation_id: Parent conversation ID.
            role: Message role (user or assistant).
            content: Message content.
            citations: Optional citations for assistant messages.
            metadata: Optional client context metadata.
        """
        message = ChatMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            citations=citations,
            metadata=metadata,
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def get_by_conversation(
        self,
        conversation_id: UUID,
        limit: int | None = None,
    ) -> Sequence[ChatMessage]:
        """Get messages for a conversation, ordered by creation time."""
        query = (
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.asc())
        )
        if limit:
            query = query.limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_recent(
        self,
        conversation_id: UUID,
        limit: int = 10,
    ) -> Sequence[ChatMessage]:
        """Get most recent messages for context building."""
        result = await self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        # Reverse to get chronological order
        return list(reversed(result.scalars().all()))

    async def count_by_conversation(self, conversation_id: UUID) -> int:
        """Count messages in a conversation."""
        result = await self.session.execute(
            select(func.count(ChatMessage.id)).where(ChatMessage.conversation_id == conversation_id)
        )
        return result.scalar_one()
