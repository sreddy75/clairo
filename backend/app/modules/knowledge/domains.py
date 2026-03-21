"""Specialist tax domain configuration for scoped retrieval.

Provides domain-aware filtering for the knowledge search pipeline.
Domains are loaded from the ``tax_domains`` database table, cached
in-memory with a 5-minute TTL, and used to construct Pinecone metadata
filters that restrict retrieval to domain-relevant content.

The :class:`DomainManager` is the primary interface.  It supports three
operations:

    1. **get_domain_filters** -- Load a domain's topic_tags, legislation_refs,
       and ruling_types for constructing scoped retrieval filters.
    2. **detect_domain** -- Synchronously auto-detect a domain from query text
       using keyword matching (mirrors ``query_router._detect_domain``).
    3. **get_all_domains** -- List all domains from the database.

Caching
-------
Domain configuration changes infrequently (admin-only), so results are
cached in a module-level dict with a simple timestamp-based TTL.  The
cache is shared across all ``DomainManager`` instances within a process.

Usage::

    manager = DomainManager(session)
    filters = await manager.get_domain_filters("gst")
    if filters:
        pinecone_filter = {"topic_tags": {"$in": filters.topic_tags}}
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.repository import TaxDomainRepository
from app.modules.knowledge.retrieval.query_router import (
    _DOMAIN_ALIAS_PATTERNS,
    _DOMAIN_PATTERNS,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Domain Filters Dataclass
# =============================================================================


@dataclass(frozen=True)
class DomainFilters:
    """Scoped retrieval filters for a specialist tax domain.

    Attributes:
        topic_tags: Content tags that belong to this domain (e.g.
            ``["GST", "BAS", "input_tax_credit"]``).  Used as a
            Pinecone ``topic_tags $in`` metadata filter.
        legislation_refs: Legislation references associated with this
            domain (e.g. ``["GST Act 1999"]``).
        ruling_types: ATO ruling type prefixes relevant to this domain
            (e.g. ``["GSTR", "GSTD"]``).
    """

    topic_tags: list[str] = field(default_factory=list)
    legislation_refs: list[str] = field(default_factory=list)
    ruling_types: list[str] = field(default_factory=list)


# =============================================================================
# In-Memory TTL Cache
# =============================================================================

# Module-level cache shared across DomainManager instances.
# Key: domain slug, Value: (timestamp, DomainFilters)
_domain_cache: dict[str, tuple[float, DomainFilters]] = {}

# Cache TTL in seconds (5 minutes).
_CACHE_TTL: int = 300


def _get_cached(slug: str) -> DomainFilters | None:
    """Return cached DomainFilters if present and not expired."""
    entry = _domain_cache.get(slug)
    if entry is None:
        return None
    cached_at, filters = entry
    if (time.monotonic() - cached_at) > _CACHE_TTL:
        # Expired -- remove and return None
        _domain_cache.pop(slug, None)
        return None
    return filters


def _set_cached(slug: str, filters: DomainFilters) -> None:
    """Store DomainFilters in the cache with the current timestamp."""
    _domain_cache[slug] = (time.monotonic(), filters)


def invalidate_cache(slug: str | None = None) -> None:
    """Invalidate cached domain filters.

    Args:
        slug: If provided, invalidate only this domain's cache entry.
            If ``None``, clear the entire cache.
    """
    if slug is None:
        _domain_cache.clear()
    else:
        _domain_cache.pop(slug, None)


# =============================================================================
# Domain Manager
# =============================================================================


class DomainManager:
    """Manages specialist tax domain configuration and scoped retrieval.

    Loads domain data from the ``tax_domains`` database table via
    :class:`TaxDomainRepository` and provides convenient accessors
    for the search pipeline.

    Args:
        session: Async SQLAlchemy database session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._repo = TaxDomainRepository(session)

    # -----------------------------------------------------------------
    # Get domain filters (async -- may hit DB on cache miss)
    # -----------------------------------------------------------------

    async def get_domain_filters(self, slug: str) -> DomainFilters | None:
        """Load domain filters for a given domain slug.

        Returns cached results when available; falls back to a DB
        lookup on cache miss or expiry.

        Args:
            slug: Domain slug (e.g. ``"gst"``, ``"division_7a"``).

        Returns:
            :class:`DomainFilters` for the domain, or ``None`` if the
            slug does not match any domain in the database.
        """
        # Check cache first
        cached = _get_cached(slug)
        if cached is not None:
            return cached

        # Cache miss -- load from DB
        domain = await self._repo.get_by_slug(slug)
        if domain is None:
            logger.debug("Domain not found in DB: slug=%s", slug)
            return None

        filters = DomainFilters(
            topic_tags=list(domain.topic_tags or []),
            legislation_refs=list(domain.legislation_refs or []),
            ruling_types=list(domain.ruling_types or []),
        )

        _set_cached(slug, filters)

        logger.debug(
            "Loaded domain filters: slug=%s tags=%s",
            slug,
            filters.topic_tags,
        )
        return filters

    # -----------------------------------------------------------------
    # Detect domain from query (sync -- no DB calls, uses regex cache)
    # -----------------------------------------------------------------

    @staticmethod
    def detect_domain(query: str) -> str | None:
        """Auto-detect the tax domain from query text via keyword matching.

        This is a **synchronous** method that performs no I/O.  It
        reuses the compiled regex patterns from
        :mod:`~app.modules.knowledge.retrieval.query_router` to keep
        the keyword mapping in a single place.

        The algorithm scores each domain by counting regex matches
        against its topic tag patterns and common alias patterns, then
        returns the domain slug with the highest score.  Returns
        ``None`` when no domain keywords are detected.

        Args:
            query: Raw user query text.

        Returns:
            Domain slug string (e.g. ``"gst"``, ``"cgt"``) or ``None``.
        """
        domain_scores: dict[str, int] = {}

        # Check compiled topic tag patterns
        for slug, patterns in _DOMAIN_PATTERNS.items():
            score = sum(1 for p in patterns if p.search(query))
            if score > 0:
                domain_scores[slug] = domain_scores.get(slug, 0) + score

        # Check alias patterns for broader coverage
        for slug, patterns in _DOMAIN_ALIAS_PATTERNS.items():
            score = sum(1 for p in patterns if p.search(query))
            if score > 0:
                domain_scores[slug] = domain_scores.get(slug, 0) + score

        if not domain_scores:
            return None

        # Return the domain with the highest score
        return max(domain_scores, key=lambda k: domain_scores[k])

    # -----------------------------------------------------------------
    # List all domains (async)
    # -----------------------------------------------------------------

    async def get_all_domains(self, active_only: bool = True) -> list[dict]:
        """Load all domains from the database.

        Args:
            active_only: If ``True`` (default), only return domains
                where ``is_active`` is True.

        Returns:
            List of serialised domain dicts, each containing slug,
            name, description, topic_tags, legislation_refs,
            ruling_types, icon, display_order, and is_active.
        """
        if active_only:
            domains = await self._repo.list_active()
        else:
            # list_active already filters by is_active; for the
            # non-active case we'd need a separate repo method.
            # For now use list_active -- matches KnowledgeService behaviour.
            domains = await self._repo.list_active()

        return [
            {
                "slug": d.slug,
                "name": d.name,
                "description": d.description,
                "topic_tags": list(d.topic_tags or []),
                "legislation_refs": list(d.legislation_refs or []),
                "ruling_types": list(d.ruling_types or []),
                "icon": d.icon,
                "display_order": d.display_order,
                "is_active": d.is_active,
            }
            for d in domains
        ]
