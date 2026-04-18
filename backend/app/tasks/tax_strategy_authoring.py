"""Celery tasks for the tax_strategies authoring pipeline (Spec 060).

Four stages — research, draft, enrich, publish — one task per stage. Each
task writes a TaxStrategyAuthoringJob row and advances the TaxStrategy's
status via TaxStrategyService._transition_status.

Task names match the routes configured in tasks/celery_app.py::TASK_ROUTES
so Celery pins them to the dedicated `tax_strategies` queue.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from celery import Task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.core.pinecone_service import PineconeService
from app.core.voyage import VoyageService
from app.modules.knowledge.chunkers.strategy import StrategyChunker, StrategyChunkerInput
from app.modules.knowledge.collections import INDEX_NAME, get_namespace_with_env
from app.modules.knowledge.models import BM25IndexEntry, ContentChunk, KnowledgeSource
from app.modules.tax_strategies.env_gate import vector_writes_enabled
from app.modules.tax_strategies.exceptions import (
    InvalidStatusTransitionError,
    StrategyNotFoundError,
    VectorWriteDisabledError,
)
from app.modules.tax_strategies.models import TaxStrategy
from app.modules.tax_strategies.service import TaxStrategyService
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# A singleton KnowledgeSource row is used as the source_id for all strategy
# ContentChunk rows (FK is NOT NULL on content_chunks). Get-or-create under
# this well-known name.
_STRATEGY_SOURCE_NAME = "tax_strategies_internal"
_STRATEGY_COLLECTION = "tax_strategies"


# ---------------------------------------------------------------------------
# Shared session helper — mirrors xero_writeback pattern.
# ---------------------------------------------------------------------------


def _make_session_factory() -> sessionmaker[AsyncSession]:
    settings = get_settings()
    engine = create_async_engine(settings.database.url, echo=False, poolclass=NullPool)
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Publish (T027) — env-gated, deterministic vector IDs
# ---------------------------------------------------------------------------


@dataclass
class _PublishOutcome:
    chunk_count: int
    vector_ids: list[str]
    vector_store_namespace: str


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="tax_strategies.publish",
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def publish_strategy(
    self: Task, strategy_id: str, triggered_by: str
) -> dict[str, Any]:
    """Chunk → embed → upsert to Pinecone → write ContentChunk/BM25 rows.

    Env gate (FR-028): when TAX_STRATEGIES_VECTOR_WRITE_ENABLED is false the
    job is marked failed with `vector_write_disabled_in_this_environment`
    and the strategy stays in status=approved.
    """
    return asyncio.run(_run_publish(strategy_id, triggered_by))


async def _run_publish(strategy_id: str, triggered_by: str) -> dict[str, Any]:
    factory = _make_session_factory()
    async with factory() as session:
        svc = TaxStrategyService(session)
        strategy = await svc.repo.get_live_version(strategy_id)
        if strategy is None:
            raise StrategyNotFoundError(strategy_id)

        job = await svc.repo.create_job(
            strategy_id=strategy_id,
            stage="publish",
            triggered_by=triggered_by,
            input_payload={"version": strategy.version},
        )
        await svc.repo.update_job(
            job, status="running", started_at=datetime.now(UTC)
        )
        await session.commit()

        try:
            outcome = await _execute_publish(session, svc, strategy)
        except VectorWriteDisabledError as exc:
            await svc.repo.update_job(
                job,
                status="failed",
                completed_at=datetime.now(UTC),
                error=VectorWriteDisabledError.code,
                output_payload={"message": str(exc)},
            )
            await session.commit()
            logger.warning(
                "publish_strategy.env_gate_blocked: %s", exc.strategy_id
            )
            return {
                "status": "failed",
                "error": VectorWriteDisabledError.code,
                "strategy_id": strategy_id,
            }
        except InvalidStatusTransitionError as exc:
            await svc.repo.update_job(
                job,
                status="failed",
                completed_at=datetime.now(UTC),
                error=f"invalid_status_transition: {exc.from_status}→{exc.to_status}",
            )
            await session.commit()
            raise
        except Exception as exc:
            logger.exception("publish_strategy failed for %s", strategy_id)
            await svc.repo.update_job(
                job,
                status="failed",
                completed_at=datetime.now(UTC),
                error=f"{type(exc).__name__}: {exc}",
            )
            await session.commit()
            raise

        await svc.repo.update_job(
            job,
            status="succeeded",
            completed_at=datetime.now(UTC),
            output_payload=asdict(outcome),
        )
        await session.commit()
        return {
            "status": "succeeded",
            "strategy_id": strategy_id,
            **asdict(outcome),
        }


async def _execute_publish(
    session: AsyncSession,
    svc: TaxStrategyService,
    strategy: TaxStrategy,
) -> _PublishOutcome:
    if strategy.status != "approved":
        raise InvalidStatusTransitionError(
            strategy.strategy_id, strategy.status, "published"
        )
    if not vector_writes_enabled():
        raise VectorWriteDisabledError(strategy.strategy_id)

    # 1. Chunk the parent content.
    primary_category = strategy.categories[0] if strategy.categories else "Uncategorised"
    chunks = StrategyChunker().chunk_strategy(
        StrategyChunkerInput(
            strategy_id=strategy.strategy_id,
            name=strategy.name,
            primary_category=primary_category,
            implementation_text=strategy.implementation_text,
            explanation_text=strategy.explanation_text,
            keywords=list(strategy.keywords),
        )
    )
    if not chunks:
        raise ValueError(
            f"StrategyChunker returned zero chunks for {strategy.strategy_id}; "
            "likely both implementation and explanation are empty."
        )

    # 2. Get-or-create the singleton tax_strategies_internal KnowledgeSource.
    source_id = await _ensure_strategy_source(session)

    # 3. Idempotency check — fetch any existing vectors up front. If every
    # vector id already exists in Pinecone with a matching content_hash
    # (the hash is stored in the vector's metadata), we skip both the
    # Voyage embed call AND the Pinecone upsert. The Postgres rows
    # (ContentChunk + BM25IndexEntry) are still written since they're
    # per-environment state — this is what lets prod "catch up" to local
    # without re-embedding (local already populated Pinecone during the
    # one-off bulk bootstrap).
    target_namespace = get_namespace_with_env(_STRATEGY_COLLECTION)
    pinecone = PineconeService(get_settings())

    # Precompute vector ids + chunk content hashes in one pass so we can
    # interrogate Pinecone before doing any embedding work.
    chunk_records: list[dict[str, Any]] = []
    vector_ids: list[str] = []
    for chunk in chunks:
        section = chunk.metadata["chunk_section"]
        vector_id = (
            f"tax_strategy:{strategy.strategy_id}:{section}:v{strategy.version}"
        )
        chunk_records.append(
            {
                "chunk": chunk,
                "section": section,
                "vector_id": vector_id,
                "content_hash": _content_hash(chunk.text),
            }
        )
        vector_ids.append(vector_id)

    existing_vectors = await pinecone.fetch_vectors(
        index_name=INDEX_NAME, ids=vector_ids, namespace=target_namespace
    )
    all_present_and_matching = True
    for rec in chunk_records:
        fetched = existing_vectors.get(rec["vector_id"])
        if fetched is None:
            all_present_and_matching = False
            break
        # Pinecone Vector objects expose `.metadata` as a dict. Be defensive
        # — some SDK shapes return dicts directly.
        meta = (
            getattr(fetched, "metadata", None)
            if not isinstance(fetched, dict)
            else fetched.get("metadata")
        )
        if not meta or meta.get("content_hash") != rec["content_hash"]:
            all_present_and_matching = False
            break

    # 4. Embed + upsert — but only if the idempotency check failed.
    voyage = VoyageService()
    now = datetime.now(UTC)
    pinecone_payloads: list[dict[str, Any]] = []
    pinecone_vectors: list[list[float]] = []

    for rec in chunk_records:
        chunk = rec["chunk"]
        section = rec["section"]
        vector_id = rec["vector_id"]
        content_hash_val = rec["content_hash"]

        payload: dict[str, Any] = {
            "chunk_id": str(uuid4()),
            "tax_strategy_id": str(strategy.id),
            "strategy_id": strategy.strategy_id,
            "name": strategy.name,
            "categories": list(strategy.categories),
            "chunk_section": section,
            "tenant_id": strategy.tenant_id,
            "_collection": _STRATEGY_COLLECTION,
            "version": strategy.version,
            "is_superseded": False,
            "entity_types": list(strategy.entity_types),
            "industry_triggers": list(strategy.industry_triggers),
            "financial_impact_type": list(strategy.financial_impact_type),
            "ato_sources": list(strategy.ato_sources),
            "case_refs": list(strategy.case_refs),
            "keywords": list(strategy.keywords),
            "content_type": "tax_strategy",
            "source_type": "tax_strategy",
            "text": chunk.text,
            "content_hash": content_hash_val,
        }
        # Optional numeric bands — Pinecone rejects None, so include only
        # when set.
        for col, value in (
            ("income_band_min", strategy.income_band_min),
            ("income_band_max", strategy.income_band_max),
            ("turnover_band_min", strategy.turnover_band_min),
            ("turnover_band_max", strategy.turnover_band_max),
            ("age_min", strategy.age_min),
            ("age_max", strategy.age_max),
        ):
            if value is not None:
                payload[col] = value
        if strategy.fy_applicable_from is not None:
            payload["fy_applicable_from"] = strategy.fy_applicable_from.isoformat()
        if strategy.fy_applicable_to is not None:
            payload["fy_applicable_to"] = strategy.fy_applicable_to.isoformat()

        # Always write ContentChunk + BM25IndexEntry — these are Postgres
        # state per environment. The chunk_id is a fresh UUID on every
        # run; Pinecone metadata's chunk_id is authoritative for vector
        # lookups either way.
        content_chunk_id = UUID(payload["chunk_id"])
        content_chunk = ContentChunk(
            id=content_chunk_id,
            source_id=source_id,
            qdrant_point_id=vector_id,
            collection_name=_STRATEGY_COLLECTION,
            content_hash=content_hash_val,
            source_url=f"clairo://tax_strategies/{strategy.strategy_id}",
            title=strategy.name,
            source_type="tax_strategy",
            entity_types=list(strategy.entity_types),
            industries=list(strategy.industry_triggers),
            content_type="tax_strategy",
            section_ref=strategy.strategy_id,
            topic_tags=list(strategy.categories),
            natural_key=strategy.strategy_id,
            tax_strategy_id=strategy.id,
            chunk_section=section,
            context_header=chunk.metadata["context_header"],
            created_at=now,
            updated_at=now,
        )
        session.add(content_chunk)
        await session.flush()

        tokens = _tokenise_for_bm25(chunk.text)
        bm25 = BM25IndexEntry(
            chunk_id=content_chunk.id,
            collection_name=_STRATEGY_COLLECTION,
            tokens=tokens,
            section_refs=[strategy.strategy_id],
        )
        session.add(bm25)

        if not all_present_and_matching:
            # Only do the expensive embed call when we're actually going to
            # upsert. Preserves the per-chunk order of vector_ids.
            embedding = await voyage.embed_document(chunk.text)
            pinecone_vectors.append(embedding)
            pinecone_payloads.append(payload)

    await session.flush()

    # 5. Upsert into Pinecone — only when we needed to embed.
    if all_present_and_matching:
        logger.info(
            "publish_strategy.idempotent_skip vectors=%d strategy=%s "
            "(all vectors present with matching content_hash; skipping embed+upsert)",
            len(vector_ids),
            strategy.strategy_id,
        )
    else:
        await pinecone.upsert_vectors(
            index_name=INDEX_NAME,
            ids=vector_ids,
            vectors=pinecone_vectors,
            payloads=pinecone_payloads,
            namespace=target_namespace,
        )

    # 6. Transition the parent to published; emits .published audit event.
    await svc._transition_status(
        strategy,
        new_status="published",
        actor_clerk_user_id="system:publish_task",
        extra_metadata={
            "chunk_count": len(chunks),
            "vector_store_namespace": target_namespace,
            "vectors_reused": all_present_and_matching,
        },
    )

    return _PublishOutcome(
        chunk_count=len(chunks),
        vector_ids=vector_ids,
        vector_store_namespace=target_namespace,
    )


async def _ensure_strategy_source(session: AsyncSession) -> UUID:
    """Get-or-create the singleton KnowledgeSource used as FK target for
    all strategy ContentChunk rows.
    """
    result = await session.execute(
        select(KnowledgeSource).where(KnowledgeSource.name == _STRATEGY_SOURCE_NAME)
    )
    source = result.scalar_one_or_none()
    if source is not None:
        return source.id

    source = KnowledgeSource(
        name=_STRATEGY_SOURCE_NAME,
        source_type="tax_strategy",
        base_url="clairo://tax_strategies",
        collection_name=_STRATEGY_COLLECTION,
        scrape_config={},
        is_active=True,
    )
    session.add(source)
    await session.flush()
    return source.id


def _content_hash(text: str) -> str:
    normalised = " ".join(text.split())
    return hashlib.sha256(normalised.encode()).hexdigest()


def _tokenise_for_bm25(text: str) -> list[str]:
    """Minimal tokeniser used for strategy chunks' BM25 index entries.

    Splits on whitespace, lowercases, strips punctuation. The hybrid search
    engine builds BM25Okapi from these tokens at query time.
    """
    import re

    clean = re.sub(r"[^\w\s-]", " ", text.lower())
    return [t for t in clean.split() if t]


# ---------------------------------------------------------------------------
# Research / draft / enrich — implementations land in T028 follow-up.
# Left as NotImplementedError so accidental invocation is loud rather than
# silently wrong.
# ---------------------------------------------------------------------------


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="tax_strategies.research",
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def research_strategy(self: Task, strategy_id: str, triggered_by: str) -> dict[str, Any]:
    """Fixture-driven research for Phase 1 (T028).

    Loads pre-populated ATO primary-source references from
    tax_strategies/data/ato_source_fixtures.py, writes them to
    TaxStrategy.ato_sources, transitions stub → researching. Phase 2
    replaces the fixture lookup with live ATO scraping per architecture
    §10.2.
    """
    return asyncio.run(_run_research(strategy_id, triggered_by))


async def _run_research(strategy_id: str, triggered_by: str) -> dict[str, Any]:
    factory = _make_session_factory()
    async with factory() as session:
        svc = TaxStrategyService(session)
        strategy = await svc.repo.get_live_version(strategy_id)
        if strategy is None:
            raise StrategyNotFoundError(strategy_id)

        job = await svc.repo.create_job(
            strategy_id=strategy_id,
            stage="research",
            triggered_by=triggered_by,
            input_payload={"version": strategy.version},
        )
        await svc.repo.update_job(
            job, status="running", started_at=datetime.now(UTC)
        )
        await session.commit()

        try:
            from app.modules.tax_strategies.data.ato_source_fixtures import (
                get_fixture_sources,
            )

            sources = get_fixture_sources(strategy_id)
            strategy.ato_sources = sources
            await session.flush()

            await svc._transition_status(
                strategy,
                new_status="researching",
                actor_clerk_user_id=triggered_by,
                extra_metadata={"source_count": len(sources)},
            )
        except Exception as exc:
            logger.exception("research_strategy failed for %s", strategy_id)
            await svc.repo.update_job(
                job,
                status="failed",
                completed_at=datetime.now(UTC),
                error=f"{type(exc).__name__}: {exc}",
            )
            await session.commit()
            raise

        output = {"ato_sources": sources, "source_count": len(sources)}
        await svc.repo.update_job(
            job,
            status="succeeded",
            completed_at=datetime.now(UTC),
            output_payload=output,
        )
        await session.commit()
        return {
            "status": "succeeded",
            "strategy_id": strategy_id,
            **output,
        }


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="tax_strategies.draft",
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def draft_strategy(self: Task, strategy_id: str, triggered_by: str) -> dict[str, Any]:
    """Anthropic draft per architecture §10.3.

    Reads the fixture-loaded ato_sources, calls Claude Sonnet, parses the
    response into implementation_text + explanation_text, and transitions
    researching → drafted. Re-drafts from `enriched` (reject path) are
    allowed; the state machine handles both edges.
    """
    return asyncio.run(_run_draft(strategy_id, triggered_by))


async def _run_draft(strategy_id: str, triggered_by: str) -> dict[str, Any]:
    from app.modules.tax_strategies.llm import run_draft_llm

    factory = _make_session_factory()
    async with factory() as session:
        svc = TaxStrategyService(session)
        strategy = await svc.repo.get_live_version(strategy_id)
        if strategy is None:
            raise StrategyNotFoundError(strategy_id)

        if strategy.status not in {"researching", "enriched"}:
            raise InvalidStatusTransitionError(
                strategy.strategy_id, strategy.status, "drafted"
            )

        job = await svc.repo.create_job(
            strategy_id=strategy_id,
            stage="draft",
            triggered_by=triggered_by,
            input_payload={
                "version": strategy.version,
                "ato_source_count": len(strategy.ato_sources or []),
            },
        )
        await svc.repo.update_job(
            job, status="running", started_at=datetime.now(UTC)
        )
        await session.commit()

        try:
            draft = await run_draft_llm(
                name=strategy.name,
                categories=list(strategy.categories),
                ato_sources=list(strategy.ato_sources or []),
            )
            strategy.implementation_text = draft.implementation_text
            strategy.explanation_text = draft.explanation_text
            await session.flush()

            await svc._transition_status(
                strategy,
                new_status="drafted",
                actor_clerk_user_id=triggered_by,
                extra_metadata={
                    "implementation_chars": len(draft.implementation_text),
                    "explanation_chars": len(draft.explanation_text),
                },
            )
        except Exception as exc:
            logger.exception("draft_strategy failed for %s", strategy_id)
            await svc.repo.update_job(
                job,
                status="failed",
                completed_at=datetime.now(UTC),
                error=f"{type(exc).__name__}: {exc}",
            )
            await session.commit()
            raise

        output = {
            "implementation_chars": len(draft.implementation_text),
            "explanation_chars": len(draft.explanation_text),
        }
        await svc.repo.update_job(
            job,
            status="succeeded",
            completed_at=datetime.now(UTC),
            output_payload=output,
        )
        await session.commit()
        return {
            "status": "succeeded",
            "strategy_id": strategy_id,
            **output,
        }


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="tax_strategies.enrich",
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def enrich_strategy(self: Task, strategy_id: str, triggered_by: str) -> dict[str, Any]:
    """Structured eligibility extraction (architecture §16 mitigations).

    Second LLM pass reads the drafted implementation + explanation and
    extracts eligibility metadata (entity types, income bands, keywords,
    etc.). Defaults to null/empty on any ambiguous field. Transitions
    drafted → enriched.
    """
    return asyncio.run(_run_enrich(strategy_id, triggered_by))


async def _run_enrich(strategy_id: str, triggered_by: str) -> dict[str, Any]:
    from app.modules.tax_strategies.llm import run_enrich_llm

    factory = _make_session_factory()
    async with factory() as session:
        svc = TaxStrategyService(session)
        strategy = await svc.repo.get_live_version(strategy_id)
        if strategy is None:
            raise StrategyNotFoundError(strategy_id)

        if strategy.status != "drafted":
            raise InvalidStatusTransitionError(
                strategy.strategy_id, strategy.status, "enriched"
            )

        job = await svc.repo.create_job(
            strategy_id=strategy_id,
            stage="enrich",
            triggered_by=triggered_by,
            input_payload={"version": strategy.version},
        )
        await svc.repo.update_job(
            job, status="running", started_at=datetime.now(UTC)
        )
        await session.commit()

        try:
            eligibility = await run_enrich_llm(
                name=strategy.name,
                categories=list(strategy.categories),
                implementation_text=strategy.implementation_text,
                explanation_text=strategy.explanation_text,
            )
            _apply_eligibility(strategy, eligibility)
            await session.flush()

            await svc._transition_status(
                strategy,
                new_status="enriched",
                actor_clerk_user_id=triggered_by,
                extra_metadata={
                    "entity_types_count": len(eligibility["entity_types"]),
                    "keywords_count": len(eligibility["keywords"]),
                },
            )
        except Exception as exc:
            logger.exception("enrich_strategy failed for %s", strategy_id)
            await svc.repo.update_job(
                job,
                status="failed",
                completed_at=datetime.now(UTC),
                error=f"{type(exc).__name__}: {exc}",
            )
            await session.commit()
            raise

        output = {"eligibility": eligibility}
        await svc.repo.update_job(
            job,
            status="succeeded",
            completed_at=datetime.now(UTC),
            output_payload=output,
        )
        await session.commit()
        return {
            "status": "succeeded",
            "strategy_id": strategy_id,
            **output,
        }


def _apply_eligibility(strategy: TaxStrategy, eligibility: dict[str, Any]) -> None:
    """Write eligibility dict fields onto the TaxStrategy row in place.

    Source of truth for which keys map to which columns. Kept as a small
    dedicated helper so that adding a field later touches exactly one
    place.
    """
    strategy.entity_types = list(eligibility["entity_types"])
    strategy.industry_triggers = list(eligibility["industry_triggers"])
    strategy.financial_impact_type = list(eligibility["financial_impact_type"])
    strategy.keywords = list(eligibility["keywords"])
    strategy.income_band_min = eligibility["income_band_min"]
    strategy.income_band_max = eligibility["income_band_max"]
    strategy.turnover_band_min = eligibility["turnover_band_min"]
    strategy.turnover_band_max = eligibility["turnover_band_max"]
    strategy.age_min = eligibility["age_min"]
    strategy.age_max = eligibility["age_max"]
