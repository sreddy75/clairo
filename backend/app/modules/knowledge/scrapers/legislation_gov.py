"""Legislation.gov.au scraper for Australian tax legislation.

Fetches and parses key Australian tax acts from the Federal Register of
Legislation (legislation.gov.au).  Content is CC BY 4.0 licensed.

The scraper yields one :class:`ScrapedContent` per *section* of each act,
rather than one per act, so that downstream chunkers receive granular,
section-level documents.

Rate limiting
~~~~~~~~~~~~~
legislation.gov.au requires a **10-second crawl delay** (per robots.txt).
The scraper enforces this by setting ``requests_per_second`` to 0.1.

HTML structure
~~~~~~~~~~~~~~
The HTML structure varies significantly across acts.  The parser is
intentionally defensive -- it will skip sections it cannot parse rather
than crash or produce garbage output.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from bs4 import BeautifulSoup, Tag

from app.modules.knowledge.scrapers.base import (
    BaseScraper,
    ScrapedContent,
    ScraperConfig,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Key Australian tax acts and their legislation.gov.au identifiers.
# ---------------------------------------------------------------------------

TAX_ACTS: dict[str, dict[str, str]] = {
    "C2004A05138": {
        "name": "Income Tax Assessment Act 1997",
        "short": "ITAA 1997",
    },
    "C1936A00027": {
        "name": "Income Tax Assessment Act 1936",
        "short": "ITAA 1936",
    },
    "C2004A00446": {
        "name": "A New Tax System (Goods and Services Tax) Act 1999",
        "short": "GST Act",
    },
    "C2004A03401": {
        "name": "Fringe Benefits Tax Assessment Act 1986",
        "short": "FBTAA",
    },
    "C2004A00957": {
        "name": "Taxation Administration Act 1953",
        "short": "TAA 1953",
    },
    "C2004A00534": {
        "name": "Superannuation Industry (Supervision) Act 1993",
        "short": "SIS Act",
    },
    "C2004A00477": {
        "name": "Superannuation Guarantee (Administration) Act 1992",
        "short": "SGAA",
    },
}

# Base URL for the Federal Register of Legislation.
_BASE_URL = "https://www.legislation.gov.au"

# ---------------------------------------------------------------------------
# Division / Part -> topic tag mapping.
# ---------------------------------------------------------------------------

# Mapping of known legislative divisions/parts to topic tags.
# Keys are compiled regex patterns; values are tag lists.
_DIVISION_TAG_RULES: list[tuple[re.Pattern[str], list[str]]] = [
    # ITAA 1936 Division 7A
    (
        re.compile(r"\bDiv(?:ision)?\s*7A\b", re.IGNORECASE),
        ["division_7a", "deemed_dividend"],
    ),
    # CGT (ITAA 1997 Part 3-1, Divisions 100-152)
    (
        re.compile(r"\bPart\s*3[- ]1\b", re.IGNORECASE),
        ["cgt", "capital_gains"],
    ),
    (
        re.compile(r"\bDiv(?:ision)?\s*10[0-4]\b", re.IGNORECASE),
        ["cgt", "capital_gains"],
    ),
    (
        re.compile(r"\bDiv(?:ision)?\s*11[0-8]\b", re.IGNORECASE),
        ["cgt", "capital_gains"],
    ),
    (
        re.compile(r"\bDiv(?:ision)?\s*12[0-6]\b", re.IGNORECASE),
        ["cgt", "capital_gains"],
    ),
    (
        re.compile(r"\bDiv(?:ision)?\s*13[0-6]\b", re.IGNORECASE),
        ["cgt", "capital_gains"],
    ),
    (
        re.compile(r"\bDiv(?:ision)?\s*14[0-9]\b", re.IGNORECASE),
        ["cgt", "capital_gains"],
    ),
    (
        re.compile(r"\bDiv(?:ision)?\s*15[0-2]\b", re.IGNORECASE),
        ["cgt", "capital_gains"],
    ),
    # Depreciation / capital allowances (Div 40, 43)
    (
        re.compile(r"\bDiv(?:ision)?\s*40\b", re.IGNORECASE),
        ["depreciation", "capital_allowances"],
    ),
    (
        re.compile(r"\bDiv(?:ision)?\s*43\b", re.IGNORECASE),
        ["depreciation", "capital_allowances", "capital_works"],
    ),
    # GST (Part 2-5 of GST Act, or any GST Act reference)
    (
        re.compile(r"\bPart\s*2[- ]5\b", re.IGNORECASE),
        ["gst"],
    ),
    # FBT
    (
        re.compile(r"\bfringe\s*benefit", re.IGNORECASE),
        ["fbt", "fringe_benefits"],
    ),
    # Superannuation / SG
    (
        re.compile(r"\bsuperannuation\s*guarantee\b", re.IGNORECASE),
        ["superannuation", "sg"],
    ),
    (
        re.compile(r"\bDiv(?:ision)?\s*29[0-5]\b", re.IGNORECASE),
        ["superannuation"],
    ),
    # Small business (Div 328)
    (
        re.compile(r"\bDiv(?:ision)?\s*328\b", re.IGNORECASE),
        ["small_business"],
    ),
    # Trusts (Div 6, 6AA, 6AABA)
    (
        re.compile(r"\bDiv(?:ision)?\s*6(?:AA(?:BA)?)?(?:\s|$)", re.IGNORECASE),
        ["trusts"],
    ),
    # PAYG instalments (Div 45)
    (
        re.compile(r"\bDiv(?:ision)?\s*45\b", re.IGNORECASE),
        ["payg"],
    ),
    # International tax (Div 770, 820, 830, 840, 850, 855, 860, 870, 880)
    (
        re.compile(r"\bDiv(?:ision)?\s*(?:770|8[2-8]\d)\b", re.IGNORECASE),
        ["international_tax"],
    ),
]

# Patterns for recognising act-specific topics from the short name.
_ACT_TAG_MAP: dict[str, list[str]] = {
    "GST Act": ["gst"],
    "FBTAA": ["fbt", "fringe_benefits"],
    "SIS Act": ["superannuation", "smsf"],
    "SGAA": ["superannuation", "sg"],
    "TAA 1953": ["tax_administration"],
}

# ---------------------------------------------------------------------------
# Section heading patterns used for splitting act HTML into sections.
# ---------------------------------------------------------------------------

# Pattern to match section references such as "109D", "104-10", "6-5".
_SECTION_REF_PATTERN = re.compile(
    r"(?:Section\s+)?(\d+[A-Z]*(?:-\d+[A-Z]*)?)",
    re.IGNORECASE,
)

# Regex for cross-references embedded in section text.
_CROSS_REF_PATTERN = re.compile(
    r"(?:"
    r"[Ss]ection\s+(\d+[A-Z]*(?:-\d+[A-Z]*)?)"
    r"|[Dd]iv(?:ision)?\s+(\d+[A-Z]*)"
    r"|[Pp]art\s+(\d+[A-Z]*(?:-\d+[A-Z]*)?)"
    r"|[Ss]ubdivision\s+(\d+[A-Z]*(?:-\d+[A-Z]*)?)"
    r")"
)


class LegislationGovScraper(BaseScraper):
    """Scraper for Australian tax legislation from legislation.gov.au.

    Fetches the latest HTML compilation of each configured tax act and
    splits it into per-section :class:`ScrapedContent` objects.

    The scraper respects a 10-second crawl delay as required by the site's
    ``robots.txt``.
    """

    def __init__(
        self,
        config: ScraperConfig | None = None,
        source_config: dict | None = None,
    ) -> None:
        """Initialise the legislation scraper.

        Overrides the default rate limit to 0.1 requests/sec (one request
        every 10 seconds) to comply with legislation.gov.au's crawl delay.

        Args:
            config: Scraper configuration.  ``requests_per_second`` is
                forced to 0.1 regardless of the value passed in.
            source_config: Source-specific config with optional keys:
                - ``acts``: list of act IDs to scrape (defaults to all
                  keys in :data:`TAX_ACTS`).
        """
        config = config or ScraperConfig()
        # Enforce the 10-second crawl delay for legislation.gov.au.
        config.requests_per_second = 0.1
        # legislation.gov.au pages can be very large (full act text).
        config.max_content_length = 50_000_000  # 50 MB
        super().__init__(config, source_config)

    # ------------------------------------------------------------------
    # Abstract method implementations
    # ------------------------------------------------------------------

    @property
    def source_type(self) -> str:
        return "legislation"

    @property
    def collection_name(self) -> str:
        return "compliance_knowledge"

    async def get_content_urls(self) -> AsyncIterator[str]:
        """Yield the latest-text URL for each configured act.

        URL pattern:
            ``https://www.legislation.gov.au/{act_id}/latest/text``

        Yields:
            Act page URLs.
        """
        act_ids: list[str] = self.source_config.get("acts", list(TAX_ACTS.keys()))
        for act_id in act_ids:
            if act_id not in TAX_ACTS:
                logger.warning(
                    "Unknown act ID '%s' -- skipping. Known acts: %s",
                    act_id,
                    list(TAX_ACTS.keys()),
                )
                continue
            url = f"{_BASE_URL}/{act_id}/latest/text"
            yield url

    async def extract_content(
        self,
        url: str,
        html: str,  # noqa: ARG002
    ) -> ScrapedContent | None:
        """Extract content from a single legislation page.

        This method returns ``None`` because the scraper overrides
        :meth:`scrape_all` to yield multiple :class:`ScrapedContent`
        objects per act (one per section).  Direct calls to
        ``scrape_url`` therefore do not produce output; callers should
        use ``scrape_all`` instead.

        Args:
            url: Page URL (unused -- required by abstract interface).
            html: Raw HTML (unused -- required by abstract interface).
        """
        # Not used -- scrape_all handles multi-section extraction.
        return None

    # ------------------------------------------------------------------
    # Overridden scrape_all
    # ------------------------------------------------------------------

    async def scrape_all(self) -> AsyncIterator[ScrapedContent]:
        """Scrape all configured acts and yield per-section content.

        For each act:
        1. Fetch the full-text HTML page.
        2. Parse the HTML into individual sections.
        3. Yield a :class:`ScrapedContent` for each parsed section.

        Yields:
            One :class:`ScrapedContent` per legislation section.
        """
        async for url in self.get_content_urls():
            # Derive act_id from the URL.
            act_id = self._act_id_from_url(url)
            if act_id is None:
                logger.warning("Could not determine act ID from URL: %s", url)
                continue

            act_info = TAX_ACTS.get(act_id)
            if act_info is None:
                logger.warning("No act info for ID '%s'", act_id)
                continue

            logger.info(
                "Fetching legislation: %s (%s)",
                act_info["name"],
                act_id,
            )

            try:
                html = await self._fetch_url(url)
            except Exception:
                logger.exception("Failed to fetch legislation page: %s", url)
                continue

            if not html:
                logger.warning("Empty response for %s", url)
                continue

            sections = self._parse_act_sections(html, act_id, act_info)
            logger.info("Parsed %d sections from %s", len(sections), act_info["short"])

            for section_content in sections:
                yield section_content

    # ------------------------------------------------------------------
    # Section parsing
    # ------------------------------------------------------------------

    def _parse_act_sections(
        self,
        html: str,
        act_id: str,
        act_info: dict[str, str],
    ) -> list[ScrapedContent]:
        """Parse full-act HTML into per-section ScrapedContent objects.

        Args:
            html: Raw HTML of the act page.
            act_id: The legislation.gov.au act identifier.
            act_info: Dict with ``name`` and ``short`` keys.

        Returns:
            List of :class:`ScrapedContent`, one per section.
        """
        soup = self.clean_html(html)
        compilation_date, compilation_number = self._extract_compilation_info(soup)

        sections: list[ScrapedContent] = []

        # Strategy 1: look for heading tags that contain section numbers.
        # legislation.gov.au uses various heading levels (h1-h6) as well as
        # styled <p> or <div> elements for section headings.
        section_headings = self._find_section_headings(soup)

        if section_headings:
            sections = self._split_by_headings(
                section_headings,
                act_id,
                act_info,
                compilation_date,
                compilation_number,
            )
        else:
            # Strategy 2 (fallback): attempt a regex-based split on the
            # raw text of the page.  This is less reliable but handles acts
            # whose HTML structure does not use identifiable heading tags.
            logger.info(
                "No heading tags found for %s -- falling back to text-based section splitting",
                act_info["short"],
            )
            sections = self._split_by_text(
                soup,
                act_id,
                act_info,
                compilation_date,
                compilation_number,
            )

        return sections

    def _find_section_headings(self, soup: BeautifulSoup) -> list[tuple[Tag, str, str]]:
        """Locate section heading elements in the HTML.

        Returns a list of ``(tag, section_ref, heading_text)`` tuples
        sorted by document order.
        """
        results: list[tuple[Tag, str, str]] = []

        # Look for headings and bold/strong text that look like section refs.
        heading_tags = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

        for tag in heading_tags:
            text = tag.get_text(strip=True)
            parsed = self._parse_section_heading(text)
            if parsed is not None:
                section_ref, heading = parsed
                results.append((tag, section_ref, heading))

        # Also look for elements with id/name attributes matching section
        # patterns (e.g., id="section-109D").
        if not results:
            for tag in soup.find_all(id=re.compile(r"(?:section|sect|s)-?\d")):
                text = tag.get_text(strip=True)
                parsed = self._parse_section_heading(text)
                if parsed is not None:
                    section_ref, heading = parsed
                    results.append((tag, section_ref, heading))

        return results

    @staticmethod
    def _parse_section_heading(text: str) -> tuple[str, str] | None:
        """Try to parse a section reference and heading from a string.

        Examples of recognised formats:
        - ``"Section 109D"``
        - ``"109D  Amounts treated as dividends"``
        - ``"104-10  CGT event A1: disposal of a CGT asset"``
        - ``"6-5  What this Act is about"``

        Returns:
            ``(section_ref, heading_text)`` or ``None`` if the text does
            not look like a section heading.
        """
        if not text:
            return None

        # Pattern: "Section <ref> <optional heading>" or "<ref> <heading>"
        m = re.match(
            r"(?:Section\s+)?"
            r"(\d+[A-Z]*(?:-\d+[A-Z]*)?)"
            r"(?:\s*[\.\:\u2014\u2013\-]\s*|\s{2,})?"
            r"(.*)",
            text,
            re.IGNORECASE,
        )
        if m:
            section_ref = m.group(1)
            heading = m.group(2).strip() if m.group(2) else ""
            # Sanity check: section ref should start with a digit.
            if section_ref and section_ref[0].isdigit():
                return section_ref, heading

        return None

    def _split_by_headings(
        self,
        headings: list[tuple[Tag, str, str]],
        act_id: str,
        act_info: dict[str, str],
        compilation_date: str | None,
        compilation_number: str | None,
    ) -> list[ScrapedContent]:
        """Split act content at recognised section headings.

        Text between consecutive headings is attributed to the preceding
        heading's section.
        """
        results: list[ScrapedContent] = []

        for idx, (tag, section_ref, heading) in enumerate(headings):
            # Collect text from this heading up to the next one.
            section_parts: list[str] = []
            if heading:
                section_parts.append(f"Section {section_ref} - {heading}")
            else:
                section_parts.append(f"Section {section_ref}")

            # Walk siblings until we hit the next section heading.
            current: Tag | None = tag.next_sibling
            next_heading_tag = headings[idx + 1][0] if idx + 1 < len(headings) else None

            while current is not None:
                if current is next_heading_tag:
                    break
                if isinstance(current, Tag):
                    text = current.get_text(separator="\n", strip=True)
                    if text:
                        section_parts.append(text)
                elif isinstance(current, str):
                    stripped = current.strip()
                    if stripped:
                        section_parts.append(stripped)
                current = current.next_sibling

            section_text = "\n\n".join(section_parts)

            # Skip very short sections (likely navigation/empty).
            if len(section_text) < 30:
                continue

            # Detect hierarchical context from the heading's ancestors.
            part, division, subdivision = self._detect_hierarchy(tag)

            content = self._build_section_content(
                section_ref=section_ref,
                heading=heading,
                text=section_text,
                act_id=act_id,
                act_info=act_info,
                part=part,
                division=division,
                subdivision=subdivision,
                compilation_date=compilation_date,
                compilation_number=compilation_number,
            )
            results.append(content)

        return results

    def _split_by_text(
        self,
        soup: BeautifulSoup,
        act_id: str,
        act_info: dict[str, str],
        compilation_date: str | None,
        compilation_number: str | None,
    ) -> list[ScrapedContent]:
        """Fallback: split act text using regex on plain text.

        Less accurate than heading-based splitting, but works when the
        HTML does not contain identifiable heading tags.
        """
        full_text = self.extract_text(soup)
        if not full_text:
            return []

        # Pattern: line starting with a section reference.
        section_splits = re.split(
            r"\n(?=(?:Section\s+)?\d+[A-Z]*(?:-\d+[A-Z]*)?\s)",
            full_text,
        )

        results: list[ScrapedContent] = []
        for chunk_text in section_splits:
            chunk_text = chunk_text.strip()
            if len(chunk_text) < 30:
                continue

            # Try to extract the section ref from the first line.
            first_line = chunk_text.split("\n", 1)[0]
            parsed = self._parse_section_heading(first_line)
            if parsed is None:
                continue

            section_ref, heading = parsed

            content = self._build_section_content(
                section_ref=section_ref,
                heading=heading,
                text=chunk_text,
                act_id=act_id,
                act_info=act_info,
                part=None,
                division=None,
                subdivision=None,
                compilation_date=compilation_date,
                compilation_number=compilation_number,
            )
            results.append(content)

        return results

    # ------------------------------------------------------------------
    # Compilation info
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_compilation_info(
        soup: BeautifulSoup,
    ) -> tuple[str | None, str | None]:
        """Extract compilation date and number from page metadata.

        Looks for metadata in ``<meta>`` tags, the page title, and common
        patterns in header text.

        Returns:
            ``(compilation_date, compilation_number)`` -- either or both
            may be ``None``.
        """
        compilation_date: str | None = None
        compilation_number: str | None = None

        # Try meta tags.
        for meta in soup.find_all("meta"):
            name = (meta.get("name") or meta.get("property") or "").lower()
            value = meta.get("content", "")
            if "compilation" in name and "date" in name:
                compilation_date = value
            elif "compilation" in name and "number" in name:
                compilation_number = value

        # Try page text for patterns like "Compilation No. 123" or
        # "Prepared on 1 July 2025".
        if compilation_date is None or compilation_number is None:
            page_text = soup.get_text(" ", strip=True)[:3000]

            if compilation_number is None:
                m = re.search(
                    r"Compilation\s*(?:No\.?|Number)\s*:?\s*(\d+)",
                    page_text,
                    re.IGNORECASE,
                )
                if m:
                    compilation_number = m.group(1)

            if compilation_date is None:
                m = re.search(
                    r"(?:Prepared\s+on|Compilation\s+date|In force from)"
                    r"\s*:?\s*(\d{1,2}\s+\w+\s+\d{4})",
                    page_text,
                    re.IGNORECASE,
                )
                if m:
                    compilation_date = m.group(1)

        return compilation_date, compilation_number

    # ------------------------------------------------------------------
    # Topic tag mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _map_division_to_tags(
        part: str | None,
        division: str | None,
        act_short_name: str,
    ) -> list[str]:
        """Map legislative division/part and act name to topic tags.

        Args:
            part: Part identifier (e.g., ``"3-1"``).
            division: Division identifier (e.g., ``"7A"``).
            act_short_name: Short act name (e.g., ``"ITAA 1936"``).

        Returns:
            De-duplicated list of topic tags.
        """
        tags: list[str] = []

        # Check act-level tags.
        for act_key, act_tags in _ACT_TAG_MAP.items():
            if act_key in act_short_name:
                tags.extend(act_tags)

        # Build a combined string for regex matching.
        combined = " ".join(
            filter(
                None,
                [
                    f"Part {part}" if part else None,
                    f"Division {division}" if division else None,
                ],
            )
        )

        if combined:
            for pattern, rule_tags in _DIVISION_TAG_RULES:
                if pattern.search(combined):
                    tags.extend(rule_tags)

        # De-duplicate while preserving order.
        seen: set[str] = set()
        unique_tags: list[str] = []
        for t in tags:
            if t not in seen:
                seen.add(t)
                unique_tags.append(t)

        return unique_tags

    # ------------------------------------------------------------------
    # Hierarchy detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_hierarchy(
        tag: Tag,
    ) -> tuple[str | None, str | None, str | None]:
        """Walk up the DOM from a section heading to determine the
        part / division / subdivision context.

        Returns:
            ``(part, division, subdivision)`` -- any may be ``None``.
        """
        part: str | None = None
        division: str | None = None
        subdivision: str | None = None

        # Walk preceding siblings and parents.
        current: Any = tag
        for _ in range(200):  # safety limit
            current = current.previous_element
            if current is None:
                break
            if not isinstance(current, Tag):
                continue

            text = current.get_text(strip=True).lower()

            if subdivision is None:
                m = re.search(
                    r"subdivision\s+(\d+[a-z]*(?:-[a-z0-9]+)*)",
                    text,
                    re.IGNORECASE,
                )
                if m:
                    subdivision = m.group(1).upper()

            if division is None:
                m = re.search(
                    r"division\s+(\d+[a-z]*)",
                    text,
                    re.IGNORECASE,
                )
                if m:
                    division = m.group(1).upper()

            if part is None:
                m = re.search(
                    r"part\s+(\d+[a-z]*(?:-\d+[a-z]*)?)",
                    text,
                    re.IGNORECASE,
                )
                if m:
                    part = m.group(1).upper()

            # Stop early once we have everything.
            if part and division and subdivision:
                break

        return part, division, subdivision

    # ------------------------------------------------------------------
    # Cross-reference extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_cross_references(text: str) -> list[str]:
        """Extract cross-references to other sections/divisions/parts.

        Args:
            text: Section text.

        Returns:
            De-duplicated list of cross-reference strings.
        """
        refs: list[str] = []
        for m in _CROSS_REF_PATTERN.finditer(text):
            if m.group(1):
                refs.append(f"s{m.group(1)}")
            elif m.group(2):
                refs.append(f"Div {m.group(2)}")
            elif m.group(3):
                refs.append(f"Part {m.group(3)}")
            elif m.group(4):
                refs.append(f"Subdiv {m.group(4)}")

        # De-duplicate while preserving order.
        seen: set[str] = set()
        unique: list[str] = []
        for r in refs:
            if r not in seen:
                seen.add(r)
                unique.append(r)

        return unique

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _act_id_from_url(url: str) -> str | None:
        """Extract the act identifier from a legislation.gov.au URL.

        Expects a URL of the form ``.../{act_id}/latest/text``.

        Returns:
            Act identifier string or ``None``.
        """
        for act_id in TAX_ACTS:
            if act_id in url:
                return act_id
        return None

    @staticmethod
    def _compute_document_hash(text: str) -> str:
        """Compute a SHA-256 hash of the section text.

        Used for change detection during incremental re-ingestion.
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _build_section_content(
        self,
        *,
        section_ref: str,
        heading: str,
        text: str,
        act_id: str,
        act_info: dict[str, str],
        part: str | None,
        division: str | None,
        subdivision: str | None,
        compilation_date: str | None,
        compilation_number: str | None,
    ) -> ScrapedContent:
        """Construct a :class:`ScrapedContent` for one legislation section.

        This centralises all per-section metadata construction.
        """
        act_name = act_info["name"]
        act_short = act_info["short"]

        # Compute deterministic keys.
        natural_key = f"legislation:{act_id}:s{section_ref}"
        document_hash = self._compute_document_hash(text)

        # Topic tags.
        topic_tags = self._map_division_to_tags(part, division, act_short)

        # Cross-references.
        cross_references = self._extract_cross_references(text)

        # Build the title.
        title = f"s{section_ref} {act_short}"
        if heading:
            title = f"s{section_ref} {act_short} - {heading}"

        # Parse compilation_date into a datetime if possible.
        effective_date = self._parse_compilation_date(compilation_date)

        source_url = f"{_BASE_URL}/{act_id}/latest/text#s{section_ref}"

        return ScrapedContent(
            source_url=source_url,
            title=title,
            text=text,
            source_type="legislation",
            collection_namespace="compliance_knowledge",
            effective_date=effective_date,
            confidence_level="high",
            raw_metadata={
                "act_id": act_id,
                "act_name": act_name,
                "act_short_name": act_short,
                "section_ref": f"s{section_ref}",
                "part": part,
                "division": division,
                "subdivision": subdivision,
                "compilation_date": compilation_date,
                "compilation_number": compilation_number,
                "natural_key": natural_key,
                "document_hash": document_hash,
                "cross_references": cross_references,
                "topic_tags": topic_tags,
            },
        )

    @staticmethod
    def _parse_compilation_date(date_str: str | None) -> datetime | None:
        """Attempt to parse a compilation date string into a datetime.

        Handles common formats found on legislation.gov.au:
        - ``"1 July 2025"``
        - ``"01/07/2025"``
        - ``"2025-07-01"``

        Returns:
            Timezone-aware ``datetime`` or ``None`` on failure.
        """
        if not date_str:
            return None

        date_str = date_str.strip()
        formats = [
            "%d %B %Y",
            "%d %b %Y",
            "%d/%m/%Y",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).replace(tzinfo=UTC)
            except ValueError:
                continue

        logger.debug("Could not parse compilation date: '%s'", date_str)
        return None
