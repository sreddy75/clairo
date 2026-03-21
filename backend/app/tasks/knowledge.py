"""Celery tasks for knowledge base ingestion.

Provides background tasks for:
- Ingesting content from configured sources
- Processing and chunking content
- Embedding and storing in Pinecone
- Tracking job progress

Usage:
    from app.tasks.knowledge import ingest_source
    result = ingest_source.delay(source_id, job_id)
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from celery import Task

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Source definitions for Spec 045 ingestion tasks.
# Each maps to a KnowledgeSource row (get-or-created on first use).
_SPEC045_SOURCES: dict[str, dict[str, str]] = {
    "ato_legal_db": {
        "name": "ATO Legal Database",
        "source_type": "ato_legal_db",
        "base_url": "https://www.ato.gov.au/law/view",
        "collection_name": "compliance_knowledge",
    },
    "legislation": {
        "name": "Australian Legislation",
        "source_type": "legislation",
        "base_url": "https://www.legislation.gov.au",
        "collection_name": "compliance_knowledge",
    },
    "case_law": {
        "name": "Australian Case Law",
        "source_type": "case_law",
        "base_url": "https://www.fedcourt.gov.au",
        "collection_name": "compliance_knowledge",
    },
    "tpb_treasury": {
        "name": "TPB & Treasury",
        "source_type": "tpb_treasury",
        "base_url": "https://www.tpb.gov.au",
        "collection_name": "compliance_knowledge",
    },
    "ato_rss": {
        "name": "ATO RSS Feeds",
        "source_type": "ato_rss",
        "base_url": "https://www.ato.gov.au",
        "collection_name": "compliance_knowledge",
    },
}


async def _get_or_create_source(db, source_key: str) -> "KnowledgeSource":
    """Get or create a KnowledgeSource record for a Spec 045 ingestion source.

    Args:
        db: Async database session.
        source_key: Key into _SPEC045_SOURCES (e.g. 'ato_legal_db').

    Returns:
        KnowledgeSource ORM instance.
    """
    from app.modules.knowledge.models import KnowledgeSource
    from app.modules.knowledge.repository import KnowledgeSourceRepository

    config = _SPEC045_SOURCES[source_key]
    repo = KnowledgeSourceRepository(db)
    source = await repo.get_by_name(config["name"])
    if source:
        return source

    source = KnowledgeSource(
        name=config["name"],
        source_type=config["source_type"],
        base_url=config["base_url"],
        collection_name=config["collection_name"],
        is_active=True,
    )
    source = await repo.create(source)
    await db.flush()
    return source


def run_async(coro):
    """Run an async function from sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    else:
        return asyncio.ensure_future(coro)


async def _ingest_source_async(
    source_id: str,
    job_id: str,
    task: Task,
) -> dict[str, Any]:
    """Async implementation of source ingestion.

    Args:
        source_id: UUID of the KnowledgeSource.
        job_id: UUID of the IngestionJob.
        task: Celery task instance for progress updates.

    Returns:
        Dict with ingestion results.
    """
    from app.config import get_settings
    from app.core.pinecone_service import PineconeService
    from app.core.voyage import VoyageService
    from app.database import get_celery_db_context
    from app.modules.knowledge.chunker import SemanticChunker
    from app.modules.knowledge.collections import INDEX_NAME, get_namespace_with_env
    from app.modules.knowledge.models import ContentChunk
    from app.modules.knowledge.repository import (
        ContentChunkRepository,
        IngestionJobRepository,
        KnowledgeSourceRepository,
    )
    from app.modules.knowledge.scrapers import ATOAPIScraper, ATORSSScraper, ATOWebScraper

    settings = get_settings()

    # Statistics
    stats = {
        "items_processed": 0,
        "items_added": 0,
        "items_updated": 0,
        "items_skipped": 0,
        "items_failed": 0,
        "tokens_used": 0,
        "errors": [],
    }

    # Initialize services
    pinecone = PineconeService(settings.pinecone)
    voyage = VoyageService(settings.voyage)
    chunker = SemanticChunker()

    async with get_celery_db_context() as db:
        source_repo = KnowledgeSourceRepository(db)
        chunk_repo = ContentChunkRepository(db)
        job_repo = IngestionJobRepository(db)

        # Get source configuration
        source = await source_repo.get_by_id(UUID(source_id))
        if not source:
            raise ValueError(f"Source not found: {source_id}")

        # Mark job as running
        await job_repo.start_job(UUID(job_id))
        await db.commit()

        # Select appropriate scraper
        scraper_class = {
            "ato_api": ATOAPIScraper,
            "ato_rss": ATORSSScraper,
            "ato_web": ATOWebScraper,
        }.get(source.source_type)

        if not scraper_class:
            # Non-scrapable sources (static_content, manual, upload_*) don't need ingestion
            logger.info(
                f"Skipping source {source_id}: source type '{source.source_type}' "
                "does not require scraping"
            )
            await job_repo.complete_job(
                UUID(job_id),
                items_processed=0,
                items_added=0,
                items_updated=0,
                items_skipped=0,
                items_failed=0,
                tokens_used=0,
                errors=[],
            )
            await db.commit()
            return stats

        # Initialize scraper
        async with scraper_class(source_config=source.scrape_config) as scraper:
            # Process each piece of content
            async for content in scraper.scrape_all():
                try:
                    stats["items_processed"] += 1

                    # Chunk the content
                    chunks = chunker.chunk_text(
                        content.text,
                        metadata={"source_url": content.source_url},
                    )

                    if not chunks:
                        stats["items_skipped"] += 1
                        continue

                    # Check for existing content by hash (first chunk)
                    existing = await chunk_repo.get_by_hash(chunks[0].content_hash)
                    if existing:
                        stats["items_skipped"] += 1
                        logger.debug(f"Skipping duplicate: {content.source_url}")
                        continue

                    # Generate embeddings for all chunks
                    chunk_texts = [c.text for c in chunks]
                    embeddings = await voyage.embed_batch(chunk_texts, parallel=False)

                    # Estimate tokens used
                    stats["tokens_used"] += sum(voyage.estimate_tokens(t) for t in chunk_texts)

                    # Store each chunk
                    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=False)):
                        chunk_uuid = uuid4()
                        qdrant_point_id = str(chunk_uuid)

                        # Prepare Pinecone metadata
                        metadata = content.to_chunk_payload(
                            chunk_id=str(chunk_uuid),
                            source_id=source_id,
                            chunk_index=i,
                        )
                        metadata["text"] = chunk.text
                        metadata["_collection"] = source.collection_name  # Base name for queries

                        # Filter out None values (Pinecone doesn't accept null)
                        metadata = {k: v for k, v in metadata.items() if v is not None}

                        # Get environment-aware namespace (e.g., compliance_knowledge_dev)
                        pinecone_namespace = get_namespace_with_env(source.collection_name)

                        # Upsert to Pinecone (using namespace for collection)
                        await pinecone.upsert_vectors(
                            index_name=INDEX_NAME,
                            ids=[qdrant_point_id],
                            vectors=[embedding],
                            payloads=[metadata],
                            namespace=pinecone_namespace,
                        )

                        # Create tracking record in PostgreSQL
                        db_chunk = ContentChunk(
                            id=chunk_uuid,
                            source_id=UUID(source_id),
                            qdrant_point_id=qdrant_point_id,
                            collection_name=source.collection_name,
                            content_hash=chunk.content_hash,
                            source_url=content.source_url,
                            title=content.title,
                            source_type=content.source_type,
                            effective_date=content.effective_date.date()
                            if content.effective_date
                            else None,
                            expiry_date=content.expiry_date.date() if content.expiry_date else None,
                            entity_types=content.entity_types,
                            industries=content.industries,
                            ruling_number=content.ruling_number,
                            is_superseded=content.is_superseded,
                            superseded_by=content.superseded_by,
                        )
                        await chunk_repo.create(db_chunk)

                    stats["items_added"] += 1

                    # Update progress periodically
                    if stats["items_processed"] % 10 == 0:
                        task.update_state(
                            state="PROGRESS",
                            meta={
                                "processed": stats["items_processed"],
                                "added": stats["items_added"],
                                "skipped": stats["items_skipped"],
                            },
                        )
                        await db.commit()

                except Exception as e:
                    stats["items_failed"] += 1
                    error_entry = {
                        "url": content.source_url if content else "unknown",
                        "error": str(e),
                        "timestamp": datetime.now(tz=UTC).isoformat(),
                    }
                    stats["errors"].append(error_entry)
                    logger.warning(f"Failed to process content: {e}")

        # Update source last_scraped
        await source_repo.update_last_scraped(
            UUID(source_id),
            scraped_at=datetime.now(tz=UTC),
            error=stats["errors"][-1]["error"] if stats["errors"] else None,
        )

        # Complete the job
        await job_repo.complete_job(
            UUID(job_id),
            items_processed=stats["items_processed"],
            items_added=stats["items_added"],
            items_updated=stats["items_updated"],
            items_skipped=stats["items_skipped"],
            items_failed=stats["items_failed"],
            tokens_used=stats["tokens_used"],
            errors=stats["errors"][:20],  # Limit stored errors
        )

        await db.commit()

    return stats


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="app.tasks.knowledge.ingest_source",
    max_retries=2,
    default_retry_delay=300,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=1800,
    retry_jitter=True,
    time_limit=3600,  # 1 hour max
    soft_time_limit=3300,  # Soft limit at 55 minutes
)
def ingest_source(
    self: Task,
    source_id: str,
    job_id: str,
) -> dict[str, Any]:
    """Ingest content from a knowledge source.

    Scrapes content, chunks it, generates embeddings, and stores
    in Qdrant with tracking in PostgreSQL.

    Args:
        source_id: UUID of the KnowledgeSource to ingest.
        job_id: UUID of the IngestionJob for tracking.

    Returns:
        Dict with ingestion statistics.
    """
    logger.info(f"Starting ingestion for source {source_id}, job {job_id}")

    try:
        # Run the async ingestion
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_ingest_source_async(source_id, job_id, self))
        finally:
            loop.close()

        logger.info(
            f"Ingestion complete for source {source_id}: "
            f"{result['items_added']} added, {result['items_skipped']} skipped"
        )

        return result

    except Exception as exc:
        logger.error(f"Ingestion failed for source {source_id}: {exc}")
        error_message = str(exc)

        # Mark job as failed
        async def fail_job(error_msg: str) -> None:
            from app.database import get_celery_db_context
            from app.modules.knowledge.repository import IngestionJobRepository

            async with get_celery_db_context() as db:
                job_repo = IngestionJobRepository(db)
                await job_repo.fail_job(
                    UUID(job_id),
                    errors=[
                        {
                            "error": error_msg,
                            "timestamp": datetime.now(tz=UTC).isoformat(),
                        }
                    ],
                )
                await db.commit()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(fail_job(error_message))
        finally:
            loop.close()

        raise


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.knowledge.ingest_all_sources",
    time_limit=7200,  # 2 hours max
)
def ingest_all_sources() -> dict[str, Any]:
    """Ingest content from all active knowledge sources.

    Triggers individual ingestion tasks for each active source.

    Returns:
        Dict with list of started job IDs.
    """

    async def _start_all():
        from app.database import get_celery_db_context
        from app.modules.knowledge.models import IngestionJob
        from app.modules.knowledge.repository import (
            IngestionJobRepository,
            KnowledgeSourceRepository,
        )

        started_jobs = []

        async with get_celery_db_context() as db:
            source_repo = KnowledgeSourceRepository(db)
            job_repo = IngestionJobRepository(db)

            # Get all active sources
            sources = await source_repo.get_all(active_only=True)

            for source in sources:
                # Create job record
                job = IngestionJob(
                    source_id=source.id,
                    status="pending",
                    triggered_by="scheduled",
                )
                created = await job_repo.create(job)
                await db.commit()

                # Queue the ingestion task
                ingest_source.delay(str(source.id), str(created.id))

                started_jobs.append(
                    {
                        "source_id": str(source.id),
                        "source_name": source.name,
                        "job_id": str(created.id),
                    }
                )

        return started_jobs

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        jobs = loop.run_until_complete(_start_all())
    finally:
        loop.close()

    logger.info(f"Started {len(jobs)} ingestion jobs")
    return {"started_jobs": jobs, "count": len(jobs)}


