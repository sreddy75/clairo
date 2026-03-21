#!/usr/bin/env python3
"""Seed script for knowledge base sources.

This script creates the default knowledge sources for a fresh deployment.
Run this after database migrations on a new environment.

Usage:
    # From backend directory
    uv run python scripts/seed_knowledge_sources.py

    # Or via Docker
    docker exec clairo-backend python scripts/seed_knowledge_sources.py

The script is idempotent - running it multiple times will not create duplicates.
"""

import asyncio
import logging
import sys
from pathlib import Path
from uuid import uuid4

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_celery_db_context
from app.modules.knowledge.models import KnowledgeSource

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# Default Knowledge Sources Configuration
# =============================================================================

DEFAULT_SOURCES = [
    # -------------------------------------------------------------------------
    # ATO API Sources (PDF Guides) - HIGH QUALITY
    # -------------------------------------------------------------------------
    {
        "name": "ATO BAS Complete Guide",
        "source_type": "ato_api",
        "base_url": "https://www.ato.gov.au/api/public/content",
        "collection_name": "compliance_knowledge",
        "scrape_config": {
            "content_ids": ["bas_guide"],
        },
        "is_active": True,
    },
    {
        "name": "ATO GST Complete Guide",
        "source_type": "ato_api",
        "base_url": "https://www.ato.gov.au/api/public/content",
        "collection_name": "compliance_knowledge",
        "scrape_config": {
            "content_ids": ["gst_guide"],
        },
        "is_active": True,
    },
    {
        "name": "ATO PAYG Withholding Guide",
        "source_type": "ato_api",
        "base_url": "https://www.ato.gov.au/api/public/content",
        "collection_name": "compliance_knowledge",
        "scrape_config": {
            "content_ids": ["payg_withholding"],
        },
        "is_active": True,
    },
    {
        "name": "ATO FBT Guide",
        "source_type": "ato_api",
        "base_url": "https://www.ato.gov.au/api/public/content",
        "collection_name": "compliance_knowledge",
        "scrape_config": {
            "content_ids": ["fbt_guide"],
        },
        "is_active": True,
    },
    {
        "name": "ATO Due Dates Reference",
        "source_type": "ato_api",
        "base_url": "https://www.ato.gov.au/api/public/content",
        "collection_name": "compliance_knowledge",
        "scrape_config": {
            "content_ids": ["due_dates"],
        },
        "is_active": True,
    },
    {
        "name": "ATO Starting a Business Guide",
        "source_type": "ato_api",
        "base_url": "https://www.ato.gov.au/api/public/content",
        "collection_name": "business_fundamentals",
        "scrape_config": {
            "content_ids": ["starting_business"],
        },
        "is_active": True,
    },
    # -------------------------------------------------------------------------
    # ATO Web Scraper Sources
    # -------------------------------------------------------------------------
    {
        "name": "ATO BAS Due Dates",
        "source_type": "ato_web",
        "base_url": "https://www.ato.gov.au",
        "collection_name": "compliance_knowledge",
        "scrape_config": {
            "urls": [
                "https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas/due-dates-for-lodging-and-paying-your-bas",
            ],
            "max_depth": 0,
        },
        "is_active": True,
    },
    {
        "name": "ATO GST Registration",
        "source_type": "ato_web",
        "base_url": "https://www.ato.gov.au",
        "collection_name": "compliance_knowledge",
        "scrape_config": {
            "urls": [
                "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/registering-for-gst",
            ],
            "max_depth": 1,
        },
        "is_active": True,
    },
    {
        "name": "ATO Small Business Deductions",
        "source_type": "ato_web",
        "base_url": "https://www.ato.gov.au",
        "collection_name": "financial_management",
        "scrape_config": {
            "urls": [
                "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions",
            ],
            "max_depth": 1,
        },
        "is_active": True,
    },
    {
        "name": "ATO Super for Employers",
        "source_type": "ato_web",
        "base_url": "https://www.ato.gov.au",
        "collection_name": "compliance_knowledge",
        "scrape_config": {
            "urls": [
                "https://www.ato.gov.au/businesses-and-organisations/super-for-employers",
            ],
            "max_depth": 1,
        },
        "is_active": True,
    },
]


async def seed_sources() -> dict:
    """Create default knowledge sources if they don't exist.

    Returns:
        Dict with counts of created and skipped sources.
    """
    created_count = 0
    skipped_count = 0

    async with get_celery_db_context() as db:
        for source_config in DEFAULT_SOURCES:
            # Check if source already exists by name
            from sqlalchemy import select

            existing = await db.execute(
                select(KnowledgeSource).where(KnowledgeSource.name == source_config["name"])
            )
            if existing.scalar_one_or_none():
                logger.info(f"Skipping existing source: {source_config['name']}")
                skipped_count += 1
                continue

            # Create new source
            source = KnowledgeSource(
                id=uuid4(),
                name=source_config["name"],
                source_type=source_config["source_type"],
                base_url=source_config["base_url"],
                collection_name=source_config["collection_name"],
                scrape_config=source_config["scrape_config"],
                is_active=source_config["is_active"],
            )
            db.add(source)
            logger.info(f"Created source: {source_config['name']}")
            created_count += 1

        await db.commit()

    return {
        "created": created_count,
        "skipped": skipped_count,
        "total": len(DEFAULT_SOURCES),
    }


async def trigger_ingestion(source_names: list[str] | None = None) -> dict:
    """Trigger ingestion jobs for sources.

    Args:
        source_names: List of source names to ingest. If None, ingest all active sources.

    Returns:
        Dict with job IDs.
    """
    from app.modules.knowledge.models import IngestionJob
    from app.tasks.knowledge import ingest_source

    jobs_created = []

    async with get_celery_db_context() as db:
        from sqlalchemy import select

        # Get sources to ingest
        query = select(KnowledgeSource).where(KnowledgeSource.is_active == True)  # noqa: E712
        if source_names:
            query = query.where(KnowledgeSource.name.in_(source_names))

        result = await db.execute(query)
        sources = result.scalars().all()

        for source in sources:
            # Create job record
            job = IngestionJob(
                id=uuid4(),
                source_id=source.id,
                status="pending",
                triggered_by="seed_script",
            )
            db.add(job)
            await db.commit()
            await db.refresh(job)

            # Queue the task
            ingest_source.delay(str(source.id), str(job.id))

            jobs_created.append(
                {
                    "source_name": source.name,
                    "source_id": str(source.id),
                    "job_id": str(job.id),
                }
            )
            logger.info(f"Queued ingestion job for: {source.name}")

    return {
        "jobs_created": len(jobs_created),
        "jobs": jobs_created,
    }


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Seed knowledge base sources")
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Trigger ingestion jobs after creating sources",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        help="Specific source names to ingest (requires --ingest)",
    )
    args = parser.parse_args()

    logger.info("Starting knowledge source seeding...")

    # Create sources
    result = await seed_sources()
    logger.info(
        f"Seeding complete: {result['created']} created, "
        f"{result['skipped']} skipped, {result['total']} total"
    )

    # Optionally trigger ingestion
    if args.ingest:
        logger.info("Triggering ingestion jobs...")
        ingest_result = await trigger_ingestion(args.sources)
        logger.info(f"Queued {ingest_result['jobs_created']} ingestion jobs")

    logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())
