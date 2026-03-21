"""Case law scraper for Australian tax cases.

Ingests tax-relevant court decisions from two sources:

1. **Open Australian Legal Corpus** (HuggingFace):
   One-time bulk load from a CC BY 4.0 JSONL dataset containing
   Australian court decisions.  Tax-relevant cases are identified
   using keyword-based classification.

2. **Federal Court RSS feed**:
   Ongoing monitoring of new judgments from the Federal Court of
   Australia for tax-related decisions.

Both sources produce :class:`ScrapedContent` objects with case metadata
(citation, court, date, legislation considered) and a natural key of
``case_law:{case_citation}``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import feedparser

from app.modules.knowledge.scrapers.base import (
    BaseScraper,
    ScrapedContent,
    ScraperConfig,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

# Federal Court of Australia decisions RSS feed.
# Moved from www.fedcourt.gov.au to the judgments subdomain circa 2025.
FEDERAL_COURT_RSS_URL = "https://www.judgments.fedcourt.gov.au/rss/fca-judgments"

# HuggingFace dataset identifier for the Open Australian Legal Corpus.
OPEN_LEGAL_CORPUS_DATASET = "umarbutler/open-australian-legal-corpus"

# Placeholder URL prefix used to represent JSONL entries from the
# HuggingFace corpus in get_content_urls (since they don't have real URLs).
_CORPUS_URL_PREFIX = "huggingface://open-australian-legal-corpus/"

# Keywords used to classify whether a case is tax-relevant.
# Any case whose text contains at least one of these (case-insensitive)
# is considered tax-related and will be ingested.
TAX_RELEVANCE_KEYWORDS: list[str] = [
    "tax",
    "GST",
    "income tax",
    "deduction",
    "capital gain",
    "ATO",
    "Commissioner of Taxation",
    "assessable income",
    "fringe benefit",
]

# Pre-compiled pattern for fast tax-relevance scanning.
_TAX_RELEVANCE_PATTERN = re.compile(
    "|".join(re.escape(kw) for kw in TAX_RELEVANCE_KEYWORDS),
    re.IGNORECASE,
)

# Court abbreviation normalisation mapping.
# Maps common variations found in citations / metadata to canonical short forms.
_COURT_NORMALISATION: dict[str, str] = {
    "high court of australia": "HCA",
    "hca": "HCA",
    "federal court of australia": "FCA",
    "fca": "FCA",
    "full federal court": "FCAFC",
    "full court of the federal court": "FCAFC",
    "fcafc": "FCAFC",
    "administrative appeals tribunal": "AATA",
    "aata": "AATA",
    "aat": "AATA",
    "administrative review tribunal": "ART",
    "art": "ART",
}

# Pattern to extract a standard Australian case citation from text.
# Matches formats like "[2010] HCA 10, [2024] FCA 123, etc.
_CITATION_PATTERN = re.compile(
    r"\[(\d{4})\]\s+(HCA|FCA|FCAFC|AATA|ART|NSWSC|VSC|QSC|WASC|SASC|TASSC)\s+(\d+)",
)

# Legislation references found in case text.
_LEGISLATION_REF_PATTERN = re.compile(
    r"""(?:
        (?:Income\s+Tax\s+Assessment\s+Act|ITAA)\s*(?:19(?:36|97))? |
        (?:A\s+New\s+Tax\s+System\s+\(Goods\s+and\s+Services\s+Tax\)\s+Act|GST\s+Act)\s*(?:1999)? |
        (?:Fringe\s+Benefits\s+Tax\s+Assessment\s+Act|FBTAA)\s*(?:1986)? |
        (?:Taxation\s+Administration\s+Act|TAA)\s*(?:1953)? |
        (?:Superannuation\s+Industry\s+\(Supervision\)\s+Act|SIS\s+Act)\s*(?:1993)? |
        (?:Superannuation\s+Guarantee\s+\(Administration\)\s+Act|SGAA)\s*(?:1992)?
    )""",
    re.VERBOSE | re.IGNORECASE,
)

# Mapping from legislation reference keywords to topic tags.
_LEGISLATION_TOPIC_MAP: dict[str, list[str]] = {
    "income tax": ["income_tax"],
    "itaa": ["income_tax"],
    "gst": ["gst"],
    "goods and services tax": ["gst"],
    "fringe benefit": ["fbt", "fringe_benefits"],
    "fbtaa": ["fbt", "fringe_benefits"],
    "superannuation": ["superannuation"],
    "sis act": ["superannuation", "smsf"],
    "sgaa": ["superannuation", "sg"],
    "taxation administration": ["tax_administration"],
    "taa": ["tax_administration"],
}


@dataclass
class _CorpusEntry:
    """Lightweight representation of a JSONL entry from the HuggingFace corpus."""

    citation: str
    text: str
    court: str | None = None
    date: str | None = None
    url: str | None = None
    metadata: dict = field(default_factory=dict)


class CaseLawScraper(BaseScraper):
    """Scraper for Australian tax case law.

    Supports two data sources controlled by ``source_config``:

    - ``source: "open_legal_corpus"`` -- bulk load from HuggingFace JSONL
    - ``source: "federal_court_rss"`` -- ongoing Federal Court RSS feed
    - ``source: "both"`` -- run both sources sequentially (default)

    Additional config keys:

    - ``filter_tax_only``: When ``True`` (default), only tax-relevant
      cases are yielded.  Set to ``False`` to ingest all cases.
    - ``corpus_path``: Local filesystem path to the JSONL file for
      the Open Australian Legal Corpus.  Required when source includes
      ``open_legal_corpus``.
    """

    def __init__(
        self,
        config: ScraperConfig | None = None,
        source_config: dict | None = None,
    ) -> None:
        """Initialise the case law scraper.

        Args:
            config: Scraper configuration.
            source_config: Source-specific configuration.
        """
        super().__init__(config or ScraperConfig(), source_config)

        self._source: str = self.source_config.get("source", "both")
        self._filter_tax_only: bool = self.source_config.get("filter_tax_only", True)
        self._corpus_path: str | None = self.source_config.get("corpus_path")

    # ------------------------------------------------------------------
    # Abstract property implementations
    # ------------------------------------------------------------------

    @property
    def source_type(self) -> str:
        """Return the source type identifier."""
        return "case_law"

    @property
    def collection_name(self) -> str:
        """Return the target collection name."""
        return "compliance_knowledge"

    # ------------------------------------------------------------------
    # URL Discovery
    # ------------------------------------------------------------------

    async def get_content_urls(self) -> AsyncIterator[str]:
        """Yield URLs / placeholder identifiers for case law content.

        For the Federal Court RSS feed, this yields the actual judgment
        page URLs.  For the HuggingFace corpus, this yields placeholder
        URLs prefixed with ``huggingface://`` that are mapped to JSONL
        entries during extraction.

        Yields:
            Content identifiers (URLs or placeholders).
        """
        if self._source in ("federal_court_rss", "both"):
            async for url in self._get_federal_court_urls():
                yield url

        # HuggingFace corpus URLs are generated during scrape_all
        # rather than here, because entries are read from the JSONL file.

    async def _get_federal_court_urls(self) -> AsyncIterator[str]:
        """Parse the Federal Court RSS feed and yield judgment URLs.

        Yields:
            Judgment page URLs from the RSS feed.
        """
        logger.info("Fetching Federal Court RSS feed: %s", FEDERAL_COURT_RSS_URL)

        feed_content = await self.fetch_feed(FEDERAL_COURT_RSS_URL)
        if not feed_content:
            logger.warning("Empty response from Federal Court RSS feed")
            return

        feed = feedparser.parse(feed_content)

        for entry in feed.entries:
            url = getattr(entry, "link", None)
            if url:
                yield url

    # ------------------------------------------------------------------
    # Content Extraction
    # ------------------------------------------------------------------

    async def extract_content(self, url: str, html: str) -> ScrapedContent | None:
        """Extract case content from a Federal Court judgment page.

        Args:
            url: The judgment page URL.
            html: Raw HTML content.

        Returns:
            ScrapedContent with case metadata, or None if the case
            should be skipped (e.g. not tax-relevant).
        """
        soup = self.clean_html(html)
        title = self.extract_title(soup) or ""
        text = self.extract_text(soup)

        if not text or len(text) < 100:
            logger.debug("Insufficient content for case at %s", url)
            return None

        # Tax relevance filter
        if self._filter_tax_only and not self._is_tax_relevant(text, title):
            logger.debug("Skipping non-tax case: %s", url)
            return None

        # Extract case metadata
        citation = self._extract_citation(text, title)
        court = self._detect_court(text, title)
        case_date = self._extract_case_date(soup, text)
        legislation_considered = self._extract_legislation_refs(text)
        topic_tags = self._derive_topic_tags(legislation_considered)

        # Build natural key from citation (or URL hash as fallback)
        if citation:
            safe_citation = re.sub(r"[\[\]\s]+", "-", citation).strip("-")
            natural_key = f"case_law:{safe_citation}"
        else:
            url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
            natural_key = f"case_law:{url_hash}"

        document_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        return ScrapedContent(
            source_url=url,
            title=title or citation or "Unknown Case",
            text=text,
            html=str(soup),
            source_type="case_law",
            collection_namespace=self.collection_name,
            effective_date=case_date,
            confidence_level="high",
            raw_metadata={
                "natural_key": natural_key,
                "document_hash": document_hash,
                "case_citation": citation,
                "court": court,
                "legislation_considered": legislation_considered,
                "topic_tags": topic_tags,
            },
        )

    # ------------------------------------------------------------------
    # Overridden scrape_all to handle both sources
    # ------------------------------------------------------------------

    async def scrape_all(self) -> AsyncIterator[ScrapedContent]:
        """Scrape all case law content from configured sources.

        Handles both the Federal Court RSS feed and the HuggingFace
        Open Australian Legal Corpus.

        Yields:
            ScrapedContent objects for each tax-relevant case.
        """
        # Source 1: Federal Court RSS feed
        if self._source in ("federal_court_rss", "both"):
            logger.info("Scraping Federal Court RSS feed")
            async for url in self._get_federal_court_urls():
                try:
                    content = await self.scrape_url(url)
                    if content:
                        yield content
                except Exception:
                    logger.warning(
                        "Failed to scrape Federal Court case: %s",
                        url,
                        exc_info=True,
                    )
                    continue

        # Source 2: Open Australian Legal Corpus (JSONL)
        if self._source in ("open_legal_corpus", "both"):
            async for content in self._scrape_legal_corpus():
                yield content

    async def _scrape_legal_corpus(self) -> AsyncIterator[ScrapedContent]:
        """Load and filter tax-relevant cases from the HuggingFace corpus.

        Reads the JSONL file line-by-line, parses each entry, applies
        the tax-relevance filter, and yields ScrapedContent objects.

        Yields:
            ScrapedContent for each tax-relevant case in the corpus.
        """
        if not self._corpus_path:
            logger.warning(
                "No corpus_path configured for Open Australian Legal Corpus. "
                "Set source_config.corpus_path to the JSONL file path."
            )
            return

        logger.info(
            "Loading Open Australian Legal Corpus from: %s",
            self._corpus_path,
        )

        line_count = 0
        tax_count = 0

        try:
            # Intentionally using blocking I/O for line-by-line JSONL reading
            # from a local file.  The corpus can be hundreds of MB and is read
            # synchronously to avoid loading it entirely into memory.
            with Path(self._corpus_path).open(encoding="utf-8") as f:  # noqa: ASYNC230
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    line_count += 1

                    try:
                        entry = self._parse_corpus_entry(line)
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.debug(
                            "Skipping malformed JSONL entry at line %d: %s",
                            line_count,
                            e,
                        )
                        continue

                    if not entry.text or len(entry.text) < 100:
                        continue

                    # Apply tax-relevance filter
                    if self._filter_tax_only and not self._is_tax_relevant(
                        entry.text, entry.citation
                    ):
                        continue

                    tax_count += 1
                    content = self._corpus_entry_to_scraped_content(entry)
                    if content:
                        yield content

        except FileNotFoundError:
            logger.error("Corpus JSONL file not found: %s", self._corpus_path)
            return

        logger.info(
            "Processed %d corpus entries; %d were tax-relevant",
            line_count,
            tax_count,
        )

    # ------------------------------------------------------------------
    # JSONL Parsing Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_corpus_entry(line: str) -> _CorpusEntry:
        """Parse a single JSONL line from the Open Australian Legal Corpus.

        The corpus format uses fields like ``citation``, ``text``,
        ``jurisdiction``, ``court``, ``date``, and ``url``.

        Args:
            line: A single JSON line from the JSONL file.

        Returns:
            Parsed corpus entry.

        Raises:
            json.JSONDecodeError: If the line is not valid JSON.
            KeyError: If required fields are missing.
        """
        data = json.loads(line)

        return _CorpusEntry(
            citation=data.get("citation", data.get("title", "")),
            text=data.get("text", ""),
            court=data.get("court"),
            date=data.get("date"),
            url=data.get("url"),
            metadata={
                k: v
                for k, v in data.items()
                if k not in ("text", "citation", "court", "date", "url")
            },
        )

    def _corpus_entry_to_scraped_content(self, entry: _CorpusEntry) -> ScrapedContent | None:
        """Convert a parsed corpus entry to a ScrapedContent object.

        Args:
            entry: Parsed JSONL entry.

        Returns:
            ScrapedContent or None if entry cannot be converted.
        """
        citation = entry.citation
        court = self._normalise_court(entry.court) if entry.court else None
        case_date = self._parse_date_string(entry.date) if entry.date else None
        legislation_considered = self._extract_legislation_refs(entry.text)
        topic_tags = self._derive_topic_tags(legislation_considered)

        # Build natural key
        if citation:
            safe_citation = re.sub(r"[\[\]\s]+", "-", citation).strip("-")
            natural_key = f"case_law:{safe_citation}"
        else:
            text_hash = hashlib.sha256(entry.text[:500].encode()).hexdigest()[:16]
            natural_key = f"case_law:{text_hash}"

        document_hash = hashlib.sha256(entry.text.encode("utf-8")).hexdigest()

        source_url = entry.url or f"{_CORPUS_URL_PREFIX}{natural_key}"

        return ScrapedContent(
            source_url=source_url,
            title=citation or "Unknown Case",
            text=entry.text,
            source_type="case_law",
            collection_namespace=self.collection_name,
            effective_date=case_date,
            confidence_level="high",
            raw_metadata={
                "natural_key": natural_key,
                "document_hash": document_hash,
                "case_citation": citation,
                "court": court,
                "legislation_considered": legislation_considered,
                "topic_tags": topic_tags,
                "corpus_metadata": entry.metadata,
            },
        )

    # ------------------------------------------------------------------
    # Tax Relevance Classification
    # ------------------------------------------------------------------

    @staticmethod
    def _is_tax_relevant(text: str, title: str = "") -> bool:
        """Determine whether a case is tax-relevant.

        Uses keyword-based classification, checking the case text and
        title against :data:`TAX_RELEVANCE_KEYWORDS`.

        Args:
            text: Full case text (or a significant portion of it).
            title: Case title or citation.

        Returns:
            True if the case is classified as tax-relevant.
        """
        # Check the title and the first portion of the text for efficiency.
        # Most tax cases will mention key terms within the first few thousand
        # characters.
        search_text = f"{title} {text[:5000]}"
        return bool(_TAX_RELEVANCE_PATTERN.search(search_text))

    # ------------------------------------------------------------------
    # Metadata Extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_citation(text: str, title: str = "") -> str | None:
        """Extract the primary case citation.

        Looks for standard citation formats like ``[2010] HCA 10``
        in the title and first portion of the text.

        Args:
            text: Case text.
            title: Case title.

        Returns:
            Citation string or None.
        """
        search_text = f"{title} {text[:2000]}"
        match = _CITATION_PATTERN.search(search_text)
        if match:
            return match.group(0)
        return None

    @staticmethod
    def _detect_court(text: str, title: str = "") -> str | None:
        """Detect the court from the case text or title.

        Checks for court name patterns and normalises to a canonical
        abbreviation (HCA, FCA, FCAFC, AATA).

        Args:
            text: Case text.
            title: Case title.

        Returns:
            Court abbreviation or None.
        """
        search_text = f"{title} {text[:3000]}".lower()

        for keyword, abbreviation in _COURT_NORMALISATION.items():
            if keyword in search_text:
                return abbreviation

        # Try extracting from citation pattern
        match = _CITATION_PATTERN.search(f"{title} {text[:2000]}")
        if match:
            return match.group(2)

        return None

    @staticmethod
    def _normalise_court(court_name: str | None) -> str | None:
        """Normalise a court name to its canonical abbreviation.

        Args:
            court_name: Raw court name string.

        Returns:
            Canonical court abbreviation or None.
        """
        if not court_name:
            return None

        key = court_name.strip().lower()
        return _COURT_NORMALISATION.get(key, court_name.upper())

    def _extract_case_date(
        self,
        soup: object,
        text: str,  # noqa: ARG002
    ) -> datetime | None:
        """Extract the case decision date.

        Tries multiple strategies: citation year and common date patterns
        in the text.  The ``soup`` parameter is accepted for interface
        consistency with future enhancements (e.g. meta tag extraction).

        Args:
            soup: Parsed HTML (reserved for future use).
            text: Full case text.

        Returns:
            Timezone-aware datetime or None.
        """
        # Strategy 1: Extract year from citation
        match = _CITATION_PATTERN.search(text[:2000])
        if match:
            year = int(match.group(1))
            try:
                return datetime(year, 1, 1, tzinfo=UTC)
            except ValueError:
                pass

        # Strategy 2: Common date patterns in text
        date_pattern = re.compile(
            r"(?:delivered|decided|judgment\s+date|date\s+of\s+(?:judgment|decision))"
            r"\s*:?\s*(\d{1,2}\s+\w+\s+\d{4})",
            re.IGNORECASE,
        )
        date_match = date_pattern.search(text[:5000])
        if date_match:
            parsed = self._parse_date_string(date_match.group(1))
            if parsed:
                return parsed

        return None

    @staticmethod
    def _parse_date_string(date_str: str | None) -> datetime | None:
        """Parse a date string in common Australian formats.

        Args:
            date_str: Date string.

        Returns:
            Timezone-aware datetime or None.
        """
        if not date_str:
            return None

        date_str = date_str.strip()
        formats = [
            "%d %B %Y",  # 1 July 2024
            "%d %b %Y",  # 1 Jul 2024
            "%d/%m/%Y",  # 01/07/2024
            "%Y-%m-%d",  # 2024-07-01
            "%Y",  # 2024 (year only)
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).replace(tzinfo=UTC)
            except ValueError:
                continue

        logger.debug("Could not parse date: '%s'", date_str)
        return None

    @staticmethod
    def _extract_legislation_refs(text: str) -> list[str]:
        """Extract legislation references mentioned in the case text.

        Args:
            text: Case text.

        Returns:
            De-duplicated list of legislation reference strings.
        """
        refs: list[str] = []
        for match in _LEGISLATION_REF_PATTERN.finditer(text[:10000]):
            ref = match.group(0).strip()
            if ref not in refs:
                refs.append(ref)
        return refs

    @staticmethod
    def _derive_topic_tags(legislation_refs: list[str]) -> list[str]:
        """Derive topic tags from legislation references.

        Maps each legislation reference to known topic tags based on
        keyword matching.

        Args:
            legislation_refs: List of legislation reference strings.

        Returns:
            De-duplicated list of topic tag strings.
        """
        tags: list[str] = []
        combined = " ".join(legislation_refs).lower()

        for keyword, keyword_tags in _LEGISLATION_TOPIC_MAP.items():
            if keyword in combined:
                for tag in keyword_tags:
                    if tag not in tags:
                        tags.append(tag)

        return tags