# ---------------------------------------------------------------------------
# Spec 045: ATO Legal Database ingestion
# ---------------------------------------------------------------------------


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="app.tasks.knowledge.ingest_ato_legal_database",
    max_retries=2,
    default_retry_delay=300,
    time_limit=7200,  # 2 hours
    soft_time_limit=7000,
)
def ingest_ato_legal_database(
    self: Task,
    parent_job_id: str | None = None,
    dev_mode: bool = False,
) -> dict[str, Any]:
    """Ingest all rulings from the ATO Legal Database.

    Scrapes ATO rulings (TRs, GSTRs, TDs, etc.), chunks with the ruling
    chunker, generates embeddings, and stores in Pinecone with full metadata.
    Uses IngestionManager for document-level idempotency and checkpoint/resume
    so the job can be retried safely.

    Args:
        parent_job_id: If this is a retry, the ID of the original job whose
            completed_items should be loaded for resume.

    Returns:
        Dict with ingestion statistics.
    """
    logger.info(
        "Starting ATO Legal Database ingestion (parent_job_id=%s, dev_mode=%s)",
        parent_job_id,
        dev_mode,
    )

    async def _run() -> dict[str, Any]:
        import hashlib

        from app.config import get_settings
        from app.core.pinecone_service import PineconeService
        from app.core.voyage import VoyageService
        from app.database import get_celery_db_context
        from app.modules.knowledge.chunkers.base import ChunkResult
        from app.modules.knowledge.collections import INDEX_NAME, get_namespace_with_env
        from app.modules.knowledge.ingestion_manager import IngestDecision, IngestionManager
        from app.modules.knowledge.models import (
            IngestionJob,
        )
        from app.modules.knowledge.repository import (
            BM25IndexRepository,
            ContentChunkRepository,
            ContentCrossReferenceRepository,
            IngestionJobRepository,
        )
        from app.modules.knowledge.scrapers.circuit_breaker import (
            CircuitOpenError,
            ScraperCircuitBreaker,
        )

        settings = get_settings()

        stats: dict[str, Any] = {
            "items_processed": 0,
            "items_added": 0,
            "items_updated": 0,
            "items_skipped": 0,
            "items_failed": 0,
            "tokens_used": 0,
            "errors": [],
        }

        async with get_celery_db_context() as db:
            job_repo = IngestionJobRepository(db)
            chunk_repo = ContentChunkRepository(db)
            bm25_repo = BM25IndexRepository(db)
            xref_repo = ContentCrossReferenceRepository(db)

            # Get or create the knowledge source record
            source = await _get_or_create_source(db, "ato_legal_db")
            collection_name = source.collection_name
            pinecone_namespace = get_namespace_with_env(collection_name)

            # Create the ingestion job record
            job = IngestionJob(
                source_id=source.id,
                status="running",
                triggered_by="manual",
                is_resumable=True,
                parent_job_id=UUID(parent_job_id) if parent_job_id else None,
            )
            job = await job_repo.create(job)
            await job_repo.start_job(job.id)
            await db.commit()

            job_id = job.id

            # Load completed items from parent job for resume support
            completed_items: set[str] = set()
            if parent_job_id:
                completed_items = await job_repo.get_job_completed_items(UUID(parent_job_id))
                logger.info(
                    "Resuming from parent job %s — %d items already completed",
                    parent_job_id,
                    len(completed_items),
                )

            # Initialise services
            pinecone = PineconeService(settings.pinecone)
            voyage = VoyageService(settings.voyage)
            circuit_breaker = ScraperCircuitBreaker(db)
            ingestion_manager = IngestionManager(
                db,
                pinecone,
                INDEX_NAME,
                pinecone_namespace,
            )

            try:
                from app.modules.knowledge.chunkers.ruling import RulingChunker
                from app.modules.knowledge.scrapers.ato_legal_db import (
                    ATOLegalDatabaseScraper,
                )

                # In dev_mode, limit to 2 ruling types with 1 page each
                scraper_config: dict = {}
                if dev_mode:
                    scraper_config = {
                        "ruling_types": ["TXR", "GST"],
                        "max_pages_per_type": 1,
                    }

                ruling_chunker = RulingChunker()
                scraper = ATOLegalDatabaseScraper(source_config=scraper_config)
                dev_limit = 5 if dev_mode else 0  # 0 = unlimited
                item_count = 0

                async for ruling in scraper.scrape_all():
                    if dev_limit and item_count >= dev_limit:
                        logger.info("Dev mode: reached limit of %d items", dev_limit)
                        break
                    item_count += 1

                    source_url: str = ruling.source_url
                    ruling_number: str = ruling.ruling_number or ""

                    try:
                        stats["items_processed"] += 1

                        # --- Resume: skip already-completed items ---
                        if source_url in completed_items:
                            stats["items_skipped"] += 1
                            continue

                        # --- Circuit breaker check ---
                        try:
                            await circuit_breaker.check("www.ato.gov.au")
                        except CircuitOpenError:
                            logger.warning("Circuit breaker open for www.ato.gov.au — aborting")
                            break

                        # --- Compute natural key and document hash ---
                        natural_key = ruling.raw_metadata.get(
                            "natural_key", f"ruling:{ruling_number}"
                        )
                        document_hash = ruling.raw_metadata.get(
                            "document_hash",
                            hashlib.sha256(ruling.text.encode()).hexdigest(),
                        )

                        # --- Check idempotency via IngestionManager ---
                        decision = await ingestion_manager.should_ingest(natural_key, document_hash)

                        if decision == IngestDecision.SKIP:
                            stats["items_skipped"] += 1
                            await job_repo.update_job_checkpoint(job_id, completed_item=source_url)
                            await db.commit()
                            continue

                        # --- Chunk the ruling ---
                        chunks: list[ChunkResult] = ruling_chunker.chunk(
                            ruling.text,
                            metadata={"ruling_number": ruling_number},
                        )

                        if not chunks:
                            stats["items_skipped"] += 1
                            await job_repo.update_job_checkpoint(job_id, completed_item=source_url)
                            await db.commit()
                            continue

                        # --- Generate embeddings for all chunks ---
                        chunk_texts = [c.text for c in chunks]
                        embeddings = await voyage.embed_batch(chunk_texts, parallel=False)
                        stats["tokens_used"] += sum(voyage.estimate_tokens(t) for t in chunk_texts)

                        # --- Insert or replace via IngestionManager ---
                        source_type = ruling.source_type or "ato_ruling"
                        extra_metadata = {
                            "ruling_number": ruling_number,
                            "is_superseded": ruling.is_superseded,
                            "superseded_by": ruling.superseded_by,
                            "effective_date": (
                                ruling.effective_date.date() if ruling.effective_date else None
                            ),
                            "confidence_level": "high",
                        }

                        if decision == IngestDecision.REPLACE:
                            chunk_models = await ingestion_manager.replace_document(
                                natural_key=natural_key,
                                new_chunks=chunks,
                                new_vectors=embeddings,
                                source_id=source.id,
                                collection_name=collection_name,
                                source_url=source_url,
                                title=ruling.title,
                                source_type=source_type,
                                document_hash=document_hash,
                                metadata=extra_metadata,
                            )
                            stats["items_updated"] += 1
                        else:  # INSERT
                            chunk_models = await ingestion_manager.insert_document(
                                natural_key=natural_key,
                                document_hash=document_hash,
                                chunks=chunks,
                                vectors=embeddings,
                                source_id=source.id,
                                collection_name=collection_name,
                                source_url=source_url,
                                title=ruling.title,
                                source_type=source_type,
                                metadata=extra_metadata,
                            )
                            stats["items_added"] += 1

                        # Populate BM25 index entries for each chunk
                        for chunk_model, chunk_result in zip(chunk_models, chunks, strict=False):
                            tokens = chunk_result.text.lower().split()
                            section_refs = chunk_result.cross_references
                            await bm25_repo.upsert(
                                chunk_id=chunk_model.id,
                                collection_name=collection_name,
                                tokens=tokens,
                                section_refs=section_refs,
                            )

                        # Create cross-reference entries
                        for chunk_model, chunk_result in zip(chunk_models, chunks, strict=False):
                            for xref in chunk_result.cross_references:
                                await xref_repo.create(
                                    {
                                        "source_chunk_id": chunk_model.id,
                                        "target_section_ref": xref,
                                        "reference_type": "cites",
                                    }
                                )

                        # Record circuit breaker success
                        await circuit_breaker.record_success("www.ato.gov.au")

                        # Update job checkpoint
                        await job_repo.update_job_checkpoint(job_id, completed_item=source_url)
                        await db.commit()

                        # Update Celery task progress
                        progress_interval = 1 if dev_mode else 5
                        if stats["items_processed"] % progress_interval == 0:
                            self.update_state(
                                state="PROGRESS",
                                meta={
                                    "source_type": "ato_legal_db",
                                    "processed": stats["items_processed"],
                                    "added": stats["items_added"],
                                    "updated": stats["items_updated"],
                                    "skipped": stats["items_skipped"],
                                    "failed": stats["items_failed"],
                                    "current_item": ruling_number,
                                },
                            )

                    except Exception as e:
                        stats["items_failed"] += 1
                        error_entry = {
                            "url": source_url,
                            "error": str(e),
                            "timestamp": datetime.now(tz=UTC).isoformat(),
                        }
                        stats["errors"].append(error_entry)
                        logger.warning("Failed to process ruling %s: %s", ruling_number, e)

                        # Record failure in job checkpoint
                        await job_repo.update_job_checkpoint(job_id, failed_item=error_entry)
                        await circuit_breaker.record_failure("www.ato.gov.au")
                        await db.commit()

                        # Update progress on failures too
                        self.update_state(
                            state="PROGRESS",
                            meta={
                                "source_type": "ato_legal_db",
                                "processed": stats["items_processed"],
                                "added": stats["items_added"],
                                "updated": stats["items_updated"],
                                "skipped": stats["items_skipped"],
                                "failed": stats["items_failed"],
                                "current_item": f"{ruling_number} (error)",
                            },
                        )

                # Complete the job
                await job_repo.complete_job(
                    job_id,
                    items_processed=stats["items_processed"],
                    items_added=stats["items_added"],
                    items_updated=stats["items_updated"],
                    items_skipped=stats["items_skipped"],
                    items_failed=stats["items_failed"],
                    tokens_used=stats["tokens_used"],
                    errors=stats["errors"][:20],
                )
                await db.commit()

            except Exception as exc:
                logger.error("ATO Legal DB ingestion job %s failed: %s", job_id, exc)
                await job_repo.fail_job(
                    job_id,
                    errors=[
                        {
                            "error": str(exc),
                            "timestamp": datetime.now(tz=UTC).isoformat(),
                        }
                    ],
                )
                await db.commit()
                raise

        stats["source_type"] = "ato_legal_db"
        return stats

    # Run the async implementation in a dedicated event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_run())
    finally:
        loop.close()

    logger.info(
        "ATO Legal DB ingestion complete: %d added, %d updated, %d skipped, %d failed",
        result["items_added"],
        result["items_updated"],
        result["items_skipped"],
        result["items_failed"],
    )
    return result


