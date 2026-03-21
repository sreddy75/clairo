"""Knowledge service orchestrating the tax knowledge search pipeline.

Wires up the full retrieval chain:
    query_router -> query_expander -> hybrid_search -> reranker -> format results

This is the main entry point for knowledge base search, domain browsing,
and legislation section lookup. The service delegates to specialised
components and keeps its own logic thin.

Usage::

    service = KnowledgeService(session, pinecone, voyage)
    results = await service.search_knowledge(request)
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pinecone_service import PineconeService
from app.core.voyage import VoyageService
from app.modules.knowledge.domains import DomainManager
from app.modules.knowledge.repository import (
    ContentChunkRepository,
    ContentCrossReferenceRepository,
    LegislationSectionRepository,
    TaxDomainRepository,
)
from app.modules.knowledge.retrieval.hybrid_search import HybridSearchEngine, ScoredChunk
from app.modules.knowledge.retrieval.query_expander import QueryExpander
from app.modules.knowledge.retrieval.query_router import QueryClassification, QueryRouter, QueryType
from app.modules.knowledge.retrieval.reranker import CrossEncoderReranker
from app.modules.knowledge.schemas import (
    KnowledgeSearchFilters,
    KnowledgeSearchRequest,
    KnowledgeSearchResultSchema,
    LegislationSectionDetail,
)

logger = logging.getLogger(__name__)

# Default Pinecone collection for tax knowledge content.
_DEFAULT_COLLECTION = "compliance_knowledge"


class KnowledgeService:
    """Orchestrates the tax knowledge search pipeline.

    Combines query routing, query expansion, hybrid search (BM25 + semantic),
    cross-encoder re-ranking, and result formatting into a single coherent
    pipeline.  Also provides domain browsing and legislation section lookup.

    Args:
        session: Async SQLAlchemy database session.
        pinecone: Pinecone vector search service.
        voyage: Voyage AI embedding service.
    """

    def __init__(
        self,
        session: AsyncSession,
        pinecone: PineconeService,
        voyage: VoyageService,
    ) -> None:
        self._session = session

        # Retrieval pipeline components
        self._hybrid_search = HybridSearchEngine(session, pinecone, voyage)
        self._reranker = CrossEncoderReranker()
        self._query_router = QueryRouter()
        self._query_expander = QueryExpander()

        # Domain manager for DB-backed domain configuration and scoping
        self._domain_manager = DomainManager(session)

        # Repositories
        self._domain_repo = TaxDomainRepository(session)
        self._legislation_repo = LegislationSectionRepository(session)
        self._chunk_repo = ContentChunkRepository(session)
        self._cross_ref_repo = ContentCrossReferenceRepository(session)

    # =========================================================================
    # Search Pipeline
    # =========================================================================

    async def search_knowledge(self, request: KnowledgeSearchRequest) -> dict:
        """Execute the full knowledge search pipeline.

        Pipeline stages:
            1. Classify query via QueryRouter.
            1a. For SECTION_LOOKUP with extracted refs, attempt direct DB
                lookup and insert as top result (relevance_score=1.0).
            2. Expand query via QueryExpander (for CONCEPTUAL/SCENARIO types).
            3. Merge any additional filters from the request into the
               Pinecone metadata filter produced by the router.
            4. Run hybrid search for each expanded query variant.
            5. If multiple variants produced results, merge via RRF.
            6. Re-rank top candidates via CrossEncoderReranker.
            7. Format results as serialised KnowledgeSearchResultSchema dicts.
            8. Prepend direct section lookup result (if found) to final list.

        Args:
            request: Search request containing query, optional domain,
                optional filters, and a result limit.

        Returns:
            Dict with keys ``results``, ``query_type``, ``domain_detected``,
            and ``total_results``.
        """
        query = request.query

        # Step 1: Classify the query.
        # Domain is NOT passed to the router.  The router's hardcoded
        # DOMAIN_TOPIC_TAGS mapping uses a smaller, differently-cased tag
        # set that would conflict with the DB-backed domain filter applied
        # in Step 1b.  Auto-detection still runs inside the router (setting
        # classification.domain_detected), but the hardcoded topic_tags
        # filter is not applied.  Step 1b handles all domain scoping.
        try:
            classification = self._query_router.classify(query)
        except Exception:
            logger.exception("Query classification failed; using CONCEPTUAL default")
            classification = QueryClassification(
                query_type=QueryType.CONCEPTUAL,
                confidence=0.3,
                pinecone_filter={"is_superseded": {"$ne": True}},
                fusion_weights=(0.7, 0.3),
            )

        logger.info(
            "Query classified: type=%s confidence=%.2f domain=%s refs=%s",
            classification.query_type.value,
            classification.confidence,
            classification.domain_detected,
            classification.extracted_refs,
        )

        # Step 1a: For SECTION_LOOKUP queries with extracted references,
        # attempt a direct legislation section lookup from the database.
        # If found, the direct match is inserted as the top result with
        # relevance_score=1.0, ahead of any hybrid search results.
        direct_section_result: dict | None = None
        if classification.query_type == QueryType.SECTION_LOOKUP and classification.extracted_refs:
            direct_section_result = await self._try_direct_section_lookup(
                classification.extracted_refs
            )

        # Step 1b: Apply domain scoping from DB-backed domain configuration.
        # When request.domain is specified or the query router auto-detected
        # a domain, load the full domain config from the tax_domains table
        # and replace/add topic_tags as a Pinecone metadata filter.  The DB
        # domain config has richer topic_tags than the hardcoded mapping in
        # the query router, providing more comprehensive scoping.
        #
        # When the router already applied a hardcoded domain filter (via
        # auto-detection), we replace its topic_tags filter with the DB
        # version to avoid conflicting tag sets.
        domain_slug = request.domain or classification.domain_detected
        if domain_slug:
            try:
                domain_filters = await self._domain_manager.get_domain_filters(domain_slug)
                if domain_filters and domain_filters.topic_tags:
                    domain_tag_filter: dict = {"topic_tags": {"$in": domain_filters.topic_tags}}
                    # Replace any existing topic_tags filter from the router
                    # with the DB-backed version, then merge back in.
                    stripped_filter = _strip_topic_tags_filter(classification.pinecone_filter)
                    classification.pinecone_filter = _merge_pinecone_filters(
                        stripped_filter, [domain_tag_filter]
                    )
                    # Ensure classification reflects the domain
                    if classification.domain_detected is None:
                        classification.domain_detected = domain_slug
                    logger.info(
                        "Applied DB domain scoping: slug=%s tags=%s",
                        domain_slug,
                        domain_filters.topic_tags,
                    )
            except Exception:
                logger.exception(
                    "Failed to load domain filters for slug=%s; "
                    "continuing without DB domain scoping",
                    domain_slug,
                )

        # Step 2: Expand query (skipped for precise lookups)
        try:
            query_variants = await self._query_expander.expand_query(
                query, classification.query_type
            )
        except Exception:
            logger.exception("Query expansion failed; using original query only")
            query_variants = [query]

        # Step 3: Merge request-level filters into the router's Pinecone filter
        pinecone_filter = self._merge_request_filters(
            classification.pinecone_filter, request.filters
        )

        # Determine fusion weights from classification
        semantic_weight, _keyword_weight = classification.fusion_weights

        # Step 4: Run hybrid search for each query variant
        all_results: list[ScoredChunk] = []
        for variant in query_variants:
            try:
                variant_results = await self._hybrid_search.hybrid_search(
                    query=variant,
                    collection=_DEFAULT_COLLECTION,
                    limit=30,
                    semantic_weight=semantic_weight,
                    pinecone_filter=pinecone_filter,
                )
                all_results.extend(variant_results)
            except Exception:
                logger.exception("Hybrid search failed for variant: %s", variant[:80])

        # Step 5: Merge results from multiple variants using RRF-style dedup
        if len(query_variants) > 1 and all_results:
            all_results = self._deduplicate_by_rrf(all_results)

        # If no hybrid search results and no direct match, return empty
        if not all_results and direct_section_result is None:
            return {
                "results": [],
                "query_type": classification.query_type.value,
                "domain_detected": classification.domain_detected,
                "total_results": 0,
            }

        # Step 6: Re-rank top candidates (optional, degrades gracefully)
        if all_results:
            try:
                reranked = self._reranker.rerank(
                    query=query,
                    candidates=all_results,
                    top_k=request.limit,
                )
            except Exception:
                logger.exception("Re-ranking failed; using hybrid search scores")
                reranked = all_results[: request.limit]
        else:
            reranked = []

        # Step 7: Format results
        formatted = self._format_results(reranked)

        # Step 8: If a direct section lookup matched, prepend it as the
        # top result with relevance_score=1.0.  Duplicate hybrid search
        # results for the same section_ref are removed to avoid redundancy.
        if direct_section_result is not None:
            direct_ref = direct_section_result.get("section_ref")
            formatted = [r for r in formatted if r.get("section_ref") != direct_ref]
            formatted.insert(0, direct_section_result)

        # Respect the requested limit
        formatted = formatted[: request.limit]

        return {
            "results": formatted,
            "query_type": classification.query_type.value,
            "domain_detected": classification.domain_detected,
            "total_results": len(formatted),
        }

    # =========================================================================
    # Domain Browsing
    # =========================================================================

    async def list_domains(self, active_only: bool = True) -> list[dict]:
        """List available specialist tax domains.

        Args:
            active_only: If True, only return active domains.

        Returns:
            List of serialised TaxDomain dicts.
        """
        if active_only:
            domains = await self._domain_repo.list_active()
        else:
            # list_active already filters; for all domains we'd need
            # a separate repo method.  For now just use list_active.
            domains = await self._domain_repo.list_active()

        return [
            {
                "slug": d.slug,
                "name": d.name,
                "description": d.description,
                "topic_tags": d.topic_tags or [],
                "legislation_refs": d.legislation_refs or [],
                "ruling_types": d.ruling_types or [],
                "icon": d.icon,
                "display_order": d.display_order,
                "is_active": d.is_active,
            }
            for d in domains
        ]

    async def get_domain(self, slug: str) -> dict | None:
        """Get a single specialist tax domain by slug.

        Args:
            slug: The domain slug (e.g. ``"gst"``, ``"division_7a"``).

        Returns:
            Serialised domain dict, or ``None`` if not found.
        """
        domain = await self._domain_repo.get_by_slug(slug)
        if domain is None:
            return None

        return {
            "slug": domain.slug,
            "name": domain.name,
            "description": domain.description,
            "topic_tags": domain.topic_tags or [],
            "legislation_refs": domain.legislation_refs or [],
            "ruling_types": domain.ruling_types or [],
            "icon": domain.icon,
            "display_order": domain.display_order,
            "is_active": domain.is_active,
        }

    # =========================================================================
    # Legislation Section Lookup
    # =========================================================================

    async def get_legislation_section(self, section_ref: str) -> dict | None:
        """Look up a specific legislation section by reference.

        Parses flexible reference formats (e.g. ``"s109D"``,
        ``"s109D ITAA 1936"``, ``"s109D-ITAA1936"``, ``"section 109D"``),
        resolves to a ``LegislationSection`` record, and enriches the
        response with associated content chunks, cross-references, and
        related rulings.

        Args:
            section_ref: The section reference string in any supported format.

        Returns:
            A dict matching the ``LegislationSectionDetail`` schema, or
            ``None`` if the section is not found.
        """
        # Parse the flexible section reference
        normalised_ref, act_id = self._parse_section_ref(section_ref)

        # Query the legislation section table
        section = await self._legislation_repo.get_by_section_ref(normalised_ref, act_id)
        if section is None:
            return None

        # Get associated content chunks for the section text
        chunks = await self._chunk_repo.get_by_section_ref(normalised_ref)
        section_text = (
            "\n\n".join(
                chunk.title + "\n" + (chunk.source_url or "")
                if not hasattr(chunk, "qdrant_point_id")
                else self._extract_chunk_text(chunk)
                for chunk in chunks
            )
            if chunks
            else ""
        )

        # If no text from chunks, use heading as fallback
        if not section_text and section.heading:
            section_text = section.heading

        # Get cross-references
        cross_refs: list[str] = list(section.cross_references or [])

        # Get related rulings by querying cross-references pointing to this section
        related_rulings: list[dict] = []
        try:
            incoming_refs = await self._cross_ref_repo.get_by_target_ref(normalised_ref)
            for ref in incoming_refs:
                if ref.source_chunk:
                    ruling_number = ref.source_chunk.ruling_number
                    if ruling_number:
                        related_rulings.append(
                            {
                                "ruling_number": ruling_number,
                                "title": ref.source_chunk.title,
                                "source_type": ref.source_chunk.source_type,
                                "reference_type": ref.reference_type,
                            }
                        )
        except Exception:
            logger.exception("Failed to load related rulings for section %s", normalised_ref)

        # Deduplicate related rulings by ruling number
        seen_rulings: set[str] = set()
        unique_rulings: list[dict] = []
        for ruling in related_rulings:
            rn = ruling.get("ruling_number", "")
            if rn and rn not in seen_rulings:
                seen_rulings.add(rn)
                unique_rulings.append(ruling)

        # Build the response matching LegislationSectionDetail
        detail = LegislationSectionDetail(
            section_ref=section.section_ref,
            act_name=section.act_name,
            act_short_name=section.act_short_name,
            heading=section.heading,
            text=section_text,
            part=section.part,
            division=section.division,
            subdivision=section.subdivision,
            compilation_date=section.compilation_date.isoformat(),
            cross_references=cross_refs,
            defined_terms=list(section.defined_terms or []),
            related_rulings=unique_rulings,
        )

        return detail.model_dump()

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    async def _try_direct_section_lookup(self, extracted_refs: list[str]) -> dict | None:
        """Attempt a direct legislation section lookup from extracted refs.

        Iterates over the extracted section references and tries to resolve
        each one via ``get_legislation_section()``.  Returns the first
        successful match formatted as a ``KnowledgeSearchResultSchema``
        dict with ``relevance_score=1.0``, or ``None`` if no match is
        found.

        Args:
            extracted_refs: List of section references extracted from the
                query by the query router (e.g. ``["s109D"]``).

        Returns:
            Formatted search result dict for the matched section, or
            ``None`` if no direct match exists in the database.
        """
        for ref in extracted_refs:
            try:
                section_detail = await self.get_legislation_section(ref)
                if section_detail is not None:
                    # Build a search result dict with perfect relevance
                    result = KnowledgeSearchResultSchema(
                        chunk_id=f"legislation:{section_detail['section_ref']}",
                        title=self._build_section_title(section_detail),
                        text=section_detail.get("text", ""),
                        source_url=None,
                        source_type="legislation",
                        section_ref=section_detail.get("section_ref"),
                        ruling_number=None,
                        effective_date=section_detail.get("compilation_date"),
                        is_superseded=False,
                        relevance_score=1.0,
                        content_type="operative_provision",
                    )
                    logger.info(
                        "Direct section lookup hit for ref=%s -> %s",
                        ref,
                        section_detail.get("section_ref"),
                    )
                    return result.model_dump()
            except Exception:
                logger.exception("Direct section lookup failed for ref: %s", ref)
        return None

    @staticmethod
    def _build_section_title(section_detail: dict) -> str:
        """Build a descriptive title for a legislation section result.

        Combines the section reference, act short name, and heading
        into a single human-readable title string.

        Args:
            section_detail: Dict from ``get_legislation_section()``.

        Returns:
            Formatted title string, e.g.
            ``"s109D - ITAA 1936 - Loans to shareholders"``.
        """
        parts = [section_detail.get("section_ref", "")]
        act_short = section_detail.get("act_short_name")
        if act_short:
            parts.append(act_short)
        heading = section_detail.get("heading")
        if heading:
            parts.append(heading)
        return " - ".join(parts)

    @staticmethod
    def _parse_section_ref(section_ref: str) -> tuple[str, str | None]:
        """Parse a flexible section reference into (normalised_ref, act_id).

        Supported formats:
            - ``"s109D"``          -> ``("s109D", None)``
            - ``"s109D-ITAA1936"`` -> ``("s109D", "ITAA1936")``
            - ``"s109D ITAA 1936"``-> ``("s109D", "ITAA1936")``
            - ``"s104-10-ITAA1997"`` -> ``("s104-10", "ITAA1997")``
            - ``"section 109D"``   -> ``("s109D", None)``
            - ``"section 109D of the ITAA 1936"`` -> ``("s109D", "ITAA1936")``

        Args:
            section_ref: Raw section reference string.

        Returns:
            Tuple of ``(normalised_section_ref, act_identifier_or_none)``.
            The act identifier has spaces removed (e.g. ``"ITAA1936"``).
        """
        cleaned = section_ref.strip()

        # Known act abbreviation patterns for splitting
        act_pattern = re.compile(
            r"[-\s]+(?:of\s+(?:the\s+)?)?"
            r"(ITAA?\s*\d{4}|GST\s*Act\s*\d{4}|FBTAA?\s*\d{4}"
            r"|TAA?\s*\d{4}|SIS\s*Act\s*\d{4}|SGAA?\s*\d{4})",
            re.IGNORECASE,
        )

        act_id: str | None = None
        section_part = cleaned

        # Try to extract act identifier from the reference
        act_match = act_pattern.search(cleaned)
        if act_match:
            act_id = re.sub(r"\s+", "", act_match.group(1)).upper()
            section_part = cleaned[: act_match.start()].strip()

        # Normalise the section part: "section 109D" -> "s109D"
        section_part = re.sub(r"^section\s+", "s", section_part, flags=re.IGNORECASE)

        # Remove trailing hyphens/spaces from section part
        section_part = section_part.rstrip("- ")

        # If the section part doesn't start with 's', 'Div', or 'Part', add 's'
        # when it looks like a bare number (e.g. "109D")
        if (
            section_part
            and not re.match(r"^(s\d|Div|Part)", section_part, re.IGNORECASE)
            and re.match(r"^\d+[A-Za-z]*(?:-\d+[A-Za-z]*)*$", section_part)
        ):
            section_part = f"s{section_part}"

        return section_part, act_id

    @staticmethod
    def _merge_request_filters(
        base_filter: dict[str, Any] | None,
        request_filters: KnowledgeSearchFilters | None,
    ) -> dict[str, Any] | None:
        """Merge router-produced Pinecone filter with request-level filters.

        Combines the base filter (from the query router) with any additional
        constraints specified in the search request, using ``$and`` when
        both sources contribute conditions.

        Args:
            base_filter: Pinecone metadata filter from the query router,
                or ``None``.
            request_filters: User-specified search filters, or ``None``.

        Returns:
            Merged Pinecone metadata filter dict, or ``None`` if no
            filters apply.
        """
        if request_filters is None:
            return base_filter

        additional_conditions: list[dict[str, Any]] = []

        # Source type filtering
        if request_filters.source_types:
            additional_conditions.append({"source_type": {"$in": request_filters.source_types}})

        # Exclude superseded content (default True)
        if request_filters.exclude_superseded:
            additional_conditions.append({"is_superseded": {"$ne": True}})

        # Financial year filter
        if request_filters.fy_applicable:
            additional_conditions.append(
                {"fy_applicable": {"$in": [request_filters.fy_applicable]}}
            )

        # Entity type filter
        if request_filters.entity_types:
            additional_conditions.append({"entity_types": {"$in": request_filters.entity_types}})

        if not additional_conditions:
            return base_filter

        # Merge with base filter using $and
        return _merge_pinecone_filters(base_filter, additional_conditions)

    @staticmethod
    def _deduplicate_by_rrf(results: list[ScoredChunk]) -> list[ScoredChunk]:
        """Deduplicate and merge scores when results come from multiple variants.

        When multiple query variants return results, the same chunk may
        appear multiple times.  This method keeps the highest score for
        each unique chunk_id and preserves the best payload/text.

        Args:
            results: Combined results from all query variants.

        Returns:
            Deduplicated list sorted by descending score.
        """
        best: dict[str, ScoredChunk] = {}
        for chunk in results:
            existing = best.get(chunk.chunk_id)
            if existing is None or chunk.score > existing.score:
                best[chunk.chunk_id] = chunk

        deduped = list(best.values())
        deduped.sort(key=lambda c: c.score, reverse=True)
        return deduped

    @staticmethod
    def _format_results(chunks: list[ScoredChunk]) -> list[dict]:
        """Format scored chunks into serialisable result dicts.

        Maps each ``ScoredChunk`` to a ``KnowledgeSearchResultSchema``-
        compatible dict by extracting metadata from the Pinecone payload.

        Args:
            chunks: Ranked and re-ranked scored chunks.

        Returns:
            List of dicts matching the ``KnowledgeSearchResultSchema`` shape.
        """
        results: list[dict] = []
        for chunk in chunks:
            payload = chunk.payload or {}

            result = KnowledgeSearchResultSchema(
                chunk_id=chunk.chunk_id,
                title=payload.get("title"),
                text=chunk.text or payload.get("text", ""),
                source_url=payload.get("source_url"),
                source_type=payload.get("source_type", "unknown"),
                section_ref=payload.get("section_ref"),
                ruling_number=payload.get("ruling_number"),
                effective_date=payload.get("effective_date"),
                is_superseded=payload.get("is_superseded", False),
                relevance_score=round(chunk.score, 4),
                content_type=payload.get("content_type"),
            )
            results.append(result.model_dump())

        return results

    @staticmethod
    def _extract_chunk_text(chunk: Any) -> str:
        """Extract display text from a ContentChunk DB model.

        Prefers a combination of title and source_url as a fallback
        since the actual text content is stored in Pinecone, not in
        the database.

        Args:
            chunk: A ``ContentChunk`` ORM instance.

        Returns:
            Best available text representation of the chunk.
        """
        parts: list[str] = []
        if chunk.title:
            parts.append(chunk.title)
        if chunk.section_ref:
            parts.append(f"[{chunk.section_ref}]")
        return " ".join(parts) if parts else "(section text)"


# =============================================================================
# Module-level filter merge utility
# =============================================================================


def _merge_pinecone_filters(
    base_filter: dict[str, Any] | None,
    additional_conditions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Merge a base Pinecone filter dict with a list of additional conditions.

    If both the base filter and additional conditions exist, they are
    combined using a ``$and`` operator.  Existing ``$and`` arrays in the
    base filter are flattened to avoid unnecessary nesting.

    Args:
        base_filter: Existing Pinecone metadata filter, or ``None``.
        additional_conditions: List of additional filter dicts to apply.

    Returns:
        Merged Pinecone metadata filter dict.
    """
    if not additional_conditions:
        return base_filter or {}

    if base_filter is None:
        if len(additional_conditions) == 1:
            return additional_conditions[0]
        return {"$and": additional_conditions}

    # Flatten any existing $and in the base filter
    existing_conditions: list[dict[str, Any]] = []
    if "$and" in base_filter:
        existing_conditions.extend(base_filter["$and"])
    else:
        existing_conditions.append(base_filter)

    existing_conditions.extend(additional_conditions)
    return {"$and": existing_conditions}


