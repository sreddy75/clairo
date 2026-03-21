"""ATO Legal Database scraper for tax rulings, determinations, and guidelines.

Scrapes content from the ATO Legal Database (www.ato.gov.au/law) including:
- Tax Rulings (TR/TXR)
- Tax Determinations (TD/TXD)
- GST Rulings and Determinations (GSTR/GSTD/GST)
- Class Rulings (CR/CLR)
- Product Rulings (PR/PRR)
- ATO Guidelines / Compendiums of Guidelines (COG)
- Practical Compliance Guidelines (PCG/TPA)
- ATO Interpretive Decisions (AID)
- Private Rulings (PSR)
- Superannuation Rulings (SGR/SRB)
- Law Administration Practice Statements (PS LA/SAV)

Uses the ATO Legal Database's print-friendly URL pattern for clean HTML extraction:
``/law/view/print?DocID={docid}&PiT=99991231235958``

Rate limited to 0.5 requests/sec (2-second interval) to be respectful of ATO servers.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup, Tag

from app.modules.knowledge.scrapers.base import (
    BaseScraper,
    ScrapedContent,
    ScraperConfig,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

# ATO Legal Database base URL
ATO_LEGAL_DB_BASE = "https://www.ato.gov.au/law"

# Print-friendly URL template for clean HTML extraction.
# PiT=99991231235958 requests the "latest in time" version.
ATO_PRINT_URL_TEMPLATE = "{base}/view/print?DocID={doc_id}&PiT=99991231235958"

# "What's New" page — lists recently published documents with DocID links.
# This replaced the old browse URL which now redirects to an internal SPA.
ATO_WHATS_NEW_URL = "https://www.ato.gov.au/law/view/whatsnew.htm"

# DocID template for constructing URLs for known ruling types/years.
# Used for enumerating recent rulings when "What's New" doesn't cover them.
ATO_DOC_ID_TEMPLATE = "{prefix}/{ruling_code}{year}{number}/NAT/ATO/00001"

# Mapping from canonical prefix to ruling code used in DocIDs.
_PREFIX_TO_DOC_CODE: dict[str, str] = {
    "TXR": "TR",
    "TXD": "TD",
    "GST": "GSTR",
    "CLR": "CR",
    "PRR": "PR",
    "COG": "PCG",
    "TPA": "PCG",
    "SRB": "SGR",
    "AID": "AID",
}

# Default ruling type prefixes to scrape.
# Each prefix corresponds to a category in the ATO Legal Database.
DEFAULT_RULING_TYPE_PREFIXES = [
    "TXR",  # Tax Rulings
    "TXD",  # Tax Determinations
    "GST",  # GST Rulings and Determinations (GSTR, GSTD)
    "CLR",  # Class Rulings
    "PRR",  # Product Rulings
    "COG",  # Compendium of Guidelines
    "TPA",  # Practical Compliance Guidelines (PCG)
    "AID",  # ATO Interpretive Decisions
    "PSR",  # Private Rulings (published versions)
    "SRB",  # Superannuation Rulings (SGR)
    "SAV",  # Law Administration Practice Statements (PS LA)
]

# Mapping of ruling type prefix to topic tags for metadata enrichment.
_PREFIX_TOPIC_MAP: dict[str, list[str]] = {
    "TXR": ["income_tax"],
    "TXD": ["income_tax"],
    "GST": ["gst"],
    "GSTR": ["gst"],
    "GSTD": ["gst"],
    "CLR": ["class_ruling"],
    "PRR": ["product_ruling"],
    "COG": ["ato_guideline"],
    "TPA": ["practical_compliance"],
    "PCG": ["practical_compliance"],
    "AID": ["interpretive_decision"],
    "PSR": ["private_ruling"],
    "SRB": ["superannuation", "smsf"],
    "SGR": ["superannuation", "smsf"],
    "SAV": ["law_administration"],
    "PSLA": ["law_administration"],
}

# Regex patterns for extracting ruling numbers from text/URLs.
_RULING_NUMBER_PATTERNS = [
    # Standard ruling formats: TR 2024/1, GSTR 2000/1, TD 2024/1, etc.
    re.compile(
        r"\b((?:TR|GSTR|GSTD|TD|PCG|SGR|CR|PR|PS\s*LA)\s*\d{4}/\d+(?:A\d+)?)\b",
        re.IGNORECASE,
    ),
    # AID format: ATO-ID 2024/1
    re.compile(r"\b(ATO[-\s]?ID\s*\d{4}/\d+)\b", re.IGNORECASE),
    # DocID-based ruling numbers embedded in URLs
    re.compile(r"DocID=([A-Z]+\d+)", re.IGNORECASE),
]

# Patterns for detecting withdrawn/superseded status in page content.
_STATUS_PATTERNS = {
    "withdrawn": [
        re.compile(
            r"this\s+(?:ruling|determination|guideline)\s+(?:has\s+been\s+|was\s+)?withdrawn",
            re.IGNORECASE,
        ),
        re.compile(r"(?:ruling|determination)\s+withdrawn", re.IGNORECASE),
        re.compile(r"status:\s*withdrawn", re.IGNORECASE),
    ],
    "superseded": [
        re.compile(
            r"this\s+(?:ruling|determination)\s+(?:has\s+been\s+|is\s+)?superseded\s+by\s+(\S+)",
            re.IGNORECASE,
        ),
        re.compile(r"superseded\s+by\s+(\S+)", re.IGNORECASE),
        re.compile(r"status:\s*superseded", re.IGNORECASE),
    ],
    "draft": [
        re.compile(r"\bdraft\s+(?:ruling|determination|guideline)\b", re.IGNORECASE),
        re.compile(r"status:\s*draft", re.IGNORECASE),
    ],
}


class ATOLegalDatabaseScraper(BaseScraper):
    """Scraper for the ATO Legal Database.

    Crawls ATO rulings, determinations, guidelines, and other legal documents
    from the ATO Legal Database. Uses print-friendly URLs for clean HTML
    extraction and supports configurable ruling type prefixes.

    Configuration via ``source_config``:
        - ``ruling_types``: List of ruling type prefixes to scrape
          (default: all types).
        - ``doc_ids``: List of specific DocIDs to scrape directly,
          bypassing type-based discovery.
        - ``max_pages_per_type``: Maximum listing pages to crawl per
          ruling type (default: 50).
    """

    def __init__(
        self,
        config: ScraperConfig | None = None,
        source_config: dict | None = None,
    ) -> None:
        """Initialize the ATO Legal Database scraper.

        Overrides base config to enforce a 2-second request interval
        (0.5 requests/sec) as required for ATO Legal Database crawling.

        Args:
            config: Scraper configuration. The ``requests_per_second``
                field is overridden to 0.5 regardless of caller value.
            source_config: Source-specific config with optional keys:
                - ``ruling_types``: list of type prefixes (default: all)
                - ``doc_ids``: list of specific DocIDs to scrape
                - ``max_pages_per_type``: max listing pages per type
        """
        # Force 0.5 requests/sec (2-second interval) for ATO compliance
        ato_config = config or ScraperConfig()
        ato_config.requests_per_second = 0.5

        super().__init__(ato_config, source_config)

        self._base_url = ATO_LEGAL_DB_BASE

        # Configurable ruling types to scrape
        self._ruling_types: list[str] = (
            source_config.get("ruling_types", DEFAULT_RULING_TYPE_PREFIXES)
            if source_config
            else DEFAULT_RULING_TYPE_PREFIXES
        )

        # Optional: specific DocIDs to scrape directly
        self._doc_ids: list[str] = source_config.get("doc_ids", []) if source_config else []

        # Maximum listing pages to crawl per ruling type
        self._max_pages_per_type: int = (
            source_config.get("max_pages_per_type", 50) if source_config else 50
        )

    @property
    def source_type(self) -> str:
        """Return the source type identifier."""
        return "ato_ruling"

    @property
    def collection_name(self) -> str:
        """Return the target collection name."""
        return "compliance_knowledge"

    # =========================================================================
    # URL Discovery
    # =========================================================================

    async def get_content_urls(self) -> AsyncIterator[str]:
        """Yield print-friendly URLs for ATO Legal Database documents.

        Discovery strategy (post-2025 ATO site restructure):
        1. If explicit ``doc_ids`` are configured, yield those directly.
        2. Scrape the "What's New" page for recently published DocIDs.
        3. Enumerate DocIDs for recent years using known ID patterns.

        The old browse URL (``/law/view/browse``) now redirects to an
        internal SPA and is no longer usable for discovery.

        Yields:
            Print-friendly URLs for individual ATO legal documents.
        """
        seen_urls: set[str] = set()

        # Priority 1: Explicit DocIDs from configuration
        if self._doc_ids:
            for doc_id in self._doc_ids:
                url = self._build_print_url(doc_id)
                if url not in seen_urls:
                    seen_urls.add(url)
                    logger.debug("Queuing explicit DocID: %s", doc_id)
                    yield url
            return

        # Priority 2: Discover from "What's New" page
        logger.info("Discovering documents from ATO What's New page")
        async for url in self._discover_from_whats_new():
            if url not in seen_urls:
                seen_urls.add(url)
                yield url

        # Priority 3: Enumerate recent DocIDs by ruling type
        current_year = datetime.now(tz=UTC).year
        years_to_scan = range(current_year, current_year - 3, -1)

        for ruling_type in self._ruling_types:
            doc_code = _PREFIX_TO_DOC_CODE.get(ruling_type)
            if not doc_code:
                continue

            for year in years_to_scan:
                for number in range(1, self._max_pages_per_type + 1):
                    doc_id = ATO_DOC_ID_TEMPLATE.format(
                        prefix=ruling_type,
                        ruling_code=doc_code,
                        year=year,
                        number=number,
                    )
                    url = self._build_print_url(doc_id)
                    if url in seen_urls:
                        continue

                    # Probe the URL to check if the document exists
                    html = await self._fetch_url(url)
                    if not html or len(html) < 200:
                        # No more documents for this type/year combo
                        logger.debug(
                            "No document at %s/%s/%d — stopping enumeration for this year",
                            ruling_type,
                            doc_code,
                            number,
                        )
                        break

                    seen_urls.add(url)
                    yield url

        logger.info(
            "ATO Legal Database discovery complete: %d unique URLs found",
            len(seen_urls),
        )

    async def _discover_from_whats_new(self) -> AsyncIterator[str]:
        """Scrape the ATO 'What's New' page for recently published DocIDs.

        The What's New page lists recent documents with links in the format
        ``/law/view/view.htm?docid=%22{DOC_CODE}%22``.

        Yields:
            Print-friendly URLs for discovered documents.
        """
        html = await self._fetch_url(ATO_WHATS_NEW_URL)
        if not html:
            logger.warning("Empty response from ATO What's New page")
            return

        soup = BeautifulSoup(html, "lxml")

        for link in soup.find_all("a", href=True):
            href = link["href"]

            # Match links with DocID or docid parameters
            if "DocID=" in href or "docId=" in href or "docid=" in href:
                parsed = urlparse(href)
                qs = parse_qs(parsed.query)
                doc_id = qs.get("DocID", qs.get("docId", qs.get("docid", [None])))[0]
                if doc_id:
                    # Strip URL-encoded quotes that wrap the DocID
                    doc_id = doc_id.strip('"').strip("'")
                    url = self._build_print_url(doc_id)
                    yield url

    # =========================================================================
    # Content Extraction
    # =========================================================================

    async def extract_content(self, url: str, html: str) -> ScrapedContent | None:
        """Extract content from an ATO Legal Database print-friendly page.

        Parses the print-friendly HTML to extract:
        - Title and ruling number
        - Document status (current/draft/withdrawn/superseded)
        - Date of effect
        - Structured text preserving Ruling, Explanation, Examples sections
        - Topic tags derived from ruling type prefix

        Args:
            url: The print-friendly URL that was scraped.
            html: Raw HTML content from the print-friendly page.

        Returns:
            ScrapedContent with full metadata, or None if content
            should be skipped (e.g. empty or unparseable page).
        """
        soup = self.clean_html(html)

        # Extract title
        title = self.extract_title(soup)
        if not title:
            logger.debug("No title found for %s", url)
            return None

        # Extract ruling number from URL DocID or page content
        ruling_number = self._extract_ruling_number(url, soup)

        # Extract the main text content, preserving document structure
        text = self._extract_legal_content(soup)
        if not text or len(text) < 50:
            logger.debug("Insufficient content for %s", url)
            return None

        # Detect document status
        status = self._detect_status(soup)
        is_superseded = status in ("superseded", "withdrawn")

        # Extract the superseded_by reference if available
        superseded_by = self._extract_superseded_by(soup)

        # Extract date of effect
        effective_date = self._extract_date_of_effect(soup)

        # Determine the ruling type prefix for topic tag mapping
        prefix = self._extract_prefix(ruling_number, url)
        topic_tags = self._map_prefix_to_tags(prefix)

        # Determine appropriate source_type
        # COG documents are guidelines, not rulings
        doc_source_type = "ato_guide" if prefix == "COG" else "ato_ruling"

        # Build the natural key for idempotent ingestion
        natural_key = (
            f"ruling:{ruling_number}"
            if ruling_number
            else f"ruling:{hashlib.sha256(url.encode()).hexdigest()[:16]}"
        )

        # Compute document hash for change detection
        document_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()

        # Extract entity types from content
        entity_types = self._extract_entity_types(text)

        return ScrapedContent(
            source_url=url,
            title=title,
            text=text,
            html=str(soup),
            source_type=doc_source_type,
            collection_namespace=self.collection_name,
            effective_date=effective_date,
            ruling_number=ruling_number,
            entity_types=entity_types,
            confidence_level="high",
            is_superseded=is_superseded,
            superseded_by=superseded_by,
            raw_metadata={
                "natural_key": natural_key,
                "document_hash": document_hash,
                "status": status,
                "prefix": prefix,
                "topic_tags": topic_tags,
            },
        )

    # =========================================================================
    # Helper: Ruling Number Extraction
    # =========================================================================

    def _extract_ruling_number(self, url: str, soup: BeautifulSoup) -> str | None:
        """Extract the ruling number from the URL DocID or page content.

        Tries multiple strategies in order of reliability:
        1. Parse the DocID query parameter from the URL.
        2. Look for a ruling number in the page title or heading.
        3. Scan the first portion of the body text.

        Args:
            url: The page URL (may contain DocID parameter).
            soup: Parsed HTML content.

        Returns:
            Normalised ruling number (e.g. "TR 2024/1") or None.
        """
        # Strategy 1: Extract from URL DocID parameter
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        doc_id = qs.get("DocID", [None])[0]
        if doc_id:
            ruling = self._parse_ruling_from_doc_id(doc_id)
            if ruling:
                return ruling

        # Strategy 2: Extract from title / heading
        title_text = ""
        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text(strip=True)

        h1 = soup.find("h1")
        if h1:
            title_text += " " + h1.get_text(strip=True)

        for pattern in _RULING_NUMBER_PATTERNS[:2]:
            match = pattern.search(title_text)
            if match:
                return self._normalise_ruling_number(match.group(1))

        # Strategy 3: Scan first 1000 chars of body text
        body_text = soup.get_text()[:1000]
        for pattern in _RULING_NUMBER_PATTERNS[:2]:
            match = pattern.search(body_text)
            if match:
                return self._normalise_ruling_number(match.group(1))

        # Fallback: use the raw DocID if available
        if doc_id:
            return doc_id

        return None

    # =========================================================================
    # Helper: Status Detection
    # =========================================================================

    def _detect_status(self, soup: BeautifulSoup) -> str:
        """Determine the document status from page content.

        Scans the page text for status indicators such as withdrawal
        notices, supersession notices, or draft labels.

        Args:
            soup: Parsed HTML content.

        Returns:
            Status string: "current", "withdrawn", "superseded", or "draft".
        """
        text = soup.get_text()[:3000]

        # Check for withdrawn status first (most restrictive)
        for pattern in _STATUS_PATTERNS["withdrawn"]:
            if pattern.search(text):
                return "withdrawn"

        # Check for superseded status
        for pattern in _STATUS_PATTERNS["superseded"]:
            if pattern.search(text):
                return "superseded"

        # Check for draft status
        for pattern in _STATUS_PATTERNS["draft"]:
            if pattern.search(text):
                return "draft"

        return "current"

    # =========================================================================
    # Helper: Date of Effect Extraction
    # =========================================================================

    def _extract_date_of_effect(self, soup: BeautifulSoup) -> datetime | None:
        """Extract the date of effect from the document.

        Looks for "Date of effect" headings/sections and common date
        patterns in the surrounding text.

        Args:
            soup: Parsed HTML content.

        Returns:
            Effective date as a timezone-aware datetime, or None.
        """
        text = soup.get_text()

        # Look for "Date of Effect" section followed by a date
        date_of_effect_patterns = [
            re.compile(
                r"date\s+of\s+effect[:\s]*(\d{1,2}\s+\w+\s+\d{4})",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?:applies?\s+from|effective\s+from|applies?\s+to\s+(?:years?\s+of\s+income|income\s+years?)\s+commencing)\s+(?:on\s+or\s+after\s+)?(\d{1,2}\s+\w+\s+\d{4})",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?:issued?|gazetted?|published)\s+(?:on\s+)?(\d{1,2}\s+\w+\s+\d{4})",
                re.IGNORECASE,
            ),
            re.compile(
                r"date\s+of\s+effect[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})",
                re.IGNORECASE,
            ),
        ]

        for pattern in date_of_effect_patterns:
            match = pattern.search(text)
            if match:
                date_str = match.group(1)
                parsed = self._parse_date(date_str)
                if parsed:
                    return parsed

        # Try meta tags as a fallback
        for prop in ["datePublished", "article:published_time", "dcterms.issued"]:
            meta = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if meta and meta.get("content"):
                try:
                    return datetime.fromisoformat(meta["content"].replace("Z", "+00:00"))
                except ValueError:
                    continue

        return None

    # =========================================================================
    # Helper: Prefix to Topic Tags Mapping
    # =========================================================================

    @staticmethod
    def _map_prefix_to_tags(prefix: str | None) -> list[str]:
        """Map a ruling type prefix to relevant topic tags.

        Args:
            prefix: Upper-case ruling type prefix (e.g. "TXR", "GST").

        Returns:
            List of topic tag strings. Falls back to an empty list
            if the prefix is unknown.
        """
        if not prefix:
            return []
        return list(_PREFIX_TOPIC_MAP.get(prefix.upper(), []))

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _build_print_url(self, doc_id: str) -> str:
        """Build a print-friendly URL for the given DocID.

        Args:
            doc_id: ATO Legal Database document identifier.

        Returns:
            Fully-qualified print URL.
        """
        return ATO_PRINT_URL_TEMPLATE.format(base=self._base_url, doc_id=doc_id)

    def _extract_doc_ids_from_listing(self, html: str) -> list[str]:
        """Extract document IDs from a listing/search result page.

        Parses the listing HTML looking for links that contain
        ``DocID=`` query parameters.

        Args:
            html: Raw HTML of the listing page.

        Returns:
            List of unique DocID strings found on the page.
        """
        soup = BeautifulSoup(html, "lxml")
        doc_ids: list[str] = []
        seen: set[str] = set()

        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "DocID=" not in href and "docId=" not in href:
                continue

            parsed = urlparse(href)
            qs = parse_qs(parsed.query)
            doc_id = qs.get("DocID", qs.get("docId", [None]))[0]
            if doc_id and doc_id not in seen:
                seen.add(doc_id)
                doc_ids.append(doc_id)

        logger.debug("Found %d DocIDs on listing page", len(doc_ids))
        return doc_ids

    def _extract_legal_content(self, soup: BeautifulSoup) -> str:
        """Extract the main text from the print-friendly legal page.

        Preserves the document structure including labelled sections
        (Ruling, Explanation, Examples, Date of Effect, Appendix).

        Args:
            soup: Cleaned BeautifulSoup object.

        Returns:
            Extracted text with section headings preserved.
        """
        # ATO print pages often use specific containers
        content_selectors = [
            "div.document-content",
            "div.LawBody",
            "div#document",
            "div.body-content",
            "article",
            "main",
        ]

        container = None
        for selector in content_selectors:
            container = soup.select_one(selector)
            if container:
                break

        if container is None:
            # Fallback: use body
            container = soup.find("body")

        if container is None:
            return self.extract_text(soup)

        # Build structured text preserving section headings
        parts: list[str] = []

        for element in container.descendants:
            if not isinstance(element, Tag):
                continue

            # Capture headings to preserve document structure
            if element.name in ("h1", "h2", "h3", "h4"):
                heading_text = element.get_text(strip=True)
                if heading_text:
                    parts.append(f"\n## {heading_text}\n")

            # Capture paragraphs and list items
            elif element.name in ("p", "li"):
                para_text = element.get_text(separator=" ", strip=True)
                if para_text:
                    parts.append(para_text)

            # Capture table rows for structured data
            elif element.name == "tr":
                cells = [td.get_text(strip=True) for td in element.find_all(["td", "th"])]
                if any(cells):
                    parts.append(" | ".join(cells))

        text = "\n".join(parts)

        # Clean up excessive whitespace while preserving structure
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)

        return text.strip()

    def _extract_superseded_by(self, soup: BeautifulSoup) -> str | None:
        """Extract the ruling number that supersedes this document.

        Args:
            soup: Parsed HTML content.

        Returns:
            Superseding ruling number or None.
        """
        text = soup.get_text()[:3000]

        for pattern in _STATUS_PATTERNS["superseded"]:
            match = pattern.search(text)
            if match and match.lastindex and match.lastindex >= 1:
                return self._normalise_ruling_number(match.group(1))

        return None

    def _extract_prefix(self, ruling_number: str | None, url: str) -> str | None:
        """Determine the ruling type prefix from the ruling number or URL.

        Args:
            ruling_number: Extracted ruling number (may be None).
            url: The document URL.

        Returns:
            Upper-case prefix string (e.g. "TXR", "GST") or None.
        """
        if ruling_number:
            # Match the leading alphabetic portion
            match = re.match(r"([A-Za-z]+(?:\s+[A-Za-z]+)?)", ruling_number)
            if match:
                raw = match.group(1).upper().replace(" ", "")
                # Map common ruling abbreviations to our canonical prefixes
                prefix_aliases: dict[str, str] = {
                    "TR": "TXR",
                    "TD": "TXD",
                    "GSTR": "GST",
                    "GSTD": "GST",
                    "CR": "CLR",
                    "PR": "PRR",
                    "PCG": "TPA",
                    "SGR": "SRB",
                    "PSLA": "SAV",
                    "ATOID": "AID",
                }
                return prefix_aliases.get(raw, raw)

        # Try to extract prefix from URL DocID parameter
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        doc_id = qs.get("DocID", [None])[0]
        if doc_id:
            match = re.match(r"([A-Za-z]+)", doc_id)
            if match:
                return match.group(1).upper()

        return None

    def _parse_ruling_from_doc_id(self, doc_id: str) -> str | None:
        """Parse a human-readable ruling number from a DocID.

        ATO DocIDs can contain embedded ruling numbers in various formats.
        This method attempts to extract and normalise them.

        Args:
            doc_id: Raw DocID string.

        Returns:
            Normalised ruling number or None.
        """
        # Common DocID formats:
        # "TXR/TR20241" -> "TR 2024/1"
        # "GST/GSTR20001" -> "GSTR 2000/1"
        # "AID/AID20241234" -> "ATO-ID 2024/1234"

        # Try to match known patterns
        patterns = [
            # TR 2024/1 style
            (
                re.compile(r"(?:TXR|TXD)/?(TR|TD)(\d{4})(\d+)"),
                lambda m: f"{m.group(1)} {m.group(2)}/{m.group(3)}",
            ),
            # GSTR 2000/1 style
            (
                re.compile(r"GST/?(GSTR|GSTD)(\d{4})(\d+)"),
                lambda m: f"{m.group(1)} {m.group(2)}/{m.group(3)}",
            ),
            # CR 2024/1 style
            (
                re.compile(r"CLR/?(CR)(\d{4})(\d+)"),
                lambda m: f"{m.group(1)} {m.group(2)}/{m.group(3)}",
            ),
            # PR 2024/1 style
            (
                re.compile(r"PRR/?(PR)(\d{4})(\d+)"),
                lambda m: f"{m.group(1)} {m.group(2)}/{m.group(3)}",
            ),
            # PCG 2024/1 style
            (
                re.compile(r"TPA/?(PCG)(\d{4})(\d+)"),
                lambda m: f"{m.group(1)} {m.group(2)}/{m.group(3)}",
            ),
            # SGR 2024/1 style
            (
                re.compile(r"SRB/?(SGR)(\d{4})(\d+)"),
                lambda m: f"{m.group(1)} {m.group(2)}/{m.group(3)}",
            ),
            # ATO-ID 2024/1 style
            (
                re.compile(r"AID/?\w*?(\d{4})(\d+)"),
                lambda m: f"ATO-ID {m.group(1)}/{m.group(2)}",
            ),
            # PS LA 2024/1 style
            (
                re.compile(r"SAV/?(PS\s*LA)(\d{4})(\d+)", re.IGNORECASE),
                lambda m: f"PS LA {m.group(2)}/{m.group(3)}",
            ),
        ]

        for pattern, formatter in patterns:
            match = pattern.search(doc_id)
            if match:
                return formatter(match)

        return None

    @staticmethod
    def _normalise_ruling_number(raw: str) -> str:
        """Normalise a ruling number to a canonical form.

        Strips excess whitespace and ensures consistent formatting.

        Args:
            raw: Raw ruling number string.

        Returns:
            Normalised ruling number (e.g. "TR 2024/1").
        """
        # Collapse whitespace
        normalised = re.sub(r"\s+", " ", raw.strip())
        return normalised

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse a date string in common Australian formats.

        Args:
            date_str: Date string to parse.

        Returns:
            Timezone-aware datetime or None if parsing fails.
        """
        formats = [
            "%d %B %Y",  # 1 July 2024
            "%d %b %Y",  # 1 Jul 2024
            "%d/%m/%Y",  # 01/07/2024
            "%d-%m-%Y",  # 01-07-2024
            "%Y-%m-%d",  # 2024-07-01 (ISO)
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).replace(tzinfo=UTC)
            except ValueError:
                continue

        logger.debug("Could not parse date: '%s'", date_str)
        return None

    def _extract_entity_types(self, text: str) -> list[str]:
        """Extract applicable entity types from content.

        Args:
            text: Document text.

        Returns:
            List of entity type strings.
        """
        text_lower = text[:3000].lower()
        entity_types: list[str] = []

        entity_keywords: dict[str, list[str]] = {
            "sole_trader": ["sole trader", "individual", "sole proprietor"],
            "company": ["company", "companies", "corporation", "pty ltd"],
            "trust": ["trust", "trustee", "beneficiary", "unit trust"],
            "partnership": ["partnership", "partner"],
            "smsf": [
                "self managed super",
                "smsf",
                "self-managed superannuation",
            ],
        }

        for entity_type, keywords in entity_keywords.items():
            if any(kw in text_lower for kw in keywords):
                entity_types.append(entity_type)

        return entity_types if entity_types else ["all"]