# ---------------------------------------------------------------------------
# Spec 045: Legislation ingestion
# ---------------------------------------------------------------------------


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="app.tasks.knowledge.ingest_legislation",
    max_retries=2,
    default_retry_delay=300,
    time_limit=7200,  # 2 hours
    soft_time_limit=7000,
)
def ingest_legislation(
    self: Task,
    acts: list[str] | None = None,
    parent_job_id: str | None = None,
    dev_mode: bool = False,
) -> dict[str, Any]:
    """Ingest legislation sections from legislation.gov.au.

    Scrapes EPUB files for key tax acts, chunks at section level using
    the legislation chunker, generates embeddings, and stores in Pinecone
    with full metadata. Also creates/updates LegislationSection records
    for cross-referencing and section-level lookup.

    Uses IngestionManager for document-level idempotency and
    checkpoint/resume so the job can be retried safely.

    A 10-second request interval is enforced for legislation.gov.au
    as required by the site's robots.txt.

    Args:
        acts: Optional list of act IDs to ingest (e.g., ["C2004A05138"]).
            If None, all configured tax acts are ingested.
        parent_job_id: If this is a retry, the ID of the original job
            whose completed_items should be loaded for resume.

    Returns:
        Dict with ingestion statistics.
    """
    logger.info(
        "Starting legislation ingestion (acts=%s, parent_job_id=%s, dev_mode=%s)",
        acts,
        parent_job_id,
        dev_mode,
    )

    async def _run() -> dict[str, Any]:
        import hashlib

        from app.config import get_settings
        from app.core.pinecone_service import PineconeService
        from app.core.voyage import VoyageService
        from app.database import get_celery_db_context
        from app.modules.knowledge.chunkers.base import ChunkResult
        from app.modules.knowledge.collections import INDEX_NAME, get_namespace_with_env
        from app.modules.knowledge.ingestion_manager import IngestDecision, IngestionManager
        from app.modules.knowledge.models import (
            IngestionJob,
        )
        from app.modules.knowledge.repository import (
            BM25IndexRepository,
            ContentChunkRepository,
            ContentCrossReferenceRepository,
            IngestionJobRepository,
            LegislationSectionRepository,
        )
        from app.modules.knowledge.scrapers.circuit_breaker import (
            CircuitOpenError,
            ScraperCircuitBreaker,
        )

        settings = get_settings()

        stats: dict[str, Any] = {
            "items_processed": 0,
            "items_added": 0,
            "items_updated": 0,
            "items_skipped": 0,
            "items_failed": 0,
            "tokens_used": 0,
            "errors": [],
        }

        async with get_celery_db_context() as db:
            job_repo = IngestionJobRepository(db)
            chunk_repo = ContentChunkRepository(db)
            bm25_repo = BM25IndexRepository(db)
            xref_repo = ContentCrossReferenceRepository(db)
            leg_repo = LegislationSectionRepository(db)

            # Get or create the knowledge source record
            source = await _get_or_create_source(db, "legislation")
            collection_name = source.collection_name
            pinecone_namespace = get_namespace_with_env(collection_name)

            # Create the ingestion job record
            job = IngestionJob(
                source_id=source.id,
                status="running",
                triggered_by="manual",
                is_resumable=True,
                parent_job_id=UUID(parent_job_id) if parent_job_id else None,
            )
            job = await job_repo.create(job)
            await job_repo.start_job(job.id)
            await db.commit()

            job_id = job.id

            # Load completed items from parent job for resume support
            completed_items: set[str] = set()
            if parent_job_id:
                completed_items = await job_repo.get_job_completed_items(UUID(parent_job_id))
                logger.info(
                    "Resuming from parent job %s — %d items already completed",
                    parent_job_id,
                    len(completed_items),
                )

            # Initialise services
            pinecone = PineconeService(settings.pinecone)
            voyage = VoyageService(settings.voyage)
            circuit_breaker = ScraperCircuitBreaker(db)
            ingestion_manager = IngestionManager(
                db,
                pinecone,
                INDEX_NAME,
                pinecone_namespace,
            )

            try:
                from app.modules.knowledge.chunkers.legislation import LegislationChunker
                from app.modules.knowledge.scrapers.legislation_gov import (
                    LegislationGovScraper,
                )

                # In dev_mode, limit to 1 act (SGAA — smallest)
                scraper_acts = acts
                if dev_mode and not acts:
                    scraper_acts = ["C2004A00477"]  # SGAA (smallest act)

                scraper_config: dict = {}
                if scraper_acts:
                    scraper_config["acts"] = scraper_acts

                legislation_chunker = LegislationChunker()
                scraper = LegislationGovScraper(source_config=scraper_config)
                dev_limit = 10 if dev_mode else 0  # 0 = unlimited
                item_count = 0

                async for section in scraper.scrape_all():
                    if dev_limit and item_count >= dev_limit:
                        logger.info("Dev mode: reached limit of %d sections", dev_limit)
                        break
                    item_count += 1

                    source_url: str = section.source_url
                    act_id: str = section.raw_metadata.get("act_id", "")
                    section_ref: str = section.raw_metadata.get("section_ref", "")

                    try:
                        stats["items_processed"] += 1

                        # --- Resume: skip already-completed items ---
                        item_key = f"{act_id}:{section_ref}"
                        if item_key in completed_items:
                            stats["items_skipped"] += 1
                            continue

                        # --- Circuit breaker check ---
                        try:
                            await circuit_breaker.check("www.legislation.gov.au")
                        except CircuitOpenError:
                            logger.warning(
                                "Circuit breaker open for www.legislation.gov.au — aborting"
                            )
                            break

                        # --- Compute natural key and document hash ---
                        natural_key = section.raw_metadata.get(
                            "natural_key", f"legislation:{act_id}:{section_ref}"
                        )
                        document_hash = section.raw_metadata.get(
                            "document_hash",
                            hashlib.sha256(section.text.encode()).hexdigest(),
                        )

                        # --- Check idempotency via IngestionManager ---
                        decision = await ingestion_manager.should_ingest(natural_key, document_hash)

                        if decision == IngestDecision.SKIP:
                            stats["items_skipped"] += 1
                            await job_repo.update_job_checkpoint(job_id, completed_item=item_key)
                            await db.commit()
                            continue

                        # --- Chunk the section ---
                        chunks: list[ChunkResult] = legislation_chunker.chunk(
                            section.text,
                            metadata={
                                "act_id": act_id,
                                "section_ref": section_ref,
                            },
                        )

                        if not chunks:
                            stats["items_skipped"] += 1
                            await job_repo.update_job_checkpoint(job_id, completed_item=item_key)
                            await db.commit()
                            continue

                        # --- Generate embeddings for all chunks ---
                        chunk_texts = [c.text for c in chunks]
                        embeddings = await voyage.embed_batch(chunk_texts, parallel=False)
                        stats["tokens_used"] += sum(voyage.estimate_tokens(t) for t in chunk_texts)

                        # --- Insert or replace via IngestionManager ---
                        extra_metadata = {
                            "is_superseded": False,
                            "effective_date": (
                                section.effective_date.date()
                                if getattr(section, "effective_date", None)
                                else None
                            ),
                            "confidence_level": "high",
                        }

                        if decision == IngestDecision.REPLACE:
                            chunk_models = await ingestion_manager.replace_document(
                                natural_key=natural_key,
                                new_chunks=chunks,
                                new_vectors=embeddings,
                                source_id=source.id,
                                collection_name=collection_name,
                                source_url=source_url,
                                title=section.title,
                                source_type="legislation",
                                document_hash=document_hash,
                                metadata=extra_metadata,
                            )
                            stats["items_updated"] += 1
                        else:  # INSERT
                            chunk_models = await ingestion_manager.insert_document(
                                natural_key=natural_key,
                                document_hash=document_hash,
                                chunks=chunks,
                                vectors=embeddings,
                                source_id=source.id,
                                collection_name=collection_name,
                                source_url=source_url,
                                title=section.title,
                                source_type="legislation",
                                metadata=extra_metadata,
                            )
                            stats["items_added"] += 1

                        # --- Create / update LegislationSection record ---
                        meta = section.raw_metadata
                        leg_section = await leg_repo.upsert(
                            {
                                "act_id": act_id,
                                "act_name": meta.get("act_name", ""),
                                "act_short_name": meta.get("act_short_name", ""),
                                "section_ref": section_ref,
                                "part": meta.get("part"),
                                "division": meta.get("division"),
                                "subdivision": meta.get("subdivision"),
                                "heading": section.title,
                                "content_hash": document_hash,
                                "compilation_date": (
                                    section.effective_date.date()
                                    if section.effective_date
                                    else datetime.now(tz=UTC).date()
                                ),
                                "compilation_number": meta.get("compilation_number"),
                                "cross_references": chunks[0].cross_references if chunks else [],
                                "defined_terms": (chunks[0].defined_terms_used if chunks else []),
                                "topic_tags": chunks[0].topic_tags if chunks else [],
                                "is_current": True,
                            }
                        )

                        # Link chunks to legislation section
                        for cm in chunk_models:
                            cm.legislation_section_id = leg_section.id

                        await db.flush()

                        # Populate BM25 index entries for each chunk
                        for chunk_model, chunk_result in zip(chunk_models, chunks, strict=False):
                            tokens = chunk_result.text.lower().split()
                            section_refs = chunk_result.cross_references
                            await bm25_repo.upsert(
                                chunk_id=chunk_model.id,
                                collection_name=collection_name,
                                tokens=tokens,
                                section_refs=section_refs,
                            )

                        # Create cross-reference entries
                        for chunk_model, chunk_result in zip(chunk_models, chunks, strict=False):
                            for xref in chunk_result.cross_references:
                                await xref_repo.create(
                                    {
                                        "source_chunk_id": chunk_model.id,
                                        "target_section_ref": xref,
                                        "reference_type": "cites",
                                    }
                                )

                        # Record circuit breaker success
                        await circuit_breaker.record_success("www.legislation.gov.au")

                        # Update job checkpoint
                        await job_repo.update_job_checkpoint(job_id, completed_item=item_key)
                        await db.commit()

                        # Update Celery task progress
                        progress_interval = 1 if dev_mode else 5
                        if stats["items_processed"] % progress_interval == 0:
                            self.update_state(
                                state="PROGRESS",
                                meta={
                                    "source_type": "legislation",
                                    "processed": stats["items_processed"],
                                    "added": stats["items_added"],
                                    "updated": stats["items_updated"],
                                    "skipped": stats["items_skipped"],
                                    "failed": stats["items_failed"],
                                    "current_item": f"{act_id} {section_ref}",
                                },
                            )

                    except Exception as e:
                        stats["items_failed"] += 1
                        error_entry = {
                            "url": source_url,
                            "section_ref": section_ref,
                            "error": str(e),
                            "timestamp": datetime.now(tz=UTC).isoformat(),
                        }
                        stats["errors"].append(error_entry)
                        logger.warning(
                            "Failed to process section %s from %s: %s",
                            section_ref,
                            act_id,
                            e,
                        )

                        # Record failure in job checkpoint
                        await job_repo.update_job_checkpoint(job_id, failed_item=error_entry)
                        await circuit_breaker.record_failure("www.legislation.gov.au")
                        await db.commit()

                        self.update_state(
                            state="PROGRESS",
                            meta={
                                "source_type": "legislation",
                                "processed": stats["items_processed"],
                                "added": stats["items_added"],
                                "updated": stats["items_updated"],
                                "skipped": stats["items_skipped"],
                                "failed": stats["items_failed"],
                                "current_item": f"{act_id} {section_ref} (error)",
                            },
                        )

                # Complete the job
                await job_repo.complete_job(
                    job_id,
                    items_processed=stats["items_processed"],
                    items_added=stats["items_added"],
                    items_updated=stats["items_updated"],
                    items_skipped=stats["items_skipped"],
                    items_failed=stats["items_failed"],
                    tokens_used=stats["tokens_used"],
                    errors=stats["errors"][:20],
                )
                await db.commit()

            except Exception as exc:
                logger.error("Legislation ingestion job %s failed: %s", job_id, exc)
                await job_repo.fail_job(
                    job_id,
                    errors=[
                        {
                            "error": str(exc),
                            "timestamp": datetime.now(tz=UTC).isoformat(),
                        }
                    ],
                )
                await db.commit()
                raise

        stats["source_type"] = "legislation"
        return stats

    # Run the async implementation in a dedicated event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_run())
    finally:
        loop.close()

    logger.info(
        "Legislation ingestion complete: %d added, %d updated, %d skipped, %d failed",
        result["items_added"],
        result["items_updated"],
        result["items_skipped"],
        result["items_failed"],
    )
    return result


