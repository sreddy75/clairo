"""Backfill BM25 index entries for content chunks missing them.

Connects directly to the database and Pinecone to create BM25IndexEntry
rows for any ContentChunk that doesn't have one yet. This fixes the issue
where non-legislation source types (ato_ruling, ato_guide, tpb_guidance,
ato_api) were ingested without BM25 entries, causing hybrid search to
only return legislation results.

Usage:
    python scripts/backfill_bm25.py
"""

import asyncio
import logging
import os
import re
import sys

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    from sqlalchemy import select as sa_select
    from sqlalchemy.orm import aliased

    from app.config import get_settings
    from app.core.pinecone_service import PineconeService
    from app.database import get_engine, get_session_factory
    from app.modules.knowledge.collections import INDEX_NAME, get_namespace_with_env
    from app.modules.knowledge.models import BM25IndexEntry, ContentChunk
    from app.modules.knowledge.repository import BM25IndexRepository

    settings = get_settings()
    pinecone = PineconeService(settings.pinecone)

    session_factory = get_session_factory()
    async with session_factory() as db:
        bm25_repo = BM25IndexRepository(db)

        # Find chunks without BM25 entries
        bm25_alias = aliased(BM25IndexEntry)
        stmt = (
            sa_select(ContentChunk)
            .outerjoin(bm25_alias, ContentChunk.id == bm25_alias.chunk_id)
            .where(bm25_alias.id.is_(None))
        )
        result = await db.execute(stmt)
        chunks = result.scalars().all()

        logger.info("Found %d chunks without BM25 entries", len(chunks))
        if not chunks:
            logger.info("Nothing to backfill!")
            return

        # Show breakdown by source_type
        by_type: dict[str, int] = {}
        for c in chunks:
            by_type[c.source_type] = by_type.get(c.source_type, 0) + 1
        for st, count in sorted(by_type.items(), key=lambda x: -x[1]):
            logger.info("  %s: %d chunks", st, count)

        # Process in batches
        batch_size = 50
        created = 0
        skipped = 0
        failed = 0

        for batch_start in range(0, len(chunks), batch_size):
            batch = chunks[batch_start : batch_start + batch_size]

            # Group by namespace
            by_namespace: dict[str, list] = {}
            for chunk in batch:
                ns = get_namespace_with_env(chunk.collection_name or "compliance_knowledge")
                by_namespace.setdefault(ns, []).append(chunk)

            for namespace, ns_chunks in by_namespace.items():
                point_ids = [c.qdrant_point_id for c in ns_chunks if c.qdrant_point_id]
                if not point_ids:
                    skipped += len(ns_chunks)
                    continue

                try:
                    fetched = await pinecone.fetch_vectors(
                        index_name=INDEX_NAME,
                        ids=point_ids,
                        namespace=namespace,
                    )
                except Exception as e:
                    logger.warning("Failed to fetch from Pinecone ns=%s: %s", namespace, e)
                    failed += len(ns_chunks)
                    continue

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
                            skipped += 1
                            continue

                        tokens = re.findall(r"\w+", text.lower())
                        section_refs = re.findall(
                            r"(?:s(?:ection)?\s*\d+[\w-]*|"
                            r"[Dd]iv(?:ision)?\s*\d+[\w]*|"
                            r"[Pp]art\s+\d+[\w-]*)",
                            text,
                        )
                        section_refs = list({ref.strip().lower() for ref in section_refs})

                        await bm25_repo.upsert(
                            chunk_id=chunk.id,
                            collection_name=chunk.collection_name or "compliance_knowledge",
                            tokens=tokens,
                            section_refs=section_refs,
                        )
                        created += 1
                    except Exception as e:
                        failed += 1
                        logger.warning("Failed BM25 for chunk %s: %s", chunk.id, e)

            await db.commit()
            logger.info(
                "Progress: %d/%d (created=%d, skipped=%d, failed=%d)",
                min(batch_start + batch_size, len(chunks)),
                len(chunks),
                created,
                skipped,
                failed,
            )

        logger.info(
            "BM25 backfill complete: created=%d, skipped=%d, failed=%d",
            created,
            skipped,
            failed,
        )

    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(main())
