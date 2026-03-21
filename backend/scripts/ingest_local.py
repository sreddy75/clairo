#!/usr/bin/env python3
"""Local knowledge base ingestion script.

Run from your local machine to avoid government sites blocking cloud IPs.
Supports ATO Legal Database, Case Law, and TPB pipelines.

Usage:
    cd backend

    # Single pipeline:
    uv run python -m scripts.ingest_local --pipeline case_law --db-url "postgresql://..."
    uv run python -m scripts.ingest_local --pipeline tpb --db-url "postgresql://..."
    uv run python -m scripts.ingest_local --pipeline ato_legal --db-url "postgresql://..."

    # All three blocked pipelines:
    uv run python -m scripts.ingest_local --pipeline all --db-url "postgresql://..."

    # Dev mode (limited items):
    uv run python -m scripts.ingest_local --pipeline case_law --dev
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import sys

sys.path.insert(0, ".")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger("ingest_local")

PIPELINES = ["ato_legal", "case_law", "tpb"]


def _setup_db(db_url: str | None) -> None:
    """Override DATABASE_URL if provided."""
    if not db_url:
        return
    import os

    url = db_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    os.environ["DATABASE_URL"] = url
    host = url.split("@")[-1] if "@" in url else "***"
    logger.info("Using database: %s", host)


# =========================================================================
# ATO Legal Database
# =========================================================================


async def run_ato_legal(dev_mode: bool) -> dict:
    from app.config import get_settings
    from app.core.pinecone_service import PineconeService
    from app.core.voyage import VoyageService
    from app.database import get_celery_db_context
    from app.modules.knowledge.chunkers.ruling import RulingChunker
    from app.modules.knowledge.collections import INDEX_NAME, get_namespace_with_env
    from app.modules.knowledge.ingestion_manager import IngestDecision, IngestionManager
    from app.modules.knowledge.scrapers.ato_legal_db import ATOLegalDatabaseScraper

    settings = get_settings()
    stats = _new_stats()

    async with get_celery_db_context() as db:
        source = await _ensure_source(
            db, "ATO Legal Database", "ato_legal_db", "https://www.ato.gov.au/law/view"
        )
        collection_name = source.collection_name
        ns = get_namespace_with_env(collection_name)

        job = await _create_job(db, source.id)
        pinecone = PineconeService(settings.pinecone)
        voyage = VoyageService(settings.voyage)
        mgr = IngestionManager(db, pinecone, INDEX_NAME, ns)

        scraper_config = (
            {"ruling_types": ["TXR", "GST"], "max_pages_per_type": 2} if dev_mode else {}
        )
        scraper = ATOLegalDatabaseScraper(source_config=scraper_config)
        chunker = RulingChunker()
        dev_limit = 5 if dev_mode else 0

        try:
            count = 0
            async for ruling in scraper.scrape_all():
                if dev_limit and count >= dev_limit:
                    break
                count += 1
                stats["items_processed"] += 1

                ruling_number = ruling.ruling_number or ""
                try:
                    nk = ruling.raw_metadata.get("natural_key", f"ruling:{ruling_number}")
                    dh = ruling.raw_metadata.get(
                        "document_hash", hashlib.sha256(ruling.text.encode()).hexdigest()
                    )

                    decision = await mgr.should_ingest(nk, dh)
                    if decision == IngestDecision.SKIP:
                        stats["items_skipped"] += 1
                        continue

                    chunks = chunker.chunk(ruling.text, metadata={"ruling_number": ruling_number})
                    if not chunks:
                        stats["items_skipped"] += 1
                        continue

                    embeddings = await voyage.embed_batch([c.text for c in chunks], parallel=False)
                    meta = {
                        "ruling_number": ruling_number,
                        "is_superseded": ruling.is_superseded,
                        "superseded_by": ruling.superseded_by,
                        "effective_date": ruling.effective_date.date()
                        if ruling.effective_date
                        else None,
                        "confidence_level": "high",
                    }

                    action = await _ingest(
                        mgr,
                        decision,
                        nk,
                        dh,
                        chunks,
                        embeddings,
                        source.id,
                        collection_name,
                        ruling.source_url,
                        ruling.title,
                        ruling.source_type or "ato_ruling",
                        meta,
                    )
                    stats[f"items_{action}"] += 1
                    await db.commit()
                    logger.info(
                        "  [%d] %s %s — %d chunks",
                        stats["items_processed"],
                        action.upper(),
                        ruling_number or ruling.title[:60],
                        len(chunks),
                    )

                except Exception as e:
                    stats["items_failed"] += 1
                    stats["errors"].append(str(e))
                    logger.warning("  [%d] FAIL %s: %s", stats["items_processed"], ruling_number, e)
                    if "greenlet_spawn" in str(e):
                        logger.warning("Session corrupted (greenlet_spawn), stopping pipeline")
                        break
                    try:
                        await db.rollback()
                    except Exception:
                        logger.warning("Session corrupted, cannot continue")
                        break
        finally:
            await scraper.close()

        await _complete_job(db, job.id, stats)

    return stats


# =========================================================================
# Case Law
# =========================================================================


async def run_case_law(dev_mode: bool) -> dict:
    from app.config import get_settings
    from app.core.pinecone_service import PineconeService
    from app.core.voyage import VoyageService
    from app.database import get_celery_db_context
    from app.modules.knowledge.chunkers.case_law import CaseLawChunker
    from app.modules.knowledge.collections import INDEX_NAME, get_namespace_with_env
    from app.modules.knowledge.ingestion_manager import IngestDecision, IngestionManager
    from app.modules.knowledge.scrapers.case_law import CaseLawScraper

    settings = get_settings()
    stats = _new_stats()

    async with get_celery_db_context() as db:
        source = await _ensure_source(
            db, "Australian Case Law", "case_law", "https://www.fedcourt.gov.au"
        )
        collection_name = source.collection_name
        ns = get_namespace_with_env(collection_name)

        job = await _create_job(db, source.id)
        pinecone = PineconeService(settings.pinecone)
        voyage = VoyageService(settings.voyage)
        mgr = IngestionManager(db, pinecone, INDEX_NAME, ns)

        # In dev_mode, only use RSS feed (not HuggingFace corpus)
        scraper_config = {
            "source": "federal_court_rss" if dev_mode else "both",
            "filter_tax_only": True,
        }
        scraper = CaseLawScraper(source_config=scraper_config)
        chunker = CaseLawChunker()
        dev_limit = 5 if dev_mode else 0

        try:
            count = 0
            async for case in scraper.scrape_all():
                if dev_limit and count >= dev_limit:
                    break
                count += 1
                stats["items_processed"] += 1

                citation = case.raw_metadata.get("case_citation", case.title or "")
                try:
                    nk = case.raw_metadata.get("natural_key", f"case_law:{citation}")
                    dh = case.raw_metadata.get(
                        "document_hash", hashlib.sha256(case.text.encode()).hexdigest()
                    )

                    decision = await mgr.should_ingest(nk, dh)
                    if decision == IngestDecision.SKIP:
                        stats["items_skipped"] += 1
                        continue

                    chunks = chunker.chunk(case.text, metadata={"case_citation": citation})
                    if not chunks:
                        stats["items_skipped"] += 1
                        continue

                    embeddings = await voyage.embed_batch([c.text for c in chunks], parallel=False)
                    meta = {
                        "court": case.raw_metadata.get("court"),
                        "case_citation": citation,
                        "is_superseded": False,
                        "effective_date": case.effective_date.date()
                        if case.effective_date
                        else None,
                        "confidence_level": "medium",
                    }

                    action = await _ingest(
                        mgr,
                        decision,
                        nk,
                        dh,
                        chunks,
                        embeddings,
                        source.id,
                        collection_name,
                        case.source_url,
                        case.title,
                        "case_law",
                        meta,
                    )
                    stats[f"items_{action}"] += 1
                    await db.commit()
                    logger.info(
                        "  [%d] %s %s — %d chunks",
                        stats["items_processed"],
                        action.upper(),
                        citation[:80],
                        len(chunks),
                    )

                except Exception as e:
                    stats["items_failed"] += 1
                    stats["errors"].append(str(e))
                    logger.warning("  [%d] FAIL %s: %s", stats["items_processed"], citation, e)
                    if "greenlet_spawn" in str(e):
                        logger.warning("Session corrupted (greenlet_spawn), stopping pipeline")
                        break
                    try:
                        await db.rollback()
                    except Exception:
                        logger.warning("Session corrupted, cannot continue")
                        break
        finally:
            await scraper.close()

        await _complete_job(db, job.id, stats)

    return stats


# =========================================================================
# TPB & Treasury
# =========================================================================


async def run_tpb(dev_mode: bool) -> dict:
    from app.config import get_settings
    from app.core.pinecone_service import PineconeService
    from app.core.voyage import VoyageService
    from app.database import get_celery_db_context
    from app.modules.knowledge.chunkers.base import ChunkResult
    from app.modules.knowledge.collections import INDEX_NAME, get_namespace_with_env
    from app.modules.knowledge.ingestion_manager import IngestDecision, IngestionManager
    from app.modules.knowledge.scrapers.tpb_treasury import TPBTreasuryScraper

    settings = get_settings()
    stats = _new_stats()

    async with get_celery_db_context() as db:
        source = await _ensure_source(
            db, "TPB & Treasury", "tpb_treasury", "https://www.tpb.gov.au"
        )
        collection_name = source.collection_name
        ns = get_namespace_with_env(collection_name)

        job = await _create_job(db, source.id)
        pinecone = PineconeService(settings.pinecone)
        voyage = VoyageService(settings.voyage)
        mgr = IngestionManager(db, pinecone, INDEX_NAME, ns)

        scraper_config = {}
        if dev_mode:
            scraper_config = {
                "tpb_paths": [
                    "/policy-and-guidance",
                    "/code-professional-conduct",
                    "/apply-register",
                ],
                "treasury_paths": [],
            }
        scraper = TPBTreasuryScraper(source_config=scraper_config)
        dev_limit = 3 if dev_mode else 0

        try:
            count = 0
            async for doc in scraper.scrape_all():
                if dev_limit and count >= dev_limit:
                    break
                count += 1
                stats["items_processed"] += 1

                try:
                    url_hash = hashlib.sha256(doc.source_url.encode()).hexdigest()[:16]
                    nk = doc.raw_metadata.get("natural_key", f"tpb:{url_hash}")
                    dh = doc.raw_metadata.get(
                        "document_hash", hashlib.sha256(doc.text.encode()).hexdigest()
                    )

                    decision = await mgr.should_ingest(nk, dh)
                    if decision == IngestDecision.SKIP:
                        stats["items_skipped"] += 1
                        continue

                    # Paragraph-based chunking for TPB content
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
                        continue

                    embeddings = await voyage.embed_batch([c.text for c in chunks], parallel=False)
                    meta = {"is_superseded": False, "confidence_level": "medium"}

                    action = await _ingest(
                        mgr,
                        decision,
                        nk,
                        dh,
                        chunks,
                        embeddings,
                        source.id,
                        collection_name,
                        doc.source_url,
                        doc.title,
                        "tpb_guidance",
                        meta,
                    )
                    stats[f"items_{action}"] += 1
                    await db.commit()
                    logger.info(
                        "  [%d] %s %s — %d chunks",
                        stats["items_processed"],
                        action.upper(),
                        (doc.title or doc.source_url)[:60],
                        len(chunks),
                    )

                except Exception as e:
                    stats["items_failed"] += 1
                    stats["errors"].append(str(e))
                    logger.warning(
                        "  [%d] FAIL %s: %s", stats["items_processed"], doc.source_url, e
                    )
                    if "greenlet_spawn" in str(e):
                        logger.warning("Session corrupted (greenlet_spawn), stopping pipeline")
                        break
                    try:
                        await db.rollback()
                    except Exception:
                        logger.warning("Session corrupted, cannot continue")
                        break
        finally:
            await scraper.close()

        await _complete_job(db, job.id, stats)

    return stats


# =========================================================================
# Shared helpers
# =========================================================================


def _new_stats() -> dict:
    return {
        "items_processed": 0,
        "items_added": 0,
        "items_updated": 0,
        "items_skipped": 0,
        "items_failed": 0,
        "errors": [],
    }


async def _ensure_source(db, name: str, source_type: str, base_url: str):
    from app.modules.knowledge.models import KnowledgeSource
    from app.modules.knowledge.repository import KnowledgeSourceRepository

    repo = KnowledgeSourceRepository(db)
    source = await repo.get_by_name(name)
    if not source:
        source = KnowledgeSource(
            name=name,
            source_type=source_type,
            base_url=base_url,
            collection_name="compliance_knowledge",
            is_active=True,
        )
        source = await repo.create(source)
        await db.flush()
    return source


async def _create_job(db, source_id):
    from app.modules.knowledge.models import IngestionJob
    from app.modules.knowledge.repository import IngestionJobRepository

    repo = IngestionJobRepository(db)
    job = IngestionJob(
        source_id=source_id, status="running", triggered_by="manual_local", is_resumable=True
    )
    job = await repo.create(job)
    await repo.start_job(job.id)
    await db.commit()
    return job


async def _complete_job(db, job_id, stats):
    from app.modules.knowledge.repository import IngestionJobRepository

    repo = IngestionJobRepository(db)
    await repo.complete_job(
        job_id,
        items_processed=stats["items_processed"],
        items_added=stats["items_added"],
        items_updated=stats["items_updated"],
        items_skipped=stats["items_skipped"],
        items_failed=stats["items_failed"],
        errors=stats["errors"][:20],
    )
    await db.commit()


async def _ingest(
    mgr,
    decision,
    nk,
    dh,
    chunks,
    embeddings,
    source_id,
    collection_name,
    source_url,
    title,
    source_type,
    meta,
) -> str:
    from app.modules.knowledge.ingestion_manager import IngestDecision

    if decision == IngestDecision.REPLACE:
        await mgr.replace_document(
            natural_key=nk,
            new_chunks=chunks,
            new_vectors=embeddings,
            source_id=source_id,
            collection_name=collection_name,
            source_url=source_url,
            title=title,
            source_type=source_type,
            document_hash=dh,
            metadata=meta,
        )
        return "updated"
    else:
        await mgr.insert_document(
            natural_key=nk,
            document_hash=dh,
            chunks=chunks,
            vectors=embeddings,
            source_id=source_id,
            collection_name=collection_name,
            source_url=source_url,
            title=title,
            source_type=source_type,
            metadata=meta,
        )
        return "added"


def _print_stats(name: str, stats: dict) -> None:
    logger.info(
        "  %s: %d processed, %d added, %d updated, %d skipped, %d failed",
        name,
        stats["items_processed"],
        stats["items_added"],
        stats["items_updated"],
        stats["items_skipped"],
        stats["items_failed"],
    )


# =========================================================================
# Main
# =========================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Local knowledge base ingestion (avoids cloud IP blocks)"
    )
    parser.add_argument(
        "--pipeline", required=True, choices=PIPELINES + ["all"], help="Pipeline to run"
    )
    parser.add_argument("--dev", action="store_true", help="Dev mode (limited items)")
    parser.add_argument("--db-url", type=str, help="Database URL (overrides DATABASE_URL env)")
    args = parser.parse_args()

    _setup_db(args.db_url)

    pipelines = PIPELINES if args.pipeline == "all" else [args.pipeline]

    logger.info("=" * 60)
    logger.info("Local Knowledge Ingestion — %s", ", ".join(pipelines))
    logger.info("=" * 60)

    runners = {
        "ato_legal": run_ato_legal,
        "case_law": run_case_law,
        "tpb": run_tpb,
    }

    all_stats = {}
    for name in pipelines:
        logger.info("\n>>> Starting pipeline: %s", name)
        stats = asyncio.run(runners[name](dev_mode=args.dev))
        all_stats[name] = stats
        _print_stats(name, stats)

    logger.info("=" * 60)
    logger.info("ALL COMPLETE")
    for name, stats in all_stats.items():
        _print_stats(name, stats)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