# ---------------------------------------------------------------------------
# Spec 045: Case law ingestion
# ---------------------------------------------------------------------------


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="app.tasks.knowledge.ingest_case_law",
    max_retries=2,
    default_retry_delay=300,
    time_limit=7200,  # 2 hours
    soft_time_limit=7000,
)
def ingest_case_law(
    self: Task,
    source: str = "both",
    filter_tax_only: bool = True,
    parent_job_id: str | None = None,
    dev_mode: bool = False,
) -> dict[str, Any]:
    """Ingest tax-relevant case law from Australian legal sources.

    Scrapes case law from the Open Australian Legal Corpus and/or
    the Federal Court RSS feed, chunks with the case law chunker,
    generates embeddings, and stores in Pinecone with full metadata.
    Uses IngestionManager for document-level idempotency and
    checkpoint/resume so the job can be retried safely.

    Natural key format: ``case_law:{citation}``

    Args:
        source: Which source to ingest from. One of
            ``"open_legal_corpus"``, ``"federal_court_rss"``, or
            ``"both"`` (default).
        filter_tax_only: If True (default), only ingest cases related
            to tax law (keyword/NLP classification).
        parent_job_id: If this is a retry, the ID of the original job
            whose completed_items should be loaded for resume.

    Returns:
        Dict with ingestion statistics.
    """
    logger.info(
        "Starting case law ingestion (source=%s, filter_tax_only=%s, "
        "parent_job_id=%s, dev_mode=%s)",
        source,
        filter_tax_only,
        parent_job_id,
        dev_mode,
    )

    async def _run() -> dict[str, Any]:
        import hashlib

        from app.config import get_settings
        from app.core.pinecone_service import PineconeService
        from app.core.voyage import VoyageService
        from app.database import get_celery_db_context
        from app.modules.knowledge.chunkers.base import ChunkResult
        from app.modules.knowledge.collections import INDEX_NAME, get_namespace_with_env
        from app.modules.knowledge.ingestion_manager import (
            IngestDecision,
            IngestionManager,
        )
        from app.modules.knowledge.models import IngestionJob
        from app.modules.knowledge.repository import (
            BM25IndexRepository,
            ContentCrossReferenceRepository,
            IngestionJobRepository,
        )
        from app.modules.knowledge.scrapers.circuit_breaker import (
            CircuitOpenError,
            ScraperCircuitBreaker,
        )

        settings = get_settings()

        stats: dict[str, Any] = {
            "items_processed": 0,
            "items_added": 0,
            "items_updated": 0,
            "items_skipped": 0,
            "items_failed": 0,
            "tokens_used": 0,
            "errors": [],
        }

        async with get_celery_db_context() as db:
            job_repo = IngestionJobRepository(db)
            bm25_repo = BM25IndexRepository(db)
            xref_repo = ContentCrossReferenceRepository(db)

            # Get or create the knowledge source record
            source = await _get_or_create_source(db, "case_law")
            collection_name = source.collection_name
            pinecone_namespace = get_namespace_with_env(collection_name)

            # Create the ingestion job record
            job = IngestionJob(
                source_id=source.id,
                status="running",
                triggered_by="manual",
                is_resumable=True,
                parent_job_id=UUID(parent_job_id) if parent_job_id else None,
            )
            job = await job_repo.create(job)
            await job_repo.start_job(job.id)
            await db.commit()

            job_id = job.id

            # Load completed items from parent job for resume support
            completed_items: set[str] = set()
            if parent_job_id:
                completed_items = await job_repo.get_job_completed_items(UUID(parent_job_id))
                logger.info(
                    "Resuming from parent job %s — %d items already completed",
                    parent_job_id,
                    len(completed_items),
                )

            # Initialise services
            pinecone = PineconeService(settings.pinecone)
            voyage = VoyageService(settings.voyage)
            circuit_breaker = ScraperCircuitBreaker(db)
            ingestion_manager = IngestionManager(
                db,
                pinecone,
                INDEX_NAME,
                pinecone_namespace,
            )

            try:
                from app.modules.knowledge.chunkers.case_law import CaseLawChunker
                from app.modules.knowledge.scrapers.case_law import CaseLawScraper

                # In dev_mode, only use RSS (not the full HuggingFace corpus)
                scraper_source = source
                if dev_mode:
                    scraper_source = "federal_court_rss"

                scraper_config: dict = {"source": scraper_source}
                if filter_tax_only:
                    scraper_config["filter_tax_only"] = True

                case_chunker = CaseLawChunker()
                scraper = CaseLawScraper(source_config=scraper_config)
                dev_limit = 5 if dev_mode else 0  # 0 = unlimited
                item_count = 0

                async for case in scraper.scrape_all():
                    if dev_limit and item_count >= dev_limit:
                        logger.info("Dev mode: reached limit of %d cases", dev_limit)
                        break
                    item_count += 1

                    source_url: str = case.source_url
                    citation: str = case.raw_metadata.get("case_citation", case.title or "")

                    try:
                        stats["items_processed"] += 1

                        # --- Resume: skip already-completed items ---
                        if source_url in completed_items:
                            stats["items_skipped"] += 1
                            continue

                        # --- Circuit breaker check ---
                        source_host = "www.fedcourt.gov.au"
                        try:
                            await circuit_breaker.check(source_host)
                        except CircuitOpenError:
                            logger.warning(
                                "Circuit breaker open for %s — aborting",
                                source_host,
                            )
                            break

                        # --- Compute natural key and document hash ---
                        natural_key = case.raw_metadata.get("natural_key", f"case_law:{citation}")
                        document_hash = case.raw_metadata.get(
                            "document_hash",
                            hashlib.sha256(case.text.encode()).hexdigest(),
                        )

                        # --- Check idempotency via IngestionManager ---
                        decision = await ingestion_manager.should_ingest(natural_key, document_hash)

                        if decision == IngestDecision.SKIP:
                            stats["items_skipped"] += 1
                            await job_repo.update_job_checkpoint(job_id, completed_item=source_url)
                            await db.commit()
                            continue

                        # --- Chunk the case ---
                        chunks: list[ChunkResult] = case_chunker.chunk(
                            case.text,
                            metadata={"case_citation": citation},
                        )

                        if not chunks:
                            stats["items_skipped"] += 1
                            await job_repo.update_job_checkpoint(job_id, completed_item=source_url)
                            await db.commit()
                            continue

                        # --- Generate embeddings for all chunks ---
                        chunk_texts = [c.text for c in chunks]
                        embeddings = await voyage.embed_batch(chunk_texts, parallel=False)
                        stats["tokens_used"] += sum(voyage.estimate_tokens(t) for t in chunk_texts)

                        # --- Insert or replace via IngestionManager ---
                        extra_metadata = {
                            "court": getattr(case, "court", None),
                            "case_citation": citation,
                            "is_superseded": False,
                            "effective_date": (
                                case.date  # type: ignore[attr-defined]
                                if getattr(case, "date", None)
                                else None
                            ),
                            "confidence_level": "medium",
                        }

                        if decision == IngestDecision.REPLACE:
                            chunk_models = await ingestion_manager.replace_document(
                                natural_key=natural_key,
                                new_chunks=chunks,
                                new_vectors=embeddings,
                                source_id=source.id,
                                collection_name=collection_name,
                                source_url=source_url,
                                title=getattr(case, "title", None),
                                source_type="case_law",
                                document_hash=document_hash,
                                metadata=extra_metadata,
                            )
                            stats["items_updated"] += 1
                        else:  # INSERT
                            chunk_models = await ingestion_manager.insert_document(
                                natural_key=natural_key,
                                document_hash=document_hash,
                                chunks=chunks,
                                vectors=embeddings,
                                source_id=source.id,
                                collection_name=collection_name,
                                source_url=source_url,
                                title=getattr(case, "title", None),
                                source_type="case_law",
                                metadata=extra_metadata,
                            )
                            stats["items_added"] += 1

                        # Populate BM25 index entries for each chunk
                        for chunk_model, chunk_result in zip(chunk_models, chunks, strict=False):
                            tokens = chunk_result.text.lower().split()
                            section_refs = chunk_result.cross_references
                            await bm25_repo.upsert(
                                chunk_id=chunk_model.id,
                                collection_name=collection_name,
                                tokens=tokens,
                                section_refs=section_refs,
                            )

                        # Create cross-reference entries
                        for chunk_model, chunk_result in zip(chunk_models, chunks, strict=False):
                            for xref in chunk_result.cross_references:
                                await xref_repo.create(
                                    {
                                        "source_chunk_id": chunk_model.id,
                                        "target_section_ref": xref,
                                        "reference_type": "cites",
                                    }
                                )

                        # Record circuit breaker success
                        await circuit_breaker.record_success(source_host)

                        # Update job checkpoint
                        await job_repo.update_job_checkpoint(job_id, completed_item=source_url)
                        await db.commit()

                        # Update Celery task progress
                        progress_interval = 1 if dev_mode else 5
                        if stats["items_processed"] % progress_interval == 0:
                            self.update_state(
                                state="PROGRESS",
                                meta={
                                    "source_type": "case_law",
                                    "processed": stats["items_processed"],
                                    "added": stats["items_added"],
                                    "updated": stats["items_updated"],
                                    "skipped": stats["items_skipped"],
                                    "failed": stats["items_failed"],
                                    "current_item": citation,
                                },
                            )

                    except Exception as e:
                        stats["items_failed"] += 1
                        error_entry = {
                            "url": source_url,
                            "citation": citation,
                            "error": str(e),
                            "timestamp": datetime.now(tz=UTC).isoformat(),
                        }
                        stats["errors"].append(error_entry)
                        logger.warning("Failed to process case %s: %s", citation, e)

                        # Record failure in job checkpoint
                        await job_repo.update_job_checkpoint(job_id, failed_item=error_entry)
                        await circuit_breaker.record_failure(source_host)
                        await db.commit()

                        self.update_state(
                            state="PROGRESS",
                            meta={
                                "source_type": "case_law",
                                "processed": stats["items_processed"],
                                "added": stats["items_added"],
                                "updated": stats["items_updated"],
                                "skipped": stats["items_skipped"],
                                "failed": stats["items_failed"],
                                "current_item": f"{citation} (error)",
                            },
                        )

                # Complete the job
                await job_repo.complete_job(
                    job_id,
                    items_processed=stats["items_processed"],
                    items_added=stats["items_added"],
                    items_updated=stats["items_updated"],
                    items_skipped=stats["items_skipped"],
                    items_failed=stats["items_failed"],
                    tokens_used=stats["tokens_used"],
                    errors=stats["errors"][:20],
                )
                await db.commit()

            except Exception as exc:
                logger.error("Case law ingestion job %s failed: %s", job_id, exc)
                await job_repo.fail_job(
                    job_id,
                    errors=[
                        {
                            "error": str(exc),
                            "timestamp": datetime.now(tz=UTC).isoformat(),
                        }
                    ],
                )
                await db.commit()
                raise

        stats["source_type"] = "case_law"
        return stats

    # Run the async implementation in a dedicated event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_run())
    finally:
        loop.close()

    logger.info(
        "Case law ingestion complete: %d added, %d updated, %d skipped, %d failed",
        result["items_added"],
        result["items_updated"],
        result["items_skipped"],
        result["items_failed"],
    )
    return result


