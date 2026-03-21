#!/usr/bin/env python3
"""Local ATO Legal Database ingestion script.

Run this from your local machine to avoid ATO blocking cloud IPs.
Uses the same ingestion pipeline as the Celery task but runs directly.

Usage:
    # Dev mode (5 items, tests connectivity):
    cd backend && uv run python -m scripts.ingest_ato_local --dev

    # Full ingestion against local DB (vectors go to shared Pinecone namespace):
    cd backend && uv run python -m scripts.ingest_ato_local

    # Full ingestion against PRODUCTION DB:
    cd backend && uv run python -m scripts.ingest_ato_local --db-url "postgresql://user:pass@host:5432/db"
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import sys

# Ensure backend/ is on the path
sys.path.insert(0, ".")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger("ingest_ato_local")


async def run(dev_mode: bool = False, db_url: str | None = None) -> dict:
    import os

    # Override DATABASE_URL if provided (convert postgres:// to asyncpg)
    if db_url:
        url = db_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        os.environ["DATABASE_URL"] = url
        logger.info(
            "Using database: %s@%s",
            url.split("@")[0].split("://")[0],
            url.split("@")[-1] if "@" in url else "***",
        )

    from app.config import get_settings
    from app.core.pinecone_service import PineconeService
    from app.core.voyage import VoyageService
    from app.database import get_celery_db_context
    from app.modules.knowledge.chunkers.base import ChunkResult
    from app.modules.knowledge.chunkers.ruling import RulingChunker
    from app.modules.knowledge.collections import INDEX_NAME, get_namespace_with_env
    from app.modules.knowledge.ingestion_manager import IngestDecision, IngestionManager
    from app.modules.knowledge.models import IngestionJob, KnowledgeSource
    from app.modules.knowledge.repository import (
        BM25IndexRepository,
        ContentCrossReferenceRepository,
        IngestionJobRepository,
        KnowledgeSourceRepository,
    )
    from app.modules.knowledge.scrapers.ato_legal_db import ATOLegalDatabaseScraper

    settings = get_settings()

    stats = {
        "items_processed": 0,
        "items_added": 0,
        "items_updated": 0,
        "items_skipped": 0,
        "items_failed": 0,
        "errors": [],
    }

    async with get_celery_db_context() as db:
        # Get or create knowledge source
        source_repo = KnowledgeSourceRepository(db)
        source = await source_repo.get_by_name("ATO Legal Database")
        if not source:
            source = KnowledgeSource(
                name="ATO Legal Database",
                source_type="ato_legal_db",
                base_url="https://www.ato.gov.au/law/view",
                collection_name="compliance_knowledge",
                is_active=True,
            )
            source = await source_repo.create(source)
            await db.flush()

        collection_name = source.collection_name
        pinecone_namespace = get_namespace_with_env(collection_name)

        logger.info(
            "Pinecone namespace: %s (shared=%s)",
            pinecone_namespace,
            pinecone_namespace == collection_name,
        )

        # Create ingestion job record
        job_repo = IngestionJobRepository(db)
        job = IngestionJob(
            source_id=source.id,
            status="running",
            triggered_by="manual_local",
            is_resumable=True,
        )
        job = await job_repo.create(job)
        await job_repo.start_job(job.id)
        await db.commit()

        # Initialise services
        pinecone = PineconeService(settings.pinecone)
        voyage = VoyageService(settings.voyage)
        bm25_repo = BM25IndexRepository(db)
        xref_repo = ContentCrossReferenceRepository(db)
        ingestion_manager = IngestionManager(
            db,
            pinecone,
            INDEX_NAME,
            pinecone_namespace,
        )

        # Configure scraper
        scraper_config = {}
        if dev_mode:
            scraper_config = {
                "ruling_types": ["TXR", "GST"],
                "max_pages_per_type": 2,
            }

        ruling_chunker = RulingChunker()
        scraper = ATOLegalDatabaseScraper(source_config=scraper_config)
        dev_limit = 5 if dev_mode else 0

        item_count = 0
        logger.info("Starting ATO Legal Database scrape (dev_mode=%s)...", dev_mode)

        try:
            async for ruling in scraper.scrape_all():
                if dev_limit and item_count >= dev_limit:
                    logger.info("Dev mode: reached limit of %d items", dev_limit)
                    break
                item_count += 1
                stats["items_processed"] += 1

                source_url = ruling.source_url
                ruling_number = ruling.ruling_number or ""

                try:
                    natural_key = ruling.raw_metadata.get("natural_key", f"ruling:{ruling_number}")
                    document_hash = ruling.raw_metadata.get(
                        "document_hash",
                        hashlib.sha256(ruling.text.encode()).hexdigest(),
                    )

                    decision = await ingestion_manager.should_ingest(natural_key, document_hash)

                    if decision == IngestDecision.SKIP:
                        stats["items_skipped"] += 1
                        logger.info(
                            "  [%d] SKIP %s (unchanged)",
                            stats["items_processed"],
                            ruling_number or source_url,
                        )
                        continue

                    # Chunk
                    chunks: list[ChunkResult] = ruling_chunker.chunk(
                        ruling.text,
                        metadata={"ruling_number": ruling_number},
                    )
                    if not chunks:
                        stats["items_skipped"] += 1
                        logger.info(
                            "  [%d] SKIP %s (no chunks)",
                            stats["items_processed"],
                            ruling_number,
                        )
                        continue

                    # Embed
                    chunk_texts = [c.text for c in chunks]
                    embeddings = await voyage.embed_batch(chunk_texts, parallel=False)

                    # Metadata
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

                    # Ingest
                    if decision == IngestDecision.REPLACE:
                        await ingestion_manager.replace_document(
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
                        action = "UPDATE"
                    else:
                        await ingestion_manager.insert_document(
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
                        action = "ADD"

                    # BM25 + cross-references (best-effort)
                    # Skipped for local script to keep it simple

                    await db.commit()

                    logger.info(
                        "  [%d] %s %s — %d chunks",
                        stats["items_processed"],
                        action,
                        ruling_number or ruling.title[:60],
                        len(chunks),
                    )

                except Exception as e:
                    stats["items_failed"] += 1
                    stats["errors"].append(str(e))
                    logger.warning(
                        "  [%d] FAIL %s: %s",
                        stats["items_processed"],
                        ruling_number or source_url,
                        e,
                    )
                    await db.rollback()

        finally:
            await scraper.close()

        # Complete job
        await job_repo.complete_job(
            job.id,
            items_processed=stats["items_processed"],
            items_added=stats["items_added"],
            items_updated=stats["items_updated"],
            items_skipped=stats["items_skipped"],
            items_failed=stats["items_failed"],
            errors=stats["errors"][:20],
        )
        await db.commit()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Local ATO Legal Database ingestion")
    parser.add_argument("--dev", action="store_true", help="Dev mode (5 items only)")
    parser.add_argument("--db-url", type=str, help="Database URL (overrides DATABASE_URL env)")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("ATO Legal Database — Local Ingestion")
    logger.info("=" * 60)

    stats = asyncio.run(run(dev_mode=args.dev, db_url=args.db_url))

    logger.info("=" * 60)
    logger.info("COMPLETE")
    logger.info("  Processed: %d", stats["items_processed"])
    logger.info("  Added:     %d", stats["items_added"])
    logger.info("  Updated:   %d", stats["items_updated"])
    logger.info("  Skipped:   %d", stats["items_skipped"])
    logger.info("  Failed:    %d", stats["items_failed"])
    if stats["errors"]:
        logger.info("  Errors:")
        for err in stats["errors"][:5]:
            logger.info("    - %s", err)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
