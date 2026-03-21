"""Semantic deduplication for insights using Voyage AI + Pinecone.

Embeds insight title+summary and searches for semantically similar active
insights per client. When a match is found the existing insight is updated
instead of creating a duplicate.

All external calls (Voyage, Pinecone) are best-effort — failures log warnings
but never block insight creation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from app.modules.knowledge.collections import INDEX_NAME, get_namespace_with_env

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.pinecone_service import PineconeService
    from app.core.voyage import VoyageService
    from app.modules.insights.models import Insight

logger = logging.getLogger(__name__)

# Cosine similarity threshold for dedup matching.
# Tested values: true duplicates score 0.73–0.77, non-duplicates 0.50–0.55.
# 0.72 catches clear semantic duplicates with safe margin from false positives.
DEDUP_SCORE_THRESHOLD = 0.72

DEDUP_NAMESPACE_BASE = "insight_dedup"


def _dedup_namespace() -> str:
    """Get the environment-qualified namespace for insight dedup vectors."""
    return get_namespace_with_env(DEDUP_NAMESPACE_BASE)


def _embed_text(insight_title: str, insight_summary: str) -> str:
    """Build the text string that gets embedded for dedup comparison."""
    return f"{insight_title} | {insight_summary}"


class InsightDedupService:
    """Semantic deduplication service for insights.

    Uses Voyage AI embeddings + Pinecone vector search to detect
    semantically similar insights per client.
    """

    def __init__(
        self,
        pinecone: PineconeService,
        voyage: VoyageService,
        db: AsyncSession,
    ) -> None:
        self._pinecone = pinecone
        self._voyage = voyage
        self._db = db

    async def find_duplicate(
        self,
        title: str,
        summary: str,
        client_id: UUID,
        tenant_id: UUID,
    ) -> Insight | None:
        """Search for a semantically similar active insight for this client.

        Args:
            title: Candidate insight title.
            summary: Candidate insight summary.
            client_id: Client (XeroConnection) ID to scope the search.
            tenant_id: Tenant ID (stored in metadata, used for defence-in-depth).

        Returns:
            Existing Insight model if a semantic duplicate is found, else None.
        """
        try:
            text = _embed_text(title, summary)
            vector = await self._voyage.embed_query(text)

            results = await self._pinecone.search(
                index_name=INDEX_NAME,
                query_vector=vector,
                namespace=_dedup_namespace(),
                filter={"client_id": {"$eq": str(client_id)}},
                limit=1,
                include_metadata=True,
            )

            if not results or results[0].score < DEDUP_SCORE_THRESHOLD:
                return None

            match = results[0]
            insight_id = match.payload.get("insight_id") if match.payload else None
            if not insight_id:
                logger.warning("Dedup match missing insight_id in metadata")
                return None

            # Look up the existing insight from the database
            from sqlalchemy import select

            from app.modules.insights.models import Insight, InsightStatus

            result = await self._db.execute(
                select(Insight).where(
                    Insight.id == UUID(insight_id),
                    Insight.tenant_id == tenant_id,
                    Insight.status.notin_(
                        [
                            InsightStatus.DISMISSED.value,
                            InsightStatus.EXPIRED.value,
                        ]
                    ),
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                logger.info(
                    f"Semantic dedup: matched '{title}' to existing insight "
                    f"{existing.id} (score={match.score:.3f})"
                )
            else:
                # Insight was dismissed/expired/deleted — stale vector, clean it up
                logger.debug(f"Dedup match {insight_id} no longer active, removing stale vector")
                await self.remove_insight(UUID(insight_id))

            return existing

        except Exception:
            logger.warning("Semantic dedup search failed, skipping", exc_info=True)
            return None

    async def index_insight(self, insight: Insight) -> None:
        """Store a vector for a newly created insight.

        Args:
            insight: The newly created Insight model.
        """
        try:
            text = _embed_text(insight.title, insight.summary)
            vector = await self._voyage.embed_text(text, input_type="document")

            await self._pinecone.upsert_vectors(
                index_name=INDEX_NAME,
                ids=[str(insight.id)],
                vectors=[vector],
                payloads=[
                    {
                        "tenant_id": str(insight.tenant_id),
                        "client_id": str(insight.client_id) if insight.client_id else "",
                        "insight_id": str(insight.id),
                        "category": insight.category,
                    }
                ],
                namespace=_dedup_namespace(),
            )
            logger.debug(f"Indexed dedup vector for insight {insight.id}")

        except Exception:
            logger.warning(
                f"Failed to index dedup vector for insight {insight.id}",
                exc_info=True,
            )

    async def update_insight_vector(self, insight: Insight) -> None:
        """Refresh the vector for an updated insight (upsert is idempotent).

        Args:
            insight: The updated Insight model.
        """
        # Pinecone upsert overwrites existing vectors with the same ID,
        # so index_insight already handles updates.
        await self.index_insight(insight)

    async def remove_insight(self, insight_id: UUID) -> None:
        """Delete the dedup vector for an insight.

        Called when an insight is actioned, dismissed, or expired so that
        future generations can recreate it if the issue resurfaces.

        Args:
            insight_id: ID of the insight whose vector should be removed.
        """
        try:
            await self._pinecone.delete_vectors(
                index_name=INDEX_NAME,
                ids=[str(insight_id)],
                namespace=_dedup_namespace(),
            )
            logger.debug(f"Removed dedup vector for insight {insight_id}")

        except Exception:
            logger.warning(
                f"Failed to remove dedup vector for insight {insight_id}",
                exc_info=True,
            )

    async def remove_insights_batch(self, insight_ids: list[UUID]) -> None:
        """Batch-delete dedup vectors for multiple insights.

        Args:
            insight_ids: List of insight IDs whose vectors should be removed.
        """
        if not insight_ids:
            return

        try:
            await self._pinecone.delete_vectors(
                index_name=INDEX_NAME,
                ids=[str(iid) for iid in insight_ids],
                namespace=_dedup_namespace(),
            )
            logger.debug(f"Removed {len(insight_ids)} dedup vectors in batch")

        except Exception:
            logger.warning(
                f"Failed to batch-remove {len(insight_ids)} dedup vectors",
                exc_info=True,
            )