# ---------------------------------------------------------------------------
# Spec 045: TPB / Treasury ingestion
# ---------------------------------------------------------------------------


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="app.tasks.knowledge.ingest_tpb_treasury",
    max_retries=2,
    default_retry_delay=300,
    time_limit=3600,  # 1 hour
    soft_time_limit=3300,
)
def ingest_tpb_treasury(
    self: Task,
    parent_job_id: str | None = None,
    dev_mode: bool = False,
) -> dict[str, Any]:
    """Ingest TPB information products and Treasury exposure drafts.

    Scrapes Tax Practitioners Board guidance and Treasury publications,
    chunks content, generates embeddings, and stores in Pinecone with
    full metadata. Uses IngestionManager for document-level idempotency
    and checkpoint/resume so the job can be retried safely.

    Natural key format: ``tpb:{url_hash}``

    Args:
        parent_job_id: If this is a retry, the ID of the original job
            whose completed_items should be loaded for resume.

    Returns:
        Dict with ingestion statistics.
    """
    logger.info(
        "Starting TPB/Treasury ingestion (parent_job_id=%s, dev_mode=%s)",
        parent_job_id,
        dev_mode,
    )

    async def _run() -> dict[str, Any]:
        import hashlib

        from app.config import get_settings
        from app.core.pinecone_service import PineconeService
        from app.core.voyage import VoyageService
        from app.database import get_celery_db_context
        from app.modules.knowledge.chunkers.base import ChunkResult
        from app.modules.knowledge.collections import INDEX_NAME, get_namespace_with_env
        from app.modules.knowledge.ingestion_manager import (
            IngestDecision,
            IngestionManager,
        )
        from app.modules.knowledge.models import IngestionJob
        from app.modules.knowledge.repository import (
            BM25IndexRepository,
            ContentCrossReferenceRepository,
            IngestionJobRepository,
        )
        from app.modules.knowledge.scrapers.circuit_breaker import (
            CircuitOpenError,
            ScraperCircuitBreaker,
        )

        settings = get_settings()

        stats: dict[str, Any] = {
            "items_processed": 0,
            "items_added": 0,
            "items_updated": 0,
            "items_skipped": 0,
            "items_failed": 0,
            "tokens_used": 0,
            "errors": [],
        }

        async with get_celery_db_context() as db:
            job_repo = IngestionJobRepository(db)
            bm25_repo = BM25IndexRepository(db)
            xref_repo = ContentCrossReferenceRepository(db)

            # Get or create the knowledge source record
            source = await _get_or_create_source(db, "tpb_treasury")
            collection_name = source.collection_name
            pinecone_namespace = get_namespace_with_env(collection_name)

            # Create the ingestion job record
            job = IngestionJob(
                source_id=source.id,
                status="running",
                triggered_by="manual",
                is_resumable=True,
                parent_job_id=UUID(parent_job_id) if parent_job_id else None,
            )
            job = await job_repo.create(job)
            await job_repo.start_job(job.id)
            await db.commit()

            job_id = job.id

            # Load completed items from parent job for resume support
            completed_items: set[str] = set()
            if parent_job_id:
                completed_items = await job_repo.get_job_completed_items(UUID(parent_job_id))
                logger.info(
                    "Resuming from parent job %s — %d items already completed",
                    parent_job_id,
                    len(completed_items),
                )

            # Initialise services
            pinecone = PineconeService(settings.pinecone)
            voyage = VoyageService(settings.voyage)
            circuit_breaker = ScraperCircuitBreaker(db)
            ingestion_manager = IngestionManager(
                db,
                pinecone,
                INDEX_NAME,
                pinecone_namespace,
            )

            try:
                from app.modules.knowledge.scrapers.tpb_treasury import (
                    TPBTreasuryScraper,
                )

                # In dev_mode, limit TPB paths to first 3
                scraper_config: dict = {}
                if dev_mode:
                    scraper_config["tpb_paths"] = [
                        "/policy-and-guidance",
                        "/code-professional-conduct",
                        "/apply-register",
                    ]
                    scraper_config["treasury_paths"] = []

                scraper = TPBTreasuryScraper(source_config=scraper_config)
                dev_limit = 3 if dev_mode else 0  # 0 = unlimited
                item_count = 0

                async for doc in scraper.scrape_all():
                    if dev_limit and item_count >= dev_limit:
                        logger.info("Dev mode: reached limit of %d docs", dev_limit)
                        break
                    item_count += 1

                    source_url: str = doc.source_url

                    try:
                        stats["items_processed"] += 1

                        # --- Resume: skip already-completed items ---
                        if source_url in completed_items:
                            stats["items_skipped"] += 1
                            continue

                        # --- Circuit breaker check ---
                        source_host = "www.tpb.gov.au"
                        try:
                            await circuit_breaker.check(source_host)
                        except CircuitOpenError:
                            logger.warning(
                                "Circuit breaker open for %s — aborting",
                                source_host,
                            )
                            break

                        # --- Compute natural key and document hash ---
                        url_hash = hashlib.sha256(source_url.encode()).hexdigest()[:16]
                        natural_key = f"tpb:{url_hash}"
                        document_hash = hashlib.sha256(doc.text.encode()).hexdigest()

                        # --- Check idempotency via IngestionManager ---
                        decision = await ingestion_manager.should_ingest(natural_key, document_hash)

                        if decision == IngestDecision.SKIP:
                            stats["items_skipped"] += 1
                            await job_repo.update_job_checkpoint(job_id, completed_item=source_url)
                            await db.commit()
                            continue

                        # --- Chunk the document ---
                        # Use paragraph-based splitting for TPB content
                        # (no specialised chunker for this source).
                        paragraphs = [p.strip() for p in doc.text.split("\n\n") if p.strip()]
                        chunks: list[ChunkResult] = []
                        current_text = ""
                        for para in paragraphs:
                            combined = f"{current_text}\n\n{para}".strip() if current_text else para
                            if len(combined) // 4 > 512 and current_text:
                                chunks.append(
                                    ChunkResult(
                                        text=current_text,
                                        content_type="guidance",
                                        section_ref=None,
                                        topic_tags=["tpb", "tax_practitioner"],
                                    )
                                )
                                current_text = para
                            else:
                                current_text = combined
                        if current_text and len(current_text) > 50:
                            chunks.append(
                                ChunkResult(
                                    text=current_text,
                                    content_type="guidance",
                                    section_ref=None,
                                    topic_tags=["tpb", "tax_practitioner"],
                                )
                            )

                        if not chunks:
                            stats["items_skipped"] += 1
                            await job_repo.update_job_checkpoint(job_id, completed_item=source_url)
                            await db.commit()
                            continue

                        # --- Generate embeddings for all chunks ---
                        chunk_texts = [c.text for c in chunks]
                        embeddings = await voyage.embed_batch(chunk_texts, parallel=False)
                        stats["tokens_used"] += sum(voyage.estimate_tokens(t) for t in chunk_texts)

                        # --- Insert or replace via IngestionManager ---
                        extra_metadata = {
                            "is_superseded": False,
                            "confidence_level": "medium",
                        }

                        if decision == IngestDecision.REPLACE:
                            chunk_models = await ingestion_manager.replace_document(
                                natural_key=natural_key,
                                new_chunks=chunks,
                                new_vectors=embeddings,
                                source_id=source.id,
                                collection_name=collection_name,
                                source_url=source_url,
                                title=getattr(doc, "title", None),
                                source_type="tpb_guidance",
                                document_hash=document_hash,
                                metadata=extra_metadata,
                            )
                            stats["items_updated"] += 1
                        else:  # INSERT
                            chunk_models = await ingestion_manager.insert_document(
                                natural_key=natural_key,
                                document_hash=document_hash,
                                chunks=chunks,
                                vectors=embeddings,
                                source_id=source.id,
                                collection_name=collection_name,
                                source_url=source_url,
                                title=getattr(doc, "title", None),
                                source_type="tpb_guidance",
                                metadata=extra_metadata,
                            )
                            stats["items_added"] += 1

                        # Populate BM25 index entries for each chunk
                        for chunk_model, chunk_result in zip(chunk_models, chunks, strict=False):
                            tokens = chunk_result.text.lower().split()
                            section_refs = chunk_result.cross_references
                            await bm25_repo.upsert(
                                chunk_id=chunk_model.id,
                                collection_name=collection_name,
                                tokens=tokens,
                                section_refs=section_refs,
                            )

                        # Create cross-reference entries
                        for chunk_model, chunk_result in zip(chunk_models, chunks, strict=False):
                            for xref in chunk_result.cross_references:
                                await xref_repo.create(
                                    {
                                        "source_chunk_id": chunk_model.id,
                                        "target_section_ref": xref,
                                        "reference_type": "cites",
                                    }
                                )

                        # Record circuit breaker success
                        await circuit_breaker.record_success(source_host)

                        # Update job checkpoint
                        await job_repo.update_job_checkpoint(job_id, completed_item=source_url)
                        await db.commit()

                        # Update Celery task progress
                        progress_interval = 1 if dev_mode else 5
                        if stats["items_processed"] % progress_interval == 0:
                            self.update_state(
                                state="PROGRESS",
                                meta={
                                    "source_type": "tpb_treasury",
                                    "processed": stats["items_processed"],
                                    "added": stats["items_added"],
                                    "updated": stats["items_updated"],
                                    "skipped": stats["items_skipped"],
                                    "failed": stats["items_failed"],
                                    "current_item": doc.title or source_url,
                                },
                            )

                    except Exception as e:
                        stats["items_failed"] += 1
                        error_entry = {
                            "url": source_url,
                            "error": str(e),
                            "timestamp": datetime.now(tz=UTC).isoformat(),
                        }
                        stats["errors"].append(error_entry)
                        logger.warning(
                            "Failed to process TPB/Treasury document %s: %s",
                            source_url,
                            e,
                        )

                        # Record failure in job checkpoint
                        await job_repo.update_job_checkpoint(job_id, failed_item=error_entry)
                        await circuit_breaker.record_failure(source_host)
                        await db.commit()

                        self.update_state(
                            state="PROGRESS",
                            meta={
                                "source_type": "tpb_treasury",
                                "processed": stats["items_processed"],
                                "added": stats["items_added"],
                                "updated": stats["items_updated"],
                                "skipped": stats["items_skipped"],
                                "failed": stats["items_failed"],
                                "current_item": f"{source_url} (error)",
                            },
                        )

                # Complete the job
                await job_repo.complete_job(
                    job_id,
                    items_processed=stats["items_processed"],
                    items_added=stats["items_added"],
                    items_updated=stats["items_updated"],
                    items_skipped=stats["items_skipped"],
                    items_failed=stats["items_failed"],
                    tokens_used=stats["tokens_used"],
                    errors=stats["errors"][:20],
                )
                await db.commit()

            except Exception as exc:
                logger.error("TPB/Treasury ingestion job %s failed: %s", job_id, exc)
                await job_repo.fail_job(
                    job_id,
                    errors=[
                        {
                            "error": str(exc),
                            "timestamp": datetime.now(tz=UTC).isoformat(),
                        }
                    ],
                )
                await db.commit()
                raise

        stats["source_type"] = "tpb_treasury"
        return stats

    # Run the async implementation in a dedicated event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_run())
    finally:
        loop.close()

    logger.info(
        "TPB/Treasury ingestion complete: %d added, %d updated, %d skipped, %d failed",
        result["items_added"],
        result["items_updated"],
        result["items_skipped"],
        result["items_failed"],
    )
    return result