def _strip_topic_tags_filter(
    pinecone_filter: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Remove any ``topic_tags`` conditions from a Pinecone filter dict.

    When replacing the query router's hardcoded domain filter with the
    richer DB-backed version, we first strip existing ``topic_tags``
    conditions to avoid conflicting or duplicate tag sets in the final
    ``$and`` filter.

    Handles three filter shapes:
        1. Top-level ``{"topic_tags": ...}`` -- returns ``None``.
        2. ``{"$and": [...]}`` with a ``topic_tags`` element -- removes
           that element from the list.
        3. No ``topic_tags`` present -- returns filter unchanged.

    Args:
        pinecone_filter: Existing Pinecone metadata filter, or ``None``.

    Returns:
        Filter dict with ``topic_tags`` conditions removed, or ``None``
        if the filter was solely a ``topic_tags`` condition.
    """
    if pinecone_filter is None:
        return None

    # Case 1: top-level topic_tags filter (e.g. {"topic_tags": {"$in": [...]}})
    if "topic_tags" in pinecone_filter and "$and" not in pinecone_filter:
        # Remove topic_tags; if nothing else remains, return None
        remaining = {k: v for k, v in pinecone_filter.items() if k != "topic_tags"}
        return remaining if remaining else None

    # Case 2: $and array containing a topic_tags condition
    if "$and" in pinecone_filter:
        filtered_conditions = [
            cond
            for cond in pinecone_filter["$and"]
            if not (isinstance(cond, dict) and "topic_tags" in cond)
        ]
        if not filtered_conditions:
            return None
        if len(filtered_conditions) == 1:
            return filtered_conditions[0]
        return {"$and": filtered_conditions}

    # Case 3: no topic_tags present
    return pinecone_filter
