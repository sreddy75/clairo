#!/usr/bin/env python3
"""Local Tax Planning Topics ingestion script.

Run from your local machine to avoid ATO blocking cloud IPs.
Scrapes ATO pages locally, stores vectors in Pinecone and chunk
records in the target database.

Usage:
    # Against local DB (default):
    cd backend && uv run python -m scripts.ingest_tax_planning_local

    # Against PRODUCTION DB:
    cd backend && uv run python -m scripts.ingest_tax_planning_local --db-url "postgresql://user:pass@host:5432/db"

    # Dry run (scrape only, no storage):
    cd backend && uv run python -m scripts.ingest_tax_planning_local --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from uuid import UUID, uuid4

sys.path.insert(0, ".")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger("ingest_tax_planning")

# Tax planning topic URLs (same as KNOWLEDGE_SOURCES in tasks/knowledge.py)
TAX_PLANNING_CONFIG = {
    "urls": [
        "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/depreciation-and-capital-expenses-and-allowances/simpler-depreciation-for-small-business/instant-asset-write-off",
        "https://www.ato.gov.au/forms-and-instructions/deductions-for-prepaid-expenses-2025",
        "https://www.ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/private-company-benefits-division-7a-dividends",
        "https://www.ato.gov.au/tax-rates-and-codes/division-7a-benchmark-interest-rate",
        "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/incentives-and-concessions",
        "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/incentives-and-concessions/small-business-cgt-concessions",
        "https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/fringe-benefits-tax/exemptions-concessions-and-other-ways-to-reduce-fbt",
        "https://www.ato.gov.au/individuals-and-families/super-for-individuals-and-families/super/growing-and-keeping-track-of-your-super/caps-limits-and-tax-on-super-contributions",
        "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/losses/loss-carry-back-tax-offset",
        "https://www.ato.gov.au/tax-rates-and-codes/company-tax-rate-changes",
        "https://www.ato.gov.au/businesses-and-organisations/trusts/trust-income-losses-and-capital-gains/trust-taxation-reimbursement-agreement",
        "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/incentives-and-concessions/research-and-development-tax-incentive-and-concessions",
        "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/payg-instalments/how-to-vary-your-payg-instalments",
        "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/depreciation-and-capital-expenses-and-allowances/simpler-depreciation-for-small-business",
        "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/deductions/deductions-you-can-claim",
        "https://www.ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/small-business-benchmarks/about-small-business-benchmarks",
    ],
    "max_depth": 1,
}

COLLECTION_NAME = "compliance_knowledge"
SOURCE_NAME = "ATO Tax Planning Topics"


async def run(db_url: str | None = None, dry_run: bool = False) -> dict:
    import os

    if db_url:
        url = db_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        os.environ["DATABASE_URL"] = url
        host = url.split("@")[-1].split("/")[0] if "@" in url else "***"
        logger.info("Target database: %s", host)

    from app.config import get_settings
    from app.core.pinecone_service import PineconeService
    from app.core.voyage import VoyageService
    from app.database import get_celery_db_context
    from app.modules.knowledge.chunker import SemanticChunker
    from app.modules.knowledge.collections import INDEX_NAME, get_namespace_with_env
    from app.modules.knowledge.models import ContentChunk, IngestionJob, KnowledgeSource
    from app.modules.knowledge.repository import (
        ContentChunkRepository,
        IngestionJobRepository,
        KnowledgeSourceRepository,
    )
    from app.modules.knowledge.scrapers.ato_web import ATOWebScraper

    settings = get_settings()
    pinecone_namespace = get_namespace_with_env(COLLECTION_NAME)

    stats = {
        "items_processed": 0,
        "items_added": 0,
        "items_skipped": 0,
        "items_failed": 0,
        "errors": [],
    }

    logger.info("Pinecone namespace: %s", pinecone_namespace)
    logger.info("Scraping %d URLs...", len(TAX_PLANNING_CONFIG["urls"]))

    # Scrape first (from local machine where ATO doesn't block)
    scraped_pages = []
    async with ATOWebScraper(source_config=TAX_PLANNING_CONFIG) as scraper:
        async for content in scraper.scrape_all():
            scraped_pages.append(content)
            logger.info(
                "  Scraped: %s (%d chars)",
                content.title or content.source_url[-60:],
                len(content.text),
            )

    logger.info("Scraped %d pages successfully", len(scraped_pages))

    if not scraped_pages:
        logger.error("No pages scraped — check network connectivity")
        return stats

    if dry_run:
        logger.info("Dry run — skipping storage")
        stats["items_processed"] = len(scraped_pages)
        return stats

    # Now store in DB + Pinecone
    pinecone = PineconeService(settings.pinecone)
    voyage = VoyageService(settings.voyage)
    chunker = SemanticChunker()

    async with get_celery_db_context() as db:
        source_repo = KnowledgeSourceRepository(db)
        chunk_repo = ContentChunkRepository(db)
        job_repo = IngestionJobRepository(db)

        # Get or create source
        source = await source_repo.get_by_name(SOURCE_NAME)
        if not source:
            source = KnowledgeSource(
                name=SOURCE_NAME,
                source_type="ato_web",
                base_url="https://www.ato.gov.au",
                collection_name=COLLECTION_NAME,
                is_active=True,
                scrape_config=TAX_PLANNING_CONFIG,
            )
            source = await source_repo.create(source)
            await db.flush()

        source_id = str(source.id)

        # Create job record
        job = IngestionJob(
            source_id=source.id,
            status="running",
            triggered_by="manual_local",
        )
        job = await job_repo.create(job)
        await job_repo.start_job(job.id)
        await db.commit()

        for content in scraped_pages:
            try:
                stats["items_processed"] += 1

                # Chunk
                chunks = chunker.chunk_text(
                    content.text,
                    metadata={"source_url": content.source_url},
                )
                if not chunks:
                    stats["items_skipped"] += 1
                    logger.info("  SKIP (no chunks): %s", content.source_url[-60:])
                    continue

                # Check dedup
                existing = await chunk_repo.get_by_hash(chunks[0].content_hash)
                if existing:
                    stats["items_skipped"] += 1
                    logger.info("  SKIP (exists): %s", content.title or content.source_url[-60:])
                    continue

                # Embed
                chunk_texts = [c.text for c in chunks]
                embeddings = await voyage.embed_batch(chunk_texts, parallel=False)

                # Store each chunk
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=False)):
                    chunk_uuid = uuid4()
                    qdrant_point_id = str(chunk_uuid)

                    # Pinecone metadata
                    metadata = content.to_chunk_payload(
                        chunk_id=str(chunk_uuid),
                        source_id=source_id,
                        chunk_index=i,
                    )
                    metadata["text"] = chunk.text
                    metadata["_collection"] = COLLECTION_NAME
                    metadata = {k: v for k, v in metadata.items() if v is not None}

                    # Upsert vector
                    await pinecone.upsert_vectors(
                        index_name=INDEX_NAME,
                        ids=[qdrant_point_id],
                        vectors=[embedding],
                        payloads=[metadata],
                        namespace=pinecone_namespace,
                    )

                    # Store DB record
                    db_chunk = ContentChunk(
                        id=chunk_uuid,
                        source_id=UUID(source_id),
                        qdrant_point_id=qdrant_point_id,
                        collection_name=COLLECTION_NAME,
                        content_hash=chunk.content_hash,
                        source_url=content.source_url,
                        title=content.title,
                        source_type=content.source_type,
                        effective_date=content.effective_date.date()
                        if content.effective_date
                        else None,
                        expiry_date=content.expiry_date.date()
                        if content.expiry_date
                        else None,
                        entity_types=content.entity_types,
                        industries=content.industries,
                        ruling_number=content.ruling_number,
                        is_superseded=content.is_superseded,
                        superseded_by=content.superseded_by,
                    )
                    await chunk_repo.create(db_chunk)

                await db.commit()
                stats["items_added"] += 1
                logger.info(
                    "  ADD [%d] %s — %d chunks",
                    stats["items_added"],
                    content.title or content.source_url[-60:],
                    len(chunks),
                )

            except Exception as e:
                stats["items_failed"] += 1
                stats["errors"].append(f"{content.source_url}: {e}")
                logger.warning("  FAIL %s: %s", content.source_url[-50:], e)
                await db.rollback()

        # Complete job
        await job_repo.complete_job(
            job.id,
            items_processed=stats["items_processed"],
            items_added=stats["items_added"],
            items_updated=0,
            items_skipped=stats["items_skipped"],
            items_failed=stats["items_failed"],
            errors=stats["errors"][:20],
        )
        await db.commit()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Local Tax Planning Topics ingestion")
    parser.add_argument("--db-url", type=str, help="Database URL (overrides DATABASE_URL)")
    parser.add_argument("--dry-run", action="store_true", help="Scrape only, don't store")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("ATO Tax Planning Topics — Local Ingestion")
    logger.info("=" * 60)

    stats = asyncio.run(run(db_url=args.db_url, dry_run=args.dry_run))

    logger.info("=" * 60)
    logger.info("COMPLETE")
    logger.info("  Processed: %d", stats["items_processed"])
    logger.info("  Added:     %d", stats["items_added"])
    logger.info("  Skipped:   %d", stats["items_skipped"])
    logger.info("  Failed:    %d", stats["items_failed"])
    if stats["errors"]:
        logger.info("  Errors:")
        for err in stats["errors"][:5]:
            logger.info("    - %s", err)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