# ---------------------------------------------------------------------------
# Spec 045: Content freshness monitoring scheduled tasks
# ---------------------------------------------------------------------------

# Stale content grace periods (in days). If a source is temporarily
# unreachable we keep existing content and only flag as "stale" after
# the grace period. We never auto-delete content due to scraping failures.
_STALE_GRACE_RULINGS_DAYS = 7
_STALE_GRACE_LEGISLATION_DAYS = 30


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.knowledge.monitor_ato_rss",
)
def monitor_ato_rss() -> dict[str, Any]:
    """Check ATO RSS for new rulings, trigger ingestion.

    Runs every 4 hours via Celery Beat. Creates an IngestionJob with
    triggered_by="scheduled" and delegates to
    ``ingest_ato_legal_database`` for the actual work.
    """
    logger.info("Scheduled task: monitor_ato_rss — checking for new rulings")

    async def _run() -> dict[str, Any]:
        from app.database import get_celery_db_context
        from app.modules.knowledge.models import IngestionJob
        from app.modules.knowledge.repository import IngestionJobRepository

        async with get_celery_db_context() as db:
            job_repo = IngestionJobRepository(db)
            source = await _get_or_create_source(db, "ato_rss")
            job = IngestionJob(
                source_id=source.id,
                status="pending",
                triggered_by="scheduled",
            )
            job = await job_repo.create(job)
            await db.commit()

            # Delegate to the full ATO Legal DB ingestion task
            ingest_ato_legal_database.delay(parent_job_id=str(job.id))

            return {"status": "dispatched", "job_id": str(job.id)}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.knowledge.delta_crawl_ato_legal_db",
)
def delta_crawl_ato_legal_db() -> dict[str, Any]:
    """Weekly delta crawl of ATO Legal Database.

    Runs weekly via Celery Beat. Detects updated/new documents via
    ``IngestionManager.should_ingest()`` (document_hash comparison).
    Delegates to ``ingest_ato_legal_database``.
    """
    logger.info("Scheduled task: delta_crawl_ato_legal_db — weekly delta crawl")

    async def _run() -> dict[str, Any]:
        from app.database import get_celery_db_context
        from app.modules.knowledge.models import IngestionJob
        from app.modules.knowledge.repository import IngestionJobRepository

        async with get_celery_db_context() as db:
            job_repo = IngestionJobRepository(db)
            source = await _get_or_create_source(db, "ato_legal_db")
            job = IngestionJob(
                source_id=source.id,
                status="pending",
                triggered_by="scheduled",
            )
            job = await job_repo.create(job)
            await db.commit()

            # The IngestionManager inside ingest_ato_legal_database
            # automatically detects unchanged documents (SKIP) and
            # changed documents (REPLACE), so a full crawl with
            # idempotency acts as a delta crawl.
            ingest_ato_legal_database.delay(parent_job_id=str(job.id))

            return {"status": "dispatched", "job_id": str(job.id)}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.knowledge.sync_legislation",
)
def sync_legislation() -> dict[str, Any]:
    """Monthly legislation sync -- detect amended acts.

    Runs monthly via Celery Beat. Re-ingests all configured legislation
    acts; the IngestionManager detects amended sections via compilation
    number / document_hash changes and applies REPLACE semantics for
    changed sections while SKIPping unchanged ones.
    """
    logger.info("Scheduled task: sync_legislation — monthly legislation sync")

    async def _run() -> dict[str, Any]:
        from app.database import get_celery_db_context
        from app.modules.knowledge.models import IngestionJob
        from app.modules.knowledge.repository import IngestionJobRepository

        async with get_celery_db_context() as db:
            job_repo = IngestionJobRepository(db)
            source = await _get_or_create_source(db, "legislation")
            job = IngestionJob(
                source_id=source.id,
                status="pending",
                triggered_by="scheduled",
            )
            job = await job_repo.create(job)
            await db.commit()

            # Ingest all configured acts — idempotency handles
            # skip/replace automatically.
            ingest_legislation.delay(acts=None, parent_job_id=str(job.id))

            return {"status": "dispatched", "job_id": str(job.id)}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.knowledge.monitor_federal_court_rss",
)
def monitor_federal_court_rss() -> dict[str, Any]:
    """Daily check for new tax judgments.

    Runs daily via Celery Beat. Dispatches ``ingest_case_law`` with
    source="federal_court_rss" to pick up any new tax-related
    judgments from the Federal Court RSS feed.
    """
    logger.info("Scheduled task: monitor_federal_court_rss — checking for new tax judgments")

    async def _run() -> dict[str, Any]:
        from app.database import get_celery_db_context
        from app.modules.knowledge.models import IngestionJob
        from app.modules.knowledge.repository import IngestionJobRepository

        async with get_celery_db_context() as db:
            job_repo = IngestionJobRepository(db)
            source = await _get_or_create_source(db, "case_law")
            job = IngestionJob(
                source_id=source.id,
                status="pending",
                triggered_by="scheduled",
            )
            job = await job_repo.create(job)
            await db.commit()

            ingest_case_law.delay(
                source="federal_court_rss",
                filter_tax_only=True,
                parent_job_id=str(job.id),
            )

            return {"status": "dispatched", "job_id": str(job.id)}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(  # type: ignore[misc]
    name="app.tasks.knowledge.check_supersessions",
)
def check_supersessions() -> dict[str, Any]:
    """Weekly check for superseded rulings.

    Runs weekly via Celery Beat. Queries content chunks for indicators
    that a ruling has been superseded (e.g., status field, superseded_by
    metadata) and marks them with ``is_superseded=True`` in both the
    PostgreSQL record and the Pinecone vector metadata.

    This ensures superseded content is deprioritised (or excluded) by
    the retrieval pipeline and that supersession warnings are surfaced
    to users.
    """
    logger.info("Scheduled task: check_supersessions — scanning for superseded rulings")

    async def _run() -> dict[str, Any]:
        from sqlalchemy import select as sa_select

        from app.config import get_settings
        from app.core.pinecone_service import PineconeService
        from app.database import get_celery_db_context
        from app.modules.knowledge.collections import INDEX_NAME, get_namespace_with_env
        from app.modules.knowledge.models import ContentChunk, IngestionJob
        from app.modules.knowledge.repository import IngestionJobRepository

        settings = get_settings()
        pinecone = PineconeService(settings.pinecone)

        marked_count = 0
        errors: list[dict] = []

        async with get_celery_db_context() as db:
            job_repo = IngestionJobRepository(db)
            source = await _get_or_create_source(db, "ato_legal_db")

            # Create tracking job
            job = IngestionJob(
                source_id=source.id,
                status="running",
                triggered_by="scheduled",
            )
            job = await job_repo.create(job)
            await job_repo.start_job(job.id)
            await db.commit()

            try:
                # Find chunks that have a non-null superseded_by value
                # but are not yet marked as superseded.
                stmt = sa_select(ContentChunk).where(
                    ContentChunk.superseded_by.isnot(None),
                    ContentChunk.is_superseded.is_(False),
                    ContentChunk.source_type.in_(["ato_ruling", "legislation"]),
                )
                result = await db.execute(stmt)
                chunks_to_mark = result.scalars().all()

                for chunk in chunks_to_mark:
                    try:
                        # Mark in PostgreSQL
                        chunk.is_superseded = True
                        await db.flush()

                        # Update Pinecone metadata — set is_superseded flag
                        # so retrieval filters exclude it by default.
                        collection_name = chunk.collection_name or "compliance_knowledge"
                        pinecone_namespace = get_namespace_with_env(collection_name)

                        if chunk.qdrant_point_id:
                            try:
                                await pinecone.upsert_vectors(
                                    index_name=INDEX_NAME,
                                    ids=[chunk.qdrant_point_id],
                                    vectors=[[0.0]],  # dummy — metadata-only update
                                    payloads=[{"is_superseded": True}],
                                    namespace=pinecone_namespace,
                                )
                            except Exception as pinecone_err:
                                logger.warning(
                                    "Failed to update Pinecone metadata for chunk %s: %s",
                                    chunk.id,
                                    pinecone_err,
                                )

                        marked_count += 1

                    except Exception as e:
                        errors.append(
                            {
                                "chunk_id": str(chunk.id),
                                "error": str(e),
                                "timestamp": datetime.now(tz=UTC).isoformat(),
                            }
                        )
                        logger.warning(
                            "Failed to mark chunk %s as superseded: %s",
                            chunk.id,
                            e,
                        )

                await db.commit()

                # Complete the job
                await job_repo.complete_job(
                    job.id,
                    items_processed=len(chunks_to_mark),
                    items_added=0,
                    items_updated=marked_count,
                    items_skipped=0,
                    items_failed=len(errors),
                    tokens_used=0,
                    errors=errors[:20],
                )
                await db.commit()

            except Exception as exc:
                logger.error("Supersession check job %s failed: %s", job.id, exc)
                await job_repo.fail_job(
                    job.id,
                    errors=[
                        {
                            "error": str(exc),
                            "timestamp": datetime.now(tz=UTC).isoformat(),
                        }
                    ],
                )
                await db.commit()
                raise

        return {
            "marked_superseded": marked_count,
            "errors": len(errors),
        }

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# BM25 index backfill (one-time utility task)
# ---------------------------------------------------------------------------


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="app.tasks.knowledge.backfill_bm25_index",
    time_limit=7200,
    soft_time_limit=7000,
)
def backfill_bm25_index(self: Task) -> dict[str, Any]:
    """Backfill BM25IndexEntry rows for existing ContentChunks.

    One-time utility task that finds all ContentChunk rows without a
    corresponding BM25IndexEntry and creates entries for them.  Because
    chunk text is stored in Pinecone (not PostgreSQL), this task fetches
    text from Pinecone metadata.  Chunks without retrievable text are
    skipped and counted in the result.

    Returns:
        Dict with backfill statistics: created, skipped, failed, total.
    """
    import re

    logger.info("Starting BM25 index backfill")

    async def _run() -> dict[str, Any]:
        from sqlalchemy import select as sa_select
        from sqlalchemy.orm import aliased

        from app.config import get_settings
        from app.core.pinecone_service import PineconeService
        from app.database import get_celery_db_context
        from app.modules.knowledge.collections import INDEX_NAME, get_namespace_with_env
        from app.modules.knowledge.models import BM25IndexEntry, ContentChunk
        from app.modules.knowledge.repository import BM25IndexRepository

        settings = get_settings()
        pinecone = PineconeService(settings.pinecone)

        stats: dict[str, int] = {
            "total": 0,
            "created": 0,
            "skipped_no_text": 0,
            "failed": 0,
        }

        async with get_celery_db_context() as db:
            bm25_repo = BM25IndexRepository(db)

            # Find chunks that have no matching BM25IndexEntry
            bm25_alias = aliased(BM25IndexEntry)
            stmt = (
                sa_select(ContentChunk)
                .outerjoin(
                    bm25_alias,
                    ContentChunk.id == bm25_alias.chunk_id,
                )
                .where(bm25_alias.id.is_(None))
            )
            result = await db.execute(stmt)
            chunks_without_bm25 = result.scalars().all()

            stats["total"] = len(chunks_without_bm25)
            logger.info("Found %d chunks without BM25 entries", stats["total"])

            # Process in batches to manage memory and Pinecone request size
            batch_size = 50
            for batch_start in range(0, len(chunks_without_bm25), batch_size):
                batch = chunks_without_bm25[batch_start : batch_start + batch_size]

                # Group by collection/namespace for efficient Pinecone fetching
                by_namespace: dict[str, list] = {}
                for chunk in batch:
                    ns = get_namespace_with_env(chunk.collection_name or "compliance_knowledge")
                    by_namespace.setdefault(ns, []).append(chunk)

                for namespace, ns_chunks in by_namespace.items():
                    point_ids = [c.qdrant_point_id for c in ns_chunks if c.qdrant_point_id]
                    if not point_ids:
                        stats["skipped_no_text"] += len(ns_chunks)
                        continue

                    # Fetch vectors/metadata from Pinecone
                    try:
                        fetched = await pinecone.fetch_vectors(
                            index_name=INDEX_NAME,
                            ids=point_ids,
                            namespace=namespace,
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to fetch vectors from Pinecone namespace %s: %s",
                            namespace,
                            e,
                        )
                        stats["failed"] += len(ns_chunks)
                        continue

                    # Build lookup: point_id -> metadata
                    fetched_map: dict[str, dict] = {}
                    if fetched:
                        for pid, vec_data in fetched.items():
                            metadata = (
                                vec_data.get("metadata", {})
                                if isinstance(vec_data, dict)
                                else getattr(vec_data, "metadata", {})
                            )
                            if metadata:
                                fetched_map[pid] = metadata

                    for chunk in ns_chunks:
                        try:
                            metadata = fetched_map.get(chunk.qdrant_point_id, {})
                            text = metadata.get("text", "")

                            if not text:
                                stats["skipped_no_text"] += 1
                                continue

                            # Tokenize: simple whitespace + lowercase
                            tokens = re.findall(r"\w+", text.lower())

                            # Extract section references for BM25 filtering
                            section_refs = re.findall(
                                r"(?:s(?:ection)?\s*\d+[\w-]*|"
                                r"[Dd]iv(?:ision)?\s*\d+[\w]*|"
                                r"[Pp]art\s+\d+[\w-]*)",
                                text,
                            )
                            # Normalise refs to lowercase and deduplicate
                            section_refs = list({ref.strip().lower() for ref in section_refs})

                            await bm25_repo.upsert(
                                chunk_id=chunk.id,
                                collection_name=(chunk.collection_name or "compliance_knowledge"),
                                tokens=tokens,
                                section_refs=section_refs,
                            )
                            stats["created"] += 1

                        except Exception as e:
                            stats["failed"] += 1
                            logger.warning(
                                "Failed to create BM25 entry for chunk %s: %s",
                                chunk.id,
                                e,
                            )

                # Commit after each batch
                await db.commit()

                # Update task progress
                processed = stats["created"] + stats["skipped_no_text"] + stats["failed"]
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "processed": processed,
                        "total": stats["total"],
                        "created": stats["created"],
                    },
                )

        logger.info(
            "BM25 backfill complete: %d created, %d skipped (no text), %d failed out of %d total",
            stats["created"],
            stats["skipped_no_text"],
            stats["failed"],
            stats["total"],
        )
        return stats

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()
